//! Read-only compatibility inspection for pre-cutover Codinal data.
//!
//! This crate intentionally has no write API. The Rust runtime must prove it
//! can read the Python-owned data directory before a future transactional
//! ownership cutover may add migration or repository code.

use rusqlite::{Connection, OpenFlags};
use serde::Deserialize;
use std::collections::BTreeSet;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

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
        io::Error::new(io::ErrorKind::InvalidData, format!("invalid storage fixture: {error}"))
    })?;
    if fixture.fixture_version != 1 || fixture.contract != "codinal.sqlite.v1" {
        return Err(io::Error::new(io::ErrorKind::InvalidData, "unsupported storage fixture"));
    }

    let mismatches = fixture
        .databases
        .iter()
        .map(|expected| inspect_database(data_dir, expected))
        .filter_map(Result::err)
        .collect();
    Ok(mismatches)
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
    let connection = Connection::open_with_flags(&path, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|_| StorageMismatch {
            file: expected.file.clone(),
            detail: "database cannot be opened read-only".to_owned(),
        })?;
    let actual_version: u32 = connection
        .query_row("PRAGMA user_version", [], |row| row.get(0))
        .map_err(|_| StorageMismatch {
            file: expected.file.clone(),
            detail: "database user_version cannot be read".to_owned(),
        })?;
    if actual_version != expected.user_version {
        return Err(StorageMismatch {
            file: expected.file.clone(),
            detail: format!("user_version is {actual_version}, expected {}", expected.user_version),
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

fn safe_database_path(data_dir: &Path, file: &str) -> Result<PathBuf, String> {
    let candidate = Path::new(file);
    if candidate.components().count() != 1 || candidate.extension().is_none_or(|extension| extension != "db") {
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
    use super::{inspect_v1_data_dir, load_v1_fixture};
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
}
