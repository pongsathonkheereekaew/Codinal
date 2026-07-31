"""Loopback-only preview verification primitives.

This module intentionally validates an origin before any optional browser
backend is invoked. It does not fetch URLs, retain cookies, or follow redirects.
"""

from __future__ import annotations

import http.client
from urllib.parse import urlsplit, urlunsplit


class PreviewVerificationError(ValueError):
    """A requested preview origin is outside the local verifier boundary."""


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})


def verify_origin(raw_url: str) -> str:
    """Return a canonical approved loopback URL, or reject it fail-closed."""
    if not isinstance(raw_url, str) or not 1 <= len(raw_url) <= 2048:
        raise PreviewVerificationError("invalid preview origin")
    try:
        parsed = urlsplit(raw_url)
        port = parsed.port
    except ValueError as error:
        raise PreviewVerificationError("invalid preview origin") from error
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.hostname not in _LOOPBACK_HOSTS
        or port is None
        or not 1 <= port <= 65535
    ):
        raise PreviewVerificationError("preview verification requires a loopback origin")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def verify_http(raw_url: str) -> dict[str, object]:
    """Perform one bounded, cookie-free request to an approved preview origin."""
    origin = verify_origin(raw_url)
    parsed = urlsplit(origin)
    connection_type = (
        http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    )
    connection = connection_type(parsed.hostname, parsed.port, timeout=5)
    try:
        target = parsed.path or "/"
        if parsed.query:
            target += f"?{parsed.query}"
        connection.request("GET", target, headers={"Accept": "text/html"})
        response = connection.getresponse()
        return {
            "origin": origin,
            "status_code": response.status,
            "ok": 200 <= response.status < 400,
            "content_length": min(int(response.getheader("Content-Length") or 0), 65_536),
        }
    except (OSError, ValueError, http.client.HTTPException) as error:
        return {"origin": origin, "ok": False, "error": type(error).__name__}
    finally:
        connection.close()
