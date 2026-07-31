//! Read-only compatibility inspection for pre-cutover Codinal data.
//!
//! This crate intentionally has no write API. The Rust runtime must prove it
//! can read the Python-owned data directory before a future transactional
//! ownership cutover may add migration or repository code.

use rusqlite::{Connection, OpenFlags};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

mod migration;

pub use migration::{
    migrate_conversation_snapshot, recover_conversation_snapshot, ConversationMigrationReport,
    CONVERSATION_SCHEMA_VERSION,
};

#[derive(Debug, Deserialize, PartialEq, Eq)]
pub struct StorageFixture {
    pub fixture_version: u32,
    pub contract: String,
    pub databases: Vec<DatabaseFixture>,
}

#[derive(Debug, Deserialize, PartialEq, Eq)]
pub struct DatabaseFixture {
    pub file: String,
    pub user_version: u32,
    pub tables: Vec<String>,
}

#[derive(Debug, PartialEq, Eq)]
pub struct StorageMismatch {
    pub file: String,
    pub detail: String,
}

#[derive(Debug, Serialize, PartialEq, Eq)]
pub struct SessionSummary {
    pub session_id: String,
    pub title: String,
    pub workspace: String,
    pub agent: String,
    pub model: String,
    pub mode: String,
    pub updated_at: String,
    pub messages: u64,
    pub pinned: bool,
    pub archived: bool,
    pub origin: Option<String>,
    pub origin_label: Option<String>,
    pub origin_session_id: Option<String>,
}

pub fn read_session_summaries(
    data_dir: &Path,
    workspace: Option<&str>,
) -> io::Result<Vec<SessionSummary>> {
    let connection = open_conversation_database(data_dir)?;
    let mut sql = String::from(
        "SELECT sessions.session_id, COALESCE(sessions.title, 'New session'),
                COALESCE(sessions.source_workspace, sessions.workspace), sessions.agent,
                sessions.model, sessions.mode, sessions.updated_at,
                COUNT(messages.sequence), sessions.pinned, sessions.archived,
                sessions.origin, sessions.origin_label, sessions.origin_session_id
         FROM sessions LEFT JOIN messages USING (session_id)
         WHERE substr(sessions.session_id, 1, 2) != '__'
           AND COALESCE(sessions.origin, '') != 'worker'",
    );
    if workspace.is_some() {
        sql.push_str(" AND COALESCE(sessions.source_workspace, sessions.workspace) = ?1");
    }
    sql.push_str(
        " GROUP BY sessions.session_id ORDER BY sessions.pinned DESC, sessions.updated_at DESC",
    );
    let mut statement = connection.prepare(&sql).map_err(sqlite_error)?;
    let map_row = |row: &rusqlite::Row<'_>| {
        Ok(SessionSummary {
            session_id: row.get(0)?,
            title: row.get(1)?,
            workspace: row.get(2)?,
            agent: row.get(3)?,
            model: row.get(4)?,
            mode: row.get(5)?,
            updated_at: row.get(6)?,
            messages: row.get(7)?,
            pinned: row.get::<_, i64>(8)? != 0,
            archived: row.get::<_, i64>(9)? != 0,
            origin: row.get(10)?,
            origin_label: row.get(11)?,
            origin_session_id: row.get(12)?,
        })
    };
    let rows = match workspace {
        Some(value) => statement.query_map([value], map_row),
        None => statement.query_map([], map_row),
    }
    .map_err(sqlite_error)?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(sqlite_error)
}

pub fn read_session_messages(
    data_dir: &Path,
    session_id: &str,
) -> io::Result<Vec<serde_json::Value>> {
    if !valid_public_session_id(session_id) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid public session id",
        ));
    }
    let connection = open_conversation_database(data_dir)?;
    let mut statement = connection
        .prepare(
            "SELECT messages.payload FROM messages
             JOIN sessions USING (session_id)
             WHERE messages.session_id = ?1
               AND substr(sessions.session_id, 1, 2) != '__'
               AND COALESCE(sessions.origin, '') != 'worker'
             ORDER BY messages.sequence",
        )
        .map_err(sqlite_error)?;
    let rows = statement
        .query_map([session_id], |row| row.get::<_, String>(0))
        .map_err(sqlite_error)?;
    rows.map(|row| {
        let payload = row.map_err(sqlite_error)?;
        serde_json::from_str(&payload)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))
    })
    .collect()
}

pub fn public_session_exists(data_dir: &Path, session_id: &str) -> io::Result<bool> {
    if !valid_public_session_id(session_id) {
        return Ok(false);
    }
    let connection = open_conversation_database(data_dir)?;
    connection
        .query_row(
            "SELECT EXISTS(
               SELECT 1 FROM sessions
               WHERE session_id = ?1
                 AND substr(session_id, 1, 2) != '__'
                 AND COALESCE(origin, '') != 'worker'
             )",
            [session_id],
            |row| row.get::<_, bool>(0),
        )
        .map_err(sqlite_error)
}

