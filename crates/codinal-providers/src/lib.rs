//! Stable provider identifiers shared with the native Keychain contract.

pub mod catalogue;
pub mod prompt;

pub use catalogue::{
    estimate_cost_microusd, CapabilitySnapshot, EffortVariant, ModelCatalogueEntry, ModelPricing,
    PricingStatus, ProbeStatus, BUNDLED_CATALOGUE_REVISION, BUNDLED_MODEL_CATALOGUE,
    MODELS_DEV_API_SHA256,
};
pub use prompt::{CachePolicy, PromptEnvelope, ProviderUsage, UsageCost};

use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
#[cfg(test)]
use std::io::BufRead;
use std::io::{self, Read, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpStream};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;
use zeroize::Zeroizing;

const MAX_BOOTSTRAP_BYTES: usize = 128 * 1024;
const MAX_API_KEY_BYTES: usize = 16 * 1024;
const MAX_BASE_URL_BYTES: usize = 512;
const MAX_PROVIDER_RESPONSE_BYTES: u64 = 2 * 1024 * 1024;
const MAX_TOOL_CALLS: usize = 64;
const MAX_ARGUMENT_BYTES: usize = 1024 * 1024;
const MAX_SSE_LINE_BYTES: usize = 128 * 1024;

pub const OPENCODE_GO_ENDPOINT: &str = "https://opencode.ai/zen/go/v1/chat/completions";
pub const OPENCODE_GO_MODEL: &str = "kimi-k2.7-code";
const OPENCODE_GO_USER_AGENT: &str = "OpenCode/1.0";
pub const DEEPSEEK_ENDPOINT: &str = "https://api.deepseek.com/chat/completions";
pub const DEEPSEEK_MODEL: &str = "deepseek-v4-pro";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum OpenCodeGoEffort {
    Medium,
}

impl OpenCodeGoEffort {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Medium => "medium",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DeepSeekEffort {
    High,
}

impl DeepSeekEffort {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::High => "high",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TokenUsage {
    pub prompt_tokens: u64,
    pub completion_tokens: u64,
    pub total_tokens: u64,
    pub provider_usage: Option<ProviderUsage>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ProviderId {
    OpenAi,
    OpenCodeGo,
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
            "opencode-go" => Self::OpenCodeGo,
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
            Self::OpenCodeGo => "opencode-go".to_owned(),
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
    pub usage: Option<TokenUsage>,
}

#[derive(Clone)]
pub struct ProviderTransport {
    client: reqwest::Client,
    runtime: Arc<tokio::runtime::Runtime>,
}

impl ProviderTransport {
    pub fn new() -> io::Result<Self> {
        let client = reqwest::Client::builder()
            .connect_timeout(Duration::from_secs(2))
            .timeout(Duration::from_secs(300))
            .build()
            .map_err(|_| io::Error::other("provider client unavailable"))?;
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|_| io::Error::other("provider runtime unavailable"))?;
        Ok(Self {
            client,
            runtime: Arc::new(runtime),
        })
    }
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
        usage: None,
    })
}

pub struct OpenCodeGoProvider {
    api_key: Zeroizing<String>,
    endpoint: String,
    model: String,
    effort: OpenCodeGoEffort,
    transport: ProviderTransport,
}

impl OpenCodeGoProvider {
    pub fn new(api_key: &str) -> io::Result<Self> {
        Self::with_endpoint(api_key, OPENCODE_GO_ENDPOINT)
    }

    pub fn with_endpoint(api_key: &str, endpoint: &str) -> io::Result<Self> {
        Self::with_transport(api_key, endpoint, ProviderTransport::new()?)
    }

