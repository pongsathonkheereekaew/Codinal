//! Native-only authenticated contract shared by Codinal desktop shells.

use std::io::{self, Read, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpStream};
use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, Instant};
use zeroize::{Zeroize, Zeroizing};

pub use codinal_tools::{
    OperationAck, OperationEnvelope, OperationProgress, OperationReceipt, OperationResume,
    OperationState, OPERATION_SCHEMA,
};

const MIN_TOKEN_LENGTH: usize = 32;
const MAX_COMMAND_TOKEN_LENGTH: usize = 128;
static NEXT_COMMAND_ID: AtomicU64 = AtomicU64::new(1);

pub struct ControlPlaneClient {
    port: u16,
    token: Zeroizing<String>,
}

#[derive(Clone, Debug)]
pub struct ControlPlaneEventStream {
    url: String,
    subprotocols: Vec<String>,
}

impl Drop for ControlPlaneEventStream {
    fn drop(&mut self) {
        for protocol in &mut self.subprotocols {
            protocol.zeroize();
        }
    }
}

impl ControlPlaneEventStream {
    pub fn url(&self) -> &str {
        &self.url
    }

    pub fn subprotocols(&self) -> Vec<String> {
        self.subprotocols.clone()
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SessionSummary {
    pub session_id: String,
    pub title: String,
    pub workspace: String,
    pub messages: u64,
    pub updated_at: String,
    pub pinned: bool,
    pub archived: bool,
    pub origin: Option<String>,
    pub origin_label: Option<String>,
    pub origin_session_id: Option<String>,
    pub project_id: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProjectRootSummary {
    pub root_id: String,
    pub path: String,
    pub primary: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProjectSummary {
    pub project_id: String,
    pub name: String,
    pub roots: Vec<ProjectRootSummary>,
    pub pinned: bool,
    pub updated_at: String,
    pub task_count: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SourceAttachment {
    pub attachment_id: String,
    pub session_id: String,
    pub path: String,
    pub name: String,
    pub kind: String,
    pub status: String,
    pub error: Option<String>,
    pub attached_at: String,
    pub updated_at: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SourcePreview {
    pub attachment: SourceAttachment,
    pub content: String,
    pub binary: bool,
    pub truncated: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ActivityItem {
    pub activity_id: String,
    pub session_id: Option<String>,
    pub kind: String,
    pub title: String,
    pub detail: String,
    pub unread: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MessageSummary {
    pub role: String,
    pub text: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TurnReceipt {
    pub turn_id: String,
    pub session_id: String,
    pub outcome: serde_json::Value,
    pub message_count: i64,
    pub created_at: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RuntimeCapabilities {
    pub runtime_owner: String,
    pub turn_execution_owner: String,
    pub receipt_write_owner: String,
    pub provider: String,
    pub model: String,
    pub effort: String,
    pub model_profiles: Vec<ModelProfile>,
    pub experimental_execution: bool,
    pub provider_configured: bool,
    pub start_turn: bool,
    pub interrupt_turn: bool,
    pub mutations: bool,
    pub run_disabled_reason: Option<String>,
    pub mutation_disabled_reason: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModelProfile {
    pub provider: String,
    pub model: String,
    pub effort: String,
    pub configured: bool,
    pub probe_status: String,
    pub ready: bool,
}

impl RuntimeCapabilities {
    fn legacy_read_only() -> Self {
        Self {
            runtime_owner: "unknown".to_owned(),
            turn_execution_owner: "none".to_owned(),
            receipt_write_owner: "unknown".to_owned(),
            provider: "unknown".to_owned(),
            model: "unknown".to_owned(),
            effort: "unknown".to_owned(),
            model_profiles: Vec::new(),
            experimental_execution: false,
            provider_configured: false,
            start_turn: false,
            interrupt_turn: false,
            mutations: false,
            run_disabled_reason: Some("legacy_read_only".to_owned()),
            mutation_disabled_reason: Some("legacy_read_only".to_owned()),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RuntimeHealth {
    pub status: String,
    pub mode: String,
    pub reason_code: String,
    pub migration_state: String,
    pub writer_lock_state: String,
    pub writer_lock_owner: Option<RuntimeOwnerMetadata>,
    pub event_store_ready: bool,
    pub capabilities: RuntimeCapabilities,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RuntimeOwnerMetadata {
    pub pid: u32,
    pub process_start_time_unix_ms: u128,
    pub data_directory_identity: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TurnControlResult {
    pub ok: bool,
    pub session_id: String,
}

#[derive(Debug, PartialEq, Eq)]
pub struct PendingApproval {
    pub approval_id: String,
    pub tool_name: String,
    pub arguments: serde_json::Value,
    pub reason: String,
    pub risk: String,
    pub command: Option<String>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ApprovalOutcome {
    Once,
    AlwaysTool,
    AlwaysCommand,
    Deny,
}

impl ApprovalOutcome {
    fn as_str(self) -> &'static str {
        match self {
            Self::Once => "once",
            Self::AlwaysTool => "always_tool",
            Self::AlwaysCommand => "always_command",
            Self::Deny => "deny",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ControlPlaneCommand {
    CheckHealth,
    StartTurn {
        session_id: String,
        input: String,
        provider: String,
        model: String,
        effort: String,
    },
    InterruptTurn {
        session_id: String,
    },
    CreateSession {
        workspace: String,
        title: String,
        model: String,
        origin: Option<String>,
        origin_label: Option<String>,
        origin_session_id: Option<String>,
    },
    ListSessions,
    LoadSession {
        session_id: String,
    },
    GetSessionMessages {
        session_id: String,
    },
    ListPendingApprovals {
        session_id: String,
    },
    ListTurnReceipts {
        session_id: String,
    },
    ResolveApproval {
        session_id: String,
        approval_id: String,
        outcome: ApprovalOutcome,
    },
}

#[derive(Debug)]
#[allow(clippy::large_enum_variant)]
pub enum CommandPayload {
    Health(RuntimeHealth),
    TurnStarted(TurnControlResult),
    TurnInterrupted(TurnControlResult),
    SessionCreated(SessionSummary),
    Sessions(Vec<SessionSummary>),
    SessionLoaded {
        messages: Vec<MessageSummary>,
        approvals: Vec<PendingApproval>,
        receipts: Vec<TurnReceipt>,
    },
    Messages(Vec<MessageSummary>),
    Approvals(Vec<PendingApproval>),
    TurnReceipts(Vec<TurnReceipt>),
    ApprovalResolved,
}

pub struct CommandEnvelope {
    request_id: String,
    idempotency_key: Option<String>,
    command: ControlPlaneCommand,
}

impl CommandEnvelope {
    pub fn new(command: ControlPlaneCommand) -> Self {
        let request_id = format!(
            "desktop-command-{}",
            NEXT_COMMAND_ID.fetch_add(1, Ordering::Relaxed)
        );
        Self {
            request_id,
            idempotency_key: None,
            command,
        }
    }

    pub fn with_request_id(
        request_id: impl Into<String>,
        command: ControlPlaneCommand,
    ) -> io::Result<Self> {
        let request_id = request_id.into();
        validate_command_token(&request_id, "request id")?;
        Ok(Self {
            request_id,
            idempotency_key: None,
            command,
        })
    }

    pub fn with_idempotency_key(mut self, idempotency_key: impl Into<String>) -> io::Result<Self> {
        let idempotency_key = idempotency_key.into();
        validate_command_token(&idempotency_key, "idempotency key")?;
        self.idempotency_key = Some(idempotency_key);
        Ok(self)
    }
}

#[derive(Debug)]
pub struct CommandResponse {
    request_id: String,
    payload: CommandPayload,
}

impl CommandResponse {
    pub fn request_id(&self) -> &str {
        &self.request_id
    }

    pub fn into_payload(self) -> CommandPayload {
        self.payload
    }
}

pub trait CommandTransport {
    fn dispatch(&self, envelope: CommandEnvelope) -> io::Result<CommandResponse>;
}

/// Native confirmation reducer. A transport request cannot be obtained until
/// the UI has explicitly moved this exact pending approval to `Confirmed`.
pub struct ApprovalConfirmation {
    session_id: String,
    approval_id: String,
    outcome: ApprovalOutcome,
    confirmed: bool,
    cancelled: bool,
}

impl ApprovalConfirmation {
    pub fn new(session_id: &str, approval_id: &str, outcome: ApprovalOutcome) -> io::Result<Self> {
        validate_session_id(session_id)?;
        validate_approval_id(approval_id)?;
        Ok(Self {
            session_id: session_id.to_owned(),
            approval_id: approval_id.to_owned(),
            outcome,
            confirmed: false,
            cancelled: false,
        })
    }

    pub fn confirm(&mut self) -> bool {
        if self.cancelled {
            false
        } else {
            self.confirmed = true;
            true
        }
    }

    pub fn cancel(&mut self) {
        self.cancelled = true;
        self.confirmed = false;
    }

    pub fn submission(&self) -> Option<(&str, &str, ApprovalOutcome)> {
        self.confirmed.then_some((
            self.session_id.as_str(),
            self.approval_id.as_str(),
            self.outcome,
        ))
    }
}

impl ControlPlaneClient {
    pub fn new(port: u16, token: &str) -> io::Result<Self> {
        if port == 0
            || token.len() < MIN_TOKEN_LENGTH
            || !token
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid control-plane credentials",
            ));
        }
        Ok(Self {
            port,
            token: Zeroizing::new(token.to_owned()),
        })
    }

    pub fn get(&self, path: &str) -> io::Result<Request> {
        validate_route(path)?;
        Ok(Request {
            url: format!("http://127.0.0.1:{}/v1/{path}", self.port),
            authorization: Zeroizing::new(format!("Bearer {}", self.token.as_str())),
        })
    }

    /// Issue an authenticated JSON GET only to the local control plane.
    pub fn get_json(&self, path: &str) -> io::Result<serde_json::Value> {
        self.get_json_with_metadata(path, None)
    }

    pub fn submit_operation(&self, envelope: &OperationEnvelope) -> io::Result<OperationAck> {
        envelope.validate_identity()?;
        let request = self.get("operations")?;
        let body = serde_json::to_vec(envelope)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        let response =
            self.send_serialized_with_metadata("POST", "operations", &body, &request, None)?;
        parse_operation_response(response)
    }

    pub fn resume_operation(
        &self,
        operation_id: &str,
        after_sequence: u64,
    ) -> io::Result<OperationResume> {
        codinal_tools::operation::validate_operation_id(operation_id)?;
        let base_path = format!("operations/{operation_id}");
        let path = format!("{base_path}?after={after_sequence}");
        let request = self.get(&base_path)?;
        let response = self.send_json_with_metadata("GET", &path, None, &request, None)?;
        parse_operation_response(response)
    }

    pub fn cancel_operation(&self, operation_id: &str) -> io::Result<OperationAck> {
        codinal_tools::operation::validate_operation_id(operation_id)?;
        let path = format!("operations/{operation_id}/cancel");
        let request = self.get(&path)?;
        let response = self.send_json_with_metadata("POST", &path, None, &request, None)?;
        parse_operation_response(response)
    }

    pub fn health(&self) -> io::Result<RuntimeHealth> {
        match CommandTransport::dispatch(
            self,
            CommandEnvelope::new(ControlPlaneCommand::CheckHealth),
        )?
        .into_payload()
        {
            CommandPayload::Health(health) => Ok(health),
            _ => Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "unexpected health command response",
            )),
        }
    }

    pub fn wait_until_ready(&self, timeout: Duration) -> io::Result<RuntimeHealth> {
        let deadline = Instant::now() + timeout;
        let mut delay = Duration::from_millis(25);

        loop {
            let error = match self.health() {
                Ok(health) => return Ok(health),
                Err(error) => error,
            };

            if Instant::now() >= deadline {
                return Err(error);
            }

            std::thread::sleep(delay);
            delay = (delay * 2).min(Duration::from_millis(250));
        }
    }

    pub fn start_turn(&self, session_id: &str, input: &str) -> io::Result<TurnControlResult> {
        let capabilities = self.capabilities()?;
        let profile = capabilities
            .model_profiles
            .iter()
            .find(|profile| {
                profile.provider == capabilities.provider
                    && profile.model == capabilities.model
                    && profile.effort == capabilities.effort
            })
            .cloned()
            .filter(|profile| profile.model != "unknown")
            .unwrap_or_else(|| ModelProfile {
                provider: if capabilities.provider == "unknown" {
                    "opencode-go".to_owned()
                } else {
                    capabilities.provider.clone()
                },
                model: if capabilities.model == "unknown" {
                    "kimi-k2.7-code".to_owned()
                } else {
                    capabilities.model.clone()
                },
                effort: if capabilities.effort == "unknown" {
                    "medium".to_owned()
                } else {
                    capabilities.effort.clone()
                },
                configured: capabilities.provider_configured,
                probe_status: if capabilities.start_turn {
                    "passed".to_owned()
                } else {
                    "unknown".to_owned()
                },
                ready: capabilities.start_turn,
            });
        self.start_turn_for_profile(session_id, input, &profile)
    }

    pub fn start_turn_with_profile(
        &self,
        session_id: &str,
        input: &str,
        profile: &ModelProfile,
    ) -> io::Result<TurnControlResult> {
        let capabilities = self.capabilities()?;
        let profile = capabilities
            .model_profiles
            .iter()
            .find(|candidate| {
                candidate.provider == profile.provider
                    && candidate.model == profile.model
                    && candidate.effort == profile.effort
            })
            .cloned()
            .unwrap_or_else(|| profile.clone());
        self.start_turn_for_profile(session_id, input, &profile)
    }

    fn start_turn_for_profile(
        &self,
        session_id: &str,
        input: &str,
        profile: &ModelProfile,
    ) -> io::Result<TurnControlResult> {
        if !profile.ready {
            return Err(io::Error::new(
                io::ErrorKind::Unsupported,
                format!(
                    "{} is not ready (configured={}, probe={})",
                    profile.model, profile.configured, profile.probe_status
                ),
            ));
        }
        match CommandTransport::dispatch(
            self,
            CommandEnvelope::new(ControlPlaneCommand::StartTurn {
                session_id: session_id.to_owned(),
                input: input.to_owned(),
                provider: profile.provider.clone(),
                model: profile.model.clone(),
                effort: profile.effort.clone(),
            }),
        )?
        .into_payload()
        {
            CommandPayload::TurnStarted(result) => Ok(result),
            _ => Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "unexpected start turn command response",
            )),
        }
    }

    pub fn interrupt_turn(&self, session_id: &str) -> io::Result<TurnControlResult> {
        let capabilities = self.capabilities()?;
        if !capabilities.interrupt_turn {
            return Err(io::Error::new(
                io::ErrorKind::Unsupported,
                format!(
                    "turn interrupt is unavailable on {} runtime",
                    capabilities.runtime_owner
                ),
            ));
        }
        match CommandTransport::dispatch(
            self,
            CommandEnvelope::new(ControlPlaneCommand::InterruptTurn {
                session_id: session_id.to_owned(),
            }),
        )?
        .into_payload()
        {
            CommandPayload::TurnInterrupted(result) => Ok(result),
            _ => Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "unexpected interrupt turn command response",
            )),
        }
    }

    pub fn create_session(&self, workspace: &str, title: &str) -> io::Result<SessionSummary> {
        self.create_session_with_profile(workspace, title, "kimi-k2.7-code", None, None, None)
    }

    pub fn create_session_with_model(
        &self,
        workspace: &str,
        title: &str,
        model: &str,
    ) -> io::Result<SessionSummary> {
        self.create_session_with_profile(workspace, title, model, None, None, None)
    }

    pub fn create_side_chat(
        &self,
        workspace: &str,
        title: &str,
        parent_session_id: &str,
    ) -> io::Result<SessionSummary> {
        self.create_side_chat_with_model(workspace, title, parent_session_id, "kimi-k2.7-code")
    }

    pub fn create_side_chat_with_model(
        &self,
        workspace: &str,
        title: &str,
        parent_session_id: &str,
        model: &str,
    ) -> io::Result<SessionSummary> {
        self.create_session_with_profile(
            workspace,
            title,
            model,
            Some("side_chat"),
            Some("Side chat"),
            Some(parent_session_id),
        )
    }

    fn create_session_with_profile(
        &self,
        workspace: &str,
        title: &str,
        model: &str,
        origin: Option<&str>,
        origin_label: Option<&str>,
        origin_session_id: Option<&str>,
    ) -> io::Result<SessionSummary> {
        if workspace.is_empty()
            || workspace.len() > 4096
            || !workspace.starts_with('/')
            || workspace
                .bytes()
                .any(|byte| byte == 0 || byte == b'\r' || byte == b'\n')
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid workspace path",
            ));
        }
        if title.trim().is_empty() || title.len() > 160 || title.contains(['\r', '\n']) {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid session title",
            ));
        }
        if !matches!(model, "kimi-k2.7-code" | "deepseek-v4-pro") {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "unsupported session model",
            ));
        }
        if origin.is_some_and(|value| value != "side_chat") {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "unsupported session origin",
            ));
        }
        if let Some(label) = origin_label {
            if label.trim().is_empty() || label.len() > 160 || label.contains(['\r', '\n']) {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidInput,
                    "invalid session origin label",
                ));
            }
        }
        if let Some(session_id) = origin_session_id {
            validate_session_id(session_id)?;
        }
        if origin.is_none() && (origin_label.is_some() || origin_session_id.is_some()) {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "origin metadata requires a session origin",
            ));
        }
        match CommandTransport::dispatch(
            self,
            CommandEnvelope::new(ControlPlaneCommand::CreateSession {
                workspace: workspace.to_owned(),
                title: title.trim().to_owned(),
                model: model.to_owned(),
                origin: origin.map(str::to_owned),
                origin_label: origin_label.map(str::to_owned),
                origin_session_id: origin_session_id.map(str::to_owned),
            }),
        )?
        .into_payload()
        {
            CommandPayload::SessionCreated(session) => Ok(session),
            _ => Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "unexpected create session command response",
            )),
        }
    }

    pub fn update_session(
        &self,
        session_id: &str,
        title: Option<&str>,
        pinned: Option<bool>,
        archived: Option<bool>,
    ) -> io::Result<SessionSummary> {
        validate_session_id(session_id)?;
        if title.is_none() && pinned.is_none() && archived.is_none() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "session update is empty",
            ));
        }
        if let Some(title) = title {
            if title.trim().is_empty() || title.len() > 160 || title.contains(['\r', '\n']) {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidInput,
                    "invalid session title",
                ));
            }
        }
        let session_id = escape_path_segment(session_id)?;
        let path = format!("sessions/{session_id}");
        let request = self.get(&path)?;
        let response = self.send_json_with_metadata(
            "PATCH",
            &path,
            Some(&serde_json::json!({
                "title": title,
                "pinned": pinned,
                "archived": archived,
            })),
            &request,
            None,
        )?;
        parse_session_summary(&response)
    }

    pub fn delete_session(&self, session_id: &str) -> io::Result<()> {
        validate_session_id(session_id)?;
        let session_id = escape_path_segment(session_id)?;
        let path = format!("sessions/{session_id}");
        let request = self.get(&path)?;
        self.send_json_with_metadata("DELETE", &path, None, &request, None)?;
        Ok(())
    }

    fn get_json_with_metadata(
        &self,
        path: &str,
        envelope: Option<&CommandEnvelope>,
    ) -> io::Result<serde_json::Value> {
        let request = self.get(path)?;
        self.send_json_with_metadata("GET", path, None, &request, envelope)
    }

    fn health_with_metadata(
        &self,
        envelope: Option<&CommandEnvelope>,
    ) -> io::Result<RuntimeHealth> {
        let response = self.get_json_with_metadata("health", envelope)?;
        let status = response
            .get("status")
            .and_then(serde_json::Value::as_str)
            .filter(|status| !status.is_empty())
            .ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidData, "health response missing status")
            })?;
        let capabilities = response
            .get("capabilities")
            .map(parse_runtime_capabilities)
            .transpose()?
            .unwrap_or_else(RuntimeCapabilities::legacy_read_only);
        let mode = response
            .get("mode")
            .and_then(serde_json::Value::as_str)
            .filter(|value| !value.is_empty())
            .unwrap_or("read_only")
            .to_owned();
        let reason_code = response
            .get("reason_code")
            .and_then(serde_json::Value::as_str)
            .filter(|value| !value.is_empty())
            .unwrap_or("legacy_read_only")
            .to_owned();
        let migration_state = response
            .get("migration")
            .and_then(|value| value.get("state"))
            .and_then(serde_json::Value::as_str)
            .unwrap_or("unknown")
            .to_owned();
        let writer_lock_state = response
            .get("writer_lock")
            .and_then(|value| value.get("state"))
            .and_then(serde_json::Value::as_str)
            .unwrap_or("unknown")
            .to_owned();
        let writer_lock_owner = response
            .get("writer_lock")
            .and_then(|value| value.get("owner_metadata"))
            .and_then(|value| {
                Some(RuntimeOwnerMetadata {
                    pid: value.get("pid")?.as_u64()?.try_into().ok()?,
                    process_start_time_unix_ms: value.get("process_start_time_unix_ms")?.as_u64()?
                        as u128,
                    data_directory_identity: value
                        .get("data_directory_identity")?
                        .as_str()?
                        .to_owned(),
                })
            });
        let event_store_ready = response
            .get("event_store")
            .and_then(|value| value.get("ready"))
            .and_then(serde_json::Value::as_bool)
            .unwrap_or(false);
        Ok(RuntimeHealth {
            status: status.to_owned(),
            mode,
            reason_code,
            migration_state,
            writer_lock_state,
            writer_lock_owner,
            event_store_ready,
            capabilities,
        })
    }

    pub fn capabilities(&self) -> io::Result<RuntimeCapabilities> {
        Ok(self.health()?.capabilities)
    }

    /// Explicitly approve and run the bounded provider capability probe.
    ///
    /// The runtime keeps the probe lease in memory; callers must refresh
    /// `capabilities()` after this returns before enabling turn controls.
    pub fn probe_capability(&self, provider: &str, model: &str, effort: &str) -> io::Result<()> {
        let supported = matches!(
            (provider, model, effort),
            ("opencode-go", "kimi-k2.7-code", "medium") | ("deepseek", "deepseek-v4-pro", "high")
        );
        if !supported {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "unsupported capability probe profile",
            ));
        }
        let path = "capabilities/probe";
        let request = self.get(path)?;
        let response = self.send_json_with_metadata(
            "POST",
            path,
            Some(&serde_json::json!({
                "approved": true,
                "provider": provider,
                "model": model,
                "effort": effort,
            })),
            &request,
            None,
        )?;
        if response.get("status").and_then(serde_json::Value::as_str) != Some("passed") {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "capability probe did not pass",
            ));
        }
        Ok(())
    }

    fn start_turn_with_metadata(
        &self,
        session_id: &str,
        input: &str,
        provider: &str,
        model: &str,
        effort: &str,
        envelope: Option<&CommandEnvelope>,
    ) -> io::Result<TurnControlResult> {
        validate_session_id(session_id)?;
        let path = format!("sessions/{session_id}/turns");
        let request = self.get(&path)?;
        let response = self.send_json_with_metadata(
            "POST",
            &path,
            Some(&serde_json::json!({
                "input": input,
                "provider": provider,
                "model": model,
                "effort": effort,
            })),
            &request,
            envelope,
        )?;
        parse_turn_control_result(&response)
    }

    fn create_session_with_metadata(
        &self,
        workspace: &str,
        title: &str,
        model: &str,
        origin: Option<&str>,
        origin_label: Option<&str>,
        origin_session_id: Option<&str>,
        envelope: Option<&CommandEnvelope>,
    ) -> io::Result<SessionSummary> {
        let path = "sessions";
        let request = self.get(path)?;
        let mut payload = serde_json::json!({
            "workspace": workspace,
            "title": title,
            "model": model,
            "mode": "code",
        });
        if let Some(object) = payload.as_object_mut() {
            if let Some(origin) = origin {
                object.insert("origin".to_owned(), serde_json::json!(origin));
            }
            if let Some(origin_label) = origin_label {
                object.insert("origin_label".to_owned(), serde_json::json!(origin_label));
            }
            if let Some(origin_session_id) = origin_session_id {
                object.insert(
                    "origin_session_id".to_owned(),
                    serde_json::json!(origin_session_id),
                );
            }
        }
        let response =
            self.send_json_with_metadata("POST", path, Some(&payload), &request, envelope)?;
        parse_session_summary(&response)
    }

    fn interrupt_turn_with_metadata(
        &self,
        session_id: &str,
        envelope: Option<&CommandEnvelope>,
    ) -> io::Result<TurnControlResult> {
        validate_session_id(session_id)?;
        let path = format!("sessions/{session_id}/interrupt");
        let request = self.get(&path)?;
        let response = self.send_json_with_metadata("POST", &path, None, &request, envelope)?;
        parse_turn_control_result(&response)
    }

    pub fn resolve_approval(
        &self,
        session_id: &str,
        approval_id: &str,
        outcome: ApprovalOutcome,
    ) -> io::Result<()> {
        let envelope = CommandEnvelope::new(ControlPlaneCommand::ResolveApproval {
            session_id: session_id.to_owned(),
            approval_id: approval_id.to_owned(),
            outcome,
        })
        .with_idempotency_key(format!(
            "approval:{session_id}:{approval_id}:{}",
            outcome.as_str()
        ))?;
        match CommandTransport::dispatch(self, envelope)?.into_payload() {
            CommandPayload::ApprovalResolved => Ok(()),
            _ => Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "unexpected approval command response",
            )),
        }
    }

    fn resolve_approval_with_metadata(
        &self,
        session_id: &str,
        approval_id: &str,
        outcome: ApprovalOutcome,
        envelope: Option<&CommandEnvelope>,
    ) -> io::Result<()> {
        validate_session_id(session_id)?;
        validate_approval_id(approval_id)?;
        let path = format!("sessions/{session_id}/approvals/{approval_id}");
        let request = self.get(&path)?;
        self.send_json_with_metadata(
            "POST",
            &path,
            Some(&serde_json::json!({ "outcome": outcome.as_str() })),
            &request,
            envelope,
        )?;
        Ok(())
    }

    /// Resolve only after the native confirmation reducer has been explicitly
    /// confirmed. Pending or cancelled reducers make no network request.
    pub fn resolve_confirmation(&self, confirmation: &ApprovalConfirmation) -> io::Result<bool> {
        let Some((session_id, approval_id, outcome)) = confirmation.submission() else {
            return Ok(false);
        };
        self.resolve_approval(session_id, approval_id, outcome)?;
        Ok(true)
    }

    fn send_json_with_metadata(
        &self,
        method: &str,
        path: &str,
        payload: Option<&serde_json::Value>,
        request: &Request,
        envelope: Option<&CommandEnvelope>,
    ) -> io::Result<serde_json::Value> {
        let body = payload
            .map(serde_json::to_vec)
            .transpose()
            .map_err(|error| io::Error::other(error.to_string()))?;
        self.send_serialized_with_metadata(
            method,
            path,
            body.as_deref().unwrap_or_default(),
            request,
            envelope,
        )
    }

    fn send_serialized_with_metadata(
        &self,
        method: &str,
        path: &str,
        body: &[u8],
        request: &Request,
        envelope: Option<&CommandEnvelope>,
    ) -> io::Result<serde_json::Value> {
        let address = SocketAddrV4::new(Ipv4Addr::LOCALHOST, self.port);
        let mut stream = TcpStream::connect_timeout(&address.into(), Duration::from_secs(2))?;
        stream.set_read_timeout(Some(Duration::from_secs(2)))?;
        stream.set_write_timeout(Some(Duration::from_secs(2)))?;
        let body = Zeroizing::new(body.to_vec());
        let command_headers = envelope
            .map(|envelope| {
                let idempotency_header = envelope
                    .idempotency_key
                    .as_deref()
                    .map(|key| format!("X-Codinal-Idempotency-Key: {key}\r\n"))
                    .unwrap_or_default();
                format!(
                    "X-Codinal-Request-Id: {}\r\n{idempotency_header}",
                    envelope.request_id
                )
            })
            .unwrap_or_default();
        let headers = Zeroizing::new(format!(
            "{method} /v1/{path} HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nAuthorization: {}\r\n{command_headers}Accept: application/json\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
            self.port,
            request.authorization(),
            body.len(),
        ));
        stream.write_all(headers.as_bytes())?;
        stream.write_all(&body)?;
        stream.flush()?;

        let mut response = Vec::new();
        stream.read_to_end(&mut response)?;
        parse_json_response(&response)
    }

    pub fn list_sessions(&self) -> io::Result<Vec<SessionSummary>> {
        match CommandTransport::dispatch(
            self,
            CommandEnvelope::new(ControlPlaneCommand::ListSessions),
        )?
        .into_payload()
        {
            CommandPayload::Sessions(sessions) => Ok(sessions),
            _ => Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "unexpected list sessions command response",
            )),
        }
    }

    pub fn search_sessions(&self, query: &str, limit: usize) -> io::Result<Vec<SessionSummary>> {
        let path = session_search_path(query, limit)?;
        let request = self.get("sessions/search")?;
        let response = self.send_json_with_metadata("GET", &path, None, &request, None)?;
        let sessions = response.as_array().ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "session search response must be an array",
            )
        })?;
        sessions.iter().map(parse_session_summary).collect()
    }

    pub fn list_source_attachments(&self, session_id: &str) -> io::Result<Vec<SourceAttachment>> {
        validate_session_id(session_id)?;
        let session_id = escape_path_segment(session_id)?;
        let path = format!("sessions/{session_id}/sources");
        let response = self.get_json(&path)?;
        let sources = response.as_array().ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "source attachments response must be an array",
            )
        })?;
        sources.iter().map(parse_source_attachment).collect()
    }

    pub fn attach_source(&self, session_id: &str, path: &str) -> io::Result<SourceAttachment> {
        validate_session_id(session_id)?;
        validate_source_path(path)?;
        let session_id = escape_path_segment(session_id)?;
        let route = format!("sessions/{session_id}/sources");
        let request = self.get(&route)?;
        let response = self.send_json_with_metadata(
            "POST",
            &route,
            Some(&serde_json::json!({"path": path})),
            &request,
            None,
        )?;
        parse_source_attachment(&response)
    }

    pub fn remove_source_attachment(
        &self,
        session_id: &str,
        attachment_id: &str,
    ) -> io::Result<()> {
        validate_session_id(session_id)?;
        validate_source_attachment_id(attachment_id)?;
        let session_id = escape_path_segment(session_id)?;
        let attachment_id = escape_path_segment(attachment_id)?;
        let route = format!("sessions/{session_id}/sources/{attachment_id}");
        let request = self.get(&route)?;
        self.send_json_with_metadata("DELETE", &route, None, &request, None)?;
        Ok(())
    }

    pub fn retry_source_attachment(
        &self,
        session_id: &str,
        attachment_id: &str,
    ) -> io::Result<SourceAttachment> {
        validate_session_id(session_id)?;
        validate_source_attachment_id(attachment_id)?;
        let session_id = escape_path_segment(session_id)?;
        let attachment_id = escape_path_segment(attachment_id)?;
        let route = format!("sessions/{session_id}/sources/{attachment_id}/retry");
        let request = self.get(&route)?;
        let response = self.send_json_with_metadata("POST", &route, None, &request, None)?;
        parse_source_attachment(&response)
    }

    pub fn preview_source(
        &self,
        session_id: &str,
        attachment_id: &str,
    ) -> io::Result<SourcePreview> {
        validate_session_id(session_id)?;
        validate_source_attachment_id(attachment_id)?;
        let session_id = escape_path_segment(session_id)?;
        let attachment_id = escape_path_segment(attachment_id)?;
        let path = format!("sessions/{session_id}/sources/{attachment_id}/preview");
        let response = self.get_json(&path)?;
        parse_source_preview(&response)
    }

    pub fn list_activity(&self) -> io::Result<Vec<ActivityItem>> {
        let response = self.get_json("activity")?;
        let items = response.as_array().ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "activity response must be an array",
            )
        })?;
        items.iter().map(parse_activity_item).collect()
    }

    pub fn mark_activity_read(&self) -> io::Result<()> {
        let path = "activity/read";
        let request = self.get(path)?;
        self.send_json_with_metadata("POST", path, None, &request, None)?;
        Ok(())
    }

    pub fn list_projects(&self) -> io::Result<Vec<ProjectSummary>> {
        let response = self.get_json("projects")?;
        let projects = response.as_array().ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "projects response must be an array",
            )
        })?;
        projects.iter().map(parse_project_summary).collect()
    }

    pub fn create_project(&self, name: &str, roots: &[String]) -> io::Result<ProjectSummary> {
        validate_project_name(name)?;
        validate_project_roots(roots)?;
        let path = "projects";
        let request = self.get(path)?;
        let response = self.send_json_with_metadata(
            "POST",
            path,
            Some(&serde_json::json!({"name": name.trim(), "roots": roots})),
            &request,
            None,
        )?;
        parse_project_summary(&response)
    }

    pub fn update_project(
        &self,
        project_id: &str,
        name: &str,
        roots: &[String],
    ) -> io::Result<ProjectSummary> {
        validate_project_id(project_id)?;
        validate_project_name(name)?;
        validate_project_roots(roots)?;
        let project_id = escape_path_segment(project_id)?;
        let path = format!("projects/{project_id}");
        let request = self.get(&path)?;
        let response = self.send_json_with_metadata(
            "PATCH",
            &path,
            Some(&serde_json::json!({"name": name.trim(), "roots": roots})),
            &request,
            None,
        )?;
        parse_project_summary(&response)
    }

    pub fn remove_project(&self, project_id: &str) -> io::Result<()> {
        validate_project_id(project_id)?;
        let project_id = escape_path_segment(project_id)?;
        let path = format!("projects/{project_id}");
        let request = self.get(&path)?;
        self.send_json_with_metadata("DELETE", &path, None, &request, None)?;
        Ok(())
    }

    pub fn set_project_pinned(&self, project_id: &str, pinned: bool) -> io::Result<()> {
        validate_project_id(project_id)?;
        let project_id = escape_path_segment(project_id)?;
        let path = format!("projects/{project_id}/pin");
        let request = self.get(&path)?;
        self.send_json_with_metadata(
            "POST",
            &path,
            Some(&serde_json::json!({"pinned": pinned})),
            &request,
            None,
        )?;
        Ok(())
    }

    pub fn assign_session_to_project(&self, project_id: &str, session_id: &str) -> io::Result<()> {
        validate_project_id(project_id)?;
        validate_session_id(session_id)?;
        let project_id = escape_path_segment(project_id)?;
        let session_id = escape_path_segment(session_id)?;
        let path = format!("projects/{project_id}/sessions/{session_id}");
        let request = self.get(&path)?;
        self.send_json_with_metadata("POST", &path, None, &request, None)?;
        Ok(())
    }

    pub fn remove_session_from_project(
        &self,
        project_id: &str,
        session_id: &str,
    ) -> io::Result<()> {
        validate_project_id(project_id)?;
        validate_session_id(session_id)?;
        let project_id = escape_path_segment(project_id)?;
        let session_id = escape_path_segment(session_id)?;
        let path = format!("projects/{project_id}/sessions/{session_id}");
        let request = self.get(&path)?;
        self.send_json_with_metadata("DELETE", &path, None, &request, None)?;
        Ok(())
    }

    fn list_sessions_with_metadata(
        &self,
        envelope: Option<&CommandEnvelope>,
    ) -> io::Result<Vec<SessionSummary>> {
        let response = self.get_json_with_metadata("sessions", envelope)?;
        let sessions = response.as_array().ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "sessions response must be an array",
            )
        })?;
        sessions.iter().map(parse_session_summary).collect()
    }

    pub fn session_messages(&self, session_id: &str) -> io::Result<Vec<MessageSummary>> {
        match CommandTransport::dispatch(
            self,
            CommandEnvelope::new(ControlPlaneCommand::GetSessionMessages {
                session_id: session_id.to_owned(),
            }),
        )?
        .into_payload()
        {
            CommandPayload::Messages(messages) => Ok(messages),
            _ => Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "unexpected session messages command response",
            )),
        }
    }

    pub fn load_session(
        &self,
        session_id: &str,
    ) -> io::Result<(Vec<MessageSummary>, Vec<PendingApproval>, Vec<TurnReceipt>)> {
        validate_session_id(session_id)?;
        match CommandTransport::dispatch(
            self,
            CommandEnvelope::new(ControlPlaneCommand::LoadSession {
                session_id: session_id.to_owned(),
            }),
        )?
        .into_payload()
        {
            CommandPayload::SessionLoaded {
                messages,
                approvals,
                receipts,
            } => Ok((messages, approvals, receipts)),
            _ => Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "unexpected load session command response",
            )),
        }
    }

    fn session_messages_with_metadata(
        &self,
        session_id: &str,
        envelope: Option<&CommandEnvelope>,
    ) -> io::Result<Vec<MessageSummary>> {
        validate_session_id(session_id)?;
        let response =
            self.get_json_with_metadata(&format!("sessions/{session_id}/messages"), envelope)?;
        let messages = response.as_array().ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "messages response must be an array",
            )
        })?;
        messages.iter().map(parse_message_summary).collect()
    }

    pub fn pending_approvals(&self, session_id: &str) -> io::Result<Vec<PendingApproval>> {
        match CommandTransport::dispatch(
            self,
            CommandEnvelope::new(ControlPlaneCommand::ListPendingApprovals {
                session_id: session_id.to_owned(),
            }),
        )?
        .into_payload()
        {
            CommandPayload::Approvals(approvals) => Ok(approvals),
            _ => Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "unexpected pending approvals command response",
            )),
        }
    }

    pub fn turn_receipts(&self, session_id: &str) -> io::Result<Vec<TurnReceipt>> {
        match CommandTransport::dispatch(
            self,
            CommandEnvelope::new(ControlPlaneCommand::ListTurnReceipts {
                session_id: session_id.to_owned(),
            }),
        )?
        .into_payload()
        {
            CommandPayload::TurnReceipts(receipts) => Ok(receipts),
            _ => Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "unexpected turn receipts command response",
            )),
        }
    }

    fn turn_receipts_with_metadata(
        &self,
        session_id: &str,
        envelope: Option<&CommandEnvelope>,
    ) -> io::Result<Vec<TurnReceipt>> {
        validate_session_id(session_id)?;
        let response =
            self.get_json_with_metadata(&format!("sessions/{session_id}/turns"), envelope)?;
        let receipts = response.as_array().ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "turn receipts response must be an array",
            )
        })?;
        receipts.iter().map(parse_turn_receipt).collect()
    }

    fn pending_approvals_with_metadata(
        &self,
        session_id: &str,
        envelope: Option<&CommandEnvelope>,
    ) -> io::Result<Vec<PendingApproval>> {
        validate_session_id(session_id)?;
        let response =
            self.get_json_with_metadata(&format!("sessions/{session_id}/approvals"), envelope)?;
        let approvals = response.as_array().ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "approvals response must be an array",
            )
        })?;
        approvals.iter().map(parse_pending_approval).collect()
    }

    pub fn session_events(&self, session_id: &str) -> io::Result<ControlPlaneEventStream> {
        let session_id = escape_path_segment(session_id)?;
        Ok(ControlPlaneEventStream {
            url: format!("ws://127.0.0.1:{}/ws/session/{session_id}", self.port),
            subprotocols: vec![
                "codinal.v1".to_owned(),
                format!("codinal.auth.{}", self.token.as_str()),
            ],
        })
    }
}

