use std::io::{self, Read, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::Engine;
use zeroize::{Zeroize, Zeroizing};

const MINIMUM_TOKEN_LENGTH: usize = 32;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RuntimeLaunchMode {
    ReadOnly,
    Ready,
    Degraded,
}

pub fn validate_session_token(token: &str) -> io::Result<()> {
    if token.len() < MINIMUM_TOKEN_LENGTH {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "session token must contain at least 32 characters",
        ));
    }
    if !token
        .bytes()
        .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-' || byte == b'_')
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "session token must use URL-safe characters",
        ));
    }
    Ok(())
}

pub fn mint_session_token() -> io::Result<String> {
    let mut entropy = [0_u8; 32];
    getrandom::fill(&mut entropy).map_err(|error| io::Error::other(error.to_string()))?;
    Ok(URL_SAFE_NO_PAD.encode(entropy))
}

pub fn free_loopback_port() -> io::Result<u16> {
    std::net::TcpListener::bind(("127.0.0.1", 0))?
        .local_addr()
        .map(|address| address.port())
}

/// Native runtime process launch contract.
pub struct NativeRuntimeLaunch {
    binary: PathBuf,
    data_dir: PathBuf,
    port: u16,
    token: String,
    writer_ownership: bool,
}

impl NativeRuntimeLaunch {
    pub fn new(binary: PathBuf, data_dir: PathBuf, port: u16, token: String) -> io::Result<Self> {
        validate_session_token(&token)?;
        if port == 0 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "runtime port must not be zero",
            ));
        }
        Ok(Self {
            binary,
            data_dir,
            port,
            token,
            writer_ownership: false,
        })
    }

    pub fn with_writer_ownership(mut self) -> Self {
        self.writer_ownership = true;
        self
    }

    pub fn command(&self) -> Command {
        let mut command = Command::new(&self.binary);
        command
            .env("CODINAL_SESSION_TOKEN", &self.token)
            .env("CODINAL_PORT", self.port.to_string())
            .env("CODINAL_DATA_DIR", &self.data_dir)
            .env("CODINAL_PARENT_PID", std::process::id().to_string())
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        if self.writer_ownership {
            command.env("CODINAL_EXPERIMENTAL_EXECUTION", "1");
        } else {
            command.env_remove("CODINAL_EXPERIMENTAL_EXECUTION");
        }
        if let Some(workspace) = std::env::var_os("CODINAL_WORKSPACE") {
            command.env("CODINAL_WORKSPACE_ROOT", workspace);
        }
        command
    }

    pub fn spawn(&self) -> io::Result<NativeRuntimeProcess> {
        Ok(NativeRuntimeProcess(self.command().spawn()?))
    }

    pub fn spawn_with_bootstrap(
        &self,
        secret_bootstrap: Zeroizing<Vec<u8>>,
    ) -> io::Result<NativeRuntimeProcess> {
        let mut command = self.command();
        command
            .env("CODINAL_SECRET_BOOTSTRAP", "stdin-v1")
            .stdin(Stdio::piped());
        let mut child = command.spawn()?;
        let result = child
            .stdin
            .take()
            .ok_or_else(|| io::Error::other("native runtime stdin pipe is unavailable"))
            .and_then(|mut stdin| stdin.write_all(&secret_bootstrap));
        if let Err(error) = result {
            let _ = child.kill();
            let _ = child.wait();
            return Err(error);
        }
        Ok(NativeRuntimeProcess(child))
    }
}

impl Drop for NativeRuntimeLaunch {
    fn drop(&mut self) {
        self.token.zeroize();
    }
}

pub struct NativeRuntimeProcess(Child);

impl NativeRuntimeProcess {
    /// Request process termination and wait so a desktop shutdown cannot leave
    /// a second runtime writer behind.
    pub fn shutdown(&mut self) -> io::Result<()> {
        match self.0.try_wait()? {
            Some(_) => Ok(()),
            None => {
                self.0.kill()?;
                self.0.wait()?;
                Ok(())
            }
        }
    }
}

