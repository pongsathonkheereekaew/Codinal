//! Compatibility inspection and owner-scoped access for Codinal data.
//!
//! Read paths remain strictly read-only. The small write API below is reserved
//! for the Rust runtime after it has acquired the owner lock and completed the
//! transactional migration gate.

use rusqlite::{Connection, OpenFlags};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

mod migration;
pub mod migration_journal;
pub mod runtime_store;

pub use migration::{
    migrate_conversation_snapshot, migrate_data_directory_snapshot, migrate_git_worktree_snapshot,
    migrate_worker_snapshot, prepare_owned_data_directory, recover_conversation_snapshot,
    recover_git_worktree_snapshot, recover_worker_snapshot, ConversationMigrationReport,
    DataDirectoryMigrationReport, CONVERSATION_SCHEMA_VERSION, GIT_WORKTREE_SCHEMA_VERSION,
    WORKER_SCHEMA_VERSION,
};
pub use migration_journal::{MigrationJournal, MigrationJournalDatabase, MIGRATION_JOURNAL_FILE};
pub use runtime_store::{
    ApprovalRecord, BudgetReservationRecord, MutationJournalRecord, RuntimeCursor,
    RuntimeEventRecord, RuntimeEventReplay, RuntimeStore, TurnReceiptRecord, TurnRecord,
    RUNTIME_STORE_FILE, RUNTIME_STORE_SCHEMA_VERSION,
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
    pub project_id: Option<String>,
    pub project_name: Option<String>,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct ProjectRootSummary {
    pub root_id: String,
    pub path: String,
    pub primary: bool,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct ProjectSummary {
    pub project_id: String,
    pub name: String,
    pub roots: Vec<ProjectRootSummary>,
    pub pinned: bool,
    pub updated_at: String,
    pub task_count: u64,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct SourceAttachment {
    pub attachment_id: String,
    pub session_id: String,
    pub path: String,
    pub name: String,
    pub kind: String,
    pub status: String,
    pub error: Option<String>,
    pub attached_at: String,
    pub updated_at: String,
}

#[derive(Debug, Serialize, PartialEq, Eq)]
pub struct TurnReceipt {
    pub turn_id: String,
    pub session_id: String,
    pub outcome: serde_json::Value,
    pub message_count: i64,
    pub created_at: String,
}

/// Create a public conversation session after the Rust runtime has acquired
/// writer ownership of the data directory.
pub fn create_session(
    data_dir: &Path,
    session_id: &str,
    title: &str,
    workspace: &str,
    agent: &str,
    model: &str,
    mode: &str,
) -> io::Result<SessionSummary> {
    create_session_with_origin(
        data_dir, session_id, title, workspace, agent, model, mode, None, None, None,
    )
}

/// Create a public conversation session with optional typed UI origin metadata.
///
/// Origins are deliberately narrow until the control-plane contract grows more
/// origin types. This keeps side chats out of the primary Chats projection
/// without letting arbitrary caller-controlled labels become navigation state.
pub fn create_session_with_origin(
    data_dir: &Path,
    session_id: &str,
    title: &str,
    workspace: &str,
    agent: &str,
    model: &str,
    mode: &str,
    origin: Option<&str>,
    origin_label: Option<&str>,
    origin_session_id: Option<&str>,
) -> io::Result<SessionSummary> {
    if !valid_public_session_id(session_id) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid public session id",
        ));
    }
    let title = bounded_single_line(title, "session title", 160)?;
    let agent = bounded_single_line(agent, "session agent", 64)?;
    let model = bounded_single_line(model, "session model", 160)?;
    let mode = bounded_single_line(mode, "session mode", 64)?;
    let origin = origin
        .map(|value| bounded_single_line(value, "session origin", 64))
        .transpose()?;
    if origin.as_deref().is_some_and(|value| value != "side_chat") {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "unsupported session origin",
        ));
    }
    let origin_label = origin_label
        .map(|value| bounded_single_line(value, "session origin label", 160))
        .transpose()?;
    let origin_session_id = origin_session_id
        .map(|value| {
            if valid_public_session_id(value) {
                Ok(value.to_owned())
            } else {
                Err(io::Error::new(
                    io::ErrorKind::InvalidInput,
                    "invalid origin session id",
                ))
            }
        })
        .transpose()?;
    if origin.is_none() && (origin_label.is_some() || origin_session_id.is_some()) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "origin metadata requires a session origin",
        ));
    }
    let workspace = canonical_workspace(workspace)?;
    let mismatches = inspect_v1_data_dir(data_dir)?;
    if !mismatches.is_empty() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "data directory does not match v1 storage",
        ));
    }
    let mut connection = Connection::open_with_flags(
        data_dir.join("codinal.db"),
        OpenFlags::SQLITE_OPEN_READ_WRITE | OpenFlags::SQLITE_OPEN_NO_MUTEX,
    )
    .map_err(sqlite_error)?;
    connection
        .execute_batch(
            "PRAGMA foreign_keys = ON; PRAGMA journal_mode = DELETE; PRAGMA synchronous = FULL;",
        )
        .map_err(sqlite_error)?;
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(sqlite_error)?;
    transaction
        .execute(
            "INSERT INTO sessions
             (session_id, workspace, source_workspace, model, mode, title, agent,
              origin, origin_label, origin_session_id)
             VALUES (?1, ?2, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
            rusqlite::params![
                session_id,
                workspace,
                model,
                mode,
                title,
                agent,
                origin,
                origin_label,
                origin_session_id,
            ],
        )
        .map_err(|error| match error {
            rusqlite::Error::SqliteFailure(inner, _)
                if inner.code == rusqlite::ffi::ErrorCode::ConstraintViolation =>
            {
                io::Error::new(io::ErrorKind::AlreadyExists, "session already exists")
            }
            other => sqlite_error(other),
        })?;
    transaction
        .execute(
            "INSERT INTO workspaces (path) VALUES (?1)
             ON CONFLICT(path) DO UPDATE SET last_used = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')",
            [workspace.as_str()],
        )
        .map_err(sqlite_error)?;
    transaction.commit().map_err(sqlite_error)?;
    read_session_summaries(data_dir, Some(&workspace))?
        .into_iter()
        .find(|session| session.session_id == session_id)
        .ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "created session was not readable",
            )
        })
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
                sessions.origin, sessions.origin_label, sessions.origin_session_id,
                project_sessions.project_id, projects.name
         FROM sessions LEFT JOIN messages USING (session_id)
         LEFT JOIN project_sessions ON project_sessions.session_id = sessions.session_id
         LEFT JOIN projects ON projects.project_id = project_sessions.project_id
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
            project_id: row.get(13)?,
            project_name: row.get(14)?,
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

