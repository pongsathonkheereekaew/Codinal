"""Shared durable-state migration, backup, and recovery primitives."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from .errors import UnsupportedSchemaVersionError

SQLiteMigration = Callable[[sqlite3.Connection], None]
BackupValidator = Callable[[Path], bool]


def prepare_sqlite_database(
    path: Path,
    supported_version: int,
    store_label: str,
) -> int:
    """Validate, recover if needed, and back up before migration."""
    if not path.exists() or path.stat().st_size == 0:
        return 0
    try:
        version, integrity = _inspect_sqlite(path)
    except sqlite3.DatabaseError as error:
        if getattr(error, "sqlite_errorcode", None) not in {
            sqlite3.SQLITE_CORRUPT,
            sqlite3.SQLITE_NOTADB,
        }:
            raise
        version = _recover_sqlite(
            path,
            supported_version,
            store_label,
        )
    else:
        if integrity != "ok":
            version = _recover_sqlite(
                path,
                supported_version,
                store_label,
            )
    if version < 0:
        raise UnsupportedSchemaVersionError(
            f"{store_label} database schema v{version} is invalid"
        )
    if version > supported_version:
        raise UnsupportedSchemaVersionError(
            f"{store_label} database schema v{version} is newer than "
            f"supported v{supported_version}"
        )
    if path.exists() and version < supported_version:
        backup_database(path, version, supported_version)
    return version


def run_sqlite_migrations(
    connection: sqlite3.Connection,
    current_version: int,
    target_version: int,
    migrations: Mapping[int, SQLiteMigration],
) -> None:
    """Apply every migration in ascending order inside one transaction."""
    if current_version < 0 or target_version < current_version:
        raise UnsupportedSchemaVersionError(
            "SQLite migration versions are invalid"
        )
    expected = set(range(current_version + 1, target_version + 1))
    if expected - set(migrations):
        raise RuntimeError("SQLite migration chain has a version gap")
    with connection:
        for version in range(current_version + 1, target_version + 1):
            migrations[version](connection)
            connection.execute(f"PRAGMA user_version = {version}")


def backup_database(
    path: Path,
    from_version: int,
    to_version: int,
) -> Path:
    target = _allocate_backup(path, from_version, to_version)
    source = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    secure_file(target)
    _fsync_file(target)
    _fsync_directory(target.parent)
    return target


def backup_file(
    path: Path,
    from_version: int,
    to_version: int,
) -> Path:
    target = _allocate_backup(path, from_version, to_version)
    _copy_file(path, target, replace=False)
    _fsync_directory(target.parent)
    return target


def restore_latest_backup(
    path: Path,
    validator: BackupValidator,
) -> Path | None:
    backup_dir = path.parent / "backups"
    if not backup_dir.is_dir():
        return None
    pattern = f"{path.name}.pre-v*-to-v*-*.bak"
    candidates = sorted(
        backup_dir.glob(pattern),
        key=_backup_timestamp,
        reverse=True,
    )
    for candidate in candidates:
        try:
            valid = validator(candidate)
        except (OSError, sqlite3.DatabaseError):
            continue
        if not valid:
            continue
        _copy_file(candidate, path, replace=True)
        _record_recovery_event(
            path,
            "restored_from_backup",
            backup=candidate.name,
        )
        return candidate
    return None


def _backup_timestamp(path: Path) -> str:
    return path.name.rsplit("-", 1)[-1].removesuffix(".bak")


def preserve_corrupt_database(path: Path) -> Path:
    return preserve_corrupt_file(
        path,
        companion_suffixes=("-journal", "-wal", "-shm"),
    )


def preserve_corrupt_file(
    path: Path,
    *,
    companion_suffixes: tuple[str, ...] = (),
) -> Path:
    recovery_dir = path.parent / "recovery"
    secure_directory(recovery_dir)
    secure_file(path)
    target = (
        recovery_dir
        / f"{path.name}.corrupt-{_timestamp()}.preserved"
    )
    os.replace(path, target)
    secure_file(target)
    companions = []
    for suffix in companion_suffixes:
        companion = Path(f"{path}{suffix}")
        if companion.exists():
            secure_file(companion)
            preserved = recovery_dir / f"{target.name}{suffix}"
            os.replace(companion, preserved)
            secure_file(preserved)
            companions.append(preserved)
    _fsync_directory(path.parent)
    _fsync_directory(recovery_dir)
    _record_recovery_event(
        path,
        "preserved_corrupt_state",
        preserved=target.name,
        companions=[item.name for item in companions],
    )
    return target


def secure_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    if stat.S_IMODE(path.stat().st_mode) != 0o700:
        raise PermissionError(f"could not secure directory: {path.name}")


def secure_file(path: Path) -> None:
    os.chmod(path, 0o600)
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise PermissionError(f"could not secure file: {path.name}")


def create_private_file(path: Path) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    os.close(descriptor)
    secure_file(path)


def _recover_sqlite(
    path: Path,
    supported_version: int,
    store_label: str,
) -> int:
    preserve_corrupt_database(path)

    def valid_backup(candidate: Path) -> bool:
        version, integrity = _inspect_sqlite(candidate)
        return version <= supported_version and integrity == "ok"

    restored = restore_latest_backup(path, valid_backup)
    if restored is None:
        return 0
    version, integrity = _inspect_sqlite(path)
    if integrity != "ok":
        raise sqlite3.DatabaseError(
            f"restored {store_label} database failed integrity check"
        )
    return version


def _inspect_sqlite(path: Path) -> tuple[int, str]:
    connection = sqlite3.connect(
        f"{path.as_uri()}?mode=ro",
        uri=True,
        timeout=0.1,
    )
    try:
        integrity_row = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()
        version_row = connection.execute(
            "PRAGMA user_version"
        ).fetchone()
        return (
            int(version_row[0]),
            str(integrity_row[0]) if integrity_row else "",
        )
    finally:
        connection.close()


def _allocate_backup(
    path: Path,
    from_version: int,
    to_version: int,
) -> Path:
    backup_dir = path.parent / "backups"
    secure_directory(backup_dir)
    target = backup_dir / (
        f"{path.name}.pre-v{from_version}-to-v{to_version}-"
        f"{_timestamp()}.bak"
    )
    create_private_file(target)
    return target


def _copy_file(source: Path, target: Path, *, replace: bool) -> None:
    if replace:
        temporary = target.with_name(
            f".{target.name}.restore-{_timestamp()}"
        )
        create_private_file(temporary)
    else:
        temporary = target
    try:
        with source.open("rb") as reader, temporary.open("r+b") as writer:
            while chunk := reader.read(1024 * 1024):
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
        secure_file(temporary)
        if replace:
            os.replace(temporary, target)
            secure_file(target)
            _fsync_directory(target.parent)
    finally:
        if replace:
            temporary.unlink(missing_ok=True)


def _record_recovery_event(
    source: Path,
    action: str,
    **details: object,
) -> None:
    recovery_dir = source.parent / "recovery"
    secure_directory(recovery_dir)
    event_path = recovery_dir / "events.jsonl"
    descriptor = os.open(
        event_path,
        os.O_WRONLY | os.O_CREAT | os.O_APPEND,
        0o600,
    )
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
        json.dump(
            {
                "at": _timestamp(),
                "store": source.name,
                "action": action,
                **details,
            },
            stream,
            separators=(",", ":"),
            sort_keys=True,
        )
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    secure_file(event_path)
    _fsync_directory(recovery_dir)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
