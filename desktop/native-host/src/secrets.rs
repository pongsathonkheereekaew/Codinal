use std::collections::BTreeMap;
use std::io::{self, BufRead, BufReader, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpStream};
use std::time::Duration;

use serde::Serialize;
use zeroize::Zeroize;

use crate::host::validate_session_token;

pub const SUPPORTED_PROVIDERS: [&str; 7] = [
    "anthropic",
    "gemini",
    "openai",
    "zai",
    "deepseek",
    "omniroute",
    "github",
];
pub const MAX_API_KEY_BYTES: usize = 16 * 1024;
pub const MAX_BASE_URL_BYTES: usize = 512;
const KEYCHAIN_SERVICE: &str = "dev.codinal.desktop.provider-secrets";

/// Providers that may carry a user-configurable self-hosted base_url next to
/// the api_key (OmniRoute now; vLLM / LM Studio later).
pub const PROVIDERS_WITH_BASE_URL: &[&str] = &["omniroute"];

pub trait SecretVault: Send + Sync {
    fn get(&self, provider: &str) -> io::Result<Option<String>>;
    fn set(&self, provider: &str, value: &str) -> io::Result<()>;
    fn delete(&self, provider: &str) -> io::Result<bool>;
    /// Optional per-provider base_url for self-hosted OpenAI-compat gateways.
    /// Default returns None so existing/test vaults stay valid.
    fn get_base_url(&self, _provider: &str) -> io::Result<Option<String>> {
        Ok(None)
    }
    /// Persist (or clear with None) the optional per-provider base_url.
    fn set_base_url(&self, _provider: &str, _value: Option<&str>) -> io::Result<()> {
        Ok(())
    }
    /// Optional per-provider failover-eligibility flag (custom providers only).
    fn get_failover_flag(&self, _provider: &str) -> io::Result<Option<bool>> {
        Ok(None)
    }
    fn set_failover_flag(&self, _provider: &str, _value: Option<bool>) -> io::Result<()> {
        Ok(())
    }
    /// Enumerate registered custom-provider slugs (registry index).
    /// Default returns empty so existing/test vaults stay valid.
    fn list_custom_slugs(&self) -> io::Result<Vec<String>> {
        Ok(Vec::new())
    }
    /// Add/remove a slug from the custom-provider registry index.
    fn set_custom_slug_registered(&self, _slug: &str, _registered: bool) -> io::Result<()> {
        Ok(())
    }
}

#[derive(Default)]
pub struct PlatformSecretVault;

#[derive(Serialize)]
struct ProviderSecret {
    api_key: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    base_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    failover_eligible: Option<bool>,
}

impl Drop for ProviderSecret {
    fn drop(&mut self) {
        self.api_key.zeroize();
    }
}

#[derive(Serialize)]
struct SecretBootstrap {
    sync_token: String,
    profiles: BTreeMap<String, ProviderSecret>,
}

#[derive(Serialize)]
pub struct ProviderSecretStatus {
    pub provider: &'static str,
    pub configured: bool,
}

pub fn validate_provider(provider: &str) -> io::Result<&str> {
    if SUPPORTED_PROVIDERS.contains(&provider) {
        Ok(provider)
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "unsupported provider",
        ))
    }
}

fn validate_provider_account(provider: &str) -> io::Result<&str> {
    if validate_provider(provider).is_ok() || validate_custom_provider(provider).is_ok() {
        Ok(provider)
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "unsupported provider account",
        ))
    }
}

