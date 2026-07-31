//! Rust-native, loopback-only v1 runtime foundation.
//!
//! This listener is deliberately limited to the authenticated health route.
//! It is not wired into desktop launch yet: Python remains the only data
//! writer until the remaining v1 routes and storage migrations pass parity.

use fs2::FileExt;
use std::collections::BTreeMap;
use std::fs;
use std::fs::{File, OpenOptions};
use std::io::{self, Read, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use zeroize::Zeroizing;

pub use codinal_policy::{ApprovalBroker, ApprovalChokepoint, PermissionRequest, Risk};
pub use codinal_providers::{AssistantTurn, OllamaProvider, ProviderId, ProviderSecrets, ToolCall};

static NEXT_EVENT_HUB_ID: AtomicU64 = AtomicU64::new(1);

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

pub struct RuntimeConfig {
    port: u16,
    token: Zeroizing<String>,
    data_dir: PathBuf,
    approval_broker: Arc<Mutex<ApprovalBroker>>,
    audit_ledger: Option<codinal_policy::AuditLedger>,
    ollama_port: u16,
}

#[derive(Debug, serde::Serialize, PartialEq, Eq)]
pub struct TurnIngressResult {
    pub pending_approval_ids: Vec<String>,
    pub allowed_read_tool_call_ids: Vec<String>,
    pub rejected_tool_call_ids: Vec<String>,
}

/// Process bootstrap for the native runtime. Constructing this value reserves
/// the data directory before any writable store can be opened.
pub struct RuntimeBootstrap {
    config: RuntimeConfig,
    provider_secrets: ProviderSecrets,
    _owner_lock: RuntimeOwnerLock,
}

struct RuntimeOwnerLock(File);

impl RuntimeOwnerLock {
    fn acquire(data_dir: &Path) -> io::Result<Self> {
        let lock = OpenOptions::new()
            .create(true)
            .read(true)
            .write(true)
            .truncate(false)
            .open(data_dir.join(".codinal-runtime.lock"))?;
        lock.try_lock_exclusive()?;
        Ok(Self(lock))
    }
}

impl Drop for RuntimeOwnerLock {
    fn drop(&mut self) {
        let _ = self.0.unlock();
    }
}

impl RuntimeBootstrap {
    pub fn from_values(port: u16, token: &str, data_dir: &Path) -> io::Result<Self> {
        let mut config = RuntimeConfig::new(port, token, data_dir)?;
        let owner_lock = RuntimeOwnerLock::acquire(config.data_dir())?;
        config.attach_audit_ledger()?;
        Ok(Self {
            config,
            provider_secrets: ProviderSecrets::empty(),
            _owner_lock: owner_lock,
        })
    }

    /// Read launch values once and remove the bearer token before starting the
    /// listener, preventing later child processes from inheriting it.
    pub fn from_environment() -> io::Result<Self> {
        let stdin = io::stdin();
        Self::from_environment_reader(&mut stdin.lock())
    }

    pub fn from_environment_reader(reader: &mut impl Read) -> io::Result<Self> {
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
        let mut runtime = Self::from_values(port, &token, Path::new(&data_dir))?;
        let channel = std::env::var("CODINAL_SECRET_BOOTSTRAP").unwrap_or_default();
        // Safe at process startup before the runtime creates threads.
        unsafe { std::env::remove_var("CODINAL_SECRET_BOOTSTRAP") };
        runtime.provider_secrets = match channel.as_str() {
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
        Ok(runtime)
    }

    pub fn config(&self) -> &RuntimeConfig {
        &self.config
    }

    pub fn provider_secrets(&self) -> &ProviderSecrets {
        &self.provider_secrets
    }

    pub fn serve_forever(&self) -> io::Result<()> {
        let listener = self.config.bind()?;
        loop {
            let (stream, peer) = listener.accept()?;
            if peer.ip().is_loopback() {
                // Bad or disconnected clients must not release the runtime's
                // owner lock. Listener failures remain fatal to the process.
                let _ = serve_stream(stream, &self.config);
            }
        }
    }
}

/// Start the packaged native runtime from its host-supplied environment.
pub fn run_from_environment() -> io::Result<()> {
    RuntimeBootstrap::from_environment()?.serve_forever()
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
            ollama_port,
        })
    }

    pub fn bind(&self) -> io::Result<TcpListener> {
        TcpListener::bind(SocketAddrV4::new(Ipv4Addr::LOCALHOST, self.port))
    }

    pub fn data_dir(&self) -> &Path {
        &self.data_dir
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

    pub fn ingest_provider_turn(
        &self,
        session_id: &str,
        turn: AssistantTurn,
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
            let approval_id = match broker.request(
                session_id,
                PermissionRequest {
                    tool_call_id: call.id,
                    tool_name: call.name,
                    arguments: serde_json::Value::Object(call.arguments),
                    reason: format!("tool requires {risk} approval"),
                    risk: risk.to_owned(),
                    command,
                },
            ) {
                Ok(approval_id) => approval_id,
                Err(error) => {
                    for approval_id in &result.pending_approval_ids {
                        broker.resolve(session_id, approval_id);
                    }
                    return Err(error);
                }
            };
            result.pending_approval_ids.push(approval_id);
        }
        Ok(result)
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
            "write_file",
            "Write a workspace file",
            vec!["path", "content"],
        ),
        ("run_shell", "Run a sandboxed command", vec!["command"]),
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

