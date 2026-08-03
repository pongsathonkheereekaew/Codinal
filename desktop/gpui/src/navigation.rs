//! Session/task navigation presentation.
//!
//! Selection and creation callbacks stay on the composition root; this module
//! only renders the bounded session summary projection.

use crate::icons::{icon, Icon};
use crate::is_activation_key;
use crate::light_theme::{color, layout};
use crate::stable_element_id;
use crate::WorkspacePrototype;
use codinal_control_plane_client::{ActivityItem, ProjectSummary, SessionSummary};
use gpui::{
    div, px, rgb, Context, FontWeight, InteractiveElement, IntoElement, KeyDownEvent,
    ParentElement, StatefulInteractiveElement, Styled,
};
use std::collections::BTreeSet;

const INITIAL_SESSION_ROWS: usize = 5;

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub(crate) struct NavigationLists {
    pub(crate) pinned: Vec<SessionSummary>,
    pub(crate) chats: Vec<SessionSummary>,
    pub(crate) archived: Vec<SessionSummary>,
}

pub(crate) fn navigation_lists(sessions: &[SessionSummary]) -> NavigationLists {
    let mut lists = NavigationLists::default();
    for session in sessions
        .iter()
        .filter(|session| session.origin.as_deref() != Some("side_chat"))
    {
        if session.archived {
            lists.archived.push(session.clone());
            continue;
        }
        if session.pinned {
            lists.pinned.push(session.clone());
        } else if session.project_id.is_none() {
            lists.chats.push(session.clone());
        }
    }
    let latest_first = |left: &SessionSummary, right: &SessionSummary| {
        right
            .updated_at
            .cmp(&left.updated_at)
            .then_with(|| left.title.cmp(&right.title))
            .then_with(|| left.session_id.cmp(&right.session_id))
    };
    lists.pinned.sort_by(latest_first);
    lists.chats.sort_by(latest_first);
    lists.archived.sort_by(latest_first);
    lists
}

fn section_heading(label: &'static str) -> impl gpui::IntoElement {
    div()
        .mt_4()
        .mb_1()
        .px_3()
        .flex()
        .items_center()
        .text_size(px(layout::TYPE_METADATA))
        .text_color(rgb(color::TEXT_TERTIARY))
        .child(label)
}

fn chats_heading(cx: &mut Context<WorkspacePrototype>) -> impl gpui::IntoElement {
    div()
        .id("chats-heading")
        .mt_4()
        .mb_1()
        .px_3()
        .flex()
        .items_center()
        .text_size(px(layout::TYPE_METADATA))
        .text_color(rgb(color::TEXT_TERTIARY))
        .role(gpui::Role::Button)
        .aria_label("Show chats")
        .tab_index(0)
        .child("Chats")
        .on_click(cx.listener(|this, _, _, cx| {
            this.clear_project_selection(cx);
        }))
}

fn session_row(
    session: &SessionSummary,
    selected_session_id: Option<&str>,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let session_id = session.session_id.clone();
    let keyboard_session_id = session_id.clone();
    let selected = selected_session_id == Some(session.session_id.as_str());
    div()
        .id(stable_element_id("session-row", &session.session_id))
        .mt_1()
        .px_3()
        .py_2()
        .rounded_lg()
        .bg(rgb(if selected {
            color::SURFACE_SELECTED
        } else {
            color::SIDEBAR
        }))
        .role(gpui::Role::Button)
        .aria_label(format!("Open chat {}", session.title))
        .tab_index(0)
        .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
        .on_key_down(cx.listener(move |this, event: &KeyDownEvent, _, cx| {
            if is_activation_key(event) {
                this.select_session(keyboard_session_id.clone(), cx);
            }
        }))
        .child(
            div()
                .flex()
                .items_center()
                .justify_between()
                .child(
                    div()
                        .text_size(px(layout::TYPE_CONTROL))
                        .overflow_hidden()
                        .text_ellipsis()
                        .child(session.title.clone()),
                )
                .child(
                    div()
                        .ml_2()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::TEXT_TERTIARY))
                        .child(session.messages.to_string()),
                ),
        )
        .on_click(cx.listener(move |this, _, _, cx| {
            cx.stop_propagation();
            this.select_session(session_id.clone(), cx);
        }))
}

