"""Immutable filesystem catalog for portable integrations."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Any, Mapping

from runtime.plugins.translator import _validated_manifest


_STATUSES = frozenset({"enabled-compatible", "installed-with-gaps", "rejected"})
_INDEX = ".catalog-index.sqlite3"


@dataclass(frozen=True)
class CatalogRecord:
    integration_id: str
    version: str
    digest: str
    source_digest: str
    status: str
    path: Path
    provenance: dict[str, Any]


class IntegrationCatalog:
    """Filesystem is canonical; SQLite is rebuilt from it on every startup."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._staging = self.root / ".staging"
        self._staging.mkdir(exist_ok=True)
        self._connection = sqlite3.connect(self.root / _INDEX)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS integrations "
            "(id TEXT, version TEXT, digest TEXT, source_digest TEXT, status TEXT, "
            "path TEXT, provenance TEXT, PRIMARY KEY(id, version))"
        )
        self._sync_index()

    def close(self) -> None:
        self._connection.close()

    def stage_and_activate(
        self,
        manifest: Mapping[str, Any],
        *,
        provenance: Mapping[str, Any],
        status: str = "enabled-compatible",
        diagnostics: tuple[str, ...] = (),
    ) -> CatalogRecord:
        if status not in _STATUSES:
            raise ValueError(f"unsupported catalog status: {status}")
        if (status == "enabled-compatible") != (not diagnostics):
            raise ValueError("catalog status and diagnostics disagree")
        provenance_data = _provenance(provenance)
        data, canonical, source_canonical, migration = _validated_manifest(manifest)
        if migration:
            raise ValueError("catalog requires a codinal.integration.v1 manifest")
        publisher, name = _identity(data)
        version = data["version"]
        _safe_segment(version, "version")
        target = self.root / publisher / name / version
        _reject_symlinked_parent(self.root, publisher, name)
        if target.exists():
            raise FileExistsError(f"immutable catalog version already exists: {target}")
        record = CatalogRecord(
            integration_id=data["id"], version=version,
            digest=_digest(canonical), source_digest=_digest(source_canonical),
            status=status, path=target, provenance=provenance_data,
        )
        stage = Path(tempfile.mkdtemp(prefix="integration-", dir=self._staging))
        try:
            (stage / "integration.json").write_bytes(canonical)
            (stage / "provenance.json").write_text(
                json.dumps(record.provenance, sort_keys=True, separators=(",", ":"), allow_nan=False), encoding="utf-8"
            )
            (stage / "status.json").write_text(
                json.dumps({"status": status, "diagnostics": diagnostics}, allow_nan=False), encoding="utf-8"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage, target)
            self._upsert(record)
            return record
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            if target.exists():
                shutil.rmtree(target)
            raise

    def get(self, integration_id: str, version: str) -> CatalogRecord | None:
        row = self._connection.execute(
            "SELECT * FROM integrations WHERE id = ? AND version = ?", (integration_id, version)
        ).fetchone()
        return self._from_row(row) if row else None

    def load_manifest(self, record: CatalogRecord) -> dict[str, Any]:
        """Revalidate canonical bytes at the only runtime catalog boundary."""
        return json.loads((record.path / "integration.json").read_bytes())

    def _sync_index(self) -> None:
        records = [self._read(path) for path in self.root.glob("*/*/*/integration.json")]
        with self._connection:
            self._connection.execute("DELETE FROM integrations")
            for record in records:
                self._upsert(record)

    def _read(self, path: Path) -> CatalogRecord:
        canonical = path.read_bytes()
        manifest = json.loads(canonical)
        data, normalized, source, migration = _validated_manifest(manifest)
        if migration or normalized != canonical or source != canonical:
            raise ValueError(f"catalog manifest integrity check failed: {path}")
        publisher, name = _identity(data)
        folder = path.parent
        _safe_segment(data["version"], "version")
        _reject_symlinked_parent(self.root, publisher, name)
        if folder != self.root / publisher / name / data["version"]:
            raise ValueError(f"catalog path does not match manifest identity: {folder}")
        provenance = _provenance(json.loads((folder / "provenance.json").read_text(encoding="utf-8")))
        status_data = json.loads((folder / "status.json").read_text(encoding="utf-8"))
        status = status_data["status"]
        diagnostics = tuple(status_data.get("diagnostics", []))
        if status not in _STATUSES:
            raise ValueError(f"invalid catalog status: {status}")
        if (status == "enabled-compatible") != (not diagnostics):
            raise ValueError("catalog status and diagnostics disagree")
        return CatalogRecord(data["id"], data["version"], _digest(canonical), _digest(canonical), status, folder, provenance)

    def _upsert(self, record: CatalogRecord) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO integrations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (record.integration_id, record.version, record.digest, record.source_digest,
             record.status, str(record.path), json.dumps(record.provenance, sort_keys=True)),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> CatalogRecord:
        return CatalogRecord(row["id"], row["version"], row["digest"], row["source_digest"], row["status"], Path(row["path"]), json.loads(row["provenance"]))


def _identity(manifest: Mapping[str, Any]) -> tuple[str, str]:
    publisher = manifest["publisher"]
    _safe_segment(publisher, "publisher")
    prefix = f"{publisher}/"
    if not manifest["id"].startswith(prefix):
        raise ValueError("integration id must begin with its publisher")
    name = manifest["id"][len(prefix):]
    _safe_segment(name, "integration id")
    return publisher, name


def _safe_segment(value: str, label: str) -> None:
    if not value or "/" in value or "\\" in value or value in {".", ".."}:
        raise ValueError(f"{label} must contain one safe name segment")


def _reject_symlinked_parent(root: Path, publisher: str, name: str) -> None:
    for path in (root / publisher, root / publisher / name):
        if path.is_symlink():
            raise ValueError(f"catalog path contains symlink: {path}")


def _provenance(value: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(value)
    for field in ("source", "issuer", "signature"):
        if not isinstance(data.get(field), str) or not data[field]:
            raise ValueError(f"provenance.{field} must be a non-empty string")
    try:
        json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("provenance must contain JSON values") from error
    return data


def _digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"
