//! Native workspace top-bar presentation and shell toggles.

use crate::icons::{icon, Icon};
use crate::light_theme::{color, layout};
use crate::{disabled_reason_label, WorkspacePrototype};
use codinal_control_plane_client::{ProjectSummary, RuntimeCapabilities, SessionSummary};
use gpui::{
    deferred, div, px, rgb, Context, FocusHandle, InteractiveElement, IntoElement, ParentElement,
    StatefulInteractiveElement, Styled,
};

// Traffic-light clearance measured from the golden primary fixture: the native
// controls end near x=68.5 logical and the first header control starts near
// x=88 logical, so the header inset must be applied at exactly one layer.
const NATIVE_TITLEBAR_LEADING_INSET: f32 = 88.0;
const NAVIGATION_TRAILING_INSET: f32 = 8.0;
const COLLAPSED_NAVIGATION_WIDTH: f32 = 228.0;
const HEADER_CONTROL_SIZE: f32 = 28.0;
const OPEN_IN_PRIMARY_WIDTH: f32 = 44.0;
const OPEN_IN_ARROW_WIDTH: f32 = 24.0;
const OPEN_IN_CONTROL_WIDTH: f32 = OPEN_IN_PRIMARY_WIDTH + OPEN_IN_ARROW_WIDTH;
const HEADER_RIGHT_INSET: f32 = 16.0;

