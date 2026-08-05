#!/usr/bin/env python3
"""Seed an isolated v1 storage fixture for a deterministic GPUI capture.

Creates the nine v1 SQLite databases with the real schemas the runtime reads
for sessions/projects/attachments/receipts, seeds a ready-chat-like state
(selected chat with messages, two projects with primary roots, attachments),
and never touches the production data directory. Rerunning replaces the
destination directory atomically.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORAGE_FIXTURE = ROOT / "contracts" / "v1" / "storage.json"


def create_database(path: Path, user_version: int, tables: list[str], name: str) -> None:
    connection = sqlite3.connect(path)
    try:
        if name == "audit.db":
            connection.executescript(
                """
                CREATE TABLE events (
                  seq INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL,
                  domain TEXT NOT NULL, action TEXT NOT NULL, actor TEXT NOT NULL,
                  subject TEXT NOT NULL, payload TEXT NOT NULL,
                  prev_hash TEXT NOT NULL, hash TEXT NOT NULL
                );
                CREATE INDEX events_domain_seq ON events(domain, seq);
                PRAGMA user_version = 1;
                """
            )
        else:
            connection.executescript(f"PRAGMA user_version = {user_version};")
            for table in tables:
                connection.execute(f"CREATE TABLE {table} (id INTEGER)")
        connection.commit()
    finally:
        connection.close()


def seed_codinal_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            DROP TABLE sessions;
            DROP TABLE messages;
            DROP TABLE project_sessions;
            DROP TABLE project_roots;
            DROP TABLE projects;
            DROP TABLE source_attachments;
            DROP TABLE turn_receipts;
            CREATE TABLE sessions (
              session_id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              source_workspace TEXT,
              workspace TEXT,
              agent TEXT NOT NULL,
              model TEXT NOT NULL,
              mode TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              pinned INTEGER NOT NULL DEFAULT 0,
              archived INTEGER NOT NULL DEFAULT 0,
              origin TEXT,
              origin_label TEXT,
              origin_session_id TEXT
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
            CREATE TABLE source_attachments (
              attachment_id TEXT NOT NULL, session_id TEXT NOT NULL,
              path TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'ready', error TEXT,
              attached_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              PRIMARY KEY (session_id, attachment_id), UNIQUE (session_id, path)
            );
            CREATE TABLE turn_receipts (
              turn_id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              outcome TEXT NOT NULL,
              message_count INTEGER NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        sessions = [
            (
                "session-refactor-layout",
                "Refactor the shell layout parser",
                "/Users/codinal/harness-flow",
                "/Users/codinal/harness-flow",
                "agent",
                "opencode-go",
                "code",
                "2026-08-04T09:30:00Z",
                0,
                0,
                None,
                None,
                None,
            ),
            (
                "session-review-capture",
                "Review the capture pipeline",
                "/Users/codinal/harness-flow",
                "/Users/codinal/harness-flow",
                "agent",
                "opencode-go",
                "code",
                "2026-08-04T08:15:00Z",
                0,
                0,
                None,
                None,
                None,
            ),
            (
                "session-keychain-bootstrap",
                "Fix the Keychain bootstrap timeout",
                "/Users/codinal/harness-flow",
                "/Users/codinal/harness-flow",
                "agent",
                "opencode-go",
                "code",
                "2026-08-03T17:45:00Z",
                1,
                0,
                None,
                None,
                None,
            ),
            (
                "session-dark-palette",
                "Add a dark mode palette",
                "/Users/codinal/harness-flow",
                "/Users/codinal/harness-flow",
                "agent",
                "opencode-go",
                "code",
                "2026-08-03T11:20:00Z",
                0,
                0,
                None,
                None,
                None,
            ),
        ]
        connection.executemany(
            """INSERT INTO sessions
               (session_id, title, source_workspace, workspace, agent, model, mode,
                updated_at, pinned, archived, origin, origin_label, origin_session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            sessions,
        )
        messages = [
            (
                "session-refactor-layout",
                0,
                json.dumps(
                    {
                        "role": "user",
                        "content": "Refactor shell_layout so the divider lands on the sidebar edge.",
                    }
                ),
            ),
            (
                "session-refactor-layout",
                1,
                json.dumps(
                    {
                        "role": "assistant",
                        "content": "The navigation strip now spans exactly the sidebar width so the header divider sits on the sidebar edge.",
                    }
                ),
            ),
            (
                "session-review-capture",
                0,
                json.dumps(
                    {
                        "role": "user",
                        "content": "Review the capture wrapper before the next parity gate.",
                    }
                ),
            ),
            (
                "session-keychain-bootstrap",
                0,
                json.dumps(
                    {
                        "role": "user",
                        "content": "The Keychain read timed out at startup; bound the wait.",
                    }
                ),
            ),
        ]
        connection.executemany(
            "INSERT INTO messages (session_id, sequence, payload) VALUES (?, ?, ?)",
            messages,
        )
        projects = [
            ("project-harness-flow", "harness-flow", 0, "2026-08-04T09:00:00Z"),
            ("project-codinal-desktop", "codinal-desktop", 0, "2026-08-02T10:00:00Z"),
        ]
        connection.executemany(
            "INSERT INTO projects (project_id, name, pinned, updated_at) VALUES (?, ?, ?, ?)",
            projects,
        )
        roots = [
            (
                "project-harness-flow",
                "root-primary",
                "/Users/codinal/harness-flow",
                1,
            ),
            (
                "project-codinal-desktop",
                "root-primary",
                "/Users/codinal/codinal-desktop",
                1,
            ),
        ]
        connection.executemany(
            "INSERT INTO project_roots (project_id, root_id, path, is_primary) VALUES (?, ?, ?, ?)",
            roots,
        )
        project_sessions = [
            ("project-harness-flow", "session-refactor-layout"),
            ("project-harness-flow", "session-review-capture"),
        ]
        connection.executemany(
            "INSERT INTO project_sessions (project_id, session_id) VALUES (?, ?)",
            project_sessions,
        )
        attachments = [
            (
                "attachment-shell-layout",
                "session-refactor-layout",
                "/Users/codinal/harness-flow/desktop/gpui/src/shell_layout.rs",
                "shell_layout.rs",
                "rust",
                "ready",
                None,
                "2026-08-04T09:00:00Z",
                "2026-08-04T09:00:00Z",
            ),
            (
                "attachment-icons",
                "session-refactor-layout",
                "/Users/codinal/harness-flow/desktop/gpui/src/icons.rs",
                "icons.rs",
                "rust",
                "ready",
                None,
                "2026-08-04T09:01:00Z",
                "2026-08-04T09:01:00Z",
            ),
        ]
        connection.executemany(
            """INSERT INTO source_attachments
               (attachment_id, session_id, path, name, kind, status, error,
                attached_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            attachments,
        )
        connection.execute(
            """INSERT INTO turn_receipts
               (turn_id, session_id, outcome, message_count, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                "turn-receipt-1",
                "session-refactor-layout",
                json.dumps({"type": "turn_end", "status": "completed"}),
                2,
                "2026-08-04T09:30:00Z",
            ),
        )
        connection.commit()
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        required=True,
        type=Path,
        help="isolated destination data directory (replaced on rerun)",
    )
    args = parser.parse_args()

    destination = args.data_dir.expanduser().resolve()
    if destination.is_dir():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=False)

    fixture = json.loads(STORAGE_FIXTURE.read_text(encoding="utf-8"))
    if fixture.get("fixture_version") != 1 or fixture.get("contract") != "codinal.sqlite.v1":
        print(f"seed: ERROR: unsupported storage fixture: {STORAGE_FIXTURE}", file=sys.stderr)
        return 2
    for database in fixture["databases"]:
        path = destination / database["file"]
        tables = [str(table) for table in database["tables"]]
        create_database(path, database["user_version"], tables, database["file"])
    seed_codinal_db(destination / "codinal.db")

    print(f"seed: wrote v1 fixture data directory: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
