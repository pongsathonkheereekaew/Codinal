use rusqlite::{Connection, OpenFlags, Transaction};
use std::fs::{self, OpenOptions};
use std::io;
use std::os::unix::fs::OpenOptionsExt;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

pub const CONVERSATION_SCHEMA_VERSION: i64 = 10;
pub const GIT_WORKTREE_SCHEMA_VERSION: i64 = 5;
pub const WORKER_SCHEMA_VERSION: i64 = 2;

#[derive(Clone, Copy)]
struct MigrationPlan {
    file: &'static str,
    target: i64,
    apply: fn(&Transaction<'_>, i64) -> io::Result<()>,
}

#[derive(Debug, PartialEq, Eq)]
pub struct DataDirectoryMigrationReport {
    pub databases: Vec<ConversationMigrationReport>,
    pub publication_durable: bool,
}

const CONVERSATION_PLAN: MigrationPlan = MigrationPlan {
    file: "codinal.db",
    target: CONVERSATION_SCHEMA_VERSION,
    apply: apply_conversation_migration,
};
const GIT_WORKTREE_PLAN: MigrationPlan = MigrationPlan {
    file: "git-worktrees.db",
    target: GIT_WORKTREE_SCHEMA_VERSION,
    apply: apply_git_worktree_migration,
};
const WORKER_PLAN: MigrationPlan = MigrationPlan {
    file: "workers.db",
    target: WORKER_SCHEMA_VERSION,
    apply: apply_worker_migration,
};
const AUDIT_PLAN: MigrationPlan = MigrationPlan {
    file: "audit.db",
    target: 1,
    apply: apply_audit_migration,
};
const EXTENSIONS_PLAN: MigrationPlan = MigrationPlan {
    file: "extensions.db",
    target: 1,
    apply: apply_extensions_migration,
};
const GOALS_PLAN: MigrationPlan = MigrationPlan {
    file: "goals.db",
    target: 1,
    apply: apply_goals_migration,
};
const MCP_PLAN: MigrationPlan = MigrationPlan {
    file: "mcp.db",
    target: 1,
    apply: apply_mcp_migration,
};
const PLAN_BUILDS_PLAN: MigrationPlan = MigrationPlan {
    file: "plan-builds.db",
    target: 1,
    apply: apply_plan_builds_migration,
};
const PREVIEW_PLAN: MigrationPlan = MigrationPlan {
    file: "preview.db",
    target: 1,
    apply: apply_preview_migration,
};

const ALL_PLANS: [MigrationPlan; 9] = [
    AUDIT_PLAN,
    CONVERSATION_PLAN,
    EXTENSIONS_PLAN,
    GIT_WORKTREE_PLAN,
    GOALS_PLAN,
    MCP_PLAN,
    PLAN_BUILDS_PLAN,
    PREVIEW_PLAN,
    WORKER_PLAN,
];

#[cfg(debug_assertions)]
fn migration_test_pause(stage: &str, file: Option<&str>) {
    let requested = std::env::var("CODINAL_TEST_MIGRATION_PAUSE").ok();
    let matches = requested.as_deref() == Some(stage)
        || file.is_some_and(|file| requested.as_deref() == Some(&format!("{stage}:{file}")));
    if matches {
        std::thread::sleep(std::time::Duration::from_secs(30));
    }
}

#[cfg(not(debug_assertions))]
fn migration_test_pause(_stage: &str, _file: Option<&str>) {}

#[derive(Debug, PartialEq, Eq)]
pub struct ConversationMigrationReport {
    pub database: String,
    pub from_version: i64,
    pub to_version: i64,
    pub backup: Option<PathBuf>,
    pub recovered_from: Option<PathBuf>,
    pub publication_durable: bool,
    pub cleanup_complete: bool,
}

/// Initialize missing databases and migrate existing databases only after the
/// caller has acquired exclusive ownership of this data directory.
pub fn prepare_owned_data_directory(
    data_dir: &Path,
) -> io::Result<Vec<ConversationMigrationReport>> {
    validate_owned_directory(data_dir)?;
    let mut journal = crate::migration_journal::begin(
        data_dir,
        ALL_PLANS.iter().map(|plan| (plan.file, plan.target)),
    )?;
    let mut reports = Vec::with_capacity(ALL_PLANS.len());
    for plan in ALL_PLANS {
        let database = data_dir.join(plan.file);
        let source_version = if validate_owned_database(data_dir, &database)? {
            inspect_database(&database)?.0
        } else {
            0
        };
        crate::migration_journal::mark_database_started(
            data_dir,
            &mut journal,
            plan.file,
            source_version,
        )?;
        let result: io::Result<ConversationMigrationReport> =
            if validate_owned_database(data_dir, &database)? {
                migrate_owned_database(data_dir, None, true, plan)
            } else {
                let staging = data_dir.join(format!(
                    ".{}.initialize-{}-{}",
                    plan.file,
                    std::process::id(),
                    timestamp()
                ));
                secure_owned_directory(data_dir, &staging)?;
                let result = (|| {
                    let staged_database = staging.join(plan.file);
                    drop(Connection::open(&staged_database).map_err(sqlite_error)?);
                    let report = migrate_owned_database(&staging, None, false, plan)?;
                    fs::rename(&staged_database, &database)?;
                    sync_directory(data_dir)?;
                    Ok(report)
                })();
                let _ = fs::remove_dir_all(&staging);
                result
            };
        match result {
            Ok(report) => {
                let checksum = report
                    .backup
                    .as_ref()
                    .and_then(|path| crate::migration_journal::sha256_file(path).ok());
                crate::migration_journal::mark_database_committed(
                    data_dir,
                    &mut journal,
                    plan.file,
                    checksum,
                )?;
                migration_test_pause("database_committed", Some(plan.file));
                reports.push(report);
            }
            Err(error) => {
                let _ = crate::migration_journal::mark_failed(data_dir, &mut journal);
                return Err(error);
            }
        }
    }
    crate::migration_journal::mark_complete(data_dir, &mut journal)?;
    migration_test_pause("commit_marker", None);
    Ok(reports)
}

pub fn migrate_data_directory_snapshot(
    source: &Path,
    destination: &Path,
) -> io::Result<DataDirectoryMigrationReport> {
    let source_metadata = fs::symlink_metadata(source)?;
    if source_metadata.file_type().is_symlink() || !source_metadata.is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid source data directory",
        ));
    }
    if destination.exists() {
        return Err(io::Error::new(
            io::ErrorKind::AlreadyExists,
            "migration destination already exists",
        ));
    }
    let canonical_source = fs::canonicalize(source)?;
    let parent = destination.parent().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            "migration destination has no parent",
        )
    })?;
    let canonical_parent = fs::canonicalize(parent)?;
    if canonical_parent.starts_with(&canonical_source) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "migration destination must be outside the source data directory",
        ));
    }
    let name = destination
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| {
            io::Error::new(io::ErrorKind::InvalidInput, "invalid migration destination")
        })?;
    let staging = parent.join(format!(
        ".{name}.cutover-{}-{}",
        std::process::id(),
        timestamp()
    ));
    fs::create_dir(&staging)?;
    fs::set_permissions(&staging, fs::Permissions::from_mode(0o700))?;
    let result = (|| {
        let mut journal = crate::migration_journal::begin(
            &staging,
            ALL_PLANS.iter().map(|plan| (plan.file, plan.target)),
        )?;
        let mut reports = Vec::with_capacity(ALL_PLANS.len());
        for plan in ALL_PLANS {
            let source_database = source.join(plan.file);
            validate_source(&source_database, plan.target)?;
            let source_version = inspect_database(&source_database)?.0;
            crate::migration_journal::mark_database_started(
                &staging,
                &mut journal,
                plan.file,
                source_version,
            )?;
            let staged_database = staging.join(plan.file);
            copy_sqlite(&source_database, &staged_database)?;
            secure_file(&staged_database)?;
            let report = migrate_owned_database(&staging, None, true, plan)?;
            let checksum = report
                .backup
                .as_ref()
                .and_then(|path| crate::migration_journal::sha256_file(path).ok());
            crate::migration_journal::mark_database_committed(
                &staging,
                &mut journal,
                plan.file,
                checksum,
            )?;
            reports.push(report);
        }
        crate::migration_journal::mark_complete(&staging, &mut journal)?;
        migration_test_pause("before_publication", None);
        fs::rename(&staging, destination)?;
        let publication_durable = sync_directory(parent).is_ok();
        Ok(DataDirectoryMigrationReport {
            databases: reports
                .into_iter()
                .map(|report| {
                    let mut report = remap_report(report, &staging, destination);
                    report.publication_durable = publication_durable;
                    report
                })
                .collect(),
            publication_durable,
        })
    })();
    if result.is_err() {
        let _ = fs::remove_dir_all(&staging);
    }
    result
}

