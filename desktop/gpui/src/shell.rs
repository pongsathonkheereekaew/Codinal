//! Native workspace top-bar presentation and shell toggles.

use crate::icons::{icon, Icon};
use crate::light_theme::{color, layout};
use crate::{disabled_reason_label, WorkspacePrototype};
use codinal_control_plane_client::{ProjectSummary, RuntimeCapabilities, SessionSummary};
use gpui::{
    div, px, rgb, Context, FocusHandle, InteractiveElement, IntoElement, ParentElement,
    StatefulInteractiveElement, Styled,
};

#[allow(clippy::too_many_arguments)]
pub(crate) fn header(
    title: &str,
    selected_session: Option<&SessionSummary>,
    projects: &[ProjectSummary],
    capabilities: &RuntimeCapabilities,
    navigation_visible: bool,
    navigation_width: f32,
    context_open: bool,
    tools_open: bool,
    session_menu_open: bool,
    session_action_in_flight: bool,
    mutation_disabled_reason: &str,
    oauth_status: &str,
    context_focus: &FocusHandle,
    tools_focus: &FocusHandle,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let runtime_label = if capabilities.start_turn {
        "Ready"
    } else if capabilities.mutations {
        "Setup required"
    } else {
        "Read-only"
    };
    let runtime_color = if capabilities.start_turn {
        color::SUCCESS
    } else {
        color::WARNING
    };
    let mutations_enabled = capabilities.mutations && !session_action_in_flight;
    let mut session_menu = div()
        .id("session-overflow-menu")
        .absolute()
        .top(px(36.0))
        .left(px(34.0))
        .w(px(236.0))
        .rounded_xl()
        .border_1()
        .border_color(rgb(color::BORDER))
        .bg(rgb(color::ELEVATED))
        .shadow_lg()
        .p_1();
    if let Some(session) = selected_session {
        let rename_disabled_reason = mutation_disabled_reason.to_owned();
        let mut rename = div()
            .id("session-menu-rename")
            .h(px(30.0))
            .px_2()
            .flex()
            .items_center()
            .rounded_md()
            .role(gpui::Role::MenuItem)
            .aria_label("Rename chat")
            .tab_index(0)
            .child("Rename");
        if mutations_enabled {
            rename = rename.on_click(cx.listener(|this, _, window, cx| {
                this.open_session_rename(window, cx);
            }));
        } else {
            rename = rename
                .text_color(rgb(color::TEXT_TERTIARY))
                .aria_description(disabled_reason_label(&rename_disabled_reason));
        }
        session_menu = session_menu.child(rename);

        let pin_label = if session.pinned {
            "Unpin chat"
        } else {
            "Pin chat"
        };
        let pin_disabled_reason = mutation_disabled_reason.to_owned();
        let mut pin = div()
            .id("session-menu-pin")
            .h(px(30.0))
            .px_2()
            .flex()
            .items_center()
            .rounded_md()
            .role(gpui::Role::MenuItem)
            .aria_label(pin_label)
            .tab_index(0)
            .child(pin_label);
        if mutations_enabled {
            pin = pin.on_click(cx.listener(|this, _, _, cx| {
                this.toggle_selected_session_pin(cx);
            }));
        } else {
            pin = pin
                .text_color(rgb(color::TEXT_TERTIARY))
                .aria_description(disabled_reason_label(&pin_disabled_reason));
        }
        session_menu = session_menu.child(pin);

        if !projects.is_empty() {
            session_menu = session_menu.child(
                div()
                    .mt_1()
                    .px_2()
                    .text_size(px(layout::TYPE_METADATA))
                    .text_color(rgb(color::TEXT_TERTIARY))
                    .child("Move to project"),
            );
            for project in projects.iter().take(12) {
                let project_id = project.project_id.clone();
                let current = session.project_id.as_deref() == Some(project.project_id.as_str());
                let project_label = project.name.clone();
                let mut move_row = div()
                    .id(format!("session-menu-project-{}", project.project_id))
                    .h(px(30.0))
                    .px_2()
                    .flex()
                    .items_center()
                    .rounded_md()
                    .role(gpui::Role::MenuItem)
                    .aria_label(format!("Move chat to project {}", project.name))
                    .tab_index(0)
                    .child(if current {
                        div()
                            .flex()
                            .items_center()
                            .child(icon(Icon::Check, color::ACCENT))
                            .child(div().ml_2().child(project_label))
                            .into_any_element()
                    } else {
                        div().child(project_label).into_any_element()
                    });
                if mutations_enabled && !current {
                    move_row = move_row.on_click(cx.listener(move |this, _, _, cx| {
                        this.move_selected_session(Some(project_id.clone()), cx);
                    }));
                } else {
                    move_row = move_row.text_color(rgb(color::TEXT_TERTIARY));
                }
                session_menu = session_menu.child(move_row);
            }
        }

        if session.project_id.is_some() {
            let move_disabled_reason = mutation_disabled_reason.to_owned();
            let mut remove_project = div()
                .id("session-menu-remove-project")
                .h(px(30.0))
                .px_2()
                .flex()
                .items_center()
                .rounded_md()
                .role(gpui::Role::MenuItem)
                .aria_label("Remove chat from project")
                .tab_index(0)
                .child("Remove from project");
            if mutations_enabled {
                remove_project = remove_project.on_click(cx.listener(move |this, _, _, cx| {
                    this.move_selected_session(None, cx);
                }));
            } else {
                remove_project = remove_project
                    .text_color(rgb(color::TEXT_TERTIARY))
                    .aria_description(disabled_reason_label(&move_disabled_reason));
            }
            session_menu = session_menu.child(remove_project);
        }

        let archived = selected_session.is_some_and(|session| session.archived);
        let archive_label = if archived {
            "Restore chat"
        } else {
            "Archive chat"
        };
        let archive_disabled_reason = mutation_disabled_reason.to_owned();
        let mut archive = div()
            .id("session-menu-archive")
            .mt_1()
            .h(px(30.0))
            .px_2()
            .flex()
            .items_center()
            .rounded_md()
            .role(gpui::Role::MenuItem)
            .aria_label(archive_label)
            .tab_index(0)
            .child(archive_label);
        if mutations_enabled {
            archive = archive.on_click(cx.listener(|this, _, _, cx| {
                this.archive_selected_session(cx);
            }));
        } else {
            archive = archive
                .text_color(rgb(color::TEXT_TERTIARY))
                .aria_description(disabled_reason_label(&archive_disabled_reason));
        }
        session_menu = session_menu.child(archive);

        let delete_disabled_reason = mutation_disabled_reason.to_owned();
        let mut delete = div()
            .id("session-menu-delete")
            .h(px(30.0))
            .px_2()
            .flex()
            .items_center()
            .rounded_md()
            .role(gpui::Role::MenuItem)
            .aria_label("Delete chat")
            .tab_index(0)
            .child("Delete chat");
        if mutations_enabled {
            delete = delete.on_click(cx.listener(|this, _, _, cx| {
                this.request_delete_session(cx);
            }));
        } else {
            delete = delete
                .text_color(rgb(color::TEXT_TERTIARY))
                .aria_description(disabled_reason_label(&delete_disabled_reason));
        }
        session_menu = session_menu.child(delete.text_color(rgb(if mutations_enabled {
            color::DANGER
        } else {
            color::TEXT_TERTIARY
        })));
    } else {
        session_menu = session_menu.child(
            div()
                .px_2()
                .py_2()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_TERTIARY))
                .child("Select a chat to see actions"),
        );
    }
    let session_menu: gpui::AnyElement = if session_menu_open {
        session_menu.into_any_element()
    } else {
        div().into_any_element()
    };
    let navigation_controls = div()
        .flex_shrink_0()
        .w(px(if navigation_visible {
            navigation_width
        } else {
            228.0
        }))
        .h_full()
        .flex()
        .items_center()
        .pl(px(84.0))
        .pr_2()
        .border_r_1()
        .border_color(rgb(color::BORDER))
        .child(
            div()
                .id("navigation-toggle")
                .mr_2()
                .w(px(30.0))
                .h(px(30.0))
                .flex()
                .items_center()
                .justify_center()
                .rounded_md()
                .bg(rgb(if navigation_visible {
                    color::SURFACE_SELECTED
                } else {
                    color::SURFACE_HOVER
                }))
                .text_size(px(layout::TYPE_CONTROL))
                .text_color(rgb(color::TEXT_SECONDARY))
                .role(gpui::Role::Button)
                .aria_label(if navigation_visible {
                    "Hide navigation sidebar"
                } else {
                    "Show navigation sidebar"
                })
                .tab_index(0)
                .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                .child(icon(Icon::Navigation, color::TEXT_SECONDARY))
                .on_click(cx.listener(|this, _, window, cx| this.toggle_navigation(window, cx))),
        )
        .child(
            div()
                .id("navigation-back")
                .w(px(26.0))
                .h(px(26.0))
                .flex()
                .items_center()
                .justify_center()
                .rounded_md()
                .text_color(rgb(color::TEXT_TERTIARY))
                .role(gpui::Role::Button)
                .aria_label("Go back")
                .aria_description("Navigation history is not available in the native runtime")
                .tab_index(0)
                .child(icon(Icon::ArrowLeft, color::TEXT_TERTIARY)),
        )
        .child(
            div()
                .id("navigation-forward")
                .w(px(26.0))
                .h(px(26.0))
                .flex()
                .items_center()
                .justify_center()
                .rounded_md()
                .text_color(rgb(color::TEXT_TERTIARY))
                .role(gpui::Role::Button)
                .aria_label("Go forward")
                .aria_description("Navigation history is not available in the native runtime")
                .tab_index(0)
                .child(icon(Icon::ArrowRight, color::TEXT_TERTIARY)),
        )
        .child(
            div()
                .id("navigation-edit")
                .ml_1()
                .w(px(30.0))
                .h(px(30.0))
                .flex()
                .items_center()
                .justify_center()
                .rounded_md()
                .text_color(rgb(color::TEXT_SECONDARY))
                .role(gpui::Role::Button)
                .aria_label("Create new chat")
                .aria_keyshortcuts("⌘N")
                .tab_index(0)
                .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                .child(icon(Icon::Edit, color::TEXT_SECONDARY))
                .on_click(cx.listener(|this, _, _, cx| this.create_task(cx))),
        );
    let title_group = div()
        .relative()
        .flex_1()
        .min_w(px(0.0))
        .h_full()
        .flex()
        .items_center()
        .child(
            div()
                .mr_3()
                .text_color(rgb(color::TEXT_SECONDARY))
                .child(icon(Icon::Folder, color::TEXT_SECONDARY)),
        )
        .child(
            div()
                .min_w(px(0.0))
                .text_size(px(layout::TYPE_CONTROL))
                .text_color(rgb(color::TEXT_PRIMARY))
                .child(title.to_owned()),
        )
        .child(
            div()
                .id("session-overflow-toggle")
                .ml_2()
                .w(px(24.0))
                .h(px(24.0))
                .flex()
                .items_center()
                .justify_center()
                .rounded_md()
                .text_color(rgb(color::TEXT_TERTIARY))
                .role(gpui::Role::Button)
                .aria_label(if session_menu_open {
                    "Close chat actions"
                } else {
                    "Open chat actions"
                })
                .tab_index(0)
                .child(icon(Icon::More, color::TEXT_TERTIARY))
                .on_click(cx.listener(|this, _, _, cx| {
                    this.toggle_session_menu(cx);
                })),
        )
        .child(session_menu);
    div()
        .h(px(layout::TOP_BAR_HEIGHT))
        .flex_shrink_0()
        .flex()
        .items_center()
        .justify_between()
        // GPUI renders this custom chrome inside the transparent native titlebar.
        // Keep the traffic-light hit targets clear before placing app controls.
        .pl(px(84.0))
        .pr_4()
        .border_b_1()
        .border_color(rgb(color::BORDER))
        .bg(rgb(color::CANVAS))
        .child(navigation_controls)
        .child(title_group)
        .child(
            div()
                .flex()
                .items_center()
                .child(
                    div()
                        .mr_3()
                        .flex()
                        .items_center()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(runtime_color))
                        .child(
                            div()
                                .mr_1()
                                .w(px(6.0))
                                .h(px(6.0))
                                .rounded_full()
                                .bg(rgb(runtime_color)),
                        )
                        .child(format!("{runtime_label} · {oauth_status}")),
                )
                .child(
                    div()
                        .id("context-toggle")
                        .h(px(30.0))
                        .px_3()
                        .flex()
                        .items_center()
                        .rounded_md()
                        .bg(rgb(if context_open {
                            color::SURFACE_SELECTED
                        } else {
                            color::SURFACE
                        }))
                        .text_size(px(layout::TYPE_CONTROL))
                        .text_color(rgb(color::TEXT_SECONDARY))
                        .role(gpui::Role::Button)
                        .aria_label(if context_open {
                            "Hide context"
                        } else {
                            "Show context"
                        })
                        .track_focus(context_focus)
                        .tab_index(0)
                        .border_1()
                        .border_color(rgb(color::BORDER))
                        .focus_visible(|style| style.border_color(rgb(color::ACCENT)))
                        .child(if context_open {
                            "Hide context  ⌘K"
                        } else {
                            "Context  ⌘K"
                        })
                        .on_click(
                            cx.listener(|this, _, window, cx| {
                                this.toggle_context_panel(window, cx)
                            }),
                        ),
                )
                .child(
                    div()
                        .id("tools-toggle")
                        .ml_2()
                        .w(px(34.0))
                        .h(px(30.0))
                        .flex()
                        .items_center()
                        .justify_center()
                        .rounded_md()
                        .bg(rgb(if tools_open {
                            color::SURFACE_SELECTED
                        } else {
                            color::SURFACE
                        }))
                        .text_size(px(layout::TYPE_CONTROL))
                        .text_color(rgb(color::TEXT_SECONDARY))
                        .role(gpui::Role::Button)
                        .aria_label(if tools_open {
                            "Hide workspace tools"
                        } else {
                            "Show workspace tools"
                        })
                        .track_focus(tools_focus)
                        .tab_index(0)
                        .border_1()
                        .border_color(rgb(color::BORDER))
                        .focus_visible(|style| style.border_color(rgb(color::ACCENT)))
                        .child(icon(Icon::Menu, color::TEXT_SECONDARY))
                        .on_click(
                            cx.listener(|this, _, window, cx| this.toggle_side_panel(window, cx)),
                        ),
                ),
        )
}
