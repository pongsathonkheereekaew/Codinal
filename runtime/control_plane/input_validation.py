"""Bounded canonical user-input validation for the loopback API."""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from typing import Any


MAX_TURN_BODY_BYTES = 15 * 1024 * 1024
MAX_TEXT_BYTES = 1024 * 1024
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENTS = 5
MAX_CONTENT_PARTS = 16

_DATA_URL = re.compile(
    r"^data:(?P<mime>[a-z0-9.+-]+/[a-z0-9.+-]+);base64,(?P<data>[A-Za-z0-9+/]*={0,2})$",
    re.IGNORECASE,
)
_IMAGE_MIMES = {
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
}


def valid_turn_input(value: Any, *, allow_context: bool = False) -> bool:
    if isinstance(value, str):
        return 1 <= len(value.encode("utf-8")) <= MAX_TEXT_BYTES
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_CONTENT_PARTS:
        return False

    text_bytes = 0
    attachment_bytes = 0
    attachments = 0
    has_content = False
    for part in value:
        if not isinstance(part, dict):
            return False
        kind = part.get("type")
        if kind == "text":
            keys = set(part)
            if keys == {"type", "text"}:
                pass
            elif (
                allow_context
                and keys == {"type", "text", "_codinal_context"}
                and isinstance(part.get("_codinal_context"), str)
                and re.fullmatch(
                    r"[0-9a-f]{64}", part["_codinal_context"]
                )
                and isinstance(part.get("text"), str)
                and hashlib.sha256(
                    part["text"].encode("utf-8")
                ).hexdigest()
                == part["_codinal_context"]
            ):
                pass
            else:
                return False
            if not isinstance(part["text"], str):
                return False
            size = len(part["text"].encode("utf-8"))
            text_bytes += size
            has_content = has_content or size > 0
        elif kind == "image_url":
            if set(part) != {"type", "image_url"}:
                return False
            image = part["image_url"]
            if (
                not isinstance(image, dict)
                or set(image) != {"url"}
                or not isinstance(image["url"], str)
            ):
                return False
            size = _data_url_size(image["url"], _IMAGE_MIMES)
            if size is None:
                return False
            attachment_bytes += size
            attachments += 1
            has_content = True
        elif kind == "file":
            if set(part) != {"type", "file"}:
                return False
            file = part["file"]
            if (
                not isinstance(file, dict)
                or set(file) != {"filename", "file_data"}
                or not _valid_filename(file["filename"])
                or not isinstance(file["file_data"], str)
            ):
                return False
            size = _data_url_size(
                file["file_data"],
                {"application/pdf"},
            )
            if size is None:
                return False
            attachment_bytes += size
            attachments += 1
            has_content = True
        else:
            return False

        if (
            text_bytes > MAX_TEXT_BYTES
            or attachment_bytes > MAX_ATTACHMENT_BYTES
            or attachments > MAX_ATTACHMENTS
        ):
            return False
    return has_content


def _data_url_size(value: str, allowed_mimes: set[str]) -> int | None:
    match = _DATA_URL.fullmatch(value)
    if match is None or match.group("mime").lower() not in allowed_mimes:
        return None
    encoded = match.group("data")
    if len(encoded) > ((MAX_ATTACHMENT_BYTES + 2) // 3) * 4:
        return None
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None
    if not _matches_signature(match.group("mime").lower(), decoded):
        return None
    return len(decoded)


def _matches_signature(mime: str, data: bytes) -> bool:
    if mime == "application/pdf":
        return data.startswith(b"%PDF-")
    if mime == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime == "image/gif":
        return data.startswith((b"GIF87a", b"GIF89a"))
    if mime == "image/webp":
        return (
            len(data) >= 12
            and data.startswith(b"RIFF")
            and data[8:12] == b"WEBP"
        )
    return False


def _valid_filename(value: Any) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value.encode("utf-8")) <= 255
        and value not in {".", ".."}
        and "/" not in value
        and "\\" not in value
        and all(ord(character) >= 32 for character in value)
    )
