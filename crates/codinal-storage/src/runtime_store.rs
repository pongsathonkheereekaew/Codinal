//! Durable state owned by the Rust runtime after writer ownership is acquired.
//!
//! Conversation history remains in the existing v1 databases. This database
//! contains only runtime coordination state whose lifecycle is independent of
//! the legacy conversation schema. It is never created by read-only paths.

use rusqlite::{Connection, OpenFlags, OptionalExtension, TransactionBehavior};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

pub const RUNTIME_STORE_FILE: &str = "codinal-runtime.db";
pub const RUNTIME_STORE_SCHEMA_VERSION: i64 = 1;
const MAX_EVENT_READ: usize = 500;
const MAX_TEXT: usize = 256;
const ACTIVITY_READ_KEY: &str = "activity_read";

#[derive(Clone)]
pub struct RuntimeStore {
    connection: Arc<Mutex<Connection>>,
    database: PathBuf,
    generation: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct RuntimeCursor {
    pub generation: String,
    pub global_sequence: i64,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct RuntimeEventRecord {
    pub global_sequence: i64,
    pub turn_id: String,
    pub sequence: i64,
    pub kind: String,
    pub payload: serde_json::Value,
    pub at: f64,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct RuntimeEventReplay {
    pub generation: String,
    pub events: Vec<RuntimeEventRecord>,
    pub next_cursor: String,
    pub cursor_expired: bool,
    pub receipt_reload_target: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TurnRecord {
    pub turn_id: String,
    pub session_id: String,
    pub state: String,
    pub sequence: i64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ApprovalRecord {
    pub approval_id: String,
    pub turn_id: String,
    pub session_id: String,
    pub request: String,
    pub state: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BudgetReservationRecord {
    pub reservation_id: String,
    pub turn_id: String,
    pub requested_tokens: i64,
    pub reserved_tokens: i64,
    pub state: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MutationJournalRecord {
    pub mutation_id: String,
    pub turn_id: String,
    pub path: String,
    pub digest: String,
    pub state: String,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct TurnReceiptRecord {
    pub turn_id: String,
    pub session_id: String,
    pub outcome: serde_json::Value,
    pub message_count: i64,
    pub created_at: String,
}

impl RuntimeStore {
    /// Open or create the runtime store. Callers must hold the lifetime
    /// writer lock before invoking this method.
    pub fn open_owned(data_dir: &Path) -> std::io::Result<Self> {
        validate_data_dir(data_dir)?;
        let database = data_dir.join(RUNTIME_STORE_FILE);
        if let Ok(metadata) = fs::symlink_metadata(&database) {
            if metadata.file_type().is_symlink() || !metadata.is_file() {
                return Err(std::io::Error::new(
                    std::io::ErrorKind::InvalidInput,
                    "runtime store must be a regular non-symlink file",
                ));
            }
        }
        let connection = Connection::open_with_flags(
            &database,
            OpenFlags::SQLITE_OPEN_READ_WRITE
                | OpenFlags::SQLITE_OPEN_CREATE
                | OpenFlags::SQLITE_OPEN_NO_MUTEX,
        )
        .map_err(sqlite_error)?;
        configure_connection(&connection)?;
        initialize_schema(&connection)?;
        let generation = read_generation(&connection)?;
        Ok(Self {
            connection: Arc::new(Mutex::new(connection)),
            database,
            generation,
        })
    }

    /// Open an existing store without creating or repairing it.
    pub fn open_read_only(data_dir: &Path) -> std::io::Result<Self> {
        validate_data_dir(data_dir)?;
        let database = data_dir.join(RUNTIME_STORE_FILE);
        let metadata = fs::symlink_metadata(&database)?;
        if metadata.file_type().is_symlink() || !metadata.is_file() {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "runtime store must be a regular non-symlink file",
            ));
        }
        let connection = Connection::open_with_flags(&database, OpenFlags::SQLITE_OPEN_READ_ONLY)
            .map_err(sqlite_error)?;
        let version: i64 = connection
            .query_row("PRAGMA user_version", [], |row| row.get(0))
            .map_err(sqlite_error)?;
        if version != RUNTIME_STORE_SCHEMA_VERSION {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "unsupported runtime store schema",
            ));
        }
        let integrity: String = connection
            .query_row("PRAGMA integrity_check", [], |row| row.get(0))
            .map_err(sqlite_error)?;
        if integrity != "ok" {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "runtime store integrity check failed",
            ));
        }
        let generation = read_generation(&connection)?;
        Ok(Self {
            connection: Arc::new(Mutex::new(connection)),
            database,
            generation,
        })
    }

    pub fn database(&self) -> &Path {
        &self.database
    }

    pub fn generation(&self) -> &str {
        &self.generation
    }

    pub fn activity_read(&self) -> std::io::Result<bool> {
        let connection = self.lock_connection()?;
        let value = connection
            .query_row(
                "SELECT value FROM store_meta WHERE key = ?1",
                [ACTIVITY_READ_KEY],
                |row| row.get::<_, String>(0),
            )
            .optional()
            .map_err(sqlite_error)?;
        Ok(value.as_deref() == Some("true"))
    }

    pub fn set_activity_read(&self, read: bool) -> std::io::Result<()> {
        let connection = self.lock_connection()?;
        connection
            .execute(
                "INSERT INTO store_meta (key, value) VALUES (?1, ?2)
                 ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                rusqlite::params![ACTIVITY_READ_KEY, if read { "true" } else { "false" }],
            )
            .map_err(sqlite_error)?;
        Ok(())
    }

    pub fn create_turn(&self, turn_id: &str, session_id: &str) -> std::io::Result<TurnRecord> {
        validate_id(turn_id, "turn")?;
        validate_id(session_id, "session")?;
        let mut connection = self.lock_connection()?;
        let transaction = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(sqlite_error)?;
        transaction
            .execute(
                "INSERT INTO turn_state (turn_id, session_id, state, sequence, updated_at)
                 VALUES (?1, ?2, 'created', 0, ?3)",
                rusqlite::params![turn_id, session_id, now()],
            )
            .map_err(sqlite_error)?;
        transaction.commit().map_err(sqlite_error)?;
        Ok(TurnRecord {
            turn_id: turn_id.to_owned(),
            session_id: session_id.to_owned(),
            state: "created".to_owned(),
            sequence: 0,
        })
    }

    pub fn read_turn(&self, turn_id: &str) -> std::io::Result<Option<TurnRecord>> {
        validate_id(turn_id, "turn")?;
        let connection = self.lock_connection()?;
        connection
            .query_row(
                "SELECT session_id, state, sequence
                 FROM turn_state WHERE turn_id = ?1",
                [turn_id],
                |row| {
                    Ok(TurnRecord {
                        turn_id: turn_id.to_owned(),
                        session_id: row.get(0)?,
                        state: row.get(1)?,
                        sequence: row.get(2)?,
                    })
                },
            )
            .optional()
            .map_err(sqlite_error)
    }

    pub fn transition_turn(&self, turn_id: &str, state: &str) -> std::io::Result<TurnRecord> {
        validate_id(turn_id, "turn")?;
        validate_text(state, "turn state")?;
        let mut connection = self.lock_connection()?;
        let transaction = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(sqlite_error)?;
        let record = transaction
            .query_row(
                "SELECT session_id, sequence FROM turn_state WHERE turn_id = ?1",
                [turn_id],
                |row| Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?)),
            )
            .optional()
            .map_err(sqlite_error)?
            .ok_or_else(|| not_found("turn"))?;
        let sequence = record.1 + 1;
        transaction
            .execute(
                "UPDATE turn_state SET state = ?1, sequence = ?2, updated_at = ?3
                 WHERE turn_id = ?4",
                rusqlite::params![state, sequence, now(), turn_id],
            )
            .map_err(sqlite_error)?;
        transaction.commit().map_err(sqlite_error)?;
        Ok(TurnRecord {
            turn_id: turn_id.to_owned(),
            session_id: record.0,
            state: state.to_owned(),
            sequence,
        })
    }

