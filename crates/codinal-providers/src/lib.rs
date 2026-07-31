//! Stable provider identifiers shared with the native Keychain contract.

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ProviderId {
    OpenAi,
    Anthropic,
    Gemini,
    Ollama,
    OmniRoute,
    Custom(String),
}

impl ProviderId {
    pub fn parse(value: &str) -> Option<Self> {
        Some(match value {
            "openai" => Self::OpenAi,
            "anthropic" => Self::Anthropic,
            "gemini" => Self::Gemini,
            "ollama" => Self::Ollama,
            "omniroute" => Self::OmniRoute,
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
            Self::Ollama => "ollama".to_owned(),
            Self::OmniRoute => "omniroute".to_owned(),
            Self::Custom(slug) => format!("custom:{slug}"),
        }
    }
}

fn valid_custom_slug(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 64
        && value.bytes().all(|byte| {
            byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'-'
        })
}

#[cfg(test)]
mod tests {
    use super::ProviderId;

    #[test]
    fn stable_provider_identifiers_round_trip_to_keychain_accounts() {
        for value in ["openai", "anthropic", "gemini", "ollama", "omniroute", "custom:local-llm"] {
            let provider = ProviderId::parse(value).expect("provider");
            assert_eq!(provider.as_keychain_account(), value);
        }
    }

    #[test]
    fn unsupported_or_unsafe_provider_identifiers_fail_closed() {
        for value in ["zai", "custom:", "custom:UPPER", "custom:../../keychain"] {
            assert!(ProviderId::parse(value).is_none(), "{value}");
        }
    }
}
