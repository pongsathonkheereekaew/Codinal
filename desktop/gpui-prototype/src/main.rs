//! PROTOTYPE — delete or absorb after G2 resolves.
//!
//! Run:
//! `cargo build --manifest-path crates/codinal-runtime/Cargo.toml`
//! `CODINAL_NATIVE_RUNTIME=crates/codinal-runtime/target/debug/codinal-runtime CODINAL_DATA_DIR=/absolute/codinal/data cargo run --manifest-path desktop/gpui-prototype/Cargo.toml`
//! This development shell boots the authenticated Rust runtime on an isolated
//! snapshot, while its UI remains an opt-in prototype.

#[cfg(target_os = "macos")]
mod secure_prompt;

#[cfg(not(target_os = "macos"))]
mod secure_prompt {
    use std::io;
    use zeroize::Zeroizing;

    pub fn prompt_api_key(_provider: &str) -> io::Result<Option<Zeroizing<String>>> {
        Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "secure credential editing is currently available only on macOS",
        ))
    }

    pub fn prompt_text(
        _title: &str,
        _detail: &str,
        _initial_value: &str,
    ) -> io::Result<Option<String>> {
        Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "native provider editing is currently available only on macOS",
        ))
    }

    pub fn prompt_boolean(_title: &str, _detail: &str) -> io::Result<Option<bool>> {
        Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "native provider editing is currently available only on macOS",
        ))
    }
}

use codinal_control_plane_client::{
    ApprovalConfirmation, ApprovalOutcome, ControlPlaneClient, PendingApproval,
};
use codinal_native_host::{
    free_loopback_port, launch_shadow_runtime_with_bootstrap, mint_session_token,
    secrets::{
        encode_secret_bootstrap, CustomProviderRecord, PlatformSecretVault, ProviderSecretStatus,
        ProviderSettingsController,
    },
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
    provider_settings_controller: Arc<ProviderSettingsController>,
    provider_delete_targets: Vec<ProviderDeleteTarget>,
    provider_edit_targets: Vec<String>,
    custom_provider_edit_targets: Vec<CustomProviderEditTarget>,
    provider_operation_in_flight: bool,
}

#[derive(Clone)]
enum ProviderDeleteTarget {
    Standard(String),
    Custom(String),
}

#[derive(Clone)]
struct CustomProviderEditTarget {
    slug: String,
    base_url: String,
    failover_eligible: bool,
}

enum ProviderDeleteOutcome {
    Refreshed(Vec<ProviderSecretStatus>, Vec<CustomProviderRecord>),
    DeletedRefreshFailed,
    SyncIndeterminate,
    DeleteFailed,
}

enum ProviderEditOutcome {
    Refreshed(Vec<ProviderSecretStatus>, Vec<CustomProviderRecord>),
    SavedRefreshFailed,
    SyncIndeterminate,
    SaveFailed,
}

fn begin_provider_operation(in_flight: &mut bool) -> bool {
    if *in_flight {
        false
    } else {
        *in_flight = true;
        true
    }
}

fn classify_provider_edit_result(
    saved: io::Result<()>,
    refresh: impl FnOnce() -> io::Result<(Vec<ProviderSecretStatus>, Vec<CustomProviderRecord>)>,
) -> ProviderEditOutcome {
    match saved {
        Ok(()) => match refresh() {
            Ok((standard, custom)) => ProviderEditOutcome::Refreshed(standard, custom),
            Err(_) => ProviderEditOutcome::SavedRefreshFailed,
        },
        Err(error) if error.kind() == io::ErrorKind::ConnectionAborted => {
            ProviderEditOutcome::SyncIndeterminate
        }
        Err(_) => ProviderEditOutcome::SaveFailed,
    }
}

