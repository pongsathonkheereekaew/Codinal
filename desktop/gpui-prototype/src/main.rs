//! PROTOTYPE — delete or absorb after G2 resolves.
//!
//! Run:
//! `cargo build --manifest-path crates/codinal-runtime/Cargo.toml`
//! `CODINAL_NATIVE_RUNTIME=crates/codinal-runtime/target/debug/codinal-runtime CODINAL_DATA_DIR=/absolute/codinal/data cargo run --manifest-path desktop/gpui-prototype/Cargo.toml`
//! This development shell boots the authenticated Rust runtime on an isolated
//! snapshot, while its UI remains an opt-in prototype.

use codinal_control_plane_client::{
    ApprovalConfirmation, ApprovalOutcome, ControlPlaneClient, PendingApproval,
};
use codinal_native_host::{
    free_loopback_port, launch_shadow_runtime_with_bootstrap, mint_session_token,
    secrets::{encode_secret_bootstrap, PlatformSecretVault},
    ShadowRuntime,
};
use gpui::{
    div, px, rgb, size, App, AppContext, Bounds, Context, InteractiveElement, ParentElement,
    PromptLevel, Render, StatefulInteractiveElement, Styled, Window, WindowBounds, WindowOptions,
};
use std::io;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use zeroize::Zeroizing;

static NEXT_SHADOW: AtomicU64 = AtomicU64::new(0);

struct WorkspacePrototype {
    _runtime: ShadowRuntime,
    client: Arc<ControlPlaneClient>,
    approval_session_id: Option<String>,
    approval_id: Option<String>,
    session_count: usize,
    session_labels: String,
    conversation: String,
    approvals: String,
    approval_prompt_detail: Option<String>,
    approval_review_status: String,
    provider_settings: String,
}

impl WorkspacePrototype {
    fn show_approval_prompt(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        let Some(detail) = self.approval_prompt_detail.as_deref() else {
            return;
        };
        let response = window.prompt(
            PromptLevel::Warning,
            "Review pending approval",
            Some(detail),
            &["Cancel", "Deny request"],
            cx,
        );
        let client = Arc::clone(&self.client);
        let session_id = self.approval_session_id.clone();
        let approval_id = self.approval_id.clone();
        cx.spawn(async move |this, cx| {
            let choice = response.await.unwrap_or(0);
            let (status, pending) = if choice == 1 {
                match (session_id, approval_id) {
                    (Some(session_id), Some(approval_id)) => {
                        let submission = (|| {
                            let mut confirmation = ApprovalConfirmation::new(
                                &session_id,
                                &approval_id,
                                ApprovalOutcome::Deny,
                            )?;
                            confirmation.confirm();
                            client.resolve_confirmation(&confirmation)
                        })();
                        match submission {
                            Ok(true) => match client.pending_approvals(&session_id) {
                                Ok(pending) => {
                                    ("Request denied — live state reloaded", Some(pending))
                                }
                                Err(_) => (
                                    "Request denied — reload failed; reopen the pane to refresh",
                                    Some(Vec::new()),
                                ),
                            },
                            Ok(false) | Err(_) => ("Decision failed — live state unchanged", None),
                        }
                    }
                    _ => ("Decision cancelled — approval is no longer pending", None),
                }
            } else {
                ("Approval review cancelled — no action sent", None)
            };
            let _ = this.update(cx, |this, cx| {
                this.approval_review_status = status.to_owned();
                if let Some(pending) = pending {
                    this.set_pending_approvals(pending);
                }
                cx.notify();
            });
        })
        .detach();
    }

    fn set_pending_approvals(&mut self, pending: Vec<PendingApproval>) {
        self.approvals = format_pending_approvals(&pending);
        self.approval_id = pending.first().map(|approval| approval.approval_id.clone());
        self.approval_prompt_detail = pending.first().map(format_approval_detail);
    }
}

fn format_pending_approvals(pending: &[PendingApproval]) -> String {
    if pending.is_empty() {
        "No pending approvals".to_owned()
    } else {
        pending
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
    }
}

fn format_approval_detail(approval: &PendingApproval) -> String {
    let arguments = serde_json::to_string_pretty(&approval.arguments)
        .unwrap_or_else(|_| "[invalid arguments]".to_owned());
    format!(
        "Risk: {}\nTool: {}\nReason: {}\nArguments:\n{}",
        approval.risk, approval.tool_name, approval.reason, arguments
    )
}

