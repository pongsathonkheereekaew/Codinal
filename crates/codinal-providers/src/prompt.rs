//! Deterministic prompt compilation shared by provider adapters.
//!
//! The stable prefix is cache metadata, not a second user-visible message. It
//! contains only versioned policy and tool-schema bytes. The dynamic suffix is
//! the exact durable conversation/tool context sent to the provider.

use sha2::{Digest, Sha256};
use std::io;

pub const PROMPT_COMPILER_VERSION: &str = "codinal.prompt.v1";
const MAX_DYNAMIC_MESSAGES: usize = 10_000;
const MAX_DYNAMIC_BYTES: usize = 4 * 1024 * 1024;
const MAX_POLICY_BYTES: usize = 64 * 1024;
const MAX_TOOL_SCHEMA_BYTES: usize = 512 * 1024;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CachePolicy {
    Disabled,
    PreferStablePrefix,
}

impl CachePolicy {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Disabled => "disabled",
            Self::PreferStablePrefix => "prefer_stable_prefix",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PromptEnvelope {
    pub stable_prefix: Vec<u8>,
    pub dynamic_suffix: Vec<serde_json::Value>,
    pub stable_prefix_hash: String,
    pub cache_policy: CachePolicy,
}

impl PromptEnvelope {
    pub fn compile(
        policy: &str,
        tools: &[serde_json::Value],
        dynamic_suffix: Vec<serde_json::Value>,
        cache_policy: CachePolicy,
    ) -> io::Result<Self> {
        if policy.is_empty()
            || policy.len() > MAX_POLICY_BYTES
            || policy.chars().any(char::is_control)
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid prompt policy",
            ));
        }
        if tools.len() > 256 || dynamic_suffix.len() > MAX_DYNAMIC_MESSAGES {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "prompt context exceeds message limit",
            ));
        }
        let tool_schema = serde_json::to_vec(tools)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        if tool_schema.len() > MAX_TOOL_SCHEMA_BYTES {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "tool schema exceeds prompt limit",
            ));
        }
        let dynamic_bytes = serde_json::to_vec(&dynamic_suffix)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        if dynamic_bytes.len() > MAX_DYNAMIC_BYTES {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "dynamic prompt context exceeds limit",
            ));
        }
        let stable_prefix = serde_json::to_vec(&serde_json::json!({
            "compiler": PROMPT_COMPILER_VERSION,
            "policy": policy,
            "tools": tools,
        }))
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        let stable_prefix_hash = format!("sha256:{:x}", Sha256::digest(&stable_prefix));
        Ok(Self {
            stable_prefix,
            dynamic_suffix,
            stable_prefix_hash,
            cache_policy,
        })
    }

    pub fn dynamic_messages(&self) -> &[serde_json::Value] {
        &self.dynamic_suffix
    }

    pub fn stable_prefix_bytes(&self) -> &[u8] {
        &self.stable_prefix
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum UsageCost {
    ProviderReported,
    CodinalEstimated,
    Unavailable,
}

impl UsageCost {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::ProviderReported => "provider_reported",
            Self::CodinalEstimated => "codinal_estimated",
            Self::Unavailable => "unavailable",
        }
    }
}

/// Provider-specific telemetry keeps unsupported fields unknown rather than
/// converting them to fabricated zeroes.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProviderUsage {
    pub input_tokens: Option<u64>,
    pub cache_read_tokens: Option<u64>,
    pub cache_write_tokens: Option<u64>,
    pub prompt_cache_hit_tokens: Option<u64>,
    pub prompt_cache_miss_tokens: Option<u64>,
    pub output_tokens: Option<u64>,
    pub first_delta_ms: Option<u64>,
    pub total_latency_ms: Option<u64>,
    pub cost: UsageCost,
}

impl ProviderUsage {
    pub fn unknown() -> Self {
        Self {
            input_tokens: None,
            cache_read_tokens: None,
            cache_write_tokens: None,
            prompt_cache_hit_tokens: None,
            prompt_cache_miss_tokens: None,
            output_tokens: None,
            first_delta_ms: None,
            total_latency_ms: None,
            cost: UsageCost::Unavailable,
        }
    }

    pub fn from_response(value: &serde_json::Value) -> io::Result<Self> {
        let object = value
            .as_object()
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid provider usage"))?;
        let optional = |names: &[&str]| {
            names
                .iter()
                .find_map(|name| object.get(*name).and_then(serde_json::Value::as_u64))
        };
        let details = object
            .get("prompt_tokens_details")
            .and_then(serde_json::Value::as_object);
        let cache_read_tokens = optional(&["cache_read_tokens", "cached_tokens"]).or_else(|| {
            details.and_then(|details| {
                optional_from_object(details, &["cached_tokens", "cache_read_tokens"])
            })
        });
        let cache_write_tokens = optional(&["cache_write_tokens", "cache_creation_input_tokens"])
            .or_else(|| {
                details.and_then(|details| {
                    optional_from_object(
                        details,
                        &["cache_write_tokens", "cache_creation_input_tokens"],
                    )
                })
            });
        Ok(Self {
            input_tokens: optional(&["input_tokens", "prompt_tokens"]),
            cache_read_tokens,
            cache_write_tokens,
            output_tokens: optional(&["output_tokens", "completion_tokens"]),
            first_delta_ms: None,
            total_latency_ms: None,
            prompt_cache_hit_tokens: None,
            prompt_cache_miss_tokens: None,
            cost: UsageCost::Unavailable,
        })
    }
}

fn optional_from_object(
    object: &serde_json::Map<String, serde_json::Value>,
    names: &[&str],
) -> Option<u64> {
    names
        .iter()
        .find_map(|name| object.get(*name).and_then(serde_json::Value::as_u64))
}

#[cfg(test)]
mod tests {
    use super::{CachePolicy, PromptEnvelope, UsageCost};

    #[test]
    fn stable_prefix_hash_is_ordered_and_dynamic_context_is_not_in_hash() {
        let tools = vec![serde_json::json!({
            "type": "function",
            "function": {"name": "read_file", "parameters": {"type": "object"}}
        })];
        let first = PromptEnvelope::compile(
            "policy.v1",
            &tools,
            vec![serde_json::json!({"role": "user", "content": "one"})],
            CachePolicy::PreferStablePrefix,
        )
        .expect("first prompt");
        let second = PromptEnvelope::compile(
            "policy.v1",
            &tools,
            vec![serde_json::json!({"role": "user", "content": "two"})],
            CachePolicy::PreferStablePrefix,
        )
        .expect("second prompt");
        assert_eq!(first.stable_prefix_hash, second.stable_prefix_hash);
        assert_ne!(first.dynamic_suffix, second.dynamic_suffix);
        assert_eq!(first.cache_policy.as_str(), "prefer_stable_prefix");
    }

    #[test]
    fn usage_keeps_provider_cache_fields_unknown_when_absent() {
        let usage = super::ProviderUsage::from_response(&serde_json::json!({
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "total_tokens": 5
        }))
        .expect("usage");
        assert_eq!(usage.input_tokens, Some(3));
        assert_eq!(usage.output_tokens, Some(2));
        assert_eq!(usage.cache_read_tokens, None);
        assert_eq!(usage.cache_write_tokens, None);
        assert_eq!(usage.cost, UsageCost::Unavailable);
    }
}
