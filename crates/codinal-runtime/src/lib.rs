//! Rust-native, loopback-only v1 runtime foundation.
//!
//! This listener is deliberately limited to the authenticated health route.
//! It is not wired into desktop launch yet: Python remains the only data
//! writer until the remaining v1 routes and storage migrations pass parity.

use std::collections::BTreeMap;
use std::fs;
use std::fs::{File, OpenOptions};
use std::io::{self, Read, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use zeroize::Zeroizing;

use fs2::FileExt;

pub use codinal_policy::{ApprovalChokepoint, Risk};

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
}

/// Owns a native runtime's exclusive data-directory lock for its lifetime.
/// The operating system releases the lock if the process exits unexpectedly.
struct RuntimeOwnerLock {
    file: File,
}

impl RuntimeOwnerLock {
    fn acquire(data_dir: &Path) -> io::Result<Self> {
        let file = OpenOptions::new()
            .create(true)
            .read(true)
            .write(true)
            .truncate(false)
            .open(data_dir.join(".codinal-runtime.lock"))?;
        file.try_lock_exclusive()?;
        Ok(Self { file })
    }
}

impl Drop for RuntimeOwnerLock {
    fn drop(&mut self) {
        let _ = self.file.unlock();
    }
}

/// Process bootstrap for the native runtime. Constructing this value reserves
/// the data directory before any writable store can be opened.
pub struct RuntimeBootstrap {
    config: RuntimeConfig,
    _owner_lock: RuntimeOwnerLock,
}

impl RuntimeBootstrap {
    pub fn from_values(port: u16, token: &str, data_dir: &Path) -> io::Result<Self> {
        let config = RuntimeConfig::new(port, token, data_dir)?;
        let owner_lock = RuntimeOwnerLock::acquire(config.data_dir())?;
        Ok(Self {
            config,
            _owner_lock: owner_lock,
        })
    }

    /// Read launch values once and remove the bearer token before starting the
    /// listener, preventing later child processes from inheriting it.
    pub fn from_environment() -> io::Result<Self> {
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
        Self::from_values(port, &token, Path::new(&data_dir))
    }

    pub fn config(&self) -> &RuntimeConfig {
        &self.config
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
        if port == 0 {
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
        })
    }

    pub fn bind(&self) -> io::Result<TcpListener> {
        TcpListener::bind(SocketAddrV4::new(Ipv4Addr::LOCALHOST, self.port))
    }

    pub fn data_dir(&self) -> &Path {
        &self.data_dir
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
    write_response(
        &mut stream,
        "404 Not Found",
        "{\"detail\":\"not found\"}",
        None,
    )
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
    Ok(RequestHead {
        method,
        path,
        headers,
    })
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

    fn free_loopback_port() -> u16 {
        std::net::TcpListener::bind("127.0.0.1:0")
            .expect("port listener")
            .local_addr()
            .expect("port address")
            .port()
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
}
