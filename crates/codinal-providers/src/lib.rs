//! Stable provider identifiers shared with the native Keychain contract.

use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::io::{self, Read, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpStream};
use std::time::Duration;
use zeroize::Zeroizing;

const MAX_BOOTSTRAP_BYTES: usize = 128 * 1024;
const MAX_API_KEY_BYTES: usize = 16 * 1024;
const MAX_BASE_URL_BYTES: usize = 512;
const MAX_PROVIDER_RESPONSE_BYTES: u64 = 2 * 1024 * 1024;
const MAX_TOOL_CALLS: usize = 64;
const MAX_ARGUMENT_BYTES: usize = 1024 * 1024;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ProviderId {
    OpenAi,
    Anthropic,
    Gemini,
    Zai,
    DeepSeek,
    Ollama,
    OmniRoute,
    GitHub,
    Custom(String),
}

impl ProviderId {
    pub fn parse(value: &str) -> Option<Self> {
        Some(match value {
            "openai" => Self::OpenAi,
            "anthropic" => Self::Anthropic,
            "gemini" => Self::Gemini,
            "zai" => Self::Zai,
            "deepseek" => Self::DeepSeek,
            "ollama" => Self::Ollama,
            "omniroute" => Self::OmniRoute,
            "github" => Self::GitHub,
            _ => Self::Custom(value.strip_prefix("custom:")?.to_owned()),
        })
        .filter(|provider| match provider {
            Self::Custom(slug) => valid_custom_slug(slug),
            _ => true,
        })
    }

    pub fn as_keychain_account(&self) -> String {
        match self {
            Self::OpenAi => "openai".to_owned(),
            Self::Anthropic => "anthropic".to_owned(),
            Self::Gemini => "gemini".to_owned(),
            Self::Zai => "zai".to_owned(),
            Self::DeepSeek => "deepseek".to_owned(),
            Self::Ollama => "ollama".to_owned(),
            Self::OmniRoute => "omniroute".to_owned(),
            Self::GitHub => "github".to_owned(),
            Self::Custom(slug) => format!("custom:{slug}"),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct ToolCall {
    pub id: String,
    pub name: String,
    pub arguments: serde_json::Map<String, serde_json::Value>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct AssistantTurn {
    pub text: Option<String>,
    pub tool_calls: Vec<ToolCall>,
    pub finish_reason: Option<String>,
}

pub struct OllamaProvider {
    port: u16,
}

impl OllamaProvider {
    pub fn new(port: u16) -> io::Result<Self> {
        if port == 0 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid Ollama port",
            ));
        }
        Ok(Self { port })
    }

    pub fn complete(
        &self,
        model: &str,
        messages: &[serde_json::Value],
        tools: &[serde_json::Value],
    ) -> io::Result<AssistantTurn> {
        if model.is_empty()
            || model.len() > 256
            || model.chars().any(char::is_control)
            || messages.len() > 10_000
            || tools.len() > 256
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid Ollama request",
            ));
        }
        let body = serde_json::to_vec(&serde_json::json!({
            "model": model,
            "messages": messages,
            "tools": tools,
            "stream": false,
        }))
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "invalid Ollama request"))?;
        if body.len() > MAX_ARGUMENT_BYTES {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "Ollama request exceeds limit",
            ));
        }
        let address = SocketAddrV4::new(Ipv4Addr::LOCALHOST, self.port);
        let mut stream = TcpStream::connect_timeout(&address.into(), Duration::from_secs(2))?;
        stream.set_read_timeout(Some(Duration::from_secs(30)))?;
        stream.set_write_timeout(Some(Duration::from_secs(2)))?;
        write!(
            stream,
            "POST /api/chat HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
            self.port,
            body.len()
        )?;
        stream.write_all(&body)?;
        stream.flush()?;
        let mut response = Vec::new();
        stream
            .take(MAX_PROVIDER_RESPONSE_BYTES + 1)
            .read_to_end(&mut response)?;
        if response.len() as u64 > MAX_PROVIDER_RESPONSE_BYTES {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "Ollama response exceeds limit",
            ));
        }
        parse_ollama_http_response(&response)
    }
}