impl CommandTransport for ControlPlaneClient {
    fn dispatch(&self, envelope: CommandEnvelope) -> io::Result<CommandResponse> {
        let request_id = envelope.request_id.clone();
        let payload = match &envelope.command {
            ControlPlaneCommand::CheckHealth => {
                CommandPayload::Health(self.health_with_metadata(Some(&envelope))?)
            }
            ControlPlaneCommand::StartTurn {
                session_id,
                input,
                provider,
                model,
                effort,
            } => CommandPayload::TurnStarted(self.start_turn_with_metadata(
                session_id,
                input,
                provider,
                model,
                effort,
                Some(&envelope),
            )?),
            ControlPlaneCommand::InterruptTurn { session_id } => CommandPayload::TurnInterrupted(
                self.interrupt_turn_with_metadata(session_id, Some(&envelope))?,
            ),
            ControlPlaneCommand::CreateSession {
                workspace,
                title,
                model,
                origin,
                origin_label,
                origin_session_id,
            } => CommandPayload::SessionCreated(self.create_session_with_metadata(
                workspace,
                title,
                model,
                origin.as_deref(),
                origin_label.as_deref(),
                origin_session_id.as_deref(),
                Some(&envelope),
            )?),
            ControlPlaneCommand::ListSessions => {
                CommandPayload::Sessions(self.list_sessions_with_metadata(Some(&envelope))?)
            }
            ControlPlaneCommand::LoadSession { session_id } => CommandPayload::SessionLoaded {
                messages: self.session_messages_with_metadata(session_id, Some(&envelope))?,
                approvals: self.pending_approvals_with_metadata(session_id, Some(&envelope))?,
                receipts: self.turn_receipts_with_metadata(session_id, Some(&envelope))?,
            },
            ControlPlaneCommand::GetSessionMessages { session_id } => CommandPayload::Messages(
                self.session_messages_with_metadata(session_id, Some(&envelope))?,
            ),
            ControlPlaneCommand::ListPendingApprovals { session_id } => CommandPayload::Approvals(
                self.pending_approvals_with_metadata(session_id, Some(&envelope))?,
            ),
            ControlPlaneCommand::ListTurnReceipts { session_id } => CommandPayload::TurnReceipts(
                self.turn_receipts_with_metadata(session_id, Some(&envelope))?,
            ),
            ControlPlaneCommand::ResolveApproval {
                session_id,
                approval_id,
                outcome,
            } => {
                self.resolve_approval_with_metadata(
                    session_id,
                    approval_id,
                    *outcome,
                    Some(&envelope),
                )?;
                CommandPayload::ApprovalResolved
            }
        };
        Ok(CommandResponse {
            request_id,
            payload,
        })
    }
}

