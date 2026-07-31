use rusqlite::{Connection, OpenFlags, Transaction};
use std::fs::{self, OpenOptions};
use std::io;
use std::os::unix::fs::OpenOptionsExt;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

pub const CONVERSATION_SCHEMA_VERSION: i64 = 8;

#[derive(Debug, PartialEq, Eq)]
pub struct ConversationMigrationReport {
    pub from_version: i64,
    pub to_version: i64,
    pub backup: Option<PathBuf>,
    pub recovered_from: Option<PathBuf>,
}

pub fn migrate_conversation_snapshot(
    source_database: &Path,
    destination: &Path,
) -> io::Result<ConversationMigrationReport> {
    validate_source(source_database)?;
    if destination.exists() {
        return Err(io::Error::new(
            io::ErrorKind::AlreadyExists,
            "migration destination already exists",
        ));
    }
    let parent = destination.parent().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            "migration destination has no parent",
        )
    })?;
    let name = destination
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| {
            io::Error::new(io::ErrorKind::InvalidInput, "invalid migration destination")
        })?;
    let staging = parent.join(format!(
        ".{name}.migrate-{}-{}",
        std::process::id(),
        timestamp()
    ));
    fs::create_dir(&staging)?;
    fs::set_permissions(&staging, fs::Permissions::from_mode(0o700))?;
    let result = (|| {
        let database = staging.join("codinal.db");
        copy_sqlite(source_database, &database)?;
        secure_file(&database)?;
        let report = migrate_owned_database(&staging, None, true)?;
        fs::rename(&staging, destination)?;
        sync_directory(parent)?;
        Ok(remap_report(report, &staging, destination))
    })();
    if result.is_err() {
        let _ = fs::remove_dir_all(&staging);
    }
    result
}

pub fn recover_conversation_snapshot(
    destination: &Path,
) -> io::Result<ConversationMigrationReport> {
    validate_owned_directory(destination)?;
    let database = destination.join("codinal.db");
    if let Ok((version, integrity)) = inspect_database(&database) {
        if integrity == "ok" {
            validate_version(version)?;
            return migrate_owned_database(destination, None, true);
        }
    }
    let backup = latest_valid_backup(destination)?
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "no valid migration backup"))?;
    let staging = destination.join(format!(
        ".codinal-recovery-{}-{}",
        std::process::id(),
        timestamp()
    ));
    fs::create_dir(&staging)?;
    fs::set_permissions(&staging, fs::Permissions::from_mode(0o700))?;
    let staged_database = staging.join("codinal.db");
    let staged = (|| {
        copy_sqlite(&backup, &staged_database)?;
        secure_file(&staged_database)?;
        migrate_owned_database(&staging, Some(backup.clone()), false)
    })();
    let report = match staged {
        Ok(report) => report,
        Err(error) => {
            let _ = fs::remove_dir_all(&staging);
            return Err(error);
        }
    };

    let recovery = destination.join("recovery");
    secure_directory(&recovery)?;
    let preserved = recovery.join(format!("codinal.db.corrupt-{}.preserved", timestamp()));
    if database.exists() {
        copy_private_file(&database, &preserved)?;
    }
    for suffix in ["-journal", "-wal", "-shm"] {
        let companion = PathBuf::from(format!("{}{suffix}", database.display()));
        if companion.exists() {
            let preserved_companion = PathBuf::from(format!("{}{suffix}", preserved.display()));
            copy_private_file(&companion, &preserved_companion)?;
            fs::remove_file(&companion)?;
        }
    }
    sync_directory(&recovery)?;
    fs::rename(&staged_database, &database)?;
    secure_file(&database)?;
    sync_directory(destination)?;
    fs::remove_dir_all(&staging)?;
    Ok(report)
}