    /// Append a per-turn event and allocate a monotonically increasing global
    /// sequence in the same transaction as the per-turn sequence.
    pub fn append_event(
        &self,
        turn_id: &str,
        kind: &str,
        payload: serde_json::Value,
    ) -> std::io::Result<RuntimeEventRecord> {
        validate_id(turn_id, "turn")?;
        validate_text(kind, "event kind")?;
        let encoded = serde_json::to_string(&payload).map_err(json_error)?;
        if encoded.len() > 64 * 1024 {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "runtime event payload exceeds limit",
            ));
        }
        let mut connection = self.lock_connection()?;
        let transaction = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(sqlite_error)?;
        let sequence: i64 = transaction
            .query_row(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM turn_events WHERE turn_id = ?1",
                [turn_id],
                |row| row.get(0),
            )
            .map_err(sqlite_error)?;
        let at = now();
        transaction
            .execute(
                "INSERT INTO turn_events (turn_id, sequence, kind, payload, at)
                 VALUES (?1, ?2, ?3, ?4, ?5)",
                rusqlite::params![turn_id, sequence, kind, encoded, at],
            )
            .map_err(sqlite_error)?;
        let global_sequence = transaction.last_insert_rowid();
        transaction.commit().map_err(sqlite_error)?;
        Ok(RuntimeEventRecord {
            global_sequence,
            turn_id: turn_id.to_owned(),
            sequence,
            kind: kind.to_owned(),
            payload,
            at,
        })
    }

    pub fn replay_events(
        &self,
        cursor: Option<&str>,
        limit: usize,
    ) -> std::io::Result<RuntimeEventReplay> {
        if limit == 0 || limit > MAX_EVENT_READ {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "invalid runtime event read limit",
            ));
        }
        let requested = cursor
            .map(parse_cursor)
            .transpose()?
            .unwrap_or(RuntimeCursor {
                generation: self.generation.clone(),
                global_sequence: 0,
            });
        if requested.generation != self.generation {
            return Ok(RuntimeEventReplay {
                generation: self.generation.clone(),
                events: Vec::new(),
                next_cursor: self.encode_cursor(0)?,
                cursor_expired: true,
                receipt_reload_target: Some("/v1/sessions/{session_id}/turns".to_owned()),
            });
        }
        let connection = self.lock_connection()?;
        let mut statement = connection
            .prepare(
                "SELECT global_sequence, turn_id, sequence, kind, payload, at
                 FROM turn_events WHERE global_sequence > ?1
                 ORDER BY global_sequence LIMIT ?2",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map(
                rusqlite::params![requested.global_sequence, limit as i64],
                decode_event,
            )
            .map_err(sqlite_error)?
            .collect::<rusqlite::Result<Vec<_>>>()
            .map_err(sqlite_error)?;
        let last = rows
            .last()
            .map_or(requested.global_sequence, |event| event.global_sequence);
        Ok(RuntimeEventReplay {
            generation: self.generation.clone(),
            events: rows,
            next_cursor: self.encode_cursor(last)?,
            cursor_expired: false,
            receipt_reload_target: None,
        })
    }

    pub fn put_approval(&self, record: &ApprovalRecord) -> std::io::Result<()> {
        validate_id(&record.approval_id, "approval")?;
        validate_id(&record.turn_id, "turn")?;
        validate_id(&record.session_id, "session")?;
        validate_text(&record.state, "approval state")?;
        let connection = self.lock_connection()?;
        connection
            .execute(
                "INSERT INTO pending_approvals
                 (approval_id, turn_id, session_id, request, state)
                 VALUES (?1, ?2, ?3, ?4, ?5)
                 ON CONFLICT(approval_id) DO UPDATE SET state = excluded.state",
                rusqlite::params![
                    record.approval_id,
                    record.turn_id,
                    record.session_id,
                    record.request,
                    record.state
                ],
            )
            .map_err(sqlite_error)?;
        Ok(())
    }

    pub fn read_pending_approvals(&self, session_id: &str) -> std::io::Result<Vec<ApprovalRecord>> {
        validate_id(session_id, "session")?;
        let connection = self.lock_connection()?;
        let mut statement = connection
            .prepare(
                "SELECT approval_id, turn_id, session_id, request, state
                 FROM pending_approvals
                 WHERE session_id = ?1 AND state = 'pending'
                 ORDER BY approval_id",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([session_id], |row| {
                Ok(ApprovalRecord {
                    approval_id: row.get(0)?,
                    turn_id: row.get(1)?,
                    session_id: row.get(2)?,
                    request: row.get(3)?,
                    state: row.get(4)?,
                })
            })
            .map_err(sqlite_error)?
            .collect::<rusqlite::Result<Vec<_>>>();
        rows.map_err(sqlite_error)
    }

    pub fn read_all_pending_approvals(&self) -> std::io::Result<Vec<ApprovalRecord>> {
        let connection = self.lock_connection()?;
        let mut statement = connection
            .prepare(
                "SELECT approval_id, turn_id, session_id, request, state
                 FROM pending_approvals
                 WHERE state = 'pending'
                 ORDER BY session_id, approval_id",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| {
                Ok(ApprovalRecord {
                    approval_id: row.get(0)?,
                    turn_id: row.get(1)?,
                    session_id: row.get(2)?,
                    request: row.get(3)?,
                    state: row.get(4)?,
                })
            })
            .map_err(sqlite_error)?
            .collect::<rusqlite::Result<Vec<_>>>();
        rows.map_err(sqlite_error)
    }

    pub fn read_approvals_for_turn(&self, turn_id: &str) -> std::io::Result<Vec<ApprovalRecord>> {
        validate_id(turn_id, "turn")?;
        let connection = self.lock_connection()?;
        let mut statement = connection
            .prepare(
                "SELECT approval_id, turn_id, session_id, request, state
                 FROM pending_approvals
                 WHERE turn_id = ?1
                 ORDER BY approval_id",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([turn_id], |row| {
                Ok(ApprovalRecord {
                    approval_id: row.get(0)?,
                    turn_id: row.get(1)?,
                    session_id: row.get(2)?,
                    request: row.get(3)?,
                    state: row.get(4)?,
                })
            })
            .map_err(sqlite_error)?
            .collect::<rusqlite::Result<Vec<_>>>();
        rows.map_err(sqlite_error)
    }

    pub fn put_budget_reservation(&self, record: &BudgetReservationRecord) -> std::io::Result<()> {
        validate_id(&record.reservation_id, "reservation")?;
        validate_id(&record.turn_id, "turn")?;
        validate_text(&record.state, "reservation state")?;
        if record.requested_tokens < 0 || record.reserved_tokens < 0 {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "budget values must be non-negative",
            ));
        }
        let connection = self.lock_connection()?;
        connection
            .execute(
                "INSERT INTO budget_reservations
                 (reservation_id, turn_id, requested_tokens, reserved_tokens, state)
                 VALUES (?1, ?2, ?3, ?4, ?5)
                 ON CONFLICT(reservation_id) DO UPDATE SET
                   requested_tokens = excluded.requested_tokens,
                   reserved_tokens = excluded.reserved_tokens,
                   state = excluded.state",
                rusqlite::params![
                    record.reservation_id,
                    record.turn_id,
                    record.requested_tokens,
                    record.reserved_tokens,
                    record.state
                ],
            )
            .map_err(sqlite_error)?;
        connection
            .execute(
                "INSERT OR IGNORE INTO budget_reservation_days (reservation_id, budget_day)
                 VALUES (?1, strftime('%Y-%m-%d', 'now'))",
                [record.reservation_id.as_str()],
            )
            .map_err(sqlite_error)?;
        Ok(())
    }

    /// Atomically reserve a bounded token budget. The reservation key is
    /// idempotent so a request retried after a process restart cannot consume
    /// the same budget twice.
    pub fn reserve_budget(
        &self,
        reservation_id: &str,
        turn_id: &str,
        requested_tokens: i64,
        max_reserved_tokens: i64,
        max_daily_tokens: i64,
    ) -> std::io::Result<BudgetReservationRecord> {
        validate_id(reservation_id, "reservation")?;
        validate_id(turn_id, "turn")?;
        if requested_tokens <= 0 || max_reserved_tokens <= 0 || max_daily_tokens <= 0 {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "budget values must be positive",
            ));
        }
        if requested_tokens > max_reserved_tokens {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "requested budget exceeds maximum",
            ));
        }
        let mut connection = self.lock_connection()?;
        let transaction = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(sqlite_error)?;
        if let Some(existing) = transaction
            .query_row(
                "SELECT turn_id, requested_tokens, reserved_tokens, state
                 FROM budget_reservations WHERE reservation_id = ?1",
                [reservation_id],
                |row| {
                    Ok(BudgetReservationRecord {
                        reservation_id: reservation_id.to_owned(),
                        turn_id: row.get(0)?,
                        requested_tokens: row.get(1)?,
                        reserved_tokens: row.get(2)?,
                        state: row.get(3)?,
                    })
                },
            )
            .optional()
            .map_err(sqlite_error)?
        {
            if existing.turn_id != turn_id || existing.requested_tokens != requested_tokens {
                return Err(std::io::Error::new(
                    std::io::ErrorKind::AlreadyExists,
                    "budget reservation key was reused",
                ));
            }
            transaction.commit().map_err(sqlite_error)?;
            return Ok(existing);
        }
        let active: i64 = transaction
            .query_row(
                "SELECT COALESCE(SUM(reserved_tokens), 0)
                 FROM budget_reservations WHERE state = 'reserved'",
                [],
                |row| row.get(0),
            )
            .map_err(sqlite_error)?;
        if active
            .checked_add(requested_tokens)
            .is_none_or(|total| total > max_reserved_tokens)
        {
            return Err(std::io::Error::new(
                std::io::ErrorKind::WouldBlock,
                "token budget is exhausted",
            ));
        }
        let day: String = transaction
            .query_row("SELECT strftime('%Y-%m-%d', 'now')", [], |row| row.get(0))
            .map_err(sqlite_error)?;
        let (daily_reserved, daily_committed): (i64, i64) = transaction
            .query_row(
                "SELECT reserved_tokens, committed_tokens
                 FROM budget_daily WHERE budget_day = ?1",
                [&day],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()
            .map_err(sqlite_error)?
            .unwrap_or((0, 0));
        if daily_committed
            .checked_add(daily_reserved)
            .and_then(|total| total.checked_add(requested_tokens))
            .is_none_or(|total| total > max_daily_tokens)
        {
            return Err(std::io::Error::new(
                std::io::ErrorKind::WouldBlock,
                "daily token budget is exhausted",
            ));
        }
        transaction
            .execute(
                "INSERT INTO budget_daily (budget_day, reserved_tokens, committed_tokens)
                 VALUES (?1, ?2, 0)
                 ON CONFLICT(budget_day) DO UPDATE SET
                   reserved_tokens = budget_daily.reserved_tokens + excluded.reserved_tokens",
                rusqlite::params![day, requested_tokens],
            )
            .map_err(sqlite_error)?;
        transaction
            .execute(
                "INSERT INTO budget_reservations
                 (reservation_id, turn_id, requested_tokens, reserved_tokens, state)
                 VALUES (?1, ?2, ?3, ?3, 'reserved')",
                rusqlite::params![reservation_id, turn_id, requested_tokens],
            )
            .map_err(sqlite_error)?;
        transaction
            .execute(
                "INSERT INTO budget_reservation_days (reservation_id, budget_day)
                 VALUES (?1, ?2)",
                rusqlite::params![reservation_id, day],
            )
            .map_err(sqlite_error)?;
        transaction.commit().map_err(sqlite_error)?;
        Ok(BudgetReservationRecord {
            reservation_id: reservation_id.to_owned(),
            turn_id: turn_id.to_owned(),
            requested_tokens,
            reserved_tokens: requested_tokens,
            state: "reserved".to_owned(),
        })
    }

    pub fn reconcile_budget(
        &self,
        reservation_id: &str,
        actual_tokens: Option<i64>,
        state: &str,
    ) -> std::io::Result<BudgetReservationRecord> {
        validate_id(reservation_id, "reservation")?;
        if !matches!(state, "settled" | "settled_unknown" | "failed" | "released") {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "invalid budget reconciliation state",
            ));
        }
        if actual_tokens.is_some_and(|tokens| tokens < 0) {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "budget usage must be non-negative",
            ));
        }
        let mut connection = self.lock_connection()?;
        let transaction = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(sqlite_error)?;
        let existing = transaction
            .query_row(
                "SELECT turn_id, requested_tokens, reserved_tokens, state
                 FROM budget_reservations WHERE reservation_id = ?1",
                [reservation_id],
                |row| {
                    Ok(BudgetReservationRecord {
                        reservation_id: reservation_id.to_owned(),
                        turn_id: row.get(0)?,
                        requested_tokens: row.get(1)?,
                        reserved_tokens: row.get(2)?,
                        state: row.get(3)?,
                    })
                },
            )
            .optional()
            .map_err(sqlite_error)?
            .ok_or_else(|| not_found("budget reservation"))?;
        if existing.state != "reserved" {
            transaction.commit().map_err(sqlite_error)?;
            return Ok(existing);
        }
        let day: String = transaction
            .query_row(
                "SELECT COALESCE(
                   (SELECT budget_day FROM budget_reservation_days WHERE reservation_id = ?1),
                   strftime('%Y-%m-%d', 'now')
                 )",
                [reservation_id],
                |row| row.get(0),
            )
            .map_err(sqlite_error)?;
        let daily = transaction
            .query_row(
                "SELECT reserved_tokens, committed_tokens
                 FROM budget_daily WHERE budget_day = ?1",
                [&day],
                |row| Ok((row.get::<_, i64>(0)?, row.get::<_, i64>(1)?)),
            )
            .optional()
            .map_err(sqlite_error)?
            .unwrap_or((0, 0));
        let daily_reserved = daily.0.saturating_sub(existing.reserved_tokens);
        let daily_committed = match state {
            "settled" => daily
                .1
                .saturating_add(actual_tokens.unwrap_or(existing.reserved_tokens)),
            "settled_unknown" | "failed" => daily.1.saturating_add(existing.reserved_tokens),
            "released" => daily.1,
            _ => daily.1,
        };
        transaction
            .execute(
                "INSERT INTO budget_daily (budget_day, reserved_tokens, committed_tokens)
                 VALUES (?1, ?2, ?3)
                 ON CONFLICT(budget_day) DO UPDATE SET
                   reserved_tokens = excluded.reserved_tokens,
                   committed_tokens = excluded.committed_tokens",
                rusqlite::params![day, daily_reserved, daily_committed],
            )
            .map_err(sqlite_error)?;
        match actual_tokens {
            Some(actual_tokens) => transaction
                .execute(
                    "UPDATE budget_reservations
                     SET reserved_tokens = ?1, state = ?2 WHERE reservation_id = ?3",
                    rusqlite::params![actual_tokens, state, reservation_id],
                )
                .map_err(sqlite_error)?,
            None => transaction
                .execute(
                    "UPDATE budget_reservations SET state = ?1 WHERE reservation_id = ?2",
                    rusqlite::params![state, reservation_id],
                )
                .map_err(sqlite_error)?,
        };
        transaction.commit().map_err(sqlite_error)?;
        Ok(BudgetReservationRecord {
            state: state.to_owned(),
            reserved_tokens: actual_tokens.unwrap_or(existing.reserved_tokens),
            ..existing
        })
    }

    pub fn read_budget_reservation(
        &self,
        reservation_id: &str,
    ) -> std::io::Result<Option<BudgetReservationRecord>> {
        validate_id(reservation_id, "reservation")?;
        let connection = self.lock_connection()?;
        connection
            .query_row(
                "SELECT turn_id, requested_tokens, reserved_tokens, state
                 FROM budget_reservations WHERE reservation_id = ?1",
                [reservation_id],
                |row| {
                    Ok(BudgetReservationRecord {
                        reservation_id: reservation_id.to_owned(),
                        turn_id: row.get(0)?,
                        requested_tokens: row.get(1)?,
                        reserved_tokens: row.get(2)?,
                        state: row.get(3)?,
                    })
                },
            )
            .optional()
            .map_err(sqlite_error)
    }

    pub fn put_mutation(&self, record: &MutationJournalRecord) -> std::io::Result<()> {
        validate_id(&record.mutation_id, "mutation")?;
        validate_id(&record.turn_id, "turn")?;
        validate_text(&record.path, "mutation path")?;
        validate_text(&record.digest, "mutation digest")?;
        validate_text(&record.state, "mutation state")?;
        let connection = self.lock_connection()?;
        connection
            .execute(
                "INSERT INTO mutation_journal
                 (mutation_id, turn_id, path, digest, state)
                 VALUES (?1, ?2, ?3, ?4, ?5)
                 ON CONFLICT(mutation_id) DO UPDATE SET state = excluded.state",
                rusqlite::params![
                    record.mutation_id,
                    record.turn_id,
                    record.path,
                    record.digest,
                    record.state
                ],
            )
            .map_err(sqlite_error)?;
        Ok(())
    }

    pub fn read_mutation(
        &self,
        mutation_id: &str,
    ) -> std::io::Result<Option<MutationJournalRecord>> {
        validate_id(mutation_id, "mutation")?;
        let connection = self.lock_connection()?;
        connection
            .query_row(
                "SELECT turn_id, path, digest, state
                 FROM mutation_journal WHERE mutation_id = ?1",
                [mutation_id],
                |row| {
                    Ok(MutationJournalRecord {
                        mutation_id: mutation_id.to_owned(),
                        turn_id: row.get(0)?,
                        path: row.get(1)?,
                        digest: row.get(2)?,
                        state: row.get(3)?,
                    })
                },
            )
            .optional()
            .map_err(sqlite_error)
    }

    pub fn write_receipt(
        &self,
        turn_id: &str,
        session_id: &str,
        outcome: serde_json::Value,
        message_count: i64,
    ) -> std::io::Result<TurnReceiptRecord> {
        validate_id(turn_id, "turn")?;
        validate_id(session_id, "session")?;
        if message_count < 0 {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "message count must be non-negative",
            ));
        }
        let encoded = serde_json::to_string(&outcome).map_err(json_error)?;
        let created_at = format!("{:.3}", now());
        let connection = self.lock_connection()?;
        connection
            .execute(
                "INSERT INTO turn_receipts
                 (turn_id, session_id, outcome, message_count, created_at)
                 VALUES (?1, ?2, ?3, ?4, ?5)
                 ON CONFLICT(turn_id) DO NOTHING",
                rusqlite::params![turn_id, session_id, encoded, message_count, created_at],
            )
            .map_err(sqlite_error)?;
        Ok(TurnReceiptRecord {
            turn_id: turn_id.to_owned(),
            session_id: session_id.to_owned(),
            outcome,
            message_count,
            created_at,
        })
    }

    pub fn read_receipts(&self, session_id: &str) -> std::io::Result<Vec<TurnReceiptRecord>> {
        validate_id(session_id, "session")?;
        let connection = self.lock_connection()?;
        let mut statement = connection
            .prepare(
                "SELECT turn_id, session_id, outcome, message_count, created_at
                 FROM turn_receipts WHERE session_id = ?1
                 ORDER BY created_at, turn_id LIMIT 100",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([session_id], |row| {
                let outcome = serde_json::from_str(&row.get::<_, String>(2)?).map_err(|error| {
                    rusqlite::Error::FromSqlConversionFailure(
                        2,
                        rusqlite::types::Type::Text,
                        Box::new(error),
                    )
                })?;
                Ok(TurnReceiptRecord {
                    turn_id: row.get(0)?,
                    session_id: row.get(1)?,
                    outcome,
                    message_count: row.get(3)?,
                    created_at: row.get(4)?,
                })
            })
            .map_err(sqlite_error)?
            .collect::<rusqlite::Result<Vec<_>>>();
        rows.map_err(sqlite_error)
    }

    pub fn read_receipt(&self, turn_id: &str) -> std::io::Result<Option<TurnReceiptRecord>> {
        validate_id(turn_id, "turn")?;
        let connection = self.lock_connection()?;
        connection
            .query_row(
                "SELECT turn_id, session_id, outcome, message_count, created_at
                 FROM turn_receipts WHERE turn_id = ?1",
                [turn_id],
                |row| {
                    let outcome =
                        serde_json::from_str(&row.get::<_, String>(2)?).map_err(|error| {
                            rusqlite::Error::FromSqlConversionFailure(
                                2,
                                rusqlite::types::Type::Text,
                                Box::new(error),
                            )
                        })?;
                    Ok(TurnReceiptRecord {
                        turn_id: row.get(0)?,
                        session_id: row.get(1)?,
                        outcome,
                        message_count: row.get(3)?,
                        created_at: row.get(4)?,
                    })
                },
            )
            .optional()
            .map_err(sqlite_error)
    }

    fn encode_cursor(&self, global_sequence: i64) -> std::io::Result<String> {
        serde_json::to_string(&RuntimeCursor {
            generation: self.generation.clone(),
            global_sequence,
        })
        .map_err(json_error)
    }

    fn lock_connection(&self) -> std::io::Result<std::sync::MutexGuard<'_, Connection>> {
        self.connection
            .lock()
            .map_err(|_| std::io::Error::other("runtime store lock poisoned"))
    }
}

