use std::collections::BTreeMap;
use std::io;

use serde::Serialize;
use zeroize::Zeroize;

use crate::host::validate_session_token;

pub const SUPPORTED_PROVIDERS: [&str; 6] =
    ["anthropic", "gemini", "openai", "zai", "deepseek", "github"];
pub const MAX_API_KEY_BYTES: usize = 16 * 1024;
const KEYCHAIN_SERVICE: &str = "dev.codinal.desktop.provider-secrets";

pub trait SecretVault: Send + Sync {
    fn get(&self, provider: &str) -> io::Result<Option<String>>;
    fn set(&self, provider: &str, value: &str) -> io::Result<()>;
    fn delete(&self, provider: &str) -> io::Result<bool>;
}

#[derive(Default)]
pub struct PlatformSecretVault;

#[derive(Serialize)]
struct ProviderSecret {
    api_key: String,
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
            profiles.insert(format!("provider:{provider}"), ProviderSecret { api_key });
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
