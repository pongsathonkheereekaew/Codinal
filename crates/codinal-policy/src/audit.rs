use rusqlite::{Connection, OpenFlags, OptionalExtension, Transaction, TransactionBehavior};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, RwLock};
use std::time::{SystemTime, UNIX_EPOCH};
use zeroize::Zeroizing;

const GENESIS_HASH: &str = "0000000000000000000000000000000000000000000000000000000000000000";
const MAX_PAYLOAD_BYTES: usize = 64 * 1024;
const MAX_EVENTS_PER_READ: usize = 200;
const MAX_CHAIN_EVENTS: usize = 1_000_000;

type ExactSecrets = Vec<(Zeroizing<String>, String)>;

#[derive(Clone, Debug, PartialEq)]
pub struct AuditLedgerInput {
    pub domain: String,
    pub action: String,
    pub actor: String,
    pub subject: String,
    pub payload: serde_json::Value,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct AuditLedgerEvent {
    pub sequence: i64,
    pub at: f64,
    pub domain: String,
    pub action: String,
    pub actor: String,
    pub subject: String,
    pub payload: serde_json::Value,
    pub prev_hash: String,
    pub hash: String,
}

#[derive(Clone, Default)]
pub struct AuditRedactor {
    exact: Arc<RwLock<ExactSecrets>>,
}

impl AuditRedactor {
    pub fn new(secrets: impl IntoIterator<Item = (String, String)>) -> Self {
        let redactor = Self::default();
        redactor.update(secrets);
        redactor
    }

    pub fn update(&self, secrets: impl IntoIterator<Item = (String, String)>) {
        let mut exact = secrets
            .into_iter()
            .filter(|(_, secret)| secret.len() >= 12)
            .map(|(provider, secret)| (Zeroizing::new(secret), format!("[REDACTED:{provider}]")))
            .collect::<Vec<_>>();
        exact.sort_by_key(|item| std::cmp::Reverse(item.0.len()));
        *self
            .exact
            .write()
            .unwrap_or_else(|error| error.into_inner()) = exact;
    }

    fn redact(&self, value: serde_json::Value) -> serde_json::Value {
        match value {
            serde_json::Value::String(value) => serde_json::Value::String(self.redact_text(&value)),
            serde_json::Value::Array(values) => serde_json::Value::Array(
                values.into_iter().map(|value| self.redact(value)).collect(),
            ),
            serde_json::Value::Object(values) => serde_json::Value::Object(
                values
                    .into_iter()
                    .map(|(key, value)| (key, self.redact(value)))
                    .collect(),
            ),
            value => value,
        }
    }