fn parse_ollama_http_response(response: &[u8]) -> io::Result<AssistantTurn> {
    let split = response
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid Ollama response"))?;
    let headers = std::str::from_utf8(&response[..split])
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid Ollama response"))?;
    if !headers.starts_with("HTTP/1.1 200 OK\r\n") && headers != "HTTP/1.1 200 OK" {
        return Err(io::Error::other("Ollama request failed"));
    }
    let mut content_length = None;
    let mut chunked = false;
    for line in headers.split("\r\n").skip(1) {
        let (name, value) = line
            .split_once(':')
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid Ollama response"))?;
        if name.eq_ignore_ascii_case("content-length") {
            if content_length.is_some() {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "invalid Ollama response",
                ));
            }
            content_length = Some(value.trim().parse::<usize>().map_err(|_| {
                io::Error::new(io::ErrorKind::InvalidData, "invalid Ollama response")
            })?);
        }
        if name.eq_ignore_ascii_case("transfer-encoding") {
            chunked = value
                .split(',')
                .any(|encoding| encoding.trim().eq_ignore_ascii_case("chunked"));
        }
    }
    if chunked && content_length.is_some() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "invalid Ollama response",
        ));
    }
    let raw_body = &response[split + 4..];
    let body = if chunked {
        decode_chunked_body(raw_body)?
    } else if let Some(length) = content_length {
        if length != raw_body.len() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid Ollama response",
            ));
        }
        raw_body.to_vec()
    } else {
        raw_body.to_vec()
    };
    let document: serde_json::Value = serde_json::from_slice(&body)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid Ollama response"))?;
    let message = document
        .get("message")
        .and_then(serde_json::Value::as_object)
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid Ollama response"))?;
    let text = match message.get("content") {
        Some(serde_json::Value::String(value))
            if value.len() <= MAX_PROVIDER_RESPONSE_BYTES as usize =>
        {
            (!value.is_empty()).then(|| value.clone())
        }
        None | Some(serde_json::Value::Null) => None,
        _ => {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid Ollama response",
            ))
        }
    };
    let calls = match message.get("tool_calls") {
        None | Some(serde_json::Value::Null) => Vec::new(),
        Some(serde_json::Value::Array(calls)) => calls.clone(),
        _ => {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid tool-call payload",
            ))
        }
    };
    if calls.len() > MAX_TOOL_CALLS {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "invalid tool-call payload",
        ));
    }
    let mut tool_calls = Vec::with_capacity(calls.len());
    for (index, call) in calls.iter().enumerate() {
        let object = call.as_object().ok_or_else(|| {
            io::Error::new(io::ErrorKind::InvalidData, "invalid tool-call payload")
        })?;
        let function = object
            .get("function")
            .and_then(serde_json::Value::as_object)
            .ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidData, "invalid tool-call payload")
            })?;
        let name = function
            .get("name")
            .and_then(serde_json::Value::as_str)
            .filter(|name| valid_tool_name(name))
            .ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidData, "invalid tool-call payload")
            })?;
        let arguments = function
            .get("arguments")
            .and_then(serde_json::Value::as_object)
            .cloned()
            .ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidData, "invalid tool-call payload")
            })?;
        validate_arguments(&arguments)?;
        let id = match object.get("id") {
            Some(serde_json::Value::String(id)) if valid_tool_call_id(id) => id.clone(),
            None => generated_tool_call_id(index, function),
            _ => {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "invalid tool-call payload",
                ))
            }
        };
        if tool_calls
            .iter()
            .any(|existing: &ToolCall| existing.id == id)
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid tool-call payload",
            ));
        }
        tool_calls.push(ToolCall {
            id,
            name: name.to_owned(),
            arguments,
        });
    }
    Ok(AssistantTurn {
        text,
        tool_calls,
        finish_reason: document
            .get("done_reason")
            .and_then(serde_json::Value::as_str)
            .map(str::to_owned),
    })
}