#[allow(clippy::too_many_arguments)]
fn project_row(
    project: &ProjectSummary,
    sessions: &[SessionSummary],
    selected_session_id: Option<&str>,
    selected_project_id: Option<&str>,
    project_hover_id: Option<&str>,
    project_menu_id: Option<&str>,
    mutations_enabled: bool,
    project_expanded: bool,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let project_id = project.project_id.clone();
    let select_project_id = project_id.clone();
    let menu_project_id = project_id.clone();
    let edit_project = project.clone();
    let pin_project_id = project_id.clone();
    let remove_project_id = project_id.clone();
    let project_pinned = project.pinned;
    let project_hovered = project_hover_id == Some(project.project_id.as_str());
    let menu_open = project_menu_id == Some(project.project_id.as_str());
    let mut row = div()
        .id(stable_element_id("project-row", &project.project_id))
        .relative()
        .mt_1()
        .px_3()
        .py_2()
        .rounded_lg()
        .bg(rgb(
            if selected_project_id == Some(project.project_id.as_str()) {
                color::SURFACE_SELECTED
            } else if project_hovered || menu_open {
                color::SURFACE_HOVER
            } else {
                color::SIDEBAR
            },
        ))
        .role(gpui::Role::Button)
        .aria_label(format!("Open project {}", project.name))
        .tab_index(0)
        .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
        .on_hover({
            let project_id = project_id.clone();
            cx.listener(move |this, hovered: &bool, _, cx| {
                this.set_project_hover(project_id.clone(), *hovered, cx);
            })
        })
        .on_click(
            cx.listener(move |this, _, _, cx| this.select_project(select_project_id.clone(), cx)),
        )
        .child(
            div()
                .flex()
                .items_center()
                .justify_between()
                .child(
                    div()
                        .flex()
                        .items_center()
                        .min_w(px(0.0))
                        .child(
                            div()
                                .mr_2()
                                .text_color(rgb(color::TEXT_SECONDARY))
                                .child(icon(Icon::Folder, color::TEXT_SECONDARY)),
                        )
                        .child(
                            div()
                                .text_size(px(layout::TYPE_CONTROL))
                                .overflow_hidden()
                                .text_ellipsis()
                                .child(project.name.clone()),
                        ),
                )
                .child(
                    div()
                        .flex()
                        .items_center()
                        .child(
                            div()
                                .mr_1()
                                .text_size(px(layout::TYPE_METADATA))
                                .text_color(rgb(color::TEXT_TERTIARY))
                                .child(project.task_count.to_string()),
                        )
                        .child(
                            div()
                                .id(stable_element_id("project-menu", &project.project_id))
                                .w(px(24.0))
                                .h(px(24.0))
                                .flex()
                                .items_center()
                                .justify_center()
                                .rounded_md()
                                .text_color(rgb(color::TEXT_SECONDARY))
                                .role(gpui::Role::Button)
                                .aria_label(format!("More actions for project {}", project.name))
                                .tab_index(0)
                                .child(if project_hovered || menu_open {
                                    icon(Icon::More, color::TEXT_SECONDARY).into_any_element()
                                } else {
                                    div().into_any_element()
                                })
                                .on_click(cx.listener(move |this, _, _, cx| {
                                    cx.stop_propagation();
                                    this.toggle_project_menu(menu_project_id.clone(), cx)
                                })),
                        ),
                ),
        )
        .child(
            div()
                .mt_1()
                .ml_6()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_TERTIARY))
                .child(if project.roots.is_empty() {
                    "No source folders".to_owned()
                } else {
                    format!("{} source folder(s)", project.roots.len())
                }),
        );
    let project_sessions = sessions
        .iter()
        .filter(|session| {
            !session.archived && session.project_id.as_deref() == Some(project.project_id.as_str())
        })
        .collect::<Vec<_>>();
    let visible_project_sessions = project_sessions.iter().take(if project_expanded {
        project_sessions.len()
    } else {
        INITIAL_SESSION_ROWS
    });
    for session in visible_project_sessions {
        row = row.child(session_row(session, selected_session_id, cx));
    }
    if !project_expanded && project_sessions.len() > INITIAL_SESSION_ROWS {
        let expand_id = project.project_id.clone();
        row = row.child(
            div()
                .id(stable_element_id("project-show-more", &project.project_id))
                .mt_1()
                .ml_6()
                .px_2()
                .py_1()
                .rounded_md()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_SECONDARY))
                .role(gpui::Role::Button)
                .aria_label(format!("Show more chats in {}", project.name))
                .tab_index(0)
                .child(format!(
                    "Show more ({} more)",
                    project_sessions.len() - INITIAL_SESSION_ROWS
                ))
                .on_click(cx.listener(move |this, _, _, cx| {
                    cx.stop_propagation();
                    this.toggle_project_expanded(expand_id.clone(), cx);
                })),
        );
    }
    if menu_open {
        let archived_chat_count = sessions
            .iter()
            .filter(|session| {
                session.archived
                    && session.project_id.as_deref() == Some(project.project_id.as_str())
            })
            .count();
        let edit_label = if project.pinned {
            "Unpin project"
        } else {
            "Pin project"
        };
        let mut menu = div()
            .id(stable_element_id("project-overflow", &project.project_id))
            .mt_1()
            .ml_6()
            .w(px(196.0))
            .rounded_lg()
            .border_1()
            .border_color(rgb(color::BORDER))
            .bg(rgb(color::ELEVATED))
            .shadow_lg()
            .p_1();
        let pin_id = pin_project_id.clone();
        let reveal_id = project.project_id.clone();
        let edit = edit_project.clone();
        let remove_id = remove_project_id.clone();
        let archive_id = project.project_id.clone();
        let mut pin = div()
            .id("project-menu-pin")
            .h(px(30.0))
            .px_2()
            .flex()
            .items_center()
            .rounded_md()
            .role(gpui::Role::MenuItem)
            .aria_label(edit_label)
            .tab_index(0)
            .child(icon(Icon::Pin, color::TEXT_SECONDARY))
            .child(div().ml_2().child(edit_label));
        if mutations_enabled {
            pin = pin.on_click(cx.listener(move |this, _, _, cx| {
                this.pin_project(pin_id.clone(), !project_pinned, cx)
            }));
        } else {
            pin = pin
                .text_color(rgb(color::TEXT_TERTIARY))
                .aria_description("Project pinning requires the Rust writer");
        }
        let mut archive = div()
            .id("project-menu-archive")
            .h(px(30.0))
            .px_2()
            .flex()
            .items_center()
            .rounded_md()
            .role(gpui::Role::MenuItem)
            .aria_label("Archive chats")
            .tab_index(0)
            .child(icon(Icon::Archive, color::TEXT_SECONDARY))
            .child(div().ml_2().child("Archive chats"));
        if mutations_enabled {
            archive = archive.on_click(cx.listener(move |this, _, _, cx| {
                this.request_archive_project(archive_id.clone(), cx);
            }));
        } else {
            archive = archive
                .text_color(rgb(color::TEXT_TERTIARY))
                .aria_description("Chat archive requires the Rust writer");
        }
        menu = menu
            .child(pin)
            .child(
                div()
                    .id("project-menu-reveal")
                    .h(px(30.0))
                    .px_2()
                    .flex()
                    .items_center()
                    .rounded_md()
                    .role(gpui::Role::MenuItem)
                    .aria_label("Reveal project in Finder")
                    .tab_index(0)
                    .child(icon(Icon::Folder, color::TEXT_SECONDARY))
                    .child(div().ml_2().child("Reveal in Finder"))
                    .on_click(cx.listener(move |this, _, _, cx| {
                        this.reveal_project(reveal_id.clone(), cx)
                    })),
            )
            .child(
                div()
                    .id("project-menu-worktree")
                    .h(px(30.0))
                    .px_2()
                    .flex()
                    .items_center()
                    .rounded_md()
                    .text_color(rgb(color::TEXT_TERTIARY))
                    .role(gpui::Role::MenuItem)
                    .aria_label("Create permanent worktree")
                    .aria_description("Permanent worktrees are not available in this runtime")
                    .tab_index(0)
                    .child(icon(Icon::Worktree, color::TEXT_TERTIARY))
                    .child(div().ml_2().child("Create permanent worktree")),
            )
            .child(
                div()
                    .id("project-menu-edit")
                    .h(px(30.0))
                    .px_2()
                    .flex()
                    .items_center()
                    .rounded_md()
                    .role(gpui::Role::MenuItem)
                    .aria_label("Edit project")
                    .tab_index(0)
                    .child(icon(Icon::Gear, color::TEXT_SECONDARY))
                    .child(div().ml_2().child("Edit project"))
                    .on_click(cx.listener(move |this, _, window, cx| {
                        this.open_project_dialog(Some(edit.clone()), window, cx)
                    })),
            )
            .child(archive);
        if archived_chat_count > 0 {
            let restore_id = project.project_id.clone();
            let mut restore = div()
                .id("project-menu-restore")
                .h(px(30.0))
                .px_2()
                .flex()
                .items_center()
                .rounded_md()
                .role(gpui::Role::MenuItem)
                .aria_label("Restore archived chats")
                .tab_index(0)
                .child(icon(Icon::Archive, color::TEXT_SECONDARY))
                .child(
                    div()
                        .ml_2()
                        .child(format!("Restore chats ({archived_chat_count})")),
                );
            if mutations_enabled {
                restore = restore.on_click(cx.listener(move |this, _, _, cx| {
                    this.restore_project_chats(restore_id.clone(), cx);
                }));
            } else {
                restore = restore
                    .text_color(rgb(color::TEXT_TERTIARY))
                    .aria_description("Chat restore requires the Rust writer");
            }
            menu = menu.child(restore);
        }
        if mutations_enabled {
            menu = menu.child(
                div()
                    .id("project-menu-remove")
                    .h(px(30.0))
                    .px_2()
                    .flex()
                    .items_center()
                    .rounded_md()
                    .text_color(rgb(color::DANGER))
                    .role(gpui::Role::MenuItem)
                    .aria_label("Remove project")
                    .tab_index(0)
                    .child(icon(Icon::Close, color::DANGER))
                    .child(div().ml_2().child("Remove project"))
                    .on_click(cx.listener(move |this, _, _, cx| {
                        this.request_remove_project(remove_id.clone(), cx)
                    })),
            );
        }
        row = row.child(menu);
    }
    if project_hovered && !menu_open {
        let preview_edit = project.clone();
        row = row.child(
            div()
                .id(stable_element_id(
                    "project-hover-preview",
                    &project.project_id,
                ))
                .absolute()
                .left(px(248.0))
                .top(px(0.0))
                .w(px(256.0))
                .rounded_xl()
                .border_1()
                .border_color(rgb(color::BORDER))
                .bg(rgb(color::ELEVATED))
                .shadow_lg()
                .p_3()
                .child(
                    div()
                        .flex()
                        .items_center()
                        .justify_between()
                        .child(
                            div()
                                .flex()
                                .items_center()
                                .text_size(px(layout::TYPE_CONTROL))
                                .child(icon(Icon::Folder, color::TEXT_SECONDARY))
                                .child(div().ml_2().child(project.name.clone())),
                        )
                        .child(icon(
                            Icon::Pin,
                            if project.pinned {
                                color::ACCENT
                            } else {
                                color::TEXT_TERTIARY
                            },
                        )),
                )
                .child(
                    div()
                        .mt_2()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::TEXT_SECONDARY))
                        .flex()
                        .items_center()
                        .child(icon(Icon::MessageCircle, color::TEXT_SECONDARY))
                        .child(div().ml_2().child(format!("{} tasks", project.task_count))),
                )
                .child(
                    div()
                        .mt_2()
                        .pt_2()
                        .border_t_1()
                        .border_color(rgb(color::BORDER))
                        .children(project.roots.iter().take(3).map(|root| {
                            div()
                                .mt_1()
                                .flex()
                                .items_center()
                                .text_size(px(layout::TYPE_METADATA))
                                .text_color(rgb(color::TEXT_SECONDARY))
                                .child(icon(
                                    if root.primary {
                                        Icon::FolderOpen
                                    } else {
                                        Icon::Folder
                                    },
                                    color::TEXT_TERTIARY,
                                ))
                                .child(
                                    div()
                                        .ml_2()
                                        .overflow_hidden()
                                        .text_ellipsis()
                                        .child(root.path.clone()),
                                )
                        }))
                        .child(if project.roots.is_empty() {
                            div()
                                .mt_1()
                                .text_size(px(layout::TYPE_METADATA))
                                .text_color(rgb(color::TEXT_TERTIARY))
                                .child("No source folders")
                                .into_any_element()
                        } else {
                            div().into_any_element()
                        }),
                )
                .child(
                    div()
                        .mt_2()
                        .pt_2()
                        .border_t_1()
                        .border_color(rgb(color::BORDER))
                        .child(
                            div()
                                .id("project-hover-edit")
                                .px_2()
                                .py_1()
                                .rounded_md()
                                .role(gpui::Role::Button)
                                .aria_label("Edit project")
                                .tab_index(0)
                                .child(icon(Icon::Gear, color::TEXT_SECONDARY))
                                .child(div().ml_2().child("Edit project"))
                                .on_click(cx.listener(move |this, _, window, cx| {
                                    cx.stop_propagation();
                                    this.open_project_dialog(Some(preview_edit.clone()), window, cx)
                                })),
                        ),
                ),
        );
    }
    row
}

