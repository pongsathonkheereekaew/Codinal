//! Native-only authenticated contract shared by Codinal desktop shells.

use std::io::{self, Read, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpStream};
use std::time::Duration;
use zeroize::Zeroizing;

const MIN_TOKEN_LENGTH: usize = 32;

pub struct ControlPlaneClient {
    port: u16,
    token: Zeroizing<String>,
}

#[derive(Debug, PartialEq, Eq)]
pub struct SessionSummary {
    pub session_id: String,
    pub title: String,
    pub workspace: String,
    pub messages: u64,
}

#[derive(Debug, PartialEq, Eq)]
pub struct MessageSummary {
    pub role: String,
    pub text: String,
}

#[derive(Debug, PartialEq, Eq)]
pub struct PendingApproval {
    pub approval_id: String,
    pub tool_name: String,
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
        let request = self.get(path)?;
        self.send_json("GET", path, None, &request)
    }

    pub fn resolve_approval(
        &self,
        session_id: &str,
        approval_id: &str,
        outcome: ApprovalOutcome,
    ) -> io::Result<()> {
        validate_session_id(session_id)?;
        validate_approval_id(approval_id)?;
        let path = format!("sessions/{session_id}/approvals/{approval_id}");
        let request = self.get(&path)?;
        self.send_json(
            "POST",
            &path,
            Some(&serde_json::json!({ "outcome": outcome.as_str() })),
            &request,
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

    fn send_json(
        &self,
        method: &str,
        path: &str,
        payload: Option<&serde_json::Value>,
        request: &Request,
    ) -> io::Result<serde_json::Value> {
        let address = SocketAddrV4::new(Ipv4Addr::LOCALHOST, self.port);
        let mut stream = TcpStream::connect_timeout(&address.into(), Duration::from_secs(2))?;
        stream.set_read_timeout(Some(Duration::from_secs(2)))?;
        stream.set_write_timeout(Some(Duration::from_secs(2)))?;
        let body = payload
            .map(serde_json::to_vec)
            .transpose()
            .map_err(|error| io::Error::other(error.to_string()))?;
        let body = Zeroizing::new(body.unwrap_or_default());
        let headers = Zeroizing::new(format!(
            "{method} /v1/{path} HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nAuthorization: {}\r\nAccept: application/json\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
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
        let response = self.get_json("sessions")?;
        let sessions = response.as_array().ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "sessions response must be an array",
            )
        })?;
        sessions.iter().map(parse_session_summary).collect()
    }

    pub fn session_messages(&self, session_id: &str) -> io::Result<Vec<MessageSummary>> {
        validate_session_id(session_id)?;
        let response = self.get_json(&format!("sessions/{session_id}/messages"))?;
        let messages = response.as_array().ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "messages response must be an array",
            )
        })?;
        messages.iter().map(parse_message_summary).collect()
    }

    pub fn pending_approvals(&self, session_id: &str) -> io::Result<Vec<PendingApproval>> {
        validate_session_id(session_id)?;
        let response = self.get_json(&format!("sessions/{session_id}/approvals"))?;
        let approvals = response.as_array().ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "approvals response must be an array",
            )
        })?;
        approvals.iter().map(parse_pending_approval).collect()
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
    };
    use std::io::{BufRead, BufReader, Read, Write};
    use std::net::TcpListener;
    use std::thread;

    const TOKEN: &str = "0123456789abcdef0123456789abcdef";

    #[test]
    fn golden_v1_fixture_stays_versioned_and_secret_free() {
        let fixture: serde_json::Value = serde_json::from_str(include_str!(
            "../../../contracts/v1/control-plane.json"
        ))
        .expect("valid golden fixture");
        assert_eq!(fixture["fixture_version"], 1);
        assert_eq!(fixture["contract"], "codinal.control-plane.v1");
        let mut payload = fixture.clone();
        payload.as_object_mut().expect("fixture object").remove("redaction");
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
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n[{\"session_id\":\"session-1\",\"title\":\"Migration\",\"workspace\":\"/tmp/workspace\",\"messages\":3}]")
                .expect("write response");
        });

        let sessions = ControlPlaneClient::new(port, TOKEN)
            .expect("client")
            .list_sessions()
            .expect("JSON response");
        assert_eq!(sessions.len(), 1);
        assert_eq!(sessions[0].title, "Migration");
        assert_eq!(sessions[0].messages, 3);
        server.join().expect("server");
    }

    #[test]
    fn refuses_an_unsafe_session_identifier() {
        let client = ControlPlaneClient::new(1, TOKEN).expect("client");
        assert!(client.session_messages("../secrets").is_err());
        assert!(client.session_messages("__internal").is_err());
    }

    #[test]
    fn parses_pending_approval_without_arguments() {
        let approval = parse_pending_approval(&serde_json::json!({
            "approval_id": "0123456789abcdef0123456789abcdef",
            "tool_name": "shell",
            "reason": "writes a local file",
            "risk": "write_local",
            "command": ""
        }))
        .expect("approval");
        assert_eq!(approval.risk, "write_local");
        assert_eq!(approval.command, None);
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
