"""Bounded, local-only Office-to-PDF conversion through Stirling PDF."""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

import httpx


_SUPPORTED_SUFFIXES: Final = {
    ".doc", ".docm", ".docx", ".ppt", ".pptm", ".pptx", ".xls", ".xlsx"
}
_LOOPBACK_HOSTS: Final = {"localhost", "127.0.0.1", "::1"}
_MAX_BYTES: Final = 25 * 1024 * 1024
_CACHE_TTL_SECONDS: Final = 24 * 60 * 60
_CACHE_MAX_BYTES: Final = 100 * 1024 * 1024
_TIMEOUT_SECONDS: Final = 60.0
_HEALTH_TIMEOUT_SECONDS: Final = 5.0


@dataclass(frozen=True)
class StirlingPreview:
    status: str
    pdf_path: Path | None = None


def check_stirling_health(
    stirling_url: str | None,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, bool | str | None]:
    """Check the documented local Stirling status endpoint without relaying errors."""
    base_url = _validated_base_url(stirling_url)
    if base_url is None:
        return {"ok": False, "version": None}
    try:
        with httpx.Client(
            base_url=base_url,
            timeout=_HEALTH_TIMEOUT_SECONDS,
            transport=transport,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = client.get("/api/v1/info/status")
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return {"ok": False, "version": None}
    if not isinstance(payload, dict) or payload.get("status") != "UP":
        return {"ok": False, "version": None}
    version = payload.get("version")
    return {"ok": True, "version": version if isinstance(version, str) else None}


class StirlingConverter:
    """Convert supported workspace files using one configured loopback server.

    The caller owns workspace-path validation. This class validates the
    configured endpoint again, serializes conversions, and keeps PDFs only in
    the private cache directory rather than the workspace.
    """

    def __init__(
        self,
        stirling_url: str | None,
        cache_dir: str | Path,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = _validated_base_url(stirling_url)
        self._cache_dir = Path(cache_dir).expanduser()
        self._client = (
            httpx.Client(
                base_url=self._base_url,
                timeout=_TIMEOUT_SECONDS,
                transport=transport,
                follow_redirects=False,
                trust_env=False,
            )
            if self._base_url is not None
            else None
        )
        self._lock = threading.Lock()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def __enter__(self) -> "StirlingConverter":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def convert(self, source: str | Path) -> StirlingPreview:
        source_path = Path(source)
        if self._client is None:
            return StirlingPreview("unconfigured")
        if source_path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            return StirlingPreview("unsupported")
        try:
            if not source_path.is_file() or source_path.stat().st_size > _MAX_BYTES:
                return StirlingPreview("unsupported")
            fingerprint = _fingerprint(source_path)
        except (OSError, ValueError):
            return StirlingPreview("failed")

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self._cache_dir, 0o700)
        cached = self._cache_dir / f"{fingerprint}.pdf"
        with self._lock:
            if _usable_cache_file(cached):
                try:
                    os.utime(cached, None, follow_symlinks=False)
                except OSError:
                    return StirlingPreview("failed")
                return StirlingPreview("ready", cached)
            try:
                self._convert_to_cache(source_path, cached)
                self._prune_cache()
            except (httpx.HTTPError, OSError, ValueError):
                return StirlingPreview("failed")
        return StirlingPreview("ready", cached)

    def _convert_to_cache(self, source: Path, cached: Path) -> None:
        temporary_path: Path | None = None
        try:
            with source.open("rb") as input_file:
                if os.fstat(input_file.fileno()).st_size > _MAX_BYTES:
                    raise ValueError("Office file exceeds preview limit")
                with self._client.stream(
                    "POST",
                    "/api/v1/convert/file/pdf",
                    files={
                        "fileInput": (
                            source.name,
                            _BoundedReader(input_file, _MAX_BYTES),
                        )
                    },
                ) as response:
                    if response.status_code != 200:
                        raise ValueError("Stirling conversion failed")
                    content_type = response.headers.get("content-type", "")
                    if not content_type.lower().startswith("application/pdf"):
                        raise ValueError("Stirling response was not a PDF")
                    with tempfile.NamedTemporaryFile(
                        mode="wb",
                        dir=self._cache_dir,
                        prefix=".conversion-",
                        suffix=".tmp",
                        delete=False,
                    ) as temporary:
                        temporary_path = Path(temporary.name)
                        os.chmod(temporary_path, 0o600)
                        total = 0
                        for chunk in response.iter_bytes():
                            total += len(chunk)
                            if total > _MAX_BYTES:
                                raise ValueError("Stirling PDF exceeds preview limit")
                            temporary.write(chunk)
                        if total == 0:
                            raise ValueError("Stirling returned an empty PDF")
                        temporary.flush()
                        os.fsync(temporary.fileno())
            os.replace(temporary_path, cached)
            os.chmod(cached, 0o600)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _prune_cache(self) -> None:
        now = time.time()
        entries: list[tuple[Path, os.stat_result]] = []
        for entry in self._cache_dir.glob("*.pdf"):
            try:
                details = entry.lstat()
            except OSError:
                continue
            if not stat.S_ISREG(details.st_mode):
                entry.unlink(missing_ok=True)
                continue
            if now - details.st_mtime > _CACHE_TTL_SECONDS:
                entry.unlink(missing_ok=True)
            else:
                entries.append((entry, details))
        total = sum(details.st_size for _, details in entries)
        for entry, details in sorted(entries, key=lambda item: item[1].st_mtime):
            if total <= _CACHE_MAX_BYTES:
                break
            try:
                entry.unlink()
                total -= details.st_size
            except OSError:
                continue


def _validated_base_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "http"
        or parsed.hostname not in _LOOPBACK_HOSTS
        or port is None
        or port == 0
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return None
    host = parsed.hostname
    assert host is not None
    return f"http://{'[' + host + ']' if ':' in host else host}:{port}"


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            total += len(chunk)
            if total > _MAX_BYTES:
                raise ValueError("Office file exceeds preview limit")
            digest.update(chunk)
    return digest.hexdigest()


def _usable_cache_file(path: Path) -> bool:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return False
    try:
        details = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    return (
        stat.S_ISREG(details.st_mode)
        and details.st_size <= _MAX_BYTES
        and details.st_size > 0
        and time.time() - details.st_mtime <= _CACHE_TTL_SECONDS
    )


class _BoundedReader:
    def __init__(self, source, limit: int) -> None:
        self._source = source
        self._limit = limit
        self._total = 0

    def read(self, size: int = -1) -> bytes:
        remaining = self._limit - self._total
        requested = remaining + 1 if size < 0 else min(size, remaining + 1)
        chunk = self._source.read(requested)
        self._total += len(chunk)
        if self._total > self._limit:
            raise ValueError("Office file exceeds preview limit")
        return chunk