pub fn encode_secret_bootstrap(
    vault: &impl SecretVault,
    sync_token: &str,
) -> io::Result<zeroize::Zeroizing<Vec<u8>>> {
    validate_session_token(sync_token)?;
    let mut profiles: BTreeMap<String, ProviderSecret> = BTreeMap::new();
    for provider in SUPPORTED_PROVIDERS {
        let value = match vault.get(provider) {
            Ok(value) => value,
            Err(error) => {
                for secret in profiles.values_mut() {
                    secret.api_key.zeroize();
                }
                return Err(error);
            }
        };
        if let Some(api_key) = value {
            let base_url = if PROVIDERS_WITH_BASE_URL.contains(&provider) {
                vault.get_base_url(provider).unwrap_or(None)
            } else {
                None
            };
            profiles.insert(
                format!("provider:{provider}"),
                ProviderSecret {
                    api_key,
                    base_url,
                    failover_eligible: None,
                },
            );
        }
    }
    // Append user-registered custom OpenAI-compatible providers.
    for slug in vault.list_custom_slugs().unwrap_or_default() {
        let custom_provider = format!("custom:{slug}");
        let profile_key = format!("provider:{custom_provider}");
        if let Some(api_key) = vault.get(&custom_provider)? {
            let base_url = vault.get_base_url(&custom_provider).unwrap_or(None);
            let failover_eligible = vault.get_failover_flag(&custom_provider).unwrap_or(None);
            profiles.insert(
                profile_key,
                ProviderSecret {
                    api_key,
                    base_url,
                    failover_eligible,
                },
            );
        }
    }
    let mut bootstrap = SecretBootstrap {
        sync_token: sync_token.to_owned(),
        profiles,
    };
    let result = serde_json::to_vec(&bootstrap)
        .map(zeroize::Zeroizing::new)
        .map_err(|error| io::Error::other(error.to_string()));
    bootstrap.sync_token.zeroize();
    for secret in bootstrap.profiles.values_mut() {
        secret.api_key.zeroize();
    }
    result
}

pub fn provider_secret_status(vault: &impl SecretVault) -> io::Result<Vec<ProviderSecretStatus>> {
    SUPPORTED_PROVIDERS
        .into_iter()
        .map(|provider| {
            let configured = match vault.get(provider)? {
                Some(mut value) => {
                    value.zeroize();
                    true
                }
                None => false,
            };
            Ok(ProviderSecretStatus {
                provider,
                configured,
            })
        })
        .collect()
}

pub fn sync_runtime_provider_secret(
    port: u16,
    token: &str,
    secret_sync_token: &str,
    provider: &str,
    api_key: Option<&str>,
    base_url: Option<&str>,
) -> io::Result<()> {
    validate_session_token(token)?;
    validate_session_token(secret_sync_token)?;
    let provider = validate_provider(provider)?;
    let (method, body) = match api_key {
        Some(value) if !value.trim().is_empty() => {
            let payload = match base_url {
                Some(url) if !url.trim().is_empty() => serde_json::json!({
                    "api_key": value,
                    "base_url": url.trim(),
                }),
                _ => serde_json::json!({ "api_key": value }),
            };
            (
                "PUT",
                serde_json::to_vec(&payload).map_err(io::Error::other)?,
            )
        }
        Some(_) => {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "api key must not be empty",
            ));
        }
        None => ("DELETE", Vec::new()),
    };
    let body = zeroize::Zeroizing::new(body);
    send_runtime_secret_request(
        port,
        token,
        secret_sync_token,
        method,
        &format!("/v1/secrets/providers/{provider}"),
        &body,
    )
}

pub fn sync_runtime_custom_provider(
    port: u16,
    token: &str,
    secret_sync_token: &str,
    slug: &str,
    base_url: &str,
    api_key: Option<&str>,
    failover_eligible: bool,
) -> io::Result<()> {
    validate_session_token(token)?;
    validate_session_token(secret_sync_token)?;
    validate_custom_slug(slug)?;
    let (method, path, body) = match api_key {
        Some(value) if !value.trim().is_empty() => (
            "POST",
            "/v1/providers/custom".to_owned(),
            serde_json::to_vec(&serde_json::json!({
                "slug": slug,
                "base_url": base_url.trim(),
                "api_key": value,
                "failover_eligible": failover_eligible,
            }))
            .map_err(io::Error::other)?,
        ),
        Some(_) => {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "api key must not be empty",
            ));
        }
        None => ("DELETE", format!("/v1/providers/custom/{slug}"), Vec::new()),
    };
    let body = zeroize::Zeroizing::new(body);
    send_runtime_secret_request(port, token, secret_sync_token, method, &path, &body)
}