pub struct NativeRuntime {
    process: NativeRuntimeProcess,
}

impl NativeRuntime {
    pub fn shutdown(&mut self) -> io::Result<()> {
        self.process.shutdown()
    }
}

impl Drop for NativeRuntime {
    fn drop(&mut self) {
        let _ = self.shutdown();
    }
}

pub fn launch_native_runtime_with_bootstrap(
    binary: PathBuf,
    data_dir: &Path,
    port: u16,
    token: String,
    secret_bootstrap: Zeroizing<Vec<u8>>,
) -> io::Result<NativeRuntime> {
    std::fs::create_dir_all(data_dir)?;
    let token = Zeroizing::new(token);
    // Production stays read-only until the explicit Experimental execution
    // gate is enabled by a later release. The shadow runtime below is the
    // only launch path that opts into writer ownership today.
    let launch = NativeRuntimeLaunch::new(binary, data_dir.to_owned(), port, token.to_string())?;
    let mut process = launch.spawn_with_bootstrap(secret_bootstrap)?;
    if let Err(readiness_error) = wait_for_runtime_ready(port, &token, Duration::from_secs(2)) {
        process
            .shutdown()
            .map_err(|_| io::Error::other("runtime readiness and shutdown both failed"))?;
        return Err(readiness_error);
    }
    Ok(NativeRuntime { process })
}

/// A disposable Rust-runtime validation process. Its data directory is an
/// isolated SQLite snapshot and is removed when the process stops.
pub struct ShadowRuntime {
    process: NativeRuntimeProcess,
    snapshot_dir: PathBuf,
}

impl ShadowRuntime {
    pub fn shutdown(&mut self) -> io::Result<()> {
        let process_result = self.process.shutdown();
        let cleanup_result = remove_shadow_snapshot(&self.snapshot_dir);
        match (process_result, cleanup_result) {
            (Ok(()), Ok(())) => Ok(()),
            (Err(process_error), Ok(())) => Err(process_error),
            (Ok(()), Err(cleanup_error)) => Err(cleanup_error),
            (Err(_), Err(_)) => Err(io::Error::other(
                "shadow runtime shutdown and snapshot cleanup both failed",
            )),
        }
    }
}

impl Drop for ShadowRuntime {
    fn drop(&mut self) {
        let _ = self.shutdown();
    }
}

/// Copy a validated production snapshot, launch the native runtime against
/// that copy, and require its authenticated health response before returning.
/// This deliberately never selects the process as the production writer.
pub fn launch_shadow_runtime(
    binary: PathBuf,
    source_data_dir: &Path,
    snapshot_dir: &Path,
    port: u16,
    token: String,
) -> io::Result<ShadowRuntime> {
    validate_shadow_destination(source_data_dir, snapshot_dir)?;
    codinal_storage::create_v1_shadow_snapshot(source_data_dir, snapshot_dir)?;
    let token = Zeroizing::new(token);
    let launch =
        match NativeRuntimeLaunch::new(binary, snapshot_dir.to_owned(), port, token.to_string()) {
            Ok(launch) => launch.with_writer_ownership(),
            Err(error) => {
                let _ = remove_shadow_snapshot(snapshot_dir);
                return Err(error);
            }
        };
    let mut process = match launch.spawn() {
        Ok(process) => process,
        Err(error) => {
            let _ = remove_shadow_snapshot(snapshot_dir);
            return Err(error);
        }
    };
    if let Err(readiness_error) = wait_for_owner_runtime_ready(port, &token, Duration::from_secs(2))
    {
        process
            .shutdown()
            .map_err(|_| io::Error::other("shadow runtime readiness and shutdown both failed"))?;
        remove_shadow_snapshot(snapshot_dir)?;
        return Err(readiness_error);
    }
    Ok(ShadowRuntime {
        process,
        snapshot_dir: snapshot_dir.to_owned(),
    })
}