fn valid_public_session_id(session_id: &str) -> bool {
    !session_id.is_empty()
        && session_id.len() <= 128
        && !session_id.starts_with("__")
        && session_id.bytes().enumerate().all(|(index, byte)| {
            byte.is_ascii_alphanumeric() || (index > 0 && matches!(byte, b'-' | b'_'))
        })
}

fn open_conversation_database(data_dir: &Path) -> io::Result<Connection> {
    let mismatches = inspect_v1_data_dir(data_dir)?;
    if !mismatches.is_empty() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "data directory does not match v1 storage",
        ));
    }
    Connection::open_with_flags(
        data_dir.join("codinal.db"),
        OpenFlags::SQLITE_OPEN_READ_ONLY,
    )
    .map_err(sqlite_error)
}

pub fn load_v1_fixture() -> Result<StorageFixture, serde_json::Error> {
    serde_json::from_str(include_str!("../../../contracts/v1/storage.json"))
}

/// Inspect an existing data directory without creating, recovering, migrating,
/// or modifying any file. A missing expected database is reported as a
/// mismatch, rather than being initialized.
pub fn inspect_v1_data_dir(data_dir: &Path) -> Result<Vec<StorageMismatch>, io::Error> {
    let metadata = fs::symlink_metadata(data_dir)?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "data directory must be a non-symlink directory",
        ));
    }
    let fixture = load_v1_fixture().map_err(|error| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            format!("invalid storage fixture: {error}"),
        )
    })?;
    if fixture.fixture_version != 1 || fixture.contract != "codinal.sqlite.v1" {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "unsupported storage fixture",
        ));
    }

    let mismatches = fixture
        .databases
        .iter()
        .map(|expected| inspect_database(data_dir, expected))
        .filter_map(Result::err)
        .collect();
    Ok(mismatches)
}

/// Create a consistent, isolated SQLite copy for Rust shadow validation.
///
/// The source is opened read-only and never modified. The destination must
/// not exist; this prevents an accidental dual-writer or overwrite of a prior
/// validation artifact.
pub fn create_v1_shadow_snapshot(source: &Path, destination: &Path) -> io::Result<()> {
    if destination.exists() {
        return Err(io::Error::new(
            io::ErrorKind::AlreadyExists,
            "shadow snapshot destination already exists",
        ));
    }
    let mismatches = inspect_v1_data_dir(source)?;
    if !mismatches.is_empty() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "source does not match the v1 storage fixture",
        ));
    }
    fs::create_dir(destination)?;
    let result = (|| {
        for database in load_v1_fixture()
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?
            .databases
        {
            let source_path = safe_database_path(source, &database.file)
                .map_err(|detail| io::Error::new(io::ErrorKind::InvalidInput, detail))?;
            let destination_path = destination.join(&database.file);
            let reader =
                Connection::open_with_flags(&source_path, OpenFlags::SQLITE_OPEN_READ_ONLY)
                    .map_err(sqlite_error)?;
            reader
                .backup(rusqlite::DatabaseName::Main, &destination_path, None)
                .map_err(sqlite_error)?;
        }
        if !inspect_v1_data_dir(destination)?.is_empty() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "shadow snapshot verification failed",
            ));
        }
        Ok(())
    })();
    if result.is_err() {
        let _ = fs::remove_dir_all(destination);
    }
    result
}

fn inspect_database(data_dir: &Path, expected: &DatabaseFixture) -> Result<(), StorageMismatch> {
    let path = safe_database_path(data_dir, &expected.file).map_err(|detail| StorageMismatch {
        file: expected.file.clone(),
        detail,
    })?;
    let metadata = fs::symlink_metadata(&path).map_err(|_| StorageMismatch {
        file: expected.file.clone(),
        detail: "database is missing".to_owned(),
    })?;
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err(StorageMismatch {
            file: expected.file.clone(),
            detail: "database must be a regular non-symlink file".to_owned(),
        });
    }
    let connection =
        Connection::open_with_flags(&path, OpenFlags::SQLITE_OPEN_READ_ONLY).map_err(|_| {
            StorageMismatch {
                file: expected.file.clone(),
                detail: "database cannot be opened read-only".to_owned(),
            }
        })?;
    let integrity: String = connection
        .query_row("PRAGMA integrity_check", [], |row| row.get(0))
        .map_err(|_| StorageMismatch {
            file: expected.file.clone(),
            detail: "database integrity cannot be checked".to_owned(),
        })?;
    if integrity != "ok" {
        return Err(StorageMismatch {
            file: expected.file.clone(),
            detail: "database integrity check failed".to_owned(),
        });
    }
    let actual_version: u32 = connection
        .query_row("PRAGMA user_version", [], |row| row.get(0))
        .map_err(|_| StorageMismatch {
            file: expected.file.clone(),
            detail: "database user_version cannot be read".to_owned(),
        })?;
    if actual_version != expected.user_version {
        return Err(StorageMismatch {
            file: expected.file.clone(),
            detail: format!(
                "user_version is {actual_version}, expected {}",
                expected.user_version
            ),
        });
    }
    let actual_tables = tables(&connection).map_err(|_| StorageMismatch {
        file: expected.file.clone(),
        detail: "database table inventory cannot be read".to_owned(),
    })?;
    let expected_tables = expected.tables.iter().cloned().collect::<BTreeSet<_>>();
    if actual_tables != expected_tables {
        return Err(StorageMismatch {
            file: expected.file.clone(),
            detail: "table inventory differs from v1 fixture".to_owned(),
        });
    }
    Ok(())
}

