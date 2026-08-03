//! Rust-native, loopback-only v1 runtime foundation.
//!
//! The production process exposes a truthful, authenticated read-only surface
//! by default. Writer ownership and execution are an explicit Experimental
//! bootstrap, never an implicit fallback.

pub mod parent_watchdog;

use fs2::FileExt;
use sha2::{Digest, Sha256};
use std::cell::Cell;
use std::collections::BTreeMap;
use std::fs;
use std::fs::{File, OpenOptions};
use std::io::{self, Read, Seek, SeekFrom, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpListener, TcpStream};
use std::os::unix::fs::MetadataExt;
use std::path::{Component, Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, RwLock, RwLockReadGuard};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tungstenite::http::HeaderValue;
use tungstenite::{accept_hdr, Message};
use zeroize::{Zeroize, Zeroizing};

pub use codinal_harness::{HarnessInventory, HarnessManager, HarnessRoots, HostProjectionRoot};
pub use codinal_policy::{
    ApprovalBroker, ApprovalChokepoint, PendingApproval, PermissionRequest, Risk,
};
pub use codinal_providers::{
    AssistantTurn, DeepSeekProvider, OllamaProvider, OpenCodeGoProvider, ProviderId,
    ProviderSecrets, ToolCall, BUNDLED_CATALOGUE_REVISION, BUNDLED_MODEL_CATALOGUE,
    DEEPSEEK_ENDPOINT, DEEPSEEK_MODEL, OPENCODE_GO_ENDPOINT, OPENCODE_GO_MODEL,
};
pub use codinal_tools::{
    GitOperation, GitRequest, McpRequest, OperationAck, OperationEnvelope, OperationLedger,
    OperationProgress, OperationReceipt, OperationResume, OperationState, ReceiptStore,
    ShellRequest, ToolClass, ToolConfig, ToolExecution, ToolGateway, ToolReceipt, ToolRisk,
    ToolStatus, OPERATION_SCHEMA,
};

static NEXT_EVENT_HUB_ID: AtomicU64 = AtomicU64::new(1);
static NEXT_SESSION_ID: AtomicU64 = AtomicU64::new(1);
static NEXT_PROJECT_ID: AtomicU64 = AtomicU64::new(1);
const MAX_TURN_TOKENS: i64 = 8_192;
const MAX_ACTIVE_RESERVED_TOKENS: i64 = 100_000;
const MAX_DAILY_TOKENS: i64 = 100_000;
const MAX_ASSISTANT_DELTA_BYTES: usize = 16 * 1024;
const MAX_TOOL_ROUNDS: usize = 4;
const MAX_TOOL_RESULT_BYTES: usize = 128 * 1024;
const CAPABILITY_PROBE_TTL_MS: u128 = 5 * 60 * 1_000;
const APPROVAL_TTL_MS: u128 = 5 * 60 * 1_000;
const APPROVAL_EXPIRY_KEY: &str = "_codinal_expires_at_ms";
const OPENCODE_GO_CAPABILITY_PROBE_MAX_OUTPUT_TOKENS: u64 = 64;
const DEEPSEEK_CAPABILITY_PROBE_MAX_OUTPUT_TOKENS: u64 = 256;
const CAPABILITY_PROBE_TOOL: &str = "codinal_capability_probe";

/// In-process, live v1 event fan-out. Events are never retained here; durable
/// replay belongs to the storage layer.
pub struct EventHub {
    id: u64,
    next_subscription_id: u64,
    global_listeners: BTreeMap<u64, EventListener>,
    session_listeners: BTreeMap<String, BTreeMap<u64, EventListener>>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RuntimeEvent {
    /// The original v1 JSON object. The event hub deliberately does not
    /// interpret or reshape this payload before fan-out.
    pub message: serde_json::Map<String, serde_json::Value>,
}

pub struct EventSubscription {
    hub_id: u64,
    scope: SubscriptionScope,
    id: u64,
}

enum SubscriptionScope {
    Global,
    Session(String),
}

pub type EventListener = Box<dyn FnMut(&RuntimeEvent) -> io::Result<()> + Send>;

impl EventHub {
    pub fn subscribe_global(&mut self, listener: EventListener) -> EventSubscription {
        let id = self.allocate_subscription_id();
        self.global_listeners.insert(id, listener);
        EventSubscription {
            hub_id: self.id,
            scope: SubscriptionScope::Global,
            id,
        }
    }

    pub fn subscribe_session(
        &mut self,
        session_id: &str,
        listener: EventListener,
    ) -> io::Result<EventSubscription> {
        validate_session_subject(session_id)?;
        let id = self.allocate_subscription_id();
        self.session_listeners
            .entry(session_id.to_owned())
            .or_default()
            .insert(id, listener);
        Ok(EventSubscription {
            hub_id: self.id,
            scope: SubscriptionScope::Session(session_id.to_owned()),
            id,
        })
    }

    pub fn unsubscribe(&mut self, subscription: EventSubscription) -> bool {
        if subscription.hub_id != self.id {
            return false;
        }
        match subscription.scope {
            SubscriptionScope::Global => self.global_listeners.remove(&subscription.id).is_some(),
            SubscriptionScope::Session(session_id) => {
                let Some(listeners) = self.session_listeners.get_mut(&session_id) else {
                    return false;
                };
                let removed = listeners.remove(&subscription.id).is_some();
                if listeners.is_empty() {
                    self.session_listeners.remove(&session_id);
                }
                removed
            }
        }
    }

    pub fn publish_global(&mut self, event: &RuntimeEvent) {
        notify_listeners(&mut self.global_listeners, event);
    }

    pub fn publish_session(&mut self, session_id: &str, event: &RuntimeEvent) -> io::Result<()> {
        validate_session_subject(session_id)?;
        if let Some(listeners) = self.session_listeners.get_mut(session_id) {
            notify_listeners(listeners, event);
            if listeners.is_empty() {
                self.session_listeners.remove(session_id);
            }
        }
        Ok(())
    }

    fn allocate_subscription_id(&mut self) -> u64 {
        let id = self.next_subscription_id;
        self.next_subscription_id = self
            .next_subscription_id
            .checked_add(1)
            .expect("subscription ids exhausted");
        id
    }
}

impl RuntimeEvent {
    pub fn new(message: serde_json::Map<String, serde_json::Value>) -> Self {
        Self { message }
    }
}

impl Default for EventHub {
    fn default() -> Self {
        Self {
            id: NEXT_EVENT_HUB_ID.fetch_add(1, Ordering::Relaxed),
            next_subscription_id: 1,
            global_listeners: BTreeMap::new(),
            session_listeners: BTreeMap::new(),
        }
    }
}

fn notify_listeners(listeners: &mut BTreeMap<u64, EventListener>, event: &RuntimeEvent) {
    let failed = listeners
        .iter_mut()
        .filter_map(|(id, listener)| listener(event).is_err().then_some(*id))
        .collect::<Vec<_>>();
    for id in failed {
        listeners.remove(&id);
    }
}

fn validate_session_subject(value: &str) -> io::Result<()> {
    let valid = !value.is_empty() && value.len() <= 128 && !value.contains(['\r', '\n']);
    valid.then_some(()).ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            "event session subject must be bounded single-line text",
        )
    })
}

#[derive(Default)]
pub struct RuntimePolicy {
    approvals: ApprovalChokepoint,
}

impl RuntimePolicy {
    pub fn approve_once(&mut self, approval_id: &str) -> bool {
        self.approvals.approve_once(approval_id)
    }

    pub fn authorize_mutation(
        &mut self,
        risk: Risk,
        approval_id: Option<&str>,
        subject: &str,
    ) -> (bool, Option<codinal_policy::AuditEvent>) {
        self.approvals
            .authorize_with_audit(risk, approval_id, subject)
    }
}

const MAX_REQUEST_BYTES: usize = 32 * 1024;
const MIN_TOKEN_LENGTH: usize = 32;
const MAX_ACTIVE_CONNECTIONS: usize = 128;

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RuntimeMode {
    Booting,
    ReadOnly,
    Ready,
    Degraded,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
pub enum RuntimeReasonCode {
    #[serde(rename = "owner_bootstrap_deferred")]
    OwnerBootstrapDeferred,
    #[serde(rename = "ready")]
    Ready,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MigrationState {
    NotStarted,
    Verified,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "snake_case")]
pub enum WriterLockState {
    NotAcquired,
    Held,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
pub struct MigrationReadiness {
    pub state: MigrationState,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct WriterLockReadiness {
    pub state: WriterLockState,
    pub owner: Option<String>,
    pub owner_metadata: Option<RuntimeOwnerIdentity>,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct RuntimeOwnerIdentity {
    pub pid: u32,
    pub process_start_time_unix_ms: u128,
    pub data_directory_identity: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
pub struct EventStoreReadiness {
    pub ready: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct RuntimeReadiness {
    pub mode: RuntimeMode,
    pub reason_code: RuntimeReasonCode,
    pub migration: MigrationReadiness,
    pub writer_lock: WriterLockReadiness,
    pub event_store: EventStoreReadiness,
    pub execution_owner: String,
    pub receipt_writer: String,
}

impl RuntimeReadiness {
    fn read_only() -> Self {
        Self {
            mode: RuntimeMode::ReadOnly,
            reason_code: RuntimeReasonCode::OwnerBootstrapDeferred,
            migration: MigrationReadiness {
                state: MigrationState::NotStarted,
            },
            writer_lock: WriterLockReadiness {
                state: WriterLockState::NotAcquired,
                owner: None,
                owner_metadata: None,
            },
            event_store: EventStoreReadiness { ready: false },
            execution_owner: "none".to_owned(),
            receipt_writer: "none".to_owned(),
        }
    }

    fn owner_ready(owner_metadata: Option<RuntimeOwnerIdentity>) -> Self {
        Self {
            mode: RuntimeMode::Ready,
            reason_code: RuntimeReasonCode::Ready,
            migration: MigrationReadiness {
                state: MigrationState::Verified,
            },
            writer_lock: WriterLockReadiness {
                state: WriterLockState::Held,
                owner: Some("rust-runtime".to_owned()),
                owner_metadata: owner_metadata.clone(),
            },
            event_store: EventStoreReadiness { ready: true },
            execution_owner: owner_metadata
                .as_ref()
                .map(|_| "rust".to_owned())
                .unwrap_or_else(|| "none".to_owned()),
            receipt_writer: "rust".to_owned(),
        }
    }

    fn reason_code(&self) -> &'static str {
        match self.reason_code {
            RuntimeReasonCode::OwnerBootstrapDeferred => "owner_bootstrap_deferred",
            RuntimeReasonCode::Ready => "ready",
        }
    }

    fn is_read_only(&self) -> bool {
        self.mode == RuntimeMode::ReadOnly
    }
}

#[derive(Clone)]
pub struct RuntimeConfig {
    port: u16,
    token: Zeroizing<String>,
    data_dir: PathBuf,
    approval_broker: Arc<Mutex<ApprovalBroker>>,
    audit_ledger: Option<codinal_policy::AuditLedger>,
    provider_secrets: Arc<RwLock<ProviderSecrets>>,
    ollama_port: u16,
    opencode_endpoint: String,
    deepseek_endpoint: String,
    provider_transport: Arc<Mutex<Option<codinal_providers::ProviderTransport>>>,
    capability_probes: Arc<Mutex<CapabilityProbeRegistry>>,
    readiness: RuntimeReadiness,
    runtime_store: Option<codinal_storage::RuntimeStore>,
    tool_gateway: Option<Arc<codinal_tools::ToolGateway>>,
    operation_ledger: Option<Arc<codinal_tools::OperationLedger>>,
    experimental_execution: bool,
    turn_cancellation: Arc<Mutex<BTreeMap<String, ActiveTurn>>>,
    activity_read: Arc<AtomicBool>,
    shutdown: Arc<AtomicBool>,
    active_connections: Arc<AtomicUsize>,
}

#[derive(Clone)]
struct ActiveTurn {
    session_id: String,
    cancellation: Arc<AtomicBool>,
}

struct ProviderTurnJob {
    turn_id: String,
    session_id: String,
    input: String,
    context_messages: Vec<serde_json::Value>,
    cancellation: Arc<AtomicBool>,
    profile: ExecutionProfile,
    fallback_requested: bool,
    budget_reservation_id: Option<String>,
}

#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
struct ProviderResumeToolCall {
    id: String,
    name: String,
    arguments: serde_json::Map<String, serde_json::Value>,
}

#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
struct ProviderTurnResume {
    provider: String,
    model: String,
    effort: String,
    input: String,
    context_messages: Vec<serde_json::Value>,
    assistant_text: Option<String>,
    tool_calls: Vec<ProviderResumeToolCall>,
    fallback_requested: bool,
    budget_reservation_id: Option<String>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
enum ExecutionProfile {
    OpenCodeGo,
    DeepSeek,
}

impl ExecutionProfile {
    fn provider(self) -> &'static str {
        match self {
            Self::OpenCodeGo => "opencode-go",
            Self::DeepSeek => "deepseek",
        }
    }

    fn model(self) -> &'static str {
        match self {
            Self::OpenCodeGo => OPENCODE_GO_MODEL,
            Self::DeepSeek => DEEPSEEK_MODEL,
        }
    }

    fn effort(self) -> &'static str {
        match self {
            Self::OpenCodeGo => "medium",
            Self::DeepSeek => "high",
        }
    }

    fn provider_id(self) -> ProviderId {
        match self {
            Self::OpenCodeGo => ProviderId::OpenCodeGo,
            Self::DeepSeek => ProviderId::DeepSeek,
        }
    }

    fn uses_budget(self) -> bool {
        matches!(self, Self::DeepSeek)
    }

    fn capability_probe_max_output_tokens(self) -> u64 {
        match self {
            Self::OpenCodeGo => OPENCODE_GO_CAPABILITY_PROBE_MAX_OUTPUT_TOKENS,
            Self::DeepSeek => DEEPSEEK_CAPABILITY_PROBE_MAX_OUTPUT_TOKENS,
        }
    }
}

#[derive(Clone, Debug)]
struct CapabilityProbeRecord {
    status: codinal_providers::ProbeStatus,
    checked_at_ms: Option<u128>,
    expires_at_ms: Option<u128>,
    endpoint: Option<String>,
    reason: Option<String>,
}

#[derive(Clone, Debug)]
struct CapabilityProbeView {
    status: codinal_providers::ProbeStatus,
    checked_at_ms: Option<u128>,
    expires_at_ms: Option<u128>,
    reason: Option<String>,
}

#[derive(Default)]
struct CapabilityProbeRegistry {
    records: BTreeMap<ExecutionProfile, CapabilityProbeRecord>,
}

impl ProviderTurnResume {
    fn profile(&self) -> io::Result<ExecutionProfile> {
        match (
            self.provider.as_str(),
            self.model.as_str(),
            self.effort.as_str(),
        ) {
            ("opencode-go", OPENCODE_GO_MODEL, "medium") => Ok(ExecutionProfile::OpenCodeGo),
            ("deepseek", DEEPSEEK_MODEL, "high") => Ok(ExecutionProfile::DeepSeek),
            _ => Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "durable provider resume profile is unsupported",
            )),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RuntimeOwnerState {
    ColdStart,
    Reconcile,
    LockedActive,
    DegradedRecovering,
}

#[derive(Debug, serde::Serialize, PartialEq, Eq)]
pub struct TurnIngressResult {
    pub pending_approval_ids: Vec<String>,
    pub allowed_read_tool_call_ids: Vec<String>,
    pub rejected_tool_call_ids: Vec<String>,
}

#[derive(Debug, Default)]
struct RuntimeStartupTrace {
    entries: Vec<String>,
}

impl RuntimeStartupTrace {
    fn record(&mut self, entry: impl Into<String>) {
        self.entries.push(entry.into());
    }

    fn as_slice(&self) -> &[String] {
        &self.entries
    }
}

/// Process bootstrap for the native runtime. Constructing this value reserves
/// the data directory before any writable store can be opened.
pub struct RuntimeBootstrap {
    config: RuntimeConfig,
    _owner_lock: RuntimeOwnerLock,
    startup_state: RuntimeOwnerState,
    startup_trace: RuntimeStartupTrace,
}

/// Read-only production bootstrap. This path intentionally does not acquire
/// the writer lock, run migration, attach a writable audit ledger, or publish
/// events. It is the only production bootstrap until the C1 owner gates pass.
pub struct ReadOnlyBootstrap {
    config: RuntimeConfig,
}

struct RuntimeOwnerLock {
    file: File,
    identity: RuntimeOwnerIdentity,
}

impl RuntimeOwnerLock {
    fn acquire(data_dir: &Path) -> io::Result<Self> {
        let lock_path = data_dir.join(".codinal-runtime.lock");
        let mut lock = OpenOptions::new()
            .create(true)
            .read(true)
            .write(true)
            .truncate(false)
            .open(&lock_path)?;
        if let Err(error) = lock.try_lock_exclusive() {
            let owner = fs::read_to_string(&lock_path)
                .ok()
                .and_then(|encoded| serde_json::from_str::<RuntimeOwnerIdentity>(&encoded).ok())
                .map(|identity| {
                    format!(
                        "pid={} start_ms={} data_dir={}",
                        identity.pid,
                        identity.process_start_time_unix_ms,
                        identity.data_directory_identity
                    )
                })
                .unwrap_or_else(|| "unknown".to_owned());
            return Err(io::Error::new(
                error.kind(),
                format!("runtime writer lock unavailable; owner={owner}"),
            ));
        }
        let identity = RuntimeOwnerIdentity {
            pid: std::process::id(),
            process_start_time_unix_ms: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map_err(|_| io::Error::other("system clock is before Unix epoch"))?
                .as_millis(),
            data_directory_identity: data_directory_identity(data_dir)?,
        };
        lock.set_len(0)?;
        lock.seek(SeekFrom::Start(0))?;
        serde_json::to_writer(&lock, &identity)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        lock.sync_all()?;
        Ok(Self {
            file: lock,
            identity,
        })
    }
}

impl Drop for RuntimeOwnerLock {
    fn drop(&mut self) {
        let _ = self.file.unlock();
    }
}

impl RuntimeBootstrap {
    fn transition_state(&mut self, next: RuntimeOwnerState) {
        self.startup_state = next;
        self.startup_trace
            .record(format!("startup:{:?}", self.startup_state));
    }

    pub fn startup_state(&self) -> RuntimeOwnerState {
        self.startup_state
    }

    pub fn startup_trace(&self) -> &[String] {
        self.startup_trace.as_slice()
    }

    fn reconcile_own_data_directory(&mut self) -> io::Result<()> {
        let reports = codinal_storage::prepare_owned_data_directory(self.config.data_dir())?;
        if reports.is_empty() {
            self.startup_trace.record("migration:report:empty");
        }
        for report in reports {
            self.startup_trace.record(format!(
                "migration:plan:{}:{}->{}:backup={} recovered={}",
                report.database,
                report.from_version,
                report.to_version,
                report.backup.is_some(),
                report.recovered_from.is_some()
            ));
        }
        Ok(())
    }

    fn with_owner_transition(config: RuntimeConfig) -> io::Result<Self> {
        let lock_path = config.data_dir().join(".codinal-runtime.lock");
        let owner_lock = RuntimeOwnerLock::acquire(config.data_dir())?;
        let mut runtime = Self {
            config,
            _owner_lock: owner_lock,
            startup_state: RuntimeOwnerState::ColdStart,
            startup_trace: RuntimeStartupTrace::default(),
        };
        runtime.startup_trace.record("startup:ColdStart");
        runtime.transition_state(RuntimeOwnerState::Reconcile);
        runtime.reconcile_own_data_directory()?;
        runtime.transition_state(RuntimeOwnerState::LockedActive);
        runtime.config.attach_audit_ledger()?;
        let runtime_store = codinal_storage::RuntimeStore::open_owned(runtime.config.data_dir())?;
        runtime
            .config
            .activity_read
            .store(runtime_store.activity_read()?, Ordering::Release);
        runtime.config.runtime_store = Some(runtime_store);
        runtime.config.attach_operation_ledger()?;
        runtime.config.attach_tool_gateway()?;
        runtime.config.restore_durable_approvals()?;
        runtime.config.readiness =
            RuntimeReadiness::owner_ready(Some(runtime._owner_lock.identity.clone()));
        runtime
            .startup_trace
            .record(format!("lock:held:{:?}", lock_path));
        Ok(runtime)
    }

    pub fn from_values(port: u16, token: &str, data_dir: &Path) -> io::Result<Self> {
        let config = RuntimeConfig::new(port, token, data_dir)?;
        Self::with_owner_transition(config)
    }

    /// Read launch values once and remove the bearer token before starting the
    /// listener, preventing later child processes from inheriting it.
    pub fn from_environment() -> io::Result<Self> {
        let stdin = io::stdin();
        Self::from_environment_reader(&mut stdin.lock())
    }

    pub fn from_environment_reader(reader: &mut impl Read) -> io::Result<Self> {
        let (config, provider_secrets) = read_environment_config(reader)?;
        let runtime = Self::with_owner_transition(config)?;
        *runtime
            .config
            .provider_secrets
            .write()
            .map_err(|_| io::Error::other("provider secret lock poisoned"))? = provider_secrets;
        Ok(runtime)
    }

    pub fn config(&self) -> &RuntimeConfig {
        &self.config
    }

    pub fn provider_secrets(&self) -> io::Result<RwLockReadGuard<'_, ProviderSecrets>> {
        self.config
            .provider_secrets
            .read()
            .map_err(|_| io::Error::other("provider secret lock poisoned"))
    }

    pub fn serve_forever(&self) -> io::Result<()> {
        serve_connections(&self.config)
    }

    pub fn request_shutdown(&self) {
        self.config.request_shutdown();
    }
}

impl ReadOnlyBootstrap {
    pub fn from_values(port: u16, token: &str, data_dir: &Path) -> io::Result<Self> {
        let mut config = RuntimeConfig::new(port, token, data_dir)?;
        config.readiness = RuntimeReadiness::read_only();
        Ok(Self { config })
    }

    pub fn from_environment() -> io::Result<Self> {
        let stdin = io::stdin();
        Self::from_environment_reader(&mut stdin.lock())
    }

    pub fn from_environment_reader(reader: &mut impl Read) -> io::Result<Self> {
        let (mut config, provider_secrets) = read_environment_config(reader)?;
        config.readiness = RuntimeReadiness::read_only();
        *config
            .provider_secrets
            .write()
            .map_err(|_| io::Error::other("provider secret lock poisoned"))? = provider_secrets;
        Ok(Self { config })
    }

    pub fn config(&self) -> &RuntimeConfig {
        &self.config
    }

    pub fn provider_secrets(&self) -> io::Result<RwLockReadGuard<'_, ProviderSecrets>> {
        self.config
            .provider_secrets
            .read()
            .map_err(|_| io::Error::other("provider secret lock poisoned"))
    }

    pub fn serve_forever(&self) -> io::Result<()> {
        serve_connections(&self.config)
    }

    pub fn request_shutdown(&self) {
        self.config.request_shutdown();
    }
}

fn read_environment_config(reader: &mut impl Read) -> io::Result<(RuntimeConfig, ProviderSecrets)> {
    let token = Zeroizing::new(std::env::var("CODINAL_SESSION_TOKEN").map_err(|_| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            "CODINAL_SESSION_TOKEN is required",
        )
    })?);
    // Safe at process startup before the runtime creates threads.
    unsafe { std::env::remove_var("CODINAL_SESSION_TOKEN") };
    let port = std::env::var("CODINAL_PORT")
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "CODINAL_PORT is required"))?
        .parse::<u16>()
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "CODINAL_PORT is invalid"))?;
    let data_dir = std::env::var_os("CODINAL_DATA_DIR").ok_or_else(|| {
        io::Error::new(io::ErrorKind::InvalidInput, "CODINAL_DATA_DIR is required")
    })?;
    let config = RuntimeConfig::new(port, &token, Path::new(&data_dir))?;
    let channel = std::env::var("CODINAL_SECRET_BOOTSTRAP").unwrap_or_default();
    // Safe at process startup before the runtime creates threads.
    unsafe { std::env::remove_var("CODINAL_SECRET_BOOTSTRAP") };
    let provider_secrets = match channel.as_str() {
        "" => ProviderSecrets::empty(),
        "stdin-v1" => {
            let mut payload = Zeroizing::new(Vec::new());
            reader.take(128 * 1024 + 1).read_to_end(&mut payload)?;
            ProviderSecrets::from_bootstrap(&payload)?
        }
        _ => {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "unsupported secret bootstrap channel",
            ));
        }
    };
    Ok((config, provider_secrets))
}

/// Start the packaged native runtime from its host-supplied environment.
pub fn run_from_environment() -> io::Result<()> {
    if std::env::var("CODINAL_EXPERIMENTAL_EXECUTION")
        .ok()
        .as_deref()
        == Some("1")
    {
        RuntimeBootstrap::from_environment()?.serve_forever()
    } else {
        ReadOnlyBootstrap::from_environment()?.serve_forever()
    }
}

impl RuntimeConfig {
    pub fn new(port: u16, token: &str, data_dir: &Path) -> io::Result<Self> {
        Self::new_with_ollama_port(port, token, data_dir, 11_434)
    }

    pub fn new_with_ollama_port(
        port: u16,
        token: &str,
        data_dir: &Path,
        ollama_port: u16,
    ) -> io::Result<Self> {
        if port == 0 || ollama_port == 0 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "runtime port must not be zero",
            ));
        }
        validate_session_token(token)?;
        let metadata = fs::symlink_metadata(data_dir)?;
        if metadata.file_type().is_symlink() || !metadata.is_dir() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "runtime data directory must be a non-symlink directory",
            ));
        }
        Ok(Self {
            port,
            token: Zeroizing::new(token.to_owned()),
            data_dir: data_dir.to_owned(),
            approval_broker: Arc::new(Mutex::new(ApprovalBroker::default())),
            audit_ledger: None,
            provider_secrets: Arc::new(RwLock::new(ProviderSecrets::empty())),
            ollama_port,
            opencode_endpoint: OPENCODE_GO_ENDPOINT.to_owned(),
            deepseek_endpoint: DEEPSEEK_ENDPOINT.to_owned(),
            provider_transport: Arc::new(Mutex::new(None)),
            capability_probes: Arc::new(Mutex::new(CapabilityProbeRegistry::default())),
            readiness: RuntimeReadiness::read_only(),
            runtime_store: None,
            tool_gateway: None,
            operation_ledger: None,
            experimental_execution: std::env::var("CODINAL_EXPERIMENTAL_EXECUTION")
                .ok()
                .as_deref()
                == Some("1"),
            turn_cancellation: Arc::new(Mutex::new(BTreeMap::new())),
            activity_read: Arc::new(AtomicBool::new(false)),
            shutdown: Arc::new(AtomicBool::new(false)),
            active_connections: Arc::new(AtomicUsize::new(0)),
        })
    }

    pub fn bind(&self) -> io::Result<TcpListener> {
        TcpListener::bind(SocketAddrV4::new(Ipv4Addr::LOCALHOST, self.port))
    }

    pub fn data_dir(&self) -> &Path {
        &self.data_dir
    }

    pub fn readiness(&self) -> &RuntimeReadiness {
        &self.readiness
    }

    pub fn runtime_store(&self) -> Option<&codinal_storage::RuntimeStore> {
        self.runtime_store.as_ref()
    }

    fn set_activity_read(&self, read: bool) -> io::Result<()> {
        if let Some(store) = self.runtime_store.as_ref() {
            store.set_activity_read(read)?;
        }
        self.activity_read.store(read, Ordering::Release);
        Ok(())
    }

    fn provider_transport(&self) -> io::Result<codinal_providers::ProviderTransport> {
        let mut transport = self
            .provider_transport
            .lock()
            .map_err(|_| io::Error::other("provider transport lock poisoned"))?;
        if let Some(transport) = transport.as_ref() {
            return Ok(transport.clone());
        }
        let created = codinal_providers::ProviderTransport::new()?;
        *transport = Some(created.clone());
        Ok(created)
    }

    fn capability_probe_view(&self, profile: ExecutionProfile) -> CapabilityProbeView {
        let mut registry = self
            .capability_probes
            .lock()
            .unwrap_or_else(|error| error.into_inner());
        let now = now_ms();
        let endpoint = profile_endpoint(self, profile);
        let record = registry
            .records
            .entry(profile)
            .or_insert_with(|| CapabilityProbeRecord {
                status: codinal_providers::ProbeStatus::NotRun,
                checked_at_ms: None,
                expires_at_ms: None,
                endpoint: None,
                reason: None,
            });
        if record.status == codinal_providers::ProbeStatus::Passed {
            if record.endpoint.as_deref() != Some(endpoint) {
                record.status = codinal_providers::ProbeStatus::Failed;
                record.expires_at_ms = None;
                record.reason = Some("endpoint_drift".to_owned());
            } else if record
                .expires_at_ms
                .is_none_or(|expires_at| expires_at <= now)
            {
                record.status = codinal_providers::ProbeStatus::Failed;
                record.reason = Some("probe_expired".to_owned());
            }
        }
        CapabilityProbeView {
            status: record.status,
            checked_at_ms: record.checked_at_ms,
            expires_at_ms: record.expires_at_ms,
            reason: record.reason.clone(),
        }
    }

    fn record_capability_probe_success(&self, profile: ExecutionProfile) -> CapabilityProbeView {
        let mut registry = self
            .capability_probes
            .lock()
            .unwrap_or_else(|error| error.into_inner());
        let checked_at_ms = now_ms();
        registry.records.insert(
            profile,
            CapabilityProbeRecord {
                status: codinal_providers::ProbeStatus::Passed,
                checked_at_ms: Some(checked_at_ms),
                expires_at_ms: Some(checked_at_ms.saturating_add(CAPABILITY_PROBE_TTL_MS)),
                endpoint: Some(profile_endpoint(self, profile).to_owned()),
                reason: None,
            },
        );
        CapabilityProbeView {
            status: codinal_providers::ProbeStatus::Passed,
            checked_at_ms: Some(checked_at_ms),
            expires_at_ms: Some(checked_at_ms.saturating_add(CAPABILITY_PROBE_TTL_MS)),
            reason: None,
        }
    }

    fn invalidate_capability_probe(&self, profile: ExecutionProfile, reason: &str) {
        let mut registry = self
            .capability_probes
            .lock()
            .unwrap_or_else(|error| error.into_inner());
        let record = registry
            .records
            .entry(profile)
            .or_insert_with(|| CapabilityProbeRecord {
                status: codinal_providers::ProbeStatus::NotRun,
                checked_at_ms: None,
                expires_at_ms: None,
                endpoint: None,
                reason: None,
            });
        record.status = codinal_providers::ProbeStatus::Failed;
        record.expires_at_ms = None;
        record.endpoint = Some(profile_endpoint(self, profile).to_owned());
        record.reason = Some(reason.to_owned());
    }

    fn probe_capability(&self, profile: ExecutionProfile) -> io::Result<CapabilityProbeView> {
        if self.readiness.is_read_only() {
            return Err(io::Error::new(
                io::ErrorKind::PermissionDenied,
                "capability probe requires the owning runtime",
            ));
        }
        if !self.experimental_execution {
            return Err(io::Error::new(
                io::ErrorKind::PermissionDenied,
                "capability probe requires experimental execution",
            ));
        }
        let api_key = {
            let secrets = self
                .provider_secrets
                .read()
                .map_err(|_| io::Error::other("provider secret lock poisoned"))?;
            secrets
                .api_key(&profile.provider_id())
                .map(str::to_owned)
                .ok_or_else(|| {
                    io::Error::new(
                        io::ErrorKind::NotFound,
                        format!("{} provider is not configured", profile.provider()),
                    )
                })?
        };
        let messages = vec![serde_json::json!({
            "role": "user",
            "content": format!("Call {CAPABILITY_PROBE_TOOL} exactly once with an empty object."),
        })];
        let tools = vec![serde_json::json!({
            "type": "function",
            "function": {
                "name": CAPABILITY_PROBE_TOOL,
                "description": "A no-side-effect capability conformance probe.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": false,
                }
            }
        })];
        let cancellation = AtomicBool::new(false);
        let result = match profile {
            ExecutionProfile::OpenCodeGo => OpenCodeGoProvider::with_transport(
                &api_key,
                profile_endpoint(self, profile),
                self.provider_transport()?,
            )?
            .complete_probe(
                &messages,
                &tools,
                &cancellation,
                profile.capability_probe_max_output_tokens(),
            ),
            ExecutionProfile::DeepSeek => DeepSeekProvider::with_transport(
                &api_key,
                profile_endpoint(self, profile),
                self.provider_transport()?,
            )?
            .complete_probe(
                &messages,
                &tools,
                &cancellation,
                profile.capability_probe_max_output_tokens(),
            ),
        };
        let turn = match result {
            Ok(turn) => turn,
            Err(error) => {
                self.invalidate_capability_probe(profile, "probe_request_failed");
                return Err(error);
            }
        };
        if turn.tool_calls.len() != 1 || turn.tool_calls[0].name != CAPABILITY_PROBE_TOOL {
            self.invalidate_capability_probe(profile, "tool_call_conformance_failed");
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "capability probe did not return the required tool call",
            ));
        }
        Ok(self.record_capability_probe_success(profile))
    }

    #[cfg(test)]
    fn mark_capability_probe_for_test(&self, profile: ExecutionProfile) {
        let _ = self.record_capability_probe_success(profile);
    }

    pub fn tool_gateway(&self) -> Option<Arc<codinal_tools::ToolGateway>> {
        self.tool_gateway.as_ref().map(Arc::clone)
    }

    pub fn operation_ledger(&self) -> Option<Arc<codinal_tools::OperationLedger>> {
        self.operation_ledger.as_ref().map(Arc::clone)
    }

    pub fn request_shutdown(&self) {
        self.shutdown.store(true, Ordering::Release);
        // Wake the blocking accept loop so shutdown does not depend on a
        // polling sleep or on a new client request arriving naturally.
        let address = SocketAddrV4::new(Ipv4Addr::LOCALHOST, self.port);
        let _ = TcpStream::connect_timeout(&address.into(), Duration::from_millis(100));
    }

    pub fn is_shutdown_requested(&self) -> bool {
        self.shutdown.load(Ordering::Acquire)
    }

    fn harness_inventory(&self) -> io::Result<Option<HarnessInventory>> {
        let Some(source_bundle) = std::env::var_os("CODINAL_HARNESS_SOURCE_BUNDLE") else {
            return Ok(None);
        };
        let user_overlay = std::env::var_os("CODINAL_HARNESS_USER_OVERLAY")
            .unwrap_or_else(|| self.data_dir.join("harness-overlay").into_os_string());
        let live_projection = std::env::var_os("CODINAL_HARNESS_LIVE_PROJECTION")
            .unwrap_or_else(|| self.data_dir.join("harness-live").into_os_string());
        let state_dir = std::env::var_os("CODINAL_HARNESS_STATE_DIR")
            .unwrap_or_else(|| self.data_dir.join("harness-state").into_os_string());
        let hosts = std::env::var("CODINAL_HARNESS_HOST_PROJECTIONS")
            .ok()
            .map(|encoded| {
                serde_json::from_str::<Vec<HostProjectionRoot>>(&encoded).map_err(|error| {
                    io::Error::new(
                        io::ErrorKind::InvalidInput,
                        format!("invalid CODINAL_HARNESS_HOST_PROJECTIONS: {error}"),
                    )
                })
            })
            .transpose()?
            .unwrap_or_default();
        self.scan_harness_roots(HarnessRoots {
            source_bundle: PathBuf::from(source_bundle),
            user_overlay: PathBuf::from(user_overlay),
            live_projection: PathBuf::from(live_projection),
            state_dir: PathBuf::from(state_dir),
            host_projections: hosts,
        })
    }

    fn scan_harness_roots(&self, roots: HarnessRoots) -> io::Result<Option<HarnessInventory>> {
        let manager = HarnessManager::new(roots)
            .map_err(|error| io::Error::new(error.kind(), error.to_string()))?;
        manager
            .scan()
            .map(Some)
            .map_err(|error| io::Error::new(error.kind(), error.to_string()))
    }

    fn health_document(&self) -> serde_json::Value {
        let read_only = self.readiness.is_read_only();
        let reason = read_only.then_some(self.readiness.reason_code());
        let probe = self.capability_probe_view(ExecutionProfile::OpenCodeGo);
        let deepseek_probe = self.capability_probe_view(ExecutionProfile::DeepSeek);
        let probe_ready = probe.status == codinal_providers::ProbeStatus::Passed;
        let deepseek_probe_ready = deepseek_probe.status == codinal_providers::ProbeStatus::Passed;
        let probe_reason = probe.reason.as_deref().unwrap_or(match probe.status {
            codinal_providers::ProbeStatus::NotRun => "capability_probe_required",
            codinal_providers::ProbeStatus::Passed => "ready",
            codinal_providers::ProbeStatus::Failed => "capability_probe_failed",
        });
        let provider_configured = self
            .provider_secrets
            .read()
            .ok()
            .and_then(|secrets| secrets.api_key(&ProviderId::OpenCodeGo).map(|_| true))
            .unwrap_or(false);
        let deepseek_configured = self
            .provider_secrets
            .read()
            .ok()
            .and_then(|secrets| secrets.api_key(&ProviderId::DeepSeek).map(|_| true))
            .unwrap_or(false);
        let execution_ready = !read_only
            && self.readiness.mode == RuntimeMode::Ready
            && self.runtime_store.is_some()
            && self.experimental_execution
            && provider_configured
            && probe_ready;
        let deepseek_execution_ready = !read_only
            && self.readiness.mode == RuntimeMode::Ready
            && self.runtime_store.is_some()
            && self.experimental_execution
            && deepseek_configured
            && deepseek_probe_ready;
        let mode = if !read_only
            && self.readiness.mode == RuntimeMode::Ready
            && provider_configured
            && self.experimental_execution
            && !probe_ready
        {
            RuntimeMode::Degraded
        } else {
            self.readiness.mode
        };
        let reason_code = if let Some(reason) = reason {
            reason
        } else if provider_configured && self.experimental_execution && !probe_ready {
            probe_reason
        } else {
            self.readiness.reason_code()
        };
        let run_disabled_reason = if execution_ready {
            None
        } else if let Some(reason) = reason {
            Some(reason)
        } else if !self.experimental_execution {
            Some("experimental_execution_disabled")
        } else if !provider_configured {
            Some("provider_not_configured")
        } else if !probe_ready {
            Some(probe_reason)
        } else {
            Some("runtime_store_unavailable")
        };
        serde_json::json!({
            "status": "ok",
            "mode": mode,
            "reason_code": reason_code,
            "migration": self.readiness.migration,
            "writer_lock": self.readiness.writer_lock,
            "event_store": self.readiness.event_store,
            "execution_owner": self.readiness.execution_owner,
            "receipt_writer": self.readiness.receipt_writer,
            "operation_protocol": {
                "schema": OPERATION_SCHEMA,
                "available": self.operation_ledger.is_some(),
            },
            "model_catalogue": model_catalogue_document(),
            "capabilities": {
                "runtime_owner": "rust",
                "turn_execution_owner": self.readiness.execution_owner,
                "receipt_write_owner": self.readiness.receipt_writer,
                "start_turn": execution_ready,
                "interrupt_turn": execution_ready,
                "mutations": !read_only,
                "run_disabled_reason": run_disabled_reason,
                "mutation_disabled_reason": reason,
                "experimental_execution": self.experimental_execution,
                "provider": "opencode-go",
                "model": OPENCODE_GO_MODEL,
                "effort": "medium",
                "provider_configured": provider_configured,
                "capability_probe": {
                    "status": probe_status_string(probe.status),
                    "reason": probe_reason,
                    "checked_at_ms": probe.checked_at_ms,
                    "expires_at_ms": probe.expires_at_ms,
                },
                "capability_snapshots": {
                    "opencode_go": capability_snapshot_json(self, ExecutionProfile::OpenCodeGo),
                    "deepseek": capability_snapshot_json(self, ExecutionProfile::DeepSeek),
                },
                "model_profiles": [
                    {
                        "provider": "opencode-go",
                        "model": OPENCODE_GO_MODEL,
                        "effort": "medium",
                        "configured": provider_configured,
                        "probe_status": probe_status_string(probe.status),
                        "ready": execution_ready,
                    },
                    {
                        "provider": "deepseek",
                        "model": DEEPSEEK_MODEL,
                        "effort": "high",
                        "configured": deepseek_configured,
                        "probe_status": probe_status_string(deepseek_probe.status),
                        "ready": deepseek_execution_ready,
                    }
                ],
                "fallback": {
                    "provider": "deepseek",
                    "model": DEEPSEEK_MODEL,
                    "effort": "high",
                    "configured": deepseek_configured,
                    "enabled_by_default": false,
                    "max_turn_tokens": MAX_TURN_TOKENS,
                    "max_daily_tokens": MAX_DAILY_TOKENS,
                },
            }
        })
    }

    pub fn approval_broker(&self) -> Arc<Mutex<ApprovalBroker>> {
        Arc::clone(&self.approval_broker)
    }

    fn attach_audit_ledger(&mut self) -> io::Result<()> {
        self.audit_ledger = self
            .data_dir
            .join("audit.db")
            .exists()
            .then(|| {
                codinal_policy::AuditLedger::open(
                    &self.data_dir,
                    codinal_policy::AuditRedactor::default(),
                )
            })
            .transpose()?;
        Ok(())
    }

    fn attach_tool_gateway(&mut self) -> io::Result<()> {
        if !self.experimental_execution {
            return Ok(());
        }
        let Some(workspace_root) = std::env::var_os("CODINAL_WORKSPACE_ROOT") else {
            return Ok(());
        };
        let config = codinal_tools::ToolConfig::for_workspace(
            PathBuf::from(workspace_root),
            self.data_dir.join("tool-state"),
        );
        match codinal_tools::ToolGateway::new(config) {
            Ok(gateway) => self.tool_gateway = Some(Arc::new(gateway)),
            // A host workspace can disappear while the owner is bootstrapping
            // (notably during process-wide environment handoff). Keep the
            // runtime alive but leave tool execution unavailable.
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(()),
            Err(error) => return Err(error),
        }
        Ok(())
    }

    fn attach_operation_ledger(&mut self) -> io::Result<()> {
        let ledger = codinal_tools::OperationLedger::open(
            &self.data_dir.join("operation-state"),
            codinal_tools::operation::DEFAULT_QUEUE_CAPACITY,
        )?;
        self.operation_ledger = Some(Arc::new(ledger));
        Ok(())
    }

    fn restore_durable_approvals(&self) -> io::Result<()> {
        let Some(store) = self.runtime_store.as_ref() else {
            return Ok(());
        };
        let pending = store.read_all_pending_approvals()?;
        let mut broker = self
            .approval_broker
            .lock()
            .map_err(|_| io::Error::other("approval broker lock poisoned"))?;
        for record in pending {
            let request: serde_json::Value = serde_json::from_str(&record.request)
                .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
            let Some(object) = request.as_object() else {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "durable approval request is not an object",
                ));
            };
            let required = |name: &str| {
                object
                    .get(name)
                    .and_then(serde_json::Value::as_str)
                    .filter(|value| !value.is_empty())
                    .map(str::to_owned)
                    .ok_or_else(|| {
                        io::Error::new(
                            io::ErrorKind::InvalidData,
                            "durable approval request is incomplete",
                        )
                    })
            };
            broker.restore_pending(
                &record.session_id,
                PendingApproval {
                    approval_id: record.approval_id,
                    tool_name: required("tool_name")?,
                    arguments: object
                        .get("arguments")
                        .cloned()
                        .unwrap_or_else(|| serde_json::json!({})),
                    reason: required("reason")?,
                    risk: required("risk")?,
                    command: object
                        .get("command")
                        .and_then(|value| (!value.is_null()).then(|| value.as_str()))
                        .flatten()
                        .map(str::to_owned),
                },
            )?;
        }
        Ok(())
    }

    pub fn ingest_provider_turn(
        &self,
        session_id: &str,
        turn: AssistantTurn,
    ) -> io::Result<TurnIngressResult> {
        self.ingest_provider_turn_for_turn(session_id, session_id, turn)
    }

    fn ingest_provider_turn_for_turn(
        &self,
        turn_id: &str,
        session_id: &str,
        turn: AssistantTurn,
    ) -> io::Result<TurnIngressResult> {
        self.ingest_provider_turn_for_turn_with_resume(turn_id, session_id, turn, None)
    }

    fn ingest_provider_turn_for_turn_with_resume(
        &self,
        turn_id: &str,
        session_id: &str,
        turn: AssistantTurn,
        resume: Option<&ProviderTurnResume>,
    ) -> io::Result<TurnIngressResult> {
        if !codinal_storage::public_session_exists(self.data_dir(), session_id)? {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid session id",
            ));
        }
        let mut result = TurnIngressResult {
            pending_approval_ids: Vec::new(),
            allowed_read_tool_call_ids: Vec::new(),
            rejected_tool_call_ids: Vec::new(),
        };
        let mut broker = self
            .approval_broker
            .lock()
            .map_err(|_| io::Error::other("approval broker lock poisoned"))?;
        for call in turn.tool_calls {
            let risk = match call.name.as_str() {
                "write_file" | "replace_in_file" | "apply_patch" | "apply_unified_diff"
                | "git_stage" | "git_commit" => Some("write_local"),
                "run_shell" => Some("exec"),
                "read_file" | "list_files" | "grep" | "git_status" | "git_diff" | "git_log" => {
                    result.allowed_read_tool_call_ids.push(call.id.clone());
                    None
                }
                _ => {
                    result.rejected_tool_call_ids.push(call.id.clone());
                    None
                }
            };
            let Some(risk) = risk else {
                continue;
            };
            let command = (risk == "exec")
                .then(|| {
                    call.arguments
                        .get("command")
                        .and_then(serde_json::Value::as_str)
                })
                .flatten()
                .map(str::to_owned);
            let permission = PermissionRequest {
                tool_call_id: call.id,
                tool_name: call.name,
                arguments: serde_json::Value::Object(call.arguments),
                reason: format!("tool requires {risk} approval"),
                risk: risk.to_owned(),
                command,
            };
            let mut permission = permission;
            let expires_at_ms = now_ms().saturating_add(APPROVAL_TTL_MS);
            permission
                .arguments
                .as_object_mut()
                .expect("approval arguments object")
                .insert(
                    APPROVAL_EXPIRY_KEY.to_owned(),
                    serde_json::json!(expires_at_ms),
                );
            if permission.tool_name == "apply_patch" {
                let provenance =
                    patch_proposal_metadata(self.data_dir(), session_id, &permission.arguments)?;
                permission
                    .arguments
                    .as_object_mut()
                    .expect("apply_patch arguments object")
                    .extend(provenance);
            }
            let mut durable_request = serde_json::json!({
                "tool_call_id": permission.tool_call_id.clone(),
                "tool_name": permission.tool_name.clone(),
                "arguments": permission.arguments.clone(),
                "reason": permission.reason.clone(),
                "risk": permission.risk.clone(),
                "command": permission.command.clone(),
                "expires_at_ms": expires_at_ms,
            });
            if permission.tool_name == "apply_patch" {
                let provenance =
                    patch_proposal_metadata(self.data_dir(), session_id, &permission.arguments)?;
                durable_request
                    .as_object_mut()
                    .expect("approval request object")
                    .extend(provenance);
            }
            if let Some(resume) = resume {
                durable_request
                    .as_object_mut()
                    .expect("approval request object")
                    .insert(
                        "resume".to_owned(),
                        serde_json::to_value(resume)
                            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?,
                    );
            }
            let approval_id = match broker.request_for_turn(session_id, turn_id, permission.clone())
            {
                Ok(approval_id) => approval_id,
                Err(error) => {
                    for approval_id in &result.pending_approval_ids {
                        broker.resolve(session_id, approval_id);
                    }
                    return Err(error);
                }
            };
            if let Some(store) = self.runtime_store.as_ref() {
                store.put_approval(&codinal_storage::ApprovalRecord {
                    approval_id: approval_id.clone(),
                    turn_id: turn_id.to_owned(),
                    session_id: session_id.to_owned(),
                    request: serde_json::to_string(&durable_request)
                        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?,
                    state: "pending".to_owned(),
                })?;
            }
            result.pending_approval_ids.push(approval_id);
        }
        Ok(result)
    }

    fn run_deepseek_turn_with_deltas<F>(
        &self,
        session_id: &str,
        user_input: &str,
        cancellation: &AtomicBool,
        context_messages: &[serde_json::Value],
        on_delta: F,
    ) -> io::Result<AssistantTurn>
    where
        F: FnMut(&str) -> io::Result<()>,
    {
        self.run_profile_turn_with_deltas(
            ExecutionProfile::DeepSeek,
            session_id,
            user_input,
            cancellation,
            context_messages,
            on_delta,
        )
    }

    fn run_profile_turn_with_deltas<F>(
        &self,
        profile: ExecutionProfile,
        session_id: &str,
        user_input: &str,
        cancellation: &AtomicBool,
        context_messages: &[serde_json::Value],
        mut on_delta: F,
    ) -> io::Result<AssistantTurn>
    where
        F: FnMut(&str) -> io::Result<()>,
    {
        if user_input.is_empty()
            || user_input.len() > 1024 * 1024
            || user_input.chars().any(|character| character == '\0')
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid turn payload",
            ));
        }
        let mut messages = codinal_storage::read_session_messages(self.data_dir(), session_id)?;
        messages.push(serde_json::json!({"role": "user", "content": user_input}));
        messages.extend(context_messages.iter().cloned());
        let tools = builtin_tool_schemas();
        let prompt = codinal_providers::prompt::PromptEnvelope::compile(
            "codinal.runtime.policy.v1",
            &tools,
            messages,
            codinal_providers::prompt::CachePolicy::PreferStablePrefix,
        )?;
        let api_key = {
            let secrets = self
                .provider_secrets
                .read()
                .map_err(|_| io::Error::other("provider secret lock poisoned"))?;
            secrets
                .api_key(&profile.provider_id())
                .map(str::to_owned)
                .ok_or_else(|| {
                    io::Error::new(
                        io::ErrorKind::NotFound,
                        format!("{} provider is not configured", profile.provider()),
                    )
                })?
        };
        let result = match profile {
            ExecutionProfile::OpenCodeGo => {
                let provider = OpenCodeGoProvider::with_transport(
                    &api_key,
                    &self.opencode_endpoint,
                    self.provider_transport()?,
                )?;
                provider.complete_with_deltas(
                    prompt.dynamic_messages(),
                    &tools,
                    cancellation,
                    &mut on_delta,
                )
            }
            ExecutionProfile::DeepSeek => {
                let provider = DeepSeekProvider::with_transport(
                    &api_key,
                    &self.deepseek_endpoint,
                    self.provider_transport()?,
                )?;
                provider.complete_with_deltas(
                    prompt.dynamic_messages(),
                    &tools,
                    cancellation,
                    &mut on_delta,
                )
            }
        };
        if result.is_err() {
            self.invalidate_capability_probe(profile, "provider_capability_drift");
        }
        result
    }

    pub fn run_ollama_turn(
        &self,
        session_id: &str,
        model: &str,
        user_input: &str,
    ) -> io::Result<TurnIngressResult> {
        let bare_model = model.strip_prefix("ollama:").ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidInput,
                "Rust turn ingress currently requires an Ollama model",
            )
        })?;
        if bare_model.is_empty()
            || user_input.is_empty()
            || user_input.len() > 1024 * 1024
            || user_input.chars().any(|character| character == '\0')
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid turn payload",
            ));
        }
        let mut messages = codinal_storage::read_session_messages(self.data_dir(), session_id)?;
        messages.push(serde_json::json!({"role": "user", "content": user_input}));
        let turn = OllamaProvider::new(self.ollama_port)?.complete(
            bare_model,
            &messages,
            &builtin_tool_schemas(),
        )?;
        self.ingest_provider_turn(session_id, turn)
    }

    /// Compare an immutable or copied Python data directory to the v1 storage
    /// fixture. This never opens a writable SQLite connection.
    pub fn inspect_storage(&self) -> io::Result<Vec<codinal_storage::StorageMismatch>> {
        codinal_storage::inspect_v1_data_dir(&self.data_dir)
    }

    /// Materialize a separately owned, validated copy for shadow reads. The
    /// configured production directory is never opened for writing.
    pub fn create_storage_shadow_snapshot(&self, destination: &Path) -> io::Result<()> {
        codinal_storage::create_v1_shadow_snapshot(&self.data_dir, destination)
    }
}

fn builtin_tool_schemas() -> Vec<serde_json::Value> {
    [
        ("read_file", "Read a workspace file", vec!["path"]),
        (
            "apply_patch",
            "Apply one approved patch to one workspace file",
            vec!["path", "patch"],
        ),
    ]
    .into_iter()
    .map(|(name, description, required)| {
        let properties = required
            .iter()
            .map(|field| ((*field).to_owned(), serde_json::json!({"type": "string"})))
            .collect::<serde_json::Map<_, _>>();
        serde_json::json!({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                    "additionalProperties": false,
                }
            }
        })
    })
    .collect()
}

fn provider_assistant_tool_message(turn: &AssistantTurn) -> io::Result<serde_json::Value> {
    let tool_calls = turn
        .tool_calls
        .iter()
        .map(|call| {
            serde_json::to_value(serde_json::json!({
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": serde_json::to_string(&serde_json::Value::Object(call.arguments.clone()))
                        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?,
                },
            }))
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))
        })
        .collect::<io::Result<Vec<_>>>()?;
    Ok(serde_json::json!({
        "role": "assistant",
        "content": turn.text,
        "tool_calls": tool_calls,
    }))
}

fn execute_read_file_tool(
    config: &RuntimeConfig,
    session_id: &str,
    call: &ToolCall,
) -> io::Result<(serde_json::Value, serde_json::Value)> {
    if call.name != "read_file" {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "unsupported read tool",
        ));
    }
    let path = call
        .arguments
        .get("path")
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "read_file path is missing"))?;
    let workspace = session_workspace(config.data_dir(), session_id)?;
    let (_, target) = resolve_workspace_target(&workspace, path)?;
    let bytes = fs::read(&target)?;
    if bytes.len() > MAX_TOOL_RESULT_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "read_file result exceeds limit",
        ));
    }
    let content = String::from_utf8(bytes.clone())
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "read_file result is not UTF-8"))?;
    let response = serde_json::json!({
        "ok": true,
        "path": path,
        "content": content,
    });
    if serde_json::to_vec(&response)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?
        .len()
        > MAX_TOOL_RESULT_BYTES
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "read_file result exceeds limit",
        ));
    }
    let audit = serde_json::json!({
        "session_id": session_id,
        "tool_call_id": call.id,
        "tool": call.name,
        "path": path,
        "bytes": bytes.len(),
        "sha256": sha256_hex(&bytes),
    });
    Ok((response, audit))
}

const MAX_PATCH_BYTES: usize = 1024 * 1024;

fn session_workspace(data_dir: &Path, session_id: &str) -> io::Result<PathBuf> {
    codinal_storage::read_session_summaries(data_dir, None)?
        .into_iter()
        .find(|session| session.session_id == session_id)
        .map(|session| PathBuf::from(session.workspace))
        .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "session workspace unavailable"))
}

fn resolve_workspace_target(
    workspace: &Path,
    relative_path: &str,
) -> io::Result<(PathBuf, PathBuf)> {
    if relative_path.is_empty()
        || relative_path.len() > 4096
        || relative_path.contains('\0')
        || relative_path.contains('\r')
        || relative_path.contains('\n')
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid workspace path",
        ));
    }
    let relative = Path::new(relative_path);
    if relative.is_absolute()
        || relative.components().any(|component| {
            matches!(
                component,
                Component::ParentDir | Component::RootDir | Component::Prefix(_)
            )
        })
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "workspace path escapes root",
        ));
    }
    let workspace_metadata = fs::symlink_metadata(workspace)?;
    if workspace_metadata.file_type().is_symlink() || !workspace_metadata.is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "workspace root must be a directory",
        ));
    }
    let canonical_workspace = fs::canonicalize(workspace)?;
    let target = canonical_workspace.join(relative);
    let target_metadata = fs::symlink_metadata(&target)?;
    if target_metadata.file_type().is_symlink() || !target_metadata.is_file() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "workspace target must be a regular file",
        ));
    }
    let canonical_target = fs::canonicalize(&target)?;
    if !canonical_target.starts_with(&canonical_workspace) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "workspace path escapes root",
        ));
    }
    Ok((canonical_workspace, canonical_target))
}

fn sha256_hex(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn patch_arguments(arguments: &serde_json::Value) -> io::Result<(&str, &str)> {
    let object = arguments.as_object().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            "apply_patch arguments are not an object",
        )
    })?;
    let path = object
        .get("path")
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "apply_patch path is missing"))?;
    let patch = object
        .get("patch")
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| {
            io::Error::new(io::ErrorKind::InvalidData, "apply_patch patch is missing")
        })?;
    if patch.is_empty() || patch.len() > MAX_PATCH_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "apply_patch patch exceeds limit",
        ));
    }
    Ok((path, patch))
}

fn patch_proposal_metadata(
    data_dir: &Path,
    session_id: &str,
    arguments: &serde_json::Value,
) -> io::Result<serde_json::Map<String, serde_json::Value>> {
    let (path, patch) = patch_arguments(arguments)?;
    let workspace = session_workspace(data_dir, session_id)?;
    let (canonical_workspace, target) = resolve_workspace_target(&workspace, path)?;
    let source = fs::read(&target)?;
    let source_text = String::from_utf8(source.clone()).map_err(|_| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            "apply_patch source is not UTF-8",
        )
    })?;
    let _ = apply_single_file_patch(path, patch, &source_text)?;
    Ok(serde_json::Map::from_iter([
        (
            "workspace_root".to_owned(),
            serde_json::Value::String(canonical_workspace.to_string_lossy().into_owned()),
        ),
        (
            "source_hash".to_owned(),
            serde_json::Value::String(sha256_hex(&source)),
        ),
        (
            "patch_hash".to_owned(),
            serde_json::Value::String(sha256_hex(patch.as_bytes())),
        ),
    ]))
}

fn apply_single_file_patch(path: &str, patch: &str, source: &str) -> io::Result<String> {
    if patch.len() > MAX_PATCH_BYTES || patch.contains('\r') || source.contains('\r') {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "unsupported patch encoding",
        ));
    }
    let lines = patch.lines().collect::<Vec<_>>();
    if lines.first().copied() != Some("*** Begin Patch")
        || lines.last().copied() != Some("*** End Patch")
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "patch must use the bounded Codinal format",
        ));
    }
    let update_lines = lines
        .iter()
        .enumerate()
        .filter_map(|(index, line)| {
            line.strip_prefix("*** Update File: ")
                .map(|path| (index, path))
        })
        .collect::<Vec<_>>();
    if update_lines.len() != 1 || update_lines[0].1 != path {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "patch must update exactly the selected file",
        ));
    }
    let update_index = update_lines[0].0;
    let end_index = lines.len() - 1;
    if update_index != 1 || end_index <= update_index + 1 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "patch is missing its update hunks",
        ));
    }
    let mut output = source.split('\n').map(str::to_owned).collect::<Vec<_>>();
    let mut cursor = 0usize;
    let mut hunk_start = None;
    let mut hunk_lines = Vec::new();
    let mut hunk_count = 0usize;
    let mut apply_hunk = |start: Option<usize>, hunk_lines: &mut Vec<&str>| -> io::Result<()> {
        if hunk_lines.is_empty() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "patch hunk is empty",
            ));
        }
        let mut old = Vec::new();
        let mut replacement = Vec::new();
        for line in hunk_lines.drain(..) {
            let (kind, text) = line.split_at(1);
            match kind {
                " " => {
                    old.push(text.to_owned());
                    replacement.push(text.to_owned());
                }
                "-" => old.push(text.to_owned()),
                "+" => replacement.push(text.to_owned()),
                _ => {
                    return Err(io::Error::new(
                        io::ErrorKind::InvalidInput,
                        "invalid patch hunk line",
                    ))
                }
            }
        }
        let position = if old.is_empty() {
            start.unwrap_or(cursor)
        } else if let Some(start) = start {
            let position = start.saturating_sub(1);
            if output
                .get(position..position.saturating_add(old.len()))
                .is_some_and(|candidate| candidate == old.as_slice())
            {
                position
            } else {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidInput,
                    "patch source context does not match",
                ));
            }
        } else {
            output
                .windows(old.len())
                .position(|candidate| candidate == old.as_slice())
                .ok_or_else(|| {
                    io::Error::new(
                        io::ErrorKind::InvalidInput,
                        "patch source context does not match",
                    )
                })?
        };
        if position > output.len() || position.saturating_add(old.len()) > output.len() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "patch hunk position is outside source",
            ));
        }
        output.splice(position..position + old.len(), replacement);
        cursor = position.saturating_add(1);
        Ok(())
    };
    for line in &lines[update_index + 1..end_index] {
        if line.starts_with("@@") {
            if hunk_start.is_some() {
                apply_hunk(hunk_start, &mut hunk_lines)?;
                hunk_count = hunk_count.saturating_add(1);
            }
            hunk_start = Some(parse_hunk_start(line)?);
            continue;
        }
        if hunk_start.is_none()
            || line.is_empty()
            || !matches!(line.as_bytes()[0], b' ' | b'+' | b'-')
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid patch hunk",
            ));
        }
        hunk_lines.push(*line);
    }
    if hunk_start.is_some() {
        apply_hunk(hunk_start, &mut hunk_lines)?;
        hunk_count = hunk_count.saturating_add(1);
    }
    let output_bytes = output.iter().map(String::len).sum::<usize>();
    if hunk_count == 0 || output_bytes > MAX_PATCH_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "patch has no bounded hunks",
        ));
    }
    Ok(output.join("\n"))
}

fn parse_hunk_start(header: &str) -> io::Result<usize> {
    let Some(rest) = header.strip_prefix("@@") else {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid patch hunk",
        ));
    };
    let Some(rest) = rest.strip_suffix("@@") else {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid patch hunk",
        ));
    };
    let Some(old) = rest.split_whitespace().find(|part| part.starts_with('-')) else {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid patch hunk",
        ));
    };
    let start = old
        .trim_start_matches('-')
        .split(',')
        .next()
        .and_then(|value| value.parse::<usize>().ok())
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "invalid patch hunk"))?;
    Ok(start)
}

fn provider_resume_from_record(
    record: &codinal_storage::ApprovalRecord,
) -> io::Result<Option<ProviderTurnResume>> {
    let request: serde_json::Value = serde_json::from_str(&record.request)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid durable approval"))?;
    let Some(resume) = request.get("resume") else {
        return Ok(None);
    };
    let resume: ProviderTurnResume = serde_json::from_value(resume.clone())
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid provider resume"))?;
    resume.profile()?;
    if resume.input.is_empty()
        || resume.input.len() > 1024 * 1024
        || resume.input.chars().any(|character| character == '\0')
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "invalid provider resume input",
        ));
    }
    Ok(Some(resume))
}

fn fail_provider_resume_budget(config: &RuntimeConfig, record: &codinal_storage::ApprovalRecord) {
    let Some(store) = config.runtime_store.as_ref() else {
        return;
    };
    let Ok(Some(resume)) = provider_resume_from_record(record) else {
        return;
    };
    if let Some(reservation_id) = resume.budget_reservation_id.as_deref() {
        let _ = store.reconcile_budget(reservation_id, None, "failed");
    }
}

fn provider_resume_context(
    config: &RuntimeConfig,
    records: &[codinal_storage::ApprovalRecord],
    resume: &ProviderTurnResume,
) -> io::Result<Vec<serde_json::Value>> {
    let mut applied_by_tool_call = BTreeMap::new();
    for record in records.iter().filter(|record| record.state == "applied") {
        let request: serde_json::Value = serde_json::from_str(&record.request)
            .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid durable approval"))?;
        let tool_call_id = request
            .get("tool_call_id")
            .and_then(serde_json::Value::as_str)
            .filter(|value| !value.is_empty())
            .ok_or_else(|| {
                io::Error::new(
                    io::ErrorKind::InvalidData,
                    "durable tool call id is missing",
                )
            })?;
        applied_by_tool_call.insert(tool_call_id.to_owned(), record);
    }
    if resume.tool_calls.is_empty()
        || resume
            .tool_calls
            .iter()
            .any(|call| call.name != "apply_patch")
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "provider resume contains an unsupported tool",
        ));
    }
    let assistant_turn = AssistantTurn {
        text: resume.assistant_text.clone(),
        tool_calls: resume
            .tool_calls
            .iter()
            .map(|call| ToolCall {
                id: call.id.clone(),
                name: call.name.clone(),
                arguments: call.arguments.clone(),
            })
            .collect(),
        finish_reason: Some("tool_calls".to_owned()),
        usage: None,
    };
    let mut context_messages = resume.context_messages.clone();
    context_messages.push(provider_assistant_tool_message(&assistant_turn)?);
    for call in &resume.tool_calls {
        let record = applied_by_tool_call.get(&call.id).ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "provider resume is missing an applied tool result",
            )
        })?;
        let mutation = apply_approved_mutation(config, record)?;
        let content = serde_json::to_string(&serde_json::json!({
            "ok": true,
            "mutation": mutation,
        }))
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        if content.len() > MAX_TOOL_RESULT_BYTES {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "approved tool result exceeds limit",
            ));
        }
        context_messages.push(serde_json::json!({
            "role": "tool",
            "tool_call_id": call.id,
            "content": content,
        }));
    }
    Ok(context_messages)
}

fn apply_approved_mutation(
    config: &RuntimeConfig,
    record: &codinal_storage::ApprovalRecord,
) -> io::Result<serde_json::Value> {
    let request: serde_json::Value = serde_json::from_str(&record.request)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid durable approval"))?;
    if request.get("tool_name").and_then(serde_json::Value::as_str) != Some("apply_patch") {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "only apply_patch is enabled in this execution slice",
        ));
    }
    let arguments = request.get("arguments").ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            "durable patch arguments are missing",
        )
    })?;
    let (path, patch) = patch_arguments(arguments)?;
    let workspace = session_workspace(config.data_dir(), &record.session_id)?;
    let (canonical_workspace, target) = resolve_workspace_target(&workspace, path)?;
    let canonical_workspace_string = canonical_workspace.to_string_lossy().into_owned();
    if request
        .get("workspace_root")
        .and_then(serde_json::Value::as_str)
        != Some(canonical_workspace_string.as_str())
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "workspace root changed since approval",
        ));
    }
    let expected_source = request
        .get("source_hash")
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "source hash is missing"))?;
    let expected_patch = request
        .get("patch_hash")
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "patch hash is missing"))?;
    if sha256_hex(patch.as_bytes()) != expected_patch {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "patch changed after approval",
        ));
    }
    let source = fs::read(&target)?;
    let mutation_id = format!("mutation-{}", record.approval_id);
    let store = config
        .runtime_store
        .as_ref()
        .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "runtime store unavailable"))?;
    if let Some(existing) = store.read_mutation(&mutation_id)? {
        let current_digest = sha256_hex(&source);
        if existing.turn_id != record.turn_id || existing.path != path {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "mutation journal identity changed",
            ));
        }
        if matches!(existing.state.as_str(), "applying" | "committed")
            && current_digest == existing.digest
        {
            store.put_mutation(&codinal_storage::MutationJournalRecord {
                mutation_id: mutation_id.clone(),
                turn_id: record.turn_id.clone(),
                path: path.to_owned(),
                digest: existing.digest.clone(),
                state: "committed".to_owned(),
            })?;
            return Ok(serde_json::json!({
                "path": path,
                "digest": existing.digest,
                "source_hash": expected_source,
                "patch_hash": expected_patch,
                "idempotent_replay": true,
            }));
        }
        if existing.state == "committed" {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "committed mutation target changed",
            ));
        }
    }
    if sha256_hex(&source) != expected_source {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "source changed after approval",
        ));
    }
    let source_text = String::from_utf8(source.clone()).map_err(|_| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            "apply_patch source is not UTF-8",
        )
    })?;
    let updated = apply_single_file_patch(path, patch, &source_text)?;
    let mutation_digest = sha256_hex(updated.as_bytes());
    store.put_mutation(&codinal_storage::MutationJournalRecord {
        mutation_id: mutation_id.clone(),
        turn_id: record.turn_id.clone(),
        path: path.to_owned(),
        digest: mutation_digest.clone(),
        state: "applying".to_owned(),
    })?;
    let temporary = target.with_file_name(format!(".codinal-{mutation_id}.tmp"));
    if let Ok(metadata) = fs::symlink_metadata(&temporary) {
        if metadata.file_type().is_symlink() || !metadata.is_file() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "mutation temporary path is unsafe",
            ));
        }
        fs::remove_file(&temporary)?;
    }
    let result = (|| -> io::Result<()> {
        let mut file = OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&temporary)?;
        file.write_all(updated.as_bytes())?;
        file.sync_all()?;
        fs::set_permissions(&temporary, fs::metadata(&target)?.permissions())?;
        let current = fs::read(&target)?;
        if sha256_hex(&current) != expected_source {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "source changed before commit",
            ));
        }
        fs::rename(&temporary, &target)?;
        File::open(&canonical_workspace)?.sync_all()?;
        Ok(())
    })();
    if let Err(error) = result {
        let _ = fs::remove_file(&temporary);
        let _ = store.put_mutation(&codinal_storage::MutationJournalRecord {
            mutation_id: mutation_id.clone(),
            turn_id: record.turn_id.clone(),
            path: path.to_owned(),
            digest: mutation_digest.clone(),
            state: "failed".to_owned(),
        });
        return Err(error);
    }
    store.put_mutation(&codinal_storage::MutationJournalRecord {
        mutation_id,
        turn_id: record.turn_id.clone(),
        path: path.to_owned(),
        digest: mutation_digest.clone(),
        state: "committed".to_owned(),
    })?;
    Ok(serde_json::json!({
        "path": path,
        "digest": mutation_digest,
        "source_hash": expected_source,
        "patch_hash": expected_patch,
    }))
}

pub fn validate_session_token(token: &str) -> io::Result<()> {
    let valid = token.len() >= MIN_TOKEN_LENGTH
        && token
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'));
    if valid {
        Ok(())
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "session token must be URL-safe and at least 32 characters",
        ))
    }
}

fn data_directory_identity(data_dir: &Path) -> io::Result<String> {
    let metadata = fs::metadata(data_dir)?;
    Ok(format!("{}:{}", metadata.dev(), metadata.ino()))
}

/// Serve one connection. This narrow lifecycle seam allows a future host to
/// own graceful shutdown without exposing the bearer token to a UI client.
pub fn serve_one(listener: &TcpListener, config: &RuntimeConfig) -> io::Result<()> {
    let (stream, peer) = listener.accept()?;
    if !peer.ip().is_loopback() {
        return Ok(());
    }
    serve_stream(stream, config)
}

struct ActiveConnection(Arc<AtomicUsize>);

impl Drop for ActiveConnection {
    fn drop(&mut self) {
        self.0.fetch_sub(1, Ordering::AcqRel);
    }
}

fn serve_connections(config: &RuntimeConfig) -> io::Result<()> {
    let listener = config.bind()?;
    while !config.is_shutdown_requested() {
        match listener.accept() {
            Ok((stream, peer)) if peer.ip().is_loopback() => {
                if config.is_shutdown_requested() {
                    continue;
                }
                if !reserve_connection(&config.active_connections) {
                    let mut stream = stream;
                    let _ = write_response(
                        &mut stream,
                        "503 Service Unavailable",
                        "{\"detail\":\"connection capacity exhausted\",\"reason_code\":\"connection_capacity\"}",
                        None,
                    );
                    continue;
                }
                let config = config.clone();
                let active = Arc::clone(&config.active_connections);
                std::thread::Builder::new()
                    .name("codinal-runtime-connection".to_owned())
                    .spawn(move || {
                        let _active = ActiveConnection(active);
                        let _ = serve_stream(stream, &config);
                    })
                    .map_err(|error| io::Error::other(format!("connection worker: {error}")))?;
            }
            Ok((_stream, _peer)) => {}
            Err(error) => return Err(error),
        }
    }
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(3);
    while config.active_connections.load(Ordering::Acquire) != 0
        && std::time::Instant::now() < deadline
    {
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
    Ok(())
}

fn reserve_connection(active: &AtomicUsize) -> bool {
    let mut current = active.load(Ordering::Acquire);
    loop {
        if current >= MAX_ACTIVE_CONNECTIONS {
            return false;
        }
        match active.compare_exchange_weak(
            current,
            current + 1,
            Ordering::AcqRel,
            Ordering::Acquire,
        ) {
            Ok(_) => return true,
            Err(observed) => current = observed,
        }
    }
}

fn serve_stream(mut stream: TcpStream, config: &RuntimeConfig) -> io::Result<()> {
    stream.set_read_timeout(Some(Duration::from_secs(2)))?;
    stream.set_write_timeout(Some(Duration::from_secs(2)))?;
    if looks_like_websocket_request(&stream)? {
        return serve_websocket(stream, config);
    }
    let request = read_headers(&mut stream)?;
    let authenticated = request.headers.iter().any(|(name, value)| {
        name == "authorization" && valid_bearer(value.as_str(), config.token.as_bytes())
    });
    if !authenticated {
        return write_response(
            &mut stream,
            "401 Unauthorized",
            "{\"detail\":\"unauthorized\"}",
            Some("Bearer"),
        );
    }
    if serve_operation_route(&mut stream, config, &request)? {
        return Ok(());
    }
    if request.method == "GET" && request.path == "/v1/version" {
        let version = std::env::var("CODINAL_VERSION")
            .ok()
            .filter(|value| !value.is_empty())
            .unwrap_or_else(|| env!("CARGO_PKG_VERSION").to_owned());
        return write_json_response(
            &mut stream,
            "200 OK",
            &serde_json::json!({ "version": version }),
        );
    }
    if request.method == "GET" && request.path == "/v1/config" {
        return write_json_response(
            &mut stream,
            "200 OK",
            &serde_json::json!({
                "runtime": "rust-native",
                "version": std::env::var("CODINAL_VERSION")
                    .ok()
                    .filter(|value| !value.is_empty())
                    .unwrap_or_else(|| env!("CARGO_PKG_VERSION").to_owned()),
            }),
        );
    }
    if request.method == "GET" && request.path == "/v1/security/status" {
        return write_json_response(
            &mut stream,
            "200 OK",
            &serde_json::json!({
                "available": false,
                "reason": "Security scanning is unavailable."
            }),
        );
    }
    if request.method == "GET" && request.path == "/v1/secrets/providers" {
        let provider_statuses = config
            .provider_secrets
            .read()
            .map_err(|_| io::Error::other("provider secret lock poisoned"))?
            .status();
        return write_json_response(&mut stream, "200 OK", &provider_statuses);
    }
    if request.method == "GET" && request.path == "/v1/health" {
        return write_json_response(&mut stream, "200 OK", &config.health_document());
    }
    if request.method == "POST" && request.path == "/v1/capabilities/probe" {
        return serve_capability_probe(&mut stream, config, &request.body);
    }
    if request.method == "GET" && request.path == "/v1/harness/inventory" {
        return match config.harness_inventory() {
            Ok(Some(inventory)) => write_json_response(&mut stream, "200 OK", &inventory),
            Ok(None) => write_json_response(
                &mut stream,
                "503 Service Unavailable",
                &serde_json::json!({
                    "detail": "harness roots are not configured",
                    "reason_code": "harness_roots_not_configured",
                }),
            ),
            Err(error) => write_json_response(
                &mut stream,
                "500 Internal Server Error",
                &serde_json::json!({
                    "detail": "harness inventory unavailable",
                    "reason": error.to_string(),
                }),
            ),
        };
    }
    if request.method == "GET" {
        if let Some(operation_id) = request.path.strip_prefix("/v1/tools/") {
            if let Some(operation_id) = operation_id.strip_suffix("/receipt") {
                let Some(gateway) = config.tool_gateway.as_ref() else {
                    return write_json_response(
                        &mut stream,
                        "503 Service Unavailable",
                        &serde_json::json!({
                            "detail": "tool gateway unavailable",
                            "reason_code": "workspace_not_configured",
                        }),
                    );
                };
                return match gateway.receipt(operation_id)? {
                    Some(receipt) => write_json_response(&mut stream, "200 OK", &receipt),
                    None => write_response(
                        &mut stream,
                        "404 Not Found",
                        "{\"detail\":\"tool receipt not found\"}",
                        None,
                    ),
                };
            }
        }
    }
    if request.method == "GET"
        && (request.path == "/v1/events" || request.path.starts_with("/v1/events?"))
    {
        let query = request.path.strip_prefix("/v1/events").unwrap_or_default();
        let (cursor, limit) = match parse_event_query(query) {
            Ok(values) => values,
            Err(()) => {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid event cursor\"}",
                    None,
                );
            }
        };
        let Some(store) = config.runtime_store.as_ref() else {
            return write_json_response(
                &mut stream,
                "503 Service Unavailable",
                &serde_json::json!({
                    "detail": "event store unavailable",
                    "reason_code": config.readiness.reason_code,
                }),
            );
        };
        let replay = store.replay_events(cursor.as_deref(), limit)?;
        let status = if replay.cursor_expired {
            "409 Conflict"
        } else {
            "200 OK"
        };
        return write_json_response(&mut stream, status, &replay);
    }
    if request.method == "POST" && request.path == "/v1/activity/read" {
        if let Err(error) = config.set_activity_read(true) {
            return write_json_response(
                &mut stream,
                "500 Internal Server Error",
                &serde_json::json!({"detail": error.to_string()}),
            );
        }
        return write_json_response(&mut stream, "200 OK", &serde_json::json!({"ok": true}));
    }
    if config.readiness.is_read_only() && request.method != "GET" {
        return write_json_response(
            &mut stream,
            "423 Locked",
            &serde_json::json!({
                "detail": "runtime is read-only",
                "action": "mutation",
                "reason_code": config.readiness.reason_code,
            }),
        );
    }
    if request.method == "POST" && request.path == "/v1/sessions" {
        return create_owned_session(&mut stream, config, &request.body);
    }
    if request.method == "POST" && request.path == "/v1/projects" {
        return create_owned_project(&mut stream, config, &request.body);
    }
    if request.method == "PATCH" {
        if let Some(session_id) = parse_session_item_path(&request.path) {
            return update_owned_session(&mut stream, config, session_id, &request.body);
        }
    }
    if request.method == "DELETE" {
        if let Some(session_id) = parse_session_item_path(&request.path) {
            return delete_owned_session(&mut stream, config, session_id);
        }
    }
    if request.method == "PATCH" {
        if let Some(project_id) = request.path.strip_prefix("/v1/projects/") {
            if !project_id.is_empty() && !project_id.contains('/') {
                return replace_owned_project(&mut stream, config, project_id, &request.body);
            }
        }
    }
    if request.method == "DELETE" {
        if let Some(project_id) = request.path.strip_prefix("/v1/projects/") {
            if !project_id.is_empty() && !project_id.contains('/') {
                return remove_owned_project(&mut stream, config, project_id);
            }
        }
    }
    if request.method == "POST" || request.method == "DELETE" {
        if let Some(path) = request.path.strip_prefix("/v1/projects/") {
            if let Some(project_id) = path.strip_suffix("/pin") {
                if request.method == "POST" && !project_id.is_empty() && !project_id.contains('/') {
                    return set_owned_project_pinned(
                        &mut stream,
                        config,
                        project_id,
                        &request.body,
                    );
                }
            }
            if let Some((project_id, session_id)) = path.split_once("/sessions/") {
                if !project_id.is_empty()
                    && !session_id.is_empty()
                    && !project_id.contains('/')
                    && !session_id.contains('/')
                {
                    return if request.method == "POST" {
                        assign_owned_session(&mut stream, config, project_id, session_id)
                    } else {
                        remove_owned_session(&mut stream, config, project_id, session_id)
                    };
                }
            }
        }
    }
    if request.method == "POST" {
        if let Some(session_id) = parse_source_collection_path(&request.path) {
            return attach_owned_source(&mut stream, config, session_id, &request.body);
        }
        if let Some((session_id, attachment_id)) = parse_source_retry_path(&request.path) {
            return retry_owned_source(&mut stream, config, session_id, attachment_id);
        }
    }
    if request.method == "DELETE" {
        if let Some((session_id, attachment_id)) = parse_source_item_path(&request.path) {
            return remove_owned_source(&mut stream, config, session_id, attachment_id);
        }
    }
    if request.method == "POST" && request.path.starts_with("/v1/tools/") {
        let Some(gateway) = config.tool_gateway.as_ref() else {
            return write_json_response(
                &mut stream,
                "503 Service Unavailable",
                &serde_json::json!({
                    "detail": "tool gateway unavailable",
                    "reason_code": "workspace_not_configured",
                }),
            );
        };
        if request.path == "/v1/tools/approve" {
            let payload: ToolApprovalRequest = match serde_json::from_slice(&request.body) {
                Ok(payload) => payload,
                Err(_) => {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid tool approval\"}",
                        None,
                    );
                }
            };
            if gateway.approve_once(&payload.approval_id) {
                return write_json_response(
                    &mut stream,
                    "200 OK",
                    &serde_json::json!({"ok": true, "approval_id": payload.approval_id}),
                );
            }
            return write_response(
                &mut stream,
                "409 Conflict",
                "{\"detail\":\"approval is invalid or already consumed\"}",
                None,
            );
        }
        if request.path == "/v1/tools/interrupt" {
            let payload: ToolInterruptRequest = match serde_json::from_slice(&request.body) {
                Ok(payload) => payload,
                Err(_) => {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid tool interrupt\"}",
                        None,
                    );
                }
            };
            return write_json_response(
                &mut stream,
                "200 OK",
                &serde_json::json!({"ok": gateway.interrupt(&payload.operation_id)}),
            );
        }
        if request.path == "/v1/tools/shell" {
            let payload: ShellToolRequest = match serde_json::from_slice(&request.body) {
                Ok(payload) => payload,
                Err(_) => {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid shell tool request\"}",
                        None,
                    );
                }
            };
            let result = gateway.execute_shell(codinal_tools::ShellRequest {
                operation_id: payload.operation_id,
                cwd: PathBuf::from(payload.cwd),
                program: payload.program,
                args: payload.args,
                approval_id: payload.approval_id,
                timeout_ms: payload.timeout_ms.unwrap_or(30_000),
            });
            return match result {
                Ok(execution) => {
                    write_json_response(&mut stream, "200 OK", &tool_execution_value(execution))
                }
                Err(error) => write_json_response(
                    &mut stream,
                    tool_error_status(&error),
                    &serde_json::json!({"detail": error.to_string()}),
                ),
            };
        }
        if request.path == "/v1/tools/git" {
            let payload: GitToolRequest = match serde_json::from_slice(&request.body) {
                Ok(payload) => payload,
                Err(_) => {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid git tool request\"}",
                        None,
                    );
                }
            };
            let operation = match payload.operation.as_str() {
                "status" => Ok(codinal_tools::GitOperation::Status),
                "diff" => Ok(codinal_tools::GitOperation::Diff {
                    path: payload.path.map(PathBuf::from),
                }),
                "create_worktree" => payload
                    .path
                    .zip(payload.revision)
                    .map(
                        |(path, revision)| codinal_tools::GitOperation::CreateWorktree {
                            path: PathBuf::from(path),
                            revision,
                        },
                    )
                    .ok_or_else(|| {
                        io::Error::new(
                            io::ErrorKind::InvalidInput,
                            "worktree path and revision are required",
                        )
                    }),
                "remove_worktree" => payload
                    .path
                    .map(|path| codinal_tools::GitOperation::RemoveWorktree {
                        path: PathBuf::from(path),
                        force: payload.force,
                    })
                    .ok_or_else(|| {
                        io::Error::new(io::ErrorKind::InvalidInput, "worktree path is required")
                    }),
                _ => Err(io::Error::new(
                    io::ErrorKind::InvalidInput,
                    "unsupported git operation",
                )),
            };
            let operation = match operation {
                Ok(operation) => operation,
                Err(error) => {
                    return write_json_response(
                        &mut stream,
                        tool_error_status(&error),
                        &serde_json::json!({"detail": error.to_string()}),
                    );
                }
            };
            let result = gateway.execute_git(codinal_tools::GitRequest {
                operation_id: payload.operation_id,
                repo: PathBuf::from(payload.repo),
                operation,
                approval_id: payload.approval_id,
                timeout_ms: payload.timeout_ms.unwrap_or(30_000),
            });
            return match result {
                Ok(execution) => {
                    write_json_response(&mut stream, "200 OK", &tool_execution_value(execution))
                }
                Err(error) => write_json_response(
                    &mut stream,
                    tool_error_status(&error),
                    &serde_json::json!({"detail": error.to_string()}),
                ),
            };
        }
        if request.path == "/v1/tools/mcp" {
            let payload: McpToolRequest = match serde_json::from_slice(&request.body) {
                Ok(payload) => payload,
                Err(_) => {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid MCP tool request\"}",
                        None,
                    );
                }
            };
            let result = gateway.execute_mcp(codinal_tools::McpRequest {
                operation_id: payload.operation_id,
                server_id: payload.server_id,
                program: payload.program,
                args: payload.args,
                method: payload.method,
                params: payload.params,
                approval_id: payload.approval_id,
                timeout_ms: payload.timeout_ms.unwrap_or(30_000),
            });
            return match result {
                Ok(execution) => {
                    write_json_response(&mut stream, "200 OK", &tool_execution_value(execution))
                }
                Err(error) => write_json_response(
                    &mut stream,
                    tool_error_status(&error),
                    &serde_json::json!({"detail": error.to_string()}),
                ),
            };
        }
    }
    if request.method == "GET" {
        if let Some(session_id) = parse_source_collection_path(&request.path) {
            return list_owned_sources(&mut stream, config, session_id);
        }
        if let Some((session_id, attachment_id)) = parse_source_item_path(&request.path) {
            return read_owned_source(&mut stream, config, session_id, attachment_id);
        }
        if let Some((session_id, attachment_id)) = parse_source_preview_path(&request.path) {
            return preview_owned_source(&mut stream, config, session_id, attachment_id);
        }
        if request.path == "/v1/activity" {
            return list_activity(&mut stream, config);
        }
        if request.path == "/v1/projects" {
            if !config.data_dir().join("codinal.db").is_file() {
                return write_json_response(
                    &mut stream,
                    "200 OK",
                    &Vec::<codinal_storage::ProjectSummary>::new(),
                );
            }
            return match codinal_storage::read_projects(config.data_dir()) {
                Ok(projects) => write_json_response(&mut stream, "200 OK", &projects),
                Err(_) => write_response(
                    &mut stream,
                    "500 Internal Server Error",
                    "{\"detail\":\"project storage unavailable\"}",
                    None,
                ),
            };
        }
        if let Some(query) = request.path.strip_prefix("/v1/sessions/search") {
            let (needle, limit) = match parse_session_search_query(query) {
                Ok((needle, limit)) => (needle, limit),
                Err(()) => {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid session search\"}",
                        None,
                    );
                }
            };
            let needle = needle.to_lowercase();
            if !config.data_dir().join("codinal.db").is_file() {
                return write_json_response(
                    &mut stream,
                    "200 OK",
                    &Vec::<serde_json::Value>::new(),
                );
            }
            let mut matches = match codinal_storage::read_session_summaries(config.data_dir(), None)
            {
                Ok(all) => all
                    .into_iter()
                    .filter(|session| {
                        session.session_id.to_lowercase().contains(&needle)
                            || session.title.to_lowercase().contains(&needle)
                            || session.workspace.to_lowercase().contains(&needle)
                    })
                    .collect::<Vec<_>>(),
                Err(_) => {
                    return write_response(
                        &mut stream,
                        "500 Internal Server Error",
                        "{\"detail\":\"session storage unavailable\"}",
                        None,
                    );
                }
            };
            matches.truncate(limit);
            return write_json_response(&mut stream, "200 OK", &matches);
        }
        if let Some(query) = request.path.strip_prefix("/v1/sessions") {
            if query.is_empty() || query.starts_with('?') {
                if !config.data_dir().join("codinal.db").is_file() {
                    return write_json_response(
                        &mut stream,
                        "200 OK",
                        &Vec::<codinal_storage::SessionSummary>::new(),
                    );
                }
                let workspace = match parse_workspace_query(query) {
                    Ok(workspace) => workspace,
                    Err(()) => {
                        return write_response(
                            &mut stream,
                            "400 Bad Request",
                            "{\"detail\":\"invalid workspace\"}",
                            None,
                        );
                    }
                };
                return match codinal_storage::read_session_summaries(
                    config.data_dir(),
                    workspace.as_deref(),
                ) {
                    Ok(sessions) => write_json_response(&mut stream, "200 OK", &sessions),
                    Err(_) => write_response(
                        &mut stream,
                        "500 Internal Server Error",
                        "{\"detail\":\"session storage unavailable\"}",
                        None,
                    ),
                };
            }
        }
    }
    if request.method == "GET" {
        if let Some(session_id) = request
            .path
            .strip_prefix("/v1/sessions/")
            .and_then(|path| path.strip_suffix("/approvals"))
        {
            if !codinal_storage::public_session_exists(config.data_dir(), session_id)? {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid session id\"}",
                    None,
                );
            }
            let durable_approvals = config
                .runtime_store
                .as_ref()
                .map(|store| store.read_pending_approvals(session_id))
                .transpose()?
                .unwrap_or_default();
            let mut broker = config
                .approval_broker
                .lock()
                .map_err(|_| io::Error::other("approval broker lock poisoned"))?;
            let mut approvals = Vec::new();
            for approval in broker.pending(session_id) {
                let Some(record) = durable_approvals
                    .iter()
                    .find(|record| record.approval_id == approval.approval_id)
                else {
                    approvals.push(approval);
                    continue;
                };
                if expire_durable_approval(config, &mut broker, record)? {
                    continue;
                }
                approvals.push(approval);
            }
            return write_json_response(&mut stream, "200 OK", &approvals);
        }
        if let Some(session_id) = request
            .path
            .strip_prefix("/v1/sessions/")
            .and_then(|path| path.strip_suffix("/messages"))
        {
            return match codinal_storage::read_session_messages(config.data_dir(), session_id) {
                Ok(messages) => write_json_response(&mut stream, "200 OK", &messages),
                Err(error) if error.kind() == io::ErrorKind::InvalidInput => write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid session id\"}",
                    None,
                ),
                Err(_) => write_response(
                    &mut stream,
                    "500 Internal Server Error",
                    "{\"detail\":\"session storage unavailable\"}",
                    None,
                ),
            };
        }
        if let Some(session_id) = request
            .path
            .strip_prefix("/v1/sessions/")
            .and_then(|path| path.strip_suffix("/turns"))
        {
            let receipts =
                match codinal_storage::read_session_turn_receipts(config.data_dir(), session_id) {
                    Ok(receipts) => receipts,
                    Err(error) if error.kind() == io::ErrorKind::InvalidInput => {
                        return write_response(
                            &mut stream,
                            "400 Bad Request",
                            "{\"detail\":\"invalid session id\"}",
                            None,
                        );
                    }
                    Err(_) => {
                        return write_response(
                            &mut stream,
                            "500 Internal Server Error",
                            "{\"detail\":\"session storage unavailable\"}",
                            None,
                        );
                    }
                };
            let mut response = serde_json::to_value(receipts)
                .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
            if let Some(store) = config.runtime_store.as_ref() {
                let runtime_receipts = store.read_receipts(session_id)?;
                if let Some(items) = response.as_array_mut() {
                    items.extend(
                        runtime_receipts
                            .into_iter()
                            .map(serde_json::to_value)
                            .collect::<Result<Vec<_>, _>>()
                            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?,
                    );
                }
            }
            return write_json_response(&mut stream, "200 OK", &response);
        }
        if let Some(session_id) = request
            .path
            .strip_prefix("/v1/sessions/")
            .and_then(|path| path.strip_suffix("/goals"))
        {
            return match codinal_storage::read_session_goals(config.data_dir(), session_id) {
                Ok(goals) => write_json_response(&mut stream, "200 OK", &goals),
                Err(error) if error.kind() == io::ErrorKind::InvalidInput => write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid session id\"}",
                    None,
                ),
                Err(_) => write_response(
                    &mut stream,
                    "500 Internal Server Error",
                    "{\"detail\":\"session storage unavailable\"}",
                    None,
                ),
            };
        }
        if let Some(session_id) = request
            .path
            .strip_prefix("/v1/sessions/")
            .and_then(|path| path.strip_suffix("/plans"))
        {
            return match codinal_storage::read_session_plan_artifacts(config.data_dir(), session_id)
            {
                Ok(plan_artifacts) => write_json_response(&mut stream, "200 OK", &plan_artifacts),
                Err(error) if error.kind() == io::ErrorKind::InvalidInput => write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid session id\"}",
                    None,
                ),
                Err(_) => write_response(
                    &mut stream,
                    "500 Internal Server Error",
                    "{\"detail\":\"session storage unavailable\"}",
                    None,
                ),
            };
        }
        if let Some(session_id) = request
            .path
            .strip_prefix("/v1/sessions/")
            .and_then(|path| path.strip_suffix("/plan-builds"))
        {
            return match codinal_storage::read_session_plan_builds(config.data_dir(), session_id) {
                Ok(plan_builds) => write_json_response(&mut stream, "200 OK", &plan_builds),
                Err(error) if error.kind() == io::ErrorKind::InvalidInput => write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid session id\"}",
                    None,
                ),
                Err(_) => write_response(
                    &mut stream,
                    "500 Internal Server Error",
                    "{\"detail\":\"session storage unavailable\"}",
                    None,
                ),
            };
        }
        if let Some(session_id) = request
            .path
            .strip_prefix("/v1/sessions/")
            .and_then(|path| path.strip_suffix("/interactions"))
        {
            if !codinal_storage::public_session_exists(config.data_dir(), session_id)? {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid session id\"}",
                    None,
                );
            }
            return write_json_response(&mut stream, "200 OK", &serde_json::json!([]));
        }
        if let Some((session_id, tail)) = request
            .path
            .strip_prefix("/v1/sessions/")
            .and_then(|path| path.split_once('/'))
        {
            let segments: Vec<&str> = tail.split('/').collect();
            if segments == ["checkpoints"]
                || segments == ["project", "index"]
                || segments == ["project", "search"]
                || segments == ["workspace", "files"]
                || segments == ["project", "open"]
                || segments == ["roots"]
                || segments == ["tree"]
                || segments == ["workers"]
                || segments == ["mcp", "servers"]
                || segments == ["preview", "evidence"]
                || segments == ["export.md"]
                || segments == ["github", "checks"]
                || segments == ["github", "pr"]
                || (segments.len() == 2 && segments.first() == Some(&"git"))
            {
                if !codinal_storage::public_session_exists(config.data_dir(), session_id)? {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid session id\"}",
                        None,
                    );
                }
                let detail = if segments == ["workspace", "files"] {
                    "{\"detail\":\"workspace operations are not implemented in rust runtime\"}"
                } else if segments == ["roots"] {
                    "{\"detail\":\"roots operations are not implemented in rust runtime\"}"
                } else if segments == ["tree"] {
                    "{\"detail\":\"tree operations are not implemented in rust runtime\"}"
                } else if segments == ["workers"] {
                    "{\"detail\":\"worker operations are not implemented in rust runtime\"}"
                } else if segments == ["export.md"] {
                    "{\"detail\":\"export operations are not implemented in rust runtime\"}"
                } else if segments.first() == Some(&"github") {
                    "{\"detail\":\"github operations are not implemented in rust runtime\"}"
                } else if segments.first() == Some(&"mcp") {
                    "{\"detail\":\"mcp operations are not implemented in rust runtime\"}"
                } else if segments.first() == Some(&"preview") {
                    "{\"detail\":\"preview operations are not implemented in rust runtime\"}"
                } else if segments.first() == Some(&"project") {
                    "{\"detail\":\"project operations are not implemented in rust runtime\"}"
                } else {
                    "{\"detail\":\"checkpoint operations are not implemented in rust runtime\"}"
                };
                if segments.len() == 2 && segments.first() == Some(&"git") {
                    return write_response(
                        &mut stream,
                        "501 Not Implemented",
                        "{\"detail\":\"git operations are not implemented in rust runtime\"}",
                        None,
                    );
                }
                return write_response(&mut stream, "501 Not Implemented", detail, None);
            }
            if segments.len() == 3
                && segments.first() == Some(&"checkpoints")
                && segments[2] == "restore"
                && !segments[1].is_empty()
            {
                if !codinal_storage::public_session_exists(config.data_dir(), session_id)? {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid session id\"}",
                        None,
                    );
                }
                return write_response(
                    &mut stream,
                    "501 Not Implemented",
                    "{\"detail\":\"checkpoint operations are not implemented in rust runtime\"}",
                    None,
                );
            }
        }
        if let Some(session_id) = request.path.strip_prefix("/v1/sessions/").and_then(|path| {
            path.strip_suffix("/artifacts")
                .or_else(|| path.strip_suffix("/artifacts/read"))
        }) {
            if !codinal_storage::public_session_exists(config.data_dir(), session_id)? {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid session id\"}",
                    None,
                );
            }
            return write_response(
                &mut stream,
                "501 Not Implemented",
                "{\"detail\":\"artifact operations are not implemented in rust runtime\"}",
                None,
            );
        }
    }
    if request.method == "POST" {
        if let Some((session_id, tail)) = request
            .path
            .strip_prefix("/v1/sessions/")
            .and_then(|path| path.split_once('/'))
        {
            let segments: Vec<&str> = tail.split('/').collect();
            if segments == ["project", "index"]
                || segments == ["project", "open"]
                || (segments.len() == 2 && segments.first() == Some(&"git"))
                || segments == ["roots"]
                || segments == ["terminal", "run"]
                || segments == ["terminal", "interrupt"]
                || segments == ["workers"]
                || segments == ["mcp", "connect"]
                || segments == ["preview", "evidence"]
                || segments == ["preview", "verify"]
                || segments == ["preview", "verify-origin"]
                || segments == ["side-conversations"]
                || segments == ["complete"]
                || segments == ["context"]
                || segments == ["goals"]
                || segments == ["inline-edit"]
                || segments == ["interrupt"]
                || segments == ["plan-builds"]
                || segments == ["security", "scan"]
                || segments == ["turns"]
                || segments == ["github", "pr"]
                || segments == ["github", "cleanup"]
                || segments == ["github", "comment"]
                || segments == ["github", "merge"]
                || (segments.len() == 2
                    && segments.first() == Some(&"interactions")
                    && !segments[1].is_empty())
            {
                if !codinal_storage::public_session_exists(config.data_dir(), session_id)? {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid session id\"}",
                        None,
                    );
                }
                if segments == ["turns"] {
                    return serve_owned_turn(&mut stream, config, session_id, &request.body);
                }
                if segments == ["interrupt"] {
                    return interrupt_owned_turn(&mut stream, config, session_id, &request.body);
                }
                let detail = if segments.first() == Some(&"roots") {
                    "{\"detail\":\"roots operations are not implemented in rust runtime\"}"
                } else if segments.first() == Some(&"git") {
                    "{\"detail\":\"git operations are not implemented in rust runtime\"}"
                } else if segments.first() == Some(&"terminal") {
                    "{\"detail\":\"terminal operations are not implemented in rust runtime\"}"
                } else if segments.first() == Some(&"workers") {
                    "{\"detail\":\"worker operations are not implemented in rust runtime\"}"
                } else if segments.first() == Some(&"mcp") {
                    "{\"detail\":\"mcp operations are not implemented in rust runtime\"}"
                } else if segments.first() == Some(&"preview") {
                    "{\"detail\":\"preview operations are not implemented in rust runtime\"}"
                } else if segments.first() == Some(&"side-conversations") {
                    "{\"detail\":\"side-conversation operations are not implemented in rust runtime\"}"
                } else if segments.first() == Some(&"github") {
                    "{\"detail\":\"github operations are not implemented in rust runtime\"}"
                } else if segments.first() == Some(&"interactions") {
                    "{\"detail\":\"interaction operations are not implemented in rust runtime\"}"
                } else if segments.first() == Some(&"security") {
                    "{\"detail\":\"security scan operations are not implemented in rust runtime\"}"
                } else if segments.first() == Some(&"project") {
                    "{\"detail\":\"project operations are not implemented in rust runtime\"}"
                } else if segments == ["complete"] {
                    "{\"detail\":\"session complete is not implemented in rust runtime\"}"
                } else if segments == ["context"] {
                    "{\"detail\":\"session context is not implemented in rust runtime\"}"
                } else if segments == ["goals"] {
                    "{\"detail\":\"goal operations are not implemented in rust runtime\"}"
                } else if segments == ["inline-edit"] {
                    "{\"detail\":\"inline-edit operations are not implemented in rust runtime\"}"
                } else if segments == ["interrupt"] {
                    "{\"detail\":\"session interrupt is not implemented in rust runtime\"}"
                } else if segments == ["plan-builds"] {
                    "{\"detail\":\"plan-build operations are not implemented in rust runtime\"}"
                } else {
                    "{\"detail\":\"turn operations are not implemented in rust runtime\"}"
                };
                return write_response(&mut stream, "501 Not Implemented", detail, None);
            }
            if segments.len() == 3
                && segments.first() == Some(&"checkpoints")
                && segments[2] == "restore"
                && !segments[1].is_empty()
            {
                if !codinal_storage::public_session_exists(config.data_dir(), session_id)? {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid session id\"}",
                        None,
                    );
                }
                return write_response(
                    &mut stream,
                    "501 Not Implemented",
                    "{\"detail\":\"checkpoint operations are not implemented in rust runtime\"}",
                    None,
                );
            }
        }
        if let Some(session_id) = request.path.strip_prefix("/v1/sessions/").and_then(|path| {
            path.strip_suffix("/artifacts/write")
                .or_else(|| path.strip_suffix("/artifacts/reveal"))
        }) {
            if !codinal_storage::public_session_exists(config.data_dir(), session_id)? {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid session id\"}",
                    None,
                );
            }
            return write_response(
                &mut stream,
                "501 Not Implemented",
                "{\"detail\":\"artifact operations are not implemented in rust runtime\"}",
                None,
            );
        }
        if let Some(goal_id) = request.path.strip_prefix("/v1/goals/").and_then(|path| {
            path.strip_suffix("/continue")
                .or_else(|| path.strip_suffix("/evidence"))
                .or_else(|| path.strip_suffix("/audit"))
        }) {
            if !codinal_storage::public_session_exists(config.data_dir(), goal_id)? {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid goal id\"}",
                    None,
                );
            }
            return write_response(
                &mut stream,
                "501 Not Implemented",
                "{\"detail\":\"goal operations are not implemented in rust runtime\"}",
                None,
            );
        }
    }
    if request.method == "POST"
        && request
            .path
            .strip_prefix("/v1/sessions/")
            .is_some_and(|path| !path.is_empty() && !path.ends_with('/') && path.ends_with("/fork"))
    {
        return write_response(
            &mut stream,
            "501 Not Implemented",
            "{\"detail\":\"session fork is not implemented in rust runtime\"}",
            None,
        );
    }
    if request.method == "DELETE"
        && request
            .path
            .strip_prefix("/v1/sessions/")
            .is_some_and(|path| {
                let mut segments = path.split('/');
                matches!(segments.next(), Some(session_id) if !session_id.is_empty())
                    && matches!(segments.next(), Some("roots"))
                    && segments.next().is_none()
            })
    {
        if let Some(session_id) = request
            .path
            .strip_prefix("/v1/sessions/")
            .and_then(|path| path.split('/').next())
        {
            if !codinal_storage::public_session_exists(config.data_dir(), session_id)? {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid session id\"}",
                    None,
                );
            }
        } else {
            return write_response(
                &mut stream,
                "400 Bad Request",
                "{\"detail\":\"invalid session id\"}",
                None,
            );
        }
        return write_response(
            &mut stream,
            "501 Not Implemented",
            "{\"detail\":\"roots operations are not implemented in rust runtime\"}",
            None,
        );
    }
    if request.method == "DELETE"
        && request
            .path
            .strip_prefix("/v1/sessions/")
            .is_some_and(|path| {
                let mut segments = path.split('/');
                matches!(segments.next(), Some(session_id) if !session_id.is_empty())
                    && segments.next() == Some("project")
                    && (matches!(segments.next(), Some("index") | Some("search")))
                    && segments.next().is_none()
            })
    {
        return write_response(
            &mut stream,
            "501 Not Implemented",
            "{\"detail\":\"project operations are not implemented in rust runtime\"}",
            None,
        );
    }
    if request.method == "DELETE"
        && request
            .path
            .strip_prefix("/v1/sessions/")
            .is_some_and(|path| {
                let mut segments = path.split('/');
                matches!(segments.next(), Some(session_id) if !session_id.is_empty())
                    && segments.next() == Some("mcp")
                    && segments.next() == Some("servers")
                    && segments.next().is_some_and(|name| !name.is_empty())
                    && segments.next().is_none()
            })
    {
        if let Some(session_id) = request
            .path
            .strip_prefix("/v1/sessions/")
            .and_then(|path| path.split('/').next())
        {
            if !codinal_storage::public_session_exists(config.data_dir(), session_id)? {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid session id\"}",
                    None,
                );
            }
        }
        return write_response(
            &mut stream,
            "501 Not Implemented",
            "{\"detail\":\"mcp operations are not implemented in rust runtime\"}",
            None,
        );
    }
    if request.method == "DELETE"
        && request
            .path
            .strip_prefix("/v1/sessions/")
            .is_some_and(|path| {
                let mut segments = path.split('/');
                matches!(segments.next(), Some(session_id) if !session_id.is_empty())
                    && segments.next() == Some("preview")
                    && segments.next() == Some("evidence")
                    && segments.next().is_none()
            })
    {
        if let Some(session_id) = request
            .path
            .strip_prefix("/v1/sessions/")
            .and_then(|path| path.split('/').next())
        {
            if !codinal_storage::public_session_exists(config.data_dir(), session_id)? {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid session id\"}",
                    None,
                );
            }
        }
        return write_response(
            &mut stream,
            "501 Not Implemented",
            "{\"detail\":\"preview operations are not implemented in rust runtime\"}",
            None,
        );
    }
    if request.method == "DELETE"
        && request
            .path
            .strip_prefix("/v1/sessions/")
            .is_some_and(|path| !path.is_empty() && !path.contains('/'))
    {
        return write_response(
            &mut stream,
            "501 Not Implemented",
            "{\"detail\":\"session delete is not implemented in rust runtime\"}",
            None,
        );
    }
    if request.method == "PATCH"
        && request
            .path
            .strip_prefix("/v1/sessions/")
            .is_some_and(|path| {
                let mut segments = path.split('/');
                matches!(segments.next(), Some(session_id) if !session_id.is_empty())
                    && segments.next() == Some("mcp")
                    && segments.next() == Some("servers")
                    && segments.next().is_some_and(|name| !name.is_empty())
                    && segments.next().is_none()
            })
    {
        if let Some(session_id) = request
            .path
            .strip_prefix("/v1/sessions/")
            .and_then(|path| path.split('/').next())
        {
            if !codinal_storage::public_session_exists(config.data_dir(), session_id)? {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid session id\"}",
                    None,
                );
            }
        }
        return write_response(
            &mut stream,
            "501 Not Implemented",
            "{\"detail\":\"mcp operations are not implemented in rust runtime\"}",
            None,
        );
    }
    if request.method == "PATCH"
        && request
            .path
            .strip_prefix("/v1/sessions/")
            .is_some_and(|path| !path.is_empty() && !path.contains('/'))
    {
        return write_response(
            &mut stream,
            "501 Not Implemented",
            "{\"detail\":\"session patch is not implemented in rust runtime\"}",
            None,
        );
    }
    if request.method == "POST" && request.path == "/v1/providers/custom"
        || request.method == "DELETE" && request.path.starts_with("/v1/providers/custom/")
    {
        let sync_tokens = request
            .headers
            .iter()
            .filter(|(name, _)| name == "x-codinal-secret-sync")
            .map(|(_, value)| value.as_str())
            .collect::<Vec<_>>();
        let mut secrets = config
            .provider_secrets
            .write()
            .map_err(|_| io::Error::other("provider secret lock poisoned"))?;
        if sync_tokens.len() != 1 || !secrets.sync_token_matches(sync_tokens[0]) {
            return write_response(
                &mut stream,
                "401 Unauthorized",
                "{\"detail\":\"unauthorized secret sync\"}",
                None,
            );
        }
        let (provider, api_key, base_url, failover_eligible) = if request.method == "POST" {
            let mut document: serde_json::Value = match serde_json::from_slice(&request.body) {
                Ok(document) => document,
                Err(_) => {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid custom provider update\"}",
                        None,
                    );
                }
            };
            let Some(object) = document.as_object_mut() else {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid custom provider update\"}",
                    None,
                );
            };
            let slug = match object.remove("slug") {
                Some(serde_json::Value::String(value)) => value,
                _ => {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid custom provider update\"}",
                        None,
                    );
                }
            };
            let api_key = match object.remove("api_key") {
                Some(serde_json::Value::String(value)) => Zeroizing::new(value),
                _ => {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid custom provider update\"}",
                        None,
                    );
                }
            };
            let base_url = match object.remove("base_url") {
                Some(serde_json::Value::String(value)) => value,
                _ => {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid custom provider update\"}",
                        None,
                    );
                }
            };
            let failover = match object.remove("failover_eligible") {
                Some(serde_json::Value::Bool(value)) => value,
                _ => {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid custom provider update\"}",
                        None,
                    );
                }
            };
            if !object.is_empty() {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid custom provider update\"}",
                    None,
                );
            }
            (
                format!("custom:{slug}"),
                Some(api_key),
                Some(base_url),
                Some(failover),
            )
        } else {
            let slug = request
                .path
                .strip_prefix("/v1/providers/custom/")
                .unwrap_or_default();
            if !request.body.is_empty() {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid custom provider update\"}",
                    None,
                );
            }
            (format!("custom:{slug}"), None, None, None)
        };
        if secrets
            .validate_update(
                &provider,
                api_key.as_deref().map(String::as_str),
                base_url.as_deref(),
                failover_eligible,
            )
            .is_err()
        {
            return write_response(
                &mut stream,
                "400 Bad Request",
                "{\"detail\":\"invalid custom provider update\"}",
                None,
            );
        }
        let Some(audit) = config.audit_ledger.as_ref() else {
            return write_response(
                &mut stream,
                "503 Service Unavailable",
                "{\"detail\":\"custom provider update could not be audited\"}",
                None,
            );
        };
        if audit
            .record(codinal_policy::AuditLedgerInput {
                domain: "provider_secret".to_owned(),
                action: if api_key.is_some() {
                    "configured"
                } else {
                    "deleted"
                }
                .to_owned(),
                actor: "system".to_owned(),
                subject: provider.clone(),
                payload: serde_json::json!({}),
            })
            .is_err()
            || secrets
                .update(
                    &provider,
                    api_key.as_deref().map(String::as_str),
                    base_url.as_deref(),
                    failover_eligible,
                )
                .is_err()
        {
            return write_response(
                &mut stream,
                "503 Service Unavailable",
                "{\"detail\":\"custom provider update failed\"}",
                None,
            );
        }
        return write_response(&mut stream, "200 OK", "{\"ok\":true}", None);
    }
    if matches!(request.method.as_str(), "PUT" | "DELETE") {
        if let Some(provider) = request.path.strip_prefix("/v1/secrets/providers/") {
            if !matches!(
                ProviderId::parse(provider),
                Some(
                    ProviderId::OpenAi
                        | ProviderId::OpenCodeGo
                        | ProviderId::Anthropic
                        | ProviderId::Gemini
                        | ProviderId::Zai
                        | ProviderId::DeepSeek
                        | ProviderId::OmniRoute
                        | ProviderId::GitHub
                )
            ) {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid provider secret update\"}",
                    None,
                );
            }
            let sync_tokens = request
                .headers
                .iter()
                .filter(|(name, _)| name == "x-codinal-secret-sync")
                .map(|(_, value)| value.as_str())
                .collect::<Vec<_>>();
            let mut secrets = config
                .provider_secrets
                .write()
                .map_err(|_| io::Error::other("provider secret lock poisoned"))?;
            if sync_tokens.len() != 1 || !secrets.sync_token_matches(sync_tokens[0]) {
                return write_response(
                    &mut stream,
                    "401 Unauthorized",
                    "{\"detail\":\"unauthorized secret sync\"}",
                    None,
                );
            }
            let (api_key, base_url) = if request.method == "PUT" {
                let mut document: serde_json::Value = match serde_json::from_slice(&request.body) {
                    Ok(document) => document,
                    Err(_) => {
                        return write_response(
                            &mut stream,
                            "400 Bad Request",
                            "{\"detail\":\"invalid provider secret update\"}",
                            None,
                        );
                    }
                };
                let Some(object) = document.as_object_mut() else {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid provider secret update\"}",
                        None,
                    );
                };
                let api_key = match object.remove("api_key") {
                    Some(serde_json::Value::String(value)) => Zeroizing::new(value),
                    _ => {
                        return write_response(
                            &mut stream,
                            "400 Bad Request",
                            "{\"detail\":\"invalid provider secret update\"}",
                            None,
                        );
                    }
                };
                let base_url = match object.remove("base_url") {
                    Some(serde_json::Value::String(value)) => Some(value),
                    None => None,
                    _ => {
                        return write_response(
                            &mut stream,
                            "400 Bad Request",
                            "{\"detail\":\"invalid provider secret update\"}",
                            None,
                        );
                    }
                };
                if !object.is_empty() {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid provider secret update\"}",
                        None,
                    );
                }
                (Some(api_key), base_url)
            } else if request.body.is_empty() {
                (None, None)
            } else {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid provider secret update\"}",
                    None,
                );
            };
            if secrets
                .validate_update(
                    provider,
                    api_key.as_deref().map(String::as_str),
                    base_url.as_deref(),
                    None,
                )
                .is_err()
            {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid provider secret update\"}",
                    None,
                );
            }
            let Some(audit) = config.audit_ledger.as_ref() else {
                return write_response(
                    &mut stream,
                    "503 Service Unavailable",
                    "{\"detail\":\"provider secret update could not be audited\"}",
                    None,
                );
            };
            if audit
                .record(codinal_policy::AuditLedgerInput {
                    domain: "provider_secret".to_owned(),
                    action: if api_key.is_some() {
                        "configured"
                    } else {
                        "deleted"
                    }
                    .to_owned(),
                    actor: "system".to_owned(),
                    subject: provider.to_owned(),
                    payload: serde_json::json!({}),
                })
                .is_err()
                || secrets
                    .update(
                        provider,
                        api_key.as_deref().map(String::as_str),
                        base_url.as_deref(),
                        None,
                    )
                    .is_err()
            {
                return write_response(
                    &mut stream,
                    "503 Service Unavailable",
                    "{\"detail\":\"provider secret update failed\"}",
                    None,
                );
            }
            return write_response(&mut stream, "200 OK", "{\"ok\":true}", None);
        }
    }
    if request.method == "POST" {
        if let Some((session_id, approval_id)) = parse_approval_decision_path(&request.path) {
            if !codinal_storage::public_session_exists(config.data_dir(), session_id)? {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid session id\"}",
                    None,
                );
            }
            if approval_id.len() != 32
                || !approval_id
                    .bytes()
                    .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
            {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid approval id\"}",
                    None,
                );
            }
            let decision: serde_json::Value = match serde_json::from_slice(&request.body) {
                Ok(decision) => decision,
                Err(_) => {
                    return write_response(
                        &mut stream,
                        "400 Bad Request",
                        "{\"detail\":\"invalid approval decision\"}",
                        None,
                    );
                }
            };
            let outcome = decision
                .as_object()
                .filter(|object| object.len() == 1)
                .and_then(|object| object.get("outcome"))
                .and_then(serde_json::Value::as_str);
            if !matches!(
                outcome,
                Some("once" | "always_tool" | "always_command" | "deny")
            ) {
                return write_response(
                    &mut stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid approval decision\"}",
                    None,
                );
            }
            let outcome = outcome.expect("validated outcome");
            let durable_record = config
                .runtime_store
                .as_ref()
                .map(|store| {
                    store.read_pending_approvals(session_id).map(|records| {
                        records
                            .into_iter()
                            .find(|record| record.approval_id == approval_id)
                    })
                })
                .transpose()?
                .flatten();
            if let Some(record) = durable_record.as_ref() {
                if approval_request_is_expired(&record.request) {
                    let mut broker = config
                        .approval_broker
                        .lock()
                        .map_err(|_| io::Error::other("approval broker lock poisoned"))?;
                    let expired = expire_durable_approval(config, &mut broker, record)?;
                    drop(broker);
                    if expired {
                        return write_json_response(
                            &mut stream,
                            "409 Conflict",
                            &serde_json::json!({
                                "detail": "approval expired",
                                "reason_code": "approval_expired",
                                "approval_id": approval_id,
                            }),
                        );
                    }
                }
            }
            if outcome != "deny" && outcome != "once" {
                return write_response(
                    &mut stream,
                    "409 Conflict",
                    "{\"detail\":\"only once or deny is enabled in this execution slice\"}",
                    None,
                );
            }
            let mut broker = config
                .approval_broker
                .lock()
                .map_err(|_| io::Error::other("approval broker lock poisoned"))?;
            if !broker
                .pending(session_id)
                .iter()
                .any(|pending| pending.approval_id == approval_id)
            {
                return write_response(
                    &mut stream,
                    "409 Conflict",
                    "{\"detail\":\"approval is no longer pending\"}",
                    None,
                );
            }
            let Some(audit) = config.audit_ledger.as_ref() else {
                return write_response(
                    &mut stream,
                    "503 Service Unavailable",
                    "{\"detail\":\"approval decision could not be saved\"}",
                    None,
                );
            };
            if audit
                .record(codinal_policy::AuditLedgerInput {
                    domain: "approval".to_owned(),
                    action: "resolve".to_owned(),
                    actor: "system".to_owned(),
                    subject: approval_id.to_owned(),
                    payload: serde_json::json!({"outcome": outcome}),
                })
                .is_err()
            {
                return write_response(
                    &mut stream,
                    "503 Service Unavailable",
                    "{\"detail\":\"approval decision could not be saved\"}",
                    None,
                );
            }
            let mutation = if outcome == "once" {
                let Some(record) = durable_record.as_ref() else {
                    return write_response(
                        &mut stream,
                        "409 Conflict",
                        "{\"detail\":\"durable approval is unavailable\"}",
                        None,
                    );
                };
                match apply_approved_mutation(config, record) {
                    Ok(mutation) => Some(mutation),
                    Err(_) => {
                        return write_response(
                            &mut stream,
                            "409 Conflict",
                            "{\"detail\":\"approved patch could not be applied; source or boundary changed\"}",
                            None,
                        );
                    }
                }
            } else {
                None
            };
            let resolved = broker.resolve(session_id, approval_id);
            let mut response_state = if outcome == "once" {
                "completed"
            } else {
                "failed"
            };
            let mut resumed = false;
            let mut worker_failed = false;
            if resolved {
                if let Some(store) = config.runtime_store.as_ref() {
                    if let Some(record) = durable_record.as_ref() {
                        store.put_approval(&codinal_storage::ApprovalRecord {
                            approval_id: approval_id.to_owned(),
                            turn_id: record.turn_id.clone(),
                            session_id: record.session_id.clone(),
                            request: record.request.clone(),
                            state: if outcome == "once" {
                                "applied".to_owned()
                            } else {
                                "denied".to_owned()
                            },
                        })?;
                        if outcome == "deny" {
                            fail_provider_resume_budget(config, record);
                        }
                        let reason = if outcome == "once" {
                            "approval_applied"
                        } else {
                            "approval_denied"
                        };
                        let approval_records = if outcome == "once" {
                            store.read_approvals_for_turn(&record.turn_id)?
                        } else {
                            Vec::new()
                        };
                        let pending_approvals = approval_records
                            .iter()
                            .any(|approval| approval.state == "pending");
                        let resume_job = if outcome == "once" && !pending_approvals {
                            provider_resume_from_record(record)
                                .ok()
                                .flatten()
                                .and_then(|resume| {
                                    let profile = resume.profile().ok()?;
                                    let context_messages =
                                        provider_resume_context(config, &approval_records, &resume)
                                            .ok()?;
                                    Some((resume, profile, context_messages))
                                })
                        } else {
                            None
                        };
                        response_state = if outcome == "deny" {
                            "failed"
                        } else if resume_job.is_some() {
                            "streaming"
                        } else if pending_approvals {
                            "awaiting_approval"
                        } else {
                            "completed"
                        };
                        let _ = store.transition_turn(&record.turn_id, response_state);
                        let _ = store.append_event(
                            &record.turn_id,
                            if outcome == "once" {
                                "mutation_committed"
                            } else {
                                "approval_denied"
                            },
                            serde_json::json!({
                                "approval_id": approval_id,
                                "session_id": record.session_id.clone(),
                                "reason": reason,
                                "mutation": mutation,
                                "state": response_state,
                            }),
                        );
                        if let Some((resume, profile, context_messages)) = resume_job {
                            let cancellation = Arc::new(AtomicBool::new(false));
                            let active_inserted = config
                                .turn_cancellation
                                .lock()
                                .map_err(|_| io::Error::other("turn coordinator lock poisoned"))?
                                .insert(
                                    record.turn_id.clone(),
                                    ActiveTurn {
                                        session_id: record.session_id.clone(),
                                        cancellation: Arc::clone(&cancellation),
                                    },
                                )
                                .is_none();
                            if active_inserted {
                                let job = ProviderTurnJob {
                                    turn_id: record.turn_id.clone(),
                                    session_id: record.session_id.clone(),
                                    input: resume.input,
                                    context_messages,
                                    cancellation,
                                    profile,
                                    fallback_requested: resume.fallback_requested,
                                    budget_reservation_id: resume.budget_reservation_id,
                                };
                                let _ = store.append_event(
                                    &record.turn_id,
                                    "approval_resumed",
                                    serde_json::json!({
                                        "approval_id": approval_id,
                                        "session_id": record.session_id.clone(),
                                        "state": "streaming",
                                    }),
                                );
                                if spawn_provider_turn_job(config, job).is_ok() {
                                    resumed = true;
                                } else {
                                    worker_failed = true;
                                    fail_provider_resume_budget(config, record);
                                    finalize_owned_turn(
                                        store,
                                        config,
                                        &record.turn_id,
                                        &record.session_id,
                                        "failed",
                                        serde_json::json!({
                                            "reason": "turn_worker_unavailable",
                                            "approval_id": approval_id,
                                        }),
                                        0,
                                    );
                                }
                            } else {
                                worker_failed = true;
                                fail_provider_resume_budget(config, record);
                                finalize_owned_turn(
                                    store,
                                    config,
                                    &record.turn_id,
                                    &record.session_id,
                                    "failed",
                                    serde_json::json!({
                                        "reason": "turn_already_active",
                                        "approval_id": approval_id,
                                    }),
                                    0,
                                );
                            }
                        } else if response_state != "awaiting_approval" {
                            let _ = store.write_receipt(
                                &record.turn_id,
                                &record.session_id,
                                serde_json::json!({
                                    "status": response_state,
                                    "reason": reason,
                                    "approval_id": approval_id,
                                    "mutation": mutation,
                                }),
                                0,
                            );
                        }
                    }
                }
            }
            drop(broker);
            return if resolved {
                write_json_response(
                    &mut stream,
                    if worker_failed {
                        "503 Service Unavailable"
                    } else if resumed {
                        "202 Accepted"
                    } else {
                        "200 OK"
                    },
                    &serde_json::json!({
                        "ok": !worker_failed,
                        "approval_id": approval_id,
                        "outcome": outcome,
                        "mutation": mutation,
                        "resumed": resumed,
                        "state": response_state,
                    }),
                )
            } else {
                write_response(
                    &mut stream,
                    "409 Conflict",
                    "{\"detail\":\"approval is no longer pending\"}",
                    None,
                )
            };
        }
    }
    write_response(
        &mut stream,
        "404 Not Found",
        "{\"detail\":\"not found\"}",
        None,
    )
}

fn looks_like_websocket_request(stream: &TcpStream) -> io::Result<bool> {
    let mut prefix = [0_u8; 8 * 1024];
    let deadline = Instant::now() + Duration::from_secs(2);
    loop {
        let size = stream.peek(&mut prefix)?;
        if size == 0 {
            return Ok(false);
        }
        let request = String::from_utf8_lossy(&prefix[..size]);
        if request.contains("\r\n\r\n") {
            let request_line = request.lines().next().unwrap_or_default();
            let supported_path = request_line.starts_with("GET /ws/events ")
                || request_line.starts_with("GET /ws/session/");
            let websocket_upgrade = request.lines().any(|line| {
                let line = line.to_ascii_lowercase();
                line.strip_prefix("upgrade:")
                    .is_some_and(|value| value.split(',').any(|part| part.trim() == "websocket"))
            });
            return Ok(supported_path && websocket_upgrade);
        }
        if size == prefix.len() || Instant::now() >= deadline {
            return Ok(false);
        }
        std::thread::sleep(Duration::from_millis(1));
    }
}

fn websocket_target(path: &str) -> Result<Option<String>, ()> {
    if path == "/ws/events" {
        return Ok(None);
    }
    let encoded = path.strip_prefix("/ws/session/").ok_or(())?;
    if encoded.is_empty() || encoded.contains('/') {
        return Err(());
    }
    let session_id = String::from_utf8(percent_decode(encoded)?).map_err(|_| ())?;
    if valid_runtime_session_id(&session_id) {
        Ok(Some(session_id))
    } else {
        Err(())
    }
}

fn valid_runtime_session_id(session_id: &str) -> bool {
    !session_id.is_empty()
        && session_id.len() <= 128
        && !session_id.starts_with("__")
        && session_id.bytes().enumerate().all(|(index, byte)| {
            byte.is_ascii_alphanumeric() || (index > 0 && matches!(byte, b'-' | b'_'))
        })
}

fn websocket_protocol_offered(headers: &tungstenite::http::HeaderMap, expected: &str) -> bool {
    headers
        .get_all("Sec-WebSocket-Protocol")
        .iter()
        .filter_map(|value| value.to_str().ok())
        .flat_map(|value| value.split(',').map(str::trim))
        .any(|value| value == expected)
}

fn websocket_auth_offered(headers: &tungstenite::http::HeaderMap, token: &[u8]) -> bool {
    headers
        .get_all("Sec-WebSocket-Protocol")
        .iter()
        .filter_map(|value| value.to_str().ok())
        .flat_map(|value| value.split(',').map(str::trim))
        .filter_map(|value| value.strip_prefix("codinal.auth."))
        .map(str::as_bytes)
        .any(|candidate| {
            candidate.len() == token.len()
                && candidate
                    .iter()
                    .zip(token)
                    .fold(0_u8, |difference, (left, right)| {
                        difference | (left ^ right)
                    })
                    == 0
        })
}

fn websocket_error(status: u16, detail: &str) -> tungstenite::http::Response<Option<String>> {
    tungstenite::http::Response::builder()
        .status(status)
        .header("Content-Type", "application/json")
        .body(Some(serde_json::json!({ "detail": detail }).to_string()))
        .expect("valid websocket error response")
}

// tungstenite's handshake callback requires a response-valued error, so this
// API-shaped Result cannot use a boxed error without changing the transport.
#[allow(clippy::result_large_err)]
fn serve_websocket(stream: TcpStream, config: &RuntimeConfig) -> io::Result<()> {
    let requested_session = Arc::new(Mutex::new(None::<String>));
    let requested_session_for_handshake = Arc::clone(&requested_session);
    let token = Zeroizing::new(config.token.as_bytes().to_vec());
    let mut socket = accept_hdr(
        stream,
        move |request: &tungstenite::handshake::server::Request,
              mut response: tungstenite::handshake::server::Response| {
            let target = websocket_target(request.uri().path())
                .map_err(|_| websocket_error(400, "invalid websocket path"))?;
            if !websocket_protocol_offered(request.headers(), "codinal.v1")
                || !websocket_auth_offered(request.headers(), &token)
            {
                return Err(websocket_error(401, "unauthorized"));
            }
            if let Some(session_id) = target {
                requested_session_for_handshake
                    .lock()
                    .map_err(|_| websocket_error(500, "websocket state unavailable"))?
                    .replace(session_id);
            }
            response.headers_mut().insert(
                "Sec-WebSocket-Protocol",
                HeaderValue::from_static("codinal.v1"),
            );
            Ok(response)
        },
    )
    .map_err(|error| io::Error::other(format!("websocket handshake failed: {error}")))?;
    socket
        .get_mut()
        .set_read_timeout(Some(Duration::from_millis(100)))?;

    let session_id = requested_session
        .lock()
        .map_err(|_| io::Error::other("websocket state lock poisoned"))?
        .clone();
    let Some(store) = config.runtime_store.as_ref() else {
        let message = serde_json::json!({
            "type": "stream_error",
            "error": "runtime event store unavailable",
            "status": "read_only",
        });
        let _ = socket.send(Message::Text(message.to_string().into()));
        let _ = socket.close(None);
        return Ok(());
    };

    let mut cursor = None;
    let mut turn_sessions = BTreeMap::<String, String>::new();
    while !config.is_shutdown_requested() {
        let replay = store.replay_events(cursor.as_deref(), 100)?;
        if replay.cursor_expired {
            let _ = socket.send(Message::Text(
                serde_json::json!({
                    "type": "reload_required",
                    "status": "cursor_expired",
                    "reload": replay.receipt_reload_target,
                })
                .to_string()
                .into(),
            ));
            cursor = None;
        } else {
            cursor = Some(replay.next_cursor);
            for event in replay.events {
                if let Some(event_session_id) = event
                    .payload
                    .get("session_id")
                    .and_then(serde_json::Value::as_str)
                {
                    turn_sessions.insert(event.turn_id.clone(), event_session_id.to_owned());
                }
                let belongs = match session_id.as_deref() {
                    Some(session_id) => turn_sessions
                        .get(&event.turn_id)
                        .is_some_and(|event_session_id| event_session_id == session_id),
                    None => true,
                };
                if belongs {
                    let message = websocket_event_message(&event);
                    socket
                        .send(Message::Text(message.to_string().into()))
                        .map_err(|error| {
                            io::Error::other(format!("websocket send failed: {error}"))
                        })?;
                }
            }
        }

        match socket.read() {
            Ok(Message::Close(_)) => {
                let _ = socket.close(None);
                break;
            }
            Ok(Message::Ping(_)) | Ok(Message::Pong(_)) => {
                let _ = socket.flush();
            }
            Ok(Message::Text(_)) | Ok(Message::Binary(_)) => {}
            Ok(_) => {}
            Err(tungstenite::Error::Io(error))
                if matches!(
                    error.kind(),
                    io::ErrorKind::WouldBlock | io::ErrorKind::TimedOut
                ) =>
            {
                continue;
            }
            Err(tungstenite::Error::ConnectionClosed | tungstenite::Error::AlreadyClosed) => {
                break;
            }
            Err(error) => {
                return Err(io::Error::other(format!("websocket read failed: {error}")));
            }
        }
    }
    Ok(())
}

fn websocket_event_message(event: &codinal_storage::RuntimeEventRecord) -> serde_json::Value {
    let event_type = match event.kind.as_str() {
        "created" => "turn_start",
        "streaming" => "turn_started",
        "assistant" => "assistant_message",
        "awaiting_approval" => "permission_required",
        "completed" | "mutation_committed" => "turn_end",
        "interrupted" => "interrupted",
        "failed" | "approval_denied" => "error",
        "approval_expired" => "approval_expired",
        other => other,
    };
    let mut message = serde_json::json!({
        "type": event_type,
        "kind": event.kind,
        "turn_id": event.turn_id,
        "sequence": event.sequence,
        "global_sequence": event.global_sequence,
    });
    let Some(output) = message.as_object_mut() else {
        return message;
    };
    if let Some(payload) = event.payload.as_object() {
        for field in ["session_id", "name", "status"] {
            if let Some(value) = payload.get(field).filter(|value| value.is_string()) {
                output.insert(field.to_owned(), value.clone());
            }
        }
        if let Some(text) = payload.get("text").and_then(serde_json::Value::as_str) {
            output.insert(
                "text".to_owned(),
                serde_json::Value::String(text.to_owned()),
            );
        }
        if matches!(
            event.kind.as_str(),
            "failed" | "approval_denied" | "approval_expired"
        ) {
            let reason = payload
                .get("reason")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("runtime turn failed");
            output.insert(
                "error".to_owned(),
                serde_json::Value::String(reason.to_owned()),
            );
        }
    }
    output
        .entry("status".to_owned())
        .or_insert_with(|| serde_json::Value::String(event.kind.clone()));
    message
}

fn create_owned_session(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    body: &[u8],
) -> io::Result<()> {
    let request: CreateSessionRequest = match serde_json::from_slice(body) {
        Ok(request) => request,
        Err(_) => {
            return write_response(
                stream,
                "400 Bad Request",
                "{\"detail\":\"invalid session request\"}",
                None,
            )
        }
    };
    let model = request.model.as_deref().unwrap_or(OPENCODE_GO_MODEL);
    if !matches!(model, OPENCODE_GO_MODEL | DEEPSEEK_MODEL) {
        return write_json_response(
            stream,
            "400 Bad Request",
            &serde_json::json!({
                "detail": "unsupported session model",
                "model": OPENCODE_GO_MODEL,
            }),
        );
    }
    let mode = request.mode.as_deref().unwrap_or("code");
    if mode != "code" {
        return write_response(
            stream,
            "400 Bad Request",
            "{\"detail\":\"unsupported session mode\"}",
            None,
        );
    }
    let title = request.title.as_deref().unwrap_or("New chat");
    let session_id = format!(
        "session-{}-{}",
        runtime_timestamp(),
        NEXT_SESSION_ID.fetch_add(1, Ordering::Relaxed)
    );
    match codinal_storage::create_session_with_origin(
        config.data_dir(),
        &session_id,
        title,
        &request.workspace,
        "code",
        model,
        mode,
        request.origin.as_deref(),
        request.origin_label.as_deref(),
        request.origin_session_id.as_deref(),
    ) {
        Ok(session) => write_json_response(stream, "201 Created", &session),
        Err(error) if error.kind() == io::ErrorKind::InvalidInput => write_json_response(
            stream,
            "400 Bad Request",
            &serde_json::json!({ "detail": error.to_string() }),
        ),
        Err(error) if error.kind() == io::ErrorKind::AlreadyExists => write_json_response(
            stream,
            "409 Conflict",
            &serde_json::json!({ "detail": "session already exists" }),
        ),
        Err(error) => write_json_response(
            stream,
            "500 Internal Server Error",
            &serde_json::json!({ "detail": error.to_string() }),
        ),
    }
}

fn update_owned_session(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    session_id: &str,
    body: &[u8],
) -> io::Result<()> {
    let request: UpdateSessionRequest = match serde_json::from_slice(body) {
        Ok(request) => request,
        Err(_) => {
            return write_response(
                stream,
                "400 Bad Request",
                "{\"detail\":\"invalid session update request\"}",
                None,
            )
        }
    };
    match codinal_storage::update_session(
        config.data_dir(),
        session_id,
        request.title.as_deref(),
        request.pinned,
        request.archived,
    ) {
        Ok(session) => write_json_response(stream, "200 OK", &session),
        Err(error) => write_project_error(stream, error),
    }
}

fn delete_owned_session(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    session_id: &str,
) -> io::Result<()> {
    match codinal_storage::delete_session(config.data_dir(), session_id) {
        Ok(()) => write_json_response(stream, "200 OK", &serde_json::json!({"ok": true})),
        Err(error) => write_project_error(stream, error),
    }
}

fn project_error_status(error: &io::Error) -> &'static str {
    match error.kind() {
        io::ErrorKind::InvalidInput | io::ErrorKind::InvalidData => "400 Bad Request",
        io::ErrorKind::PermissionDenied => "403 Forbidden",
        io::ErrorKind::NotFound => "404 Not Found",
        io::ErrorKind::AlreadyExists => "409 Conflict",
        _ => "500 Internal Server Error",
    }
}

fn write_project_error(stream: &mut TcpStream, error: io::Error) -> io::Result<()> {
    write_json_response(
        stream,
        project_error_status(&error),
        &serde_json::json!({"detail": error.to_string()}),
    )
}

#[derive(serde::Serialize)]
struct ActivityItemResponse {
    activity_id: String,
    session_id: Option<String>,
    kind: String,
    title: String,
    detail: String,
    unread: bool,
}

fn list_activity(stream: &mut TcpStream, config: &RuntimeConfig) -> io::Result<()> {
    let marked_read = config.activity_read.load(Ordering::Acquire);
    let mut items = Vec::new();
    if let Some(store) = config.runtime_store.as_ref() {
        for approval in store.read_all_pending_approvals()? {
            items.push(ActivityItemResponse {
                activity_id: format!("approval-{}", approval.approval_id),
                session_id: Some(approval.session_id),
                kind: "waiting".to_owned(),
                title: "Approval needed".to_owned(),
                detail: format!("Action {} is waiting for review", approval.approval_id),
                unread: !marked_read,
            });
        }
    }
    for (turn_id, active_turn) in config
        .turn_cancellation
        .lock()
        .map_err(|_| io::Error::other("turn coordinator lock poisoned"))?
        .iter()
    {
        items.push(ActivityItemResponse {
            activity_id: format!("turn-{turn_id}"),
            session_id: Some(active_turn.session_id.clone()),
            kind: "running".to_owned(),
            title: "Turn running".to_owned(),
            detail: "A Codinal turn is still working".to_owned(),
            unread: !marked_read,
        });
    }
    write_json_response(stream, "200 OK", &items)
}

fn source_path_details(path: &str) -> io::Result<(String, String, String)> {
    let path = path.trim();
    if path.is_empty()
        || path.len() > 4096
        || path.bytes().any(|byte| matches!(byte, 0 | b'\r' | b'\n'))
        || !Path::new(path).is_absolute()
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "source path must be an absolute path",
        ));
    }
    let selected = Path::new(path);
    let metadata = fs::symlink_metadata(selected)?;
    if metadata.file_type().is_symlink() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "source path must not be a symbolic link",
        ));
    }
    if !metadata.is_file() && !metadata.is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "source path must be a file or folder",
        ));
    }
    let canonical = fs::canonicalize(selected)?;
    let kind = if metadata.is_dir() { "folder" } else { "file" }.to_owned();
    let name = canonical
        .file_name()
        .and_then(|name| name.to_str())
        .filter(|name| !name.is_empty())
        .unwrap_or_else(|| canonical.to_str().unwrap_or("source"))
        .to_owned();
    Ok((canonical.to_string_lossy().into_owned(), name, kind))
}

fn source_attachment_id(session_id: &str, path: &str) -> String {
    format!(
        "source-{}",
        &sha256_hex(format!("{session_id}\0{path}").as_bytes())[..32]
    )
}

fn write_source_error(stream: &mut TcpStream, error: io::Error) -> io::Result<()> {
    write_json_response(
        stream,
        project_error_status(&error),
        &serde_json::json!({"detail": error.to_string()}),
    )
}

fn list_owned_sources(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    session_id: &str,
) -> io::Result<()> {
    if !codinal_storage::public_session_exists(config.data_dir(), session_id)? {
        return write_response(
            stream,
            "400 Bad Request",
            "{\"detail\":\"invalid session id\"}",
            None,
        );
    }
    match codinal_storage::read_source_attachments(config.data_dir(), session_id) {
        Ok(sources) => write_json_response(stream, "200 OK", &sources),
        Err(error) => write_source_error(stream, error),
    }
}

fn read_owned_source(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    session_id: &str,
    attachment_id: &str,
) -> io::Result<()> {
    match codinal_storage::read_source_attachment(config.data_dir(), session_id, attachment_id) {
        Ok(source) => write_json_response(stream, "200 OK", &source),
        Err(error) => write_source_error(stream, error),
    }
}

#[derive(serde::Serialize)]
struct SourcePreviewResponse {
    attachment: codinal_storage::SourceAttachment,
    content: String,
    binary: bool,
    truncated: bool,
}

fn preview_owned_source(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    session_id: &str,
    attachment_id: &str,
) -> io::Result<()> {
    let attachment =
        match codinal_storage::read_source_attachment(config.data_dir(), session_id, attachment_id)
        {
            Ok(source) => source,
            Err(error) => return write_source_error(stream, error),
        };
    if attachment.status != "ready" {
        return write_json_response(
            stream,
            "409 Conflict",
            &serde_json::json!({
                "detail": attachment.error.clone().unwrap_or_else(|| "source is unavailable".to_owned()),
                "source": attachment,
            }),
        );
    }
    let mut content = String::new();
    let mut binary = false;
    let mut truncated = false;
    if attachment.kind == "folder" {
        content = "Folder source · preview is available from the attached path".to_owned();
    } else {
        const MAX_SOURCE_PREVIEW_BYTES: usize = 256 * 1024;
        let bytes = match fs::read(&attachment.path) {
            Ok(bytes) => bytes,
            Err(error) => return write_source_error(stream, error),
        };
        let bounded = if bytes.len() > MAX_SOURCE_PREVIEW_BYTES {
            truncated = true;
            &bytes[..MAX_SOURCE_PREVIEW_BYTES]
        } else {
            &bytes
        };
        match String::from_utf8(bounded.to_vec()) {
            Ok(text) => content = text,
            Err(_) => binary = true,
        }
    }
    write_json_response(
        stream,
        "200 OK",
        &SourcePreviewResponse {
            attachment,
            content,
            binary,
            truncated,
        },
    )
}

fn attach_owned_source(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    session_id: &str,
    body: &[u8],
) -> io::Result<()> {
    let request: AttachSourceRequest = match serde_json::from_slice(body) {
        Ok(request) => request,
        Err(_) => {
            return write_response(
                stream,
                "400 Bad Request",
                "{\"detail\":\"invalid source attachment request\"}",
                None,
            )
        }
    };
    let (path, name, kind) = match source_path_details(&request.path) {
        Ok(details) => details,
        Err(error) => return write_source_error(stream, error),
    };
    let attachment_id = source_attachment_id(session_id, &path);
    match codinal_storage::attach_source_attachment(
        config.data_dir(),
        session_id,
        &attachment_id,
        &path,
        &name,
        &kind,
    ) {
        Ok(source) => write_json_response(stream, "201 Created", &source),
        Err(error) => write_source_error(stream, error),
    }
}

fn retry_owned_source(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    session_id: &str,
    attachment_id: &str,
) -> io::Result<()> {
    match codinal_storage::retry_source_attachment(config.data_dir(), session_id, attachment_id) {
        Ok(source) => write_json_response(stream, "200 OK", &source),
        Err(error) => write_source_error(stream, error),
    }
}

fn remove_owned_source(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    session_id: &str,
    attachment_id: &str,
) -> io::Result<()> {
    match codinal_storage::remove_source_attachment(config.data_dir(), session_id, attachment_id) {
        Ok(()) => write_json_response(stream, "200 OK", &serde_json::json!({"ok": true})),
        Err(error) => write_source_error(stream, error),
    }
}

fn create_owned_project(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    body: &[u8],
) -> io::Result<()> {
    let request: CreateProjectRequest = match serde_json::from_slice(body) {
        Ok(request) => request,
        Err(_) => {
            return write_response(
                stream,
                "400 Bad Request",
                "{\"detail\":\"invalid project request\"}",
                None,
            )
        }
    };
    let project_id = format!(
        "project-{}-{}",
        runtime_timestamp(),
        NEXT_PROJECT_ID.fetch_add(1, Ordering::Relaxed)
    );
    match codinal_storage::create_project(
        config.data_dir(),
        &project_id,
        &request.name,
        &request.roots,
    ) {
        Ok(project) => write_json_response(stream, "201 Created", &project),
        Err(error) => write_project_error(stream, error),
    }
}

fn replace_owned_project(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    project_id: &str,
    body: &[u8],
) -> io::Result<()> {
    let request: UpdateProjectRequest = match serde_json::from_slice(body) {
        Ok(request) => request,
        Err(_) => {
            return write_response(
                stream,
                "400 Bad Request",
                "{\"detail\":\"invalid project update\"}",
                None,
            )
        }
    };
    match codinal_storage::replace_project(
        config.data_dir(),
        project_id,
        &request.name,
        &request.roots,
    ) {
        Ok(project) => write_json_response(stream, "200 OK", &project),
        Err(error) => write_project_error(stream, error),
    }
}

fn remove_owned_project(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    project_id: &str,
) -> io::Result<()> {
    match codinal_storage::remove_project(config.data_dir(), project_id) {
        Ok(()) => write_json_response(stream, "200 OK", &serde_json::json!({"ok": true})),
        Err(error) => write_project_error(stream, error),
    }
}

fn set_owned_project_pinned(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    project_id: &str,
    body: &[u8],
) -> io::Result<()> {
    let request: ProjectPinnedRequest = match serde_json::from_slice(body) {
        Ok(request) => request,
        Err(_) => {
            return write_response(
                stream,
                "400 Bad Request",
                "{\"detail\":\"invalid project pin request\"}",
                None,
            )
        }
    };
    match codinal_storage::set_project_pinned(config.data_dir(), project_id, request.pinned) {
        Ok(()) => write_json_response(stream, "200 OK", &serde_json::json!({"ok": true})),
        Err(error) => write_project_error(stream, error),
    }
}

fn assign_owned_session(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    project_id: &str,
    session_id: &str,
) -> io::Result<()> {
    match codinal_storage::assign_session_to_project(config.data_dir(), session_id, project_id) {
        Ok(()) => write_json_response(stream, "200 OK", &serde_json::json!({"ok": true})),
        Err(error) => write_project_error(stream, error),
    }
}

fn remove_owned_session(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    project_id: &str,
    session_id: &str,
) -> io::Result<()> {
    match codinal_storage::remove_session_from_project(config.data_dir(), project_id, session_id) {
        Ok(()) => write_json_response(stream, "200 OK", &serde_json::json!({"ok": true})),
        Err(error) => write_project_error(stream, error),
    }
}

fn serve_owned_turn(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    session_id: &str,
    body: &[u8],
) -> io::Result<()> {
    let Some(store) = config.runtime_store.as_ref() else {
        return write_response(
            stream,
            "501 Not Implemented",
            "{\"detail\":\"turn execution owner is unavailable\"}",
            None,
        );
    };
    let document = if body.is_empty() {
        serde_json::json!({})
    } else {
        match serde_json::from_slice::<serde_json::Value>(body) {
            Ok(document) => document,
            Err(_) => {
                return write_response(
                    stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid turn request\"}",
                    None,
                );
            }
        }
    };
    if document.as_object().is_some_and(serde_json::Map::is_empty) {
        return write_response(
            stream,
            "501 Not Implemented",
            "{\"detail\":\"turn operations are not implemented in rust runtime\"}",
            None,
        );
    }
    if document
        .get("provider")
        .and_then(serde_json::Value::as_str)
        .is_some()
    {
        return start_provider_turn(stream, config, session_id, &document);
    }
    let turn_id = document
        .get("turn_id")
        .and_then(serde_json::Value::as_str)
        .filter(|value| !value.is_empty())
        .map(str::to_owned)
        .unwrap_or_else(|| format!("turn-{}-{}", std::process::id(), runtime_timestamp()));
    if turn_id.len() > 256
        || !turn_id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
    {
        return write_response(
            stream,
            "400 Bad Request",
            "{\"detail\":\"invalid turn id\"}",
            None,
        );
    }
    if let Err(error) = config.set_activity_read(false) {
        return write_json_response(
            stream,
            "500 Internal Server Error",
            &serde_json::json!({"detail": error.to_string()}),
        );
    }
    let cancellation = Arc::new(AtomicBool::new(false));
    {
        let mut active = config
            .turn_cancellation
            .lock()
            .map_err(|_| io::Error::other("turn coordinator lock poisoned"))?;
        if active
            .insert(
                turn_id.clone(),
                ActiveTurn {
                    session_id: session_id.to_owned(),
                    cancellation: Arc::clone(&cancellation),
                },
            )
            .is_some()
        {
            return write_response(
                stream,
                "409 Conflict",
                "{\"detail\":\"turn is already active\"}",
                None,
            );
        }
    }
    if let Err(error) = store.create_turn(&turn_id, session_id).and_then(|_| {
        store
            .append_event(
                &turn_id,
                "created",
                serde_json::json!({"session_id": session_id}),
            )
            .map(|_| ())
    }) {
        config
            .turn_cancellation
            .lock()
            .map_err(|_| io::Error::other("turn coordinator lock poisoned"))?
            .remove(&turn_id);
        return write_json_response(
            stream,
            "500 Internal Server Error",
            &serde_json::json!({"detail": error.to_string()}),
        );
    }
    while !cancellation.load(Ordering::Acquire) && !config.is_shutdown_requested() {
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
    let _ = store.transition_turn(&turn_id, "interrupted");
    let _ = store.append_event(
        &turn_id,
        "interrupted",
        serde_json::json!({
            "session_id": session_id,
            "reason": "cancellation"
        }),
    );
    let receipt = store.write_receipt(
        &turn_id,
        session_id,
        serde_json::json!({"status": "interrupted", "reason": "cancellation"}),
        0,
    )?;
    config
        .turn_cancellation
        .lock()
        .map_err(|_| io::Error::other("turn coordinator lock poisoned"))?
        .remove(&turn_id);
    write_json_response(
        stream,
        "200 OK",
        &serde_json::json!({
            "ok": true,
            "session_id": session_id,
            "turn_id": turn_id,
            "outcome": "interrupted",
            "created_at": receipt.created_at,
            "receipt": {
                "authoritative": true,
                "reload": format!("/v1/sessions/{session_id}/turns")
            }
        }),
    )
}

fn serve_capability_probe(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    body: &[u8],
) -> io::Result<()> {
    if config.readiness.is_read_only() {
        return write_json_response(
            stream,
            "423 Locked",
            &serde_json::json!({
                "detail": "capability probe requires the owning runtime",
                "reason_code": "owner_bootstrap_deferred",
            }),
        );
    }
    if !config.experimental_execution {
        return write_json_response(
            stream,
            "423 Locked",
            &serde_json::json!({
                "detail": "capability probe requires experimental execution",
                "reason_code": "experimental_execution_disabled",
            }),
        );
    }
    let document: serde_json::Value = match serde_json::from_slice(body) {
        Ok(document) => document,
        Err(_) => {
            return write_json_response(
                stream,
                "400 Bad Request",
                &serde_json::json!({"detail": "invalid capability probe payload"}),
            )
        }
    };
    let object = match document.as_object() {
        Some(object) => object,
        None => {
            return write_json_response(
                stream,
                "400 Bad Request",
                &serde_json::json!({"detail": "invalid capability probe payload"}),
            )
        }
    };
    if object.get("approved").and_then(serde_json::Value::as_bool) != Some(true) {
        return write_json_response(
            stream,
            "428 Precondition Required",
            &serde_json::json!({
                "detail": "capability probe requires explicit approval",
                "reason_code": "probe_approval_required",
            }),
        );
    }
    let profile = match (
        object.get("provider").and_then(serde_json::Value::as_str),
        object.get("model").and_then(serde_json::Value::as_str),
        object.get("effort").and_then(serde_json::Value::as_str),
    ) {
        (Some("opencode-go"), Some(OPENCODE_GO_MODEL), Some("medium")) => {
            ExecutionProfile::OpenCodeGo
        }
        (Some("deepseek"), Some(DEEPSEEK_MODEL), Some("high")) => ExecutionProfile::DeepSeek,
        _ => {
            return write_json_response(
                stream,
                "400 Bad Request",
                &serde_json::json!({"detail": "unsupported capability probe profile"}),
            )
        }
    };
    match config.probe_capability(profile) {
        Ok(view) => write_json_response(
            stream,
            "200 OK",
            &serde_json::json!({
                "status": "passed",
                "provider": profile.provider(),
                "model": profile.model(),
                "effort": profile.effort(),
                "probe_status": probe_status_string(view.status),
                "checked_at_ms": view.checked_at_ms,
                "expires_at_ms": view.expires_at_ms,
                "max_output_tokens": profile.capability_probe_max_output_tokens(),
            }),
        ),
        Err(error) if error.kind() == io::ErrorKind::NotFound => write_json_response(
            stream,
            "503 Service Unavailable",
            &serde_json::json!({
                "detail": error.to_string(),
                "reason_code": "provider_not_configured",
            }),
        ),
        Err(error) if error.kind() == io::ErrorKind::PermissionDenied => write_json_response(
            stream,
            "423 Locked",
            &serde_json::json!({
                "detail": error.to_string(),
                "reason_code": "capability_probe_unavailable",
            }),
        ),
        Err(error) => write_json_response(
            stream,
            "502 Bad Gateway",
            &serde_json::json!({
                "detail": "capability probe failed",
                "reason_code": "capability_probe_failed",
                "error": error.to_string(),
            }),
        ),
    }
}

fn start_provider_turn(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    session_id: &str,
    document: &serde_json::Value,
) -> io::Result<()> {
    if !config.experimental_execution {
        return write_json_response(
            stream,
            "423 Locked",
            &serde_json::json!({
                "detail": "experimental execution is disabled",
                "reason_code": "experimental_execution_disabled"
            }),
        );
    }
    let object = document
        .as_object()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "invalid turn request"))?;
    let profile = match (
        object.get("provider").and_then(serde_json::Value::as_str),
        object.get("model").and_then(serde_json::Value::as_str),
        object.get("effort").and_then(serde_json::Value::as_str),
    ) {
        (Some("opencode-go"), Some(OPENCODE_GO_MODEL), Some("medium")) => {
            ExecutionProfile::OpenCodeGo
        }
        (Some("deepseek"), Some(DEEPSEEK_MODEL), Some("high")) => ExecutionProfile::DeepSeek,
        _ => {
            return write_json_response(
                stream,
                "400 Bad Request",
                &serde_json::json!({
                    "detail": "unsupported provider profile",
                    "profiles": [
                        {"provider": "opencode-go", "model": OPENCODE_GO_MODEL, "effort": "medium"},
                        {"provider": "deepseek", "model": DEEPSEEK_MODEL, "effort": "high"}
                    ]
                }),
            );
        }
    };
    let fallback_requested = match object.get("fallback") {
        None => false,
        Some(value) if value.as_str() == Some("deepseek") => {
            if profile != ExecutionProfile::OpenCodeGo {
                return write_json_response(
                    stream,
                    "400 Bad Request",
                    &serde_json::json!({"detail": "DeepSeek fallback is only valid for OpenCode Go"}),
                );
            }
            true
        }
        Some(_) => {
            return write_json_response(
                stream,
                "400 Bad Request",
                &serde_json::json!({"detail": "unsupported fallback profile"}),
            );
        }
    };
    let input = object
        .get("input")
        .and_then(serde_json::Value::as_str)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "invalid turn payload"))?;
    if input.len() > 1024 * 1024 || input.chars().any(|character| character == '\0') {
        return write_json_response(
            stream,
            "400 Bad Request",
            &serde_json::json!({"detail": "invalid turn payload"}),
        );
    }
    let turn_id = object
        .get("turn_id")
        .and_then(serde_json::Value::as_str)
        .filter(|value| !value.is_empty())
        .map(str::to_owned)
        .unwrap_or_else(|| format!("turn-{}-{}", std::process::id(), runtime_timestamp()));
    if turn_id.len() > 256
        || !turn_id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
    {
        return write_json_response(
            stream,
            "400 Bad Request",
            &serde_json::json!({"detail": "invalid turn id"}),
        );
    }
    let provider_configured = config
        .provider_secrets
        .read()
        .map_err(|_| io::Error::other("provider secret lock poisoned"))?
        .api_key(&profile.provider_id())
        .is_some();
    if !provider_configured {
        return write_json_response(
            stream,
            "503 Service Unavailable",
            &serde_json::json!({
                "detail": format!("{} provider is not configured", profile.provider()),
                "reason_code": "provider_not_configured"
            }),
        );
    }
    if fallback_requested
        && config
            .provider_secrets
            .read()
            .map_err(|_| io::Error::other("provider secret lock poisoned"))?
            .api_key(&ProviderId::DeepSeek)
            .is_none()
    {
        return write_json_response(
            stream,
            "503 Service Unavailable",
            &serde_json::json!({
                "detail": "DeepSeek fallback is not configured",
                "reason_code": "fallback_provider_not_configured"
            }),
        );
    }
    let probe = config.capability_probe_view(profile);
    if probe.status != codinal_providers::ProbeStatus::Passed {
        return write_json_response(
            stream,
            "503 Service Unavailable",
            &serde_json::json!({
                "detail": "selected provider capability probe is not current",
                "reason_code": probe.reason.as_deref().unwrap_or("capability_probe_required"),
                "probe_status": probe_status_string(probe.status),
            }),
        );
    }
    if fallback_requested {
        let fallback_probe = config.capability_probe_view(ExecutionProfile::DeepSeek);
        if fallback_probe.status != codinal_providers::ProbeStatus::Passed {
            return write_json_response(
                stream,
                "503 Service Unavailable",
                &serde_json::json!({
                    "detail": "fallback provider capability probe is not current",
                    "reason_code": fallback_probe.reason.as_deref().unwrap_or("fallback_capability_probe_required"),
                    "probe_status": probe_status_string(fallback_probe.status),
                }),
            );
        }
    }
    let Some(store) = config.runtime_store.as_ref() else {
        return write_json_response(
            stream,
            "503 Service Unavailable",
            &serde_json::json!({
                "detail": "runtime event store is unavailable",
                "reason_code": "runtime_store_unavailable"
            }),
        );
    };
    if let Some(receipt) = store.read_receipt(&turn_id)? {
        if receipt.session_id != session_id {
            return write_json_response(
                stream,
                "409 Conflict",
                &serde_json::json!({"detail": "turn id belongs to another session"}),
            );
        }
        return write_json_response(
            stream,
            "200 OK",
            &serde_json::json!({
                "ok": true,
                "accepted": false,
                "idempotent_replay": true,
                "session_id": session_id,
                "turn_id": turn_id,
                "state": receipt.outcome.get("status").and_then(serde_json::Value::as_str),
                "outcome": receipt.outcome,
                "receipt": {
                    "authoritative": true,
                    "created_at": receipt.created_at,
                    "reload": format!("/v1/sessions/{session_id}/turns")
                }
            }),
        );
    }
    if let Some(existing) = store.read_turn(&turn_id)? {
        if existing.session_id != session_id {
            return write_json_response(
                stream,
                "409 Conflict",
                &serde_json::json!({"detail": "turn id belongs to another session"}),
            );
        }
        return write_json_response(
            stream,
            "409 Conflict",
            &serde_json::json!({
                "detail": "turn already exists",
                "turn_id": turn_id,
                "state": existing.state
            }),
        );
    }
    if let Err(error) = config.set_activity_read(false) {
        return write_json_response(
            stream,
            "500 Internal Server Error",
            &serde_json::json!({"detail": error.to_string()}),
        );
    }
    let cancellation = Arc::new(AtomicBool::new(false));
    {
        let mut active = config
            .turn_cancellation
            .lock()
            .map_err(|_| io::Error::other("turn coordinator lock poisoned"))?;
        if active
            .insert(
                turn_id.clone(),
                ActiveTurn {
                    session_id: session_id.to_owned(),
                    cancellation: Arc::clone(&cancellation),
                },
            )
            .is_some()
        {
            return write_response(
                stream,
                "409 Conflict",
                "{\"detail\":\"turn is already active\"}",
                None,
            );
        }
    }
    if let Err(error) = store.create_turn(&turn_id, session_id).and_then(|_| {
        store
            .append_event(
                &turn_id,
                "created",
                serde_json::json!({
                    "session_id": session_id,
                    "provider": profile.provider(),
                    "model": profile.model(),
                    "effort": profile.effort(),
                    "fallback": fallback_requested,
                }),
            )
            .map(|_| ())
    }) {
        config
            .turn_cancellation
            .lock()
            .map_err(|_| io::Error::other("turn coordinator lock poisoned"))?
            .remove(&turn_id);
        return write_json_response(
            stream,
            "500 Internal Server Error",
            &serde_json::json!({"detail": error.to_string()}),
        );
    }
    let budget_reservation_id =
        (profile.uses_budget() || fallback_requested).then(|| budget_reservation_id(&turn_id));
    if let Some(reservation_id) = budget_reservation_id.as_ref() {
        if let Err(error) = store.reserve_budget(
            reservation_id,
            &turn_id,
            MAX_TURN_TOKENS,
            MAX_ACTIVE_RESERVED_TOKENS,
            MAX_DAILY_TOKENS,
        ) {
            let _ = store.transition_turn(&turn_id, "failed");
            let _ = store.append_event(
                &turn_id,
                "failed",
                serde_json::json!({
                    "session_id": session_id,
                    "reason": if error.kind() == io::ErrorKind::WouldBlock { "budget_exhausted" } else { "budget_reservation_failed" },
                    "max_reserved_tokens": MAX_TURN_TOKENS,
                }),
            );
            let _ = store.write_receipt(
                &turn_id,
                session_id,
                serde_json::json!({
                    "status": "failed",
                    "reason": if error.kind() == io::ErrorKind::WouldBlock { "budget_exhausted" } else { "budget_reservation_failed" },
                    "budget_reservation_id": reservation_id,
                }),
                0,
            );
            remove_active_turn(config, &turn_id);
            return write_json_response(
                stream,
                if error.kind() == io::ErrorKind::WouldBlock {
                    "429 Too Many Requests"
                } else {
                    "503 Service Unavailable"
                },
                &serde_json::json!({"detail": "token budget is unavailable"}),
            );
        }
    }
    let job = ProviderTurnJob {
        turn_id: turn_id.clone(),
        session_id: session_id.to_owned(),
        input: input.to_owned(),
        context_messages: Vec::new(),
        cancellation: Arc::clone(&cancellation),
        profile,
        fallback_requested,
        budget_reservation_id: budget_reservation_id.clone(),
    };

    if spawn_provider_turn_job(config, job).is_err() {
        let _ = store.transition_turn(&turn_id, "failed");
        let _ = store.append_event(
            &turn_id,
            "failed",
            serde_json::json!({
                "session_id": session_id,
                "reason": "turn_worker_unavailable"
            }),
        );
        let _ = store.write_receipt(
            &turn_id,
            session_id,
            serde_json::json!({
                "status": "failed",
                "reason": "turn_worker_unavailable",
                "budget_reservation_id": budget_reservation_id,
            }),
            0,
        );
        if let Some(reservation_id) = budget_reservation_id.as_ref() {
            let _ = store.reconcile_budget(reservation_id, None, "failed");
        }
        config
            .turn_cancellation
            .lock()
            .map_err(|_| io::Error::other("turn coordinator lock poisoned"))?
            .remove(&turn_id);
        return write_response(
            stream,
            "503 Service Unavailable",
            "{\"detail\":\"turn worker unavailable\"}",
            None,
        );
    }
    write_json_response(
        stream,
        "202 Accepted",
        &serde_json::json!({
            "ok": true,
            "accepted": true,
            "session_id": session_id,
            "turn_id": turn_id,
            "provider": profile.provider(),
            "model": profile.model(),
            "effort": profile.effort(),
            "fallback": fallback_requested.then_some("deepseek"),
            "budget_reservation_id": budget_reservation_id,
            "state": "streaming"
        }),
    )
}

fn spawn_provider_turn_job(config: &RuntimeConfig, job: ProviderTurnJob) -> io::Result<()> {
    let worker_config = config.clone();
    std::thread::Builder::new()
        .name("codinal-runtime-turn".to_owned())
        .spawn(move || {
            execute_provider_turn(&worker_config, job);
        })
        .map(|_| ())
        .map_err(|_| io::Error::other("turn worker unavailable"))
}

fn execute_provider_turn(config: &RuntimeConfig, job: ProviderTurnJob) {
    let turn_id = &job.turn_id;
    let session_id = &job.session_id;
    let input = &job.input;
    let cancellation = &job.cancellation;
    let profile = job.profile;
    let fallback_requested = job.fallback_requested;
    let budget_reservation_id = job.budget_reservation_id.as_deref();
    let Some(store) = config.runtime_store.as_ref() else {
        return;
    };
    let message_count = codinal_storage::read_session_messages(config.data_dir(), session_id)
        .map(|messages| messages.len() as i64)
        .unwrap_or_default();
    let _ = store.transition_turn(turn_id, "streaming");
    let _ = store.append_event(
        turn_id,
        "streaming",
        serde_json::json!({
            "session_id": session_id,
            "provider": profile.provider(),
            "endpoint": profile_endpoint(config, profile),
            "model": profile.model(),
            "effort": profile.effort(),
            "capability_snapshot": capability_snapshot_json(config, profile),
            "fallback": fallback_requested,
            "budget_reservation_id": budget_reservation_id,
        }),
    );
    if let Ok(prompt) = codinal_providers::PromptEnvelope::compile(
        "codinal.runtime.policy.v1",
        &builtin_tool_schemas(),
        Vec::new(),
        codinal_providers::CachePolicy::PreferStablePrefix,
    ) {
        let _ = store.append_event(
            turn_id,
            "prompt_compiled",
            serde_json::json!({
                "compiler": codinal_providers::prompt::PROMPT_COMPILER_VERSION,
                "stable_prefix_hash": prompt.stable_prefix_hash,
                "stable_prefix_bytes": prompt.stable_prefix_bytes().len(),
                "cache_policy": prompt.cache_policy.as_str(),
            }),
        );
    }
    let mut fallback_attempted = false;
    let started_at = Instant::now();
    let first_delta_ms = Cell::new(None);
    let mut emit_delta = |delta: &str| {
        if delta.is_empty() {
            return Ok(());
        }
        let elapsed_ms = u64::try_from(started_at.elapsed().as_millis()).unwrap_or(u64::MAX);
        let is_first_delta = first_delta_ms.get().is_none();
        let mut is_first_chunk = true;
        for_bounded_text_chunks(delta, MAX_ASSISTANT_DELTA_BYTES, |chunk| {
            let event = serde_json::json!({
                "session_id": session_id,
                "text": chunk,
                "first_delta_ms": is_first_chunk.then_some(elapsed_ms),
            });
            is_first_chunk = false;
            store.append_event(turn_id, "assistant_delta", event)?;
            Ok(())
        })?;
        if is_first_delta {
            first_delta_ms.set(Some(elapsed_ms));
        }
        Ok(())
    };
    let mut context_messages = job.context_messages.clone();
    let result = config.run_profile_turn_with_deltas(
        profile,
        session_id,
        input,
        cancellation,
        &context_messages,
        &mut emit_delta,
    );
    let (effective_profile, result) = if result.is_err()
        && profile == ExecutionProfile::OpenCodeGo
        && fallback_requested
        && !cancellation.load(Ordering::Acquire)
        && first_delta_ms.get().is_none()
    {
        fallback_attempted = true;
        (
            ExecutionProfile::DeepSeek,
            config.run_deepseek_turn_with_deltas(
                session_id,
                input,
                cancellation,
                &context_messages,
                &mut emit_delta,
            ),
        )
    } else {
        (profile, result)
    };
    let mut result = Some(result);
    let mut tool_rounds = 0;
    loop {
        let should_run_read_tool_loop = result.as_ref().is_some_and(|result| {
            result.as_ref().is_ok_and(|turn| {
                !turn.tool_calls.is_empty()
                    && turn.tool_calls.iter().all(|call| call.name == "read_file")
            })
        });
        if !should_run_read_tool_loop {
            break;
        }
        if tool_rounds >= MAX_TOOL_ROUNDS {
            result = Some(Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "tool round limit exceeded",
            )));
            break;
        }
        let turn = match result.take() {
            Some(Ok(turn)) => turn,
            _ => break,
        };
        let assistant_message = match provider_assistant_tool_message(&turn) {
            Ok(message) => message,
            Err(error) => {
                result = Some(Err(error));
                break;
            }
        };
        let proposal = serde_json::json!({
            "session_id": session_id,
            "tool_calls": turn
                .tool_calls
                .iter()
                .map(|call| {
                    serde_json::json!({
                        "id": call.id,
                        "name": call.name,
                        "arguments": call.arguments,
                    })
                })
                .collect::<Vec<_>>(),
        });
        if let Err(error) = store.append_event(turn_id, "tool_proposed", proposal) {
            result = Some(Err(error));
            break;
        }
        context_messages.push(assistant_message);
        let mut tool_error = None;
        for call in &turn.tool_calls {
            let (response, audit) = match execute_read_file_tool(config, session_id, call) {
                Ok(result) => result,
                Err(error) => {
                    tool_error = Some(error);
                    break;
                }
            };
            if let Err(error) = store.append_event(turn_id, "tool_result", audit) {
                tool_error = Some(error);
                break;
            }
            let content = match serde_json::to_string(&response) {
                Ok(content) if content.len() <= MAX_TOOL_RESULT_BYTES => content,
                Ok(_) => {
                    tool_error = Some(io::Error::new(
                        io::ErrorKind::InvalidData,
                        "read_file result exceeds limit",
                    ));
                    break;
                }
                Err(error) => {
                    tool_error = Some(io::Error::new(io::ErrorKind::InvalidData, error));
                    break;
                }
            };
            context_messages.push(serde_json::json!({
                "role": "tool",
                "tool_call_id": call.id,
                "content": content,
            }));
        }
        if let Some(error) = tool_error {
            result = Some(Err(error));
            break;
        }
        tool_rounds += 1;
        result = Some(config.run_profile_turn_with_deltas(
            effective_profile,
            session_id,
            input,
            cancellation,
            &context_messages,
            &mut emit_delta,
        ));
    }
    let result = result.expect("provider result is present");
    let budget_provider_attempted = effective_profile == ExecutionProfile::DeepSeek;
    match result {
        Ok(_turn) if cancellation.load(Ordering::Acquire) => {
            reconcile_turn_budget(
                store,
                budget_reservation_id,
                None,
                budget_provider_attempted,
                "interrupted",
            );
            finalize_owned_turn(
                store,
                config,
                turn_id,
                session_id,
                "interrupted",
                serde_json::json!({"reason": "cancellation"}),
                message_count,
            );
        }
        Ok(turn) => {
            let tool_event = serde_json::json!({
                "session_id": session_id,
                "text": turn.text,
                "tool_calls": turn.tool_calls.iter().map(|call| serde_json::json!({
                    "id": call.id,
                    "name": call.name,
                    "arguments": call.arguments,
                })).collect::<Vec<_>>(),
                "finish_reason": turn.finish_reason,
                "usage": turn
                    .usage
                    .as_ref()
                    .map(|usage| token_usage_json_for_profile(effective_profile, usage)),
                "provider": effective_profile.provider(),
                "model": effective_profile.model(),
                "effort": effective_profile.effort(),
                "capability_snapshot": capability_snapshot_json(config, effective_profile),
                "fallback_attempted": fallback_attempted,
                "first_delta_ms": first_delta_ms.get(),
            });
            let _ = store.append_event(turn_id, "assistant", tool_event);
            let resume = turn
                .tool_calls
                .iter()
                .all(|call| call.name == "apply_patch")
                .then(|| ProviderTurnResume {
                    provider: effective_profile.provider().to_owned(),
                    model: effective_profile.model().to_owned(),
                    effort: effective_profile.effort().to_owned(),
                    input: input.to_owned(),
                    context_messages: context_messages.clone(),
                    assistant_text: turn.text.clone(),
                    tool_calls: turn
                        .tool_calls
                        .iter()
                        .map(|call| ProviderResumeToolCall {
                            id: call.id.clone(),
                            name: call.name.clone(),
                            arguments: call.arguments.clone(),
                        })
                        .collect(),
                    fallback_requested,
                    budget_reservation_id: job.budget_reservation_id.clone(),
                });
            match config.ingest_provider_turn_for_turn_with_resume(
                turn_id,
                session_id,
                turn.clone(),
                resume.as_ref(),
            ) {
                Ok(ingress) if !ingress.pending_approval_ids.is_empty() => {
                    let _ = config.set_activity_read(false);
                    let _ = store.transition_turn(turn_id, "awaiting_approval");
                    let _ = store.append_event(
                        turn_id,
                        "awaiting_approval",
                        serde_json::json!({
                            "session_id": session_id,
                            "approval_ids": ingress.pending_approval_ids,
                            "allowed_read_tool_call_ids": ingress.allowed_read_tool_call_ids,
                            "rejected_tool_call_ids": ingress.rejected_tool_call_ids,
                        }),
                    );
                    remove_active_turn(config, turn_id);
                }
                Ok(ingress) => {
                    reconcile_turn_budget(
                        store,
                        budget_reservation_id,
                        Some(&turn),
                        budget_provider_attempted,
                        "completed",
                    );
                    finalize_owned_turn(
                        store,
                        config,
                        turn_id,
                        session_id,
                        "completed",
                        serde_json::json!({
                            "text": turn.text,
                            "finish_reason": turn.finish_reason,
                            "usage": turn
                                .usage
                                .as_ref()
                                .map(|usage| token_usage_json_for_profile(effective_profile, usage)),
                            "provider": effective_profile.provider(),
                            "endpoint": profile_endpoint(config, effective_profile),
                            "model": effective_profile.model(),
                            "effort": effective_profile.effort(),
                            "capability_snapshot": capability_snapshot_json(config, effective_profile),
                            "fallback_attempted": fallback_attempted,
                            "first_delta_ms": first_delta_ms.get(),
                            "first_delta_seen": first_delta_ms.get().is_some(),
                            "budget_reservation_id": budget_reservation_id,
                            "allowed_read_tool_call_ids": ingress.allowed_read_tool_call_ids,
                            "rejected_tool_call_ids": ingress.rejected_tool_call_ids,
                        }),
                        message_count,
                    );
                }
                Err(_) => {
                    reconcile_turn_budget(
                        store,
                        budget_reservation_id,
                        None,
                        budget_provider_attempted,
                        "failed",
                    );
                    finalize_owned_turn(
                        store,
                        config,
                        turn_id,
                        session_id,
                        "failed",
                        serde_json::json!({"reason": "policy_rejected"}),
                        message_count,
                    );
                }
            }
        }
        Err(error) if error.kind() == io::ErrorKind::Interrupted => {
            reconcile_turn_budget(
                store,
                budget_reservation_id,
                None,
                budget_provider_attempted,
                "interrupted",
            );
            finalize_owned_turn(
                store,
                config,
                turn_id,
                session_id,
                "interrupted",
                serde_json::json!({"reason": "cancellation"}),
                message_count,
            );
        }
        Err(_) => {
            reconcile_turn_budget(
                store,
                budget_reservation_id,
                None,
                budget_provider_attempted,
                "failed",
            );
            finalize_owned_turn(
                store,
                config,
                turn_id,
                session_id,
                "failed",
                serde_json::json!({"reason": "provider_request_failed"}),
                message_count,
            );
        }
    }
}

fn for_bounded_text_chunks<F>(text: &str, max_bytes: usize, mut on_chunk: F) -> io::Result<()>
where
    F: FnMut(&str) -> io::Result<()>,
{
    if max_bytes == 0 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "assistant delta limit must be positive",
        ));
    }
    let mut start = 0;
    while start < text.len() {
        let mut end = start;
        for (offset, character) in text[start..].char_indices() {
            let next = start + offset + character.len_utf8();
            if next.saturating_sub(start) > max_bytes && end > start {
                break;
            }
            end = next;
            if next.saturating_sub(start) >= max_bytes {
                break;
            }
        }
        if end == start {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "assistant delta could not be bounded",
            ));
        }
        on_chunk(&text[start..end])?;
        start = end;
    }
    Ok(())
}

fn profile_endpoint(config: &RuntimeConfig, profile: ExecutionProfile) -> &str {
    match profile {
        ExecutionProfile::OpenCodeGo => &config.opencode_endpoint,
        ExecutionProfile::DeepSeek => &config.deepseek_endpoint,
    }
}

fn model_catalogue_document() -> serde_json::Value {
    serde_json::json!({
        "revision": BUNDLED_CATALOGUE_REVISION,
        "metadata": {
            "source": codinal_providers::catalogue::MODELS_DEV_METADATA_SOURCE,
            "revision": codinal_providers::MODELS_DEV_API_SHA256,
            "status": "synchronized",
        },
        "entries": serde_json::to_value(BUNDLED_MODEL_CATALOGUE)
            .unwrap_or_else(|_| serde_json::Value::Array(Vec::new())),
    })
}

fn probe_status_string(status: codinal_providers::ProbeStatus) -> &'static str {
    match status {
        codinal_providers::ProbeStatus::NotRun => "not_run",
        codinal_providers::ProbeStatus::Passed => "passed",
        codinal_providers::ProbeStatus::Failed => "failed",
    }
}

fn capability_snapshot_json(
    config: &RuntimeConfig,
    profile: ExecutionProfile,
) -> serde_json::Value {
    let probe_status = config.capability_probe_view(profile).status;
    codinal_providers::catalogue::snapshot(
        profile.provider(),
        profile.model(),
        profile.effort(),
        probe_status,
    )
    .and_then(|snapshot| serde_json::to_value(snapshot).ok())
    .unwrap_or_else(|| {
        serde_json::json!({
            "provider": profile.provider(),
            "model": profile.model(),
            "requested_effort": profile.effort(),
            "probe_status": "unknown",
        })
    })
}

fn budget_reservation_id(turn_id: &str) -> String {
    let digest = Sha256::digest(turn_id.as_bytes());
    format!("budget-{:x}", digest)
}

fn reconcile_turn_budget(
    store: &codinal_storage::RuntimeStore,
    reservation_id: Option<&str>,
    turn: Option<&AssistantTurn>,
    provider_attempted: bool,
    terminal_status: &str,
) {
    let Some(reservation_id) = reservation_id else {
        return;
    };
    let usage = turn.and_then(|turn| turn.usage.as_ref());
    let actual_tokens = usage.and_then(|usage| i64::try_from(usage.total_tokens).ok());
    let state = if !provider_attempted {
        "released"
    } else if actual_tokens.is_some()
        && matches!(terminal_status, "completed" | "awaiting_approval")
    {
        "settled"
    } else if matches!(terminal_status, "completed" | "awaiting_approval") {
        "settled_unknown"
    } else {
        "failed"
    };
    let _ = store.reconcile_budget(reservation_id, actual_tokens, state);
}

fn token_usage_json_for_profile(
    profile: ExecutionProfile,
    usage: &codinal_providers::TokenUsage,
) -> serde_json::Value {
    let provider_usage = usage.provider_usage.as_ref().map(|usage| {
        serde_json::json!({
            "input_tokens": usage.input_tokens,
            "cache_read_tokens": usage.cache_read_tokens,
            "cache_write_tokens": usage.cache_write_tokens,
            "prompt_cache_hit_tokens": usage.prompt_cache_hit_tokens,
            "prompt_cache_miss_tokens": usage.prompt_cache_miss_tokens,
            "output_tokens": usage.output_tokens,
            "first_delta_ms": usage.first_delta_ms,
            "total_latency_ms": usage.total_latency_ms,
            "cost": usage.cost.as_str(),
        })
    });
    let cost_input_tokens = usage.provider_usage.as_ref().and_then(|provider_usage| {
        if profile == ExecutionProfile::DeepSeek {
            provider_usage
                .prompt_cache_miss_tokens
                .or(provider_usage.input_tokens)
        } else {
            provider_usage.input_tokens
        }
    });
    let estimated_cost_microusd = usage.provider_usage.as_ref().and_then(|usage| {
        codinal_providers::estimate_cost_microusd(
            profile.provider(),
            profile.model(),
            cost_input_tokens,
            usage.cache_read_tokens,
            usage.cache_write_tokens,
            usage.output_tokens,
        )
    });
    serde_json::json!({
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "provider": provider_usage,
        "cost_estimate": {
            "classification": estimated_cost_microusd
                .map_or(usage.provider_usage.as_ref().map_or("unavailable", |usage| usage.cost.as_str()), |_| "codinal_estimated"),
            "usd_microusd": estimated_cost_microusd,
            "input_tokens": cost_input_tokens,
            "cache_read_tokens": usage.provider_usage.as_ref().and_then(|usage| usage.cache_read_tokens),
            "output_tokens": usage.provider_usage.as_ref().and_then(|usage| usage.output_tokens),
            "models_dev_revision": codinal_providers::MODELS_DEV_API_SHA256,
        },
    })
}

fn finalize_owned_turn(
    store: &codinal_storage::RuntimeStore,
    config: &RuntimeConfig,
    turn_id: &str,
    session_id: &str,
    status: &str,
    outcome: serde_json::Value,
    message_count: i64,
) {
    let _ = store.transition_turn(turn_id, status);
    let mut event = outcome.clone();
    if let Some(object) = event.as_object_mut() {
        object.insert(
            "session_id".to_owned(),
            serde_json::Value::String(session_id.to_owned()),
        );
        object.insert(
            "status".to_owned(),
            serde_json::Value::String(status.to_owned()),
        );
    }
    let _ = store.append_event(turn_id, status, event.clone());
    let _ = store.write_receipt(turn_id, session_id, event, message_count);
    remove_active_turn(config, turn_id);
}

fn remove_active_turn(config: &RuntimeConfig, turn_id: &str) {
    if let Ok(mut active) = config.turn_cancellation.lock() {
        active.remove(turn_id);
    }
}

fn interrupt_owned_turn(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    session_id: &str,
    body: &[u8],
) -> io::Result<()> {
    if config.runtime_store.is_none() {
        return write_response(
            stream,
            "501 Not Implemented",
            "{\"detail\":\"session interrupt is not implemented in rust runtime\"}",
            None,
        );
    }
    let requested_turn_id = if body.is_empty() {
        None
    } else {
        let document = match serde_json::from_slice::<serde_json::Value>(body) {
            Ok(document) => document,
            Err(_) => {
                return write_response(
                    stream,
                    "400 Bad Request",
                    "{\"detail\":\"invalid interrupt request\"}",
                    None,
                );
            }
        };
        document
            .get("turn_id")
            .and_then(serde_json::Value::as_str)
            .map(str::to_owned)
    };
    let active = config
        .turn_cancellation
        .lock()
        .map_err(|_| io::Error::other("turn coordinator lock poisoned"))?
        .iter()
        .find(|(turn_id, active)| {
            active.session_id == session_id
                && requested_turn_id
                    .as_deref()
                    .is_none_or(|requested| requested == turn_id.as_str())
        })
        .map(|(turn_id, active)| (turn_id.clone(), active.cancellation.clone()));
    let Some((turn_id, cancellation)) = active else {
        return write_response(
            stream,
            "501 Not Implemented",
            "{\"detail\":\"session interrupt is not implemented in rust runtime\"}",
            None,
        );
    };
    cancellation.store(true, Ordering::Release);
    write_json_response(
        stream,
        "202 Accepted",
        &serde_json::json!({
            "accepted": true,
            "ok": true,
            "session_id": session_id,
            "turn_id": turn_id
        }),
    )
}

fn runtime_timestamp() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_micros()
}

fn now_ms() -> u128 {
    runtime_timestamp() / 1_000
}

fn approval_expiry_from_request(request: &str) -> Option<u128> {
    let value: serde_json::Value = serde_json::from_str(request).ok()?;
    value
        .get("expires_at_ms")
        .and_then(serde_json::Value::as_u64)
        .map(u128::from)
        .or_else(|| {
            value
                .get("arguments")
                .and_then(serde_json::Value::as_object)
                .and_then(|arguments| arguments.get(APPROVAL_EXPIRY_KEY))
                .and_then(serde_json::Value::as_u64)
                .map(u128::from)
        })
}

fn approval_request_is_expired(request: &str) -> bool {
    approval_expiry_from_request(request).is_some_and(|expires_at_ms| expires_at_ms <= now_ms())
}

fn expire_durable_approval(
    config: &RuntimeConfig,
    broker: &mut ApprovalBroker,
    record: &codinal_storage::ApprovalRecord,
) -> io::Result<bool> {
    if record.state != "pending" || !approval_request_is_expired(&record.request) {
        return Ok(false);
    }
    if !broker.resolve(&record.session_id, &record.approval_id) {
        return Ok(false);
    }
    let Some(store) = config.runtime_store.as_ref() else {
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            "runtime store unavailable",
        ));
    };
    if let Some(audit) = config.audit_ledger.as_ref() {
        audit.record(codinal_policy::AuditLedgerInput {
            domain: "approval".to_owned(),
            action: "expire".to_owned(),
            actor: "system".to_owned(),
            subject: record.approval_id.clone(),
            payload: serde_json::json!({"reason": "approval_expired"}),
        })?;
    }
    store.put_approval(&codinal_storage::ApprovalRecord {
        approval_id: record.approval_id.clone(),
        turn_id: record.turn_id.clone(),
        session_id: record.session_id.clone(),
        request: record.request.clone(),
        state: "expired".to_owned(),
    })?;
    fail_provider_resume_budget(config, record);
    let _ = store.transition_turn(&record.turn_id, "failed");
    let _ = store.append_event(
        &record.turn_id,
        "approval_expired",
        serde_json::json!({
            "approval_id": record.approval_id,
            "session_id": record.session_id,
            "reason": "approval_expired",
            "state": "failed",
        }),
    );
    let _ = store.write_receipt(
        &record.turn_id,
        &record.session_id,
        serde_json::json!({
            "status": "failed",
            "reason": "approval_expired",
            "approval_id": record.approval_id,
        }),
        0,
    );
    Ok(true)
}

fn parse_workspace_query(query: &str) -> Result<Option<String>, ()> {
    if query.is_empty() {
        return Ok(None);
    }
    let encoded = query.strip_prefix("?workspace=").ok_or(())?;
    if encoded.is_empty() || encoded.contains('&') {
        return Err(());
    }
    let bytes = percent_decode(encoded)?;
    let workspace = String::from_utf8(bytes).map_err(|_| ())?;
    if workspace.len() > 4096 || !Path::new(&workspace).is_absolute() {
        return Err(());
    }
    Ok(Some(workspace))
}

fn parse_session_search_query(query: &str) -> Result<(String, usize), ()> {
    if !query.starts_with('?') || query == "?" {
        return Err(());
    }
    let encoded = query.strip_prefix('?').ok_or(())?;
    let mut q: Option<String> = None;
    let mut limit = 50usize;
    for pair in encoded.split('&') {
        if pair.is_empty() {
            return Err(());
        }
        let mut split = pair.splitn(2, '=');
        let key = split.next().ok_or(())?;
        let encoded_value = split.next().ok_or(())?;
        let value = String::from_utf8(percent_decode(encoded_value)?).map_err(|_| ())?;
        match key {
            "q" => {
                if q.is_some() {
                    return Err(());
                }
                q = Some(value);
            }
            "limit" => {
                if !value.bytes().all(|byte| byte.is_ascii_digit()) {
                    return Err(());
                }
                let parsed = value.parse::<usize>().map_err(|_| ())?;
                if !(1..=100).contains(&parsed) {
                    return Err(());
                }
                limit = parsed;
            }
            _ => return Err(()),
        }
    }
    let q = q.ok_or(())?;
    let q = q.trim().to_string();
    if !(1..=256).contains(&q.len()) {
        return Err(());
    }
    if q.chars().any(|ch| ch == '\0') {
        return Err(());
    }
    Ok((q, limit))
}

fn parse_event_query(query: &str) -> Result<(Option<String>, usize), ()> {
    if query.is_empty() {
        return Ok((None, 100));
    }
    let mut cursor = None;
    let mut limit = 100;
    for pair in query.strip_prefix('?').ok_or(())?.split('&') {
        let (key, encoded_value) = pair.split_once('=').ok_or(())?;
        let value = String::from_utf8(percent_decode(encoded_value)?).map_err(|_| ())?;
        match key {
            "after" if cursor.is_none() => {
                if value.len() > 1024 {
                    return Err(());
                }
                cursor = Some(value);
            }
            "limit" if value.bytes().all(|byte| byte.is_ascii_digit()) => {
                limit = value.parse::<usize>().map_err(|_| ())?;
                if !(1..=500).contains(&limit) {
                    return Err(());
                }
            }
            _ => return Err(()),
        }
    }
    Ok((cursor, limit))
}

fn percent_decode(value: &str) -> Result<Vec<u8>, ()> {
    let bytes = value.as_bytes();
    let mut decoded = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        if bytes[index] == b'%' {
            let pair = bytes.get(index + 1..index + 3).ok_or(())?;
            let text = std::str::from_utf8(pair).map_err(|_| ())?;
            decoded.push(u8::from_str_radix(text, 16).map_err(|_| ())?);
            index += 3;
        } else if bytes[index] == b'+' {
            decoded.push(b' ');
            index += 1;
        } else {
            decoded.push(bytes[index]);
            index += 1;
        }
    }
    Ok(decoded)
}

fn valid_bearer(value: &str, token: &[u8]) -> bool {
    let Some(candidate) = value.strip_prefix("Bearer ") else {
        return false;
    };
    let candidate = candidate.as_bytes();
    if candidate.is_empty() || candidate.contains(&b' ') || candidate.len() != token.len() {
        return false;
    }
    candidate
        .iter()
        .zip(token)
        .fold(0_u8, |difference, (left, right)| {
            difference | (left ^ right)
        })
        == 0
}

fn serve_operation_route(
    stream: &mut TcpStream,
    config: &RuntimeConfig,
    request: &RequestHead,
) -> io::Result<bool> {
    if request.path != "/v1/operations" && !request.path.starts_with("/v1/operations/") {
        return Ok(false);
    }
    let Some(ledger) = config.operation_ledger.as_ref() else {
        write_json_response(
            stream,
            "423 Locked",
            &serde_json::json!({
                "detail": "operation protocol is unavailable",
                "schema": OPERATION_SCHEMA,
                "reason_code": "operation_protocol_unavailable",
            }),
        )?;
        return Ok(true);
    };

    if request.method == "POST" && request.path == "/v1/operations" {
        let envelope: OperationEnvelope = match serde_json::from_slice(&request.body) {
            Ok(envelope) => envelope,
            Err(error) => {
                write_json_response(
                    stream,
                    "400 Bad Request",
                    &serde_json::json!({
                        "detail": "invalid operation envelope",
                        "reason": error.to_string(),
                    }),
                )?;
                return Ok(true);
            }
        };
        let operation_id = envelope.operation_id.clone();
        let capability = envelope.capability.clone();
        let result = ledger.submit(envelope);
        if let Ok(ack) = &result {
            if ack.state == OperationState::Accepted
                && !ack.replayed
                && is_supported_operation_capability(&capability)
            {
                spawn_operation_worker(config, operation_id);
            }
        }
        return write_operation_ack(stream, result).map(|_| true);
    }

    let Some(rest) = request.path.strip_prefix("/v1/operations/") else {
        return write_operation_error(
            stream,
            io::Error::new(io::ErrorKind::InvalidInput, "invalid operation route"),
        )
        .map(|_| true);
    };
    if rest.is_empty() {
        return write_operation_error(
            stream,
            io::Error::new(io::ErrorKind::InvalidInput, "operation id is missing"),
        )
        .map(|_| true);
    }

    if request.method == "GET" {
        let (operation_id, query) = rest.split_once('?').unwrap_or((rest, ""));
        if !valid_operation_route_id(operation_id) {
            return write_operation_error(
                stream,
                io::Error::new(io::ErrorKind::InvalidInput, "invalid operation id"),
            )
            .map(|_| true);
        }
        let after = match parse_operation_after(query) {
            Ok(after) => after,
            Err(error) => return write_operation_error(stream, error).map(|_| true),
        };
        return match ledger.resume(operation_id, after) {
            Ok(resume) => write_json_response(stream, "200 OK", &resume),
            Err(error) => write_operation_error(stream, error),
        }
        .map(|_| true);
    }

    if request.method == "POST" {
        if let Some(operation_id) = rest.strip_suffix("/cancel") {
            if !valid_operation_route_id(operation_id) {
                return write_operation_error(
                    stream,
                    io::Error::new(io::ErrorKind::InvalidInput, "invalid operation id"),
                )
                .map(|_| true);
            }
            if let Some(gateway) = config.tool_gateway.as_ref() {
                gateway.interrupt(operation_id);
            }
            return write_operation_ack(stream, ledger.request_cancel(operation_id)).map(|_| true);
        }
    }

    write_operation_error(
        stream,
        io::Error::new(io::ErrorKind::InvalidInput, "unsupported operation route"),
    )
    .map(|_| true)
}

fn write_operation_ack(stream: &mut TcpStream, result: io::Result<OperationAck>) -> io::Result<()> {
    match result {
        Ok(ack) => write_json_response(
            stream,
            if ack.state.is_terminal() {
                "200 OK"
            } else {
                "202 Accepted"
            },
            &ack,
        ),
        Err(error) => write_operation_error(stream, error),
    }
}

fn write_operation_error(stream: &mut TcpStream, error: io::Error) -> io::Result<()> {
    write_json_response(
        stream,
        operation_error_status(&error),
        &serde_json::json!({
            "detail": error.to_string(),
            "reason_code": operation_error_reason(&error),
        }),
    )
}

fn operation_error_status(error: &io::Error) -> &'static str {
    match error.kind() {
        io::ErrorKind::InvalidInput | io::ErrorKind::InvalidData => "400 Bad Request",
        io::ErrorKind::NotFound => "404 Not Found",
        io::ErrorKind::AlreadyExists => "409 Conflict",
        io::ErrorKind::WouldBlock => "429 Too Many Requests",
        _ => "500 Internal Server Error",
    }
}

fn operation_error_reason(error: &io::Error) -> &'static str {
    match error.kind() {
        io::ErrorKind::InvalidInput | io::ErrorKind::InvalidData => "invalid_operation",
        io::ErrorKind::NotFound => "operation_not_found",
        io::ErrorKind::AlreadyExists => "operation_conflict",
        io::ErrorKind::WouldBlock => "operation_queue_full",
        _ => "operation_protocol_error",
    }
}

fn parse_operation_after(query: &str) -> io::Result<u64> {
    if query.is_empty() {
        return Ok(0);
    }
    let value = query
        .strip_prefix("after=")
        .filter(|value| !value.is_empty())
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "invalid operation cursor"))?;
    value
        .parse::<u64>()
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "invalid operation cursor"))
}

fn valid_operation_route_id(value: &str) -> bool {
    codinal_tools::operation::validate_operation_id(value).is_ok()
}

const OPERATION_GIT_STATUS: &str = "git.status";
const OPERATION_GIT_DIFF: &str = "git.diff";
const OPERATION_GIT_CREATE_WORKTREE: &str = "git.create_worktree";
const OPERATION_GIT_REMOVE_WORKTREE: &str = "git.remove_worktree";

fn is_supported_operation_capability(capability: &str) -> bool {
    matches!(
        capability,
        OPERATION_GIT_STATUS
            | OPERATION_GIT_DIFF
            | OPERATION_GIT_CREATE_WORKTREE
            | OPERATION_GIT_REMOVE_WORKTREE
    )
}

fn spawn_operation_worker(config: &RuntimeConfig, operation_id: String) {
    let config = config.clone();
    let _ = std::thread::Builder::new()
        .name("codinal-operation-worker".to_owned())
        .spawn(move || run_operation_worker(&config, &operation_id));
}

fn run_operation_worker(config: &RuntimeConfig, operation_id: &str) {
    let Some(ledger) = config.operation_ledger.as_ref() else {
        return;
    };
    let work = match ledger.claim_operation(operation_id) {
        Ok(Some(work)) => work,
        Ok(None) | Err(_) => return,
    };

    if let Err(error) = ledger.publish_progress(
        operation_id,
        1,
        serde_json::json!({
            "stage": "started",
            "capability": work.envelope.capability.as_str(),
        }),
    ) {
        finish_operation_worker(
            ledger,
            operation_id,
            OperationState::Failed,
            serde_json::json!({
                "reason": "operation_start_progress_failed",
                "detail": error.to_string(),
            }),
        );
        return;
    }
    if ledger.cancellation_requested(operation_id).unwrap_or(false) {
        finish_operation_worker(
            ledger,
            operation_id,
            OperationState::Cancelled,
            serde_json::json!({"reason": "cancelled_before_execution"}),
        );
        return;
    }
    match ledger.execution_allowed(operation_id) {
        Ok(true) => {}
        Ok(false) => {
            finish_operation_worker(
                ledger,
                operation_id,
                OperationState::Failed,
                serde_json::json!({"reason": "operation_not_executable"}),
            );
            return;
        }
        Err(error) => {
            finish_operation_worker(
                ledger,
                operation_id,
                OperationState::Failed,
                serde_json::json!({
                    "reason": "operation_execution_boundary_failed",
                    "detail": error.to_string(),
                }),
            );
            return;
        }
    }

    let result = match operation_git_request(&work.envelope) {
        Ok(request) => match config.tool_gateway.as_ref() {
            Some(gateway) => gateway.execute_git(request),
            None => Err(io::Error::new(
                io::ErrorKind::NotFound,
                "operation tool gateway is unavailable",
            )),
        },
        Err(error) => Err(error),
    };

    let (terminal_state, outcome) = match result {
        Ok(execution) => {
            let terminal_state = match execution.receipt.status {
                codinal_tools::ToolStatus::Succeeded => OperationState::Succeeded,
                codinal_tools::ToolStatus::Interrupted => OperationState::Cancelled,
                codinal_tools::ToolStatus::Pending
                | codinal_tools::ToolStatus::Failed
                | codinal_tools::ToolStatus::Rejected => OperationState::Failed,
            };
            (
                terminal_state,
                serde_json::json!({"tool_execution": operation_execution_value(execution)}),
            )
        }
        Err(error) => (
            OperationState::Failed,
            serde_json::json!({
                "reason": "operation_execution_failed",
                "detail": error.to_string(),
            }),
        ),
    };
    if let Err(error) = ledger.publish_progress(
        operation_id,
        2,
        serde_json::json!({
            "stage": "finished",
            "state": terminal_state,
        }),
    ) {
        finish_operation_worker(
            ledger,
            operation_id,
            OperationState::Failed,
            serde_json::json!({
                "reason": "operation_finish_progress_failed",
                "detail": error.to_string(),
            }),
        );
        return;
    }
    finish_operation_worker(ledger, operation_id, terminal_state, outcome);
}

fn finish_operation_worker(
    ledger: &codinal_tools::OperationLedger,
    operation_id: &str,
    terminal_state: OperationState,
    outcome: serde_json::Value,
) {
    let cancelled = ledger.cancellation_requested(operation_id).unwrap_or(false);
    let terminal_state = if cancelled {
        OperationState::Cancelled
    } else {
        terminal_state
    };
    let _ = ledger.finish(operation_id, terminal_state, outcome);
}

fn operation_git_request(envelope: &OperationEnvelope) -> io::Result<codinal_tools::GitRequest> {
    let payload: OperationGitPayload = serde_json::from_value(envelope.payload.clone())
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error.to_string()))?;
    let operation = match envelope.capability.as_str() {
        OPERATION_GIT_STATUS => codinal_tools::GitOperation::Status,
        OPERATION_GIT_DIFF => codinal_tools::GitOperation::Diff {
            path: payload.path.map(PathBuf::from),
        },
        OPERATION_GIT_CREATE_WORKTREE => {
            let path = payload.path.ok_or_else(|| {
                io::Error::new(
                    io::ErrorKind::InvalidInput,
                    "worktree path and revision are required",
                )
            })?;
            let revision = payload.revision.ok_or_else(|| {
                io::Error::new(
                    io::ErrorKind::InvalidInput,
                    "worktree path and revision are required",
                )
            })?;
            codinal_tools::GitOperation::CreateWorktree {
                path: PathBuf::from(path),
                revision,
            }
        }
        OPERATION_GIT_REMOVE_WORKTREE => {
            let path = payload.path.ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidInput, "worktree path is required")
            })?;
            codinal_tools::GitOperation::RemoveWorktree {
                path: PathBuf::from(path),
                force: payload.force,
            }
        }
        _ => {
            return Err(io::Error::new(
                io::ErrorKind::Unsupported,
                "unsupported operation capability",
            ));
        }
    };
    Ok(codinal_tools::GitRequest {
        operation_id: envelope.operation_id.clone(),
        repo: PathBuf::from(payload.repo),
        operation,
        approval_id: payload.approval_id,
        timeout_ms: payload.timeout_ms.unwrap_or(30_000),
    })
}

struct RequestHead {
    method: String,
    path: String,
    headers: Vec<(String, Zeroizing<String>)>,
    body: Zeroizing<Vec<u8>>,
}

impl Drop for RequestHead {
    fn drop(&mut self) {
        for (_, value) in &mut self.headers {
            value.zeroize();
        }
        self.body.zeroize();
    }
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct CreateSessionRequest {
    workspace: String,
    #[serde(default)]
    title: Option<String>,
    #[serde(default)]
    model: Option<String>,
    #[serde(default)]
    mode: Option<String>,
    #[serde(default)]
    origin: Option<String>,
    #[serde(default)]
    origin_label: Option<String>,
    #[serde(default)]
    origin_session_id: Option<String>,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct UpdateSessionRequest {
    #[serde(default)]
    title: Option<String>,
    #[serde(default)]
    pinned: Option<bool>,
    #[serde(default)]
    archived: Option<bool>,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct CreateProjectRequest {
    name: String,
    #[serde(default)]
    roots: Vec<String>,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct UpdateProjectRequest {
    name: String,
    #[serde(default)]
    roots: Vec<String>,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct ProjectPinnedRequest {
    pinned: bool,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct AttachSourceRequest {
    path: String,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct ShellToolRequest {
    operation_id: String,
    #[serde(default)]
    cwd: String,
    program: String,
    #[serde(default)]
    args: Vec<String>,
    approval_id: Option<String>,
    #[serde(default)]
    timeout_ms: Option<u64>,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct GitToolRequest {
    operation_id: String,
    #[serde(default)]
    repo: String,
    operation: String,
    #[serde(default)]
    path: Option<String>,
    #[serde(default)]
    revision: Option<String>,
    #[serde(default)]
    force: bool,
    approval_id: Option<String>,
    #[serde(default)]
    timeout_ms: Option<u64>,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct OperationGitPayload {
    #[serde(default)]
    repo: String,
    #[serde(default)]
    path: Option<String>,
    #[serde(default)]
    revision: Option<String>,
    #[serde(default)]
    force: bool,
    approval_id: Option<String>,
    #[serde(default)]
    timeout_ms: Option<u64>,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct McpToolRequest {
    operation_id: String,
    server_id: String,
    program: String,
    #[serde(default)]
    args: Vec<String>,
    method: String,
    #[serde(default = "empty_json_object")]
    params: serde_json::Value,
    approval_id: Option<String>,
    #[serde(default)]
    timeout_ms: Option<u64>,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct ToolApprovalRequest {
    approval_id: String,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct ToolInterruptRequest {
    operation_id: String,
}

fn empty_json_object() -> serde_json::Value {
    serde_json::json!({})
}

fn tool_execution_value(execution: codinal_tools::ToolExecution) -> serde_json::Value {
    serde_json::json!({
        "receipt": execution.receipt,
        "stdout": String::from_utf8_lossy(&execution.stdout),
        "stderr": String::from_utf8_lossy(&execution.stderr),
        "response": execution.response,
    })
}

fn operation_execution_value(execution: codinal_tools::ToolExecution) -> serde_json::Value {
    serde_json::json!({
        "receipt": execution.receipt,
        "response": execution.response,
    })
}

fn tool_error_status(error: &io::Error) -> &'static str {
    match error.kind() {
        io::ErrorKind::InvalidInput | io::ErrorKind::InvalidData => "400 Bad Request",
        io::ErrorKind::PermissionDenied => "403 Forbidden",
        io::ErrorKind::NotFound => "404 Not Found",
        _ => "500 Internal Server Error",
    }
}

fn read_headers(stream: &mut TcpStream) -> io::Result<RequestHead> {
    let mut request = Zeroizing::new(Vec::with_capacity(1024));
    let mut buffer = Zeroizing::new([0_u8; 1024]);
    loop {
        let read = stream.read(&mut *buffer)?;
        if read == 0 {
            return Err(io::Error::new(
                io::ErrorKind::UnexpectedEof,
                "incomplete request headers",
            ));
        }
        request.extend_from_slice(&buffer[..read]);
        if request.windows(4).any(|window| window == b"\r\n\r\n") {
            break;
        }
        if request.len() > MAX_REQUEST_BYTES {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "request headers exceed limit",
            ));
        }
    }
    let end = request
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .expect("header delimiter checked");
    let text = std::str::from_utf8(&request[..end])
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "request headers are not UTF-8"))?;
    let mut lines = text.split("\r\n");
    let mut request_line = lines.next().unwrap_or_default().split_ascii_whitespace();
    let method = request_line.next().unwrap_or_default().to_owned();
    let path = request_line.next().unwrap_or_default().to_owned();
    let version = request_line.next().unwrap_or_default();
    if method.is_empty()
        || path.is_empty()
        || !matches!(version, "HTTP/1.0" | "HTTP/1.1")
        || request_line.next().is_some()
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "invalid request line",
        ));
    }
    let headers = lines
        .map(|line| {
            let (name, value) = line.split_once(':').ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidData, "invalid request header")
            })?;
            Ok((
                name.trim().to_ascii_lowercase(),
                Zeroizing::new(value.trim().to_owned()),
            ))
        })
        .collect::<io::Result<Vec<_>>>()?;
    let content_lengths = headers
        .iter()
        .filter(|(name, _)| name == "content-length")
        .map(|(_, value)| value.parse::<usize>())
        .collect::<Result<Vec<_>, _>>()
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid content length"))?;
    if content_lengths.len() > 1 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "duplicate content length",
        ));
    }
    let content_length = content_lengths.first().copied().unwrap_or(0);
    if content_length > MAX_REQUEST_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "request body exceeds limit",
        ));
    }
    let body_start = end + 4;
    while request.len() < body_start + content_length {
        let read = stream.read(&mut *buffer)?;
        if read == 0 {
            return Err(io::Error::new(
                io::ErrorKind::UnexpectedEof,
                "incomplete request body",
            ));
        }
        request.extend_from_slice(&buffer[..read]);
    }
    let body = Zeroizing::new(request[body_start..body_start + content_length].to_vec());
    request.zeroize();
    Ok(RequestHead {
        method,
        path,
        headers,
        body,
    })
}

fn parse_approval_decision_path(path: &str) -> Option<(&str, &str)> {
    let path = path.strip_prefix("/v1/sessions/")?;
    let (session_id, remainder) = path.split_once("/approvals/")?;
    (!session_id.is_empty() && !remainder.is_empty() && !remainder.contains('/'))
        .then_some((session_id, remainder))
}

fn parse_session_item_path(path: &str) -> Option<&str> {
    let session_id = path.strip_prefix("/v1/sessions/")?;
    (!session_id.is_empty() && !session_id.contains('/')).then_some(session_id)
}

fn parse_source_collection_path(path: &str) -> Option<&str> {
    let session_id = path
        .strip_prefix("/v1/sessions/")?
        .strip_suffix("/sources")?;
    (!session_id.is_empty() && !session_id.contains('/')).then_some(session_id)
}

fn parse_source_item_path(path: &str) -> Option<(&str, &str)> {
    let path = path.strip_prefix("/v1/sessions/")?;
    let (session_id, attachment_id) = path.split_once("/sources/")?;
    (!session_id.is_empty()
        && !attachment_id.is_empty()
        && !session_id.contains('/')
        && !attachment_id.contains('/'))
    .then_some((session_id, attachment_id))
}

fn parse_source_retry_path(path: &str) -> Option<(&str, &str)> {
    let path = path.strip_prefix("/v1/sessions/")?;
    let (session_id, attachment_id) = path.split_once("/sources/")?;
    let attachment_id = attachment_id.strip_suffix("/retry")?;
    (!session_id.is_empty()
        && !attachment_id.is_empty()
        && !session_id.contains('/')
        && !attachment_id.contains('/'))
    .then_some((session_id, attachment_id))
}

fn parse_source_preview_path(path: &str) -> Option<(&str, &str)> {
    let path = path.strip_prefix("/v1/sessions/")?;
    let (session_id, attachment_id) = path.split_once("/sources/")?;
    let attachment_id = attachment_id.strip_suffix("/preview")?;
    (!session_id.is_empty()
        && !attachment_id.is_empty()
        && !session_id.contains('/')
        && !attachment_id.contains('/'))
    .then_some((session_id, attachment_id))
}

fn write_response(
    stream: &mut TcpStream,
    status: &str,
    body: &str,
    www_authenticate: Option<&str>,
) -> io::Result<()> {
    let authenticate = www_authenticate
        .map(|value| format!("WWW-Authenticate: {value}\r\n"))
        .unwrap_or_default();
    let response = format!(
        "HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n{authenticate}Connection: close\r\n\r\n{body}",
        body.len()
    );
    stream.write_all(response.as_bytes())?;
    stream.flush()
}

fn write_json_response<T: serde::Serialize>(
    stream: &mut TcpStream,
    status: &str,
    value: &T,
) -> io::Result<()> {
    let body = serde_json::to_string(value)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
    write_response(stream, status, &body, None)
}

#[cfg(test)]
mod tests {
    use super::{
        apply_approved_mutation, apply_single_file_patch, approval_request_is_expired,
        budget_reservation_id, now_ms, patch_proposal_metadata, reserve_connection,
        serve_connections, serve_one, token_usage_json_for_profile, EventHub, ExecutionProfile,
        OperationEnvelope, OperationState, ProviderId, ProviderSecrets, Risk, RuntimeBootstrap,
        RuntimeConfig, RuntimeEvent, RuntimeMode, RuntimeOwnerLock, RuntimeOwnerState,
        RuntimePolicy, RuntimeReadiness, WriterLockState, APPROVAL_EXPIRY_KEY,
        BUNDLED_CATALOGUE_REVISION, CAPABILITY_PROBE_TOOL,
        DEEPSEEK_CAPABILITY_PROBE_MAX_OUTPUT_TOKENS, DEEPSEEK_ENDPOINT, DEEPSEEK_MODEL,
        MAX_ACTIVE_CONNECTIONS, OPENCODE_GO_CAPABILITY_PROBE_MAX_OUTPUT_TOKENS,
        OPENCODE_GO_ENDPOINT, OPENCODE_GO_MODEL,
    };
    use sha2::{Digest, Sha256};
    use std::collections::BTreeMap;
    use std::ffi::OsString;
    use std::fs;
    use std::io::{Read, Write};
    use std::net::TcpStream;
    use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
    use std::sync::{Arc, Mutex};
    use std::thread;
    use std::time::{Duration, Instant};
    use zeroize::Zeroizing;

    const TOKEN: &str = "0123456789abcdef0123456789abcdef";
    static NEXT_TEST_DIR: AtomicU64 = AtomicU64::new(0);
    static ENVIRONMENT_LOCK: Mutex<()> = Mutex::new(());

    #[test]
    fn connection_reservation_is_bounded_and_released() {
        let active = AtomicUsize::new(0);
        for _ in 0..MAX_ACTIVE_CONNECTIONS {
            assert!(reserve_connection(&active));
        }
        assert!(!reserve_connection(&active));
        active.fetch_sub(1, Ordering::AcqRel);
        assert!(reserve_connection(&active));
    }

    struct EnvironmentRestore(Vec<(&'static str, Option<OsString>)>);

    impl EnvironmentRestore {
        fn capture(names: &[&'static str]) -> Self {
            Self(
                names
                    .iter()
                    .map(|name| (*name, std::env::var_os(name)))
                    .collect(),
            )
        }
    }

    impl Drop for EnvironmentRestore {
        fn drop(&mut self) {
            for (name, value) in &self.0 {
                // Safe while the test-wide environment lock is held.
                unsafe {
                    match value {
                        Some(value) => std::env::set_var(name, value),
                        None => std::env::remove_var(name),
                    }
                }
            }
        }
    }

    fn control_plane_fixture() -> serde_json::Value {
        serde_json::from_str(include_str!("../../../contracts/v1/control-plane.json"))
            .expect("fixture")
    }

    fn data_dir() -> std::path::PathBuf {
        let path = std::env::temp_dir().join(format!(
            "codinal-runtime-test-{}-{}",
            std::process::id(),
            NEXT_TEST_DIR.fetch_add(1, Ordering::Relaxed)
        ));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir(&path).expect("data directory");
        path
    }

    fn fixture_data_dir() -> std::path::PathBuf {
        let path = data_dir();
        for database in codinal_storage::load_v1_fixture()
            .expect("fixture")
            .databases
        {
            let connection = rusqlite::Connection::open(path.join(&database.file)).expect("db");
            if database.file == "audit.db" {
                connection
                    .execute_batch(
                        "CREATE TABLE events (
                           seq INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL,
                           domain TEXT NOT NULL, action TEXT NOT NULL, actor TEXT NOT NULL,
                           subject TEXT NOT NULL, payload TEXT NOT NULL,
                           prev_hash TEXT NOT NULL, hash TEXT NOT NULL
                         );
                         CREATE INDEX events_domain_seq ON events(domain, seq);
                         PRAGMA user_version = 1;",
                    )
                    .expect("audit schema");
                continue;
            }
            connection
                .execute_batch(&format!("PRAGMA user_version = {};", database.user_version))
                .expect("version");
            for table in database.tables {
                connection
                    .execute_batch(&format!("CREATE TABLE {table} (id INTEGER);"))
                    .expect("table");
            }
            if database.file == "codinal.db" {
                connection
                    .execute_batch(
                        "DROP TABLE sessions;
                         DROP TABLE messages;
                         DROP TABLE project_sessions;
                         DROP TABLE project_roots;
                         DROP TABLE projects;
                         DROP TABLE source_attachments;
                         CREATE TABLE sessions (
                           session_id TEXT PRIMARY KEY,
                           title TEXT NOT NULL,
                           source_workspace TEXT,
                           workspace TEXT,
                           agent TEXT NOT NULL,
                           model TEXT NOT NULL,
                           mode TEXT NOT NULL,
                           updated_at TEXT NOT NULL,
                           pinned INTEGER NOT NULL DEFAULT 0,
                           archived INTEGER NOT NULL DEFAULT 0,
                           origin TEXT,
                           origin_label TEXT,
                           origin_session_id TEXT
                         );
                         CREATE TABLE messages (
                           session_id TEXT NOT NULL, sequence INTEGER NOT NULL, payload TEXT NOT NULL,
                           PRIMARY KEY (session_id, sequence)
                         );
                         CREATE TABLE projects (
                           project_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                           pinned INTEGER NOT NULL DEFAULT 0,
                           updated_at TEXT NOT NULL
                         );
                         CREATE TABLE project_roots (
                           project_id TEXT NOT NULL, root_id TEXT NOT NULL, path TEXT NOT NULL,
                           is_primary INTEGER NOT NULL DEFAULT 0,
                           PRIMARY KEY (project_id, root_id)
                         );
                         CREATE TABLE project_sessions (
                           project_id TEXT NOT NULL, session_id TEXT PRIMARY KEY
                         );
                         CREATE TABLE source_attachments (
                           attachment_id TEXT NOT NULL, session_id TEXT NOT NULL,
                           path TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL,
                           status TEXT NOT NULL DEFAULT 'ready', error TEXT,
                           attached_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                           PRIMARY KEY (session_id, attachment_id), UNIQUE (session_id, path)
                         );
                         INSERT INTO sessions
                           (session_id, title, source_workspace, workspace, agent, model, mode,
                            updated_at, pinned, archived, origin)
                           VALUES
                           ('session-1', 'Session One', NULL, '/tmp', 'agent', 'gpt-4o', 'code',
                            '2026-01-01T00:00:00Z', 0, 0, NULL),
                           ('worker-1', 'Worker Session', '/tmp', '/tmp', 'agent', 'gpt-4o', 'code',
                            '2026-01-01T00:00:00Z', 0, 0, 'worker');"
                    )
                    .expect("sessions");
            }
        }
        path
    }

    fn free_loopback_port() -> u16 {
        std::net::TcpListener::bind("127.0.0.1:0")
            .expect("port listener")
            .local_addr()
            .expect("port address")
            .port()
    }

    fn read_http_request(stream: &mut TcpStream) -> Vec<u8> {
        let mut request = Vec::new();
        loop {
            let mut chunk = [0_u8; 1024];
            let read = stream.read(&mut chunk).expect("request");
            assert!(read > 0);
            request.extend_from_slice(&chunk[..read]);
            let Some(split) = request.windows(4).position(|window| window == b"\r\n\r\n") else {
                continue;
            };
            let headers = String::from_utf8_lossy(&request[..split]);
            let length = headers
                .lines()
                .find_map(|line| {
                    line.to_ascii_lowercase()
                        .strip_prefix("content-length: ")
                        .and_then(|value| value.parse::<usize>().ok())
                })
                .unwrap_or(0);
            if request.len() >= split + 4 + length {
                return request;
            }
        }
    }

    #[test]
    fn single_file_apply_patch_is_bounded_and_preserves_atomic_source_shape() {
        let source = "old\nsecond\n";
        let patch = "*** Begin Patch\n*** Update File: note.txt\n@@ -1,2 +1,2 @@\n-old\n+new\n second\n*** End Patch";
        assert_eq!(
            apply_single_file_patch("note.txt", patch, source).expect("patch"),
            "new\nsecond\n"
        );
        assert!(apply_single_file_patch("other.txt", patch, source).is_err());
        assert!(apply_single_file_patch(
            "note.txt",
            "*** Begin Patch\n*** Update File: note.txt\n@@ -1 +1 @@\n-old\n+new\n",
            source
        )
        .is_err());
    }

    #[test]
    fn approved_patch_checks_hashes_and_commits_one_file_atomically() {
        let data_dir = fixture_data_dir();
        let workspace = data_dir.join("workspace");
        fs::create_dir(&workspace).expect("workspace");
        let target = workspace.join("note.txt");
        fs::write(&target, "old\nsecond\n").expect("source");
        rusqlite::Connection::open(data_dir.join("codinal.db"))
            .expect("conversation db")
            .execute(
                "UPDATE sessions SET workspace = ?1 WHERE session_id = 'session-1'",
                [&workspace.to_string_lossy().to_string()],
            )
            .expect("workspace update");
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let arguments = serde_json::json!({
            "path": "note.txt",
            "patch": "*** Begin Patch\n*** Update File: note.txt\n@@ -1,2 +1,2 @@\n-old\n+new\n second\n*** End Patch"
        });
        let mut request = serde_json::json!({
            "tool_name": "apply_patch",
            "arguments": arguments,
        });
        let metadata = patch_proposal_metadata(&data_dir, "session-1", &request["arguments"])
            .expect("proposal metadata");
        request
            .as_object_mut()
            .expect("request object")
            .extend(metadata);
        let record = codinal_storage::ApprovalRecord {
            approval_id: "0123456789abcdef0123456789abcdef".to_owned(),
            turn_id: "turn-apply".to_owned(),
            session_id: "session-1".to_owned(),
            request: serde_json::to_string(&request).expect("request json"),
            state: "pending".to_owned(),
        };
        fs::write(
            workspace.join(".codinal-mutation-0123456789abcdef0123456789abcdef.tmp"),
            "stale temporary output",
        )
        .expect("stale temp");
        let mutation = apply_approved_mutation(runtime.config(), &record).expect("mutation");
        assert_eq!(mutation["path"], "note.txt");
        assert_eq!(
            fs::read_to_string(&target).expect("updated source"),
            "new\nsecond\n"
        );
        let replay = apply_approved_mutation(runtime.config(), &record).expect("idempotent replay");
        assert_eq!(replay["idempotent_replay"], true);
        fs::write(&target, "tampered\n").expect("tamper source");
        assert!(apply_approved_mutation(runtime.config(), &record).is_err());
        drop(runtime);
        fs::remove_dir_all(data_dir).expect("cleanup");
    }

    #[test]
    fn opencode_go_turn_uses_fixture_sse_and_writes_terminal_receipt() {
        let data_dir = fixture_data_dir();
        let provider_listener =
            std::net::TcpListener::bind("127.0.0.1:0").expect("provider listener");
        let provider_endpoint = format!(
            "http://127.0.0.1:{}/v1/chat/completions",
            provider_listener
                .local_addr()
                .expect("provider address")
                .port()
        );
        let provider = thread::spawn(move || {
            let (mut stream, _) = provider_listener.accept().expect("provider accept");
            let request = read_http_request(&mut stream);
            let request_text = String::from_utf8_lossy(&request);
            assert!(request_text.starts_with("POST /v1/chat/completions HTTP/1.1\r\n"));
            assert!(request_text
                .lines()
                .any(|line| line.eq_ignore_ascii_case("authorization: Bearer provider-secret")));
            let response = concat!(
                "data: {\"choices\":[{\"index\":0,\"delta\":{\"role\":\"assistant\",\"content\":\"fixture answer\"},\"finish_reason\":null}]}\n\n",
                "data: {\"choices\":[{\"index\":0,\"delta\":{},\"finish_reason\":\"stop\"}],\"usage\":{\"prompt_tokens\":4,\"completion_tokens\":3,\"total_tokens\":7}}\n\n",
                "data: [DONE]\n\n"
            );
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{response}",
                response.len()
            )
            .expect("provider response");
        });
        let mut config =
            RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        config.experimental_execution = true;
        config.readiness = RuntimeReadiness::owner_ready(None);
        config.opencode_endpoint = provider_endpoint;
        config.runtime_store =
            Some(codinal_storage::RuntimeStore::open_owned(&data_dir).expect("runtime store"));
        *config.provider_secrets.write().expect("provider secrets") =
            ProviderSecrets::from_bootstrap(
                br#"{"sync_token":"0123456789abcdef0123456789abcdef","profiles":{"provider:opencode-go":{"api_key":"provider-secret"}}}"#,
            )
        .expect("provider bootstrap");
        config.mark_capability_probe_for_test(ExecutionProfile::OpenCodeGo);
        let port = config.port;
        let server_config = config.clone();
        let server = thread::spawn(move || serve_connections(&server_config));
        for _ in 0..100 {
            if TcpStream::connect(("127.0.0.1", port)).is_ok() {
                break;
            }
            thread::sleep(std::time::Duration::from_millis(10));
        }
        let body = serde_json::json!({
            "turn_id": "turn-provider",
            "input": "answer with fixture",
            "provider": "opencode-go",
            "model": OPENCODE_GO_MODEL,
            "effort": "medium"
        });
        let body = serde_json::to_string(&body).expect("turn body");
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("runtime connection");
        write!(
            stream,
            "POST /v1/sessions/session-1/turns HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.len()
        )
        .expect("turn request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("turn response");
        assert!(response.starts_with("HTTP/1.1 202 Accepted\r\n"));
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        let receipts = loop {
            let receipts = config
                .runtime_store
                .as_ref()
                .expect("store")
                .read_receipts("session-1")
                .expect("receipts");
            if !receipts.is_empty() || std::time::Instant::now() >= deadline {
                break receipts;
            }
            thread::sleep(std::time::Duration::from_millis(10));
        };
        assert_eq!(receipts.len(), 1);
        assert_eq!(receipts[0].outcome["status"], "completed");
        assert_eq!(receipts[0].outcome["text"], "fixture answer");
        assert_eq!(receipts[0].outcome["usage"]["total_tokens"], 7);
        assert_eq!(
            receipts[0].outcome["usage"]["provider"]["cache_read_tokens"],
            serde_json::Value::Null
        );
        assert_eq!(receipts[0].outcome["provider"], "opencode-go");
        assert_eq!(receipts[0].outcome["first_delta_seen"], true);
        assert!(receipts[0].outcome["first_delta_ms"].is_number());
        let events = config
            .runtime_store
            .as_ref()
            .expect("store")
            .replay_events(None, 100)
            .expect("events")
            .events;
        let deltas = events
            .iter()
            .filter(|event| event.kind == "assistant_delta")
            .collect::<Vec<_>>();
        assert_eq!(deltas.len(), 1);
        assert_eq!(deltas[0].payload["text"], "fixture answer");
        assert!(deltas[0].payload["first_delta_ms"].is_number());
        let prompt_event = events
            .iter()
            .find(|event| event.kind == "prompt_compiled")
            .expect("prompt compilation event");
        assert!(prompt_event.payload["stable_prefix_hash"]
            .as_str()
            .is_some_and(|hash| hash.starts_with("sha256:")));
        assert_eq!(prompt_event.payload["cache_policy"], "prefer_stable_prefix");
        let mut replay_stream = TcpStream::connect(("127.0.0.1", port)).expect("replay connection");
        write!(
            replay_stream,
            "POST /v1/sessions/session-1/turns HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.len()
        )
        .expect("replay request");
        let mut replay_response = String::new();
        replay_stream
            .read_to_string(&mut replay_response)
            .expect("replay response");
        assert!(replay_response.starts_with("HTTP/1.1 200 OK\r\n"));
        assert!(replay_response.contains("\"idempotent_replay\":true"));
        config.request_shutdown();
        server.join().expect("runtime server").expect("serve");
        provider.join().expect("provider");
        fs::remove_dir_all(data_dir).expect("cleanup");
    }

    #[test]
    #[ignore = "fixed 3-session/90-turn local benchmark"]
    fn fixture_cold_warm_benchmark() {
        let data_dir = fixture_data_dir();
        let database = rusqlite::Connection::open(data_dir.join("codinal.db")).expect("db");
        for session_id in ["session-2", "session-3"] {
            database
                .execute(
                    "INSERT INTO sessions
                       (session_id, title, source_workspace, workspace, agent, model, mode,
                        updated_at, pinned, archived, origin)
                     VALUES (?1, ?2, NULL, '/tmp', 'agent', ?3, 'code',
                        '2026-01-01T00:00:00Z', 0, 0, NULL)",
                    rusqlite::params![session_id, session_id, OPENCODE_GO_MODEL],
                )
                .expect("benchmark session");
        }
        drop(database);

        let provider_listener =
            std::net::TcpListener::bind("127.0.0.1:0").expect("provider listener");
        let provider_endpoint = format!(
            "http://127.0.0.1:{}/v1/chat/completions",
            provider_listener
                .local_addr()
                .expect("provider address")
                .port()
        );
        let request_sizes = Arc::new(Mutex::new(Vec::<usize>::new()));
        let provider_request_sizes = Arc::clone(&request_sizes);
        let provider = thread::spawn(move || {
            for turn_index in 0..90 {
                let (mut stream, _) = provider_listener.accept().expect("provider accept");
                let request = read_http_request(&mut stream);
                provider_request_sizes
                    .lock()
                    .expect("request sizes")
                    .push(request.len());
                let response = format!(
                    "data: {}\n\ndata: {}\n\ndata: [DONE]\n\n",
                    serde_json::json!({
                        "choices": [{
                            "index": 0,
                            "delta": {"role": "assistant", "content": format!("fixture answer {turn_index}")},
                            "finish_reason": null
                        }]
                    }),
                    serde_json::json!({
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7}
                    })
                );
                write!(
                    stream,
                    "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{response}",
                    response.len()
                )
                .expect("provider response");
            }
        });

        let mut config =
            RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("benchmark config");
        config.experimental_execution = true;
        config.readiness = RuntimeReadiness::owner_ready(None);
        config.opencode_endpoint = provider_endpoint;
        config.runtime_store =
            Some(codinal_storage::RuntimeStore::open_owned(&data_dir).expect("runtime store"));
        *config.provider_secrets.write().expect("provider secrets") = ProviderSecrets::from_bootstrap(
            br#"{"sync_token":"0123456789abcdef0123456789abcdef","profiles":{"provider:opencode-go":{"api_key":"provider-secret"}}}"#,
        )
        .expect("provider bootstrap");
        config.mark_capability_probe_for_test(ExecutionProfile::OpenCodeGo);
        let port = config.port;
        let server_config = config.clone();
        let server = thread::spawn(move || serve_connections(&server_config));
        for _ in 0..100 {
            if TcpStream::connect(("127.0.0.1", port)).is_ok() {
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }

        let session_ids = ["session-1", "session-2", "session-3"];
        let mut cold_e2e_ms = Vec::new();
        let mut warm_e2e_ms = Vec::new();
        let mut cold_first_delta_ms = Vec::new();
        let mut warm_first_delta_ms = Vec::new();
        let benchmark_started = Instant::now();
        for (session_index, session_id) in session_ids.iter().enumerate() {
            for turn_index in 0..30 {
                let turn_id = format!("benchmark-{session_index}-{turn_index}");
                let input = format!("benchmark session {session_index} turn {turn_index}");
                let body = serde_json::json!({
                    "turn_id": turn_id,
                    "input": input,
                    "provider": "opencode-go",
                    "model": OPENCODE_GO_MODEL,
                    "effort": "medium"
                });
                let body = serde_json::to_string(&body).expect("turn body");
                let started = Instant::now();
                let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("runtime");
                write!(
                    stream,
                    "POST /v1/sessions/{session_id}/turns HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                    body.len()
                )
                .expect("turn request");
                let mut response = String::new();
                stream.read_to_string(&mut response).expect("turn response");
                assert!(response.starts_with("HTTP/1.1 202 Accepted\r\n"));

                let deadline = Instant::now() + Duration::from_secs(5);
                let receipt = loop {
                    if let Some(receipt) = config
                        .runtime_store
                        .as_ref()
                        .expect("store")
                        .read_receipt(&turn_id)
                        .expect("receipt")
                    {
                        break receipt;
                    }
                    assert!(Instant::now() < deadline, "receipt timeout for {turn_id}");
                    thread::sleep(Duration::from_millis(1));
                };
                assert_eq!(receipt.outcome["status"], "completed");
                let e2e_ms = started.elapsed().as_millis();
                let first_delta_ms = receipt.outcome["first_delta_ms"]
                    .as_u64()
                    .expect("first delta telemetry") as u128;
                if turn_index == 0 {
                    cold_e2e_ms.push(e2e_ms);
                    cold_first_delta_ms.push(first_delta_ms);
                } else {
                    warm_e2e_ms.push(e2e_ms);
                    warm_first_delta_ms.push(first_delta_ms);
                }
            }
        }

        config.request_shutdown();
        server.join().expect("runtime server").expect("serve");
        provider.join().expect("provider");

        let summarize = |samples: &[u128]| {
            let mut sorted = samples.to_vec();
            sorted.sort_unstable();
            let percentile = |percent: usize| {
                let index = (sorted.len() * percent).div_ceil(100).saturating_sub(1);
                sorted[index]
            };
            serde_json::json!({
                "count": sorted.len(),
                "min_ms": sorted[0],
                "p50_ms": percentile(50),
                "p95_ms": percentile(95),
                "max_ms": sorted[sorted.len() - 1],
                "mean_ms": sorted.iter().sum::<u128>() / sorted.len() as u128
            })
        };
        let store = config.runtime_store.as_ref().expect("store");
        let mut event_count = 0;
        let mut assistant_delta_count = 0;
        let mut cursor = None;
        loop {
            let replay = store.replay_events(cursor.as_deref(), 500).expect("events");
            event_count += replay.events.len();
            assistant_delta_count += replay
                .events
                .iter()
                .filter(|event| event.kind == "assistant_delta")
                .count();
            if replay.events.len() < 500 {
                break;
            }
            let next_cursor = replay.next_cursor;
            assert_ne!(cursor.as_deref(), Some(next_cursor.as_str()));
            cursor = Some(next_cursor);
        }
        let request_sizes = request_sizes.lock().expect("request sizes").clone();
        assert_eq!(request_sizes.len(), 90);
        assert_eq!(assistant_delta_count, 90);
        assert!(event_count >= 90);

        let mut fixture = BTreeMap::new();
        fixture.insert("endpoint_profile", "opencode-go-chat-completions-loopback");
        fixture.insert("effort", "medium");
        fixture.insert("model", OPENCODE_GO_MODEL);
        fixture.insert("policy", "experimental_execution-owner_ready-no_tools");
        fixture.insert("region", "loopback");
        fixture.insert("sample", "3_sessions_x_30_turns");
        let fixture_bytes = serde_json::to_vec(&fixture).expect("fixture bytes");
        let fixture_hash = Sha256::digest(fixture_bytes);
        let fixture_hash = fixture_hash
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect::<String>();
        let total_ms = benchmark_started.elapsed().as_millis().max(1);
        let request_bytes_total: usize = request_sizes.iter().sum();
        let benchmark = serde_json::json!({
            "fixture_hash": format!("sha256:{fixture_hash}"),
            "sample": {"sessions": 3, "turns_per_session": 30, "total_turns": 90},
            "cold": {
                "e2e": summarize(&cold_e2e_ms),
                "first_delta": summarize(&cold_first_delta_ms)
            },
            "warm": {
                "e2e": summarize(&warm_e2e_ms),
                "first_delta": summarize(&warm_first_delta_ms)
            },
            "runtime_events": event_count,
            "published_stream_events": assistant_delta_count,
            "observed_stream_rate_per_s": assistant_delta_count as f64 * 1000.0 / total_ms as f64,
            "provider_request_bytes": {
                "count": request_sizes.len(),
                "total": request_bytes_total,
                "min": request_sizes.iter().min().copied().expect("request bytes"),
                "max": request_sizes.iter().max().copied().expect("request bytes")
            },
            "provider_cache": "unknown_fixture_did_not_report_cache_fields",
            "provider_cost": "unknown_fixture_did_not_report_cost",
            "target_hardware_ui_metrics": "not_measured"
        });
        println!(
            "fixture cold/warm benchmark: {}",
            serde_json::to_string_pretty(&benchmark).expect("benchmark json")
        );
        fs::remove_dir_all(data_dir).expect("cleanup");
    }

    #[test]
    fn opencode_go_read_file_tool_round_trips_through_the_same_turn() {
        let data_dir = fixture_data_dir();
        let workspace = data_dir.join("workspace");
        fs::create_dir(&workspace).expect("workspace");
        fs::write(workspace.join("note.txt"), "workspace evidence\n").expect("file");
        rusqlite::Connection::open(data_dir.join("codinal.db"))
            .expect("db")
            .execute(
                "UPDATE sessions SET workspace = ?1 WHERE session_id = 'session-1'",
                [&workspace.to_string_lossy().to_string()],
            )
            .expect("workspace update");

        let provider_listener =
            std::net::TcpListener::bind("127.0.0.1:0").expect("provider listener");
        let provider_endpoint = format!(
            "http://127.0.0.1:{}/v1/chat/completions",
            provider_listener
                .local_addr()
                .expect("provider address")
                .port()
        );
        let provider = thread::spawn(move || {
            let (mut first_stream, _) = provider_listener.accept().expect("first provider accept");
            let first_request = read_http_request(&mut first_stream);
            let first_body_start = first_request
                .windows(4)
                .position(|window| window == b"\r\n\r\n")
                .expect("first headers")
                + 4;
            let first_body: serde_json::Value =
                serde_json::from_slice(&first_request[first_body_start..]).expect("first body");
            assert_eq!(first_body["messages"][0]["role"], "user");
            let first_response = concat!(
                "data: {\"choices\":[{\"index\":0,\"delta\":{\"tool_calls\":[{\"index\":0,\"id\":\"call-read\",\"function\":{\"name\":\"read_file\",\"arguments\":\"{\\\"path\\\":\\\"note.txt\\\"}\"}}]},\"finish_reason\":\"tool_calls\"}]}\n\n",
                "data: [DONE]\n\n"
            );
            write!(
                first_stream,
                "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{first_response}",
                first_response.len()
            )
            .expect("first response");

            let (mut second_stream, _) =
                provider_listener.accept().expect("second provider accept");
            let second_request = read_http_request(&mut second_stream);
            let second_body_start = second_request
                .windows(4)
                .position(|window| window == b"\r\n\r\n")
                .expect("second headers")
                + 4;
            let second_body: serde_json::Value =
                serde_json::from_slice(&second_request[second_body_start..]).expect("second body");
            let messages = second_body["messages"].as_array().expect("messages");
            assert_eq!(messages.last().expect("tool result")["role"], "tool");
            assert!(messages.last().expect("tool result")["content"]
                .as_str()
                .expect("tool content")
                .contains("workspace evidence"));
            let second_response = concat!(
                "data: {\"choices\":[{\"index\":0,\"delta\":{\"content\":\"read answer\"},\"finish_reason\":\"stop\"}],\"usage\":{\"prompt_tokens\":8,\"completion_tokens\":3,\"total_tokens\":11}}\n\n",
                "data: [DONE]\n\n"
            );
            write!(
                second_stream,
                "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{second_response}",
                second_response.len()
            )
            .expect("second response");
        });

        let mut config =
            RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        config.experimental_execution = true;
        config.readiness = RuntimeReadiness::owner_ready(None);
        config.opencode_endpoint = provider_endpoint;
        config.runtime_store =
            Some(codinal_storage::RuntimeStore::open_owned(&data_dir).expect("runtime store"));
        *config.provider_secrets.write().expect("provider secrets") =
            ProviderSecrets::from_bootstrap(
                br#"{"sync_token":"0123456789abcdef0123456789abcdef","profiles":{"provider:opencode-go":{"api_key":"provider-secret"}}}"#,
            )
            .expect("provider bootstrap");
        config.mark_capability_probe_for_test(ExecutionProfile::OpenCodeGo);
        let port = config.port;
        let server_config = config.clone();
        let server = thread::spawn(move || serve_connections(&server_config));
        for _ in 0..100 {
            if TcpStream::connect(("127.0.0.1", port)).is_ok() {
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }
        let body = serde_json::json!({
            "turn_id": "turn-read-tool",
            "input": "inspect note",
            "provider": "opencode-go",
            "model": OPENCODE_GO_MODEL,
            "effort": "medium"
        });
        let body = serde_json::to_string(&body).expect("turn body");
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("runtime connection");
        write!(
            stream,
            "POST /v1/sessions/session-1/turns HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.len()
        )
        .expect("turn request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("turn response");
        assert!(response.starts_with("HTTP/1.1 202 Accepted\r\n"));
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        let receipts = loop {
            let receipts = config
                .runtime_store
                .as_ref()
                .expect("store")
                .read_receipts("session-1")
                .expect("receipts");
            if !receipts.is_empty() || std::time::Instant::now() >= deadline {
                break receipts;
            }
            thread::sleep(Duration::from_millis(10));
        };
        assert_eq!(receipts.len(), 1);
        assert_eq!(receipts[0].outcome["status"], "completed");
        assert_eq!(receipts[0].outcome["text"], "read answer");
        assert_eq!(receipts[0].outcome["first_delta_seen"], true);
        let events = config
            .runtime_store
            .as_ref()
            .expect("store")
            .replay_events(None, 100)
            .expect("events")
            .events;
        assert!(events.iter().any(|event| event.kind == "tool_result"));
        assert!(events.iter().any(|event| event.kind == "assistant_delta"));
        config.request_shutdown();
        server.join().expect("runtime server").expect("serve");
        provider.join().expect("provider");
        fs::remove_dir_all(data_dir).expect("cleanup");
    }

    #[test]
    fn opencode_go_apply_patch_approval_resumes_the_same_turn() {
        let data_dir = fixture_data_dir();
        let workspace = data_dir.join("workspace");
        fs::create_dir(&workspace).expect("workspace");
        fs::write(workspace.join("note.txt"), "old\nsecond\n").expect("file");
        rusqlite::Connection::open(data_dir.join("codinal.db"))
            .expect("db")
            .execute(
                "UPDATE sessions SET workspace = ?1 WHERE session_id = 'session-1'",
                [&workspace.to_string_lossy().to_string()],
            )
            .expect("workspace update");

        let provider_listener =
            std::net::TcpListener::bind("127.0.0.1:0").expect("provider listener");
        let provider_endpoint = format!(
            "http://127.0.0.1:{}/v1/chat/completions",
            provider_listener
                .local_addr()
                .expect("provider address")
                .port()
        );
        let patch = "*** Begin Patch\n*** Update File: note.txt\n@@ -1,2 +1,2 @@\n-old\n+new\n second\n*** End Patch";
        let provider = thread::spawn(move || {
            let (mut first_stream, _) = provider_listener.accept().expect("first provider accept");
            let _first_request = read_http_request(&mut first_stream);
            let arguments = serde_json::json!({"path": "note.txt", "patch": patch});
            let first_event = serde_json::json!({
                "choices": [{
                    "index": 0,
                    "delta": {
                        "tool_calls": [{
                            "index": 0,
                            "id": "call-patch",
                            "function": {
                                "name": "apply_patch",
                                "arguments": serde_json::to_string(&arguments).expect("arguments")
                            }
                        }]
                    },
                    "finish_reason": "tool_calls"
                }]
            });
            let first_response = format!("data: {first_event}\n\ndata: [DONE]\n\n");
            write!(
                first_stream,
                "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{first_response}",
                first_response.len()
            )
            .expect("first response");

            let (mut second_stream, _) =
                provider_listener.accept().expect("second provider accept");
            let second_request = read_http_request(&mut second_stream);
            let second_body_start = second_request
                .windows(4)
                .position(|window| window == b"\r\n\r\n")
                .expect("second headers")
                + 4;
            let second_body: serde_json::Value =
                serde_json::from_slice(&second_request[second_body_start..]).expect("second body");
            let messages = second_body["messages"].as_array().expect("messages");
            assert!(messages
                .iter()
                .any(|message| message["role"] == "assistant"));
            let tool_message = messages
                .iter()
                .find(|message| message["role"] == "tool")
                .expect("approved tool result");
            assert_eq!(tool_message["tool_call_id"], "call-patch");
            assert!(tool_message["content"]
                .as_str()
                .expect("tool content")
                .contains("\"path\":\"note.txt\""));
            let second_response = concat!(
                "data: {\"choices\":[{\"index\":0,\"delta\":{\"content\":\"patched answer\"},\"finish_reason\":\"stop\"}],\"usage\":{\"prompt_tokens\":9,\"completion_tokens\":3,\"total_tokens\":12}}\n\n",
                "data: [DONE]\n\n"
            );
            write!(
                second_stream,
                "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{second_response}",
                second_response.len()
            )
            .expect("second response");
        });

        let mut config =
            RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        config.experimental_execution = true;
        config.readiness = RuntimeReadiness::owner_ready(None);
        config.opencode_endpoint = provider_endpoint;
        config.runtime_store =
            Some(codinal_storage::RuntimeStore::open_owned(&data_dir).expect("runtime store"));
        *config.provider_secrets.write().expect("provider secrets") =
            ProviderSecrets::from_bootstrap(
                br#"{"sync_token":"0123456789abcdef0123456789abcdef","profiles":{"provider:opencode-go":{"api_key":"provider-secret"}}}"#,
            )
            .expect("provider bootstrap");
        config.mark_capability_probe_for_test(ExecutionProfile::OpenCodeGo);
        config.attach_audit_ledger().expect("audit ledger");
        let port = config.port;
        let server_config = config.clone();
        let server = thread::spawn(move || serve_connections(&server_config));
        for _ in 0..100 {
            if TcpStream::connect(("127.0.0.1", port)).is_ok() {
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }

        let body = serde_json::to_string(&serde_json::json!({
            "turn_id": "turn-approval-resume",
            "input": "patch note",
            "provider": "opencode-go",
            "model": OPENCODE_GO_MODEL,
            "effort": "medium"
        }))
        .expect("turn body");
        let mut turn_stream = TcpStream::connect(("127.0.0.1", port)).expect("runtime connection");
        write!(
            turn_stream,
            "POST /v1/sessions/session-1/turns HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.len()
        )
        .expect("turn request");
        let mut turn_response = String::new();
        turn_stream
            .read_to_string(&mut turn_response)
            .expect("turn response");
        assert!(turn_response.starts_with("HTTP/1.1 202 Accepted\r\n"));

        let store = config.runtime_store.as_ref().expect("store");
        let deadline = Instant::now() + Duration::from_secs(2);
        let approval = loop {
            let approvals = store
                .read_pending_approvals("session-1")
                .expect("pending approvals");
            if let Some(approval) = approvals.into_iter().next() {
                break approval;
            }
            assert!(Instant::now() < deadline, "approval was not persisted");
            thread::sleep(Duration::from_millis(10));
        };
        let approval_body = r#"{"outcome":"once"}"#;
        let approval_path = format!("/v1/sessions/session-1/approvals/{}", approval.approval_id);
        let mut approval_stream =
            TcpStream::connect(("127.0.0.1", port)).expect("approval connection");
        write!(
            approval_stream,
            "POST {approval_path} HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{approval_body}",
            approval_body.len()
        )
        .expect("approval request");
        let mut approval_response = String::new();
        approval_stream
            .read_to_string(&mut approval_response)
            .expect("approval response");
        assert!(
            approval_response.starts_with("HTTP/1.1 202 Accepted\r\n"),
            "{approval_response}"
        );
        assert!(approval_response.contains("\"resumed\":true"));

        let deadline = Instant::now() + Duration::from_secs(2);
        let receipts = loop {
            let receipts = store.read_receipts("session-1").expect("receipts");
            if !receipts.is_empty() || Instant::now() >= deadline {
                break receipts;
            }
            thread::sleep(Duration::from_millis(10));
        };
        assert_eq!(receipts.len(), 1);
        assert_eq!(receipts[0].outcome["status"], "completed");
        assert_eq!(receipts[0].outcome["text"], "patched answer");
        assert_eq!(
            fs::read_to_string(workspace.join("note.txt")).expect("patched file"),
            "new\nsecond\n"
        );
        let events = store.replay_events(None, 100).expect("events").events;
        assert!(events.iter().any(|event| event.kind == "approval_resumed"));
        assert!(events
            .iter()
            .any(|event| event.kind == "mutation_committed"));
        config.request_shutdown();
        server.join().expect("runtime server").expect("serve");
        provider.join().expect("provider");
        fs::remove_dir_all(data_dir).expect("cleanup");
    }

    #[test]
    #[ignore = "requires a separately approved OpenCode Go credential"]
    fn live_opencode_go_turn_uses_real_provider_and_writes_terminal_receipt() {
        let api_key = Zeroizing::new(
            std::env::var("CODINAL_LIVE_OPENCODE_GO_API_KEY")
                .expect("CODINAL_LIVE_OPENCODE_GO_API_KEY is required"),
        );
        assert!(!api_key.is_empty(), "live OpenCode Go credential is empty");

        let data_dir = fixture_data_dir();
        let bootstrap = serde_json::to_vec(&serde_json::json!({
            "sync_token": TOKEN,
            "profiles": {
                "provider:opencode-go": {"api_key": api_key.as_str()}
            }
        }))
        .expect("provider bootstrap JSON");
        let provider_secrets =
            ProviderSecrets::from_bootstrap(&bootstrap).expect("provider bootstrap");
        let mut config =
            RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        config.experimental_execution = true;
        config.readiness = RuntimeReadiness::owner_ready(None);
        config.opencode_endpoint = OPENCODE_GO_ENDPOINT.to_owned();
        config.runtime_store =
            Some(codinal_storage::RuntimeStore::open_owned(&data_dir).expect("runtime store"));
        *config.provider_secrets.write().expect("provider secrets") = provider_secrets;
        config
            .probe_capability(ExecutionProfile::OpenCodeGo)
            .expect("live OpenCode Go capability probe");

        let port = config.port;
        let server_config = config.clone();
        let server = thread::spawn(move || serve_connections(&server_config));
        for _ in 0..100 {
            if TcpStream::connect(("127.0.0.1", port)).is_ok() {
                break;
            }
            thread::sleep(std::time::Duration::from_millis(10));
        }

        let body = serde_json::to_string(&serde_json::json!({
            "turn_id": "turn-live-opencode-go",
            "input": "Reply with exactly LIVE_OK and nothing else.",
            "provider": "opencode-go",
            "model": OPENCODE_GO_MODEL,
            "effort": "medium"
        }))
        .expect("turn body");
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("runtime connection");
        write!(
            stream,
            "POST /v1/sessions/session-1/turns HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.len()
        )
        .expect("turn request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("turn response");
        assert!(response.starts_with("HTTP/1.1 202 Accepted\r\n"));

        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(90);
        let receipts = loop {
            let receipts = config
                .runtime_store
                .as_ref()
                .expect("store")
                .read_receipts("session-1")
                .expect("receipts");
            if !receipts.is_empty() || std::time::Instant::now() >= deadline {
                break receipts;
            }
            thread::sleep(std::time::Duration::from_millis(50));
        };
        assert_eq!(receipts.len(), 1);
        assert_eq!(receipts[0].outcome["status"], "completed");
        assert_eq!(
            receipts[0].outcome["text"].as_str().map(str::trim),
            Some("LIVE_OK")
        );
        assert_eq!(receipts[0].outcome["provider"], "opencode-go");
        assert_eq!(receipts[0].outcome["model"], OPENCODE_GO_MODEL);
        assert_eq!(receipts[0].outcome["effort"], "medium");

        config.request_shutdown();
        server.join().expect("runtime server").expect("serve");
        fs::remove_dir_all(data_dir).expect("cleanup");
    }

    #[test]
    fn deepseek_cost_estimate_uses_prompt_cache_miss_tokens() {
        let usage = codinal_providers::TokenUsage {
            prompt_tokens: 151,
            completion_tokens: 8,
            total_tokens: 159,
            provider_usage: Some(codinal_providers::ProviderUsage {
                input_tokens: Some(151),
                cache_read_tokens: Some(128),
                cache_write_tokens: None,
                prompt_cache_hit_tokens: Some(128),
                prompt_cache_miss_tokens: Some(23),
                output_tokens: Some(8),
                first_delta_ms: None,
                total_latency_ms: None,
                cost: codinal_providers::UsageCost::Unavailable,
            }),
        };
        let outcome = token_usage_json_for_profile(ExecutionProfile::DeepSeek, &usage);
        assert_eq!(
            outcome["cost_estimate"]["classification"],
            "codinal_estimated"
        );
        assert_eq!(outcome["cost_estimate"]["usd_microusd"], 18);
        assert_eq!(outcome["cost_estimate"]["input_tokens"], 23);
        assert_eq!(outcome["cost_estimate"]["cache_read_tokens"], 128);
    }

    #[test]
    fn capability_probe_budget_matches_provider_reasoning_profile() {
        assert_eq!(
            ExecutionProfile::OpenCodeGo.capability_probe_max_output_tokens(),
            OPENCODE_GO_CAPABILITY_PROBE_MAX_OUTPUT_TOKENS
        );
        assert_eq!(
            ExecutionProfile::DeepSeek.capability_probe_max_output_tokens(),
            DEEPSEEK_CAPABILITY_PROBE_MAX_OUTPUT_TOKENS
        );
    }

    #[test]
    fn deepseek_turn_uses_independent_profile_and_settles_durable_budget() {
        let data_dir = fixture_data_dir();
        let provider_listener =
            std::net::TcpListener::bind("127.0.0.1:0").expect("provider listener");
        let provider_endpoint = format!(
            "http://127.0.0.1:{}/chat/completions",
            provider_listener
                .local_addr()
                .expect("provider address")
                .port()
        );
        let provider = thread::spawn(move || {
            let (mut stream, _) = provider_listener.accept().expect("provider accept");
            let request = read_http_request(&mut stream);
            let request_text = String::from_utf8_lossy(&request);
            assert!(request_text.starts_with("POST /chat/completions HTTP/1.1\r\n"));
            assert!(request_text
                .lines()
                .any(|line| line.eq_ignore_ascii_case("authorization: Bearer deepseek-secret")));
            let body_start = request
                .windows(4)
                .position(|window| window == b"\r\n\r\n")
                .expect("headers")
                + 4;
            let body: serde_json::Value =
                serde_json::from_slice(&request[body_start..]).expect("request body");
            assert_eq!(body["model"], DEEPSEEK_MODEL);
            assert_eq!(body["thinking"]["type"], "enabled");
            assert_eq!(body["reasoning_effort"], "high");
            assert_eq!(body["stream_options"]["include_usage"], true);
            let response = concat!(
                "data: {\"choices\":[{\"index\":0,\"delta\":{\"content\":null,\"reasoning_content\":\"private\"},\"finish_reason\":null}],\"usage\":null}\n\n",
                "data: {\"choices\":[{\"index\":0,\"delta\":{\"content\":\"deepseek answer\"},\"finish_reason\":\"stop\"}],\"usage\":{\"prompt_tokens\":12,\"completion_tokens\":6,\"total_tokens\":18,\"prompt_cache_hit_tokens\":4}}\n\n",
                "data: [DONE]\n\n"
            );
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{response}",
                response.len()
            )
            .expect("provider response");
        });
        let mut config =
            RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        config.experimental_execution = true;
        config.readiness = RuntimeReadiness::owner_ready(None);
        config.deepseek_endpoint = provider_endpoint;
        config.runtime_store =
            Some(codinal_storage::RuntimeStore::open_owned(&data_dir).expect("runtime store"));
        *config.provider_secrets.write().expect("provider secrets") =
            ProviderSecrets::from_bootstrap(
                br#"{"sync_token":"0123456789abcdef0123456789abcdef","profiles":{"provider:deepseek":{"api_key":"deepseek-secret"}}}"#,
            )
            .expect("provider bootstrap");
        config.mark_capability_probe_for_test(ExecutionProfile::DeepSeek);
        let port = config.port;
        let server_config = config.clone();
        let server = thread::spawn(move || serve_connections(&server_config));
        for _ in 0..100 {
            if TcpStream::connect(("127.0.0.1", port)).is_ok() {
                break;
            }
            thread::sleep(std::time::Duration::from_millis(10));
        }
        let body = serde_json::json!({
            "turn_id": "turn-deepseek",
            "input": "answer with DeepSeek",
            "provider": "deepseek",
            "model": DEEPSEEK_MODEL,
            "effort": "high"
        });
        let body = serde_json::to_string(&body).expect("turn body");
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("runtime connection");
        write!(
            stream,
            "POST /v1/sessions/session-1/turns HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.len()
        )
        .expect("turn request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("turn response");
        assert!(response.starts_with("HTTP/1.1 202 Accepted\r\n"));
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        let receipts = loop {
            let receipts = config
                .runtime_store
                .as_ref()
                .expect("store")
                .read_receipts("session-1")
                .expect("receipts");
            if !receipts.is_empty() || std::time::Instant::now() >= deadline {
                break receipts;
            }
            thread::sleep(std::time::Duration::from_millis(10));
        };
        assert_eq!(receipts.len(), 1);
        assert_eq!(receipts[0].outcome["status"], "completed");
        assert_eq!(receipts[0].outcome["provider"], "deepseek");
        assert_eq!(receipts[0].outcome["usage"]["total_tokens"], 18);
        assert_eq!(
            receipts[0].outcome["capability_snapshot"]["models_dev_revision"],
            codinal_providers::MODELS_DEV_API_SHA256
        );
        assert_eq!(
            receipts[0].outcome["capability_snapshot"]["probe_status"],
            "passed"
        );
        assert_eq!(
            receipts[0].outcome["usage"]["cost_estimate"]["classification"],
            "codinal_estimated"
        );
        assert_eq!(
            receipts[0].outcome["usage"]["cost_estimate"]["usd_microusd"],
            11
        );
        let reservation = config
            .runtime_store
            .as_ref()
            .expect("store")
            .read_budget_reservation(&budget_reservation_id("turn-deepseek"))
            .expect("budget read")
            .expect("budget");
        assert_eq!(reservation.state, "settled");
        assert_eq!(reservation.reserved_tokens, 18);
        config.request_shutdown();
        server.join().expect("runtime server").expect("serve");
        provider.join().expect("provider");
        fs::remove_dir_all(data_dir).expect("cleanup");
    }

    #[test]
    #[ignore = "requires a separately approved DeepSeek credential"]
    fn live_deepseek_turn_uses_real_provider_and_settles_durable_budget() {
        let api_key = Zeroizing::new(
            std::env::var("CODINAL_LIVE_DEEPSEEK_API_KEY")
                .expect("CODINAL_LIVE_DEEPSEEK_API_KEY is required"),
        );
        assert!(!api_key.is_empty(), "live DeepSeek credential is empty");

        let data_dir = fixture_data_dir();
        let bootstrap = serde_json::to_vec(&serde_json::json!({
            "sync_token": TOKEN,
            "profiles": {
                "provider:deepseek": {"api_key": api_key.as_str()}
            }
        }))
        .expect("provider bootstrap JSON");
        let provider_secrets =
            ProviderSecrets::from_bootstrap(&bootstrap).expect("provider bootstrap");
        let mut config =
            RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        config.experimental_execution = true;
        config.readiness = RuntimeReadiness::owner_ready(None);
        config.deepseek_endpoint = DEEPSEEK_ENDPOINT.to_owned();
        config.runtime_store =
            Some(codinal_storage::RuntimeStore::open_owned(&data_dir).expect("runtime store"));
        *config.provider_secrets.write().expect("provider secrets") = provider_secrets;
        config
            .probe_capability(ExecutionProfile::DeepSeek)
            .expect("live DeepSeek capability probe");

        let port = config.port;
        let server_config = config.clone();
        let server = thread::spawn(move || serve_connections(&server_config));
        for _ in 0..100 {
            if TcpStream::connect(("127.0.0.1", port)).is_ok() {
                break;
            }
            thread::sleep(std::time::Duration::from_millis(10));
        }

        let body = serde_json::to_string(&serde_json::json!({
            "turn_id": "turn-live-deepseek",
            "input": "Reply with exactly DEEPSEEK_LIVE_OK and nothing else.",
            "provider": "deepseek",
            "model": DEEPSEEK_MODEL,
            "effort": "high"
        }))
        .expect("turn body");
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("runtime connection");
        write!(
            stream,
            "POST /v1/sessions/session-1/turns HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.len()
        )
        .expect("turn request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("turn response");
        assert!(response.starts_with("HTTP/1.1 202 Accepted\r\n"));

        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(90);
        let receipts = loop {
            let receipts = config
                .runtime_store
                .as_ref()
                .expect("store")
                .read_receipts("session-1")
                .expect("receipts");
            if !receipts.is_empty() || std::time::Instant::now() >= deadline {
                break receipts;
            }
            thread::sleep(std::time::Duration::from_millis(50));
        };
        assert_eq!(receipts.len(), 1);
        assert_eq!(receipts[0].outcome["status"], "completed");
        assert_eq!(
            receipts[0].outcome["text"].as_str().map(str::trim),
            Some("DEEPSEEK_LIVE_OK")
        );
        assert_eq!(receipts[0].outcome["provider"], "deepseek");
        assert_eq!(receipts[0].outcome["model"], DEEPSEEK_MODEL);
        assert_eq!(receipts[0].outcome["effort"], "high");
        assert_eq!(
            receipts[0].outcome["usage"]["cost_estimate"]["classification"],
            "codinal_estimated"
        );
        if let Some(cache_miss_tokens) =
            receipts[0].outcome["usage"]["provider"]["prompt_cache_miss_tokens"].as_u64()
        {
            assert_eq!(
                receipts[0].outcome["usage"]["cost_estimate"]["input_tokens"],
                cache_miss_tokens
            );
        }
        let reservation = config
            .runtime_store
            .as_ref()
            .expect("store")
            .read_budget_reservation(&budget_reservation_id("turn-live-deepseek"))
            .expect("budget read")
            .expect("budget");
        assert_eq!(reservation.state, "settled");
        assert!(reservation.reserved_tokens > 0);

        config.request_shutdown();
        server.join().expect("runtime server").expect("serve");
        fs::remove_dir_all(data_dir).expect("cleanup");
    }

    #[test]
    fn deepseek_fallback_is_opt_in_and_budgeted_after_primary_failure() {
        let data_dir = fixture_data_dir();
        let provider_listener =
            std::net::TcpListener::bind("127.0.0.1:0").expect("provider listener");
        let provider_endpoint = format!(
            "http://127.0.0.1:{}/chat/completions",
            provider_listener
                .local_addr()
                .expect("provider address")
                .port()
        );
        let provider = thread::spawn(move || {
            let (mut first_stream, _) = provider_listener.accept().expect("primary accept");
            let first_request = read_http_request(&mut first_stream);
            let first_body_start = first_request
                .windows(4)
                .position(|window| window == b"\r\n\r\n")
                .expect("primary headers")
                + 4;
            let first_body: serde_json::Value =
                serde_json::from_slice(&first_request[first_body_start..]).expect("primary body");
            assert_eq!(first_body["model"], OPENCODE_GO_MODEL);
            assert!(first_body.get("thinking").is_none());
            write!(
                first_stream,
                "HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            )
            .expect("primary response");

            let (mut fallback_stream, _) = provider_listener.accept().expect("fallback accept");
            let fallback_request = read_http_request(&mut fallback_stream);
            let fallback_text = String::from_utf8_lossy(&fallback_request);
            assert!(fallback_text.starts_with("POST /chat/completions HTTP/1.1\r\n"));
            let fallback_body_start = fallback_request
                .windows(4)
                .position(|window| window == b"\r\n\r\n")
                .expect("fallback headers")
                + 4;
            let fallback_body: serde_json::Value =
                serde_json::from_slice(&fallback_request[fallback_body_start..])
                    .expect("fallback body");
            assert_eq!(fallback_body["model"], DEEPSEEK_MODEL);
            assert_eq!(fallback_body["thinking"]["type"], "enabled");
            let response = concat!(
                "data: {\"choices\":[{\"index\":0,\"delta\":{\"content\":\"fallback answer\"},\"finish_reason\":\"stop\"}],\"usage\":{\"prompt_tokens\":8,\"completion_tokens\":4,\"total_tokens\":12}}\n\n",
                "data: [DONE]\n\n"
            );
            write!(
                fallback_stream,
                "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{response}",
                response.len()
            )
            .expect("fallback response");
        });
        let mut config =
            RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        config.experimental_execution = true;
        config.readiness = RuntimeReadiness::owner_ready(None);
        config.opencode_endpoint = provider_endpoint.clone();
        config.deepseek_endpoint = provider_endpoint;
        config.runtime_store =
            Some(codinal_storage::RuntimeStore::open_owned(&data_dir).expect("runtime store"));
        *config.provider_secrets.write().expect("provider secrets") =
            ProviderSecrets::from_bootstrap(
                br#"{"sync_token":"0123456789abcdef0123456789abcdef","profiles":{"provider:opencode-go":{"api_key":"opencode-secret"},"provider:deepseek":{"api_key":"deepseek-secret"}}}"#,
            )
            .expect("provider bootstrap");
        config.mark_capability_probe_for_test(ExecutionProfile::OpenCodeGo);
        config.mark_capability_probe_for_test(ExecutionProfile::DeepSeek);
        let port = config.port;
        let server_config = config.clone();
        let server = thread::spawn(move || serve_connections(&server_config));
        for _ in 0..100 {
            if TcpStream::connect(("127.0.0.1", port)).is_ok() {
                break;
            }
            thread::sleep(std::time::Duration::from_millis(10));
        }
        let body = serde_json::json!({
            "turn_id": "turn-fallback",
            "input": "answer with fallback",
            "provider": "opencode-go",
            "model": OPENCODE_GO_MODEL,
            "effort": "medium",
            "fallback": "deepseek"
        });
        let body = serde_json::to_string(&body).expect("turn body");
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("runtime connection");
        write!(
            stream,
            "POST /v1/sessions/session-1/turns HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.len()
        )
        .expect("turn request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("turn response");
        assert!(response.starts_with("HTTP/1.1 202 Accepted\r\n"));
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        let receipts = loop {
            let receipts = config
                .runtime_store
                .as_ref()
                .expect("store")
                .read_receipts("session-1")
                .expect("receipts");
            if !receipts.is_empty() || std::time::Instant::now() >= deadline {
                break receipts;
            }
            thread::sleep(std::time::Duration::from_millis(10));
        };
        assert_eq!(receipts.len(), 1);
        assert_eq!(receipts[0].outcome["provider"], "deepseek");
        assert_eq!(receipts[0].outcome["fallback_attempted"], true);
        let reservation = config
            .runtime_store
            .as_ref()
            .expect("store")
            .read_budget_reservation(&budget_reservation_id("turn-fallback"))
            .expect("budget read")
            .expect("budget");
        assert_eq!(reservation.state, "settled");
        assert_eq!(reservation.reserved_tokens, 12);
        config.request_shutdown();
        server.join().expect("runtime server").expect("serve");
        provider.join().expect("provider");
        fs::remove_dir_all(data_dir).expect("cleanup");
    }

    #[test]
    fn rejects_invalid_runtime_configuration() {
        let path = data_dir();
        assert!(RuntimeConfig::new(0, TOKEN, &path).is_err());
        assert!(RuntimeConfig::new(3000, "too-short", &path).is_err());
        fs::remove_dir(path).expect("remove");
    }

    #[test]
    fn storage_preflight_is_read_only_and_reports_missing_reference_data() {
        let path = data_dir();
        let config = RuntimeConfig::new(3000, TOKEN, &path).expect("config");
        assert_eq!(config.readiness.mode, RuntimeMode::ReadOnly);
        assert_eq!(
            config.readiness.writer_lock.state,
            WriterLockState::NotAcquired
        );
        assert_eq!(config.inspect_storage().expect("inspect").len(), 9);
        assert!(path.read_dir().expect("read").next().is_none());
        fs::remove_dir(path).expect("remove");
    }

    #[test]
    fn runtime_bootstrap_exclusively_owns_its_data_directory() {
        let path = data_dir();
        let owner = RuntimeBootstrap::from_values(3000, TOKEN, &path).expect("first owner");
        assert!(RuntimeBootstrap::from_values(3001, TOKEN, &path).is_err());
        assert_eq!(owner.startup_state(), RuntimeOwnerState::LockedActive);
        assert!(owner
            .startup_trace()
            .iter()
            .any(|entry| entry == "startup:Reconcile"));
        assert!(owner
            .startup_trace()
            .iter()
            .any(|entry| entry == "startup:LockedActive"));
        assert!(owner
            .startup_trace()
            .iter()
            .any(|entry| entry.contains("lock:held:")));
        drop(owner);
        assert!(RuntimeBootstrap::from_values(3001, TOKEN, &path).is_ok());
        fs::remove_dir_all(path).expect("remove");
    }

    #[test]
    fn runtime_bootstrap_records_migration_trace_for_reconcile() {
        let path = data_dir();
        let owner = RuntimeBootstrap::from_values(3000, TOKEN, &path).expect("runtime");
        let migration_traces = owner
            .startup_trace()
            .iter()
            .filter(|entry| entry.starts_with("migration:plan:"));
        assert!(
            migration_traces.count() >= 1,
            "expected migration report entries for reconcile bootstrap path"
        );
        drop(owner);
        fs::remove_dir_all(path).expect("remove");
    }

    #[test]
    fn runtime_bootstrap_consumes_the_host_token_environment_value() {
        let _guard = ENVIRONMENT_LOCK.lock().expect("environment lock");
        let _restore = EnvironmentRestore::capture(&[
            "CODINAL_SESSION_TOKEN",
            "CODINAL_PORT",
            "CODINAL_DATA_DIR",
        ]);
        let path = data_dir();
        // Safe while the test-wide environment lock is held.
        unsafe {
            std::env::set_var("CODINAL_SESSION_TOKEN", TOKEN);
            std::env::set_var("CODINAL_PORT", "3000");
            std::env::set_var("CODINAL_DATA_DIR", &path);
        }
        let bootstrap = RuntimeBootstrap::from_environment().expect("bootstrap");
        assert!(std::env::var("CODINAL_SESSION_TOKEN").is_err());
        assert_eq!(bootstrap.config().data_dir(), path);
        drop(bootstrap);
        fs::remove_dir_all(path).expect("remove");
    }

    #[test]
    fn runtime_bootstrap_consumes_one_shot_provider_secrets_from_stdin() {
        let _guard = ENVIRONMENT_LOCK.lock().expect("environment lock");
        let _restore = EnvironmentRestore::capture(&[
            "CODINAL_SESSION_TOKEN",
            "CODINAL_PORT",
            "CODINAL_DATA_DIR",
            "CODINAL_SECRET_BOOTSTRAP",
        ]);
        let path = data_dir();
        unsafe {
            std::env::set_var("CODINAL_SESSION_TOKEN", TOKEN);
            std::env::set_var("CODINAL_PORT", "43123");
            std::env::set_var("CODINAL_DATA_DIR", &path);
            std::env::set_var("CODINAL_SECRET_BOOTSTRAP", "stdin-v1");
        }
        let payload = br#"{"sync_token":"0123456789abcdef0123456789abcdef","profiles":{"provider:openai":{"api_key":"provider-secret"}}}"#;
        let mut input = std::io::Cursor::new(payload);
        let runtime = RuntimeBootstrap::from_environment_reader(&mut input).expect("runtime");
        assert_eq!(
            runtime
                .provider_secrets()
                .expect("provider secrets")
                .api_key(&super::ProviderId::OpenAi),
            Some("provider-secret")
        );
        assert!(std::env::var_os("CODINAL_SECRET_BOOTSTRAP").is_none());
        assert!(format!(
            "{:?}",
            runtime.provider_secrets().expect("provider secrets")
        )
        .contains("configured_profiles"));
        assert!(!format!(
            "{:?}",
            runtime.provider_secrets().expect("provider secrets")
        )
        .contains("provider-secret"));
        drop(runtime);
        fs::remove_dir_all(path).expect("remove");
    }

    #[test]
    fn mutation_gate_is_owned_by_the_runtime() {
        let mut policy = RuntimePolicy::default();
        assert!(
            !policy
                .authorize_mutation(Risk::WriteLocal, None, "session-1")
                .0
        );
        assert!(policy.approve_once("approval-token-0123456789"));
        assert!(
            policy
                .authorize_mutation(
                    Risk::WriteLocal,
                    Some("approval-token-0123456789"),
                    "session-1"
                )
                .0
        );
    }

    #[test]
    fn event_history_preserves_the_v1_published_order() {
        let fixture = control_plane_fixture();
        let sequence = fixture["events"][0]["sequence"]
            .as_array()
            .expect("sequence");
        let mut events = EventHub::default();
        let received = Arc::new(Mutex::new(Vec::new()));
        let received_by_listener = Arc::clone(&received);
        let subscription = events
            .subscribe_session(
                "fixture-session",
                Box::new(move |event| {
                    received_by_listener.lock().expect("received").push(
                        event.message["type"]
                            .as_str()
                            .expect("event type")
                            .to_owned(),
                    );
                    Ok(())
                }),
            )
            .expect("subscribe");
        for event_type in sequence {
            events
                .publish_session(
                    "fixture-session",
                    &RuntimeEvent::new(
                        serde_json::json!({ "type": event_type.as_str().expect("event type") })
                            .as_object()
                            .expect("object")
                            .clone(),
                    ),
                )
                .expect("publish");
        }
        assert_eq!(
            received.lock().expect("received").clone(),
            sequence
                .iter()
                .map(|event| event.as_str().expect("event type").to_owned())
                .collect::<Vec<_>>()
        );
        assert!(events.unsubscribe(subscription));
    }

    #[test]
    fn reconnect_subscription_receives_only_future_v1_events() {
        let fixture = control_plane_fixture();
        let reconnect = &fixture["events"][1];
        let mut events = EventHub::default();
        let first = Arc::new(Mutex::new(Vec::new()));
        let first_by_listener = Arc::clone(&first);
        let first_subscription = events
            .subscribe_session(
                reconnect["stream"].as_str().expect("stream"),
                Box::new(move |event| {
                    first_by_listener.lock().expect("first").push(
                        event.message["type"]
                            .as_str()
                            .expect("event type")
                            .to_owned(),
                    );
                    Ok(())
                }),
            )
            .expect("subscribe");
        for event_type in reconnect["before_reconnect"]
            .as_array()
            .expect("before reconnect")
        {
            events
                .publish_session(
                    reconnect["stream"].as_str().expect("stream"),
                    &RuntimeEvent::new(
                        serde_json::json!({ "type": event_type.as_str().expect("event type") })
                            .as_object()
                            .expect("object")
                            .clone(),
                    ),
                )
                .expect("publish before reconnect");
        }
        assert!(events.unsubscribe(first_subscription));
        let second = Arc::new(Mutex::new(Vec::new()));
        let second_by_listener = Arc::clone(&second);
        events
            .subscribe_session(
                reconnect["stream"].as_str().expect("stream"),
                Box::new(move |event| {
                    second_by_listener.lock().expect("second").push(
                        event.message["type"]
                            .as_str()
                            .expect("event type")
                            .to_owned(),
                    );
                    Ok(())
                }),
            )
            .expect("resubscribe");
        for event_type in reconnect["after_reconnect"]
            .as_array()
            .expect("after reconnect")
        {
            events
                .publish_session(
                    reconnect["stream"].as_str().expect("stream"),
                    &RuntimeEvent::new(
                        serde_json::json!({ "type": event_type.as_str().expect("event type") })
                            .as_object()
                            .expect("object")
                            .clone(),
                    ),
                )
                .expect("publish after reconnect");
        }
        assert_eq!(
            first.lock().expect("first").clone(),
            reconnect["before_reconnect"]
                .as_array()
                .expect("before reconnect")
                .iter()
                .map(|event| event.as_str().expect("event type").to_owned())
                .collect::<Vec<_>>()
        );
        assert_eq!(
            second.lock().expect("second").clone(),
            reconnect["after_reconnect"]
                .as_array()
                .expect("after reconnect")
                .iter()
                .map(|event| event.as_str().expect("event type").to_owned())
                .collect::<Vec<_>>()
        );
    }

    #[test]
    fn event_hub_preserves_payload_and_prunes_failed_listeners() {
        let mut events = EventHub::default();
        let received = Arc::new(Mutex::new(Vec::new()));
        let received_by_listener = Arc::clone(&received);
        events.subscribe_global(Box::new(move |event| {
            received_by_listener
                .lock()
                .expect("received")
                .push(event.clone());
            Ok(())
        }));
        let failed_calls = Arc::new(Mutex::new(0));
        let failed_by_listener = Arc::clone(&failed_calls);
        events.subscribe_global(Box::new(move |_| {
            *failed_by_listener.lock().expect("failed calls") += 1;
            Err(std::io::Error::other("closed"))
        }));
        let event = RuntimeEvent::new(
            serde_json::json!({ "sequence": 1, "text": "payload survives fan-out" })
                .as_object()
                .expect("object")
                .clone(),
        );
        events.publish_global(&event);
        events.publish_global(&event);
        assert_eq!(
            received.lock().expect("received").as_slice(),
            &[event.clone(), event]
        );
        assert_eq!(*failed_calls.lock().expect("failed calls"), 1);
        assert!(events
            .subscribe_session(&"a".repeat(129), Box::new(|_| Ok(())))
            .is_err());
    }

    #[test]
    fn health_route_requires_exact_bearer_token() {
        let data_dir = data_dir();
        let config = RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        let listener = config.bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, &config));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(b"GET /v1/health HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        let expected = &control_plane_fixture()["http"][0]["response"];
        assert!(response.starts_with(&format!("HTTP/1.1 {} Unauthorized\r\n", expected["status"])));
        assert!(response.contains(&format!(
            "WWW-Authenticate: {}\r\n",
            expected["headers"]["www-authenticate"]
                .as_str()
                .expect("header")
        )));
        assert!(response.ends_with(expected["json"].to_string().as_str()));
        server.join().expect("server").expect("serve");
        fs::remove_dir(data_dir).expect("remove");
    }

    #[test]
    fn health_route_accepts_exact_bearer_token() {
        let data_dir = data_dir();
        let config = RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        let listener = config.bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, &config));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(format!("GET /v1/health HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n").as_bytes())
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        let expected = &control_plane_fixture()["http"][1]["response"];
        assert!(response.starts_with(&format!("HTTP/1.1 {} OK\r\n", expected["status"])));
        let body = response
            .split_once("\r\n\r\n")
            .map(|(_, body)| body)
            .expect("health body");
        let health: serde_json::Value = serde_json::from_str(body).expect("health json");
        assert_eq!(health["status"], "ok");
        assert_eq!(health["capabilities"]["runtime_owner"], "rust");
        assert_eq!(health["capabilities"]["turn_execution_owner"], "none");
        assert_eq!(health["capabilities"]["receipt_write_owner"], "none");
        assert_eq!(health["capabilities"]["start_turn"], false);
        assert_eq!(health["capabilities"]["interrupt_turn"], false);
        assert_eq!(
            health["model_catalogue"]["revision"],
            BUNDLED_CATALOGUE_REVISION
        );
        assert_eq!(
            health["model_catalogue"]["metadata"]["status"],
            "synchronized"
        );
        assert_eq!(
            health["model_catalogue"]["metadata"]["revision"],
            codinal_providers::MODELS_DEV_API_SHA256
        );
        assert_eq!(
            health["capabilities"]["capability_probe"]["status"],
            "not_run"
        );
        assert_eq!(
            health["capabilities"]["capability_snapshots"]["opencode_go"]["probe_status"],
            "not_run"
        );
        server.join().expect("server").expect("serve");
        fs::remove_dir(data_dir).expect("remove");
    }

    #[test]
    fn capability_probe_requires_approval_is_bounded_and_expires_on_drift() {
        let data_dir = fixture_data_dir();
        let provider_listener =
            std::net::TcpListener::bind("127.0.0.1:0").expect("provider listener");
        let provider_endpoint = format!(
            "http://127.0.0.1:{}/v1/chat/completions",
            provider_listener
                .local_addr()
                .expect("provider address")
                .port()
        );
        let provider = thread::spawn(move || {
            let (mut stream, _) = provider_listener.accept().expect("provider accept");
            let request = read_http_request(&mut stream);
            let body_start = request
                .windows(4)
                .position(|window| window == b"\r\n\r\n")
                .expect("headers")
                + 4;
            let body: serde_json::Value =
                serde_json::from_slice(&request[body_start..]).expect("probe body");
            assert_eq!(body["model"], OPENCODE_GO_MODEL);
            assert_eq!(body["reasoning_effort"], "medium");
            assert_eq!(
                body["max_tokens"],
                OPENCODE_GO_CAPABILITY_PROBE_MAX_OUTPUT_TOKENS
            );
            assert_eq!(body["tools"][0]["function"]["name"], CAPABILITY_PROBE_TOOL);
            let response = concat!(
                "data: {\"choices\":[{\"index\":0,\"delta\":{\"tool_calls\":[{\"index\":0,\"id\":\"probe-call\",\"function\":{\"name\":\"codinal_capability_probe\",\"arguments\":\"{}\"}}]},\"finish_reason\":null}]}\n\n",
                "data: {\"choices\":[{\"index\":0,\"delta\":{},\"finish_reason\":\"tool_calls\"}],\"usage\":{\"prompt_tokens\":5,\"completion_tokens\":1,\"total_tokens\":6}}\n\n",
                "data: [DONE]\n\n"
            );
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{response}",
                response.len()
            )
            .expect("probe response");
        });
        let mut config =
            RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        config.experimental_execution = true;
        config.readiness = RuntimeReadiness::owner_ready(None);
        config.opencode_endpoint = provider_endpoint.clone();
        config.runtime_store =
            Some(codinal_storage::RuntimeStore::open_owned(&data_dir).expect("runtime store"));
        *config.provider_secrets.write().expect("provider secrets") =
            ProviderSecrets::from_bootstrap(
                br#"{"sync_token":"0123456789abcdef0123456789abcdef","profiles":{"provider:opencode-go":{"api_key":"provider-secret"}}}"#,
            )
            .expect("provider bootstrap");
        let port = config.port;
        let server_config = config.clone();
        let server = thread::spawn(move || serve_connections(&server_config));
        for _ in 0..100 {
            if TcpStream::connect(("127.0.0.1", port)).is_ok() {
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }
        let send_probe = |approved: bool| {
            let body = serde_json::json!({
                "approved": approved,
                "provider": "opencode-go",
                "model": OPENCODE_GO_MODEL,
                "effort": "medium"
            })
            .to_string();
            let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("runtime connection");
            write!(
                stream,
                "POST /v1/capabilities/probe HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                body.len()
            )
            .expect("probe request");
            let mut response = String::new();
            stream
                .read_to_string(&mut response)
                .expect("probe response");
            response
        };
        let rejected = send_probe(false);
        assert!(rejected.starts_with("HTTP/1.1 428 Precondition Required\r\n"));
        let passed = send_probe(true);
        assert!(passed.starts_with("HTTP/1.1 200 OK\r\n"));
        let health = config.health_document();
        assert_eq!(health["mode"], "ready");
        assert_eq!(health["capabilities"]["start_turn"], true);
        assert_eq!(
            health["capabilities"]["capability_probe"]["status"],
            "passed"
        );
        let model_profiles = health["capabilities"]["model_profiles"]
            .as_array()
            .expect("model profiles");
        assert_eq!(model_profiles.len(), 2);
        assert_eq!(model_profiles[0]["provider"], "opencode-go");
        assert_eq!(model_profiles[0]["model"], OPENCODE_GO_MODEL);
        assert_eq!(model_profiles[0]["ready"], true);
        assert_eq!(model_profiles[1]["provider"], "deepseek");
        assert_eq!(model_profiles[1]["model"], DEEPSEEK_MODEL);
        assert_eq!(model_profiles[1]["ready"], false);
        provider.join().expect("provider");

        config.opencode_endpoint = "http://127.0.0.1:1/v1/chat/completions".to_owned();
        let drifted = config.health_document();
        assert_eq!(drifted["mode"], "degraded");
        assert_eq!(
            drifted["capabilities"]["run_disabled_reason"],
            "endpoint_drift"
        );
        assert_eq!(
            drifted["capabilities"]["capability_snapshots"]["opencode_go"]["probe_status"],
            "failed"
        );

        config.opencode_endpoint = provider_endpoint;
        {
            let mut probes = config.capability_probes.lock().expect("probe registry");
            probes
                .records
                .get_mut(&ExecutionProfile::OpenCodeGo)
                .expect("probe record")
                .status = codinal_providers::ProbeStatus::Passed;
            let record = probes
                .records
                .get_mut(&ExecutionProfile::OpenCodeGo)
                .expect("probe record");
            record.endpoint = Some(config.opencode_endpoint.clone());
            record.reason = None;
            record.expires_at_ms = Some(0);
        }
        let expired = config.health_document();
        assert_eq!(expired["mode"], "degraded");
        assert_eq!(
            expired["capabilities"]["run_disabled_reason"],
            "probe_expired"
        );
        config.request_shutdown();
        server.join().expect("runtime server").expect("serve");
        fs::remove_dir_all(data_dir).expect("cleanup");
    }

    #[test]
    fn owner_can_create_a_session_over_the_control_plane() {
        let data_dir = data_dir();
        let workspace = data_dir.with_extension("workspace");
        fs::create_dir(&workspace).expect("workspace");
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let config = runtime.config().clone();
        let server = thread::spawn(move || serve_one(&listener, &config));
        let body = serde_json::json!({
            "workspace": workspace.to_string_lossy(),
            "title": "New task",
            "model": OPENCODE_GO_MODEL,
            "mode": "code",
            "origin": "side_chat",
            "origin_label": "Side chat",
            "origin_session_id": "parent-session"
        })
        .to_string();
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "POST /v1/sessions HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                    body.len()
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 201 Created\r\n"));
        let response_body = response
            .split_once("\r\n\r\n")
            .map(|(_, body)| body)
            .expect("response body");
        let session: serde_json::Value = serde_json::from_str(response_body).expect("session json");
        assert!(session["session_id"]
            .as_str()
            .is_some_and(|id| id.starts_with("session-")));
        assert_eq!(session["title"], "New task");
        assert_eq!(session["origin"], "side_chat");
        assert_eq!(session["origin_label"], "Side chat");
        assert_eq!(session["origin_session_id"], "parent-session");
        server.join().expect("server").expect("serve");
        assert_eq!(
            codinal_storage::read_session_summaries(&data_dir, None)
                .expect("sessions")
                .len(),
            1
        );
        drop(runtime);
        fs::remove_dir_all(workspace).expect("remove workspace");
        fs::remove_dir_all(data_dir).expect("remove data");
    }

    #[test]
    fn owner_can_manage_projects_over_the_control_plane() {
        let data_dir = data_dir();
        let workspace = data_dir.with_extension("workspace");
        fs::create_dir(&workspace).expect("workspace");
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let request = |method: &str, path: &str, body: &str| -> String {
            let listener = runtime.config().bind().expect("listener");
            let port = listener.local_addr().expect("address").port();
            let config = runtime.config().clone();
            let server = thread::spawn(move || serve_one(&listener, &config));
            let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
            write!(
                stream,
                "{method} {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                body.len()
            )
            .expect("request");
            let mut response = String::new();
            stream.read_to_string(&mut response).expect("response");
            server.join().expect("server").expect("serve");
            response
        };

        let response = request("GET", "/v1/projects", "");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"), "{response}");
        assert!(response.ends_with("[]"), "{response}");

        let body = serde_json::json!({
            "name": "Harness",
            "roots": [workspace.to_string_lossy()]
        })
        .to_string();
        let response = request("POST", "/v1/projects", &body);
        assert!(
            response.starts_with("HTTP/1.1 201 Created\r\n"),
            "{response}"
        );
        let project: serde_json::Value =
            serde_json::from_str(response.split_once("\r\n\r\n").expect("body").1)
                .expect("project JSON");
        let project_id = project["project_id"]
            .as_str()
            .expect("project id")
            .to_owned();
        assert_eq!(project["name"], "Harness");

        let response = request(
            "POST",
            &format!("/v1/projects/{project_id}/pin"),
            r#"{"pinned":true}"#,
        );
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"), "{response}");
        let response = request("GET", "/v1/projects", "");
        let projects: serde_json::Value =
            serde_json::from_str(response.split_once("\r\n\r\n").expect("body").1)
                .expect("projects JSON");
        assert_eq!(projects[0]["pinned"], true);

        codinal_storage::create_session(
            &data_dir,
            "session-project",
            "Project chat",
            workspace.to_str().expect("workspace UTF-8"),
            "code",
            OPENCODE_GO_MODEL,
            "code",
        )
        .expect("create project chat");
        let response = request(
            "POST",
            &format!("/v1/projects/{project_id}/sessions/session-project"),
            "",
        );
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"), "{response}");
        let response = request("GET", "/v1/projects", "");
        let projects: serde_json::Value =
            serde_json::from_str(response.split_once("\r\n\r\n").expect("body").1)
                .expect("projects JSON");
        assert_eq!(projects[0]["task_count"], 1);

        let response = request(
            "DELETE",
            &format!("/v1/projects/{project_id}/sessions/session-project"),
            "",
        );
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"), "{response}");

        let response = request("DELETE", &format!("/v1/projects/{project_id}"), "");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"), "{response}");
        assert!(codinal_storage::read_projects(&data_dir)
            .expect("projects")
            .is_empty());

        drop(runtime);
        fs::remove_dir_all(workspace).expect("remove workspace");
        fs::remove_dir_all(data_dir).expect("remove data");
    }

    #[test]
    fn owner_can_manage_conversation_sources_over_the_control_plane() {
        let data_dir = data_dir();
        let workspace = data_dir.with_extension("workspace");
        fs::create_dir(&workspace).expect("workspace");
        let source = workspace.join("reference.md");
        fs::write(&source, "keep the original").expect("source");
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let request = |method: &str, path: &str, body: &str| -> String {
            let listener = runtime.config().bind().expect("listener");
            let port = listener.local_addr().expect("address").port();
            let config = runtime.config().clone();
            let server = thread::spawn(move || serve_one(&listener, &config));
            let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
            write!(
                stream,
                "{method} {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                body.len()
            )
            .expect("request");
            let mut response = String::new();
            stream.read_to_string(&mut response).expect("response");
            server.join().expect("server").expect("serve");
            response
        };
        codinal_storage::create_session(
            &data_dir,
            "session-source",
            "Source chat",
            workspace.to_str().expect("workspace UTF-8"),
            "code",
            OPENCODE_GO_MODEL,
            "code",
        )
        .expect("create source session");

        let body = serde_json::json!({"path": source}).to_string();
        let response = request("POST", "/v1/sessions/session-source/sources", &body);
        assert!(
            response.starts_with("HTTP/1.1 201 Created\r\n"),
            "{response}"
        );
        let attachment: serde_json::Value =
            serde_json::from_str(response.split_once("\r\n\r\n").expect("body").1)
                .expect("source JSON");
        assert_eq!(attachment["name"], "reference.md");
        assert_eq!(attachment["kind"], "file");
        assert_eq!(attachment["status"], "ready");
        let attachment_id = attachment["attachment_id"]
            .as_str()
            .expect("attachment id")
            .to_owned();

        let response = request("GET", "/v1/sessions/session-source/sources", "");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"), "{response}");
        let sources: serde_json::Value =
            serde_json::from_str(response.split_once("\r\n\r\n").expect("body").1)
                .expect("sources JSON");
        assert_eq!(sources.as_array().expect("source list").len(), 1);

        let response = request(
            "DELETE",
            &format!("/v1/sessions/session-source/sources/{attachment_id}"),
            "",
        );
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"), "{response}");
        assert!(
            source.exists(),
            "detaching must preserve the original source"
        );

        let body = serde_json::json!({"path": source}).to_string();
        let response = request("POST", "/v1/sessions/session-source/sources", &body);
        assert!(
            response.starts_with("HTTP/1.1 201 Created\r\n"),
            "{response}"
        );

        let preview_path = format!("/v1/sessions/session-source/sources/{attachment_id}/preview");
        let response = request("GET", &preview_path, "");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"), "{response}");
        let preview: serde_json::Value =
            serde_json::from_str(response.split_once("\r\n\r\n").expect("body").1)
                .expect("preview JSON");
        assert_eq!(preview["attachment"]["attachment_id"], attachment_id);
        assert_eq!(preview["content"], "keep the original");
        assert_eq!(preview["binary"], false);
        assert_eq!(preview["truncated"], false);

        fs::remove_file(&source).expect("remove original");
        let response = request(
            "POST",
            &format!("/v1/sessions/session-source/sources/{attachment_id}/retry"),
            "",
        );
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"), "{response}");
        let retried: serde_json::Value =
            serde_json::from_str(response.split_once("\r\n\r\n").expect("body").1)
                .expect("retried source JSON");
        assert_eq!(retried["status"], "unavailable");

        let response = request(
            "DELETE",
            &format!("/v1/sessions/session-source/sources/{attachment_id}"),
            "",
        );
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"), "{response}");

        drop(runtime);
        fs::remove_dir_all(workspace).expect("remove workspace");
        fs::remove_dir_all(data_dir).expect("remove data");
    }

    #[test]
    fn activity_route_is_typed_and_mark_read_is_allowed_in_read_only_mode() {
        let data_dir = data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let request = |method: &str, path: &str| -> String {
            let listener = runtime.config().bind().expect("listener");
            let port = listener.local_addr().expect("address").port();
            let config = runtime.config().clone();
            let server = thread::spawn(move || serve_one(&listener, &config));
            let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
            write!(
                stream,
                "{method} {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            )
            .expect("request");
            let mut response = String::new();
            stream.read_to_string(&mut response).expect("response");
            server.join().expect("server").expect("serve");
            response
        };
        let response = request("GET", "/v1/activity");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"), "{response}");
        assert!(response.ends_with("[]"), "{response}");
        let response = request("POST", "/v1/activity/read");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"), "{response}");
        assert!(response.ends_with("{\"ok\":true}"), "{response}");
        drop(runtime);
        fs::remove_dir_all(data_dir).expect("remove data");
    }

    #[test]
    fn authenticated_websocket_replays_runtime_events_for_a_session() {
        use tungstenite::client::IntoClientRequest;
        use tungstenite::http::header::{HeaderValue, SEC_WEBSOCKET_PROTOCOL};
        use tungstenite::Message;

        let data_dir = data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let store = runtime.config().runtime_store().expect("runtime store");
        store.create_turn("turn-ws", "session-ws").expect("turn");
        store
            .append_event(
                "turn-ws",
                "created",
                serde_json::json!({"session_id": "session-ws"}),
            )
            .expect("event");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let config = runtime.config().clone();
        let server = thread::spawn(move || serve_one(&listener, &config));
        let mut request = format!("ws://127.0.0.1:{port}/ws/session/session-ws")
            .into_client_request()
            .expect("websocket request");
        request.headers_mut().insert(
            SEC_WEBSOCKET_PROTOCOL,
            HeaderValue::from_str(&format!("codinal.v1, codinal.auth.{TOKEN}"))
                .expect("protocol header"),
        );
        let (mut socket, response) = tungstenite::connect(request).expect("websocket connect");
        assert_eq!(response.status().as_u16(), 101);
        assert_eq!(
            response
                .headers()
                .get(SEC_WEBSOCKET_PROTOCOL)
                .and_then(|value| value.to_str().ok()),
            Some("codinal.v1")
        );
        let message = socket.read().expect("event");
        let raw = match message {
            Message::Text(raw) => raw.to_string(),
            Message::Binary(raw) => {
                String::from_utf8(raw.as_slice().to_vec()).expect("event UTF-8")
            }
            other => panic!("unexpected websocket message: {other:?}"),
        };
        let event: serde_json::Value = serde_json::from_str(&raw).expect("event json");
        assert_eq!(event["type"], "turn_start");
        assert_eq!(event["turn_id"], "turn-ws");
        socket.close(None).expect("close");
        server.join().expect("server").expect("serve");
        drop(runtime);
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn tool_routes_require_experimental_execution_approval_and_receipts() {
        let _environment = ENVIRONMENT_LOCK.lock().expect("environment lock");
        let restore = EnvironmentRestore::capture(&[
            "CODINAL_WORKSPACE_ROOT",
            "CODINAL_EXPERIMENTAL_EXECUTION",
        ]);
        let data_dir = data_dir();
        let workspace = data_dir.join("workspace");
        fs::create_dir(&workspace).expect("workspace");
        fs::write(workspace.join("hello.txt"), b"hello from tool\n").expect("file");
        unsafe {
            std::env::set_var("CODINAL_WORKSPACE_ROOT", &workspace);
            std::env::set_var("CODINAL_EXPERIMENTAL_EXECUTION", "1");
        }
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let config = runtime.config().clone();
        let listener = config.bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let send = |request: String| {
            let server_listener = listener.try_clone().expect("listener clone");
            let server_config = config.clone();
            let server = thread::spawn(move || serve_one(&server_listener, &server_config));
            let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
            stream.write_all(request.as_bytes()).expect("request");
            let mut response = String::new();
            stream.read_to_string(&mut response).expect("response");
            server.join().expect("server").expect("serve");
            response
        };
        let approval_id = "route-tool-approval-123456";
        let rejected_body = serde_json::json!({
            "operation_id": "route-shell-rejected",
            "cwd": "",
            "program": "cat",
            "args": ["hello.txt"],
            "approval_id": approval_id
        })
        .to_string();
        let rejected = send(format!(
            "POST /v1/tools/shell HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{rejected_body}",
            rejected_body.len()
        ));
        let rejected_json: serde_json::Value =
            serde_json::from_str(rejected.split_once("\r\n\r\n").expect("body").1)
                .expect("rejected json");
        assert_eq!(rejected_json["receipt"]["status"], "rejected");

        let approval_body = serde_json::json!({"approval_id": approval_id}).to_string();
        let approved = send(format!(
            "POST /v1/tools/approve HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{approval_body}",
            approval_body.len()
        ));
        assert!(approved.starts_with("HTTP/1.1 200 OK\r\n"));

        let success_body = serde_json::json!({
            "operation_id": "route-shell-approved",
            "cwd": "",
            "program": "cat",
            "args": ["hello.txt"],
            "approval_id": approval_id
        })
        .to_string();
        let success = send(format!(
            "POST /v1/tools/shell HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{success_body}",
            success_body.len()
        ));
        let success_json: serde_json::Value =
            serde_json::from_str(success.split_once("\r\n\r\n").expect("body").1)
                .expect("success json");
        assert_eq!(success_json["receipt"]["status"], "succeeded");
        assert_eq!(success_json["stdout"], "hello from tool\n");

        let receipt = send(format!(
            "GET /v1/tools/route-shell-approved/receipt HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
        ));
        let receipt_json: serde_json::Value =
            serde_json::from_str(receipt.split_once("\r\n\r\n").expect("body").1)
                .expect("receipt json");
        assert_eq!(receipt_json["operation_id"], "route-shell-approved");
        assert_eq!(receipt_json["status"], "succeeded");
        drop(runtime);
        fs::remove_dir_all(data_dir).expect("remove");
        drop(restore);
    }

    #[test]
    fn writer_lock_reports_process_identity_without_releasing_the_first_owner() {
        let data_dir = data_dir();
        let owner = RuntimeOwnerLock::acquire(&data_dir).expect("first owner");
        let error = match RuntimeOwnerLock::acquire(&data_dir) {
            Ok(_) => panic!("second owner rejected"),
            Err(error) => error,
        };
        let detail = error.to_string();
        assert!(detail.contains("writer lock unavailable"));
        assert!(detail.contains(&format!("pid={}", std::process::id())));
        assert!(detail.contains("start_ms="));
        assert!(detail.contains("data_dir="));
        drop(owner);
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn owner_restart_restores_durable_pending_approval_into_the_live_broker() {
        let data_dir = fixture_data_dir();
        let runtime = RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir)
            .expect("first runtime");
        let store = runtime.config().runtime_store().expect("store");
        store
            .create_turn("turn-restore", "session-1")
            .expect("turn");
        store
            .put_approval(&codinal_storage::ApprovalRecord {
                approval_id: "abcdefabcdefabcdefabcdefabcdefab".to_owned(),
                turn_id: "turn-restore".to_owned(),
                session_id: "session-1".to_owned(),
                request: serde_json::to_string(&serde_json::json!({
                    "tool_name": "apply_patch",
                    "arguments": {"path": "note.txt", "patch": "fixture"},
                    "reason": "write_local approval",
                    "risk": "write_local",
                    "command": null
                }))
                .expect("request"),
                state: "pending".to_owned(),
            })
            .expect("approval");
        drop(runtime);

        let restarted = RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir)
            .expect("restarted runtime");
        let pending = restarted
            .config()
            .approval_broker()
            .lock()
            .expect("broker")
            .pending("session-1");
        assert_eq!(pending.len(), 1);
        assert_eq!(pending[0].approval_id, "abcdefabcdefabcdefabcdefabcdefab");
        drop(restarted);
        fs::remove_dir_all(data_dir).expect("cleanup");
    }

    #[test]
    fn concurrent_runtime_connections_interrupt_a_held_turn_and_replay_events() {
        let data_dir = fixture_data_dir();
        let port = free_loopback_port();
        let runtime = RuntimeBootstrap::from_values(port, TOKEN, &data_dir).expect("runtime");
        let server_config = runtime.config().clone();
        let server = thread::spawn(move || serve_connections(&server_config));
        let mut probe = None;
        for _ in 0..100 {
            if let Ok(stream) = TcpStream::connect(("127.0.0.1", port)) {
                probe = Some(stream);
                break;
            }
            thread::sleep(std::time::Duration::from_millis(10));
        }
        drop(probe.expect("runtime listener"));

        let mut held = TcpStream::connect(("127.0.0.1", port)).expect("held connection");
        let body = r#"{"turn_id":"turn-held","input":"hold"}"#;
        write!(
            held,
            "POST /v1/sessions/session-1/turns HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("held request");
        let held_response = thread::spawn(move || {
            let mut response = String::new();
            held.read_to_string(&mut response).expect("held response");
            response
        });
        thread::sleep(std::time::Duration::from_millis(100));

        let mut interrupt = TcpStream::connect(("127.0.0.1", port)).expect("interrupt connection");
        interrupt
            .write_all(
                format!(
                    "POST /v1/sessions/session-1/interrupt HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Length: 0\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("interrupt request");
        let mut interrupt_response = String::new();
        interrupt
            .read_to_string(&mut interrupt_response)
            .expect("interrupt response");
        assert!(interrupt_response.starts_with("HTTP/1.1 202 Accepted\r\n"));

        let held_response = held_response.join().expect("held worker");
        assert!(held_response.starts_with("HTTP/1.1 200 OK\r\n"));
        assert!(held_response.contains("\"outcome\":\"interrupted\""));

        let mut receipts = TcpStream::connect(("127.0.0.1", port)).expect("receipt connection");
        receipts
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/turns HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("receipt request");
        let mut receipt_response = String::new();
        receipts
            .read_to_string(&mut receipt_response)
            .expect("receipt response");
        let receipt_body = receipt_response
            .split_once("\r\n\r\n")
            .map(|(_, body)| body)
            .expect("receipt body");
        let receipts: serde_json::Value = serde_json::from_str(receipt_body).expect("receipt json");
        assert_eq!(receipts.as_array().expect("receipt list").len(), 1);
        assert_eq!(receipts[0]["outcome"]["status"], "interrupted");

        let mut events = TcpStream::connect(("127.0.0.1", port)).expect("event connection");
        events
            .write_all(
                format!(
                    "GET /v1/events HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("event request");
        let mut event_response = String::new();
        events
            .read_to_string(&mut event_response)
            .expect("event response");
        let event_body = event_response
            .split_once("\r\n\r\n")
            .map(|(_, body)| body)
            .expect("event body");
        let replay: serde_json::Value = serde_json::from_str(event_body).expect("event json");
        assert_eq!(replay["cursor_expired"], false);
        assert_eq!(replay["events"].as_array().expect("events").len(), 2);
        assert_eq!(replay["events"][1]["kind"], "interrupted");

        runtime.request_shutdown();
        server.join().expect("server").expect("serve");
        drop(runtime);
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn version_route_returns_active_version() {
        let _guard = ENVIRONMENT_LOCK.lock().expect("environment lock");
        let restore = EnvironmentRestore::capture(&["CODINAL_VERSION"]);
        unsafe {
            std::env::set_var("CODINAL_VERSION", "slice-a-test");
        }
        let data_dir = data_dir();
        let config = RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        let listener = config.bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, &config));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/version HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.contains("\"version\":\"slice-a-test\""));
        drop(restore);
        server.join().expect("server").expect("serve");
        fs::remove_dir(data_dir).expect("remove");
    }

    #[test]
    fn config_route_returns_non_secret_runtime_config() {
        let data_dir = data_dir();
        let config = RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        let listener = config.bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, &config));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/config HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.contains("\"runtime\":\"rust-native\""));
        assert!(response.contains("\"version\":\""));
        server.join().expect("server").expect("serve");
        fs::remove_dir(data_dir).expect("remove");
    }

    #[test]
    fn operation_protocol_route_accepts_resumes_and_cancels() {
        let data_dir = data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        assert!(runtime.config().operation_ledger().is_some());
        let envelope = OperationEnvelope::new(
            "request-operation-1",
            "operation-1",
            "idempotency-1",
            u128::MAX,
            "workspace.inspect",
            serde_json::json!({"path": "src"}),
        )
        .expect("envelope");
        let body = serde_json::to_string(&envelope).expect("envelope json");

        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let config = runtime.config().clone();
        let server = thread::spawn(move || serve_one(&listener, &config));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/operations HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.len()
        )
        .expect("submit request");
        let mut response = String::new();
        stream
            .read_to_string(&mut response)
            .expect("submit response");
        assert!(response.starts_with("HTTP/1.1 202 Accepted\r\n"));
        let response_body = response
            .split_once("\r\n\r\n")
            .map(|(_, body)| body)
            .expect("submit body");
        let ack: serde_json::Value = serde_json::from_str(response_body).expect("ack json");
        assert_eq!(ack["operation_id"], "operation-1");
        assert_eq!(ack["state"], "accepted");
        server.join().expect("server").expect("serve");

        let listener = runtime.config().bind().expect("resume listener");
        let port = listener.local_addr().expect("resume address").port();
        let config = runtime.config().clone();
        let server = thread::spawn(move || serve_one(&listener, &config));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("resume connect");
        stream
            .write_all(
                format!(
                    "GET /v1/operations/operation-1?after=0 HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nConnection: close\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("resume request");
        let mut response = String::new();
        stream
            .read_to_string(&mut response)
            .expect("resume response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));
        assert!(response.contains("\"operation-1\""), "{response}");
        server.join().expect("server").expect("serve");

        let listener = runtime.config().bind().expect("cancel listener");
        let port = listener.local_addr().expect("cancel address").port();
        let config = runtime.config().clone();
        let server = thread::spawn(move || serve_one(&listener, &config));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("cancel connect");
        stream
            .write_all(
                format!(
                    "POST /v1/operations/operation-1/cancel HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("cancel request");
        let mut response = String::new();
        stream
            .read_to_string(&mut response)
            .expect("cancel response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));
        assert!(response.contains("\"state\":\"cancelled\""));
        server.join().expect("server").expect("serve");
        drop(runtime);
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn operation_route_runs_approved_git_status_with_progress_and_receipt() {
        let _environment = ENVIRONMENT_LOCK.lock().expect("environment lock");
        let restore = EnvironmentRestore::capture(&[
            "CODINAL_WORKSPACE_ROOT",
            "CODINAL_EXPERIMENTAL_EXECUTION",
        ]);
        let data_dir = data_dir();
        let workspace = data_dir.join("workspace");
        fs::create_dir(&workspace).expect("workspace");
        let git_status = std::process::Command::new("git")
            .args(["init", "--quiet"])
            .current_dir(&workspace)
            .status()
            .expect("git init");
        assert!(git_status.success(), "git init failed: {git_status}");
        unsafe {
            std::env::set_var("CODINAL_WORKSPACE_ROOT", &workspace);
            std::env::set_var("CODINAL_EXPERIMENTAL_EXECUTION", "1");
        }
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let approval_id = "operation-git-approval-123456";
        assert!(runtime
            .config()
            .tool_gateway()
            .expect("tool gateway")
            .approve_once(approval_id));
        let envelope = OperationEnvelope::new(
            "request-git-status",
            "operation:git:status",
            "idempotency-git-status",
            u128::MAX,
            "git.status",
            serde_json::json!({"repo": "", "approval_id": approval_id}),
        )
        .expect("envelope");
        let body = serde_json::to_string(&envelope).expect("envelope body");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let config = runtime.config().clone();
        let server = thread::spawn(move || serve_one(&listener, &config));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/operations HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.len()
        )
        .expect("submit request");
        let mut response = String::new();
        stream
            .read_to_string(&mut response)
            .expect("submit response");
        assert!(response.starts_with("HTTP/1.1 202 Accepted\r\n"));
        server.join().expect("server").expect("serve");

        let ledger = runtime
            .config()
            .operation_ledger()
            .expect("operation ledger");
        let deadline = std::time::Instant::now() + Duration::from_secs(2);
        let resumed = loop {
            let resumed = ledger.resume("operation:git:status", 0).expect("resume");
            if resumed.receipt.is_some() || std::time::Instant::now() >= deadline {
                break resumed;
            }
            thread::sleep(Duration::from_millis(10));
        };
        let receipt = resumed.receipt.expect("operation receipt");
        assert_eq!(resumed.ack.state, OperationState::Succeeded);
        assert_eq!(receipt.state, OperationState::Succeeded);
        assert_eq!(resumed.progress.len(), 2);
        assert_eq!(resumed.progress[0].payload["stage"], "started");
        assert_eq!(resumed.progress[1].payload["stage"], "finished");
        assert_eq!(
            receipt.outcome["tool_execution"]["receipt"]["status"],
            "succeeded"
        );
        drop(runtime);
        drop(restore);
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn security_status_route_reports_unavailable() {
        let data_dir = data_dir();
        let config = RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        let listener = config.bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, &config));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/security/status HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.contains("\"available\":false"));
        assert!(response.contains("\"reason\":\"Security scanning is unavailable.\""));
        server.join().expect("server").expect("serve");
        fs::remove_dir(data_dir).expect("remove");
    }

    #[test]
    fn secrets_provider_status_returns_configured_flag_only() {
        let data_dir = data_dir();
        let config = RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        let bootstrap = ProviderSecrets::from_bootstrap(
            br#"{"sync_token":"0123456789abcdef0123456789abcdef","profiles":{"provider:openai":{"api_key":"provider-secret"}}}"#,
        )
        .expect("bootstrap");
        *config.provider_secrets.write().expect("provider secrets") = bootstrap;
        let listener = config.bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, &config));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/secrets/providers HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.contains("\"provider\":\"openai\""));
        assert!(response.contains("\"configured\":true"));
        assert!(response.contains("\"provider\":\"anthropic\""));
        server.join().expect("server").expect("serve");
        fs::remove_dir(data_dir).expect("remove");
    }

    #[test]
    fn fresh_runtime_lists_zero_sessions_instead_of_rejecting_request() {
        let data_dir = data_dir();
        let runtime = RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir)
            .expect("fresh runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(format!("GET /v1/sessions HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n").as_bytes())
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"), "{response}");
        assert!(response.ends_with("[]"), "{response}");
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn harness_inventory_route_is_read_only_and_reports_projection_drift() {
        let _environment_lock = ENVIRONMENT_LOCK.lock().expect("environment lock");
        let _restore = EnvironmentRestore::capture(&[
            "CODINAL_HARNESS_SOURCE_BUNDLE",
            "CODINAL_HARNESS_USER_OVERLAY",
            "CODINAL_HARNESS_LIVE_PROJECTION",
            "CODINAL_HARNESS_STATE_DIR",
            "CODINAL_HARNESS_HOST_PROJECTIONS",
        ]);
        let data_dir = data_dir();
        let source = data_dir.join("source");
        let overlay = data_dir.join("overlay");
        let live = data_dir.join("live");
        let state = data_dir.join("state");
        fs::create_dir_all(&source).expect("source");
        fs::create_dir_all(&overlay).expect("overlay");
        fs::create_dir_all(&live).expect("live");
        fs::write(source.join("AGENTS.md"), b"source").expect("source file");
        fs::write(live.join("AGENTS.md"), b"drift").expect("live file");
        unsafe {
            std::env::set_var("CODINAL_HARNESS_SOURCE_BUNDLE", &source);
            std::env::set_var("CODINAL_HARNESS_USER_OVERLAY", &overlay);
            std::env::set_var("CODINAL_HARNESS_LIVE_PROJECTION", &live);
            std::env::set_var("CODINAL_HARNESS_STATE_DIR", &state);
            std::env::set_var("CODINAL_HARNESS_HOST_PROJECTIONS", "[]");
        }
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/harness/inventory HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"), "{response}");
        assert!(response.contains("content_drift"), "{response}");
        assert!(!state.exists(), "read-only inventory created state");
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_route_requires_bearer_token() {
        let data_dir = data_dir();
        let runtime = RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir)
            .expect("fresh runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all("GET /v1/sessions HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n".as_bytes())
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 401 Unauthorized\r\n"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_messages_route_returns_messages() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/messages HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request messages");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_turns_route_returns_receipts_with_shared_wire_shape() {
        let data_dir = fixture_data_dir();
        let database = rusqlite::Connection::open(data_dir.join("codinal.db")).expect("db");
        database
            .execute_batch(
                "DROP TABLE turn_receipts;
                 CREATE TABLE turn_receipts (
                   turn_id TEXT PRIMARY KEY,
                   session_id TEXT NOT NULL,
                   outcome TEXT NOT NULL,
                   message_count INTEGER NOT NULL,
                   created_at TEXT NOT NULL
                 );
                 INSERT INTO turn_receipts
                   (turn_id, session_id, outcome, message_count, created_at)
                 VALUES
                   ('turn-receipt-api', 'session-1',
                    '{\"type\":\"turn_end\",\"status\":\"completed\"}',
                    2, '2026-01-01T00:01:00Z');",
            )
            .expect("receipt fixture");
        drop(database);

        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/turns HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request receipts");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));
        let body = response
            .split_once("\r\n\r\n")
            .map(|(_, body)| body)
            .expect("response body");
        let payload: serde_json::Value = serde_json::from_str(body).expect("JSON response");
        assert_eq!(payload.as_array().expect("receipt array").len(), 1);
        assert_eq!(payload[0]["turn_id"], "turn-receipt-api");
        assert_eq!(payload[0]["session_id"], "session-1");
        assert_eq!(
            payload[0]["outcome"],
            serde_json::json!({"type": "turn_end", "status": "completed"})
        );
        assert_eq!(payload[0]["message_count"], 2);
        assert_eq!(payload[0]["created_at"], "2026-01-01T00:01:00Z");
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_search_route_returns_matching_results() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/search?q=session-1 HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));
        assert!(response.contains("session-1"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_search_route_rejects_malformed_query() {
        let data_dir = data_dir();
        let runtime = RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir)
            .expect("fresh runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/search?limit=0 HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 400 Bad Request\r\n"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_goals_route_returns_goal_list() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/goals HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));
        assert!(response.ends_with("[]"), "{response}");
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_plans_route_returns_plan_artifacts() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/plans HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_plan_builds_route_returns_plan_builds() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/plan-builds HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_artifacts_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/artifacts HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("artifact operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_artifacts_read_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/artifacts/read HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("artifact operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_artifacts_write_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{"path":"README.md","content":"test"}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/artifacts/write HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("artifact operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_artifacts_reveal_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{"path":"README.md"}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/artifacts/reveal HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("artifact operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_checkpoints_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/checkpoints HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("checkpoint operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_checkpoint_restore_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{"message_index":3}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/checkpoints/cp-1/restore HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("checkpoint operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_project_index_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/project/index HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("project operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_project_index_route_post_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "POST /v1/sessions/session-1/project/index HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{{}}"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("project operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_project_index_delete_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "DELETE /v1/sessions/session-1/project/index HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("project operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_project_search_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/project/search HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("project operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_project_search_delete_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "DELETE /v1/sessions/session-1/project/search HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("project operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_project_open_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "POST /v1/sessions/session-1/project/open HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{{}}"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("project operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_workspace_files_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/workspace/files HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("workspace operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_roots_get_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/roots HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("roots operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_roots_post_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/roots HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("roots operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_roots_delete_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "DELETE /v1/sessions/session-1/roots HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("roots operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_tree_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/tree HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("session not found") || response.contains("not implemented"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_git_status_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/git/status HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("git operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_git_commit_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/git/commit HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("git operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_git_stage_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/git/stage HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("git operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_git_apply_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/git/apply HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("git operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_git_push_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/git/push HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("git operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_git_diff_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/git/diff HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("git operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_git_files_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/git/files HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("git operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_git_graph_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/git/graph HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("git operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_git_log_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/git/log HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("git operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_terminal_run_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{"command":"ls"}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/terminal/run HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("terminal operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_terminal_interrupt_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "POST /v1/sessions/session-1/terminal/interrupt HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Length: 0\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("terminal operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_workers_get_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/workers HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("worker operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_workers_post_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{"kind":"local"}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/workers HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("worker operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_mcp_connect_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{"name":"my-server","url":"stdio://local"}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/mcp/connect HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("mcp operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_mcp_servers_get_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/mcp/servers HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("mcp operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_mcp_servers_delete_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "DELETE /v1/sessions/session-1/mcp/servers/my-server HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("mcp operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_mcp_servers_patch_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{"enabled":false}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "PATCH /v1/sessions/session-1/mcp/servers/my-server HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("mcp operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_preview_evidence_get_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/preview/evidence HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("preview operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_preview_evidence_post_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{"kind":"screenshot"}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/preview/evidence HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("preview operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_preview_evidence_delete_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "DELETE /v1/sessions/session-1/preview/evidence HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("preview operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_preview_verify_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{"url":"http://127.0.0.1:8080/"}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/preview/verify HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("preview operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_preview_verify_origin_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{"url":"http://127.0.0.1:8080/"}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/preview/verify-origin HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("preview operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_side_conversations_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/side-conversations HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(
            response.contains("side-conversation operations are not implemented in rust runtime")
        );
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_complete_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/complete HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("session complete is not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_context_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/context HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("session context is not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_export_md_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/export.md HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("export operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_github_checks_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/github/checks HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("github operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_github_pr_get_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/github/pr HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("github operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_github_pr_post_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/github/pr HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("github operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_github_cleanup_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/github/cleanup HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("github operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_github_comment_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/github/comment HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("github operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_github_merge_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/github/merge HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("github operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_inline_edit_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/inline-edit HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("inline-edit operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_interrupt_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "POST /v1/sessions/session-1/interrupt HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Length: 0\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("session interrupt is not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_interactions_decision_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/interactions/abc123 HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("interaction operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_turns_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/turns HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("turn operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_plan_builds_post_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/plan-builds HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("plan-build operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_goals_post_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/goals HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("goal operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_security_scan_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let body = r#"{}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/security/scan HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        assert!(response.contains("security scan operations are not implemented in rust runtime"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn websocket_global_events_route_replays_runtime_events() {
        use tungstenite::client::IntoClientRequest;
        use tungstenite::http::header::{HeaderValue, SEC_WEBSOCKET_PROTOCOL};
        use tungstenite::Message;

        let data_dir = data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let store = runtime.config().runtime_store().expect("runtime store");
        store
            .create_turn("turn-global", "session-global")
            .expect("turn");
        store
            .append_event(
                "turn-global",
                "created",
                serde_json::json!({"session_id": "session-global"}),
            )
            .expect("event");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let config = runtime.config().clone();
        let server = thread::spawn(move || serve_one(&listener, &config));
        let mut request = format!("ws://127.0.0.1:{port}/ws/events")
            .into_client_request()
            .expect("websocket request");
        request.headers_mut().insert(
            SEC_WEBSOCKET_PROTOCOL,
            HeaderValue::from_str(&format!("codinal.v1, codinal.auth.{TOKEN}"))
                .expect("protocol header"),
        );
        let (mut socket, response) = tungstenite::connect(request).expect("websocket connect");
        assert_eq!(response.status().as_u16(), 101);
        assert_eq!(
            response
                .headers()
                .get(SEC_WEBSOCKET_PROTOCOL)
                .and_then(|value| value.to_str().ok()),
            Some("codinal.v1")
        );
        let message = socket.read().expect("event");
        let raw = match message {
            Message::Text(raw) => raw.to_string(),
            Message::Binary(raw) => {
                String::from_utf8(raw.as_slice().to_vec()).expect("event UTF-8")
            }
            other => panic!("unexpected websocket message: {other:?}"),
        };
        let event: serde_json::Value = serde_json::from_str(&raw).expect("event json");
        assert_eq!(event["type"], "turn_start");
        assert_eq!(event["turn_id"], "turn-global");
        socket.close(None).expect("close");
        server.join().expect("server").expect("serve");
        drop(runtime);
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn websocket_session_events_route_replays_only_requested_session() {
        use tungstenite::client::IntoClientRequest;
        use tungstenite::http::header::{HeaderValue, SEC_WEBSOCKET_PROTOCOL};
        use tungstenite::Message;

        let data_dir = data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let store = runtime.config().runtime_store().expect("runtime store");
        store
            .create_turn("turn-other", "session-other")
            .expect("turn");
        store
            .append_event(
                "turn-other",
                "created",
                serde_json::json!({"session_id": "session-other"}),
            )
            .expect("event");
        store
            .create_turn("turn-requested", "session-requested")
            .expect("turn");
        store
            .append_event(
                "turn-requested",
                "created",
                serde_json::json!({"session_id": "session-requested"}),
            )
            .expect("event");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let config = runtime.config().clone();
        let server = thread::spawn(move || serve_one(&listener, &config));
        let mut request = format!("ws://127.0.0.1:{port}/ws/session/session-requested")
            .into_client_request()
            .expect("websocket request");
        request.headers_mut().insert(
            SEC_WEBSOCKET_PROTOCOL,
            HeaderValue::from_str(&format!("codinal.v1, codinal.auth.{TOKEN}"))
                .expect("protocol header"),
        );
        let (mut socket, response) = tungstenite::connect(request).expect("websocket connect");
        assert_eq!(response.status().as_u16(), 101);
        let message = socket.read().expect("event");
        let raw = match message {
            Message::Text(raw) => raw.to_string(),
            Message::Binary(raw) => {
                String::from_utf8(raw.as_slice().to_vec()).expect("event UTF-8")
            }
            other => panic!("unexpected websocket message: {other:?}"),
        };
        let event: serde_json::Value = serde_json::from_str(&raw).expect("event json");
        assert_eq!(event["type"], "turn_start");
        assert_eq!(event["turn_id"], "turn-requested");
        socket.close(None).expect("close");
        server.join().expect("server").expect("serve");
        drop(runtime);
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_interactions_route_returns_empty_list() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "GET /v1/sessions/session-1/interactions HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));
        assert!(response.ends_with("[]"), "{response}");
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn goals_continue_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        let body = r#"{\"force\":true}"#;
        write!(
            stream,
            "POST /v1/goals/session-1/continue HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn goals_evidence_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        let body = r#"{\"summary\":\"ready\"}"#;
        write!(
            stream,
            "POST /v1/goals/session-1/evidence HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn goals_audit_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        let body = r#"{\"status\":\"done\",\"summary\":\"ok\"}"#;
        write!(
            stream,
            "POST /v1/goals/session-1/audit HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_fork_route_is_not_implemented() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "POST /v1/sessions/session-1/fork HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: 19\r\n\r\n{}",
                    "{\"message_index\":3}",
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 501 Not Implemented\r\n"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_patch_route_updates_chat_metadata() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "PATCH /v1/sessions/session-1 HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: 15\r\n\r\n{}",
                    "{\"pinned\":true}",
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn sessions_delete_route_removes_only_chat_data() {
        let data_dir = fixture_data_dir();
        let runtime =
            RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir).expect("runtime");
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(
                format!(
                    "DELETE /v1/sessions/session-1 HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
                )
                .as_bytes(),
            )
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn runtime_bootstrap_reuses_existing_installed_data_directory() {
        let data_dir = fixture_data_dir();
        let runtime = RuntimeBootstrap::from_values(free_loopback_port(), TOKEN, &data_dir)
            .expect("existing runtime");
        assert!(!codinal_storage::read_session_summaries(&data_dir, None)
            .expect("existing sessions")
            .is_empty());
        let listener = runtime.config().bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, runtime.config()));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(format!("GET /v1/health HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n").as_bytes())
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));
        server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn pending_approval_route_is_authenticated_and_public_session_scoped() {
        let data_dir = fixture_data_dir();
        let config = RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        config
            .approval_broker()
            .lock()
            .expect("broker")
            .request(
                "session-1",
                super::PermissionRequest {
                    tool_call_id: "call-1".to_owned(),
                    tool_name: "write_file".to_owned(),
                    arguments: serde_json::json!({"path": "README.md"}),
                    reason: "write workspace file".to_owned(),
                    risk: "write_local".to_owned(),
                    command: None,
                },
            )
            .expect("approval");
        let listener = config.bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || serve_one(&listener, &config));
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        stream
            .write_all(format!("GET /v1/sessions/session-1/approvals HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n").as_bytes())
            .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));
        assert!(response.contains("\"tool_name\":\"write_file\""));
        assert!(!response.contains("call-1"));
        server.join().expect("server").expect("serve");

        let worker_config =
            RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        let worker_listener = worker_config.bind().expect("listener");
        let worker_port = worker_listener.local_addr().expect("address").port();
        let worker_server = thread::spawn(move || serve_one(&worker_listener, &worker_config));
        let mut worker_stream = TcpStream::connect(("127.0.0.1", worker_port)).expect("connect");
        worker_stream
            .write_all(format!("GET /v1/sessions/worker-1/approvals HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n").as_bytes())
            .expect("request");
        let mut worker_response = String::new();
        worker_stream
            .read_to_string(&mut worker_response)
            .expect("response");
        assert!(worker_response.starts_with("HTTP/1.1 400 Bad Request\r\n"));
        worker_server.join().expect("server").expect("serve");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn confirmed_approval_decision_removes_only_the_selected_pending_item() {
        let data_dir = fixture_data_dir();
        let mut config =
            RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        config.readiness = RuntimeReadiness::owner_ready(None);
        config.attach_audit_ledger().expect("audit ledger");
        let broker = config.approval_broker();
        let approval_id = broker
            .lock()
            .expect("broker")
            .request(
                "session-1",
                super::PermissionRequest {
                    tool_call_id: "call-1".to_owned(),
                    tool_name: "write_file".to_owned(),
                    arguments: serde_json::json!({"path": "README.md"}),
                    reason: "write workspace file".to_owned(),
                    risk: "write_local".to_owned(),
                    command: None,
                },
            )
            .expect("approval");
        let listener = config.bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            serve_one(&listener, &config)?;
            serve_one(&listener, &config)
        });
        let unsupported = r#"{"outcome":"once"}"#;
        let mut unsupported_stream =
            TcpStream::connect(("127.0.0.1", port)).expect("connect unsupported");
        write!(
            unsupported_stream,
            "POST /v1/sessions/session-1/approvals/{approval_id} HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{unsupported}",
            unsupported.len()
        )
        .expect("unsupported request");
        let mut unsupported_response = String::new();
        unsupported_stream
            .read_to_string(&mut unsupported_response)
            .expect("unsupported response");
        assert!(unsupported_response.starts_with("HTTP/1.1 409 Conflict\r\n"));
        assert_eq!(broker.lock().expect("broker").pending("session-1").len(), 1);
        let body = r#"{"outcome":"deny"}"#;
        let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
        write!(
            stream,
            "POST /v1/sessions/session-1/approvals/{approval_id} HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .expect("request");
        let mut response = String::new();
        stream.read_to_string(&mut response).expect("response");
        assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));
        assert!(broker
            .lock()
            .expect("broker")
            .pending("session-1")
            .is_empty());
        server.join().expect("server").expect("serve");
        let audit =
            codinal_policy::AuditLedger::open(&data_dir, codinal_policy::AuditRedactor::default())
                .expect("audit ledger");
        let events = audit.list(Some("approval"), 10).expect("audit events");
        assert_eq!(events[0].action, "resolve");
        assert_eq!(events[0].subject, approval_id);
        assert_eq!(events[0].payload["outcome"], "deny");
        drop(audit);
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn live_provider_secret_update_requires_both_tokens_and_persists_no_secret() {
        let data_dir = fixture_data_dir();
        let mut config =
            RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        config.readiness = RuntimeReadiness::owner_ready(None);
        config.attach_audit_ledger().expect("audit ledger");
        *config.provider_secrets.write().expect("provider secrets") =
            ProviderSecrets::from_bootstrap(
                br#"{"sync_token":"abcdef0123456789abcdef0123456789","profiles":{}}"#,
            )
            .expect("bootstrap");
        let provider_secrets = Arc::clone(&config.provider_secrets);
        let listener = config.bind().expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            serve_one(&listener, &config)?;
            serve_one(&listener, &config)?;
            serve_one(&listener, &config)
        });
        let body = r#"{"api_key":"live-provider-secret"}"#;
        for (sync_token, expected) in [
            ("abcdef0123456789abcdef012345678x", "401 Unauthorized"),
            ("abcdef0123456789abcdef0123456789", "200 OK"),
        ] {
            let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
            write!(
                stream,
                "PUT /v1/secrets/providers/openai HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nX-Codinal-Secret-Sync: {sync_token}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{body}",
                body.len()
            )
            .expect("request");
            let mut response = String::new();
            stream.read_to_string(&mut response).expect("response");
            assert!(response.starts_with(&format!("HTTP/1.1 {expected}\r\n")));
        }
        let custom_body = r#"{"slug":"local","base_url":"http://127.0.0.1:1234/v1","api_key":"custom-provider-secret","failover_eligible":true}"#;
        let mut custom_stream = TcpStream::connect(("127.0.0.1", port)).expect("custom connect");
        write!(
            custom_stream,
            "POST /v1/providers/custom HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nX-Codinal-Secret-Sync: abcdef0123456789abcdef0123456789\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{custom_body}",
            custom_body.len()
        )
        .expect("custom request");
        let mut custom_response = String::new();
        custom_stream
            .read_to_string(&mut custom_response)
            .expect("custom response");
        assert!(custom_response.starts_with("HTTP/1.1 200 OK\r\n"));
        server.join().expect("server").expect("serve");
        let secrets = provider_secrets.read().expect("provider secrets");
        assert_eq!(
            secrets.api_key(&ProviderId::OpenAi),
            Some("live-provider-secret")
        );
        assert_eq!(
            secrets.api_key(&ProviderId::Custom("local".to_owned())),
            Some("custom-provider-secret")
        );
        drop(secrets);
        let bytes = fs::read(data_dir.join("audit.db")).expect("audit bytes");
        assert!(!bytes
            .windows("live-provider-secret".len())
            .any(|window| window == b"live-provider-secret"));
        assert!(!bytes
            .windows("custom-provider-secret".len())
            .any(|window| window == b"custom-provider-secret"));
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn ollama_turn_ingress_feeds_the_live_approval_broker() {
        let provider_listener = std::net::TcpListener::bind("127.0.0.1:0").expect("provider");
        let provider_port = provider_listener.local_addr().expect("address").port();
        let provider = thread::spawn(move || {
            let (mut stream, _) = provider_listener.accept().expect("accept");
            let _request = read_http_request(&mut stream);
            let body = r#"{"message":{"role":"assistant","content":"","tool_calls":[{"id":"call-1","function":{"name":"write_file","arguments":{"path":"README.md","content":"hello"}}}]},"done":true,"done_reason":"stop"}"#;
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                body.len()
            )
            .expect("response");
        });
        let turn = super::OllamaProvider::new(provider_port)
            .expect("ollama")
            .complete(
                "qwen3",
                &[serde_json::json!({"role": "user", "content": "update README"})],
                &[],
            )
            .expect("assistant turn");
        provider.join().expect("provider");

        let data_dir = fixture_data_dir();
        let config = RuntimeConfig::new(free_loopback_port(), TOKEN, &data_dir).expect("config");
        let result = config
            .ingest_provider_turn("session-1", turn)
            .expect("ingress");
        assert_eq!(result.pending_approval_ids.len(), 1);
        let pending = config
            .approval_broker()
            .lock()
            .expect("broker")
            .pending("session-1");
        assert_eq!(pending[0].tool_name, "write_file");
        assert_eq!(pending[0].arguments["path"], "README.md");
        fs::remove_dir_all(data_dir).expect("remove");
    }

    #[test]
    fn approval_expiry_is_read_from_the_durable_request() {
        let expired = serde_json::json!({"expires_at_ms": 0}).to_string();
        assert!(approval_request_is_expired(&expired));

        let future = serde_json::json!({
            "arguments": {APPROVAL_EXPIRY_KEY: now_ms().saturating_add(60_000)}
        })
        .to_string();
        assert!(!approval_request_is_expired(&future));
    }

    #[test]
    fn websocket_preserves_approval_expiry_as_a_terminal_event() {
        let message = super::websocket_event_message(&codinal_storage::RuntimeEventRecord {
            global_sequence: 1,
            turn_id: "turn-1".to_owned(),
            sequence: 1,
            kind: "approval_expired".to_owned(),
            payload: serde_json::json!({
                "reason": "approval_expired",
                "session_id": "session-1",
            }),
            at: 0.0,
        });
        assert_eq!(message["type"], "approval_expired");
        assert_eq!(message["error"], "approval_expired");
    }
}