pub fn launch_shadow_runtime_with_bootstrap(
    binary: PathBuf,
    source_data_dir: &Path,
    snapshot_dir: &Path,
    port: u16,
    token: String,
    secret_bootstrap: Zeroizing<Vec<u8>>,
) -> io::Result<ShadowRuntime> {
    validate_shadow_destination(source_data_dir, snapshot_dir)?;
    codinal_storage::create_v1_shadow_snapshot(source_data_dir, snapshot_dir)?;
    let token = Zeroizing::new(token);
    let launch =
        match NativeRuntimeLaunch::new(binary, snapshot_dir.to_owned(), port, token.to_string()) {
            Ok(launch) => launch.with_writer_ownership(),
            Err(error) => {
                let _ = remove_shadow_snapshot(snapshot_dir);
                return Err(error);
            }
        };
    let mut process = match launch.spawn_with_bootstrap(secret_bootstrap) {
        Ok(process) => process,
        Err(error) => {
            let _ = remove_shadow_snapshot(snapshot_dir);
            return Err(error);
        }
    };
    if let Err(readiness_error) = wait_for_owner_runtime_ready(port, &token, Duration::from_secs(2))
    {
        process
            .shutdown()
            .map_err(|_| io::Error::other("shadow runtime readiness and shutdown both failed"))?;
        remove_shadow_snapshot(snapshot_dir)?;
        return Err(readiness_error);
    }
    Ok(ShadowRuntime {
        process,
        snapshot_dir: snapshot_dir.to_owned(),
    })
}

fn validate_shadow_destination(source_data_dir: &Path, snapshot_dir: &Path) -> io::Result<()> {
    let source = source_data_dir.canonicalize()?;
    let parent = snapshot_dir
        .parent()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "invalid shadow path"))?
        .canonicalize()?;
    if parent.starts_with(source) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "shadow snapshot must be outside production data",
        ));
    }
    Ok(())
}

fn remove_shadow_snapshot(snapshot_dir: &Path) -> io::Result<()> {
    match std::fs::remove_dir_all(snapshot_dir) {
        Ok(()) => Ok(()),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(error),
    }
}

/// Poll the native runtime's authenticated loopback health route until it is
/// ready or the caller-provided deadline expires.
pub fn wait_for_runtime_ready(
    port: u16,
    token: &str,
    timeout: Duration,
) -> io::Result<RuntimeLaunchMode> {
    validate_session_token(token)?;
    let address = SocketAddrV4::new(Ipv4Addr::LOCALHOST, port);
    let deadline = Instant::now() + timeout;
    let mut last_error;
    loop {
        match TcpStream::connect_timeout(&address.into(), Duration::from_millis(100)) {
            Ok(mut stream) => {
                let result = (|| {
                    stream.set_read_timeout(Some(Duration::from_millis(100)))?;
                    stream.set_write_timeout(Some(Duration::from_millis(100)))?;
                    let request = Zeroizing::new(format!(
                            "GET /v1/health HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {token}\r\nConnection: close\r\n\r\n"
                        ));
                    stream.write_all(request.as_bytes())?;
                    let mut response = String::new();
                    stream.read_to_string(&mut response)?;
                    let body = response
                        .split_once("\r\n\r\n")
                        .map(|(_, body)| body)
                        .ok_or_else(|| io::Error::other("native runtime health body missing"))?;
                    let health: serde_json::Value = serde_json::from_str(body)
                        .map_err(|_| io::Error::other("native runtime health body invalid"))?;
                    if !response.starts_with("HTTP/1.1 200 OK\r\n")
                        || health.get("status").and_then(serde_json::Value::as_str) != Some("ok")
                    {
                        return Err(io::Error::other("native runtime health check failed"));
                    }
                    match health.get("mode").and_then(serde_json::Value::as_str) {
                        Some("read_only") => Ok(RuntimeLaunchMode::ReadOnly),
                        Some("ready") => Ok(RuntimeLaunchMode::Ready),
                        Some("degraded") => Ok(RuntimeLaunchMode::Degraded),
                        Some("booting") => Err(io::Error::other("native runtime is still booting")),
                        None => Ok(RuntimeLaunchMode::ReadOnly),
                        Some(_) => Err(io::Error::other("native runtime health mode is invalid")),
                    }
                })();
                last_error = match result {
                    Ok(mode) => return Ok(mode),
                    Err(error) => error,
                };
            }
            Err(error) => last_error = error,
        }
        if Instant::now() >= deadline {
            return Err(last_error);
        }
        std::thread::sleep(Duration::from_millis(20));
    }
}

