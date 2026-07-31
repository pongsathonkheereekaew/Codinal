use std::fs;
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
    let mut shadow = launch_shadow_runtime(
        env!("CARGO_BIN_EXE_codinal-runtime").into(),
        &source,
        &snapshot,
        free_loopback_port().expect("port"),
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
        let connection = Connection::open(path.join(database.file)).expect("database");
        connection
            .execute_batch(&format!("PRAGMA user_version = {};", database.user_version))
            .expect("version");
        for table in database.tables {
            connection
                .execute_batch(&format!("CREATE TABLE {table} (id INTEGER);"))
                .expect("table");
        }
    }
}