// The header navigation strip is the same width as the sidebar below it, so
// the header divider lands exactly on the sidebar's right edge. The leading
// inset is applied inside the strip (clear of the traffic lights), never on
// the outer header as well.
fn navigation_controls_width(navigation_visible: bool, navigation_width: f32) -> f32 {
    if navigation_visible {
        navigation_width
    } else {
        COLLAPSED_NAVIGATION_WIDTH
    }
}

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
    open_in_menu_open: bool,
    open_in_enabled: bool,
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
    let mutations_enabled = capabilities.mutations && !session_action_in_flight;
    let mut session_menu = div()
        .id("session-overflow-menu")
        .absolute()
        .top(px(36.0))
        .right(px(0.0))
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
    let open_in_icon_color = if open_in_enabled {
        color::TEXT_SECONDARY
    } else {
        color::TEXT_TERTIARY
    };
    let mut open_in_finder = div()
        .id("open-in-finder")
        .h(px(30.0))
        .px_2()
        .flex()
        .items_center()
        .justify_between()
        .rounded_md()
        .role(gpui::Role::MenuItem)
        .aria_label("Open workspace in Finder")
        .tab_index(0)
        .text_color(rgb(if open_in_enabled {
            color::TEXT_PRIMARY
        } else {
            color::TEXT_TERTIARY
        }))
        .child(
            div()
                .flex()
                .items_center()
                .child(
                    div()
                        .w(px(20.0))
                        .h(px(20.0))
                        .flex()
                        .items_center()
                        .justify_center()
                        .child(icon(Icon::FolderOpen, open_in_icon_color)),
                )
                .child(div().ml_2().child("Finder")),
        )
        .child(icon(
            Icon::Check,
            if open_in_enabled {
                color::ACCENT
            } else {
                color::TEXT_TERTIARY
            },
        ));
    if open_in_enabled {
        open_in_finder = open_in_finder
            .hover(|style| style.bg(rgb(color::SURFACE_HOVER)))
            .on_click(cx.listener(|this, _, _, cx| {
                cx.stop_propagation();
                this.reveal_selected_workspace_in_finder(cx);
            }));
    } else {
        open_in_finder =
            open_in_finder.aria_description("Select a project or chat workspace first");
    }
    let open_in_menu: gpui::AnyElement = if open_in_menu_open {
        deferred(
            div()
                .id("open-in-menu")
                .absolute()
                .top(px(34.0))
                .right(px(0.0))
                .w(px(220.0))
                .rounded_xl()
                .border_1()
                .border_color(rgb(color::BORDER))
                .bg(rgb(color::ELEVATED))
                .shadow_lg()
                .p_1()
                .child(open_in_finder)
                .child(
                    div()
                        .id("open-in-terminal")
                        .h(px(30.0))
                        .px_2()
                        .flex()
                        .items_center()
                        .rounded_md()
                        .text_color(rgb(color::TEXT_TERTIARY))
                        .role(gpui::Role::MenuItem)
                        .aria_label("Open workspace in Terminal")
                        .aria_description("External Terminal launching is not available")
                        .tab_index(0)
                        .child(
                            div()
                                .w(px(20.0))
                                .h(px(20.0))
                                .flex()
                                .items_center()
                                .justify_center()
                                .child(icon(Icon::Terminal, color::TEXT_TERTIARY)),
                        )
                        .child(div().ml_2().child("Terminal")),
                )
                .child(
                    div()
                        .id("open-in-ghostty")
                        .h(px(30.0))
                        .px_2()
                        .flex()
                        .items_center()
                        .rounded_md()
                        .text_color(rgb(color::TEXT_TERTIARY))
                        .role(gpui::Role::MenuItem)
                        .aria_label("Open workspace in Ghostty")
                        .aria_description("External Ghostty launching is not available")
                        .tab_index(0)
                        .child(
                            div()
                                .w(px(20.0))
                                .h(px(20.0))
                                .flex()
                                .items_center()
                                .justify_center()
                                .child(icon(Icon::Terminal, color::TEXT_TERTIARY)),
                        )
                        .child(div().ml_2().child("Ghostty")),
                )
                .child(
                    div()
                        .id("open-in-xcode")
                        .h(px(30.0))
                        .px_2()
                        .flex()
                        .items_center()
                        .rounded_md()
                        .text_color(rgb(color::TEXT_TERTIARY))
                        .role(gpui::Role::MenuItem)
                        .aria_label("Open workspace in Xcode")
                        .aria_description("External Xcode launching is not available")
                        .tab_index(0)
                        .child(
                            div()
                                .w(px(20.0))
                                .h(px(20.0))
                                .flex()
                                .items_center()
                                .justify_center()
                                .child(icon(Icon::Hammer, color::TEXT_TERTIARY)),
                        )
                        .child(div().ml_2().child("Xcode")),
                )
                .into_any_element(),
        )
        .into_any_element()
    } else {
        div().into_any_element()
    };
    let mut navigation_toggle = div()
        .id("navigation-toggle")
        .mr_1()
        .w(px(HEADER_CONTROL_SIZE))
        .h(px(HEADER_CONTROL_SIZE))
        .flex()
        .items_center()
        .justify_center()
        .rounded_md()
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
        .hover(|style| style.bg(rgb(color::SURFACE_HOVER)))
        .on_click(cx.listener(|this, _, window, cx| this.toggle_navigation(window, cx)));
    if navigation_visible {
        navigation_toggle = navigation_toggle.bg(rgb(color::SURFACE_SELECTED));
    }
    let navigation_controls = div()
        .flex_shrink_0()
        .w(px(navigation_controls_width(
            navigation_visible,
            navigation_width,
        )))
        .h_full()
        .flex()
        .items_center()
        .pl(px(NATIVE_TITLEBAR_LEADING_INSET))
        .pr(px(NAVIGATION_TRAILING_INSET))
        .border_r_1()
        .border_color(rgb(color::BORDER))
        // The header strip sits over the sidebar, so it uses the sidebar
        // background instead of the conversation canvas.
        .bg(rgb(color::SIDEBAR))
        .child(navigation_toggle)
        .child(
            div()
                .id("navigation-back")
                .w(px(HEADER_CONTROL_SIZE))
                .h(px(HEADER_CONTROL_SIZE))
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
                .ml_1()
                .w(px(HEADER_CONTROL_SIZE))
                .h(px(HEADER_CONTROL_SIZE))
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
        );
    let mut open_in_primary = div()
        .id("open-in-primary")
        .w(px(OPEN_IN_PRIMARY_WIDTH))
        .h_full()
        .flex()
        .items_center()
        .justify_center()
        .rounded_lg()
        .role(gpui::Role::Button)
        .aria_label(if open_in_enabled {
            "Open selected workspace in Finder"
        } else {
            "Open selected workspace in Finder unavailable"
        })
        .aria_description(if open_in_enabled {
            "Open in Finder"
        } else {
            "Select a project or chat workspace first"
        })
        .tab_index(0)
        .text_color(rgb(open_in_icon_color))
        .hover(|style| style.bg(rgb(color::SURFACE_HOVER)))
        .child(icon(Icon::ArrowSquareOut, open_in_icon_color));
    if open_in_enabled {
        open_in_primary = open_in_primary.on_click(cx.listener(|this, _, _, cx| {
            this.reveal_selected_workspace_in_finder(cx);
        }));
    }
    let open_in_control = div()
        .relative()
        .w(px(OPEN_IN_CONTROL_WIDTH))
        .h(px(HEADER_CONTROL_SIZE))
        .flex()
        .items_center()
        .rounded_md()
        .bg(rgb(color::SURFACE))
        .border_1()
        .border_color(rgb(color::BORDER))
        .child(open_in_menu)
        .child(open_in_primary)
        .child(
            div()
                .id("open-in-menu-toggle")
                .w(px(OPEN_IN_ARROW_WIDTH))
                .h_full()
                .flex()
                .items_center()
                .justify_center()
                .rounded_r_lg()
                .border_l_1()
                .border_color(rgb(color::BORDER))
                .role(gpui::Role::Button)
                .aria_label(if open_in_menu_open {
                    "Close open in menu"
                } else {
                    "Choose where to open the workspace"
                })
                .tab_index(0)
                .text_color(rgb(color::TEXT_SECONDARY))
                .hover(|style| style.bg(rgb(color::SURFACE_HOVER)))
                .child(icon(Icon::ChevronDown, color::TEXT_SECONDARY))
                .on_click(cx.listener(|this, _, _, cx| {
                    cx.stop_propagation();
                    this.toggle_open_in_menu(cx);
                })),
        );
    let title_group = div()
        .relative()
        .flex_1()
        .min_w(px(0.0))
        .h_full()
        .flex()
        .items_center()
        // The golden places the title group's leading glyph about 15 logical
        // px past the sidebar edge.
        .pl(px(15.0))
        .child(
            div()
                .mr_3()
                .text_color(rgb(color::TEXT_SECONDARY))
                .child(icon(Icon::Folder, color::TEXT_SECONDARY)),
        )
        .child(
            div()
                .flex_1()
                .min_w(px(0.0))
                .overflow_hidden()
                .text_size(px(crate::light_theme::typography::HEADER_TITLE))
                .text_color(rgb(color::TEXT_PRIMARY))
                .text_ellipsis()
                .child(title.to_owned()),
        )
        .child(
            div()
                .id("session-overflow-toggle")
                .relative()
                .ml_2()
                .w(px(24.0))
                .h(px(24.0))
                .flex_shrink_0()
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
                .hover(|style| style.bg(rgb(color::SURFACE_HOVER)))
                .child(deferred(session_menu).with_priority(10))
                .on_click(cx.listener(|this, _, _, cx| {
                    this.toggle_session_menu(cx);
                })),
        );
    let mut context_toggle = div()
        .id("context-toggle")
        .ml_2()
        .w(px(HEADER_CONTROL_SIZE))
        .h(px(HEADER_CONTROL_SIZE))
        .flex()
        .items_center()
        .justify_center()
        .rounded_md()
        .text_size(px(layout::TYPE_CONTROL))
        .text_color(rgb(color::TEXT_SECONDARY))
        .role(gpui::Role::Button)
        .aria_label(if context_open {
            "Hide pinned environment summary"
        } else {
            "Show pinned environment summary"
        })
        .aria_keyshortcuts("⌘K")
        .aria_description(format!(
            "Pinned summary · Runtime {runtime_label} · {oauth_status}"
        ))
        .track_focus(context_focus)
        .tab_index(0)
        .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
        .hover(|style| style.bg(rgb(color::SURFACE_HOVER)))
        .child(icon(Icon::Sliders, color::TEXT_SECONDARY))
        .on_click(cx.listener(|this, _, window, cx| this.toggle_context_panel(window, cx)));
    if context_open {
        context_toggle = context_toggle.bg(rgb(color::SURFACE_SELECTED));
    }
    let mut tools_toggle = div()
        .id("tools-toggle")
        .ml_2()
        .w(px(HEADER_CONTROL_SIZE))
        .h(px(HEADER_CONTROL_SIZE))
        .flex()
        .items_center()
        .justify_center()
        .rounded_md()
        .text_color(rgb(color::TEXT_SECONDARY))
        .role(gpui::Role::Button)
        .aria_label(if tools_open {
            "Hide workspace tools"
        } else {
            "Show workspace tools"
        })
        .track_focus(tools_focus)
        .tab_index(0)
        .focus_visible(|style| style.bg(rgb(color::SURFACE_HOVER)))
        .hover(|style| style.bg(rgb(color::SURFACE_HOVER)))
        .child(icon(Icon::Workbench, color::TEXT_SECONDARY))
        .on_click(cx.listener(|this, _, window, cx| this.toggle_side_panel(window, cx)));
    if tools_open {
        tools_toggle = tools_toggle.bg(rgb(color::SURFACE_SELECTED));
    }
    div()
        .h(px(layout::TOP_BAR_HEIGHT))
        .flex_shrink_0()
        .flex()
        .items_center()
        .justify_between()
        // The traffic-light clearance is applied once, inside the navigation
        // control strip above; the conversation and title areas start at the
        // sidebar edge.
        .pr(px(HEADER_RIGHT_INSET))
        .border_b_1()
        .border_color(rgb(color::BORDER))
        .bg(rgb(color::CANVAS))
        .child(navigation_controls)
        .child(title_group)
        .child(
            div()
                .relative()
                .flex()
                .items_center()
                .child(open_in_control)
                .child(context_toggle)
                .child(tools_toggle),
        )
}