    fn redact_text(&self, text: &str) -> String {
        let mut output = text.to_owned();
        let exact = self.exact.read().unwrap_or_else(|error| error.into_inner());
        for (secret, marker) in exact.iter() {
            output = output.replace(secret.as_str(), marker);
        }
        for (prefix, marker) in [
            ("sk-ant-", "[REDACTED:anthropic]"),
            ("sk-", "[REDACTED:key]"),
            ("AIza", "[REDACTED:gemini]"),
        ] {
            output = redact_prefixed_tokens(&output, prefix, marker);
        }
        output
    }
}

#[derive(Clone)]
pub struct AuditLedger {
    connection: Arc<Mutex<Connection>>,
    redactor: AuditRedactor,
    _database: PathBuf,
}

impl AuditLedger {
    pub fn open(data_dir: &Path, redactor: AuditRedactor) -> io::Result<Self> {
        validate_directory(data_dir)?;
        let database = data_dir.join("audit.db");
        let metadata = fs::symlink_metadata(&database)?;
        if metadata.file_type().is_symlink() || !metadata.is_file() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid audit database",
            ));
        }
        let connection = Connection::open_with_flags(
            &database,
            OpenFlags::SQLITE_OPEN_READ_WRITE | OpenFlags::SQLITE_OPEN_NO_MUTEX,
        )
        .map_err(sqlite_error)?;
        let version = connection
            .query_row("PRAGMA user_version", [], |row| row.get::<_, i64>(0))
            .map_err(sqlite_error)?;
        let integrity = connection
            .query_row("PRAGMA integrity_check", [], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        if version != 1 || integrity != "ok" || !verify_connection(&connection)? {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid audit ledger",
            ));
        }
        connection
            .execute_batch("PRAGMA journal_mode = DELETE; PRAGMA synchronous = FULL;")
            .map_err(sqlite_error)?;
        Ok(Self {
            connection: Arc::new(Mutex::new(connection)),
            redactor,
            _database: database,
        })
    }

    pub fn record(&self, input: AuditLedgerInput) -> io::Result<AuditLedgerEvent> {
        let input = AuditLedgerInput {
            domain: self.redactor.redact_text(&input.domain),
            action: self.redactor.redact_text(&input.action),
            actor: self.redactor.redact_text(&input.actor),
            subject: self.redactor.redact_text(&input.subject),
            payload: self.redactor.redact(input.payload),
        };
        validate_input(&input)?;
        validate_payload(&input.payload)?;
        let at = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|_| io::Error::other("system clock is before Unix epoch"))?
            .as_secs_f64();
        let mut connection = self
            .connection
            .lock()
            .map_err(|_| io::Error::other("audit ledger lock poisoned"))?;
        let transaction = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(sqlite_error)?;
        if !verify_transaction(&transaction)? {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "audit chain is corrupt",
            ));
        }
        let prev_hash = transaction
            .query_row(
                "SELECT hash FROM events ORDER BY seq DESC LIMIT 1",
                [],
                |row| row.get::<_, String>(0),
            )
            .optional()
            .map_err(sqlite_error)?
            .unwrap_or_else(|| GENESIS_HASH.to_owned());
        let event_count = transaction
            .query_row("SELECT COUNT(*) FROM events", [], |row| {
                row.get::<_, i64>(0)
            })
            .map_err(sqlite_error)?;
        if event_count >= MAX_CHAIN_EVENTS as i64 {
            return Err(io::Error::new(
                io::ErrorKind::OutOfMemory,
                "audit ledger capacity reached",
            ));
        }
        let hash = event_hash(at, &input, &input.payload, &prev_hash)?;
        let encoded = canonical_json(&input.payload)?;
        transaction
            .execute(
                "INSERT INTO events (at, domain, action, actor, subject, payload, prev_hash, hash)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
                rusqlite::params![
                    at,
                    input.domain,
                    input.action,
                    input.actor,
                    input.subject,
                    encoded,
                    prev_hash,
                    hash
                ],
            )
            .map_err(sqlite_error)?;
        let sequence = transaction.last_insert_rowid();
        transaction.commit().map_err(sqlite_error)?;
        Ok(AuditLedgerEvent {
            sequence,
            at,
            domain: input.domain,
            action: input.action,
            actor: input.actor,
            subject: input.subject,
            payload: input.payload,
            prev_hash,
            hash,
        })
    }

    pub fn record_policy_event(&self, event: &super::AuditEvent) -> io::Result<AuditLedgerEvent> {
        self.record(AuditLedgerInput {
            domain: event.domain.clone(),
            action: event.action.clone(),
            actor: "system".to_owned(),
            subject: event.subject.clone(),
            payload: serde_json::json!({}),
        })
    }

    pub fn list(&self, domain: Option<&str>, limit: usize) -> io::Result<Vec<AuditLedgerEvent>> {
        if limit == 0 || limit > MAX_EVENTS_PER_READ {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid audit read limit",
            ));
        }
        if let Some(domain) = domain {
            validate_text(domain, 128, false)?;
        }
        let connection = self
            .connection
            .lock()
            .map_err(|_| io::Error::other("audit ledger lock poisoned"))?;
        if !verify_connection(&connection)? {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "audit chain is corrupt",
            ));
        }
        let sql = if domain.is_some() {
            "SELECT seq, at, domain, action, actor, subject, payload, prev_hash, hash
             FROM events WHERE domain = ?1 ORDER BY seq DESC LIMIT ?2"
        } else {
            "SELECT seq, at, domain, action, actor, subject, payload, prev_hash, hash
             FROM events ORDER BY seq DESC LIMIT ?2"
        };
        let mut statement = connection.prepare(sql).map_err(sqlite_error)?;
        let rows = statement
            .query_map(rusqlite::params![domain, limit as i64], decode_event)
            .map_err(sqlite_error)?
            .collect::<rusqlite::Result<Vec<_>>>()
            .map_err(sqlite_error)?;
        Ok(rows)
    }

    pub fn verify_chain(&self) -> io::Result<bool> {
        let connection = self
            .connection
            .lock()
            .map_err(|_| io::Error::other("audit ledger lock poisoned"))?;
        verify_connection(&connection)
    }
}