pub fn migrate_conversation_snapshot(
    source_database: &Path,
    destination: &Path,
) -> io::Result<ConversationMigrationReport> {
    migrate_snapshot(source_database, destination, CONVERSATION_PLAN)
}

pub fn migrate_git_worktree_snapshot(
    source_database: &Path,
    destination: &Path,
) -> io::Result<ConversationMigrationReport> {
    migrate_snapshot(source_database, destination, GIT_WORKTREE_PLAN)
}

pub fn migrate_worker_snapshot(
    source_database: &Path,
    destination: &Path,
) -> io::Result<ConversationMigrationReport> {
    migrate_snapshot(source_database, destination, WORKER_PLAN)
}

fn migrate_snapshot(
    source_database: &Path,
    destination: &Path,
    plan: MigrationPlan,
) -> io::Result<ConversationMigrationReport> {
    validate_source(source_database, plan.target)?;
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
        let database = staging.join(plan.file);
        copy_sqlite(source_database, &database)?;
        secure_file(&database)?;
        let report = migrate_owned_database(&staging, None, true, plan)?;
        fs::rename(&staging, destination)?;
        let publication_durable = sync_directory(parent).is_ok();
        let mut report = remap_report(report, &staging, destination);
        report.publication_durable = publication_durable;
        Ok(report)
    })();
    if result.is_err() {
        let _ = fs::remove_dir_all(&staging);
    }
    result
}

