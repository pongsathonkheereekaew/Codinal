# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Andrew Ng
# Vendored and adapted from andrewyng/openworker:
# coworker/pdf_support.py @ 54b4bfd82d75704a4079ecea4f8f622aa152dbde.
"""Local PDF adaptation for models without native PDF support."""

from __future__ import annotations

import base64
import hashlib
import io
import itertools
import json
import logging
import struct
import subprocess
import sys
import zlib
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

MAX_EXTRACT_CHARS = 200_000
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 20
MAX_RASTER_PIXELS_PER_PAGE = 16_000_000
MAX_WORKER_OUTPUT_BYTES = 40 * 1024 * 1024
PDF_WORKER_TIMEOUT_SECONDS = 10
RASTER_SCALE = 2.0
RASTER_MAX_PAGES = MAX_PDF_PAGES
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
        raw = base64.b64decode(file_data[len(prefix) :], validate=True)
        return raw if len(raw) <= MAX_PDF_BYTES else None
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


def _extract_text_local(file_data: str) -> Optional[str]:
    raw = _pdf_bytes(file_data)
    if raw is None:
        return None
    try:
        from pypdf import PdfReader

        chunks: list[str] = []
        total = 0
        pages = PdfReader(io.BytesIO(raw), strict=False).pages
        for page in itertools.islice(pages, MAX_PDF_PAGES):
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


def _run_worker_command(
    command: list[str],
    input_text: str,
    *,
    timeout: float = PDF_WORKER_TIMEOUT_SECONDS,
) -> Optional[str]:
    try:
        completed = subprocess.run(
            command,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.warning("isolated PDF worker failed or timed out")
        return None
    if (
        completed.returncode != 0
        or len(completed.stdout.encode("utf-8")) > MAX_WORKER_OUTPUT_BYTES
    ):
        logger.warning("isolated PDF worker returned invalid output")
        return None
    return completed.stdout


def _run_isolated(mode: str, file_data: str, max_pages: int) -> Any:
    output = _run_worker_command(
        [
            sys.executable,
            "-m",
            "runtime.turn_engine.pdf_worker",
            mode,
            str(max_pages),
        ],
        file_data,
    )
    if output is None:
        return None
    try:
        return json.loads(output)
    except (json.JSONDecodeError, TypeError):
        logger.warning("isolated PDF worker returned malformed JSON")
        return None


def extract_text(file_data: str) -> Optional[str]:
    """Extract PDF text in a killable worker, capped for context safety."""

    def compute() -> Optional[str]:
        result = _run_isolated("text", file_data, MAX_PDF_PAGES)
        return result if isinstance(result, str) else None

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


def _rasterize_local(
    file_data: str,
    max_pages: int,
) -> Optional[list[str]]:
    raw = _pdf_bytes(file_data)
    if raw is None:
        return None
    try:
        import pypdfium2

        document = pypdfium2.PdfDocument(raw)
        pages: list[str] = []
        output_bytes = 0
        try:
            for index in range(min(len(document), max_pages)):
                page = document[index]
                width, height = page.get_size()
                if (
                    width
                    * RASTER_SCALE
                    * height
                    * RASTER_SCALE
                    > MAX_RASTER_PIXELS_PER_PAGE
                ):
                    return None
                bitmap = page.render(
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
                image = (
                    "data:image/png;base64,"
                    + base64.b64encode(png).decode("ascii")
                )
                output_bytes += len(image.encode("ascii"))
                if output_bytes > MAX_WORKER_OUTPUT_BYTES:
                    return None
                pages.append(image)
        finally:
            document.close()
        return pages or None
    except Exception:
        logger.warning("pdf rasterization failed", exc_info=True)
        return None


def rasterize(
    file_data: str,
    max_pages: int = RASTER_MAX_PAGES,
) -> Optional[list[str]]:
    """Render PDF pages in a killable worker as PNG data URLs."""

    def compute() -> Optional[list[str]]:
        result = _run_isolated(
            "images",
            file_data,
            min(max_pages, RASTER_MAX_PAGES),
        )
        if not isinstance(result, list) or not all(
            isinstance(item, str) for item in result
        ):
            return None
        return result

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
