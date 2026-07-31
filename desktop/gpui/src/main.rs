//! Native Codinal desktop shell.
//!
//! Development run:
//! `cargo build --manifest-path crates/codinal-runtime/Cargo.toml`
//! `CODINAL_NATIVE_RUNTIME=crates/codinal-runtime/target/debug/codinal-runtime CODINAL_DATA_DIR=/absolute/codinal/data cargo run --manifest-path desktop/gpui/Cargo.toml`
//! Debug builds boot an authenticated Rust runtime on an isolated snapshot.
//! Release builds boot the bundled native runtime against the production data.

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
    ApprovalConfirmation, ApprovalOutcome, ControlPlaneClient, MessageSummary, PendingApproval,
    SessionSummary,
};
use codinal_native_host::control_client::OAuthRelayController;
#[cfg(target_os = "macos")]
use codinal_native_host::pty::{PtyOutputBuffer, PtyOutputDelta, PtyRegistry};
#[cfg(target_os = "macos")]
use codinal_native_host::updater::run_restart_helper_if_requested;
#[cfg(target_os = "macos")]
use codinal_native_host::workspace::choose_workspace as choose_native_workspace;
use codinal_native_host::{
    free_loopback_port, launch_native_runtime_with_bootstrap, launch_shadow_runtime_with_bootstrap,
    mint_session_token,
    secrets::{
        encode_secret_bootstrap, CustomProviderRecord, PlatformSecretVault, ProviderSecretStatus,
        ProviderSettingsController,
    },
    updater::{AvailableUpdate, NativeUpdater},
    NativeRuntime, ShadowRuntime,
};
use gpui::Task;
use gpui::{
    canvas, div, px, rgb, size, App, AppContext, Bounds, Context, ElementInputHandler,
    EntityInputHandler, FocusHandle, InteractiveElement, KeyDownEvent, ParentElement, Pixels,
    Point, PromptLevel, Render, StatefulInteractiveElement, Styled, UTF16Selection, Window,
    WindowBounds, WindowOptions,
};
use std::io;
use std::ops::Range;
use std::path::PathBuf;
#[cfg(target_os = "macos")]
use std::sync::atomic::AtomicBool;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::mpsc::{sync_channel, Receiver, SyncSender, TrySendError};
use std::sync::Arc;
#[cfg(target_os = "macos")]
use std::sync::Mutex;
#[cfg(target_os = "macos")]
use std::thread;
use std::time::Duration;
use zeroize::Zeroizing;

static NEXT_SHADOW: AtomicU64 = AtomicU64::new(0);

fn enqueue_oauth_urls(
    sender: &SyncSender<Zeroizing<String>>,
    dropped: &AtomicU64,
    urls: impl IntoIterator<Item = String>,
) {
    for url in urls {
        if matches!(
            sender.try_send(Zeroizing::new(url)),
            Err(TrySendError::Full(_) | TrySendError::Disconnected(_))
        ) {
            dropped.fetch_add(1, Ordering::Relaxed);
        }
    }
}

fn approval_completion_is_current(
    current_generation: u64,
    current_session_id: Option<&str>,
    expected_generation: u64,
    expected_session_id: Option<&str>,
) -> bool {
    current_generation == expected_generation && current_session_id == expected_session_id
}

struct WorkspacePrototype {
    _runtime: DesktopRuntime,
    client: Arc<ControlPlaneClient>,
    approval_session_id: Option<String>,
    approval_id: Option<String>,
    session_count: usize,
    sessions: Vec<SessionSummary>,
    selected_session_id: Option<String>,
    session_status: String,
    session_load_generation: u64,
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
    oauth_relay: Arc<OAuthRelayController>,
    oauth_status: String,
    oauth_dropped: Arc<AtomicU64>,
    oauth_poll: Option<Task<()>>,
    updater: Option<Arc<NativeUpdater>>,
    available_update: Option<AvailableUpdate>,
    updater_status: String,
    updater_operation_in_flight: bool,
    updater_restart_required: bool,
    terminal_parser: vt100::Parser,
    terminal_display: String,
    terminal_status: String,
    #[cfg(target_os = "macos")]
    terminal_registry: Arc<PtyRegistry>,
    #[cfg(target_os = "macos")]
    terminal_session_id: String,
    #[cfg(target_os = "macos")]
    terminal_generation: u64,
    #[cfg(target_os = "macos")]
    terminal_workspace: String,
    terminal_state: TerminalState,
    terminal_focus: FocusHandle,
    terminal_marked_text: String,
    terminal_marked_selection: Range<usize>,
    #[cfg(target_os = "macos")]
    terminal_input: Option<SyncSender<Vec<u8>>>,
    #[cfg(target_os = "macos")]
    terminal_input_cancel: Option<Arc<AtomicBool>>,
    #[cfg(target_os = "macos")]
    terminal_resize: Option<SyncSender<(u16, u16)>>,
    #[cfg(target_os = "macos")]
    terminal_resize_result: Option<Arc<Mutex<Option<TerminalResizeOutcome>>>>,
    #[cfg(target_os = "macos")]
    terminal_resize_pending: Option<(u16, u16)>,
    #[cfg(target_os = "macos")]
    terminal_resize_failed: Option<(u16, u16)>,
    #[cfg(target_os = "macos")]
    terminal_poll: Option<Task<()>>,
}