/// Apply the user-visible session metadata mutations as one database transaction.
/// The runtime deliberately keeps this narrow: it cannot mutate workspace files,
/// only the chat projection shown by the desktop shell.
pub fn update_session(
    data_dir: &Path,
    session_id: &str,
    title: Option<&str>,
    pinned: Option<bool>,
    archived: Option<bool>,
) -> io::Result<SessionSummary> {
    validate_public_session_id(session_id)?;
    let title = title
        .map(|value| bounded_single_line(value, "session title", 160))
        .transpose()?;
    if title.is_none() && pinned.is_none() && archived.is_none() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "session update is empty",
        ));
    }
    let mut connection = open_conversation_database_for_write(data_dir)?;
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(sqlite_error)?;
    let changed = transaction
        .execute(
            "UPDATE sessions
             SET title = COALESCE(?2, title),
                 pinned = COALESCE(?3, pinned),
                 archived = COALESCE(?4, archived),
                 updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
             WHERE session_id = ?1
               AND substr(session_id, 1, 2) != '__'
               AND COALESCE(origin, '') != 'worker'",
            rusqlite::params![session_id, title, pinned, archived],
        )
        .map_err(sqlite_error)?;
    if changed != 1 {
        return Err(io::Error::new(io::ErrorKind::NotFound, "session not found"));
    }
    transaction.commit().map_err(sqlite_error)?;
    read_session_summaries(data_dir, None)?
        .into_iter()
        .find(|session| session.session_id == session_id)
        .ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "updated session was not readable",
            )
        })
}

/// Delete only the chat record and its conversation-owned metadata. Workspace
/// folders and files are never touched by this operation.
pub fn delete_session(data_dir: &Path, session_id: &str) -> io::Result<()> {
    validate_public_session_id(session_id)?;
    let mut connection = open_conversation_database_for_write(data_dir)?;
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(sqlite_error)?;
    // These explicit deletes keep compatibility with older v1 fixtures that did
    // not declare foreign keys on the three navigation/source tables. The
    // remaining conversation-owned tables use ON DELETE CASCADE in the current
    // schema; the runtime store is a separate database and is intentionally not
    // mutated by this chat projection action.
    for table in ["project_sessions", "source_attachments", "messages"] {
        transaction
            .execute(
                &format!("DELETE FROM {table} WHERE session_id = ?1"),
                [session_id],
            )
            .map_err(sqlite_error)?;
    }
    let changed = transaction
        .execute(
            "DELETE FROM sessions
             WHERE session_id = ?1
               AND substr(session_id, 1, 2) != '__'
               AND COALESCE(origin, '') != 'worker'",
            [session_id],
        )
        .map_err(sqlite_error)?;
    if changed != 1 {
        return Err(io::Error::new(io::ErrorKind::NotFound, "session not found"));
    }
    transaction.commit().map_err(sqlite_error)
}

pub fn read_projects(data_dir: &Path) -> io::Result<Vec<ProjectSummary>> {
    let connection = open_conversation_database(data_dir)?;
    let mut statement = connection
        .prepare(
            "SELECT projects.project_id, projects.name, projects.pinned, projects.updated_at,
                    COUNT(DISTINCT CASE WHEN sessions.archived = 0 THEN sessions.session_id END)
             FROM projects
             LEFT JOIN project_sessions USING (project_id)
             LEFT JOIN sessions USING (session_id)
             GROUP BY projects.project_id
             ORDER BY projects.pinned DESC, projects.updated_at DESC, projects.project_id",
        )
        .map_err(sqlite_error)?;
    let rows = statement
        .query_map([], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, i64>(2)? != 0,
                row.get::<_, String>(3)?,
                row.get::<_, i64>(4)? as u64,
            ))
        })
        .map_err(sqlite_error)?;
    let projects = rows
        .collect::<rusqlite::Result<Vec<_>>>()
        .map_err(sqlite_error)?;
    projects
        .into_iter()
        .map(|(project_id, name, pinned, updated_at, task_count)| {
            let roots = read_project_roots(&connection, &project_id)?;
            Ok(ProjectSummary {
                project_id,
                name,
                roots,
                pinned,
                updated_at,
                task_count,
            })
        })
        .collect()
}

