use std::io::{self, Read, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::Engine;
use zeroize::{Zeroize, Zeroizing};

const MINIMUM_TOKEN_LENGTH: usize = 32;

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

pub fn initialization_script(port: u16, token: &str) -> String {
    let http = serde_json::json!(format!("http://127.0.0.1:{port}"));
    let websocket = serde_json::json!(format!("ws://127.0.0.1:{port}"));
    let token = serde_json::json!(token);
    format!(
        "Object.defineProperties(window, {{\
         __CODINAL_HTTP__: {{ value: {http}, writable: false }},\
         __CODINAL_WS__: {{ value: {websocket}, writable: false }},\
         __CODINAL_TOKEN__: {{ value: {token}, writable: false }}\
         }});"
    )
}

pub struct SidecarLaunch {
    python: PathBuf,
    runtime_root: PathBuf,
    data_dir: PathBuf,
    port: u16,
    token: String,
}

/// Native runtime process launch contract. This is separate from
/// `SidecarLaunch` while Python remains the reference implementation.
pub struct NativeRuntimeLaunch {
    binary: PathBuf,
    data_dir: PathBuf,
    port: u16,
    token: String,
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
        })
    }

    pub fn command(&self) -> Command {
        let mut command = Command::new(&self.binary);
        command
            .env("CODINAL_SESSION_TOKEN", &self.token)
            .env("CODINAL_PORT", self.port.to_string())
            .env("CODINAL_DATA_DIR", &self.data_dir)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
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
            Ok(launch) => launch,
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
    if let Err(readiness_error) = wait_for_runtime_ready(port, &token, Duration::from_secs(2)) {
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
            Ok(launch) => launch,
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
    if let Err(readiness_error) = wait_for_runtime_ready(port, &token, Duration::from_secs(2)) {
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
pub fn wait_for_runtime_ready(port: u16, token: &str, timeout: Duration) -> io::Result<()> {
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
                    (response.starts_with("HTTP/1.1 200 OK\r\n")
                        && response.ends_with("{\"status\":\"ok\"}"))
                    .then_some(())
                    .ok_or_else(|| io::Error::other("native runtime health check failed"))
                })();
                last_error = match result {
                    Ok(()) => return Ok(()),
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

impl SidecarLaunch {
    pub fn new(
        python: PathBuf,
        runtime_root: PathBuf,
        data_dir: PathBuf,
        port: u16,
        token: String,
    ) -> io::Result<Self> {
        validate_session_token(&token)?;
        if port == 0 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "sidecar port must not be zero",
            ));
        }
        Ok(Self {
            python,
            runtime_root,
            data_dir,
            port,
            token,
        })
    }

    pub fn command(&self) -> Command {
        let mut command = Command::new(&self.python);
        command
            .args(["-B", "-m", "runtime.control_plane"])
            .current_dir(&self.runtime_root)
            .env("CODINAL_SESSION_TOKEN", &self.token)
            .env("CODINAL_PORT", self.port.to_string())
            .env("CODINAL_DATA_DIR", &self.data_dir)
            .env("CODINAL_SECRET_BOOTSTRAP", "stdin-v1")
            .env("PYTHONDONTWRITEBYTECODE", "1")
            .env("PYTHONUNBUFFERED", "1")
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        if let Ok(helper) = std::env::current_exe() {
            command.env("CODINAL_HOST_HELPER", helper);
        }
        command
    }

    pub fn spawn_with_bootstrap(&self, secret_bootstrap: Zeroizing<Vec<u8>>) -> io::Result<Child> {
        let mut child = self.command().spawn()?;
        let result = child
            .stdin
            .take()
            .ok_or_else(|| io::Error::other("sidecar stdin pipe is unavailable"))
            .and_then(|mut stdin| stdin.write_all(&secret_bootstrap));
        if let Err(error) = result {
            let _ = child.kill();
            let _ = child.wait();
            return Err(error);
        }
        Ok(child)
    }
}

impl Drop for SidecarLaunch {
    fn drop(&mut self) {
        self.token.zeroize();
    }
}

pub fn development_runtime_root() -> PathBuf {
    std::env::var_os("CODINAL_RUNTIME_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("../..")
                .to_path_buf()
        })
}

pub fn python_executable(runtime_root: &Path) -> PathBuf {
    std::env::var_os("CODINAL_PYTHON")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            if cfg!(windows) {
                runtime_root.join(".venv/Scripts/python.exe")
            } else {
                runtime_root.join(".venv/bin/python")
            }
        })
}