fn validate_session_id(session_id: &str) -> io::Result<()> {
    let valid = !session_id.starts_with("__")
        && !session_id.is_empty()
        && session_id.len() <= 128
        && session_id.bytes().enumerate().all(|(index, byte)| {
            byte.is_ascii_alphanumeric() || (index > 0 && matches!(byte, b'_' | b'-'))
        });
    if valid {
        Ok(())
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid session id",
        ))
    }
}

fn validate_project_id(project_id: &str) -> io::Result<()> {
    validate_session_id(project_id)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "invalid project id"))
}

fn validate_project_name(name: &str) -> io::Result<()> {
    if name.trim().is_empty() || name.len() > 160 || name.contains(['\r', '\n']) {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid project name",
        ))
    } else {
        Ok(())
    }
}

fn validate_project_roots(roots: &[String]) -> io::Result<()> {
    if roots.len() > 64 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "too many project roots",
        ));
    }
    for root in roots {
        if root.is_empty()
            || root.len() > 4096
            || !Path::new(root).is_absolute()
            || root.contains(['\0', '\r', '\n'])
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid project root",
            ));
        }
    }
    Ok(())
}

fn validate_source_path(path: &str) -> io::Result<()> {
    if path.is_empty()
        || path.len() > 4096
        || !Path::new(path).is_absolute()
        || path.contains(['\0', '\r', '\n'])
    {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid source path",
        ))
    } else {
        Ok(())
    }
}