    pub fn with_transport(
        api_key: &str,
        endpoint: &str,
        transport: ProviderTransport,
    ) -> io::Result<Self> {
        if api_key.is_empty()
            || api_key.trim() != api_key
            || api_key.len() > MAX_API_KEY_BYTES
            || endpoint.is_empty()
            || endpoint.len() > MAX_BASE_URL_BYTES
            || !(endpoint.starts_with("http://") || endpoint.starts_with("https://"))
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid OpenCode Go configuration",
            ));
        }
        Ok(Self {
            api_key: Zeroizing::new(api_key.to_owned()),
            endpoint: endpoint.to_owned(),
            model: OPENCODE_GO_MODEL.to_owned(),
            effort: OpenCodeGoEffort::Medium,
            transport,
        })
    }

    pub fn model(&self) -> &str {
        &self.model
    }

    pub fn effort(&self) -> OpenCodeGoEffort {
        self.effort
    }

    pub fn complete(
        &self,
        messages: &[serde_json::Value],
        tools: &[serde_json::Value],
        cancellation: &AtomicBool,
    ) -> io::Result<AssistantTurn> {
        self.complete_with_deltas(messages, tools, cancellation, |_| Ok(()))
    }

    pub fn complete_with_deltas<F>(
        &self,
        messages: &[serde_json::Value],
        tools: &[serde_json::Value],
        cancellation: &AtomicBool,
        on_delta: F,
    ) -> io::Result<AssistantTurn>
    where
        F: FnMut(&str) -> io::Result<()>,
    {
        self.complete_with_deltas_limited(messages, tools, cancellation, None, on_delta)
    }

    pub fn complete_probe(
        &self,
        messages: &[serde_json::Value],
        tools: &[serde_json::Value],
        cancellation: &AtomicBool,
        max_output_tokens: u64,
    ) -> io::Result<AssistantTurn> {
        self.complete_with_deltas_limited(
            messages,
            tools,
            cancellation,
            Some(max_output_tokens),
            |_| Ok(()),
        )
    }

    fn complete_with_deltas_limited<F>(
        &self,
        messages: &[serde_json::Value],
        tools: &[serde_json::Value],
        cancellation: &AtomicBool,
        max_output_tokens: Option<u64>,
        on_delta: F,
    ) -> io::Result<AssistantTurn>
    where
        F: FnMut(&str) -> io::Result<()>,
    {
        if cancellation.load(Ordering::Acquire) {
            return Err(io::Error::new(
                io::ErrorKind::Interrupted,
                "OpenCode Go request interrupted",
            ));
        }
        if messages.len() > 10_000 || tools.len() > 256 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid OpenCode Go request",
            ));
        }
        if max_output_tokens == Some(0) {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid OpenCode Go output limit",
            ));
        }
        let mut document = serde_json::json!({
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": true,
            "reasoning_effort": self.effort.as_str(),
        });
        if let Some(max_output_tokens) = max_output_tokens {
            document["max_tokens"] = serde_json::Value::from(max_output_tokens);
        }
        let body = serde_json::to_vec(&document).map_err(|_| {
            io::Error::new(io::ErrorKind::InvalidInput, "invalid OpenCode Go request")
        })?;
        if body.len() > MAX_ARGUMENT_BYTES {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "OpenCode Go request exceeds limit",
            ));
        }

        self.transport
            .runtime
            .block_on(complete_chat_completions_request(
                &self.transport.client,
                self.api_key.as_str(),
                &self.endpoint,
                &body,
                cancellation,
                ChatCompletionsProfile::OpenCodeGo,
                Some(OPENCODE_GO_USER_AGENT),
                on_delta,
            ))
    }
}

pub struct DeepSeekProvider {
    api_key: Zeroizing<String>,
    endpoint: String,
    model: String,
    effort: DeepSeekEffort,
    transport: ProviderTransport,
}

impl DeepSeekProvider {
    pub fn new(api_key: &str) -> io::Result<Self> {
        Self::with_endpoint(api_key, DEEPSEEK_ENDPOINT)
    }

    pub fn with_endpoint(api_key: &str, endpoint: &str) -> io::Result<Self> {
        Self::with_transport(api_key, endpoint, ProviderTransport::new()?)
    }