fn verify_connection(connection: &Connection) -> io::Result<bool> {
    verify_rows(connection)
}

fn verify_transaction(transaction: &Transaction<'_>) -> io::Result<bool> {
    verify_rows(transaction)
}

fn verify_rows(connection: &Connection) -> io::Result<bool> {
    let mut statement = connection
        .prepare("SELECT seq, at, domain, action, actor, subject, payload, prev_hash, hash FROM events ORDER BY seq")
        .map_err(sqlite_error)?;
    let mut rows = statement.query([]).map_err(sqlite_error)?;
    let mut expected_sequence = None;
    let mut expected_prev = GENESIS_HASH.to_owned();
    let mut count = 0_usize;
    while let Some(row) = rows.next().map_err(sqlite_error)? {
        let sequence = row.get::<_, i64>(0).map_err(sqlite_error)?;
        let at = row.get::<_, f64>(1).map_err(sqlite_error)?;
        let input = AuditLedgerInput {
            domain: row.get(2).map_err(sqlite_error)?,
            action: row.get(3).map_err(sqlite_error)?,
            actor: row.get(4).map_err(sqlite_error)?,
            subject: row.get(5).map_err(sqlite_error)?,
            payload: serde_json::from_str(&row.get::<_, String>(6).map_err(sqlite_error)?)
                .map_err(json_error)?,
        };
        let prev_hash = row.get::<_, String>(7).map_err(sqlite_error)?;
        let stored_hash = row.get::<_, String>(8).map_err(sqlite_error)?;
        let sequence_matches = expected_sequence.is_none_or(|expected| sequence == expected);
        if !sequence_matches || prev_hash != expected_prev {
            return Ok(false);
        }
        let computed = event_hash(at, &input, &input.payload, &prev_hash)?;
        if computed != stored_hash {
            return Ok(false);
        }
        expected_sequence = Some(sequence + 1);
        expected_prev = stored_hash;
        count += 1;
        if count > MAX_CHAIN_EVENTS {
            return Ok(false);
        }
    }
    let sqlite_sequence = connection
        .query_row(
            "SELECT seq FROM sqlite_sequence WHERE name = 'events'",
            [],
            |row| row.get::<_, i64>(0),
        )
        .optional()
        .map_err(sqlite_error)?
        .unwrap_or(0);
    let last_sequence = expected_sequence.map_or(0, |next| next - 1);
    Ok(sqlite_sequence == last_sequence)
}

fn event_hash(
    at: f64,
    input: &AuditLedgerInput,
    payload: &serde_json::Value,
    prev_hash: &str,
) -> io::Result<String> {
    let body = serde_json::json!({
        "at": at,
        "domain": input.domain,
        "action": input.action,
        "actor": input.actor,
        "subject": input.subject,
        "payload": payload,
    });
    let canonical = canonical_json(&body)?;
    let mut digest = Sha256::new();
    digest.update(prev_hash.as_bytes());
    digest.update(b"|");
    digest.update(canonical.as_bytes());
    Ok(format!("{:x}", digest.finalize()))
}

fn canonical_json(value: &serde_json::Value) -> io::Result<String> {
    let mut canonical = String::new();
    write_canonical_json(value, &mut canonical)?;
    Ok(canonical)
}

fn write_canonical_json(value: &serde_json::Value, output: &mut String) -> io::Result<()> {
    match value {
        serde_json::Value::Null => output.push_str("null"),
        serde_json::Value::Bool(value) => output.push_str(if *value { "true" } else { "false" }),
        serde_json::Value::Number(value) => output.push_str(&python_number(value)?),
        serde_json::Value::String(value) => {
            let encoded = serde_json::to_string(value).map_err(json_error)?;
            output.push_str(&ascii_escaped_json(&encoded));
        }
        serde_json::Value::Array(values) => {
            output.push('[');
            for (index, value) in values.iter().enumerate() {
                if index > 0 {
                    output.push(',');
                }
                write_canonical_json(value, output)?;
            }
            output.push(']');
        }
        serde_json::Value::Object(values) => {
            output.push('{');
            let mut entries = values.iter().collect::<Vec<_>>();
            entries.sort_unstable_by(|left, right| left.0.cmp(right.0));
            for (index, (key, value)) in entries.into_iter().enumerate() {
                if index > 0 {
                    output.push(',');
                }
                let encoded_key = serde_json::to_string(key).map_err(json_error)?;
                output.push_str(&ascii_escaped_json(&encoded_key));
                output.push(':');
                write_canonical_json(value, output)?;
            }
            output.push('}');
        }
    }
    Ok(())
}

