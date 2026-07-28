from __future__ import annotations

import os
import time

import httpx

from runtime.artifacts import StirlingConverter


PDF = b"%PDF-1.7\npreview\n"


def test_conversion_is_loopback_only_and_returns_cached_private_pdf(tmp_path):
    source = tmp_path / "report.docx"
    source.write_bytes(b"office document")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.path == "/api/v1/convert/file/pdf"
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})

    cache = tmp_path / "cache"
    with StirlingConverter(
        "http://localhost:8080", cache, transport=httpx.MockTransport(handler)
    ) as converter:
        first = converter.convert(source)
        second = converter.convert(source)

    assert first.status == "ready"
    assert first.pdf_path is not None
    assert first.pdf_path.read_bytes() == PDF
    assert second == first
    assert len(calls) == 1
    assert (first.pdf_path.stat().st_mode & 0o777) == 0o600
    assert (cache.stat().st_mode & 0o777) == 0o700
    assert converter._client is None or converter._client._trust_env is False


def test_conversion_replaces_a_cache_symlink_instead_of_following_it(tmp_path):
    source = tmp_path / "report.docx"
    source.write_bytes(b"office document")
    cache = tmp_path / "cache"
    secret = tmp_path / "secret.pdf"
    secret.write_bytes(b"outside cache")
    calls = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(True)
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})

    with StirlingConverter(
        "http://localhost:8080", cache, transport=httpx.MockTransport(handler)
    ) as converter:
        first = converter.convert(source)
        assert first.pdf_path is not None
        first.pdf_path.unlink()
        first.pdf_path.symlink_to(secret)
        second = converter.convert(source)

    assert second.status == "ready"
    assert second.pdf_path is not None
    assert not second.pdf_path.is_symlink()
    assert second.pdf_path.read_bytes() == PDF
    assert calls == [True, True]


def test_conversion_never_uses_nonloopback_or_unsupported_files(tmp_path):
    source = tmp_path / "report.exe"
    source.write_bytes(b"binary")

    for endpoint in (None, "https://localhost:8080", "http://example.com:8080"):
        with StirlingConverter(endpoint, tmp_path / "cache") as converter:
            result = converter.convert(source)
        assert result.pdf_path is None
        assert result.status in {"unconfigured", "unsupported"}


def test_conversion_rejects_oversized_input_without_contacting_stirling(tmp_path):
    source = tmp_path / "large.docx"
    source.write_bytes(b"x" * (25 * 1024 * 1024 + 1))
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})

    with StirlingConverter(
        "http://localhost:8080", tmp_path / "cache", transport=httpx.MockTransport(handler)
    ) as converter:
        assert converter.convert(source).status == "unsupported"

    assert calls == []


def test_conversion_rejects_non_pdf_and_oversized_responses_without_cache(tmp_path):
    source = tmp_path / "sheet.xlsx"
    source.write_bytes(b"sheet")
    cache = tmp_path / "cache"

    def non_pdf(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not a pdf", headers={"content-type": "text/plain"})

    with StirlingConverter(
        "http://127.0.0.1:8080", cache, transport=httpx.MockTransport(non_pdf)
    ) as converter:
        assert converter.convert(source).status == "failed"

    assert not list(cache.glob("*.pdf"))


def test_cache_cleanup_expires_old_entries_and_prunes_lru(tmp_path):
    source = tmp_path / "slides.pptx"
    source.write_bytes(b"slides")
    cache = tmp_path / "cache"
    cache.mkdir()
    old = cache / "old.pdf"
    old.write_bytes(PDF)
    os.utime(old, (time.time() - 25 * 60 * 60,) * 2)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})

    with StirlingConverter(
        "http://[::1]:8080", cache, transport=httpx.MockTransport(handler)
    ) as converter:
        ready = converter.convert(source)

    assert ready.status == "ready"
    assert not old.exists()
