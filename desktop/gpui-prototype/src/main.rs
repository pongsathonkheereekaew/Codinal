//! PROTOTYPE — delete or absorb after G2 resolves.
//!
//! Run: `cargo run --manifest-path desktop/gpui-prototype/Cargo.toml`
//! This development shell boots the same authenticated Python sidecar as the
//! Tauri shell, while its UI remains an opt-in prototype.

use codinal_control_plane_client::ControlPlaneClient;
use codinal_native_host::{
    development_runtime_root, free_loopback_port, mint_session_token, runtime_layout,
    secrets::{encode_secret_bootstrap, PlatformSecretVault},
    validate_runtime_layout, SidecarLaunch,
};
use gpui::{
    div, px, rgb, size, App, AppContext, Bounds, Context, InteractiveElement, ParentElement,
    PromptLevel, Render, StatefulInteractiveElement, Styled, Window, WindowBounds, WindowOptions,
};
use std::io;
use std::path::PathBuf;
use std::process::Child;
use std::thread;
use std::time::{Duration, Instant};

struct SidecarProcess(Child);

impl Drop for SidecarProcess {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

struct WorkspacePrototype {
    _sidecar: SidecarProcess,
    session_count: usize,
    session_labels: String,
    conversation: String,
    approvals: String,
    approval_prompt_detail: Option<String>,
}

impl WorkspacePrototype {
    fn show_approval_prompt(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        let Some(detail) = self.approval_prompt_detail.as_deref() else {
            return;
        };
        let _ = window.prompt(
            PromptLevel::Warning,
            "Review pending approval",
            Some(detail),
            &["Cancel", "Review only"],
            cx,
        );
    }
}

impl Render for WorkspacePrototype {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl gpui::IntoElement {
        let sidecar = format!(
            "authenticated sidecar ready · {} sessions",
            self.session_count
        );
        div()
            .size_full()
            .flex()
            .flex_col()
            .bg(rgb(0x101214))
            .text_color(rgb(0xd8dee9))
            .child(header(sidecar))
            .child(
                div()
                    .flex()
                    .flex_1()
                    .child(session_pane(&self.session_labels))
                    .child(conversation_pane(&self.conversation))
                    .child(approval_pane(
                        &self.approvals,
                        self.approval_prompt_detail.is_some(),
                        cx,
                    )),
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

fn header(sidecar: String) -> impl gpui::IntoElement {
    div()
        .h(px(44.0))
        .flex()
        .items_center()
        .justify_between()
        .px_3()
        .border_b_1()
        .border_color(rgb(0x30363d))
        .child(format!("Codinal GPUI prototype — {sidecar}"))
        .child("⌘K command palette · ⌘. cancel")
}

fn session_pane(labels: &str) -> impl gpui::IntoElement {
    div()
        .flex_1()
        .min_w(px(220.0))
        .border_r_1()
        .border_color(rgb(0x30363d))
        .p_3()
        .child(div().text_lg().child("Sessions"))
        .child(
            div()
                .mt_2()
                .text_sm()
                .text_color(rgb(0x8b949e))
                .child(labels.to_owned()),
        )
}

fn conversation_pane(messages: &str) -> impl gpui::IntoElement {
    div()
        .flex_1()
        .min_w(px(220.0))
        .border_r_1()
        .border_color(rgb(0x30363d))
        .p_3()
        .child(div().text_lg().child("Conversation"))
        .child(
            div()
                .mt_2()
                .text_sm()
                .text_color(rgb(0x8b949e))
                .child(messages.to_owned()),
        )
}

fn approval_pane(
    approvals: &str,
    has_pending_approval: bool,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let pane = div()
        .flex_1()
        .min_w(px(220.0))
        .border_r_1()
        .border_color(rgb(0x30363d))
        .p_3()
        .child(div().text_lg().child("Approvals"))
        .child(
            div()
                .mt_2()
                .text_sm()
                .text_color(rgb(0x8b949e))
                .child(approvals.to_owned()),
        );
    if has_pending_approval {
        pane.child(
            div()
                .id("review-pending-approval")
                .mt_3()
                .px_2()
                .py_1()
                .bg(rgb(0x30363d))
                .child("Review approval…")
                .on_click(cx.listener(|this, _, window, cx| {
                    this.show_approval_prompt(window, cx);
                })),
        )
    } else {
        pane
    }
}

fn development_data_dir() -> io::Result<PathBuf> {
    std::env::var_os("CODINAL_DATA_DIR")
        .map(PathBuf::from)
        .ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::NotFound,
                "CODINAL_DATA_DIR is required for the GPUI development shell",
            )
        })
}

fn start_sidecar() -> io::Result<(ControlPlaneClient, SidecarProcess)> {
    let layout = runtime_layout(&development_runtime_root(), true);
    validate_runtime_layout(&layout)?;
    let token = mint_session_token()?;
    let secret_sync_token = mint_session_token()?;
    let port = free_loopback_port()?;
    let secret_bootstrap = encode_secret_bootstrap(&PlatformSecretVault, &secret_sync_token)?;
    let launch = SidecarLaunch::new(
        layout.python,
        layout.runtime_root,
        development_data_dir()?,
        port,
        token.clone(),
    )?;
    let sidecar = SidecarProcess(launch.spawn_with_bootstrap(secret_bootstrap)?);
    let client = ControlPlaneClient::new(port, &token)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidInput, error.to_string()))?;
    let deadline = Instant::now() + Duration::from_secs(3);
    loop {
        match client.get_json("sessions") {
            Ok(_) => return Ok((client, sidecar)),
            Err(error) if Instant::now() >= deadline => return Err(error),
            Err(_) => thread::sleep(Duration::from_millis(50)),
        }
    }
}