pub fn create_project(
    data_dir: &Path,
    project_id: &str,
    name: &str,
    roots: &[String],
) -> io::Result<ProjectSummary> {
    validate_project_id(project_id)?;
    let name = bounded_single_line(name, "project name", 160)?;
    let roots = validate_project_roots(roots)?;
    let mut connection = open_conversation_database_for_write(data_dir)?;
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(sqlite_error)?;
    transaction
        .execute(
            "INSERT INTO projects (project_id, name) VALUES (?1, ?2)",
            rusqlite::params![project_id, name],
        )
        .map_err(|error| match error {
            rusqlite::Error::SqliteFailure(inner, _)
                if inner.code == rusqlite::ffi::ErrorCode::ConstraintViolation =>
            {
                io::Error::new(io::ErrorKind::AlreadyExists, "project already exists")
            }
            other => sqlite_error(other),
        })?;
    insert_project_roots(&transaction, project_id, &roots)?;
    transaction.commit().map_err(sqlite_error)?;
    read_projects(data_dir)?
        .into_iter()
        .find(|project| project.project_id == project_id)
        .ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "created project was not readable",
            )
        })
}

pub fn replace_project(
    data_dir: &Path,
    project_id: &str,
    name: &str,
    roots: &[String],
) -> io::Result<ProjectSummary> {
    validate_project_id(project_id)?;
    let name = bounded_single_line(name, "project name", 160)?;
    let roots = validate_project_roots(roots)?;
    let mut connection = open_conversation_database_for_write(data_dir)?;
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(sqlite_error)?;
    let changed = transaction
        .execute(
            "UPDATE projects SET name = ?2, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
             WHERE project_id = ?1",
            rusqlite::params![project_id, name],
        )
        .map_err(sqlite_error)?;
    if changed != 1 {
        return Err(io::Error::new(io::ErrorKind::NotFound, "project not found"));
    }
    transaction
        .execute(
            "DELETE FROM project_roots WHERE project_id = ?1",
            [project_id],
        )
        .map_err(sqlite_error)?;
    insert_project_roots(&transaction, project_id, &roots)?;
    transaction.commit().map_err(sqlite_error)?;
    read_projects(data_dir)?
        .into_iter()
        .find(|project| project.project_id == project_id)
        .ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "updated project was not readable",
            )
        })
}

pub fn remove_project(data_dir: &Path, project_id: &str) -> io::Result<()> {
    validate_project_id(project_id)?;
    let connection = open_conversation_database_for_write(data_dir)?;
    let changed = connection
        .execute("DELETE FROM projects WHERE project_id = ?1", [project_id])
        .map_err(sqlite_error)?;
    if changed == 1 {
        Ok(())
    } else {
        Err(io::Error::new(io::ErrorKind::NotFound, "project not found"))
    }
}

pub fn set_project_pinned(data_dir: &Path, project_id: &str, pinned: bool) -> io::Result<()> {
    validate_project_id(project_id)?;
    let connection = open_conversation_database_for_write(data_dir)?;
    let changed = connection
        .execute(
            "UPDATE projects SET pinned = ?2, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
             WHERE project_id = ?1",
            rusqlite::params![project_id, pinned],
        )
        .map_err(sqlite_error)?;
    if changed == 1 {
        Ok(())
    } else {
        Err(io::Error::new(io::ErrorKind::NotFound, "project not found"))
    }
}

pub fn assign_session_to_project(
    data_dir: &Path,
    session_id: &str,
    project_id: &str,
) -> io::Result<()> {
    if !valid_public_session_id(session_id) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid public session id",
        ));
    }
    validate_project_id(project_id)?;
    let mut connection = open_conversation_database_for_write(data_dir)?;
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(sqlite_error)?;
    let exists = transaction
        .query_row(
            "SELECT EXISTS(SELECT 1 FROM sessions WHERE session_id = ?1 AND substr(session_id, 1, 2) != '__')
             AND EXISTS(SELECT 1 FROM projects WHERE project_id = ?2)",
            rusqlite::params![session_id, project_id],
            |row| row.get::<_, bool>(0),
        )
        .map_err(sqlite_error)?;
    if !exists {
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            "session or project not found",
        ));
    }
    transaction
        .execute(
            "INSERT INTO project_sessions (project_id, session_id) VALUES (?2, ?1)
             ON CONFLICT(session_id) DO UPDATE SET project_id = excluded.project_id",
            rusqlite::params![session_id, project_id],
        )
        .map_err(sqlite_error)?;
    transaction.commit().map_err(sqlite_error)
}

pub fn remove_session_from_project(
    data_dir: &Path,
    project_id: &str,
    session_id: &str,
) -> io::Result<()> {
    if !valid_public_session_id(session_id) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid public session id",
        ));
    }
    validate_project_id(project_id)?;
    let mut connection = open_conversation_database_for_write(data_dir)?;
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(sqlite_error)?;
    let changed = transaction
        .execute(
            "DELETE FROM project_sessions WHERE project_id = ?1 AND session_id = ?2",
            rusqlite::params![project_id, session_id],
        )
        .map_err(sqlite_error)?;
    if changed != 1 {
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            "session is not assigned to project",
        ));
    }
    transaction.commit().map_err(sqlite_error)
}

