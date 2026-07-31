use std::io::{Read, Write};
use std::net::TcpListener;
use std::thread;

use codinal_desktop::control_client::relay_oauth_callback;
use codinal_desktop::oauth::parse_oauth_deep_link;
use codinal_native_host::secrets::{sync_runtime_custom_provider, sync_runtime_provider_secret};
use url::Url;

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

    sync_runtime_provider_secret(
        port,
        "test-session-token-with-at-least-32-characters",
        "test-secret-sync-token-with-at-least-32-chars",
        "openai",
        Some("sk-test-secret"),
        None,
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

    let error = sync_runtime_provider_secret(
        port,
        "test-session-token-with-at-least-32-characters",
        "test-secret-sync-token-with-at-least-32-chars",
        "gemini",
        Some("must-not-echo"),
        None,
    )
    .expect_err("sync fails");
    request.join().expect("server thread");

    assert!(!error.to_string().contains("must-not-echo"));
}

#[test]
fn custom_provider_sync_uses_the_shared_native_transport() {
    let (port, request) = capture_request("200 OK");
    sync_runtime_custom_provider(
        port,
        "test-session-token-with-at-least-32-characters",
        "test-secret-sync-token-with-at-least-32-chars",
        "local",
        "http://127.0.0.1:1234/v1",
        Some("custom-secret"),
        true,
    )
    .expect("sync succeeds");
    let request = request.join().expect("server thread");
    assert!(request.starts_with("POST /v1/providers/custom HTTP/1.1\r\n"));
    assert!(request.ends_with(
        r#"{"api_key":"custom-secret","base_url":"http://127.0.0.1:1234/v1","failover_eligible":true,"slug":"local"}"#
    ));
    assert!(!request.starts_with("POST /v1/providers/custom?"));
}

#[test]
fn oauth_relay_uses_both_native_tokens_and_posts_code_in_json_body() {
    let (port, request) = capture_request("200 OK");
    let callback = parse_oauth_deep_link(
        &Url::parse(
            "codinal://oauth/callback?flow=provider%3Aopenai\
             &state=oauth-state-token-with-at-least-32-chars\
             &code=authorization-code",
        )
        .unwrap(),
    )
    .unwrap();

    relay_oauth_callback(
        port,
        "test-session-token-with-at-least-32-characters",
        "test-secret-sync-token-with-at-least-32-chars",
        &callback,
    )
    .expect("relay succeeds");
    let request = request.join().expect("server thread");

    assert!(request.starts_with("POST /v1/oauth/callback HTTP/1.1\r\n"));
    assert!(request
        .contains("Authorization: Bearer test-session-token-with-at-least-32-characters\r\n"));
    assert!(request
        .contains("X-Codinal-Secret-Sync: test-secret-sync-token-with-at-least-32-chars\r\n"));
    assert!(request.ends_with(
        r#"{"code":"authorization-code","error":"","flow":"provider:openai","state":"oauth-state-token-with-at-least-32-chars"}"#
    ));
    assert!(!request.starts_with("POST /v1/oauth/callback?"));
}

#[test]
fn oauth_relay_error_never_echoes_authorization_code() {
    let (port, request) = capture_request("400 Bad Request");
    let callback = parse_oauth_deep_link(
        &Url::parse(
            "codinal://oauth/callback?flow=provider%3Aopenai\
             &state=oauth-state-token-with-at-least-32-chars\
             &code=must-not-echo",
        )
        .unwrap(),
    )
    .unwrap();

    let error = relay_oauth_callback(
        port,
        "test-session-token-with-at-least-32-characters",
        "test-secret-sync-token-with-at-least-32-chars",
        &callback,
    )
    .expect_err("relay fails");
    request.join().expect("server thread");

    assert!(!error.to_string().contains("must-not-echo"));
}