fn projects_heading(
    mutations_enabled: bool,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let mut heading = div()
        .mt_4()
        .mb_1()
        .px_3()
        .flex()
        .items_center()
        .justify_between()
        .text_size(px(layout::TYPE_METADATA))
        .text_color(rgb(color::TEXT_TERTIARY))
        .child("Projects");
    let mut add = div()
        .id("create-project")
        .w(px(24.0))
        .h(px(24.0))
        .flex()
        .items_center()
        .justify_center()
        .rounded_md()
        .role(gpui::Role::Button)
        .aria_label("Create project")
        .tab_index(0)
        .child(icon(Icon::Plus, color::TEXT_SECONDARY));
    if mutations_enabled {
        add = add.on_click(
            cx.listener(|this, _, window, cx| this.open_project_dialog(None, window, cx)),
        );
    } else {
        add = add.text_color(rgb(color::TEXT_TERTIARY));
    }
    heading = heading.child(add);
    heading
}

fn product_surface_row(
    id: &'static str,
    label: &'static str,
    icon_kind: Icon,
    shortcut: &'static str,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let reason = "surface_not_implemented";
    div()
        .id(id)
        .h(px(32.0))
        .px_3()
        .flex()
        .items_center()
        .rounded_lg()
        .text_size(px(layout::TYPE_CONTROL))
        .text_color(rgb(color::TEXT_SECONDARY))
        .role(gpui::Role::Button)
        .aria_label(label)
        .aria_description(format!(
            "{label} is not available in the current Rust runtime"
        ))
        .tab_index(0)
        .child(
            div()
                .w(px(22.0))
                .text_color(rgb(color::TEXT_TERTIARY))
                .child(icon(icon_kind, color::TEXT_TERTIARY)),
        )
        .child(div().flex_1().child(label))
        .child(
            div()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_TERTIARY))
                .child(shortcut),
        )
        .on_click(cx.listener(move |this, _, _, cx| {
            this.show_navigation_unavailable(label, reason, cx);
        }))
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn session_pane(
    sessions: &[SessionSummary],
    projects: &[ProjectSummary],
    selected_session_id: Option<&str>,
    selected_project_id: Option<&str>,
    project_hover_id: Option<&str>,
    project_menu_id: Option<&str>,
    mutations_enabled: bool,
    mutation_disabled_reason: &str,
    expanded_project_ids: &BTreeSet<String>,
    chats_expanded: bool,
    mode_menu_open: bool,
    activity_open: bool,
    activity_items: &[ActivityItem],
    activity_status: &str,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let lists = navigation_lists(sessions);
    let mut list = div()
        .id("session-list")
        .flex()
        .flex_col()
        .flex_1()
        .min_h(px(0.0))
        .overflow_y_scroll();
    if !lists.pinned.is_empty() {
        list = list.child(section_heading("Pinned"));
        for session in &lists.pinned {
            list = list.child(session_row(session, selected_session_id, cx));
        }
    }
    list = list.child(projects_heading(mutations_enabled, cx));
    if projects.is_empty() {
        list = list.child(
            div()
                .id("projects-empty")
                .mx_2()
                .px_3()
                .py_2()
                .rounded_lg()
                .bg(rgb(color::SIDEBAR))
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_TERTIARY))
                .child("No projects yet")
                .child(div().mt_1().child(if mutations_enabled {
                    "Use + to add a project"
                } else {
                    "Project changes require the Rust writer"
                })),
        );
    } else {
        for project in projects {
            list = list.child(project_row(
                project,
                sessions,
                selected_session_id,
                selected_project_id,
                project_hover_id,
                project_menu_id,
                mutations_enabled,
                expanded_project_ids.contains(&project.project_id),
                cx,
            ));
        }
    }
    list = list.child(chats_heading(cx));
    let visible_chats = lists.chats.iter().take(if chats_expanded {
        lists.chats.len()
    } else {
        INITIAL_SESSION_ROWS
    });
    for session in visible_chats {
        list = list.child(session_row(session, selected_session_id, cx));
    }
    if !chats_expanded && lists.chats.len() > INITIAL_SESSION_ROWS {
        list = list.child(
            div()
                .id("chats-show-more")
                .mt_1()
                .px_3()
                .py_1()
                .rounded_md()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_SECONDARY))
                .role(gpui::Role::Button)
                .aria_label("Show more chats")
                .tab_index(0)
                .child(format!(
                    "Show more ({} more)",
                    lists.chats.len() - INITIAL_SESSION_ROWS
                ))
                .on_click(cx.listener(|this, _, _, cx| {
                    this.toggle_chats_expanded(cx);
                })),
        );
    }
    if lists.chats.is_empty() {
        list = list.child(
            div()
                .mt_4()
                .rounded_lg()
                .bg(rgb(color::SURFACE))
                .p_3()
                .child(
                    div()
                        .text_size(px(layout::TYPE_CONTROL))
                        .child("No chats yet"),
                )
                .child(
                    div()
                        .mt_1()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::TEXT_SECONDARY))
                        .child(if mutations_enabled {
                            "Create a chat to start a conversation."
                        } else {
                            "Chats appear after the Rust writer is ready."
                        }),
                ),
        );
    }
    if !lists.archived.is_empty() {
        list = list.child(section_heading("Archived"));
        for session in &lists.archived {
            list = list.child(session_row(session, selected_session_id, cx));
        }
    }
    let mut new_task = div()
        .id("new-chat")
        .h(px(34.0))
        .px_3()
        .flex()
        .items_center()
        .justify_between()
        .rounded_lg()
        .bg(rgb(if mutations_enabled {
            color::SURFACE_HOVER
        } else {
            color::SIDEBAR
        }))
        .role(gpui::Role::Button)
        .aria_label("Create new chat")
        .aria_keyshortcuts("⌘N")
        .tab_index(0)
        .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
        .text_color(rgb(if mutations_enabled {
            color::TEXT_PRIMARY
        } else {
            color::TEXT_TERTIARY
        }))
        .child(
            div()
                .flex()
                .items_center()
                .text_size(px(layout::TYPE_CONTROL))
                .child(
                    div()
                        .w(px(20.0))
                        .flex()
                        .items_center()
                        .child(icon(Icon::NewChat, color::TEXT_PRIMARY)),
                )
                .child(div().ml_2().child("New chat")),
        )
        .child(
            div()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_TERTIARY))
                .child("⌘N"),
        );
    if mutations_enabled {
        new_task = new_task
            .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
                if is_activation_key(event) {
                    this.create_task(cx);
                }
            }))
            .on_click(cx.listener(|this, _, _, cx| this.create_task(cx)));
    } else {
        let mutation_disabled_reason = mutation_disabled_reason.to_owned();
        let keyboard_disabled_reason = mutation_disabled_reason.clone();
        new_task = new_task
            .on_key_down(cx.listener(move |this, event: &KeyDownEvent, _, cx| {
                if is_activation_key(event) {
                    this.show_new_task_unavailable(&keyboard_disabled_reason, cx);
                }
            }))
            .on_click(cx.listener(move |this, _, _, cx| {
                this.show_new_task_unavailable(&mutation_disabled_reason, cx);
            }));
    }
    let search_click = cx.listener(|this, _, window, cx| {
        this.open_search(window, cx);
    });
    let activity_click = cx.listener(|this, _, _, cx| {
        this.toggle_activity(cx);
    });
    let mode_click = cx.listener(|this, _, _, cx| {
        this.toggle_mode_menu(cx);
    });
    let unread = activity_items.iter().filter(|item| item.unread).count();
    let mut activity_popup = div()
        .id("activity-popover")
        .absolute()
        .top(px(42.0))
        .right(px(8.0))
        .w(px(320.0))
        .rounded_xl()
        .border_1()
        .border_color(rgb(color::BORDER))
        .bg(rgb(color::ELEVATED))
        .shadow_lg()
        .p_3();
    if activity_items.is_empty() {
        activity_popup = activity_popup.child(
            div()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_SECONDARY))
                .child(activity_status.to_owned()),
        );
    } else {
        for item in activity_items.iter().take(20) {
            let session_id = item.session_id.clone();
            let mut row = div()
                .id(stable_element_id("activity-item", &item.activity_id))
                .py_2()
                .border_b_1()
                .border_color(rgb(color::BORDER))
                .text_size(px(layout::TYPE_METADATA))
                .child(
                    div()
                        .text_color(rgb(if item.unread {
                            color::TEXT_PRIMARY
                        } else {
                            color::TEXT_SECONDARY
                        }))
                        .child(item.title.clone()),
                )
                .child(
                    div()
                        .mt_1()
                        .text_color(rgb(color::TEXT_TERTIARY))
                        .child(item.detail.clone()),
                );
            if let Some(session_id) = session_id {
                row = row
                    .role(gpui::Role::Button)
                    .aria_label(format!("Open activity chat {session_id}"))
                    .tab_index(0)
                    .on_click(cx.listener(move |this, _, _, cx| {
                        this.select_session(session_id.clone(), cx);
                        this.activity_open = false;
                    }));
            }
            activity_popup = activity_popup.child(row);
        }
        if unread > 0 {
            activity_popup = activity_popup.child(
                div()
                    .id("activity-mark-read")
                    .mt_2()
                    .text_color(rgb(color::ACCENT))
                    .role(gpui::Role::Button)
                    .aria_label("Mark all activity as read")
                    .tab_index(0)
                    .child("Mark all as read")
                    .on_click(cx.listener(|this, _, _, cx| {
                        this.mark_activity_read(cx);
                    })),
            );
        }
    }
    let activity_popup: gpui::AnyElement = if activity_open {
        activity_popup.into_any_element()
    } else {
        div().into_any_element()
    };
    let mode_popup = div()
        .id("mode-popover")
        .absolute()
        .top(px(42.0))
        .left(px(8.0))
        .w(px(224.0))
        .rounded_xl()
        .border_1()
        .border_color(rgb(color::BORDER))
        .bg(rgb(color::ELEVATED))
        .shadow_lg()
        .p_1()
        .child(
            div()
                .id("mode-codinal")
                .h(px(30.0))
                .px_2()
                .flex()
                .items_center()
                .rounded_md()
                .bg(rgb(color::SURFACE_SELECTED))
                .role(gpui::Role::MenuItem)
                .aria_label("Codinal mode")
                .aria_description("Current workspace mode")
                .tab_index(0)
                .child(
                    div()
                        .w(px(20.0))
                        .flex()
                        .items_center()
                        .child(icon(Icon::Check, color::ACCENT)),
                )
                .child("Codinal"),
        )
        .child(
            div()
                .id("mode-chatgpt")
                .h(px(30.0))
                .px_2()
                .flex()
                .items_center()
                .rounded_md()
                .text_color(rgb(color::TEXT_TERTIARY))
                .role(gpui::Role::MenuItem)
                .aria_label("ChatGPT mode unavailable")
                .aria_description("ChatGPT mode is not available in the current Rust runtime")
                .tab_index(0)
                .child(div().w(px(20.0)).child(div().w(px(16.0)).h(px(16.0))))
                .child("ChatGPT"),
        );
    let mode_popup: gpui::AnyElement = if mode_menu_open {
        mode_popup.into_any_element()
    } else {
        div().into_any_element()
    };
    let product_navigation = div()
        .id("product-navigation")
        .mt_1()
        .flex()
        .flex_col()
        .child(product_surface_row(
            "nav-pull-requests",
            "Pull requests",
            Icon::PullRequest,
            "",
            cx,
        ))
        .child(product_surface_row(
            "nav-sites",
            "Sites",
            Icon::Sites,
            "",
            cx,
        ))
        .child(product_surface_row(
            "nav-scheduled",
            "Scheduled",
            Icon::Time,
            "",
            cx,
        ))
        .child(product_surface_row(
            "nav-plugins",
            "Plugins",
            Icon::Plugins,
            "",
            cx,
        ));
    div()
        .relative()
        .flex_1()
        .min_h(px(0.0))
        .min_w(px(200.0))
        .flex()
        .flex_col()
        .px_2()
        .child(
            div()
                .h(px(42.0))
                .px_2()
                .flex()
                .items_center()
                .justify_between()
                .child(
                    div()
                        .id("codinal-mode-trigger")
                        .h(px(28.0))
                        .px_1()
                        .flex()
                        .items_center()
                        .rounded_md()
                        .text_size(px(layout::TYPE_SECTION))
                        .font_weight(FontWeight::SEMIBOLD)
                        .role(gpui::Role::Button)
                        .aria_label("Switch workspace mode")
                        .aria_description("Choose between Codinal and ChatGPT modes")
                        .tab_index(0)
                        .child("Codinal")
                        .child(
                            div()
                                .ml_1()
                                .flex()
                                .items_center()
                                .child(icon(Icon::ChevronDown, color::TEXT_SECONDARY)),
                        )
                        .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
                            if is_activation_key(event) {
                                this.toggle_mode_menu(cx);
                            }
                        }))
                        .on_click(mode_click),
                )
                .child(
                    div()
                        .flex()
                        .items_center()
                        .child(
                            div()
                                .id("sidebar-search")
                                .w(px(28.0))
                                .h(px(28.0))
                                .flex()
                                .items_center()
                                .justify_center()
                                .rounded_md()
                                .text_size(px(layout::TYPE_CONTROL))
                                .text_color(rgb(color::TEXT_SECONDARY))
                                .role(gpui::Role::Button)
                                .aria_label("Search chats")
                                .aria_description("Search chats by title, path, or session")
                                .tab_index(0)
                                .child(icon(Icon::Search, color::TEXT_SECONDARY))
                                .on_click(search_click),
                        )
                        .child(
                            div()
                                .id("sidebar-activity")
                                .ml_1()
                                .w(px(28.0))
                                .h(px(28.0))
                                .flex()
                                .items_center()
                                .justify_center()
                                .rounded_md()
                                .text_size(px(layout::TYPE_CONTROL))
                                .text_color(rgb(color::TEXT_SECONDARY))
                                .role(gpui::Role::Button)
                                .aria_label("Open activity")
                                .aria_description(if unread == 0 {
                                    "No unread activity"
                                } else {
                                    "Unread activity available"
                                })
                                .tab_index(0)
                                .child(icon(
                                    Icon::Bell,
                                    if unread == 0 {
                                        color::TEXT_SECONDARY
                                    } else {
                                        color::ACCENT
                                    },
                                ))
                                .on_click(activity_click),
                        ),
                ),
        )
        .child(activity_popup)
        .child(new_task)
        .child(product_navigation)
        .child(list)
        .child(mode_popup)
}