pub fn read_source_attachments(
    data_dir: &Path,
    session_id: &str,
) -> io::Result<Vec<SourceAttachment>> {
    validate_public_session_id(session_id)?;
    let connection = open_conversation_database(data_dir)?;
    let mut statement = connection
        .prepare(
            "SELECT source_attachments.attachment_id, source_attachments.session_id,
                    source_attachments.path, source_attachments.name, source_attachments.kind,
                    source_attachments.status, source_attachments.error,
                    source_attachments.attached_at, source_attachments.updated_at
             FROM source_attachments
             JOIN sessions USING (session_id)
             WHERE source_attachments.session_id = ?1
               AND substr(sessions.session_id, 1, 2) != '__'
               AND COALESCE(sessions.origin, '') != 'worker'
             ORDER BY source_attachments.attached_at, source_attachments.attachment_id
             LIMIT 100",
        )
        .map_err(sqlite_error)?;
    let rows = statement
        .query_map([session_id], |row| {
            Ok(SourceAttachment {
                attachment_id: row.get(0)?,
                session_id: row.get(1)?,
                path: row.get(2)?,
                name: row.get(3)?,
                kind: row.get(4)?,
                status: row.get(5)?,
                error: row.get(6)?,
                attached_at: row.get(7)?,
                updated_at: row.get(8)?,
            })
        })
        .map_err(sqlite_error)?;
    let mut sources = rows
        .collect::<rusqlite::Result<Vec<_>>>()
        .map_err(sqlite_error)?;
    for source in &mut sources {
        if source.status == "ready" {
            let (status, error) = source_path_state(Path::new(&source.path));
            source.status = status.to_owned();
            source.error = error;
        }
    }
    Ok(sources)
}

pub fn read_source_attachment(
    data_dir: &Path,
    session_id: &str,
    attachment_id: &str,
) -> io::Result<SourceAttachment> {
    validate_public_session_id(session_id)?;
    validate_source_attachment_id(attachment_id)?;
    read_source_attachments(data_dir, session_id)?
        .into_iter()
        .find(|source| source.attachment_id == attachment_id)
        .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "source attachment not found"))
}

pub fn attach_source_attachment(
    data_dir: &Path,
    session_id: &str,
    attachment_id: &str,
    path: &str,
    name: &str,
    kind: &str,
) -> io::Result<SourceAttachment> {
    validate_public_session_id(session_id)?;
    validate_source_attachment_id(attachment_id)?;
    let path = bounded_single_line(path, "source path", 4096)?;
    if !Path::new(&path).is_absolute() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "source path must be absolute",
        ));
    }
    let name = bounded_single_line(name, "source name", 512)?;
    let kind = bounded_single_line(kind, "source kind", 16)?;
    if !matches!(kind.as_str(), "file" | "folder") {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "source kind must be file or folder",
        ));
    }
    let mut connection = open_conversation_database_for_write(data_dir)?;
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(sqlite_error)?;
    let public_session = transaction
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
        .map_err(sqlite_error)?;
    if !public_session {
        return Err(io::Error::new(io::ErrorKind::NotFound, "session not found"));
    }
    transaction
        .execute(
            "INSERT INTO source_attachments
             (attachment_id, session_id, path, name, kind, status, error)
             VALUES (?1, ?2, ?3, ?4, ?5, 'ready', NULL)",
            rusqlite::params![attachment_id, session_id, path, name, kind],
        )
        .map_err(|error| match error {
            rusqlite::Error::SqliteFailure(inner, _)
                if inner.code == rusqlite::ffi::ErrorCode::ConstraintViolation =>
            {
                io::Error::new(io::ErrorKind::AlreadyExists, "source already attached")
            }
            other => sqlite_error(other),
        })?;
    transaction.commit().map_err(sqlite_error)?;
    read_source_attachment(data_dir, session_id, attachment_id)
}

pub fn retry_source_attachment(
    data_dir: &Path,
    session_id: &str,
    attachment_id: &str,
) -> io::Result<SourceAttachment> {
    validate_public_session_id(session_id)?;
    validate_source_attachment_id(attachment_id)?;
    let mut connection = open_conversation_database_for_write(data_dir)?;
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(sqlite_error)?;
    let path = transaction
        .query_row(
            "SELECT source_attachments.path
             FROM source_attachments JOIN sessions USING (session_id)
             WHERE source_attachments.session_id = ?1
               AND source_attachments.attachment_id = ?2
               AND substr(sessions.session_id, 1, 2) != '__'
               AND COALESCE(sessions.origin, '') != 'worker'",
            rusqlite::params![session_id, attachment_id],
            |row| row.get::<_, String>(0),
        )
        .map_err(|error| match error {
            rusqlite::Error::QueryReturnedNoRows => {
                io::Error::new(io::ErrorKind::NotFound, "source attachment not found")
            }
            other => sqlite_error(other),
        })?;
    let (status, error) = source_path_state(Path::new(&path));
    transaction
        .execute(
            "UPDATE source_attachments
             SET status = ?3, error = ?4,
                 updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
             WHERE session_id = ?1 AND attachment_id = ?2",
            rusqlite::params![session_id, attachment_id, status, error],
        )
        .map_err(sqlite_error)?;
    transaction.commit().map_err(sqlite_error)?;
    read_source_attachment(data_dir, session_id, attachment_id)
}

pub fn remove_source_attachment(
    data_dir: &Path,
    session_id: &str,
    attachment_id: &str,
) -> io::Result<()> {
    validate_public_session_id(session_id)?;
    validate_source_attachment_id(attachment_id)?;
    let connection = open_conversation_database_for_write(data_dir)?;
    let changed = connection
        .execute(
            "DELETE FROM source_attachments
             WHERE session_id = ?1 AND attachment_id = ?2",
            rusqlite::params![session_id, attachment_id],
        )
        .map_err(sqlite_error)?;
    if changed == 1 {
        Ok(())
    } else {
        Err(io::Error::new(
            io::ErrorKind::NotFound,
            "source attachment not found",
        ))
    }
}

