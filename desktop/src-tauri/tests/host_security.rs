use std::path::PathBuf;

use codinal_desktop::host::{initialization_script, mint_session_token, SidecarLaunch};

#[test]
fn session_tokens_are_unique_url_safe_256_bit_values() {
    let first = mint_session_token().expect("first token");
    let second = mint_session_token().expect("second token");

    assert_eq!(first.len(), 43);
    assert_ne!(first, second);
    assert!(first
        .bytes()
        .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-' || byte == b'_'));
}

#[test]
fn sidecar_token_is_in_environment_not_arguments() {
    let launch = SidecarLaunch::new(
        PathBuf::from("/opt/codinal/python"),
        PathBuf::from("/opt/codinal/runtime"),
        PathBuf::from("/tmp/codinal-data"),
        43123,
        "test-session-token-with-at-least-32-characters".to_owned(),
    )
    .expect("valid launch");

    let command = launch.command();
    let arguments: Vec<_> = command.get_args().collect();
    let session_token = command
        .get_envs()
        .find(|(name, _)| *name == std::ffi::OsStr::new("CODINAL_SESSION_TOKEN"))
        .and_then(|(_, value)| value);
    let bootstrap_channel = command
        .get_envs()
        .find(|(name, _)| *name == std::ffi::OsStr::new("CODINAL_SECRET_BOOTSTRAP"))
        .and_then(|(_, value)| value);

    assert_eq!(arguments, ["-B", "-m", "runtime.control_plane"]);
    assert!(!arguments
        .iter()
        .any(|argument| { argument.to_string_lossy().contains("test-session-token") }));
    assert_eq!(
        session_token,
        Some(std::ffi::OsStr::new(
            "test-session-token-with-at-least-32-characters"
        ))
    );
    assert_eq!(bootstrap_channel, Some(std::ffi::OsStr::new("stdin-v1")));
    assert!(!command.get_envs().any(|(_, value)| {
        value.is_some_and(|value| value.to_string_lossy().contains("provider-secret"))
    }));
    assert_eq!(
        command.get_current_dir(),
        Some(std::path::Path::new("/opt/codinal/runtime"))
    );
}

#[test]
fn initialization_keeps_credentials_in_memory() {
    let script = initialization_script(43123, "test-session-token-with-at-least-32-characters");

    assert!(script.contains("__CODINAL_HTTP__"));
    assert!(script.contains("__CODINAL_WS__"));
    assert!(script.contains("__CODINAL_TOKEN__"));
    assert!(!script.contains("localStorage"));
    assert!(!script.contains("sessionStorage"));
}
