//! GPUI presentation for the unified tools dock.
//!
//! The dock renders bounded local projections and delegates every action to
//! the composition root. It never owns runtime, policy, filesystem, or PTY
//! execution authority.

use crate::icons::{icon, Icon};
use crate::light_theme::{color, layout};
use crate::side_panel::{
    review_changed_paths, FilePreview, ReviewSnapshot, SidePanelTool, WorkspaceSnapshot,
    SIDE_PANEL_ITEMS,
};
use crate::terminal_view;
use crate::{
    file_tree_resize_handle, stable_element_id, DraggedFileTreeDivider, TerminalState,
    WorkspacePrototype,
};
use codinal_control_plane_client::{ProjectRootSummary, SessionSummary};
use gpui::{
    div, px, rgb, Context, FocusHandle, FontWeight, InteractiveElement, IntoElement, ParentElement,
    StatefulInteractiveElement, Styled,
};

fn workspace_tool_menu(cx: &mut Context<WorkspacePrototype>) -> impl IntoElement {
    let mut menu = div()
        .id("workspace-tool-picker-menu")
        .w(px(254.0))
        .flex()
        .flex_col()
        .rounded_xl()
        .border_1()
        .border_color(rgb(color::BORDER))
        .bg(rgb(color::ELEVATED))
        .shadow_lg()
        .p_2()
        .occlude();
    for item in SIDE_PANEL_ITEMS.iter() {
        let tool = item.tool;
        menu = menu.child(
            div()
                .id(stable_element_id("workspace-tool-row", item.label))
                .h(px(36.0))
                .px_3()
                .flex()
                .items_center()
                .justify_between()
                .rounded_lg()
                .role(gpui::Role::Button)
                .aria_label(format!("Open {}", item.label))
                .tab_index(0)
                .text_size(px(layout::TYPE_CONTROL))
                .focus_visible(|style| style.border_color(rgb(color::ACCENT)))
                .child(
                    div()
                        .flex()
                        .items_center()
                        .child(
                            div()
                                .w(px(28.0))
                                .text_color(rgb(color::TEXT_SECONDARY))
                                .child(icon(item.icon, color::TEXT_SECONDARY)),
                        )
                        .child(div().child(item.label)),
                )
                .child(
                    div()
                        .px_2()
                        .py_1()
                        .rounded_md()
                        .bg(rgb(color::SURFACE))
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::TEXT_TERTIARY))
                        .child(item.shortcut),
                )
                .on_click(cx.listener(move |this, _, window, cx| {
                    this.activate_side_panel_tool(tool, window, cx);
                })),
        );
    }
    menu
}

