//! Versioned local operation lifecycle shared by future runtime vertical slices.
//!
//! The ledger is deliberately transport-agnostic. It owns the request identity,
//! idempotency binding, bounded queue, monotonic progress, cancellation, and
//! durable terminal receipt. The authenticated runtime transport can expose
//! these values without becoming the source of truth.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, VecDeque};
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

pub const OPERATION_SCHEMA: &str = "codinal.operation.v1";
pub const DEFAULT_QUEUE_CAPACITY: usize = 32;

const MAX_OPERATION_PAYLOAD_BYTES: usize = 64 * 1024;
const MAX_OPERATION_UPDATES: usize = 4_096;
const MAX_OPERATION_UPDATE_BYTES: usize = 64 * 1024;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OperationEnvelope {
    pub schema: String,
    pub request_id: String,
    pub operation_id: String,
    pub idempotency_key: String,
    pub payload_digest: String,
    pub deadline_at_ms: u128,
    pub capability: String,
    pub payload: serde_json::Value,
}

impl OperationEnvelope {
    pub fn new(
        request_id: impl Into<String>,
        operation_id: impl Into<String>,
        idempotency_key: impl Into<String>,
        deadline_at_ms: u128,
        capability: impl Into<String>,
        payload: serde_json::Value,
    ) -> io::Result<Self> {
        let envelope = Self {
            schema: OPERATION_SCHEMA.to_owned(),
            request_id: request_id.into(),
            operation_id: operation_id.into(),
            idempotency_key: idempotency_key.into(),
            payload_digest: digest_json(&payload)?,
            deadline_at_ms,
            capability: capability.into(),
            payload,
        };
        envelope.validate_identity()?;
        Ok(envelope)
    }

    pub fn validate(&self, now_ms: u128) -> io::Result<()> {
        self.validate_identity()?;
        if self.deadline_at_ms <= now_ms {
            return Err(invalid("operation deadline has expired"));
        }
        Ok(())
    }

    pub fn validate_identity(&self) -> io::Result<()> {
        if self.schema != OPERATION_SCHEMA {
            return Err(invalid("unsupported operation schema"));
        }
        validate_token(&self.request_id, "request")?;
        validate_operation_id(&self.operation_id)?;
        validate_token(&self.idempotency_key, "idempotency")?;
        validate_token(&self.capability, "capability")?;
        let encoded = serde_json::to_vec(&self.payload)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        if encoded.len() > MAX_OPERATION_PAYLOAD_BYTES {
            return Err(invalid("operation payload exceeds limit"));
        }
        if self.payload_digest != digest_bytes(&encoded) {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "operation payload digest does not match payload",
            ));
        }
        Ok(())
    }
}