#[cfg(test)]
mod tests {
    use super::{
        navigation_controls_width, COLLAPSED_NAVIGATION_WIDTH, HEADER_CONTROL_SIZE,
        HEADER_RIGHT_INSET, NATIVE_TITLEBAR_LEADING_INSET, OPEN_IN_CONTROL_WIDTH,
    };
    use crate::shell_layout::NAVIGATION_DEFAULT_WIDTH;

    #[test]
    fn header_navigation_strip_spans_the_sidebar_edge() {
        assert_eq!(
            navigation_controls_width(true, NAVIGATION_DEFAULT_WIDTH),
            NAVIGATION_DEFAULT_WIDTH
        );
        assert_eq!(
            navigation_controls_width(false, NAVIGATION_DEFAULT_WIDTH),
            COLLAPSED_NAVIGATION_WIDTH
        );
    }

    #[test]
    fn traffic_light_clearance_is_applied_once() {
        assert_eq!(NATIVE_TITLEBAR_LEADING_INSET, 88.0);
        let inset = NATIVE_TITLEBAR_LEADING_INSET;
        assert!(inset > 68.5, "must clear the native traffic lights");
        assert!(
            inset + 28.0 <= NAVIGATION_DEFAULT_WIDTH - 8.0,
            "leading control must fit inside the sidebar strip"
        );
    }

    #[test]
    fn header_divider_lands_on_the_sidebar_edge_at_the_golden_viewport() {
        let shell = crate::shell_layout::resolve_shell(
            crate::shell_layout::PanelPreferences::default(),
            crate::shell_layout::ShellRequest {
                viewport_width: 1_710.0,
                navigation_open: true,
                workbench_open: true,
                context_open: true,
            },
        );
        assert_eq!(shell.navigation_width, NAVIGATION_DEFAULT_WIDTH);
        assert_eq!(
            navigation_controls_width(true, shell.navigation_width),
            shell.navigation_width,
            "the header divider must sit exactly on the sidebar edge"
        );
    }
    #[test]
    fn golden_right_header_controls_keep_their_edges() {
        let right_edge = 1_710.0 - HEADER_RIGHT_INSET;
        let side_panel_start = right_edge - HEADER_CONTROL_SIZE;
        let context_start = side_panel_start - HEADER_CONTROL_SIZE;
        let open_in_start = context_start - OPEN_IN_CONTROL_WIDTH;

        assert_eq!(side_panel_start, 1_666.0);
        assert_eq!(context_start, 1_638.0);
        assert_eq!(open_in_start, 1_570.0);
    }
}
