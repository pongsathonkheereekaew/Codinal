use std::io::{Read, Write};
use std::net::TcpListener;
use std::thread;

use codinal_desktop::control_client::sync_provider_secret;

fn capture_request(status: &str) -> (u16, thread::JoinHandle<String>) {
    let listener = TcpListener::bind(("127.0.0.1", 0)).expect("listener");
    let port = listener.local_addr().expect("address").port();
    let status = status.to_owned();
    let handle = thread::spawn(move || {
        let (mut stream, _) = listener.accept().expect("connection");
        let mut request = Vec::new();
        let mut buffer = [0_u8; 1024];
        loop {
            let count = stream.read(&mut buffer).expect("request read");
            request.extend_from_slice(&buffer[..count]);
            let Some(header_end) = request
                .windows(4)
                .position(|window| window == b"\r\n\r\n")
                .map(|index| index + 4)
            else {
                continue;
            };
            let headers = String::from_utf8_lossy(&request[..header_end]);
            let content_length = headers
                .lines()
                .find_map(|line| {
                    line.strip_prefix("Content-Length: ")
                        .and_then(|value| value.parse::<usize>().ok())
                })
                .unwrap_or(0);
            if request.len() >= header_end + content_length {
                break;
            }
        }
        write!(
            stream,
            "HTTP/1.1 {status}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        )
        .expect("response");
        String::from_utf8(request).expect("UTF-8 request")
    });
    (port, handle)
}

#[test]
fn provider_secret_sync_uses_authenticated_body_not_url() {
    let (port, request) = capture_request("200 OK");

    sync_provider_secret(
        port,
        "test-session-token-with-at-least-32-characters",
        "test-secret-sync-token-with-at-least-32-chars",
        "openai",
        Some("sk-test-secret"),
    )
    .expect("sync succeeds");
    let request = request.join().expect("server thread");

    assert!(request.starts_with("PUT /v1/secrets/providers/openai HTTP/1.1\r\n"));
    assert!(request
        .contains("Authorization: Bearer test-session-token-with-at-least-32-characters\r\n"));
    assert!(request
        .contains("X-Codinal-Secret-Sync: test-secret-sync-token-with-at-least-32-chars\r\n"));
    assert!(request.ends_with(r#"{"api_key":"sk-test-secret"}"#));
    assert!(!request.starts_with("PUT /v1/secrets/providers/openai?"));
}

#[test]
fn provider_secret_sync_errors_never_echo_secret() {
    let (port, request) = capture_request("500 Internal Server Error");

    let error = sync_provider_secret(
        port,
        "test-session-token-with-at-least-32-characters",
        "test-secret-sync-token-with-at-least-32-chars",
        "gemini",
        Some("must-not-echo"),
    )
    .expect_err("sync fails");
    request.join().expect("server thread");

    assert!(!error.to_string().contains("must-not-echo"));
}