pub fn validate_operation_id(value: &str) -> io::Result<()> {
    validate_token(value, "operation")
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OperationState {
    Accepted,
    Running,
    Cancelling,
    Succeeded,
    Failed,
    Cancelled,
    Interrupted,
}

impl OperationState {
    pub fn is_terminal(self) -> bool {
        matches!(
            self,
            Self::Succeeded | Self::Failed | Self::Cancelled | Self::Interrupted
        )
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OperationAck {
    pub schema: String,
    pub request_id: String,
    pub operation_id: String,
    pub state: OperationState,
    pub replayed: bool,
    pub next_sequence: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub receipt: Option<OperationReceipt>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OperationProgress {
    pub schema: String,
    pub operation_id: String,
    pub sequence: u64,
    pub payload: serde_json::Value,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OperationReceipt {
    pub schema: String,
    pub operation_id: String,
    pub state: OperationState,
    pub sequence: u64,
    pub outcome: serde_json::Value,
    pub completed_at_ms: u128,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OperationResume {
    pub ack: OperationAck,
    pub progress: Vec<OperationProgress>,
    pub receipt: Option<OperationReceipt>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct OperationWork {
    pub envelope: OperationEnvelope,
}

#[derive(Clone)]
pub struct OperationLedger {
    operations_dir: PathBuf,
    capacity: usize,
    state: Arc<Mutex<LedgerState>>,
}

#[derive(Debug, Default)]
struct LedgerState {
    operations: BTreeMap<String, PersistedOperation>,
    queue: VecDeque<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PersistedOperation {
    envelope: OperationEnvelope,
    state: OperationState,
    progress: Vec<OperationProgress>,
    receipt: Option<OperationReceipt>,
    cancel_requested: bool,
}

impl OperationLedger {
    pub fn open(state_dir: &Path, capacity: usize) -> io::Result<Self> {
        if capacity == 0 {
            return Err(invalid("operation queue capacity must be positive"));
        }
        if !state_dir.is_absolute() {
            return Err(invalid("operation state directory must be absolute"));
        }
        super::ensure_directory(state_dir)?;
        let operations_dir = state_dir.join("operations");
        super::ensure_directory(&operations_dir)?;

        let mut state = LedgerState::default();
        let mut recovered = Vec::new();
        for entry in fs::read_dir(&operations_dir)? {
            let entry = entry?;
            let path = entry.path();
            let metadata = fs::symlink_metadata(&path)?;
            if metadata.file_type().is_symlink() || !metadata.is_file() {
                return Err(invalid("operation directory contains a non-file"));
            }
            if path.extension().and_then(|value| value.to_str()) != Some("json") {
                continue;
            }
            let bytes = fs::read(&path)?;
            let mut record: PersistedOperation =
                serde_json::from_slice(&bytes).map_err(|error| {
                    io::Error::new(
                        io::ErrorKind::InvalidData,
                        format!("invalid operation record: {error}"),
                    )
                })?;
            validate_record(&record)?;
            if matches!(
                record.state,
                OperationState::Running | OperationState::Cancelling
            ) {
                record.state = OperationState::Interrupted;
                record.cancel_requested = true;
                record.receipt = Some(terminal_receipt(
                    &record.envelope.operation_id,
                    OperationState::Interrupted,
                    record.progress.len() as u64 + 1,
                    serde_json::json!({"reason": "process_restarted"}),
                    super::now_ms(),
                ));
                recovered.push(record.clone());
            }
            if record.state == OperationState::Accepted {
                state.queue.push_back(record.envelope.operation_id.clone());
            }
            state
                .operations
                .insert(record.envelope.operation_id.clone(), record);
        }
        if state.queue.len() > capacity {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "persisted operation queue exceeds configured capacity",
            ));
        }
        let ledger = Self {
            operations_dir,
            capacity,
            state: Arc::new(Mutex::new(state)),
        };
        for record in recovered {
            ledger.persist(&record)?;
        }
        Ok(ledger)
    }

    pub fn submit(&self, envelope: OperationEnvelope) -> io::Result<OperationAck> {
        self.submit_at(envelope, super::now_ms())
    }

    pub fn submit_at(&self, envelope: OperationEnvelope, now_ms: u128) -> io::Result<OperationAck> {
        envelope.validate_identity()?;
        let mut state = self.lock_state()?;
        if let Some(existing_id) = state
            .operations
            .values()
            .find(|record| record.envelope.idempotency_key == envelope.idempotency_key)
            .map(|record| record.envelope.operation_id.clone())
        {
            let existing = state
                .operations
                .get(&existing_id)
                .expect("idempotency index points to operation")
                .clone();
            if existing.envelope.payload_digest != envelope.payload_digest
                || existing.envelope.capability != envelope.capability
            {
                return Err(io::Error::new(
                    io::ErrorKind::AlreadyExists,
                    "idempotency key is bound to a different payload",
                ));
            }
            return Ok(ack_for(&existing, true));
        }
        if state.operations.contains_key(&envelope.operation_id) {
            return Err(io::Error::new(
                io::ErrorKind::AlreadyExists,
                "operation id is already in use",
            ));
        }
        if state.queue.len() >= self.capacity {
            return Err(io::Error::new(
                io::ErrorKind::WouldBlock,
                "operation queue is full",
            ));
        }
        if envelope.deadline_at_ms <= now_ms {
            return Err(invalid("operation deadline has expired"));
        }
        let record = PersistedOperation {
            envelope,
            state: OperationState::Accepted,
            progress: Vec::new(),
            receipt: None,
            cancel_requested: false,
        };
        self.persist(&record)?;
        state.queue.push_back(record.envelope.operation_id.clone());
        let ack = ack_for(&record, false);
        state
            .operations
            .insert(record.envelope.operation_id.clone(), record);
        Ok(ack)
    }

    pub fn claim_next(&self) -> io::Result<Option<OperationWork>> {
        self.claim_next_at(super::now_ms())
    }

    pub fn claim_next_at(&self, now_ms: u128) -> io::Result<Option<OperationWork>> {
        let mut state = self.lock_state()?;
        while let Some(operation_id) = state.queue.pop_front() {
            let Some(record) = state.operations.get_mut(&operation_id) else {
                continue;
            };
            if record.state != OperationState::Accepted {
                continue;
            }
            if record.envelope.deadline_at_ms <= now_ms {
                record.state = OperationState::Failed;
                record.receipt = Some(terminal_receipt(
                    &record.envelope.operation_id,
                    OperationState::Failed,
                    record.progress.len() as u64 + 1,
                    serde_json::json!({"reason": "deadline_exceeded"}),
                    now_ms,
                ));
                let snapshot = record.clone();
                self.persist(&snapshot)?;
                continue;
            }
            record.state = OperationState::Running;
            let snapshot = record.clone();
            self.persist(&snapshot)?;
            return Ok(Some(OperationWork {
                envelope: record.envelope.clone(),
            }));
        }
        Ok(None)
    }

    pub fn claim_operation(&self, operation_id: &str) -> io::Result<Option<OperationWork>> {
        self.claim_operation_at(operation_id, super::now_ms())
    }

    pub fn claim_operation_at(
        &self,
        operation_id: &str,
        now_ms: u128,
    ) -> io::Result<Option<OperationWork>> {
        validate_operation_id(operation_id)?;
        let mut state = self.lock_state()?;
        let Some(queue_index) = state.queue.iter().position(|queued| queued == operation_id) else {
            return Ok(None);
        };
        state.queue.remove(queue_index);
        let Some(record) = state.operations.get_mut(operation_id) else {
            return Ok(None);
        };
        if record.state != OperationState::Accepted {
            return Ok(None);
        }
        if record.envelope.deadline_at_ms <= now_ms {
            record.state = OperationState::Failed;
            record.receipt = Some(terminal_receipt(
                &record.envelope.operation_id,
                OperationState::Failed,
                record.progress.len() as u64 + 1,
                serde_json::json!({"reason": "deadline_exceeded"}),
                now_ms,
            ));
            let snapshot = record.clone();
            self.persist(&snapshot)?;
            return Ok(None);
        }
        record.state = OperationState::Running;
        let snapshot = record.clone();
        self.persist(&snapshot)?;
        Ok(Some(OperationWork {
            envelope: record.envelope.clone(),
        }))
    }

    pub fn publish_progress(
        &self,
        operation_id: &str,
        sequence: u64,
        payload: serde_json::Value,
    ) -> io::Result<OperationProgress> {
        self.publish_progress_at(operation_id, sequence, payload, super::now_ms())
    }

    pub fn publish_progress_at(
        &self,
        operation_id: &str,
        sequence: u64,
        payload: serde_json::Value,
        now_ms: u128,
    ) -> io::Result<OperationProgress> {
        validate_operation_id(operation_id)?;
        let encoded = serde_json::to_vec(&payload)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        if encoded.len() > MAX_OPERATION_UPDATE_BYTES {
            return Err(invalid("operation progress exceeds limit"));
        }
        let mut state = self.lock_state()?;
        let record = state
            .operations
            .get_mut(operation_id)
            .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "operation not found"))?;
        if record.state != OperationState::Running {
            return Err(invalid("operation is not running"));
        }
        if record.envelope.deadline_at_ms <= now_ms {
            record.state = OperationState::Failed;
            record.receipt = Some(terminal_receipt(
                operation_id,
                OperationState::Failed,
                record.progress.len() as u64 + 1,
                serde_json::json!({"reason": "deadline_exceeded"}),
                now_ms,
            ));
            let snapshot = record.clone();
            self.persist(&snapshot)?;
            return Err(invalid("operation deadline has expired"));
        }
        let expected = record.progress.len() as u64 + 1;
        if sequence < expected {
            let previous = record
                .progress
                .iter()
                .find(|progress| progress.sequence == sequence)
                .ok_or_else(|| {
                    io::Error::new(io::ErrorKind::InvalidData, "invalid progress sequence")
                })?;
            if previous.payload == payload {
                return Ok(previous.clone());
            }
            return Err(io::Error::new(
                io::ErrorKind::AlreadyExists,
                "progress sequence is bound to a different payload",
            ));
        }
        if sequence != expected || record.progress.len() >= MAX_OPERATION_UPDATES {
            return Err(invalid("operation progress sequence is not monotonic"));
        }
        let progress = OperationProgress {
            schema: OPERATION_SCHEMA.to_owned(),
            operation_id: operation_id.to_owned(),
            sequence,
            payload,
        };
        record.progress.push(progress.clone());
        let snapshot = record.clone();
        self.persist(&snapshot)?;
        Ok(progress)
    }

    pub fn request_cancel(&self, operation_id: &str) -> io::Result<OperationAck> {
        self.request_cancel_at(operation_id, super::now_ms())
    }

    pub fn request_cancel_at(&self, operation_id: &str, now_ms: u128) -> io::Result<OperationAck> {
        validate_operation_id(operation_id)?;
        let mut state = self.lock_state()?;
        let current_state = state
            .operations
            .get(operation_id)
            .map(|record| record.state)
            .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "operation not found"))?;
        if current_state.is_terminal() {
            let record = state
                .operations
                .get(operation_id)
                .expect("operation checked above");
            return Ok(ack_for(record, true));
        }
        if current_state == OperationState::Accepted {
            state.queue.retain(|queued| queued != operation_id);
        }
        let record = state
            .operations
            .get_mut(operation_id)
            .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "operation not found"))?;
        record.cancel_requested = true;
        if record.state == OperationState::Accepted {
            record.state = OperationState::Cancelled;
            record.receipt = Some(terminal_receipt(
                operation_id,
                OperationState::Cancelled,
                record.progress.len() as u64 + 1,
                serde_json::json!({"reason": "cancelled_before_start"}),
                now_ms,
            ));
        } else {
            record.state = OperationState::Cancelling;
        }
        let snapshot = record.clone();
        self.persist(&snapshot)?;
        Ok(ack_for(record, false))
    }

    pub fn cancellation_requested(&self, operation_id: &str) -> io::Result<bool> {
        validate_operation_id(operation_id)?;
        let state = self.lock_state()?;
        state
            .operations
            .get(operation_id)
            .map(|record| record.cancel_requested)
            .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "operation not found"))
    }

    pub fn execution_allowed(&self, operation_id: &str) -> io::Result<bool> {
        self.execution_allowed_at(operation_id, super::now_ms())
    }

    pub fn execution_allowed_at(&self, operation_id: &str, now_ms: u128) -> io::Result<bool> {
        validate_operation_id(operation_id)?;
        let mut state = self.lock_state()?;
        let record = state
            .operations
            .get_mut(operation_id)
            .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "operation not found"))?;
        if record.state != OperationState::Running || record.cancel_requested {
            return Ok(false);
        }
        if record.envelope.deadline_at_ms <= now_ms {
            record.state = OperationState::Failed;
            record.receipt = Some(terminal_receipt(
                operation_id,
                OperationState::Failed,
                record.progress.len() as u64 + 1,
                serde_json::json!({"reason": "deadline_exceeded"}),
                now_ms,
            ));
            let snapshot = record.clone();
            self.persist(&snapshot)?;
            return Ok(false);
        }
        Ok(true)
    }

    pub fn finish(
        &self,
        operation_id: &str,
        terminal_state: OperationState,
        outcome: serde_json::Value,
    ) -> io::Result<OperationReceipt> {
        self.finish_at(operation_id, terminal_state, outcome, super::now_ms())
    }

    pub fn finish_at(
        &self,
        operation_id: &str,
        terminal_state: OperationState,
        outcome: serde_json::Value,
        now_ms: u128,
    ) -> io::Result<OperationReceipt> {
        validate_operation_id(operation_id)?;
        if !terminal_state.is_terminal() {
            return Err(invalid("operation finish state must be terminal"));
        }
        let encoded = serde_json::to_vec(&outcome)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        if encoded.len() > MAX_OPERATION_UPDATE_BYTES {
            return Err(invalid("operation receipt exceeds limit"));
        }
        let mut state = self.lock_state()?;
        let record = state
            .operations
            .get_mut(operation_id)
            .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "operation not found"))?;
        if let Some(receipt) = &record.receipt {
            if receipt.state == terminal_state && receipt.outcome == outcome {
                return Ok(receipt.clone());
            }
            return Err(io::Error::new(
                io::ErrorKind::AlreadyExists,
                "operation already has a different terminal receipt",
            ));
        }
        if record.state != OperationState::Running && record.state != OperationState::Cancelling {
            return Err(invalid("operation is not running"));
        }
        if record.cancel_requested && terminal_state != OperationState::Cancelled {
            return Err(io::Error::new(
                io::ErrorKind::AlreadyExists,
                "operation cancellation must win over completion",
            ));
        }
        let (terminal_state, outcome) = if terminal_state != OperationState::Cancelled
            && now_ms >= record.envelope.deadline_at_ms
        {
            (
                OperationState::Failed,
                serde_json::json!({"reason": "deadline_exceeded"}),
            )
        } else {
            (terminal_state, outcome)
        };
        record.state = terminal_state;
        record.receipt = Some(terminal_receipt(
            operation_id,
            terminal_state,
            record.progress.len() as u64 + 1,
            outcome,
            now_ms,
        ));
        let receipt = record.receipt.clone().expect("terminal receipt inserted");
        let snapshot = record.clone();
        self.persist(&snapshot)?;
        Ok(receipt)
    }

    pub fn resume(&self, operation_id: &str, after_sequence: u64) -> io::Result<OperationResume> {
        validate_operation_id(operation_id)?;
        let state = self.lock_state()?;
        let record = state
            .operations
            .get(operation_id)
            .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "operation not found"))?;
        let last_sequence = record.progress.len() as u64;
        if after_sequence > last_sequence {
            return Err(invalid("resume cursor is ahead of operation progress"));
        }
        Ok(OperationResume {
            ack: ack_for(record, true),
            progress: record
                .progress
                .iter()
                .filter(|progress| progress.sequence > after_sequence)
                .cloned()
                .collect(),
            receipt: record.receipt.clone(),
        })
    }

    pub fn queued_len(&self) -> io::Result<usize> {
        Ok(self.lock_state()?.queue.len())
    }

    fn lock_state(&self) -> io::Result<std::sync::MutexGuard<'_, LedgerState>> {
        self.state
            .lock()
            .map_err(|_| io::Error::other("operation ledger lock poisoned"))
    }

    fn persist(&self, record: &PersistedOperation) -> io::Result<()> {
        let path = self.operations_dir.join(format!(
            "{}.json",
            operation_file_id(&record.envelope.operation_id,)
        ));
        let bytes = serde_json::to_vec_pretty(record)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        super::write_atomic(&path, &bytes, "operation record")
    }
}