fn send_runtime_secret_request(
    port: u16,
    token: &str,
    secret_sync_token: &str,
    method: &str,
    path: &str,
    body: &[u8],
) -> io::Result<()> {
    let address = SocketAddrV4::new(Ipv4Addr::LOCALHOST, port);
    let mut stream = TcpStream::connect_timeout(&address.into(), Duration::from_secs(2))?;
    stream.set_read_timeout(Some(Duration::from_secs(2)))?;
    stream.set_write_timeout(Some(Duration::from_secs(2)))?;
    let headers = zeroize::Zeroizing::new(format!(
        "{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {token}\r\nX-Codinal-Secret-Sync: {secret_sync_token}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        body.len()
    ));
    stream
        .write_all(headers.as_bytes())
        .and_then(|()| stream.write_all(body))
        .and_then(|()| stream.flush())
        .map_err(indeterminate_secret_sync)?;
    let mut status_line = String::new();
    let read = BufReader::new(stream)
        .read_line(&mut status_line)
        .map_err(indeterminate_secret_sync)?;
    if read == 0 {
        return Err(indeterminate_secret_sync(io::Error::new(
            io::ErrorKind::UnexpectedEof,
            "missing runtime response",
        )));
    }
    if status_line.split_whitespace().nth(1) != Some("200") {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "runtime rejected provider secret update",
        ));
    }
    Ok(())
}

fn indeterminate_secret_sync(_error: io::Error) -> io::Error {
    io::Error::new(
        io::ErrorKind::ConnectionAborted,
        "runtime provider secret update is indeterminate; restart required",
    )
}

pub fn update_provider_secret(
    vault: &impl SecretVault,
    provider: &str,
    api_key: Option<&str>,
    base_url: Option<&str>,
    sync_runtime: impl FnOnce() -> io::Result<()>,
) -> io::Result<bool> {
    let provider = validate_provider(provider)?;
    if api_key.is_some_and(|value| value.trim().is_empty()) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "api key must not be empty",
        ));
    }
    if api_key.is_some_and(|value| value.trim() != value) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "api key must not contain surrounding whitespace",
        ));
    }
    if api_key.is_some_and(|value| value.len() > MAX_API_KEY_BYTES) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "api key is too large",
        ));
    }
    let accepts_base_url = PROVIDERS_WITH_BASE_URL.contains(&provider);
    if base_url.is_some() && !accepts_base_url {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "provider does not accept a base_url",
        ));
    }
    if base_url.is_some_and(|value| value.trim().len() > MAX_BASE_URL_BYTES) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "base_url is too large",
        ));
    }
    let normalized_base_url = base_url.map(|value| value.trim().to_owned());
    if let Some(url) = normalized_base_url.as_deref() {
        if !url.is_empty() && !(url.starts_with("http://") || url.starts_with("https://")) {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "base_url must be an http(s) URL",
            ));
        }
    }

    let mut previous = vault.get(provider)?;
    let previous_base_url = if accepts_base_url {
        vault.get_base_url(provider)?
    } else {
        None
    };
    let mutation = match api_key {
        Some(value) => vault.set(provider, value),
        None => vault.delete(provider).map(|_| ()),
    };
    if let Err(error) = mutation {
        if let Some(value) = previous.as_mut() {
            value.zeroize();
        }
        return Err(error);
    }

    if accepts_base_url {
        let base_result = if normalized_base_url
            .as_deref()
            .is_some_and(|value| !value.is_empty())
        {
            vault.set_base_url(provider, normalized_base_url.as_deref())
        } else {
            vault.set_base_url(provider, None)
        };
        if let Err(error) = base_result {
            let rollback = restore_provider_secret(
                vault,
                provider,
                previous.as_deref(),
                previous_base_url.as_deref(),
                accepts_base_url,
            );
            if let Some(value) = previous.as_mut() {
                value.zeroize();
            }
            if rollback.is_err() {
                return Err(io::Error::other("secret update failed and rollback failed"));
            }
            return Err(error);
        }
    }

    if let Err(sync_error) = sync_runtime() {
        if sync_error.kind() == io::ErrorKind::ConnectionAborted {
            if let Some(value) = previous.as_mut() {
                value.zeroize();
            }
            return Err(sync_error);
        }
        let rollback = restore_provider_secret(
            vault,
            provider,
            previous.as_deref(),
            previous_base_url.as_deref(),
            accepts_base_url,
        );
        if let Some(value) = previous.as_mut() {
            value.zeroize();
        }
        if rollback.is_err() {
            return Err(io::Error::other("secret update failed and rollback failed"));
        }
        return Err(sync_error);
    }

    if let Some(value) = previous.as_mut() {
        value.zeroize();
    }
    Ok(api_key.is_some())
}