fn initialize_schema(connection: &Connection) -> std::io::Result<()> {
    let version: i64 = connection
        .query_row("PRAGMA user_version", [], |row| row.get(0))
        .map_err(sqlite_error)?;
    if version > RUNTIME_STORE_SCHEMA_VERSION {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "runtime store schema is newer than this binary",
        ));
    }
    connection
        .execute_batch(
            "CREATE TABLE IF NOT EXISTS store_meta (
               key TEXT PRIMARY KEY,
               value TEXT NOT NULL
             );
             CREATE TABLE IF NOT EXISTS turn_state (
               turn_id TEXT PRIMARY KEY,
               session_id TEXT NOT NULL,
               state TEXT NOT NULL,
               sequence INTEGER NOT NULL,
               updated_at REAL NOT NULL
             );
             CREATE TABLE IF NOT EXISTS turn_events (
               global_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
               turn_id TEXT NOT NULL,
               sequence INTEGER NOT NULL,
               kind TEXT NOT NULL,
               payload TEXT NOT NULL,
               at REAL NOT NULL,
               UNIQUE(turn_id, sequence)
             );
             CREATE INDEX IF NOT EXISTS turn_events_turn_sequence
               ON turn_events(turn_id, sequence);
             CREATE TABLE IF NOT EXISTS pending_approvals (
               approval_id TEXT PRIMARY KEY,
               turn_id TEXT NOT NULL,
               session_id TEXT NOT NULL,
               request TEXT NOT NULL,
               state TEXT NOT NULL
             );
             CREATE TABLE IF NOT EXISTS budget_reservations (
               reservation_id TEXT PRIMARY KEY,
               turn_id TEXT NOT NULL,
               requested_tokens INTEGER NOT NULL,
               reserved_tokens INTEGER NOT NULL,
               state TEXT NOT NULL
             );
             CREATE TABLE IF NOT EXISTS budget_daily (
               budget_day TEXT PRIMARY KEY,
               reserved_tokens INTEGER NOT NULL,
               committed_tokens INTEGER NOT NULL
             );
             CREATE TABLE IF NOT EXISTS budget_reservation_days (
               reservation_id TEXT PRIMARY KEY,
               budget_day TEXT NOT NULL
             );
             CREATE TABLE IF NOT EXISTS mutation_journal (
               mutation_id TEXT PRIMARY KEY,
               turn_id TEXT NOT NULL,
               path TEXT NOT NULL,
               digest TEXT NOT NULL,
               state TEXT NOT NULL
             );
             CREATE TABLE IF NOT EXISTS turn_receipts (
               turn_id TEXT PRIMARY KEY,
               session_id TEXT NOT NULL,
               outcome TEXT NOT NULL,
               message_count INTEGER NOT NULL,
               created_at TEXT NOT NULL
             );
             CREATE INDEX IF NOT EXISTS turn_receipts_session_created
               ON turn_receipts(session_id, created_at, turn_id);
             PRAGMA user_version = 1;",
        )
        .map_err(sqlite_error)?;
    Ok(())
}