fn sqlite_error(error: rusqlite::Error) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, error)
}

fn safe_database_path(data_dir: &Path, file: &str) -> Result<PathBuf, String> {
    let candidate = Path::new(file);
    if candidate.components().count() != 1
        || candidate
            .extension()
            .is_none_or(|extension| extension != "db")
    {
        return Err("fixture database name is unsafe".to_owned());
    }
    Ok(data_dir.join(candidate))
}

fn tables(connection: &Connection) -> rusqlite::Result<BTreeSet<String>> {
    let mut statement = connection.prepare(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
    )?;
    let tables = statement
        .query_map([], |row| row.get::<_, String>(0))?
        .collect::<rusqlite::Result<BTreeSet<_>>>()?;
    Ok(tables)
}

#[cfg(test)]
mod tests {
    use super::{
        create_v1_shadow_snapshot, inspect_v1_data_dir, load_v1_fixture, read_session_messages,
        read_session_summaries,
    };
    use rusqlite::Connection;
    use std::fs;
    use std::path::Path;
    use std::sync::atomic::{AtomicU64, Ordering};

    static NEXT_TEST_DIR: AtomicU64 = AtomicU64::new(0);

    fn fresh_dir() -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "codinal-storage-test-{}-{}",
            std::process::id(),
            NEXT_TEST_DIR.fetch_add(1, Ordering::Relaxed)
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir(&dir).expect("directory");
        dir
    }

    fn create_fixture_databases(dir: &Path) {
        for database in load_v1_fixture().expect("fixture").databases {
            let connection = Connection::open(dir.join(database.file)).expect("database");
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

    #[test]
    fn embeds_the_versioned_reference_inventory() {
        let fixture = load_v1_fixture().expect("fixture");
        assert_eq!(fixture.fixture_version, 1);
        assert_eq!(fixture.contract, "codinal.sqlite.v1");
        assert_eq!(fixture.databases.len(), 9);
    }

    #[test]
    fn rejects_a_missing_inventory_without_creating_files() {
        let dir = fresh_dir();
        let mismatches = inspect_v1_data_dir(&dir).expect("inspect");
        assert_eq!(mismatches.len(), 9);
        assert!(dir.read_dir().expect("read").next().is_none());
        fs::remove_dir(&dir).expect("remove");
    }

    #[test]
    fn accepts_a_read_only_v1_database_inventory() {
        let dir = fresh_dir();
        create_fixture_databases(&dir);
        assert!(inspect_v1_data_dir(&dir).expect("inspect").is_empty());
        fs::remove_dir_all(&dir).expect("remove");
    }

    #[test]
    fn creates_an_isolated_verified_shadow_snapshot() {
        let source = fresh_dir();
        create_fixture_databases(&source);
        let destination = source.with_extension("shadow");
        create_v1_shadow_snapshot(&source, &destination).expect("snapshot");
        assert!(inspect_v1_data_dir(&destination)
            .expect("inspect")
            .is_empty());
        assert!(create_v1_shadow_snapshot(&source, &destination).is_err());
        fs::remove_dir_all(source).expect("remove source");
        fs::remove_dir_all(destination).expect("remove destination");
    }

    #[test]
    fn reads_public_sessions_and_ordered_messages_without_writing() {
        let dir = fresh_dir();
        create_fixture_databases(&dir);
        let database = Connection::open(dir.join("codinal.db")).expect("database");
        database.execute_batch(
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
               ('session-1','/work','/source','gpt','code','Migration','code',1,0,NULL,NULL,NULL,'2026-01-02T00:00:00Z'),
               ('__internal','/work',NULL,'gpt','code',NULL,'code',0,0,NULL,NULL,NULL,'2026-01-03T00:00:00Z'),
               ('worker-1','/work',NULL,'gpt','code',NULL,'code',0,0,'worker',NULL,NULL,'2026-01-04T00:00:00Z');
             INSERT INTO messages VALUES
               ('session-1',1,'{\"role\":\"assistant\",\"content\":\"second\"}'),
               ('session-1',0,'{\"role\":\"user\",\"content\":\"first\"}'),
               ('worker-1',0,'{\"role\":\"assistant\",\"content\":\"private\"}');",
        )
        .expect("fixture rows");
        drop(database);

        let sessions = read_session_summaries(&dir, None).expect("sessions");
        assert_eq!(sessions.len(), 1);
        assert_eq!(sessions[0].session_id, "session-1");
        assert_eq!(sessions[0].workspace, "/source");
        assert_eq!(sessions[0].messages, 2);
        let messages = read_session_messages(&dir, "session-1").expect("messages");
        assert_eq!(messages[0]["content"], "first");
        assert_eq!(messages[1]["content"], "second");
        assert!(read_session_messages(&dir, "worker-1")
            .expect("hidden worker messages")
            .is_empty());

        fs::remove_dir_all(dir).expect("remove");
    }
}