pub fn recover_conversation_snapshot(
    destination: &Path,
) -> io::Result<ConversationMigrationReport> {
    recover_snapshot(destination, CONVERSATION_PLAN)
}

pub fn recover_git_worktree_snapshot(
    destination: &Path,
) -> io::Result<ConversationMigrationReport> {
    recover_snapshot(destination, GIT_WORKTREE_PLAN)
}

pub fn recover_worker_snapshot(destination: &Path) -> io::Result<ConversationMigrationReport> {
    recover_snapshot(destination, WORKER_PLAN)
}

fn recover_snapshot(
    destination: &Path,
    plan: MigrationPlan,
) -> io::Result<ConversationMigrationReport> {
    validate_owned_directory(destination)?;
    let database = destination.join(plan.file);
    if let Ok((version, integrity)) = inspect_database(&database) {
        if integrity == "ok" {
            validate_version(version, plan.target)?;
            return migrate_owned_database(destination, None, true, plan);
        }
    }
    let backup = latest_valid_backup(destination, plan)?
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "no valid migration backup"))?;
    let staging = destination.join(format!(
        ".{}-recovery-{}-{}",
        plan.file,
        std::process::id(),
        timestamp()
    ));
    fs::create_dir(&staging)?;
    fs::set_permissions(&staging, fs::Permissions::from_mode(0o700))?;
    let staged_database = staging.join(plan.file);
    let staged = (|| {
        copy_sqlite(&backup, &staged_database)?;
        secure_file(&staged_database)?;
        migrate_owned_database(&staging, Some(backup.clone()), false, plan)
    })();
    let report = match staged {
        Ok(report) => report,
        Err(error) => {
            let _ = fs::remove_dir_all(&staging);
            return Err(error);
        }
    };

    let recovery = destination.join("recovery");
    secure_owned_directory(destination, &recovery)?;
    let preserved = recovery.join(format!("{}.corrupt-{}.preserved", plan.file, timestamp()));
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
    let publication_durable = sync_directory(destination).is_ok();
    let cleanup_complete = fs::remove_dir(&staging).is_ok();
    Ok(ConversationMigrationReport {
        publication_durable,
        cleanup_complete,
        ..report
    })
}

fn migrate_owned_database(
    destination: &Path,
    recovered_from: Option<PathBuf>,
    create_pre_migration_backup: bool,
    plan: MigrationPlan,
) -> io::Result<ConversationMigrationReport> {
    validate_owned_directory(destination)?;
    let database = destination.join(plan.file);
    if !validate_owned_database(destination, &database)? {
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            "owned database is missing",
        ));
    }
    let (from_version, integrity) = inspect_database(&database)?;
    if integrity != "ok" {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "conversation database failed integrity check",
        ));
    }
    validate_version(from_version, plan.target)?;
    let backup = if create_pre_migration_backup && from_version < plan.target {
        Some(create_backup(
            destination,
            &database,
            from_version,
            plan.target,
        )?)
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
    for version in (from_version + 1)..=plan.target {
        (plan.apply)(&transaction, version)?;
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
    if to_version != plan.target || integrity != "ok" {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "migrated conversation database failed verification",
        ));
    }
    Ok(ConversationMigrationReport {
        database: plan.file.to_owned(),
        from_version,
        to_version,
        backup,
        recovered_from,
        publication_durable: true,
        cleanup_complete: true,
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

fn apply_conversation_migration(transaction: &Transaction<'_>, version: i64) -> io::Result<()> {
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
        9 => transaction.execute_batch(V9_SCHEMA).map_err(sqlite_error)?,
        10 => transaction
            .execute_batch(V10_SCHEMA)
            .map_err(sqlite_error)?,
        _ => {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "conversation migration chain has a gap",
            ))
        }
    }
    Ok(())
}

