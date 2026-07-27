"""Secret-aware redaction for outbound content and audit payloads.

The redactor scrubs exact matches of registered provider API keys (and a
conservative set of common key prefixes as a backstop) from text that is about
to leave the local trust boundary: the provider feed, the audit ledger, and
MCP tool arguments. It never mutates the in-memory conversation transcript —
the user-visible history keeps fidelity; only the outbound copy is scrubbed.

The redactor subscribes to ``ProviderSecretService`` so a key rotation is
picked up without rebuilding the runtime.
"""

from __future__ import annotations

import copy
import json
import re
import threading
from typing import Any, Optional, Protocol

# Common cloud API-key prefixes. Backstop for keys that entered history before
# being registered (e.g. a user pasted one into chat). Match a reasonably long
# token after the prefix so we don't redact ordinary prose.
_PREFIX_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "[REDACTED:key]"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "[REDACTED:anthropic]"),
    (re.compile(r"AIza[A-Za-z0-9_\-]{20,}"), "[REDACTED:gemini]"),
]

_MIN_KEY_LEN = 12  # don't bother redacting absurdly short strings


class _SecretSource(Protocol):
    def snapshot(self) -> dict[str, str]: ...

    def subscribe(self, listener) -> None: ...


class SecretRedactor:
    def __init__(self, secrets: Optional[_SecretSource] = None) -> None:
        self._lock = threading.RLock()
        self._secrets = secrets
        self._exact: list[tuple[str, str]] = []
        self._refresh()
        if secrets is not None:
            secrets.subscribe(self._on_change)

    def _on_change(self, _provider: str) -> None:
        self._refresh()

    def _refresh(self) -> None:
        if self._secrets is None:
            return
        snapshot = self._secrets.snapshot()
        with self._lock:
            self._exact = [
                (key, f"[REDACTED:{provider}]")
                for provider, key in snapshot.items()
                if isinstance(key, str) and len(key) >= _MIN_KEY_LEN
            ]
            # Longest-first so a key that is a prefix of another is replaced correctly.
            self._exact.sort(key=lambda pair: len(pair[0]), reverse=True)

    def redact(self, text: Any) -> Any:
        if not isinstance(text, str) or not text:
            return text
        with self._lock:
            exact = list(self._exact)
        out = text
        for key, marker in exact:
            if key and key in out:
                out = out.replace(key, marker)
        for pattern, marker in _PREFIX_PATTERNS:
            if pattern.search(out):
                out = pattern.sub(marker, out)
        return out

    def redact_payload(self, payload: Any) -> Any:
        """Redact a JSON-serializable payload (dict/list/str/primitive)."""
        if isinstance(payload, str):
            return self.redact(payload)
        if isinstance(payload, dict):
            return {k: self.redact_payload(v) for k, v in payload.items()}
        if isinstance(payload, list):
            return [self.redact_payload(item) for item in payload]
        return payload

    def redact_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return a deep copy of ``messages`` with secrets scrubbed.

        Never mutates the input. Walks ``content`` (string or OpenAI parts),
        tool-call ``arguments`` (JSON string or dict), and any top-level
        string field that commonly carries text.
        """
        out = copy.deepcopy(messages)
        for message in out:
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            message["content"] = self._redact_content(content)
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list):
                for call in tool_calls:
                    if not isinstance(call, dict):
                        continue
                    fn = call.get("function")
                    if not isinstance(fn, dict):
                        continue
                    fn["arguments"] = self._redact_arguments(
                        fn.get("arguments")
                    )
        return out

    def _redact_content(self, content: Any) -> Any:
        if isinstance(content, str):
            return self.redact(content)
        if isinstance(content, list):
            return [self._redact_content_part(part) for part in content]
        return content

    def _redact_content_part(self, part: Any) -> Any:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            return {**part, "text": self.redact(part["text"])}
        return part

    def _redact_arguments(self, arguments: Any) -> Any:
        if isinstance(arguments, str):
            redacted = self.redact(arguments)
            # Re-validate it's still JSON; if not, return the redacted string as-is.
            try:
                parsed = json.loads(redacted)
            except (json.JSONDecodeError, ValueError):
                return redacted
            return json.dumps(self.redact_payload(parsed), separators=(",", ":"))
        if isinstance(arguments, dict):
            return self.redact_payload(arguments)
        return arguments
