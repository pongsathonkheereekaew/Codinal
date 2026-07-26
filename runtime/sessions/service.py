# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Andrew Ng
# Extracted and adapted from andrewyng/openworker:
# coworker/server/manager.py @
# 54b4bfd82d75704a4079ecea4f8f622aa152dbde.
"""Session lifecycle service with injected storage and runtime collaborators."""

from __future__ import annotations

import base64
import copy
import itertools
import os
import re
import shutil
import stat
import time
from uuid import uuid4
from dataclasses import dataclass, replace
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Iterable,
    Optional,
    Protocol,
)

from runtime.events import Event
from runtime.policy import Mode
from runtime.search import RepositorySearchCoordinator

from .models import (
    RootDir,
    SessionRecord,
    SessionSearchHit,
    TurnCheckpoint,
    TurnStatus,
)
from .context import is_project_context_part, make_project_context_item

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
_MAX_CONTEXT_FILE_BYTES = 256 * 1024
_MAX_CONTEXT_FOLDER_BYTES = 512 * 1024
_MAX_CONTEXT_FOLDER_FILE_BYTES = 64 * 1024
_MAX_CONTEXT_FOLDER_ENTRIES = 200
_MAX_CONTEXT_FOLDER_DEPTH = 12
_TREE_IGNORE_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "target",
}
_TREE_IGNORE_CASEFOLD = {name.casefold() for name in _TREE_IGNORE_NAMES}
_MAX_TREE_SCAN = 5_000