fn read_project_roots(
    connection: &Connection,
    project_id: &str,
) -> io::Result<Vec<ProjectRootSummary>> {
    let mut statement = connection
        .prepare(
            "SELECT root_id, path, is_primary FROM project_roots
             WHERE project_id = ?1 ORDER BY is_primary DESC, root_id",
        )
        .map_err(sqlite_error)?;
    let rows = statement
        .query_map([project_id], |row| {
            Ok(ProjectRootSummary {
                root_id: row.get(0)?,
                path: row.get(1)?,
                primary: row.get(2)?,
            })
        })
        .map_err(sqlite_error)?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(sqlite_error)
}

fn insert_project_roots(
    transaction: &rusqlite::Transaction<'_>,
    project_id: &str,
    roots: &[String],
) -> io::Result<()> {
    for (index, path) in roots.iter().enumerate() {
        let root_id = format!("{project_id}-root-{}", index + 1);
        transaction
            .execute(
                "INSERT INTO project_roots (project_id, root_id, path, is_primary)
                 VALUES (?1, ?2, ?3, ?4)",
                rusqlite::params![project_id, root_id, path, index == 0],
            )
            .map_err(sqlite_error)?;
    }
    Ok(())
}

fn validate_project_id(project_id: &str) -> io::Result<()> {
    if valid_public_session_id(project_id) {
        Ok(())
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid project id",
        ))
    }
}

fn validate_project_roots(roots: &[String]) -> io::Result<Vec<String>> {
    let mut unique = BTreeSet::new();
    for root in roots {
        let root = bounded_single_line(root, "project root", 4096)?;
        if !Path::new(&root).is_absolute() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "project root must be an absolute path",
            ));
        }
        unique.insert(root);
    }
    Ok(unique.into_iter().collect())
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

pub fn read_session_turn_receipts(
    data_dir: &Path,
    session_id: &str,
) -> io::Result<Vec<TurnReceipt>> {
    if !valid_public_session_id(session_id) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid public session id",
        ));
    }
    let connection = open_conversation_database(data_dir)?;
    if !table_has_columns(
        &connection,
        "turn_receipts",
        &[
            "turn_id",
            "session_id",
            "outcome",
            "message_count",
            "created_at",
        ],
    )? {
        return Ok(Vec::new());
    }
    let mut statement = connection
        .prepare(
            "SELECT turn_receipts.turn_id, turn_receipts.session_id,
                    turn_receipts.outcome, turn_receipts.message_count,
                    turn_receipts.created_at
             FROM turn_receipts
             JOIN sessions USING (session_id)
             WHERE turn_receipts.session_id = ?1
               AND substr(sessions.session_id, 1, 2) != '__'
               AND COALESCE(sessions.origin, '') != 'worker'
             ORDER BY turn_receipts.created_at, turn_receipts.turn_id
             LIMIT 100",
        )
        .map_err(sqlite_error)?;
    let rows = statement
        .query_map([session_id], |row| {
            let outcome_text: String = row.get(2)?;
            let outcome = serde_json::from_str(&outcome_text).map_err(|error| {
                rusqlite::Error::FromSqlConversionFailure(
                    2,
                    rusqlite::types::Type::Text,
                    Box::new(error),
                )
            })?;
            Ok(TurnReceipt {
                turn_id: row.get(0)?,
                session_id: row.get(1)?,
                outcome,
                message_count: row.get(3)?,
                created_at: row.get(4)?,
            })
        })
        .map_err(sqlite_error)?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(sqlite_error)
}

pub fn read_session_goals(data_dir: &Path, session_id: &str) -> io::Result<Vec<serde_json::Value>> {
    if !valid_public_session_id(session_id) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid public session id",
        ));
    }
    let connection = open_conversation_database(data_dir)?;
    if !table_has_columns(
        &connection,
        "goals",
        &[
            "goal_id",
            "session_id",
            "objective",
            "requirements",
            "continuation_prompt",
            "token_budget",
            "time_budget_seconds",
            "state",
            "tokens_used",
            "continuation_count",
            "continuation_running",
            "baseline_message_count",
            "continuation_turn_id",
            "turn_started_at",
            "evidence",
            "audit_summary",
            "requirement_evidence",
            "created_at",
            "updated_at",
            "version",
        ],
    )? {
        return Ok(Vec::new());
    }
    let mut statement = connection
        .prepare(
            "SELECT goals.goal_id, goals.objective, goals.requirements, goals.continuation_prompt,
                    goals.token_budget, goals.time_budget_seconds, goals.state, goals.tokens_used,
                    goals.continuation_count, goals.continuation_running, goals.baseline_message_count,
                    goals.continuation_turn_id, goals.turn_started_at, goals.evidence,
                    goals.audit_summary, goals.requirement_evidence, goals.created_at, goals.updated_at, goals.version
             FROM goals
             JOIN sessions USING (session_id)
             WHERE goals.session_id = ?1
               AND substr(sessions.session_id, 1, 2) != '__'
               AND COALESCE(sessions.origin, '') != 'worker'
             ORDER BY goals.created_at",
        )
        .map_err(sqlite_error)?;
    let rows = statement
        .query_map([session_id], |row| {
            Ok(serde_json::json!({
                "goal_id": row.get::<_, String>(0)?,
                "objective": row.get::<_, String>(1)?,
                "requirements": parse_json_or_text(row.get::<_, String>(2)?),
                "continuation_prompt": row.get::<_, String>(3)?,
                "token_budget": row.get::<_, Option<i64>>(4)?,
                "time_budget_seconds": row.get::<_, Option<i64>>(5)?,
                "state": row.get::<_, String>(6)?,
                "tokens_used": row.get::<_, i64>(7)?,
                "continuation_count": row.get::<_, i64>(8)?,
                "continuation_running": row.get::<_, i64>(9)? == 1,
                "baseline_message_count": row.get::<_, i64>(10)?,
                "continuation_turn_id": row.get::<_, String>(11)?,
                "turn_started_at": row.get::<_, String>(12)?,
                "evidence": parse_json_or_text(row.get::<_, String>(13)?),
                "audit_summary": parse_json_or_text(row.get::<_, String>(14)?),
                "requirement_evidence": parse_json_or_text(row.get::<_, String>(15)?),
                "created_at": row.get::<_, String>(16)?,
                "updated_at": row.get::<_, String>(17)?,
                "version": row.get::<_, i64>(18)?,
            }))
        })
        .map_err(sqlite_error)?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(sqlite_error)
}