fn validate_source_attachment_id(attachment_id: &str) -> io::Result<()> {
    if !attachment_id.is_empty()
        && attachment_id.len() <= 160
        && attachment_id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
    {
        Ok(())
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid source attachment id",
        ))
    }
}

fn validate_approval_id(approval_id: &str) -> io::Result<()> {
    if approval_id.len() == 32
        && approval_id
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        Ok(())
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid approval id",
        ))
    }
}

fn escape_path_segment(value: &str) -> io::Result<String> {
    if value.is_empty() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "control-plane path segment must not be empty",
        ));
    }
    Ok(url::form_urlencoded::byte_serialize(value.as_bytes())
        .collect::<String>()
        .replace('+', "%20"))
}

fn session_search_path(query: &str, limit: usize) -> io::Result<String> {
    let query = query.trim();
    if !(1..=256).contains(&query.len())
        || query.chars().any(|character| character == '\0')
        || !(1..=100).contains(&limit)
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid session search",
        ));
    }
    Ok(format!(
        "sessions/search?q={}&limit={limit}",
        escape_path_segment(query)?
    ))
}

fn parse_session_summary(value: &serde_json::Value) -> io::Result<SessionSummary> {
    let object = value.as_object().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            "session response must be an object",
        )
    })?;
    let required = |field| {
        object
            .get(field)
            .and_then(serde_json::Value::as_str)
            .filter(|value| !value.is_empty())
            .map(str::to_owned)
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid session response"))
    };
    Ok(SessionSummary {
        session_id: required("session_id")?,
        title: required("title")?,
        workspace: required("workspace")?,
        messages: object
            .get("messages")
            .and_then(serde_json::Value::as_u64)
            .ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidData, "invalid session response")
            })?,
        updated_at: object
            .get("updated_at")
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default()
            .to_owned(),
        pinned: object
            .get("pinned")
            .and_then(serde_json::Value::as_bool)
            .unwrap_or(false),
        archived: object
            .get("archived")
            .and_then(serde_json::Value::as_bool)
            .unwrap_or(false),
        origin: object
            .get("origin")
            .and_then(serde_json::Value::as_str)
            .map(str::to_owned),
        origin_label: object
            .get("origin_label")
            .and_then(serde_json::Value::as_str)
            .map(str::to_owned),
        origin_session_id: object
            .get("origin_session_id")
            .and_then(serde_json::Value::as_str)
            .map(str::to_owned),
        project_id: object
            .get("project_id")
            .and_then(serde_json::Value::as_str)
            .filter(|value| !value.is_empty())
            .map(str::to_owned),
    })
}