#[cfg(test)]
mod tests {
    use super::navigation_lists;
    use codinal_control_plane_client::SessionSummary;

    fn session(
        id: &str,
        updated_at: &str,
        pinned: bool,
        archived: bool,
        project_id: Option<&str>,
    ) -> SessionSummary {
        SessionSummary {
            session_id: id.to_owned(),
            title: id.to_owned(),
            workspace: "/tmp/workspace".to_owned(),
            messages: 1,
            updated_at: updated_at.to_owned(),
            pinned,
            archived,
            origin: None,
            origin_label: None,
            origin_session_id: None,
            project_id: project_id.map(str::to_owned),
        }
    }

    #[test]
    fn navigation_lists_never_duplicate_or_show_archived_project_chats() {
        let lists = navigation_lists(&[
            session("pinned-old", "2026-08-03T02:00:00Z", true, false, None),
            session("pinned", "2026-08-03T03:00:00Z", true, false, None),
            session("chat", "2026-08-03T02:00:00Z", false, false, None),
            session("chat-new", "2026-08-03T04:00:00Z", false, false, None),
            {
                let mut side_chat =
                    session("side-chat", "2026-08-03T05:00:00Z", false, false, None);
                side_chat.origin = Some("side_chat".to_owned());
                side_chat
            },
            session(
                "project",
                "2026-08-03T04:00:00Z",
                false,
                false,
                Some("project-1"),
            ),
            session("archived", "2026-08-03T05:00:00Z", false, true, None),
        ]);
        assert_eq!(
            lists
                .pinned
                .iter()
                .map(|s| s.session_id.as_str())
                .collect::<Vec<_>>(),
            ["pinned", "pinned-old"]
        );
        assert_eq!(
            lists
                .chats
                .iter()
                .map(|s| s.session_id.as_str())
                .collect::<Vec<_>>(),
            ["chat-new", "chat"]
        );
        assert_eq!(
            lists
                .archived
                .iter()
                .map(|s| s.session_id.as_str())
                .collect::<Vec<_>>(),
            ["archived"]
        );
        assert!(lists
            .pinned
            .iter()
            .chain(lists.chats.iter())
            .all(|session| session.origin.as_deref() != Some("side_chat")));
    }
}