fn configure_connection(connection: &Connection) -> std::io::Result<()> {
    connection
        .execute_batch("PRAGMA journal_mode = DELETE; PRAGMA synchronous = FULL;")
        .map_err(sqlite_error)
}

fn read_generation(connection: &Connection) -> std::io::Result<String> {
    let generation = connection
        .query_row(
            "SELECT value FROM store_meta WHERE key = 'generation'",
            [],
            |row| row.get::<_, String>(0),
        )
        .optional()
        .map_err(sqlite_error)?;
    if let Some(generation) = generation {
        return Ok(generation);
    }
    let generation = format!("{}-{}", std::process::id(), timestamp());
    connection
        .execute(
            "INSERT INTO store_meta (key, value) VALUES ('generation', ?1)",
            [generation.as_str()],
        )
        .map_err(sqlite_error)?;
    Ok(generation)
}

fn parse_cursor(value: &str) -> std::io::Result<RuntimeCursor> {
    if value.len() > 1024 {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "runtime cursor is too large",
        ));
    }
    let cursor: RuntimeCursor = serde_json::from_str(value).map_err(json_error)?;
    if cursor.generation.is_empty() || cursor.global_sequence < 0 {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "invalid runtime cursor",
        ));
    }
    Ok(cursor)
}

fn decode_event(row: &rusqlite::Row<'_>) -> rusqlite::Result<RuntimeEventRecord> {
    let payload = serde_json::from_str(&row.get::<_, String>(4)?).map_err(|error| {
        rusqlite::Error::FromSqlConversionFailure(4, rusqlite::types::Type::Text, Box::new(error))
    })?;
    Ok(RuntimeEventRecord {
        global_sequence: row.get(0)?,
        turn_id: row.get(1)?,
        sequence: row.get(2)?,
        kind: row.get(3)?,
        payload,
        at: row.get(5)?,
    })
}