fn wait_for_owner_runtime_ready(port: u16, token: &str, timeout: Duration) -> io::Result<()> {
    match wait_for_runtime_ready(port, token, timeout)? {
        RuntimeLaunchMode::Ready | RuntimeLaunchMode::Degraded => Ok(()),
        mode => Err(io::Error::other(format!(
            "native runtime did not acquire writer ownership: {mode:?}"
        ))),
    }
}

#[cfg(test)]
mod tests {
    use super::{
        free_loopback_port, launch_shadow_runtime, wait_for_owner_runtime_ready,
        wait_for_runtime_ready, NativeRuntimeLaunch, RuntimeLaunchMode,
    };
    use rusqlite::Connection;
    use std::fs;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::path::PathBuf;
    use std::process::Command;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::thread;
    use std::time::Duration;

    const TOKEN: &str = "abcdefghijklmnopqrstuvwxyzABCDEF";
    static NEXT_TEST_DIR: AtomicU64 = AtomicU64::new(0);

    fn fixture_data_dir() -> PathBuf {
        let path = std::env::temp_dir().join(format!(
            "codinal-native-host-test-{}-{}",
            std::process::id(),
            NEXT_TEST_DIR.fetch_add(1, Ordering::Relaxed)
        ));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir(&path).expect("data directory");
        for database in codinal_storage::load_v1_fixture()
            .expect("fixture")
            .databases
        {
            let connection = Connection::open(path.join(&database.file)).expect("database");
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
        }
        path
    }

