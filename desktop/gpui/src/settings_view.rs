//! GPUI presentation for provider settings and signed updates.
//!
//! Buttons here only delegate to existing native Rust controllers. No provider
//! credential, updater, or runtime authority is stored in this view module.

use crate::light_theme::{color, layout};
use crate::{
    disabled_reason_label, stable_element_id, CustomProviderEditTarget, ProviderDeleteTarget,
    WorkspacePrototype,
};
use gpui::{
    div, px, rgb, Context, InteractiveElement, ParentElement, StatefulInteractiveElement, Styled,
};

pub(crate) fn updater_pane(
    status: &str,
    configured: bool,
    update_available: bool,
    idle: bool,
    restart_required: bool,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let mut actions = div().flex().flex_row().flex_wrap();
    if configured && idle && !restart_required {
        actions = actions.child(
            div()
                .id("update-check")
                .mr_2()
                .px_2()
                .py_1()
                .rounded_md()
                .bg(rgb(color::SURFACE))
                .text_color(rgb(color::TEXT_SECONDARY))
                .role(gpui::Role::Button)
                .aria_label("Check for updates")
                .tab_index(0)
                .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                .child("Check for updates")
                .on_click(cx.listener(|this, _, _, cx| this.check_for_update(cx))),
        );
        if update_available {
            actions = actions.child(
                div()
                    .id("update-install")
                    .mr_2()
                    .px_2()
                    .py_1()
                    .rounded_md()
                    .bg(rgb(color::ACCENT_MUTED))
                    .text_color(rgb(color::SUCCESS))
                    .role(gpui::Role::Button)
                    .aria_label("Install signed update")
                    .tab_index(0)
                    .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                    .child("Install signed update")
                    .on_click(cx.listener(|this, _, window, cx| {
                        this.show_update_install_prompt(window, cx);
                    })),
            );
        }
    }
    if configured && idle {
        if restart_required {
            actions = actions.child(
                div()
                    .id("update-restart")
                    .mr_2()
                    .px_2()
                    .py_1()
                    .rounded_md()
                    .bg(rgb(color::ACCENT_MUTED))
                    .text_color(rgb(color::SUCCESS))
                    .role(gpui::Role::Button)
                    .aria_label("Restart after signed update")
                    .tab_index(0)
                    .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                    .child("Restart now")
                    .on_click(cx.listener(|this, _, _, cx| this.restart_after_update(cx))),
            );
        }
        actions = actions.child(
            div()
                .id("update-rollback")
                .px_2()
                .py_1()
                .rounded_md()
                .bg(rgb(color::DANGER_MUTED))
                .text_color(rgb(color::DANGER))
                .role(gpui::Role::Button)
                .aria_label("Restore previous signed version")
                .tab_index(0)
                .focus_visible(|style| style.bg(rgb(color::DANGER_MUTED)))
                .child("Restore previous version")
                .on_click(cx.listener(|this, _, window, cx| {
                    this.show_update_rollback_prompt(window, cx);
                })),
        );
    }
    div()
        .id("native-updater-pane")
        .role(gpui::Role::Region)
        .aria_label("Native signed updater")
        .aria_description(status.to_owned())
        .border_t_1()
        .border_color(rgb(color::BORDER))
        .p_3()
        .child(
            div()
                .text_size(px(layout::TYPE_CONTROL))
                .child("Native updater"),
        )
        .child(
            div()
                .mt_1()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_SECONDARY))
                .child(status.to_owned()),
        )
        .child(div().mt_2().child(actions))
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn provider_settings_pane(
    settings: &str,
    probe_status: &str,
    delete_targets: &[ProviderDeleteTarget],
    edit_targets: &[String],
    custom_edit_targets: &[CustomProviderEditTarget],
    actions_enabled: bool,
    probe_enabled: bool,
    disabled_reason: &str,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let mut pane = div()
        .id("provider-settings-pane")
        .max_h(px(300.0))
        .overflow_y_scroll()
        .border_t_1()
        .border_color(rgb(color::BORDER))
        .p_3()
        .child(
            div()
                .text_size(px(layout::TYPE_CONTROL))
                .child("Provider settings"),
        )
        .child(
            div()
                .mt_2()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_SECONDARY))
                .child(settings.to_owned()),
        );
    pane = pane.child(
        div()
            .mt_2()
            .text_size(px(layout::TYPE_METADATA))
            .text_color(rgb(color::TEXT_SECONDARY))
            .child(probe_status.to_owned()),
    );
    let mut edit_actions = div().flex().flex_row().flex_wrap();
    if probe_enabled {
        edit_actions = edit_actions.child(
            div()
                .id("probe-provider-capability")
                .mt_2()
                .mr_2()
                .px_2()
                .py_1()
                .rounded_md()
                .bg(rgb(color::ACCENT_MUTED))
                .text_color(rgb(color::ACCENT))
                .role(gpui::Role::Button)
                .aria_label("Check provider capability")
                .tab_index(0)
                .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                .child("Check provider capability")
                .on_click(cx.listener(|this, _, _, cx| {
                    this.probe_provider_capability(cx);
                })),
        );
    }
    for provider in edit_targets.iter() {
        if !actions_enabled {
            break;
        }
        let provider = provider.clone();
        let label = format!("Set {provider} credential…");
        edit_actions = edit_actions.child(
            div()
                .id(stable_element_id("set-provider-credential", &provider))
                .mt_2()
                .mr_2()
                .px_2()
                .py_1()
                .rounded_md()
                .bg(rgb(color::SURFACE))
                .role(gpui::Role::Button)
                .aria_label(label.clone())
                .tab_index(0)
                .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                .child(label)
                .on_click(cx.listener(move |this, _, _, cx| {
                    this.show_provider_edit_prompt(provider.clone(), cx);
                })),
        );
    }
    for provider in custom_edit_targets.iter() {
        if !actions_enabled {
            break;
        }
        let provider = provider.clone();
        let label = format!("Edit custom:{}…", provider.slug);
        edit_actions = edit_actions.child(
            div()
                .id(stable_element_id("edit-custom-provider", &provider.slug))
                .mt_2()
                .mr_2()
                .px_2()
                .py_1()
                .rounded_md()
                .bg(rgb(color::SURFACE))
                .role(gpui::Role::Button)
                .aria_label(label.clone())
                .tab_index(0)
                .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                .child(label)
                .on_click(cx.listener(move |this, _, _, cx| {
                    this.show_custom_provider_edit_prompt(Some(provider.clone()), cx);
                })),
        );
    }
    if actions_enabled {
        edit_actions = edit_actions.child(
            div()
                .id("add-custom-provider")
                .mt_2()
                .mr_2()
                .px_2()
                .py_1()
                .rounded_md()
                .bg(rgb(color::SURFACE))
                .role(gpui::Role::Button)
                .aria_label("Add custom provider")
                .tab_index(0)
                .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                .child("Add custom provider…")
                .on_click(cx.listener(|this, _, _, cx| {
                    this.show_custom_provider_edit_prompt(None, cx);
                })),
        );
    }
    if !actions_enabled {
        pane = pane.child(
            div()
                .mt_2()
                .text_size(px(layout::TYPE_BODY))
                .text_color(rgb(color::TEXT_SECONDARY))
                .child(format!(
                    "Provider changes unavailable · {}",
                    disabled_reason_label(disabled_reason)
                )),
        );
    }
    pane = pane.child(edit_actions);
    if actions_enabled {
        let mut delete_actions = div().flex().flex_row().flex_wrap();
        for target in delete_targets.iter() {
            let target = target.clone();
            let target_key = match &target {
                ProviderDeleteTarget::Standard(provider) => format!("standard:{provider}"),
                ProviderDeleteTarget::Custom(slug) => format!("custom:{slug}"),
            };
            let label = match &target {
                ProviderDeleteTarget::Standard(provider) => {
                    format!("Delete {provider} credential…")
                }
                ProviderDeleteTarget::Custom(slug) => {
                    format!("Delete custom:{slug}…")
                }
            };
            delete_actions = delete_actions.child(
                div()
                    .id(stable_element_id("delete-provider-credential", &target_key))
                    .mt_2()
                    .mr_2()
                    .px_2()
                    .py_1()
                    .rounded_md()
                    .bg(rgb(color::DANGER_MUTED))
                    .text_color(rgb(color::DANGER))
                    .role(gpui::Role::Button)
                    .aria_label(label.clone())
                    .tab_index(0)
                    .focus_visible(|style| style.bg(rgb(color::DANGER_MUTED)))
                    .child(label)
                    .on_click(cx.listener(move |this, _, window, cx| {
                        this.show_provider_delete_prompt(target.clone(), window, cx);
                    })),
            );
        }
        pane.child(delete_actions)
    } else {
        pane
    }
}
