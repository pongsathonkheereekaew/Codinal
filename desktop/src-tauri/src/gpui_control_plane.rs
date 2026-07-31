//! Versioned native-client contract for the experimental GPUI shell.
//!
//! This module owns the authenticated loopback protocol boundary.  GPUI views
//! receive decoded data, never the bearer token or a URL containing it.

use std::io::{self, Read, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpStream};
use std::time::Duration;

use crate::host::validate_session_token;
use zeroize::{Zeroize, Zeroizing};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ControlPlaneVersion {
    V1,
}

impl ControlPlaneVersion {
    const fn path_prefix(self) -> &'static str {
        match self {
            Self::V1 => "/v1",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DesktopShell {
    Tauri,
    Gpui,
}

impl DesktopShell {
    /// Select a shell only for development. Release builds always retain the
    /// signed Tauri shell until the GPUI parity gates have passed.
    pub fn select(value: Option<&str>, development: bool) -> io::Result<Self> {
        match value.unwrap_or("tauri") {
            "tauri" => Ok(Self::Tauri),
            "gpui" if development => Ok(Self::Gpui),
            "gpui" => Err(io::Error::new(
                io::ErrorKind::PermissionDenied,
                "the GPUI shell is available only in development builds",
            )),
            _ => Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "desktop_shell must be tauri or gpui",
            )),
        }
    }
}

/// An authenticated native request descriptor. It intentionally has no
/// `Debug` implementation, preventing bearer credentials from entering logs.
pub struct ControlPlaneRequest {
    version: ControlPlaneVersion,
    method: &'static str,
    url: String,
    path: String,
    port: u16,
    authorization: Zeroizing<String>,
}

impl ControlPlaneRequest {
    pub const fn version(&self) -> ControlPlaneVersion {
        self.version
    }

    pub const fn method(&self) -> &'static str {
        self.method
    }

    pub fn url(&self) -> &str {
        &self.url
    }

    pub fn header(&self, name: &str) -> Option<&str> {
        (name.eq_ignore_ascii_case("authorization")).then_some(self.authorization.as_str())
    }

    /// Execute one authenticated JSON request against the loopback sidecar.
    /// The request body is intentionally absent in G0; mutation payloads are
    /// added only alongside their typed reducers in later GPUI milestones.
    pub fn execute_json(&self) -> io::Result<serde_json::Value> {
        let address = SocketAddrV4::new(Ipv4Addr::LOCALHOST, self.port);
        let mut stream = TcpStream::connect_timeout(&address.into(), Duration::from_secs(2))?;
        stream.set_read_timeout(Some(Duration::from_secs(2)))?;
        stream.set_write_timeout(Some(Duration::from_secs(2)))?;

        let request = Zeroizing::new(format!(
            "{} {} HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nAuthorization: {}\r\nAccept: application/json\r\nConnection: close\r\n\r\n",
            self.method,
            self.path,
            self.port,
            self.authorization.as_str()
        ));
        stream.write_all(request.as_bytes())?;
        stream.flush()?;

        let mut response = Vec::new();
        stream.read_to_end(&mut response)?;
        let header_end = response
            .windows(4)
            .position(|window| window == b"\r\n\r\n")
            .ok_or_else(|| io::Error::other("control plane returned malformed HTTP"))?;
        let headers = std::str::from_utf8(&response[..header_end])
            .map_err(|_| io::Error::other("control plane returned non-UTF-8 HTTP headers"))?;
        let status = headers.split_whitespace().nth(1);
        if !matches!(status, Some("200" | "201" | "202" | "204")) {
            return Err(io::Error::other("control plane rejected request"));
        }
        let body = &response[header_end + 4..];
        if body.is_empty() {
            return Ok(serde_json::Value::Null);
        }
        serde_json::from_slice(body)
            .map_err(|_| io::Error::other("control plane returned invalid JSON"))
    }
}

/// A WebSocket descriptor that authenticates through the existing protocol
/// subprotocol, never a query parameter.
pub struct ControlPlaneEventStream {
    url: String,
    subprotocols: Vec<String>,
}

impl Drop for ControlPlaneEventStream {
    fn drop(&mut self) {
        self.subprotocols.zeroize();
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

/// Native-only owner of the sidecar bearer token for the GPUI migration.
///
/// Transport execution is intentionally deferred to the GPUI shell. This
/// G0 contract makes every required route and auth mechanism explicit first.
pub struct ControlPlaneClient {
    port: u16,
    token: Zeroizing<String>,
    version: ControlPlaneVersion,
}

impl ControlPlaneClient {
    pub fn new(port: u16, token: &str) -> io::Result<Self> {
        if port == 0 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "control-plane port must not be zero",
            ));
        }
        validate_session_token(token)?;
        Ok(Self {
            port,
            token: Zeroizing::new(token.to_owned()),
            version: ControlPlaneVersion::V1,
        })
    }

    pub fn sessions(&self) -> io::Result<ControlPlaneRequest> {
        self.request("GET", "sessions")
    }

    pub fn approvals(&self, session_id: &str) -> io::Result<ControlPlaneRequest> {
        self.session_request(session_id, "approvals")
    }

    pub fn preview_evidence(&self, session_id: &str) -> io::Result<ControlPlaneRequest> {
        self.session_request(session_id, "preview/evidence")
    }

    pub fn git_status(&self, session_id: &str) -> io::Result<ControlPlaneRequest> {
        self.session_request(session_id, "git/status")
    }

    pub fn workers(&self, session_id: &str) -> io::Result<ControlPlaneRequest> {
        self.session_request(session_id, "workers")
    }

    pub fn settings(&self) -> io::Result<ControlPlaneRequest> {
        self.request("GET", "settings")
    }

    pub fn audit(&self) -> io::Result<ControlPlaneRequest> {
        self.request("GET", "audit")
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

    fn session_request(&self, session_id: &str, suffix: &str) -> io::Result<ControlPlaneRequest> {
        let session_id = escape_path_segment(session_id)?;
        self.request("GET", &format!("sessions/{session_id}/{suffix}"))
    }

    fn request(&self, method: &'static str, path: &str) -> io::Result<ControlPlaneRequest> {
        if path.is_empty() || path.starts_with('/') || path.contains('?') || path.contains('#') {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "control-plane route must be a relative path",
            ));
        }
        Ok(ControlPlaneRequest {
            version: self.version,
            method,
            url: format!(
                "http://127.0.0.1:{}/{}/{path}",
                self.port,
                self.version.path_prefix().trim_start_matches('/')
            ),
            path: format!("{}/{path}", self.version.path_prefix()),
            port: self.port,
            authorization: Zeroizing::new(format!("Bearer {}", self.token.as_str())),
        })
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