fn restore_provider_secret(
    vault: &impl SecretVault,
    provider: &str,
    api_key: Option<&str>,
    base_url: Option<&str>,
    manages_base_url: bool,
) -> io::Result<()> {
    match api_key {
        Some(value) => vault.set(provider, value)?,
        None => {
            vault.delete(provider)?;
        }
    }
    if manages_base_url {
        vault.set_base_url(provider, base_url)?;
    }
    Ok(())
}

#[derive(Serialize)]
pub struct CustomProviderRecord {
    pub slug: String,
    pub base_url: String,
    pub failover_eligible: bool,
}

pub fn list_custom_providers(vault: &impl SecretVault) -> io::Result<Vec<CustomProviderRecord>> {
    let mut rows = Vec::new();
    for slug in vault.list_custom_slugs()? {
        let provider = format!("custom:{slug}");
        let base_url = vault.get_base_url(&provider)?.unwrap_or_default();
        let failover_eligible = vault.get_failover_flag(&provider)?.unwrap_or(false);
        rows.push(CustomProviderRecord {
            slug,
            base_url,
            failover_eligible,
        });
    }
    rows.sort_by(|a, b| a.slug.cmp(&b.slug));
    Ok(rows)
}

pub fn set_custom_provider(
    vault: &impl SecretVault,
    slug: &str,
    base_url: &str,
    api_key: &str,
    failover_eligible: bool,
    sync_runtime: impl FnOnce() -> io::Result<()>,
) -> io::Result<()> {
    validate_custom_slug(slug)?;
    let trimmed_url = base_url.trim();
    if !(trimmed_url.starts_with("http://") || trimmed_url.starts_with("https://")) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "base_url must be an http(s) URL",
        ));
    }
    if trimmed_url.len() > MAX_BASE_URL_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "base_url is too large",
        ));
    }
    if api_key.trim().is_empty() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "api key must not be empty",
        ));
    }
    if api_key.len() > MAX_API_KEY_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "api key is too large",
        ));
    }
    let provider = format!("custom:{slug}");
    let mut previous_key = vault.get(&provider)?;
    let previous_url = vault.get_base_url(&provider)?;
    let previous_flag = vault.get_failover_flag(&provider)?;
    let was_registered = vault.list_custom_slugs()?.iter().any(|value| value == slug);
    vault.set(&provider, api_key)?;
    let url_result = vault.set_base_url(&provider, Some(trimmed_url));
    let flag_result = vault.set_failover_flag(&provider, Some(failover_eligible));
    let index_result = vault.set_custom_slug_registered(slug, true);
    // Roll back the api_key if any of the metadata writes failed.
    if url_result.is_err() || flag_result.is_err() || index_result.is_err() {
        let rollback = restore_custom_provider(
            vault,
            slug,
            previous_key.as_deref(),
            previous_url.as_deref(),
            previous_flag,
            was_registered,
        );
        if let Some(value) = previous_key.as_mut() {
            value.zeroize();
        }
        return if rollback.is_ok() {
            Err(io::Error::other("custom provider metadata write failed"))
        } else {
            Err(io::Error::other(
                "custom provider update failed and rollback failed",
            ))
        };
    }
    if let Err(error) = sync_runtime() {
        if error.kind() == io::ErrorKind::ConnectionAborted {
            if let Some(value) = previous_key.as_mut() {
                value.zeroize();
            }
            return Err(error);
        }
        let rollback = restore_custom_provider(
            vault,
            slug,
            previous_key.as_deref(),
            previous_url.as_deref(),
            previous_flag,
            was_registered,
        );
        if let Some(value) = previous_key.as_mut() {
            value.zeroize();
        }
        return if rollback.is_ok() {
            Err(error)
        } else {
            Err(io::Error::other(
                "custom provider update failed and rollback failed",
            ))
        };
    }
    if let Some(value) = previous_key.as_mut() {
        value.zeroize();
    }
    Ok(())
}