fn decode_chunked_body(mut encoded: &[u8]) -> io::Result<Vec<u8>> {
    let mut decoded = Vec::new();
    loop {
        let line_end = encoded
            .windows(2)
            .position(|window| window == b"\r\n")
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid Ollama response"))?;
        let size_text = std::str::from_utf8(&encoded[..line_end])
            .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid Ollama response"))?;
        let size = usize::from_str_radix(size_text.split(';').next().unwrap_or_default(), 16)
            .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid Ollama response"))?;
        encoded = &encoded[line_end + 2..];
        if size == 0 {
            if encoded != b"\r\n" {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "invalid Ollama response",
                ));
            }
            return Ok(decoded);
        }
        if size > encoded.len().saturating_sub(2)
            || &encoded[size..size + 2] != b"\r\n"
            || decoded.len().saturating_add(size) > MAX_PROVIDER_RESPONSE_BYTES as usize
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid Ollama response",
            ));
        }
        decoded.extend_from_slice(&encoded[..size]);
        encoded = &encoded[size + 2..];
    }
}

fn generated_tool_call_id(
    index: usize,
    function: &serde_json::Map<String, serde_json::Value>,
) -> String {
    let canonical = serde_json::to_vec(function).unwrap_or_default();
    let digest = Sha256::digest(canonical);
    format!("ollama-{index}-{:x}", digest)[..32].to_owned()
}

fn valid_tool_name(name: &str) -> bool {
    (1..=128).contains(&name.len())
        && name
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'.' | b':' | b'-'))
}

fn valid_tool_call_id(id: &str) -> bool {
    (1..=256).contains(&id.len()) && !id.chars().any(|character| character < ' ')
}

fn validate_arguments(arguments: &serde_json::Map<String, serde_json::Value>) -> io::Result<()> {
    let mut budget = 10_000;
    validate_json_value(
        &serde_json::Value::Object(arguments.clone()),
        0,
        &mut budget,
    )?;
    let bytes = serde_json::to_vec(arguments)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid tool-call payload"))?;
    if bytes.len() > MAX_ARGUMENT_BYTES {
        Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "invalid tool-call payload",
        ))
    } else {
        Ok(())
    }
}

fn validate_json_value(
    value: &serde_json::Value,
    depth: usize,
    budget: &mut usize,
) -> io::Result<()> {
    if depth > 32 || *budget == 0 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "invalid tool-call payload",
        ));
    }
    *budget -= 1;
    match value {
        serde_json::Value::Null
        | serde_json::Value::Bool(_)
        | serde_json::Value::Number(_)
        | serde_json::Value::String(_) => Ok(()),
        serde_json::Value::Array(values) if values.len() <= 4096 => {
            for value in values {
                validate_json_value(value, depth + 1, budget)?;
            }
            Ok(())
        }
        serde_json::Value::Object(values)
            if values.len() <= 4096 && values.keys().all(|key| key.len() <= 256) =>
        {
            for value in values.values() {
                validate_json_value(value, depth + 1, budget)?;
            }
            Ok(())
        }
        _ => Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "invalid tool-call payload",
        )),
    }
}

fn valid_custom_slug(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 64
        && !value.starts_with('-')
        && !value.ends_with('-')
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-')
}

struct SecretString(Zeroizing<String>);

impl<'de> Deserialize<'de> for SecretString {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        String::deserialize(deserializer).map(|value| Self(Zeroizing::new(value)))
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct SecretBootstrapDocument {
    sync_token: SecretString,
    profiles: BTreeMap<String, SecretProfileDocument>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct SecretProfileDocument {
    api_key: SecretString,
    base_url: Option<String>,
    failover_eligible: Option<bool>,
}

struct SecretProfile {
    api_key: Zeroizing<String>,
    base_url: Option<String>,
    _failover_eligible: Option<bool>,
}

pub struct ProviderSecrets {
    _sync_token: Zeroizing<String>,
    profiles: BTreeMap<String, SecretProfile>,
}

impl std::fmt::Debug for ProviderSecrets {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("ProviderSecrets")
            .field("configured_profiles", &self.profiles.len())
            .finish()
    }
}

impl ProviderSecrets {
    pub fn empty() -> Self {
        Self {
            _sync_token: Zeroizing::new(String::new()),
            profiles: BTreeMap::new(),
        }
    }