fn main() -> io::Result<()> {
    let (client, sidecar) = start_sidecar()?;
    let sessions = client.list_sessions()?;
    let session_count = sessions.len();
    let session_labels = if sessions.is_empty() {
        "No sessions yet".to_owned()
    } else {
        sessions
            .iter()
            .take(10)
            .map(|session| format!("{} · {} messages", session.title, session.messages))
            .collect::<Vec<_>>()
            .join("\n")
    };
    let conversation = match sessions.first() {
        Some(session) => client
            .session_messages(&session.session_id)?
            .iter()
            .take(50)
            .map(|message| format!("{}: {}", message.role, message.text))
            .collect::<Vec<_>>()
            .join("\n\n"),
        None => "Select a session to view its conversation".to_owned(),
    };
    let (approvals, approval_prompt_detail) = match sessions.first() {
        Some(session) => {
            let approvals = client.pending_approvals(&session.session_id)?;
            if approvals.is_empty() {
                ("No pending approvals".to_owned(), None)
            } else {
                let rendered = approvals
                    .iter()
                    .map(|approval| {
                        let command = approval
                            .command
                            .as_deref()
                            .map(|value| format!("\n{value}"))
                            .unwrap_or_default();
                        format!(
                            "{} · {}\n{}{}\nRead-only until native confirmation UI ships",
                            approval.risk, approval.tool_name, approval.reason, command
                        )
                    })
                    .collect::<Vec<_>>()
                    .join("\n\n");
                let first = &approvals[0];
                (
                    rendered,
                    Some(format!(
                        "Risk: {}\nTool: {}\nReason: {}\nCommand: {}\n\nNo action is sent from this review prompt.",
                        first.risk,
                        first.tool_name,
                        first.reason,
                        first.command.as_deref().unwrap_or("(none)"),
                    )),
                )
            }
        }
        None => ("No pending approvals".to_owned(), None),
    };
    gpui_platform::application().run(move |cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(1280.0), px(800.0)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |_, cx| {
                cx.new(|_| WorkspacePrototype {
                    _sidecar: sidecar,
                    session_count,
                    session_labels,
                    conversation,
                    approvals,
                    approval_prompt_detail,
                })
            },
        )
        .expect("open GPUI prototype window");
        cx.activate(true);
    });
    Ok(())
}