pub fn delete_custom_provider(
    vault: &impl SecretVault,
    slug: &str,
    sync_runtime: impl FnOnce() -> io::Result<()>,
) -> io::Result<bool> {
    validate_custom_slug(slug)?;
    let provider = format!("custom:{slug}");
    let mut previous_key = vault.get(&provider)?;
    let previous_url = vault.get_base_url(&provider)?;
    let previous_flag = vault.get_failover_flag(&provider)?;
    let was_registered = vault.list_custom_slugs()?.iter().any(|value| value == slug);
    let _ = vault.set_custom_slug_registered(slug, false);
    let _ = vault.set_base_url(&provider, None);
    let _ = vault.set_failover_flag(&provider, None);
    let existed = vault.delete(&provider)?;
    if let Err(error) = sync_runtime() {
        if error.kind() == io::ErrorKind::ConnectionAborted {
            if let Some(value) = previous_key.as_mut() {
                value.zeroize();
            }
            return Err(error);
        }
        let rollback = restore_custom_provider(
            vault,
            slug,
            previous_key.as_deref(),
            previous_url.as_deref(),
            previous_flag,
            was_registered,
        );
        if let Some(value) = previous_key.as_mut() {
            value.zeroize();
        }
        return if rollback.is_ok() {
            Err(error)
        } else {
            Err(io::Error::other(
                "custom provider delete failed and rollback failed",
            ))
        };
    }
    if let Some(value) = previous_key.as_mut() {
        value.zeroize();
    }
    Ok(existed)
}

fn restore_custom_provider(
    vault: &impl SecretVault,
    slug: &str,
    api_key: Option<&str>,
    base_url: Option<&str>,
    failover_eligible: Option<bool>,
    registered: bool,
) -> io::Result<()> {
    let provider = format!("custom:{slug}");
    match api_key {
        Some(value) => vault.set(&provider, value)?,
        None => {
            vault.delete(&provider)?;
        }
    }
    vault.set_base_url(&provider, base_url)?;
    vault.set_failover_flag(&provider, failover_eligible)?;
    vault.set_custom_slug_registered(slug, registered)
}

#[cfg(target_os = "macos")]
impl SecretVault for PlatformSecretVault {
    fn get(&self, provider: &str) -> io::Result<Option<String>> {
        use security_framework::passwords::get_generic_password;
        use security_framework_sys::base::errSecItemNotFound;

        let provider = validate_provider_account(provider)?;
        match get_generic_password(KEYCHAIN_SERVICE, provider) {
            Ok(mut value) => match std::str::from_utf8(&value) {
                Ok(text) => {
                    let result = text.to_owned();
                    value.zeroize();
                    Ok(Some(result))
                }
                Err(_) => {
                    value.zeroize();
                    Err(io::Error::new(
                        io::ErrorKind::InvalidData,
                        "invalid keychain value",
                    ))
                }
            },
            Err(error) if error.code() == errSecItemNotFound => Ok(None),
            Err(error) => Err(io::Error::other(format!("keychain read failed: {error}"))),
        }
    }

