use std::fs;
use std::io::{Read, Write};
use std::net::{Shutdown, TcpListener, TcpStream};
use std::path::Path;
use std::process::{Child, Command};
use std::thread;
use std::time::{Duration, Instant, SystemTime};

const TOKEN: &str = "0123456789abcdef0123456789abcdef";

struct RuntimeProcess(Child);

impl Drop for RuntimeProcess {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

#[test]
fn runtime_keeps_serving_after_a_malformed_loopback_connection() {
    let data_dir = std::env::temp_dir().join(format!(
        "codinal-runtime-bootstrap-test-{}",
        std::process::id()
    ));
    let _ = fs::remove_dir_all(&data_dir);
    fs::create_dir(&data_dir).expect("data directory");
    let port = TcpListener::bind("127.0.0.1:0")
        .expect("port listener")
        .local_addr()
        .expect("address")
        .port();
    let mut command = Command::new(env!("CARGO_BIN_EXE_codinal-runtime"));
    command
        .env("CODINAL_SESSION_TOKEN", TOKEN)
        .env("CODINAL_PORT", port.to_string())
        .env("CODINAL_DATA_DIR", &data_dir)
        .env_remove("CODINAL_EXPERIMENTAL_EXECUTION");
    let process = RuntimeProcess(command.spawn().expect("runtime process"));

    let mut malformed = connect_when_ready(port);
    malformed
        .write_all(b"GET /v1/health HTTP/1.1\r\n")
        .expect("malformed request");
    malformed.shutdown(Shutdown::Write).expect("close request");
    thread::sleep(Duration::from_millis(50));

    let mut healthy = connect_when_ready(port);
    healthy
        .write_all(
            format!(
                "GET /v1/health HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
            )
            .as_bytes(),
        )
        .expect("health request");
    let mut response = String::new();
    healthy
        .read_to_string(&mut response)
        .expect("health response");
    assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));

    drop(process);
    fs::remove_dir_all(data_dir).expect("remove data directory");
}

#[test]
fn runtime_starts_in_typed_read_only_mode_without_claiming_ownership() {
    let data_dir = std::env::temp_dir().join(format!(
        "codinal-runtime-read-only-bootstrap-test-{}",
        std::process::id()
    ));
    let _ = fs::remove_dir_all(&data_dir);
    fs::create_dir(&data_dir).expect("data directory");
    let before = directory_fingerprint(&data_dir);
    let port = TcpListener::bind("127.0.0.1:0")
        .expect("port listener")
        .local_addr()
        .expect("address")
        .port();
    let mut command = Command::new(env!("CARGO_BIN_EXE_codinal-runtime"));
    command
        .env("CODINAL_SESSION_TOKEN", TOKEN)
        .env("CODINAL_PORT", port.to_string())
        .env("CODINAL_DATA_DIR", &data_dir)
        .env_remove("CODINAL_EXPERIMENTAL_EXECUTION");
    let process = RuntimeProcess(command.spawn().expect("runtime process"));

    let health = authenticated_get(port, "/v1/health");
    let health_json: serde_json::Value = response_body(&health).parse().expect("health json");
    assert_eq!(health_json["status"], "ok");
    assert_eq!(health_json["mode"], "read_only");
    assert_eq!(health_json["reason_code"], "owner_bootstrap_deferred");
    assert_eq!(health_json["migration"]["state"], "not_started");
    assert_eq!(health_json["writer_lock"]["state"], "not_acquired");
    assert_eq!(health_json["event_store"]["ready"], false);
    assert_eq!(health_json["capabilities"]["runtime_owner"], "rust");
    assert_eq!(health_json["capabilities"]["receipt_write_owner"], "none");
    assert_eq!(health_json["capabilities"]["start_turn"], false);
    assert_eq!(
        health_json["capabilities"]["run_disabled_reason"],
        "owner_bootstrap_deferred"
    );
    assert_eq!(
        health_json["capabilities"]["mutation_disabled_reason"],
        "owner_bootstrap_deferred"
    );
    assert!(!data_dir.join(".codinal-runtime.lock").exists());

    let mutation = authenticated_post(port, "/v1/sessions/session-1/turns");
    let mutation_json: serde_json::Value = response_body(&mutation).parse().expect("mutation json");
    assert!(mutation.starts_with("HTTP/1.1 423 Locked\r\n"));
    assert_eq!(mutation_json["reason_code"], "owner_bootstrap_deferred");
    assert_eq!(mutation_json["action"], "mutation");
    assert_eq!(directory_fingerprint(&data_dir), before);

    drop(process);
    fs::remove_dir_all(data_dir).expect("remove data directory");
}

