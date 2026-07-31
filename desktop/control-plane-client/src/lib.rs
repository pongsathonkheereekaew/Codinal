//! Native-only authenticated contract shared by Codinal desktop shells.

use std::io;
use zeroize::Zeroizing;

const MIN_TOKEN_LENGTH: usize = 32;

pub struct ControlPlaneClient {
    port: u16,
    token: Zeroizing<String>,
}

impl ControlPlaneClient {
    pub fn new(port: u16, token: &str) -> io::Result<Self> {
        if port == 0 || token.len() < MIN_TOKEN_LENGTH || !token.bytes().all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_')) {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "invalid control-plane credentials"));
        }
        Ok(Self { port, token: Zeroizing::new(token.to_owned()) })
    }

    pub fn get(&self, path: &str) -> io::Result<Request> {
        if path.is_empty() || path.starts_with('/') || path.contains('?') || path.contains('#') {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "invalid control-plane route"));
        }
        Ok(Request {
            url: format!("http://127.0.0.1:{}/v1/{path}", self.port),
            authorization: Zeroizing::new(format!("Bearer {}", self.token.as_str())),
        })
    }
}

pub struct Request {
    url: String,
    authorization: Zeroizing<String>,
}

impl Request {
    pub fn url(&self) -> &str { &self.url }
    pub fn authorization(&self) -> &str { self.authorization.as_str() }
}
