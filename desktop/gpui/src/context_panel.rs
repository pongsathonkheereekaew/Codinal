//! Contextual safety panel presentation.
//!
//! Approval content is rendered from the typed UI projection.  Runtime
//! confirmation remains on `WorkspacePrototype` and the authenticated client.

use crate::disabled_reason_label;
use crate::icons::{icon, Icon};
use crate::is_activation_key;
use crate::light_theme::{color, layout};
use crate::ui_model::PendingApprovalProjection;
use crate::WorkspacePrototype;
use codinal_control_plane_client::{SourceAttachment, SourcePreview};
use gpui::{
    div, img, px, rgb, Context, InteractiveElement, IntoElement, KeyDownEvent, ObjectFit,
    ParentElement, StatefulInteractiveElement, Styled, StyledImage,
};

fn environment_row(
    id: &'static str,
    label: &'static str,
    detail: String,
    icon_kind: Icon,
    enabled: bool,
) -> impl gpui::IntoElement {
    div()
        .id(id)
        .px_3()
        .py_2()
        .flex()
        .items_center()
        .justify_between()
        .rounded_lg()
        .text_size(px(layout::TYPE_CONTROL))
        .text_color(rgb(if enabled {
            color::TEXT_PRIMARY
        } else {
            color::TEXT_TERTIARY
        }))
        .child(
            div()
                .flex()
                .items_center()
                .flex_shrink_0()
                .min_w(px(0.0))
                .child(
                    div()
                        .w(px(24.0))
                        .h(px(20.0))
                        .flex()
                        .items_center()
                        .justify_center()
                        .mr_2()
                        .text_color(rgb(color::TEXT_SECONDARY))
                        .child(icon(
                            icon_kind,
                            if enabled {
                                color::TEXT_SECONDARY
                            } else {
                                color::TEXT_TERTIARY
                            },
                        )),
                )
                .child(label),
        )
        .child(
            div()
                .ml_2()
                .flex_1()
                .min_w(px(0.0))
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_TERTIARY))
                .overflow_hidden()
                .text_ellipsis()
                .text_right()
                .child(detail),
        )
}

fn source_icon(kind: &str) -> Icon {
    let kind = kind.to_ascii_lowercase();
    if kind.contains("image") || kind.contains("screenshot") || kind.contains("png") {
        Icon::Image
    } else {
        Icon::File
    }
}