class SessionStore(Protocol):
    def load(self, session_id: str) -> SessionRecord | None: ...

    def save(self, record: SessionRecord) -> None: ...

    def save_checkpoint(
        self,
        record: SessionRecord,
        *,
        completed_tool_call_id: str | None = None,
    ) -> None: ...

    def list(self, *, workspace: Optional[str] = None) -> list[SessionRecord]: ...

    def search(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[SessionSearchHit]: ...

    def export_records(self) -> list[SessionRecord]: ...

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

    def delete_approval_decision(
        self,
        session_id: str,
        tool_call_id: str,
    ) -> None: ...


class SessionEngine(Protocol):
    messages: list[dict[str, Any]]
    roots: list[RootDir]

    def run(
        self,
        user_input: str | list[dict[str, Any]],
        *,
        source: dict[str, Any] | None = None,
    ) -> AsyncIterator[Event]: ...

    def request_interrupt(self) -> None: ...


class EngineFactory(Protocol):
    def __call__(self, request: EngineRequest) -> SessionEngine: ...


class SessionSnapshotter(Protocol):
    def __call__(
        self, session_id: str, engine: SessionEngine
    ) -> Optional[SessionRecord]: ...


class DeleteCallback(Protocol):
    def __call__(self, session_id: str) -> None: ...


class SessionCleanupError(RuntimeError):
    """A stable callback error that may be shown to the user."""


class ArtifactOpener(Protocol):
    def __call__(self, path: Path, mode: str, descriptor: int) -> None: ...


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
        self._project_search = RepositorySearchCoordinator()

    def attach_engine(self, session_id: str, engine: SessionEngine) -> None:
        self._engines[session_id] = engine

    def get_engine(
        self,
        session_id: str,
        *,
        workspace: Optional[str | Path] = None,
        agent: str = "code",
        mode: str | None = None,
        model: str | None = None,
    ) -> Optional[SessionEngine]:
        engine = self._engines.get(session_id)
        if engine is not None:
            live_roots = getattr(engine, "roots", None)
            if live_roots is not None:
                self._reconcile_live_roots(engine, live_roots)
            if mode is not None:
                engine.permissions.mode = Mode(mode)
                self.persist(session_id)
            return engine
        if self._engine_factory is None:
            raise RuntimeError("no engine factory configured")
        record = self._store.load(session_id)
        selected_workspace = (
            (record.source_workspace or record.workspace)
            if record
            else workspace
        )
        if not selected_workspace:
            return None
        if record is not None and self._primary_root(record) is None:
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
        selected_model = (
            (model or "").strip()
            if record is None and (model or "").strip()
            else record.model if record else default_model
        )
        selected_mode = (
            mode or record.mode
            if record
            else mode or self._default_mode
        )
        durable_extra_roots = (
            self._durable_extra_roots(record) if record else []
        )
        active_extra_roots = [
            active
            for root in durable_extra_roots
            for active in _validated_extra_roots([root])
        ]
        engine = self._engine_factory(
            EngineRequest(
                session_id=session_id,
                workspace=resolved_workspace,
                record=record,
                model=selected_model,
                mode=selected_mode,
                agent=record.agent if record else agent,
                messages=list(record.messages) if record else [],
                extra_roots=(
                    active_extra_roots
                ),
                grants=dict(record.grants) if record else {},
            )
        )
        try:
            engine.durable_extra_roots = durable_extra_roots
        except (AttributeError, TypeError):
            pass
        self._engines[session_id] = engine
        if record is not None and mode is not None:
            self.persist(session_id)
        return engine

    def persist(self, session_id: str) -> bool:
        record = self._snapshot(session_id)
        if record is None:
            return False
        self._store.save(record)
        return True

    def persist_checkpoint(
        self,
        session_id: str,
        *,
        checkpoint: TurnCheckpoint,
        completed_tool_call_id: str | None = None,
    ) -> bool:
        record = self._snapshot(session_id)
        if record is None:
            return False
        updated = replace(
            record,
            turn_checkpoint=checkpoint,
        )
        if completed_tool_call_id is None:
            self._store.save(updated)
        else:
            self._store.save_checkpoint(
                updated,
                completed_tool_call_id=completed_tool_call_id,
            )
        return True

    def persist_terminal_checkpoint(
        self,
        session_id: str,
        *,
        checkpoint: TurnCheckpoint,
        turn_id: str,
        outcome: dict[str, Any],
    ) -> bool:
        record = self._snapshot(session_id)
        if record is None:
            return False
        updated = replace(record, turn_checkpoint=checkpoint)
        self._store.save(
            updated,
            terminal_receipt={
                "turn_id": turn_id,
                "session_id": session_id,
                "outcome": dict(outcome),
                "message_count": len(updated.messages),
            },
        )
        return True

    def turn_receipt(
        self,
        turn_id: str,
    ) -> dict[str, Any] | None:
        return self._store.load_turn_receipt(turn_id)

    def latest_turn_receipt(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:
        return self._store.latest_turn_receipt(session_id)

    def recoverable_sessions(self) -> list[SessionRecord]:
        return [
            record
            for record in self._store.list()
            if not record.session_id.startswith("__")
            and record.turn_checkpoint.status is not TurnStatus.IDLE
        ]

    def restore_conversation(
        self,
        session_id: str,
        *,
        message_count: int,
    ) -> bool:
        if (
            not isinstance(message_count, int)
            or message_count < 0
        ):
            raise ValueError("invalid checkpoint message count")
        record = self._store.load(session_id)
        if record is None:
            return False
        if record.turn_checkpoint.status is not TurnStatus.IDLE:
            raise RuntimeError("session recovery is still active")
        if message_count > len(record.messages):
            raise ValueError("checkpoint exceeds conversation history")
        restored_messages = list(record.messages[:message_count])
        self._store.save(
            replace(
                record,
                messages=restored_messages,
                message_count=message_count,
            )
        )
        engine = self._engines.get(session_id)
        if engine is not None:
            engine.messages[:] = restored_messages
        return True

    def clear_approval_decision(
        self,
        session_id: str,
        tool_call_id: str,
    ) -> None:
        self._store.delete_approval_decision(
            session_id,
            tool_call_id,
        )

    def mark_recovery_failed(self, session_id: str) -> bool:
        record = self._store.load(session_id)
        if record is None:
            return False
        if (
            record.messages
            and record.messages[-1].get("role") == "notice"
            and record.messages[-1].get("kind") == "recovery_error"
        ):
            return True
        self._store.save(
            replace(
                record,
                messages=[
                    *record.messages,
                    {
                        "role": "notice",
                        "kind": "recovery_error",
                        "text": (
                            "Codinal could not resume this interrupted "
                            "turn. The recovery checkpoint was preserved."
                        ),
                        "ts": time.time(),
                    },
                ],
            )
        )
        return True

    def _snapshot(self, session_id: str) -> SessionRecord | None:
        engine = self._engines.get(session_id)
        if engine is None or self._snapshotter is None:
            return None
        record = self._snapshotter(session_id, engine)
        return record

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
                "workspace": record.source_workspace or record.workspace,
                "agent": record.agent,
                "model": record.model,
                "mode": record.mode,
                "updated_at": record.updated_at,
                "messages": record.message_count,
                "pinned": record.pinned,
                "archived": record.archived,
                "origin": record.origin,
                "origin_label": record.origin_label,
                "origin_session_id": record.origin_session_id,
            }
            for record in self._store.list(workspace=workspace)
            if (
                not record.session_id.startswith("__")
                and record.origin != "worker"
            )
        ]

    def search_sessions(
        self,
        query: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        results = []
        for hit in self._store.search(query, limit=limit):
            record = hit.record
            if (
                record.session_id.startswith("__")
                or record.origin == "worker"
            ):
                continue
            results.append(
                {
                    "session_id": record.session_id,
                    "title": record.title or "New session",
                    "workspace": (
                        record.source_workspace or record.workspace
                    ),
                    "agent": record.agent,
                    "model": record.model,
                    "mode": record.mode,
                    "updated_at": record.updated_at,
                    "messages": record.message_count,
                    "pinned": record.pinned,
                    "archived": record.archived,
                    "origin": record.origin,
                    "origin_label": record.origin_label,
                    "origin_session_id": record.origin_session_id,
                    "match_excerpt": hit.excerpt,
                    "match_message_index": hit.message_index,
                }
            )
        return results

    def fork(
        self,
        session_id: str,
        *,
        message_index: int,
        new_session_id: str | None = None,
    ) -> dict[str, Any]:
        return self._branch_conversation(
            session_id,
            message_index=message_index,
            new_session_id=new_session_id,
            origin="fork",
            title_prefix="Fork of ",
        )

    def create_worker_session(
        self,
        session_id: str,
        *,
        worker_id: str,
        child_session_id: str,
        model: str,
    ) -> dict[str, Any]:
        """Create an authority-empty child session for one background worker."""
        if (
            session_id.startswith("__")
            or child_session_id.startswith("__")
            or self._store.load(child_session_id) is not None
        ):
            return {"ok": False, "error": "could not allocate session"}
        parent = self._snapshot(session_id) or self._store.load(session_id)
        if parent is None:
            return {"ok": False, "error": "session not found"}
        source_workspace = parent.workspace
        try:
            root = RootDir(source_workspace, writable=True)
        except (OSError, ValueError):
            return {"ok": False, "error": "workspace is unavailable"}
        worker = SessionRecord(
            session_id=child_session_id,
            workspace=str(root.path),
            workspace_device=root.device,
            workspace_inode=root.inode,
            source_workspace=str(root.path),
            model=model,
            mode=Mode.AUTO.value,
            messages=[],
            title=f"Worker · {worker_id}"[:120],
            agent="worker",
            message_count=0,
            extra_roots=[],
            grants={},
            origin="worker",
            origin_label=worker_id,
            origin_session_id=parent.session_id,
        )
        self._store.save(worker)
        return {
            "ok": True,
            "session_id": child_session_id,
            "source_session_id": session_id,
            "workspace": str(root.path),
        }

    def side_conversation(
        self,
        session_id: str,
        *,
        message_index: int,
        new_session_id: str | None = None,
    ) -> dict[str, Any]:
        return self._branch_conversation(
            session_id,
            message_index=message_index,
            new_session_id=new_session_id,
            origin="side_conversation",
            title_prefix="Side conversation · ",
        )

    def _branch_conversation(
        self,
        session_id: str,
        *,
        message_index: int,
        new_session_id: str | None,
        origin: str,
        title_prefix: str,
    ) -> dict[str, Any]:
        if session_id.startswith("__"):
            return {"ok": False, "error": "session not found"}
        if (
            isinstance(message_index, bool)
            or not isinstance(message_index, int)
            or message_index < 0
        ):
            return {"ok": False, "error": "invalid message index"}
        record = self._snapshot(session_id) or self._store.load(session_id)
        if record is None:
            return {"ok": False, "error": "session not found"}
        if message_index >= len(record.messages):
            return {"ok": False, "error": "invalid message index"}
        if not _is_safe_fork_boundary(record.messages, message_index):
            return {"ok": False, "error": "invalid fork boundary"}
        target_id = new_session_id
        if target_id is None:
            for _attempt in range(4):
                candidate = f"session-{uuid4()}"
                if self._store.load(candidate) is None:
                    target_id = candidate
                    break
        if target_id is None or self._store.load(target_id) is not None:
            return {"ok": False, "error": "could not allocate session"}
        source_workspace = record.source_workspace or record.workspace
        try:
            fork_root = RootDir(source_workspace, writable=True)
        except (OSError, ValueError):
            return {"ok": False, "error": "workspace is unavailable"}
        forked = SessionRecord(
            session_id=target_id,
            workspace=source_workspace,
            workspace_device=fork_root.device,
            workspace_inode=fork_root.inode,
            source_workspace=source_workspace,
            model=record.model,
            mode=record.mode,
            messages=copy.deepcopy(
                record.messages[: message_index + 1]
            ),
            title=f"{title_prefix}{record.title or 'New session'}"[:120],
            agent=record.agent,
            message_count=message_index + 1,
            extra_roots=[],
            grants={},
            origin=origin,
            origin_label=record.title or record.session_id,
            origin_session_id=(
                record.session_id if origin == "side_conversation" else None
            ),
        )
        self._store.save(forked)
        public_session = {
            "session_id": target_id,
            "title": forked.title,
            "workspace": source_workspace,
            "agent": forked.agent,
            "model": forked.model,
            "mode": forked.mode,
            "updated_at": forked.updated_at,
            "messages": len(forked.messages),
            "pinned": False,
            "archived": False,
            "origin": forked.origin,
            "origin_label": forked.origin_label,
            "origin_session_id": forked.origin_session_id,
        }
        return {
            "ok": True,
            "session_id": target_id,
            "source_session_id": session_id,
            "message_count": message_index + 1,
            "session": public_session,
        }

    def export_markdown(self, session_id: str) -> dict[str, Any]:
        if session_id.startswith("__"):
            return {"ok": False, "error": "session not found"}
        record = self._snapshot(session_id) or self._store.load(session_id)
        if record is None:
            return {"ok": False, "error": "session not found"}
        title = record.title or "Codinal conversation"
        sections = [f"# {title}"]
        for message in record.messages:
            role = message.get("role")
            if role not in {"user", "assistant"}:
                continue
            content, attachments = _visible_markdown_content(
                message.get("content")
            )
            if not content and not attachments:
                continue
            body = content
            if attachments:
                labels = "\n".join(
                    f"_Attachment: {filename}_" for filename in attachments
                )
                body = f"{body}\n\n{labels}" if body else labels
            sections.append(
                f"## {'You' if role == 'user' else 'Codinal'}\n\n{body}"
            )
        content = "\n\n".join(sections).rstrip() + "\n"
        return {
            "ok": True,
            "filename": f"{_safe_markdown_slug(title)}.md",
            "content": content,
        }

    def export(self) -> dict[str, Any]:
        """Return the stable v1 conversation export."""
        sessions = []
        for record in self._store.export_records():
            if record.session_id.startswith("__"):
                continue
            sessions.append(
                {
                    "session_id": record.session_id,
                    "workspace": record.workspace,
                    "source_workspace": record.source_workspace,
                    "model": record.model,
                    "mode": record.mode,
                    "messages": list(record.messages),
                    "title": record.title,
                    "agent": record.agent,
                    "updated_at": record.updated_at,
                    "extra_roots": list(record.extra_roots),
                    "grants": dict(record.grants),
                    "pinned": record.pinned,
                    "archived": record.archived,
                    "origin": record.origin,
                    "origin_label": record.origin_label,
                }
            )
        return {
            "export_version": 1,
            "sessions": sessions,
        }

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

    def set_model(self, session_id: str, model: str) -> dict[str, Any]:
        if session_id.startswith("__"):
            return {"ok": False, "error": "internal session"}
        normalized = (model or "").strip()
        if (
            not normalized
            or len(normalized.encode("utf-8")) > 256
            or any(ord(character) < 32 for character in normalized)
        ):
            return {"ok": False, "error": "invalid model"}
        engine = self._engines.get(session_id)
        if engine is not None:
            previous = str(getattr(engine, "model", ""))
            engine.model = normalized
            if not self.persist(session_id):
                engine.model = previous
                return {"ok": False, "error": "model persistence failed"}
        else:
            record = self._store.load(session_id)
            if record is None:
                return {"ok": False, "error": "session not found"}
            self._store.save(replace(record, model=normalized))
        return {
            "ok": True,
            "session_id": session_id,
            "model": normalized,
        }

    def delete(self, session_id: str) -> dict[str, Any]:
        if session_id.startswith("__"):
            return {"ok": False, "error": "internal sessions cannot be deleted here"}

        engine = self._engines.pop(session_id, None)
        if engine is not None:
            engine.request_interrupt()

        record = self._store.load(session_id)
        cleanup_errors = []
        if record is not None:
            for callback in self._delete_callbacks:
                try:
                    callback(session_id)
                except SessionCleanupError as exc:
                    cleanup_errors.append(str(exc))
                except Exception:
                    cleanup_errors.append("cleanup failed")
        if cleanup_errors:
            return {
                "ok": False,
                "session_id": session_id,
                "cleanup_errors": cleanup_errors,
            }

        ok = self._store.delete(session_id)
        if ok:
            cleanup_error = self._remove_scratch_workspace(record)
            if cleanup_error:
                cleanup_errors.append("scratch cleanup failed")

        result: dict[str, Any] = {"ok": ok, "session_id": session_id}
        if cleanup_errors:
            result["cleanup_errors"] = cleanup_errors
        return result

    def roots(self, session_id: str) -> list[dict[str, Any]]:
        engine = self._engines.get(session_id)
        live_roots = getattr(engine, "roots", None) if engine is not None else None
        if live_roots is not None:
            self._reconcile_live_roots(engine, live_roots)
            roots = [
                self._root_view(
                    root,
                    primary=index == 0,
                    available=_root_available(root),
                )
                for index, root in enumerate(live_roots)
            ]
            configured = {
                str(root.get("path", "")): root
                for root in getattr(engine, "durable_extra_roots", [])
            }
            visible = {root["path"] for root in roots}
            roots.extend(
                _inactive_root_view(root)
                for path, root in configured.items()
                if path and path not in visible
            )
            source_workspace = getattr(engine, "source_workspace", None)
            if roots and source_workspace:
                roots[0]["label"] = (
                    Path(source_workspace).name or str(source_workspace)
                )
            return roots

        record = self._store.load(session_id)
        if record is None or not record.workspace:
            return []
        primary = self._primary_root(record)
        if primary is None:
            return []
        primary.label = Path(
            record.source_workspace or record.workspace
        ).name
        active_roots = [
            RootDir(
                path=root["path"],
                writable=bool(root.get("writable", False)),
                label=str(root.get("label", "")),
                device=int(root["_device"]),
                inode=int(root["_inode"]),
            )
            for root in self._record_extra_roots(record)
        ]
        roots = [primary, *active_roots]
        views = [
            self._root_view(root, primary=index == 0)
            for index, root in enumerate(roots)
        ]
        visible = {root["path"] for root in views}
        views.extend(
            _inactive_root_view(root)
            for root in self._durable_extra_roots(record)
            if str(root.get("path", "")) not in visible
        )
        return views

    def add_root(
        self, session_id: str, path: str, *, writable: bool = False
    ) -> dict[str, Any]:
        candidate = Path(path).expanduser()
        if not candidate.is_dir():
            return {"ok": False, "error": f"not a directory: {path}"}
        try:
            resolved = candidate.resolve(strict=True)
            if candidate.is_symlink() or resolved != candidate.absolute():
                raise OSError("root is not a real directory")
        except (OSError, RuntimeError):
            return {"ok": False, "error": "directory is unavailable"}
        if _disallowed_tree_root(resolved):
            return {"ok": False, "error": "directory cannot be added"}
        try:
            stat = resolved.stat()
        except OSError:
            return {"ok": False, "error": "directory is unavailable"}
        binding = {
            "path": str(resolved),
            "writable": writable,
            "label": resolved.name,
            "_device": int(stat.st_dev),
            "_inode": int(stat.st_ino),
        }
        current = self.roots(session_id)
        if current and Path(current[0]["path"]).resolve() == resolved:
            return {"ok": True, "roots": current}
        engine = self._engines.get(session_id)
        live_roots = getattr(engine, "roots", None) if engine is not None else None

        if live_roots is not None:
            durable_roots = getattr(
                engine,
                "durable_extra_roots",
                self._extra_root_records(live_roots),
            )
            extra_roots = [
                record
                for record in durable_roots
                if Path(str(record["path"])).expanduser().absolute()
                != resolved
            ]
            extra_roots.append(binding)
        else:
            record = self._store.load(session_id)
            if record is None:
                return {"ok": False, "error": "session not found"}
            extra_roots = [
                root
                for root in self._durable_extra_roots(record)
                if Path(str(root["path"])).expanduser().absolute() != resolved
            ]
            extra_roots.append(binding)

        self._store.touch_workspace(str(resolved))
        self._store.set_extra_roots(session_id, extra_roots)
        if live_roots is not None:
            engine.durable_extra_roots = extra_roots
            live_roots[1:] = [
                RootDir(
                    path=root["path"],
                    writable=bool(root["writable"]),
                    label=str(root["label"]),
                    device=int(root["_device"]),
                    inode=int(root["_inode"]),
                )
                for root in _validated_extra_roots(extra_roots)
            ]
        return {"ok": True, "roots": self.roots(session_id)}

    def remove_root(self, session_id: str, path: str) -> dict[str, Any]:
        configured_path = Path(path).expanduser()
        if not configured_path.is_absolute():
            return {"ok": False, "error": "invalid root path"}
        configured_path = configured_path.absolute()
        current = self.roots(session_id)
        if (
            current
            and Path(current[0]["path"]).expanduser().absolute()
            == configured_path
        ):
            return {
                "ok": False,
                "error": "cannot remove the primary workspace",
            }

        engine = self._engines.get(session_id)
        live_roots = getattr(engine, "roots", None) if engine is not None else None
        if live_roots is not None:
            durable_roots = getattr(
                engine,
                "durable_extra_roots",
                self._extra_root_records(live_roots),
            )
            extra_roots = [
                root
                for root in durable_roots
                if Path(str(root["path"])).expanduser().absolute()
                != configured_path
            ]
        else:
            record = self._store.load(session_id)
            if record is None:
                return {"ok": False, "error": "session not found"}
            extra_roots = [
                root
                for root in self._durable_extra_roots(record)
                if Path(str(root["path"])).expanduser().absolute()
                != configured_path
            ]
        self._store.set_extra_roots(session_id, extra_roots)
        if live_roots is not None:
            engine.durable_extra_roots = extra_roots
            live_roots[1:] = [
                RootDir(
                    path=root["path"],
                    writable=bool(root["writable"]),
                    label=str(root["label"]),
                    device=int(root["_device"]),
                    inode=int(root["_inode"]),
                )
                for root in _validated_extra_roots(extra_roots)
            ]
        return {"ok": True, "roots": self.roots(session_id)}

    def tree(
        self,
        session_id: str,
        *,
        root: str,
        path: str = "",
        limit: int = 200,
    ) -> dict[str, Any]:
        if (
            not isinstance(root, str)
            or not root
            or not isinstance(path, str)
            or len(path) > 4096
            or Path(path).is_absolute()
            or ".." in Path(path).parts
            or isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 500
        ):
            return {"ok": False, "error": "invalid tree path"}
        requested_root = Path(root).expanduser()
        if not requested_root.is_absolute():
            return {"ok": False, "error": "root is unavailable"}
        requested_root = requested_root.absolute()
        try:
            if (
                requested_root.is_symlink()
                or requested_root.resolve(strict=True) != requested_root
            ):
                raise OSError("root is not a real directory")
        except (OSError, ValueError, RuntimeError):
            return {"ok": False, "error": "root is unavailable"}
        root_view = next(
            (
                candidate
                for candidate in self.roots(session_id)
                if Path(candidate["path"]).expanduser().absolute()
                == requested_root
            ),
            None,
        )
        if root_view is None or _disallowed_tree_root(requested_root):
            return {
                "ok": False,
                "error": "root is not part of the session",
            }
        if root_view.get("available") is False:
            return {"ok": False, "error": "root is unavailable"}
        selected = requested_root
        parts = tuple(
            part for part in Path(path).parts if part not in {"", "."}
        )
        if any(part.casefold() in _TREE_IGNORE_CASEFOLD for part in parts):
            return {"ok": False, "error": "invalid tree path"}
        expected_identity = self._root_identity(
            session_id,
            selected,
        )
        if expected_identity is None:
            return {"ok": False, "error": "root is unavailable"}
        entries = []
        scanned = 0
        scan_limit = min(max(limit * 10, limit + 1), _MAX_TREE_SCAN)
        descriptors = []
        try:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            current_fd = os.open(selected, flags)
            descriptors.append(current_fd)
            root_stat = os.fstat(current_fd)
            if expected_identity is not None and expected_identity != (
                int(root_stat.st_dev),
                int(root_stat.st_ino),
            ):
                raise OSError("root identity changed")
            for component in parts:
                current_fd = os.open(
                    component,
                    flags,
                    dir_fd=current_fd,
                )
                descriptors.append(current_fd)
            with os.scandir(current_fd) as iterator:
                for candidate in iterator:
                    if candidate.name.casefold() in _TREE_IGNORE_CASEFOLD:
                        continue
                    scanned += 1
                    if scanned > scan_limit:
                        break
                    if candidate.is_symlink():
                        kind = "symlink"
                    elif candidate.is_dir(follow_symlinks=False):
                        kind = "directory"
                    elif candidate.is_file(follow_symlinks=False):
                        kind = "file"
                    else:
                        continue
                    entries.append(
                        {
                            "name": candidate.name,
                            "path": "/".join((*parts, candidate.name)),
                            "kind": kind,
                        }
                    )
        except (OSError, ValueError):
            return {"ok": False, "error": "directory is unavailable"}
        finally:
            for descriptor in reversed(descriptors):
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        order = {"directory": 0, "symlink": 1, "file": 2}
        entries.sort(
            key=lambda entry: (
                order[entry["kind"]],
                entry["name"].casefold(),
            )
        )
        truncated = len(entries) > limit or scanned > scan_limit
        return {
            "ok": True,
            "root": str(selected),
            "path": "/".join(parts),
            "entries": entries[:limit],
            "truncated": truncated,
        }

    def project_search(
        self,
        session_id: str,
        *,
        query: str,
        mode: str = "text",
        limit: int = 50,
    ) -> dict[str, Any]:
        roots = []
        for root in self.roots(session_id):
            if root.get("available") is False:
                continue
            selected = Path(str(root["path"])).expanduser().absolute()
            identity = self._root_identity(session_id, selected)
            if identity is None:
                continue
            roots.append(
                {
                    **root,
                    "_device": identity[0],
                    "_inode": identity[1],
                }
            )
        if not roots:
            return {"ok": False, "error": "project roots unavailable"}
        return self._project_search.search(
            session_id,
            roots,
            query=query,
            mode=mode,
            limit=limit,
        )

    def cancel_project_search(self, session_id: str) -> bool:
        return self._project_search.cancel(session_id)

    def project_context(
        self,
        session_id: str,
        *,
        root: str,
        path: str,
        kind: str,
    ) -> dict[str, Any]:
        if kind == "folder":
            descriptor, root_view, normalized, error = self._open_project_path(
                session_id,
                root=root,
                path=path,
                directory=True,
            )
            if descriptor is None:
                return {"ok": False, "error": error}
            try:
                content, truncated = _recursive_folder_context(descriptor)
            except OSError:
                return {"ok": False, "error": "path is unavailable"}
            finally:
                os.close(descriptor)
            root_label = str(root_view.get("label") or Path(root).name)
            return {
                "ok": True,
                "item": make_project_context_item(
                    kind="folder",
                    root=str(Path(root).expanduser().absolute()),
                    path=normalized,
                    label=(
                        f"{root_label}/{normalized}"
                        if normalized
                        else root_label
                    ),
                    content=content,
                    truncated=truncated,
                ),
            }
        if kind != "file":
            return {"ok": False, "error": "unsupported context kind"}
        descriptor, root_view, normalized, error = self._open_project_path(
            session_id,
            root=root,
            path=path,
            directory=False,
        )
        if descriptor is None:
            return {"ok": False, "error": error}
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                return {"ok": False, "error": "path is unavailable"}
            with os.fdopen(descriptor, "rb", closefd=True) as reader:
                descriptor = None
                payload = reader.read(_MAX_CONTEXT_FILE_BYTES + 1)
        except OSError:
            return {"ok": False, "error": "path is unavailable"}
        finally:
            if descriptor is not None:
                os.close(descriptor)
        truncated = len(payload) > _MAX_CONTEXT_FILE_BYTES
        payload = payload[:_MAX_CONTEXT_FILE_BYTES]
        try:
            content = payload.decode("utf-8")
        except UnicodeDecodeError:
            return {"ok": False, "error": "binary file cannot be context"}
        return {
            "ok": True,
            "item": make_project_context_item(
                kind="file",
                root=str(Path(root).expanduser().absolute()),
                path=normalized,
                label=(
                    f"{root_view.get('label') or Path(root).name}/"
                    f"{normalized}"
                ),
                content=content,
                truncated=truncated,
            ),
        }

    def open_project_path(
        self,
        session_id: str,
        *,
        root: str,
        path: str,
        mode: str,
    ) -> dict[str, Any]:
        if mode not in {"open", "reveal"}:
            return {"ok": False, "error": "mode must be open or reveal"}
        descriptor, _root_view, normalized, error = self._open_project_path(
            session_id,
            root=root,
            path=path,
            directory=not bool(path),
        )
        if descriptor is None:
            return {"ok": False, "error": error}
        try:
            metadata = os.fstat(descriptor)
            if not (
                stat.S_ISREG(metadata.st_mode)
                or stat.S_ISDIR(metadata.st_mode)
            ):
                return {"ok": False, "error": "path is unavailable"}
            if self._artifact_opener is None:
                return {
                    "ok": False,
                    "error": "artifact opener is not configured",
                }
            target = Path(root).expanduser().absolute().joinpath(
                *Path(normalized).parts
            )
            try:
                self._artifact_opener(target, mode, descriptor)
            except OSError as exc:
                return {"ok": False, "error": str(exc)}
        finally:
            os.close(descriptor)
        return {"ok": True}

    def project_root_identity(
        self,
        session_id: str,
        root: str,
    ) -> tuple[int, int] | None:
        selected = Path(root).expanduser()
        if not selected.is_absolute():
            return None
        selected = selected.absolute()
        if not any(
            Path(candidate["path"]).expanduser().absolute() == selected
            and candidate.get("available") is not False
            for candidate in self.roots(session_id)
        ):
            return None
        return self._root_identity(session_id, selected)

    def _open_project_path(
        self,
        session_id: str,
        *,
        root: str,
        path: str,
        directory: bool,
    ) -> tuple[
        Optional[int],
        dict[str, Any],
        str,
        Optional[str],
    ]:
        if (
            not isinstance(root, str)
            or not root
            or not isinstance(path, str)
            or len(path) > 4096
            or Path(path).is_absolute()
            or ".." in Path(path).parts
        ):
            return None, {}, "", "invalid project path"
        selected = Path(root).expanduser()
        if not selected.is_absolute():
            return None, {}, "", "root is unavailable"
        selected = selected.absolute()
        root_view = next(
            (
                candidate
                for candidate in self.roots(session_id)
                if Path(candidate["path"]).expanduser().absolute() == selected
            ),
            None,
        )
        if root_view is None or root_view.get("available") is False:
            return None, {}, "", "root is not part of the session"
        parts = tuple(
            component
            for component in Path(path).parts
            if component not in {"", "."}
        )
        if (
            (not directory and not parts)
            or any(
                component.casefold() in _TREE_IGNORE_CASEFOLD
                for component in parts
            )
        ):
            return None, {}, "", "invalid project path"
        expected_identity = self._root_identity(session_id, selected)
        if expected_identity is None:
            return None, {}, "", "root is unavailable"
        descriptors = []
        try:
            directory_flags = (
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_CLOEXEC
            )
            current_fd = os.open(selected, directory_flags)
            descriptors.append(current_fd)
            root_metadata = os.fstat(current_fd)
            if expected_identity != (
                int(root_metadata.st_dev),
                int(root_metadata.st_ino),
            ):
                raise OSError("root identity changed")
            for index, component in enumerate(parts):
                final = index == len(parts) - 1
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
                if not final or directory:
                    flags |= os.O_DIRECTORY
                current_fd = os.open(component, flags, dir_fd=current_fd)
                descriptors.append(current_fd)
            result = os.dup(current_fd)
        except (OSError, ValueError):
            return None, {}, "", "path is unavailable"
        finally:
            for descriptor in reversed(descriptors):
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        return result, root_view, "/".join(parts), None

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
        record = self._store.load(session_id)
        if record is None or not record.workspace:
            return {"ok": False, "error": "no workspace"}
        descriptor, _root_view, normalized, error = self._open_project_path(
            session_id,
            root=record.workspace,
            path=path,
            directory=False,
        )
        if descriptor is None:
            return {"ok": False, "error": error}
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                return {"ok": False, "error": "not found"}
            if self._artifact_opener is None:
                return {
                    "ok": False,
                    "error": "artifact opener is not configured",
                }
            target = Path(record.workspace).expanduser().absolute().joinpath(
                *Path(normalized).parts
            )
            self._artifact_opener(target, mode, descriptor)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            os.close(descriptor)
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
    def _root_view(
        root: RootDir,
        *,
        primary: bool,
        available: bool = True,
    ) -> dict[str, Any]:
        view = {
            "path": str(root.path),
            "writable": bool(root.writable),
            "label": root.label,
            "primary": primary,
            "exists": available and root.path.is_dir(),
        }
        if not available:
            view["available"] = False
        return view

    def _primary_root(self, record: SessionRecord) -> RootDir | None:
        try:
            root = RootDir(
                path=record.workspace,
                writable=True,
                device=record.workspace_device,
                inode=record.workspace_inode,
            )
        except (OSError, ValueError):
            return None
        if (
            record.workspace_device is None
            and record.workspace_inode is None
        ):
            record.workspace_device = root.device
            record.workspace_inode = root.inode
            self._store.save(record)
        return root

    def _record_extra_roots(
        self,
        record: SessionRecord,
    ) -> list[dict[str, Any]]:
        durable = self._durable_extra_roots(record)
        active: list[dict[str, Any]] = []
        for root in durable:
            active.extend(_validated_extra_roots([root]))
        return active

    @staticmethod
    def _reconcile_live_roots(
        engine: SessionEngine,
        live_roots: list[RootDir],
    ) -> None:
        active_paths = {str(root.path) for root in live_roots[1:]}
        for record in getattr(engine, "durable_extra_roots", []):
            validated = _validated_extra_roots([record])
            if not validated:
                continue
            root = validated[0]
            if str(root["path"]) in active_paths:
                continue
            live_roots.append(
                RootDir(
                    path=root["path"],
                    writable=bool(root["writable"]),
                    label=str(root["label"]),
                    device=int(root["_device"]),
                    inode=int(root["_inode"]),
                )
            )
            active_paths.add(str(root["path"]))

    def _durable_extra_roots(
        self,
        record: SessionRecord,
    ) -> list[dict[str, Any]]:
        durable: list[dict[str, Any]] = []
        changed = False
        for root in record.extra_roots:
            if not isinstance(root, dict):
                continue
            device = root.get("_device")
            inode = root.get("_inode")
            if device is None and inode is None:
                bound = _validated_extra_roots(
                    [root],
                    bind_unbound=True,
                )
                if bound:
                    durable.append(bound[0])
                    changed = True
                else:
                    durable.append(root)
            else:
                durable.append(root)
        if changed:
            record.extra_roots = durable
            self._store.save(record)
        return durable

    @staticmethod
    def _extra_root_records(roots: list[RootDir]) -> list[dict[str, Any]]:
        return [
            {
                "path": str(root.path),
                "writable": bool(root.writable),
                "label": root.label,
                "_device": root.device,
                "_inode": root.inode,
            }
            for root in roots[1:]
            if root.device is not None and root.inode is not None
        ]

    def _root_identity(
        self,
        session_id: str,
        selected: Path,
    ) -> tuple[int, int] | None:
        engine = self._engines.get(session_id)
        live_roots = getattr(engine, "roots", None) if engine is not None else None
        if live_roots is not None:
            matching = next(
                (
                    root
                    for root in live_roots
                    if root.path == selected
                    and root.device is not None
                    and root.inode is not None
                ),
                None,
            )
            return (
                (int(matching.device), int(matching.inode))
                if matching is not None
                else None
            )
        record = self._store.load(session_id)
        if record is None:
            return None
        primary = Path(record.workspace).expanduser().absolute()
        if primary == selected:
            root = self._primary_root(record)
            if root is None:
                return None
            return (int(root.device), int(root.inode))
        matching = next(
            (
                root
                for root in self._record_extra_roots(record)
                if Path(root["path"]) == selected
            ),
            None,
        )
        return (
            (int(matching["_device"]), int(matching["_inode"]))
            if matching is not None
            else None
        )


def _disallowed_tree_root(path: Path) -> bool:
    return (
        ".git" in (part.casefold() for part in path.parts)
        or path.name.casefold() in _TREE_IGNORE_CASEFOLD
    )


def _root_available(root: RootDir) -> bool:
    try:
        metadata = os.stat(root.path, follow_symlinks=False)
    except OSError:
        return False
    return (
        not root.path.is_symlink()
        and root.path.resolve(strict=True) == root.path
        and root.device is not None
        and root.inode is not None
        and (int(metadata.st_dev), int(metadata.st_ino))
        == (int(root.device), int(root.inode))
    )


def _inactive_root_view(root: dict[str, Any]) -> dict[str, Any]:
    path = str(root.get("path", ""))
    return {
        "path": path,
        "writable": bool(root.get("writable", False)),
        "label": str(root.get("label", "")) or Path(path).name,
        "primary": False,
        "exists": False,
        "available": False,
    }


def _validated_extra_roots(
    roots: list[dict[str, Any]],
    *,
    bind_unbound: bool = False,
) -> list[dict[str, Any]]:
    valid = []
    for root in roots:
        try:
            path = Path(str(root["path"])).expanduser()
            device = root.get("_device")
            inode = root.get("_inode")
            if (
                path.is_symlink()
                or _disallowed_tree_root(path)
            ):
                continue
            resolved = path.resolve(strict=True)
            if resolved != path.absolute() or not resolved.is_dir():
                continue
            stat = os.stat(resolved, follow_symlinks=False)
            if device is None and inode is None and bind_unbound:
                device = int(stat.st_dev)
                inode = int(stat.st_ino)
            if (
                isinstance(device, bool)
                or not isinstance(device, int)
                or isinstance(inode, bool)
                or not isinstance(inode, int)
            ):
                continue
            if (int(stat.st_dev), int(stat.st_ino)) != (device, inode):
                continue
            valid.append(
                {
                    "path": str(resolved),
                    "writable": bool(root.get("writable", False)),
                    "label": str(root.get("label", "")) or resolved.name,
                    "_device": device,
                    "_inode": inode,
                }
            )
        except (KeyError, OSError, TypeError, ValueError):
            continue
    return valid


def _is_safe_fork_boundary(
    messages: list[dict[str, Any]],
    message_index: int,
) -> bool:
    pending: set[str] = set()
    for message in messages[: message_index + 1]:
        if not isinstance(message, dict):
            return False
        role = message.get("role")
        if pending:
            if role != "tool":
                return False
            tool_call_id = message.get("tool_call_id")
            if (
                not isinstance(tool_call_id, str)
                or tool_call_id not in pending
            ):
                return False
            pending.remove(tool_call_id)
            continue
        if role == "tool":
            return False
        tool_calls = message.get("tool_calls")
        if role != "assistant" or not tool_calls:
            continue
        if not isinstance(tool_calls, list):
            return False
        call_ids = []
        for call in tool_calls:
            call_id = call.get("id") if isinstance(call, dict) else None
            if not isinstance(call_id, str) or not call_id:
                return False
            call_ids.append(call_id)
        if len(set(call_ids)) != len(call_ids):
            return False
        pending.update(call_ids)
    return not pending


def _visible_markdown_content(content: Any) -> tuple[str, list[str]]:
    if isinstance(content, str):
        return content, []
    if not isinstance(content, list):
        return "", []
    text_parts = []
    attachments = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if (
            part.get("type") == "text"
            and isinstance(part.get("text"), str)
            and not is_project_context_part(part)
        ):
            text_parts.append(part["text"])
        elif part.get("type") == "file":
            file = part.get("file")
            filename = file.get("filename") if isinstance(file, dict) else None
            if isinstance(filename, str) and filename:
                attachments.append(Path(filename).name)
        elif part.get("type") == "image_url":
            attachments.append("Image")
    return "\n".join(text_parts), attachments


def _recursive_folder_context(root_descriptor: int) -> tuple[str, bool]:
    chunks: list[bytes] = []
    total_bytes = 0
    entries_seen = 0
    truncated = False

    def append(value: str) -> bool:
        nonlocal total_bytes, truncated
        encoded = value.encode("utf-8")
        remaining = _MAX_CONTEXT_FOLDER_BYTES - total_bytes
        if remaining <= 0:
            truncated = True
            return False
        if len(encoded) > remaining:
            chunks.append(encoded[:remaining])
            total_bytes += remaining
            truncated = True
            return False
        chunks.append(encoded)
        total_bytes += len(encoded)
        return True

    def walk(directory_descriptor: int, prefix: str, depth: int) -> None:
        nonlocal entries_seen, truncated
        if depth > _MAX_CONTEXT_FOLDER_DEPTH:
            truncated = True
            return
        remaining = _MAX_CONTEXT_FOLDER_ENTRIES - entries_seen
        with os.scandir(directory_descriptor) as iterator:
            scanned = list(
                itertools.islice(
                    iterator,
                    remaining + 1,
                )
            )
        if len(scanned) > remaining:
            truncated = True
            scanned.pop()
        entries = sorted(
            scanned,
            key=lambda entry: entry.name.casefold(),
        )
        for entry in entries:
            if entries_seen >= _MAX_CONTEXT_FOLDER_ENTRIES:
                truncated = True
                return
            if entry.name.casefold() in _TREE_IGNORE_CASEFOLD:
                continue
            entries_seen += 1
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            try:
                if entry.is_symlink():
                    if not append(f"symlink {relative} (omitted)\n"):
                        return
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if not append(f"directory {relative}/\n"):
                        return
                    child = os.open(
                        entry.name,
                        os.O_RDONLY
                        | os.O_DIRECTORY
                        | os.O_NOFOLLOW
                        | os.O_CLOEXEC,
                        dir_fd=directory_descriptor,
                    )
                    try:
                        walk(child, relative, depth + 1)
                    finally:
                        os.close(child)
                    if truncated and total_bytes >= _MAX_CONTEXT_FOLDER_BYTES:
                        return
                    continue
                if not entry.is_file(follow_symlinks=False):
                    if not append(f"other {relative} (omitted)\n"):
                        return
                    continue
                file_descriptor = os.open(
                    entry.name,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=directory_descriptor,
                )
                try:
                    payload = os.read(
                        file_descriptor,
                        _MAX_CONTEXT_FOLDER_FILE_BYTES + 1,
                    )
                finally:
                    os.close(file_descriptor)
                file_truncated = (
                    len(payload) > _MAX_CONTEXT_FOLDER_FILE_BYTES
                )
                payload = payload[:_MAX_CONTEXT_FOLDER_FILE_BYTES]
                try:
                    text = payload.decode("utf-8")
                    if "\x00" in text:
                        raise UnicodeDecodeError(
                            "utf-8", payload, 0, 1, "NUL byte"
                        )
                except UnicodeDecodeError:
                    if not append(f"file {relative} (binary omitted)\n"):
                        return
                    continue
                header = (
                    f"file {relative}"
                    f"{' (truncated)' if file_truncated else ''}:\n"
                )
                if not append(header) or not append(text):
                    return
                if text and not text.endswith("\n") and not append("\n"):
                    return
                if not append("\n"):
                    return
                truncated = truncated or file_truncated
            except OSError:
                truncated = True
                if not append(f"unavailable {relative}\n"):
                    return

    walk(root_descriptor, "", 0)
    if not chunks:
        return "(empty folder)", truncated
    return b"".join(chunks).decode("utf-8", errors="ignore").rstrip(), truncated


def _safe_markdown_slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
    return (slug or "codinal-conversation")[:80].rstrip("-")


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
