"""Session-scoped durable prompts shared by live and recovered turns."""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

_KINDS = {"directory", "plan", "question"}


class InteractionDecisionStore(Protocol):
    def load_interaction_decision(
        self,
        session_id: str,
        tool_call_id: str,
        kind: str,
        request_fingerprint: str,
    ) -> dict[str, Any] | None: ...

    def save_interaction_decision(
        self,
        session_id: str,
        tool_call_id: str,
        kind: str,
        request_fingerprint: str,
        response: dict[str, Any],
    ) -> None: ...


class InteractionPersistenceError(RuntimeError):
    """A prompt response could not be durably acknowledged."""


@dataclass
class _Pending:
    session_id: str
    interaction_id: str
    tool_call_id: str
    kind: str
    arguments: dict[str, Any]
    fingerprint: str
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future[dict[str, Any]]
    response_normalizer: Callable[
        [dict[str, Any], bool],
        dict[str, Any],
    ] | None = None
    resolved: bool = False


class InteractionBroker:
    def __init__(self, decisions: InteractionDecisionStore) -> None:
        self._decisions = decisions
        self._lock = threading.RLock()
        self._pending: dict[tuple[str, str], _Pending] = {}
        self._closed = False

    @staticmethod
    def interaction_id(
        session_id: str,
        tool_call_id: str,
        kind: str,
    ) -> str:
        if (
            not isinstance(session_id, str)
            or not isinstance(tool_call_id, str)
            or kind not in _KINDS
        ):
            raise ValueError("invalid interaction identity")
        return hashlib.sha256(
            f"{session_id}\0{tool_call_id}\0{kind}".encode("utf-8")
        ).hexdigest()[:32]

    def requester(
        self,
        session_id: str,
        kind: str,
        *,
        response_normalizer: Callable[
            [dict[str, Any], bool],
            dict[str, Any],
        ] | None = None,
    ) -> Callable[
        [dict[str, Any], str],
        Awaitable[dict[str, Any]],
    ]:
        if kind not in _KINDS:
            raise ValueError("invalid interaction kind")

        def request(
            arguments: dict[str, Any],
            tool_call_id: str,
        ) -> Awaitable[dict[str, Any]]:
            normalized = _normalize_arguments(kind, arguments)
            fingerprint = _fingerprint(kind, normalized)
            durable = self._decisions.load_interaction_decision(
                session_id,
                tool_call_id,
                kind,
                fingerprint,
            )
            if durable is not None:
                try:
                    replay = (
                        response_normalizer(durable, True)
                        if response_normalizer is not None
                        else durable
                    )
                except (OSError, ValueError):
                    replay = _declined(
                        kind,
                        "approved resource changed",
                    )
                return _immediate(replay)
            interaction_id = self.interaction_id(
                session_id,
                tool_call_id,
                kind,
            )
            loop = asyncio.get_running_loop()
            pending = _Pending(
                session_id=session_id,
                interaction_id=interaction_id,
                tool_call_id=tool_call_id,
                kind=kind,
                arguments=normalized,
                fingerprint=fingerprint,
                loop=loop,
                future=loop.create_future(),
                response_normalizer=response_normalizer,
            )
            key = (session_id, interaction_id)
            with self._lock:
                if self._closed or key in self._pending:
                    return _immediate(_declined(kind, "prompt unavailable"))
                self._pending[key] = pending
            return self._wait(key, pending)

        return request

    async def _wait(
        self,
        key: tuple[str, str],
        pending: _Pending,
    ) -> dict[str, Any]:
        try:
            return await pending.future
        finally:
            with self._lock:
                if self._pending.get(key) is pending:
                    self._pending.pop(key, None)

    def pending(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            pending = [
                item
                for item in self._pending.values()
                if item.session_id == session_id and not item.resolved
            ]
        return [
            {
                "interaction_id": item.interaction_id,
                "kind": item.kind,
                "arguments": dict(item.arguments),
            }
            for item in pending
        ]

    def resolve(
        self,
        session_id: str,
        interaction_id: str,
        response: dict[str, Any],
    ) -> bool:
        key = (session_id, interaction_id)
        with self._lock:
            pending = self._pending.get(key)
            if pending is None or pending.resolved:
                return False
            normalized = _normalize_response(pending.kind, response)
            if pending.response_normalizer is not None:
                normalized = pending.response_normalizer(
                    normalized,
                    False,
                )
            try:
                self._decisions.save_interaction_decision(
                    session_id,
                    pending.tool_call_id,
                    pending.kind,
                    pending.fingerprint,
                    normalized,
                )
            except Exception:
                raise InteractionPersistenceError(
                    "interaction response persistence failed"
                ) from None
            pending.resolved = True
        pending.loop.call_soon_threadsafe(
            _complete,
            pending.future,
            normalized,
        )
        return True

    def close(self) -> None:
        with self._lock:
            self._closed = True
            pending = [
                item
                for item in self._pending.values()
                if not item.resolved
            ]
            for item in pending:
                item.resolved = True
        for item in pending:
            item.loop.call_soon_threadsafe(
                _complete,
                item.future,
                _declined(item.kind, "runtime stopped"),
            )


async def _immediate(response: dict[str, Any]) -> dict[str, Any]:
    return response


def _complete(
    future: asyncio.Future[dict[str, Any]],
    response: dict[str, Any],
) -> None:
    if not future.done():
        future.set_result(response)


def _normalize_arguments(
    kind: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise ValueError("invalid interaction arguments")
    normalized = json.loads(
        json.dumps(arguments, allow_nan=False, sort_keys=True)
    )
    encoded = json.dumps(normalized, separators=(",", ":")).encode("utf-8")
    if len(encoded) > 64 * 1024:
        raise ValueError("interaction arguments exceed limit")
    if kind == "question":
        question = str(normalized.get("question", "")).strip()
        if not question:
            raise ValueError("question is required")
        normalized["question"] = question
    elif kind == "plan":
        plan = str(normalized.get("plan", "")).strip()
        if not plan:
            raise ValueError("plan is required")
        normalized["plan"] = plan
    return normalized


def _normalize_response(
    kind: str,
    response: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise ValueError("invalid interaction response")
    if kind == "question":
        answer = response.get("answer")
        if not isinstance(answer, str) or not 1 <= len(answer.strip()) <= 16_384:
            raise ValueError("invalid question answer")
        return {"answer": answer.strip()}
    if kind == "plan":
        approved = response.get("approved")
        if not isinstance(approved, bool):
            raise ValueError("invalid plan response")
        if approved:
            mode = response.get("mode", "interactive")
            if mode not in {"interactive", "auto"}:
                raise ValueError("invalid plan mode")
            return {"approved": True, "mode": mode}
        feedback = response.get("feedback", "")
        if not isinstance(feedback, str) or len(feedback) > 16_384:
            raise ValueError("invalid plan feedback")
        return {
            "approved": False,
            "feedback": feedback.strip(),
        }
    granted = response.get("granted")
    if not isinstance(granted, bool):
        raise ValueError("invalid directory response")
    if not granted:
        return {"granted": False}
    path = response.get("path")
    if not isinstance(path, str) or not 1 <= len(path) <= 4096:
        raise ValueError("invalid directory path")
    return {
        "granted": True,
        "path": path,
        "writable": bool(response.get("writable", False)),
    }


def _declined(kind: str, error: str) -> dict[str, Any]:
    if kind == "question":
        return {"answer": "", "error": error}
    if kind == "plan":
        return {"approved": False, "error": error}
    return {"granted": False, "error": error}


def _fingerprint(kind: str, arguments: dict[str, Any]) -> str:
    payload = json.dumps(
        {"arguments": arguments, "kind": kind},
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
