# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Andrew Ng
# Extracted and adapted from andrewyng/openworker:
# coworker/server/manager.py @
# 54b4bfd82d75704a4079ecea4f8f622aa152dbde.
"""Session lifecycle service with injected storage and runtime collaborators."""

from __future__ import annotations

import base64
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Protocol

from .models import RootDir, SessionRecord

_ARTIFACT_SUFFIXES = {
    ".md",
    ".markdown",
    ".html",
    ".htm",
    ".txt",
    ".json",
    ".csv",
    ".tsv",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".pdf",
    ".xlsx",
    ".xls",
    ".pptx",
    ".ppt",
    ".pptm",
    ".docx",
    ".doc",
    ".docm",
}
_MAX_BINARY_PREVIEW = 25 * 1024 * 1024


class SessionStore(Protocol):
    def load(self, session_id: str) -> SessionRecord | None: ...

    def save(self, record: SessionRecord) -> None: ...

    def list(self, *, workspace: Optional[str] = None) -> list[SessionRecord]: ...

    def rename(self, session_id: str, title: str) -> bool: ...

    def set_flags(
        self,
        session_id: str,
        *,
        pinned: Optional[bool] = None,
        archived: Optional[bool] = None,
    ) -> bool: ...

    def delete(self, session_id: str) -> bool: ...

    def set_extra_roots(
        self, session_id: str, extra_roots: list[dict[str, Any]]
    ) -> None: ...

    def touch_workspace(self, path: str) -> None: ...


class SessionEngine(Protocol):
    messages: list[dict[str, Any]]
    roots: list[RootDir]

    def request_interrupt(self) -> None: ...


class EngineFactory(Protocol):
    def __call__(self, request: EngineRequest) -> SessionEngine: ...


class SessionSnapshotter(Protocol):
    def __call__(
        self, session_id: str, engine: SessionEngine
    ) -> Optional[SessionRecord]: ...


class DeleteCallback(Protocol):
    def __call__(self, session_id: str) -> None: ...


class ArtifactOpener(Protocol):
    def __call__(self, path: Path, mode: str) -> None: ...


@dataclass(frozen=True)
class EngineRequest:
    session_id: str
    workspace: Path
    record: Optional[SessionRecord]
    model: str
    mode: str
    agent: str
    messages: list[dict[str, Any]]
    extra_roots: list[dict[str, Any]]
    grants: dict[str, Any]


