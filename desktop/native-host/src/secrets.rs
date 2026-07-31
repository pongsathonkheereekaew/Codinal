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
    vault.set(&provider, api_key)?;
    let url_result = vault.set_base_url(&provider, Some(trimmed_url));
    let flag_result = vault.set_failover_flag(&provider, Some(failover_eligible));
    let index_result = vault.set_custom_slug_registered(slug, true);
    // Roll back the api_key if any of the metadata writes failed.
    if url_result.is_err() || flag_result.is_err() || index_result.is_err() {
        let _ = vault.delete(&provider);
        let _ = vault.set_base_url(&provider, None);
        let _ = vault.set_failover_flag(&provider, None);
        return Err(io::Error::other("custom provider metadata write failed"));
    }
    sync_runtime()?;
    Ok(())
}

pub fn delete_custom_provider(
    vault: &impl SecretVault,
    slug: &str,
    sync_runtime: impl FnOnce() -> io::Result<()>,
) -> io::Result<bool> {
    validate_custom_slug(slug)?;
    let provider = format!("custom:{slug}");
    let _ = vault.set_custom_slug_registered(slug, false);
    let _ = vault.set_base_url(&provider, None);
    let _ = vault.set_failover_flag(&provider, None);
    let existed = vault.delete(&provider)?;
    sync_runtime()?;
    Ok(existed)
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