fn migrate_owned_database(
    destination: &Path,
    recovered_from: Option<PathBuf>,
    create_pre_migration_backup: bool,
) -> io::Result<ConversationMigrationReport> {
    validate_owned_directory(destination)?;
    let database = destination.join("codinal.db");
    let (from_version, integrity) = inspect_database(&database)?;
    if integrity != "ok" {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "conversation database failed integrity check",
        ));
    }
    validate_version(from_version)?;
    let backup = if create_pre_migration_backup && from_version < CONVERSATION_SCHEMA_VERSION {
        Some(create_backup(destination, &database, from_version)?)
    } else {
        recovered_from.clone()
    };
    let mut connection = Connection::open_with_flags(
        &database,
        OpenFlags::SQLITE_OPEN_READ_WRITE | OpenFlags::SQLITE_OPEN_NO_MUTEX,
    )
    .map_err(sqlite_error)?;
    connection
        .execute_batch(
            "PRAGMA foreign_keys = ON; PRAGMA journal_mode = DELETE; PRAGMA synchronous = FULL;",
        )
        .map_err(sqlite_error)?;
    let transaction = connection.transaction().map_err(sqlite_error)?;
    for version in (from_version + 1)..=CONVERSATION_SCHEMA_VERSION {
        apply_migration(&transaction, version)?;
        transaction
            .pragma_update(None, "user_version", version)
            .map_err(sqlite_error)?;
    }
    transaction.commit().map_err(sqlite_error)?;
    connection
        .execute_batch("PRAGMA optimize")
        .map_err(sqlite_error)?;
    drop(connection);
    secure_file(&database)?;
    sync_file(&database)?;
    sync_directory(destination)?;
    let (to_version, integrity) = inspect_database(&database)?;
    if to_version != CONVERSATION_SCHEMA_VERSION || integrity != "ok" {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "migrated conversation database failed verification",
        ));
    }
    Ok(ConversationMigrationReport {
        from_version,
        to_version,
        backup,
        recovered_from,
    })
}

fn remap_report(
    mut report: ConversationMigrationReport,
    staging: &Path,
    destination: &Path,
) -> ConversationMigrationReport {
    report.backup = report.backup.and_then(|path| {
        path.strip_prefix(staging)
            .ok()
            .map(|tail| destination.join(tail))
    });
    report
}

fn copy_private_file(source: &Path, destination: &Path) -> io::Result<()> {
    let mut target = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(destination)?;
    let result = (|| {
        let mut source = OpenOptions::new().read(true).open(source)?;
        io::copy(&mut source, &mut target)?;
        target.sync_all()
    })();
    if result.is_err() {
        let _ = fs::remove_file(destination);
        return result;
    }
    secure_file(destination)?;
    sync_file(destination)
}

fn apply_migration(transaction: &Transaction<'_>, version: i64) -> io::Result<()> {
    match version {
        1 => transaction.execute_batch(V1_SCHEMA).map_err(sqlite_error)?,
        2 => add_column(transaction, "sessions", "source_workspace", "TEXT")?,
        3 => {
            add_column(
                transaction,
                "sessions",
                "turn_status",
                "TEXT NOT NULL DEFAULT 'idle'",
            )?;
            add_column(
                transaction,
                "sessions",
                "active_tool_call_ids",
                "TEXT NOT NULL DEFAULT '[]'",
            )?;
            transaction.execute_batch(V3_SCHEMA).map_err(sqlite_error)?;
            add_column(
                transaction,
                "approval_decisions",
                "request_fingerprint",
                "TEXT NOT NULL DEFAULT ''",
            )?;
        }
        4 => transaction.execute_batch(V4_SCHEMA).map_err(sqlite_error)?,
        5 => {
            add_column(transaction, "sessions", "workspace_device", "INTEGER")?;
            add_column(transaction, "sessions", "workspace_inode", "INTEGER")?;
        }
        6 => add_column(transaction, "sessions", "origin_session_id", "TEXT")?,
        7 => transaction.execute_batch(V7_SCHEMA).map_err(sqlite_error)?,
        8 => transaction.execute_batch(V8_SCHEMA).map_err(sqlite_error)?,
        _ => {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "conversation migration chain has a gap",
            ))
        }
    }
    Ok(())
}

