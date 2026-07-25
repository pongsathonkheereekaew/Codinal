use std::io;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};

use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::Engine;

const MINIMUM_TOKEN_LENGTH: usize = 32;

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

#[derive(Debug, Clone)]
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
        if token.len() < MINIMUM_TOKEN_LENGTH {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "session token must contain at least 32 characters",
            ));
        }
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
            .env("PYTHONUNBUFFERED", "1")
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        command
    }

    pub fn spawn(&self) -> io::Result<Child> {
        self.command().spawn()
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
