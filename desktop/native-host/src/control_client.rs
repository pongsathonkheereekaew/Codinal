use std::io::{self, BufRead, BufReader, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpStream};
use std::time::Duration;

use zeroize::Zeroizing;

use crate::host::validate_session_token;
use crate::oauth::{parse_oauth_deep_link, OAuthDeepLink};
use url::Url;

pub struct OAuthRelayController {
    port: u16,
    token: Zeroizing<String>,
    secret_sync_token: Zeroizing<String>,
}

impl OAuthRelayController {
    pub fn new(port: u16, token: String, secret_sync_token: String) -> io::Result<Self> {
        validate_session_token(&token)?;
        validate_session_token(&secret_sync_token)?;
        Ok(Self {
            port,
            token: Zeroizing::new(token),
            secret_sync_token: Zeroizing::new(secret_sync_token),
        })
    }

    /// Parse and relay an OS deep link without exposing either credential.
    /// Returns the non-secret flow identifier for shell status rendering.
    pub fn relay_url(&self, url: Url) -> io::Result<String> {
        let parsed = parse_oauth_deep_link(&url);
        let _serialized_url = Zeroizing::new(String::from(url));
        let callback = parsed?;
        let flow = callback.flow().to_owned();
        relay_oauth_callback(self.port, &self.token, &self.secret_sync_token, &callback)?;
        Ok(flow)
    }

    pub fn relay_deep_link(&self, raw_url: &str) -> io::Result<String> {
        let url = Url::parse(raw_url)
            .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "invalid OAuth callback"))?;
        self.relay_url(url)
    }
}

pub fn relay_oauth_callback(
    port: u16,
    token: &str,
    secret_sync_token: &str,
    callback: &OAuthDeepLink,
) -> io::Result<()> {
    validate_session_token(token)?;
    validate_session_token(secret_sync_token)?;
    let body = Zeroizing::new(
        serde_json::to_vec(&serde_json::json!({
            "flow": callback.flow(),
            "state": callback.state(),
            "code": callback.code(),
            "error": callback.error(),
        }))
        .map_err(|error| io::Error::other(error.to_string()))?,
    );
    send_json_request(
        port,
        token,
        secret_sync_token,
        "POST",
        "/v1/oauth/callback",
        &body,
        "control plane rejected OAuth callback",
    )
}

fn send_json_request(
    port: u16,
    token: &str,
    secret_sync_token: &str,
    method: &str,
    path: &str,
    body: &[u8],
    rejection_message: &'static str,
) -> io::Result<()> {
    let address = SocketAddrV4::new(Ipv4Addr::LOCALHOST, port);
    let mut stream = TcpStream::connect_timeout(&address.into(), Duration::from_secs(2))?;
    stream.set_read_timeout(Some(Duration::from_secs(2)))?;
    stream.set_write_timeout(Some(Duration::from_secs(2)))?;

    let headers = Zeroizing::new(format!(
        "{method} {path} HTTP/1.1\r\n\
         Host: 127.0.0.1:{port}\r\n\
         Authorization: Bearer {token}\r\n\
         X-Codinal-Secret-Sync: {secret_sync_token}\r\n\
         Content-Type: application/json\r\n\
         Content-Length: {}\r\n\
         Connection: close\r\n\r\n",
        body.len()
    ));
    let write_result = stream
        .write_all(headers.as_bytes())
        .and_then(|()| stream.write_all(body))
        .and_then(|()| stream.flush());
    write_result?;

    let mut status_line = String::new();
    BufReader::new(stream).read_line(&mut status_line)?;
    let status = status_line.split_whitespace().nth(1);
    if status != Some("200") {
        return Err(io::Error::other(rejection_message));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn relay_controller_rejects_invalid_credentials_and_urls_before_network() {
        assert!(OAuthRelayController::new(1, "short".to_owned(), "short".to_owned()).is_err());
        let controller = OAuthRelayController::new(1, "a".repeat(32), "b".repeat(32)).unwrap();
        let error = controller
            .relay_deep_link("https://example.com/not-oauth")
            .unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::InvalidInput);
    }
}