fn parse_project_summary(value: &serde_json::Value) -> io::Result<ProjectSummary> {
    let object = value.as_object().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            "project response must be an object",
        )
    })?;
    let required = |field| {
        object
            .get(field)
            .and_then(serde_json::Value::as_str)
            .filter(|value| !value.is_empty())
            .map(str::to_owned)
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid project response"))
    };
    let roots = object
        .get("roots")
        .and_then(serde_json::Value::as_array)
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid project roots"))?
        .iter()
        .map(|value| {
            let root = value.as_object().ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidData, "invalid project root response")
            })?;
            Ok(ProjectRootSummary {
                root_id: root
                    .get("root_id")
                    .and_then(serde_json::Value::as_str)
                    .filter(|value| !value.is_empty())
                    .ok_or_else(|| {
                        io::Error::new(io::ErrorKind::InvalidData, "invalid project root response")
                    })?
                    .to_owned(),
                path: root
                    .get("path")
                    .and_then(serde_json::Value::as_str)
                    .filter(|value| !value.is_empty())
                    .ok_or_else(|| {
                        io::Error::new(io::ErrorKind::InvalidData, "invalid project root response")
                    })?
                    .to_owned(),
                primary: root
                    .get("primary")
                    .and_then(serde_json::Value::as_bool)
                    .unwrap_or(false),
            })
        })
        .collect::<io::Result<Vec<_>>>()?;
    Ok(ProjectSummary {
        project_id: required("project_id")?,
        name: required("name")?,
        roots,
        pinned: object
            .get("pinned")
            .and_then(serde_json::Value::as_bool)
            .unwrap_or(false),
        updated_at: object
            .get("updated_at")
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default()
            .to_owned(),
        task_count: object
            .get("task_count")
            .and_then(serde_json::Value::as_u64)
            .unwrap_or(0),
    })
}

fn parse_source_attachment(value: &serde_json::Value) -> io::Result<SourceAttachment> {
    let object = value.as_object().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            "source attachment response must be an object",
        )
    })?;
    let required = |field| {
        object
            .get(field)
            .and_then(serde_json::Value::as_str)
            .filter(|value| !value.is_empty())
            .map(str::to_owned)
            .ok_or_else(|| {
                io::Error::new(
                    io::ErrorKind::InvalidData,
                    "invalid source attachment response",
                )
            })
    };
    Ok(SourceAttachment {
        attachment_id: required("attachment_id")?,
        session_id: required("session_id")?,
        path: required("path")?,
        name: required("name")?,
        kind: required("kind")?,
        status: required("status")?,
        error: object
            .get("error")
            .and_then(serde_json::Value::as_str)
            .map(str::to_owned),
        attached_at: object
            .get("attached_at")
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default()
            .to_owned(),
        updated_at: object
            .get("updated_at")
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default()
            .to_owned(),
    })
}

fn parse_activity_item(value: &serde_json::Value) -> io::Result<ActivityItem> {
    let object = value.as_object().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            "activity item response must be an object",
        )
    })?;
    let required = |field| {
        object
            .get(field)
            .and_then(serde_json::Value::as_str)
            .filter(|value| !value.is_empty())
            .map(str::to_owned)
            .ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidData, "invalid activity item response")
            })
    };
    Ok(ActivityItem {
        activity_id: required("activity_id")?,
        session_id: object
            .get("session_id")
            .and_then(serde_json::Value::as_str)
            .map(str::to_owned),
        kind: required("kind")?,
        title: required("title")?,
        detail: required("detail")?,
        unread: object
            .get("unread")
            .and_then(serde_json::Value::as_bool)
            .unwrap_or(false),
    })
}

fn parse_source_preview(value: &serde_json::Value) -> io::Result<SourcePreview> {
    let object = value.as_object().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            "source preview response must be an object",
        )
    })?;
    Ok(SourcePreview {
        attachment: parse_source_attachment(object.get("attachment").ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "source preview is missing attachment",
            )
        })?)?,
        content: object
            .get("content")
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default()
            .to_owned(),
        binary: object
            .get("binary")
            .and_then(serde_json::Value::as_bool)
            .unwrap_or(false),
        truncated: object
            .get("truncated")
            .and_then(serde_json::Value::as_bool)
            .unwrap_or(false),
    })
}

fn parse_message_summary(value: &serde_json::Value) -> io::Result<MessageSummary> {
    let object = value.as_object().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            "message response must be an object",
        )
    })?;
    let role = object
        .get("role")
        .and_then(serde_json::Value::as_str)
        .filter(|role| matches!(*role, "user" | "assistant" | "tool" | "notice"))
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid message role"))?;
    let text = object
        .get("content")
        .and_then(serde_json::Value::as_str)
        .or_else(|| object.get("text").and_then(serde_json::Value::as_str))
        .unwrap_or("[structured content]");
    Ok(MessageSummary {
        role: role.to_owned(),
        text: text.chars().take(4_000).collect(),
    })
}

