"""Loopback-only preview verification primitives.

This module intentionally validates an origin before any optional browser
backend is invoked. It does not fetch URLs, retain cookies, or follow redirects.
"""

from __future__ import annotations

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