fn apply_git_worktree_migration(transaction: &Transaction<'_>, version: i64) -> io::Result<()> {
    match version {
        1 => transaction
            .execute_batch(GIT_V1_SCHEMA)
            .map_err(sqlite_error)?,
        2 => transaction
            .execute_batch(GIT_V2_SCHEMA)
            .map_err(sqlite_error)?,
        3 => {
            add_column(
                transaction,
                "code_checkpoints",
                "capture_mode",
                "TEXT NOT NULL DEFAULT 'whole_tree'",
            )?;
            transaction
                .execute_batch(GIT_V3_SCHEMA)
                .map_err(sqlite_error)?;
        }
        4 => transaction
            .execute_batch(GIT_V4_SCHEMA)
            .map_err(sqlite_error)?,
        5 => transaction
            .execute_batch(GIT_V5_SCHEMA)
            .map_err(sqlite_error)?,
        _ => {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "Git worktree migration chain has a gap",
            ))
        }
    }
    Ok(())
}

fn apply_worker_migration(transaction: &Transaction<'_>, version: i64) -> io::Result<()> {
    match version {
        1 => transaction
            .execute_batch(WORKER_V1_SCHEMA)
            .map_err(sqlite_error)?,
        2 => {
            add_column(
                transaction,
                "workers",
                "build_id",
                "TEXT NOT NULL DEFAULT ''",
            )?;
            add_column(
                transaction,
                "workers",
                "plan_task_id",
                "TEXT NOT NULL DEFAULT ''",
            )?;
            add_column(
                transaction,
                "workers",
                "candidate_index",
                "INTEGER NOT NULL DEFAULT -1",
            )?;
            transaction
                .execute_batch(WORKER_V2_SCHEMA)
                .map_err(sqlite_error)?;
        }
        _ => {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "worker migration chain has a gap",
            ))
        }
    }
    Ok(())
}

fn apply_single_version(
    transaction: &Transaction<'_>,
    version: i64,
    schema: &str,
) -> io::Result<()> {
    if version != 1 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "single-version migration chain has a gap",
        ));
    }
    transaction.execute_batch(schema).map_err(sqlite_error)
}

fn apply_audit_migration(transaction: &Transaction<'_>, version: i64) -> io::Result<()> {
    apply_single_version(transaction, version, AUDIT_V1_SCHEMA)
}

fn apply_extensions_migration(transaction: &Transaction<'_>, version: i64) -> io::Result<()> {
    apply_single_version(transaction, version, EXTENSIONS_V1_SCHEMA)
}

fn apply_goals_migration(transaction: &Transaction<'_>, version: i64) -> io::Result<()> {
    apply_single_version(transaction, version, GOALS_V1_SCHEMA)
}

fn apply_mcp_migration(transaction: &Transaction<'_>, version: i64) -> io::Result<()> {
    apply_single_version(transaction, version, MCP_V1_SCHEMA)
}

fn apply_plan_builds_migration(transaction: &Transaction<'_>, version: i64) -> io::Result<()> {
    apply_single_version(transaction, version, PLAN_BUILDS_V1_SCHEMA)
}

fn apply_preview_migration(transaction: &Transaction<'_>, version: i64) -> io::Result<()> {
    apply_single_version(transaction, version, PREVIEW_V1_SCHEMA)
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

fn validate_source(path: &Path, target: i64) -> io::Result<()> {
    let metadata = fs::symlink_metadata(path)?;
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid source database",
        ));
    }
    let (version, integrity) = inspect_database(path)?;
    validate_version(version, target)?;
    if integrity != "ok" {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "source database is corrupt",
        ));
    }
    Ok(())
}

fn validate_version(version: i64, target: i64) -> io::Result<()> {
    if !(0..=target).contains(&version) {
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

fn validate_owned_database(directory: &Path, database: &Path) -> io::Result<bool> {
    let metadata = match fs::symlink_metadata(database) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(false),
        Err(error) => return Err(error),
    };
    if !metadata.file_type().is_file() || metadata.file_type().is_symlink() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "owned database must be a regular non-symlink file",
        ));
    }
    let canonical_directory = fs::canonicalize(directory)?;
    let canonical_database = fs::canonicalize(database)?;
    if !canonical_database.starts_with(&canonical_directory) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "owned database escapes its data directory",
        ));
    }
    Ok(true)
}

fn create_backup(
    destination: &Path,
    database: &Path,
    version: i64,
    target: i64,
) -> io::Result<PathBuf> {
    let backups = destination.join("backups");
    secure_owned_directory(destination, &backups)?;
    let backup = backups.join(format!(
        "{}.pre-v{version}-to-v{target}-{}.bak",
        database
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("database.db"),
        timestamp()
    ));
    copy_sqlite(database, &backup)?;
    secure_file(&backup)?;
    sync_file(&backup)?;
    sync_directory(&backups)?;
    migration_test_pause(
        "backup_fsync",
        database.file_name().and_then(|name| name.to_str()),
    );
    Ok(backup)
}

