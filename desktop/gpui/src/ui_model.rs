//! Pure UI state, projections, and effects for the native workspace.
//!
//! This module owns no GPUI window, network, filesystem, provider, or runtime
//! authority.  Commands become typed effects; the composition root executes
//! those effects through the existing Rust control-plane client.

use crate::session_projection::{session_event_order, ParsedSessionEvent, SessionEventOrder};
use crate::workbench::{
    ApprovalProjection, ComposerState, Readiness, TimelineBlock, TimelineKind, WorkbenchAction,
    WorkbenchError, WorkbenchState,
};
use codinal_control_plane_client::{MessageSummary, PendingApproval, TurnReceipt};

pub const MAX_UI_MESSAGES: usize = 50;
pub const MAX_UI_APPROVALS: usize = 20;
pub const MAX_UI_RECEIPT_CHARS: usize = 8_192;
pub const MAX_STREAMING_ASSISTANT_BYTES: usize = 256 * 1_024;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum UiCommand {
    StartTurn,
    InterruptTurn,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PendingApprovalProjection {
    pub approval_id: String,
    pub tool_name: String,
    pub reason: String,
    pub risk: String,
    pub arguments: serde_json::Value,
    pub command: Option<String>,
}

impl PendingApprovalProjection {
    fn from_runtime(approval: PendingApproval) -> Self {
        Self {
            approval_id: approval.approval_id,
            tool_name: approval.tool_name,
            reason: approval.reason,
            risk: approval.risk,
            arguments: approval.arguments,
            command: approval.command,
        }
    }

    pub fn is_patch(&self) -> bool {
        self.tool_name == "apply_patch"
    }

    pub fn detail(&self) -> String {
        if self.is_patch() {
            if let Some(arguments) = self.arguments.as_object() {
                let path = arguments
                    .get("path")
                    .and_then(serde_json::Value::as_str)
                    .unwrap_or("[invalid path]");
                let patch = arguments
                    .get("patch")
                    .and_then(serde_json::Value::as_str)
                    .unwrap_or("[invalid patch]");
                let source_hash = arguments
                    .get("source_hash")
                    .and_then(serde_json::Value::as_str)
                    .unwrap_or("[missing]");
                let patch_hash = arguments
                    .get("patch_hash")
                    .and_then(serde_json::Value::as_str)
                    .unwrap_or("[missing]");
                let expiry_line = arguments
                    .get("_codinal_expires_at_ms")
                    .and_then(serde_json::Value::as_u64)
                    .map_or_else(String::new, |expires_at_ms| {
                        format!("Expiry (unix ms): {expires_at_ms}\n")
                    });
                return format!(
                    "Risk: {}\nTool: apply_patch\nPath: {path}\nSource hash: {source_hash}\nPatch hash: {patch_hash}\n{expiry_line}Full diff:\n{patch}",
                    self.risk,
                );
            }
        }
        let arguments = serde_json::to_string_pretty(&self.arguments)
            .unwrap_or_else(|_| "[invalid arguments]".to_owned());
        format!(
            "Risk: {}\nTool: {}\nReason: {}\nArguments:\n{}",
            self.risk, self.tool_name, self.reason, arguments
        )
    }

    fn workbench_projection(&self) -> ApprovalProjection {
        ApprovalProjection {
            approval_id: self.approval_id.clone(),
            tool_name: self.tool_name.clone(),
            reason: self.reason.clone(),
            full_diff: self.detail(),
        }
    }
}

#[derive(Debug, PartialEq, Eq)]
pub enum UiAction {
    SelectSession,
    LoadSession {
        messages: Vec<MessageSummary>,
        approvals: Vec<PendingApproval>,
        receipts: Vec<TurnReceipt>,
    },
    SetPendingApprovals(Vec<PendingApproval>),
    SetStreamStatus(String),
    StartTurn {
        session_id: String,
        input: String,
    },
    RequestInterrupt {
        session_id: String,
    },
    ClearStreaming,
    SetReadiness(Readiness),
}

#[derive(Debug, PartialEq, Eq)]
pub enum UiEvent {
    SessionStream {
        event: Box<ParsedSessionEvent>,
        pending: Option<Result<Vec<PendingApproval>, String>>,
    },
    StartTurnResult {
        accepted: bool,
    },
    InterruptTurnResult {
        accepted: bool,
    },
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum UiEffect {
    LoadSelectedSession { reason: &'static str },
    StartTurn { session_id: String, input: String },
    InterruptTurn { session_id: String },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum UiEventDisposition {
    Applied,
    Duplicate,
    Rejected,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct UiEventOutcome {
    pub disposition: UiEventDisposition,
    pub effects: Vec<UiEffect>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum UiModelError {
    Workbench(WorkbenchError),
    CommandAlreadyInFlight,
}

impl From<WorkbenchError> for UiModelError {
    fn from(error: WorkbenchError) -> Self {
        Self::Workbench(error)
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct UiState {
    pub workbench: WorkbenchState,
    pub streaming_assistant: Option<TimelineBlock>,
    pub pending_approvals: Vec<PendingApprovalProjection>,
    pub turn_receipts: Vec<TurnReceipt>,
    pub approval_review_status: String,
    pub session_stream_status: String,
    pub command_in_flight: Option<UiCommand>,
    pub event_watermark: Option<u64>,
}

impl UiState {
    pub fn new(readiness: Readiness) -> Result<Self, UiModelError> {
        let mut state = Self {
            workbench: WorkbenchState::default(),
            streaming_assistant: None,
            pending_approvals: Vec::new(),
            turn_receipts: Vec::new(),
            approval_review_status: "No approval action sent".to_owned(),
            session_stream_status: "Session stream inactive".to_owned(),
            command_in_flight: None,
            event_watermark: None,
        };
        state.dispatch(UiAction::SetReadiness(readiness))?;
        Ok(state)
    }

    pub fn dispatch(&mut self, action: UiAction) -> Result<Vec<UiEffect>, UiModelError> {
        UiReducer::reduce(self, action)
    }

    pub fn apply_event(&mut self, event: UiEvent) -> UiEventOutcome {
        UiReducer::apply_event(self, event)
    }

    pub fn has_pending_approval(&self) -> bool {
        !self.pending_approvals.is_empty()
    }

    pub fn pending_approval(&self) -> Option<&PendingApprovalProjection> {
        self.pending_approvals.first()
    }

    pub fn approval_id(&self) -> Option<&str> {
        self.pending_approval()
            .map(|approval| approval.approval_id.as_str())
    }

    pub fn turn_in_flight(&self) -> bool {
        matches!(
            self.workbench.composer,
            ComposerState::Running | ComposerState::Interrupting
        )
    }

    pub fn turn_command_in_flight(&self) -> bool {
        self.command_in_flight.is_some()
    }

    #[cfg(test)]
    pub fn snapshot(&self) -> String {
        let approvals = self
            .pending_approvals
            .iter()
            .map(|approval| approval.approval_id.as_str())
            .collect::<Vec<_>>()
            .join(",");
        format!(
            "{};command={:?};watermark={:?};streaming={};approvals={approvals};receipts={}",
            self.workbench.snapshot(),
            self.command_in_flight,
            self.event_watermark,
            self.streaming_assistant
                .as_ref()
                .map(|block| block.content.as_str())
                .unwrap_or("none"),
            self.turn_receipts.len(),
        )
    }

    pub fn reset_for_session(&mut self) {
        let _ = self.workbench.dispatch(WorkbenchAction::ResetSession);
        self.streaming_assistant = None;
        self.pending_approvals.clear();
        self.turn_receipts.clear();
        self.approval_review_status = "Loading approvals for selected chat".to_owned();
        self.session_stream_status = "Connecting to session stream…".to_owned();
        self.command_in_flight = None;
        self.event_watermark = None;
    }
}

pub struct UiReducer;

impl UiReducer {
    pub fn reduce(state: &mut UiState, action: UiAction) -> Result<Vec<UiEffect>, UiModelError> {
        match action {
            UiAction::SelectSession => {
                state.reset_for_session();
                Ok(Vec::new())
            }
            UiAction::LoadSession {
                messages,
                approvals,
                receipts,
            } => {
                let blocks = message_blocks(&messages, &receipts);
                state
                    .workbench
                    .dispatch(WorkbenchAction::ReplaceTimeline { blocks })?;
                state.streaming_assistant = None;
                state.turn_receipts = receipts;
                set_pending_approvals(state, approvals)?;
                Ok(Vec::new())
            }
            UiAction::SetPendingApprovals(pending) => {
                set_pending_approvals(state, pending)?;
                Ok(Vec::new())
            }
            UiAction::SetStreamStatus(status) => {
                state.session_stream_status = status;
                Ok(Vec::new())
            }
            UiAction::StartTurn { session_id, input } => {
                if state.command_in_flight.is_some() {
                    return Err(UiModelError::CommandAlreadyInFlight);
                }
                state.workbench.dispatch(WorkbenchAction::SubmitRun)?;
                state.command_in_flight = Some(UiCommand::StartTurn);
                Ok(vec![UiEffect::StartTurn { session_id, input }])
            }
            UiAction::RequestInterrupt { session_id } => {
                if state.command_in_flight.is_some() {
                    return Err(UiModelError::CommandAlreadyInFlight);
                }
                state
                    .workbench
                    .dispatch(WorkbenchAction::RequestInterrupt)?;
                state.command_in_flight = Some(UiCommand::InterruptTurn);
                Ok(vec![UiEffect::InterruptTurn { session_id }])
            }
            UiAction::ClearStreaming => {
                state.streaming_assistant = None;
                Ok(Vec::new())
            }
            UiAction::SetReadiness(readiness) => {
                state
                    .workbench
                    .dispatch(WorkbenchAction::SetReadiness(readiness))?;
                Ok(Vec::new())
            }
        }
    }

    pub fn apply_event(state: &mut UiState, event: UiEvent) -> UiEventOutcome {
        match event {
            UiEvent::StartTurnResult { accepted } => {
                if state.command_in_flight == Some(UiCommand::StartTurn) {
                    state.command_in_flight = None;
                    if !accepted {
                        let _ = state.workbench.dispatch(WorkbenchAction::ResetTurn);
                    }
                }
                UiEventOutcome {
                    disposition: UiEventDisposition::Applied,
                    effects: Vec::new(),
                }
            }
            UiEvent::InterruptTurnResult { accepted } => {
                if state.command_in_flight == Some(UiCommand::InterruptTurn) {
                    state.command_in_flight = None;
                    if !accepted {
                        let _ = state.workbench.dispatch(WorkbenchAction::ResetTurn);
                    }
                }
                UiEventOutcome {
                    disposition: UiEventDisposition::Applied,
                    effects: Vec::new(),
                }
            }
            UiEvent::SessionStream { event, pending } => {
                apply_session_event(state, *event, pending)
            }
        }
    }
}

fn apply_session_event(
    state: &mut UiState,
    event: ParsedSessionEvent,
    pending: Option<Result<Vec<PendingApproval>, String>>,
) -> UiEventOutcome {
    match session_event_order(&mut state.event_watermark, &event) {
        SessionEventOrder::Duplicate => {
            return UiEventOutcome {
                disposition: UiEventDisposition::Duplicate,
                effects: Vec::new(),
            };
        }
        SessionEventOrder::Invalid => {
            state.session_stream_status = "Rejected unordered session event".to_owned();
            return UiEventOutcome {
                disposition: UiEventDisposition::Rejected,
                effects: Vec::new(),
            };
        }
        SessionEventOrder::Apply => {}
    }

    let mut effects = Vec::new();
    match event.event_type.as_str() {
        "reload_required" => {
            state.streaming_assistant = None;
            state.session_stream_status = if event.status.is_empty() {
                "Runtime requested a durable session reload".to_owned()
            } else {
                format!("Runtime requested reload: {}", event.status)
            };
            effects.push(UiEffect::LoadSelectedSession {
                reason: "Session reloaded after runtime cursor reset",
            });
        }
        "stream_error" => {
            reset_turn(state);
            state.streaming_assistant = None;
            state.session_stream_status = if !event.error.is_empty() {
                format!("Stream error: {}", event.error)
            } else if !event.status.is_empty() {
                format!("Stream error: {}", event.status)
            } else {
                "Runtime session stream error".to_owned()
            };
            effects.push(UiEffect::LoadSelectedSession {
                reason: "Session reloaded after stream error",
            });
        }
        "turn_start" | "turn_started" => {
            state.command_in_flight = None;
            observe_turn_started(state);
            state.session_stream_status = "Session turn running".to_owned();
        }
        "turn_end" | "turn_completed" => {
            reset_turn(state);
            state.streaming_assistant = None;
            state.session_stream_status = "Session turn completed".to_owned();
            effects.push(UiEffect::LoadSelectedSession {
                reason: "Session synchronized after turn completion",
            });
        }
        "interrupted" | "turn_interrupted" => {
            reset_turn(state);
            state.streaming_assistant = None;
            state.session_stream_status = "Session turn interrupted".to_owned();
            effects.push(UiEffect::LoadSelectedSession {
                reason: "Session synchronized after turn interruption",
            });
        }
        "approval_expired" => {
            reset_turn(state);
            state.streaming_assistant = None;
            state.session_stream_status = "Approval expired; session turn failed".to_owned();
            effects.push(UiEffect::LoadSelectedSession {
                reason: "Session synchronized after approval expiry",
            });
        }
        "assistant_delta" if !event.text.is_empty() => {
            let mut text = state.streaming_assistant.take().map(|block| block.content);
            let truncated =
                append_streaming_delta(&mut text, &event.text, MAX_STREAMING_ASSISTANT_BYTES);
            state.streaming_assistant = Some(TimelineBlock {
                block_id: "assistant-stream".to_owned(),
                kind: TimelineKind::Assistant,
                content: text.unwrap_or_default(),
                streaming: true,
            });
            if truncated {
                state.session_stream_status =
                    "Live assistant output truncated; waiting for durable message".to_owned();
            }
        }
        "assistant_message" => {
            state.streaming_assistant = None;
            effects.push(UiEffect::LoadSelectedSession {
                reason: "Session synchronized after assistant message",
            });
        }
        "error" => {
            reset_turn(state);
            state.streaming_assistant = None;
            state.session_stream_status = if event.error.is_empty() {
                "Session turn failed".to_owned()
            } else {
                format!("Stream error: {}", event.error)
            };
            effects.push(UiEffect::LoadSelectedSession {
                reason: "Session synchronized after turn failure",
            });
        }
        "permission_required" => {
            let reload_required = match pending {
                Some(Ok(pending)) => {
                    state.session_stream_status = "Approval request from runtime".to_owned();
                    set_pending_approvals(state, pending).is_err()
                }
                Some(Err(error)) => {
                    let _ = set_pending_approvals(state, Vec::new());
                    state.approval_review_status =
                        "Approval controls disabled until reload succeeds".to_owned();
                    state.session_stream_status = format!("Approval review reload failed: {error}");
                    true
                }
                None => {
                    let _ = set_pending_approvals(state, Vec::new());
                    state.approval_review_status =
                        "Approval controls disabled until reload succeeds".to_owned();
                    state.session_stream_status =
                        "Approval event did not include review state".to_owned();
                    true
                }
            };
            if reload_required {
                effects.push(UiEffect::LoadSelectedSession {
                    reason: "Session reloaded after approval projection failure",
                });
            }
        }
        "tool_proposed" if !event.name.is_empty() => {
            state.session_stream_status = format!("Tool proposed: {}", event.name);
        }
        "tool_started" => {
            if !event.name.is_empty() {
                state.session_stream_status = format!("Tool running: {}", event.name);
            }
            if !event.status.is_empty() {
                state.session_stream_status = format!("Tool started: {}", event.status);
            }
        }
        "tool_finished" => {
            if !event.name.is_empty() {
                state.session_stream_status = format!("Tool finished: {}", event.name);
            }
            if !event.status.is_empty() {
                state.session_stream_status = format!("Tool result: {}", event.status);
            }
        }
        "worker_status" if !event.name.is_empty() => {
            state.session_stream_status = format!("Worker update: {}", event.name);
        }
        "plan_build_status" if !event.status.is_empty() => {
            state.session_stream_status = format!("Plan build: {}", event.status);
        }
        "goal_status" if !event.status.is_empty() => {
            state.session_stream_status = format!("Goal: {}", event.status);
        }
        _ => {}
    }
    UiEventOutcome {
        disposition: UiEventDisposition::Applied,
        effects,
    }
}

fn set_pending_approvals(
    state: &mut UiState,
    pending: Vec<PendingApproval>,
) -> Result<(), UiModelError> {
    state.pending_approvals = pending
        .into_iter()
        .take(MAX_UI_APPROVALS)
        .map(PendingApprovalProjection::from_runtime)
        .collect();
    if let Some(approval) = state.pending_approvals.first() {
        state.workbench.dispatch(WorkbenchAction::BeginApproval(
            approval.workbench_projection(),
        ))?;
    } else {
        state.workbench.dispatch(WorkbenchAction::ClearApproval)?;
    }
    Ok(())
}

fn message_blocks(messages: &[MessageSummary], receipts: &[TurnReceipt]) -> Vec<TimelineBlock> {
    let mut blocks = messages
        .iter()
        .take(MAX_UI_MESSAGES)
        .enumerate()
        .map(|(index, message)| TimelineBlock {
            block_id: format!("message-{index}"),
            kind: timeline_kind(&message.role),
            content: message.text.clone(),
            streaming: false,
        })
        .collect::<Vec<_>>();
    let remaining = MAX_UI_MESSAGES.saturating_sub(blocks.len());
    blocks.extend(
        receipts
            .iter()
            .rev()
            .take(remaining)
            .enumerate()
            .map(|(index, receipt)| TimelineBlock {
                block_id: format!("receipt-{index}"),
                kind: TimelineKind::Receipt,
                content: receipt_summary(receipt),
                streaming: false,
            }),
    );
    blocks
}

fn receipt_summary(receipt: &TurnReceipt) -> String {
    let outcome = receipt.outcome.as_object();
    let status = outcome
        .and_then(|value| value.get("status"))
        .and_then(serde_json::Value::as_str)
        .unwrap_or("unknown");
    let provider = outcome
        .and_then(|value| value.get("provider"))
        .and_then(serde_json::Value::as_str)
        .unwrap_or("");
    let model = outcome
        .and_then(|value| value.get("model"))
        .and_then(serde_json::Value::as_str)
        .unwrap_or("");
    let effort = outcome
        .and_then(|value| value.get("effort"))
        .and_then(serde_json::Value::as_str)
        .unwrap_or("");
    let identity = [provider, model, effort]
        .into_iter()
        .filter(|value| !value.is_empty())
        .collect::<Vec<_>>()
        .join(" · ");
    let text = outcome
        .and_then(|value| value.get("text"))
        .and_then(serde_json::Value::as_str)
        .or_else(|| {
            outcome
                .and_then(|value| value.get("reason"))
                .and_then(serde_json::Value::as_str)
        })
        .unwrap_or("No terminal response text");
    let text = text.chars().take(MAX_UI_RECEIPT_CHARS).collect::<String>();
    if identity.is_empty() {
        format!("{text}\n\n{status}")
    } else {
        format!("{text}\n\n{status} · {identity}")
    }
}

fn timeline_kind(role: &str) -> TimelineKind {
    if role.eq_ignore_ascii_case("user") {
        TimelineKind::User
    } else if role.to_ascii_lowercase().starts_with("assistant") {
        TimelineKind::Assistant
    } else if role.eq_ignore_ascii_case("tool") {
        TimelineKind::Tool
    } else if role.eq_ignore_ascii_case("approval") {
        TimelineKind::Approval
    } else if role.eq_ignore_ascii_case("receipt") {
        TimelineKind::Receipt
    } else {
        TimelineKind::System
    }
}

fn observe_turn_started(state: &mut UiState) {
    if state.workbench.composer == ComposerState::Idle {
        let _ = state
            .workbench
            .dispatch(WorkbenchAction::ObserveTurnStarted);
    } else if state.workbench.composer == ComposerState::Interrupting {
        state.workbench.composer = ComposerState::Running;
    }
}

fn reset_turn(state: &mut UiState) {
    state.command_in_flight = None;
    let _ = state.workbench.dispatch(WorkbenchAction::ResetTurn);
}

pub(crate) fn append_streaming_delta(
    streaming: &mut Option<String>,
    delta: &str,
    limit: usize,
) -> bool {
    let value = streaming.get_or_insert_with(String::new);
    let remaining = limit.saturating_sub(value.len());
    if delta.len() <= remaining {
        value.push_str(delta);
        return false;
    }
    let mut boundary = remaining.min(delta.len());
    while !delta.is_char_boundary(boundary) {
        boundary = boundary.saturating_sub(1);
    }
    value.push_str(&delta[..boundary]);
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    use codinal_control_plane_client::{MessageSummary, TurnReceipt};

    fn ready_state() -> UiState {
        UiState::new(Readiness::Ready).expect("ready state")
    }

    fn event(raw: &str) -> ParsedSessionEvent {
        crate::session_projection::parse_session_event(raw.as_bytes()).expect("event")
    }

    #[test]
    fn load_projection_keeps_typed_message_blocks_and_receipts_bounded() {
        let mut state = ready_state();
        let messages = (0..(MAX_UI_MESSAGES + 1))
            .map(|index| MessageSummary {
                role: "assistant".to_owned(),
                text: format!("message-{index}"),
            })
            .collect();
        state
            .dispatch(UiAction::LoadSession {
                messages,
                approvals: Vec::new(),
                receipts: Vec::new(),
            })
            .expect("load");
        assert_eq!(state.workbench.blocks.len(), MAX_UI_MESSAGES);
        assert_eq!(state.workbench.blocks[0].block_id, "message-0");
        assert_eq!(state.workbench.blocks[0].kind, TimelineKind::Assistant);
    }

    #[test]
    fn load_projection_renders_terminal_receipt_when_messages_are_empty() {
        let mut state = ready_state();
        state
            .dispatch(UiAction::LoadSession {
                messages: Vec::new(),
                approvals: Vec::new(),
                receipts: vec![TurnReceipt {
                    turn_id: "turn-1".to_owned(),
                    session_id: "session-1".to_owned(),
                    outcome: serde_json::json!({
                        "status": "completed",
                        "text": "GPUI_LIVE_OK",
                        "provider": "opencode-go",
                        "model": "kimi-k2.7-code",
                        "effort": "medium"
                    }),
                    message_count: 0,
                    created_at: "2026-08-02T00:00:00Z".to_owned(),
                }],
            })
            .expect("load");
        assert_eq!(state.workbench.blocks.len(), 1);
        assert_eq!(state.workbench.blocks[0].kind, TimelineKind::Receipt);
        assert!(state.workbench.blocks[0].content.contains("GPUI_LIVE_OK"));
        assert!(state.workbench.blocks[0]
            .content
            .contains("opencode-go · kimi-k2.7-code · medium"));
    }

    #[test]
    fn command_actions_produce_effects_and_runtime_rejection_resets_state() {
        let mut state = ready_state();
        let effects = state
            .dispatch(UiAction::StartTurn {
                session_id: "session-1".to_owned(),
                input: "hello".to_owned(),
            })
            .expect("start");
        assert_eq!(
            effects,
            vec![UiEffect::StartTurn {
                session_id: "session-1".to_owned(),
                input: "hello".to_owned(),
            }]
        );
        assert!(state.turn_in_flight());
        assert!(state.turn_command_in_flight());
        state.apply_event(UiEvent::StartTurnResult { accepted: false });
        assert!(!state.turn_in_flight());
        assert!(!state.turn_command_in_flight());
    }

    #[test]
    fn duplicate_and_invalid_stream_events_do_not_change_timeline() {
        let mut state = ready_state();
        let first = state.apply_event(UiEvent::SessionStream {
            event: Box::new(event(
                r#"{"type":"assistant_delta","turn_id":"turn-1","sequence":1,"global_sequence":10,"text":"hi"}"#,
            )),
            pending: None,
        });
        assert_eq!(first.disposition, UiEventDisposition::Applied);
        let duplicate = state.apply_event(UiEvent::SessionStream {
            event: Box::new(event(
                r#"{"type":"assistant_delta","turn_id":"turn-1","sequence":1,"global_sequence":10,"text":"hi"}"#,
            )),
            pending: None,
        });
        assert_eq!(duplicate.disposition, UiEventDisposition::Duplicate);
        assert_eq!(
            state.streaming_assistant.as_ref().expect("stream").content,
            "hi"
        );
        let invalid = state.apply_event(UiEvent::SessionStream {
            event: Box::new(event(r#"{"type":"assistant_delta","global_sequence":11}"#)),
            pending: None,
        });
        assert_eq!(invalid.disposition, UiEventDisposition::Rejected);
    }

    #[test]
    fn approval_projection_is_typed_and_requires_reload_when_review_is_unavailable() {
        let mut state = ready_state();
        let outcome = state.apply_event(UiEvent::SessionStream {
            event: Box::new(event(
                r#"{"type":"permission_required","turn_id":"turn-1","sequence":1,"global_sequence":12}"#,
            )),
            pending: None,
        });
        assert_eq!(outcome.disposition, UiEventDisposition::Applied);
        assert_eq!(
            outcome.effects,
            vec![UiEffect::LoadSelectedSession {
                reason: "Session reloaded after approval projection failure"
            }]
        );
        assert!(!state.has_pending_approval());
    }

    #[test]
    fn approval_expiry_resets_the_running_turn_and_reloads_receipt_state() {
        let mut state = ready_state();
        state
            .dispatch(UiAction::StartTurn {
                session_id: "session-1".to_owned(),
                input: "run".to_owned(),
            })
            .expect("start");
        let outcome = state.apply_event(UiEvent::SessionStream {
            event: Box::new(event(
                r#"{"type":"approval_expired","turn_id":"turn-1","sequence":1,"global_sequence":13,"status":"failed"}"#,
            )),
            pending: None,
        });
        assert_eq!(outcome.disposition, UiEventDisposition::Applied);
        assert_eq!(state.workbench.composer, ComposerState::Idle);
        assert!(!state.turn_in_flight());
        assert_eq!(
            outcome.effects,
            vec![UiEffect::LoadSelectedSession {
                reason: "Session synchronized after approval expiry"
            }]
        );
    }

    #[test]
    fn snapshot_is_stable_for_a_replayable_ui_projection() {
        let mut state = ready_state();
        state
            .dispatch(UiAction::LoadSession {
                messages: vec![MessageSummary {
                    role: "user".to_owned(),
                    text: "hello".to_owned(),
                }],
                approvals: Vec::new(),
                receipts: Vec::new(),
            })
            .expect("load");
        let snapshot = state.snapshot();
        assert!(snapshot.contains("message-0:User:final:\"hello\""));
        assert!(snapshot.contains("watermark=None"));
        assert!(snapshot.contains("approvals="));
    }
}
