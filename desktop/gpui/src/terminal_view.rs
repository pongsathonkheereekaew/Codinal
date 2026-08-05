//! GPUI presentation for the already-owned native PTY.
//!
//! This module renders terminal state and routes focus/input callbacks back to
//! the composition root; it does not create or own a terminal process.

use crate::light_theme::{color, layout};
use crate::{
    disabled_reason_label, should_request_terminal_resize, terminal_grid_for_bounds,
    terminal_should_handle_key, InputTarget, TerminalState, WorkspacePrototype,
};
use gpui::{
    canvas, div, px, rgb, Context, ElementInputHandler, FocusHandle, FontWeight,
    InteractiveElement, ParentElement, StatefulInteractiveElement, Styled,
};

#[allow(clippy::too_many_arguments)]
pub(crate) fn terminal_pane(
    output: &str,
    status: &str,
    state: TerminalState,
    terminal_kept_alive: bool,
    workspace: &str,
    actions_enabled: bool,
    disabled_reason: &str,
    focus: &FocusHandle,
    entity: gpui::Entity<WorkspacePrototype>,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let input_focus = focus.clone();
    let key_focus = focus.clone();
    let mut actions = div().flex().flex_row().flex_wrap();
    #[cfg(target_os = "macos")]
    {
        if !actions_enabled {
            actions = actions.child(
                div()
                    .id("terminal-disabled")
                    .px_2()
                    .py_1()
                    .rounded_md()
                    .bg(rgb(color::surface()))
                    .text_color(rgb(color::text_secondary()))
                    .child(format!(
                        "Terminal unavailable · {}",
                        disabled_reason_label(disabled_reason)
                    )),
            );
        } else if state.can_open() {
            actions = actions
                .child(
                    div()
                        .id("terminal-workspace")
                        .mr_2()
                        .px_2()
                        .py_1()
                        .rounded_md()
                        .bg(rgb(color::surface()))
                        .role(gpui::Role::Button)
                        .aria_label("Choose terminal workspace")
                        .tab_index(0)
                        .border_1()
                        .border_color(rgb(color::border()))
                        .focus_visible(|style| style.border_color(rgb(color::accent())))
                        .child("Choose workspace")
                        .on_click(cx.listener(|this, _, _, cx| {
                            this.choose_workspace(cx);
                        })),
                )
                .child(
                    div()
                        .id("terminal-open")
                        .px_2()
                        .py_1()
                        .rounded_md()
                        .bg(rgb(color::surface()))
                        .role(gpui::Role::Button)
                        .aria_label("Open native terminal")
                        .tab_index(0)
                        .border_1()
                        .border_color(rgb(color::border()))
                        .focus_visible(|style| style.border_color(rgb(color::accent())))
                        .child("Open terminal")
                        .on_click(cx.listener(|this, _, _, cx| {
                            this.open_terminal(cx);
                        })),
                );
        } else if state == TerminalState::Running {
            actions = actions
                .child(
                    div()
                        .id("terminal-interrupt")
                        .mr_2()
                        .px_2()
                        .py_1()
                        .rounded_md()
                        .bg(rgb(color::surface()))
                        .role(gpui::Role::Button)
                        .aria_label("Send Control-C to terminal")
                        .tab_index(0)
                        .border_1()
                        .border_color(rgb(color::border()))
                        .focus_visible(|style| style.border_color(rgb(color::accent())))
                        .child("Ctrl-C")
                        .on_click(cx.listener(|this, _, _, cx| {
                            this.send_terminal_interrupt(cx);
                        })),
                )
                .child(
                    div()
                        .id("terminal-kill")
                        .px_2()
                        .py_1()
                        .rounded_md()
                        .bg(rgb(color::danger_muted()))
                        .text_color(rgb(color::danger()))
                        .role(gpui::Role::Button)
                        .aria_label("Stop native terminal")
                        .tab_index(0)
                        .border_1()
                        .border_color(rgb(color::danger_muted()))
                        .focus_visible(|style| style.border_color(rgb(color::accent())))
                        .child("Stop terminal")
                        .on_click(cx.listener(|this, _, _, cx| {
                            this.kill_terminal(cx);
                        })),
                );
        }
    }
    div()
        .id("native-terminal-pane")
        .role(gpui::Role::Terminal)
        .aria_label("Interactive native terminal")
        .aria_description(status.to_owned())
        .relative()
        .tab_group()
        .track_focus(focus)
        .on_click(cx.listener(|this, _, window, cx| {
            this.input_target = InputTarget::Terminal;
            this.terminal_focus.focus(window, cx);
        }))
        .on_key_down(cx.listener(move |this, event, window, cx| {
            #[cfg(target_os = "macos")]
            if terminal_should_handle_key(key_focus.is_focused(window), event) {
                this.send_terminal_key(event, cx);
            }
        }))
        .size_full()
        .min_h(px(0.0))
        .flex()
        .flex_col()
        .overflow_hidden()
        .focus_visible(|style| style.border_color(rgb(color::accent())))
        .bg(rgb(color::sidebar()))
        .p_3()
        .child(
            div()
                .flex()
                .items_center()
                .justify_between()
                .text_size(px(layout::TYPE_SECTION))
                .font_weight(FontWeight::SEMIBOLD)
                .child(if terminal_kept_alive {
                    "Native terminal · kept alive when hidden"
                } else {
                    "Native terminal"
                }),
        )
        .child(
            div()
                .mt_2()
                .text_size(px(layout::TYPE_CONTROL))
                .child(status.to_owned()),
        )
        .child(
            div()
                .mt_1()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(color::text_secondary()))
                .child(format!("Workspace: {workspace}")),
        )
        .child(actions)
        .child(
            div()
                .id("native-terminal-output")
                .mt_2()
                .flex_1()
                .min_h(px(0.0))
                .overflow_y_scroll()
                .font_family("SF Mono")
                .text_size(px(crate::light_theme::typography::CODE))
                .text_color(rgb(color::text_primary()))
                .child(output.to_owned()),
        )
        .child(
            canvas(
                |bounds, _, _| bounds,
                move |bounds, _, window, cx| {
                    window.handle_input(
                        &input_focus,
                        ElementInputHandler::new(bounds, entity.clone()),
                        cx,
                    );
                    let (cols, rows) = terminal_grid_for_bounds(bounds);
                    entity.update(cx, |this, cx| {
                        if should_request_terminal_resize(
                            this.terminal_state,
                            this.terminal_parser.screen().size(),
                            this.terminal_resize_pending,
                            this.terminal_resize_failed,
                            (cols, rows),
                        ) {
                            this.resize_terminal(cols, rows, cx);
                        }
                    });
                },
            )
            .absolute()
            .size_full(),
        )
}