/// Serve one connection. This narrow lifecycle seam allows a future host to
/// own graceful shutdown without exposing the bearer token to a UI client.
pub fn serve_one(listener: &TcpListener, config: &RuntimeConfig) -> io::Result<()> {
    let (stream, peer) = listener.accept()?;
    if !peer.ip().is_loopback() {
        return Ok(());
    }
    serve_stream(stream, config)
}

fn serve_stream(mut stream: TcpStream, config: &RuntimeConfig) -> io::Result<()> {
    stream.set_read_timeout(Some(std::time::Duration::from_secs(2)))?;
    stream.set_write_timeout(Some(std::time::Duration::from_secs(2)))?;
    let request = read_headers(&mut stream)?;
    let authenticated = request.headers.iter().any(|(name, value)| {
        name == "authorization" && valid_bearer(value, config.token.as_bytes())
    });
    if !authenticated {
        return write_response(
            &mut stream,
            "401 Unauthorized",
            "{\"detail\":\"unauthorized\"}",
            Some("Bearer"),
        );
    }
    if request.method == "GET" && request.path == "/v1/health" {
        return write_response(&mut stream, "200 OK", "{\"status\":\"ok\"}", None);
    }
    if request.method == "GET" && request.path.starts_with("/v1/sessions") {
        if let Some(query) = request.path.strip_prefix("/v1/sessions") {
            if query.is_empty() || query.starts_with('?') {
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
            let approvals = config
                .approval_broker
                .lock()
                .map_err(|_| io::Error::other("approval broker lock poisoned"))?
                .pending(session_id);
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
            if outcome != Some("deny") {
                return write_response(
                    &mut stream,
                    "409 Conflict",
                    "{\"detail\":\"approval outcome is not yet applicable\"}",
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
                    payload: serde_json::json!({"outcome": outcome.expect("validated outcome")}),
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
            let resolved = broker.resolve(session_id, approval_id);
            return if resolved {
                write_response(&mut stream, "200 OK", "{\"ok\":true}", None)
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

struct RequestHead {
    method: String,
    path: String,
    headers: Vec<(String, String)>,
    body: Vec<u8>,
}

fn read_headers(stream: &mut TcpStream) -> io::Result<RequestHead> {
    let mut request = Vec::with_capacity(1024);
    let mut buffer = [0_u8; 1024];
    loop {
        let read = stream.read(&mut buffer)?;
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
            Ok((name.trim().to_ascii_lowercase(), value.trim().to_owned()))
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
        let read = stream.read(&mut buffer)?;
        if read == 0 {
            return Err(io::Error::new(
                io::ErrorKind::UnexpectedEof,
                "incomplete request body",
            ));
        }
        request.extend_from_slice(&buffer[..read]);
    }
    let body = request[body_start..body_start + content_length].to_vec();
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
        serve_one, EventHub, Risk, RuntimeBootstrap, RuntimeConfig, RuntimeEvent, RuntimePolicy,
    };
    use std::ffi::OsString;
    use std::fs;
    use std::io::{Read, Write};
    use std::net::TcpStream;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::sync::{Arc, Mutex};
    use std::thread;

    const TOKEN: &str = "0123456789abcdef0123456789abcdef";
    static NEXT_TEST_DIR: AtomicU64 = AtomicU64::new(0);
    static ENVIRONMENT_LOCK: Mutex<()> = Mutex::new(());

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
                         CREATE TABLE sessions (
                           session_id TEXT PRIMARY KEY, origin TEXT, updated_at TEXT NOT NULL
                         );
                         CREATE TABLE messages (
                           session_id TEXT NOT NULL, sequence INTEGER NOT NULL, payload TEXT NOT NULL,
                           PRIMARY KEY (session_id, sequence)
                         );
                         INSERT INTO sessions VALUES ('session-1', NULL, '2026-01-01T00:00:00Z');
                         INSERT INTO sessions VALUES ('worker-1', 'worker', '2026-01-01T00:00:00Z');",
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
        assert_eq!(config.inspect_storage().expect("inspect").len(), 9);
        assert!(path.read_dir().expect("read").next().is_none());
        fs::remove_dir(path).expect("remove");
    }

    #[test]
    fn runtime_bootstrap_exclusively_owns_its_data_directory() {
        let path = data_dir();
        let owner = RuntimeBootstrap::from_values(3000, TOKEN, &path).expect("first owner");
        assert!(RuntimeBootstrap::from_values(3001, TOKEN, &path).is_err());
        drop(owner);
        assert!(RuntimeBootstrap::from_values(3001, TOKEN, &path).is_ok());
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
                .api_key(&super::ProviderId::OpenAi),
            Some("provider-secret")
        );
        assert!(std::env::var_os("CODINAL_SECRET_BOOTSTRAP").is_none());
        assert!(format!("{:?}", runtime.provider_secrets()).contains("configured_profiles"));
        assert!(!format!("{:?}", runtime.provider_secrets()).contains("provider-secret"));
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
        assert!(response.ends_with(expected["json"].to_string().as_str()));
        server.join().expect("server").expect("serve");
        fs::remove_dir(data_dir).expect("remove");
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
}