    pub fn from_bootstrap(payload: &[u8]) -> io::Result<Self> {
        if payload.is_empty() || payload.len() > MAX_BOOTSTRAP_BYTES {
            return Err(invalid_bootstrap());
        }
        let document: SecretBootstrapDocument =
            serde_json::from_slice(payload).map_err(|_| invalid_bootstrap())?;
        if !valid_token(&document.sync_token.0) || document.profiles.len() > 128 {
            return Err(invalid_bootstrap());
        }
        let mut profiles = BTreeMap::new();
        for (profile_name, profile_document) in &document.profiles {
            let provider_name = profile_name
                .strip_prefix("provider:")
                .ok_or_else(invalid_bootstrap)?;
            let provider = ProviderId::parse(provider_name).ok_or_else(invalid_bootstrap)?;
            if profile_document.api_key.0.is_empty()
                || profile_document.api_key.0.trim() != profile_document.api_key.0.as_str()
                || profile_document.api_key.0.len() > MAX_API_KEY_BYTES
            {
                return Err(invalid_bootstrap());
            }
            if profile_document
                .base_url
                .as_ref()
                .is_some_and(|url| url.is_empty() || url.len() > MAX_BASE_URL_BYTES)
            {
                return Err(invalid_bootstrap());
            }
            if profile_document.base_url.is_some()
                && !matches!(provider, ProviderId::OmniRoute | ProviderId::Custom(_))
            {
                return Err(invalid_bootstrap());
            }
            if matches!(provider, ProviderId::Custom(_)) && profile_document.base_url.is_none() {
                return Err(invalid_bootstrap());
            }
            if profile_document.failover_eligible.is_some()
                && !matches!(provider, ProviderId::Custom(_))
            {
                return Err(invalid_bootstrap());
            }
            profiles.insert(
                provider.as_keychain_account(),
                SecretProfile {
                    api_key: Zeroizing::new(profile_document.api_key.0.to_string()),
                    base_url: profile_document.base_url.clone(),
                    _failover_eligible: profile_document.failover_eligible,
                },
            );
        }
        Ok(Self {
            _sync_token: Zeroizing::new(document.sync_token.0.to_string()),
            profiles,
        })
    }

    pub fn api_key(&self, provider: &ProviderId) -> Option<&str> {
        self.profiles
            .get(&provider.as_keychain_account())
            .map(|profile| profile.api_key.as_str())
    }

    pub fn base_url(&self, provider: &ProviderId) -> Option<&str> {
        self.profiles
            .get(&provider.as_keychain_account())
            .and_then(|profile| profile.base_url.as_deref())
    }

    pub fn configured_profiles(&self) -> usize {
        self.profiles.len()
    }

    pub fn sync_token_matches(&self, candidate: &str) -> bool {
        let expected = self._sync_token.as_bytes();
        let candidate = candidate.as_bytes();
        if candidate.len() != expected.len() || candidate.is_empty() {
            return false;
        }
        candidate
            .iter()
            .zip(expected)
            .fold(0_u8, |difference, (left, right)| {
                difference | (left ^ right)
            })
            == 0
    }

    pub fn update(
        &mut self,
        provider: &str,
        api_key: Option<&str>,
        base_url: Option<&str>,
        failover_eligible: Option<bool>,
    ) -> io::Result<()> {
        self.validate_update(provider, api_key, base_url, failover_eligible)?;
        let provider = ProviderId::parse(provider).ok_or_else(invalid_secret_update)?;
        let account = provider.as_keychain_account();
        let Some(api_key) = api_key else {
            self.profiles.remove(&account);
            return Ok(());
        };
        self.profiles.insert(
            account,
            SecretProfile {
                api_key: Zeroizing::new(api_key.to_owned()),
                base_url: base_url.map(str::to_owned),
                _failover_eligible: failover_eligible,
            },
        );
        Ok(())
    }