pub fn read_session_plan_artifacts(
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
    if !table_has_columns(
        &connection,
        "plan_artifacts",
        &[
            "session_id",
            "plan_id",
            "tool_call_id",
            "plan",
            "tasks",
            "selected_task_ids",
            "status",
            "revision",
            "updated_at",
        ],
    )? {
        return Ok(Vec::new());
    }
    let mut statement = connection
        .prepare(
            "SELECT plan_artifacts.session_id, plan_artifacts.plan_id, plan_artifacts.tool_call_id,
                    plan_artifacts.plan, plan_artifacts.tasks, plan_artifacts.selected_task_ids,
                    plan_artifacts.status, plan_artifacts.revision, plan_artifacts.updated_at
             FROM plan_artifacts
             JOIN sessions USING (session_id)
             WHERE plan_artifacts.session_id = ?1
               AND substr(sessions.session_id, 1, 2) != '__'
               AND COALESCE(sessions.origin, '') != 'worker'
             ORDER BY plan_artifacts.updated_at DESC, plan_artifacts.plan_id",
        )
        .map_err(sqlite_error)?;
    let rows = statement
        .query_map([session_id], |row| {
            Ok(serde_json::json!({
                "plan_id": row.get::<_, String>(1)?,
                "session_id": row.get::<_, String>(0)?,
                "tool_call_id": row.get::<_, String>(2)?,
                "content": {
                    "plan": row.get::<_, String>(3)?,
                    "tasks": parse_json_or_text(row.get::<_, String>(4)?),
                },
                "selected_task_ids": parse_json_or_text(row.get::<_, String>(5)?),
                "status": row.get::<_, String>(6)?,
                "revision": row.get::<_, i64>(7)?,
                "updated_at": row.get::<_, String>(8)?,
            }))
        })
        .map_err(sqlite_error)?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(sqlite_error)
}

pub fn read_session_plan_builds(
    data_dir: &Path,
    session_id: &str,
) -> io::Result<Vec<serde_json::Value>> {
    if !valid_public_session_id(session_id) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid public session id",
        ));
    }
    let connection = open_plan_builds_database(data_dir)?;
    if !table_has_columns(
        &connection,
        "plan_builds",
        &[
            "build_id",
            "parent_session_id",
            "plan_id",
            "tasks",
            "state",
            "error",
            "created_at",
            "updated_at",
        ],
    )? {
        return Ok(Vec::new());
    }
    let mut statement = connection
        .prepare(
            "SELECT build_id, parent_session_id, plan_id, tasks, state, error,
                    created_at, updated_at
             FROM plan_builds
             WHERE parent_session_id = ?1
             ORDER BY created_at, build_id
             LIMIT 100",
        )
        .map_err(sqlite_error)?;
    let rows = statement
        .query_map([session_id], |row| {
            Ok(serde_json::json!({
                "build_id": row.get::<_, String>(0)?,
                "parent_session_id": row.get::<_, String>(1)?,
                "plan_id": row.get::<_, String>(2)?,
                "tasks": parse_json_or_text(row.get::<_, String>(3)?),
                "state": row.get::<_, String>(4)?,
                "error": row.get::<_, String>(5)?,
                "created_at": row.get::<_, String>(6)?,
                "updated_at": row.get::<_, String>(7)?,
            }))
        })
        .map_err(sqlite_error)?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(sqlite_error)
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

fn validate_public_session_id(session_id: &str) -> io::Result<()> {
    if valid_public_session_id(session_id) {
        Ok(())
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid public session id",
        ))
    }
}

fn validate_source_attachment_id(attachment_id: &str) -> io::Result<()> {
    if !attachment_id.is_empty()
        && attachment_id.len() <= 160
        && attachment_id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
    {
        Ok(())
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid source attachment id",
        ))
    }
}

fn source_path_state(path: &Path) -> (&'static str, Option<String>) {
    match fs::symlink_metadata(path) {
        Ok(metadata) if metadata.file_type().is_symlink() => (
            "unavailable",
            Some("source path is a symbolic link".to_owned()),
        ),
        Ok(metadata) if metadata.is_file() || metadata.is_dir() => ("ready", None),
        Ok(_) => (
            "unavailable",
            Some("source path is not a file or folder".to_owned()),
        ),
        Err(error) => ("unavailable", Some(error.to_string())),
    }
}

fn bounded_single_line(value: &str, label: &str, max_bytes: usize) -> io::Result<String> {
    let value = value.trim();
    if value.is_empty()
        || value.len() > max_bytes
        || value
            .bytes()
            .any(|byte| byte == 0 || byte == b'\r' || byte == b'\n')
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("{label} is invalid"),
        ));
    }
    Ok(value.to_owned())
}

