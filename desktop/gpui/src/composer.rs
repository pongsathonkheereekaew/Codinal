//! Composer and turn-control presentation.
//!
//! The view owns no command authority.  It emits existing workspace callbacks
//! for submit, interrupt, focus, and context-panel actions.

use crate::composer_input_is_enabled;
use crate::disabled_reason_label;
use crate::icons::{icon, Icon};
use crate::is_activation_key;
use crate::light_theme::{color, layout};
use crate::{permission_profile_label, PermissionProfile, WorkspacePrototype};
use codinal_control_plane_client::{ModelProfile, RuntimeCapabilities};
use gpui::{
    canvas, div, px, rgb, Context, ElementInputHandler, Entity, FocusHandle, InteractiveElement,
    IntoElement, KeyDownEvent, ParentElement, StatefulInteractiveElement, Styled,
};

#[allow(clippy::too_many_arguments)]
pub(crate) fn composer_pane(
    session_count: &usize,
    has_selected_session: bool,
    has_selected_project: bool,
    approval_pending: bool,
    turn_in_flight: bool,
    turn_command_in_flight: bool,
    composer_text: &str,
    capabilities: &RuntimeCapabilities,
    model_profiles: &[ModelProfile],
    selected_model_profile: &ModelProfile,
    permission_profile: PermissionProfile,
    permission_menu_open: bool,
    model_menu_open: bool,
    focus: &FocusHandle,
    entity: Entity<WorkspacePrototype>,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let active_sessions = format!("{session_count} chat(s)");
    let input_enabled = composer_input_is_enabled(
        has_selected_session,
        approval_pending,
        selected_model_profile.ready,
        turn_in_flight,
        turn_command_in_flight,
    ) && selected_model_profile.ready;
    let input_focus = focus.clone();
    let input_entity = entity.clone();
    let input_placeholder = if has_selected_session {
        "Ask Codinal to inspect, change, or explain…"
    } else if has_selected_project {
        "Do anything"
    } else {
        "Select a chat to start composing…"
    };
    let input_text = if composer_text.is_empty() {
        input_placeholder.to_owned()
    } else {
        composer_text.to_owned()
    };
    let input_color = if composer_text.is_empty() || !input_enabled {
        rgb(color::text_tertiary())
    } else {
        rgb(color::text_primary())
    };
    let composer_line_count = composer_text.split('\n').count().max(1) as f32;
    let input_height = (52.0 + (composer_line_count - 1.0) * 22.0).min(104.0);
    let composer_height =
        (layout::COMPOSER_HEIGHT + (input_height - 52.0)).min(layout::COMPOSER_HEIGHT + 78.0);
    let composer_input = div()
        .id("composer-input")
        .relative()
        .flex_1()
        .min_w(px(0.0))
        .h(px(input_height))
        .px_1()
        .py_2()
        .track_focus(focus)
        .role(gpui::Role::TextInput)
        .aria_label("Composer input")
        .aria_placeholder(input_placeholder)
        .tab_index(0)
        .focus_visible(|style| {
            style
                .bg(rgb(color::accent_muted()))
                .border_color(rgb(color::accent()))
        })
        .border_1()
        .border_color(rgb(color::border()))
        .on_click(cx.listener(|this, _, window, cx| {
            this.focus_composer(window, cx);
        }))
        .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
            if event.keystroke.key == "enter"
                && !event.keystroke.modifiers.shift
                && (event.keystroke.modifiers.platform || !event.keystroke.modifiers.control)
            {
                this.submit_composer(cx);
            }
        }))
        .child(
            div()
                .text_size(px(crate::light_theme::typography::COMPOSER))
                .text_color(input_color)
                .child(input_text),
        )
        .child(
            canvas(
                |bounds, _, _| bounds,
                move |bounds, _, window, cx| {
                    window.handle_input(
                        &input_focus,
                        ElementInputHandler::new(bounds, input_entity.clone()),
                        cx,
                    );
                },
            )
            .absolute()
            .size_full(),
        );
    let send_button: gpui::AnyElement = if input_enabled {
        div()
            .id("run-turn")
            .w(px(34.0))
            .h(px(34.0))
            .flex()
            .items_center()
            .justify_center()
            .rounded_full()
            .bg(rgb(color::text_primary()))
            .text_color(rgb(color::canvas()))
            .role(gpui::Role::Button)
            .aria_label("Run turn")
            .aria_keyshortcuts("⌘↩")
            .tab_index(0)
            .focus_visible(|style| style.bg(rgb(color::accent())))
            .hover(|style| style.bg(rgb(color::text_primary()).opacity(0.85)))
            .active(|style| style.opacity(0.7))
            .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
                if is_activation_key(event) {
                    this.submit_composer(cx);
                }
            }))
            .child(icon(Icon::Send, color::canvas()))
            .on_click(cx.listener(|this, _, _, cx| this.submit_composer(cx)))
            .into_any_element()
    } else {
        div()
            .id("run-turn-disabled")
            .w(px(34.0))
            .h(px(34.0))
            .flex()
            .items_center()
            .justify_center()
            .rounded_full()
            .bg(rgb(color::surface_selected()))
            .text_color(rgb(color::text_tertiary()))
            .role(gpui::Role::Button)
            .aria_label("Run turn unavailable")
            .aria_description(if approval_pending {
                "Resolve the pending approval before starting another turn"
            } else {
                "Turn execution is not ready"
            })
            .tab_index(0)
            .focus_visible(|style| style.bg(rgb(color::accent_muted())))
            .child(icon(Icon::Send, color::text_tertiary()))
            .into_any_element()
    };
    let mut actions = div().flex().items_center();
    if capabilities.interrupt_turn && turn_in_flight && !turn_command_in_flight {
        actions = actions.child(
            div()
                .id("interrupt-turn")
                .px_2()
                .py_1()
                .rounded_md()
                .bg(rgb(color::danger_muted()))
                .text_color(rgb(color::danger()))
                .role(gpui::Role::Button)
                .aria_label("Interrupt turn")
                .aria_keyshortcuts("Escape")
                .tab_index(0)
                .focus_visible(|style| style.bg(rgb(color::danger())))
                .active(|style| style.opacity(0.7))
                .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
                    if is_activation_key(event) {
                        this.interrupt_turn(cx);
                    }
                }))
                .child("Interrupt turn")
                .on_click(cx.listener(|this, _, _, cx| this.interrupt_turn(cx))),
        );
    } else if turn_in_flight && !turn_command_in_flight {
        let reason = capabilities
            .run_disabled_reason
            .as_deref()
            .unwrap_or("runtime_read_only");
        actions = actions.child(
            div()
                .id("interrupt-turn-disabled")
                .px_2()
                .py_1()
                .rounded_md()
                .bg(rgb(color::surface()))
                .text_color(rgb(color::text_secondary()))
                .role(gpui::Role::Button)
                .aria_label("Interrupt turn unavailable")
                .tab_index(0)
                .focus_visible(|style| style.bg(rgb(color::accent_muted())))
                .child(format!(
                    "Interrupt unavailable · {}",
                    disabled_reason_label(reason)
                )),
        );
    }
    let composer_status = if approval_pending {
        "Review the pending approval before starting another turn.".to_owned()
    } else if !has_selected_session && !has_selected_project {
        if capabilities.mutations {
            "No chat selected · use + New chat to start composing.".to_owned()
        } else {
            let reason = capabilities
                .mutation_disabled_reason
                .as_deref()
                .unwrap_or("runtime_read_only");
            format!("No chat selected · {}.", disabled_reason_label(reason))
        }
    } else if !has_selected_session {
        "Project selected · use + New chat before starting a turn.".to_owned()
    } else if !selected_model_profile.ready {
        disabled_reason_label(
            capabilities
                .run_disabled_reason
                .as_deref()
                .unwrap_or("selected model is not ready"),
        )
        .to_owned()
    } else if turn_in_flight {
        "Turn is running · live output arrives on the session stream.".to_owned()
    } else {
        "⌘↩ to run · Enter a message for the selected chat.".to_owned()
    };
    let access_label = if !capabilities.mutations {
        "Read-only"
    } else if selected_model_profile.ready {
        permission_profile_label(permission_profile)
    } else if capabilities.mutations {
        "Setup required"
    } else {
        "Read-only"
    };
    let access_color = if selected_model_profile.ready {
        color::success()
    } else {
        color::warning()
    };
    let model_label =
        if selected_model_profile.model.is_empty() || selected_model_profile.model == "unknown" {
            "Model unavailable".to_owned()
        } else {
            selected_model_profile.model.clone()
        };
    let permission_menu: gpui::AnyElement = if permission_menu_open {
        let profiles = [
            (
                PermissionProfile::AskForApproval,
                "Always ask to edit external files and use the internet",
                true,
            ),
            (
                PermissionProfile::ApproveForMe,
                "Only ask for actions detected as potentially unsafe",
                false,
            ),
            (
                PermissionProfile::FullAccess,
                "Unrestricted access to the internet and any file on your computer",
                false,
            ),
            (
                PermissionProfile::Custom,
                "Uses permissions defined in config.toml",
                false,
            ),
        ];
        let mut menu = div()
            .id("permission-profile-menu")
            .absolute()
            .bottom(px(62.0))
            .left(px(36.0))
            .w(px(360.0))
            .rounded_xl()
            .border_1()
            .border_color(rgb(color::border()))
            .bg(rgb(color::elevated()))
            .shadow_lg()
            .p_2()
            .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
                if event.keystroke.key == "escape" {
                    this.close_permission_menu(cx);
                }
            }));
        for (profile, description, available) in profiles {
            let available = available && capabilities.mutations && selected_model_profile.ready;
            let selected = profile == permission_profile;
            menu = menu.child(
                div()
                    .id(format!(
                        "permission-profile-{}",
                        permission_profile_label(profile)
                    ))
                    .px_2()
                    .py_2()
                    .rounded_lg()
                    .flex()
                    .items_start()
                    .role(gpui::Role::MenuItem)
                    .aria_label(permission_profile_label(profile))
                    .aria_description(if available {
                        "Permission profile available"
                    } else {
                        "Permission profile is not available for the selected model"
                    })
                    .tab_index(0)
                    .text_color(rgb(if available {
                        color::text_primary()
                    } else {
                        color::text_tertiary()
                    }))
                    .child(
                        div()
                            .w(px(22.0))
                            .text_color(rgb(if selected {
                                color::accent()
                            } else {
                                color::text_tertiary()
                            }))
                            .child(if selected {
                                icon(Icon::Check, color::accent()).into_any_element()
                            } else {
                                div().into_any_element()
                            }),
                    )
                    .child(
                        div()
                            .flex_1()
                            .child(div().child(permission_profile_label(profile)))
                            .child(
                                div()
                                    .mt_1()
                                    .text_size(px(layout::TYPE_METADATA))
                                    .text_color(rgb(color::text_tertiary()))
                                    .child(description),
                            ),
                    )
                    .on_click(cx.listener(move |this, _, _, cx| {
                        this.select_permission_profile(profile, cx)
                    })),
            );
        }
        menu.into_any_element()
    } else {
        div().into_any_element()
    };
    let model_menu: gpui::AnyElement = if model_menu_open {
        let mut menu = div()
            .id("model-profile-menu")
            .absolute()
            .bottom(px(62.0))
            .right(px(38.0))
            .w(px(360.0))
            .rounded_xl()
            .border_1()
            .border_color(rgb(color::border()))
            .bg(rgb(color::elevated()))
            .shadow_lg()
            .p_2()
            .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
                if event.keystroke.key == "escape" {
                    this.close_model_menu(cx);
                }
            }));
        for profile in model_profiles.iter().cloned() {
            let selected = profile.provider == selected_model_profile.provider
                && profile.model == selected_model_profile.model
                && profile.effort == selected_model_profile.effort;
            let available = profile.ready;
            let unavailable_reason = if !profile.configured {
                "Provider is not configured"
            } else if profile.probe_status != "passed" {
                "Capability probe is required"
            } else {
                "Runtime is not ready"
            };
            let profile_for_click = profile.clone();
            menu = menu.child(
                div()
                    .id(format!(
                        "model-profile-{}-{}",
                        profile.provider, profile.model
                    ))
                    .px_2()
                    .py_2()
                    .rounded_lg()
                    .flex()
                    .items_start()
                    .role(gpui::Role::MenuItem)
                    .aria_label(format!("Select model {}", profile.model))
                    .aria_description(if available {
                        format!("{} profile is ready", profile.provider)
                    } else {
                        unavailable_reason.to_owned()
                    })
                    .tab_index(0)
                    .text_color(rgb(if available {
                        color::text_primary()
                    } else {
                        color::text_tertiary()
                    }))
                    .child(
                        div()
                            .w(px(22.0))
                            .text_color(rgb(if selected {
                                color::accent()
                            } else {
                                color::text_tertiary()
                            }))
                            .child(if selected {
                                icon(Icon::Check, color::accent()).into_any_element()
                            } else {
                                div().into_any_element()
                            }),
                    )
                    .child(
                        div()
                            .flex_1()
                            .child(div().child(profile.model.clone()))
                            .child(
                                div()
                                    .mt_1()
                                    .text_size(px(layout::TYPE_METADATA))
                                    .text_color(rgb(color::text_tertiary()))
                                    .child(if available {
                                        format!("{} · {}", profile.provider, profile.effort)
                                    } else {
                                        format!(
                                            "{} · {} · {}",
                                            profile.provider, profile.effort, unavailable_reason
                                        )
                                    }),
                            ),
                    )
                    .on_click(cx.listener(move |this, _, _, cx| {
                        this.select_model_profile(profile_for_click.clone(), cx)
                    })),
            );
        }
        menu.into_any_element()
    } else {
        div().into_any_element()
    };
    let model_button = div()
        .id("model-profile-selector")
        .mr_2()
        .h(px(28.0))
        .flex()
        .items_center()
        .text_size(px(layout::TYPE_METADATA))
        .text_color(rgb(if selected_model_profile.ready {
            color::text_secondary()
        } else {
            color::text_tertiary()
        }))
        .role(gpui::Role::Button)
        .aria_label(format!("Model: {}", model_label))
        .aria_description(if selected_model_profile.ready {
            "Choose a ready provider model"
        } else {
            "Selected model is not ready"
        })
        .tab_index(0)
        .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
            if event.keystroke.key == "escape" {
                this.close_model_menu(cx);
            }
        }))
        .on_click(cx.listener(|this, _, _, cx| this.toggle_model_menu(cx)))
        .child(model_label)
        .child(icon(Icon::ChevronDown, color::text_secondary()));
    let voice_button = div()
        .id("composer-voice")
        .mr_2()
        .h(px(28.0))
        .flex()
        .items_center()
        .justify_center()
        .text_size(px(layout::TYPE_METADATA))
        .text_color(rgb(color::text_tertiary()))
        .role(gpui::Role::Button)
        .aria_label("Voice input unavailable")
        .aria_description("Voice input is not exposed by the native runtime")
        .tab_index(0)
        .child(icon(Icon::Mic, color::text_tertiary()));
    div()
        .id("composer-prompt")
        .relative()
        .w_full()
        .px_4()
        .pb_4()
        .flex()
        .justify_center()
        .bg(rgb(color::canvas()))
        .child(
            div()
                .w_full()
                .max_w(px(layout::CONTENT_MAX_WIDTH))
                .h(px(composer_height))
                .rounded_2xl()
                .border_1()
                .border_color(rgb(color::border_strong()))
                .bg(rgb(color::elevated()))
                .shadow_lg()
                .p_3()
                .child(composer_input)
                .child(
                    div()
                        .h(px(18.0))
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::text_tertiary()))
                        .child(composer_status),
                )
                .child(
                    div()
                        .mt_1()
                        .flex()
                        .items_center()
                        .justify_between()
                        .child(
                            div()
                                .flex()
                                .items_center()
                                .child(
                                    div()
                                        .id("composer-context-add")
                                        .w(px(28.0))
                                        .h(px(28.0))
                                        .mr_2()
                                        .flex()
                                        .items_center()
                                        .justify_center()
                                        .rounded_full()
                                        .bg(rgb(color::accent_muted()))
                                        .text_color(rgb(color::accent()))
                                        .role(gpui::Role::Button)
                                        .aria_label("Show Environment")
                                        .aria_keyshortcuts("⌘K")
                                        .tab_index(0)
                                        .focus_visible(|style| style.bg(rgb(color::accent_muted())))
                                        .on_key_down(cx.listener(
                                            |this, event: &KeyDownEvent, window, cx| {
                                                if is_activation_key(event) {
                                                    this.toggle_context_panel(window, cx);
                                                }
                                            },
                                        ))
                                        .child(icon(Icon::Plus, color::accent()))
                                        .on_click(cx.listener(|this, _, window, cx| {
                                            this.toggle_context_panel(window, cx);
                                        })),
                                )
                                .child(
                                    div()
                                        .mr_3()
                                        .h(px(28.0))
                                        .flex()
                                        .items_center()
                                        .text_size(px(layout::TYPE_METADATA))
                                        .text_color(rgb(access_color))
                                        .id("permission-profile")
                                        .role(gpui::Role::Button)
                                        .aria_label(format!("Permission profile: {access_label}"))
                                        .tab_index(0)
                                        .on_key_down(cx.listener(
                                            |this, event: &KeyDownEvent, _, cx| {
                                                if event.keystroke.key == "escape" {
                                                    this.close_permission_menu(cx);
                                                }
                                            },
                                        ))
                                        .on_click(cx.listener(|this, _, _, cx| {
                                            this.toggle_permission_menu(cx)
                                        }))
                                        .child(icon(Icon::Permission, access_color))
                                        .child(div().ml_1().child(access_label)),
                                )
                                .child(actions),
                        )
                        .child(
                            div()
                                .flex()
                                .items_center()
                                .child(
                                    div()
                                        .mr_2()
                                        .h(px(28.0))
                                        .flex()
                                        .items_center()
                                        .text_size(px(layout::TYPE_METADATA))
                                        .text_color(rgb(color::text_secondary()))
                                        .child(selected_model_profile.provider.clone()),
                                )
                                .child(model_button)
                                .child(
                                    div()
                                        .mr_3()
                                        .h(px(28.0))
                                        .flex()
                                        .items_center()
                                        .text_size(px(layout::TYPE_METADATA))
                                        .text_color(rgb(color::text_tertiary()))
                                        .child(format!(
                                            "{} · {active_sessions}",
                                            selected_model_profile.effort
                                        )),
                                )
                                .child(voice_button)
                                .child(send_button),
                        ),
                ),
        )
        .child(model_menu)
        .child(permission_menu)
}
