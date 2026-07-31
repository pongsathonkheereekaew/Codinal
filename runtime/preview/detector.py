"""Detect localhost dev-server URLs in terminal output.

Scans shell stdout/stderr for ``http://localhost:PORT`` and
``http://127.0.0.1:PORT`` patterns so the UI can surface clickable
"Preview" links. Bounded + de-duplicated; never matches non-localhost.
"""

from __future__ import annotations

import re
from typing import Any

_URL_RE = re.compile(
    r"https?://(?:localhost|127\.0\.0\.1):(\d{1,5})\S*"
)
_MAX_URLS = 8
_MAX_URL_LEN = 256


def detect_devserver_urls(output: str) -> list[dict[str, Any]]:
    """Return ``[{url, port}]`` for localhost URLs found in ``output``.

    Non-localhost URLs are ignored. De-duplicated by URL; bounded to
    ``_MAX_URLS``. ``output`` is truncated before scanning to cap cost.
    """
    if not isinstance(output, str) or not output:
        return []
    haystack = output[: 64 * 1024]
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for match in _URL_RE.finditer(haystack):
        raw = match.group(0)
        if len(raw) > _MAX_URL_LEN:
            raw = raw[:_MAX_URL_LEN]
        # Strip trailing punctuation that's not part of the URL.
        url = raw.rstrip(".,;)]}>'\"")
        url = re.sub(
            r"^(https?://)localhost(?=[:/]|$)",
            r"\g<1>127.0.0.1",
            url,
        )
        if url in seen:
            continue
        seen.add(url)
        port = int(match.group(1))
        results.append({"url": url, "port": port})
        if len(results) >= _MAX_URLS:
            break
    return results