    pub fn with_transport(
        api_key: &str,
        endpoint: &str,
        transport: ProviderTransport,
    ) -> io::Result<Self> {
        if api_key.is_empty()
            || api_key.trim() != api_key
            || api_key.len() > MAX_API_KEY_BYTES
            || endpoint.is_empty()
            || endpoint.len() > MAX_BASE_URL_BYTES
            || !(endpoint.starts_with("http://") || endpoint.starts_with("https://"))
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid DeepSeek configuration",
            ));
        }
        Ok(Self {
            api_key: Zeroizing::new(api_key.to_owned()),
            endpoint: endpoint.to_owned(),
            model: DEEPSEEK_MODEL.to_owned(),
            effort: DeepSeekEffort::High,
            transport,
        })
    }

    pub fn model(&self) -> &str {
        &self.model
    }

    pub fn effort(&self) -> DeepSeekEffort {
        self.effort
    }

    pub fn complete(
        &self,
        messages: &[serde_json::Value],
        tools: &[serde_json::Value],
        cancellation: &AtomicBool,
    ) -> io::Result<AssistantTurn> {
        self.complete_with_deltas(messages, tools, cancellation, |_| Ok(()))
    }

    pub fn complete_with_deltas<F>(
        &self,
        messages: &[serde_json::Value],
        tools: &[serde_json::Value],
        cancellation: &AtomicBool,
        on_delta: F,
    ) -> io::Result<AssistantTurn>
    where
        F: FnMut(&str) -> io::Result<()>,
    {
        self.complete_with_deltas_limited(messages, tools, cancellation, None, on_delta)
    }

    pub fn complete_probe(
        &self,
        messages: &[serde_json::Value],
        tools: &[serde_json::Value],
        cancellation: &AtomicBool,
        max_output_tokens: u64,
    ) -> io::Result<AssistantTurn> {
        self.complete_with_deltas_limited(
            messages,
            tools,
            cancellation,
            Some(max_output_tokens),
            |_| Ok(()),
        )
    }

    fn complete_with_deltas_limited<F>(
        &self,
        messages: &[serde_json::Value],
        tools: &[serde_json::Value],
        cancellation: &AtomicBool,
        max_output_tokens: Option<u64>,
        on_delta: F,
    ) -> io::Result<AssistantTurn>
    where
        F: FnMut(&str) -> io::Result<()>,
    {
        if cancellation.load(Ordering::Acquire) {
            return Err(io::Error::new(
                io::ErrorKind::Interrupted,
                "DeepSeek request interrupted",
            ));
        }
        if messages.len() > 10_000 || tools.len() > 256 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid DeepSeek request",
            ));
        }
        if max_output_tokens == Some(0) {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid DeepSeek output limit",
            ));
        }
        let mut document = serde_json::json!({
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "thinking": {"type": "enabled"},
            "reasoning_effort": self.effort.as_str(),
            "stream": true,
            "stream_options": {"include_usage": true},
        });
        if let Some(max_output_tokens) = max_output_tokens {
            document["max_tokens"] = serde_json::Value::from(max_output_tokens);
        }
        let body = serde_json::to_vec(&document)
            .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "invalid DeepSeek request"))?;
        if body.len() > MAX_ARGUMENT_BYTES {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "DeepSeek request exceeds limit",
            ));
        }
        self.transport
            .runtime
            .block_on(complete_chat_completions_request(
                &self.transport.client,
                self.api_key.as_str(),
                &self.endpoint,
                &body,
                cancellation,
                ChatCompletionsProfile::DeepSeek,
                None,
                on_delta,
            ))
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
enum ChatCompletionsProfile {
    #[default]
    OpenCodeGo,
    DeepSeek,
}

#[allow(clippy::too_many_arguments)]
async fn complete_chat_completions_request<F>(
    client: &reqwest::Client,
    api_key: &str,
    endpoint: &str,
    body: &[u8],
    cancellation: &AtomicBool,
    profile: ChatCompletionsProfile,
    user_agent: Option<&str>,
    mut on_delta: F,
) -> io::Result<AssistantTurn>
where
    F: FnMut(&str) -> io::Result<()>,
{
    let response = tokio::select! {
        result = client
            .post(endpoint)
            .bearer_auth(api_key)
            .header(reqwest::header::ACCEPT, "text/event-stream")
            .header(reqwest::header::CONTENT_TYPE, "application/json")
            .header(reqwest::header::USER_AGENT, user_agent.unwrap_or("Codinal/1.0"))
            .body(body.to_owned())
            .send() => result.map_err(|_| io::Error::other("provider request failed"))?,
        _ = wait_for_cancellation(cancellation) => {
            return Err(io::Error::new(
                io::ErrorKind::Interrupted,
                "provider request interrupted",
            ));
        }
    };
    if !response.status().is_success() {
        return Err(io::Error::other("provider request failed"));
    }
    let mut response = response;
    let mut parser = ChatCompletionsSseParser::new(profile);
    loop {
        let chunk = tokio::select! {
            result = response.chunk() => result
                .map_err(|_| io::Error::other("provider stream failed"))?,
            _ = wait_for_cancellation(cancellation) => {
                return Err(io::Error::new(
                    io::ErrorKind::Interrupted,
                    "provider request interrupted",
                ));
            }
        };
        let Some(chunk) = chunk else {
            break;
        };
        if parser.received_bytes.saturating_add(chunk.len()) > MAX_PROVIDER_RESPONSE_BYTES as usize
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "provider response exceeds limit",
            ));
        }
        parser.received_bytes = parser.received_bytes.saturating_add(chunk.len());
        parser.feed(&chunk, cancellation, &mut on_delta)?;
    }
    parser.finish(cancellation, &mut on_delta)
}

async fn wait_for_cancellation(cancellation: &AtomicBool) {
    while !cancellation.load(Ordering::Acquire) {
        tokio::time::sleep(Duration::from_millis(20)).await;
    }
}

#[derive(Default)]
struct OpenCodeGoToolCall {
    id: Option<String>,
    name: String,
    arguments: String,
}