    fn set(&self, provider: &str, value: &str) -> io::Result<()> {
        use security_framework::passwords::set_generic_password;

        let provider = validate_provider_account(provider)?;
        if value.trim().is_empty() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "api key must not be empty",
            ));
        }
        if value.trim() != value {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "api key must not contain surrounding whitespace",
            ));
        }
        if value.len() > MAX_API_KEY_BYTES {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "api key is too large",
            ));
        }
        set_generic_password(KEYCHAIN_SERVICE, provider, value.as_bytes())
            .map_err(|error| io::Error::other(format!("keychain write failed: {error}")))
    }

    fn delete(&self, provider: &str) -> io::Result<bool> {
        use security_framework::passwords::delete_generic_password;
        use security_framework_sys::base::errSecItemNotFound;

        let provider = validate_provider_account(provider)?;
        match delete_generic_password(KEYCHAIN_SERVICE, provider) {
            Ok(()) => Ok(true),
            Err(error) if error.code() == errSecItemNotFound => Ok(false),
            Err(error) => Err(io::Error::other(format!("keychain delete failed: {error}"))),
        }
    }

    fn get_base_url(&self, provider: &str) -> io::Result<Option<String>> {
        use security_framework::passwords::get_generic_password;
        use security_framework_sys::base::errSecItemNotFound;

        validate_provider_account(provider)?;
        let account = format!("{provider}:base_url");
        match get_generic_password(KEYCHAIN_SERVICE, &account) {
            Ok(bytes) => match String::from_utf8(bytes) {
                Ok(text) => {
                    let trimmed = text.trim();
                    if trimmed.is_empty() {
                        Ok(None)
                    } else {
                        Ok(Some(trimmed.to_owned()))
                    }
                }
                Err(_) => Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "invalid keychain value",
                )),
            },
            Err(error) if error.code() == errSecItemNotFound => Ok(None),
            Err(error) => Err(io::Error::other(format!("keychain read failed: {error}"))),
        }
    }

    fn set_base_url(&self, provider: &str, value: Option<&str>) -> io::Result<()> {
        use security_framework::passwords::{delete_generic_password, set_generic_password};
        use security_framework_sys::base::errSecItemNotFound;

        validate_provider_account(provider)?;
        let account = format!("{provider}:base_url");
        match value.map(str::trim) {
            Some(text) if !text.is_empty() => {
                if text.len() > MAX_BASE_URL_BYTES {
                    return Err(io::Error::new(
                        io::ErrorKind::InvalidInput,
                        "base_url is too large",
                    ));
                }
                set_generic_password(KEYCHAIN_SERVICE, &account, text.as_bytes())
                    .map_err(|error| io::Error::other(format!("keychain write failed: {error}")))
            }
            _ => match delete_generic_password(KEYCHAIN_SERVICE, &account) {
                Ok(()) => Ok(()),
                Err(error) if error.code() == errSecItemNotFound => Ok(()),
                Err(error) => Err(io::Error::other(format!("keychain delete failed: {error}"))),
            },
        }
    }

    fn get_failover_flag(&self, provider: &str) -> io::Result<Option<bool>> {
        use security_framework::passwords::get_generic_password;
        use security_framework_sys::base::errSecItemNotFound;

        validate_custom_provider(provider)?;
        let account = format!("{provider}:failover");
        match get_generic_password(KEYCHAIN_SERVICE, &account) {
            Ok(bytes) => match String::from_utf8(bytes) {
                Ok(text) => Ok(Some(text.trim() == "1")),
                Err(_) => Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "invalid keychain value",
                )),
            },
            Err(error) if error.code() == errSecItemNotFound => Ok(None),
            Err(error) => Err(io::Error::other(format!("keychain read failed: {error}"))),
        }
    }

    fn set_failover_flag(&self, provider: &str, value: Option<bool>) -> io::Result<()> {
        use security_framework::passwords::{delete_generic_password, set_generic_password};
        use security_framework_sys::base::errSecItemNotFound;

        validate_custom_provider(provider)?;
        let account = format!("{provider}:failover");
        match value {
            Some(flag) => {
                let text = if flag { "1" } else { "0" };
                set_generic_password(KEYCHAIN_SERVICE, &account, text.as_bytes())
                    .map_err(|error| io::Error::other(format!("keychain write failed: {error}")))
            }
            None => match delete_generic_password(KEYCHAIN_SERVICE, &account) {
                Ok(()) => Ok(()),
                Err(error) if error.code() == errSecItemNotFound => Ok(()),
                Err(error) => Err(io::Error::other(format!("keychain delete failed: {error}"))),
            },
        }
    }

    fn list_custom_slugs(&self) -> io::Result<Vec<String>> {
        use security_framework::passwords::get_generic_password;
        use security_framework_sys::base::errSecItemNotFound;

        match get_generic_password(KEYCHAIN_SERVICE, "custom-providers-index") {
            Ok(bytes) => match String::from_utf8(bytes) {
                Ok(text) => {
                    let trimmed = text.trim();
                    if trimmed.is_empty() {
                        Ok(Vec::new())
                    } else {
                        Ok(trimmed.split('\n').map(|s| s.to_owned()).collect())
                    }
                }
                Err(_) => Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "invalid keychain value",
                )),
            },
            Err(error) if error.code() == errSecItemNotFound => Ok(Vec::new()),
            Err(error) => Err(io::Error::other(format!("keychain read failed: {error}"))),
        }
    }

    fn set_custom_slug_registered(&self, slug: &str, registered: bool) -> io::Result<()> {
        use security_framework::passwords::set_generic_password;

        validate_custom_slug(slug)?;
        let mut slugs = self.list_custom_slugs().unwrap_or_default();
        if registered {
            if !slugs.iter().any(|s| s == slug) {
                slugs.push(slug.to_owned());
            }
        } else {
            slugs.retain(|s| s != slug);
        }
        let payload = slugs.join("\n");
        set_generic_password(
            KEYCHAIN_SERVICE,
            "custom-providers-index",
            payload.as_bytes(),
        )
        .map_err(|error| io::Error::other(format!("keychain write failed: {error}")))
    }
}

