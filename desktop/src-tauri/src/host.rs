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
    use super::{runtime_layout_from, NativeRuntimeLaunch, RuntimeLayout, SidecarLaunch};
    use std::path::{Path, PathBuf};

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
}