fn validate_data_dir(data_dir: &Path) -> std::io::Result<()> {
    let metadata = fs::symlink_metadata(data_dir)?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "runtime data directory must be a non-symlink directory",
        ));
    }
    Ok(())
}

fn validate_id(value: &str, name: &str) -> std::io::Result<()> {
    if value.is_empty()
        || value.len() > MAX_TEXT
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
    {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            format!("invalid {name} id"),
        ));
    }
    Ok(())
}

fn validate_text(value: &str, name: &str) -> std::io::Result<()> {
    if value.is_empty() || value.len() > MAX_TEXT || value.contains(['\r', '\n']) {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            format!("invalid {name}"),
        ));
    }
    Ok(())
}

fn not_found(name: &str) -> std::io::Error {
    std::io::Error::new(std::io::ErrorKind::NotFound, format!("{name} not found"))
}

fn now() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64()
}

fn timestamp() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_micros()
}

fn sqlite_error(error: rusqlite::Error) -> std::io::Error {
    std::io::Error::new(std::io::ErrorKind::InvalidData, error)
}

fn json_error(error: serde_json::Error) -> std::io::Error {
    std::io::Error::new(std::io::ErrorKind::InvalidData, error)
}

#[cfg(test)]
mod tests {
    use super::{
        ApprovalRecord, BudgetReservationRecord, MutationJournalRecord, RuntimeCursor, RuntimeStore,
    };
    use std::fs;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::sync::Arc;
    use std::thread;

