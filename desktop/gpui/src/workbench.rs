//! Pure Codinal workbench projections and state transitions.
//!
//! GPUI owns rendering and input plumbing; this module owns the safety
//! contract that rendering must reflect. Keeping the reducer independent from
//! entities makes live and replayed turns use the same state machine.

use std::collections::BTreeMap;

pub const MAX_TRANSCRIPT_BLOCKS: usize = 4_096;
pub const MAX_TRANSCRIPT_BYTES: usize = 4 * 1024 * 1024;
pub const MAX_STREAM_DELTA_BYTES: usize = 64 * 1024;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Appearance {
    Light,
    Dark,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Readiness {
    Ready,
    Disabled { reason: String },
}

impl Readiness {
    pub fn is_ready(&self) -> bool {
        matches!(self, Self::Ready)
    }

    pub fn reason(&self) -> Option<&str> {
        match self {
            Self::Ready => None,
            Self::Disabled { reason } => Some(reason),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ComposerState {
    Idle,
    Running,
    Interrupting,
    ApprovalPending,
    Reconnecting,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TimelineKind {
    User,
    Assistant,
    Tool,
    Approval,
    Receipt,
    System,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TimelineBlock {
    pub block_id: String,
    pub kind: TimelineKind,
    pub content: String,
    pub streaming: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ApprovalProjection {
    pub approval_id: String,
    pub tool_name: String,
    pub reason: String,
    pub full_diff: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LayoutAnatomy {
    pub top_bar_height: u16,
    pub sidebar_width: u16,
    pub center_is_primary: bool,
    pub context_panel_visible: bool,
    pub context_panel_reason: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AccessibleControl {
    pub id: &'static str,
    pub label: &'static str,
    pub shortcut: &'static str,
    pub enabled: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum WorkbenchAction {
    ResetSession,
    ResetTurn,
    ObserveTurnStarted,
    ReplaceTimeline {
        blocks: Vec<TimelineBlock>,
    },
    SetReadiness(Readiness),
    SetAppearance(Appearance),
    SetReducedMotion(bool),
    SubmitRun,
    RequestInterrupt,
    BeginApproval(ApprovalProjection),
    ResolveApproval {
        approval_id: String,
        outcome: ApprovalOutcome,
    },
    ClearApproval,
    Approve,
    Deny,
    StreamDelta {
        block_id: String,
        kind: TimelineKind,
        delta: String,
    },
    FlushStream,
    CompleteReceipt {
        block_id: String,
        summary: String,
    },
    BeginReconnect,
    FinishReconnect,
    UserScrolledAway,
    FollowBottom,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ApprovalOutcome {
    Approve,
    Deny,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FollowBehavior {
    Instant,
    Smooth,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum WorkbenchError {
    ReadinessDisabled(String),
    InvalidTransition(&'static str),
    InvalidBlockId,
    DeltaTooLarge,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct WorkbenchState {
    pub appearance: Appearance,
    pub reduced_motion: bool,
    pub readiness: Readiness,
    pub composer: ComposerState,
    pub blocks: Vec<TimelineBlock>,
    pub approval: Option<ApprovalProjection>,
    pub follow_bottom: bool,
    pending_stream: BTreeMap<String, (TimelineKind, String)>,
}

impl Default for WorkbenchState {
    fn default() -> Self {
        Self {
            appearance: Appearance::Light,
            reduced_motion: false,
            readiness: Readiness::Disabled {
                reason: "experimental_execution_disabled".to_owned(),
            },
            composer: ComposerState::Idle,
            blocks: Vec::new(),
            approval: None,
            follow_bottom: true,
            pending_stream: BTreeMap::new(),
        }
    }
}

impl WorkbenchState {
    pub fn dispatch(&mut self, action: WorkbenchAction) -> Result<(), WorkbenchError> {
        match action {
            WorkbenchAction::ResetSession => {
                self.blocks.clear();
                self.pending_stream.clear();
                self.approval = None;
                self.composer = ComposerState::Idle;
                self.follow_bottom = true;
            }
            WorkbenchAction::ResetTurn => {
                self.pending_stream.clear();
                self.composer = ComposerState::Idle;
            }
            WorkbenchAction::ObserveTurnStarted => self.composer = ComposerState::Running,
            WorkbenchAction::ReplaceTimeline { blocks } => {
                for block in &blocks {
                    validate_block_id(&block.block_id)?;
                }
                self.blocks = blocks;
                self.pending_stream.clear();
                self.follow_bottom = true;
            }
            WorkbenchAction::SetReadiness(readiness) => {
                if !readiness.is_ready() && self.composer == ComposerState::Running {
                    self.composer = ComposerState::Reconnecting;
                }
                self.readiness = readiness;
            }
            WorkbenchAction::SetAppearance(appearance) => self.appearance = appearance,
            WorkbenchAction::SetReducedMotion(reduced_motion) => {
                self.reduced_motion = reduced_motion
            }
            WorkbenchAction::SubmitRun => {
                if let Some(reason) = self.readiness.reason() {
                    return Err(WorkbenchError::ReadinessDisabled(reason.to_owned()));
                }
                if self.approval.is_some() {
                    return Err(WorkbenchError::InvalidTransition(
                        "approval must be resolved before running",
                    ));
                }
                if self.composer != ComposerState::Idle {
                    return Err(WorkbenchError::InvalidTransition(
                        "run requires an idle composer",
                    ));
                }
                self.composer = ComposerState::Running;
            }
            WorkbenchAction::RequestInterrupt => {
                if self.composer != ComposerState::Running {
                    return Err(WorkbenchError::InvalidTransition(
                        "interrupt requires a running turn",
                    ));
                }
                self.composer = ComposerState::Interrupting;
            }
            WorkbenchAction::BeginApproval(approval) => {
                if approval.approval_id.is_empty()
                    || approval.tool_name.is_empty()
                    || approval.full_diff.is_empty()
                {
                    return Err(WorkbenchError::InvalidTransition(
                        "approval must include a full diff",
                    ));
                }
                self.approval = Some(approval);
                self.composer = ComposerState::ApprovalPending;
            }
            WorkbenchAction::ResolveApproval {
                approval_id,
                outcome: _outcome,
            } => {
                let Some(approval) = self.approval.as_ref() else {
                    return Err(WorkbenchError::InvalidTransition(
                        "approval decision has no pending request",
                    ));
                };
                if approval.approval_id != approval_id {
                    return Err(WorkbenchError::InvalidTransition(
                        "approval decision does not match the pending request",
                    ));
                }
                self.approval = None;
                self.composer = ComposerState::Idle;
            }
            WorkbenchAction::ClearApproval => {
                self.approval = None;
                if self.composer == ComposerState::ApprovalPending {
                    self.composer = ComposerState::Idle;
                }
            }
            WorkbenchAction::Approve | WorkbenchAction::Deny => {
                return Err(WorkbenchError::InvalidTransition(
                    "approval decisions must identify the pending request",
                ));
            }
            WorkbenchAction::StreamDelta {
                block_id,
                kind,
                delta,
            } => {
                validate_block_id(&block_id)?;
                if delta.len() > MAX_STREAM_DELTA_BYTES {
                    return Err(WorkbenchError::DeltaTooLarge);
                }
                if let Some(existing) = self
                    .blocks
                    .iter()
                    .find(|existing| existing.block_id == block_id)
                {
                    if existing.kind != kind {
                        return Err(WorkbenchError::InvalidTransition(
                            "stream block kind changed",
                        ));
                    }
                    if !existing.streaming {
                        return Err(WorkbenchError::InvalidTransition(
                            "stream block is already finalized",
                        ));
                    }
                }
                let entry = self
                    .pending_stream
                    .entry(block_id)
                    .or_insert_with(|| (kind, String::new()));
                if entry.0 != kind {
                    return Err(WorkbenchError::InvalidTransition(
                        "stream block kind changed",
                    ));
                }
                entry.1.push_str(&delta);
            }
            WorkbenchAction::FlushStream => self.flush_stream()?,
            WorkbenchAction::CompleteReceipt { block_id, summary } => {
                validate_block_id(&block_id)?;
                self.pending_stream.remove(&block_id);
                replace_block(
                    &mut self.blocks,
                    TimelineBlock {
                        block_id,
                        kind: TimelineKind::Receipt,
                        content: summary,
                        streaming: false,
                    },
                );
                self.composer = ComposerState::Idle;
                self.follow_bottom = true;
            }
            WorkbenchAction::BeginReconnect => self.composer = ComposerState::Reconnecting,
            WorkbenchAction::FinishReconnect => {
                if self.composer == ComposerState::Reconnecting {
                    self.composer = ComposerState::Idle;
                }
            }
            WorkbenchAction::UserScrolledAway => self.follow_bottom = false,
            WorkbenchAction::FollowBottom => self.follow_bottom = true,
        }
        self.trim_transcript();
        Ok(())
    }

    pub fn flush_stream(&mut self) -> Result<(), WorkbenchError> {
        let pending = std::mem::take(&mut self.pending_stream);
        for (block_id, (kind, content)) in pending {
            upsert_block(
                &mut self.blocks,
                TimelineBlock {
                    block_id,
                    kind,
                    content,
                    streaming: true,
                },
            );
        }
        Ok(())
    }

    pub fn layout_anatomy(&self) -> LayoutAnatomy {
        LayoutAnatomy {
            top_bar_height: 52,
            sidebar_width: 280,
            center_is_primary: true,
            context_panel_visible: self.approval.is_some(),
            context_panel_reason: self
                .approval
                .as_ref()
                .map(|approval| format!("Review {} before continuing", approval.tool_name)),
        }
    }

    pub fn follow_behavior(&self) -> FollowBehavior {
        if self.reduced_motion {
            FollowBehavior::Instant
        } else {
            FollowBehavior::Smooth
        }
    }

    pub fn accessibility_controls(&self) -> Vec<AccessibleControl> {
        vec![
            AccessibleControl {
                id: "run",
                label: "Run turn",
                shortcut: "⌘↩",
                enabled: self.readiness.is_ready() && self.composer == ComposerState::Idle,
            },
            AccessibleControl {
                id: "interrupt",
                label: "Interrupt turn",
                shortcut: "Esc",
                enabled: self.composer == ComposerState::Running,
            },
            AccessibleControl {
                id: "approval",
                label: "Review pending approval",
                shortcut: "⌘↩",
                enabled: self.approval.is_some(),
            },
        ]
    }

    pub fn snapshot(&self) -> String {
        let blocks = self
            .blocks
            .iter()
            .map(|block| {
                format!(
                    "{}:{:?}:{}:{:?}",
                    block.block_id,
                    block.kind,
                    if block.streaming {
                        "streaming"
                    } else {
                        "final"
                    },
                    block.content,
                )
            })
            .collect::<Vec<_>>()
            .join("|");
        let pending = self
            .pending_stream
            .iter()
            .map(|(block_id, (kind, content))| format!("{block_id}:{kind:?}:{content:?}"))
            .collect::<Vec<_>>()
            .join("|");
        format!(
            "appearance={:?};reduced_motion={};composer={:?};ready={};approval={};follow_bottom={};blocks={blocks};pending={pending}",
            self.appearance,
            self.reduced_motion,
            self.composer,
            self.readiness.is_ready(),
            self.approval
                .as_ref()
                .map(|approval| approval.approval_id.as_str())
                .unwrap_or("none"),
            self.follow_bottom
        )
    }

    fn trim_transcript(&mut self) {
        while self.blocks.len() > MAX_TRANSCRIPT_BLOCKS
            || self
                .blocks
                .iter()
                .map(|block| block.content.len())
                .sum::<usize>()
                > MAX_TRANSCRIPT_BYTES
        {
            if self.blocks.is_empty() {
                break;
            }
            self.blocks.remove(0);
        }
    }
}

fn upsert_block(blocks: &mut Vec<TimelineBlock>, block: TimelineBlock) {
    if let Some(existing) = blocks
        .iter_mut()
        .find(|existing| existing.block_id == block.block_id)
    {
        existing.kind = block.kind;
        existing.content.push_str(&block.content);
        existing.streaming = block.streaming;
        return;
    }
    blocks.push(block);
}

fn replace_block(blocks: &mut Vec<TimelineBlock>, block: TimelineBlock) {
    if let Some(existing) = blocks
        .iter_mut()
        .find(|existing| existing.block_id == block.block_id)
    {
        *existing = block;
        return;
    }
    blocks.push(block);
}

fn validate_block_id(block_id: &str) -> Result<(), WorkbenchError> {
    if block_id.is_empty()
        || block_id.len() > 128
        || !block_id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
    {
        return Err(WorkbenchError::InvalidBlockId);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready() -> WorkbenchState {
        let mut state = WorkbenchState::default();
        state
            .dispatch(WorkbenchAction::SetReadiness(Readiness::Ready))
            .expect("ready");
        state
    }

    #[test]
    fn native_layout_keeps_conversation_primary_and_approval_contextual() {
        let mut state = ready();
        let layout = state.layout_anatomy();
        assert_eq!(layout.top_bar_height, 52);
        assert_eq!(layout.sidebar_width, 280);
        assert!(layout.center_is_primary);
        assert!(!layout.context_panel_visible);
        state
            .dispatch(WorkbenchAction::BeginApproval(ApprovalProjection {
                approval_id: "approval-1".to_owned(),
                tool_name: "apply_patch".to_owned(),
                reason: "write one file".to_owned(),
                full_diff: "-old\n+new".to_owned(),
            }))
            .expect("approval");
        assert!(state.layout_anatomy().context_panel_visible);
    }

    #[test]
    fn readiness_and_approval_are_hard_run_boundaries() {
        let mut state = WorkbenchState::default();
        assert_eq!(
            state.dispatch(WorkbenchAction::SubmitRun),
            Err(WorkbenchError::ReadinessDisabled(
                "experimental_execution_disabled".to_owned()
            ))
        );
        state
            .dispatch(WorkbenchAction::SetReadiness(Readiness::Ready))
            .expect("ready");
        state
            .dispatch(WorkbenchAction::BeginApproval(ApprovalProjection {
                approval_id: "approval-1".to_owned(),
                tool_name: "apply_patch".to_owned(),
                reason: "write".to_owned(),
                full_diff: "-old\n+new".to_owned(),
            }))
            .expect("approval");
        assert!(state.dispatch(WorkbenchAction::SubmitRun).is_err());
        state
            .dispatch(WorkbenchAction::ResolveApproval {
                approval_id: "approval-1".to_owned(),
                outcome: ApprovalOutcome::Deny,
            })
            .expect("deny");
        state.dispatch(WorkbenchAction::SubmitRun).expect("run");
    }

    #[test]
    fn approval_resolution_cannot_apply_to_a_different_request() {
        let mut state = ready();
        state
            .dispatch(WorkbenchAction::BeginApproval(ApprovalProjection {
                approval_id: "approval-1".to_owned(),
                tool_name: "apply_patch".to_owned(),
                reason: "write".to_owned(),
                full_diff: "-old\n+new".to_owned(),
            }))
            .expect("approval");
        assert_eq!(
            state.dispatch(WorkbenchAction::ResolveApproval {
                approval_id: "approval-2".to_owned(),
                outcome: ApprovalOutcome::Approve,
            }),
            Err(WorkbenchError::InvalidTransition(
                "approval decision does not match the pending request"
            ))
        );
        assert!(state.approval.is_some());
    }

    #[test]
    fn readiness_loss_reconnects_and_cannot_be_restarted_locally() {
        let mut state = ready();
        state.dispatch(WorkbenchAction::SubmitRun).expect("run");
        state
            .dispatch(WorkbenchAction::SetReadiness(Readiness::Disabled {
                reason: "runtime_read_only".to_owned(),
            }))
            .expect("readiness update");
        assert_eq!(state.composer, ComposerState::Reconnecting);
        assert_eq!(
            state.dispatch(WorkbenchAction::SubmitRun),
            Err(WorkbenchError::ReadinessDisabled(
                "runtime_read_only".to_owned()
            ))
        );
    }

    #[test]
    fn run_interrupt_receipt_and_reconnect_transitions_are_explicit() {
        let mut state = ready();
        state.dispatch(WorkbenchAction::SubmitRun).expect("run");
        state
            .dispatch(WorkbenchAction::RequestInterrupt)
            .expect("interrupt");
        assert_eq!(state.composer, ComposerState::Interrupting);
        state
            .dispatch(WorkbenchAction::CompleteReceipt {
                block_id: "receipt-1".to_owned(),
                summary: "interrupted".to_owned(),
            })
            .expect("receipt");
        assert_eq!(state.composer, ComposerState::Idle);
        state
            .dispatch(WorkbenchAction::BeginReconnect)
            .expect("reconnect");
        assert_eq!(state.composer, ComposerState::Reconnecting);
        state
            .dispatch(WorkbenchAction::FinishReconnect)
            .expect("reconnected");
        assert_eq!(state.composer, ComposerState::Idle);
    }

    #[test]
    fn streaming_updates_coalesce_by_stable_block_id_and_flush_once() {
        let mut state = ready();
        state.dispatch(WorkbenchAction::SubmitRun).expect("run");
        state
            .dispatch(WorkbenchAction::StreamDelta {
                block_id: "assistant-1".to_owned(),
                kind: TimelineKind::Assistant,
                delta: "hello".to_owned(),
            })
            .expect("delta");
        state
            .dispatch(WorkbenchAction::StreamDelta {
                block_id: "assistant-1".to_owned(),
                kind: TimelineKind::Assistant,
                delta: " world".to_owned(),
            })
            .expect("delta");
        assert!(state.blocks.is_empty());
        state.dispatch(WorkbenchAction::FlushStream).expect("flush");
        assert_eq!(state.blocks.len(), 1);
        assert_eq!(state.blocks[0].block_id, "assistant-1");
        assert_eq!(state.blocks[0].content, "hello world");
    }

    #[test]
    fn scroll_anchor_and_reduced_motion_are_explicit_state() {
        let mut state = ready();
        state
            .dispatch(WorkbenchAction::SetReducedMotion(true))
            .expect("motion");
        state
            .dispatch(WorkbenchAction::UserScrolledAway)
            .expect("scroll");
        assert!(state.reduced_motion);
        assert_eq!(state.follow_behavior(), FollowBehavior::Instant);
        assert!(!state.follow_bottom);
        state
            .dispatch(WorkbenchAction::FollowBottom)
            .expect("follow");
        assert!(state.follow_bottom);
    }

    #[test]
    fn receipt_replay_is_idempotent_and_cannot_change_block_kind() {
        let mut state = ready();
        state
            .dispatch(WorkbenchAction::CompleteReceipt {
                block_id: "receipt-1".to_owned(),
                summary: "completed".to_owned(),
            })
            .expect("receipt");
        state
            .dispatch(WorkbenchAction::CompleteReceipt {
                block_id: "receipt-1".to_owned(),
                summary: "completed".to_owned(),
            })
            .expect("replayed receipt");
        assert_eq!(state.blocks[0].content, "completed");
        assert_eq!(
            state.dispatch(WorkbenchAction::StreamDelta {
                block_id: "receipt-1".to_owned(),
                kind: TimelineKind::Assistant,
                delta: "unsafe replacement".to_owned(),
            }),
            Err(WorkbenchError::InvalidTransition(
                "stream block kind changed"
            ))
        );
    }

    #[test]
    fn accessibility_projection_keeps_safety_actions_labeled() {
        let state = ready();
        let controls = state.accessibility_controls();
        assert_eq!(controls[0].label, "Run turn");
        assert_eq!(controls[0].shortcut, "⌘↩");
        assert_eq!(controls[1].label, "Interrupt turn");
        assert_eq!(controls[1].shortcut, "Esc");
        assert!(!controls[1].enabled);
    }

    #[test]
    fn snapshot_is_stable_for_replay_and_live_rendering() {
        let mut state = ready();
        state
            .dispatch(WorkbenchAction::StreamDelta {
                block_id: "assistant-1".to_owned(),
                kind: TimelineKind::Assistant,
                delta: "hello".to_owned(),
            })
            .expect("delta");
        state.dispatch(WorkbenchAction::FlushStream).expect("flush");
        assert_eq!(
            state.snapshot(),
            "appearance=Light;reduced_motion=false;composer=Idle;ready=true;approval=none;follow_bottom=true;blocks=assistant-1:Assistant:streaming:\"hello\";pending="
        );
    }
}
