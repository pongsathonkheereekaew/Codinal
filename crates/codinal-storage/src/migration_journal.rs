//! Durable directory-wide migration journal.
//!
//! SQLite transactions protect each database. This journal records the
//! cross-database publication protocol so a crash cannot be mistaken for a
//! fully reconciled directory.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::unix::fs::MetadataExt;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

pub const MIGRATION_JOURNAL_FILE: &str = ".codinal-migration-journal.json";
const JOURNAL_VERSION: u32 = 1;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MigrationJournal {
    pub journal_version: u32,
    pub operation_id: String,
    pub directory_identity: String,
    pub status: String,
    pub databases: Vec<MigrationJournalDatabase>,
    pub commit_marker: bool,
    pub reconciliation: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MigrationJournalDatabase {
    pub file: String,
    pub source_version: i64,
    pub target_version: i64,
    pub backup_checksum: Option<String>,
    pub stage: String,
}

pub fn begin(
    data_dir: &Path,
    databases: impl IntoIterator<Item = (&'static str, i64)>,
) -> io::Result<MigrationJournal> {
    validate_directory(data_dir)?;
    if let Some(existing) = read(data_dir)? {
        if existing.status == "running" {
            return Ok(existing);
        }
        if existing.status == "failed" {
            return Err(io::Error::new(
                io::ErrorKind::PermissionDenied,
                "migration journal is failed; diagnostic read-only recovery is required",
            ));
        }
    }
    let entries = databases
        .into_iter()
        .map(|(file, target_version)| MigrationJournalDatabase {
            file: file.to_owned(),
            source_version: -1,
            target_version,
            backup_checksum: None,
            stage: "planned".to_owned(),
        })
        .collect();
    let journal = MigrationJournal {
        journal_version: JOURNAL_VERSION,
        operation_id: format!("{}-{}", std::process::id(), timestamp()),
        directory_identity: directory_identity(data_dir)?,
        status: "running".to_owned(),
        databases: entries,
        commit_marker: false,
        reconciliation: "pending".to_owned(),
    };
    write(data_dir, &journal)?;
    Ok(journal)
}

pub fn mark_database_started(
    data_dir: &Path,
    journal: &mut MigrationJournal,
    file: &str,
    source_version: i64,
) -> io::Result<()> {
    let entry = entry_mut(journal, file)?;
    entry.source_version = source_version;
    entry.stage = "started".to_owned();
    write(data_dir, journal)
}

pub fn mark_database_committed(
    data_dir: &Path,
    journal: &mut MigrationJournal,
    file: &str,
    backup_checksum: Option<String>,
) -> io::Result<()> {
    let entry = entry_mut(journal, file)?;
    entry.backup_checksum = backup_checksum;
    entry.stage = "committed".to_owned();
    write(data_dir, journal)
}

pub fn mark_failed(data_dir: &Path, journal: &mut MigrationJournal) -> io::Result<()> {
    journal.status = "failed".to_owned();
    journal.reconciliation = "diagnostic_read_only_required".to_owned();
    write(data_dir, journal)
}

pub fn mark_complete(data_dir: &Path, journal: &mut MigrationJournal) -> io::Result<()> {
    journal.status = "complete".to_owned();
    journal.commit_marker = true;
    journal.reconciliation = "verified".to_owned();
    write(data_dir, journal)
}

pub fn read(data_dir: &Path) -> io::Result<Option<MigrationJournal>> {
    validate_directory(data_dir)?;
    let path = data_dir.join(MIGRATION_JOURNAL_FILE);
    let mut file = match File::open(path) {
        Ok(file) => file,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error),
    };
    let mut encoded = String::new();
    file.read_to_string(&mut encoded)?;
    let journal: MigrationJournal = serde_json::from_str(&encoded).map_err(json_error)?;
    if journal.journal_version != JOURNAL_VERSION
        || journal.directory_identity != directory_identity(data_dir)?
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "migration journal identity or version mismatch",
        ));
    }
    Ok(Some(journal))
}

