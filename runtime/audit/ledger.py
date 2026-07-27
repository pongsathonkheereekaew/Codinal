"""Hash-chained, append-only SQLite audit ledger.

Reusable across domains. Each event chains on the previous row's hash:

    hash = sha256(prev_hash || H(at || domain || action || actor || subject || payload))

A tampered row breaks `verify_chain()`. Backups, corruption recovery, and
schema migration follow the shared primitives in `runtime.storage.migrations`
(identical to WorkerStore / GoalStore).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from runtime.storage.migrations import (
    create_private_file,
    prepare_sqlite_database,
    run_sqlite_migrations,
    secure_directory,
    secure_file,
)

_SCHEMA_VERSION = 1
_GENESIS_HASH = "0" * 64


def _migrate_to_v1(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            at REAL NOT NULL,
            domain TEXT NOT NULL,
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            subject TEXT NOT NULL,
            payload TEXT NOT NULL,
            prev_hash TEXT NOT NULL,
            hash TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS events_domain_seq
        ON events(domain, seq)
        """
    )


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _event_hash(
    *,
    at: float,
    domain: str,
    action: str,
    actor: str,
    subject: str,
    payload: Any,
    prev_hash: str,
) -> str:
    body = _canonical(
        {
            "at": at,
            "domain": domain,
            "action": action,
            "actor": actor,
            "subject": subject,
            "payload": payload,
        }
    )
    digest = hashlib.sha256()
    digest.update(prev_hash.encode("ascii"))
    digest.update(b"|")
    digest.update(body.encode("utf-8"))
    return digest.hexdigest()


class AuditLedger:
    def __init__(self, data_dir: str | Path) -> None:
        self.base = Path(data_dir).expanduser().resolve()
        secure_directory(self.base)
        self.db_path = self.base / "audit.db"
        self._lock = threading.RLock()
        previous_version = prepare_sqlite_database(
            self.db_path,
            _SCHEMA_VERSION,
            "audit",
        )
        if not self.db_path.exists():
            create_private_file(self.db_path)
        secure_file(self.db_path)
        self._connection = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode = DELETE")
        self._connection.execute("PRAGMA synchronous = FULL")
        run_sqlite_migrations(
            self._connection,
            previous_version,
            _SCHEMA_VERSION,
            {1: _migrate_to_v1},
        )
        secure_file(self.db_path)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _last_hash(self) -> str:
        row = self._connection.execute(
            "SELECT hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return row["hash"] if row is not None else _GENESIS_HASH

    def record(
        self,
        domain: str,
        action: str,
        *,
        actor: str = "system",
        subject: str = "",
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        at = time.time()
        prev_hash = self._last_hash()
        event_hash = _event_hash(
            at=at,
            domain=domain,
            action=action,
            actor=actor,
            subject=subject,
            payload=payload or {},
            prev_hash=prev_hash,
        )
        row = {
            "at": at,
            "domain": domain,
            "action": action,
            "actor": actor,
            "subject": subject,
            "payload": _canonical(payload or {}),
            "prev_hash": prev_hash,
            "hash": event_hash,
        }
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO events
                    (at, domain, action, actor, subject, payload, prev_hash, hash)
                VALUES
                    (:at, :domain, :action, :actor, :subject, :payload, :prev_hash, :hash)
                """,
                row,
            )
        return {
            "at": at,
            "domain": domain,
            "action": action,
            "actor": actor,
            "subject": subject,
            "payload": payload or {},
            "prev_hash": prev_hash,
            "hash": event_hash,
        }

    def list(
        self,
        *,
        domain: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with self._lock:
            if domain is None:
                cursor = self._connection.execute(
                    """
                    SELECT at, domain, action, actor, subject, payload, prev_hash, hash
                    FROM events ORDER BY seq DESC LIMIT ?
                    """,
                    (int(limit),),
                )
            else:
                cursor = self._connection.execute(
                    """
                    SELECT at, domain, action, actor, subject, payload, prev_hash, hash
                    FROM events WHERE domain = ? ORDER BY seq DESC LIMIT ?
                    """,
                    (domain, int(limit)),
                )
            rows = [dict(r) for r in cursor.fetchall()]
        for row in rows:
            row["payload"] = json.loads(row["payload"])
        return rows

    def verify_chain(self) -> bool:
        """Recompute every hash from the genesis; True only if no row was tampered."""
        with self._lock:
            cursor = self._connection.execute(
                """
                SELECT at, domain, action, actor, subject, payload, prev_hash, hash
                FROM events ORDER BY seq ASC
                """
            )
            expected_prev = _GENESIS_HASH
            for row in cursor.fetchall():
                if row["prev_hash"] != expected_prev:
                    return False
                recomputed = _event_hash(
                    at=row["at"],
                    domain=row["domain"],
                    action=row["action"],
                    actor=row["actor"],
                    subject=row["subject"],
                    payload=json.loads(row["payload"]),
                    prev_hash=row["prev_hash"],
                )
                if recomputed != row["hash"]:
                    return False
                expected_prev = row["hash"]
        return True