fn canonical_workspace(workspace: &str) -> io::Result<String> {
    let workspace = bounded_single_line(workspace, "workspace", 4096)?;
    let path = Path::new(&workspace);
    if !path.is_absolute() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "workspace must be an absolute path",
        ));
    }
    let metadata = fs::symlink_metadata(path)?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "workspace must be a regular non-symlink directory",
        ));
    }
    Ok(fs::canonicalize(path)?.to_string_lossy().into_owned())
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

fn open_conversation_database_for_write(data_dir: &Path) -> io::Result<Connection> {
    let mismatches = inspect_v1_data_dir(data_dir)?;
    if !mismatches.is_empty() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "data directory does not match v1 storage",
        ));
    }
    let connection = Connection::open_with_flags(
        data_dir.join("codinal.db"),
        OpenFlags::SQLITE_OPEN_READ_WRITE | OpenFlags::SQLITE_OPEN_NO_MUTEX,
    )
    .map_err(sqlite_error)?;
    connection
        .execute_batch(
            "PRAGMA foreign_keys = ON; PRAGMA journal_mode = DELETE; PRAGMA synchronous = FULL;",
        )
        .map_err(sqlite_error)?;
    Ok(connection)
}

fn open_plan_builds_database(data_dir: &Path) -> io::Result<Connection> {
    let mismatches = inspect_v1_data_dir(data_dir)?;
    if !mismatches.is_empty() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "data directory does not match v1 storage",
        ));
    }
    Connection::open_with_flags(
        data_dir.join("plan-builds.db"),
        OpenFlags::SQLITE_OPEN_READ_ONLY,
    )
    .map_err(sqlite_error)
}

fn parse_json_or_text(value: String) -> serde_json::Value {
    serde_json::from_str(&value).unwrap_or(serde_json::Value::String(value))
}