fn parse_runtime_capabilities(value: &serde_json::Value) -> io::Result<RuntimeCapabilities> {
    let object = value.as_object().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            "runtime capabilities response must be an object",
        )
    })?;
    let required = |field| {
        object
            .get(field)
            .and_then(serde_json::Value::as_str)
            .filter(|value| !value.is_empty())
            .map(str::to_owned)
            .ok_or_else(|| {
                io::Error::new(
                    io::ErrorKind::InvalidData,
                    "invalid runtime capabilities response",
                )
            })
    };
    let boolean = |field| {
        object
            .get(field)
            .and_then(serde_json::Value::as_bool)
            .ok_or_else(|| {
                io::Error::new(
                    io::ErrorKind::InvalidData,
                    "invalid runtime capabilities response",
                )
            })
    };
    let provider = object
        .get("provider")
        .and_then(serde_json::Value::as_str)
        .filter(|value| !value.is_empty())
        .unwrap_or("unknown")
        .to_owned();
    let model = object
        .get("model")
        .and_then(serde_json::Value::as_str)
        .filter(|value| !value.is_empty())
        .unwrap_or("unknown")
        .to_owned();
    let effort = object
        .get("effort")
        .and_then(serde_json::Value::as_str)
        .filter(|value| !value.is_empty())
        .unwrap_or("unknown")
        .to_owned();
    let provider_configured = object
        .get("provider_configured")
        .and_then(serde_json::Value::as_bool)
        .unwrap_or(false);
    let start_turn = boolean("start_turn")?;
    let model_profiles = parse_model_profiles(
        object,
        &provider,
        &model,
        &effort,
        provider_configured,
        start_turn,
    )?;
    Ok(RuntimeCapabilities {
        runtime_owner: required("runtime_owner")?,
        turn_execution_owner: required("turn_execution_owner")?,
        receipt_write_owner: required("receipt_write_owner")?,
        provider,
        model,
        effort,
        model_profiles,
        experimental_execution: object
            .get("experimental_execution")
            .and_then(serde_json::Value::as_bool)
            .unwrap_or(false),
        provider_configured,
        start_turn,
        interrupt_turn: boolean("interrupt_turn")?,
        mutations: object
            .get("mutations")
            .and_then(serde_json::Value::as_bool)
            .unwrap_or(false),
        run_disabled_reason: object
            .get("run_disabled_reason")
            .and_then(serde_json::Value::as_str)
            .filter(|value| !value.is_empty())
            .map(str::to_owned),
        mutation_disabled_reason: object
            .get("mutation_disabled_reason")
            .and_then(serde_json::Value::as_str)
            .filter(|value| !value.is_empty())
            .map(str::to_owned),
    })
}

fn parse_model_profiles(
    object: &serde_json::Map<String, serde_json::Value>,
    current_provider: &str,
    current_model: &str,
    current_effort: &str,
    current_configured: bool,
    current_ready: bool,
) -> io::Result<Vec<ModelProfile>> {
    let Some(values) = object
        .get("model_profiles")
        .and_then(serde_json::Value::as_array)
    else {
        return Ok(vec![ModelProfile {
            provider: current_provider.to_owned(),
            model: current_model.to_owned(),
            effort: current_effort.to_owned(),
            configured: current_configured,
            probe_status: if current_ready {
                "passed".to_owned()
            } else {
                "unknown".to_owned()
            },
            ready: current_ready,
        }]);
    };
    let profiles = values
        .iter()
        .map(|value| {
            let object = value.as_object().ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidData, "invalid model profile")
            })?;
            let required = |field| {
                object
                    .get(field)
                    .and_then(serde_json::Value::as_str)
                    .filter(|value| !value.is_empty())
                    .map(str::to_owned)
                    .ok_or_else(|| {
                        io::Error::new(io::ErrorKind::InvalidData, "invalid model profile")
                    })
            };
            let configured = object
                .get("configured")
                .and_then(serde_json::Value::as_bool)
                .unwrap_or(false);
            let probe_status = object
                .get("probe_status")
                .and_then(serde_json::Value::as_str)
                .filter(|value| !value.is_empty())
                .unwrap_or("unknown")
                .to_owned();
            let ready = object
                .get("ready")
                .and_then(serde_json::Value::as_bool)
                .unwrap_or(configured && probe_status == "passed");
            Ok(ModelProfile {
                provider: required("provider")?,
                model: required("model")?,
                effort: required("effort")?,
                configured,
                probe_status,
                ready,
            })
        })
        .collect::<io::Result<Vec<_>>>()?;
    if profiles.is_empty() {
        return Ok(vec![ModelProfile {
            provider: current_provider.to_owned(),
            model: current_model.to_owned(),
            effort: current_effort.to_owned(),
            configured: current_configured,
            probe_status: if current_ready {
                "passed".to_owned()
            } else {
                "unknown".to_owned()
            },
            ready: current_ready,
        }]);
    }
    Ok(profiles)
}

fn parse_turn_control_result(value: &serde_json::Value) -> io::Result<TurnControlResult> {
    let object = value.as_object().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            "turn control response must be an object",
        )
    })?;
    let ok = object
        .get("ok")
        .and_then(serde_json::Value::as_bool)
        .ok_or_else(|| {
            io::Error::new(io::ErrorKind::InvalidData, "invalid turn control response")
        })?;
    let session_id = object
        .get("session_id")
        .and_then(serde_json::Value::as_str)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid turn control response"))?
        .to_owned();
    validate_session_id(&session_id)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid turn control response"))?;
    Ok(TurnControlResult { ok, session_id })
}

fn parse_turn_receipt(value: &serde_json::Value) -> io::Result<TurnReceipt> {
    let object = value.as_object().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            "turn receipt response must be an object",
        )
    })?;
    let required = |field| {
        object
            .get(field)
            .and_then(serde_json::Value::as_str)
            .filter(|value| !value.is_empty())
            .map(str::to_owned)
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid turn receipt"))
    };
    let outcome = object
        .get("outcome")
        .cloned()
        .filter(|value| value.is_object())
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid turn receipt"))?;
    Ok(TurnReceipt {
        turn_id: required("turn_id")?,
        session_id: required("session_id")?,
        outcome,
        message_count: object
            .get("message_count")
            .and_then(serde_json::Value::as_i64)
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid turn receipt"))?,
        created_at: required("created_at")?,
    })
}

fn parse_pending_approval(value: &serde_json::Value) -> io::Result<PendingApproval> {
    let object = value.as_object().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            "approval response must be an object",
        )
    })?;
    let required = |field| {
        object
            .get(field)
            .and_then(serde_json::Value::as_str)
            .filter(|value| !value.is_empty())
            .map(str::to_owned)
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid approval response"))
    };
    let approval_id = required("approval_id")?;
    validate_approval_id(&approval_id)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid approval response"))?;
    Ok(PendingApproval {
        approval_id,
        tool_name: required("tool_name")?,
        arguments: object
            .get("arguments")
            .filter(|value| value.is_object())
            .cloned()
            .ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidData, "invalid approval response")
            })?,
        reason: required("reason")?,
        risk: required("risk")?,
        command: object
            .get("command")
            .and_then(serde_json::Value::as_str)
            .filter(|value| !value.is_empty())
            .map(str::to_owned),
    })
}

fn validate_route(path: &str) -> io::Result<()> {
    if path.is_empty() || path.starts_with('/') || path.contains('?') || path.contains('#') {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid control-plane route",
        ));
    }
    Ok(())
}

fn validate_command_token(value: &str, label: &str) -> io::Result<()> {
    if !value.is_empty()
        && value.len() <= MAX_COMMAND_TOKEN_LENGTH
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.' | b':'))
    {
        Ok(())
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("invalid command {label}"),
        ))
    }
}

fn parse_json_response(response: &[u8]) -> io::Result<serde_json::Value> {
    let header_end = response
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "malformed control-plane response",
            )
        })?;
    let status_line = response[..header_end]
        .split(|byte| *byte == b'\n')
        .next()
        .ok_or_else(|| {
            io::Error::new(io::ErrorKind::InvalidData, "missing control-plane status")
        })?;
    if !status_line.starts_with(b"HTTP/1.1 2") && !status_line.starts_with(b"HTTP/1.0 2") {
        return Err(io::Error::other("control plane rejected request"));
    }
    serde_json::from_slice(&response[header_end + 4..])
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error.to_string()))
}

fn parse_operation_response<T: serde::de::DeserializeOwned>(
    response: serde_json::Value,
) -> io::Result<T> {
    serde_json::from_value(response)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error.to_string()))
}

pub struct Request {
    url: String,
    authorization: Zeroizing<String>,
}

impl Request {
    pub fn url(&self) -> &str {
        &self.url
    }
    pub fn authorization(&self) -> &str {
        self.authorization.as_str()
    }
}

#[cfg(test)]
mod tests {
    use super::{
        parse_pending_approval, ApprovalConfirmation, ApprovalOutcome, ControlPlaneClient,
        OperationEnvelope, OperationState,
    };
    use std::io::{BufRead, BufReader, Read, Write};
    use std::net::TcpListener;
    use std::thread;

    const TOKEN: &str = "0123456789abcdef0123456789abcdef";

    #[test]
    fn golden_v1_fixture_stays_versioned_and_secret_free() {
        let fixture: serde_json::Value =
            serde_json::from_str(include_str!("../../../contracts/v1/control-plane.json"))
                .expect("valid golden fixture");
        assert_eq!(fixture["fixture_version"], 1);
        assert_eq!(fixture["contract"], "codinal.control-plane.v1");
        let mut payload = fixture.clone();
        payload
            .as_object_mut()
            .expect("fixture object")
            .remove("redaction");
        let serialized = payload.to_string().to_ascii_lowercase();
        for marker in fixture["redaction"]["forbidden_value_markers"]
            .as_array()
            .expect("markers")
        {
            assert!(
                !serialized.contains(marker.as_str().expect("string marker")),
                "fixture must not contain secret-shaped material"
            );
        }
    }

    #[test]
    fn golden_v1_event_fixtures_pin_order_and_reconnect_contracts() {
        let fixture: serde_json::Value =
            serde_json::from_str(include_str!("../../../contracts/v1/control-plane.json"))
                .expect("valid golden fixture");
        let events = fixture["events"].as_array().expect("event fixtures");
        assert_eq!(
            events[0]["sequence"],
            serde_json::json!(["turn_started", "tool_proposed", "turn_completed"])
        );
        assert_eq!(
            events[1]["before_reconnect"],
            serde_json::json!(["turn_started"])
        );
        assert_eq!(
            events[1]["after_reconnect"],
            serde_json::json!(["turn_completed"])
        );
    }

    #[test]
    fn golden_storage_fixture_pins_every_reference_database() {
        let fixture: serde_json::Value =
            serde_json::from_str(include_str!("../../../contracts/v1/storage.json"))
                .expect("valid storage fixture");
        assert_eq!(fixture["fixture_version"], 1);
        assert_eq!(fixture["contract"], "codinal.sqlite.v1");
        assert_eq!(
            fixture["databases"].as_array().expect("databases").len(),
            9,
            "new durable stores require an explicit fixture update"
        );
    }