fn ack_for(record: &PersistedOperation, replayed: bool) -> OperationAck {
    let next_sequence = record
        .receipt
        .as_ref()
        .map_or(record.progress.len() as u64 + 1, |receipt| {
            receipt.sequence + 1
        });
    OperationAck {
        schema: OPERATION_SCHEMA.to_owned(),
        request_id: record.envelope.request_id.clone(),
        operation_id: record.envelope.operation_id.clone(),
        state: record.state,
        replayed,
        next_sequence,
        receipt: record.receipt.clone(),
    }
}

fn terminal_receipt(
    operation_id: &str,
    state: OperationState,
    sequence: u64,
    outcome: serde_json::Value,
    completed_at_ms: u128,
) -> OperationReceipt {
    OperationReceipt {
        schema: OPERATION_SCHEMA.to_owned(),
        operation_id: operation_id.to_owned(),
        state,
        sequence,
        outcome,
        completed_at_ms,
    }
}

fn validate_record(record: &PersistedOperation) -> io::Result<()> {
    record.envelope.validate_identity()?;
    if record.progress.len() > MAX_OPERATION_UPDATES {
        return Err(invalid("operation progress history exceeds limit"));
    }
    for (index, progress) in record.progress.iter().enumerate() {
        if progress.schema != OPERATION_SCHEMA
            || progress.operation_id != record.envelope.operation_id
            || progress.sequence != index as u64 + 1
        {
            return Err(invalid("invalid operation progress identity"));
        }
        let encoded = serde_json::to_vec(&progress.payload)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        if encoded.len() > MAX_OPERATION_UPDATE_BYTES {
            return Err(invalid("operation progress exceeds limit"));
        }
    }
    match (record.state.is_terminal(), record.receipt.as_ref()) {
        (false, Some(_)) => return Err(invalid("non-terminal operation has a receipt")),
        (true, None) => return Err(invalid("terminal operation is missing receipt")),
        (true, Some(receipt)) => {
            if receipt.schema != OPERATION_SCHEMA
                || receipt.operation_id != record.envelope.operation_id
                || receipt.state != record.state
                || !receipt.state.is_terminal()
                || receipt.sequence != record.progress.len() as u64 + 1
            {
                return Err(invalid("invalid operation receipt identity"));
            }
        }
        (false, None) => {}
    }
    Ok(())
}