fn add_column(
    transaction: &Transaction<'_>,
    table: &str,
    column: &str,
    declaration: &str,
) -> io::Result<()> {
    let mut statement = transaction
        .prepare(&format!("PRAGMA table_info({table})"))
        .map_err(sqlite_error)?;
    let columns = statement
        .query_map([], |row| row.get::<_, String>(1))
        .map_err(sqlite_error)?
        .collect::<rusqlite::Result<Vec<_>>>()
        .map_err(sqlite_error)?;
    drop(statement);
    if !columns.iter().any(|existing| existing == column) {
        transaction
            .execute_batch(&format!(
                "ALTER TABLE {table} ADD COLUMN {column} {declaration}"
            ))
            .map_err(sqlite_error)?;
    }
    Ok(())
}

fn validate_source(path: &Path) -> io::Result<()> {
    let metadata = fs::symlink_metadata(path)?;
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid source database",
        ));
    }
    let (version, integrity) = inspect_database(path)?;
    validate_version(version)?;
    if integrity != "ok" {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "source database is corrupt",
        ));
    }
    Ok(())
}

fn validate_version(version: i64) -> io::Result<()> {
    if !(0..=CONVERSATION_SCHEMA_VERSION).contains(&version) {
        Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "unsupported conversation schema version",
        ))
    } else {
        Ok(())
    }
}

fn validate_owned_directory(path: &Path) -> io::Result<()> {
    let metadata = fs::symlink_metadata(path)?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid migration directory",
        ));
    }
    Ok(())
}

fn create_backup(destination: &Path, database: &Path, version: i64) -> io::Result<PathBuf> {
    let backups = destination.join("backups");
    secure_directory(&backups)?;
    let backup = backups.join(format!(
        "codinal.db.pre-v{version}-to-v{CONVERSATION_SCHEMA_VERSION}-{}.bak",
        timestamp()
    ));
    copy_sqlite(database, &backup)?;
    secure_file(&backup)?;
    sync_file(&backup)?;
    sync_directory(&backups)?;
    Ok(backup)
}

fn latest_valid_backup(destination: &Path) -> io::Result<Option<PathBuf>> {
    let backups = destination.join("backups");
    if !backups.is_dir() {
        return Ok(None);
    }
    let mut candidates = fs::read_dir(backups)?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| {
            path.file_name()
                .and_then(|name| name.to_str())
                .is_some_and(|name| name.starts_with("codinal.db.pre-v") && name.ends_with(".bak"))
        })
        .collect::<Vec<_>>();
    candidates.sort_by_key(|path| std::cmp::Reverse(backup_timestamp(path)));
    for candidate in candidates {
        if inspect_database(&candidate).is_ok_and(|(version, integrity)| {
            version <= CONVERSATION_SCHEMA_VERSION && integrity == "ok"
        }) {
            return Ok(Some(candidate));
        }
    }
    Ok(None)
}

fn backup_timestamp(path: &Path) -> String {
    path.file_stem()
        .and_then(|name| name.to_str())
        .and_then(|name| name.rsplit_once('-'))
        .map(|(_, timestamp)| timestamp)
        .unwrap_or_default()
        .to_owned()
}

fn copy_sqlite(source: &Path, destination: &Path) -> io::Result<()> {
    let created = !destination.exists();
    if created {
        OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(destination)?;
    }
    let source = Connection::open_with_flags(
        source,
        OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
    )
    .map_err(sqlite_error)?;
    let result = source
        .backup(rusqlite::DatabaseName::Main, destination, None)
        .map_err(sqlite_error);
    if result.is_err() && created {
        let _ = fs::remove_file(destination);
    }
    if result.is_ok() {
        sync_file(destination)?;
        if let Some(parent) = destination.parent() {
            sync_directory(parent)?;
        }
    }
    result
}

