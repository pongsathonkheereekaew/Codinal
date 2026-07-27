use std::io::{self, BufRead, BufReader, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpStream};
use std::time::Duration;

use zeroize::Zeroizing;

use crate::host::validate_session_token;
use crate::oauth::OAuthDeepLink;
use crate::secrets::validate_provider;

pub fn sync_provider_secret(
    port: u16,
    token: &str,
    secret_sync_token: &str,
    provider: &str,
    api_key: Option<&str>,
    base_url: Option<&str>,
) -> io::Result<()> {
    validate_session_token(token)?;
    validate_session_token(secret_sync_token)?;
    let provider = validate_provider(provider)?;
    let (method, body) = match api_key {
        Some(value) if !value.trim().is_empty() => {
            let payload = match base_url {
                Some(url) if !url.trim().is_empty() => serde_json::json!({
                    "api_key": value,
                    "base_url": url.trim(),
                }),
                _ => serde_json::json!({ "api_key": value }),
            };
            (
                "PUT",
                serde_json::to_vec(&payload)
                    .map_err(|error| io::Error::other(error.to_string()))?,
            )
        }
        Some(_) => {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "api key must not be empty",
            ));
        }
        None => ("DELETE", Vec::new()),
    };
    let body = Zeroizing::new(body);

    send_json_request(
        port,
        token,
        secret_sync_token,
        method,
        &format!("/v1/secrets/providers/{provider}"),
        &body,
        "control plane rejected secret update",
    )
}

/// Sync a custom OpenAI-compatible provider add/remove to the Python runtime.
/// `api_key = None` triggers DELETE; otherwise POST with full metadata.
pub fn sync_custom_provider(
    port: u16,
    token: &str,
    secret_sync_token: &str,
    slug: &str,
    base_url: &str,
    api_key: Option<&str>,
    failover_eligible: bool,
) -> io::Result<()> {
    validate_session_token(token)?;
    validate_session_token(secret_sync_token)?;
    if slug.is_empty() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "slug must not be empty",
        ));
    }
    let (method, path, body) = match api_key {
        Some(key) if !key.trim().is_empty() => {
            let payload = serde_json::json!({
                "slug": slug,
                "base_url": base_url.trim(),
                "api_key": key,
                "failover_eligible": failover_eligible,
            });
            let body = serde_json::to_vec(&payload)
                .map_err(|error| io::Error::other(error.to_string()))?;
            ("POST", "/v1/providers/custom".to_owned(), body)
        }
        Some(_) => {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "api key must not be empty",
            ));
        }
        None => ("DELETE", format!("/v1/providers/custom/{slug}"), Vec::new()),
    };
    let body = Zeroizing::new(body);
    send_json_request(
        port,
        token,
        secret_sync_token,
        method,
        &path,
        &body,
        "control plane rejected custom provider update",
    )
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