    static NEXT_DIR: AtomicU64 = AtomicU64::new(0);

    fn data_dir() -> std::path::PathBuf {
        let path = std::env::temp_dir().join(format!(
            "codinal-runtime-store-test-{}-{}",
            std::process::id(),
            NEXT_DIR.fetch_add(1, Ordering::Relaxed)
        ));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir(&path).expect("data directory");
        path
    }

    #[test]
    fn owner_store_reopens_read_only_and_replays_after_cursor() {
        let path = data_dir();
        let store = RuntimeStore::open_owned(&path).expect("store");
        store.create_turn("turn-1", "session-1").expect("turn");
        let first = store
            .append_event("turn-1", "created", serde_json::json!({"ok": true}))
            .expect("first event");
        store
            .append_event("turn-1", "streaming", serde_json::json!({"chunk": 1}))
            .expect("second event");
        let cursor = serde_json::to_string(&RuntimeCursor {
            generation: store.generation().to_owned(),
            global_sequence: first.global_sequence,
        })
        .expect("cursor");
        let replay = store.replay_events(Some(&cursor), 10).expect("replay");
        assert_eq!(replay.events.len(), 1);
        assert_eq!(replay.events[0].sequence, 2);
        let receipt = store
            .write_receipt(
                "turn-1",
                "session-1",
                serde_json::json!({"status": "interrupted"}),
                0,
            )
            .expect("receipt");
        assert_eq!(
            store.read_receipts("session-1").expect("receipts"),
            vec![receipt]
        );
        drop(store);
        let read_only = RuntimeStore::open_read_only(&path).expect("read-only store");
        assert_eq!(read_only.generation(), replay.generation);
        fs::remove_dir_all(path).expect("cleanup");
    }