#[derive(Default)]
struct ChatCompletionsSseParser {
    line: Vec<u8>,
    text: String,
    finish_reason: Option<String>,
    usage: Option<TokenUsage>,
    tool_calls: BTreeMap<usize, OpenCodeGoToolCall>,
    saw_done: bool,
    received_bytes: usize,
    profile: ChatCompletionsProfile,
}

impl ChatCompletionsSseParser {
    fn new(profile: ChatCompletionsProfile) -> Self {
        Self {
            profile,
            ..Self::default()
        }
    }

    fn feed<F>(
        &mut self,
        bytes: &[u8],
        cancellation: &AtomicBool,
        on_delta: &mut F,
    ) -> io::Result<()>
    where
        F: FnMut(&str) -> io::Result<()>,
    {
        if self.saw_done {
            return Ok(());
        }
        self.line.extend_from_slice(bytes);
        if self.line.len() > MAX_SSE_LINE_BYTES && !self.line.contains(&b'\n') {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "OpenCode Go SSE line exceeds limit",
            ));
        }
        while let Some(newline) = self.line.iter().position(|byte| *byte == b'\n') {
            let current = self.line.drain(..=newline).collect::<Vec<_>>();
            self.process_line(&current, cancellation, on_delta)?;
            if self.saw_done {
                self.line.clear();
                break;
            }
        }
        if self.line.len() > MAX_SSE_LINE_BYTES {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "OpenCode Go SSE line exceeds limit",
            ));
        }
        Ok(())
    }

    fn finish<F>(
        &mut self,
        cancellation: &AtomicBool,
        on_delta: &mut F,
    ) -> io::Result<AssistantTurn>
    where
        F: FnMut(&str) -> io::Result<()>,
    {
        if !self.line.is_empty() {
            let current = std::mem::take(&mut self.line);
            self.process_line(&current, cancellation, on_delta)?;
        }
        if !self.saw_done {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "OpenCode Go stream ended before completion",
            ));
        }
        std::mem::take(self).finish_turn()
    }

    fn process_line<F>(
        &mut self,
        line: &[u8],
        cancellation: &AtomicBool,
        on_delta: &mut F,
    ) -> io::Result<()>
    where
        F: FnMut(&str) -> io::Result<()>,
    {
        if cancellation.load(Ordering::Acquire) {
            return Err(io::Error::new(
                io::ErrorKind::Interrupted,
                "OpenCode Go request interrupted",
            ));
        }
        if line.len() > MAX_SSE_LINE_BYTES {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "OpenCode Go SSE line exceeds limit",
            ));
        }
        let line_text = std::str::from_utf8(line)
            .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go SSE"))?
            .trim_end_matches(['\r', '\n']);
        let Some(data) = line_text.strip_prefix("data:") else {
            return Ok(());
        };
        let data = data.trim_start();
        if data == "[DONE]" {
            self.saw_done = true;
            return Ok(());
        }
        if data.is_empty() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid OpenCode Go SSE",
            ));
        }
        let event: serde_json::Value = serde_json::from_str(data)
            .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go SSE"))?;
        let object = event
            .as_object()
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go SSE"))?;

        if let Some(raw_usage) = object.get("usage") {
            if !raw_usage.is_null() {
                self.usage = Some(parse_token_usage(raw_usage, self.profile)?);
            }
        }
        let Some(raw_choices) = object.get("choices") else {
            return Ok(());
        };
        let choices = raw_choices
            .as_array()
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go SSE"))?;
        if choices.len() > 1 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "multiple OpenCode Go choices are unsupported",
            ));
        }
        let Some(choice) = choices.first() else {
            return Ok(());
        };
        let choice = choice
            .as_object()
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go SSE"))?;
        if let Some(reason) = choice.get("finish_reason") {
            if !reason.is_null() {
                let reason = reason.as_str().ok_or_else(|| {
                    io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go SSE")
                })?;
                if reason.len() > 128 {
                    return Err(io::Error::new(
                        io::ErrorKind::InvalidData,
                        "invalid OpenCode Go SSE",
                    ));
                }
                self.finish_reason = Some(reason.to_owned());
            }
        }
        let Some(delta) = choice.get("delta") else {
            return Ok(());
        };
        let Some(delta) = delta.as_object() else {
            if delta.is_null() {
                return Ok(());
            }
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid chat-completions SSE",
            ));
        };
        if let Some(content) = delta.get("content") {
            if let Some(content) = content.as_str() {
                if self.text.len().saturating_add(content.len())
                    > MAX_PROVIDER_RESPONSE_BYTES as usize
                {
                    return Err(io::Error::new(
                        io::ErrorKind::InvalidData,
                        "provider response exceeds limit",
                    ));
                }
                self.text.push_str(content);
                if !content.is_empty() {
                    on_delta(content)?;
                }
            } else if !content.is_null() {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "invalid chat-completions SSE",
                ));
            }
        }
        let Some(raw_tool_calls) = delta.get("tool_calls") else {
            return Ok(());
        };
        let raw_tool_calls = raw_tool_calls.as_array().ok_or_else(|| {
            io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go tool calls")
        })?;
        if raw_tool_calls.len() > MAX_TOOL_CALLS {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid OpenCode Go tool calls",
            ));
        }
        for raw_call in raw_tool_calls {
            let call = raw_call.as_object().ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go tool calls")
            })?;
            let index = call
                .get("index")
                .and_then(serde_json::Value::as_u64)
                .ok_or_else(|| {
                    io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go tool calls")
                })? as usize;
            if index >= MAX_TOOL_CALLS {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "invalid OpenCode Go tool calls",
                ));
            }
            let accumulated = self.tool_calls.entry(index).or_default();
            if let Some(id) = call.get("id") {
                if !id.is_null() {
                    let id = id
                        .as_str()
                        .filter(|id| valid_tool_call_id(id))
                        .ok_or_else(|| {
                            io::Error::new(
                                io::ErrorKind::InvalidData,
                                "invalid OpenCode Go tool calls",
                            )
                        })?;
                    if accumulated
                        .id
                        .as_deref()
                        .is_some_and(|existing| existing != id)
                    {
                        return Err(io::Error::new(
                            io::ErrorKind::InvalidData,
                            "invalid OpenCode Go tool calls",
                        ));
                    }
                    accumulated.id = Some(id.to_owned());
                }
            }
            let Some(function) = call.get("function") else {
                continue;
            };
            let function = function.as_object().ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go tool calls")
            })?;
            if let Some(name) = function.get("name") {
                if !name.is_null() {
                    let name = name.as_str().ok_or_else(|| {
                        io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go tool calls")
                    })?;
                    if name.len() > 128 {
                        return Err(io::Error::new(
                            io::ErrorKind::InvalidData,
                            "invalid OpenCode Go tool calls",
                        ));
                    }
                    accumulated.name.push_str(name);
                }
            }
            if let Some(arguments) = function.get("arguments") {
                if !arguments.is_null() {
                    let arguments = arguments.as_str().ok_or_else(|| {
                        io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go tool calls")
                    })?;
                    if accumulated.arguments.len().saturating_add(arguments.len())
                        > MAX_ARGUMENT_BYTES
                    {
                        return Err(io::Error::new(
                            io::ErrorKind::InvalidData,
                            "OpenCode Go tool arguments exceed limit",
                        ));
                    }
                    accumulated.arguments.push_str(arguments);
                }
            }
        }
        Ok(())
    }

    fn finish_turn(self) -> io::Result<AssistantTurn> {
        let mut normalized_tool_calls = Vec::with_capacity(self.tool_calls.len());
        for (index, accumulated) in self.tool_calls {
            if !valid_tool_name(&accumulated.name) {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "invalid OpenCode Go tool calls",
                ));
            }
            let arguments = if accumulated.arguments.is_empty() {
                serde_json::Map::new()
            } else {
                let value: serde_json::Value = serde_json::from_str(&accumulated.arguments)
                    .map_err(|_| {
                        io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go tool calls")
                    })?;
                value.as_object().cloned().ok_or_else(|| {
                    io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go tool calls")
                })?
            };
            validate_arguments(&arguments)?;
            let id = accumulated.id.unwrap_or_else(|| {
                generated_tool_call_id_with_prefix("opencode-go", index, &accumulated.name)
            });
            if normalized_tool_calls
                .iter()
                .any(|existing: &ToolCall| existing.id == id)
            {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "duplicate OpenCode Go tool call id",
                ));
            }
            normalized_tool_calls.push(ToolCall {
                id,
                name: accumulated.name,
                arguments,
            });
        }
        Ok(AssistantTurn {
            text: (!self.text.is_empty()).then_some(self.text),
            tool_calls: normalized_tool_calls,
            finish_reason: self.finish_reason,
            usage: self.usage,
        })
    }
}

