//! Small, reusable accessibility contracts for the native shell.
//!
//! GPUI owns the platform accessibility tree. This module keeps labels,
//! keyboard activation, and stable element identity deterministic so leaf
//! views do not invent divergent safety semantics.

use gpui::KeyDownEvent;

pub(crate) fn stable_element_id(prefix: &str, key: &str) -> String {
    format!("{prefix}:{key}")
}

pub(crate) fn is_activation_key(event: &KeyDownEvent) -> bool {
    matches!(
        event.keystroke.key.to_ascii_lowercase().as_str(),
        "enter" | "space"
    )
}

pub(crate) fn disabled_reason_label(reason: &str) -> &str {
    let reason = reason.trim();
    if reason.contains("owner_bootstrap_deferred") {
        return "Native runtime setup is still completing";
    }
    match reason {
        "provider_not_configured" => "Configure a provider in Environment before running",
        "experimental_execution_disabled" => "Execution is disabled in this launch",
        "runtime_read_only" => "The native runtime is read-only",
        "surface_not_implemented" => "This surface is not implemented in the native runtime",
        _ => reason,
    }
}

#[cfg(test)]
mod tests {
    use super::{disabled_reason_label, stable_element_id};

    #[test]
    fn safety_reason_labels_are_truthful_and_stable() {
        assert_eq!(
            disabled_reason_label("runtime:owner_bootstrap_deferred"),
            "Native runtime setup is still completing"
        );
        assert_eq!(
            disabled_reason_label("provider_not_configured"),
            "Configure a provider in Environment before running"
        );
        assert_eq!(disabled_reason_label("custom_reason"), "custom_reason");
        assert_eq!(
            stable_element_id("approval", "approval-1"),
            "approval:approval-1"
        );
    }
}