    #[test]
    fn gets_authenticated_json_from_loopback() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("connection");
            let mut request = String::new();
            let mut reader = BufReader::new(&stream);
            loop {
                let mut line = String::new();
                reader.read_line(&mut line).expect("read request");
                if line == "\r\n" {
                    break;
                }
                request.push_str(&line);
            }
            assert!(request.starts_with("GET /v1/sessions HTTP/1.1\r\n"));
            assert!(request.contains(&format!("Authorization: Bearer {TOKEN}\r\n")));
            stream
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n[{\"session_id\":\"session-1\",\"title\":\"Migration\",\"workspace\":\"/tmp/workspace\",\"messages\":3,\"updated_at\":\"2026-08-03T10:00:00Z\",\"pinned\":true,\"archived\":false,\"origin\":null,\"origin_label\":null,\"origin_session_id\":null,\"project_id\":\"project-1\"}]")
                .expect("write response");
        });

        let sessions = ControlPlaneClient::new(port, TOKEN)
            .expect("client")
            .list_sessions()
            .expect("JSON response");
        assert_eq!(sessions.len(), 1);
        assert_eq!(sessions[0].title, "Migration");
        assert_eq!(sessions[0].messages, 3);
        assert_eq!(sessions[0].updated_at, "2026-08-03T10:00:00Z");
        assert!(sessions[0].pinned);
        assert_eq!(sessions[0].project_id.as_deref(), Some("project-1"));
        server.join().expect("server");
    }

    #[test]
    fn searches_authenticated_session_path_and_parses_results() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("connection");
            let mut request = String::new();
            let mut reader = BufReader::new(&stream);
            loop {
                let mut line = String::new();
                reader.read_line(&mut line).expect("read request");
                if line == "\r\n" {
                    break;
                }
                request.push_str(&line);
            }
            assert!(request
                .starts_with("GET /v1/sessions/search?q=fix%20%2F%20bug&limit=20 HTTP/1.1\r\n"));
            assert!(request.contains(&format!("Authorization: Bearer {TOKEN}\r\n")));
            stream
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n[{\"session_id\":\"session-1\",\"title\":\"Fix bug\",\"workspace\":\"/tmp/workspace\",\"messages\":2,\"updated_at\":\"2026-08-03T10:00:00Z\",\"pinned\":false,\"archived\":false,\"origin\":null,\"origin_label\":null,\"origin_session_id\":null,\"project_id\":null}]")
                .expect("write response");
        });

        let sessions = ControlPlaneClient::new(port, TOKEN)
            .expect("client")
            .search_sessions("fix / bug", 20)
            .expect("search response");
        assert_eq!(sessions.len(), 1);
        assert_eq!(sessions[0].title, "Fix bug");
        server.join().expect("server");
    }

    #[test]
    fn lists_authenticated_conversation_sources_and_parses_typed_state() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("connection");
            let mut request = String::new();
            let mut reader = BufReader::new(&stream);
            loop {
                let mut line = String::new();
                reader.read_line(&mut line).expect("read request");
                if line == "\r\n" {
                    break;
                }
                request.push_str(&line);
            }
            assert!(request.starts_with("GET /v1/sessions/session-1/sources HTTP/1.1\r\n"));
            assert!(request.contains(&format!("Authorization: Bearer {TOKEN}\r\n")));
            stream
                .write_all(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n[{\"attachment_id\":\"source-abc\",\"session_id\":\"session-1\",\"path\":\"/tmp/reference.md\",\"name\":\"reference.md\",\"kind\":\"file\",\"status\":\"ready\",\"error\":null,\"attached_at\":\"2026-08-03T10:00:00Z\",\"updated_at\":\"2026-08-03T10:00:00Z\"}]",
                )
                .expect("write response");
        });

        let sources = ControlPlaneClient::new(port, TOKEN)
            .expect("client")
            .list_source_attachments("session-1")
            .expect("source response");
        assert_eq!(sources.len(), 1);
        assert_eq!(sources[0].attachment_id, "source-abc");
        assert_eq!(sources[0].kind, "file");
        assert_eq!(sources[0].status, "ready");
        assert_eq!(sources[0].error, None);
        server.join().expect("server");
    }

    #[test]
    fn source_client_rejects_unsafe_paths_and_attachment_ids() {
        let client = ControlPlaneClient::new(1, TOKEN).expect("client");
        assert!(client.attach_source("session-1", "relative.md").is_err());
        assert!(client
            .remove_source_attachment("session-1", "source/escape")
            .is_err());
        assert!(client
            .retry_source_attachment("__internal", "source-safe")
            .is_err());
    }

    #[test]
    fn parses_typed_source_preview_metadata_and_content() {
        let preview = super::parse_source_preview(&serde_json::json!({
            "attachment": {
                "attachment_id": "source-abc",
                "session_id": "session-1",
                "path": "/tmp/reference.md",
                "name": "reference.md",
                "kind": "file",
                "status": "ready",
                "error": null,
                "attached_at": "2026-08-03T10:00:00Z",
                "updated_at": "2026-08-03T10:00:00Z"
            },
            "content": "keep the original",
            "binary": false,
            "truncated": true
        }))
        .expect("source preview");
        assert_eq!(preview.attachment.name, "reference.md");
        assert_eq!(preview.content, "keep the original");
        assert!(!preview.binary);
        assert!(preview.truncated);
    }

    #[test]
    fn legacy_session_summary_defaults_optional_navigation_metadata() {
        let summary = super::parse_session_summary(&serde_json::json!({
            "session_id": "session-legacy",
            "title": "Legacy",
            "workspace": "/tmp/workspace",
            "messages": 0
        }))
        .expect("legacy summary");
        assert_eq!(summary.updated_at, "");
        assert!(!summary.pinned);
        assert!(!summary.archived);
        assert_eq!(summary.project_id, None);
    }

    #[test]
    fn session_search_path_is_bounded_and_percent_encoded() {
        assert_eq!(
            super::session_search_path("  fix / bug  ", 20).expect("search path"),
            "sessions/search?q=fix%20%2F%20bug&limit=20"
        );
        assert!(super::session_search_path("", 20).is_err());
        assert!(super::session_search_path("query", 0).is_err());
        assert!(super::session_search_path("query", 101).is_err());
    }

    #[test]
    fn capability_probe_sends_explicit_approval_and_profile() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("connection");
            let mut reader = BufReader::new(&stream);
            let mut headers = String::new();
            loop {
                let mut line = String::new();
                reader.read_line(&mut line).expect("read header");
                if line == "\r\n" {
                    break;
                }
                headers.push_str(&line);
            }
            assert!(headers.starts_with("POST /v1/capabilities/probe HTTP/1.1\r\n"));
            assert!(headers.contains(&format!("Authorization: Bearer {TOKEN}\r\n")));
            let body_len = headers
                .lines()
                .find_map(|line| {
                    line.strip_prefix("Content-Length: ")
                        .and_then(|value| value.parse::<usize>().ok())
                })
                .expect("content length");
            let mut body = vec![0_u8; body_len];
            reader.read_exact(&mut body).expect("read body");
            let body: serde_json::Value = serde_json::from_slice(&body).expect("JSON body");
            assert_eq!(body["approved"], true);
            assert_eq!(body["provider"], "opencode-go");
            assert_eq!(body["model"], "kimi-k2.7-code");
            assert_eq!(body["effort"], "medium");
            stream
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"status\":\"passed\"}")
                .expect("write response");
        });
        ControlPlaneClient::new(port, TOKEN)
            .expect("client")
            .probe_capability("opencode-go", "kimi-k2.7-code", "medium")
            .expect("probe");
        server.join().expect("server");
    }

    #[test]
    fn typed_operation_client_preserves_envelope_and_lifecycle_routes() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            let read_request = |stream: &mut std::net::TcpStream| {
                let mut reader = BufReader::new(stream);
                let mut headers = String::new();
                loop {
                    let mut line = String::new();
                    reader.read_line(&mut line).expect("read headers");
                    if line == "\r\n" {
                        break;
                    }
                    headers.push_str(&line);
                }
                let length = headers
                    .lines()
                    .find_map(|line| {
                        line.strip_prefix("Content-Length: ")
                            .and_then(|value| value.parse::<usize>().ok())
                    })
                    .unwrap_or(0);
                let mut body = vec![0_u8; length];
                reader.read_exact(&mut body).expect("read body");
                (headers, body)
            };

            let (mut stream, _) = listener.accept().expect("submit connection");
            let (headers, body) = read_request(&mut stream);
            assert!(headers.starts_with("POST /v1/operations HTTP/1.1\r\n"));
            let envelope: serde_json::Value = serde_json::from_slice(&body).expect("envelope");
            assert_eq!(envelope["operation_id"], "operation:1");
            assert_eq!(envelope["capability"], "git.status");
            stream
                .write_all(b"HTTP/1.1 202 Accepted\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"schema\":\"codinal.operation.v1\",\"request_id\":\"request-1\",\"operation_id\":\"operation:1\",\"state\":\"accepted\",\"replayed\":false,\"next_sequence\":1}")
                .expect("submit response");
            stream
                .shutdown(std::net::Shutdown::Write)
                .expect("close submit response");

            let (mut stream, _) = listener.accept().expect("resume connection");
            let (headers, _) = read_request(&mut stream);
            assert!(headers.starts_with("GET /v1/operations/operation:1?after=0 HTTP/1.1\r\n"));
            stream
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"ack\":{\"schema\":\"codinal.operation.v1\",\"request_id\":\"request-1\",\"operation_id\":\"operation:1\",\"state\":\"accepted\",\"replayed\":true,\"next_sequence\":1},\"progress\":[],\"receipt\":null}")
                .expect("resume response");
            stream
                .shutdown(std::net::Shutdown::Write)
                .expect("close resume response");

            let (mut stream, _) = listener.accept().expect("cancel connection");
            let (headers, _) = read_request(&mut stream);
            assert!(headers.starts_with("POST /v1/operations/operation:1/cancel HTTP/1.1\r\n"));
            stream
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"schema\":\"codinal.operation.v1\",\"request_id\":\"request-1\",\"operation_id\":\"operation:1\",\"state\":\"cancelled\",\"replayed\":false,\"next_sequence\":2}")
                .expect("cancel response");
            stream
                .shutdown(std::net::Shutdown::Write)
                .expect("close cancel response");
        });

        let envelope = OperationEnvelope::new(
            "request-1",
            "operation:1",
            "idempotency-1",
            u128::MAX,
            "git.status",
            serde_json::json!({"repo": "", "approval_id": "approval-1"}),
        )
        .expect("envelope");
        let client = ControlPlaneClient::new(port, TOKEN).expect("client");
        let ack = client.submit_operation(&envelope).expect("submit");
        assert_eq!(ack.state, OperationState::Accepted);
        let resume = client.resume_operation("operation:1", 0).expect("resume");
        assert_eq!(resume.ack.operation_id, "operation:1");
        let cancelled = client.cancel_operation("operation:1").expect("cancel");
        assert_eq!(cancelled.state, OperationState::Cancelled);
        server.join().expect("server");
    }

    #[test]
    fn health_returns_typed_status_and_request_metadata() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("connection");
            let mut request = String::new();
            let mut reader = BufReader::new(&stream);
            loop {
                let mut line = String::new();
                reader.read_line(&mut line).expect("read request");
                if line == "\r\n" {
                    break;
                }
                request.push_str(&line);
            }
            assert!(request.starts_with("GET /v1/health HTTP/1.1\r\n"));
            assert!(request.contains(&format!("Authorization: Bearer {TOKEN}\r\n")));
            assert!(request.contains("X-Codinal-Request-Id: desktop-command-"));
            stream
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"status\":\"ok\",\"capabilities\":{\"runtime_owner\":\"python\",\"turn_execution_owner\":\"python\",\"receipt_write_owner\":\"python\",\"start_turn\":true,\"interrupt_turn\":true}}")
                .expect("write response");
        });

        let health = ControlPlaneClient::new(port, TOKEN)
            .expect("client")
            .health()
            .expect("health response");
        assert_eq!(health.status, "ok");
        assert_eq!(health.capabilities.runtime_owner, "python");
        assert!(health.capabilities.start_turn);
        assert!(health.capabilities.interrupt_turn);
        server.join().expect("server");
    }

    #[test]
    fn health_preserves_read_only_mode_and_disabled_action_reasons() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("connection");
            let mut request = String::new();
            let mut reader = BufReader::new(&stream);
            loop {
                let mut line = String::new();
                reader.read_line(&mut line).expect("read request");
                if line == "\r\n" {
                    break;
                }
                request.push_str(&line);
            }
            assert!(request.starts_with("GET /v1/health HTTP/1.1\r\n"));
            stream
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"status\":\"ok\",\"mode\":\"read_only\",\"reason_code\":\"owner_bootstrap_deferred\",\"migration\":{\"state\":\"not_started\"},\"writer_lock\":{\"state\":\"not_acquired\",\"owner\":null},\"event_store\":{\"ready\":false},\"capabilities\":{\"runtime_owner\":\"rust\",\"turn_execution_owner\":\"none\",\"receipt_write_owner\":\"none\",\"start_turn\":false,\"interrupt_turn\":false,\"mutations\":false,\"run_disabled_reason\":\"owner_bootstrap_deferred\",\"mutation_disabled_reason\":\"owner_bootstrap_deferred\"}}")
                .expect("write response");
        });

        let health = ControlPlaneClient::new(port, TOKEN)
            .expect("client")
            .health()
            .expect("health response");
        assert_eq!(health.mode, "read_only");
        assert_eq!(health.reason_code, "owner_bootstrap_deferred");
        assert_eq!(health.migration_state, "not_started");
        assert_eq!(health.writer_lock_state, "not_acquired");
        assert!(!health.event_store_ready);
        assert_eq!(
            health.capabilities.run_disabled_reason.as_deref(),
            Some("owner_bootstrap_deferred")
        );
        assert!(!health.capabilities.mutations);
        server.join().expect("server");
    }

    #[test]
    fn starts_and_interrupts_turn_with_python_wire_shape() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            {
                let (mut stream, _) = listener.accept().expect("capability connection");
                let mut reader = BufReader::new(&stream);
                let mut request = String::new();
                loop {
                    let mut line = String::new();
                    reader
                        .read_line(&mut line)
                        .expect("read capability request");
                    if line == "\r\n" {
                        break;
                    }
                    request.push_str(&line);
                }
                assert!(request.starts_with("GET /v1/health HTTP/1.1\r\n"));
                stream
                    .write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"status\":\"ok\",\"capabilities\":{\"runtime_owner\":\"python\",\"turn_execution_owner\":\"python\",\"receipt_write_owner\":\"python\",\"start_turn\":true,\"interrupt_turn\":true}}")
                    .expect("write capability response");
            }
            {
                let (mut stream, _) = listener.accept().expect("start connection");
                let mut reader = BufReader::new(&stream);
                let mut request = String::new();
                loop {
                    let mut line = String::new();
                    reader.read_line(&mut line).expect("read start request");
                    if line == "\r\n" {
                        break;
                    }
                    request.push_str(&line);
                }
                assert!(request.starts_with("POST /v1/sessions/session-1/turns HTTP/1.1\r\n"));
                assert!(request.contains("X-Codinal-Request-Id: desktop-command-"));
                let body_len = request
                    .lines()
                    .find_map(|line| {
                        line.strip_prefix("Content-Length: ")
                            .and_then(|value| value.parse::<usize>().ok())
                    })
                    .expect("content length");
                let mut received = vec![0_u8; body_len];
                reader.read_exact(&mut received).expect("read start body");
                let body: serde_json::Value = serde_json::from_slice(&received).expect("body");
                assert_eq!(body["input"], "Fix bug");
                assert_eq!(body["provider"], "opencode-go");
                assert_eq!(body["model"], "kimi-k2.7-code");
                assert_eq!(body["effort"], "medium");
                stream
                    .write_all(b"HTTP/1.1 202 Accepted\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"ok\":true,\"session_id\":\"session-1\"}")
                    .expect("write start response");
            }
            {
                let (mut stream, _) = listener.accept().expect("capability connection");
                let mut reader = BufReader::new(&stream);
                let mut request = String::new();
                loop {
                    let mut line = String::new();
                    reader
                        .read_line(&mut line)
                        .expect("read capability request");
                    if line == "\r\n" {
                        break;
                    }
                    request.push_str(&line);
                }
                assert!(request.starts_with("GET /v1/health HTTP/1.1\r\n"));
                stream
                    .write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"status\":\"ok\",\"capabilities\":{\"runtime_owner\":\"python\",\"turn_execution_owner\":\"python\",\"receipt_write_owner\":\"python\",\"start_turn\":true,\"interrupt_turn\":true}}")
                    .expect("write capability response");
            }
            {
                let (mut stream, _) = listener.accept().expect("interrupt connection");
                let mut reader = BufReader::new(&stream);
                let mut request = String::new();
                loop {
                    let mut line = String::new();
                    reader.read_line(&mut line).expect("read interrupt request");
                    if line == "\r\n" {
                        break;
                    }
                    request.push_str(&line);
                }
                assert!(request.starts_with("POST /v1/sessions/session-1/interrupt HTTP/1.1\r\n"));
                stream
                    .write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"ok\":true,\"session_id\":\"session-1\"}")
                    .expect("write interrupt response");
            }
        });

        let client = ControlPlaneClient::new(port, TOKEN).expect("client");
        assert_eq!(
            client
                .start_turn("session-1", "Fix bug")
                .expect("start turn"),
            super::TurnControlResult {
                ok: true,
                session_id: "session-1".to_owned(),
            }
        );
        assert_eq!(
            client.interrupt_turn("session-1").expect("interrupt turn"),
            super::TurnControlResult {
                ok: true,
                session_id: "session-1".to_owned(),
            }
        );
        server.join().expect("server");
    }

    #[test]
    fn refuses_an_unsafe_session_identifier() {
        let client = ControlPlaneClient::new(1, TOKEN).expect("client");
        assert!(client.session_messages("../secrets").is_err());
        assert!(client.session_messages("__internal").is_err());
    }

    #[test]
    fn parses_pending_approval_with_review_arguments() {
        let approval = parse_pending_approval(&serde_json::json!({
            "approval_id": "0123456789abcdef0123456789abcdef",
            "tool_name": "shell",
            "arguments": {"path": "README.md"},
            "reason": "writes a local file",
            "risk": "write_local",
            "command": ""
        }))
        .expect("approval");
        assert_eq!(approval.risk, "write_local");
        assert_eq!(approval.command, None);
        assert_eq!(approval.arguments["path"], "README.md");
    }

    #[test]
    fn resolves_only_the_explicit_approval_payload() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("connection");
            let mut reader = BufReader::new(&stream);
            let mut request = String::new();
            loop {
                let mut line = String::new();
                reader.read_line(&mut line).expect("read request");
                if line == "\r\n" {
                    break;
                }
                request.push_str(&line);
            }
            assert!(request.starts_with("POST /v1/sessions/session-1/approvals/0123456789abcdef0123456789abcdef HTTP/1.1\r\n"));
            let mut body = [0_u8; 18];
            reader.read_exact(&mut body).expect("read body");
            assert_eq!(&body, b"{\"outcome\":\"deny\"}");
            stream
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"ok\":true}")
                .expect("write response");
        });

        ControlPlaneClient::new(port, TOKEN)
            .expect("client")
            .resolve_approval(
                "session-1",
                "0123456789abcdef0123456789abcdef",
                ApprovalOutcome::Deny,
            )
            .expect("approval result");
        server.join().expect("server");
    }

    #[test]
    fn builds_session_events_stream_without_token_in_url() {
        let stream = ControlPlaneClient::new(1, TOKEN)
            .expect("client")
            .session_events("alpha/beta")
            .expect("stream");
        assert_eq!(stream.url(), "ws://127.0.0.1:1/ws/session/alpha%2Fbeta");
        assert_eq!(
            stream.subprotocols(),
            vec!["codinal.v1".to_owned(), format!("codinal.auth.{TOKEN}")]
        );
        assert!(!stream.url().contains(TOKEN));
    }

    #[test]
    fn confirmation_defaults_to_cancel_and_cannot_be_revived() {
        let mut confirmation = ApprovalConfirmation::new(
            "session-1",
            "0123456789abcdef0123456789abcdef",
            ApprovalOutcome::Once,
        )
        .expect("confirmation");
        assert_eq!(confirmation.submission(), None);
        confirmation.cancel();
        assert!(!confirmation.confirm());
        assert_eq!(confirmation.submission(), None);
    }

    #[test]
    fn confirmed_reducer_exposes_only_its_original_payload() {
        let mut confirmation = ApprovalConfirmation::new(
            "session-1",
            "0123456789abcdef0123456789abcdef",
            ApprovalOutcome::Deny,
        )
        .expect("confirmation");
        assert!(confirmation.confirm());
        assert_eq!(
            confirmation.submission(),
            Some((
                "session-1",
                "0123456789abcdef0123456789abcdef",
                ApprovalOutcome::Deny,
            ))
        );
    }

    #[test]
    fn unconfirmed_reducer_never_attempts_transport() {
        let client = ControlPlaneClient::new(1, TOKEN).expect("client");
        let confirmation = ApprovalConfirmation::new(
            "session-1",
            "0123456789abcdef0123456789abcdef",
            ApprovalOutcome::Once,
        )
        .expect("confirmation");
        assert!(!client
            .resolve_confirmation(&confirmation)
            .expect("no transport"));
    }
}
