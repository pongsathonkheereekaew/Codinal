//! Conversation-first transcript presentation.
//!
//! This view accepts bounded typed blocks from `ui_model`; it does not parse
//! durable strings or invoke runtime effects.

use crate::icons::{icon, Icon};
use crate::light_theme::{color, layout};
use crate::stable_element_id;
use crate::workbench::{TimelineBlock, TimelineKind};
use gpui::{
    div, px, rgb, Context, FontWeight, InteractiveElement, IntoElement, ParentElement,
    StatefulInteractiveElement, Styled,
};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum StarterCategory {
    Explore,
    Build,
    Review,
    Fix,
}

impl StarterCategory {
    pub(crate) fn title(self) -> &'static str {
        match self {
            Self::Explore => "Explore and understand code",
            Self::Build => "Build a new feature, app, or tool",
            Self::Review => "Review code and suggest changes",
            Self::Fix => "Fix issues and failures",
        }
    }

    pub(crate) fn seed(self) -> &'static str {
        match self {
            Self::Explore => "Explore",
            Self::Build => "Build",
            Self::Review => "Review",
            Self::Fix => "Fix",
        }
    }

    fn suggestions(self) -> &'static [&'static str] {
        match self {
            Self::Explore => &[
                "Explain this codebase",
                "Find the main entry points",
                "Trace a request through the app",
                "Identify the risky areas",
            ],
            Self::Build => &[
                "Build a feature",
                "Build UI changes",
                "Build a prototype",
                "Build an internal tool",
            ],
            Self::Review => &[
                "Review the current changes",
                "Review a pull request",
                "Find potential regressions",
                "Suggest cleanup opportunities",
            ],
            Self::Fix => &[
                "Fix a bug",
                "Fix failing tests",
                "Fix a build failure",
                "Fix a performance issue",
            ],
        }
    }

    fn icon(self) -> Icon {
        match self {
            Self::Explore => Icon::Telescope,
            Self::Build => Icon::Hammer,
            Self::Review => Icon::RefreshCode,
            Self::Fix => Icon::Bug,
        }
    }

    fn icon_color(self) -> u32 {
        match self {
            Self::Explore => color::accent(),
            Self::Build => color::purple(),
            Self::Review => color::success(),
            Self::Fix => color::danger(),
        }
    }
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn conversation_pane(
    messages: &[TimelineBlock],
    streaming_assistant: Option<&TimelineBlock>,
    stream_status: &str,
    starter_context: &str,
    starter_category: Option<StarterCategory>,
    cx: &mut Context<crate::WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let mut transcript = div()
        .w_full()
        .max_w(px(layout::CONTENT_MAX_WIDTH))
        .mx_auto()
        .px_6()
        .pt_6()
        .pb_6()
        .flex()
        .flex_col();
    let render_block = |block: &TimelineBlock| -> gpui::AnyElement {
        let (role, is_user, is_assistant) = match block.kind {
            TimelineKind::User => ("user", true, false),
            TimelineKind::Assistant => ("assistant", false, true),
            TimelineKind::Tool => ("tool", false, false),
            TimelineKind::Approval => ("approval", false, false),
            TimelineKind::Receipt => ("receipt", false, false),
            TimelineKind::System => ("system", false, false),
        };
        let message_id = stable_element_id("message-block", &block.block_id);
        if is_user {
            div()
                .id(message_id.clone())
                .w_full()
                .mb_5()
                .flex()
                .justify_end()
                .child(
                    div()
                        .max_w(px(layout::MESSAGE_MAX_WIDTH))
                        .rounded_2xl()
                        .bg(rgb(color::surface()))
                        .px_4()
                        .py_3()
                        .text_size(px(crate::light_theme::typography::BODY))
                        .child(block.content.clone()),
                )
                .into_any_element()
        } else if is_assistant {
            div()
                .id(message_id.clone())
                .w_full()
                .mb_5()
                .child(
                    div()
                        .mb_2()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::text_secondary()))
                        .child(if block.streaming {
                            "Codinal · working"
                        } else {
                            "Codinal"
                        }),
                )
                .child(
                    div()
                        .text_size(px(crate::light_theme::typography::BODY))
                        .text_color(rgb(color::text_primary()))
                        .child(block.content.clone()),
                )
                .into_any_element()
        } else if block.kind == TimelineKind::Receipt {
            div()
                .id(message_id)
                .w_full()
                .mb_5()
                .rounded_lg()
                .border_1()
                .border_color(rgb(color::accent()))
                .bg(rgb(color::accent_muted()))
                .p_3()
                .child(
                    div()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::accent()))
                        .child("Terminal receipt"),
                )
                .child(
                    div()
                        .mt_2()
                        .text_size(px(crate::light_theme::typography::BODY))
                        .text_color(rgb(color::text_primary()))
                        .child(block.content.clone()),
                )
                .into_any_element()
        } else {
            div()
                .id(message_id)
                .w_full()
                .mb_5()
                .rounded_lg()
                .border_1()
                .border_color(rgb(color::border()))
                .bg(rgb(color::sidebar()))
                .p_3()
                .child(
                    div()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::text_secondary()))
                        .child(role),
                )
                .child(
                    div()
                        .mt_2()
                        .text_size(px(crate::light_theme::typography::BODY))
                        .child(block.content.clone()),
                )
                .into_any_element()
        }
    };
    for block in messages.iter().take(50) {
        transcript = transcript.child(render_block(block));
    }
    if let Some(block) = streaming_assistant.filter(|block| !block.content.is_empty()) {
        transcript = transcript.child(render_block(block));
    }
    let has_content = !messages.is_empty()
        || streaming_assistant
            .map(|block| !block.content.is_empty())
            .unwrap_or(false);
    let body: gpui::AnyElement = if !has_content {
        let categories = [
            StarterCategory::Explore,
            StarterCategory::Build,
            StarterCategory::Review,
            StarterCategory::Fix,
        ];
        let mut starter_body = div()
            .id("starter-workspace")
            .w(px(820.0))
            .max_w_full()
            .px_4()
            .child(
                div()
                    .text_size(px(layout::TYPE_SECTION))
                    .font_weight(FontWeight::SEMIBOLD)
                    .text_color(rgb(color::text_primary()))
                    .child(format!("What should we build in {starter_context}?")),
            );
        if let Some(category) = starter_category {
            let selected_category = category;
            let mut suggestions = div().id("starter-suggestions").mt_5().flex().flex_col();
            for suggestion in category.suggestions() {
                let suggestion = (*suggestion).to_owned();
                suggestions = suggestions.child(
                    div()
                        .id(stable_element_id("starter-suggestion", &suggestion))
                        .py_2()
                        .flex()
                        .items_center()
                        .text_size(px(crate::light_theme::typography::BODY))
                        .text_color(rgb(color::text_secondary()))
                        .role(gpui::Role::Button)
                        .aria_label(format!("Use suggestion {suggestion}"))
                        .tab_index(0)
                        .child(icon(category.icon(), category.icon_color()))
                        .child(div().ml_3().child(suggestion.clone()))
                        .on_click(cx.listener(move |this, _, window, cx| {
                            this.apply_starter_text(&suggestion, window, cx);
                        })),
                );
            }
            starter_body = starter_body
                .child(
                    div()
                        .mt_2()
                        .text_size(px(crate::light_theme::typography::BODY))
                        .text_color(rgb(color::text_secondary()))
                        .child(format!(
                            "{} ideas to get started",
                            selected_category.title()
                        )),
                )
                .child(suggestions);
        } else {
            let mut cards = div().id("starter-cards").mt_6().flex().gap_3();
            for category in categories {
                cards = cards.child(
                    div()
                        .id(stable_element_id("starter-card", category.title()))
                        .w(px(190.0))
                        .min_h(px(112.0))
                        .p_3()
                        .flex()
                        .flex_col()
                        .justify_between()
                        .rounded_xl()
                        .border_1()
                        .border_color(rgb(color::border()))
                        .bg(rgb(color::elevated()))
                        .role(gpui::Role::Button)
                        .aria_label(format!("Start {}", category.title()))
                        .tab_index(0)
                        .focus_visible(|style| style.border_color(rgb(color::accent())))
                        .child(
                            div()
                                .text_size(px(layout::TYPE_SECTION))
                                .text_color(rgb(color::accent()))
                                .child(icon(category.icon(), category.icon_color())),
                        )
                        .child(
                            div()
                                .mt_4()
                                .text_size(px(layout::TYPE_CONTROL))
                                .text_color(rgb(color::text_primary()))
                                .child(category.title()),
                        )
                        .on_click(cx.listener(move |this, _, window, cx| {
                            this.select_starter_category(category, window, cx);
                        })),
                );
            }
            starter_body = starter_body.child(cards);
        }
        div()
            .flex_1()
            .flex()
            .items_center()
            .justify_center()
            .child(starter_body)
            .into_any_element()
    } else {
        transcript
            .id("conversation-transcript")
            .flex_1()
            .min_h(px(0.0))
            .overflow_y_scroll()
            .into_any_element()
    };
    div()
        .id("conversation-pane")
        .flex_1()
        .min_h(px(0.0))
        .min_w(px(220.0))
        .flex()
        .flex_col()
        .bg(rgb(color::canvas()))
        .child(
            div()
                .w_full()
                .max_w(px(layout::CONTENT_MAX_WIDTH))
                .mx_auto()
                .px_6()
                .pt_3()
                .child(
                    div()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::text_tertiary()))
                        .child(stream_status.to_owned()),
                ),
        )
        .child(body)
}
