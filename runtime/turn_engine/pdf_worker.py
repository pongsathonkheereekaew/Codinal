"""Killable subprocess entry point for untrusted PDF parsing."""

from __future__ import annotations

import json
import sys

from runtime.turn_engine import pdf_support


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in {"text", "images"}:
        return 2
    try:
        max_pages = min(
            max(1, int(sys.argv[2])),
            pdf_support.MAX_PDF_PAGES,
        )
    except ValueError:
        return 2
    max_input = ((pdf_support.MAX_PDF_BYTES + 2) // 3) * 4 + 64
    file_data = sys.stdin.read(max_input + 1)
    if len(file_data) > max_input:
        return 2
    if sys.argv[1] == "text":
        result = pdf_support._extract_text_local(file_data)
    else:
        result = pdf_support._rasterize_local(file_data, max_pages)
    output = json.dumps(result, separators=(",", ":"))
    if len(output.encode("utf-8")) > pdf_support.MAX_WORKER_OUTPUT_BYTES:
        return 3
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
