# SPDX-License-Identifier: MIT
"""Provider-ready project context snapshots."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


def is_project_context_part(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "type",
        "text",
        "_codinal_context",
    }:
        return False
    text = value.get("text")
    fingerprint = value.get("_codinal_context")
    return (
        value.get("type") == "text"
        and isinstance(text, str)
        and isinstance(fingerprint, str)
        and _FINGERPRINT.fullmatch(fingerprint) is not None
        and hashlib.sha256(text.encode("utf-8")).hexdigest() == fingerprint
    )


def make_project_context_item(
    *,
    kind: str,
    root: str,
    path: str,
    label: str,
    content: str,
    truncated: bool,
) -> dict[str, Any]:
    metadata = json.dumps(
        {
            "kind": kind,
            "path": path,
            "root": root,
            "truncated": truncated,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    text = (
        f"<!-- codinal-context:{metadata} -->\n"
        f"{content}"
        f"{'' if content.endswith(chr(10)) else chr(10)}"
        "<!-- /codinal-context -->"
    )
    fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "kind": kind,
        "root": root,
        "path": path,
        "label": label,
        "truncated": truncated,
        "fingerprint": fingerprint,
        "content_part": {
            "type": "text",
            "text": text,
            "_codinal_context": fingerprint,
        },
        "provider_part": {"type": "text", "text": text},
    }
