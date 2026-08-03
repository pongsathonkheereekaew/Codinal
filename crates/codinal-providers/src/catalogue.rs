//! Pinned provider/model capability metadata used for truthful startup and
//! durable turn provenance.
//!
//! The bundled entries are display metadata only until a selected endpoint has
//! been probed. Missing synchronized metadata or probe evidence is represented
//! explicitly; it is never treated as a successful capability.

use serde::Serialize;

use super::{DEEPSEEK_ENDPOINT, DEEPSEEK_MODEL, OPENCODE_GO_ENDPOINT, OPENCODE_GO_MODEL};

pub const BUNDLED_CATALOGUE_REVISION: &str = "codinal-model-catalogue.v1.2026-08-02";
pub const MODELS_DEV_METADATA_SOURCE: &str = "models.dev";
pub const MODELS_DEV_API_SHA256: &str =
    "973d58dc69d845b3959493afc16025115eab123bee879594d9d3cedb640beeea";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum EffortVariant {
    OpenCodeGoMedium,
    DeepSeekHigh,
}

impl EffortVariant {
    pub const fn provider(self) -> &'static str {
        match self {
            Self::OpenCodeGoMedium => "opencode-go",
            Self::DeepSeekHigh => "deepseek",
        }
    }

    pub const fn value(self) -> &'static str {
        match self {
            Self::OpenCodeGoMedium => "medium",
            Self::DeepSeekHigh => "high",
        }
    }

    pub const fn wire_value(self) -> &'static str {
        match self {
            Self::OpenCodeGoMedium | Self::DeepSeekHigh => "reasoning_effort",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ProbeStatus {
    NotRun,
    Passed,
    Failed,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PricingStatus {
    Synchronized,
    Unknown,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub struct ModelPricing {
    pub input_per_million_usd_micros: u64,
    pub output_per_million_usd_micros: u64,
    pub cache_read_per_million_usd_micros: Option<u64>,
    pub cache_write_per_million_usd_micros: Option<u64>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub struct ModelCatalogueEntry {
    pub provider: &'static str,
    pub endpoint: &'static str,
    pub model: &'static str,
    pub protocol: &'static str,
    pub allowed_efforts: &'static [EffortVariant],
    pub default_effort: EffortVariant,
    pub streaming: bool,
    pub tool_calls: bool,
    pub cache_read_tokens: bool,
    pub cache_write_tokens: bool,
    pub pricing: PricingStatus,
    pub pricing_snapshot: Option<ModelPricing>,
    pub bundled_revision: &'static str,
    pub models_dev_revision: Option<&'static str>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct CapabilitySnapshot {
    pub provider: String,
    pub endpoint: String,
    pub model: String,
    pub protocol: String,
    pub requested_effort: String,
    pub effective_effort: String,
    pub effort_variant: EffortVariant,
    pub effort_wire_field: String,
    pub streaming: bool,
    pub tool_calls: bool,
    pub cache_read_tokens: bool,
    pub cache_write_tokens: bool,
    pub pricing: PricingStatus,
    pub pricing_snapshot: Option<ModelPricing>,
    pub bundled_revision: String,
    pub models_dev_source: String,
    pub models_dev_revision: Option<String>,
    pub probe_status: ProbeStatus,
}

const OPENCODE_GO_EFFORTS: &[EffortVariant] = &[EffortVariant::OpenCodeGoMedium];
const DEEPSEEK_EFFORTS: &[EffortVariant] = &[EffortVariant::DeepSeekHigh];
const OPENCODE_GO_PRICING: ModelPricing = ModelPricing {
    input_per_million_usd_micros: 950_000,
    output_per_million_usd_micros: 4_000_000,
    cache_read_per_million_usd_micros: Some(190_000),
    cache_write_per_million_usd_micros: None,
};
const DEEPSEEK_PRICING: ModelPricing = ModelPricing {
    input_per_million_usd_micros: 435_000,
    output_per_million_usd_micros: 870_000,
    cache_read_per_million_usd_micros: Some(3_625),
    cache_write_per_million_usd_micros: None,
};

pub static BUNDLED_MODEL_CATALOGUE: &[ModelCatalogueEntry] = &[
    ModelCatalogueEntry {
        provider: "opencode-go",
        endpoint: OPENCODE_GO_ENDPOINT,
        model: OPENCODE_GO_MODEL,
        protocol: "chat_completions_sse",
        allowed_efforts: OPENCODE_GO_EFFORTS,
        default_effort: EffortVariant::OpenCodeGoMedium,
        streaming: true,
        tool_calls: true,
        cache_read_tokens: true,
        cache_write_tokens: false,
        pricing: PricingStatus::Synchronized,
        pricing_snapshot: Some(OPENCODE_GO_PRICING),
        bundled_revision: BUNDLED_CATALOGUE_REVISION,
        models_dev_revision: Some(MODELS_DEV_API_SHA256),
    },
    ModelCatalogueEntry {
        provider: "deepseek",
        endpoint: DEEPSEEK_ENDPOINT,
        model: DEEPSEEK_MODEL,
        protocol: "chat_completions_sse",
        allowed_efforts: DEEPSEEK_EFFORTS,
        default_effort: EffortVariant::DeepSeekHigh,
        streaming: true,
        tool_calls: true,
        cache_read_tokens: true,
        cache_write_tokens: false,
        pricing: PricingStatus::Synchronized,
        pricing_snapshot: Some(DEEPSEEK_PRICING),
        bundled_revision: BUNDLED_CATALOGUE_REVISION,
        models_dev_revision: Some(MODELS_DEV_API_SHA256),
    },
];

pub fn find(provider: &str, model: &str) -> Option<&'static ModelCatalogueEntry> {
    BUNDLED_MODEL_CATALOGUE
        .iter()
        .find(|entry| entry.provider == provider && entry.model == model)
}

pub fn snapshot(
    provider: &str,
    model: &str,
    requested_effort: &str,
    probe_status: ProbeStatus,
) -> Option<CapabilitySnapshot> {
    let entry = find(provider, model)?;
    let effort = entry
        .allowed_efforts
        .iter()
        .copied()
        .find(|effort| effort.value() == requested_effort)?;
    Some(CapabilitySnapshot {
        provider: entry.provider.to_owned(),
        endpoint: entry.endpoint.to_owned(),
        model: entry.model.to_owned(),
        protocol: entry.protocol.to_owned(),
        requested_effort: requested_effort.to_owned(),
        effective_effort: effort.value().to_owned(),
        effort_variant: effort,
        effort_wire_field: effort.wire_value().to_owned(),
        streaming: entry.streaming,
        tool_calls: entry.tool_calls,
        cache_read_tokens: entry.cache_read_tokens,
        cache_write_tokens: entry.cache_write_tokens,
        pricing: entry.pricing,
        pricing_snapshot: entry.pricing_snapshot,
        bundled_revision: entry.bundled_revision.to_owned(),
        models_dev_source: MODELS_DEV_METADATA_SOURCE.to_owned(),
        models_dev_revision: entry.models_dev_revision.map(str::to_owned),
        probe_status,
    })
}

/// Estimate billable USD in microdollars only when every priced component is
/// known. An absent provider counter remains unknown instead of becoming zero.
pub fn estimate_cost_microusd(
    provider: &str,
    model: &str,
    input_tokens: Option<u64>,
    cache_read_tokens: Option<u64>,
    cache_write_tokens: Option<u64>,
    output_tokens: Option<u64>,
) -> Option<u64> {
    let pricing = find(provider, model)?.pricing_snapshot?;
    let input = u128::from(input_tokens?) * u128::from(pricing.input_per_million_usd_micros);
    let output = u128::from(output_tokens?) * u128::from(pricing.output_per_million_usd_micros);
    let cache_read = match (cache_read_tokens, pricing.cache_read_per_million_usd_micros) {
        (Some(tokens), Some(price)) => u128::from(tokens) * u128::from(price),
        (None, None) => 0,
        _ => return None,
    };
    let cache_write = match (
        cache_write_tokens,
        pricing.cache_write_per_million_usd_micros,
    ) {
        (Some(tokens), Some(price)) => u128::from(tokens) * u128::from(price),
        (None, None) => 0,
        _ => return None,
    };
    let microdollars = (input + output + cache_read + cache_write).div_ceil(1_000_000);
    u64::try_from(microdollars).ok()
}

#[cfg(test)]
mod tests {
    use super::{
        estimate_cost_microusd, find, snapshot, EffortVariant, ProbeStatus,
        BUNDLED_CATALOGUE_REVISION, MODELS_DEV_API_SHA256,
    };

    #[test]
    fn bundled_profiles_are_pinned_and_typed() {
        let opencode = find("opencode-go", "kimi-k2.7-code").expect("OpenCode profile");
        assert_eq!(opencode.default_effort, EffortVariant::OpenCodeGoMedium);
        assert_eq!(opencode.allowed_efforts, &[EffortVariant::OpenCodeGoMedium]);
        assert!(opencode.streaming && opencode.tool_calls);
        assert_eq!(opencode.models_dev_revision, Some(MODELS_DEV_API_SHA256));
        assert_eq!(opencode.pricing, super::PricingStatus::Synchronized);
        assert_eq!(
            opencode
                .pricing_snapshot
                .expect("pricing")
                .output_per_million_usd_micros,
            4_000_000
        );

        let deepseek = find("deepseek", "deepseek-v4-pro").expect("DeepSeek profile");
        assert_eq!(deepseek.default_effort, EffortVariant::DeepSeekHigh);
        assert_eq!(deepseek.allowed_efforts, &[EffortVariant::DeepSeekHigh]);
        assert!(deepseek.cache_read_tokens);
        assert_eq!(deepseek.pricing, super::PricingStatus::Synchronized);
    }

    #[test]
    fn unsupported_effort_does_not_clamp_silently() {
        assert!(snapshot("opencode-go", "kimi-k2.7-code", "high", ProbeStatus::NotRun).is_none());
        let snapshot = snapshot("deepseek", "deepseek-v4-pro", "high", ProbeStatus::NotRun)
            .expect("DeepSeek snapshot");
        assert_eq!(snapshot.requested_effort, "high");
        assert_eq!(snapshot.effective_effort, "high");
        assert_eq!(snapshot.probe_status, ProbeStatus::NotRun);
        assert_eq!(snapshot.bundled_revision, BUNDLED_CATALOGUE_REVISION);
        assert_eq!(
            snapshot.models_dev_revision,
            Some(MODELS_DEV_API_SHA256.to_owned())
        );
        assert_eq!(snapshot.pricing, super::PricingStatus::Synchronized);

        assert_eq!(
            estimate_cost_microusd(
                "deepseek",
                "deepseek-v4-pro",
                Some(11),
                Some(4),
                None,
                Some(7)
            ),
            Some(11)
        );
        assert_eq!(
            estimate_cost_microusd("deepseek", "deepseek-v4-pro", Some(11), None, None, Some(7)),
            None
        );
    }
}
