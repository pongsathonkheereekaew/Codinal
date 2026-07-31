//! PROTOTYPE — delete or absorb after G2 resolves.
//!
//! Run: `cargo run --manifest-path desktop/gpui-prototype/Cargo.toml`
//! This intentionally has no persistence or sidecar access. It tests whether
//! GPUI's layout model can express Codinal's workspace panes before any
//! production shell work begins.

use gpui::{
    div, px, rgb, size, App, AppContext, Bounds, Context, ParentElement, Render, Styled, Window,
    WindowBounds, WindowOptions,
};

struct WorkspacePrototype;

impl Render for WorkspacePrototype {
    fn render(&mut self, _window: &mut Window, _cx: &mut Context<Self>) -> impl gpui::IntoElement {
        div()
            .size_full()
            .flex()
            .flex_col()
            .bg(rgb(0x101214))
            .text_color(rgb(0xd8dee9))
            .child(header())
            .child(
                div()
                    .flex()
                    .flex_1()
                    .child(pane("Files", "10,000-file virtual tree boundary"))
                    .child(pane("Conversation", "streamed assistant events"))
                    .child(pane("Review", "diff and explicit apply evidence")),
            )
            .child(
                div()
                    .h(px(180.0))
                    .border_t_1()
                    .border_color(rgb(0x30363d))
                    .p_3()
                    .child("Terminal — 10,000-line scroll boundary"),
            )
    }
}

fn header() -> impl gpui::IntoElement {
    div()
        .h(px(44.0))
        .flex()
        .items_center()
        .justify_between()
        .px_3()
        .border_b_1()
        .border_color(rgb(0x30363d))
        .child("Codinal GPUI prototype — development only")
        .child("⌘K command palette · ⌘. cancel")
}

fn pane(title: &'static str, state: &'static str) -> impl gpui::IntoElement {
    div()
        .flex_1()
        .min_w(px(220.0))
        .border_r_1()
        .border_color(rgb(0x30363d))
        .p_3()
        .child(div().text_lg().child(title))
        .child(div().mt_2().text_sm().text_color(rgb(0x8b949e)).child(state))
}

fn main() {
    gpui_platform::application().run(|cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(1280.0), px(800.0)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |_, cx| cx.new(|_| WorkspacePrototype),
        )
        .expect("open GPUI prototype window");
        cx.activate(true);
    });
}