fn source_visual(source: &SourceAttachment) -> gpui::AnyElement {
    let kind = source.kind.to_ascii_lowercase();
    let is_image = kind.contains("image")
        || kind.contains("screenshot")
        || kind.contains("png")
        || kind.contains("jpg")
        || kind.contains("jpeg")
        || kind.contains("webp");
    if source.status == "ready" && is_image && std::path::Path::new(&source.path).is_file() {
        img(source.path.clone())
            .w(px(18.0))
            .h(px(18.0))
            .rounded_sm()
            .object_fit(ObjectFit::Cover)
            .into_any_element()
    } else {
        icon(source_icon(&source.kind), color::TEXT_TERTIARY).into_any_element()
    }
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn environment_pane(
    workspace: &str,
    runtime_status: &str,
    review_status: &str,
    branch_status: &str,
    _files_status: &str,
    sources: &[SourceAttachment],
    sources_status: &str,
    source_menu_open: bool,
    source_operation_in_flight: bool,
    mutations_enabled: bool,
    disabled_reason: &str,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let workspace = if workspace.is_empty() {
        "No workspace selected".to_owned()
    } else {
        workspace.to_owned()
    };
    let source_detail = if workspace == "No workspace selected" {
        "Select a chat to view source attachments".to_owned()
    } else {
        sources_status.to_owned()
    };
    let mut source_list = div().id("environment-sources-list").mt_1();
    if sources.is_empty() {
        source_list = source_list.child(
            div()
                .id("environment-sources-empty")
                .px_3()
                .py_2()
                .rounded_lg()
                .bg(rgb(color::SURFACE))
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_SECONDARY))
                .child(source_detail),
        );
    } else {
        for source in sources.iter().take(100) {
            let attachment_id = source.attachment_id.clone();
            let retry_id = attachment_id.clone();
            let remove_id = attachment_id.clone();
            let status = source.status.clone();
            let status_detail = source
                .error
                .clone()
                .unwrap_or_else(|| format!("{} · {}", source.kind, source.status));
            let mut row = div()
                .id(crate::stable_element_id("source-row", &attachment_id))
                .px_3()
                .py_2()
                .rounded_lg()
                .bg(rgb(color::SURFACE))
                .child(
                    div()
                        .flex()
                        .items_center()
                        .text_size(px(layout::TYPE_CONTROL))
                        .text_color(rgb(color::TEXT_PRIMARY))
                        .overflow_hidden()
                        .text_ellipsis()
                        .child(
                            div()
                                .w(px(20.0))
                                .h(px(20.0))
                                .flex()
                                .items_center()
                                .justify_center()
                                .child(source_visual(source)),
                        )
                        .child(div().ml_2().child(source.name.clone())),
                )
                .child(
                    div()
                        .mt_1()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(if status == "ready" {
                            color::TEXT_TERTIARY
                        } else {
                            color::DANGER
                        }))
                        .overflow_hidden()
                        .text_ellipsis()
                        .child(status_detail),
                );
            if mutations_enabled && status != "ready" {
                row = row.child(
                    div()
                        .id(crate::stable_element_id("source-retry", &retry_id))
                        .mt_1()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::ACCENT))
                        .role(gpui::Role::Button)
                        .aria_label(format!("Retry source {}", source.name))
                        .tab_index(0)
                        .child("Retry")
                        .on_click(cx.listener(move |this, _, _, cx| {
                            this.retry_source(retry_id.clone(), cx);
                        })),
                );
            }
            if mutations_enabled {
                row = row.child(
                    div()
                        .id(crate::stable_element_id("source-remove", &remove_id))
                        .mt_1()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::DANGER))
                        .role(gpui::Role::Button)
                        .aria_label(format!("Remove source {}", source.name))
                        .tab_index(0)
                        .child("Remove")
                        .on_click(cx.listener(move |this, _, _, cx| {
                            this.remove_source(remove_id.clone(), cx);
                        })),
                );
            }
            source_list = source_list.child(row);
        }
    }
    let mut source_add = div()
        .id("environment-sources-add")
        .mt_2()
        .px_3()
        .py_2()
        .rounded_lg()
        .bg(rgb(if mutations_enabled {
            color::SURFACE
        } else {
            color::CANVAS
        }))
        .text_size(px(layout::TYPE_METADATA))
        .text_color(rgb(if mutations_enabled {
            color::ACCENT
        } else {
            color::TEXT_TERTIARY
        }))
        .role(gpui::Role::Button)
        .aria_label("Add a source file or folder")
        .aria_description(if mutations_enabled {
            "Choose a file or folder to attach to this conversation"
        } else {
            disabled_reason
        })
        .tab_index(0)
        .child(if source_operation_in_flight {
            "Working…"
        } else {
            "+ Add source"
        });
    if mutations_enabled {
        source_add = source_add.on_click(cx.listener(|this, _, _, cx| {
            this.toggle_source_menu(cx);
        }));
    }
    let source_menu: gpui::AnyElement = if source_menu_open {
        div()
            .id("environment-sources-menu")
            .mt_1()
            .px_2()
            .py_1()
            .rounded_lg()
            .bg(rgb(color::ELEVATED))
            .border_1()
            .border_color(rgb(color::BORDER))
            .child(
                div()
                    .id("source-add-file")
                    .px_2()
                    .py_1()
                    .role(gpui::Role::Button)
                    .aria_label("Add source file")
                    .tab_index(0)
                    .child("Add file")
                    .on_click(cx.listener(|this, _, _, cx| {
                        this.add_source(false, cx);
                    })),
            )
            .child(
                div()
                    .id("source-add-folder")
                    .px_2()
                    .py_1()
                    .role(gpui::Role::Button)
                    .aria_label("Add source folder")
                    .tab_index(0)
                    .child("Add folder")
                    .on_click(cx.listener(|this, _, _, cx| {
                        this.add_source(true, cx);
                    })),
            )
            .into_any_element()
    } else {
        div().into_any_element()
    };
    div()
        .id("environment-pane")
        .border_b_1()
        .border_color(rgb(color::BORDER))
        .p_3()
        .child(
            div()
                .flex()
                .items_center()
                .justify_between()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_TERTIARY))
                .child("Environment")
                .child(icon(Icon::Plus, color::TEXT_TERTIARY)),
        )
        .child(environment_row(
            "environment-changes",
            "Changes",
            review_status.to_owned(),
            Icon::Changes,
            true,
        ))
        .child(environment_row(
            "environment-local",
            "Local",
            workspace.clone(),
            Icon::Laptop,
            true,
        ))
        .child(environment_row(
            "environment-runtime",
            "Runtime",
            runtime_status.to_owned(),
            Icon::Navigation,
            true,
        ))
        .child(environment_row(
            "environment-branch",
            "Branch",
            branch_status.to_owned(),
            Icon::GitBranch,
            branch_status != "Branch metadata unavailable",
        ))
        .child(environment_row(
            "environment-commit",
            "Commit or push",
            "Disabled until a native Git mutation route is available".to_owned(),
            Icon::GitCommit,
            false,
        ))
        .child(environment_row(
            "environment-compare",
            "Compare branch",
            "Disabled until branch comparison is available".to_owned(),
            Icon::Github,
            false,
        ))
        .child(
            div()
                .mt_3()
                .pt_3()
                .border_t_1()
                .border_color(rgb(color::BORDER))
                .flex()
                .items_center()
                .justify_between()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_TERTIARY))
                .child("Sources")
                .child(icon(Icon::Plus, color::TEXT_TERTIARY)),
        )
        .child(
            div()
                .id("environment-sources-view-all")
                .mt_2()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::ACCENT))
                .role(gpui::Role::Button)
                .aria_label("View all sources")
                .tab_index(0)
                .child(icon(Icon::Link, color::ACCENT))
                .child(div().ml_1().child("View all"))
                .on_click(cx.listener(|this, _, _, cx| {
                    this.open_sources_drawer(cx);
                })),
        )
        .child(source_list)
        .child(source_add)
        .child(source_menu)
}