    pub fn validate_update(
        &self,
        provider: &str,
        api_key: Option<&str>,
        base_url: Option<&str>,
        failover_eligible: Option<bool>,
    ) -> io::Result<()> {
        let provider = ProviderId::parse(provider).ok_or_else(invalid_secret_update)?;
        let Some(api_key) = api_key else {
            return if base_url.is_none() && failover_eligible.is_none() {
                Ok(())
            } else {
                Err(invalid_secret_update())
            };
        };
        if api_key.is_empty()
            || api_key.trim() != api_key
            || api_key.len() > MAX_API_KEY_BYTES
            || base_url.is_some_and(|url| {
                url.is_empty()
                    || url.trim() != url
                    || url.len() > MAX_BASE_URL_BYTES
                    || !(url.starts_with("http://") || url.starts_with("https://"))
            })
            || (base_url.is_some()
                && !matches!(provider, ProviderId::OmniRoute | ProviderId::Custom(_)))
            || (matches!(provider, ProviderId::Custom(_)) && base_url.is_none())
            || (failover_eligible.is_some() && !matches!(provider, ProviderId::Custom(_)))
        {
            return Err(invalid_secret_update());
        }
        Ok(())
    }
}

fn valid_token(token: &str) -> bool {
    token.len() >= 32
        && token
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
}

fn invalid_bootstrap() -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, "invalid secret bootstrap")
}

fn invalid_secret_update() -> io::Error {
    io::Error::new(
        io::ErrorKind::InvalidInput,
        "invalid provider secret update",
    )
}

#[cfg(test)]
mod tests {
    use super::{parse_ollama_http_response, OllamaProvider, ProviderId, ProviderSecrets};
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::thread;

    fn read_http_request(stream: &mut std::net::TcpStream) -> Vec<u8> {
        let mut request = Vec::new();
        loop {
            let mut chunk = [0_u8; 1024];
            let read = stream.read(&mut chunk).expect("request");
            assert!(read > 0);
            request.extend_from_slice(&chunk[..read]);
            let Some(split) = request.windows(4).position(|window| window == b"\r\n\r\n") else {
                continue;
            };
            let headers = String::from_utf8_lossy(&request[..split]);
            let length = headers
                .lines()
                .find_map(|line| {
                    line.to_ascii_lowercase()
                        .strip_prefix("content-length: ")
                        .and_then(|value| value.parse::<usize>().ok())
                })
                .unwrap_or(0);
            if request.len() >= split + 4 + length {
                return request;
            }
        }
    }

    #[test]
    fn stable_provider_identifiers_round_trip_to_keychain_accounts() {
        for value in [
            "openai",
            "anthropic",
            "gemini",
            "zai",
            "deepseek",
            "ollama",
            "omniroute",
            "github",
            "custom:local-llm",
        ] {
            let provider = ProviderId::parse(value).expect("provider");
            assert_eq!(provider.as_keychain_account(), value);
        }
    }

    #[test]
    fn unsupported_or_unsafe_provider_identifiers_fail_closed() {
        for value in [
            "unknown",
            "custom:",
            "custom:-bad",
            "custom:bad-",
            "custom:../../keychain",
        ] {
            assert!(ProviderId::parse(value).is_none(), "{value}");
        }
    }

    #[test]
    fn parses_bounded_stdin_v1_secret_bootstrap() {
        let secrets = ProviderSecrets::from_bootstrap(
            br#"{"sync_token":"0123456789abcdef0123456789abcdef","profiles":{"provider:openai":{"api_key":"secret"},"provider:custom:local":{"api_key":"local-secret","base_url":"http://127.0.0.1:1234/v1","failover_eligible":true}}}"#,
        )
        .expect("bootstrap");
        assert_eq!(secrets.api_key(&ProviderId::OpenAi), Some("secret"));
        assert_eq!(
            secrets.base_url(&ProviderId::Custom("local".to_owned())),
            Some("http://127.0.0.1:1234/v1")
        );
        assert_eq!(secrets.configured_profiles(), 2);
        assert!(!format!("{secrets:?}").contains("secret"));
    }