pub(crate) fn side_chat_sessions_for_parent(
    sessions: &[SessionSummary],
    parent_id: Option<&str>,
    limit: usize,
) -> Vec<SessionSummary> {
    let Some(parent_id) = parent_id else {
        return Vec::new();
    };
    let mut children = sessions
        .iter()
        .filter(|session| {
            !session.archived
                && session.origin.as_deref() == Some("side_chat")
                && session.origin_session_id.as_deref() == Some(parent_id)
        })
        .cloned()
        .collect::<Vec<_>>();
    children.sort_by(|left, right| {
        right
            .updated_at
            .cmp(&left.updated_at)
            .then_with(|| left.title.cmp(&right.title))
            .then_with(|| left.session_id.cmp(&right.session_id))
    });
    children.truncate(limit);
    children
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn tools_panel(
    open_tabs: &[SidePanelTool],
    selected_tool: Option<SidePanelTool>,
    tool_picker_open: bool,
    review: Option<&ReviewSnapshot>,
    review_status: &str,
    files: Option<&WorkspaceSnapshot>,
    files_status: &str,
    file_preview: Option<&FilePreview>,
    file_preview_status: &str,
    file_roots: &[ProjectRootSummary],
    file_root_menu_open: bool,
    file_tree_width: f32,
    review_workspace: &str,
    browser_url: &str,
    browser_status: &str,
    side_chat_status: &str,
    side_chat_parent_id: Option<&str>,
    side_chat_sessions: &[SessionSummary],
    selected_session_id: Option<&str>,
    side_chat_in_flight: bool,
    terminal_output: &str,
    terminal_status: &str,
    terminal_state: TerminalState,
    terminal_kept_alive: bool,
    terminal_workspace: &str,
    terminal_actions_enabled: bool,
    terminal_disabled_reason: &str,
    terminal_focus: &FocusHandle,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let mut tabs = div()
        .id("workspace-tool-tabs")
        .flex_1()
        .min_w(px(0.0))
        .h_full()
        .flex()
        .items_center()
        .overflow_x_scroll();
    for tool in open_tabs.iter().copied() {
        let item = SIDE_PANEL_ITEMS
            .iter()
            .find(|item| item.tool == tool)
            .expect("open workspace tool has metadata");
        let selected = selected_tool == Some(tool);
        tabs = tabs.child(
            div()
                .id(stable_element_id("workspace-tool-tab", item.label))
                .h(px(34.0))
                .px_3()
                .flex()
                .items_center()
                .rounded_lg()
                .bg(rgb(if selected {
                    color::SURFACE_SELECTED
                } else {
                    color::CANVAS
                }))
                .text_size(px(layout::TYPE_CONTROL))
                .text_color(rgb(if selected {
                    color::TEXT_PRIMARY
                } else {
                    color::TEXT_SECONDARY
                }))
                .role(gpui::Role::Tab)
                .aria_label(format!("Show {}", item.label))
                .aria_selected(selected)
                .tab_index(0)
                .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                .child(icon(item.icon, color::TEXT_SECONDARY))
                .child(div().ml_2().child(item.label))
                .on_click(cx.listener(move |this, _, window, cx| {
                    this.select_side_panel_tab(tool, window, cx);
                })),
        );
    }

    let floating_menu: gpui::AnyElement = if tool_picker_open && !open_tabs.is_empty() {
        div()
            .id("workspace-tool-picker")
            .absolute()
            .top(px(layout::TOP_BAR_HEIGHT - 4.0))
            .right(px(8.0))
            .child(workspace_tool_menu(cx))
            .into_any_element()
    } else {
        div().into_any_element()
    };

    let detail: gpui::AnyElement = match selected_tool {
        Some(SidePanelTool::Review) => {
            let mut scope_picker = div()
                .id("tool-review-scope-picker")
                .mt_3()
                .px_2()
                .py_1()
                .rounded_md()
                .bg(rgb(if file_roots.len() > 1 {
                    color::SURFACE
                } else {
                    color::CANVAS
                }))
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(if file_roots.len() > 1 {
                    color::TEXT_PRIMARY
                } else {
                    color::TEXT_TERTIARY
                }))
                .overflow_hidden()
                .text_ellipsis()
                .role(gpui::Role::Button)
                .aria_label("Select review source root")
                .aria_description(if file_roots.len() > 1 {
                    "Switch Review scope between project source roots"
                } else {
                    "The project primary source root is active"
                })
                .tab_index(0)
                .child(if review_workspace.is_empty() {
                    "No source root selected".to_owned()
                } else {
                    review_workspace.to_owned()
                });
            if file_roots.len() > 1 {
                scope_picker = scope_picker.on_click(cx.listener(|this, _, _, cx| {
                    this.toggle_file_root_menu(cx);
                }));
            }
            let review_scope_menu: gpui::AnyElement =
                if file_root_menu_open && file_roots.len() > 1 {
                    let mut menu = div()
                        .id("tool-review-scope-menu")
                        .mt_1()
                        .rounded_lg()
                        .border_1()
                        .border_color(rgb(color::BORDER))
                        .bg(rgb(color::ELEVATED))
                        .shadow_lg()
                        .p_1();
                    for root in file_roots {
                        let path = root.path.clone();
                        let selected = review_workspace == root.path;
                        menu = menu.child(
                            div()
                                .id(stable_element_id("review-scope-root", &root.root_id))
                                .px_2()
                                .py_1()
                                .rounded_md()
                                .text_size(px(layout::TYPE_METADATA))
                                .text_color(rgb(if selected {
                                    color::ACCENT
                                } else {
                                    color::TEXT_PRIMARY
                                }))
                                .role(gpui::Role::MenuItem)
                                .aria_label(format!("Review source root {}", root.path))
                                .tab_index(0)
                                .child(root.path.clone())
                                .on_click(cx.listener(move |this, _, _, cx| {
                                    this.select_file_root(path.clone(), cx);
                                })),
                        );
                    }
                    menu.into_any_element()
                } else {
                    div().into_any_element()
                };
            let mut content = div()
                .id("tool-review-detail")
                .size_full()
                .overflow_y_scroll()
                .p_3()
                .child(
                    div()
                        .flex()
                        .items_center()
                        .justify_between()
                        .child(
                            div()
                                .text_size(px(layout::TYPE_SECTION))
                                .font_weight(FontWeight::SEMIBOLD)
                                .child("Workspace review"),
                        )
                        .child(
                            div()
                                .id("tool-review-refresh")
                                .px_2()
                                .py_1()
                                .rounded_md()
                                .bg(rgb(color::SURFACE))
                                .text_size(px(layout::TYPE_CONTROL))
                                .role(gpui::Role::Button)
                                .aria_label("Refresh workspace review")
                                .tab_index(0)
                                .border_1()
                                .border_color(rgb(color::BORDER))
                                .focus_visible(|style| style.border_color(rgb(color::ACCENT)))
                                .child("Refresh")
                                .on_click(cx.listener(|this, _, _, cx| this.refresh_review(cx))),
                        ),
                )
                .child(
                    div()
                        .mt_2()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::TEXT_SECONDARY))
                        .child(review_status.to_owned()),
                )
                .child(scope_picker)
                .child(review_scope_menu);
            if let Some(review) = review {
                let changed_paths = review_changed_paths(&review.diff, 24);
                let mut files = div()
                    .id("tool-review-files")
                    .mt_3()
                    .rounded_lg()
                    .bg(rgb(color::SURFACE))
                    .p_3()
                    .text_size(px(layout::TYPE_METADATA));
                files = files.child(
                    div()
                        .flex()
                        .items_center()
                        .justify_between()
                        .text_color(rgb(color::TEXT_SECONDARY))
                        .child("Changed files")
                        .child(format!("{} file(s)", changed_paths.len())),
                );
                if changed_paths.is_empty() {
                    files = files.child(
                        div()
                            .mt_2()
                            .text_color(rgb(color::TEXT_TERTIARY))
                            .child("No file changes in the selected workspace"),
                    );
                } else {
                    for path in changed_paths {
                        files = files.child(
                            div()
                                .mt_2()
                                .flex()
                                .items_center()
                                .text_color(rgb(color::TEXT_PRIMARY))
                                .child(icon(Icon::File, color::TEXT_SECONDARY))
                                .child(
                                    div()
                                        .ml_2()
                                        .overflow_hidden()
                                        .text_ellipsis()
                                        .child(path),
                                ),
                        );
                    }
                }
                let read_only_actions = div()
                    .mt_3()
                    .flex()
                    .items_center()
                    .gap_2()
                    .child(
                        div()
                            .id("tool-review-stage-all")
                            .px_2()
                            .py_1()
                            .rounded_md()
                            .bg(rgb(color::CANVAS))
                            .text_color(rgb(color::TEXT_TERTIARY))
                            .role(gpui::Role::Button)
                            .aria_label("Stage all changes unavailable")
                            .aria_description("Review is read-only until a Git mutation route is available")
                            .tab_index(0)
                            .child("Stage all"),
                    )
                    .child(
                        div()
                            .id("tool-review-revert")
                            .px_2()
                            .py_1()
                            .rounded_md()
                            .bg(rgb(color::CANVAS))
                            .text_color(rgb(color::TEXT_TERTIARY))
                            .role(gpui::Role::Button)
                            .aria_label("Revert changes unavailable")
                            .aria_description("Review is read-only until a Git mutation route is available")
                            .tab_index(0)
                            .child("Revert"),
                    )
                    .child(
                        div()
                            .id("tool-review-comment")
                            .px_2()
                            .py_1()
                            .rounded_md()
                            .bg(rgb(color::CANVAS))
                            .text_color(rgb(color::TEXT_TERTIARY))
                            .role(gpui::Role::Button)
                            .aria_label("Inline comments unavailable")
                            .aria_description("Inline review comments are not exposed by the current runtime")
                            .tab_index(0)
                            .child("Comment"),
                    );
                content = content
                    .child(
                        div()
                            .mt_3()
                            .rounded_lg()
                            .bg(rgb(color::SURFACE))
                            .p_3()
                            .text_size(px(layout::TYPE_CONTROL))
                            .child(
                                div()
                                    .flex()
                                    .items_center()
                                    .justify_between()
                                    .child("Working tree")
                                    .child(
                                        div()
                                            .px_2()
                                            .py_1()
                                            .rounded_md()
                                            .bg(rgb(color::ACCENT_MUTED))
                                            .text_size(px(layout::TYPE_METADATA))
                                            .text_color(rgb(color::ACCENT))
                                            .child(review.branch.clone()),
                                    ),
                            )
                            .child(
                                div()
                                    .mt_2()
                                    .text_size(px(layout::TYPE_METADATA))
                                    .text_color(rgb(color::TEXT_SECONDARY))
                                    .child(review.summary.clone()),
                            )
                            .child(
                                div()
                                    .mt_2()
                                    .text_size(px(layout::TYPE_METADATA))
                                    .text_color(rgb(color::TEXT_TERTIARY))
                                    .child("Read-only Git projection"),
                            ),
                    )
                    .child(files)
                    .child(read_only_actions)
                    .child(
                        div()
                            .id("tool-review-diff")
                            .mt_2()
                            .max_h(px(260.0))
                            .flex()
                            .flex_col()
                            .overflow_y_scroll()
                            .rounded_lg()
                            .bg(rgb(color::SIDEBAR))
                            .p_3()
                            .font_family("SF Mono")
                            .text_size(px(layout::TYPE_CODE))
                            .text_color(rgb(color::TEXT_PRIMARY))
                            .child(review.diff.clone()),
                    );
            }
            content.into_any_element()
        }
        Some(SidePanelTool::Terminal) => terminal_view::terminal_pane(
            terminal_output,
            terminal_status,
            terminal_state,
            terminal_kept_alive,
            terminal_workspace,
            terminal_actions_enabled,
            terminal_disabled_reason,
            terminal_focus,
            cx.entity(),
            cx,
        )
        .into_any_element(),
        Some(SidePanelTool::Browser) => div()
            .id("tool-browser-detail")
            .size_full()
            .flex()
            .flex_col()
            .overflow_hidden()
            .p_3()
            .child(
                div()
                    .text_size(px(layout::TYPE_SECTION))
                    .font_weight(FontWeight::SEMIBOLD)
                    .child("Browser"),
            )
            .child(
                div()
                    .mt_3()
                    .h(px(34.0))
                    .px_3()
                    .flex()
                    .items_center()
                    .rounded_lg()
                    .border_1()
                    .border_color(rgb(color::BORDER))
                    .bg(rgb(color::SURFACE))
                    .text_size(px(layout::TYPE_CONTROL))
                    .text_color(rgb(color::TEXT_SECONDARY))
                    .child(browser_url.to_owned()),
            )
            .child(
                div()
                    .mt_2()
                    .text_size(px(layout::TYPE_METADATA))
                    .text_color(rgb(color::TEXT_SECONDARY))
                    .child("Embedded WebView is unavailable in the Rust + GPUI runtime."),
            )
            .child(
                div()
                    .mt_2()
                    .rounded_lg()
                    .bg(rgb(color::SURFACE))
                    .p_3()
                    .text_size(px(layout::TYPE_CONTROL))
                    .child("Navigation controls are disabled until a native browser bridge is available."),
            )
            .child(
                div()
                    .mt_2()
                    .text_size(px(layout::TYPE_METADATA))
                    .text_color(rgb(color::TEXT_SECONDARY))
                    .child(browser_status.to_owned()),
            )
            .child(
                div()
                    .id("tool-browser-open")
                    .mt_3()
                    .px_3()
                    .py_2()
                    .rounded_lg()
                    .bg(rgb(color::SURFACE_SELECTED))
                    .text_size(px(layout::TYPE_CONTROL))
                    .role(gpui::Role::Button)
                    .aria_label("Open browser URL")
                    .tab_index(0)
                    .border_1()
                    .border_color(rgb(color::BORDER))
                    .focus_visible(|style| style.border_color(rgb(color::ACCENT)))
                    .child("Open in system browser…")
                    .on_click(cx.listener(|this, _, _, cx| this.show_browser_prompt(cx))),
            )
            .into_any_element(),
        Some(SidePanelTool::Files) => {
            let selected_root = files
                .map(|snapshot| snapshot.root.as_str())
                .or_else(|| file_roots.first().map(|root| root.path.as_str()))
                .unwrap_or("No source root selected");
            let mut root_picker = div()
                .id("tool-files-root-picker")
                .max_w(px(file_tree_width - 20.0))
                .px_2()
                .py_1()
                .rounded_md()
                .bg(rgb(if file_roots.len() > 1 {
                    color::SURFACE
                } else {
                    color::CANVAS
                }))
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(if file_roots.len() > 1 {
                    color::TEXT_PRIMARY
                } else {
                    color::TEXT_TERTIARY
                }))
                .overflow_hidden()
                .text_ellipsis()
                .role(gpui::Role::Button)
                .aria_label("Select source root")
                .aria_description(if file_roots.len() > 1 {
                    "Switch the Files and Review scope between project source roots"
                } else {
                    "The project primary source root is active"
                })
                .tab_index(0)
                .child(selected_root.to_owned());
            if file_roots.len() > 1 {
                root_picker = root_picker.on_click(cx.listener(|this, _, _, cx| {
                    this.toggle_file_root_menu(cx);
                }));
            }
            let root_menu: gpui::AnyElement = if file_root_menu_open && file_roots.len() > 1 {
                let mut menu = div()
                    .id("tool-files-root-menu")
                    .mt_1()
                    .rounded_lg()
                    .border_1()
                    .border_color(rgb(color::BORDER))
                    .bg(rgb(color::ELEVATED))
                    .shadow_lg()
                    .p_1();
                for root in file_roots.iter().cloned() {
                    let path = root.path.clone();
                    let label = if root.primary {
                        format!("{} · primary", root.path)
                    } else {
                        root.path.clone()
                    };
                    menu = menu.child(
                        div()
                            .id(stable_element_id("tool-files-root", &root.root_id))
                            .px_2()
                            .py_2()
                            .rounded_md()
                            .text_size(px(layout::TYPE_METADATA))
                            .role(gpui::Role::MenuItem)
                            .aria_label(format!("Use source root {}", root.path))
                            .tab_index(0)
                            .child(label)
                            .on_click(cx.listener(move |this, _, _, cx| {
                                this.select_file_root(path.clone(), cx);
                            })),
                    );
                }
                menu.into_any_element()
            } else {
                div().into_any_element()
            };
            let mut tree = div()
                .id("workspace-file-tree")
                .w(px(file_tree_width))
                .min_w(px(file_tree_width))
                .h_full()
                .flex()
                .flex_col()
                .overflow_hidden()
                .bg(rgb(color::CANVAS))
                .p_2()
                .child(
                    div()
                        .h(px(32.0))
                        .flex()
                        .items_center()
                        .justify_between()
                        .child(div().text_size(px(layout::TYPE_CONTROL)).child("Files"))
                        .child(
                            div()
                                .id("tool-files-refresh")
                                .px_2()
                                .py_1()
                                .rounded_md()
                                .bg(rgb(color::SURFACE))
                                .text_size(px(layout::TYPE_METADATA))
                                .role(gpui::Role::Button)
                                .aria_label("Refresh workspace files")
                                .tab_index(0)
                                .border_1()
                                .border_color(rgb(color::BORDER))
                                .focus_visible(|style| style.border_color(rgb(color::ACCENT)))
                                .child("Refresh")
                                .on_click(cx.listener(|this, _, _, cx| this.refresh_files(cx))),
                        ),
                )
                .child(root_picker)
                .child(root_menu)
                .child(
                    div()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::TEXT_SECONDARY))
                        .child(files_status.to_owned()),
                );
            if let Some(files) = files {
                let mut rows = div()
                    .id("tool-files-list")
                    .mt_2()
                    .flex_1()
                    .min_h(px(0.0))
                    .flex()
                    .flex_col()
                    .overflow_y_scroll()
                    .bg(rgb(color::CANVAS));
                for entry in files.entries.iter().take(80) {
                    let selected = file_preview
                        .is_some_and(|preview| preview.relative_path == entry.relative_path);
                    let mut row = div()
                        .id(stable_element_id(
                            "workspace-file-row",
                            &entry.relative_path,
                        ))
                        .px_2()
                        .py_1()
                        .rounded_md()
                        .bg(rgb(if selected {
                            color::SURFACE_SELECTED
                        } else {
                            color::CANVAS
                        }))
                        .text_size(px(layout::TYPE_CONTROL))
                        .text_color(rgb(if entry.is_directory {
                            color::TEXT_PRIMARY
                        } else {
                            color::TEXT_SECONDARY
                        }))
                        .child(if entry.is_directory {
                            icon(Icon::Folder, color::TEXT_PRIMARY).into_any_element()
                        } else {
                            icon(Icon::File, color::TEXT_SECONDARY).into_any_element()
                        })
                        .child(div().ml_2().child(entry.relative_path.clone()));
                    if !entry.is_directory {
                        let relative_path = entry.relative_path.clone();
                        row = row
                            .role(gpui::Role::Button)
                            .aria_label(format!("Open {}", entry.relative_path))
                            .tab_index(0)
                            .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                            .on_click(cx.listener(move |this, _, _, cx| {
                                this.open_workspace_file(relative_path.clone(), cx);
                            }));
                    }
                    rows = rows.child(row);
                }
                tree = tree.child(rows);
            }
            let file_detail: gpui::AnyElement = if let Some(preview) = file_preview {
                let reveal_path = preview.relative_path.clone();
                div()
                    .id("workspace-file-preview")
                    .size_full()
                    .min_w(px(0.0))
                    .flex()
                    .flex_col()
                    .p_3()
                    .child(
                        div()
                            .flex()
                            .items_center()
                            .justify_between()
                            .text_size(px(layout::TYPE_CONTROL))
                            .font_weight(FontWeight::SEMIBOLD)
                            .child(preview.relative_path.clone())
                            .child(
                                div()
                                    .id("workspace-file-reveal")
                                    .px_2()
                                    .py_1()
                                    .rounded_md()
                                    .bg(rgb(color::SURFACE))
                                    .text_size(px(layout::TYPE_METADATA))
                                    .role(gpui::Role::Button)
                                    .aria_label("Reveal file in Finder")
                                    .tab_index(0)
                                    .child("Reveal in Finder")
                                    .on_click(cx.listener(move |this, _, _, cx| {
                                        this.reveal_workspace_file(reveal_path.clone(), cx);
                                    })),
                            ),
                    )
                    .child(
                        div()
                            .mt_1()
                            .text_size(px(layout::TYPE_METADATA))
                            .text_color(rgb(color::TEXT_SECONDARY))
                            .child(file_preview_status.to_owned()),
                    )
                    .child(
                        div()
                            .id("workspace-file-preview-content")
                            .mt_3()
                            .flex_1()
                            .min_h(px(0.0))
                            .overflow_y_scroll()
                            .font_family("SF Mono")
                            .text_size(px(layout::TYPE_CODE))
                            .child(preview.text.clone()),
                    )
                    .into_any_element()
            } else {
                div()
                    .size_full()
                    .flex()
                    .flex_col()
                    .items_center()
                    .justify_center()
                    .text_color(rgb(color::TEXT_SECONDARY))
                    .child(
                        div()
                            .text_size(px(layout::TYPE_SECTION))
                            .font_weight(FontWeight::SEMIBOLD)
                            .child("Open file"),
                    )
                    .child(
                        div()
                            .mt_2()
                            .text_size(px(layout::TYPE_METADATA))
                            .child(file_preview_status.to_owned()),
                    )
                    .into_any_element()
            };
            div()
                .id("tool-files-detail")
                .size_full()
                .min_w(px(0.0))
                .flex()
                .on_drag_move::<DraggedFileTreeDivider>(
                    cx.listener(|this, event, _window, cx| this.resize_file_tree(event, cx)),
                )
                .on_drop::<DraggedFileTreeDivider>(
                    cx.listener(|this, _event, _window, cx| this.persist_panel_preferences(cx)),
                )
                .child(div().flex_1().min_w(px(0.0)).child(file_detail))
                .child(file_tree_resize_handle(cx))
                .child(tree)
                .into_any_element()
        }
        Some(SidePanelTool::SideChat) => {
            let parent = side_chat_parent_id
                .map(|id| id.chars().take(24).collect::<String>())
                .unwrap_or_else(|| "No parent yet".to_owned());
            let mut side_chat_list = div().id("tool-side-chat-list").mt_3();
            if side_chat_sessions.is_empty() {
                side_chat_list = side_chat_list.child(
                    div()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::TEXT_TERTIARY))
                        .child(if side_chat_parent_id.is_some() {
                            "No side chats for this parent yet"
                        } else {
                            "Select a chat to see its side chats"
                        }),
                );
            } else {
                side_chat_list = side_chat_list.child(
                    div()
                        .mb_1()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::TEXT_SECONDARY))
                        .child("Side chats"),
                );
                for session in side_chat_sessions {
                    let session_id = session.session_id.clone();
                    let selected = selected_session_id == Some(session.session_id.as_str());
                    side_chat_list = side_chat_list.child(
                        div()
                            .id(stable_element_id("side-chat-row", &session.session_id))
                            .mt_1()
                            .px_2()
                            .py_2()
                            .rounded_lg()
                            .bg(rgb(if selected {
                                color::SURFACE_SELECTED
                            } else {
                                color::SURFACE
                            }))
                            .role(gpui::Role::Button)
                            .aria_label(format!("Open side chat {}", session.title))
                            .tab_index(0)
                            .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                            .child(
                                div()
                                    .text_size(px(layout::TYPE_CONTROL))
                                    .overflow_hidden()
                                    .text_ellipsis()
                                    .child(session.title.clone()),
                            )
                            .child(
                                div()
                                    .mt_1()
                                    .text_size(px(layout::TYPE_METADATA))
                                    .text_color(rgb(color::TEXT_TERTIARY))
                                    .child(format!("{} message(s)", session.messages)),
                            )
                            .on_click(cx.listener(move |this, _, _, cx| {
                                this.open_side_chat_session(session_id.clone(), cx);
                            })),
                    );
                }
            }
            let parent_action: gpui::AnyElement = if let Some(parent_id) = side_chat_parent_id {
                let parent_id = parent_id.to_owned();
                div()
                    .id("tool-side-chat-parent")
                    .mt_3()
                    .px_3()
                    .py_2()
                    .rounded_lg()
                    .bg(rgb(color::CANVAS))
                    .text_size(px(layout::TYPE_METADATA))
                    .text_color(rgb(color::TEXT_SECONDARY))
                    .role(gpui::Role::Button)
                    .aria_label("Open parent chat")
                    .tab_index(0)
                    .child("Open parent chat")
                    .on_click(cx.listener(move |this, _, _, cx| {
                        this.open_side_chat_session(parent_id.clone(), cx);
                    }))
                    .into_any_element()
            } else {
                div().into_any_element()
            };
            div()
                .id("tool-side-chat-detail")
                .size_full()
                .overflow_y_scroll()
                .p_3()
                .child(
                    div()
                        .text_size(px(layout::TYPE_SECTION))
                        .font_weight(FontWeight::SEMIBOLD)
                        .child("Side chat"),
                )
                .child(
                    div()
                        .mt_2()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::TEXT_SECONDARY))
                        .child(side_chat_status.to_owned()),
                )
                .child(
                    div()
                        .mt_2()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::TEXT_TERTIARY))
                        .child(format!("Parent: {parent}")),
                )
                .child(parent_action)
                .child(side_chat_list)
                .child(
                    div()
                        .id("tool-side-chat-create")
                        .mt_3()
                        .px_3()
                        .py_2()
                        .rounded_lg()
                        .bg(rgb(if side_chat_in_flight {
                            color::SURFACE
                        } else {
                            color::SURFACE_SELECTED
                        }))
                        .text_size(px(layout::TYPE_CONTROL))
                        .text_color(rgb(if side_chat_in_flight {
                            color::TEXT_TERTIARY
                        } else {
                            color::TEXT_PRIMARY
                        }))
                        .role(gpui::Role::Button)
                        .aria_label("Create side chat")
                        .tab_index(0)
                        .border_1()
                        .border_color(rgb(color::BORDER))
                        .focus_visible(|style| style.border_color(rgb(color::ACCENT)))
                        .child(if side_chat_in_flight {
                            "Creating side chat…"
                        } else {
                            "New side chat"
                        })
                        .on_click(cx.listener(|this, _, _, cx| this.create_side_chat(cx))),
                )
                .into_any_element()
        }
        None => div()
            .id("tool-picker-detail")
            .size_full()
            .flex()
            .flex_col()
            .items_center()
            .justify_center()
            .child(workspace_tool_menu(cx))
            .into_any_element(),
    };

    div()
        .id("workspace-tools-panel")
        .tab_group()
        .relative()
        .size_full()
        .min_h(px(0.0))
        .flex()
        .flex_col()
        .overflow_hidden()
        .bg(rgb(color::ELEVATED))
        .border_l_1()
        .border_color(rgb(color::BORDER))
        .child(
            div()
                .h(px(layout::TOP_BAR_HEIGHT))
                .min_h(px(layout::TOP_BAR_HEIGHT))
                .px_2()
                .flex()
                .items_center()
                .border_b_1()
                .border_color(rgb(color::BORDER))
                .child(tabs)
                .child(
                    div()
                        .id("workspace-tool-add")
                        .ml_1()
                        .w(px(30.0))
                        .h(px(30.0))
                        .flex()
                        .items_center()
                        .justify_center()
                        .rounded_lg()
                        .text_size(px(layout::TYPE_SECTION))
                        .font_weight(FontWeight::SEMIBOLD)
                        .role(gpui::Role::Button)
                        .aria_label("Add workspace tool")
                        .tab_index(0)
                        .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                        .child(icon(Icon::Plus, color::TEXT_PRIMARY))
                        .on_click(cx.listener(|this, _, _, cx| this.toggle_tool_picker(cx))),
                )
                .child(
                    div()
                        .id("workspace-tool-close-tab")
                        .ml_1()
                        .w(px(28.0))
                        .h(px(28.0))
                        .flex()
                        .items_center()
                        .justify_center()
                        .rounded_md()
                        .role(gpui::Role::Button)
                        .aria_label("Close active workspace tool")
                        .tab_index(0)
                        .focus_visible(|style| style.border_color(rgb(color::ACCENT)))
                        .child(icon(Icon::Close, color::TEXT_SECONDARY))
                        .on_click(cx.listener(|this, _, window, cx| {
                            this.close_active_side_panel_tab(window, cx)
                        })),
                ),
        )
        .child(div().flex_1().min_h(px(0.0)).child(detail))
        .child(floating_menu)
}