class SessionService:
    def __init__(
        self,
        store: SessionStore,
        *,
        scratch_base: str | Path,
        engine_factory: Optional[EngineFactory] = None,
        snapshotter: Optional[SessionSnapshotter] = None,
        delete_callbacks: Iterable[DeleteCallback] = (),
        artifact_opener: Optional[ArtifactOpener] = None,
        default_model: str = "gpt-5.6-sol",
        default_model_provider: Optional[Callable[[], str]] = None,
        default_mode: str = "interactive",
    ) -> None:
        self._store = store
        self._scratch_base = Path(scratch_base).expanduser().resolve()
        self._engine_factory = engine_factory
        self._snapshotter = snapshotter
        self._delete_callbacks = tuple(delete_callbacks)
        self._artifact_opener = artifact_opener
        self._default_model = default_model
        self._default_model_provider = default_model_provider
        self._default_mode = default_mode
        self._engines: dict[str, SessionEngine] = {}

    def attach_engine(self, session_id: str, engine: SessionEngine) -> None:
        self._engines[session_id] = engine

    def get_engine(
        self,
        session_id: str,
        *,
        workspace: Optional[str | Path] = None,
        agent: str = "code",
    ) -> Optional[SessionEngine]:
        engine = self._engines.get(session_id)
        if engine is not None:
            return engine
        if self._engine_factory is None:
            raise RuntimeError("no engine factory configured")
        record = self._store.load(session_id)
        selected_workspace = record.workspace if record else workspace
        if not selected_workspace:
            return None
        resolved_workspace = Path(selected_workspace).expanduser().resolve()
        if not resolved_workspace.is_dir():
            return None
        self._store.touch_workspace(str(resolved_workspace))
        default_model = self._default_model
        if record is None and self._default_model_provider is not None:
            default_model = (
                (self._default_model_provider() or "").strip()
                or self._default_model
            )
        engine = self._engine_factory(
            EngineRequest(
                session_id=session_id,
                workspace=resolved_workspace,
                record=record,
                model=record.model if record else default_model,
                mode=record.mode if record else self._default_mode,
                agent=record.agent if record else agent,
                messages=list(record.messages) if record else [],
                extra_roots=list(record.extra_roots) if record else [],
                grants=dict(record.grants) if record else {},
            )
        )
        self._engines[session_id] = engine
        return engine

    def persist(self, session_id: str) -> bool:
        engine = self._engines.get(session_id)
        if engine is None or self._snapshotter is None:
            return False
        record = self._snapshotter(session_id, engine)
        if record is None:
            return False
        self._store.save(record)
        return True

    def messages(self, session_id: str) -> list[dict[str, Any]]:
        engine = self._engines.get(session_id)
        if engine is not None:
            return list(engine.messages)
        record = self._store.load(session_id)
        return list(record.messages) if record else []

    def list_sessions(
        self, *, workspace: Optional[str] = None
    ) -> list[dict[str, Any]]:
        return [
            {
                "session_id": record.session_id,
                "title": record.title or "New session",
                "workspace": record.workspace,
                "agent": record.agent,
                "model": record.model,
                "mode": record.mode,
                "updated_at": record.updated_at,
                "messages": record.message_count,
                "pinned": record.pinned,
                "archived": record.archived,
                "origin": record.origin,
                "origin_label": record.origin_label,
            }
            for record in self._store.list(workspace=workspace)
            if not record.session_id.startswith("__")
        ]

    def rename(self, session_id: str, title: str) -> dict[str, Any]:
        if session_id.startswith("__"):
            return {"ok": False, "error": "internal sessions cannot be renamed"}
        normalized = " ".join((title or "").split())[:120]
        return {
            "ok": self._store.rename(session_id, normalized),
            "session_id": session_id,
            "title": normalized,
        }

    def set_flags(
        self,
        session_id: str,
        *,
        pinned: Optional[bool] = None,
        archived: Optional[bool] = None,
    ) -> dict[str, Any]:
        if session_id.startswith("__"):
            return {
                "ok": False,
                "error": "internal sessions cannot be modified here",
            }
        return {
            "ok": self._store.set_flags(
                session_id,
                pinned=pinned,
                archived=archived,
            ),
            "session_id": session_id,
        }

    def delete(self, session_id: str) -> dict[str, Any]:
        if session_id.startswith("__"):
            return {"ok": False, "error": "internal sessions cannot be deleted here"}

        engine = self._engines.pop(session_id, None)
        if engine is not None:
            engine.request_interrupt()

        record = self._store.load(session_id)
        ok = self._store.delete(session_id)
        cleanup_errors = []
        if ok:
            for callback in self._delete_callbacks:
                try:
                    callback(session_id)
                except Exception as exc:
                    cleanup_errors.append(str(exc))
            cleanup_error = self._remove_scratch_workspace(record)
            if cleanup_error:
                cleanup_errors.append(cleanup_error)

        result: dict[str, Any] = {"ok": ok, "session_id": session_id}
        if cleanup_errors:
            result["cleanup_errors"] = cleanup_errors
        return result

    def roots(self, session_id: str) -> list[dict[str, Any]]:
        engine = self._engines.get(session_id)
        live_roots = getattr(engine, "roots", None) if engine is not None else None
        if live_roots is not None:
            return [
                self._root_view(root, primary=index == 0)
                for index, root in enumerate(live_roots)
            ]

        record = self._store.load(session_id)
        if record is None or not record.workspace:
            return []
        roots = [
            RootDir(
                path=record.workspace,
                writable=True,
                label=Path(record.workspace).name,
            )
        ]
        roots.extend(
            RootDir(
                path=root["path"],
                writable=bool(root.get("writable", False)),
                label=str(root.get("label", "")),
            )
            for root in record.extra_roots
        )
        return [
            self._root_view(root, primary=index == 0)
            for index, root in enumerate(roots)
        ]

    def add_root(
        self, session_id: str, path: str, *, writable: bool = False
    ) -> dict[str, Any]:
        resolved = Path(path).expanduser()
        if not resolved.is_dir():
            return {"ok": False, "error": f"not a directory: {path}"}
        resolved = resolved.resolve()
        current = self.roots(session_id)
        if current and Path(current[0]["path"]).resolve() == resolved:
            return {"ok": True, "roots": current}
        engine = self._engines.get(session_id)
        live_roots = getattr(engine, "roots", None) if engine is not None else None

        if live_roots is not None:
            matching = next(
                (root for root in live_roots if root.path == resolved),
                None,
            )
            if matching is None:
                live_roots.append(
                    RootDir(path=resolved, writable=writable)
                )
            else:
                matching.writable = writable
            extra_roots = self._extra_root_records(live_roots)
        else:
            record = self._store.load(session_id)
            if record is None:
                return {"ok": False, "error": "session not found"}
            extra_roots = [
                root
                for root in record.extra_roots
                if Path(str(root["path"])).expanduser().resolve() != resolved
            ]
            extra_roots.append(
                {
                    "path": str(resolved),
                    "writable": writable,
                    "label": resolved.name,
                }
            )

        self._store.set_extra_roots(session_id, extra_roots)
        self._store.touch_workspace(str(resolved))
        return {"ok": True, "roots": self.roots(session_id)}

    def remove_root(self, session_id: str, path: str) -> dict[str, Any]:
        resolved = Path(path).expanduser().resolve()
        current = self.roots(session_id)
        if current and Path(current[0]["path"]).resolve() == resolved:
            return {
                "ok": False,
                "error": "cannot remove the primary workspace",
            }

        engine = self._engines.get(session_id)
        live_roots = getattr(engine, "roots", None) if engine is not None else None
        if live_roots is not None:
            live_roots[:] = [root for root in live_roots if root.path != resolved]
            extra_roots = self._extra_root_records(live_roots)
        else:
            record = self._store.load(session_id)
            if record is None:
                return {"ok": False, "error": "session not found"}
            extra_roots = [
                root
                for root in record.extra_roots
                if Path(str(root["path"])).expanduser().resolve() != resolved
            ]
        self._store.set_extra_roots(session_id, extra_roots)
        return {"ok": True, "roots": self.roots(session_id)}

    def list_artifacts(self, session_id: str) -> list[dict[str, Any]]:
        record = self._store.load(session_id)
        if record is None or not record.workspace:
            return []
        root = Path(record.workspace).expanduser().resolve()
        if not root.is_dir():
            return []
        artifacts = []
        for path in root.rglob("*"):
            try:
                relative = path.relative_to(root)
                if any(
                    part.startswith(".")
                    or part in {"node_modules", "target", "dist", "__pycache__"}
                    for part in relative.parts
                ):
                    continue
                resolved = path.resolve()
                resolved.relative_to(root)
                if (
                    not resolved.is_file()
                    or resolved.suffix.lower() not in _ARTIFACT_SUFFIXES
                ):
                    continue
                stat = resolved.stat()
                artifacts.append(
                    {
                        "path": str(relative),
                        "abs_path": str(resolved),
                        "name": resolved.name,
                        "kind": _artifact_kind(resolved),
                        "size": stat.st_size,
                        "modified_at": stat.st_mtime,
                    }
                )
            except (OSError, ValueError):
                continue
        artifacts.sort(key=lambda artifact: artifact["modified_at"], reverse=True)
        return artifacts[:80]

    def read_artifact(self, session_id: str, path: str) -> dict[str, Any]:
        target, error = self._artifact_target(session_id, path)
        if target is None:
            return {"ok": False, "error": error}
        kind = _artifact_kind(target)
        if kind == "office":
            return {"ok": True, "path": path, "kind": kind}
        if kind in {"image", "pdf", "sheet"}:
            if target.stat().st_size > _MAX_BINARY_PREVIEW:
                return {"ok": False, "error": "file too large to preview"}
            mime = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif",
                ".pdf": "application/pdf",
                ".xlsx": (
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                ".xls": "application/vnd.ms-excel",
            }.get(target.suffix.lower(), "application/octet-stream")
            encoded = base64.b64encode(target.read_bytes()).decode("ascii")
            return {
                "ok": True,
                "path": path,
                "kind": kind,
                "data_url": f"data:{mime};base64,{encoded}",
            }
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return {"ok": False, "error": "binary file cannot be previewed"}
        return {
            "ok": True,
            "path": path,
            "kind": kind,
            "content": text[:500_000],
            "truncated": len(text) > 500_000,
        }

    def reveal_artifact(
        self, session_id: str, path: str, *, mode: str = "reveal"
    ) -> dict[str, Any]:
        if mode not in {"open", "reveal"}:
            return {"ok": False, "error": "mode must be open or reveal"}
        target, error = self._artifact_target(session_id, path)
        if target is None:
            return {"ok": False, "error": error}
        if self._artifact_opener is None:
            return {"ok": False, "error": "artifact opener is not configured"}
        try:
            self._artifact_opener(target, mode)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True}

    def _remove_scratch_workspace(
        self, record: Optional[SessionRecord]
    ) -> Optional[str]:
        if record is None or not record.workspace:
            return None
        workspace = Path(record.workspace)
        try:
            resolved = workspace.resolve()
            if (
                resolved.is_relative_to(self._scratch_base)
                and resolved != self._scratch_base
                and resolved.is_dir()
            ):
                shutil.rmtree(resolved)
        except OSError as exc:
            return str(exc)
        return None

    def _artifact_target(
        self, session_id: str, path: str
    ) -> tuple[Optional[Path], Optional[str]]:
        record = self._store.load(session_id)
        if record is None or not record.workspace:
            return None, "no workspace"
        root = Path(record.workspace).expanduser().resolve()
        target = (root / path).expanduser().resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return None, "path escapes workspace"
        if not target.is_file():
            return None, "not found"
        return target, None

    @staticmethod
    def _root_view(root: RootDir, *, primary: bool) -> dict[str, Any]:
        return {
            "path": str(root.path),
            "writable": bool(root.writable),
            "label": root.label,
            "primary": primary,
            "exists": root.path.is_dir(),
        }

    @staticmethod
    def _extra_root_records(roots: list[RootDir]) -> list[dict[str, Any]]:
        return [
            {
                "path": str(root.path),
                "writable": bool(root.writable),
                "label": root.label,
            }
            for root in roots[1:]
        ]


def _artifact_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return "image"
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".xlsx", ".xls"}:
        return "sheet"
    if suffix in {".pptx", ".ppt", ".pptm", ".docx", ".doc", ".docm"}:
        return "office"
    if suffix in {".csv", ".tsv"}:
        return "csv"
    if suffix in {".py", ".js", ".ts", ".tsx", ".css", ".json"}:
        return "code"
    return "text"
