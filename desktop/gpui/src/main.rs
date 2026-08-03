//! Native Codinal desktop shell.
//!
//! Development run:
//! `cargo build --manifest-path crates/codinal-runtime/Cargo.toml`
//! `CODINAL_NATIVE_RUNTIME=crates/codinal-runtime/target/debug/codinal-runtime CODINAL_DATA_DIR=/absolute/codinal/data cargo run --manifest-path desktop/gpui/Cargo.toml`
//! Debug builds boot an authenticated Rust runtime on an isolated snapshot.
//! Release builds boot the bundled native runtime against the production data.

mod accessibility;
mod composer;
mod context_panel;
mod conversation;
mod dock;
mod dock_view;
mod icons;
mod light_theme;
mod navigation;
#[cfg(target_os = "macos")]
mod secure_prompt;
mod session_projection;
mod session_stream;
mod settings_view;
mod shell;
mod shell_layout;
mod side_panel;
mod terminal_view;
mod ui_model;

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

pub mod workbench;

pub(crate) use accessibility::{disabled_reason_label, is_activation_key, stable_element_id};

use codinal_control_plane_client::{
    ActivityItem, ApprovalConfirmation, ApprovalOutcome, ControlPlaneClient, ModelProfile,
    PendingApproval, ProjectRootSummary, ProjectSummary, RuntimeCapabilities, SessionSummary,
    SourceAttachment, SourcePreview,
};
use codinal_native_host::control_client::OAuthRelayController;
use codinal_native_host::project_open::open_browser_url;
#[cfg(target_os = "macos")]
use codinal_native_host::pty::{PtyOutputBuffer, PtyOutputDelta, PtyRegistry};
#[cfg(target_os = "macos")]
use codinal_native_host::updater::run_restart_helper_if_requested;
#[cfg(target_os = "macos")]
use codinal_native_host::workspace::choose_workspace as choose_native_workspace;
use codinal_native_host::workspace::{
    choose_source_file as choose_native_source_file,
    choose_source_folder as choose_native_source_folder,
    choose_workspace_folders as choose_native_workspace_folders,
};
use codinal_native_host::{
    free_loopback_port, launch_native_runtime_with_bootstrap, launch_shadow_runtime_with_bootstrap,
    mint_session_token,
    secrets::{
        encode_empty_secret_bootstrap, encode_platform_secret_bootstrap_with_timeout,
        platform_provider_status_with_timeout, CustomProviderRecord, PlatformSecretVault,
        ProviderSecretStatus, ProviderSettingsController, SUPPORTED_PROVIDERS,
    },
    updater::{AvailableUpdate, NativeUpdater},
    NativeRuntime, ShadowRuntime,
};
use composer::composer_pane;
use context_panel::{approval_pane, environment_pane, sources_drawer};
use conversation::{conversation_pane, StarterCategory};
use dock::{DockAction, DockState};
use dock_view::{side_chat_sessions_for_parent, tools_panel};
use gpui::Task;
use gpui::{
    actions, deferred, div, point, px, rgb, rgba, size, App, AppContext, Bounds, Context,
    DragMoveEvent, EntityInputHandler, FocusHandle, FontWeight, InteractiveElement, IntoElement,
    KeyBinding, KeyDownEvent, MouseButton, MouseMoveEvent, ParentElement, Pixels, Point,
    PromptLevel, Render, StatefulInteractiveElement, Styled, TitlebarOptions, UTF16Selection,
    Window, WindowBounds, WindowOptions,
};
use icons::{icon, CodinalAssets, Icon};
use light_theme::{color, layout};
use navigation::session_pane;
use session_projection::parse_session_event;
use session_stream::{spawn_session_stream, SessionStreamUpdate, SessionStreamWorker};
use settings_view::{provider_settings_pane, updater_pane};
use shell::header;
use shell_layout::{
    load_panel_preferences, resize_panel_preferences, resolve_shell, save_panel_preferences,
    PanelPreferences, PanelResizeTarget, ShellRequest, WorkbenchPlacement, FILE_TREE_MAX_WIDTH,
    FILE_TREE_MIN_WIDTH, NAVIGATION_MAX_WIDTH, NAVIGATION_MIN_WIDTH, WORKBENCH_MAX_WIDTH,
    WORKBENCH_MIN_WIDTH,
};
use side_panel::{FilePreview, ReviewSnapshot, SidePanelTool, WorkspaceSnapshot};
use std::collections::BTreeSet;
use std::io;
use std::ops::Range;
use std::path::PathBuf;
#[cfg(target_os = "macos")]
use std::process::Command;
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
use ui_model::{UiAction, UiEffect, UiEvent, UiEventDisposition, UiState};
use workbench::Readiness;
use zeroize::Zeroizing;

actions!(
    codinal_shell,
    [
        NewTaskAction,
        ToggleContextAction,
        FocusNextAction,
        FocusPreviousAction
    ]
);

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

fn readiness_from_capabilities(capabilities: &RuntimeCapabilities) -> Readiness {
    if capabilities.start_turn {
        Readiness::Ready
    } else {
        Readiness::Disabled {
            reason: capabilities
                .run_disabled_reason
                .clone()
                .unwrap_or_else(|| "runtime_read_only".to_owned()),
        }
    }
}

fn capability_probe_status(capabilities: &RuntimeCapabilities) -> String {
    if capabilities.start_turn {
        "Provider capability verified".to_owned()
    } else {
        format!(
            "Provider capability check required · {}",
            disabled_reason_label(
                capabilities
                    .run_disabled_reason
                    .as_deref()
                    .unwrap_or("capability_probe_required")
            )
        )
    }
}