    fn ready_listener() -> (u16, thread::JoinHandle<()>) {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("connection");
            let mut request = [0_u8; 1024];
            let size = stream.read(&mut request).expect("request");
            assert!(std::str::from_utf8(&request[..size])
                .expect("request text")
                .contains(&format!("Authorization: Bearer {TOKEN}")));
            stream
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 110\r\n\r\n{\"status\":\"ok\",\"mode\":\"read_only\",\"reason_code\":\"owner_bootstrap_deferred\"}")
                .expect("response");
        });
        (port, server)
    }

    #[test]
    fn native_runtime_token_is_in_environment_not_arguments() {
        let launch = NativeRuntimeLaunch::new(
            PathBuf::from("/App/Resources/codinal-runtime"),
            PathBuf::from("/Data"),
            41000,
            "abcdefghijklmnopqrstuvwxyzABCDEF".to_owned(),
        )
        .expect("valid launch");
        let command = launch.command();
        let arguments: Vec<_> = command.get_args().collect();
        let token = command
            .get_envs()
            .find(|(name, _)| *name == std::ffi::OsStr::new("CODINAL_SESSION_TOKEN"))
            .and_then(|(_, value)| value);
        let parent_pid = command
            .get_envs()
            .find(|(name, _)| *name == std::ffi::OsStr::new("CODINAL_PARENT_PID"))
            .and_then(|(_, value)| value);

        assert!(arguments.is_empty());
        assert_eq!(
            token,
            Some(std::ffi::OsStr::new("abcdefghijklmnopqrstuvwxyzABCDEF"))
        );
        assert_eq!(
            parent_pid,
            Some(std::ffi::OsStr::new(&std::process::id().to_string()))
        );
        assert!(!arguments.iter().any(|argument| {
            argument
                .to_string_lossy()
                .contains("abcdefghijklmnopqrstuvwxyzABCDEF")
        }));
    }

    #[test]
    fn writer_ownership_is_an_explicit_launch_contract() {
        let read_only = NativeRuntimeLaunch::new(
            PathBuf::from("/App/Resources/codinal-runtime"),
            PathBuf::from("/Data"),
            41000,
            TOKEN.to_owned(),
        )
        .expect("read-only launch")
        .command();
        let owner = NativeRuntimeLaunch::new(
            PathBuf::from("/App/Resources/codinal-runtime"),
            PathBuf::from("/Data"),
            41000,
            TOKEN.to_owned(),
        )
        .expect("owner launch")
        .with_writer_ownership()
        .command();
        let execution_flag = |command: &Command| {
            command
                .get_envs()
                .find(|(name, _)| *name == std::ffi::OsStr::new("CODINAL_EXPERIMENTAL_EXECUTION"))
                .and_then(|(_, value)| value.map(std::ffi::OsStr::to_os_string))
        };

        assert_eq!(execution_flag(&read_only), None);
        assert_eq!(execution_flag(&owner), Some(std::ffi::OsString::from("1")));
    }

    #[test]
    fn read_only_mode_is_accepted_without_being_ready() {
        let (port, server) = ready_listener();
        assert_eq!(
            wait_for_runtime_ready(port, TOKEN, Duration::from_secs(1)).expect("ready"),
            RuntimeLaunchMode::ReadOnly
        );
        server.join().expect("server");
    }

    #[test]
    fn degraded_owner_mode_reaches_the_ui_for_explicit_capability_probe() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("connection");
            let mut request = [0_u8; 1024];
            let size = stream.read(&mut request).expect("request");
            assert!(std::str::from_utf8(&request[..size])
                .expect("request text")
                .contains(&format!("Authorization: Bearer {TOKEN}")));
            let body =
                r#"{"status":"ok","mode":"degraded","reason_code":"capability_probe_required"}"#;
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Length: {}\r\n\r\n{}",
                body.len(),
                body
            )
            .expect("response");
        });
        wait_for_owner_runtime_ready(port, TOKEN, Duration::from_secs(1))
            .expect("degraded owner remains available for explicit probe");
        server.join().expect("server");
    }

    #[test]
    fn writer_owner_launch_rejects_a_read_only_runtime() {
        let (port, server) = ready_listener();
        let error = wait_for_owner_runtime_ready(port, TOKEN, Duration::from_secs(1))
            .expect_err("read-only runtime was accepted as writer owner");
        assert!(error
            .to_string()
            .contains("did not acquire writer ownership"));
        server.join().expect("server");
    }

    #[test]
    fn failed_shadow_launch_removes_the_isolated_snapshot() {
        let source = fixture_data_dir();
        let snapshot = source.with_extension("shadow");
        assert!(launch_shadow_runtime(
            PathBuf::from("/usr/bin/true"),
            &source,
            &snapshot,
            free_loopback_port().expect("port"),
            TOKEN.to_owned(),
        )
        .is_err());
        assert!(!snapshot.exists());
        assert!(codinal_storage::inspect_v1_data_dir(&source)
            .expect("source inspection")
            .is_empty());
        fs::remove_dir_all(source).expect("remove source");
    }

    #[test]
    fn shadow_launch_rejects_a_destination_inside_production_data() {
        let source = fixture_data_dir();
        let snapshot = source.join("shadow");
        let result = launch_shadow_runtime(
            PathBuf::from("/usr/bin/true"),
            &source,
            &snapshot,
            free_loopback_port().expect("port"),
            TOKEN.to_owned(),
        );
        let error = match result {
            Ok(_) => panic!("nested shadow destination was accepted"),
            Err(error) => error,
        };
        assert_eq!(error.kind(), std::io::ErrorKind::InvalidInput);
        assert!(!snapshot.exists());
        fs::remove_dir_all(source).expect("remove source");
    }
}