    #[test]
    fn rejects_malformed_or_oversized_secret_bootstrap() {
        assert!(
            ProviderSecrets::from_bootstrap(br#"{"sync_token":"short","profiles":{}}"#).is_err()
        );
        assert!(ProviderSecrets::from_bootstrap(&vec![b'x'; 128 * 1024 + 1]).is_err());
        assert!(ProviderSecrets::from_bootstrap(
            br#"{"sync_token":"0123456789abcdef0123456789abcdef","profiles":{"provider:unknown":{"api_key":"secret"}}}"#,
        )
        .is_err());
    }

    #[test]
    fn live_secret_updates_require_the_bootstrap_sync_token_and_preserve_validation() {
        let mut secrets = ProviderSecrets::from_bootstrap(
            br#"{"sync_token":"0123456789abcdef0123456789abcdef","profiles":{}}"#,
        )
        .expect("bootstrap");
        assert!(!secrets.sync_token_matches("0123456789abcdef0123456789abcdeg"));
        assert!(secrets.sync_token_matches("0123456789abcdef0123456789abcdef"));
        secrets
            .update("openai", Some("replacement-secret"), None, None)
            .expect("update");
        assert_eq!(
            secrets.api_key(&ProviderId::OpenAi),
            Some("replacement-secret")
        );
        assert!(secrets
            .update("openai", Some(" secret"), None, None)
            .is_err());
        assert!(secrets
            .update("openai", Some("secret"), Some("https://invalid"), None)
            .is_err());
        assert!(secrets
            .update(
                "omniroute",
                Some("secret"),
                Some("file:///tmp/provider"),
                None,
            )
            .is_err());
        secrets.update("openai", None, None, None).expect("delete");
        assert_eq!(secrets.api_key(&ProviderId::OpenAi), None);
    }

    #[test]
    fn ollama_adapter_normalizes_real_tool_call_response() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept");
            let request = read_http_request(&mut stream);
            let request = String::from_utf8_lossy(&request);
            assert!(request.starts_with("POST /api/chat HTTP/1.1\r\n"));
            let body = r#"{"message":{"role":"assistant","content":"","tool_calls":[{"function":{"name":"write_file","arguments":{"path":"README.md","content":"hello"}}}]},"done":true,"done_reason":"stop"}"#;
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                body.len()
            )
            .expect("response");
        });
        let turn = OllamaProvider::new(port)
            .expect("provider")
            .complete(
                "qwen3",
                &[serde_json::json!({"role": "user", "content": "update README"})],
                &[serde_json::json!({"type": "function", "function": {"name": "write_file"}})],
            )
            .expect("turn");
        assert_eq!(turn.tool_calls.len(), 1);
        assert_eq!(turn.tool_calls[0].name, "write_file");
        assert_eq!(turn.tool_calls[0].arguments["path"], "README.md");
        assert!(turn.tool_calls[0].id.starts_with("ollama-0-"));
        server.join().expect("server");
    }

    #[test]
    fn ollama_parser_accepts_chunked_json_and_rejects_malformed_tool_calls() {
        let body = br#"{"message":{"role":"assistant","content":"hello"},"done":true}"#;
        let response = format!(
            "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n{:x}\r\n{}\r\n0\r\n\r\n",
            body.len(),
            std::str::from_utf8(body).expect("body")
        );
        let turn = parse_ollama_http_response(response.as_bytes()).expect("chunked response");
        assert_eq!(turn.text.as_deref(), Some("hello"));

        let malformed =
            b"HTTP/1.1 200 OK\r\n\r\n{\"message\":{\"content\":\"\",\"tool_calls\":{}}}";
        assert!(parse_ollama_http_response(malformed).is_err());
    }
}
