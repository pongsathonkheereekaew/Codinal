use std::io::{self, BufRead, BufReader, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpStream};
use std::time::Duration;

use zeroize::Zeroizing;

use crate::host::validate_session_token;
use crate::secrets::validate_provider;

pub fn sync_provider_secret(
    port: u16,
    token: &str,
    secret_sync_token: &str,
    provider: &str,
    api_key: Option<&str>,
) -> io::Result<()> {
    validate_session_token(token)?;
    validate_session_token(secret_sync_token)?;
    let provider = validate_provider(provider)?;
    let (method, body) = match api_key {
        Some(value) if !value.trim().is_empty() => (
            "PUT",
            serde_json::to_vec(&serde_json::json!({"api_key": value}))
                .map_err(|error| io::Error::other(error.to_string()))?,
        ),
        Some(_) => {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "api key must not be empty",
            ));
        }
        None => ("DELETE", Vec::new()),
    };
    let body = Zeroizing::new(body);

    let address = SocketAddrV4::new(Ipv4Addr::LOCALHOST, port);
    let mut stream = TcpStream::connect_timeout(&address.into(), Duration::from_secs(2))?;
    stream.set_read_timeout(Some(Duration::from_secs(2)))?;
    stream.set_write_timeout(Some(Duration::from_secs(2)))?;

    let headers = Zeroizing::new(format!(
        "{method} /v1/secrets/providers/{provider} HTTP/1.1\r\n\
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
        .and_then(|()| stream.write_all(&body))
        .and_then(|()| stream.flush());
    write_result?;

    let mut status_line = String::new();
    BufReader::new(stream).read_line(&mut status_line)?;
    let status = status_line.split_whitespace().nth(1);
    if status != Some("200") {
        return Err(io::Error::other("control plane rejected secret update"));
    }
    Ok(())
}
