//! Rust-native, loopback-only v1 runtime foundation.
//!
//! This listener is deliberately limited to the authenticated health route.
//! It is not wired into desktop launch yet: Python remains the only data
//! writer until the remaining v1 routes and storage migrations pass parity.

use std::fs;
use std::io::{self, Read, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use zeroize::Zeroizing;

const MAX_REQUEST_BYTES: usize = 32 * 1024;
const MIN_TOKEN_LENGTH: usize = 32;

pub struct RuntimeConfig {
    port: u16,
    token: Zeroizing<String>,
    data_dir: PathBuf,
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
    use super::{serve_one, RuntimeConfig};
    use std::fs;
    use std::io::{Read, Write};
    use std::net::TcpStream;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::thread;

    const TOKEN: &str = "0123456789abcdef0123456789abcdef";
    static NEXT_TEST_DIR: AtomicU64 = AtomicU64::new(0);

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