fn latest_valid_backup(destination: &Path, plan: MigrationPlan) -> io::Result<Option<PathBuf>> {
    let backups = destination.join("backups");
    if !backups.exists() {
        return Ok(None);
    }
    validate_owned_directory_within(destination, &backups)?;
    let mut candidates = fs::read_dir(backups)?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| {
            path.file_name()
                .and_then(|name| name.to_str())
                .is_some_and(|name| {
                    name.starts_with(&format!("{}.pre-v", plan.file)) && name.ends_with(".bak")
                })
        })
        .collect::<Vec<_>>();
    candidates.sort_by_key(|path| std::cmp::Reverse(backup_timestamp(path)));
    for candidate in candidates {
        if inspect_database(&candidate)
            .is_ok_and(|(version, integrity)| version <= plan.target && integrity == "ok")
        {
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

fn secure_owned_directory(owner: &Path, path: &Path) -> io::Result<()> {
    validate_owned_directory(owner)?;
    match fs::symlink_metadata(path) {
        Ok(metadata) => {
            if metadata.file_type().is_symlink() || !metadata.is_dir() {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidInput,
                    "owned subdirectory must be a non-symlink directory",
                ));
            }
        }
        Err(error) if error.kind() == io::ErrorKind::NotFound => fs::create_dir(path)?,
        Err(error) => return Err(error),
    }
    validate_owned_directory_within(owner, path)?;
    fs::set_permissions(path, fs::Permissions::from_mode(0o700))
}

fn validate_owned_directory_within(owner: &Path, path: &Path) -> io::Result<()> {
    let metadata = fs::symlink_metadata(path)?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "owned subdirectory must be a non-symlink directory",
        ));
    }
    let canonical_owner = fs::canonicalize(owner)?;
    let canonical_path = fs::canonicalize(path)?;
    if !canonical_path.starts_with(&canonical_owner) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "owned subdirectory escapes its data directory",
        ));
    }
    Ok(())
}

fn secure_file(path: &Path) -> io::Result<()> {
    let metadata = fs::symlink_metadata(path)?;
    if !metadata.file_type().is_file() || metadata.file_type().is_symlink() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "database artifact must be a regular non-symlink file",
        ));
    }
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

