"""Loopback-only Ollama model discovery."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


_OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
_DISCOVERY_TIMEOUT_SECONDS = 0.75
_MAX_RESPONSE_BYTES = 1_048_576
_MAX_MODELS = 128


class _NoRedirect(HTTPRedirectHandler):
    """Keep a loopback request from being redirected to another origin."""

    def redirect_request(self, *_args, **_kwargs):
        return None


def discover_ollama_models() -> dict[str, Any]:
    """Return installed Ollama models without accepting a user-supplied URL.

    The endpoint is intentionally fixed to the IPv4 loopback address.  A
    missing, slow, malformed, or unavailable local service is a normal state,
    so callers receive a stable unavailable result without network detail.
    """
    request = Request(
        _OLLAMA_TAGS_URL,
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        opener = build_opener(ProxyHandler({}), _NoRedirect())
        with opener.open(request, timeout=_DISCOVERY_TIMEOUT_SECONDS) as response:
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except (HTTPError, OSError, URLError, ValueError):
        return {"available": False, "models": []}
    if len(raw) > _MAX_RESPONSE_BYTES:
        return {"available": False, "models": []}
    try:
        payload = json.loads(raw)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return {"available": False, "models": []}
    rows = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {"available": False, "models": []}
    models: list[str] = []
    for row in rows[:_MAX_MODELS]:
        name = row.get("name") if isinstance(row, dict) else None
        if not _valid_model_name(name):
            continue
        model = f"ollama:{name}"
        if model not in models:
            models.append(model)
    return {"available": True, "models": models}


def _valid_model_name(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and len(value) <= 240
        and value.isascii()
        and value.isprintable()
        and not any(character.isspace() for character in value)
    )