    #[test]
    fn activity_read_marker_survives_read_only_reopen() {
        let path = data_dir();
        let store = RuntimeStore::open_owned(&path).expect("store");
        assert!(!store.activity_read().expect("default activity marker"));
        store.set_activity_read(true).expect("mark activity read");
        assert!(store.activity_read().expect("read activity marker"));
        drop(store);
        let read_only = RuntimeStore::open_read_only(&path).expect("read-only store");
        assert!(read_only.activity_read().expect("reopened activity marker"));
        fs::remove_dir_all(path).expect("cleanup");
    }

    #[test]
    fn cursor_from_another_store_expires_with_receipt_reload_target() {
        let first_path = data_dir();
        let second_path = data_dir();
        let first = RuntimeStore::open_owned(&first_path).expect("first");
        let second = RuntimeStore::open_owned(&second_path).expect("second");
        let cursor = serde_json::to_string(&RuntimeCursor {
            generation: first.generation().to_owned(),
            global_sequence: 0,
        })
        .expect("cursor");
        let replay = second.replay_events(Some(&cursor), 10).expect("replay");
        assert!(replay.cursor_expired);
        assert!(replay.receipt_reload_target.is_some());
        fs::remove_dir_all(first_path).expect("cleanup first");
        fs::remove_dir_all(second_path).expect("cleanup second");
    }

