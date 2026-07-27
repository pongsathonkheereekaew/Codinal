use std::collections::BTreeMap;
use std::io;

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
}

#[derive(Default)]
pub struct PlatformSecretVault;

#[derive(Serialize)]
struct ProviderSecret {
    api_key: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    base_url: Option<String>,
}

#[derive(Serialize)]
struct SecretBootstrap {
    sync_token: String,
    profiles: BTreeMap<String, ProviderSecret>,
}

#[derive(Serialize)]
pub struct ProviderSecretStatus {
    provider: &'static str,
    configured: bool,
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

pub fn encode_secret_bootstrap(vault: &impl SecretVault, sync_token: &str) -> io::Result<Vec<u8>> {
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
                ProviderSecret { api_key, base_url },
            );
        }
    }
    let mut bootstrap = SecretBootstrap {
        sync_token: sync_token.to_owned(),
        profiles,
    };
    let result =
        serde_json::to_vec(&bootstrap).map_err(|error| io::Error::other(error.to_string()));
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
            let rollback = match previous.as_deref() {
                Some(value) => vault.set(provider, value),
                None => vault.delete(provider).map(|_| ()),
            };
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
        let rollback = match previous.as_deref() {
            Some(value) => vault.set(provider, value),
            None => vault.delete(provider).map(|_| ()),
        };
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

#[cfg(target_os = "macos")]
impl SecretVault for PlatformSecretVault {
    fn get(&self, provider: &str) -> io::Result<Option<String>> {
        use security_framework::passwords::get_generic_password;
        use security_framework_sys::base::errSecItemNotFound;

        let provider = validate_provider(provider)?;
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

        let provider = validate_provider(provider)?;
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

        let provider = validate_provider(provider)?;
        match delete_generic_password(KEYCHAIN_SERVICE, provider) {
            Ok(()) => Ok(true),
            Err(error) if error.code() == errSecItemNotFound => Ok(false),
            Err(error) => Err(io::Error::other(format!("keychain delete failed: {error}"))),
        }
    }

    fn get_base_url(&self, provider: &str) -> io::Result<Option<String>> {
        use security_framework::passwords::get_generic_password;
        use security_framework_sys::base::errSecItemNotFound;

        validate_provider(provider)?;
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

        validate_provider(provider)?;
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
}

#[cfg(not(target_os = "macos"))]
impl SecretVault for PlatformSecretVault {
    fn get(&self, provider: &str) -> io::Result<Option<String>> {
        validate_provider(provider)?;
        Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "native secret vault is not available on this platform",
        ))
    }

    fn set(&self, provider: &str, _value: &str) -> io::Result<()> {
        validate_provider(provider)?;
        Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "native secret vault is not available on this platform",
        ))
    }

    fn delete(&self, provider: &str) -> io::Result<bool> {
        validate_provider(provider)?;
        Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "native secret vault is not available on this platform",
        ))
    }
}