fn classify_provider_delete_result(
    deleted: io::Result<()>,
    refresh: impl FnOnce() -> io::Result<(Vec<ProviderSecretStatus>, Vec<CustomProviderRecord>)>,
) -> ProviderDeleteOutcome {
    match deleted {
        Ok(()) => match refresh() {
            Ok((standard, custom)) => ProviderDeleteOutcome::Refreshed(standard, custom),
            Err(_) => ProviderDeleteOutcome::DeletedRefreshFailed,
        },
        Err(error) if error.kind() == io::ErrorKind::ConnectionAborted => {
            ProviderDeleteOutcome::SyncIndeterminate
        }
        Err(_) => ProviderDeleteOutcome::DeleteFailed,
    }
}

fn custom_provider_edit_targets(custom: &[CustomProviderRecord]) -> Vec<CustomProviderEditTarget> {
    custom
        .iter()
        .map(|provider| CustomProviderEditTarget {
            slug: provider.slug.clone(),
            base_url: provider.base_url.clone(),
            failover_eligible: provider.failover_eligible,
        })
        .collect()
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

    fn show_provider_delete_prompt(
        &mut self,
        target: ProviderDeleteTarget,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        if !begin_provider_operation(&mut self.provider_operation_in_flight) {
            return;
        }
        let label = match &target {
            ProviderDeleteTarget::Standard(provider) => provider.as_str(),
            ProviderDeleteTarget::Custom(slug) => slug.as_str(),
        };
        let detail = format!("Delete the Keychain credential for {label}? This cannot be undone.");
        let response = window.prompt(
            PromptLevel::Critical,
            "Delete provider credential",
            Some(&detail),
            &["Cancel", "Delete"],
            cx,
        );
        let controller = Arc::clone(&self.provider_settings_controller);
        cx.spawn(async move |this, cx| {
            if response.await.unwrap_or(0) != 1 {
                let _ = this.update(cx, |this, cx| {
                    this.provider_operation_in_flight = false;
                    cx.notify();
                });
                return;
            }
            let outcome = cx
                .background_executor()
                .spawn(async move {
                    let deleted = match &target {
                        ProviderDeleteTarget::Standard(provider) => {
                            controller.delete_standard(provider)
                        }
                        ProviderDeleteTarget::Custom(slug) => {
                            controller.delete_custom(slug).map(|_| ())
                        }
                    };
                    classify_provider_delete_result(deleted, || controller.status())
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.provider_operation_in_flight = false;
                match outcome {
                    ProviderDeleteOutcome::Refreshed(standard, custom) => {
                        let (summary, targets) = format_provider_settings(&standard, &custom);
                        this.provider_settings = summary;
                        this.provider_delete_targets = targets;
                        this.custom_provider_edit_targets =
                            custom_provider_edit_targets(&custom);
                    }
                    ProviderDeleteOutcome::DeletedRefreshFailed => {
                        this.provider_settings =
                            "Credential deleted — status reload failed; restart to refresh"
                                .to_owned();
                        this.provider_delete_targets.clear();
                        this.custom_provider_edit_targets.clear();
                    }
                    ProviderDeleteOutcome::SyncIndeterminate => {
                        this.provider_settings = "Credential deleted from Keychain — runtime sync indeterminate; restart required".to_owned();
                        this.provider_delete_targets.clear();
                        this.custom_provider_edit_targets.clear();
                    }
                    ProviderDeleteOutcome::DeleteFailed => {
                        this.provider_settings =
                            "Provider deletion failed — Keychain status requires reload".to_owned();
                        this.provider_delete_targets.clear();
                        this.custom_provider_edit_targets.clear();
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    fn show_provider_edit_prompt(&mut self, provider: String, cx: &mut Context<Self>) {
        if self.provider_operation_in_flight {
            return;
        }
        let base_url = if provider == "omniroute" {
            match secure_prompt::prompt_text(
                "Set OmniRoute base URL",
                "Enter the HTTP(S) OpenAI-compatible endpoint.",
                "",
            ) {
                Ok(Some(value)) => Some(value),
                Ok(None) => return,
                Err(_) => {
                    self.provider_settings = "Native provider URL prompt failed".to_owned();
                    cx.notify();
                    return;
                }
            }
        } else {
            None
        };
        let api_key = match secure_prompt::prompt_api_key(&provider) {
            Ok(Some(api_key)) => api_key,
            Ok(None) => return,
            Err(_) => {
                self.provider_settings = "Secure credential prompt failed".to_owned();
                cx.notify();
                return;
            }
        };
        if !begin_provider_operation(&mut self.provider_operation_in_flight) {
            return;
        }
        cx.notify();
        let controller = Arc::clone(&self.provider_settings_controller);
        cx.spawn(async move |this, cx| {
            let outcome = cx
                .background_executor()
                .spawn(async move {
                    let saved = controller.set_standard(&provider, api_key, base_url.as_deref());
                    classify_provider_edit_result(saved, || controller.status())
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.provider_operation_in_flight = false;
                this.apply_provider_edit_outcome(outcome);
                cx.notify();
            });
        })
        .detach();
    }

    fn show_custom_provider_edit_prompt(
        &mut self,
        existing: Option<CustomProviderEditTarget>,
        cx: &mut Context<Self>,
    ) {
        if self.provider_operation_in_flight {
            return;
        }
        let slug = match existing.as_ref() {
            Some(provider) => provider.slug.clone(),
            None => match secure_prompt::prompt_text(
                "Custom provider ID",
                "Use letters, digits, and internal hyphens (maximum 64 characters).",
                "",
            ) {
                Ok(Some(value)) => value,
                Ok(None) => return,
                Err(_) => {
                    self.provider_settings = "Native custom-provider prompt failed".to_owned();
                    cx.notify();
                    return;
                }
            },
        };
        let initial_url = existing
            .as_ref()
            .map(|provider| provider.base_url.as_str())
            .unwrap_or("");
        let base_url = match secure_prompt::prompt_text(
            "Custom provider base URL",
            "Enter the HTTP(S) OpenAI-compatible endpoint.",
            initial_url,
        ) {
            Ok(Some(value)) => value,
            Ok(None) => return,
            Err(_) => {
                self.provider_settings = "Native custom-provider URL prompt failed".to_owned();
                cx.notify();
                return;
            }
        };
        let api_key = match secure_prompt::prompt_api_key(&format!("custom:{slug}")) {
            Ok(Some(value)) => value,
            Ok(None) => return,
            Err(_) => {
                self.provider_settings = "Secure credential prompt failed".to_owned();
                cx.notify();
                return;
            }
        };
        let current_failover = existing
            .as_ref()
            .is_some_and(|provider| provider.failover_eligible);
        let failover_eligible = match secure_prompt::prompt_boolean(
            "Custom provider failover",
            &format!(
                "This provider is currently {} for automatic failover.",
                if current_failover {
                    "eligible"
                } else {
                    "not eligible"
                }
            ),
        ) {
            Ok(Some(value)) => value,
            Ok(None) => return,
            Err(_) => {
                self.provider_settings = "Native failover prompt failed".to_owned();
                cx.notify();
                return;
            }
        };
        if !begin_provider_operation(&mut self.provider_operation_in_flight) {
            return;
        }
        cx.notify();
        let controller = Arc::clone(&self.provider_settings_controller);
        cx.spawn(async move |this, cx| {
            let outcome = cx
                .background_executor()
                .spawn(async move {
                    let saved = controller.set_custom(&slug, &base_url, api_key, failover_eligible);
                    classify_provider_edit_result(saved, || controller.status())
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.provider_operation_in_flight = false;
                this.apply_provider_edit_outcome(outcome);
                cx.notify();
            });
        })
        .detach();
    }

    fn apply_provider_edit_outcome(&mut self, outcome: ProviderEditOutcome) {
        match outcome {
            ProviderEditOutcome::Refreshed(standard, custom) => {
                let (summary, targets) = format_provider_settings(&standard, &custom);
                self.provider_settings = summary;
                self.provider_delete_targets = targets;
                self.custom_provider_edit_targets = custom_provider_edit_targets(&custom);
            }
            ProviderEditOutcome::SavedRefreshFailed => {
                self.provider_settings =
                    "Credential saved — status reload failed; restart to refresh".to_owned();
            }
            ProviderEditOutcome::SyncIndeterminate => {
                self.provider_settings =
                    "Credential saved to Keychain — runtime sync indeterminate; restart required"
                        .to_owned();
            }
            ProviderEditOutcome::SaveFailed => {
                self.provider_settings = "Credential save failed — live state unchanged".to_owned();
            }
        }
    }
}

fn format_provider_settings(
    standard: &[ProviderSecretStatus],
    custom: &[CustomProviderRecord],
) -> (String, Vec<ProviderDeleteTarget>) {
    let mut rows = standard
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
    rows.extend(custom.iter().map(|provider| {
        format!(
            "custom:{}: configured · {}",
            provider.slug, provider.base_url
        )
    }));
    let mut targets = standard
        .iter()
        .filter(|status| status.configured)
        .map(|status| ProviderDeleteTarget::Standard(status.provider.to_owned()))
        .collect::<Vec<_>>();
    targets.extend(
        custom
            .iter()
            .map(|provider| ProviderDeleteTarget::Custom(provider.slug.clone())),
    );
    (rows.join(" · "), targets)
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
            .child(provider_settings_pane(
                &self.provider_settings,
                &self.provider_delete_targets,
                &self.provider_edit_targets,
                &self.custom_provider_edit_targets,
                !self.provider_operation_in_flight,
                cx,
            ))
    }
}

fn provider_settings_pane(
    settings: &str,
    delete_targets: &[ProviderDeleteTarget],
    edit_targets: &[String],
    custom_edit_targets: &[CustomProviderEditTarget],
    actions_enabled: bool,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let mut pane = div()
        .id("provider-settings-pane")
        .h(px(280.0))
        .overflow_y_scroll()
        .border_t_1()
        .border_color(rgb(0x30363d))
        .p_3()
        .child(div().text_lg().child("Provider settings"))
        .child(
            div()
                .mt_2()
                .text_sm()
                .text_color(rgb(0x8b949e))
                .child(settings.to_owned()),
        );
    let mut edit_actions = div().flex().flex_row().flex_wrap();
    for (index, provider) in edit_targets.iter().enumerate() {
        if !actions_enabled {
            break;
        }
        let provider = provider.clone();
        let label = format!("Set {provider} credential…");
        edit_actions = edit_actions.child(
            div()
                .id(("set-provider-credential", index))
                .mt_2()
                .mr_2()
                .px_2()
                .py_1()
                .bg(rgb(0x30363d))
                .child(label)
                .on_click(cx.listener(move |this, _, _, cx| {
                    this.show_provider_edit_prompt(provider.clone(), cx);
                })),
        );
    }
    for (index, provider) in custom_edit_targets.iter().enumerate() {
        if !actions_enabled {
            break;
        }
        let provider = provider.clone();
        let label = format!("Edit custom:{}…", provider.slug);
        edit_actions = edit_actions.child(
            div()
                .id(("edit-custom-provider", index))
                .mt_2()
                .mr_2()
                .px_2()
                .py_1()
                .bg(rgb(0x30363d))
                .child(label)
                .on_click(cx.listener(move |this, _, _, cx| {
                    this.show_custom_provider_edit_prompt(Some(provider.clone()), cx);
                })),
        );
    }
    if actions_enabled {
        edit_actions = edit_actions.child(
            div()
                .id("add-custom-provider")
                .mt_2()
                .mr_2()
                .px_2()
                .py_1()
                .bg(rgb(0x30363d))
                .child("Add custom provider…")
                .on_click(cx.listener(|this, _, _, cx| {
                    this.show_custom_provider_edit_prompt(None, cx);
                })),
        );
    }
    pane = pane.child(edit_actions);
    if actions_enabled {
        let mut delete_actions = div().flex().flex_row().flex_wrap();
        for (index, target) in delete_targets.iter().enumerate() {
            let target = target.clone();
            let label = match &target {
                ProviderDeleteTarget::Standard(provider) => {
                    format!("Delete {provider} credential…")
                }
                ProviderDeleteTarget::Custom(slug) => {
                    format!("Delete custom:{slug}…")
                }
            };
            delete_actions = delete_actions.child(
                div()
                    .id(("delete-provider-credential", index))
                    .mt_2()
                    .mr_2()
                    .px_2()
                    .py_1()
                    .bg(rgb(0x5a1d1d))
                    .child(label)
                    .on_click(cx.listener(move |this, _, window, cx| {
                        this.show_provider_delete_prompt(target.clone(), window, cx);
                    })),
            );
        }
        pane.child(delete_actions)
    } else {
        pane
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

fn start_native_runtime() -> io::Result<(
    ControlPlaneClient,
    ShadowRuntime,
    Arc<ProviderSettingsController>,
)> {
    let data_dir = development_data_dir()?;
    let token = mint_session_token()?;
    let secret_sync_token = Zeroizing::new(mint_session_token()?);
    let vault = PlatformSecretVault;
    let secret_bootstrap = encode_secret_bootstrap(&vault, &secret_sync_token)?;
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
    let provider_settings = Arc::new(ProviderSettingsController::new(
        vault,
        port,
        &token,
        &secret_sync_token,
    )?);
    Ok((client, runtime, provider_settings))
}

fn main() -> io::Result<()> {
    let (client, runtime, provider_settings_controller) = start_native_runtime()?;
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
    let (standard_status, custom_status) = provider_settings_controller.status()?;
    let (provider_settings, provider_delete_targets) =
        format_provider_settings(&standard_status, &custom_status);
    let provider_edit_targets = standard_status
        .iter()
        .map(|status| status.provider.to_owned())
        .collect();
    let custom_provider_edit_targets = custom_provider_edit_targets(&custom_status);
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
                    provider_settings_controller,
                    provider_delete_targets,
                    provider_edit_targets,
                    custom_provider_edit_targets,
                    provider_operation_in_flight: false,
                })
            },
        )
        .expect("open GPUI prototype window");
        cx.activate(true);
    });
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{
        begin_provider_operation, classify_provider_delete_result, classify_provider_edit_result,
        custom_provider_edit_targets, CustomProviderRecord, ProviderDeleteOutcome,
        ProviderEditOutcome,
    };
    use std::io;

    #[test]
    fn duplicate_provider_operation_is_rejected_until_completion() {
        let mut in_flight = false;
        assert!(begin_provider_operation(&mut in_flight));
        assert!(!begin_provider_operation(&mut in_flight));
        in_flight = false;
        assert!(begin_provider_operation(&mut in_flight));
    }

    #[test]
    fn indeterminate_sync_is_not_reported_as_unchanged() {
        let outcome = classify_provider_edit_result(
            Err(io::Error::new(
                io::ErrorKind::ConnectionAborted,
                "response lost after commit",
            )),
            || panic!("indeterminate writes must not be refreshed as definite success"),
        );
        assert!(matches!(outcome, ProviderEditOutcome::SyncIndeterminate));
    }

    #[test]
    fn indeterminate_delete_is_not_reported_as_definite_failure() {
        let outcome = classify_provider_delete_result(
            Err(io::Error::new(
                io::ErrorKind::ConnectionAborted,
                "response lost after commit",
            )),
            || panic!("indeterminate deletes must not refresh as definite success"),
        );
        assert!(matches!(outcome, ProviderDeleteOutcome::SyncIndeterminate));
    }

    #[test]
    fn refreshed_custom_targets_do_not_retain_deleted_provider() {
        let remaining = vec![CustomProviderRecord {
            slug: "remaining".to_owned(),
            base_url: "https://remaining.example/v1".to_owned(),
            failover_eligible: false,
        }];
        let targets = custom_provider_edit_targets(&remaining);
        assert_eq!(targets.len(), 1);
        assert_eq!(targets[0].slug, "remaining");
        assert!(!targets.iter().any(|provider| provider.slug == "deleted"));
    }
}