fn ascii_escaped_json(encoded: &str) -> String {
    let mut canonical = String::with_capacity(encoded.len());
    for character in encoded.chars() {
        if character.is_ascii() {
            canonical.push(character);
        } else {
            let codepoint = character as u32;
            if codepoint <= 0xffff {
                use std::fmt::Write;
                write!(canonical, "\\u{codepoint:04x}").expect("writing to String cannot fail");
            } else {
                use std::fmt::Write;
                let adjusted = codepoint - 0x1_0000;
                let high = 0xd800 + (adjusted >> 10);
                let low = 0xdc00 + (adjusted & 0x3ff);
                write!(canonical, "\\u{high:04x}\\u{low:04x}")
                    .expect("writing to String cannot fail");
            }
        }
    }
    canonical
}

fn python_number(number: &serde_json::Number) -> io::Result<String> {
    if number.is_i64() || number.is_u64() {
        return Ok(number.to_string());
    }
    let encoded = number.to_string();
    let (negative, unsigned) = encoded
        .strip_prefix('-')
        .map_or((false, encoded.as_str()), |value| (true, value));
    let (mantissa, exponent) = if let Some((mantissa, exponent)) = unsigned.split_once(['e', 'E']) {
        let exponent = exponent.parse::<i32>().map_err(|_| {
            io::Error::new(io::ErrorKind::InvalidData, "invalid JSON number exponent")
        })?;
        (mantissa, exponent)
    } else {
        (unsigned, 0_i32)
    };
    let decimal_index = mantissa.find('.').unwrap_or(mantissa.len()) as i32 + exponent;
    let mut digits = mantissa.replace('.', "");
    let leading = digits.bytes().take_while(|byte| *byte == b'0').count();
    if leading == digits.len() {
        return Ok(if negative { "-0.0" } else { "0.0" }.to_owned());
    }
    digits.drain(..leading);
    let decimal_index = decimal_index - leading as i32;
    let scientific_exponent = decimal_index - 1;
    let mut output = String::new();
    if negative {
        output.push('-');
    }
    if !(-4..16).contains(&scientific_exponent) {
        output.push(digits.as_bytes()[0] as char);
        if digits.len() > 1 {
            output.push('.');
            output.push_str(&digits[1..]);
        }
        output.push('e');
        output.push(if scientific_exponent >= 0 { '+' } else { '-' });
        use std::fmt::Write;
        write!(output, "{:02}", scientific_exponent.unsigned_abs())
            .expect("writing to String cannot fail");
    } else if decimal_index <= 0 {
        output.push_str("0.");
        output.extend(std::iter::repeat_n('0', (-decimal_index) as usize));
        output.push_str(&digits);
    } else if decimal_index as usize >= digits.len() {
        output.push_str(&digits);
        output.extend(std::iter::repeat_n(
            '0',
            decimal_index as usize - digits.len(),
        ));
        output.push_str(".0");
    } else {
        let (whole, fraction) = digits.split_at(decimal_index as usize);
        output.push_str(whole);
        output.push('.');
        output.push_str(fraction);
    }
    Ok(output)
}

fn validate_input(input: &AuditLedgerInput) -> io::Result<()> {
    validate_text(&input.domain, 128, false)?;
    validate_text(&input.action, 128, false)?;
    validate_text(&input.actor, 128, false)?;
    validate_text(&input.subject, 256, true)
}

fn validate_text(value: &str, maximum: usize, empty_allowed: bool) -> io::Result<()> {
    if (!empty_allowed && value.is_empty())
        || value.len() > maximum
        || value.contains(['\r', '\n', '\0'])
    {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid audit metadata",
        ))
    } else {
        Ok(())
    }
}