pub(crate) fn sources_drawer(
    open: bool,
    sources: &[SourceAttachment],
    status: &str,
    preview: Option<&SourcePreview>,
    preview_status: &str,
    cx: &mut Context<WorkspacePrototype>,
) -> gpui::AnyElement {
    if !open {
        return div().into_any_element();
    }
    let mut list = div().id("sources-drawer-list").mt_3();
    if sources.is_empty() {
        list = list.child(
            div()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_SECONDARY))
                .child(status.to_owned()),
        );
    } else {
        for source in sources {
            let preview_id = source.attachment_id.clone();
            list = list.child(
                div()
                    .id(crate::stable_element_id(
                        "sources-drawer-row",
                        &source.attachment_id,
                    ))
                    .py_3()
                    .border_b_1()
                    .border_color(rgb(color::BORDER))
                    .role(gpui::Role::Button)
                    .aria_label(format!("Preview source {}", source.name))
                    .tab_index(0)
                    .on_click(cx.listener(move |this, _, _, cx| {
                        this.preview_source(preview_id.clone(), cx);
                    }))
                    .child(
                        div()
                            .flex()
                            .items_center()
                            .text_size(px(layout::TYPE_CONTROL))
                            .text_color(rgb(color::TEXT_PRIMARY))
                            .child(source_visual(source))
                            .child(div().ml_2().child(source.name.clone())),
                    )
                    .child(
                        div()
                            .mt_1()
                            .text_size(px(layout::TYPE_METADATA))
                            .text_color(rgb(color::TEXT_TERTIARY))
                            .overflow_hidden()
                            .text_ellipsis()
                            .child(source.path.clone()),
                    )
                    .child(
                        div()
                            .mt_2()
                            .text_size(px(layout::TYPE_METADATA))
                            .text_color(rgb(if source.status == "ready" {
                                color::TEXT_SECONDARY
                            } else {
                                color::DANGER
                            }))
                            .child(if source.status == "ready" {
                                "Attached to conversation"
                            } else {
                                "Source unavailable"
                            }),
                    ),
            );
        }
    }
    let preview_panel = if let Some(preview) = preview {
        let content = if preview.binary {
            "Binary source · content preview is unavailable".to_owned()
        } else if preview.content.is_empty() {
            "(empty source)".to_owned()
        } else {
            preview.content.clone()
        };
        div()
            .id("sources-drawer-preview")
            .mt_4()
            .pt_4()
            .border_t_1()
            .border_color(rgb(color::BORDER))
            .child(
                div()
                    .text_size(px(layout::TYPE_CONTROL))
                    .text_color(rgb(color::TEXT_PRIMARY))
                    .child(preview.attachment.name.clone()),
            )
            .child(
                div()
                    .mt_1()
                    .text_size(px(layout::TYPE_METADATA))
                    .text_color(rgb(color::TEXT_TERTIARY))
                    .child(preview_status.to_owned()),
            )
            .child(
                div()
                    .id("sources-drawer-preview-content")
                    .mt_2()
                    .max_h(px(320.0))
                    .p_2()
                    .rounded_lg()
                    .bg(rgb(color::SURFACE))
                    .text_size(px(layout::TYPE_METADATA))
                    .text_color(rgb(color::TEXT_PRIMARY))
                    .overflow_y_scroll()
                    .child(content),
            )
            .into_any_element()
    } else {
        div()
            .id("sources-drawer-preview-status")
            .mt_4()
            .pt_4()
            .border_t_1()
            .border_color(rgb(color::BORDER))
            .text_size(px(layout::TYPE_METADATA))
            .text_color(rgb(color::TEXT_TERTIARY))
            .child(preview_status.to_owned())
            .into_any_element()
    };
    div()
        .id("sources-drawer")
        .absolute()
        .top_0()
        .right_0()
        .bottom_0()
        .w(px(360.0))
        .p_4()
        .bg(rgb(color::ELEVATED))
        .border_l_1()
        .border_color(rgb(color::BORDER))
        .shadow_lg()
        .child(
            div()
                .flex()
                .items_center()
                .justify_between()
                .text_size(px(layout::TYPE_SECTION))
                .child("Sources")
                .child(
                    div()
                        .id("sources-drawer-close")
                        .text_color(rgb(color::TEXT_SECONDARY))
                        .role(gpui::Role::Button)
                        .aria_label("Close sources")
                        .tab_index(0)
                        .child(icon(Icon::Close, color::TEXT_SECONDARY))
                        .on_click(cx.listener(|this, _, _, cx| {
                            this.close_sources_drawer(cx);
                        })),
                ),
        )
        .child(list)
        .child(preview_panel)
        .into_any_element()
}