fn operation_file_id(operation_id: &str) -> String {
    digest_bytes(operation_id.as_bytes())[..32].to_owned()
}

fn digest_json(value: &serde_json::Value) -> io::Result<String> {
    let encoded = serde_json::to_vec(value)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
    Ok(digest_bytes(&encoded))
}

fn digest_bytes(bytes: &[u8]) -> String {
    let mut digest = Sha256::new();
    digest.update(bytes);
    format!("{:x}", digest.finalize())
}

fn validate_token(value: &str, label: &str) -> io::Result<()> {
    if value.is_empty()
        || value.len() > 128
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.' | b':'))
    {
        return Err(invalid(format!("invalid {label} token")));
    }
    Ok(())
}

fn invalid(message: impl Into<String>) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidInput, message.into())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};

    static NEXT_TEST_ID: AtomicU64 = AtomicU64::new(0);

    fn state_dir(name: &str) -> PathBuf {
        let path = std::env::temp_dir().join(format!(
            "codinal-operation-{name}-{}-{}",
            std::process::id(),
            NEXT_TEST_ID.fetch_add(1, Ordering::Relaxed)
        ));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir_all(&path).expect("state directory");
        path
    }

    fn envelope(operation_id: &str, key: &str, payload: serde_json::Value) -> OperationEnvelope {
        OperationEnvelope::new(
            format!("request-{operation_id}"),
            operation_id,
            key,
            2_000,
            "workspace.inspect",
            payload,
        )
        .expect("envelope")
    }

    #[test]
    fn envelope_binds_payload_digest_and_deadline() {
        let envelope = envelope("op-1", "key-1", serde_json::json!({"path": "src"}));
        assert!(envelope.validate(1_000).is_ok());

        let mut tampered = envelope.clone();
        tampered.payload = serde_json::json!({"path": "other"});
        assert_eq!(
            tampered
                .validate(1_000)
                .expect_err("digest mismatch")
                .kind(),
            io::ErrorKind::InvalidData
        );
        assert_eq!(
            envelope.validate(2_000).expect_err("expired").kind(),
            io::ErrorKind::InvalidInput
        );
    }

    #[test]
    fn duplicate_same_payload_replays_original_operation() {
        let root = state_dir("duplicate");
        let ledger = OperationLedger::open(&root, 2).expect("ledger");
        let first = ledger
            .submit_at(
                envelope("op-1", "key-1", serde_json::json!({"path": "src"})),
                1_000,
            )
            .expect("submit");
        let replay = ledger
            .submit_at(
                envelope("op-retry", "key-1", serde_json::json!({"path": "src"})),
                1_100,
            )
            .expect("replay");
        assert_eq!(replay.operation_id, first.operation_id);
        assert_eq!(replay.request_id, first.request_id);
        assert!(replay.replayed);
        assert_eq!(ledger.queued_len().expect("queue"), 1);
        ledger.claim_next_at(1_200).expect("claim").expect("work");
        let receipt = ledger
            .finish_at(
                "op-1",
                OperationState::Succeeded,
                serde_json::json!({"ok": true}),
                1_300,
            )
            .expect("finish");
        let terminal_replay = ledger
            .submit_at(
                envelope("op-after", "key-1", serde_json::json!({"path": "src"})),
                3_000,
            )
            .expect("terminal replay");
        assert_eq!(terminal_replay.state, OperationState::Succeeded);
        assert_eq!(terminal_replay.request_id, first.request_id);
        assert!(terminal_replay.replayed);
        assert_eq!(terminal_replay.receipt, Some(receipt));
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn duplicate_different_payload_fails_closed() {
        let root = state_dir("conflict");
        let ledger = OperationLedger::open(&root, 2).expect("ledger");
        ledger
            .submit_at(
                envelope("op-1", "key-1", serde_json::json!({"path": "src"})),
                1_000,
            )
            .expect("submit");
        assert_eq!(
            ledger
                .submit_at(
                    envelope("op-2", "key-1", serde_json::json!({"path": "other"})),
                    1_100,
                )
                .expect_err("conflict")
                .kind(),
            io::ErrorKind::AlreadyExists
        );
        assert_eq!(ledger.queued_len().expect("queue"), 1);
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn queue_overflow_is_deterministic_and_does_not_persist_rejected_work() {
        let root = state_dir("backpressure");
        let ledger = OperationLedger::open(&root, 1).expect("ledger");
        ledger
            .submit_at(envelope("op-1", "key-1", serde_json::json!({})), 1_000)
            .expect("first submit");
        assert_eq!(
            ledger
                .submit_at(envelope("op-2", "key-2", serde_json::json!({})), 1_000)
                .expect_err("queue full")
                .kind(),
            io::ErrorKind::WouldBlock
        );
        drop(ledger);
        let reopened = OperationLedger::open(&root, 1).expect("reopen");
        assert_eq!(reopened.queued_len().expect("queue"), 1);
        assert_eq!(
            reopened
                .resume("op-2", 0)
                .expect_err("not persisted")
                .kind(),
            io::ErrorKind::NotFound
        );
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn progress_resume_and_terminal_receipt_are_idempotent() {
        let root = state_dir("resume");
        let ledger = OperationLedger::open(&root, 2).expect("ledger");
        let accepted = ledger
            .submit_at(
                envelope("op-1", "key-1", serde_json::json!({"x": 1})),
                1_000,
            )
            .expect("submit");
        assert_eq!(accepted.state, OperationState::Accepted);
        ledger.claim_next_at(1_100).expect("claim").expect("work");
        assert_eq!(
            ledger.resume("op-1", 0).expect("running").ack.state,
            OperationState::Running
        );
        let progress = ledger
            .publish_progress_at("op-1", 1, serde_json::json!({"percent": 50}), 1_150)
            .expect("progress");
        assert_eq!(
            ledger
                .publish_progress_at("op-1", 1, serde_json::json!({"percent": 50}), 1_150)
                .expect("duplicate progress"),
            progress
        );
        assert_eq!(
            ledger
                .publish_progress_at("op-1", 3, serde_json::json!({"percent": 100}), 1_150)
                .expect_err("gap")
                .kind(),
            io::ErrorKind::InvalidInput
        );
        let receipt = ledger
            .finish_at(
                "op-1",
                OperationState::Succeeded,
                serde_json::json!({"changed": []}),
                1_200,
            )
            .expect("finish");
        assert_eq!(
            ledger
                .finish_at(
                    "op-1",
                    OperationState::Succeeded,
                    serde_json::json!({"changed": []}),
                    1_300,
                )
                .expect("duplicate finish"),
            receipt
        );
        let resumed = ledger.resume("op-1", 0).expect("resume");
        assert_eq!(resumed.ack.state, OperationState::Succeeded);
        assert_eq!(resumed.progress, vec![progress]);
        assert_eq!(resumed.receipt, Some(receipt));
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn deadline_is_enforced_before_running_progress() {
        let root = state_dir("deadline-progress");
        let ledger = OperationLedger::open(&root, 2).expect("ledger");
        ledger
            .submit_at(envelope("op-1", "key-1", serde_json::json!({})), 1_000)
            .expect("submit");
        ledger.claim_next_at(1_100).expect("claim").expect("work");
        assert_eq!(
            ledger
                .publish_progress_at("op-1", 1, serde_json::json!({"stage": "late"}), 2_000,)
                .expect_err("expired progress")
                .kind(),
            io::ErrorKind::InvalidInput
        );
        let resumed = ledger.resume("op-1", 0).expect("resume");
        assert_eq!(resumed.ack.state, OperationState::Failed);
        assert_eq!(
            resumed.receipt.expect("deadline receipt").outcome["reason"],
            "deadline_exceeded"
        );
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn deadline_is_enforced_when_running_work_finishes() {
        let root = state_dir("deadline-finish");
        let ledger = OperationLedger::open(&root, 2).expect("ledger");
        ledger
            .submit_at(envelope("op-1", "key-1", serde_json::json!({})), 1_000)
            .expect("submit");
        ledger.claim_next_at(1_100).expect("claim").expect("work");
        let receipt = ledger
            .finish_at(
                "op-1",
                OperationState::Succeeded,
                serde_json::json!({"ok": true}),
                2_000,
            )
            .expect("deadline receipt");
        assert_eq!(receipt.state, OperationState::Failed);
        assert_eq!(receipt.outcome["reason"], "deadline_exceeded");
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn execution_boundary_rejects_expired_or_cancelled_work() {
        let root = state_dir("execution-boundary");
        let ledger = OperationLedger::open(&root, 2).expect("ledger");
        ledger
            .submit_at(envelope("op-1", "key-1", serde_json::json!({})), 1_000)
            .expect("submit");
        ledger.claim_next_at(1_100).expect("claim").expect("work");
        assert!(ledger.execution_allowed_at("op-1", 1_200).expect("allowed"));
        assert!(!ledger.execution_allowed_at("op-1", 2_000).expect("expired"));
        assert_eq!(
            ledger.resume("op-1", 0).expect("resume").ack.state,
            OperationState::Failed
        );

        ledger
            .submit_at(envelope("op-2", "key-2", serde_json::json!({})), 1_000)
            .expect("submit second");
        ledger
            .claim_next_at(1_100)
            .expect("claim second")
            .expect("work");
        ledger.request_cancel_at("op-2", 1_200).expect("cancel");
        assert!(!ledger
            .execution_allowed_at("op-2", 1_300)
            .expect("cancelled"));
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn cancellation_wins_and_restart_recovers_running_work() {
        let root = state_dir("cancel-restart");
        let ledger = OperationLedger::open(&root, 2).expect("ledger");
        ledger
            .submit_at(envelope("op-1", "key-1", serde_json::json!({})), 1_000)
            .expect("submit");
        ledger.claim_next_at(1_100).expect("claim").expect("work");
        let cancelling = ledger.request_cancel_at("op-1", 1_200).expect("cancel");
        assert_eq!(cancelling.state, OperationState::Cancelling);
        assert!(ledger.cancellation_requested("op-1").expect("cancel state"));
        assert_eq!(
            ledger
                .finish_at(
                    "op-1",
                    OperationState::Succeeded,
                    serde_json::json!({"ok": true}),
                    1_300,
                )
                .expect_err("cancellation wins")
                .kind(),
            io::ErrorKind::AlreadyExists
        );
        drop(ledger);
        let reopened = OperationLedger::open(&root, 2).expect("reopen");
        let resumed = reopened.resume("op-1", 0).expect("resume");
        assert_eq!(resumed.ack.state, OperationState::Interrupted);
        assert_eq!(
            resumed.receipt.expect("restart receipt").outcome["reason"],
            "process_restarted"
        );
        let replay = reopened
            .submit_at(envelope("op-retry", "key-1", serde_json::json!({})), 1_400)
            .expect("replay");
        assert_eq!(replay.state, OperationState::Interrupted);
        assert!(replay.replayed);
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn queued_cancellation_never_reaches_worker() {
        let root = state_dir("cancel-queued");
        let ledger = OperationLedger::open(&root, 2).expect("ledger");
        ledger
            .submit_at(envelope("op-1", "key-1", serde_json::json!({})), 1_000)
            .expect("submit");
        let ack = ledger.request_cancel_at("op-1", 1_100).expect("cancel");
        assert_eq!(ack.state, OperationState::Cancelled);
        assert!(ledger.claim_next_at(1_200).expect("claim").is_none());
        let resumed = ledger.resume("op-1", 0).expect("resume");
        assert_eq!(resumed.ack.state, OperationState::Cancelled);
        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn operation_id_validation_is_shared_and_colons_are_supported() {
        let root = state_dir("operation-id-validation");
        let ledger = OperationLedger::open(&root, 2).expect("ledger");
        ledger
            .submit_at(
                envelope("operation:1", "key-1", serde_json::json!({})),
                1_000,
            )
            .expect("submit");
        ledger
            .claim_operation_at("operation:1", 1_100)
            .expect("claim")
            .expect("work");
        ledger
            .publish_progress_at(
                "operation:1",
                1,
                serde_json::json!({"stage": "started"}),
                1_200,
            )
            .expect("progress");
        let receipt = ledger
            .finish_at(
                "operation:1",
                OperationState::Succeeded,
                serde_json::json!({"ok": true}),
                1_300,
            )
            .expect("finish");
        assert_eq!(
            ledger.resume("operation:1", 0).expect("resume").receipt,
            Some(receipt)
        );

        for operation_id in ["", "operation/1"] {
            assert_eq!(
                ledger
                    .publish_progress(operation_id, 1, serde_json::json!({}))
                    .expect_err("invalid progress id")
                    .kind(),
                io::ErrorKind::InvalidInput
            );
            assert_eq!(
                ledger
                    .request_cancel(operation_id)
                    .expect_err("invalid cancel id")
                    .kind(),
                io::ErrorKind::InvalidInput
            );
            assert_eq!(
                ledger
                    .cancellation_requested(operation_id)
                    .expect_err("invalid cancellation id")
                    .kind(),
                io::ErrorKind::InvalidInput
            );
            assert_eq!(
                ledger
                    .finish(
                        operation_id,
                        OperationState::Succeeded,
                        serde_json::json!({}),
                    )
                    .expect_err("invalid finish id")
                    .kind(),
                io::ErrorKind::InvalidInput
            );
            assert_eq!(
                ledger
                    .resume(operation_id, 0)
                    .expect_err("invalid resume id")
                    .kind(),
                io::ErrorKind::InvalidInput
            );
        }
        fs::remove_dir_all(root).expect("cleanup");
    }
}
