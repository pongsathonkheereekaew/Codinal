use std::fs;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};

use codinal_native_host::{free_loopback_port, launch_shadow_runtime};
use rusqlite::Connection;

const TOKEN: &str = "0123456789abcdef0123456789abcdef";
static NEXT_TEST_DIR: AtomicU64 = AtomicU64::new(0);

#[test]
fn native_host_runs_the_real_runtime_only_on_a_shadow_snapshot() {
    let source = fixture_data_dir();
    let snapshot = source.with_extension("shadow");
    let port = free_loopback_port().expect("port");
    let mut shadow = launch_shadow_runtime(
        env!("CARGO_BIN_EXE_codinal-runtime").into(),
        &source,
        &snapshot,
        port,
        TOKEN.to_owned(),
    )
    .expect("shadow runtime");

    assert!(codinal_storage::inspect_v1_data_dir(&source)
        .expect("production inspection")
        .is_empty());
    assert!(codinal_storage::inspect_v1_data_dir(&snapshot)
        .expect("snapshot inspection")
        .is_empty());
    assert!(snapshot.join(".codinal-runtime.lock").is_file());
    let sessions = authenticated_get(port, "/v1/sessions");
    assert!(sessions.starts_with("HTTP/1.1 200 OK\r\n"));
    assert!(sessions.ends_with("[{\"session_id\":\"session-1\",\"title\":\"Migration\",\"workspace\":\"/source project\",\"agent\":\"code\",\"model\":\"gpt\",\"mode\":\"code\",\"updated_at\":\"2026-01-02T00:00:00Z\",\"messages\":2,\"pinned\":true,\"archived\":false,\"origin\":null,\"origin_label\":null,\"origin_session_id\":null}]"));
    let filtered = authenticated_get(port, "/v1/sessions?workspace=%2Fsource+project");
    assert!(filtered.starts_with("HTTP/1.1 200 OK\r\n"));
    assert!(filtered.contains("\"session_id\":\"session-1\""));
    assert!(authenticated_get(port, "/v1/sessions?workspace=relative")
        .starts_with("HTTP/1.1 400 Bad Request\r\n"));
    let messages = authenticated_get(port, "/v1/sessions/session-1/messages");
    assert!(messages.starts_with("HTTP/1.1 200 OK\r\n"));
    assert!(messages.ends_with("[{\"content\":\"first\",\"role\":\"user\"},{\"content\":\"second\",\"role\":\"assistant\"}]"));
    assert!(authenticated_get(port, "/v1/sessions/worker-1/messages").ends_with("[]"));

    shadow.shutdown().expect("shutdown");
    assert!(!snapshot.exists());
    assert!(codinal_storage::inspect_v1_data_dir(&source)
        .expect("production reinspection")
        .is_empty());
    fs::remove_dir_all(source).expect("remove source");
}

fn fixture_data_dir() -> std::path::PathBuf {
    let path = std::env::temp_dir().join(format!(
        "codinal-shadow-launch-test-{}-{}",
        std::process::id(),
        NEXT_TEST_DIR.fetch_add(1, Ordering::Relaxed)
    ));
    let _ = fs::remove_dir_all(&path);
    fs::create_dir(&path).expect("data directory");
    create_fixture_databases(&path);
    path
}

fn create_fixture_databases(path: &Path) {
    for database in codinal_storage::load_v1_fixture()
        .expect("fixture")
        .databases
    {
        let connection = Connection::open(path.join(&database.file)).expect("database");
        connection
            .execute_batch(&format!("PRAGMA user_version = {};", database.user_version))
            .expect("version");
        for table in database.tables {
            connection
                .execute_batch(&format!("CREATE TABLE {table} (id INTEGER);"))
                .expect("table");
        }
        if database.file == "codinal.db" {
            connection
                .execute_batch(
                    "DROP TABLE sessions;
                     DROP TABLE messages;
                     CREATE TABLE sessions (
                       session_id TEXT PRIMARY KEY, workspace TEXT NOT NULL,
                       source_workspace TEXT, model TEXT NOT NULL, mode TEXT NOT NULL,
                       title TEXT, agent TEXT NOT NULL, pinned INTEGER NOT NULL,
                       archived INTEGER NOT NULL, origin TEXT, origin_label TEXT,
                       origin_session_id TEXT, updated_at TEXT NOT NULL
                     );
                     CREATE TABLE messages (
                       session_id TEXT NOT NULL, sequence INTEGER NOT NULL, payload TEXT NOT NULL,
                       PRIMARY KEY (session_id, sequence)
                     );
                     INSERT INTO sessions VALUES
                       ('session-1','/work','/source project','gpt','code','Migration','code',1,0,NULL,NULL,NULL,'2026-01-02T00:00:00Z'),
                       ('worker-1','/work',NULL,'gpt','code',NULL,'code',0,0,'worker',NULL,NULL,'2026-01-04T00:00:00Z');
                     INSERT INTO messages VALUES
                       ('session-1',1,'{\"role\":\"assistant\",\"content\":\"second\"}'),
                       ('session-1',0,'{\"role\":\"user\",\"content\":\"first\"}'),
                       ('worker-1',0,'{\"role\":\"assistant\",\"content\":\"private\"}');",
                )
                .expect("session fixture");
        }
    }
}

fn authenticated_get(port: u16, path: &str) -> String {
    let mut stream = TcpStream::connect(("127.0.0.1", port)).expect("connect");
    write!(
        stream,
        "GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\nConnection: close\r\n\r\n"
    )
    .expect("request");
    let mut response = String::new();
    stream.read_to_string(&mut response).expect("response");
    response
}