fn table_has_columns(connection: &Connection, table: &str, columns: &[&str]) -> io::Result<bool> {
    let mut statement = connection
        .prepare(&format!("PRAGMA table_info({table})"))
        .map_err(sqlite_error)?;
    let names = statement
        .query_map([], |row| row.get::<_, String>(1))
        .map_err(sqlite_error)?;
    let names = names
        .collect::<rusqlite::Result<BTreeSet<_>>>()
        .map_err(sqlite_error)?;
    for column in columns {
        if !names.contains(*column) {
            return Ok(false);
        }
    }
    Ok(true)
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
        assign_session_to_project, attach_source_attachment, create_project, create_session,
        create_session_with_origin, create_v1_shadow_snapshot, delete_session, inspect_v1_data_dir,
        load_v1_fixture, prepare_owned_data_directory, read_projects, read_session_messages,
        read_session_summaries, read_source_attachments, remove_project,
        remove_session_from_project, remove_source_attachment, replace_project,
        retry_source_attachment, set_project_pinned, update_session,
    };
    use rusqlite::Connection;
    use std::fs;
    use std::io;
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
             DROP TABLE project_sessions;
             DROP TABLE project_roots;
             DROP TABLE projects;
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
             CREATE TABLE projects (
               project_id TEXT PRIMARY KEY, name TEXT NOT NULL,
               pinned INTEGER NOT NULL DEFAULT 0,
               updated_at TEXT NOT NULL
             );
             CREATE TABLE project_roots (
               project_id TEXT NOT NULL, root_id TEXT NOT NULL, path TEXT NOT NULL,
               is_primary INTEGER NOT NULL DEFAULT 0,
               PRIMARY KEY (project_id, root_id)
             );
             CREATE TABLE project_sessions (
               project_id TEXT NOT NULL, session_id TEXT PRIMARY KEY
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

    #[test]
    fn owner_can_create_a_public_session_and_workspace_atomically() {
        let dir = fresh_dir();
        let workspace = dir.join("workspace");
        fs::create_dir(&workspace).expect("workspace");
        prepare_owned_data_directory(&dir).expect("owned storage");

        let session = create_session(
            &dir,
            "session-created",
            "New task",
            workspace.to_str().expect("workspace UTF-8"),
            "code",
            "kimi-k2.7-code",
            "code",
        )
        .expect("create session");

        assert_eq!(session.session_id, "session-created");
        assert_eq!(session.title, "New task");
        assert_eq!(
            session.workspace,
            workspace
                .canonicalize()
                .expect("canonical workspace")
                .display()
                .to_string()
        );
        assert_eq!(session.messages, 0);
        assert_eq!(
            read_session_summaries(&dir, None).expect("sessions").len(),
            1
        );
        assert!(
            create_session(
                &dir,
                "session-created",
                "Duplicate",
                workspace.to_str().expect("workspace UTF-8"),
                "code",
                "kimi-k2.7-code",
                "code",
            )
            .expect_err("duplicate session must be rejected")
            .kind()
                == io::ErrorKind::AlreadyExists
        );

        fs::remove_dir_all(dir).expect("remove");
    }

    #[test]
    fn owner_can_persist_a_typed_side_chat_origin() {
        let dir = fresh_dir();
        let workspace = dir.join("workspace");
        fs::create_dir(&workspace).expect("workspace");
        prepare_owned_data_directory(&dir).expect("owned storage");

        let session = create_session_with_origin(
            &dir,
            "side-chat-1",
            "Side chat · Parent",
            workspace.to_str().expect("workspace UTF-8"),
            "code",
            "kimi-k2.7-code",
            "code",
            Some("side_chat"),
            Some("Side chat"),
            Some("parent-session"),
        )
        .expect("create side chat");

        assert_eq!(session.origin.as_deref(), Some("side_chat"));
        assert_eq!(session.origin_label.as_deref(), Some("Side chat"));
        assert_eq!(session.origin_session_id.as_deref(), Some("parent-session"));

        let invalid = create_session_with_origin(
            &dir,
            "invalid-origin",
            "Invalid",
            workspace.to_str().expect("workspace UTF-8"),
            "code",
            "kimi-k2.7-code",
            "code",
            Some("unknown"),
            None,
            None,
        )
        .expect_err("unknown origins must be rejected");
        assert_eq!(invalid.kind(), io::ErrorKind::InvalidInput);

        fs::remove_dir_all(dir).expect("remove");
    }

    #[test]
    fn owner_can_manage_projects_and_membership_atomically() {
        let dir = fresh_dir();
        let workspace = dir.join("workspace");
        fs::create_dir(&workspace).expect("workspace");
        prepare_owned_data_directory(&dir).expect("owned storage");
        let root = workspace.to_string_lossy().into_owned();

        let project = create_project(&dir, "project-1", "Harness", std::slice::from_ref(&root))
            .expect("create project");
        assert_eq!(project.name, "Harness");
        assert_eq!(project.roots.len(), 1);
        assert!(project.roots[0].primary);
        assert_eq!(read_projects(&dir).expect("projects").len(), 1);

        set_project_pinned(&dir, "project-1", true).expect("pin project");
        assert!(read_projects(&dir).expect("pinned project")[0].pinned);

        create_session(
            &dir,
            "session-1",
            "Chat",
            workspace.to_str().expect("workspace UTF-8"),
            "code",
            "kimi-k2.7-code",
            "code",
        )
        .expect("create session");
        assign_session_to_project(&dir, "session-1", "project-1").expect("assign session");
        let session = read_session_summaries(&dir, None)
            .expect("sessions")
            .into_iter()
            .find(|session| session.session_id == "session-1")
            .expect("session");
        assert_eq!(session.project_id.as_deref(), Some("project-1"));
        assert_eq!(session.project_name.as_deref(), Some("Harness"));
        assert_eq!(read_projects(&dir).expect("project count")[0].task_count, 1);

        replace_project(&dir, "project-1", "Codinal", &[]).expect("replace project");
        assert_eq!(
            read_projects(&dir).expect("replaced project")[0].name,
            "Codinal"
        );
        remove_session_from_project(&dir, "project-1", "session-1").expect("remove membership");
        assert_eq!(
            read_projects(&dir).expect("unassigned project")[0].task_count,
            0
        );
        remove_project(&dir, "project-1").expect("remove project");
        assert!(read_projects(&dir).expect("projects").is_empty());

        fs::remove_dir_all(dir).expect("remove");
    }

    #[test]
    fn owner_can_update_and_delete_a_session_without_touching_workspace_files() {
        let dir = fresh_dir();
        let workspace = dir.join("workspace");
        fs::create_dir(&workspace).expect("workspace");
        let source = workspace.join("keep.txt");
        fs::write(&source, "keep").expect("source");
        prepare_owned_data_directory(&dir).expect("owned storage");
        create_session(
            &dir,
            "session-actions",
            "Original",
            workspace.to_str().expect("workspace UTF-8"),
            "code",
            "kimi-k2.7-code",
            "code",
        )
        .expect("create session");

        let updated = update_session(
            &dir,
            "session-actions",
            Some("Renamed"),
            Some(true),
            Some(true),
        )
        .expect("update session");
        assert_eq!(updated.title, "Renamed");
        assert!(updated.pinned);
        assert!(updated.archived);

        delete_session(&dir, "session-actions").expect("delete session");
        assert!(read_session_summaries(&dir, None)
            .expect("sessions")
            .is_empty());
        assert_eq!(fs::read_to_string(source).expect("source remains"), "keep");
        fs::remove_dir_all(dir).expect("remove");
    }

    #[test]
    fn owner_can_attach_retry_and_remove_sources_without_touching_originals() {
        let dir = fresh_dir();
        let workspace = dir.join("workspace");
        fs::create_dir(&workspace).expect("workspace");
        let source = workspace.join("reference.md");
        fs::write(&source, "keep this file").expect("source");
        prepare_owned_data_directory(&dir).expect("owned storage");
        create_session(
            &dir,
            "session-1",
            "Chat",
            workspace.to_str().expect("workspace UTF-8"),
            "code",
            "kimi-k2.7-code",
            "code",
        )
        .expect("create session");

        let attachment = attach_source_attachment(
            &dir,
            "session-1",
            "source-reference",
            source.to_str().expect("source UTF-8"),
            "reference.md",
            "file",
        )
        .expect("attach source");
        assert_eq!(attachment.status, "ready");
        assert_eq!(
            read_source_attachments(&dir, "session-1")
                .expect("list")
                .len(),
            1
        );

        fs::remove_file(&source).expect("remove original for retry test");
        let unavailable =
            retry_source_attachment(&dir, "session-1", "source-reference").expect("retry source");
        assert_eq!(unavailable.status, "unavailable");
        assert!(unavailable.error.is_some());

        remove_source_attachment(&dir, "session-1", "source-reference").expect("remove record");
        assert!(read_source_attachments(&dir, "session-1")
            .expect("empty source list")
            .is_empty());
        assert!(
            !source.exists(),
            "remove only detaches; the test removed the original"
        );

        fs::remove_dir_all(dir).expect("remove");
    }
}