pub fn sha256_file(path: &Path) -> io::Result<String> {
    let mut file = File::open(path)?;
    let mut digest = Sha256::new();
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let read = file.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        digest.update(&buffer[..read]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

fn write(data_dir: &Path, journal: &MigrationJournal) -> io::Result<()> {
    remove_stale_staging_files(data_dir)?;
    let path = data_dir.join(MIGRATION_JOURNAL_FILE);
    let staging = data_dir.join(format!(
        ".{MIGRATION_JOURNAL_FILE}.{}-{}",
        std::process::id(),
        timestamp()
    ));
    let encoded = serde_json::to_vec_pretty(journal).map_err(json_error)?;
    {
        let mut file = OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&staging)?;
        file.write_all(&encoded)?;
        file.write_all(b"\n")?;
        file.sync_all()?;
    }
    fs::rename(&staging, &path)?;
    sync_directory(data_dir)
}

fn remove_stale_staging_files(data_dir: &Path) -> io::Result<()> {
    let prefix = format!(".{MIGRATION_JOURNAL_FILE}.");
    for entry in fs::read_dir(data_dir)? {
        let entry = entry?;
        if !entry.file_name().to_string_lossy().starts_with(&prefix) {
            continue;
        }
        let metadata = fs::symlink_metadata(entry.path())?;
        if metadata.file_type().is_symlink() || !metadata.is_file() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "migration journal staging path is unsafe",
            ));
        }
        fs::remove_file(entry.path())?;
    }
    Ok(())
}

fn entry_mut<'a>(
    journal: &'a mut MigrationJournal,
    file: &str,
) -> io::Result<&'a mut MigrationJournalDatabase> {
    journal
        .databases
        .iter_mut()
        .find(|entry| entry.file == file)
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "unknown migration database"))
}

fn validate_directory(path: &Path) -> io::Result<()> {
    let metadata = fs::symlink_metadata(path)?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "migration journal directory must be a non-symlink directory",
        ));
    }
    Ok(())
}

fn directory_identity(path: &Path) -> io::Result<String> {
    let metadata = fs::metadata(path)?;
    Ok(format!("{}:{}", metadata.dev(), metadata.ino()))
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

fn json_error(error: serde_json::Error) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, error)
}

#[cfg(test)]
mod tests {
    use super::{
        begin, mark_complete, mark_database_committed, mark_database_started, mark_failed, read,
        sha256_file,
    };
    use std::fs;
    use std::sync::atomic::{AtomicU64, Ordering};

    static NEXT_DIR: AtomicU64 = AtomicU64::new(0);

    #[test]
    fn journal_is_durable_and_records_backup_checksum() {
        let path = std::env::temp_dir().join(format!(
            "codinal-migration-journal-test-{}-{}",
            std::process::id(),
            NEXT_DIR.fetch_add(1, Ordering::Relaxed)
        ));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir(&path).expect("directory");
        let backup = path.join("backup.db");
        fs::write(&backup, b"backup").expect("backup");
        let mut journal = begin(&path, [("codinal.db", 8)]).expect("begin");
        mark_database_started(&path, &mut journal, "codinal.db", 7).expect("started");
        mark_database_committed(
            &path,
            &mut journal,
            "codinal.db",
            Some(sha256_file(&backup).expect("checksum")),
        )
        .expect("committed");
        mark_complete(&path, &mut journal).expect("complete");
        let persisted = read(&path).expect("read").expect("journal");
        assert!(persisted.commit_marker);
        assert_eq!(persisted.reconciliation, "verified");
        assert!(persisted.databases[0].backup_checksum.is_some());
        let stale = path.join("..codinal-migration-journal.json.stale");
        fs::write(&stale, b"stale staging").expect("stale staging");
        begin(&path, [("codinal.db", 8)]).expect("new operation");
        assert!(!stale.exists());
        fs::remove_dir_all(path).expect("cleanup");
    }

    #[test]
    fn failed_journal_requires_diagnostic_recovery_before_writer_retry() {
        let path = std::env::temp_dir().join(format!(
            "codinal-migration-journal-failed-{}-{}",
            std::process::id(),
            NEXT_DIR.fetch_add(1, Ordering::Relaxed)
        ));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir(&path).expect("directory");
        let mut journal = begin(&path, [("codinal.db", 8)]).expect("begin");
        mark_failed(&path, &mut journal).expect("mark failed");
        let error = begin(&path, [("codinal.db", 8)]).expect_err("failed journal was retried");
        assert_eq!(error.kind(), std::io::ErrorKind::PermissionDenied);
        assert_eq!(
            read(&path).expect("read").expect("journal").status,
            "failed"
        );
        fs::remove_dir_all(path).expect("cleanup");
    }
}