#[test]
fn runtime_acquires_owner_only_when_experimental_execution_is_explicit() {
    let data_dir = std::env::temp_dir().join(format!(
        "codinal-runtime-owner-bootstrap-test-{}",
        std::process::id()
    ));
    let _ = fs::remove_dir_all(&data_dir);
    fs::create_dir(&data_dir).expect("data directory");
    let port = TcpListener::bind("127.0.0.1:0")
        .expect("port listener")
        .local_addr()
        .expect("address")
        .port();
    let mut command = Command::new(env!("CARGO_BIN_EXE_codinal-runtime"));
    command
        .env("CODINAL_SESSION_TOKEN", TOKEN)
        .env("CODINAL_PORT", port.to_string())
        .env("CODINAL_DATA_DIR", &data_dir)
        .env("CODINAL_EXPERIMENTAL_EXECUTION", "1");
    let process = RuntimeProcess(command.spawn().expect("runtime process"));

    let health = authenticated_get(port, "/v1/health");
    let health_json: serde_json::Value = response_body(&health).parse().expect("health json");
    assert_eq!(health_json["status"], "ok");
    assert_eq!(health_json["mode"], "ready");
    assert_eq!(health_json["writer_lock"]["state"], "held");
    assert_eq!(health_json["event_store"]["ready"], true);
    assert_eq!(health_json["capabilities"]["experimental_execution"], true);
    assert!(data_dir.join(".codinal-runtime.lock").exists());
    assert!(data_dir.join("codinal-runtime.db").exists());

    drop(process);
    fs::remove_dir_all(data_dir).expect("remove data directory");
}

#[test]
fn owner_process_kill_and_restart_keeps_the_same_runtime_history() {
    let data_dir = std::env::temp_dir().join(format!(
        "codinal-runtime-owner-restart-test-{}",
        std::process::id()
    ));
    let _ = fs::remove_dir_all(&data_dir);
    fs::create_dir(&data_dir).expect("data directory");
    let port = TcpListener::bind("127.0.0.1:0")
        .expect("port listener")
        .local_addr()
        .expect("address")
        .port();
    let mut command = Command::new(env!("CARGO_BIN_EXE_codinal-runtime"));
    command
        .env("CODINAL_SESSION_TOKEN", TOKEN)
        .env("CODINAL_PORT", port.to_string())
        .env("CODINAL_DATA_DIR", &data_dir)
        .env("CODINAL_EXPERIMENTAL_EXECUTION", "1");
    let mut first = RuntimeProcess(command.spawn().expect("first runtime"));
    let health = authenticated_get(port, "/v1/health");
    let health_json: serde_json::Value = response_body(&health).parse().expect("health json");
    assert_eq!(health_json["mode"], "ready");
    let first_generation: String = rusqlite::Connection::open(data_dir.join("codinal-runtime.db"))
        .expect("runtime store")
        .query_row(
            "SELECT value FROM store_meta WHERE key = 'generation'",
            [],
            |row| row.get(0),
        )
        .expect("generation");
    first.0.kill().expect("kill first runtime");
    first.0.wait().expect("wait first runtime");

    let second = RuntimeProcess(command.spawn().expect("second runtime"));
    let restarted = authenticated_get(port, "/v1/health");
    let restarted_json: serde_json::Value = response_body(&restarted).parse().expect("health json");
    assert_eq!(restarted_json["mode"], "ready");
    assert_eq!(restarted_json["writer_lock"]["state"], "held");
    let second_generation: String = rusqlite::Connection::open(data_dir.join("codinal-runtime.db"))
        .expect("runtime store")
        .query_row(
            "SELECT value FROM store_meta WHERE key = 'generation'",
            [],
            |row| row.get(0),
        )
        .expect("generation");
    assert_eq!(second_generation, first_generation);
    drop(second);
    fs::remove_dir_all(data_dir).expect("remove data directory");
}

#[test]
fn migration_fault_restart_recovers_backup_database_stage_and_commit_marker() {
    for stage in [
        "backup_fsync:codinal.db",
        "database_committed:codinal.db",
        "commit_marker",
    ] {
        let data_dir = std::env::temp_dir().join(format!(
            "codinal-runtime-migration-fault-{}-{}",
            std::process::id(),
            stage.replace(':', "-")
        ));
        let _ = fs::remove_dir_all(&data_dir);
        fs::create_dir(&data_dir).expect("data directory");
        create_legacy_conversation_database(&data_dir);
        let port = TcpListener::bind("127.0.0.1:0")
            .expect("port listener")
            .local_addr()
            .expect("address")
            .port();
        let mut command = Command::new(env!("CARGO_BIN_EXE_codinal-runtime"));
        command
            .env("CODINAL_SESSION_TOKEN", TOKEN)
            .env("CODINAL_PORT", port.to_string())
            .env("CODINAL_DATA_DIR", &data_dir)
            .env("CODINAL_EXPERIMENTAL_EXECUTION", "1")
            .env("CODINAL_TEST_MIGRATION_PAUSE", stage);
        let mut first = RuntimeProcess(command.spawn().expect("fault runtime"));
        wait_for_migration_stage(&data_dir, stage, &mut first);
        first.0.kill().expect("kill fault runtime");
        first.0.wait().expect("wait fault runtime");
        command.env_remove("CODINAL_TEST_MIGRATION_PAUSE");

        let second = RuntimeProcess(command.spawn().expect("restart runtime"));
        let health = authenticated_get(port, "/v1/health");
        let health_json: serde_json::Value = response_body(&health).parse().expect("health json");
        assert_eq!(health_json["mode"], "ready", "stage={stage}");
        let sessions = authenticated_get(port, "/v1/sessions");
        assert!(sessions.contains("retained-v1"), "stage={stage}");
        let journal =
            fs::read_to_string(data_dir.join(".codinal-migration-journal.json")).expect("journal");
        let journal: serde_json::Value = serde_json::from_str(&journal).expect("journal json");
        assert_eq!(journal["status"], "complete", "stage={stage}");
        drop(second);
        fs::remove_dir_all(data_dir).expect("remove data directory");
    }
}