enum DesktopRuntime {
    Production { _process: NativeRuntime },
    Shadow { _process: ShadowRuntime },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum TerminalState {
    Closed,
    Opening,
    Running,
    Stopping,
    Exited,
    Failed,
}

impl TerminalState {
    fn can_open(self) -> bool {
        matches!(self, Self::Closed | Self::Exited | Self::Failed)
    }
}

fn terminal_key_bytes(event: &KeyDownEvent) -> Option<Vec<u8>> {
    let keystroke = &event.keystroke;
    if keystroke.modifiers.platform {
        return None;
    }
    let modifier = 1
        + usize::from(keystroke.modifiers.shift)
        + 2 * usize::from(keystroke.modifiers.alt)
        + 4 * usize::from(keystroke.modifiers.control);
    let modified_csi = |final_byte: char| format!("\x1b[1;{modifier}{final_byte}").into_bytes();
    let modified_tilde = |code: usize| format!("\x1b[{code};{modifier}~").into_bytes();
    let navigation = match keystroke.key.as_str() {
        "up" => Some(if modifier == 1 {
            b"\x1b[A".to_vec()
        } else {
            modified_csi('A')
        }),
        "down" => Some(if modifier == 1 {
            b"\x1b[B".to_vec()
        } else {
            modified_csi('B')
        }),
        "right" => Some(if modifier == 1 {
            b"\x1b[C".to_vec()
        } else {
            modified_csi('C')
        }),
        "left" => Some(if modifier == 1 {
            b"\x1b[D".to_vec()
        } else {
            modified_csi('D')
        }),
        "home" => Some(if modifier == 1 {
            b"\x1b[H".to_vec()
        } else {
            modified_csi('H')
        }),
        "end" => Some(if modifier == 1 {
            b"\x1b[F".to_vec()
        } else {
            modified_csi('F')
        }),
        "insert" => Some(if modifier == 1 {
            b"\x1b[2~".to_vec()
        } else {
            modified_tilde(2)
        }),
        "delete" => Some(if modifier == 1 {
            b"\x1b[3~".to_vec()
        } else {
            modified_tilde(3)
        }),
        "pageup" => Some(if modifier == 1 {
            b"\x1b[5~".to_vec()
        } else {
            modified_tilde(5)
        }),
        "pagedown" => Some(if modifier == 1 {
            b"\x1b[6~".to_vec()
        } else {
            modified_tilde(6)
        }),
        _ => None,
    };
    if navigation.is_some() {
        return navigation;
    }
    let function = match keystroke.key.as_str() {
        "f1" if modifier == 1 => Some(b"\x1bOP".to_vec()),
        "f2" if modifier == 1 => Some(b"\x1bOQ".to_vec()),
        "f3" if modifier == 1 => Some(b"\x1bOR".to_vec()),
        "f4" if modifier == 1 => Some(b"\x1bOS".to_vec()),
        "f1" => Some(modified_csi('P')),
        "f2" => Some(modified_csi('Q')),
        "f3" => Some(modified_csi('R')),
        "f4" => Some(modified_csi('S')),
        "f5" => Some(if modifier == 1 {
            b"\x1b[15~".to_vec()
        } else {
            modified_tilde(15)
        }),
        "f6" => Some(if modifier == 1 {
            b"\x1b[17~".to_vec()
        } else {
            modified_tilde(17)
        }),
        "f7" => Some(if modifier == 1 {
            b"\x1b[18~".to_vec()
        } else {
            modified_tilde(18)
        }),
        "f8" => Some(if modifier == 1 {
            b"\x1b[19~".to_vec()
        } else {
            modified_tilde(19)
        }),
        "f9" => Some(if modifier == 1 {
            b"\x1b[20~".to_vec()
        } else {
            modified_tilde(20)
        }),
        "f10" => Some(if modifier == 1 {
            b"\x1b[21~".to_vec()
        } else {
            modified_tilde(21)
        }),
        "f11" => Some(if modifier == 1 {
            b"\x1b[23~".to_vec()
        } else {
            modified_tilde(23)
        }),
        "f12" => Some(if modifier == 1 {
            b"\x1b[24~".to_vec()
        } else {
            modified_tilde(24)
        }),
        _ => None,
    };
    if function.is_some() {
        return function;
    }
    let mut bytes = if keystroke.modifiers.control {
        let key = keystroke.key.to_ascii_lowercase();
        match key.as_bytes() {
            [value @ b'a'..=b'z'] => vec![value - b'a' + 1],
            [b'@'] | [b' '] | b"space" => vec![0],
            [b'['] => vec![0x1b],
            [b'\\'] => vec![0x1c],
            [b']'] => vec![0x1d],
            [b'^'] => vec![0x1e],
            [b'_'] => vec![0x1f],
            _ => return None,
        }
    } else {
        match keystroke.key.as_str() {
            "enter" => b"\r".to_vec(),
            "backspace" => vec![0x7f],
            "tab" if keystroke.modifiers.shift => b"\x1b[Z".to_vec(),
            "tab" => b"\t".to_vec(),
            "escape" => vec![0x1b],
            _ => return None,
        }
    };
    if keystroke.modifiers.alt {
        bytes.insert(0, 0x1b);
    }
    Some(bytes)
}

#[cfg(target_os = "macos")]
struct TerminalResizeOutcome {
    cols: u16,
    rows: u16,
    boundary: Option<u64>,
    result: Result<(), String>,
}

#[cfg(target_os = "macos")]
fn apply_terminal_resize_outcome(
    parser: &mut vt100::Parser,
    display: &mut String,
    status: &mut String,
    outcome: TerminalResizeOutcome,
) -> bool {
    match outcome.result {
        Ok(()) => {
            parser.screen_mut().set_size(outcome.rows, outcome.cols);
            *display = parser.screen().contents();
            *status = format!("Terminal resized to {}×{}", outcome.cols, outcome.rows);
            true
        }
        Err(error) => {
            *status = format!("Terminal resize failed: {error}");
            false
        }
    }
}

#[cfg(target_os = "macos")]
fn apply_terminal_update(
    parser: &mut vt100::Parser,
    display: &mut String,
    status: &mut String,
    delta: &PtyOutputDelta,
    resize: Option<TerminalResizeOutcome>,
) -> Option<(bool, u16, u16)> {
    let Some(outcome) = resize else {
        apply_terminal_delta(parser, display, status, delta);
        return None;
    };
    let geometry = (outcome.cols, outcome.rows);
    if delta.truncated {
        let (rows, cols) = parser.screen().size();
        *parser = vt100::Parser::new(rows, cols, 1_000);
        *status = "Terminal history truncated to bounded tail".to_owned();
    }
    let applied = if outcome.result.is_ok() {
        let retained_start = delta.next_cursor.saturating_sub(delta.bytes.len() as u64);
        let boundary = outcome.boundary.unwrap_or(retained_start);
        let split = boundary
            .clamp(retained_start, delta.next_cursor)
            .saturating_sub(retained_start) as usize;
        parser.process(&delta.bytes[..split]);
        let applied = apply_terminal_resize_outcome(parser, display, status, outcome);
        parser.process(&delta.bytes[split..]);
        applied
    } else {
        parser.process(&delta.bytes);
        apply_terminal_resize_outcome(parser, display, status, outcome)
    };
    *display = parser.screen().contents();
    if delta.exited {
        *status = "Terminal exited".to_owned();
    }
    Some((applied, geometry.0, geometry.1))
}

#[cfg(target_os = "macos")]
fn enqueue_terminal_input(sender: &SyncSender<Vec<u8>>, bytes: Vec<u8>) -> io::Result<()> {
    const MAX_INPUT_MESSAGE_BYTES: usize = 16 * 1024;
    if bytes.len() > MAX_INPUT_MESSAGE_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "terminal input exceeds 16 KiB message limit",
        ));
    }
    match sender.try_send(bytes) {
        Ok(()) => Ok(()),
        Err(TrySendError::Full(_)) => Err(io::Error::new(
            io::ErrorKind::WouldBlock,
            "terminal input queue is full",
        )),
        Err(TrySendError::Disconnected(_)) => Err(io::Error::new(
            io::ErrorKind::BrokenPipe,
            "terminal input queue is closed",
        )),
    }
}