impl Render for WorkspacePrototype {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl gpui::IntoElement {
        let runtime = format!(
            "authenticated Rust runtime ready · {} sessions",
            self.session_count
        );
        div()
            .size_full()
            .flex()
            .flex_col()
            .bg(rgb(0x101214))
            .text_color(rgb(0xd8dee9))
            .child(header(runtime))
            .child(
                div()
                    .flex()
                    .flex_1()
                    .child(session_pane(&self.session_labels))
                    .child(conversation_pane(&self.conversation))
                    .child(approval_pane(
                        &self.approvals,
                        self.approval_prompt_detail.is_some(),
                        &self.approval_review_status,
                        cx,
                    )),
            )
            .child(
                div()
                    .h(px(180.0))
                    .border_t_1()
                    .border_color(rgb(0x30363d))
                    .p_3()
                    .child(div().text_lg().child("Provider settings"))
                    .child(
                        div()
                            .mt_2()
                            .text_sm()
                            .text_color(rgb(0x8b949e))
                            .child(self.provider_settings.clone()),
                    ),
            )
    }
}

fn header(runtime: String) -> impl gpui::IntoElement {
    div()
        .h(px(44.0))
        .flex()
        .items_center()
        .justify_between()
        .px_3()
        .border_b_1()
        .border_color(rgb(0x30363d))
        .child(format!("Codinal GPUI prototype — {runtime}"))
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
    review_status: &str,
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
        )
        .child(
            div()
                .mt_2()
                .text_sm()
                .text_color(rgb(0x8b949e))
                .child(review_status.to_owned()),
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

fn native_runtime_binary() -> io::Result<PathBuf> {
    std::env::var_os("CODINAL_NATIVE_RUNTIME")
        .map(PathBuf::from)
        .ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::NotFound,
                "CODINAL_NATIVE_RUNTIME is required for the GPUI development shell",
            )
        })
}

fn start_native_runtime() -> io::Result<(ControlPlaneClient, ShadowRuntime)> {
    let data_dir = development_data_dir()?;
    let token = mint_session_token()?;
    let secret_sync_token = Zeroizing::new(mint_session_token()?);
    let secret_bootstrap = encode_secret_bootstrap(&PlatformSecretVault, &secret_sync_token)?;
    let port = free_loopback_port()?;
    let snapshot = std::env::temp_dir().join(format!(
        "codinal-gpui-shadow-{}-{}",
        std::process::id(),
        NEXT_SHADOW.fetch_add(1, Ordering::Relaxed)
    ));
    let runtime = launch_shadow_runtime_with_bootstrap(
        native_runtime_binary()?,
        &data_dir,
        &snapshot,
        port,
        token.clone(),
        secret_bootstrap,
    )?;
    let client = ControlPlaneClient::new(port, &token)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidInput, error.to_string()))?;
    Ok((client, runtime))
}

fn main() -> io::Result<()> {
    let (client, runtime) = start_native_runtime()?;
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
    let client = Arc::new(client);
    let approval_session_id = sessions.first().map(|session| session.session_id.clone());
    let pending = match approval_session_id.as_deref() {
        Some(session_id) => client.pending_approvals(session_id)?,
        None => Vec::new(),
    };
    let approvals = format_pending_approvals(&pending);
    let approval_id = pending.first().map(|approval| approval.approval_id.clone());
    let approval_prompt_detail = pending.first().map(format_approval_detail);
    let vault = PlatformSecretVault;
    let standard_status = codinal_native_host::secrets::provider_secret_status(&vault)?;
    let custom_status = codinal_native_host::secrets::list_custom_providers(&vault)?;
    let mut provider_settings = standard_status
        .iter()
        .map(|status| {
            format!(
                "{}: {}",
                status.provider,
                if status.configured {
                    "configured"
                } else {
                    "not configured"
                }
            )
        })
        .collect::<Vec<_>>();
    provider_settings.extend(custom_status.iter().map(|provider| {
        format!(
            "custom:{}: configured · {}",
            provider.slug, provider.base_url
        )
    }));
    let provider_settings = provider_settings.join(" · ");
    gpui_platform::application().run(move |cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(1280.0), px(800.0)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |_, cx| {
                cx.new(|_| WorkspacePrototype {
                    _runtime: runtime,
                    client,
                    approval_session_id,
                    approval_id,
                    session_count,
                    session_labels,
                    conversation,
                    approvals,
                    approval_prompt_detail,
                    approval_review_status: "No approval action sent".to_owned(),
                    provider_settings,
                })
            },
        )
        .expect("open GPUI prototype window");
        cx.activate(true);
    });
    Ok(())
}
