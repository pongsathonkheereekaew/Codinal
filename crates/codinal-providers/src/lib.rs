//! Stable provider identifiers shared with the native Keychain contract.

use serde::Deserialize;
use std::collections::BTreeMap;
use std::io;
use zeroize::Zeroizing;

const MAX_BOOTSTRAP_BYTES: usize = 128 * 1024;
const MAX_API_KEY_BYTES: usize = 16 * 1024;
const MAX_BASE_URL_BYTES: usize = 512;

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

#[cfg(test)]
mod tests {
    use super::{ProviderId, ProviderSecrets};

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
}