    #[test]
    fn coordination_records_are_durable_and_idempotent_by_key() {
        let path = data_dir();
        let store = RuntimeStore::open_owned(&path).expect("store");
        store.create_turn("turn-1", "session-1").expect("turn");
        store
            .put_approval(&ApprovalRecord {
                approval_id: "approval-1".to_owned(),
                turn_id: "turn-1".to_owned(),
                session_id: "session-1".to_owned(),
                request: "{}".to_owned(),
                state: "pending".to_owned(),
            })
            .expect("approval");
        store
            .put_budget_reservation(&BudgetReservationRecord {
                reservation_id: "reservation-1".to_owned(),
                turn_id: "turn-1".to_owned(),
                requested_tokens: 10,
                reserved_tokens: 10,
                state: "reserved".to_owned(),
            })
            .expect("budget");
        store
            .put_mutation(&MutationJournalRecord {
                mutation_id: "mutation-1".to_owned(),
                turn_id: "turn-1".to_owned(),
                path: "src/lib.rs".to_owned(),
                digest: "sha256:test".to_owned(),
                state: "proposed".to_owned(),
            })
            .expect("mutation");
        drop(store);
        assert!(RuntimeStore::open_read_only(&path).is_ok());
        fs::remove_dir_all(path).expect("cleanup");
    }

    #[test]
    fn budget_reservation_is_atomic_bounded_and_reconciles_after_restart() {
        let path = data_dir();
        let store = Arc::new(RuntimeStore::open_owned(&path).expect("store"));
        for index in 0..3 {
            store
                .create_turn(&format!("turn-budget-{index}"), "session-1")
                .expect("turn");
        }
        let mut workers = Vec::new();
        for index in 0..3 {
            let store = Arc::clone(&store);
            workers.push(thread::spawn(move || {
                store.reserve_budget(
                    &format!("reservation-{index}"),
                    &format!("turn-budget-{index}"),
                    60,
                    100,
                    100,
                )
            }));
        }
        let results = workers
            .into_iter()
            .map(|worker| worker.join().expect("worker"))
            .collect::<Vec<_>>();
        assert_eq!(results.iter().filter(|result| result.is_ok()).count(), 1);
        let reservation = results
            .into_iter()
            .find_map(Result::ok)
            .expect("reservation");
        assert_eq!(reservation.state, "reserved");
        let replay = store
            .reserve_budget(
                &reservation.reservation_id,
                &reservation.turn_id,
                reservation.requested_tokens,
                100,
                100,
            )
            .expect("idempotent retry");
        assert_eq!(replay, reservation);
        let settled = store
            .reconcile_budget(&reservation.reservation_id, Some(17), "settled")
            .expect("settle");
        assert_eq!(settled.reserved_tokens, 17);
        assert_eq!(settled.state, "settled");
        assert_eq!(
            store
                .reserve_budget("reservation-daily", "turn-budget-1", 84, 100, 100)
                .expect_err("daily cap")
                .kind(),
            std::io::ErrorKind::WouldBlock
        );
        drop(store);
        let reopened = RuntimeStore::open_read_only(&path).expect("reopen");
        assert_eq!(
            reopened
                .read_budget_reservation(&reservation.reservation_id)
                .expect("read")
                .expect("record")
                .state,
            "settled"
        );
        fs::remove_dir_all(path).expect("cleanup");
    }
}