fn validate_payload(payload: &serde_json::Value) -> io::Result<()> {
    let mut nodes = 0_usize;
    let mut pending = vec![(payload, 0_usize)];
    while let Some((value, depth)) = pending.pop() {
        nodes += 1;
        if nodes > 10_000 || depth > 32 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "audit payload exceeds structural limit",
            ));
        }
        match value {
            serde_json::Value::Array(values) => {
                pending.extend(values.iter().map(|value| (value, depth + 1)));
            }
            serde_json::Value::Object(values) => {
                if values.keys().any(|key| key.len() > 256) {
                    return Err(io::Error::new(
                        io::ErrorKind::InvalidInput,
                        "audit payload key exceeds limit",
                    ));
                }
                pending.extend(values.values().map(|value| (value, depth + 1)));
            }
            _ => {}
        }
    }
    let encoded = canonical_json(payload)?;
    if encoded.len() > MAX_PAYLOAD_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "audit payload exceeds limit",
        ));
    }
    Ok(())
}

fn decode_event(row: &rusqlite::Row<'_>) -> rusqlite::Result<AuditLedgerEvent> {
    let payload: String = row.get(6)?;
    let payload = serde_json::from_str(&payload).map_err(|error| {
        rusqlite::Error::FromSqlConversionFailure(6, rusqlite::types::Type::Text, Box::new(error))
    })?;
    Ok(AuditLedgerEvent {
        sequence: row.get(0)?,
        at: row.get(1)?,
        domain: row.get(2)?,
        action: row.get(3)?,
        actor: row.get(4)?,
        subject: row.get(5)?,
        payload,
        prev_hash: row.get(7)?,
        hash: row.get(8)?,
    })
}

fn redact_prefixed_tokens(text: &str, prefix: &str, marker: &str) -> String {
    let mut output = String::with_capacity(text.len());
    let mut remaining = text;
    while let Some(position) = remaining.find(prefix) {
        output.push_str(&remaining[..position]);
        let candidate = &remaining[position..];
        let length = candidate
            .bytes()
            .take_while(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-'))
            .count();
        if length >= prefix.len() + 20 {
            output.push_str(marker);
            remaining = &candidate[length..];
        } else {
            output.push_str(prefix);
            remaining = &candidate[prefix.len()..];
        }
    }
    output.push_str(remaining);
    output
}

fn validate_directory(path: &Path) -> io::Result<()> {
    let metadata = fs::symlink_metadata(path)?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid audit data directory",
        ));
    }
    Ok(())
}

fn sqlite_error(error: rusqlite::Error) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, error)
}

fn json_error(error: serde_json::Error) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, error)
}

#[cfg(test)]
mod tests {
    use super::{event_hash, AuditLedger, AuditLedgerInput, AuditRedactor, GENESIS_HASH};
    use rusqlite::Connection;
    use std::fs;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::thread;

    static NEXT_DIR: AtomicU64 = AtomicU64::new(0);