#[derive(Debug, PartialEq, Eq)]
pub struct RuntimeLayout {
    pub runtime_root: PathBuf,
    pub python: PathBuf,
}

pub fn runtime_layout(resource_dir: &Path, development: bool) -> RuntimeLayout {
    let override_root = std::env::var_os("CODINAL_RUNTIME_ROOT").map(PathBuf::from);
    let override_python = std::env::var_os("CODINAL_PYTHON").map(PathBuf::from);
    runtime_layout_from(resource_dir, development, override_root, override_python)
}

pub fn runtime_layout_from(
    resource_dir: &Path,
    development: bool,
    override_root: Option<PathBuf>,
    override_python: Option<PathBuf>,
) -> RuntimeLayout {
    let override_root = development.then_some(override_root).flatten();
    let override_python = development.then_some(override_python).flatten();
    let runtime_root = override_root.unwrap_or_else(|| {
        if development {
            Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("../..")
                .to_path_buf()
        } else {
            resource_dir.join("runtime")
        }
    });
    let python = override_python.unwrap_or_else(|| {
        if development {
            python_executable(&runtime_root)
        } else {
            resource_dir.join("python/bin/python3")
        }
    });
    RuntimeLayout {
        runtime_root,
        python,
    }
}

pub fn validate_runtime_layout(layout: &RuntimeLayout) -> io::Result<()> {
    if !layout.runtime_root.is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            "bundled runtime is unavailable",
        ));
    }
    if !layout.python.is_file() {
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            "bundled Python is unavailable",
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{
        free_loopback_port, launch_shadow_runtime, runtime_layout_from, wait_for_runtime_ready,
        NativeRuntimeLaunch, RuntimeLayout, SidecarLaunch,
    };
    use rusqlite::Connection;
    use std::fs;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::path::{Path, PathBuf};
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
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 15\r\n\r\n{\"status\":\"ok\"}")
                .expect("response");
        });
        (port, server)
    }

    #[test]
    fn release_layout_uses_app_resources() {
        assert_eq!(
            runtime_layout_from(Path::new("/App/Resources"), false, None, None),
            RuntimeLayout {
                runtime_root: PathBuf::from("/App/Resources/runtime"),
                python: PathBuf::from("/App/Resources/python/bin/python3"),
            }
        );
    }

    #[test]
    fn explicit_layout_overrides_are_preserved() {
        assert_eq!(
            runtime_layout_from(
                Path::new("/ignored"),
                true,
                Some(PathBuf::from("/custom/runtime")),
                Some(PathBuf::from("/custom/python")),
            ),
            RuntimeLayout {
                runtime_root: PathBuf::from("/custom/runtime"),
                python: PathBuf::from("/custom/python"),
            }
        );
    }

    #[test]
    fn release_layout_ignores_unsigned_environment_overrides() {
        assert_eq!(
            runtime_layout_from(
                Path::new("/App/Resources"),
                false,
                Some(PathBuf::from("/unsigned/runtime")),
                Some(PathBuf::from("/unsigned/python")),
            ),
            RuntimeLayout {
                runtime_root: PathBuf::from("/App/Resources/runtime"),
                python: PathBuf::from("/App/Resources/python/bin/python3"),
            }
        );
    }

    #[test]
    fn sidecar_never_writes_bytecode_into_signed_app_resources() {
        let launch = SidecarLaunch::new(
            PathBuf::from("/App/Resources/python/bin/python3"),
            PathBuf::from("/App/Resources/runtime"),
            PathBuf::from("/Data"),
            41000,
            "abcdefghijklmnopqrstuvwxyzABCDEF".to_owned(),
        )
        .expect("valid launch");
        let command = launch.command();
        let args: Vec<_> = command.get_args().collect();
        let envs: Vec<_> = command.get_envs().collect();

        assert_eq!(args[0], "-B");
        assert!(envs.iter().any(|(key, value)| {
            key.to_string_lossy() == "PYTHONDONTWRITEBYTECODE"
                && value.is_some_and(|value| value.to_string_lossy() == "1")
        }));
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

        assert!(arguments.is_empty());
        assert_eq!(
            token,
            Some(std::ffi::OsStr::new("abcdefghijklmnopqrstuvwxyzABCDEF"))
        );
        assert!(!arguments.iter().any(|argument| {
            argument
                .to_string_lossy()
                .contains("abcdefghijklmnopqrstuvwxyzABCDEF")
        }));
    }

    #[test]
    fn readiness_probe_requires_authenticated_loopback_health() {
        let (port, server) = ready_listener();
        wait_for_runtime_ready(port, TOKEN, Duration::from_secs(1)).expect("ready");
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