fn wait_for_migration_stage(data_dir: &Path, stage: &str, process: &mut RuntimeProcess) {
    let deadline = Instant::now() + Duration::from_secs(10);
    loop {
        let reached = if stage == "backup_fsync:codinal.db" {
            data_dir.join("backups").is_dir()
                && fs::read_dir(data_dir.join("backups"))
                    .expect("backups")
                    .next()
                    .is_some()
        } else {
            fs::read_to_string(data_dir.join(".codinal-migration-journal.json"))
                .ok()
                .and_then(|encoded| serde_json::from_str::<serde_json::Value>(&encoded).ok())
                .is_some_and(|journal| {
                    if stage == "commit_marker" {
                        journal["commit_marker"] == true
                    } else {
                        let file = stage
                            .strip_prefix("database_committed:")
                            .expect("database stage");
                        journal["databases"].as_array().is_some_and(|databases| {
                            databases.iter().any(|database| {
                                database["file"] == file && database["stage"] == "committed"
                            })
                        })
                    }
                })
        };
        if reached {
            return;
        }
        if process
            .0
            .try_wait()
            .expect("fault process status")
            .is_some()
        {
            panic!("fault process exited before stage {stage}");
        }
        if Instant::now() >= deadline {
            panic!("migration stage not reached: {stage}");
        }
        thread::sleep(Duration::from_millis(10));
    }
}

fn create_legacy_conversation_database(data_dir: &Path) {
    let connection = rusqlite::Connection::open(data_dir.join("codinal.db")).expect("database");
    connection
        .execute_batch(
            r#"
            CREATE TABLE sessions (
              session_id TEXT PRIMARY KEY, workspace TEXT NOT NULL,
              model TEXT NOT NULL, mode TEXT NOT NULL, title TEXT,
              agent TEXT NOT NULL DEFAULT 'code', extra_roots TEXT NOT NULL DEFAULT '[]',
              grants TEXT NOT NULL DEFAULT '{}', pinned INTEGER NOT NULL DEFAULT 0,
              archived INTEGER NOT NULL DEFAULT 0, origin TEXT, origin_label TEXT,
              updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE messages (
              session_id TEXT NOT NULL, sequence INTEGER NOT NULL, payload TEXT NOT NULL,
              PRIMARY KEY (session_id, sequence)
            );
            CREATE TABLE workspaces (path TEXT PRIMARY KEY, last_used TEXT NOT NULL DEFAULT '');
            INSERT INTO sessions (session_id, workspace, model, mode, title)
              VALUES ('retained-v1', '/workspace', 'ollama:qwen3', 'interactive', 'Retained');
            INSERT INTO messages VALUES
              ('retained-v1', 0, '{"role":"user","content":"preserve this"}');
            PRAGMA user_version = 1;
            "#,
        )
        .expect("legacy schema");
}

fn connect_when_ready(port: u16) -> TcpStream {
    for _ in 0..500 {
        if let Ok(stream) = TcpStream::connect(("127.0.0.1", port)) {
            return stream;
        }
        thread::sleep(Duration::from_millis(10));
    }
    panic!("runtime did not start");
}

fn authenticated_get(port: u16, path: &str) -> String {
    let mut stream = connect_when_ready(port);
    write!(
        stream,
        "GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nConnection: close\r\n\r\n"
    )
    .expect("request");
    let mut response = String::new();
    stream.read_to_string(&mut response).expect("response");
    response
}

fn authenticated_post(port: u16, path: &str) -> String {
    let mut stream = connect_when_ready(port);
    write!(
        stream,
        "POST {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
    )
    .expect("request");
    let mut response = String::new();
    stream.read_to_string(&mut response).expect("response");
    response
}

fn response_body(response: &str) -> &str {
    response
        .split_once("\r\n\r\n")
        .map(|(_, body)| body)
        .expect("response body")
}

fn directory_fingerprint(path: &std::path::Path) -> Vec<(String, u64, SystemTime)> {
    let mut entries = fs::read_dir(path)
        .expect("directory")
        .map(|entry| {
            let entry = entry.expect("entry");
            let metadata = entry.metadata().expect("metadata");
            (
                entry.file_name().to_string_lossy().into_owned(),
                metadata.len(),
                metadata.modified().expect("modified time"),
            )
        })
        .collect::<Vec<_>>();
    entries.sort_by(|left, right| left.0.cmp(&right.0));
    entries
}
