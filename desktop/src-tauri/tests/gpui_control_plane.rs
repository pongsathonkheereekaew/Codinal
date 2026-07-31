use std::io::{Read, Write};
use std::net::TcpListener;
use std::thread;

use codinal_desktop::gpui_control_plane::{ControlPlaneClient, ControlPlaneVersion, DesktopShell};
use serde_json::json;

const TOKEN: &str = "test-session-token-with-at-least-32-characters";
const SESSIONS_FIXTURE: &[u8] = include_bytes!("fixtures/gpui_control_plane/v1-sessions.json");
const SESSION_EVENT_FIXTURE: &str =
    include_str!("fixtures/gpui_control_plane/v1-session-event.json");

#[test]
fn native_client_executes_a_loopback_request_with_bearer_auth() {
    let listener = TcpListener::bind(("127.0.0.1", 0)).expect("listener");
    let port = listener.local_addr().expect("address").port();
    let server = thread::spawn(move || {
        let (mut stream, _) = listener.accept().expect("connection");
        let mut buffer = [0_u8; 4096];
        let count = stream.read(&mut buffer).expect("request read");
        let request = String::from_utf8(buffer[..count].to_vec()).expect("UTF-8 request");
        write!(
            stream,
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
            SESSIONS_FIXTURE.len(),
            std::str::from_utf8(SESSIONS_FIXTURE).expect("fixture is UTF-8")
        )
        .expect("response");
        request
    });
    let client = ControlPlaneClient::new(port, TOKEN).expect("valid client");

    let response = client.sessions().unwrap().execute_json().expect("response");
    let request = server.join().expect("server thread");

    assert_eq!(response, json!([]));
    assert!(request.starts_with("GET /v1/sessions HTTP/1.1\r\n"));
    assert!(request.contains(&format!("Authorization: Bearer {TOKEN}\r\n")));
}

#[test]
fn golden_v1_event_fixture_is_valid_json_without_a_bearer_token() {
    let event: serde_json::Value = serde_json::from_str(SESSION_EVENT_FIXTURE).expect("event JSON");

    assert_eq!(event["type"], "assistant_delta");
    assert!(!SESSION_EVENT_FIXTURE.contains(TOKEN));
}

#[test]
fn versioned_client_builds_authenticated_v1_routes_without_exposing_the_token_in_urls() {
    let client = ControlPlaneClient::new(43123, TOKEN).expect("valid client");

    let request = client.sessions().expect("sessions request");

    assert_eq!(request.version(), ControlPlaneVersion::V1);
    assert_eq!(request.method(), "GET");
    assert_eq!(request.url(), "http://127.0.0.1:43123/v1/sessions");
    assert_eq!(
        request.header("Authorization"),
        Some("Bearer test-session-token-with-at-least-32-characters")
    );
    assert!(!request.url().contains(TOKEN));
}

#[test]
fn session_scoped_routes_escape_ids_and_cover_the_gpui_migration_surfaces() {
    let client = ControlPlaneClient::new(43123, TOKEN).expect("valid client");

    assert_eq!(
        client.approvals("session/one").unwrap().url(),
        "http://127.0.0.1:43123/v1/sessions/session%2Fone/approvals"
    );
    assert_eq!(
        client.preview_evidence("session one").unwrap().url(),
        "http://127.0.0.1:43123/v1/sessions/session%20one/preview/evidence"
    );
    assert_eq!(
        client.git_status("session-one").unwrap().url(),
        "http://127.0.0.1:43123/v1/sessions/session-one/git/status"
    );
    assert_eq!(
        client.workers("session-one").unwrap().url(),
        "http://127.0.0.1:43123/v1/sessions/session-one/workers"
    );
    assert_eq!(
        client.settings().unwrap().url(),
        "http://127.0.0.1:43123/v1/settings"
    );
    assert_eq!(
        client.audit().unwrap().url(),
        "http://127.0.0.1:43123/v1/audit"
    );
}

#[test]
fn event_stream_uses_the_existing_authenticated_subprotocol_without_a_query_token() {
    let client = ControlPlaneClient::new(43123, TOKEN).expect("valid client");
    let stream = client.session_events("session one").expect("event stream");

    assert_eq!(
        stream.url(),
        "ws://127.0.0.1:43123/ws/session/session%20one"
    );
    assert_eq!(
        stream.subprotocols(),
        vec![
            "codinal.v1".to_owned(),
            "codinal.auth.test-session-token-with-at-least-32-characters".to_owned()
        ]
    );
    assert!(!stream.url().contains(TOKEN));
}

#[test]
fn gpui_shell_selection_is_development_only() {
    assert_eq!(
        DesktopShell::select(Some("gpui"), true).unwrap(),
        DesktopShell::Gpui
    );
    assert_eq!(
        DesktopShell::select(Some("tauri"), false).unwrap(),
        DesktopShell::Tauri
    );
    assert!(DesktopShell::select(Some("gpui"), false).is_err());
    assert!(DesktopShell::select(Some("unknown"), true).is_err());
}
