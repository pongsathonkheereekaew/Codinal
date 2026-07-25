# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Andrew Ng
# Vendored and adapted from andrewyng/openworker:
# coworker/pdf_support.py @ 54b4bfd82d75704a4079ecea4f8f622aa152dbde.
"""Local PDF adaptation for models without native PDF support."""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import struct
import zlib
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

MAX_EXTRACT_CHARS = 200_000
RASTER_SCALE = 2.0
RASTER_MAX_PAGES = 100
FALLBACK_MODES = ("text", "images")

_fallback_mode = "text"
_cache: dict[tuple[str, str], Any] = {}
_CACHE_MAX = 8


def set_fallback_mode(mode: Any) -> str:
    global _fallback_mode
    _fallback_mode = mode if mode in FALLBACK_MODES else "text"
    return _fallback_mode


def fallback_mode() -> str:
    return _fallback_mode


def _cached(key: tuple[str, str], compute: Callable[[], Any]) -> Any:
    if key in _cache:
        return _cache[key]
    value = compute()
    if len(_cache) >= _CACHE_MAX:
        _cache.pop(next(iter(_cache)))
    _cache[key] = value
    return value


def _digest(file_data: str) -> str:
    return hashlib.sha256(file_data.encode("ascii", "ignore")).hexdigest()


def _pdf_bytes(file_data: str) -> Optional[bytes]:
    prefix = "data:application/pdf;base64,"
    if not isinstance(file_data, str) or not file_data.startswith(prefix):
        return None
    try:
        return base64.b64decode(file_data[len(prefix) :], validate=False)
    except (ValueError, TypeError):
        return None


def inspect(file_data: str) -> dict[str, Any]:
    """Return page count and byte size without raising on malformed input."""
    raw = _pdf_bytes(file_data)
    if raw is None:
        return {"ok": False, "error": "not a PDF data URL"}
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw), strict=False)
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                return {"ok": False, "error": "PDF is password-protected"}
        return {"ok": True, "pages": len(reader.pages), "bytes": len(raw)}
    except Exception as exc:
        return {
            "ok": False,
            "error": f"could not read PDF: {exc.__class__.__name__}",
        }


def extract_text(file_data: str) -> Optional[str]:
    """Extract embedded PDF text locally, capped for provider context safety."""

    def compute() -> Optional[str]:
        raw = _pdf_bytes(file_data)
        if raw is None:
            return None
        try:
            from pypdf import PdfReader

            chunks: list[str] = []
            total = 0
            for page in PdfReader(io.BytesIO(raw), strict=False).pages:
                text = page.extract_text() or ""
                if text:
                    chunks.append(text)
                    total += len(text)
                    if total >= MAX_EXTRACT_CHARS:
                        break
            return "\n\n".join(chunks)[:MAX_EXTRACT_CHARS]
        except Exception:
            logger.warning("pdf text extraction failed", exc_info=True)
            return None

    return _cached((_digest(file_data), "text"), compute)


def _encode_png(
    width: int,
    height: int,
    pixels: bytes,
    stride: int,
    channels: int,
) -> bytes:
    color_type = 6 if channels == 4 else 2
    row_bytes = width * channels
    scanlines = bytearray()
    for y in range(height):
        scanlines.append(0)
        start = y * stride
        scanlines.extend(pixels[start : start + row_bytes])

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(scanlines), 6))
        + chunk(b"IEND", b"")
    )


def rasterize(
    file_data: str,
    max_pages: int = RASTER_MAX_PAGES,
) -> Optional[list[str]]:
    """Render PDF pages locally as PNG data URLs."""

    def compute() -> Optional[list[str]]:
        raw = _pdf_bytes(file_data)
        if raw is None:
            return None
        try:
            import pypdfium2

            document = pypdfium2.PdfDocument(raw)
            pages: list[str] = []
            try:
                for index in range(min(len(document), max_pages)):
                    bitmap = document[index].render(
                        scale=RASTER_SCALE,
                        rev_byteorder=True,
                    )
                    png = _encode_png(
                        bitmap.width,
                        bitmap.height,
                        bytes(bitmap.buffer),
                        bitmap.stride,
                        bitmap.n_channels,
                    )
                    pages.append(
                        "data:image/png;base64,"
                        + base64.b64encode(png).decode("ascii")
                    )
            finally:
                document.close()
            return pages or None
        except Exception:
            logger.warning("pdf rasterization failed", exc_info=True)
            return None

    return _cached((_digest(file_data), f"images:{max_pages}"), compute)


def adapt_content(
    content: list[dict[str, Any]],
    capabilities: Any,
) -> list[dict[str, Any]]:
    """Replace PDF file parts without mutating canonical message history."""
    out: list[dict[str, Any]] = []
    for part in content:
        if not (isinstance(part, dict) and part.get("type") == "file"):
            out.append(part)
            continue
        file = part.get("file") or {}
        name = str(file.get("filename") or "attachment.pdf")
        file_data = file.get("file_data") or ""

        if fallback_mode() == "images" and getattr(
            capabilities,
            "vision",
            False,
        ):
            images = rasterize(file_data)
            if images:
                out.append(
                    {
                        "type": "text",
                        "text": (
                            f"[Attached PDF: {name} — {len(images)} "
                            "page image(s), rendered locally]"
                        ),
                    }
                )
                out.extend(
                    {
                        "type": "image_url",
                        "image_url": {"url": image},
                    }
                    for image in images
                )
                continue

        text = extract_text(file_data)
        if text:
            note = (
                f"[Attached PDF: {name} — text extracted locally; "
                f"this model has no native PDF support]\n{text}"
            )
        else:
            note = (
                f"[Attached PDF: {name} — no extractable text "
                "(likely scanned). A model with native PDF support can read it.]"
            )
        out.append({"type": "text", "text": note})
    return out