fn validate_custom_slug(slug: &str) -> io::Result<()> {
    let valid = !slug.is_empty()
        && slug.len() <= 64
        && slug.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-')
        && !slug.starts_with('-')
        && !slug.ends_with('-');
    if valid {
        Ok(())
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid custom provider slug",
        ))
    }
}

fn validate_custom_provider(provider: &str) -> io::Result<()> {
    if let Some(slug) = provider.strip_prefix("custom:") {
        validate_custom_slug(slug)
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "not a custom provider",
        ))
    }
}

#[cfg(not(target_os = "macos"))]
impl SecretVault for PlatformSecretVault {
    fn get(&self, provider: &str) -> io::Result<Option<String>> {
        validate_provider_account(provider)?;
        Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "native secret vault is not available on this platform",
        ))
    }

    fn set(&self, provider: &str, _value: &str) -> io::Result<()> {
        validate_provider_account(provider)?;
        Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "native secret vault is not available on this platform",
        ))
    }

    fn delete(&self, provider: &str) -> io::Result<bool> {
        validate_provider_account(provider)?;
        Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "native secret vault is not available on this platform",
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::{
        delete_custom_provider, encode_secret_bootstrap, set_custom_provider,
        update_provider_secret, validate_provider_account, SecretVault,
    };
    use codinal_providers::{ProviderId, ProviderSecrets};
    use std::collections::{BTreeMap, BTreeSet};
    use std::io;
    use std::sync::Mutex;

    struct CustomVault;

    #[derive(Default)]
    struct MemoryVault {
        keys: Mutex<BTreeMap<String, String>>,
        urls: Mutex<BTreeMap<String, String>>,
        flags: Mutex<BTreeMap<String, bool>>,
        slugs: Mutex<BTreeSet<String>>,
    }

    impl SecretVault for MemoryVault {
        fn get(&self, provider: &str) -> io::Result<Option<String>> {
            Ok(self.keys.lock().expect("keys").get(provider).cloned())
        }

        fn set(&self, provider: &str, value: &str) -> io::Result<()> {
            self.keys
                .lock()
                .expect("keys")
                .insert(provider.to_owned(), value.to_owned());
            Ok(())
        }

        fn delete(&self, provider: &str) -> io::Result<bool> {
            Ok(self.keys.lock().expect("keys").remove(provider).is_some())
        }

        fn get_base_url(&self, provider: &str) -> io::Result<Option<String>> {
            Ok(self.urls.lock().expect("urls").get(provider).cloned())
        }

        fn set_base_url(&self, provider: &str, value: Option<&str>) -> io::Result<()> {
            let mut urls = self.urls.lock().expect("urls");
            match value {
                Some(value) => {
                    urls.insert(provider.to_owned(), value.to_owned());
                }
                None => {
                    urls.remove(provider);
                }
            }
            Ok(())
        }

        fn get_failover_flag(&self, provider: &str) -> io::Result<Option<bool>> {
            Ok(self.flags.lock().expect("flags").get(provider).copied())
        }

        fn set_failover_flag(&self, provider: &str, value: Option<bool>) -> io::Result<()> {
            let mut flags = self.flags.lock().expect("flags");
            match value {
                Some(value) => {
                    flags.insert(provider.to_owned(), value);
                }
                None => {
                    flags.remove(provider);
                }
            }
            Ok(())
        }

        fn list_custom_slugs(&self) -> io::Result<Vec<String>> {
            Ok(self.slugs.lock().expect("slugs").iter().cloned().collect())
        }

        fn set_custom_slug_registered(&self, slug: &str, registered: bool) -> io::Result<()> {
            let mut slugs = self.slugs.lock().expect("slugs");
            if registered {
                slugs.insert(slug.to_owned());
            } else {
                slugs.remove(slug);
            }
            Ok(())
        }
    }

    impl SecretVault for CustomVault {
        fn get(&self, provider: &str) -> io::Result<Option<String>> {
            Ok((provider == "custom:Local").then(|| "custom-secret".to_owned()))
        }

        fn set(&self, _provider: &str, _value: &str) -> io::Result<()> {
            unreachable!()
        }

        fn delete(&self, _provider: &str) -> io::Result<bool> {
            unreachable!()
        }

        fn get_base_url(&self, provider: &str) -> io::Result<Option<String>> {
            Ok((provider == "custom:Local").then(|| "localhost:8080".to_owned()))
        }

        fn get_failover_flag(&self, provider: &str) -> io::Result<Option<bool>> {
            Ok((provider == "custom:Local").then_some(true))
        }

        fn list_custom_slugs(&self) -> io::Result<Vec<String>> {
            Ok(vec!["Local".to_owned()])
        }
    }

    #[test]
    fn encoder_and_native_parser_share_custom_provider_contract() {
        assert!(validate_provider_account("custom:Local").is_ok());
        let token = "0123456789abcdef0123456789abcdef";
        let payload = encode_secret_bootstrap(&CustomVault, token).expect("encode");
        let parsed = ProviderSecrets::from_bootstrap(&payload).expect("parse");
        let provider = ProviderId::Custom("Local".to_owned());
        assert_eq!(parsed.api_key(&provider), Some("custom-secret"));
        assert_eq!(parsed.base_url(&provider), Some("localhost:8080"));
    }

    #[test]
    fn indeterminate_custom_sync_keeps_keychain_as_restart_source_of_truth() {
        let vault = MemoryVault::default();
        let indeterminate = || {
            Err(io::Error::new(
                io::ErrorKind::ConnectionAborted,
                "response lost after commit",
            ))
        };
        assert!(set_custom_provider(
            &vault,
            "local",
            "http://127.0.0.1:1234/v1",
            "new-secret",
            true,
            indeterminate,
        )
        .is_err());
        assert_eq!(
            vault.get("custom:local").expect("key"),
            Some("new-secret".to_owned())
        );
        assert_eq!(vault.list_custom_slugs().expect("slugs"), vec!["local"]);

        assert!(delete_custom_provider(&vault, "local", indeterminate).is_err());
        assert_eq!(vault.get("custom:local").expect("key"), None);
        assert!(vault.list_custom_slugs().expect("slugs").is_empty());
    }

    #[test]
    fn definite_omniroute_rejection_restores_key_and_base_url() {
        let vault = MemoryVault::default();
        vault.set("omniroute", "old-key").expect("old key");
        vault
            .set_base_url("omniroute", Some("https://old.example/v1"))
            .expect("old URL");
        let result = update_provider_secret(
            &vault,
            "omniroute",
            Some("new-key"),
            Some("https://new.example/v1"),
            || Err(io::Error::new(io::ErrorKind::InvalidData, "rejected")),
        );
        assert!(result.is_err());
        assert_eq!(
            vault.get("omniroute").expect("key"),
            Some("old-key".to_owned())
        );
        assert_eq!(
            vault.get_base_url("omniroute").expect("URL"),
            Some("https://old.example/v1".to_owned())
        );
    }
}