pub(crate) fn approval_pane(
    approvals: &[PendingApprovalProjection],
    has_pending_approval: bool,
    review_status: &str,
    actions_enabled: bool,
    disabled_reason: &str,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let approval_summary = if approvals.is_empty() {
        "No pending approvals".to_owned()
    } else {
        approvals
            .iter()
            .take(20)
            .map(|approval| {
                format!(
                    "{} · {} · {}",
                    approval.risk, approval.tool_name, approval.reason
                )
            })
            .collect::<Vec<_>>()
            .join("\n")
    };
    let pane = div()
        .id("approval-pane")
        .border_b_1()
        .border_color(rgb(color::BORDER))
        .p_4()
        .child(div().text_size(px(layout::TYPE_CONTROL)).child("Approvals"))
        .child(
            div()
                .mt_2()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_SECONDARY))
                .child(approval_summary),
        )
        .child(
            div()
                .mt_2()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::TEXT_SECONDARY))
                .child(review_status.to_owned()),
        );
    if has_pending_approval {
        if actions_enabled {
            pane.child(
                div()
                    .id("review-pending-approval")
                    .mt_3()
                    .px_2()
                    .py_1()
                    .rounded_md()
                    .bg(rgb(color::ACCENT))
                    .text_color(rgb(color::CANVAS))
                    .role(gpui::Role::Button)
                    .aria_label("Review pending approval")
                    .aria_keyshortcuts("Enter")
                    .tab_index(0)
                    .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                    .on_key_down(cx.listener(|this, event: &KeyDownEvent, window, cx| {
                        if is_activation_key(event) {
                            this.show_approval_prompt(window, cx);
                        }
                    }))
                    .child("Review approval…")
                    .on_click(cx.listener(|this, _, window, cx| {
                        this.show_approval_prompt(window, cx);
                    })),
            )
        } else {
            pane.child(
                div()
                    .id("review-pending-approval-disabled")
                    .mt_3()
                    .px_2()
                    .py_1()
                    .rounded_md()
                    .bg(rgb(color::SURFACE))
                    .text_color(rgb(color::TEXT_SECONDARY))
                    .role(gpui::Role::Button)
                    .aria_label("Approval action unavailable")
                    .aria_description(disabled_reason_label(disabled_reason))
                    .tab_index(0)
                    .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                    .child(format!(
                        "Approval action unavailable · {}",
                        disabled_reason_label(disabled_reason)
                    )),
            )
        }
    } else {
        pane
    }
}
