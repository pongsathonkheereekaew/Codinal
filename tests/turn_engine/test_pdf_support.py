import base64
import io
import sys
import time

import pytest
from pypdf import PdfWriter

from runtime.providers import ModelCapabilities
from runtime.turn_engine import pdf_support


def blank_pdf_url(pages=2):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=300)
    buffer = io.BytesIO()
    writer.write(buffer)
    return (
        "data:application/pdf;base64,"
        + base64.b64encode(buffer.getvalue()).decode()
    )


@pytest.fixture(autouse=True)
def reset_mode():
    pdf_support.set_fallback_mode("text")
    yield
    pdf_support.set_fallback_mode("text")


def test_inspect_counts_pages_and_rejects_non_pdf():
    result = pdf_support.inspect(blank_pdf_url(3))

    assert result["ok"] is True
    assert result["pages"] == 3
    assert pdf_support.inspect("plain text")["ok"] is False


def test_pdf_decode_rejects_bytes_over_the_local_budget(monkeypatch):
    monkeypatch.setattr(pdf_support, "MAX_PDF_BYTES", 5)
    encoded = base64.b64encode(b"%PDF-too-large").decode()

    result = pdf_support.inspect(
        f"data:application/pdf;base64,{encoded}",
    )

    assert result == {"ok": False, "error": "not a PDF data URL"}


def test_text_extraction_reads_at_most_the_page_budget(monkeypatch):
    calls = 0

    class Page:
        def extract_text(self):
            nonlocal calls
            calls += 1
            return "page"

    class Reader:
        pages = [Page() for _ in range(pdf_support.MAX_PDF_PAGES + 5)]

    monkeypatch.setattr("pypdf.PdfReader", lambda *_args, **_kwargs: Reader())
    encoded = base64.b64encode(b"%PDF-page-budget").decode()

    extracted = pdf_support._extract_text_local(
        f"data:application/pdf;base64,{encoded}",
    )

    assert extracted
    assert calls == pdf_support.MAX_PDF_PAGES


def test_timed_out_workers_do_not_prevent_the_next_job():
    sleeper = [sys.executable, "-c", "import time; time.sleep(5)"]
    started = time.monotonic()

    assert (
        pdf_support._run_worker_command(sleeper, "", timeout=0.05)
        is None
    )
    assert (
        pdf_support._run_worker_command(sleeper, "", timeout=0.05)
        is None
    )
    output = pdf_support._run_worker_command(
        [sys.executable, "-c", "print('ok')"],
        "",
        timeout=1,
    )

    assert output == "ok\n"
    assert time.monotonic() - started < 1


def test_scanned_pdf_becomes_visible_text_note():
    content = [
        {
            "type": "file",
            "file": {
                "filename": "scan.pdf",
                "file_data": blank_pdf_url(),
            },
        }
    ]

    adapted = pdf_support.adapt_content(
        content,
        ModelCapabilities(vision=False, pdf=False),
    )

    assert adapted[0]["type"] == "text"
    assert "no extractable text" in adapted[0]["text"]


def test_images_mode_renders_pages_for_vision_model():
    pdf_support.set_fallback_mode("images")
    content = [
        {
            "type": "file",
            "file": {
                "filename": "scan.pdf",
                "file_data": blank_pdf_url(2),
            },
        }
    ]

    adapted = pdf_support.adapt_content(
        content,
        ModelCapabilities(vision=True, pdf=False),
    )

    assert [part["type"] for part in adapted] == [
        "text",
        "image_url",
        "image_url",
    ]
    image = adapted[1]["image_url"]["url"]
    assert base64.b64decode(image.split(",", 1)[1]).startswith(
        b"\x89PNG\r\n\x1a\n"
    )