#[cfg(test)]
fn parse_chat_completions_sse<R: BufRead>(
    reader: &mut R,
    cancellation: &AtomicBool,
) -> io::Result<AssistantTurn> {
    let mut parser = ChatCompletionsSseParser::new(ChatCompletionsProfile::OpenCodeGo);
    let mut line = Vec::new();
    loop {
        line.clear();
        let read = reader
            .read_until(b'\n', &mut line)
            .map_err(|_| io::Error::other("OpenCode Go stream failed"))?;
        if read == 0 {
            break;
        }
        parser.feed(&line, cancellation, &mut |_| Ok(()))?;
        if parser.saw_done {
            break;
        }
    }
    parser.finish(cancellation, &mut |_| Ok(()))
}

fn parse_token_usage(
    value: &serde_json::Value,
    profile: ChatCompletionsProfile,
) -> io::Result<TokenUsage> {
    let object = value
        .as_object()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go usage"))?;
    let number = |name: &str| {
        object
            .get(name)
            .and_then(serde_json::Value::as_u64)
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid OpenCode Go usage"))
    };
    let mut provider_usage = ProviderUsage::from_response(value)?;
    if profile == ChatCompletionsProfile::DeepSeek {
        provider_usage.prompt_cache_hit_tokens =
            optional_usage_number(object, "prompt_cache_hit_tokens")?;
        provider_usage.prompt_cache_miss_tokens =
            optional_usage_number(object, "prompt_cache_miss_tokens")?;
        provider_usage.cache_read_tokens = provider_usage
            .cache_read_tokens
            .or(provider_usage.prompt_cache_hit_tokens);
    }
    Ok(TokenUsage {
        prompt_tokens: number("prompt_tokens")?,
        completion_tokens: number("completion_tokens")?,
        total_tokens: number("total_tokens")?,
        provider_usage: Some(provider_usage),
    })
}