const V9_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS projects (
  project_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  pinned INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS project_roots (
  project_id TEXT NOT NULL,
  root_id TEXT NOT NULL,
  path TEXT NOT NULL,
  is_primary INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (project_id, root_id),
  UNIQUE (project_id, path),
  FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS project_sessions (
  project_id TEXT NOT NULL,
  session_id TEXT PRIMARY KEY,
  FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
  FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS project_sessions_project
ON project_sessions(project_id, session_id);
"#;

const V10_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS source_attachments (
  attachment_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  path TEXT NOT NULL,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ready',
  error TEXT,
  attached_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  PRIMARY KEY (session_id, attachment_id),
  UNIQUE (session_id, path),
  FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS source_attachments_session
ON source_attachments(session_id, attached_at, attachment_id);
"#;

const GIT_V1_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS git_worktrees (
  session_id TEXT PRIMARY KEY, source_root TEXT NOT NULL, git_common_dir TEXT NOT NULL,
  source_branch TEXT NOT NULL, base_commit TEXT NOT NULL, worktree_path TEXT NOT NULL UNIQUE,
  session_branch TEXT NOT NULL, source_dirty INTEGER NOT NULL, state TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
"#;

const GIT_V2_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS code_checkpoints (
  checkpoint_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, before_tree TEXT NOT NULL,
  after_tree TEXT NOT NULL DEFAULT '', before_message_count INTEGER NOT NULL,
  after_message_count INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (session_id) REFERENCES git_worktrees(session_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_checkpoint_per_session
ON code_checkpoints(session_id) WHERE state = 'pending';
"#;

const GIT_V3_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS checkpoint_files (
  checkpoint_id TEXT NOT NULL, path TEXT NOT NULL, before_blob TEXT NOT NULL DEFAULT '',
  after_blob TEXT NOT NULL DEFAULT '', before_mode INTEGER NOT NULL DEFAULT 0,
  after_mode INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (checkpoint_id, path),
  FOREIGN KEY (checkpoint_id) REFERENCES code_checkpoints(checkpoint_id) ON DELETE CASCADE
);
"#;

const GIT_V4_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS checkpoint_restores (
  operation_id TEXT PRIMARY KEY, checkpoint_id TEXT NOT NULL, session_id TEXT NOT NULL UNIQUE,
  scope TEXT NOT NULL, state TEXT NOT NULL, message_count INTEGER NOT NULL,
  code_before_tree TEXT NOT NULL DEFAULT '', code_after_tree TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (session_id) REFERENCES git_worktrees(session_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS checkpoint_restore_history (
  operation_id TEXT NOT NULL, checkpoint_id TEXT NOT NULL, position INTEGER NOT NULL,
  PRIMARY KEY (operation_id, checkpoint_id), UNIQUE (operation_id, position),
  FOREIGN KEY (operation_id) REFERENCES checkpoint_restores(operation_id) ON DELETE CASCADE
);
"#;

const GIT_V5_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS plain_workspaces (
  session_id TEXT PRIMARY KEY, workspace_path TEXT NOT NULL,
  FOREIGN KEY (session_id) REFERENCES git_worktrees(session_id) ON DELETE CASCADE
);
"#;

const WORKER_V1_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS workers (
  worker_id TEXT PRIMARY KEY, parent_session_id TEXT NOT NULL,
  child_session_id TEXT NOT NULL UNIQUE, task TEXT NOT NULL, ownership TEXT NOT NULL,
  dependencies TEXT NOT NULL, model TEXT NOT NULL, state TEXT NOT NULL,
  worker_kind TEXT NOT NULL, protocol_version TEXT NOT NULL, capabilities TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '', commit_hash TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS workers_parent_created
ON workers(parent_session_id, created_at, worker_id);
"#;

const WORKER_V2_SCHEMA: &str = r#"
CREATE INDEX IF NOT EXISTS workers_build
ON workers(build_id, plan_task_id, candidate_index);
"#;

const AUDIT_V1_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, domain TEXT NOT NULL,
  action TEXT NOT NULL, actor TEXT NOT NULL, subject TEXT NOT NULL, payload TEXT NOT NULL,
  prev_hash TEXT NOT NULL, hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_domain_seq ON events(domain, seq);
"#;

const EXTENSIONS_V1_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS extensions (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, version TEXT NOT NULL,
  publisher TEXT NOT NULL, requested_permissions TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1, manifest_hash TEXT NOT NULL, manifest TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"#;

const GOALS_V1_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS goals (
  goal_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, objective TEXT NOT NULL,
  requirements TEXT NOT NULL, continuation_prompt TEXT NOT NULL, token_budget INTEGER,
  time_budget_seconds INTEGER, state TEXT NOT NULL, tokens_used INTEGER NOT NULL,
  continuation_count INTEGER NOT NULL, continuation_running INTEGER NOT NULL,
  baseline_message_count INTEGER NOT NULL, continuation_turn_id TEXT NOT NULL,
  turn_started_at TEXT NOT NULL, evidence TEXT NOT NULL, audit_summary TEXT NOT NULL,
  requirement_evidence TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  version INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS goals_session_created ON goals(session_id, created_at, goal_id);
"#;

const MCP_V1_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS connections (
  session_id TEXT NOT NULL, name TEXT NOT NULL, transport TEXT NOT NULL,
  definition TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, connected_at REAL NOT NULL,
  PRIMARY KEY (session_id, name)
);
CREATE INDEX IF NOT EXISTS connections_enabled ON connections(enabled, session_id);
"#;

const PLAN_BUILDS_V1_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS plan_builds (
  build_id TEXT PRIMARY KEY, parent_session_id TEXT NOT NULL, plan_id TEXT NOT NULL,
  tasks TEXT NOT NULL, state TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS plan_builds_parent_created
ON plan_builds(parent_session_id, created_at, build_id);
"#;

const PREVIEW_V1_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, kind TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS evidence_session ON evidence(session_id, id);
"#;

#[cfg(test)]
mod tests {
    use super::{
        apply_conversation_migration, apply_git_worktree_migration, apply_worker_migration,
        migrate_conversation_snapshot, migrate_data_directory_snapshot,
        migrate_git_worktree_snapshot, migrate_owned_database, migrate_worker_snapshot,
        prepare_owned_data_directory, recover_conversation_snapshot, ALL_PLANS, CONVERSATION_PLAN,
        CONVERSATION_SCHEMA_VERSION,
    };
    use rusqlite::Connection;
    use std::fs;
    use std::os::unix::fs::symlink;
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
            apply_conversation_migration(&transaction, migration).expect("migration fixture");
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
            CONVERSATION_SCHEMA_VERSION
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
            CONVERSATION_SCHEMA_VERSION
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
                CONVERSATION_SCHEMA_VERSION
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
            11
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

    #[test]
    fn git_worktree_corpus_migrates_v0_through_v4_and_preserves_records() {
        let root = directory();
        for version in 0_i64..=4 {
            let source = root.join(format!("git-v{version}.db"));
            let destination = root.join(format!("git-cutover-v{version}"));
            let mut connection = Connection::open(&source).expect("source");
            let transaction = connection.transaction().expect("transaction");
            for migration in 1..=version.max(1) {
                apply_git_worktree_migration(&transaction, migration).expect("fixture migration");
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
                    "INSERT INTO git_worktrees (
                       session_id, source_root, git_common_dir, source_branch, base_commit,
                       worktree_path, session_branch, source_dirty, state
                     ) VALUES (?1, '/source', '/source/.git', 'main', ?2, ?3,
                               'codinal/test', 0, 'active')",
                    rusqlite::params![
                        format!("git-v{version}"),
                        "a".repeat(40),
                        format!("/worktree-{version}")
                    ],
                )
                .expect("worktree");
            if version >= 2 {
                connection
                    .execute(
                        "INSERT INTO code_checkpoints (
                           checkpoint_id, session_id, before_tree, before_message_count, state
                         ) VALUES (?1, ?2, ?3, 0, 'completed')",
                        rusqlite::params![
                            format!("checkpoint-{version}"),
                            format!("git-v{version}"),
                            "b".repeat(40)
                        ],
                    )
                    .expect("checkpoint");
            }
            drop(connection);

            let report = migrate_git_worktree_snapshot(&source, &destination).expect("migration");
            assert_eq!((report.from_version, report.to_version), (version, 5));
            let migrated =
                Connection::open(destination.join("git-worktrees.db")).expect("migrated");
            assert_eq!(
                migrated
                    .query_row("SELECT base_commit FROM git_worktrees", [], |row| {
                        row.get::<_, String>(0)
                    })
                    .expect("retained worktree"),
                "a".repeat(40)
            );
            if version >= 2 {
                assert_eq!(
                    migrated
                        .query_row("SELECT capture_mode FROM code_checkpoints", [], |row| {
                            row.get::<_, String>(0)
                        })
                        .expect("capture mode"),
                    "whole_tree"
                );
            }
        }
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn worker_v1_migration_adds_comparison_metadata_without_losing_record() {
        let root = directory();
        let source = root.join("workers-v1.db");
        let destination = root.join("workers-cutover");
        let mut connection = Connection::open(&source).expect("source");
        let transaction = connection.transaction().expect("transaction");
        apply_worker_migration(&transaction, 1).expect("v1 schema");
        transaction
            .pragma_update(None, "user_version", 1)
            .expect("version");
        transaction.commit().expect("commit");
        connection
            .execute(
                "INSERT INTO workers (
                   worker_id, parent_session_id, child_session_id, task, ownership,
                   dependencies, model, state, worker_kind, protocol_version, capabilities
                 ) VALUES ('worker-1', 'parent-1', 'child-1', 'migrate', '[]', '[]',
                           'ollama:qwen3', 'queued', 'implementation', '1', '[]')",
                [],
            )
            .expect("worker");
        drop(connection);

        let report = migrate_worker_snapshot(&source, &destination).expect("migration");
        assert_eq!((report.from_version, report.to_version), (1, 2));
        let migrated = Connection::open(destination.join("workers.db")).expect("migrated");
        let metadata = migrated
            .query_row(
                "SELECT build_id, plan_task_id, candidate_index FROM workers",
                [],
                |row| {
                    Ok((
                        row.get::<_, String>(0)?,
                        row.get::<_, String>(1)?,
                        row.get::<_, i64>(2)?,
                    ))
                },
            )
            .expect("metadata");
        assert_eq!(metadata, (String::new(), String::new(), -1));
        fs::remove_dir_all(root).expect("cleanup");
    }

    fn create_complete_data_directory(path: &Path) {
        fs::create_dir(path).expect("source directory");
        for plan in ALL_PLANS {
            let mut connection = Connection::open(path.join(plan.file)).expect("source database");
            let transaction = connection.transaction().expect("transaction");
            for version in 1..=plan.target {
                (plan.apply)(&transaction, version).expect("fixture migration");
                transaction
                    .pragma_update(None, "user_version", version)
                    .expect("fixture version");
            }
            transaction.commit().expect("fixture commit");
        }
    }

    #[test]
    fn owned_directory_preparation_is_reentrant_and_preserves_records() {
        let root = directory();
        let first = prepare_owned_data_directory(&root).expect("initialize");
        assert_eq!(first.len(), ALL_PLANS.len());
        let database = Connection::open(root.join("codinal.db")).expect("conversation database");
        database
            .execute(
                "INSERT INTO sessions (session_id, workspace, model, mode, title, agent)
                 VALUES ('session-1', '/workspace', 'model', 'code', 'Preserved', 'code')",
                [],
            )
            .expect("session");
        drop(database);

        let second = prepare_owned_data_directory(&root).expect("prepare again");
        assert_eq!(second.len(), ALL_PLANS.len());
        let database = Connection::open(root.join("codinal.db")).expect("conversation database");
        let title: String = database
            .query_row(
                "SELECT title FROM sessions WHERE session_id = 'session-1'",
                [],
                |row| row.get(0),
            )
            .expect("preserved session");
        assert_eq!(title, "Preserved");
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn owned_migration_restarts_after_journal_boundaries_without_duplicate_history() {
        let root = directory();
        create_v1(&root.join("codinal.db"));
        let mut journal = crate::migration_journal::begin(
            &root,
            ALL_PLANS.iter().map(|plan| (plan.file, plan.target)),
        )
        .expect("journal");
        crate::migration_journal::mark_database_started(&root, &mut journal, "codinal.db", 1)
            .expect("started boundary");
        drop(journal);

        let mut resumed = crate::migration_journal::read(&root)
            .expect("journal read")
            .expect("running journal");
        let report =
            migrate_owned_database(&root, None, true, CONVERSATION_PLAN).expect("database commit");
        crate::migration_journal::mark_database_committed(
            &root,
            &mut resumed,
            "codinal.db",
            report
                .backup
                .as_ref()
                .map(|path| crate::migration_journal::sha256_file(path).expect("backup hash")),
        )
        .expect("committed boundary");
        drop(resumed);

        let reports = prepare_owned_data_directory(&root).expect("restart reconciliation");
        assert_eq!(reports.len(), ALL_PLANS.len());
        let journal = crate::migration_journal::read(&root)
            .expect("journal read")
            .expect("complete journal");
        assert_eq!(journal.status, "complete");
        assert!(journal.commit_marker);
        let database = Connection::open(root.join("codinal.db")).expect("database");
        assert_eq!(
            database
                .query_row(
                    "SELECT COUNT(*) FROM sessions WHERE session_id = 'retained-v1'",
                    [],
                    |row| row.get::<_, i64>(0),
                )
                .expect("retained history"),
            1
        );
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn owned_directory_preparation_rejects_database_symlinks() {
        let root = directory();
        let data = root.join("data");
        fs::create_dir(&data).expect("data directory");
        let external = root.join("external.db");
        fs::write(&external, b"external data").expect("external database");
        symlink(&external, data.join("codinal.db")).expect("database symlink");

        let error = prepare_owned_data_directory(&data).expect_err("reject symlink");
        assert_eq!(error.kind(), std::io::ErrorKind::InvalidInput);
        assert_eq!(
            fs::read(&external).expect("external data"),
            b"external data"
        );
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn owned_directory_preparation_rejects_backup_directory_symlink() {
        let root = directory();
        let data = root.join("data");
        fs::create_dir(&data).expect("data directory");
        create_v1(&data.join("codinal.db"));
        let external = root.join("external-backups");
        fs::create_dir(&external).expect("external backup directory");
        symlink(&external, data.join("backups")).expect("backup symlink");

        let error = prepare_owned_data_directory(&data).expect_err("reject backup symlink");
        assert_eq!(error.kind(), std::io::ErrorKind::InvalidInput);
        assert_eq!(
            fs::read_dir(&external).expect("external backups").count(),
            0
        );
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn whole_data_directory_cutover_publishes_only_after_all_nine_databases_verify() {
        let root = directory();
        let source = root.join("source");
        let destination = root.join("cutover");
        create_complete_data_directory(&source);
        let report = migrate_data_directory_snapshot(&source, &destination).expect("cutover");
        assert_eq!(report.databases.len(), 9);
        assert!(report.publication_durable);
        assert!(crate::inspect_v1_data_dir(&destination)
            .expect("inventory")
            .is_empty());
        assert!(report
            .databases
            .iter()
            .all(|database| database.backup.is_none()));
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn whole_data_directory_cutover_is_atomic_when_one_database_is_unsupported() {
        let root = directory();
        let source = root.join("source");
        let destination = root.join("cutover");
        create_complete_data_directory(&source);
        let audit = Connection::open(source.join("audit.db")).expect("audit");
        audit
            .pragma_update(None, "user_version", 99)
            .expect("future version");
        drop(audit);
        assert!(migrate_data_directory_snapshot(&source, &destination).is_err());
        assert!(!destination.exists());
        assert_eq!(
            fs::read_dir(&root)
                .expect("root")
                .filter_map(Result::ok)
                .filter(|entry| entry.file_name().to_string_lossy().contains(".cutover-"))
                .count(),
            0
        );
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn whole_data_directory_cutover_rejects_a_destination_below_source() {
        let root = directory();
        let source = root.join("source");
        create_complete_data_directory(&source);
        let destination = source.join("cutover");
        assert!(migrate_data_directory_snapshot(&source, &destination).is_err());
        assert!(!destination.exists());
        assert_eq!(fs::read_dir(&source).expect("source inventory").count(), 9);
        fs::remove_dir_all(root).expect("cleanup");
    }
}