fn inspect_database(path: &Path) -> io::Result<(i64, String)> {
    let connection = Connection::open_with_flags(
        path,
        OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
    )
    .map_err(sqlite_error)?;
    let integrity = connection
        .query_row("PRAGMA integrity_check", [], |row| row.get(0))
        .map_err(sqlite_error)?;
    let version = connection
        .query_row("PRAGMA user_version", [], |row| row.get(0))
        .map_err(sqlite_error)?;
    Ok((version, integrity))
}

fn secure_directory(path: &Path) -> io::Result<()> {
    fs::create_dir_all(path)?;
    fs::set_permissions(path, fs::Permissions::from_mode(0o700))?;
    Ok(())
}

fn secure_file(path: &Path) -> io::Result<()> {
    fs::set_permissions(path, fs::Permissions::from_mode(0o600))
}

fn sync_file(path: &Path) -> io::Result<()> {
    OpenOptions::new().read(true).open(path)?.sync_all()
}

fn sync_directory(path: &Path) -> io::Result<()> {
    OpenOptions::new().read(true).open(path)?.sync_all()
}

fn timestamp() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_micros()
}

fn sqlite_error(error: rusqlite::Error) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, error)
}

const V1_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY, workspace TEXT NOT NULL, model TEXT NOT NULL,
  mode TEXT NOT NULL, title TEXT, agent TEXT NOT NULL DEFAULT 'code',
  extra_roots TEXT NOT NULL DEFAULT '[]', grants TEXT NOT NULL DEFAULT '{}',
  pinned INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0,
  origin TEXT, origin_label TEXT,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS messages (
  session_id TEXT NOT NULL, sequence INTEGER NOT NULL, payload TEXT NOT NULL,
  PRIMARY KEY (session_id, sequence),
  FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS workspaces (
  path TEXT PRIMARY KEY,
  last_used TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
"#;

const V3_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS approval_decisions (
  session_id TEXT NOT NULL, tool_call_id TEXT NOT NULL,
  request_fingerprint TEXT NOT NULL, outcome TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  PRIMARY KEY (session_id, tool_call_id),
  FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
"#;

const V4_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS interaction_decisions (
  session_id TEXT NOT NULL, tool_call_id TEXT NOT NULL, kind TEXT NOT NULL,
  request_fingerprint TEXT NOT NULL, response TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  PRIMARY KEY (session_id, tool_call_id),
  FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
"#;

const V7_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS plan_artifacts (
  session_id TEXT NOT NULL, plan_id TEXT NOT NULL, tool_call_id TEXT NOT NULL,
  plan TEXT NOT NULL, tasks TEXT NOT NULL DEFAULT '[]',
  selected_task_ids TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'draft',
  revision INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  PRIMARY KEY (session_id, plan_id), UNIQUE (session_id, tool_call_id),
  FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
"#;

const V8_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS turn_receipts (
  turn_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, outcome TEXT NOT NULL,
  message_count INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS turn_receipts_session_created
ON turn_receipts(session_id, created_at, turn_id);
"#;

#[cfg(test)]
mod tests {
    use super::{
        apply_migration, migrate_conversation_snapshot, recover_conversation_snapshot,
        CONVERSATION_SCHEMA_VERSION,
    };
    use rusqlite::Connection;
    use std::fs;
    use std::os::unix::fs::PermissionsExt;
    use std::path::{Path, PathBuf};
    use std::sync::atomic::{AtomicU64, Ordering};

    static NEXT_DIR: AtomicU64 = AtomicU64::new(0);

    fn directory() -> PathBuf {
        let path = std::env::temp_dir().join(format!(
            "codinal-migration-test-{}-{}",
            std::process::id(),
            NEXT_DIR.fetch_add(1, Ordering::Relaxed)
        ));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir(&path).expect("test directory");
        path
    }

    fn create_v1(path: &Path) {
        let connection = Connection::open(path).expect("source");
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
                INSERT INTO sessions (session_id, workspace, model, mode)
                VALUES ('retained-v1', '/workspace', 'ollama:qwen3', 'interactive');
                INSERT INTO messages VALUES
                ('retained-v1', 0, '{"role":"user","content":"preserve this"}');
                PRAGMA user_version = 1;
                "#,
            )
            .expect("v1 schema");
    }

    fn create_version(path: &Path, version: i64) {
        let mut connection = Connection::open(path).expect("source");
        let transaction = connection.transaction().expect("transaction");
        for migration in 1..=version.max(1) {
            apply_migration(&transaction, migration).expect("migration fixture");
            transaction
                .pragma_update(None, "user_version", migration)
                .expect("fixture version");
        }
        transaction.commit().expect("fixture commit");
        if version == 0 {
            connection
                .pragma_update(None, "user_version", 0)
                .expect("legacy version");
        }
        connection
            .execute(
                "INSERT INTO sessions (session_id, workspace, model, mode) VALUES (?1, '/workspace', 'ollama:qwen3', 'interactive')",
                [format!("retained-v{version}")],
            )
            .expect("retained session");
    }

    #[test]
    fn migrates_v1_snapshot_with_private_backup_and_preserved_data() {
        let root = directory();
        let source = root.join("legacy.db");
        let destination = root.join("cutover");
        create_v1(&source);

        let report = migrate_conversation_snapshot(&source, &destination).expect("migration");
        assert_eq!(report.from_version, 1);
        assert_eq!(report.to_version, CONVERSATION_SCHEMA_VERSION);
        assert_eq!(
            fs::metadata(&destination)
                .expect("destination")
                .permissions()
                .mode()
                & 0o777,
            0o700
        );
        assert_eq!(
            fs::metadata(report.backup.as_ref().expect("backup path"))
                .expect("backup")
                .permissions()
                .mode()
                & 0o777,
            0o600
        );
        let migrated = Connection::open(destination.join("codinal.db")).expect("migrated");
        assert_eq!(
            migrated
                .query_row("PRAGMA user_version", [], |row| row.get::<_, i64>(0))
                .expect("version"),
            8
        );
        assert_eq!(
            migrated
                .query_row(
                    "SELECT json_extract(payload, '$.content') FROM messages",
                    [],
                    |row| row.get::<_, String>(0),
                )
                .expect("message"),
            "preserve this"
        );
        assert_eq!(
            migrated
                .query_row("PRAGMA integrity_check", [], |row| row.get::<_, String>(0))
                .expect("integrity"),
            "ok"
        );
        drop(migrated);
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn corrupt_interrupted_destination_restores_backup_and_replays_migration() {
        let root = directory();
        let source = root.join("legacy.db");
        let destination = root.join("cutover");
        create_v1(&source);
        migrate_conversation_snapshot(&source, &destination).expect("initial migration");
        fs::write(destination.join("codinal.db"), b"interrupted migration").expect("corrupt");
        fs::write(destination.join("codinal.db-journal"), b"stale hot journal").expect("journal");

        let report = recover_conversation_snapshot(&destination).expect("recovery");
        assert!(report.recovered_from.is_some());
        let recovered = Connection::open(destination.join("codinal.db")).expect("recovered");
        assert_eq!(
            recovered
                .query_row("PRAGMA user_version", [], |row| row.get::<_, i64>(0))
                .expect("version"),
            8
        );
        assert_eq!(
            recovered
                .query_row("SELECT COUNT(*) FROM messages", [], |row| row
                    .get::<_, i64>(0))
                .expect("messages"),
            1
        );
        drop(recovered);
        assert_eq!(
            fs::read_dir(destination.join("recovery"))
                .expect("recovery directory")
                .filter_map(Result::ok)
                .filter(|entry| entry.file_name().to_string_lossy().ends_with(".preserved"))
                .count(),
            1
        );
        assert!(!destination.join("codinal.db-journal").exists());
        assert!(fs::read_dir(destination.join("recovery"))
            .expect("recovery directory")
            .filter_map(Result::ok)
            .any(|entry| entry
                .file_name()
                .to_string_lossy()
                .ends_with(".preserved-journal")));
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn refuses_future_schema_without_creating_destination() {
        let root = directory();
        let source = root.join("future.db");
        let destination = root.join("cutover");
        let connection = Connection::open(&source).expect("source");
        connection
            .execute_batch("CREATE TABLE future(value TEXT); PRAGMA user_version = 99;")
            .expect("future schema");
        drop(connection);
        let original = fs::read(&source).expect("original");

        assert!(migrate_conversation_snapshot(&source, &destination).is_err());
        assert_eq!(fs::read(&source).expect("source"), original);
        assert!(!destination.exists());
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn migration_corpus_replays_every_released_conversation_boundary() {
        let root = directory();
        for version in [0, 2, 3, 6, 7] {
            let source = root.join(format!("v{version}.db"));
            let destination = root.join(format!("cutover-v{version}"));
            create_version(&source, version);
            let report =
                migrate_conversation_snapshot(&source, &destination).expect("versioned migration");
            assert_eq!(report.from_version, version);
            let migrated = Connection::open(destination.join("codinal.db")).expect("migrated");
            assert_eq!(
                migrated
                    .query_row("PRAGMA user_version", [], |row| row.get::<_, i64>(0))
                    .expect("version"),
                8
            );
            assert_eq!(
                migrated
                    .query_row("SELECT COUNT(*) FROM sessions", [], |row| row
                        .get::<_, i64>(0))
                    .expect("sessions"),
                1
            );
        }
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn empty_v0_database_builds_the_complete_schema() {
        let root = directory();
        let source = root.join("empty.db");
        let destination = root.join("cutover");
        drop(Connection::open(&source).expect("empty source"));
        migrate_conversation_snapshot(&source, &destination).expect("migration");
        let migrated = Connection::open(destination.join("codinal.db")).expect("migrated");
        assert_eq!(
            migrated
                .query_row(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'",
                    [],
                    |row| { row.get::<_, i64>(0) }
                )
                .expect("tables"),
            7
        );
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn healthy_current_snapshot_validation_does_not_create_another_backup() {
        let root = directory();
        let source = root.join("legacy.db");
        let destination = root.join("cutover");
        create_v1(&source);
        migrate_conversation_snapshot(&source, &destination).expect("migration");
        let before = fs::read_dir(destination.join("backups"))
            .expect("backups")
            .count();
        let report = recover_conversation_snapshot(&destination).expect("validation");
        assert!(report.backup.is_none());
        assert_eq!(
            fs::read_dir(destination.join("backups"))
                .expect("backups")
                .count(),
            before
        );
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn failed_initial_migration_removes_staging_and_remains_retryable() {
        let root = directory();
        let source = root.join("malformed-v1.db");
        let destination = root.join("cutover");
        let connection = Connection::open(&source).expect("source");
        connection
            .execute_batch("CREATE TABLE unrelated(value TEXT); PRAGMA user_version = 1;")
            .expect("malformed schema");
        drop(connection);
        assert!(migrate_conversation_snapshot(&source, &destination).is_err());
        assert!(!destination.exists());
        assert_eq!(
            fs::read_dir(&root)
                .expect("root")
                .filter_map(Result::ok)
                .filter(|entry| entry.file_name().to_string_lossy().contains(".migrate-"))
                .count(),
            0
        );
        assert!(migrate_conversation_snapshot(&source, &destination).is_err());
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn recovery_without_a_valid_backup_keeps_the_active_database() {
        let root = directory();
        let destination = root.join("cutover");
        fs::create_dir(&destination).expect("destination");
        let active = destination.join("codinal.db");
        let corrupt = b"corrupt without backup";
        fs::write(&active, corrupt).expect("active");
        assert!(recover_conversation_snapshot(&destination).is_err());
        assert_eq!(fs::read(&active).expect("active remains"), corrupt);
        assert!(recover_conversation_snapshot(&destination).is_err());
        fs::remove_dir_all(root).expect("cleanup");
    }
}