    fn ledger_directory() -> PathBuf {
        let path = std::env::temp_dir().join(format!(
            "codinal-audit-test-{}-{}",
            std::process::id(),
            NEXT_DIR.fetch_add(1, Ordering::Relaxed)
        ));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir(&path).expect("directory");
        let connection = Connection::open(path.join("audit.db")).expect("database");
        connection
            .execute_batch(
                "CREATE TABLE events (
                   seq INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL,
                   domain TEXT NOT NULL, action TEXT NOT NULL, actor TEXT NOT NULL,
                   subject TEXT NOT NULL, payload TEXT NOT NULL,
                   prev_hash TEXT NOT NULL, hash TEXT NOT NULL
                 );
                 CREATE INDEX events_domain_seq ON events(domain, seq);
                 PRAGMA user_version = 1;",
            )
            .expect("schema");
        path
    }

    fn input(action: &str, payload: serde_json::Value) -> AuditLedgerInput {
        AuditLedgerInput {
            domain: "policy".to_owned(),
            action: action.to_owned(),
            actor: "runtime".to_owned(),
            subject: "session-1".to_owned(),
            payload,
        }
    }

    #[test]
    fn chain_survives_restart_and_reads_newest_first() {
        let path = ledger_directory();
        let ledger = AuditLedger::open(&path, AuditRedactor::default()).expect("ledger");
        let first = ledger
            .record(input(
                "approval_denied",
                serde_json::json!({"risk": "exec"}),
            ))
            .expect("first");
        let second = ledger
            .record(input(
                "approval_consumed",
                serde_json::json!({"risk": "write_local"}),
            ))
            .expect("second");
        assert_eq!(first.prev_hash, GENESIS_HASH);
        assert_eq!(second.prev_hash, first.hash);
        drop(ledger);

        let restarted = AuditLedger::open(&path, AuditRedactor::default()).expect("restart");
        assert!(restarted.verify_chain().expect("verify"));
        let events = restarted.list(Some("policy"), 10).expect("events");
        assert_eq!(events[0].action, "approval_consumed");
        assert_eq!(events[1].action, "approval_denied");
        fs::remove_dir_all(path).expect("cleanup");
    }

    #[test]
    fn payload_is_recursively_redacted_before_persistence() {
        let path = ledger_directory();
        let secret = "provider-secret-0123456789";
        let ledger = AuditLedger::open(
            &path,
            AuditRedactor::new([("openai".to_owned(), secret.to_owned())]),
        )
        .expect("ledger");
        let event = ledger
            .record(input(
                "approval_denied",
                serde_json::json!({
                    "nested": [format!("token={secret}"), {"key": "sk-abcdefghijklmnopqrstuvwxyz"}]
                }),
            ))
            .expect("event");
        assert!(!event.payload.to_string().contains(secret));
        assert!(event.payload.to_string().contains("REDACTED"));
        drop(ledger);
        let bytes = fs::read(path.join("audit.db")).expect("database bytes");
        assert!(!bytes
            .windows(secret.len())
            .any(|window| window == secret.as_bytes()));
        fs::remove_dir_all(path).expect("cleanup");
    }

    #[test]
    fn rotated_secrets_and_metadata_are_redacted_before_persistence() {
        let path = ledger_directory();
        let redactor = AuditRedactor::default();
        let ledger = AuditLedger::open(&path, redactor.clone()).expect("ledger");
        let secret = "rotated-secret-0123456789";
        redactor.update([("rotated".to_owned(), secret.to_owned())]);
        let event = ledger
            .record(AuditLedgerInput {
                domain: "policy".to_owned(),
                action: format!("denied-{secret}"),
                actor: format!("actor-{secret}"),
                subject: format!("subject-{secret}"),
                payload: serde_json::json!({"token": secret}),
            })
            .expect("event");
        let encoded = serde_json::to_string(&event).expect("event json");
        assert!(!encoded.contains(secret));
        assert!(encoded.contains("REDACTED:rotated"));
        drop(ledger);
        let bytes = fs::read(path.join("audit.db")).expect("database bytes");
        assert!(!bytes
            .windows(secret.len())
            .any(|window| window == secret.as_bytes()));
        fs::remove_dir_all(path).expect("cleanup");
    }

    #[test]
    fn valid_python_style_pruned_chain_opens_with_preserved_sequences() {
        let path = ledger_directory();
        let ledger = AuditLedger::open(&path, AuditRedactor::default()).expect("ledger");
        for action in ["first", "second", "third"] {
            ledger
                .record(input(action, serde_json::json!({})))
                .expect("event");
        }
        drop(ledger);

        let connection = Connection::open(path.join("audit.db")).expect("database");
        connection
            .execute("DELETE FROM events WHERE seq = 1", [])
            .expect("prune");
        let mut previous = GENESIS_HASH.to_owned();
        for sequence in [2_i64, 3_i64] {
            let (at, domain, action, actor, subject, payload): (
                f64,
                String,
                String,
                String,
                String,
                String,
            ) = connection
                .query_row(
                    "SELECT at, domain, action, actor, subject, payload FROM events WHERE seq = ?1",
                    [sequence],
                    |row| {
                        Ok((
                            row.get(0)?,
                            row.get(1)?,
                            row.get(2)?,
                            row.get(3)?,
                            row.get(4)?,
                            row.get(5)?,
                        ))
                    },
                )
                .expect("row");
            let payload = serde_json::from_str(&payload).expect("payload");
            let input = AuditLedgerInput {
                domain,
                action,
                actor,
                subject,
                payload,
            };
            let hash = event_hash(at, &input, &input.payload, &previous).expect("hash");
            connection
                .execute(
                    "UPDATE events SET prev_hash = ?1, hash = ?2 WHERE seq = ?3",
                    rusqlite::params![previous, hash, sequence],
                )
                .expect("rechain");
            previous = hash;
        }
        drop(connection);

        let ledger = AuditLedger::open(&path, AuditRedactor::default()).expect("pruned ledger");
        let events = ledger.list(None, 10).expect("events");
        assert_eq!(events[0].sequence, 3);
        assert_eq!(events[1].sequence, 2);
        fs::remove_dir_all(path).expect("cleanup");
    }

    #[test]
    fn tamper_and_tail_truncation_fail_closed_on_restart() {
        for truncate in [false, true] {
            let path = ledger_directory();
            let ledger = AuditLedger::open(&path, AuditRedactor::default()).expect("ledger");
            ledger
                .record(input("first", serde_json::json!({})))
                .expect("first");
            ledger
                .record(input("second", serde_json::json!({})))
                .expect("second");
            drop(ledger);
            let connection = Connection::open(path.join("audit.db")).expect("database");
            if truncate {
                connection
                    .execute("DELETE FROM events WHERE seq = 2", [])
                    .expect("truncate");
            } else {
                connection
                    .execute("UPDATE events SET subject = 'forged' WHERE seq = 1", [])
                    .expect("tamper");
            }
            drop(connection);
            assert!(AuditLedger::open(&path, AuditRedactor::default()).is_err());
            fs::remove_dir_all(path).expect("cleanup");
        }
    }

    #[test]
    fn concurrent_appends_share_one_verified_chain() {
        let path = ledger_directory();
        let ledger = AuditLedger::open(&path, AuditRedactor::default()).expect("ledger");
        let threads = (0..16)
            .map(|index| {
                let ledger = ledger.clone();
                thread::spawn(move || {
                    ledger
                        .record(input(
                            &format!("event-{index}"),
                            serde_json::json!({"index": index}),
                        ))
                        .expect("append");
                })
            })
            .collect::<Vec<_>>();
        for thread in threads {
            thread.join().expect("thread");
        }
        assert!(ledger.verify_chain().expect("verify"));
        assert_eq!(ledger.list(None, 200).expect("events").len(), 16);
        fs::remove_dir_all(path).expect("cleanup");
    }

    #[test]
    fn approval_outcome_persists_compatible_metadata() {
        let path = ledger_directory();
        let ledger = AuditLedger::open(&path, AuditRedactor::default()).expect("ledger");
        let event = super::super::AuditEvent::new("policy", "approval_denied", "session-1")
            .expect("policy event");
        let persisted = ledger.record_policy_event(&event).expect("persist");
        assert_eq!(persisted.domain, "policy");
        assert_eq!(persisted.action, "approval_denied");
        assert_eq!(persisted.actor, "system");
        assert_eq!(persisted.subject, "session-1");
        fs::remove_dir_all(path).expect("cleanup");
    }

    #[test]
    fn hash_matches_the_python_v1_canonical_vector() {
        let input = input(
            "approval_denied",
            serde_json::json!({"risk": "exec", "nested": [1, true]}),
        );
        assert_eq!(
            event_hash(1_700_000_000.25, &input, &input.payload, GENESIS_HASH).expect("hash"),
            "f6eec45e4c11107e2ab79c0d609fb831c4c77b4137bed4a73073969fdbc04591"
        );
    }

    #[test]
    fn unicode_hash_matches_the_python_v1_canonical_vector() {
        let input = AuditLedgerInput {
            domain: "นโยบาย".to_owned(),
            action: "อนุมัติ".to_owned(),
            actor: "ระบบ".to_owned(),
            subject: "งาน😀".to_owned(),
            payload: serde_json::json!({"ข้อความ": "สวัสดี"}),
        };
        assert_eq!(
            event_hash(1_700_000_000.25, &input, &input.payload, GENESIS_HASH).expect("hash"),
            "5e7573e9ce33ab1963e1ca8ee4af12df2b3652f29bcc0347d31bba2d27c80e43"
        );
    }

    #[test]
    fn floating_point_hash_matches_the_python_v1_canonical_vector() {
        let input = AuditLedgerInput {
            domain: "policy".to_owned(),
            action: "float_vector".to_owned(),
            actor: "runtime".to_owned(),
            subject: "session-1".to_owned(),
            payload: serde_json::json!({
                "small": 1e-7,
                "large": 1e20,
                "whole": 1.0,
                "fixed": 1e-4,
            }),
        };
        assert_eq!(
            event_hash(1_700_000_000.25, &input, &input.payload, GENESIS_HASH).expect("hash"),
            "1239b873ead5dde6d4f2a61afeac9b8aba50031ccaa51dc1e49bd53c45d52300"
        );
    }
}
