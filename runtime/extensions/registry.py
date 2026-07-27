"""SQLite-backed extension registry with provenance verification."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from runtime.storage.migrations import (
    create_private_file,
    prepare_sqlite_database,
    run_sqlite_migrations,
    secure_directory,
    secure_file,
)

from .models import ExtensionPackage, validate_manifest

_SCHEMA_VERSION = 1


def _migrate_to_v1(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS extensions (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            publisher TEXT NOT NULL,
            requested_permissions TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            manifest_hash TEXT NOT NULL,
            manifest TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )
        """
    )


class ExtensionRegistry:
    def __init__(self, data_dir: str | Path) -> None:
        self.base = Path(data_dir).expanduser().resolve()
        secure_directory(self.base)
        self.db_path = self.base / "extensions.db"
        self._lock = threading.RLock()
        previous_version = prepare_sqlite_database(
            self.db_path,
            _SCHEMA_VERSION,
            "extensions",
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

    def register(self, manifest: dict[str, Any]) -> ExtensionPackage:
        validate_manifest(manifest)
        canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        manifest_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        pkg_id = f"{manifest['publisher']}/{manifest['name']}"
        pkg = ExtensionPackage(
            id=pkg_id,
            kind=manifest["kind"],
            name=manifest["name"],
            version=manifest["version"],
            publisher=manifest["publisher"],
            requested_permissions=tuple(manifest.get("requested_permissions", [])),
            enabled=True,
            manifest_hash=manifest_hash,
            manifest=canonical,
        )
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO extensions
                    (id, kind, name, version, publisher,
                     requested_permissions, enabled, manifest_hash, manifest)
                VALUES
                    (:id, :kind, :name, :version, :publisher,
                     :perms, :enabled, :hash, :manifest)
                """,
                {
                    "id": pkg.id,
                    "kind": pkg.kind,
                    "name": pkg.name,
                    "version": pkg.version,
                    "publisher": pkg.publisher,
                    "perms": json.dumps(list(pkg.requested_permissions)),
                    "enabled": 1,
                    "hash": pkg.manifest_hash,
                    "manifest": pkg.manifest,
                },
            )
        return pkg

    def list(self) -> list[ExtensionPackage]:
        with self._lock:
            cursor = self._connection.execute(
                "SELECT * FROM extensions ORDER BY id"
            )
            return [self._row_to_pkg(row) for row in cursor.fetchall()]

    def get(self, package_id: str) -> Optional[ExtensionPackage]:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM extensions WHERE id = ?",
                (package_id,),
            ).fetchone()
            return self._row_to_pkg(row) if row else None

    def set_enabled(self, package_id: str, enabled: bool) -> bool:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE extensions SET enabled = ? WHERE id = ?",
                (1 if enabled else 0, package_id),
            )
            return cursor.rowcount > 0

    def remove(self, package_id: str) -> bool:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "DELETE FROM extensions WHERE id = ?",
                (package_id,),
            )
            return cursor.rowcount > 0

    def verify(self, package_id: str) -> Optional[bool]:
        """Re-compute manifest hash and compare. None if not found."""
        pkg = self.get(package_id)
        if pkg is None:
            return None
        recomputed = hashlib.sha256(pkg.manifest.encode("utf-8")).hexdigest()
        return recomputed == pkg.manifest_hash

    def _row_to_pkg(self, row: sqlite3.Row) -> ExtensionPackage:
        return ExtensionPackage(
            id=row["id"],
            kind=row["kind"],
            name=row["name"],
            version=row["version"],
            publisher=row["publisher"],
            requested_permissions=tuple(json.loads(row["requested_permissions"])),
            enabled=bool(row["enabled"]),
            manifest_hash=row["manifest_hash"],
            manifest=row["manifest"],
        )
