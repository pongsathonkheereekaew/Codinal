use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};

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
            .args(["-m", "runtime.control_plane"])
            .current_dir(&self.runtime_root)
            .env("CODINAL_SESSION_TOKEN", &self.token)
            .env("CODINAL_PORT", self.port.to_string())
            .env("CODINAL_DATA_DIR", &self.data_dir)
            .env("CODINAL_SECRET_BOOTSTRAP", "stdin-v1")
            .env("PYTHONUNBUFFERED", "1")
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        command
    }

    pub fn spawn_with_bootstrap(&self, secret_bootstrap: Vec<u8>) -> io::Result<Child> {
        let secret_bootstrap = Zeroizing::new(secret_bootstrap);
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
