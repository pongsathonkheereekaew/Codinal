#!/usr/bin/env python3
"""Generate the signed update manifest published with a Codinal release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

RUST_READABLE_SCHEMA_MIN = 1
RUST_READABLE_SCHEMA_MAX = 1


def build_manifest(
    *,
    version: str,
    url: str,
    signature: str,
    notes: str,
    pub_date: str,
) -> dict[str, object]:
    return {
        "version": version,
        "notes": notes,
        "pub_date": pub_date,
        "schema": {
            "min_readable": RUST_READABLE_SCHEMA_MIN,
            "max_readable": RUST_READABLE_SCHEMA_MAX,
        },
        "platforms": {
            "darwin-aarch64": {
                "signature": signature.strip(),
                "url": url,
            }
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--signature-file", required=True, type=Path)
    parser.add_argument("--notes", required=True)
    parser.add_argument("--pub-date", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest = build_manifest(
        version=args.version,
        url=args.url,
        signature=args.signature_file.read_text(encoding="utf-8"),
        notes=args.notes,
        pub_date=args.pub_date,
    )
    args.output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