fn optional_usage_number(
    object: &serde_json::Map<String, serde_json::Value>,
    name: &str,
) -> io::Result<Option<u64>> {
    match object.get(name) {
        None | Some(serde_json::Value::Null) => Ok(None),
        Some(value) => value
            .as_u64()
            .map(Some)
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid provider usage")),
    }
}

fn generated_tool_call_id_with_prefix(prefix: &str, index: usize, name: &str) -> String {
    let digest = Sha256::digest(name.as_bytes());
    format!("{prefix}-{index}-{:x}", digest)
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

    pub fn status(&self) -> Vec<serde_json::Value> {
        let providers = [
            "anthropic",
            "gemini",
            "openai",
            "opencode-go",
            "zai",
            "deepseek",
            "omniroute",
            "github",
        ];
        providers
            .into_iter()
            .map(|provider| {
                serde_json::json!({
                    "provider": provider,
                    "configured": self.api_key(&ProviderId::parse(provider).expect("builtin provider"))
                        .is_some(),
                })
            })
            .collect()
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
    use super::{
        parse_ollama_http_response, DeepSeekProvider, OllamaProvider, OpenCodeGoProvider,
        ProviderId, ProviderSecrets, DEEPSEEK_MODEL, OPENCODE_GO_ENDPOINT,
    };
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::thread;
    use std::time::Duration;

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
            "opencode-go",
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
    fn opencode_go_endpoint_matches_official_go_contract() {
        assert_eq!(
            OPENCODE_GO_ENDPOINT,
            "https://opencode.ai/zen/go/v1/chat/completions"
        );
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

    #[test]
    fn opencode_go_adapter_sends_pinned_profile_and_normalizes_sse() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let endpoint = format!(
            "http://127.0.0.1:{}/v1/chat/completions",
            listener.local_addr().expect("address").port()
        );
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept");
            let request = read_http_request(&mut stream);
            let request_text = String::from_utf8_lossy(&request);
            assert!(request_text.starts_with("POST /v1/chat/completions HTTP/1.1\r\n"));
            assert!(request_text
                .lines()
                .any(|line| line.eq_ignore_ascii_case("authorization: Bearer test-secret")));
            assert!(request_text
                .lines()
                .any(|line| line.eq_ignore_ascii_case("user-agent: OpenCode/1.0")));
            let body_start = request
                .windows(4)
                .position(|window| window == b"\r\n\r\n")
                .expect("headers")
                + 4;
            let body = &request[body_start..];
            let body: serde_json::Value = serde_json::from_slice(body).expect("json body");
            assert_eq!(body["model"], super::OPENCODE_GO_MODEL);
            assert_eq!(body["stream"], true);
            assert_eq!(body["reasoning_effort"], "medium");
            let response = concat!(
                "data: {\"choices\":[{\"index\":0,\"delta\":{\"role\":\"assistant\",\"content\":\"hello \"},\"finish_reason\":null}]}\n\n",
                "data: {\"choices\":[{\"index\":0,\"delta\":{\"content\":\"world\",\"tool_calls\":[{\"index\":0,\"id\":\"call-1\",\"function\":{\"name\":\"write_file\",\"arguments\":\"\"}}]},\"finish_reason\":null}]}\n\n",
                "data: {\"choices\":[{\"index\":0,\"delta\":{\"tool_calls\":[{\"index\":0,\"id\":null,\"function\":{\"name\":null,\"arguments\":\"{\\\"path\\\":\\\"README.md\\\"}\"}}]},\"finish_reason\":\"tool_calls\"}],\"usage\":{\"prompt_tokens\":3,\"completion_tokens\":2,\"total_tokens\":5}}\n\n",
                "data: [DONE]\n\n"
            );
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{response}",
                response.len()
            )
            .expect("response");
        });
        let mut deltas = Vec::new();
        let turn = OpenCodeGoProvider::with_endpoint("test-secret", &endpoint)
            .expect("provider")
            .complete_with_deltas(
                &[serde_json::json!({"role":"user","content":"update README"})],
                &[serde_json::json!({"type":"function","function":{"name":"write_file"}})],
                &AtomicBool::new(false),
                |delta| {
                    deltas.push(delta.to_owned());
                    Ok(())
                },
            )
            .expect("turn");
        assert_eq!(deltas, vec!["hello ".to_owned(), "world".to_owned()]);
        assert_eq!(turn.text.as_deref(), Some("hello world"));
        assert_eq!(turn.finish_reason.as_deref(), Some("tool_calls"));
        assert_eq!(turn.tool_calls.len(), 1);
        assert_eq!(turn.tool_calls[0].id, "call-1");
        assert_eq!(turn.tool_calls[0].name, "write_file");
        assert_eq!(turn.tool_calls[0].arguments["path"], "README.md");
        let usage = turn.usage.expect("usage");
        assert_eq!(
            (
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens
            ),
            (3, 2, 5)
        );
        let provider_usage = usage.provider_usage.expect("provider usage");
        assert_eq!(provider_usage.input_tokens, Some(3));
        assert_eq!(provider_usage.output_tokens, Some(2));
        assert_eq!(provider_usage.cache_read_tokens, None);
        assert_eq!(provider_usage.cache_write_tokens, None);
        assert_eq!(provider_usage.cost, super::UsageCost::Unavailable);
        server.join().expect("server");
    }

    #[test]
    fn opencode_go_adapter_is_interruptible_before_network_io_and_rejects_incomplete_sse() {
        let cancelled = AtomicBool::new(true);
        let provider = OpenCodeGoProvider::new("test-secret").expect("provider");
        assert_eq!(
            provider
                .complete(&[], &[], &cancelled)
                .expect_err("cancelled")
                .kind(),
            std::io::ErrorKind::Interrupted
        );
        let incomplete = b"data: {\"choices\":[]}\n\n";
        assert!(super::parse_chat_completions_sse(
            &mut std::io::Cursor::new(incomplete),
            &AtomicBool::new(false)
        )
        .is_err());
        let malformed = b"data: {not-json}\n\ndata: [DONE]\n\n";
        assert!(super::parse_chat_completions_sse(
            &mut std::io::Cursor::new(malformed),
            &AtomicBool::new(false)
        )
        .is_err());
        let multiple_choices = b"data: {\"choices\":[{},{}]}\n\ndata: [DONE]\n\n";
        assert!(super::parse_chat_completions_sse(
            &mut std::io::Cursor::new(multiple_choices),
            &AtomicBool::new(false)
        )
        .is_err());
    }

    #[test]
    fn provider_rate_limit_fails_closed_without_emitting_deltas() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let endpoint = format!(
            "http://127.0.0.1:{}/chat/completions",
            listener.local_addr().expect("address").port()
        );
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept");
            let _request = read_http_request(&mut stream);
            stream
                .write_all(
                    b"HTTP/1.1 429 Too Many Requests\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
                )
                .expect("rate-limit response");
        });
        let mut deltas = Vec::new();
        let result = OpenCodeGoProvider::with_endpoint("test-secret", &endpoint)
            .expect("provider")
            .complete_with_deltas(
                &[serde_json::json!({"role":"user","content":"hello"})],
                &[],
                &AtomicBool::new(false),
                |delta| {
                    deltas.push(delta.to_owned());
                    Ok(())
                },
            );
        assert!(result.is_err());
        assert!(deltas.is_empty());
        server.join().expect("server");
    }

    #[test]
    fn provider_interrupt_after_partial_stream_stops_before_usage_and_done() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let endpoint = format!(
            "http://127.0.0.1:{}/chat/completions",
            listener.local_addr().expect("address").port()
        );
        let first =
            b"data: {\"choices\":[{\"index\":0,\"delta\":{\"content\":\"partial\"},\"finish_reason\":null}]}\n\n";
        let second = b"data: {\"choices\":[{\"index\":0,\"delta\":{},\"finish_reason\":\"stop\"}],\"usage\":{\"prompt_tokens\":3,\"completion_tokens\":1,\"total_tokens\":4}}\n\ndata: [DONE]\n\n";
        let response_len = first.len() + second.len();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept");
            let _request = read_http_request(&mut stream);
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {response_len}\r\nConnection: close\r\n\r\n"
            )
            .expect("headers");
            stream.write_all(first).expect("first event");
            stream.flush().expect("flush");
            thread::sleep(Duration::from_millis(200));
            let _ = stream.write_all(second);
        });
        let cancellation = AtomicBool::new(false);
        let mut deltas = Vec::new();
        let error = OpenCodeGoProvider::with_endpoint("test-secret", &endpoint)
            .expect("provider")
            .complete_with_deltas(
                &[serde_json::json!({"role":"user","content":"hello"})],
                &[],
                &cancellation,
                |delta| {
                    deltas.push(delta.to_owned());
                    cancellation.store(true, Ordering::Release);
                    Ok(())
                },
            )
            .expect_err("interrupted stream");
        assert_eq!(error.kind(), std::io::ErrorKind::Interrupted);
        assert_eq!(deltas, vec!["partial"]);
        server.join().expect("server");
    }

    #[test]
    fn deepseek_adapter_sends_pinned_thinking_profile_and_reuses_sse_normalizer() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let endpoint = format!(
            "http://127.0.0.1:{}/chat/completions",
            listener.local_addr().expect("address").port()
        );
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept");
            let request = read_http_request(&mut stream);
            let request_text = String::from_utf8_lossy(&request);
            assert!(request_text.starts_with("POST /chat/completions HTTP/1.1\r\n"));
            assert!(request_text
                .lines()
                .any(|line| line.eq_ignore_ascii_case("authorization: Bearer deepseek-secret")));
            let body_start = request
                .windows(4)
                .position(|window| window == b"\r\n\r\n")
                .expect("headers")
                + 4;
            let body: serde_json::Value =
                serde_json::from_slice(&request[body_start..]).expect("json body");
            assert_eq!(body["model"], DEEPSEEK_MODEL);
            assert_eq!(body["stream"], true);
            assert_eq!(body["thinking"]["type"], "enabled");
            assert_eq!(body["reasoning_effort"], "high");
            assert_eq!(body["stream_options"]["include_usage"], true);
            let response = concat!(
                "data: {\"choices\":[{\"index\":0,\"delta\":{\"role\":\"assistant\",\"content\":null,\"reasoning_content\":\"thinking\"},\"finish_reason\":null}],\"usage\":null}\n\n",
                "data: {\"choices\":[{\"index\":0,\"delta\":{\"content\":\"done\",\"tool_calls\":[{\"index\":0,\"id\":\"call-ds-1\",\"function\":{\"name\":\"apply_patch\",\"arguments\":\"{\\\"path\\\":\\\"README.md\\\"}\"}}]},\"finish_reason\":\"tool_calls\"}],\"usage\":{\"prompt_tokens\":11,\"completion_tokens\":7,\"total_tokens\":18,\"prompt_cache_hit_tokens\":4,\"prompt_cache_miss_tokens\":7}}\n\n",
                "data: [DONE]\n\n"
            );
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{response}",
                response.len()
            )
            .expect("response");
        });
        let turn = DeepSeekProvider::with_endpoint("deepseek-secret", &endpoint)
            .expect("provider")
            .complete(
                &[serde_json::json!({"role":"user","content":"update README"})],
                &[serde_json::json!({"type":"function","function":{"name":"apply_patch"}})],
                &AtomicBool::new(false),
            )
            .expect("turn");
        assert_eq!(turn.text.as_deref(), Some("done"));
        assert_eq!(turn.finish_reason.as_deref(), Some("tool_calls"));
        assert_eq!(turn.tool_calls.len(), 1);
        assert_eq!(turn.tool_calls[0].id, "call-ds-1");
        assert_eq!(turn.tool_calls[0].name, "apply_patch");
        assert_eq!(turn.tool_calls[0].arguments["path"], "README.md");
        let usage = turn.usage.expect("usage");
        assert_eq!(
            (
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens
            ),
            (11, 7, 18)
        );
        let provider_usage = usage.provider_usage.expect("provider usage");
        assert_eq!(provider_usage.input_tokens, Some(11));
        assert_eq!(provider_usage.output_tokens, Some(7));
        assert_eq!(provider_usage.prompt_cache_hit_tokens, Some(4));
        assert_eq!(provider_usage.prompt_cache_miss_tokens, Some(7));
        assert_eq!(provider_usage.cache_read_tokens, Some(4));
        assert_eq!(provider_usage.cache_write_tokens, None);
        assert_eq!(provider_usage.cost, super::UsageCost::Unavailable);
        server.join().expect("server");
    }
}