#[cfg(test)]
mod tests {
    use super::side_chat_sessions_for_parent;
    use codinal_control_plane_client::SessionSummary;

    fn session(
        id: &str,
        updated_at: &str,
        origin: Option<&str>,
        origin_session_id: Option<&str>,
        archived: bool,
    ) -> SessionSummary {
        SessionSummary {
            session_id: id.to_owned(),
            title: id.to_owned(),
            workspace: "/tmp/workspace".to_owned(),
            messages: 1,
            updated_at: updated_at.to_owned(),
            pinned: false,
            archived,
            origin: origin.map(str::to_owned),
            origin_label: None,
            origin_session_id: origin_session_id.map(str::to_owned),
            project_id: None,
        }
    }

    #[test]
    fn side_chat_tree_is_parent_scoped_sorted_and_bounded() {
        let sessions = vec![
            session(
                "older",
                "2026-08-03T01:00:00Z",
                Some("side_chat"),
                Some("parent"),
                false,
            ),
            session(
                "newer",
                "2026-08-03T02:00:00Z",
                Some("side_chat"),
                Some("parent"),
                false,
            ),
            session(
                "other-parent",
                "2026-08-03T03:00:00Z",
                Some("side_chat"),
                Some("other"),
                false,
            ),
            session(
                "archived",
                "2026-08-03T04:00:00Z",
                Some("side_chat"),
                Some("parent"),
                true,
            ),
        ];
        let children = side_chat_sessions_for_parent(&sessions, Some("parent"), 1);
        assert_eq!(
            children
                .iter()
                .map(|session| session.session_id.as_str())
                .collect::<Vec<_>>(),
            ["newer"]
        );
        assert!(side_chat_sessions_for_parent(&sessions, None, 20).is_empty());
    }
}
