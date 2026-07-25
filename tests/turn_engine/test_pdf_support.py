import base64
import io

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