#[cfg(target_os = "macos")]
fn run_terminal_writer(
    receiver: Receiver<Vec<u8>>,
    cancelled: Arc<AtomicBool>,
    mut write: impl FnMut(&[u8]) -> io::Result<()>,
) {
    while let Ok(bytes) = receiver.recv() {
        if cancelled.load(Ordering::Acquire) || write(&bytes).is_err() {
            break;
        }
    }
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

#[cfg(target_os = "macos")]
fn apply_terminal_delta(
    parser: &mut vt100::Parser,
    display: &mut String,
    status: &mut String,
    delta: &PtyOutputDelta,
) {
    if delta.truncated {
        let (rows, cols) = parser.screen().size();
        *parser = vt100::Parser::new(rows, cols, 1_000);
        *status = "Terminal history truncated to bounded tail".to_owned();
    }
    parser.process(&delta.bytes);
    *display = parser.screen().contents();
    if delta.exited {
        *status = "Terminal exited".to_owned();
    }
}

fn terminal_grid_for_bounds(bounds: Bounds<Pixels>) -> (u16, u16) {
    const CELL_WIDTH: f32 = 8.0;
    const CELL_HEIGHT: f32 = 18.0;
    let width = bounds.size.width.as_f32();
    let height = bounds.size.height.as_f32();
    let cols = if width.is_finite() {
        ((width - 24.0) / CELL_WIDTH).floor().clamp(2.0, 500.0) as u16
    } else {
        2
    };
    let rows = if height.is_finite() {
        ((height - 92.0) / CELL_HEIGHT).floor().clamp(1.0, 200.0) as u16
    } else {
        1
    };
    (cols, rows)
}

fn should_request_terminal_resize(
    state: TerminalState,
    current: (u16, u16),
    pending: Option<(u16, u16)>,
    failed: Option<(u16, u16)>,
    desired: (u16, u16),
) -> bool {
    state == TerminalState::Running
        && current != (desired.1, desired.0)
        && pending.is_none()
        && failed != Some(desired)
}

impl WorkspacePrototype {
    fn select_session(&mut self, session_id: String, cx: &mut Context<Self>) {
        if !self
            .sessions
            .iter()
            .any(|session| session.session_id == session_id)
        {
            return;
        }
        self.session_load_generation = self.session_load_generation.wrapping_add(1);
        let generation = self.session_load_generation;
        self.session_status = "Loading session…".to_owned();
        let client = Arc::clone(&self.client);
        cx.notify();
        cx.spawn(async move |this, cx| {
            let requested_id = session_id.clone();
            let outcome = cx
                .background_executor()
                .spawn(async move {
                    let messages = client.session_messages(&session_id)?;
                    let approvals = client.pending_approvals(&session_id)?;
                    Ok::<_, io::Error>((messages, approvals))
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                if this.session_load_generation != generation {
                    return;
                }
                match outcome {
                    Ok((messages, approvals)) => {
                        this.selected_session_id = Some(requested_id.clone());
                        this.approval_session_id = Some(requested_id);
                        this.conversation = format_conversation(&messages);
                        this.set_pending_approvals(approvals);
                        this.session_status = "Session loaded from Rust runtime".to_owned();
                    }
                    Err(error) => {
                        this.session_status = format!("Session load failed: {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    fn restart_after_update(&mut self, cx: &mut Context<Self>) {
        if !self.updater_restart_required || self.updater_operation_in_flight {
            return;
        }
        let Some(updater) = self.updater.as_ref() else {
            return;
        };
        match updater.spawn_restart_helper() {
            Ok(()) => cx.quit(),
            Err(error) => {
                self.updater_status = format!("Could not restart Codinal: {error}");
                cx.notify();
            }
        }
    }

    fn check_for_update(&mut self, cx: &mut Context<Self>) {
        if self.updater_operation_in_flight || self.updater_restart_required {
            return;
        }
        let Some(updater) = self.updater.clone() else {
            self.updater_status = "Updates are available in packaged release builds".to_owned();
            cx.notify();
            return;
        };
        self.updater_operation_in_flight = true;
        self.updater_status = "Checking for updates…".to_owned();
        cx.notify();
        cx.spawn(async move |this, cx| {
            let outcome = cx
                .background_executor()
                .spawn(async move { updater.check().map_err(|error| error.to_string()) })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.updater_operation_in_flight = false;
                match outcome {
                    Ok(Some(update)) => {
                        this.updater_status = format!("Version {} is available", update.version);
                        this.available_update = Some(update);
                    }
                    Ok(None) => {
                        this.updater_status = "Codinal is up to date".to_owned();
                        this.available_update = None;
                    }
                    Err(error) => {
                        this.updater_status = format!("Update check failed: {error}");
                        this.available_update = None;
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    fn show_update_install_prompt(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if self.updater_operation_in_flight || self.updater_restart_required {
            return;
        }
        let Some(update) = self.available_update.as_ref() else {
            return;
        };
        let detail = match update.notes.as_deref() {
            Some(notes) if !notes.trim().is_empty() => {
                format!("Install signed version {}?\n\n{}", update.version, notes)
            }
            _ => format!("Install signed version {}?", update.version),
        };
        let response = window.prompt(
            PromptLevel::Warning,
            "Install Codinal update",
            Some(&detail),
            &["Cancel", "Install update"],
            cx,
        );
        let update = update.clone();
        self.updater_operation_in_flight = true;
        self.updater_status = format!("Awaiting confirmation for version {}", update.version);
        cx.notify();
        cx.spawn(async move |this, cx| {
            if response.await.unwrap_or(0) == 1 {
                let _ = this.update(cx, |this, cx| this.install_update(update, cx));
            } else {
                let _ = this.update(cx, |this, cx| {
                    this.updater_operation_in_flight = false;
                    this.updater_status = "Update installation cancelled".to_owned();
                    cx.notify();
                });
            }
        })
        .detach();
    }

    fn install_update(&mut self, update: AvailableUpdate, cx: &mut Context<Self>) {
        let Some(updater) = self.updater.clone() else {
            self.updater_operation_in_flight = false;
            return;
        };
        self.updater_status = format!("Downloading version {}…", update.version);
        cx.notify();
        cx.spawn(async move |this, cx| {
            let version = update.version.clone();
            let outcome = cx
                .background_executor()
                .spawn(async move {
                    let archive = updater.download(&update)?;
                    updater.install(&update, &archive)
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.updater_operation_in_flight = false;
                match outcome {
                    Ok(()) => {
                        this.updater_status =
                            format!("Version {version} installed — restart Codinal to apply");
                        this.available_update = None;
                        this.updater_restart_required = true;
                    }
                    Err(error) => {
                        this.updater_status = format!("Update install failed: {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    fn show_update_rollback_prompt(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if self.updater_operation_in_flight || self.updater.is_none() {
            return;
        }
        let response = window.prompt(
            PromptLevel::Critical,
            "Restore previous Codinal version",
            Some("This replaces the installed app bundle with its signed backup. Restart is required."),
            &["Cancel", "Restore previous version"],
            cx,
        );
        self.updater_operation_in_flight = true;
        self.updater_status = "Awaiting rollback confirmation".to_owned();
        cx.notify();
        cx.spawn(async move |this, cx| {
            if response.await.unwrap_or(0) == 1 {
                let _ = this.update(cx, |this, cx| this.rollback_update(cx));
            } else {
                let _ = this.update(cx, |this, cx| {
                    this.updater_operation_in_flight = false;
                    this.updater_status = "Update rollback cancelled".to_owned();
                    cx.notify();
                });
            }
        })
        .detach();
    }

    fn rollback_update(&mut self, cx: &mut Context<Self>) {
        let Some(updater) = self.updater.clone() else {
            self.updater_operation_in_flight = false;
            return;
        };
        self.updater_status = "Restoring the previous signed app…".to_owned();
        cx.notify();
        cx.spawn(async move |this, cx| {
            let outcome = cx
                .background_executor()
                .spawn(async move { updater.rollback() })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.updater_operation_in_flight = false;
                this.updater_status = match outcome {
                    Ok(()) => "Previous version restored — restart Codinal to apply".to_owned(),
                    Err(error) => format!("Update rollback failed: {error}"),
                };
                cx.notify();
            });
        })
        .detach();
    }

    fn start_oauth_poll(&mut self, receiver: Receiver<Zeroizing<String>>, cx: &mut Context<Self>) {
        let relay = Arc::clone(&self.oauth_relay);
        let dropped = Arc::clone(&self.oauth_dropped);
        self.oauth_poll = Some(cx.spawn(async move |this, cx| loop {
            let dropped_count = dropped.swap(0, Ordering::AcqRel);
            if dropped_count > 0 {
                let _ = this.update(cx, |this, cx| {
                    this.oauth_status =
                        format!("OAuth callback queue rejected {dropped_count} URL(s)");
                    cx.notify();
                });
            }
            let raw_url = match receiver.try_recv() {
                Ok(url) => url,
                Err(std::sync::mpsc::TryRecvError::Empty) => {
                    cx.background_executor()
                        .timer(Duration::from_millis(50))
                        .await;
                    continue;
                }
                Err(std::sync::mpsc::TryRecvError::Disconnected) => break,
            };
            let relay = Arc::clone(&relay);
            let result = cx
                .background_executor()
                .spawn(async move { relay.relay_deep_link(&raw_url) })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.oauth_status = match result {
                    Ok(flow) => format!("OAuth callback relayed: {flow}"),
                    Err(error) => format!("OAuth callback rejected: {error}"),
                };
                cx.notify();
            });
        }));
    }

    #[cfg(target_os = "macos")]
    fn choose_workspace(&mut self, cx: &mut Context<Self>) {
        if !self.terminal_state.can_open() {
            return;
        }
        match choose_native_workspace() {
            Ok(path) => {
                self.terminal_workspace = path.to_string_lossy().into_owned();
                self.terminal_status = format!("Workspace selected: {}", path.display());
            }
            Err(error) if error.kind() == io::ErrorKind::Interrupted => {
                self.terminal_status = "Workspace selection cancelled".to_owned();
            }
            Err(error) => {
                self.terminal_status = format!("Workspace selection failed: {error}");
            }
        }
        cx.notify();
    }

    #[cfg(target_os = "macos")]
    fn open_terminal(&mut self, cx: &mut Context<Self>) {
        if !self.terminal_state.can_open() {
            return;
        }
        self.terminal_state = TerminalState::Opening;
        self.terminal_generation = self.terminal_generation.saturating_add(1);
        self.terminal_session_id = format!("gpui-main-terminal-{}", self.terminal_generation);
        self.terminal_status = "Opening terminal…".to_owned();
        let (rows, cols) = self.terminal_parser.screen().size();
        self.terminal_parser = vt100::Parser::new(rows, cols, 1_000);
        self.terminal_display.clear();
        self.terminal_marked_text.clear();
        self.terminal_marked_selection = 0..0;
        if let Some(cancelled) = self.terminal_input_cancel.take() {
            cancelled.store(true, Ordering::Release);
        }
        self.terminal_input.take();
        self.terminal_resize.take();
        self.terminal_resize_result.take();
        self.terminal_resize_pending = None;
        self.terminal_resize_failed = None;
        cx.notify();
        let registry = Arc::clone(&self.terminal_registry);
        let writer_registry = Arc::clone(&self.terminal_registry);
        let resize_registry = Arc::clone(&self.terminal_registry);
        let output = Arc::new(PtyOutputBuffer::default());
        let callback_output = Arc::clone(&output);
        let resize_output = Arc::clone(&output);
        let session_id = self.terminal_session_id.clone();
        let writer_session_id = session_id.clone();
        let generation = self.terminal_generation;
        let workspace = self.terminal_workspace.clone();
        let (rows, cols) = self.terminal_parser.screen().size();
        cx.spawn(async move |this, cx| {
            let opened = cx
                .background_executor()
                .spawn(async move {
                    registry.open(
                        &session_id,
                        &workspace,
                        None,
                        cols,
                        rows,
                        move |_, chunk| match chunk {
                            Some(bytes) => callback_output.push(bytes),
                            None => callback_output.mark_exited(),
                        },
                    )
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                match opened {
                    Ok(()) => {
                        let (sender, receiver) = sync_channel::<Vec<u8>>(256);
                        let (resize_sender, resize_receiver) = sync_channel::<(u16, u16)>(1);
                        let resize_result = Arc::new(Mutex::new(None));
                        let thread_resize_result = Arc::clone(&resize_result);
                        let cancelled = Arc::new(AtomicBool::new(false));
                        let writer_cancelled = Arc::clone(&cancelled);
                        let resize_cancelled = Arc::clone(&cancelled);
                        let resize_session_id = writer_session_id.clone();
                        let writer_started = thread::Builder::new()
                            .name(format!("gpui-pty-writer-{generation}"))
                            .spawn(move || {
                                run_terminal_writer(receiver, writer_cancelled, |bytes| {
                                    writer_registry.write(&writer_session_id, bytes)
                                });
                            })
                            .is_ok();
                        let resizer_started = thread::Builder::new()
                            .name(format!("gpui-pty-resizer-{generation}"))
                            .spawn(move || {
                                while let Ok((cols, rows)) = resize_receiver.recv() {
                                    if resize_cancelled.load(Ordering::Acquire) {
                                        break;
                                    }
                                    let mut boundary = None;
                                    let result = resize_registry
                                        .resize_ordered(&resize_session_id, cols, rows, || {
                                            boundary = Some(resize_output.cursor());
                                        })
                                        .map_err(|error| error.to_string());
                                    *thread_resize_result.lock().unwrap() =
                                        Some(TerminalResizeOutcome {
                                            cols,
                                            rows,
                                            boundary,
                                            result,
                                        });
                                }
                            })
                            .is_ok();
                        this.terminal_input = writer_started.then_some(sender);
                        this.terminal_resize = resizer_started.then_some(resize_sender);
                        this.terminal_resize_result = resizer_started.then_some(resize_result);
                        this.terminal_resize_pending = None;
                        this.terminal_resize_failed = None;
                        this.terminal_input_cancel =
                            (writer_started || resizer_started).then_some(cancelled);
                        this.terminal_state = TerminalState::Running;
                        this.terminal_status = if writer_started && resizer_started {
                            "Terminal running · VT screen active".to_owned()
                        } else {
                            "Terminal running · control worker unavailable".to_owned()
                        };
                        this.start_terminal_poll(
                            output,
                            this.terminal_generation,
                            this.terminal_resize_result.clone(),
                            cx,
                        );
                    }
                    Err(error) => {
                        this.terminal_state = TerminalState::Failed;
                        this.terminal_status = format!("Terminal open failed: {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    #[cfg(target_os = "macos")]
    fn start_terminal_poll(
        &mut self,
        output: Arc<PtyOutputBuffer>,
        generation: u64,
        resize_result: Option<Arc<Mutex<Option<TerminalResizeOutcome>>>>,
        cx: &mut Context<Self>,
    ) {
        let registry = Arc::clone(&self.terminal_registry);
        let session_id = self.terminal_session_id.clone();
        self.terminal_poll = Some(cx.spawn(async move |this, cx| {
            let mut cursor = 0;
            loop {
                cx.background_executor()
                    .timer(Duration::from_millis(33))
                    .await;
                let delta = output.read_since(cursor);
                cursor = delta.next_cursor;
                let exited = delta.exited;
                let resize_outcome = resize_result
                    .as_ref()
                    .and_then(|result| result.lock().unwrap().take());
                if delta.truncated || !delta.bytes.is_empty() || exited || resize_outcome.is_some()
                {
                    let _ = this.update(cx, |this, cx| {
                        if this.terminal_generation != generation {
                            return;
                        }
                        let resize_applied = apply_terminal_update(
                            &mut this.terminal_parser,
                            &mut this.terminal_display,
                            &mut this.terminal_status,
                            &delta,
                            resize_outcome,
                        );
                        if let Some((applied, cols, rows)) = resize_applied {
                            this.terminal_resize_pending = None;
                            this.terminal_resize_failed = (!applied).then_some((cols, rows));
                        }
                        if exited {
                            if let Some(cancelled) = this.terminal_input_cancel.take() {
                                cancelled.store(true, Ordering::Release);
                            }
                            this.terminal_input.take();
                            this.terminal_resize.take();
                            this.terminal_resize_result.take();
                            this.terminal_resize_pending = None;
                            this.terminal_resize_failed = None;
                            this.terminal_marked_text.clear();
                            this.terminal_marked_selection = 0..0;
                            this.terminal_state = TerminalState::Stopping;
                            this.terminal_status = "Terminal exited · cleaning up".to_owned();
                        }
                        cx.notify();
                    });
                }
                if exited {
                    break;
                }
            }
            let _ = cx
                .background_executor()
                .spawn(async move { registry.kill(&session_id) })
                .await;
            let _ = this.update(cx, |this, cx| {
                if this.terminal_generation != generation {
                    return;
                }
                this.terminal_state = TerminalState::Exited;
                this.terminal_status = "Terminal exited".to_owned();
                cx.notify();
            });
        }));
    }

    #[cfg(target_os = "macos")]
    fn send_terminal_interrupt(&mut self, cx: &mut Context<Self>) {
        self.send_terminal_bytes(vec![0x03], true, cx);
    }

    #[cfg(target_os = "macos")]
    fn send_terminal_key(&mut self, event: &KeyDownEvent, cx: &mut Context<Self>) {
        if self.terminal_state != TerminalState::Running {
            return;
        }
        let Some(bytes) = terminal_key_bytes(event) else {
            return;
        };
        cx.stop_propagation();
        self.send_terminal_bytes(bytes, false, cx);
    }

    #[cfg(target_os = "macos")]
    fn send_terminal_bytes(
        &mut self,
        bytes: Vec<u8>,
        report_success: bool,
        cx: &mut Context<Self>,
    ) {
        let result = self
            .terminal_input
            .as_ref()
            .ok_or_else(|| io::Error::new(io::ErrorKind::BrokenPipe, "terminal input unavailable"))
            .and_then(|sender| enqueue_terminal_input(sender, bytes));
        match result {
            Ok(()) if report_success => {
                self.terminal_status = "Sent Ctrl-C".to_owned();
                cx.notify();
            }
            Ok(()) => {}
            Err(error) => {
                self.terminal_status = format!("Terminal input failed: {error}");
                cx.notify();
            }
        }
    }

    #[cfg(target_os = "macos")]
    fn resize_terminal(&mut self, cols: u16, rows: u16, cx: &mut Context<Self>) {
        if self.terminal_resize_pending.is_some() {
            return;
        }
        let result = self
            .terminal_resize
            .as_ref()
            .ok_or_else(|| {
                io::Error::new(io::ErrorKind::BrokenPipe, "terminal resizer unavailable")
            })
            .and_then(|sender| {
                sender.try_send((cols, rows)).map_err(|error| match error {
                    TrySendError::Full(_) => {
                        io::Error::new(io::ErrorKind::WouldBlock, "terminal resize already queued")
                    }
                    TrySendError::Disconnected(_) => {
                        io::Error::new(io::ErrorKind::BrokenPipe, "terminal resizer is closed")
                    }
                })
            });
        match result {
            Ok(()) => {
                self.terminal_resize_pending = Some((cols, rows));
                self.terminal_resize_failed = None;
                self.terminal_status = format!("Resizing terminal to {cols}×{rows}…");
            }
            Err(error) => {
                self.terminal_resize_failed = Some((cols, rows));
                self.terminal_status = format!("Terminal resize deferred: {error}");
            }
        }
        cx.notify();
    }

    #[cfg(target_os = "macos")]
    fn kill_terminal(&mut self, cx: &mut Context<Self>) {
        if self.terminal_state != TerminalState::Running {
            return;
        }
        self.terminal_state = TerminalState::Stopping;
        if let Some(cancelled) = self.terminal_input_cancel.take() {
            cancelled.store(true, Ordering::Release);
        }
        self.terminal_input.take();
        self.terminal_resize.take();
        self.terminal_resize_result.take();
        self.terminal_resize_pending = None;
        self.terminal_resize_failed = None;
        self.terminal_status = "Stopping terminal…".to_owned();
        cx.notify();
        let registry = Arc::clone(&self.terminal_registry);
        let session_id = self.terminal_session_id.clone();
        let generation = self.terminal_generation;
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move { registry.kill(&session_id) })
                .await;
            let _ = this.update(cx, |this, cx| {
                if this.terminal_generation != generation {
                    return;
                }
                match result {
                    Ok(_) => {
                        this.terminal_state = TerminalState::Exited;
                        this.terminal_status = "Terminal stopped".to_owned();
                    }
                    Err(error) => {
                        this.terminal_state = TerminalState::Failed;
                        this.terminal_status = format!("Terminal stop failed: {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

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
        let target_session_id = session_id.clone();
        let approval_id = self.approval_id.clone();
        let session_generation = self.session_load_generation;
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
                if !approval_completion_is_current(
                    this.session_load_generation,
                    this.approval_session_id.as_deref(),
                    session_generation,
                    target_session_id.as_deref(),
                ) {
                    return;
                }
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

impl EntityInputHandler for WorkspacePrototype {
    fn text_for_range(
        &mut self,
        range: Range<usize>,
        adjusted_range: &mut Option<Range<usize>>,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<String> {
        let utf16: Vec<u16> = self.terminal_marked_text.encode_utf16().collect();
        let end = range.end.min(utf16.len());
        let start = range.start.min(end);
        *adjusted_range = Some(start..end);
        String::from_utf16(&utf16[start..end]).ok()
    }

    fn selected_text_range(
        &mut self,
        _ignore_disabled_input: bool,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<UTF16Selection> {
        Some(UTF16Selection {
            range: self.terminal_marked_selection.clone(),
            reversed: false,
        })
    }

    fn marked_text_range(
        &self,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<Range<usize>> {
        let len = self.terminal_marked_text.encode_utf16().count();
        (len > 0).then_some(0..len)
    }

    fn unmark_text(&mut self, _window: &mut Window, cx: &mut Context<Self>) {
        let text = std::mem::take(&mut self.terminal_marked_text);
        self.terminal_marked_selection = 0..0;
        #[cfg(target_os = "macos")]
        if self.terminal_state == TerminalState::Running && !text.is_empty() {
            self.send_terminal_bytes(text.into_bytes(), false, cx);
        }
        cx.notify();
    }

    fn replace_text_in_range(
        &mut self,
        _range: Option<Range<usize>>,
        text: &str,
        _window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        self.terminal_marked_text.clear();
        self.terminal_marked_selection = 0..0;
        #[cfg(target_os = "macos")]
        if self.terminal_state == TerminalState::Running && !text.is_empty() {
            self.send_terminal_bytes(text.as_bytes().to_vec(), false, cx);
        }
        cx.notify();
    }

    fn replace_and_mark_text_in_range(
        &mut self,
        _range: Option<Range<usize>>,
        new_text: &str,
        new_selected_range: Option<Range<usize>>,
        _window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        self.terminal_marked_text.clear();
        self.terminal_marked_text.push_str(new_text);
        let len = new_text.encode_utf16().count();
        self.terminal_marked_selection = new_selected_range
            .map(|range| range.start.min(len)..range.end.min(len))
            .unwrap_or(len..len);
        cx.notify();
    }

    fn bounds_for_range(
        &mut self,
        _range_utf16: Range<usize>,
        element_bounds: Bounds<Pixels>,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<Bounds<Pixels>> {
        Some(element_bounds)
    }

    fn character_index_for_point(
        &mut self,
        _point: Point<Pixels>,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<usize> {
        Some(0)
    }

    fn accepts_text_input(&self, _window: &mut Window, _cx: &mut Context<Self>) -> bool {
        self.terminal_state == TerminalState::Running
    }
}

impl Render for WorkspacePrototype {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl gpui::IntoElement {
        let runtime = format!(
            "authenticated Rust runtime ready · {} sessions · {}",
            self.session_count, self.oauth_status
        );
        #[cfg(target_os = "macos")]
        let terminal_workspace = self.terminal_workspace.clone();
        #[cfg(not(target_os = "macos"))]
        let terminal_workspace = "Native workspace selection unavailable".to_owned();
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
                    .child(session_pane(
                        &self.sessions,
                        self.selected_session_id.as_deref(),
                        &self.session_status,
                        cx,
                    ))
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
            .child(updater_pane(
                &self.updater_status,
                self.updater.is_some(),
                self.available_update.is_some(),
                !self.updater_operation_in_flight,
                self.updater_restart_required,
                cx,
            ))
            .child(terminal_pane(
                &self.terminal_display,
                &self.terminal_status,
                self.terminal_state,
                &terminal_workspace,
                &self.terminal_focus,
                cx.entity(),
                cx,
            ))
    }
}

fn updater_pane(
    status: &str,
    configured: bool,
    update_available: bool,
    idle: bool,
    restart_required: bool,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let mut actions = div().flex().flex_row().flex_wrap();
    if configured && idle && !restart_required {
        actions = actions.child(
            div()
                .id("update-check")
                .mr_2()
                .px_2()
                .py_1()
                .bg(rgb(0x30363d))
                .child("Check for updates")
                .on_click(cx.listener(|this, _, _, cx| this.check_for_update(cx))),
        );
        if update_available {
            actions = actions.child(
                div()
                    .id("update-install")
                    .mr_2()
                    .px_2()
                    .py_1()
                    .bg(rgb(0x245c35))
                    .child("Install signed update")
                    .on_click(cx.listener(|this, _, window, cx| {
                        this.show_update_install_prompt(window, cx);
                    })),
            );
        }
    }
    if configured && idle {
        if restart_required {
            actions = actions.child(
                div()
                    .id("update-restart")
                    .mr_2()
                    .px_2()
                    .py_1()
                    .bg(rgb(0x245c35))
                    .child("Restart now")
                    .on_click(cx.listener(|this, _, _, cx| this.restart_after_update(cx))),
            );
        }
        actions = actions.child(
            div()
                .id("update-rollback")
                .px_2()
                .py_1()
                .bg(rgb(0x5a1d1d))
                .child("Restore previous version")
                .on_click(cx.listener(|this, _, window, cx| {
                    this.show_update_rollback_prompt(window, cx);
                })),
        );
    }
    div()
        .id("native-updater-pane")
        .role(gpui::Role::Region)
        .aria_label("Native signed updater")
        .aria_description(status.to_owned())
        .border_t_1()
        .border_color(rgb(0x30363d))
        .p_3()
        .child(div().text_lg().child("Native updater"))
        .child(div().mt_1().text_sm().child(status.to_owned()))
        .child(actions)
}

fn terminal_pane(
    output: &str,
    status: &str,
    state: TerminalState,
    workspace: &str,
    focus: &FocusHandle,
    entity: gpui::Entity<WorkspacePrototype>,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let input_focus = focus.clone();
    let mut actions = div().flex().flex_row().flex_wrap();
    #[cfg(target_os = "macos")]
    {
        if state.can_open() {
            actions = actions
                .child(
                    div()
                        .id("terminal-workspace")
                        .mr_2()
                        .px_2()
                        .py_1()
                        .bg(rgb(0x30363d))
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
                        .bg(rgb(0x30363d))
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
                        .bg(rgb(0x30363d))
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
                        .bg(rgb(0x5a1d1d))
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
        .track_focus(focus)
        .on_click(cx.listener(|this, _, window, cx| {
            this.terminal_focus.focus(window, cx);
        }))
        .on_key_down(cx.listener(|this, event, _, cx| {
            #[cfg(target_os = "macos")]
            this.send_terminal_key(event, cx);
        }))
        .h(px(220.0))
        .overflow_y_scroll()
        .border_t_1()
        .border_color(rgb(0x30363d))
        .p_3()
        .child(div().text_lg().child("Native terminal stream"))
        .child(div().mt_2().text_sm().child(status.to_owned()))
        .child(
            div()
                .mt_1()
                .text_sm()
                .text_color(rgb(0x8b949e))
                .child(format!("Workspace: {workspace}")),
        )
        .child(actions)
        .child(
            div()
                .mt_2()
                .text_sm()
                .text_color(rgb(0xc9d1d9))
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
        .child(format!("Codinal — {runtime}"))
        .child("⌘K command palette · ⌘. cancel")
}

fn session_pane(
    sessions: &[SessionSummary],
    selected_session_id: Option<&str>,
    status: &str,
    cx: &mut Context<WorkspacePrototype>,
) -> impl gpui::IntoElement {
    let mut list = div().flex().flex_col();
    for (index, session) in sessions.iter().enumerate() {
        let session_id = session.session_id.clone();
        let selected = selected_session_id == Some(session.session_id.as_str());
        list = list.child(
            div()
                .id(("session-row", index))
                .mt_1()
                .px_2()
                .py_1()
                .bg(rgb(if selected { 0x245c35 } else { 0x20252b }))
                .child(format!("{} · {} messages", session.title, session.messages))
                .on_click(cx.listener(move |this, _, _, cx| {
                    this.select_session(session_id.clone(), cx);
                })),
        );
    }
    if sessions.is_empty() {
        list = list.child("No sessions yet");
    }
    div()
        .flex_1()
        .min_w(px(220.0))
        .border_r_1()
        .border_color(rgb(0x30363d))
        .p_3()
        .child(div().text_lg().child("Sessions"))
        .child(
            div()
                .mt_1()
                .text_sm()
                .text_color(rgb(0x8b949e))
                .child(status.to_owned()),
        )
        .child(list)
}

fn format_conversation(messages: &[MessageSummary]) -> String {
    if messages.is_empty() {
        return "This session has no messages".to_owned();
    }
    messages
        .iter()
        .take(50)
        .map(|message| format!("{}: {}", message.role, message.text))
        .collect::<Vec<_>>()
        .join("\n\n")
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

fn production_data_dir() -> io::Result<PathBuf> {
    let home = std::env::var_os("HOME").ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::NotFound,
            "could not locate the user home directory",
        )
    })?;
    Ok(PathBuf::from(home).join("Library/Application Support/dev.codinal.desktop"))
}

fn desktop_data_dir() -> io::Result<PathBuf> {
    if cfg!(debug_assertions) {
        development_data_dir()
    } else {
        production_data_dir()
    }
}

fn native_runtime_binary() -> io::Result<PathBuf> {
    if cfg!(debug_assertions) {
        return std::env::var_os("CODINAL_NATIVE_RUNTIME")
            .map(PathBuf::from)
            .ok_or_else(|| {
                io::Error::new(
                    io::ErrorKind::NotFound,
                    "CODINAL_NATIVE_RUNTIME is required for a GPUI debug build",
                )
            });
    }
    let executable = std::env::current_exe()?;
    let contents = executable
        .parent()
        .and_then(|path| path.parent())
        .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "invalid app bundle layout"))?;
    Ok(contents.join("Resources/codinal-runtime"))
}

fn release_updater() -> io::Result<Option<Arc<NativeUpdater>>> {
    if cfg!(debug_assertions) {
        return Ok(None);
    }
    let executable = std::env::current_exe()?;
    let contents = executable
        .parent()
        .and_then(|path| path.parent())
        .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "invalid app bundle layout"))?;
    let app_bundle = contents
        .parent()
        .map(PathBuf::from)
        .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "invalid app bundle layout"))?;
    NativeUpdater::for_release_bundle(env!("CARGO_PKG_VERSION"), app_bundle)
        .map(Arc::new)
        .map(Some)
        .map_err(io::Error::other)
}

fn start_native_runtime() -> io::Result<(
    ControlPlaneClient,
    DesktopRuntime,
    Arc<ProviderSettingsController>,
    Arc<OAuthRelayController>,
)> {
    let data_dir = desktop_data_dir()?;
    let token = mint_session_token()?;
    let secret_sync_token = Zeroizing::new(mint_session_token()?);
    let vault = PlatformSecretVault;
    let secret_bootstrap = encode_secret_bootstrap(&vault, &secret_sync_token)?;
    let port = free_loopback_port()?;
    let runtime = if cfg!(debug_assertions) {
        let snapshot = std::env::temp_dir().join(format!(
            "codinal-gpui-shadow-{}-{}",
            std::process::id(),
            NEXT_SHADOW.fetch_add(1, Ordering::Relaxed)
        ));
        DesktopRuntime::Shadow {
            _process: launch_shadow_runtime_with_bootstrap(
                native_runtime_binary()?,
                &data_dir,
                &snapshot,
                port,
                token.clone(),
                secret_bootstrap,
            )?,
        }
    } else {
        DesktopRuntime::Production {
            _process: launch_native_runtime_with_bootstrap(
                native_runtime_binary()?,
                &data_dir,
                port,
                token.clone(),
                secret_bootstrap,
            )?,
        }
    };
    let client = ControlPlaneClient::new(port, &token)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidInput, error.to_string()))?;
    let provider_settings = Arc::new(ProviderSettingsController::new(
        vault,
        port,
        &token,
        &secret_sync_token,
    )?);
    let oauth_relay = Arc::new(OAuthRelayController::new(
        port,
        token,
        secret_sync_token.to_string(),
    )?);
    Ok((client, runtime, provider_settings, oauth_relay))
}

#[cfg(target_os = "macos")]
fn prepare_native_terminal() -> io::Result<(Arc<PtyRegistry>, String, String)> {
    let workspace = std::env::var_os("CODINAL_WORKSPACE")
        .map(PathBuf::from)
        .unwrap_or(desktop_data_dir()?);
    let workspace = workspace
        .to_str()
        .ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidInput,
                "terminal workspace is not UTF-8",
            )
        })?
        .to_owned();
    let registry = Arc::new(PtyRegistry::default());
    let session_id = "gpui-main-terminal".to_owned();
    Ok((registry, session_id, workspace))
}

fn main() -> io::Result<()> {
    #[cfg(target_os = "macos")]
    if run_restart_helper_if_requested().map_err(io::Error::other)? {
        return Ok(());
    }
    let (client, runtime, provider_settings_controller, oauth_relay) = start_native_runtime()?;
    let updater = release_updater()?;
    #[cfg(target_os = "macos")]
    let (terminal_registry, terminal_session_id, terminal_workspace) = prepare_native_terminal()?;
    let sessions = client.list_sessions()?;
    let session_count = sessions.len();
    let conversation = match sessions.first() {
        Some(session) => format_conversation(&client.session_messages(&session.session_id)?),
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
    let (oauth_url_sender, oauth_url_receiver) = sync_channel::<Zeroizing<String>>(32);
    let oauth_dropped = Arc::new(AtomicU64::new(0));
    let callback_dropped = Arc::clone(&oauth_dropped);
    let application = gpui_platform::application();
    application.on_open_urls(move |urls| {
        enqueue_oauth_urls(&oauth_url_sender, &callback_dropped, urls);
    });
    application.run(move |cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(1280.0), px(800.0)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |_, cx| {
                let entity = cx.new(|cx: &mut Context<WorkspacePrototype>| WorkspacePrototype {
                    _runtime: runtime,
                    client,
                    approval_session_id,
                    approval_id,
                    session_count,
                    selected_session_id: sessions.first().map(|session| session.session_id.clone()),
                    sessions,
                    session_status: "Session list loaded from Rust runtime".to_owned(),
                    session_load_generation: 0,
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
                    oauth_relay,
                    oauth_status: "OAuth idle".to_owned(),
                    oauth_dropped,
                    oauth_poll: None,
                    updater,
                    available_update: None,
                    updater_status: if cfg!(debug_assertions) {
                        "Updates are disabled in development builds".to_owned()
                    } else {
                        "Ready to check the signed release channel".to_owned()
                    },
                    updater_operation_in_flight: false,
                    updater_restart_required: false,
                    terminal_parser: vt100::Parser::new(30, 100, 1_000),
                    terminal_display: String::new(),
                    terminal_status: "Terminal closed".to_owned(),
                    terminal_state: TerminalState::Closed,
                    terminal_focus: cx.focus_handle(),
                    terminal_marked_text: String::new(),
                    terminal_marked_selection: 0..0,
                    #[cfg(target_os = "macos")]
                    terminal_registry,
                    #[cfg(target_os = "macos")]
                    terminal_session_id,
                    #[cfg(target_os = "macos")]
                    terminal_generation: 0,
                    #[cfg(target_os = "macos")]
                    terminal_workspace,
                    #[cfg(target_os = "macos")]
                    terminal_input: None,
                    #[cfg(target_os = "macos")]
                    terminal_input_cancel: None,
                    #[cfg(target_os = "macos")]
                    terminal_resize: None,
                    #[cfg(target_os = "macos")]
                    terminal_resize_result: None,
                    #[cfg(target_os = "macos")]
                    terminal_resize_pending: None,
                    #[cfg(target_os = "macos")]
                    terminal_resize_failed: None,
                    #[cfg(target_os = "macos")]
                    terminal_poll: None,
                });
                entity.update(cx, |this, cx| {
                    this.start_oauth_poll(oauth_url_receiver, cx);
                });
                entity
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
        approval_completion_is_current, begin_provider_operation, classify_provider_delete_result,
        classify_provider_edit_result, custom_provider_edit_targets, format_conversation,
        CustomProviderRecord, ProviderDeleteOutcome, ProviderEditOutcome,
    };
    use codinal_control_plane_client::MessageSummary;
    #[cfg(target_os = "macos")]
    use codinal_native_host::pty::PtyOutputDelta;
    use gpui::{KeyDownEvent, Keystroke, Modifiers};
    use std::io;

    #[test]
    fn conversation_format_is_bounded_and_handles_empty_sessions() {
        assert_eq!(format_conversation(&[]), "This session has no messages");
        let messages = (0..55)
            .map(|index| MessageSummary {
                role: "assistant".to_owned(),
                text: format!("message-{index}"),
            })
            .collect::<Vec<_>>();
        let formatted = format_conversation(&messages);
        assert!(formatted.contains("message-0"));
        assert!(formatted.contains("message-49"));
        assert!(!formatted.contains("message-50"));
    }

    #[test]
    fn approval_completion_must_match_session_and_selection_generation() {
        assert!(approval_completion_is_current(
            4,
            Some("session-a"),
            4,
            Some("session-a")
        ));
        assert!(!approval_completion_is_current(
            5,
            Some("session-a"),
            4,
            Some("session-a")
        ));
        assert!(!approval_completion_is_current(
            4,
            Some("session-b"),
            4,
            Some("session-a")
        ));
    }

    #[test]
    fn duplicate_provider_operation_is_rejected_until_completion() {
        let mut in_flight = false;
        assert!(begin_provider_operation(&mut in_flight));
        assert!(!begin_provider_operation(&mut in_flight));
        in_flight = false;
        assert!(begin_provider_operation(&mut in_flight));
    }

    #[test]
    fn oauth_url_queue_is_bounded_and_counts_rejections() {
        use std::sync::atomic::{AtomicU64, Ordering};
        use std::sync::mpsc::sync_channel;

        let (sender, receiver) = sync_channel(1);
        let dropped = AtomicU64::new(0);
        super::enqueue_oauth_urls(&sender, &dropped, ["first".to_owned(), "second".to_owned()]);
        assert_eq!(receiver.recv().unwrap().as_str(), "first");
        assert_eq!(dropped.load(Ordering::Relaxed), 1);
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

    #[cfg(target_os = "macos")]
    #[test]
    fn terminal_delta_replaces_truncated_history_and_marks_exit() {
        let mut parser = vt100::Parser::new(2, 10, 10);
        parser.process(b"stale");
        let mut display = parser.screen().contents();
        let mut status = "running".to_owned();
        super::apply_terminal_delta(
            &mut parser,
            &mut display,
            &mut status,
            &PtyOutputDelta {
                bytes: b"tail".to_vec(),
                next_cursor: 10,
                truncated: true,
                exited: true,
            },
        );
        assert_eq!(display, "tail");
        assert_eq!(status, "Terminal exited");
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn terminal_delta_applies_cursor_and_erase_escape_sequences() {
        let mut parser = vt100::Parser::new(3, 12, 10);
        let mut display = String::new();
        let mut status = "running".to_owned();
        super::apply_terminal_delta(
            &mut parser,
            &mut display,
            &mut status,
            &PtyOutputDelta {
                bytes: b"hello\r\x1b[2Kworld\x1b[2D!!".to_vec(),
                next_cursor: 20,
                truncated: false,
                exited: false,
            },
        );
        assert_eq!(display, "wor!!");
        assert_eq!(parser.screen().cursor_position(), (0, 5));
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn terminal_replay_keeps_visible_screen_bounded() {
        let mut parser = vt100::Parser::new(24, 80, 1_000);
        let mut display = String::new();
        let mut status = "running".to_owned();
        let replay = "0123456789abcdef\r\n".repeat(20_000).into_bytes();
        super::apply_terminal_delta(
            &mut parser,
            &mut display,
            &mut status,
            &PtyOutputDelta {
                next_cursor: replay.len() as u64,
                bytes: replay,
                truncated: false,
                exited: false,
            },
        );
        assert!(display.len() <= 24 * 81);
        assert_eq!(parser.screen().size(), (24, 80));
    }

    #[test]
    fn terminal_lifecycle_allows_reopen_only_after_terminal_states() {
        assert!(super::TerminalState::Closed.can_open());
        assert!(super::TerminalState::Exited.can_open());
        assert!(super::TerminalState::Failed.can_open());
        assert!(!super::TerminalState::Opening.can_open());
        assert!(!super::TerminalState::Running.can_open());
        assert!(!super::TerminalState::Stopping.can_open());
    }

    #[test]
    fn terminal_grid_tracks_rendered_bounds_with_safe_minimums() {
        let bounds = gpui::Bounds::new(
            gpui::point(gpui::px(0.0), gpui::px(0.0)),
            gpui::size(gpui::px(824.0), gpui::px(452.0)),
        );
        assert_eq!(super::terminal_grid_for_bounds(bounds), (100, 20));
        let tiny = gpui::Bounds::new(
            gpui::point(gpui::px(0.0), gpui::px(0.0)),
            gpui::size(gpui::px(1.0), gpui::px(1.0)),
        );
        assert_eq!(super::terminal_grid_for_bounds(tiny), (2, 1));
        let huge = gpui::Bounds::new(
            gpui::point(gpui::px(0.0), gpui::px(0.0)),
            gpui::size(gpui::px(1_000_000.0), gpui::px(1_000_000.0)),
        );
        assert_eq!(super::terminal_grid_for_bounds(huge), (500, 200));
    }

    #[test]
    fn failed_resize_is_not_resubmitted_each_render() {
        assert!(!super::should_request_terminal_resize(
            super::TerminalState::Running,
            (24, 80),
            None,
            Some((120, 40)),
            (120, 40),
        ));
        assert!(super::should_request_terminal_resize(
            super::TerminalState::Running,
            (24, 80),
            None,
            Some((120, 40)),
            (100, 30),
        ));
    }

    #[test]
    fn terminal_key_mapping_leaves_text_to_ime_and_covers_xterm_controls() {
        let event = |key: &str, key_char: Option<&str>, modifiers: Modifiers| KeyDownEvent {
            keystroke: Keystroke {
                key: key.to_owned(),
                key_char: key_char.map(str::to_owned),
                modifiers,
            },
            is_held: false,
            prefer_character_input: false,
        };
        assert_eq!(
            super::terminal_key_bytes(&event("a", Some("ก"), Modifiers::default())),
            None
        );
        assert_eq!(
            super::terminal_key_bytes(&event(
                "c",
                Some("c"),
                Modifiers {
                    control: true,
                    ..Default::default()
                }
            )),
            Some(vec![3])
        );
        assert_eq!(
            super::terminal_key_bytes(&event(
                "space",
                Some(" "),
                Modifiers {
                    control: true,
                    ..Default::default()
                }
            )),
            Some(vec![0])
        );
        assert_eq!(
            super::terminal_key_bytes(&event("up", None, Modifiers::default())),
            Some(b"\x1b[A".to_vec())
        );
        assert_eq!(
            super::terminal_key_bytes(&event(
                "left",
                None,
                Modifiers {
                    control: true,
                    shift: true,
                    ..Default::default()
                }
            )),
            Some(b"\x1b[1;6D".to_vec())
        );
        assert_eq!(
            super::terminal_key_bytes(&event(
                "tab",
                None,
                Modifiers {
                    shift: true,
                    ..Default::default()
                }
            )),
            Some(b"\x1b[Z".to_vec())
        );
        assert_eq!(
            super::terminal_key_bytes(&event(
                "f5",
                None,
                Modifiers {
                    alt: true,
                    ..Default::default()
                }
            )),
            Some(b"\x1b[15;3~".to_vec())
        );
        assert_eq!(
            super::terminal_key_bytes(&event(
                "k",
                Some("k"),
                Modifiers {
                    platform: true,
                    ..Default::default()
                }
            )),
            None
        );
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn terminal_input_queue_is_bounded_fifo_and_reports_disconnect() {
        use std::sync::mpsc::sync_channel;

        let (sender, receiver) = sync_channel(2);
        super::enqueue_terminal_input(&sender, b"first".to_vec()).unwrap();
        super::enqueue_terminal_input(&sender, "ไทย🙂".as_bytes().to_vec()).unwrap();
        let full = super::enqueue_terminal_input(&sender, b"third".to_vec()).unwrap_err();
        assert_eq!(full.kind(), io::ErrorKind::WouldBlock);
        assert_eq!(receiver.recv().unwrap(), b"first");
        assert_eq!(receiver.recv().unwrap(), "ไทย🙂".as_bytes());
        drop(receiver);
        let closed = super::enqueue_terminal_input(&sender, b"after".to_vec()).unwrap_err();
        assert_eq!(closed.kind(), io::ErrorKind::BrokenPipe);

        let (sender, _receiver) = sync_channel(2);
        let oversized = super::enqueue_terminal_input(&sender, vec![0; 16 * 1024 + 1]).unwrap_err();
        assert_eq!(oversized.kind(), io::ErrorKind::InvalidInput);
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn terminal_writer_discards_queued_input_after_cancellation() {
        use std::sync::atomic::AtomicBool;
        use std::sync::{mpsc::sync_channel, Arc, Mutex};

        let (sender, receiver) = sync_channel(2);
        sender.send(b"unsafe-after-stop".to_vec()).unwrap();
        drop(sender);
        let cancelled = Arc::new(AtomicBool::new(true));
        let writes = Arc::new(Mutex::new(Vec::new()));
        let observed = Arc::clone(&writes);
        super::run_terminal_writer(receiver, cancelled, |bytes| {
            observed.lock().unwrap().push(bytes.to_vec());
            Ok(())
        });
        assert!(writes.lock().unwrap().is_empty());
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn failed_terminal_resize_does_not_mutate_parser_geometry() {
        let mut parser = vt100::Parser::new(24, 80, 10);
        let mut display = String::new();
        let mut status = String::new();
        let applied = super::apply_terminal_resize_outcome(
            &mut parser,
            &mut display,
            &mut status,
            super::TerminalResizeOutcome {
                cols: 120,
                rows: 40,
                boundary: None,
                result: Err("ioctl rejected".to_owned()),
            },
        );
        assert!(!applied);
        assert_eq!(parser.screen().size(), (24, 80));
        assert_eq!(status, "Terminal resize failed: ioctl rejected");
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn resize_boundary_parses_post_sigwinch_redraw_at_new_geometry() {
        let mut parser = vt100::Parser::new(2, 5, 10);
        let mut display = String::new();
        let mut status = String::new();
        let delta = PtyOutputDelta {
            bytes: b"abcde\x1b[2J\x1b[H123456789".to_vec(),
            next_cursor: 21,
            truncated: false,
            exited: false,
        };
        let applied = super::apply_terminal_update(
            &mut parser,
            &mut display,
            &mut status,
            &delta,
            Some(super::TerminalResizeOutcome {
                cols: 10,
                rows: 2,
                boundary: Some(5),
                result: Ok(()),
            }),
        );
        assert_eq!(applied, Some((true, 10, 2)));
        assert_eq!(parser.screen().size(), (2, 10));
        assert_eq!(display, "123456789");
    }
}