pub(crate) fn permission_profile_label(profile: PermissionProfile) -> &'static str {
    match profile {
        PermissionProfile::AskForApproval => "Ask for approval",
        PermissionProfile::ApproveForMe => "Approve for me",
        PermissionProfile::FullAccess => "Full access",
        PermissionProfile::Custom => "Custom",
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

fn projection_reload_is_current(
    current_generation: u64,
    current_session_id: Option<&str>,
    current_event_watermark: Option<u64>,
    expected_generation: u64,
    expected_session_id: Option<&str>,
    expected_event_watermark: Option<u64>,
) -> bool {
    current_generation == expected_generation
        && current_session_id == expected_session_id
        && current_event_watermark == expected_event_watermark
}

fn projection_reload_may_apply(watermark_is_current: bool, reload_pending: bool) -> bool {
    watermark_is_current && !reload_pending
}

fn session_reload_retry_delay(retry_count: u8) -> Option<Duration> {
    const DELAYS_MS: [u64; 5] = [250, 500, 1_000, 2_000, 4_000];
    DELAYS_MS
        .get(usize::from(retry_count))
        .copied()
        .map(Duration::from_millis)
}

fn session_reload_should_coalesce(load_in_flight: bool, retry_scheduled: bool) -> bool {
    load_in_flight || retry_scheduled
}

fn permission_required_panel_state(side_panel_open: bool) -> (bool, bool) {
    (true, side_panel_open)
}

fn side_tools_should_show(side_panel_open: bool, _approval_visible: bool) -> bool {
    side_panel_open
}

fn side_tool_focus_handoff_required(
    current_tool: Option<SidePanelTool>,
    requested_tool: SidePanelTool,
    context_panel_displaced: bool,
) -> bool {
    context_panel_displaced || current_tool != Some(requested_tool)
}

#[cfg(test)]
fn approval_event_requires_reload(pending: &Option<Result<Vec<PendingApproval>, String>>) -> bool {
    !matches!(pending, Some(Ok(_)))
}

fn context_panel_should_show(context_panel_open: bool, pending_approval: bool) -> bool {
    context_panel_open || pending_approval
}

pub(crate) fn composer_input_is_enabled(
    has_selected_session: bool,
    approval_pending: bool,
    start_turn: bool,
    turn_in_flight: bool,
    turn_command_in_flight: bool,
) -> bool {
    has_selected_session
        && !approval_pending
        && start_turn
        && !turn_in_flight
        && !turn_command_in_flight
}

fn approval_completion_is_current_for_request(
    current_generation: u64,
    current_session_id: Option<&str>,
    current_approval_id: Option<&str>,
    expected_generation: u64,
    expected_session_id: Option<&str>,
    expected_approval_id: Option<&str>,
) -> bool {
    approval_completion_is_current(
        current_generation,
        current_session_id,
        expected_generation,
        expected_session_id,
    ) && current_approval_id == expected_approval_id
}

fn approval_can_be_approved(tool_name: Option<&str>) -> bool {
    tool_name == Some("apply_patch")
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ShellShortcut {
    NewTask,
    ToggleContext,
    Search,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ShellFocusDirection {
    Next,
    Previous,
}

fn shell_shortcut(event: &KeyDownEvent) -> Option<ShellShortcut> {
    if !event.keystroke.modifiers.platform {
        return None;
    }
    match event.keystroke.key.to_ascii_lowercase().as_str() {
        "n" => Some(ShellShortcut::NewTask),
        "k" => Some(ShellShortcut::ToggleContext),
        "f" => Some(ShellShortcut::Search),
        _ => None,
    }
}

fn shell_focus_direction(event: &KeyDownEvent) -> Option<ShellFocusDirection> {
    let modifiers = event.keystroke.modifiers;
    if modifiers.platform || modifiers.control || modifiers.alt {
        return None;
    }

    if event.keystroke.key.eq_ignore_ascii_case("tab") {
        Some(if modifiers.shift {
            ShellFocusDirection::Previous
        } else {
            ShellFocusDirection::Next
        })
    } else {
        None
    }
}

fn terminal_should_capture_key(event: &KeyDownEvent) -> bool {
    if shell_shortcut(event).is_some() {
        return false;
    }
    let modifiers = event.keystroke.modifiers;
    side_panel::tool_for_shortcut(
        &event.keystroke.key,
        modifiers.platform,
        modifiers.control,
        modifiers.alt,
        modifiers.shift,
    )
    .is_none()
}

pub(crate) fn terminal_should_handle_key(terminal_has_focus: bool, event: &KeyDownEvent) -> bool {
    terminal_has_focus && terminal_should_capture_key(event)
}

pub(crate) struct WorkspacePrototype {
    _runtime: DesktopRuntime,
    client: Arc<ControlPlaneClient>,
    runtime_capabilities: RuntimeCapabilities,
    approval_session_id: Option<String>,
    ui: UiState,
    session_count: usize,
    sessions: Vec<SessionSummary>,
    projects: Vec<ProjectSummary>,
    selected_session_id: Option<String>,
    selected_project_id: Option<String>,
    mode_menu_open: bool,
    session_menu_open: bool,
    session_rename_open: bool,
    session_delete_confirm: bool,
    session_action_in_flight: bool,
    session_action_status: String,
    session_rename_text: String,
    session_rename_focus: FocusHandle,
    session_rename_marked_text: String,
    session_rename_marked_selection: Range<usize>,
    project_hover_id: Option<String>,
    project_hover_generation: u64,
    project_hover_task: Option<Task<()>>,
    project_menu_id: Option<String>,
    expanded_project_ids: BTreeSet<String>,
    chats_expanded: bool,
    project_dialog_open: bool,
    project_remove_confirm: Option<String>,
    project_archive_confirm: Option<String>,
    project_editing_id: Option<String>,
    project_name_text: String,
    project_roots_text: String,
    project_name_marked_text: String,
    project_name_marked_selection: Range<usize>,
    project_roots_marked_text: String,
    project_roots_marked_selection: Range<usize>,
    project_name_focus: FocusHandle,
    project_roots_focus: FocusHandle,
    project_save_in_flight: bool,
    project_status: String,
    search_open: bool,
    search_text: String,
    search_results: Vec<SessionSummary>,
    search_status: String,
    search_generation: u64,
    search_focus: FocusHandle,
    search_marked_text: String,
    search_marked_selection: Range<usize>,
    source_attachments: Vec<SourceAttachment>,
    sources_status: String,
    sources_generation: u64,
    source_menu_open: bool,
    source_operation_in_flight: bool,
    sources_drawer_open: bool,
    source_preview: Option<SourcePreview>,
    source_preview_status: String,
    source_preview_generation: u64,
    activity_open: bool,
    activity_items: Vec<ActivityItem>,
    activity_status: String,
    activity_generation: u64,
    permission_profile: PermissionProfile,
    permission_menu_open: bool,
    selected_model_profile: ModelProfile,
    model_menu_open: bool,
    session_status: String,
    session_selection_generation: u64,
    session_load_generation: u64,
    session_load_in_flight: bool,
    session_reload_pending_reason: Option<&'static str>,
    session_reload_retry_count: u8,
    session_reload_retry_task: Option<Task<()>>,
    session_event_generation: u64,
    session_event_task: Option<Task<()>>,
    session_event_worker: Option<SessionStreamWorker>,
    provider_settings: String,
    provider_settings_controller: Arc<ProviderSettingsController>,
    provider_delete_targets: Vec<ProviderDeleteTarget>,
    provider_edit_targets: Vec<String>,
    custom_provider_edit_targets: Vec<CustomProviderEditTarget>,
    provider_operation_in_flight: bool,
    provider_probe_in_flight: bool,
    provider_probe_status: String,
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
    shell_focus: FocusHandle,
    context_panel_trigger_focus: FocusHandle,
    side_panel_trigger_focus: FocusHandle,
    terminal_focus: FocusHandle,
    terminal_marked_text: String,
    terminal_marked_selection: Range<usize>,
    composer_focus: FocusHandle,
    composer_text: String,
    starter_category: Option<StarterCategory>,
    composer_marked_text: String,
    composer_marked_selection: Range<usize>,
    input_target: InputTarget,
    navigation_open: bool,
    panel_preferences: PanelPreferences,
    panel_preferences_path: PathBuf,
    panel_preferences_save_task: Option<Task<()>>,
    active_panel_resize: Option<PanelResizeTarget>,
    context_panel_open: bool,
    dock: DockState,
    review_snapshot: Option<ReviewSnapshot>,
    review_status: String,
    review_generation: u64,
    workspace_snapshot: Option<WorkspaceSnapshot>,
    files_status: String,
    files_generation: u64,
    file_root_menu_open: bool,
    selected_root_path: Option<String>,
    file_preview: Option<FilePreview>,
    file_preview_status: String,
    file_preview_generation: u64,
    browser_url: String,
    browser_status: String,
    side_chat_status: String,
    side_chat_parent_id: Option<String>,
    side_chat_in_flight: bool,
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

struct NativeRuntimeStart {
    client: ControlPlaneClient,
    runtime: DesktopRuntime,
    provider_settings_controller: Arc<ProviderSettingsController>,
    oauth_relay: Arc<OAuthRelayController>,
    secret_bootstrap_error: Option<String>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum InputTarget {
    Composer,
    Terminal,
    ProjectName,
    ProjectRoots,
    SessionRename,
    Search,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum PermissionProfile {
    AskForApproval,
    ApproveForMe,
    FullAccess,
    Custom,
}

#[derive(Clone, Copy, Debug)]
struct DraggedNavigationDivider;

#[derive(Clone, Copy, Debug)]
struct DraggedWorkbenchDivider;

#[derive(Clone, Copy, Debug)]
pub(crate) struct DraggedFileTreeDivider;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum TerminalState {
    Closed,
    Opening,
    Running,
    Stopping,
    Exited,
    Failed,
}

impl TerminalState {
    pub(crate) fn can_open(self) -> bool {
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
pub(crate) enum ProviderDeleteTarget {
    Standard(String),
    Custom(String),
}

#[derive(Clone)]
pub(crate) struct CustomProviderEditTarget {
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

pub(crate) fn terminal_grid_for_bounds(bounds: Bounds<Pixels>) -> (u16, u16) {
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

pub(crate) fn should_request_terminal_resize(
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
    fn clear_project_hover(&mut self) {
        self.project_hover_generation = self.project_hover_generation.wrapping_add(1);
        self.project_hover_id = None;
        let _ = self.project_hover_task.take();
    }

    pub(crate) fn toggle_context_panel(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self.context_panel_open = !self.context_panel_open;
        if !self.context_panel_open {
            self.context_panel_trigger_focus.focus(window, cx);
        }
        cx.notify();
    }

    pub(crate) fn open_project_dialog(
        &mut self,
        project: Option<ProjectSummary>,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        self.project_editing_id = project.as_ref().map(|project| project.project_id.clone());
        self.project_name_text = project
            .as_ref()
            .map(|project| project.name.clone())
            .unwrap_or_default();
        self.project_roots_text = project
            .as_ref()
            .map(|project| {
                project
                    .roots
                    .iter()
                    .map(|root| root.path.as_str())
                    .collect::<Vec<_>>()
                    .join("\n")
            })
            .unwrap_or_default();
        self.project_name_marked_text.clear();
        self.project_name_marked_selection = 0..0;
        self.project_roots_marked_text.clear();
        self.project_roots_marked_selection = 0..0;
        self.project_dialog_open = true;
        self.clear_project_hover();
        self.project_menu_id = None;
        self.project_status.clear();
        self.input_target = InputTarget::ProjectName;
        self.project_name_focus.focus(window, cx);
        cx.notify();
    }

    pub(crate) fn close_project_dialog(&mut self, cx: &mut Context<Self>) {
        if !self.project_save_in_flight {
            self.project_dialog_open = false;
            self.project_editing_id = None;
            self.project_status.clear();
            self.input_target = InputTarget::Composer;
            cx.notify();
        }
    }

    pub(crate) fn focus_project_name(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self.input_target = InputTarget::ProjectName;
        self.project_name_focus.focus(window, cx);
    }

    pub(crate) fn focus_project_roots(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self.input_target = InputTarget::ProjectRoots;
        self.project_roots_focus.focus(window, cx);
    }

    pub(crate) fn focus_search(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self.input_target = InputTarget::Search;
        self.search_focus.focus(window, cx);
    }

    pub(crate) fn focus_session_rename(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self.input_target = InputTarget::SessionRename;
        self.session_rename_focus.focus(window, cx);
    }

    pub(crate) fn toggle_session_menu(&mut self, cx: &mut Context<Self>) {
        if self.selected_session_id.is_none() {
            self.session_action_status = "Select a chat to see chat actions".to_owned();
            cx.notify();
            return;
        }
        self.session_menu_open = !self.session_menu_open;
        self.mode_menu_open = false;
        self.project_menu_id = None;
        self.clear_project_hover();
        cx.notify();
    }

    pub(crate) fn open_session_rename(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        let Some(session_id) = self.selected_session_id.as_deref() else {
            return;
        };
        let Some(session) = self
            .sessions
            .iter()
            .find(|session| session.session_id == session_id)
        else {
            return;
        };
        self.session_rename_text = session.title.clone();
        self.session_rename_marked_text.clear();
        self.session_rename_marked_selection = 0..0;
        self.session_rename_open = true;
        self.session_menu_open = false;
        self.session_action_status.clear();
        self.input_target = InputTarget::SessionRename;
        self.session_rename_focus.focus(window, cx);
        cx.notify();
    }

    pub(crate) fn close_session_rename(&mut self, cx: &mut Context<Self>) {
        if self.session_action_in_flight {
            return;
        }
        self.session_rename_open = false;
        self.session_action_status.clear();
        self.input_target = InputTarget::Composer;
        cx.notify();
    }

    pub(crate) fn save_session_rename(&mut self, cx: &mut Context<Self>) {
        if self.session_action_in_flight {
            return;
        }
        let Some(session_id) = self.selected_session_id.clone() else {
            return;
        };
        let title = self.session_rename_text.trim().to_owned();
        if title.is_empty() {
            self.session_action_status = "Chat name is required".to_owned();
            cx.notify();
            return;
        }
        self.session_action_in_flight = true;
        self.session_action_status = "Renaming chat…".to_owned();
        let client = Arc::clone(&self.client);
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move { client.update_session(&session_id, Some(&title), None, None) })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.session_action_in_flight = false;
                match result {
                    Ok(session) => {
                        this.replace_session_summary(session);
                        this.session_rename_open = false;
                        this.session_action_status = "Chat renamed".to_owned();
                        this.input_target = InputTarget::Composer;
                    }
                    Err(error) => {
                        this.session_action_status = format!("Rename failed · {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn toggle_selected_session_pin(&mut self, cx: &mut Context<Self>) {
        if self.session_action_in_flight || !self.runtime_capabilities.mutations {
            return;
        }
        let Some(session) = self.selected_session_id.as_deref().and_then(|id| {
            self.sessions
                .iter()
                .find(|session| session.session_id == id)
        }) else {
            return;
        };
        let session_id = session.session_id.clone();
        let pinned = !session.pinned;
        self.session_menu_open = false;
        self.session_action_in_flight = true;
        self.session_action_status = if pinned {
            "Pinning chat…".to_owned()
        } else {
            "Unpinning chat…".to_owned()
        };
        let client = Arc::clone(&self.client);
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move { client.update_session(&session_id, None, Some(pinned), None) })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.session_action_in_flight = false;
                match result {
                    Ok(session) => {
                        this.replace_session_summary(session);
                        this.session_action_status = if pinned {
                            "Chat pinned".to_owned()
                        } else {
                            "Chat unpinned".to_owned()
                        };
                    }
                    Err(error) => {
                        this.session_action_status = format!("Chat pin failed · {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn move_selected_session(
        &mut self,
        target_project_id: Option<String>,
        cx: &mut Context<Self>,
    ) {
        if self.session_action_in_flight || !self.runtime_capabilities.mutations {
            return;
        }
        let Some(session) = self.selected_session_id.as_deref().and_then(|id| {
            self.sessions
                .iter()
                .find(|session| session.session_id == id)
        }) else {
            return;
        };
        let session_id = session.session_id.clone();
        let current_project_id = session.project_id.clone();
        if current_project_id == target_project_id {
            self.session_menu_open = false;
            cx.notify();
            return;
        }
        self.session_menu_open = false;
        self.session_action_in_flight = true;
        self.session_action_status = "Moving chat…".to_owned();
        let client = Arc::clone(&self.client);
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move {
                    if let Some(project_id) = target_project_id.as_deref() {
                        client.assign_session_to_project(project_id, &session_id)?;
                    } else if let Some(project_id) = current_project_id.as_deref() {
                        client.remove_session_from_project(project_id, &session_id)?;
                    }
                    Ok::<_, io::Error>((client.list_sessions()?, client.list_projects()?))
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.session_action_in_flight = false;
                match result {
                    Ok((sessions, projects)) => {
                        this.sessions = sessions;
                        this.projects = projects;
                        this.selected_project_id = this
                            .selected_session_id
                            .as_deref()
                            .and_then(|id| {
                                this.sessions
                                    .iter()
                                    .find(|session| session.session_id == id)
                            })
                            .and_then(|session| session.project_id.clone());
                        this.session_action_status = "Chat moved".to_owned();
                    }
                    Err(error) => {
                        this.session_action_status = format!("Move failed · {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn archive_selected_session(&mut self, cx: &mut Context<Self>) {
        if self.session_action_in_flight || !self.runtime_capabilities.mutations {
            return;
        }
        let Some(session_id) = self.selected_session_id.clone() else {
            return;
        };
        self.session_menu_open = false;
        self.session_action_in_flight = true;
        let restoring = self
            .selected_session_id
            .as_deref()
            .and_then(|id| {
                self.sessions
                    .iter()
                    .find(|session| session.session_id == id)
            })
            .is_some_and(|session| session.archived);
        self.session_action_status = if restoring {
            "Restoring chat…".to_owned()
        } else {
            "Archiving chat…".to_owned()
        };
        let client = Arc::clone(&self.client);
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move {
                    client.update_session(&session_id, None, None, Some(!restoring))?;
                    Ok::<_, io::Error>((client.list_sessions()?, client.list_projects()?))
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.session_action_in_flight = false;
                match result {
                    Ok((sessions, projects)) => {
                        this.sessions = sessions;
                        this.projects = projects;
                        this.session_count = this
                            .sessions
                            .iter()
                            .filter(|session| {
                                !session.archived && session.origin.as_deref() != Some("side_chat")
                            })
                            .count();
                        if restoring {
                            this.session_action_status = "Chat restored".to_owned();
                        } else {
                            this.clear_selected_session_projection();
                            this.session_action_status = "Chat archived".to_owned();
                        }
                    }
                    Err(error) => {
                        this.session_action_status = format!("Archive failed · {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn request_delete_session(&mut self, cx: &mut Context<Self>) {
        if self.selected_session_id.is_none() || !self.runtime_capabilities.mutations {
            return;
        }
        self.session_menu_open = false;
        self.session_delete_confirm = true;
        cx.notify();
    }

    pub(crate) fn cancel_delete_session(&mut self, cx: &mut Context<Self>) {
        if self.session_action_in_flight {
            return;
        }
        self.session_delete_confirm = false;
        cx.notify();
    }

    pub(crate) fn delete_selected_session(&mut self, cx: &mut Context<Self>) {
        if self.session_action_in_flight {
            return;
        }
        let Some(session_id) = self.selected_session_id.clone() else {
            return;
        };
        self.session_delete_confirm = false;
        self.session_action_in_flight = true;
        self.session_action_status = "Deleting chat…".to_owned();
        let client = Arc::clone(&self.client);
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move {
                    client.delete_session(&session_id)?;
                    Ok::<_, io::Error>((client.list_sessions()?, client.list_projects()?))
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.session_action_in_flight = false;
                match result {
                    Ok((sessions, projects)) => {
                        this.sessions = sessions;
                        this.projects = projects;
                        this.session_count = this
                            .sessions
                            .iter()
                            .filter(|session| {
                                !session.archived && session.origin.as_deref() != Some("side_chat")
                            })
                            .count();
                        this.clear_selected_session_projection();
                        this.session_action_status = "Chat deleted".to_owned();
                    }
                    Err(error) => {
                        this.session_action_status = format!("Delete failed · {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    fn replace_session_summary(&mut self, session: SessionSummary) {
        if let Some(existing) = self
            .sessions
            .iter_mut()
            .find(|existing| existing.session_id == session.session_id)
        {
            *existing = session.clone();
        } else {
            self.sessions.push(session.clone());
        }
        self.selected_project_id = session.project_id.clone();
    }

    fn clear_selected_session_projection(&mut self) {
        self.session_event_generation = self.session_event_generation.wrapping_add(1);
        let _ = self.session_event_task.take();
        let _ = self.session_event_worker.take();
        self.dock.dispatch(DockAction::SelectSession(None));
        self.selected_session_id = None;
        self.selected_project_id = None;
        self.side_chat_parent_id = None;
        self.approval_session_id = None;
        self.file_root_menu_open = false;
        self.selected_root_path = None;
        self.source_attachments.clear();
        self.source_preview = None;
        self.sources_drawer_open = false;
        self.review_snapshot = None;
        self.workspace_snapshot = None;
        self.file_preview = None;
        let _ = self.ui.dispatch(UiAction::SelectSession);
        self.session_status = "Select a chat to begin".to_owned();
    }

    pub(crate) fn save_project(&mut self, cx: &mut Context<Self>) {
        if self.project_save_in_flight {
            return;
        }
        if !self.runtime_capabilities.mutations {
            self.project_status = "Project changes require the Rust writer".to_owned();
            cx.notify();
            return;
        }
        let name = self.project_name_text.trim().to_owned();
        let roots = self
            .project_roots_text
            .lines()
            .map(str::trim)
            .filter(|root| !root.is_empty())
            .map(str::to_owned)
            .collect::<Vec<_>>();
        if name.is_empty() {
            self.project_status = "Project name is required".to_owned();
            cx.notify();
            return;
        }
        let editing_id = self.project_editing_id.clone();
        let client = Arc::clone(&self.client);
        self.project_save_in_flight = true;
        self.project_status = "Saving project…".to_owned();
        cx.notify();
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move {
                    match editing_id {
                        Some(project_id) => client.update_project(&project_id, &name, &roots),
                        None => client.create_project(&name, &roots),
                    }
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.project_save_in_flight = false;
                match result {
                    Ok(project) => {
                        if let Some(existing) = this
                            .projects
                            .iter_mut()
                            .find(|existing| existing.project_id == project.project_id)
                        {
                            *existing = project;
                        } else {
                            this.projects.insert(0, project);
                        }
                        this.project_dialog_open = false;
                        this.project_editing_id = None;
                        this.project_status = "Project saved".to_owned();
                        this.input_target = InputTarget::Composer;
                    }
                    Err(error) => {
                        this.project_status = format!("Project save failed: {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn add_project_folder(&mut self, cx: &mut Context<Self>) {
        #[cfg(target_os = "macos")]
        let selected = choose_native_workspace_folders();
        #[cfg(not(target_os = "macos"))]
        let selected: io::Result<Vec<PathBuf>> = Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "native folder picker is only available on macOS",
        ));
        match selected {
            Ok(paths) => {
                for path in paths {
                    let path = path.to_string_lossy();
                    if self.project_roots_text.lines().any(|root| root == path) {
                        continue;
                    }
                    if !self.project_roots_text.trim().is_empty() {
                        self.project_roots_text.push('\n');
                    }
                    self.project_roots_text.push_str(&path);
                }
                self.project_status.clear();
            }
            Err(error) if error.kind() == io::ErrorKind::Interrupted => {
                self.project_status = "Folder selection cancelled".to_owned();
            }
            Err(error) => {
                self.project_status = format!("Folder selection failed: {error}");
            }
        }
        cx.notify();
    }

    pub(crate) fn toggle_project_menu(&mut self, project_id: String, cx: &mut Context<Self>) {
        self.clear_project_hover();
        self.mode_menu_open = false;
        self.project_menu_id = if self.project_menu_id.as_deref() == Some(project_id.as_str()) {
            None
        } else {
            Some(project_id)
        };
        cx.notify();
    }

    pub(crate) fn toggle_mode_menu(&mut self, cx: &mut Context<Self>) {
        self.mode_menu_open = !self.mode_menu_open;
        if self.mode_menu_open {
            self.session_menu_open = false;
            self.project_menu_id = None;
            self.activity_open = false;
            self.permission_menu_open = false;
            self.model_menu_open = false;
            self.clear_project_hover();
        }
        cx.notify();
    }

    pub(crate) fn close_mode_menu(&mut self, cx: &mut Context<Self>) {
        if self.mode_menu_open {
            self.mode_menu_open = false;
            cx.notify();
        }
    }

    pub(crate) fn toggle_project_expanded(&mut self, project_id: String, cx: &mut Context<Self>) {
        if !self.expanded_project_ids.insert(project_id.clone()) {
            self.expanded_project_ids.remove(&project_id);
        }
        cx.notify();
    }

    pub(crate) fn toggle_chats_expanded(&mut self, cx: &mut Context<Self>) {
        self.chats_expanded = !self.chats_expanded;
        cx.notify();
    }

    pub(crate) fn set_project_hover(
        &mut self,
        project_id: String,
        hovered: bool,
        cx: &mut Context<Self>,
    ) {
        if hovered {
            if self.project_menu_id.is_none() {
                self.clear_project_hover();
                let generation = self.project_hover_generation;
                self.project_hover_task = Some(cx.spawn(async move |this, cx| {
                    cx.background_executor()
                        .timer(Duration::from_millis(180))
                        .await;
                    let _ = this.update(cx, |this, cx| {
                        if this.project_hover_generation == generation
                            && this.project_menu_id.is_none()
                        {
                            this.project_hover_id = Some(project_id);
                            cx.notify();
                        }
                    });
                }));
            }
        } else {
            self.clear_project_hover();
        }
        cx.notify();
    }

    pub(crate) fn select_project(&mut self, project_id: String, cx: &mut Context<Self>) {
        if !self
            .projects
            .iter()
            .any(|project| project.project_id == project_id)
        {
            return;
        }
        if self.selected_session_id.is_some() {
            self.clear_selected_session_projection();
        }
        self.selected_project_id = Some(project_id);
        self.project_menu_id = None;
        self.clear_project_hover();
        self.context_panel_open = false;
        self.session_status = "Project selected · choose New chat to start".to_owned();
        if !self.dock.open() {
            self.dock.dispatch(DockAction::Toggle);
        }
        if self.dock.open_tabs().is_empty() {
            self.dock.dispatch(DockAction::TogglePicker);
        }
        match self.dock.active() {
            Some(SidePanelTool::Review) => self.refresh_review(cx),
            Some(SidePanelTool::Files) => self.refresh_files(cx),
            _ => cx.notify(),
        }
    }

    pub(crate) fn clear_project_selection(&mut self, cx: &mut Context<Self>) {
        self.selected_project_id = None;
        self.project_menu_id = None;
        cx.notify();
    }

    pub(crate) fn open_search(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self.search_open = true;
        self.search_text.clear();
        self.search_results.clear();
        self.search_status = "Search chats by title, path, or session".to_owned();
        self.search_generation = self.search_generation.wrapping_add(1);
        self.input_target = InputTarget::Search;
        self.search_focus.focus(window, cx);
        cx.notify();
    }

    pub(crate) fn close_search(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if !self.search_open {
            return;
        }
        self.search_open = false;
        self.search_generation = self.search_generation.wrapping_add(1);
        self.input_target = InputTarget::Composer;
        self.composer_focus.focus(window, cx);
        cx.notify();
    }

    pub(crate) fn refresh_search_results(&mut self, cx: &mut Context<Self>) {
        let query = self.search_text.trim().to_owned();
        self.search_generation = self.search_generation.wrapping_add(1);
        let generation = self.search_generation;
        if query.is_empty() {
            self.search_results.clear();
            self.search_status = "Search chats by title, path, or session".to_owned();
            cx.notify();
            return;
        }
        self.search_results.clear();
        self.search_status = "Searching chats…".to_owned();
        let client = Arc::clone(&self.client);
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move { client.search_sessions(&query, 20) })
                .await;
            let _ = this.update(cx, |this, cx| {
                if !this.search_open || this.search_generation != generation {
                    return;
                }
                match result {
                    Ok(results) if results.is_empty() => {
                        this.search_status = "No matching chats".to_owned();
                    }
                    Ok(results) => {
                        this.search_status = format!("{} matching chat(s)", results.len());
                        this.search_results = results;
                    }
                    Err(error) => {
                        this.search_status = format!("Search unavailable · {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn select_search_result(
        &mut self,
        session_id: String,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        self.close_search(window, cx);
        self.select_session(session_id, cx);
    }

    pub(crate) fn refresh_sources(&mut self, cx: &mut Context<Self>) {
        self.source_preview_generation = self.source_preview_generation.wrapping_add(1);
        self.source_preview = None;
        self.source_preview_status = "Select a source to preview".to_owned();
        let Some(session_id) = self.selected_session_id.clone() else {
            self.source_attachments.clear();
            self.sources_status = "Select a chat to view source attachments".to_owned();
            cx.notify();
            return;
        };
        self.sources_generation = self.sources_generation.wrapping_add(1);
        let generation = self.sources_generation;
        self.sources_status = "Loading sources…".to_owned();
        self.source_attachments.clear();
        let client = Arc::clone(&self.client);
        let request_session_id = session_id.clone();
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move { client.list_source_attachments(&request_session_id) })
                .await;
            let _ = this.update(cx, |this, cx| {
                if this.sources_generation != generation
                    || this.selected_session_id.as_deref() != Some(session_id.as_str())
                {
                    return;
                }
                match result {
                    Ok(sources) => {
                        this.sources_status = if sources.is_empty() {
                            "No source attachments in this chat".to_owned()
                        } else {
                            format!("{} source attachment(s)", sources.len())
                        };
                        this.source_attachments = sources;
                    }
                    Err(error) => {
                        this.sources_status = format!("Sources unavailable · {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn toggle_source_menu(&mut self, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.mutations {
            self.sources_status = format!(
                "Add source unavailable · {}",
                disabled_reason_label(
                    self.runtime_capabilities
                        .mutation_disabled_reason
                        .as_deref()
                        .unwrap_or("runtime_read_only")
                )
            );
            cx.notify();
            return;
        }
        self.source_menu_open = !self.source_menu_open;
        cx.notify();
    }

    pub(crate) fn add_source(&mut self, folder: bool, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.mutations
            || self.source_operation_in_flight
            || self.selected_session_id.is_none()
        {
            return;
        }
        self.source_menu_open = false;
        let selected = if folder {
            choose_native_source_folder()
        } else {
            choose_native_source_file()
        };
        let path = match selected {
            Ok(path) => path,
            Err(error) if error.kind() == io::ErrorKind::Interrupted => {
                self.sources_status = "Source selection cancelled".to_owned();
                cx.notify();
                return;
            }
            Err(error) => {
                self.sources_status = format!("Source selection failed · {error}");
                cx.notify();
                return;
            }
        };
        let Some(session_id) = self.selected_session_id.clone() else {
            return;
        };
        self.source_operation_in_flight = true;
        self.sources_generation = self.sources_generation.wrapping_add(1);
        let generation = self.sources_generation;
        self.sources_status = format!("Attaching {}…", path.display());
        let client = Arc::clone(&self.client);
        let request_session_id = session_id.clone();
        let request_path = path.clone();
        cx.notify();
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move {
                    client.attach_source(&request_session_id, &request_path.to_string_lossy())
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                if this.sources_generation != generation
                    || this.selected_session_id.as_deref() != Some(session_id.as_str())
                {
                    return;
                }
                this.source_operation_in_flight = false;
                match result {
                    Ok(source) => {
                        this.source_attachments
                            .retain(|existing| existing.attachment_id != source.attachment_id);
                        this.source_attachments.push(source.clone());
                        this.sources_status = format!("Attached {}", source.name);
                    }
                    Err(error) => {
                        this.sources_status = format!("Source attach failed · {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn remove_source(&mut self, attachment_id: String, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.mutations || self.source_operation_in_flight {
            return;
        }
        let Some(session_id) = self.selected_session_id.clone() else {
            return;
        };
        self.source_operation_in_flight = true;
        self.sources_generation = self.sources_generation.wrapping_add(1);
        let generation = self.sources_generation;
        self.sources_status = "Removing source attachment…".to_owned();
        let client = Arc::clone(&self.client);
        let request_session_id = session_id.clone();
        let request_attachment_id = attachment_id.clone();
        cx.notify();
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move {
                    client.remove_source_attachment(&request_session_id, &request_attachment_id)
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                if this.sources_generation != generation
                    || this.selected_session_id.as_deref() != Some(session_id.as_str())
                {
                    return;
                }
                this.source_operation_in_flight = false;
                match result {
                    Ok(()) => {
                        this.source_attachments
                            .retain(|source| source.attachment_id != attachment_id);
                        this.sources_status = if this.source_attachments.is_empty() {
                            "No source attachments in this chat".to_owned()
                        } else {
                            format!("{} source attachment(s)", this.source_attachments.len())
                        };
                    }
                    Err(error) => {
                        this.sources_status = format!("Source remove failed · {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn retry_source(&mut self, attachment_id: String, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.mutations || self.source_operation_in_flight {
            return;
        }
        let Some(session_id) = self.selected_session_id.clone() else {
            return;
        };
        self.source_operation_in_flight = true;
        self.sources_generation = self.sources_generation.wrapping_add(1);
        let generation = self.sources_generation;
        self.sources_status = "Retrying source attachment…".to_owned();
        let client = Arc::clone(&self.client);
        let request_session_id = session_id.clone();
        let request_attachment_id = attachment_id.clone();
        cx.notify();
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move {
                    client.retry_source_attachment(&request_session_id, &request_attachment_id)
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                if this.sources_generation != generation
                    || this.selected_session_id.as_deref() != Some(session_id.as_str())
                {
                    return;
                }
                this.source_operation_in_flight = false;
                match result {
                    Ok(source) => {
                        if let Some(existing) = this
                            .source_attachments
                            .iter_mut()
                            .find(|existing| existing.attachment_id == source.attachment_id)
                        {
                            *existing = source.clone();
                        }
                        this.sources_status = format!("{} · {}", source.name, source.status);
                    }
                    Err(error) => {
                        this.sources_status = format!("Source retry failed · {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn open_sources_drawer(&mut self, cx: &mut Context<Self>) {
        self.sources_drawer_open = true;
        cx.notify();
    }

    pub(crate) fn preview_source(&mut self, attachment_id: String, cx: &mut Context<Self>) {
        let Some(session_id) = self.selected_session_id.clone() else {
            return;
        };
        if !self
            .source_attachments
            .iter()
            .any(|source| source.attachment_id == attachment_id)
        {
            return;
        }
        self.sources_drawer_open = true;
        self.source_preview_generation = self.source_preview_generation.wrapping_add(1);
        let generation = self.source_preview_generation;
        self.source_preview = None;
        self.source_preview_status = "Loading source preview…".to_owned();
        let client = Arc::clone(&self.client);
        let request_session_id = session_id.clone();
        let request_attachment_id = attachment_id;
        cx.notify();
        cx.spawn(async move |this, cx| {
            let result =
                cx.background_executor()
                    .spawn(async move {
                        client.preview_source(&request_session_id, &request_attachment_id)
                    })
                    .await;
            let _ = this.update(cx, |this, cx| {
                if this.source_preview_generation != generation
                    || this.selected_session_id.as_deref() != Some(session_id.as_str())
                {
                    return;
                }
                match result {
                    Ok(preview) => {
                        this.source_preview_status = if preview.binary {
                            "Binary source · metadata only".to_owned()
                        } else if preview.truncated {
                            "Preview loaded · bounded at 256 KiB".to_owned()
                        } else {
                            "Preview loaded".to_owned()
                        };
                        this.source_preview = Some(preview);
                    }
                    Err(error) => {
                        this.source_preview_status =
                            format!("Source preview unavailable · {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn close_sources_drawer(&mut self, cx: &mut Context<Self>) {
        self.sources_drawer_open = false;
        self.source_preview_generation = self.source_preview_generation.wrapping_add(1);
        self.source_preview = None;
        self.source_preview_status = "Select a source to preview".to_owned();
        cx.notify();
    }

    pub(crate) fn toggle_activity(&mut self, cx: &mut Context<Self>) {
        self.activity_open = !self.activity_open;
        if self.activity_open {
            self.refresh_activity(cx);
        } else {
            cx.notify();
        }
    }

    pub(crate) fn refresh_activity(&mut self, cx: &mut Context<Self>) {
        self.activity_generation = self.activity_generation.wrapping_add(1);
        let generation = self.activity_generation;
        self.activity_status = "Loading activity…".to_owned();
        let client = Arc::clone(&self.client);
        cx.notify();
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move { client.list_activity() })
                .await;
            let _ = this.update(cx, |this, cx| {
                if this.activity_generation != generation || !this.activity_open {
                    return;
                }
                match result {
                    Ok(items) => {
                        this.activity_status = if items.is_empty() {
                            "No new activity".to_owned()
                        } else {
                            format!("{} activity item(s)", items.len())
                        };
                        this.activity_items = items;
                    }
                    Err(error) => {
                        this.activity_status = format!("Activity unavailable · {error}");
                        this.activity_items.clear();
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn mark_activity_read(&mut self, cx: &mut Context<Self>) {
        if self.activity_items.is_empty() {
            return;
        }
        let client = Arc::clone(&self.client);
        self.activity_status = "Marking activity as read…".to_owned();
        cx.notify();
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move { client.mark_activity_read() })
                .await;
            let _ = this.update(cx, |this, cx| {
                match result {
                    Ok(()) => {
                        for item in &mut this.activity_items {
                            item.unread = false;
                        }
                        this.activity_status = "Activity marked as read".to_owned();
                    }
                    Err(error) => {
                        this.activity_status = format!("Activity read failed · {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn pin_project(&mut self, project_id: String, pinned: bool, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.mutations || self.project_save_in_flight {
            return;
        }
        let client = Arc::clone(&self.client);
        self.project_menu_id = None;
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move {
                    client.set_project_pinned(&project_id, pinned)?;
                    client.list_projects()
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                match result {
                    Ok(projects) => this.projects = projects,
                    Err(error) => this.project_status = format!("Project pin failed: {error}"),
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn request_archive_project(&mut self, project_id: String, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.mutations || self.session_action_in_flight {
            return;
        }
        self.project_menu_id = None;
        self.project_archive_confirm = Some(project_id);
        cx.notify();
    }

    pub(crate) fn cancel_archive_project(&mut self, cx: &mut Context<Self>) {
        if self.session_action_in_flight {
            return;
        }
        self.project_archive_confirm = None;
        cx.notify();
    }

    pub(crate) fn archive_project_chats(&mut self, project_id: String, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.mutations || self.session_action_in_flight {
            return;
        }
        let session_ids = self
            .sessions
            .iter()
            .filter(|session| {
                !session.archived && session.project_id.as_deref() == Some(project_id.as_str())
            })
            .map(|session| session.session_id.clone())
            .collect::<Vec<_>>();
        self.project_menu_id = None;
        self.project_archive_confirm = None;
        if session_ids.is_empty() {
            self.project_status = "No active chats in project".to_owned();
            cx.notify();
            return;
        }
        self.session_action_in_flight = true;
        self.project_status = "Archiving project chats…".to_owned();
        let client = Arc::clone(&self.client);
        let archived_session_ids = session_ids.clone();
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move {
                    for session_id in &session_ids {
                        client.update_session(session_id, None, None, Some(true))?;
                    }
                    Ok::<_, io::Error>((client.list_sessions()?, client.list_projects()?))
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.session_action_in_flight = false;
                match result {
                    Ok((sessions, projects)) => {
                        this.sessions = sessions;
                        this.projects = projects;
                        this.session_count = this
                            .sessions
                            .iter()
                            .filter(|session| {
                                !session.archived && session.origin.as_deref() != Some("side_chat")
                            })
                            .count();
                        if this.selected_session_id.as_deref().is_some_and(|id| {
                            archived_session_ids.iter().any(|archived| archived == id)
                        }) {
                            this.clear_selected_session_projection();
                        }
                        this.project_status = "Project chats archived".to_owned();
                    }
                    Err(error) => {
                        this.project_status = format!("Archive project chats failed · {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn restore_project_chats(&mut self, project_id: String, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.mutations || self.session_action_in_flight {
            return;
        }
        let session_ids = self
            .sessions
            .iter()
            .filter(|session| {
                session.archived && session.project_id.as_deref() == Some(project_id.as_str())
            })
            .map(|session| session.session_id.clone())
            .collect::<Vec<_>>();
        self.project_menu_id = None;
        if session_ids.is_empty() {
            self.project_status = "No archived chats in project".to_owned();
            cx.notify();
            return;
        }
        self.session_action_in_flight = true;
        self.project_status = "Restoring project chats…".to_owned();
        let client = Arc::clone(&self.client);
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move {
                    for session_id in &session_ids {
                        client.update_session(session_id, None, None, Some(false))?;
                    }
                    Ok::<_, io::Error>((client.list_sessions()?, client.list_projects()?))
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.session_action_in_flight = false;
                match result {
                    Ok((sessions, projects)) => {
                        this.sessions = sessions;
                        this.projects = projects;
                        this.session_count = this
                            .sessions
                            .iter()
                            .filter(|session| {
                                !session.archived && session.origin.as_deref() != Some("side_chat")
                            })
                            .count();
                        this.project_status = "Project chats restored".to_owned();
                    }
                    Err(error) => {
                        this.project_status = format!("Restore project chats failed · {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn request_remove_project(&mut self, project_id: String, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.mutations || self.project_save_in_flight {
            return;
        }
        self.project_menu_id = None;
        self.project_remove_confirm = Some(project_id);
        cx.notify();
    }

    pub(crate) fn cancel_remove_project(&mut self, cx: &mut Context<Self>) {
        self.project_remove_confirm = None;
        cx.notify();
    }

    pub(crate) fn remove_project_root(&mut self, root: String, cx: &mut Context<Self>) {
        let roots = self
            .project_roots_text
            .lines()
            .filter(|candidate| candidate.trim() != root.trim())
            .map(str::trim)
            .filter(|candidate| !candidate.is_empty())
            .collect::<Vec<_>>();
        self.project_roots_text = roots.join("\n");
        self.project_roots_marked_text.clear();
        self.project_roots_marked_selection = 0..0;
        cx.notify();
    }

    pub(crate) fn make_project_root_primary(&mut self, root: String, cx: &mut Context<Self>) {
        let mut roots = self
            .project_roots_text
            .lines()
            .map(str::trim)
            .filter(|candidate| !candidate.is_empty())
            .map(str::to_owned)
            .collect::<Vec<_>>();
        if let Some(index) = roots.iter().position(|candidate| candidate == &root) {
            let primary = roots.remove(index);
            roots.insert(0, primary);
            self.project_roots_text = roots.join("\n");
            self.project_roots_marked_text.clear();
            self.project_roots_marked_selection = 0..0;
        }
        cx.notify();
    }

    pub(crate) fn remove_project(&mut self, project_id: String, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.mutations || self.project_save_in_flight {
            return;
        }
        let client = Arc::clone(&self.client);
        let removed_project_id = project_id.clone();
        self.project_menu_id = None;
        self.project_remove_confirm = None;
        self.project_save_in_flight = true;
        self.project_status = "Removing project…".to_owned();
        cx.notify();
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move {
                    client.remove_project(&project_id)?;
                    Ok::<_, io::Error>((client.list_projects()?, client.list_sessions()?))
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.project_save_in_flight = false;
                match result {
                    Ok((projects, sessions)) => {
                        this.projects = projects;
                        this.sessions = sessions;
                        this.session_count = this
                            .sessions
                            .iter()
                            .filter(|session| {
                                !session.archived && session.origin.as_deref() != Some("side_chat")
                            })
                            .count();
                        if this.selected_project_id.as_deref() == Some(removed_project_id.as_str())
                        {
                            this.selected_project_id = None;
                        }
                        this.project_status =
                            "Project removed · chats returned to Chats".to_owned();
                    }
                    Err(error) => this.project_status = format!("Project remove failed: {error}"),
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn reveal_project(&mut self, project_id: String, cx: &mut Context<Self>) {
        let Some(root) = self
            .projects
            .iter()
            .find(|project| project.project_id == project_id)
            .and_then(|project| project.roots.first())
            .map(|root| root.path.clone())
        else {
            self.project_status = "Project has no source folder to reveal".to_owned();
            cx.notify();
            return;
        };
        #[cfg(target_os = "macos")]
        let result = Command::new("/usr/bin/open")
            .args(["-R", root.as_str()])
            .status()
            .map_err(|error| error.to_string())
            .and_then(|status| {
                if status.success() {
                    Ok(())
                } else {
                    Err(format!("Finder exited with {status}"))
                }
            });
        #[cfg(not(target_os = "macos"))]
        let result: Result<(), String> = Err("Finder reveal is only available on macOS".to_owned());
        self.project_status = match result {
            Ok(()) => format!("Revealed {root} in Finder"),
            Err(error) => format!("Reveal in Finder failed: {error}"),
        };
        cx.notify();
    }

    fn selected_model_is_ready(&self) -> bool {
        self.selected_model_profile.ready
    }

    fn sync_selected_model_profile(&mut self, capabilities: &RuntimeCapabilities) {
        let selected = &self.selected_model_profile;
        if let Some(profile) = capabilities.model_profiles.iter().find(|profile| {
            profile.provider == selected.provider
                && profile.model == selected.model
                && profile.effort == selected.effort
        }) {
            self.selected_model_profile = profile.clone();
            return;
        }
        if let Some(profile) = capabilities.model_profiles.iter().find(|profile| {
            profile.provider == capabilities.provider
                && profile.model == capabilities.model
                && profile.effort == capabilities.effort
        }) {
            self.selected_model_profile = profile.clone();
        }
    }

    pub(crate) fn toggle_model_menu(&mut self, cx: &mut Context<Self>) {
        self.model_menu_open = !self.model_menu_open;
        self.permission_menu_open = false;
        cx.notify();
    }

    pub(crate) fn close_model_menu(&mut self, cx: &mut Context<Self>) {
        if self.model_menu_open {
            self.model_menu_open = false;
            cx.notify();
        }
    }

    pub(crate) fn select_model_profile(&mut self, profile: ModelProfile, cx: &mut Context<Self>) {
        if !profile.ready {
            let reason = if !profile.configured {
                "provider is not configured"
            } else if profile.probe_status != "passed" {
                "capability probe is not ready"
            } else {
                "runtime is not ready"
            };
            self.session_status = format!("{} unavailable · {reason}", profile.model);
            self.model_menu_open = true;
        } else {
            self.selected_model_profile = profile.clone();
            self.model_menu_open = false;
            self.permission_menu_open = false;
            self.session_status = format!("Model selected · {}", profile.model);
        }
        cx.notify();
    }

    pub(crate) fn toggle_permission_menu(&mut self, cx: &mut Context<Self>) {
        self.permission_menu_open = !self.permission_menu_open;
        cx.notify();
    }

    pub(crate) fn close_permission_menu(&mut self, cx: &mut Context<Self>) {
        if self.permission_menu_open {
            self.permission_menu_open = false;
            cx.notify();
        }
    }

    pub(crate) fn select_permission_profile(
        &mut self,
        profile: PermissionProfile,
        cx: &mut Context<Self>,
    ) {
        if !self.runtime_capabilities.mutations || !self.selected_model_is_ready() {
            self.session_status = format!(
                "{} is not available until the selected model is ready",
                permission_profile_label(profile)
            );
            self.permission_menu_open = true;
        } else if profile == PermissionProfile::AskForApproval {
            self.permission_profile = profile;
            self.permission_menu_open = false;
        } else {
            self.session_status = format!(
                "{} is not available for the selected {} model",
                permission_profile_label(profile),
                if self.runtime_capabilities.model.is_empty() {
                    "runtime"
                } else {
                    self.runtime_capabilities.model.as_str()
                }
            );
            self.permission_menu_open = true;
        }
        cx.notify();
    }

    pub(crate) fn focus_composer(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self.input_target = InputTarget::Composer;
        self.composer_focus.focus(window, cx);
    }

    pub(crate) fn select_starter_category(
        &mut self,
        category: StarterCategory,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        self.starter_category = Some(category);
        if self.composer_text.trim().is_empty() {
            self.set_composer_text(category.seed());
        } else {
            self.append_composer_text(category.seed());
        }
        self.input_target = InputTarget::Composer;
        self.composer_focus.focus(window, cx);
        cx.notify();
    }

    pub(crate) fn apply_starter_text(
        &mut self,
        text: &str,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        let is_category_seed = self
            .starter_category
            .is_some_and(|category| self.composer_text.trim() == category.seed());
        if self.composer_text.trim().is_empty() || is_category_seed {
            self.set_composer_text(text);
        } else {
            self.append_composer_text(text);
        }
        self.input_target = InputTarget::Composer;
        self.composer_focus.focus(window, cx);
        cx.notify();
    }

    fn set_composer_text(&mut self, text: &str) {
        self.composer_text.clear();
        self.composer_text.push_str(text);
        self.composer_marked_text.clear();
        let cursor = self.composer_text.encode_utf16().count();
        self.composer_marked_selection = cursor..cursor;
    }

    fn append_composer_text(&mut self, text: &str) {
        if !self.composer_text.is_empty()
            && !self
                .composer_text
                .chars()
                .last()
                .is_some_and(char::is_whitespace)
        {
            self.composer_text.push_str("\n\n");
        }
        self.composer_text.push_str(text);
        self.composer_marked_text.clear();
        let cursor = self.composer_text.encode_utf16().count();
        self.composer_marked_selection = cursor..cursor;
    }

    pub(crate) fn toggle_navigation(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self.navigation_open = !self.navigation_open;
        self.shell_focus.focus(window, cx);
        cx.notify();
    }

    fn resize_navigation(
        &mut self,
        event: &DragMoveEvent<DraggedNavigationDivider>,
        cx: &mut Context<Self>,
    ) {
        self.panel_preferences.navigation_width = (event.event.position.x - event.bounds.left())
            .as_f32()
            .clamp(NAVIGATION_MIN_WIDTH, NAVIGATION_MAX_WIDTH);
        cx.notify();
    }

    fn resize_workbench(
        &mut self,
        event: &DragMoveEvent<DraggedWorkbenchDivider>,
        cx: &mut Context<Self>,
    ) {
        self.panel_preferences.workbench_width = (event.bounds.right() - event.event.position.x)
            .as_f32()
            .clamp(WORKBENCH_MIN_WIDTH, WORKBENCH_MAX_WIDTH);
        cx.notify();
    }

    pub(crate) fn resize_file_tree(
        &mut self,
        event: &DragMoveEvent<DraggedFileTreeDivider>,
        cx: &mut Context<Self>,
    ) {
        self.panel_preferences.file_tree_width = (event.bounds.right() - event.event.position.x)
            .as_f32()
            .clamp(FILE_TREE_MIN_WIDTH, FILE_TREE_MAX_WIDTH);
        cx.notify();
    }

    fn start_panel_resize(&mut self, target: PanelResizeTarget, cx: &mut Context<Self>) {
        self.active_panel_resize = Some(target);
        cx.notify();
    }

    fn resize_active_panel(
        &mut self,
        event: &MouseMoveEvent,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        let Some(target) = self.active_panel_resize else {
            return;
        };
        if !event.dragging() {
            self.active_panel_resize = None;
            self.persist_panel_preferences(cx);
            return;
        }
        self.panel_preferences = resize_panel_preferences(
            self.panel_preferences,
            target,
            event.position.x.as_f32(),
            window.viewport_size().width.as_f32(),
        );
        cx.notify();
    }

    fn finish_panel_resize(&mut self, cx: &mut Context<Self>) {
        if self.active_panel_resize.take().is_some() {
            self.persist_panel_preferences(cx);
            cx.notify();
        }
    }

    fn adjust_panel_width(
        &mut self,
        target: PanelResizeTarget,
        direction: f32,
        cx: &mut Context<Self>,
    ) {
        const KEYBOARD_RESIZE_STEP: f32 = 8.0;
        match target {
            PanelResizeTarget::Navigation => {
                self.panel_preferences.navigation_width = (self.panel_preferences.navigation_width
                    + direction * KEYBOARD_RESIZE_STEP)
                    .clamp(NAVIGATION_MIN_WIDTH, NAVIGATION_MAX_WIDTH);
            }
            PanelResizeTarget::Workbench => {
                self.panel_preferences.workbench_width = (self.panel_preferences.workbench_width
                    + direction * KEYBOARD_RESIZE_STEP)
                    .clamp(WORKBENCH_MIN_WIDTH, WORKBENCH_MAX_WIDTH);
            }
            PanelResizeTarget::FileTree => {
                self.panel_preferences.file_tree_width = (self.panel_preferences.file_tree_width
                    + direction * KEYBOARD_RESIZE_STEP)
                    .clamp(FILE_TREE_MIN_WIDTH, FILE_TREE_MAX_WIDTH);
            }
        }
        self.persist_panel_preferences(cx);
        cx.notify();
    }

    pub(crate) fn persist_panel_preferences(&mut self, cx: &mut Context<Self>) {
        let path = self.panel_preferences_path.clone();
        let preferences = self.panel_preferences;
        let previous = self.panel_preferences_save_task.take();
        self.panel_preferences_save_task = Some(cx.spawn(async move |_this, cx| {
            if let Some(previous) = previous {
                previous.await;
            }
            let result = cx
                .background_executor()
                .spawn(async move { save_panel_preferences(&path, preferences) })
                .await;
            if let Err(error) = result {
                eprintln!("failed to persist Codinal panel preferences: {error}");
            }
        }));
    }

    pub(crate) fn toggle_side_panel(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        let closing = self.dock.open();
        self.dock.dispatch(DockAction::Toggle);
        if self.dock.open() && self.dock.open_tabs().is_empty() {
            self.dock.dispatch(DockAction::TogglePicker);
        }
        if closing {
            self.input_target = InputTarget::Composer;
            self.side_panel_trigger_focus.focus(window, cx);
        }
        cx.notify();
    }

    pub(crate) fn toggle_tool_picker(&mut self, cx: &mut Context<Self>) {
        self.dock.dispatch(DockAction::TogglePicker);
        cx.notify();
    }

    pub(crate) fn close_active_side_panel_tab(
        &mut self,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        let closing_terminal = self.dock.active() == Some(SidePanelTool::Terminal);
        self.dock.dispatch(DockAction::CloseActive);
        if closing_terminal {
            self.input_target = InputTarget::Composer;
            self.side_panel_trigger_focus.focus(window, cx);
        }
        if self.dock.active().is_none() {
            self.side_panel_trigger_focus.focus(window, cx);
        }
        cx.notify();
    }

    pub(crate) fn select_side_panel_tab(
        &mut self,
        tool: SidePanelTool,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        self.dock.dispatch(DockAction::Activate(tool));
        if tool != SidePanelTool::Terminal {
            self.input_target = InputTarget::Composer;
        }
        self.side_panel_trigger_focus.focus(window, cx);
        match tool {
            SidePanelTool::Review if self.review_snapshot.is_none() => self.refresh_review(cx),
            SidePanelTool::Files if self.workspace_snapshot.is_none() => self.refresh_files(cx),
            _ => cx.notify(),
        }
    }

    fn selected_project_roots(&self) -> Vec<ProjectRootSummary> {
        let session = self.sessions.iter().find(|session| {
            self.selected_session_id.as_deref() == Some(session.session_id.as_str())
        });
        let project_id = session
            .and_then(|session| session.project_id.as_deref())
            .or(self.selected_project_id.as_deref());
        project_id
            .and_then(|project_id| {
                self.projects
                    .iter()
                    .find(|project| project.project_id == project_id)
            })
            .map(|project| project.roots.clone())
            .unwrap_or_default()
    }

    fn selected_workspace(&self) -> Option<PathBuf> {
        let session = self.sessions.iter().find(|session| {
            self.selected_session_id.as_deref() == Some(session.session_id.as_str())
        });
        let project_id = session
            .and_then(|session| session.project_id.as_deref())
            .or(self.selected_project_id.as_deref());
        let project = project_id.and_then(|project_id| {
            self.projects
                .iter()
                .find(|project| project.project_id == project_id)
        });
        if let Some(path) = self.selected_root_path.as_deref().and_then(|path| {
            project
                .filter(|project| project.roots.iter().any(|root| root.path == path))
                .map(|_| PathBuf::from(path))
        }) {
            return Some(path);
        }
        project
            .and_then(|project| {
                project
                    .roots
                    .iter()
                    .find(|root| root.primary)
                    .or_else(|| project.roots.first())
                    .map(|root| PathBuf::from(&root.path))
            })
            .or_else(|| session.map(|session| PathBuf::from(&session.workspace)))
    }

    pub(crate) fn toggle_file_root_menu(&mut self, cx: &mut Context<Self>) {
        if self.selected_project_roots().len() < 2 {
            self.file_root_menu_open = false;
            return;
        }
        self.file_root_menu_open = !self.file_root_menu_open;
        cx.notify();
    }

    pub(crate) fn select_file_root(&mut self, path: String, cx: &mut Context<Self>) {
        if !self
            .selected_project_roots()
            .iter()
            .any(|root| root.path == path)
        {
            return;
        }
        self.selected_root_path = Some(path);
        self.file_root_menu_open = false;
        self.files_generation = self.files_generation.wrapping_add(1);
        self.file_preview_generation = self.file_preview_generation.wrapping_add(1);
        self.workspace_snapshot = None;
        self.file_preview = None;
        self.files_status = "Loading selected source root…".to_owned();
        self.file_preview_status = "Select a file from the workspace tree".to_owned();
        match self.dock.active() {
            Some(SidePanelTool::Review) => self.refresh_review(cx),
            Some(SidePanelTool::Files) => self.refresh_files(cx),
            _ => cx.notify(),
        }
    }

    pub(crate) fn activate_side_panel_tool(
        &mut self,
        tool: SidePanelTool,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        let focus_handoff = side_tool_focus_handoff_required(self.dock.active(), tool, false);
        self.dock.dispatch(DockAction::Activate(tool));
        if focus_handoff {
            self.side_panel_trigger_focus.focus(window, cx);
        }
        match tool {
            SidePanelTool::Review => self.refresh_review(cx),
            SidePanelTool::Terminal => cx.notify(),
            SidePanelTool::Browser => cx.notify(),
            SidePanelTool::Files => self.refresh_files(cx),
            SidePanelTool::SideChat => cx.notify(),
        }
    }

    pub(crate) fn refresh_review(&mut self, cx: &mut Context<Self>) {
        self.review_generation = self.review_generation.wrapping_add(1);
        self.review_status =
            "Review unavailable · native runtime Git route is not enabled".to_owned();
        self.review_snapshot = None;
        cx.notify();
    }

    pub(crate) fn refresh_files(&mut self, cx: &mut Context<Self>) {
        self.files_generation = self.files_generation.wrapping_add(1);
        self.file_preview_generation = self.file_preview_generation.wrapping_add(1);
        self.file_preview = None;
        self.file_preview_status =
            "File preview unavailable · native runtime file route is not enabled".to_owned();
        self.files_status =
            "Files unavailable · native runtime workspace route is not enabled".to_owned();
        self.workspace_snapshot = None;
        cx.notify();
    }

    pub(crate) fn open_workspace_file(&mut self, relative_path: String, cx: &mut Context<Self>) {
        self.file_preview_generation = self.file_preview_generation.wrapping_add(1);
        self.file_preview = None;
        self.file_preview_status = format!(
            "File preview unavailable · native runtime route is not enabled ({relative_path})"
        );
        cx.notify();
    }

    pub(crate) fn reveal_workspace_file(&mut self, relative_path: String, cx: &mut Context<Self>) {
        self.file_preview_status = format!(
            "Reveal unavailable · native runtime file route is not enabled ({relative_path})"
        );
        cx.notify();
    }

    pub(crate) fn show_browser_prompt(&mut self, cx: &mut Context<Self>) {
        let url = match secure_prompt::prompt_text(
            "Open in system browser",
            "Enter a credential-free HTTP(S) URL. Codinal does not embed WebView/WebKit.",
            &self.browser_url,
        ) {
            Ok(Some(url)) => url,
            Ok(None) => {
                self.browser_status = "Browser open cancelled".to_owned();
                cx.notify();
                return;
            }
            Err(error) => {
                self.browser_status = format!("Browser prompt failed: {error}");
                cx.notify();
                return;
            }
        };
        match open_browser_url(&url) {
            Ok(()) => {
                self.browser_url = url;
                self.browser_status = "Opened with the macOS system browser".to_owned();
            }
            Err(error) => {
                self.browser_status = format!("Browser open failed: {error}");
            }
        }
        cx.notify();
    }

    pub(crate) fn open_side_chat_session(&mut self, session_id: String, cx: &mut Context<Self>) {
        if !self
            .sessions
            .iter()
            .any(|session| session.session_id == session_id)
        {
            return;
        }
        self.select_session(session_id, cx);
        self.dock
            .dispatch(DockAction::Activate(SidePanelTool::SideChat));
        self.side_chat_status = "Side chat selected · parent chat remains available".to_owned();
        cx.notify();
    }

    pub(crate) fn create_side_chat(&mut self, cx: &mut Context<Self>) {
        if self.side_chat_in_flight {
            return;
        }
        if !self.runtime_capabilities.mutations {
            let reason = self
                .runtime_capabilities
                .mutation_disabled_reason
                .as_deref()
                .unwrap_or("runtime_read_only");
            self.side_chat_status =
                format!("Side chat unavailable · {}", disabled_reason_label(reason));
            cx.notify();
            return;
        }
        let Some(parent) = self
            .sessions
            .iter()
            .find(|session| {
                self.selected_session_id.as_deref() == Some(session.session_id.as_str())
            })
            .cloned()
        else {
            self.side_chat_status = "Select a chat before opening a side chat".to_owned();
            cx.notify();
            return;
        };
        let parent_context = parent
            .origin_session_id
            .as_deref()
            .and_then(|parent_id| {
                self.sessions
                    .iter()
                    .find(|session| session.session_id == parent_id)
            })
            .unwrap_or(&parent);
        let title = format!(
            "Side chat · {}",
            parent_context.title.chars().take(120).collect::<String>()
        );
        let workspace = self
            .selected_workspace()
            .map(|workspace| workspace.to_string_lossy().into_owned())
            .unwrap_or_else(|| parent_context.workspace.clone());
        let parent_id = parent_context.session_id.clone();
        let parent_id_for_request = parent_id.clone();
        let selected_model = self.selected_model_profile.model.clone();
        let client = Arc::clone(&self.client);
        self.side_chat_in_flight = true;
        self.side_chat_status = "Creating isolated side chat…".to_owned();
        cx.notify();
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move {
                    client.create_side_chat_with_model(
                        &workspace,
                        &title,
                        &parent_id_for_request,
                        &selected_model,
                    )
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.side_chat_in_flight = false;
                match result {
                    Ok(session) => {
                        let child_id = session.session_id.clone();
                        if !this
                            .sessions
                            .iter()
                            .any(|existing| existing.session_id == child_id)
                        {
                            this.sessions.insert(0, session);
                        }
                        this.session_count = this
                            .sessions
                            .iter()
                            .filter(|session| {
                                !session.archived && session.origin.as_deref() != Some("side_chat")
                            })
                            .count();
                        this.side_chat_parent_id = Some(parent_id);
                        this.side_chat_status =
                            "Side chat created · parent chat remains unchanged".to_owned();
                        this.select_session(child_id, cx);
                        this.dock
                            .dispatch(DockAction::Activate(SidePanelTool::SideChat));
                    }
                    Err(error) => {
                        this.side_chat_status = format!("Side chat failed: {error}");
                        cx.notify();
                    }
                }
            });
        })
        .detach();
    }

    pub(crate) fn show_new_task_unavailable(
        &mut self,
        disabled_reason: &str,
        cx: &mut Context<Self>,
    ) {
        self.session_status = format!(
            "New chat unavailable · {}",
            disabled_reason_label(disabled_reason)
        );
        cx.notify();
    }

    pub(crate) fn show_navigation_unavailable(
        &mut self,
        surface: &'static str,
        disabled_reason: &str,
        cx: &mut Context<Self>,
    ) {
        self.session_status = format!(
            "{surface} unavailable · {}",
            disabled_reason_label(disabled_reason)
        );
        cx.notify();
    }

    pub(crate) fn create_task(&mut self, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.mutations {
            let reason = self
                .runtime_capabilities
                .mutation_disabled_reason
                .as_deref()
                .unwrap_or("runtime_read_only");
            self.session_status =
                format!("New chat unavailable · {}", disabled_reason_label(reason));
            cx.notify();
            return;
        }
        let selected_project_id = self.selected_project_id.clone();
        let project_workspace = selected_project_id.as_deref().and_then(|project_id| {
            self.projects
                .iter()
                .find(|project| project.project_id == project_id)
                .and_then(|project| {
                    project
                        .roots
                        .iter()
                        .find(|root| root.primary)
                        .or_else(|| project.roots.first())
                        .map(|root| root.path.clone())
                })
        });
        if selected_project_id.is_some() && project_workspace.is_none() {
            self.session_status =
                "New chat unavailable · selected project has no source folder".to_owned();
            cx.notify();
            return;
        }
        #[cfg(target_os = "macos")]
        let workspace = match project_workspace {
            Some(path) => path,
            None => match choose_native_workspace() {
                Ok(path) => path.to_string_lossy().into_owned(),
                Err(error) if error.kind() == io::ErrorKind::Interrupted => {
                    self.session_status = "New chat cancelled".to_owned();
                    cx.notify();
                    return;
                }
                Err(error) => {
                    self.session_status = format!("Workspace selection failed: {error}");
                    cx.notify();
                    return;
                }
            },
        };
        #[cfg(not(target_os = "macos"))]
        let workspace = match project_workspace {
            Some(path) => path,
            None => match std::env::current_dir() {
                Ok(path) => path.to_string_lossy().into_owned(),
                Err(error) => {
                    self.session_status = format!("Workspace selection failed: {error}");
                    cx.notify();
                    return;
                }
            },
        };
        let client = Arc::clone(&self.client);
        let selected_model = self.selected_model_profile.model.clone();
        self.session_status = "Creating new chat…".to_owned();
        cx.notify();
        cx.spawn(async move |this, cx| {
            let result: io::Result<(SessionSummary, Option<Vec<ProjectSummary>>)> = cx
                .background_executor()
                .spawn(async move {
                    let session = client.create_session_with_model(
                        &workspace,
                        "New chat",
                        &selected_model,
                    )?;
                    if let Some(project_id) = selected_project_id.as_deref() {
                        client.assign_session_to_project(project_id, &session.session_id)?;
                        let session = client
                            .list_sessions()?
                            .into_iter()
                            .find(|candidate| candidate.session_id == session.session_id)
                            .ok_or_else(|| {
                                io::Error::new(
                                    io::ErrorKind::InvalidData,
                                    "created project chat was not readable",
                                )
                            })?;
                        let projects = client.list_projects()?;
                        Ok((session, Some(projects)))
                    } else {
                        Ok((session, None))
                    }
                })
                .await;
            let _ = this.update(cx, |this, cx| match result {
                Ok((session, projects)) => {
                    if let Some(projects) = projects {
                        this.projects = projects;
                    }
                    let session_id = session.session_id.clone();
                    if !this
                        .sessions
                        .iter()
                        .any(|existing| existing.session_id == session_id)
                    {
                        this.sessions.insert(0, session);
                    }
                    this.session_count = this
                        .sessions
                        .iter()
                        .filter(|session| {
                            !session.archived && session.origin.as_deref() != Some("side_chat")
                        })
                        .count();
                    this.session_status = "New chat created".to_owned();
                    this.select_session(session_id, cx);
                }
                Err(error) => {
                    this.session_status = format!("New chat failed: {error}");
                    cx.notify();
                }
            });
        })
        .detach();
    }

    pub(crate) fn select_session(&mut self, session_id: String, cx: &mut Context<Self>) {
        let Some(selected_session) = self
            .sessions
            .iter()
            .find(|session| session.session_id == session_id)
        else {
            return;
        };
        self.session_status = "Loading session…".to_owned();
        self.session_menu_open = false;
        self.session_delete_confirm = false;
        self.session_rename_open = false;
        self.session_action_status.clear();
        self.dock
            .dispatch(DockAction::SelectSession(Some(session_id.clone())));
        self.selected_session_id = Some(session_id.clone());
        self.selected_project_id = selected_session.project_id.clone();
        self.side_chat_parent_id = if selected_session.origin.as_deref() == Some("side_chat") {
            selected_session.origin_session_id.clone()
        } else {
            Some(selected_session.session_id.clone())
        };
        self.approval_session_id = Some(session_id.clone());
        self.ui
            .dispatch(UiAction::SelectSession)
            .expect("reset UI session projection");
        self.review_generation = self.review_generation.wrapping_add(1);
        self.files_generation = self.files_generation.wrapping_add(1);
        self.file_preview_generation = self.file_preview_generation.wrapping_add(1);
        self.review_snapshot = None;
        self.workspace_snapshot = None;
        self.file_preview = None;
        self.file_root_menu_open = false;
        self.selected_root_path = None;
        self.starter_category = None;
        self.review_status = "Review not loaded for this chat".to_owned();
        self.files_status = "Files not loaded for this chat".to_owned();
        self.file_preview_status = "Select a file from the workspace tree".to_owned();
        self.session_selection_generation = self.session_selection_generation.wrapping_add(1);
        self.session_load_generation = self.session_load_generation.wrapping_add(1);
        self.session_load_in_flight = false;
        self.session_reload_pending_reason = None;
        self.session_reload_retry_count = 0;
        let _ = self.session_reload_retry_task.take();
        self.session_event_generation = self.session_event_generation.wrapping_add(1);
        let stream_generation = self.session_event_generation;
        cx.notify();
        self.start_session_event_stream(session_id.clone(), stream_generation, cx);
        self.reload_selected_session_projection("Session loaded from execution control plane", cx);
        self.refresh_sources(cx);
        match self.dock.active() {
            Some(SidePanelTool::Review) => self.refresh_review(cx),
            Some(SidePanelTool::Files) => self.refresh_files(cx),
            _ => self.refresh_review(cx),
        }
    }

    fn reload_selected_session_projection(&mut self, reason: &'static str, cx: &mut Context<Self>) {
        if session_reload_should_coalesce(
            self.session_load_in_flight,
            self.session_reload_retry_task.is_some(),
        ) {
            self.session_reload_pending_reason = Some(reason);
            return;
        }
        let Some(session_id) = self.selected_session_id.clone() else {
            return;
        };
        self.session_reload_pending_reason = None;
        self.session_load_in_flight = true;
        self.session_load_generation = self.session_load_generation.wrapping_add(1);
        let generation = self.session_load_generation;
        let event_watermark = self.ui.event_watermark;
        let requested_id = session_id.clone();
        let client = Arc::clone(&self.client);
        cx.spawn(async move |this, cx| {
            let outcome = cx
                .background_executor()
                .spawn(async move { client.load_session(&session_id) })
                .await;
            let _ = this.update(cx, |this, cx| {
                if this.session_load_generation != generation
                    || this.selected_session_id.as_deref() != Some(requested_id.as_str())
                {
                    return;
                }
                this.session_load_in_flight = false;
                let watermark_is_current = projection_reload_is_current(
                    this.session_load_generation,
                    this.selected_session_id.as_deref(),
                    this.ui.event_watermark,
                    generation,
                    Some(requested_id.as_str()),
                    event_watermark,
                );
                if !projection_reload_may_apply(
                    watermark_is_current,
                    this.session_reload_pending_reason.is_some(),
                ) {
                    let retry_reason = this.session_reload_pending_reason.take().unwrap_or(reason);
                    this.schedule_session_reload_retry(
                        retry_reason,
                        "Session changed during reload",
                        cx,
                    );
                    cx.notify();
                    return;
                }
                match outcome {
                    Ok((messages, approvals, receipts)) => {
                        this.session_reload_retry_count = 0;
                        let _ = this.session_reload_retry_task.take();
                        this.approval_session_id = Some(requested_id);
                        this.ui
                            .dispatch(UiAction::LoadSession {
                                messages,
                                approvals,
                                receipts,
                            })
                            .expect("load UI session projection");
                        this.session_status =
                            format!("{reason} · {} receipt(s)", this.ui.turn_receipts.len());
                    }
                    Err(error) => {
                        this.session_reload_pending_reason = None;
                        this.ui
                            .dispatch(UiAction::SetPendingApprovals(Vec::new()))
                            .expect("clear UI approvals");
                        this.ui.approval_review_status =
                            "Approval controls disabled until session reload succeeds".to_owned();
                        this.session_status = format!("Session reload failed: {error}");
                        this.schedule_session_reload_retry(reason, "Session reload failed", cx);
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    fn schedule_session_reload_retry(
        &mut self,
        reason: &'static str,
        status: &'static str,
        cx: &mut Context<Self>,
    ) {
        if self.session_reload_retry_task.is_some() {
            return;
        }
        let Some(delay) = session_reload_retry_delay(self.session_reload_retry_count) else {
            self.session_status = format!("{status} · automatic retry limit reached");
            return;
        };
        let Some(session_id) = self.selected_session_id.clone() else {
            return;
        };
        let selection_generation = self.session_selection_generation;
        self.session_reload_retry_count = self.session_reload_retry_count.saturating_add(1);
        let attempt = self.session_reload_retry_count;
        self.session_status = format!("{status} · retry {attempt}/5 in {} ms", delay.as_millis());
        self.session_reload_retry_task = Some(cx.spawn(async move |this, cx| {
            cx.background_executor().timer(delay).await;
            let _ = this.update(cx, |this, cx| {
                if this.session_selection_generation != selection_generation
                    || this.selected_session_id.as_deref() != Some(session_id.as_str())
                {
                    return;
                }
                let _ = this.session_reload_retry_task.take();
                this.reload_selected_session_projection(reason, cx);
            });
        }));
    }

    fn start_session_event_stream(
        &mut self,
        session_id: String,
        stream_generation: u64,
        cx: &mut Context<Self>,
    ) {
        let _ = self.session_event_worker.take();
        let _ = self.session_event_task.take();
        self.ui
            .dispatch(UiAction::ClearStreaming)
            .expect("clear streaming UI projection");
        let selected_id = session_id.clone();
        let client = Arc::clone(&self.client);
        let (worker, receiver) = match spawn_session_stream(client, session_id) {
            Ok(worker) => worker,
            Err(error) => {
                self.ui.session_stream_status =
                    format!("Session stream worker failed to start: {error}");
                cx.notify();
                return;
            }
        };
        self.session_event_worker = Some(worker);
        let runtime_task = cx.spawn(async move |this, cx| {
            let mut receiver = receiver;
            loop {
                let (received, returned_receiver) = cx
                    .background_executor()
                    .spawn(async move {
                        let received = receiver.recv();
                        (received, receiver)
                    })
                    .await;
                receiver = returned_receiver;
                let first = match received {
                    Ok(update) => update,
                    Err(_) => {
                        let _ = this.update(cx, |this, cx| {
                            if this.session_event_generation == stream_generation
                                && this.selected_session_id.as_deref() == Some(selected_id.as_str())
                            {
                                this.ui.session_stream_status =
                                    "Session stream worker stopped".to_owned();
                                this.ui.streaming_assistant = None;
                                cx.notify();
                            }
                        });
                        break;
                    }
                };
                let mut updates = Vec::with_capacity(64);
                updates.push(first);
                updates.extend(receiver.try_iter().take(63));
                let mut stopped = false;
                let _ = this.update(cx, |this, cx| {
                    if this.session_event_generation != stream_generation
                        || this.selected_session_id.as_deref() != Some(selected_id.as_str())
                    {
                        stopped = true;
                        return;
                    }
                    let mut reload_reason = None;
                    for update in updates {
                        if let Some(reason) = this.apply_session_stream_update(update) {
                            reload_reason = Some(reason);
                        }
                    }
                    if let Some(reason) = reload_reason {
                        this.reload_selected_session_projection(reason, cx);
                    }
                    cx.notify();
                });
                if stopped {
                    break;
                }
            }
        });
        self.session_event_task = Some(runtime_task);
    }

    fn apply_session_stream_update(&mut self, update: SessionStreamUpdate) -> Option<&'static str> {
        match update {
            SessionStreamUpdate::Connecting => {
                self.ui
                    .dispatch(UiAction::SetStreamStatus(
                        "Connecting to session stream…".to_owned(),
                    ))
                    .expect("set stream status");
                None
            }
            SessionStreamUpdate::StartFailed(error) => {
                self.ui.session_stream_status = format!("Session stream failed to start: {error}");
                None
            }
            SessionStreamUpdate::HandshakeFailed(error) => {
                self.ui.session_stream_status = format!("Session stream handshake failed: {error}");
                None
            }
            SessionStreamUpdate::Connected => {
                self.session_reload_retry_count = 0;
                let _ = self.session_reload_retry_task.take();
                self.ui.session_stream_status = "Session stream connected".to_owned();
                Some("Session synchronized after stream connection")
            }
            SessionStreamUpdate::Closed => {
                self.ui.session_stream_status = "Session stream closed".to_owned();
                self.ui.streaming_assistant = None;
                None
            }
            SessionStreamUpdate::Disconnected(error) => {
                self.ui.session_stream_status = format!("Session stream disconnected: {error}");
                self.ui.streaming_assistant = None;
                None
            }
            SessionStreamUpdate::ConnectionFailed(error) => {
                self.ui.session_stream_status =
                    format!("Session stream connection failed: {error}");
                self.ui.streaming_assistant = None;
                None
            }
            SessionStreamUpdate::Event { raw, pending } => {
                let Some(event) = parse_session_event(&raw) else {
                    self.ui.session_stream_status = "Rejected malformed session event".to_owned();
                    return None;
                };
                if event.event_type == "permission_required" {
                    let (context_open, dock_open) =
                        permission_required_panel_state(self.dock.open());
                    self.context_panel_open = context_open;
                    self.dock.set_open(dock_open);
                }
                let outcome = self.ui.apply_event(UiEvent::SessionStream {
                    event: Box::new(event),
                    pending,
                });
                match outcome.disposition {
                    UiEventDisposition::Duplicate => None,
                    UiEventDisposition::Rejected => None,
                    UiEventDisposition::Applied => outcome.effects.into_iter().find_map(|effect| {
                        if let UiEffect::LoadSelectedSession { reason } = effect {
                            Some(reason)
                        } else {
                            None
                        }
                    }),
                }
            }
        }
    }

    pub(crate) fn restart_after_update(&mut self, cx: &mut Context<Self>) {
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

    pub(crate) fn check_for_update(&mut self, cx: &mut Context<Self>) {
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

    pub(crate) fn show_update_install_prompt(
        &mut self,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
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

    pub(crate) fn show_update_rollback_prompt(
        &mut self,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
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
    pub(crate) fn choose_workspace(&mut self, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.mutations {
            let reason = self
                .runtime_capabilities
                .mutation_disabled_reason
                .as_deref()
                .unwrap_or("runtime_read_only");
            self.terminal_status =
                format!("Terminal unavailable · {}", disabled_reason_label(reason));
            cx.notify();
            return;
        }
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
    pub(crate) fn open_terminal(&mut self, cx: &mut Context<Self>) {
        const NATIVE_TERMINAL_ROUTE_ENABLED: bool = false;
        if !NATIVE_TERMINAL_ROUTE_ENABLED {
            self.terminal_state = TerminalState::Failed;
            self.terminal_status =
                "Terminal unavailable · native runtime terminal route is not enabled".to_owned();
            cx.notify();
            return;
        }
        if !self.runtime_capabilities.mutations {
            let reason = self
                .runtime_capabilities
                .mutation_disabled_reason
                .as_deref()
                .unwrap_or("runtime_read_only");
            self.terminal_status =
                format!("Terminal unavailable · {}", disabled_reason_label(reason));
            cx.notify();
            return;
        }
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
        let (terminal_wake_sender, terminal_wake_receiver) = sync_channel::<()>(1);
        let callback_wake_sender = terminal_wake_sender.clone();
        let resize_wake_sender = terminal_wake_sender;
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
                        move |_, chunk| {
                            match chunk {
                                Some(bytes) => callback_output.push(bytes),
                                None => callback_output.mark_exited(),
                            }
                            let _ = callback_wake_sender.try_send(());
                        },
                    )
                })
                .await;
            let _ = this.update(cx, move |this, cx| {
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
                                    let _ = resize_wake_sender.try_send(());
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
                        this.dock.dispatch(DockAction::ObserveTerminalOpened);
                        this.terminal_status = if writer_started && resizer_started {
                            "Terminal running · VT screen active".to_owned()
                        } else {
                            "Terminal running · control worker unavailable".to_owned()
                        };
                        this.start_terminal_poll(
                            output,
                            terminal_wake_receiver,
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
        wake_receiver: Receiver<()>,
        generation: u64,
        resize_result: Option<Arc<Mutex<Option<TerminalResizeOutcome>>>>,
        cx: &mut Context<Self>,
    ) {
        let registry = Arc::clone(&self.terminal_registry);
        let session_id = self.terminal_session_id.clone();
        self.terminal_poll = Some(cx.spawn(async move |this, cx| {
            let mut cursor = 0;
            let mut wake_receiver = wake_receiver;
            loop {
                let (received, returned_receiver) = cx
                    .background_executor()
                    .spawn(async move {
                        let received = wake_receiver.recv();
                        (received, wake_receiver)
                    })
                    .await;
                wake_receiver = returned_receiver;
                if received.is_err() {
                    break;
                }
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
    pub(crate) fn send_terminal_interrupt(&mut self, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.mutations {
            return;
        }
        self.send_terminal_bytes(vec![0x03], true, cx);
    }

    #[cfg(target_os = "macos")]
    pub(crate) fn send_terminal_key(&mut self, event: &KeyDownEvent, cx: &mut Context<Self>) {
        if !terminal_should_capture_key(event) {
            return;
        }
        if !self.runtime_capabilities.mutations {
            return;
        }
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
    pub(crate) fn resize_terminal(&mut self, cols: u16, rows: u16, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.mutations {
            return;
        }
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
    pub(crate) fn kill_terminal(&mut self, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.mutations {
            return;
        }
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

    pub(crate) fn show_approval_prompt(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        let Some(approval) = self.ui.pending_approval() else {
            return;
        };
        let detail = approval.detail();
        let approve_patch = approval_can_be_approved(Some(approval.tool_name.as_str()));
        let choices = if approve_patch {
            vec!["Cancel", "Deny request", "Approve patch once"]
        } else {
            vec!["Cancel", "Deny request"]
        };
        let response = window.prompt(
            PromptLevel::Warning,
            "Review pending approval",
            Some(&detail),
            &choices,
            cx,
        );
        let client = Arc::clone(&self.client);
        let session_id = self.approval_session_id.clone();
        let target_session_id = session_id.clone();
        let approval_id = Some(approval.approval_id.clone());
        let target_approval_id = approval_id.clone();
        let session_generation = self.session_selection_generation;
        cx.spawn(async move |this, cx| {
            let choice = response.await.unwrap_or(0);
            let decision = if choice == 1 {
                Some(ApprovalOutcome::Deny)
            } else if approve_patch && choice == 2 {
                Some(ApprovalOutcome::Once)
            } else {
                None
            };
            let (status, pending, reload_required) = if let Some(outcome) = decision {
                match (session_id, approval_id) {
                    (Some(session_id), Some(approval_id)) => {
                        let submission = (|| {
                            let mut confirmation = ApprovalConfirmation::new(
                                &session_id,
                                &approval_id,
                                outcome,
                            )?;
                            confirmation.confirm();
                            client.resolve_confirmation(&confirmation)
                        })();
                        match submission {
                            Ok(true) => match client.pending_approvals(&session_id) {
                                Ok(pending) => {
                                    (
                                        if outcome == ApprovalOutcome::Once {
                                            "Patch approved — live state reloaded"
                                        } else {
                                            "Request denied — live state reloaded"
                                        },
                                        Some(pending),
                                        false,
                                    )
                                }
                                Err(_) => (
                                    if outcome == ApprovalOutcome::Once {
                                        "Patch decision saved — reload failed; reopen the pane to refresh"
                                    } else {
                                        "Request denied — reload failed; reopen the pane to refresh"
                                    },
                                    Some(Vec::new()),
                                    true,
                                ),
                            },
                            Ok(false) | Err(_) => {
                                ("Decision failed — live state unchanged", None, false)
                            }
                        }
                    }
                    _ => (
                        "Decision cancelled — approval is no longer pending",
                        None,
                        false,
                    ),
                }
            } else {
                ("Approval review cancelled — no action sent", None, false)
            };
            let _ = this.update(cx, |this, cx| {
                if !approval_completion_is_current_for_request(
                    this.session_selection_generation,
                    this.approval_session_id.as_deref(),
                    this.ui.approval_id(),
                    session_generation,
                    target_session_id.as_deref(),
                    target_approval_id.as_deref(),
                ) {
                    return;
                }
                this.ui.approval_review_status = status.to_owned();
                if let Some(pending) = pending {
                    this.set_pending_approvals(pending);
                }
                if reload_required {
                    this.reload_selected_session_projection(
                        "Session reloaded after approval refresh failure",
                        cx,
                    );
                }
                cx.notify();
            });
        })
        .detach();
    }

    fn set_pending_approvals(&mut self, pending: Vec<PendingApproval>) {
        self.ui
            .dispatch(UiAction::SetPendingApprovals(pending))
            .expect("set UI approval projection");
    }

    pub(crate) fn submit_composer(&mut self, cx: &mut Context<Self>) {
        let input = self.composer_text.trim().to_owned();
        if input.is_empty() {
            self.ui.session_stream_status = "Enter a message before running the turn".to_owned();
            cx.notify();
            return;
        }
        let Some(session_id) = self.selected_session_id.clone() else {
            self.ui.session_stream_status = "Select a chat before running the turn".to_owned();
            cx.notify();
            return;
        };
        if self.ui.has_pending_approval() {
            self.ui.session_stream_status =
                "Resolve the pending approval before starting another turn".to_owned();
            cx.notify();
            return;
        }
        if !self.selected_model_is_ready() {
            let reason = self
                .runtime_capabilities
                .run_disabled_reason
                .as_deref()
                .unwrap_or("selected_model_not_ready");
            self.ui.session_stream_status = format!(
                "Turn execution unavailable: {}",
                disabled_reason_label(reason)
            );
            cx.notify();
            return;
        }
        self.composer_text.clear();
        self.starter_category = None;
        self.composer_marked_text.clear();
        self.composer_marked_selection = 0..0;
        self.start_turn_with_input(session_id, input, cx);
    }

    fn start_turn_with_input(&mut self, session_id: String, input: String, cx: &mut Context<Self>) {
        if self.ui.has_pending_approval() {
            self.ui.session_stream_status =
                "Resolve the pending approval before starting another turn".to_owned();
            cx.notify();
            return;
        }
        if !self.selected_model_is_ready() {
            self.ui.session_stream_status = format!(
                "Turn execution unavailable: selected model {} is not ready",
                self.selected_model_profile.model
            );
            cx.notify();
            return;
        }
        if self.selected_session_id.as_deref() != Some(session_id.as_str()) {
            self.ui.session_stream_status = "Select a session before starting a turn".to_owned();
            cx.notify();
            return;
        }
        if self.ui.turn_in_flight() || self.ui.turn_command_in_flight() {
            return;
        }

        let effects = match self.ui.dispatch(UiAction::StartTurn { session_id, input }) {
            Ok(effects) => effects,
            Err(_) => return,
        };
        let Some(UiEffect::StartTurn { session_id, input }) = effects.into_iter().next() else {
            return;
        };

        let client = Arc::clone(&self.client);
        let selected_model_profile = self.selected_model_profile.clone();
        let generation = self.session_selection_generation;
        let target_session_id = session_id.clone();
        self.ui.session_stream_status = "Submitting turn…".to_owned();
        cx.notify();
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move {
                    client.start_turn_with_profile(&session_id, &input, &selected_model_profile)
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                if this.session_selection_generation != generation
                    || this.selected_session_id.as_deref() != Some(target_session_id.as_str())
                    || !this.ui.turn_command_in_flight()
                {
                    return;
                }
                match result {
                    Ok(result) if result.ok && result.session_id == target_session_id => {
                        this.ui
                            .apply_event(UiEvent::StartTurnResult { accepted: true });
                        this.ui.session_stream_status =
                            "Turn accepted · waiting for session events".to_owned();
                    }
                    Ok(_) => {
                        this.ui
                            .apply_event(UiEvent::StartTurnResult { accepted: false });
                        this.ui.session_stream_status = "Turn was not accepted".to_owned();
                    }
                    Err(error) => {
                        this.ui
                            .apply_event(UiEvent::StartTurnResult { accepted: false });
                        this.ui.session_stream_status = format!("Turn failed to start: {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn interrupt_turn(&mut self, cx: &mut Context<Self>) {
        if !self.runtime_capabilities.interrupt_turn {
            self.ui.session_stream_status = format!(
                "Turn interrupt unavailable: {} runtime has no interrupt_turn capability",
                self.runtime_capabilities.runtime_owner
            );
            cx.notify();
            return;
        }
        let Some(session_id) = self.selected_session_id.clone() else {
            return;
        };
        if !self.ui.turn_in_flight() || self.ui.turn_command_in_flight() {
            return;
        }
        let effects = match self.ui.dispatch(UiAction::RequestInterrupt { session_id }) {
            Ok(effects) => effects,
            Err(_) => return,
        };
        let Some(UiEffect::InterruptTurn { session_id }) = effects.into_iter().next() else {
            return;
        };
        let client = Arc::clone(&self.client);
        let generation = self.session_selection_generation;
        let target_session_id = session_id.clone();
        self.ui.session_stream_status = "Requesting turn interrupt…".to_owned();
        cx.notify();
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move { client.interrupt_turn(&session_id) })
                .await;
            let _ = this.update(cx, |this, cx| {
                if this.session_selection_generation != generation
                    || this.selected_session_id.as_deref() != Some(target_session_id.as_str())
                    || !this.ui.turn_command_in_flight()
                {
                    return;
                }
                match result {
                    Ok(result) if result.session_id == target_session_id && result.ok => {
                        this.ui
                            .apply_event(UiEvent::InterruptTurnResult { accepted: true });
                        this.ui.session_stream_status =
                            "Interrupt accepted · waiting for session events".to_owned();
                    }
                    Ok(_) => {
                        this.ui
                            .apply_event(UiEvent::InterruptTurnResult { accepted: false });
                        this.ui.session_stream_status = "No active turn to interrupt".to_owned();
                    }
                    Err(error) => {
                        this.ui
                            .apply_event(UiEvent::InterruptTurnResult { accepted: false });
                        this.ui.session_stream_status = format!("Turn interrupt failed: {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn show_provider_delete_prompt(
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

    pub(crate) fn show_provider_edit_prompt(&mut self, provider: String, cx: &mut Context<Self>) {
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

    pub(crate) fn probe_provider_capability(&mut self, cx: &mut Context<Self>) {
        if self.provider_probe_in_flight {
            return;
        }
        if !self.runtime_capabilities.mutations {
            self.provider_probe_status = format!(
                "Capability check unavailable · {}",
                disabled_reason_label(
                    self.runtime_capabilities
                        .mutation_disabled_reason
                        .as_deref()
                        .unwrap_or("runtime_read_only")
                )
            );
            cx.notify();
            return;
        }
        if !self.selected_model_profile.configured {
            self.provider_probe_status =
                "Configure the selected provider before checking capability".to_owned();
            cx.notify();
            return;
        }
        let provider = self.selected_model_profile.provider.clone();
        let model = self.selected_model_profile.model.clone();
        let effort = self.selected_model_profile.effort.clone();
        self.provider_probe_in_flight = true;
        self.provider_probe_status = format!("Checking {provider} capability…");
        cx.notify();
        let client = Arc::clone(&self.client);
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_executor()
                .spawn(async move {
                    client
                        .probe_capability(&provider, &model, &effort)
                        .and_then(|_| client.capabilities())
                })
                .await;
            let _ = this.update(cx, |this, cx| {
                this.provider_probe_in_flight = false;
                match result {
                    Ok(capabilities) => {
                        this.provider_probe_status = capability_probe_status(&capabilities);
                        let readiness = readiness_from_capabilities(&capabilities);
                        this.sync_selected_model_profile(&capabilities);
                        this.runtime_capabilities = capabilities;
                        if let Err(error) = this.ui.dispatch(UiAction::SetReadiness(readiness)) {
                            this.provider_probe_status =
                                format!("Capability state refresh failed · {error:?}");
                        }
                    }
                    Err(error) => {
                        this.provider_probe_status = format!("Capability check failed · {error}");
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }

    pub(crate) fn show_custom_provider_edit_prompt(
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

impl WorkspacePrototype {
    fn active_marked_text(&self) -> &str {
        match self.input_target {
            InputTarget::Composer => &self.composer_marked_text,
            InputTarget::Terminal => &self.terminal_marked_text,
            InputTarget::ProjectName => &self.project_name_marked_text,
            InputTarget::ProjectRoots => &self.project_roots_marked_text,
            InputTarget::SessionRename => &self.session_rename_marked_text,
            InputTarget::Search => &self.search_marked_text,
        }
    }

    fn active_marked_selection(&self) -> &Range<usize> {
        match self.input_target {
            InputTarget::Composer => &self.composer_marked_selection,
            InputTarget::Terminal => &self.terminal_marked_selection,
            InputTarget::ProjectName => &self.project_name_marked_selection,
            InputTarget::ProjectRoots => &self.project_roots_marked_selection,
            InputTarget::SessionRename => &self.session_rename_marked_selection,
            InputTarget::Search => &self.search_marked_selection,
        }
    }
}

impl EntityInputHandler for WorkspacePrototype {
    fn text_for_range(
        &mut self,
        range: Range<usize>,
        adjusted_range: &mut Option<Range<usize>>,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<String> {
        let utf16: Vec<u16> = self.active_marked_text().encode_utf16().collect();
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
            range: self.active_marked_selection().clone(),
            reversed: false,
        })
    }

    fn marked_text_range(
        &self,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<Range<usize>> {
        let len = self.active_marked_text().encode_utf16().count();
        (len > 0).then_some(0..len)
    }

    fn unmark_text(&mut self, _window: &mut Window, cx: &mut Context<Self>) {
        match self.input_target {
            InputTarget::Composer => {
                let text = std::mem::take(&mut self.composer_marked_text);
                self.composer_marked_selection = 0..0;
                self.composer_text.push_str(&text);
            }
            InputTarget::Terminal => {
                let text = std::mem::take(&mut self.terminal_marked_text);
                self.terminal_marked_selection = 0..0;
                #[cfg(target_os = "macos")]
                if self.terminal_state == TerminalState::Running && !text.is_empty() {
                    self.send_terminal_bytes(text.into_bytes(), false, cx);
                }
            }
            InputTarget::ProjectName => {
                let text = std::mem::take(&mut self.project_name_marked_text);
                self.project_name_marked_selection = 0..0;
                self.project_name_text.push_str(&text);
            }
            InputTarget::ProjectRoots => {
                let text = std::mem::take(&mut self.project_roots_marked_text);
                self.project_roots_marked_selection = 0..0;
                self.project_roots_text.push_str(&text);
            }
            InputTarget::SessionRename => {
                let text = std::mem::take(&mut self.session_rename_marked_text);
                self.session_rename_marked_selection = 0..0;
                self.session_rename_text.push_str(&text);
            }
            InputTarget::Search => {
                let text = std::mem::take(&mut self.search_marked_text);
                self.search_marked_selection = 0..0;
                self.search_text.push_str(&text);
                self.refresh_search_results(cx);
            }
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
        match self.input_target {
            InputTarget::Composer => {
                self.composer_marked_text.clear();
                self.composer_marked_selection = 0..0;
                self.composer_text.push_str(text);
            }
            InputTarget::Terminal => {
                self.terminal_marked_text.clear();
                self.terminal_marked_selection = 0..0;
                #[cfg(target_os = "macos")]
                if self.terminal_state == TerminalState::Running && !text.is_empty() {
                    self.send_terminal_bytes(text.as_bytes().to_vec(), false, cx);
                }
            }
            InputTarget::ProjectName => {
                self.project_name_marked_text.clear();
                self.project_name_marked_selection = 0..0;
                self.project_name_text.push_str(text);
            }
            InputTarget::ProjectRoots => {
                self.project_roots_marked_text.clear();
                self.project_roots_marked_selection = 0..0;
                self.project_roots_text.push_str(text);
            }
            InputTarget::SessionRename => {
                self.session_rename_marked_text.clear();
                self.session_rename_marked_selection = 0..0;
                self.session_rename_text.push_str(text);
            }
            InputTarget::Search => {
                self.search_marked_text.clear();
                self.search_marked_selection = 0..0;
                self.search_text.push_str(text);
                self.refresh_search_results(cx);
            }
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
        let len = new_text.encode_utf16().count();
        let selection = new_selected_range
            .map(|range| range.start.min(len)..range.end.min(len))
            .unwrap_or(len..len);
        match self.input_target {
            InputTarget::Composer => {
                self.composer_marked_text.clear();
                self.composer_marked_text.push_str(new_text);
                self.composer_marked_selection = selection;
            }
            InputTarget::Terminal => {
                self.terminal_marked_text.clear();
                self.terminal_marked_text.push_str(new_text);
                self.terminal_marked_selection = selection;
            }
            InputTarget::ProjectName => {
                self.project_name_marked_text.clear();
                self.project_name_marked_text.push_str(new_text);
                self.project_name_marked_selection = selection;
            }
            InputTarget::ProjectRoots => {
                self.project_roots_marked_text.clear();
                self.project_roots_marked_text.push_str(new_text);
                self.project_roots_marked_selection = selection;
            }
            InputTarget::SessionRename => {
                self.session_rename_marked_text.clear();
                self.session_rename_marked_text.push_str(new_text);
                self.session_rename_marked_selection = selection;
            }
            InputTarget::Search => {
                self.search_marked_text.clear();
                self.search_marked_text.push_str(new_text);
                self.search_marked_selection = selection;
            }
        }
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
        match self.input_target {
            InputTarget::Composer => {
                self.selected_session_id.is_some()
                    && self.selected_model_profile.ready
                    && !self.ui.turn_in_flight()
                    && !self.ui.turn_command_in_flight()
            }
            InputTarget::Terminal => self.terminal_state == TerminalState::Running,
            InputTarget::ProjectName | InputTarget::ProjectRoots => {
                self.project_dialog_open && !self.project_save_in_flight
            }
            InputTarget::SessionRename => {
                self.session_rename_open && !self.session_action_in_flight
            }
            InputTarget::Search => self.search_open,
        }
    }
}

fn navigation_resize_handle(cx: &mut Context<WorkspacePrototype>) -> impl IntoElement {
    deferred(
        div()
            .id("navigation-resize-handle")
            .absolute()
            .top(px(0.0))
            .right(px(-layout::RESIZE_HIT_WIDTH / 2.0))
            .bottom(px(0.0))
            .w(px(layout::RESIZE_HIT_WIDTH))
            .cursor_col_resize()
            .block_mouse_except_scroll()
            .role(gpui::Role::Button)
            .aria_label("Resize navigation sidebar")
            .tab_index(0)
            .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
            .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
                match event.keystroke.key.as_str() {
                    "left" => this.adjust_panel_width(PanelResizeTarget::Navigation, -1.0, cx),
                    "right" => this.adjust_panel_width(PanelResizeTarget::Navigation, 1.0, cx),
                    _ => {}
                }
            }))
            .on_mouse_down(
                MouseButton::Left,
                cx.listener(|this, _, _, cx| {
                    this.start_panel_resize(PanelResizeTarget::Navigation, cx)
                }),
            )
            .on_drag(DraggedNavigationDivider, |_, _, _, cx| {
                cx.new(|_| gpui::Empty)
            }),
    )
}

fn workbench_resize_handle(cx: &mut Context<WorkspacePrototype>) -> impl IntoElement {
    deferred(
        div()
            .id("workbench-resize-handle")
            .absolute()
            .top(px(0.0))
            .left(px(-layout::RESIZE_HIT_WIDTH / 2.0))
            .bottom(px(0.0))
            .w(px(layout::RESIZE_HIT_WIDTH))
            .cursor_col_resize()
            .block_mouse_except_scroll()
            .role(gpui::Role::Button)
            .aria_label("Resize workspace workbench")
            .tab_index(0)
            .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
            .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
                match event.keystroke.key.as_str() {
                    "left" => this.adjust_panel_width(PanelResizeTarget::Workbench, 1.0, cx),
                    "right" => this.adjust_panel_width(PanelResizeTarget::Workbench, -1.0, cx),
                    _ => {}
                }
            }))
            .on_mouse_down(
                MouseButton::Left,
                cx.listener(|this, _, _, cx| {
                    this.start_panel_resize(PanelResizeTarget::Workbench, cx)
                }),
            )
            .on_drag(DraggedWorkbenchDivider, |_, _, _, cx| {
                cx.new(|_| gpui::Empty)
            }),
    )
}

pub(crate) fn file_tree_resize_handle(cx: &mut Context<WorkspacePrototype>) -> impl IntoElement {
    div()
        .id("file-tree-resize-handle")
        .relative()
        .h_full()
        .w(px(1.0))
        .flex_shrink_0()
        .bg(rgb(color::BORDER))
        .child(deferred(
            div()
                .id("file-tree-resize-hit")
                .absolute()
                .top(px(0.0))
                .left(px(-layout::RESIZE_HIT_WIDTH / 2.0))
                .bottom(px(0.0))
                .w(px(layout::RESIZE_HIT_WIDTH))
                .cursor_col_resize()
                .block_mouse_except_scroll()
                .role(gpui::Role::Button)
                .aria_label("Resize workspace file tree")
                .tab_index(0)
                .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
                    match event.keystroke.key.as_str() {
                        "left" => this.adjust_panel_width(PanelResizeTarget::FileTree, 1.0, cx),
                        "right" => this.adjust_panel_width(PanelResizeTarget::FileTree, -1.0, cx),
                        _ => {}
                    }
                }))
                .on_mouse_down(
                    MouseButton::Left,
                    cx.listener(|this, _, _, cx| {
                        this.start_panel_resize(PanelResizeTarget::FileTree, cx)
                    }),
                )
                .on_drag(DraggedFileTreeDivider, |_, _, _, cx| {
                    cx.new(|_| gpui::Empty)
                }),
        ))
}

#[allow(clippy::too_many_arguments)]
fn session_rename_dialog(
    open: bool,
    title: &str,
    status: &str,
    saving: bool,
    focus: &FocusHandle,
    entity: gpui::Entity<WorkspacePrototype>,
    cx: &mut Context<WorkspacePrototype>,
) -> gpui::AnyElement {
    if !open {
        return div().into_any_element();
    }
    let input_focus = focus.clone();
    let input_entity = entity.clone();
    let title_value = if title.is_empty() {
        "Chat name".to_owned()
    } else {
        title.to_owned()
    };
    let title_color = if title.is_empty() {
        color::TEXT_TERTIARY
    } else {
        color::TEXT_PRIMARY
    };
    let input = div()
        .id("session-rename-input")
        .h(px(42.0))
        .px_3()
        .flex()
        .items_center()
        .rounded_lg()
        .border_1()
        .border_color(rgb(color::ACCENT))
        .bg(rgb(color::CANVAS))
        .role(gpui::Role::TextInput)
        .aria_label("Chat name")
        .tab_index(0)
        .track_focus(focus)
        .on_click(cx.listener(|this, _, window, cx| this.focus_session_rename(window, cx)))
        .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
            if event.keystroke.key == "escape" {
                this.close_session_rename(cx);
            } else if event.keystroke.key == "enter" {
                this.save_session_rename(cx);
            }
        }))
        .child(
            div()
                .text_size(px(layout::TYPE_BODY))
                .text_color(rgb(title_color))
                .child(title_value),
        )
        .child(
            gpui::canvas(
                |bounds, _, _| bounds,
                move |bounds, _, window, cx| {
                    window.handle_input(
                        &input_focus,
                        gpui::ElementInputHandler::new(bounds, input_entity.clone()),
                        cx,
                    );
                },
            )
            .absolute()
            .size_full(),
        );
    div()
        .id("session-rename-overlay")
        .absolute()
        .top(px(0.0))
        .left(px(0.0))
        .right(px(0.0))
        .bottom(px(0.0))
        .flex()
        .items_center()
        .justify_center()
        .bg(rgba(0x00000026))
        .child(
            div()
                .id("session-rename-dialog")
                .w(px(420.0))
                .rounded_2xl()
                .border_1()
                .border_color(rgb(color::BORDER))
                .bg(rgb(color::ELEVATED))
                .shadow_lg()
                .p_4()
                .child(
                    div()
                        .text_size(px(layout::TYPE_SECTION))
                        .font_weight(FontWeight::SEMIBOLD)
                        .child("Rename chat"),
                )
                .child(div().mt_3().child(input))
                .child(
                    div()
                        .mt_2()
                        .min_h(px(18.0))
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(
                            if status.contains("failed") || status.contains("required") {
                                color::DANGER
                            } else {
                                color::TEXT_SECONDARY
                            },
                        ))
                        .child(status.to_owned()),
                )
                .child(
                    div()
                        .mt_4()
                        .flex()
                        .justify_end()
                        .child(
                            div()
                                .id("session-rename-cancel")
                                .px_3()
                                .py_2()
                                .rounded_lg()
                                .role(gpui::Role::Button)
                                .aria_label("Cancel rename chat")
                                .tab_index(0)
                                .child("Cancel")
                                .on_click(cx.listener(|this, _, _, cx| {
                                    this.close_session_rename(cx);
                                })),
                        )
                        .child(
                            div()
                                .id("session-rename-save")
                                .ml_2()
                                .px_3()
                                .py_2()
                                .rounded_lg()
                                .bg(rgb(if saving {
                                    color::SURFACE_SELECTED
                                } else {
                                    color::TEXT_PRIMARY
                                }))
                                .text_color(rgb(if saving {
                                    color::TEXT_TERTIARY
                                } else {
                                    color::CANVAS
                                }))
                                .role(gpui::Role::Button)
                                .aria_label("Save chat name")
                                .tab_index(0)
                                .child(if saving { "Saving…" } else { "Save" })
                                .on_click(cx.listener(|this, _, _, cx| {
                                    this.save_session_rename(cx);
                                })),
                        ),
                ),
        )
        .into_any_element()
}

fn session_delete_dialog(
    open: bool,
    title: &str,
    deleting: bool,
    cx: &mut Context<WorkspacePrototype>,
) -> gpui::AnyElement {
    if !open {
        return div().into_any_element();
    }
    div()
        .id("session-delete-overlay")
        .absolute()
        .top(px(0.0))
        .left(px(0.0))
        .right(px(0.0))
        .bottom(px(0.0))
        .flex()
        .items_center()
        .justify_center()
        .bg(rgba(0x00000026))
        .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
            if event.keystroke.key == "escape" {
                this.cancel_delete_session(cx);
            }
        }))
        .child(
            div()
                .id("session-delete-dialog")
                .w(px(420.0))
                .rounded_2xl()
                .border_1()
                .border_color(rgb(color::BORDER))
                .bg(rgb(color::ELEVATED))
                .shadow_lg()
                .p_4()
                .child(
                    div()
                        .text_size(px(layout::TYPE_SECTION))
                        .font_weight(FontWeight::SEMIBOLD)
                        .child("Delete chat?"),
                )
                .child(div().mt_3().text_size(px(layout::TYPE_BODY)).child(format!(
                    "Delete {title}? Conversation data is removed; workspace files stay untouched."
                )))
                .child(
                    div()
                        .mt_4()
                        .flex()
                        .justify_end()
                        .child(
                            div()
                                .id("session-delete-cancel")
                                .px_3()
                                .py_2()
                                .rounded_lg()
                                .role(gpui::Role::Button)
                                .aria_label("Cancel delete chat")
                                .tab_index(0)
                                .child("Cancel")
                                .on_click(cx.listener(|this, _, _, cx| {
                                    this.cancel_delete_session(cx);
                                })),
                        )
                        .child(
                            div()
                                .id("session-delete-confirm")
                                .ml_2()
                                .px_3()
                                .py_2()
                                .rounded_lg()
                                .bg(rgb(if deleting {
                                    color::SURFACE_SELECTED
                                } else {
                                    color::DANGER
                                }))
                                .text_color(rgb(if deleting {
                                    color::TEXT_TERTIARY
                                } else {
                                    color::CANVAS
                                }))
                                .role(gpui::Role::Button)
                                .aria_label("Delete chat")
                                .tab_index(0)
                                .child(if deleting {
                                    "Deleting…"
                                } else {
                                    "Delete chat"
                                })
                                .on_click(cx.listener(move |this, _, _, cx| {
                                    if !deleting {
                                        this.delete_selected_session(cx);
                                    }
                                })),
                        ),
                ),
        )
        .into_any_element()
}

#[allow(clippy::too_many_arguments)]
fn project_remove_dialog(
    open: bool,
    project_id: Option<&str>,
    project_name: &str,
    removing: bool,
    cx: &mut Context<WorkspacePrototype>,
) -> gpui::AnyElement {
    if !open {
        return div().into_any_element();
    }
    let Some(project_id) = project_id else {
        return div().into_any_element();
    };
    let project_id = project_id.to_owned();
    div()
        .id("project-remove-overlay")
        .absolute()
        .top(px(0.0))
        .left(px(0.0))
        .right(px(0.0))
        .bottom(px(0.0))
        .flex()
        .items_center()
        .justify_center()
        .bg(rgba(0x00000026))
        .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
            if event.keystroke.key == "escape" {
                this.cancel_remove_project(cx);
            }
        }))
        .child(
            div()
                .id("project-remove-dialog")
                .w(px(420.0))
                .rounded_2xl()
                .border_1()
                .border_color(rgb(color::BORDER))
                .bg(rgb(color::ELEVATED))
                .shadow_lg()
                .p_4()
                .child(
                    div()
                        .text_size(px(layout::TYPE_SECTION))
                        .font_weight(FontWeight::SEMIBOLD)
                        .child("Remove project?"),
                )
                .child(
                    div()
                        .mt_3()
                        .text_size(px(layout::TYPE_BODY))
                        .child(format!(
                            "Remove {project_name} from Codinal? Chats return to Chats; source folders and files stay untouched."
                        )),
                )
                .child(
                    div()
                        .mt_4()
                        .flex()
                        .justify_end()
                        .child(
                            div()
                                .id("project-remove-cancel")
                                .px_3()
                                .py_2()
                                .rounded_lg()
                                .role(gpui::Role::Button)
                                .aria_label("Cancel remove project")
                                .tab_index(0)
                                .child("Cancel")
                                .on_click(cx.listener(|this, _, _, cx| {
                                    this.cancel_remove_project(cx);
                                })),
                        )
                        .child(
                            div()
                                .id("project-remove-confirm")
                                .ml_2()
                                .px_3()
                                .py_2()
                                .rounded_lg()
                                .bg(rgb(if removing {
                                    color::SURFACE_SELECTED
                                } else {
                                    color::DANGER
                                }))
                                .text_color(rgb(if removing {
                                    color::TEXT_TERTIARY
                                } else {
                                    color::CANVAS
                                }))
                                .role(gpui::Role::Button)
                                .aria_label("Remove project")
                                .tab_index(0)
                                .child(if removing { "Removing…" } else { "Remove project" })
                                .on_click(cx.listener(move |this, _, _, cx| {
                                    if !removing {
                                        this.remove_project(project_id.clone(), cx);
                                    }
                                })),
                        ),
                ),
        )
        .into_any_element()
}

#[allow(clippy::too_many_arguments)]
fn project_archive_dialog(
    open: bool,
    project_id: Option<&str>,
    project_name: &str,
    chat_count: usize,
    archiving: bool,
    cx: &mut Context<WorkspacePrototype>,
) -> gpui::AnyElement {
    if !open {
        return div().into_any_element();
    }
    let Some(project_id) = project_id else {
        return div().into_any_element();
    };
    let project_id = project_id.to_owned();
    div()
        .id("project-archive-overlay")
        .absolute()
        .top(px(0.0))
        .left(px(0.0))
        .right(px(0.0))
        .bottom(px(0.0))
        .flex()
        .items_center()
        .justify_center()
        .bg(rgba(0x00000026))
        .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
            if event.keystroke.key == "escape" {
                this.cancel_archive_project(cx);
            }
        }))
        .child(
            div()
                .id("project-archive-dialog")
                .w(px(420.0))
                .rounded_2xl()
                .border_1()
                .border_color(rgb(color::BORDER))
                .bg(rgb(color::ELEVATED))
                .shadow_lg()
                .p_4()
                .child(
                    div()
                        .text_size(px(layout::TYPE_SECTION))
                        .font_weight(FontWeight::SEMIBOLD)
                        .child("Archive project chats?"),
                )
                .child(
                    div()
                        .mt_3()
                        .text_size(px(layout::TYPE_BODY))
                        .child(format!(
                            "Archive {chat_count} active chat(s) in {project_name}? The project and source folders stay untouched."
                        )),
                )
                .child(
                    div()
                        .mt_4()
                        .flex()
                        .justify_end()
                        .child(
                            div()
                                .id("project-archive-cancel")
                                .px_3()
                                .py_2()
                                .rounded_lg()
                                .role(gpui::Role::Button)
                                .aria_label("Cancel archive project chats")
                                .tab_index(0)
                                .child("Cancel")
                                .on_click(cx.listener(|this, _, _, cx| {
                                    this.cancel_archive_project(cx);
                                })),
                        )
                        .child(
                            div()
                                .id("project-archive-confirm")
                                .ml_2()
                                .px_3()
                                .py_2()
                                .rounded_lg()
                                .bg(rgb(if archiving {
                                    color::SURFACE_SELECTED
                                } else {
                                    color::TEXT_PRIMARY
                                }))
                                .text_color(rgb(if archiving {
                                    color::TEXT_TERTIARY
                                } else {
                                    color::CANVAS
                                }))
                                .role(gpui::Role::Button)
                                .aria_label("Archive project chats")
                                .tab_index(0)
                                .child(if archiving {
                                    "Archiving…"
                                } else {
                                    "Archive chats"
                                })
                                .on_click(cx.listener(move |this, _, _, cx| {
                                    if !archiving {
                                        this.archive_project_chats(project_id.clone(), cx);
                                    }
                                })),
                        ),
                ),
        )
        .into_any_element()
}

#[allow(clippy::too_many_arguments)]
fn project_dialog(
    open: bool,
    editing: bool,
    editing_id: Option<&str>,
    name: &str,
    roots: &str,
    status: &str,
    saving: bool,
    name_focus: &FocusHandle,
    roots_focus: &FocusHandle,
    entity: gpui::Entity<WorkspacePrototype>,
    cx: &mut Context<WorkspacePrototype>,
) -> gpui::AnyElement {
    if !open {
        return div().into_any_element();
    }
    let name_focus_for_input = name_focus.clone();
    let roots_focus_for_input = roots_focus.clone();
    let name_entity = entity.clone();
    let roots_entity = entity.clone();
    let name_value = if name.is_empty() {
        "Project name".to_owned()
    } else {
        name.to_owned()
    };
    let roots_value = if roots.is_empty() {
        "Add folders Codinal can read and edit".to_owned()
    } else {
        roots.to_owned()
    };
    let name_color = if name.is_empty() {
        color::TEXT_TERTIARY
    } else {
        color::TEXT_PRIMARY
    };
    let roots_color = if roots.is_empty() {
        color::TEXT_TERTIARY
    } else {
        color::TEXT_PRIMARY
    };
    let name_input = div()
        .id("project-name-input")
        .h(px(42.0))
        .px_3()
        .flex()
        .items_center()
        .rounded_lg()
        .border_1()
        .border_color(rgb(color::ACCENT))
        .bg(rgb(color::CANVAS))
        .role(gpui::Role::TextInput)
        .aria_label("Project name")
        .tab_index(0)
        .track_focus(name_focus)
        .on_click(cx.listener(|this, _, window, cx| this.focus_project_name(window, cx)))
        .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
            if event.keystroke.key == "escape" {
                this.close_project_dialog(cx);
            }
        }))
        .child(
            div()
                .text_size(px(layout::TYPE_BODY))
                .text_color(rgb(name_color))
                .child(name_value),
        )
        .child(
            gpui::canvas(
                |bounds, _, _| bounds,
                move |bounds, _, window, cx| {
                    window.handle_input(
                        &name_focus_for_input,
                        gpui::ElementInputHandler::new(bounds, name_entity.clone()),
                        cx,
                    );
                },
            )
            .absolute()
            .size_full(),
        );
    let roots_input = div()
        .id("project-roots-input")
        .h(px(88.0))
        .px_3()
        .py_2()
        .flex()
        .items_start()
        .rounded_lg()
        .border_1()
        .border_color(rgb(color::BORDER))
        .bg(rgb(color::CANVAS))
        .role(gpui::Role::TextInput)
        .aria_label("Project source folders")
        .tab_index(0)
        .track_focus(roots_focus)
        .on_click(cx.listener(|this, _, window, cx| this.focus_project_roots(window, cx)))
        .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
            if event.keystroke.key == "escape" {
                this.close_project_dialog(cx);
            }
        }))
        .child(
            div()
                .text_size(px(layout::TYPE_CONTROL))
                .text_color(rgb(roots_color))
                .child(roots_value),
        )
        .child(
            gpui::canvas(
                |bounds, _, _| bounds,
                move |bounds, _, window, cx| {
                    window.handle_input(
                        &roots_focus_for_input,
                        gpui::ElementInputHandler::new(bounds, roots_entity.clone()),
                        cx,
                    );
                },
            )
            .absolute()
            .size_full(),
        );
    let source_folders: gpui::AnyElement = if editing && !roots.trim().is_empty() {
        let mut rows = div()
            .id("project-source-folder-rows")
            .mt_1()
            .flex()
            .flex_col();
        for root in roots.lines().map(str::trim).filter(|root| !root.is_empty()) {
            let root = root.to_owned();
            let remove_root = root.clone();
            let make_primary_root = root.clone();
            let is_primary = roots
                .lines()
                .map(str::trim)
                .find(|candidate| !candidate.is_empty())
                == Some(root.as_str());
            let mut primary_button = div()
                .id(stable_element_id("project-source-primary", &root))
                .mr_1()
                .px_2()
                .py_1()
                .rounded_md()
                .text_size(px(layout::TYPE_METADATA))
                .text_color(rgb(if is_primary {
                    color::ACCENT
                } else {
                    color::TEXT_TERTIARY
                }))
                .role(gpui::Role::Button)
                .aria_label(if is_primary {
                    format!("Primary source folder {root}")
                } else {
                    format!("Make source folder {root} primary")
                })
                .tab_index(0)
                .child(if is_primary {
                    "Primary"
                } else {
                    "Make primary"
                });
            if !is_primary {
                primary_button = primary_button.on_click(cx.listener(move |this, _, _, cx| {
                    this.make_project_root_primary(make_primary_root.clone(), cx);
                }));
            }
            rows = rows.child(
                div()
                    .id(stable_element_id("project-source-folder", &root))
                    .h(px(40.0))
                    .px_3()
                    .flex()
                    .items_center()
                    .justify_between()
                    .rounded_lg()
                    .border_1()
                    .border_color(rgb(color::BORDER))
                    .bg(rgb(color::CANVAS))
                    .child(
                        div()
                            .flex()
                            .items_center()
                            .min_w(px(0.0))
                            .child(icon(Icon::Folder, color::TEXT_SECONDARY))
                            .child(
                                div()
                                    .ml_2()
                                    .text_size(px(layout::TYPE_CONTROL))
                                    .overflow_hidden()
                                    .text_ellipsis()
                                    .child(root.clone()),
                            ),
                    )
                    .child(
                        div().flex().items_center().child(primary_button).child(
                            div()
                                .id(stable_element_id("project-source-remove", &root))
                                .w(px(24.0))
                                .h(px(24.0))
                                .flex()
                                .items_center()
                                .justify_center()
                                .text_color(rgb(color::TEXT_TERTIARY))
                                .role(gpui::Role::Button)
                                .aria_label(format!("Remove source folder {root}"))
                                .tab_index(0)
                                .child(icon(Icon::Close, color::TEXT_TERTIARY))
                                .on_click(cx.listener(move |this, _, _, cx| {
                                    this.remove_project_root(remove_root.clone(), cx);
                                })),
                        ),
                    ),
            );
        }
        rows.into_any_element()
    } else {
        div().mt_1().child(roots_input).into_any_element()
    };
    let remove_project_button: gpui::AnyElement = if editing {
        let editing_id = editing_id.map(str::to_owned);
        div()
            .id("project-dialog-remove")
            .px_3()
            .py_2()
            .rounded_lg()
            .bg(rgb(color::DANGER_MUTED))
            .text_size(px(layout::TYPE_CONTROL))
            .text_color(rgb(color::DANGER))
            .role(gpui::Role::Button)
            .aria_label("Remove project")
            .tab_index(0)
            .child("Remove project")
            .on_click(cx.listener(move |this, _, _, cx| {
                if let Some(project_id) = editing_id.clone() {
                    this.close_project_dialog(cx);
                    this.request_remove_project(project_id, cx);
                }
            }))
            .into_any_element()
    } else {
        div().into_any_element()
    };
    let save_label = if editing { "Save" } else { "Create project" };
    div()
        .id("project-dialog-overlay")
        .absolute()
        .top(px(0.0))
        .left(px(0.0))
        .right(px(0.0))
        .bottom(px(0.0))
        .flex()
        .items_center()
        .justify_center()
        .bg(rgba(0x00000026))
        .child(
            div()
                .id("project-dialog")
                .w(px(520.0))
                .rounded_2xl()
                .border_1()
                .border_color(rgb(color::BORDER))
                .bg(rgb(color::ELEVATED))
                .shadow_lg()
                .p_4()
                .child(
                    div()
                        .flex()
                        .items_center()
                        .justify_between()
                        .child(
                            div()
                                .text_size(px(layout::TYPE_SECTION))
                                .font_weight(FontWeight::SEMIBOLD)
                                .child(if editing {
                                    "Edit project"
                                } else {
                                    "Create project"
                                }),
                        )
                        .child(
                            div()
                                .id("project-dialog-close")
                                .w(px(28.0))
                                .h(px(28.0))
                                .flex()
                                .items_center()
                                .justify_center()
                                .rounded_md()
                                .role(gpui::Role::Button)
                                .aria_label("Close project dialog")
                                .tab_index(0)
                                .child(icon(Icon::Close, color::TEXT_SECONDARY))
                                .on_click(
                                    cx.listener(|this, _, _, cx| this.close_project_dialog(cx)),
                                ),
                        ),
                )
                .child(div().mt_3().child(name_input))
                .child(
                    div()
                        .mt_3()
                        .text_size(px(layout::TYPE_CONTROL))
                        .font_weight(FontWeight::SEMIBOLD)
                        .child("Source folders"),
                )
                .child(source_folders)
                .child(
                    div()
                        .id("project-dialog-add-folder")
                        .mt_2()
                        .px_3()
                        .py_2()
                        .rounded_lg()
                        .bg(rgb(color::SURFACE))
                        .text_size(px(layout::TYPE_CONTROL))
                        .role(gpui::Role::Button)
                        .aria_label("Add project source folder")
                        .tab_index(0)
                        .child(icon(Icon::AddFolder, color::TEXT_SECONDARY))
                        .child(div().ml_2().child("Add folder"))
                        .on_click(cx.listener(|this, _, _, cx| this.add_project_folder(cx))),
                )
                .child(
                    div()
                        .mt_2()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::TEXT_SECONDARY))
                        .child(
                            "Add folders Codinal can read and edit; one absolute path per line.",
                        ),
                )
                .child(
                    div()
                        .mt_2()
                        .min_h(px(18.0))
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(if status.is_empty() {
                            color::TEXT_TERTIARY
                        } else if status.contains("failed") {
                            color::DANGER
                        } else {
                            color::TEXT_SECONDARY
                        }))
                        .child(status.to_owned()),
                )
                .child(
                    div()
                        .mt_4()
                        .flex()
                        .items_center()
                        .justify_end()
                        .child(remove_project_button)
                        .child(div().flex_1())
                        .child(
                            div()
                                .id("project-dialog-cancel")
                                .px_3()
                                .py_2()
                                .rounded_lg()
                                .text_size(px(layout::TYPE_CONTROL))
                                .role(gpui::Role::Button)
                                .aria_label("Cancel project")
                                .tab_index(0)
                                .child("Cancel")
                                .on_click(
                                    cx.listener(|this, _, _, cx| this.close_project_dialog(cx)),
                                ),
                        )
                        .child(
                            div()
                                .id("project-dialog-save")
                                .ml_2()
                                .px_3()
                                .py_2()
                                .rounded_lg()
                                .bg(rgb(if saving {
                                    color::SURFACE_SELECTED
                                } else {
                                    color::TEXT_PRIMARY
                                }))
                                .text_color(rgb(if saving {
                                    color::TEXT_TERTIARY
                                } else {
                                    color::CANVAS
                                }))
                                .text_size(px(layout::TYPE_CONTROL))
                                .role(gpui::Role::Button)
                                .aria_label(save_label)
                                .tab_index(0)
                                .child(if saving { "Saving…" } else { save_label })
                                .on_click(cx.listener(|this, _, _, cx| this.save_project(cx))),
                        ),
                ),
        )
        .into_any_element()
}

#[allow(clippy::too_many_arguments)]
fn search_palette(
    open: bool,
    query: &str,
    results: &[SessionSummary],
    status: &str,
    search_focus: &FocusHandle,
    entity: gpui::Entity<WorkspacePrototype>,
    cx: &mut Context<WorkspacePrototype>,
) -> gpui::AnyElement {
    if !open {
        return div().into_any_element();
    }
    let input_focus = search_focus.clone();
    let input_entity = entity.clone();
    let query_value = if query.is_empty() {
        "Search chats".to_owned()
    } else {
        query.to_owned()
    };
    let query_color = if query.is_empty() {
        color::TEXT_TERTIARY
    } else {
        color::TEXT_PRIMARY
    };
    let first_result = results.first().map(|session| session.session_id.clone());
    let search_input = div()
        .id("search-input")
        .h(px(42.0))
        .px_3()
        .flex()
        .items_center()
        .rounded_lg()
        .border_1()
        .border_color(rgb(color::ACCENT))
        .bg(rgb(color::CANVAS))
        .role(gpui::Role::TextInput)
        .aria_label("Search chats")
        .aria_keyshortcuts("⌘F")
        .tab_index(0)
        .track_focus(search_focus)
        .on_click(cx.listener(|this, _, window, cx| this.focus_search(window, cx)))
        .on_key_down(cx.listener(move |this, event: &KeyDownEvent, window, cx| {
            if event.keystroke.key.eq_ignore_ascii_case("escape") {
                this.close_search(window, cx);
            } else if event.keystroke.key.eq_ignore_ascii_case("enter") {
                if let Some(session_id) = first_result.clone() {
                    this.select_search_result(session_id, window, cx);
                }
            }
        }))
        .child(
            div()
                .mr_2()
                .text_color(rgb(color::TEXT_SECONDARY))
                .child(icon(Icon::Search, color::TEXT_SECONDARY)),
        )
        .child(
            div()
                .text_size(px(layout::TYPE_BODY))
                .text_color(rgb(query_color))
                .child(query_value),
        )
        .child(
            gpui::canvas(
                |bounds, _, _| bounds,
                move |bounds, _, window, cx| {
                    window.handle_input(
                        &input_focus,
                        gpui::ElementInputHandler::new(bounds, input_entity.clone()),
                        cx,
                    );
                },
            )
            .absolute()
            .size_full(),
        );

    let mut result_list = div()
        .id("search-results")
        .mt_2()
        .max_h(px(320.0))
        .overflow_y_scroll()
        .flex()
        .flex_col();
    for session in results.iter().take(20) {
        let session_id = session.session_id.clone();
        let keyboard_session_id = session_id.clone();
        result_list = result_list.child(
            div()
                .id(stable_element_id("search-result", &session_id))
                .px_3()
                .py_2()
                .rounded_lg()
                .role(gpui::Role::Button)
                .aria_label(format!("Open chat {}", session.title))
                .tab_index(0)
                .focus_visible(|style| style.bg(rgb(color::ACCENT_MUTED)))
                .on_key_down(cx.listener(move |this, event: &KeyDownEvent, window, cx| {
                    if is_activation_key(event) {
                        this.select_search_result(keyboard_session_id.clone(), window, cx);
                    }
                }))
                .on_click(cx.listener(move |this, _, window, cx| {
                    this.select_search_result(session_id.clone(), window, cx);
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
                                .child(format!("{} messages", session.messages)),
                        ),
                )
                .child(
                    div()
                        .mt_1()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::TEXT_SECONDARY))
                        .overflow_hidden()
                        .text_ellipsis()
                        .child(session.workspace.clone()),
                ),
        );
    }

    div()
        .id("search-overlay")
        .absolute()
        .top(px(0.0))
        .left(px(0.0))
        .right(px(0.0))
        .bottom(px(0.0))
        .flex()
        .justify_center()
        .items_start()
        .pt(px(72.0))
        .bg(rgba(0x00000018))
        .child(
            div()
                .id("search-palette")
                .w(px(560.0))
                .rounded_2xl()
                .border_1()
                .border_color(rgb(color::BORDER))
                .bg(rgb(color::ELEVATED))
                .shadow_lg()
                .p_3()
                .child(
                    div()
                        .mb_2()
                        .flex()
                        .items_center()
                        .justify_between()
                        .text_size(px(layout::TYPE_SECTION))
                        .font_weight(FontWeight::SEMIBOLD)
                        .child("Search chats")
                        .child(
                            div()
                                .text_size(px(layout::TYPE_METADATA))
                                .text_color(rgb(color::TEXT_TERTIARY))
                                .child("Esc to close"),
                        ),
                )
                .child(search_input)
                .child(result_list)
                .child(
                    div()
                        .mt_2()
                        .px_1()
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::TEXT_TERTIARY))
                        .child(status.to_owned()),
                ),
        )
        .into_any_element()
}

impl Render for WorkspacePrototype {
    fn render(&mut self, window: &mut Window, cx: &mut Context<Self>) -> impl gpui::IntoElement {
        let has_pending_approval = self.ui.has_pending_approval();
        let show_context = context_panel_should_show(self.context_panel_open, has_pending_approval);
        let resolved_shell = resolve_shell(
            self.panel_preferences,
            ShellRequest {
                viewport_width: window.viewport_size().width.as_f32(),
                navigation_open: self.navigation_open,
                workbench_open: self.dock.open(),
                context_open: show_context,
            },
        );
        let navigation_visible = self.navigation_open;
        let session_status = if self.ui.session_stream_status.is_empty() {
            self.session_status.clone()
        } else {
            format!(
                "{} · {}",
                self.session_status, self.ui.session_stream_status
            )
        };
        #[cfg(target_os = "macos")]
        let terminal_workspace = self.terminal_workspace.clone();
        #[cfg(not(target_os = "macos"))]
        let terminal_workspace = "Native workspace selection unavailable".to_owned();
        let selected_session = self.sessions.iter().find(|session| {
            self.selected_session_id.as_deref() == Some(session.session_id.as_str())
        });
        let selected_title = selected_session
            .map(|session| session.title.clone())
            .or_else(|| {
                self.selected_project_id.as_deref().and_then(|project_id| {
                    self.projects
                        .iter()
                        .find(|project| project.project_id == project_id)
                        .map(|project| project.name.clone())
                })
            })
            .unwrap_or_else(|| "New chat".to_owned());
        let starter_context = self
            .selected_project_id
            .as_deref()
            .and_then(|project_id| {
                self.projects
                    .iter()
                    .find(|project| project.project_id == project_id)
            })
            .map(|project| project.name.as_str())
            .unwrap_or("Codinal");
        let selected_workspace = self
            .selected_workspace()
            .map(|workspace| workspace.to_string_lossy().into_owned())
            .unwrap_or_default();
        let changes_status = self
            .review_snapshot
            .as_ref()
            .map(|review| review.summary.as_str())
            .unwrap_or(self.review_status.as_str());
        let show_side_tools = side_tools_should_show(self.dock.open(), has_pending_approval);
        let context_reserve = if show_context {
            resolved_shell.context_width + 32.0
        } else {
            0.0
        };
        let left_sidebar: gpui::AnyElement = if navigation_visible {
            div()
                .id("session-sidebar")
                .relative()
                .w(px(resolved_shell.navigation_width))
                .min_w(px(resolved_shell.navigation_width))
                .h_full()
                .flex()
                .flex_col()
                .bg(rgb(color::SIDEBAR))
                .border_r_1()
                .border_color(rgb(color::BORDER))
                .child(session_pane(
                    &self.sessions,
                    &self.projects,
                    self.selected_session_id.as_deref(),
                    self.selected_project_id.as_deref(),
                    self.project_hover_id.as_deref(),
                    self.project_menu_id.as_deref(),
                    self.runtime_capabilities.mutations,
                    self.runtime_capabilities
                        .mutation_disabled_reason
                        .as_deref()
                        .unwrap_or("runtime_read_only"),
                    &self.expanded_project_ids,
                    self.chats_expanded,
                    self.mode_menu_open,
                    self.activity_open,
                    &self.activity_items,
                    &self.activity_status,
                    cx,
                ))
                .child(
                    div()
                        .h(px(42.0))
                        .px_3()
                        .flex()
                        .items_center()
                        .justify_between()
                        .border_t_1()
                        .border_color(rgb(color::BORDER))
                        .text_size(px(layout::TYPE_METADATA))
                        .text_color(rgb(color::TEXT_SECONDARY))
                        .child(
                            div()
                                .flex()
                                .items_center()
                                .child(
                                    div()
                                        .mr_2()
                                        .w(px(22.0))
                                        .h(px(22.0))
                                        .flex()
                                        .items_center()
                                        .justify_center()
                                        .rounded_full()
                                        .bg(rgb(color::SURFACE_SELECTED))
                                        .text_size(px(layout::TYPE_METADATA))
                                        .child("PK"),
                                )
                                .child("Pongsathon Kheereekaew"),
                        )
                        .child(
                            div()
                                .id("sidebar-help")
                                .w(px(24.0))
                                .h(px(24.0))
                                .flex()
                                .items_center()
                                .justify_center()
                                .rounded_md()
                                .role(gpui::Role::Button)
                                .aria_label("Help")
                                .tab_index(0)
                                .child("?")
                                .on_click(cx.listener(|this, _, _, cx| {
                                    this.show_navigation_unavailable(
                                        "Help",
                                        "surface_not_implemented",
                                        cx,
                                    );
                                })),
                        ),
                )
                .child(navigation_resize_handle(cx))
                .into_any_element()
        } else {
            div().into_any_element()
        };
        let selected_session_can_run = self
            .selected_session_id
            .as_deref()
            .and_then(|id| {
                self.sessions
                    .iter()
                    .find(|session| session.session_id == id)
            })
            .is_some_and(|session| !session.archived);
        let center_pane = div()
            .id("conversation-center")
            .flex_1()
            .min_w(px(420.0))
            .min_h(px(0.0))
            .mr(px(context_reserve))
            .flex()
            .flex_col()
            .bg(rgb(color::CANVAS))
            .child(conversation_pane(
                &self.ui.workbench.blocks,
                self.ui.streaming_assistant.as_ref(),
                &self.ui.session_stream_status,
                self.selected_session_id.is_some(),
                self.selected_project_id.is_some(),
                self.runtime_capabilities.mutations,
                self.selected_model_profile.ready,
                self.runtime_capabilities
                    .mutation_disabled_reason
                    .as_deref()
                    .unwrap_or("runtime_read_only"),
                self.runtime_capabilities
                    .run_disabled_reason
                    .as_deref()
                    .unwrap_or("provider_not_configured"),
                starter_context,
                self.starter_category,
                cx,
            ))
            .child(composer_pane(
                &self.session_count,
                selected_session_can_run,
                self.selected_project_id.is_some(),
                has_pending_approval,
                self.ui.turn_in_flight(),
                self.ui.turn_command_in_flight(),
                &self.composer_text,
                &self.runtime_capabilities,
                &self.runtime_capabilities.model_profiles,
                &self.selected_model_profile,
                self.permission_profile,
                self.permission_menu_open,
                self.model_menu_open,
                &self.composer_focus,
                cx.entity(),
                cx,
            ));
        let context_panel: gpui::AnyElement = if show_context {
            div()
                .id("context-panel")
                .absolute()
                .top_4()
                .right(px(resolved_shell.context_right))
                .w(px(resolved_shell.context_width))
                .max_h(px(layout::CONTEXT_MAX_HEIGHT))
                .flex()
                .flex_col()
                .overflow_y_scroll()
                .bg(rgb(color::ELEVATED))
                .border_1()
                .border_color(rgb(color::BORDER))
                .rounded_2xl()
                .shadow_lg()
                .child(
                    div()
                        .px_4()
                        .py_3()
                        .flex()
                        .items_center()
                        .justify_between()
                        .text_size(px(layout::TYPE_SECTION))
                        .font_weight(FontWeight::SEMIBOLD)
                        .child(if has_pending_approval {
                            "Review"
                        } else {
                            "Environment"
                        })
                        .child(
                            div()
                                .text_size(px(layout::TYPE_METADATA))
                                .text_color(rgb(color::TEXT_TERTIARY))
                                .child("⌘K"),
                        ),
                )
                .child(environment_pane(
                    &selected_workspace,
                    &session_status,
                    changes_status,
                    self.review_snapshot
                        .as_ref()
                        .map(|review| review.branch.as_str())
                        .unwrap_or("Branch metadata unavailable"),
                    &self.files_status,
                    &self.source_attachments,
                    &self.sources_status,
                    self.source_menu_open,
                    self.source_operation_in_flight,
                    self.runtime_capabilities.mutations && self.selected_session_id.is_some(),
                    self.runtime_capabilities
                        .mutation_disabled_reason
                        .as_deref()
                        .unwrap_or("runtime_read_only"),
                    cx,
                ))
                .child(approval_pane(
                    &self.ui.pending_approvals,
                    has_pending_approval,
                    &self.ui.approval_review_status,
                    self.runtime_capabilities.mutations,
                    self.runtime_capabilities
                        .mutation_disabled_reason
                        .as_deref()
                        .unwrap_or("runtime_read_only"),
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
                .child(provider_settings_pane(
                    &self.provider_settings,
                    &self.provider_probe_status,
                    &self.provider_delete_targets,
                    &self.provider_edit_targets,
                    &self.custom_provider_edit_targets,
                    self.runtime_capabilities.mutations
                        && !self.provider_operation_in_flight
                        && !self.provider_probe_in_flight,
                    self.runtime_capabilities.mutations
                        && self.runtime_capabilities.provider_configured
                        && !self.provider_operation_in_flight
                        && !self.provider_probe_in_flight,
                    self.runtime_capabilities
                        .mutation_disabled_reason
                        .as_deref()
                        .unwrap_or("runtime_read_only"),
                    cx,
                ))
                .into_any_element()
        } else {
            div().into_any_element()
        };
        let file_roots = self.selected_project_roots();
        let side_chat_sessions =
            side_chat_sessions_for_parent(&self.sessions, self.side_chat_parent_id.as_deref(), 20);
        let side_tools_panel: gpui::AnyElement = if show_side_tools {
            let panel = tools_panel(
                self.dock.open_tabs(),
                self.dock.active(),
                self.dock.picker_open(),
                self.review_snapshot.as_ref(),
                &self.review_status,
                self.workspace_snapshot.as_ref(),
                &self.files_status,
                self.file_preview.as_ref(),
                &self.file_preview_status,
                &file_roots,
                self.file_root_menu_open,
                resolved_shell.file_tree_width,
                &selected_workspace,
                &self.browser_url,
                &self.browser_status,
                &self.side_chat_status,
                self.side_chat_parent_id.as_deref(),
                &side_chat_sessions,
                self.selected_session_id.as_deref(),
                self.side_chat_in_flight,
                &self.terminal_display,
                &self.terminal_status,
                self.terminal_state,
                self.dock.terminal_kept_alive(),
                &terminal_workspace,
                self.runtime_capabilities.mutations,
                self.runtime_capabilities
                    .mutation_disabled_reason
                    .as_deref()
                    .unwrap_or("runtime_read_only"),
                &self.terminal_focus,
                cx,
            );
            match resolved_shell.workbench_placement {
                WorkbenchPlacement::Docked => div()
                    .id("workspace-workbench-dock")
                    .relative()
                    .w(px(resolved_shell.workbench_width))
                    .min_w(px(resolved_shell.workbench_width))
                    .h_full()
                    .child(panel)
                    .child(workbench_resize_handle(cx))
                    .into_any_element(),
                WorkbenchPlacement::Overlay => div()
                    .id("workspace-workbench-overlay")
                    .absolute()
                    .top(px(8.0))
                    .right(px(8.0))
                    .bottom(px(8.0))
                    .w(px(resolved_shell.workbench_width))
                    .overflow_hidden()
                    .rounded_xl()
                    .border_1()
                    .border_color(rgb(color::BORDER))
                    .shadow_lg()
                    .occlude()
                    .child(panel)
                    .child(workbench_resize_handle(cx))
                    .into_any_element(),
                WorkbenchPlacement::Hidden => div().into_any_element(),
            }
        } else {
            div().into_any_element()
        };
        let workspace = div()
            .id("workbench")
            .relative()
            .flex()
            .flex_row()
            .flex_1()
            .min_h(px(0.0))
            .bg(rgb(color::CANVAS))
            .on_drag_move::<DraggedWorkbenchDivider>(
                cx.listener(|this, event, _window, cx| this.resize_workbench(event, cx)),
            )
            .on_drop::<DraggedWorkbenchDivider>(
                cx.listener(|this, _event, _window, cx| this.persist_panel_preferences(cx)),
            )
            .child(
                div()
                    .id("conversation-workspace")
                    .relative()
                    .flex_1()
                    .min_w(px(0.0))
                    .h_full()
                    .flex()
                    .child(center_pane)
                    .child(context_panel),
            )
            .child(side_tools_panel);
        let main_column = div()
            .flex_1()
            .min_w(px(0.0))
            .h_full()
            .flex()
            .flex_col()
            .bg(rgb(color::CANVAS))
            .child(workspace);
        let session_rename_dialog = session_rename_dialog(
            self.session_rename_open,
            &self.session_rename_text,
            &self.session_action_status,
            self.session_action_in_flight,
            &self.session_rename_focus,
            cx.entity(),
            cx,
        );
        let session_delete_title = selected_session
            .map(|session| session.title.as_str())
            .unwrap_or("this chat");
        let session_delete_dialog = session_delete_dialog(
            self.session_delete_confirm,
            session_delete_title,
            self.session_action_in_flight,
            cx,
        );
        let project_dialog = project_dialog(
            self.project_dialog_open,
            self.project_editing_id.is_some(),
            self.project_editing_id.as_deref(),
            &self.project_name_text,
            &self.project_roots_text,
            &self.project_status,
            self.project_save_in_flight,
            &self.project_name_focus,
            &self.project_roots_focus,
            cx.entity(),
            cx,
        );
        let remove_project_id = self.project_remove_confirm.as_deref();
        let remove_project_name = remove_project_id
            .and_then(|project_id| {
                self.projects
                    .iter()
                    .find(|project| project.project_id == project_id)
            })
            .map(|project| project.name.as_str())
            .unwrap_or("this project");
        let remove_project_dialog = project_remove_dialog(
            remove_project_id.is_some(),
            remove_project_id,
            remove_project_name,
            self.project_save_in_flight,
            cx,
        );
        let archive_project_id = self.project_archive_confirm.as_deref();
        let archive_project_name = archive_project_id
            .and_then(|project_id| {
                self.projects
                    .iter()
                    .find(|project| project.project_id == project_id)
            })
            .map(|project| project.name.as_str())
            .unwrap_or("this project");
        let archive_chat_count = archive_project_id
            .map(|project_id| {
                self.sessions
                    .iter()
                    .filter(|session| {
                        !session.archived && session.project_id.as_deref() == Some(project_id)
                    })
                    .count()
            })
            .unwrap_or(0);
        let archive_project_dialog = project_archive_dialog(
            archive_project_id.is_some(),
            archive_project_id,
            archive_project_name,
            archive_chat_count,
            self.session_action_in_flight,
            cx,
        );
        let search_palette = search_palette(
            self.search_open,
            &self.search_text,
            &self.search_results,
            &self.search_status,
            &self.search_focus,
            cx.entity(),
            cx,
        );
        let source_drawer = sources_drawer(
            self.sources_drawer_open,
            &self.source_attachments,
            &self.sources_status,
            self.source_preview.as_ref(),
            &self.source_preview_status,
            cx,
        );
        let top_chrome = header(
            &selected_title,
            selected_session,
            &self.projects,
            &self.runtime_capabilities,
            navigation_visible,
            resolved_shell.navigation_width,
            show_context,
            show_side_tools,
            self.session_menu_open,
            self.session_action_in_flight,
            self.runtime_capabilities
                .mutation_disabled_reason
                .as_deref()
                .unwrap_or("runtime_read_only"),
            &self.oauth_status,
            &self.context_panel_trigger_focus,
            &self.side_panel_trigger_focus,
            cx,
        );
        let shell_body = div()
            .relative()
            .flex()
            .flex_1()
            .min_h(px(0.0))
            .child(left_sidebar)
            .child(main_column)
            .child(session_rename_dialog)
            .child(session_delete_dialog)
            .child(project_dialog)
            .child(remove_project_dialog)
            .child(archive_project_dialog)
            .child(search_palette)
            .child(source_drawer);
        div()
            .size_full()
            .relative()
            .flex()
            .flex_col()
            .bg(rgb(color::CANVAS))
            .text_size(px(layout::TYPE_BODY))
            .text_color(rgb(color::TEXT_PRIMARY))
            .track_focus(&self.shell_focus)
            .on_mouse_move(cx.listener(|this, event: &MouseMoveEvent, window, cx| {
                this.resize_active_panel(event, window, cx)
            }))
            .on_mouse_up(
                MouseButton::Left,
                cx.listener(|this, _, _, cx| this.finish_panel_resize(cx)),
            )
            .on_drag_move::<DraggedNavigationDivider>(
                cx.listener(|this, event, _window, cx| this.resize_navigation(event, cx)),
            )
            .on_drop::<DraggedNavigationDivider>(
                cx.listener(|this, _event, _window, cx| this.persist_panel_preferences(cx)),
            )
            .on_action(cx.listener(|this, _: &NewTaskAction, _, cx| this.create_task(cx)))
            .on_action(cx.listener(|this, _: &ToggleContextAction, window, cx| {
                this.toggle_context_panel(window, cx)
            }))
            .on_action(cx.listener(|_, _: &FocusNextAction, window, cx| {
                window.focus_next(cx);
            }))
            .on_action(cx.listener(|_, _: &FocusPreviousAction, window, cx| {
                window.focus_prev(cx);
            }))
            .on_key_down(cx.listener(|this, event: &KeyDownEvent, window, cx| {
                if let Some(direction) = shell_focus_direction(event) {
                    match direction {
                        ShellFocusDirection::Next => window.focus_next(cx),
                        ShellFocusDirection::Previous => window.focus_prev(cx),
                    }
                    cx.stop_propagation();
                    return;
                }

                if event.keystroke.key.eq_ignore_ascii_case("escape") {
                    if this.search_open {
                        this.close_search(window, cx);
                    } else if this.sources_drawer_open {
                        this.close_sources_drawer(cx);
                    } else if this.activity_open {
                        this.activity_open = false;
                        cx.notify();
                    } else if this.permission_menu_open {
                        this.close_permission_menu(cx);
                    } else if this.model_menu_open {
                        this.close_model_menu(cx);
                    } else if this.mode_menu_open {
                        this.close_mode_menu(cx);
                    } else if this.project_menu_id.is_some() {
                        this.project_menu_id = None;
                        this.clear_project_hover();
                        cx.notify();
                    } else if this.project_hover_id.is_some() {
                        this.clear_project_hover();
                        cx.notify();
                    } else if this.session_menu_open {
                        this.session_menu_open = false;
                        cx.notify();
                    } else if this.ui.turn_in_flight() {
                        this.interrupt_turn(cx);
                    }
                    cx.stop_propagation();
                    return;
                }

                match shell_shortcut(event) {
                    Some(ShellShortcut::NewTask) => this.create_task(cx),
                    Some(ShellShortcut::ToggleContext) => this.toggle_context_panel(window, cx),
                    Some(ShellShortcut::Search) => this.open_search(window, cx),
                    None => {
                        let modifiers = event.keystroke.modifiers;
                        if let Some(tool) = side_panel::tool_for_shortcut(
                            &event.keystroke.key,
                            modifiers.platform,
                            modifiers.control,
                            modifiers.alt,
                            modifiers.shift,
                        ) {
                            this.activate_side_panel_tool(tool, window, cx);
                        }
                    }
                }
            }))
            .child(top_chrome)
            .child(shell_body)
    }
}

#[cfg(test)]
fn format_conversation(messages: &[codinal_control_plane_client::MessageSummary]) -> String {
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

fn capture_window_size() -> (f32, f32) {
    // WindowBounds is expressed in display pixels here. The profile names use
    // logical Codex viewport dimensions, so convert the two approved @2x
    // profiles before opening the capture window.
    match std::env::var("CODINAL_CAPTURE_PROFILE").ok().as_deref() {
        Some("window-1710x1112@2x") => (3_420.0, 2_224.0),
        Some("window-1280x720@2x") => (2_560.0, 1_440.0),
        _ => (layout::WINDOW_WIDTH, layout::WINDOW_HEIGHT),
    }
}

fn start_native_runtime() -> io::Result<NativeRuntimeStart> {
    let data_dir = desktop_data_dir()?;
    let runtime_token = mint_session_token()?;
    let secret_sync_token = Zeroizing::new(mint_session_token()?);
    let vault = PlatformSecretVault;
    let (secret_bootstrap, secret_bootstrap_error) = if std::env::var_os(
        "CODINAL_CAPTURE_NO_KEYCHAIN",
    )
    .is_some()
    {
        let message =
            "provider Keychain bootstrap skipped by CODINAL_CAPTURE_NO_KEYCHAIN".to_owned();
        eprintln!("{message}");
        (
            encode_empty_secret_bootstrap(&secret_sync_token)?,
            Some(message),
        )
    } else {
        match encode_platform_secret_bootstrap_with_timeout(
            &secret_sync_token,
            Duration::from_secs(2),
        ) {
            Ok(payload) => (payload, None),
            Err(error) => {
                let error_message = error.to_string();
                eprintln!(
                    "provider Keychain bootstrap unavailable; starting with no provider secrets: {error_message}"
                );
                (
                    encode_empty_secret_bootstrap(&secret_sync_token)?,
                    Some(error_message),
                )
            }
        }
    };
    let runtime_port = free_loopback_port()?;
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
                runtime_port,
                runtime_token.clone(),
                secret_bootstrap,
            )?,
        }
    } else {
        DesktopRuntime::Production {
            _process: launch_native_runtime_with_bootstrap(
                native_runtime_binary()?,
                &data_dir,
                runtime_port,
                runtime_token.clone(),
                secret_bootstrap,
            )?,
        }
    };
    let client = ControlPlaneClient::new(runtime_port, &runtime_token)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidInput, error.to_string()))?;
    let _health = client
        .wait_until_ready(Duration::from_secs(5))
        .map_err(|error| {
            io::Error::new(
                error.kind(),
                format!("native Rust runtime did not become healthy: {error}"),
            )
        })?;
    let provider_settings = Arc::new(ProviderSettingsController::new(
        vault,
        runtime_port,
        &runtime_token,
        &secret_sync_token,
    )?);
    let oauth_relay = Arc::new(OAuthRelayController::new(
        runtime_port,
        runtime_token,
        secret_sync_token.to_string(),
    )?);
    Ok(NativeRuntimeStart {
        client,
        runtime,
        provider_settings_controller: provider_settings,
        oauth_relay,
        secret_bootstrap_error,
    })
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
    let NativeRuntimeStart {
        client,
        runtime,
        provider_settings_controller,
        oauth_relay,
        secret_bootstrap_error,
    } = start_native_runtime()?;
    let runtime_capabilities = client.capabilities()?;
    let updater = release_updater()?;
    let panel_preferences_path = desktop_data_dir()?.join("ui-layout-v1.json");
    let panel_preferences = load_panel_preferences(&panel_preferences_path).unwrap_or_default();
    #[cfg(target_os = "macos")]
    let (terminal_registry, terminal_session_id, terminal_workspace) = prepare_native_terminal()?;
    let sessions = client.list_sessions()?;
    let projects = client.list_projects().unwrap_or_default();
    let session_count = sessions
        .iter()
        .filter(|session| !session.archived && session.origin.as_deref() != Some("side_chat"))
        .count();
    let initial_context_panel_open = !sessions.is_empty();
    let mut initial_dock = DockState::default();
    if sessions.is_empty() {
        initial_dock.dispatch(DockAction::Toggle);
    }
    let initial_messages = match sessions.first() {
        Some(session) => client.session_messages(&session.session_id)?,
        None => Vec::new(),
    };
    let initial_side_chat_parent_id = sessions.first().and_then(|session| {
        if session.origin.as_deref() == Some("side_chat") {
            session.origin_session_id.clone()
        } else {
            Some(session.session_id.clone())
        }
    });
    let client = Arc::new(client);
    let approval_session_id = sessions.first().map(|session| session.session_id.clone());
    let pending = match approval_session_id.as_deref() {
        Some(session_id) => client.pending_approvals(session_id)?,
        None => Vec::new(),
    };
    let turn_receipts = match approval_session_id.as_deref() {
        Some(session_id) => client.turn_receipts(session_id)?,
        None => Vec::new(),
    };
    let readiness = readiness_from_capabilities(&runtime_capabilities);
    let provider_probe_status = capability_probe_status(&runtime_capabilities);
    let selected_model_profile = runtime_capabilities
        .model_profiles
        .iter()
        .find(|profile| {
            profile.provider == runtime_capabilities.provider
                && profile.model == runtime_capabilities.model
                && profile.effort == runtime_capabilities.effort
        })
        .cloned()
        .unwrap_or_else(|| ModelProfile {
            provider: runtime_capabilities.provider.clone(),
            model: runtime_capabilities.model.clone(),
            effort: runtime_capabilities.effort.clone(),
            configured: runtime_capabilities.provider_configured,
            probe_status: if runtime_capabilities.start_turn {
                "passed".to_owned()
            } else {
                "unknown".to_owned()
            },
            ready: runtime_capabilities.start_turn,
        });
    let mut ui = UiState::new(readiness).map_err(|error| {
        io::Error::new(io::ErrorKind::InvalidData, format!("UI state: {error:?}"))
    })?;
    ui.dispatch(UiAction::LoadSession {
        messages: initial_messages,
        approvals: pending,
        receipts: turn_receipts,
    })
    .map_err(|error| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            format!("UI projection: {error:?}"),
        )
    })?;
    let provider_edit_targets = SUPPORTED_PROVIDERS
        .iter()
        .map(|provider| (*provider).to_owned())
        .collect();
    let (provider_settings, provider_delete_targets, custom_provider_edit_targets) =
        match secret_bootstrap_error {
            Some(error) => (
                format!("Provider Keychain status unavailable · {error}"),
                Vec::new(),
                Vec::new(),
            ),
            None => match platform_provider_status_with_timeout(Duration::from_secs(2)) {
                Ok((standard_status, custom_status)) => {
                    let (settings, delete_targets) =
                        format_provider_settings(&standard_status, &custom_status);
                    (
                        settings,
                        delete_targets,
                        custom_provider_edit_targets(&custom_status),
                    )
                }
                Err(error) => (
                    format!("Provider Keychain status unavailable · {error}"),
                    Vec::new(),
                    Vec::new(),
                ),
            },
        };
    let (oauth_url_sender, oauth_url_receiver) = sync_channel::<Zeroizing<String>>(32);
    let oauth_dropped = Arc::new(AtomicU64::new(0));
    let callback_dropped = Arc::clone(&oauth_dropped);
    let application = gpui_platform::application().with_assets(CodinalAssets);
    application.on_open_urls(move |urls| {
        enqueue_oauth_urls(&oauth_url_sender, &callback_dropped, urls);
    });
    application.run(move |cx: &mut App| {
        cx.bind_keys([
            KeyBinding::new("cmd-n", NewTaskAction, None),
            KeyBinding::new("cmd-k", ToggleContextAction, None),
            KeyBinding::new("tab", FocusNextAction, None),
            KeyBinding::new("shift-tab", FocusPreviousAction, None),
        ]);
        let (window_width, window_height) = capture_window_size();
        let bounds = Bounds::centered(None, size(px(window_width), px(window_height)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                titlebar: Some(TitlebarOptions {
                    title: Some("Codinal".into()),
                    appears_transparent: true,
                    traffic_light_position: Some(point(px(18.0), px(18.0))),
                }),
                ..Default::default()
            },
            |window, cx| {
                let entity = cx.new(|cx: &mut Context<WorkspacePrototype>| {
                    let shell_focus = cx.focus_handle();
                    shell_focus.focus(window, cx);
                    WorkspacePrototype {
                        _runtime: runtime,
                        client,
                        runtime_capabilities,
                        approval_session_id,
                        ui,
                        session_count,
                        projects,
                        selected_session_id: sessions
                            .first()
                            .map(|session| session.session_id.clone()),
                        selected_project_id: sessions
                            .first()
                            .and_then(|session| session.project_id.clone()),
                        mode_menu_open: false,
                        session_menu_open: false,
                        session_rename_open: false,
                        session_delete_confirm: false,
                        session_action_in_flight: false,
                        session_action_status: String::new(),
                        session_rename_text: String::new(),
                        session_rename_focus: cx.focus_handle(),
                        session_rename_marked_text: String::new(),
                        session_rename_marked_selection: 0..0,
                        project_hover_id: None,
                        project_hover_generation: 0,
                        project_hover_task: None,
                        project_menu_id: None,
                        expanded_project_ids: BTreeSet::new(),
                        chats_expanded: false,
                        project_dialog_open: false,
                        project_remove_confirm: None,
                        project_archive_confirm: None,
                        project_editing_id: None,
                        project_name_text: String::new(),
                        project_roots_text: String::new(),
                        project_name_marked_text: String::new(),
                        project_name_marked_selection: 0..0,
                        project_roots_marked_text: String::new(),
                        project_roots_marked_selection: 0..0,
                        project_name_focus: cx.focus_handle(),
                        project_roots_focus: cx.focus_handle(),
                        project_save_in_flight: false,
                        project_status: String::new(),
                        search_open: false,
                        search_text: String::new(),
                        search_results: Vec::new(),
                        search_status: "Search chats by title, path, or session".to_owned(),
                        search_generation: 0,
                        search_focus: cx.focus_handle(),
                        search_marked_text: String::new(),
                        search_marked_selection: 0..0,
                        source_attachments: Vec::new(),
                        sources_status: if sessions.is_empty() {
                            "Select a chat to view source attachments".to_owned()
                        } else {
                            "Loading sources…".to_owned()
                        },
                        sources_generation: 0,
                        source_menu_open: false,
                        source_operation_in_flight: false,
                        sources_drawer_open: false,
                        source_preview: None,
                        source_preview_status: "Select a source to preview".to_owned(),
                        source_preview_generation: 0,
                        activity_open: false,
                        activity_items: Vec::new(),
                        activity_status: "No new activity".to_owned(),
                        activity_generation: 0,
                        permission_profile: PermissionProfile::AskForApproval,
                        permission_menu_open: false,
                        selected_model_profile: selected_model_profile.clone(),
                        model_menu_open: false,
                        sessions,
                        session_status: "Session list loaded from execution control plane"
                            .to_owned(),
                        session_selection_generation: 0,
                        session_load_generation: 0,
                        session_load_in_flight: false,
                        session_reload_pending_reason: None,
                        session_reload_retry_count: 0,
                        session_reload_retry_task: None,
                        session_event_generation: 0,
                        session_event_task: None,
                        session_event_worker: None,
                        provider_settings,
                        provider_settings_controller,
                        provider_delete_targets,
                        provider_edit_targets,
                        custom_provider_edit_targets,
                        provider_operation_in_flight: false,
                        provider_probe_in_flight: false,
                        provider_probe_status,
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
                        shell_focus,
                        context_panel_trigger_focus: cx.focus_handle(),
                        side_panel_trigger_focus: cx.focus_handle(),
                        terminal_focus: cx.focus_handle(),
                        terminal_marked_text: String::new(),
                        terminal_marked_selection: 0..0,
                        composer_focus: cx.focus_handle(),
                        composer_text: String::new(),
                        starter_category: None,
                        composer_marked_text: String::new(),
                        composer_marked_selection: 0..0,
                        input_target: InputTarget::Composer,
                        navigation_open: true,
                        panel_preferences,
                        panel_preferences_path,
                        panel_preferences_save_task: None,
                        active_panel_resize: None,
                        context_panel_open: initial_context_panel_open,
                        dock: initial_dock,
                        review_snapshot: None,
                        review_status: "Select Review to inspect the workspace".to_owned(),
                        review_generation: 0,
                        workspace_snapshot: None,
                        files_status: "Select Files to inspect the workspace".to_owned(),
                        files_generation: 0,
                        file_root_menu_open: false,
                        selected_root_path: None,
                        file_preview: None,
                        file_preview_status: "Select a file from the workspace tree".to_owned(),
                        file_preview_generation: 0,
                        browser_url: "http://127.0.0.1:3000".to_owned(),
                        browser_status: "Ready to open a credential-free HTTP(S) URL".to_owned(),
                        side_chat_status: "Select Side chat to create an isolated chat".to_owned(),
                        side_chat_parent_id: initial_side_chat_parent_id,
                        side_chat_in_flight: false,
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
                    }
                });
                entity.update(cx, |this, cx| {
                    this.start_oauth_poll(oauth_url_receiver, cx);
                    if let Some(session_id) = this.selected_session_id.clone() {
                        this.dock
                            .dispatch(DockAction::SelectSession(Some(session_id.clone())));
                        this.session_event_generation =
                            this.session_event_generation.wrapping_add(1);
                        let generation = this.session_event_generation;
                        this.start_session_event_stream(session_id, generation, cx);
                        this.refresh_sources(cx);
                        this.refresh_review(cx);
                    }
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
    use super::ui_model::append_streaming_delta;
    use super::{
        approval_can_be_approved, approval_completion_is_current,
        approval_completion_is_current_for_request, begin_provider_operation,
        classify_provider_delete_result, classify_provider_edit_result, composer_input_is_enabled,
        context_panel_should_show, custom_provider_edit_targets, disabled_reason_label,
        format_conversation, is_activation_key, shell_focus_direction, shell_shortcut,
        stable_element_id, CustomProviderRecord, ProviderDeleteOutcome, ProviderEditOutcome,
        ShellFocusDirection, ShellShortcut,
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
    fn visual_shell_keeps_contextual_state_and_composer_readiness_explicit() {
        assert!(!context_panel_should_show(false, false));
        assert!(context_panel_should_show(false, true));
        assert!(context_panel_should_show(true, false));

        assert!(!composer_input_is_enabled(false, false, true, false, false));
        assert!(!composer_input_is_enabled(true, true, true, false, false));
        assert!(!composer_input_is_enabled(true, false, true, true, false));
        assert!(!composer_input_is_enabled(true, false, true, false, true));
        assert!(composer_input_is_enabled(true, false, true, false, false));
    }

    #[test]
    fn pending_approval_blocks_composer_even_when_runtime_is_ready() {
        assert!(!composer_input_is_enabled(true, true, true, false, false));
    }

    #[test]
    fn approval_completion_requires_the_same_request_identity() {
        assert!(approval_completion_is_current_for_request(
            4,
            Some("session-a"),
            Some("approval-a"),
            4,
            Some("session-a"),
            Some("approval-a"),
        ));
        assert!(!approval_completion_is_current_for_request(
            4,
            Some("session-a"),
            Some("approval-b"),
            4,
            Some("session-a"),
            Some("approval-a"),
        ));
    }

    #[test]
    fn rendered_identity_keys_are_domain_stable_not_positions() {
        assert_eq!(
            stable_element_id("session-row", "session-a"),
            "session-row:session-a"
        );
        assert_ne!(
            stable_element_id("session-row", "session-a"),
            stable_element_id("session-row", "session-b")
        );
    }

    #[test]
    fn approval_action_kind_comes_from_typed_runtime_identity() {
        assert!(approval_can_be_approved(Some("apply_patch")));
        assert!(!approval_can_be_approved(Some("run_command")));
        assert!(!approval_can_be_approved(Some(
            "reason mentions apply_patch"
        )));
    }

    #[test]
    fn safety_controls_accept_only_keyboard_activation_keys() {
        let event = |key: &str| KeyDownEvent {
            keystroke: Keystroke {
                key: key.to_owned(),
                key_char: None,
                modifiers: Modifiers::default(),
            },
            is_held: false,
            prefer_character_input: false,
        };
        assert!(is_activation_key(&event("Enter")));
        assert!(is_activation_key(&event("space")));
        assert!(!is_activation_key(&event("escape")));
    }

    #[test]
    fn light_shell_translates_known_runtime_reason_codes() {
        assert_eq!(
            disabled_reason_label("runtime:owner_bootstrap_deferred"),
            "Native runtime setup is still completing"
        );
        assert_eq!(disabled_reason_label("custom_reason"), "custom_reason");
    }

    #[test]
    fn light_shell_routes_platform_shortcuts_case_insensitively() {
        let event = |key: &str, platform: bool| KeyDownEvent {
            keystroke: Keystroke {
                key: key.to_owned(),
                key_char: None,
                modifiers: Modifiers {
                    platform,
                    ..Default::default()
                },
            },
            is_held: false,
            prefer_character_input: false,
        };
        assert_eq!(
            shell_shortcut(&event("K", true)),
            Some(ShellShortcut::ToggleContext)
        );
        assert_eq!(
            shell_shortcut(&event("n", true)),
            Some(ShellShortcut::NewTask)
        );
        assert_eq!(
            shell_shortcut(&event("F", true)),
            Some(ShellShortcut::Search)
        );
        assert_eq!(shell_shortcut(&event("k", false)), None);
    }

    #[test]
    fn shell_routes_tab_focus_without_intercepting_modified_tab() {
        let event = |key: &str, shift: bool, platform: bool| KeyDownEvent {
            keystroke: Keystroke {
                key: key.to_owned(),
                key_char: None,
                modifiers: Modifiers {
                    shift,
                    platform,
                    ..Default::default()
                },
            },
            is_held: false,
            prefer_character_input: false,
        };
        assert_eq!(
            shell_focus_direction(&event("Tab", false, false)),
            Some(ShellFocusDirection::Next)
        );
        assert_eq!(
            shell_focus_direction(&event("tab", true, false)),
            Some(ShellFocusDirection::Previous)
        );
        assert_eq!(shell_focus_direction(&event("tab", false, true)), None);
    }

    #[test]
    fn session_event_order_rejects_replay_duplicates_and_missing_identity() {
        use super::parse_session_event;
        use super::session_projection::{session_event_order, SessionEventOrder};

        let event = |global_sequence| {
            parse_session_event(
                format!(
                    r#"{{"type":"turn_started","turn_id":"turn-1","sequence":1,"global_sequence":{global_sequence}}}"#
                )
                .as_bytes(),
            )
            .unwrap()
        };
        let mut last = None;
        assert_eq!(
            session_event_order(&mut last, &event(10)),
            SessionEventOrder::Apply
        );
        assert_eq!(last, Some(10));
        assert_eq!(
            session_event_order(&mut last, &event(10)),
            SessionEventOrder::Duplicate
        );
        assert_eq!(
            session_event_order(&mut last, &event(9)),
            SessionEventOrder::Duplicate
        );
        assert_eq!(
            session_event_order(&mut last, &event(11)),
            SessionEventOrder::Apply
        );

        let missing_identity =
            parse_session_event(br#"{"type":"assistant_message","global_sequence":12}"#).unwrap();
        assert_eq!(
            session_event_order(&mut last, &missing_identity),
            SessionEventOrder::Invalid
        );
        assert_eq!(last, Some(11));

        let reload = parse_session_event(br#"{"type":"reload_required"}"#).unwrap();
        assert_eq!(
            session_event_order(&mut last, &reload),
            SessionEventOrder::Apply
        );
        assert_eq!(last, None);
    }

    #[test]
    fn projection_reload_requires_the_same_event_watermark() {
        assert!(super::projection_reload_is_current(
            7,
            Some("session-a"),
            Some(42),
            7,
            Some("session-a"),
            Some(42),
        ));
        assert!(!super::projection_reload_is_current(
            7,
            Some("session-a"),
            Some(43),
            7,
            Some("session-a"),
            Some(42),
        ));
        assert!(super::projection_reload_may_apply(true, false));
        assert!(!super::projection_reload_may_apply(true, true));
        assert!(!super::projection_reload_may_apply(false, false));
    }

    #[test]
    fn session_reload_retry_uses_bounded_exponential_backoff() {
        assert_eq!(
            super::session_reload_retry_delay(0),
            Some(std::time::Duration::from_millis(250))
        );
        assert_eq!(
            super::session_reload_retry_delay(1),
            Some(std::time::Duration::from_millis(500))
        );
        assert_eq!(
            super::session_reload_retry_delay(4),
            Some(std::time::Duration::from_millis(4_000))
        );
        assert_eq!(super::session_reload_retry_delay(5), None);
    }

    #[test]
    fn session_reload_coalesces_while_a_load_or_retry_is_active() {
        assert!(super::session_reload_should_coalesce(true, false));
        assert!(super::session_reload_should_coalesce(false, true));
        assert!(super::session_reload_should_coalesce(true, true));
        assert!(!super::session_reload_should_coalesce(false, false));
    }

    #[test]
    fn permission_required_keeps_the_active_side_panel_mounted() {
        assert_eq!(super::permission_required_panel_state(true), (true, true));
        assert_eq!(super::permission_required_panel_state(false), (true, false));
        assert!(super::side_tools_should_show(true, true));
        assert!(!super::side_tools_should_show(false, true));
    }

    #[test]
    fn changing_side_tools_requires_a_stable_focus_handoff() {
        use super::side_panel::SidePanelTool;

        assert!(super::side_tool_focus_handoff_required(
            Some(SidePanelTool::Review),
            SidePanelTool::Files,
            false
        ));
        assert!(super::side_tool_focus_handoff_required(
            Some(SidePanelTool::Review),
            SidePanelTool::Review,
            true
        ));
        assert!(!super::side_tool_focus_handoff_required(
            Some(SidePanelTool::Review),
            SidePanelTool::Review,
            false
        ));
    }

    #[test]
    fn streaming_assistant_buffer_is_utf8_safe_and_bounded() {
        let mut streaming = Some("abc".to_owned());
        assert!(append_streaming_delta(&mut streaming, "กข", 7));
        let streaming = streaming.unwrap();
        assert_eq!(streaming, "abcก");
        assert!(streaming.len() <= 7);
    }

    #[test]
    fn failed_approval_projection_requires_a_durable_reload() {
        assert!(!super::approval_event_requires_reload(&Some(Ok(Vec::<
            codinal_control_plane_client::PendingApproval,
        >::new(
        )))));
        assert!(super::approval_event_requires_reload(&Some(Err(
            "approval read failed".to_owned()
        ))));
        assert!(super::approval_event_requires_reload(&None));
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn terminal_leaves_global_shell_shortcuts_for_the_root_dispatcher() {
        let event = |key: &str, modifiers: Modifiers| KeyDownEvent {
            keystroke: Keystroke {
                key: key.to_owned(),
                key_char: Some(key.to_owned()),
                modifiers,
            },
            is_held: false,
            prefer_character_input: false,
        };
        let review = event(
            "g",
            Modifiers {
                control: true,
                shift: true,
                ..Default::default()
            },
        );
        assert!(!super::terminal_should_capture_key(&review));
        assert!(super::terminal_should_capture_key(&event(
            "g",
            Modifiers::default()
        )));
        assert!(!super::terminal_should_handle_key(
            false,
            &event("enter", Modifiers::default())
        ));
        assert!(super::terminal_should_handle_key(
            true,
            &event("enter", Modifiers::default())
        ));
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
