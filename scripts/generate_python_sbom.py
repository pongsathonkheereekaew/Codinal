#!/usr/bin/env python3
"""Generate a deterministic CycloneDX inventory from a hashed pip lock."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from pathlib import Path
from urllib.parse import quote

REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)")


def components_from_lock(lock: str) -> list[dict[str, object]]:
    components: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in lock.splitlines():
        match = REQUIREMENT.match(line)
        if match:
            name, version = match.groups()
            normalized = name.lower().replace("_", "-")
            current = {
                "type": "library",
                "name": normalized,
                "version": version,
                "purl": (
                    f"pkg:pypi/{quote(normalized)}@{quote(version)}"
                ),
                "hashes": [],
            }
            components.append(current)
            continue
        if current is not None and "--hash=sha256:" in line:
            digest = line.split("--hash=sha256:", 1)[1].split()[0].rstrip("\\")
            current["hashes"].append(
                {"alg": "SHA-256", "content": digest}
            )
    for component in components:
        if not component["hashes"]:
            component.pop("hashes")
    return components


def build_sbom(lock: str, version: str) -> dict[str, object]:
    lock_digest = hashlib.sha256(lock.encode("utf-8")).hexdigest()
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": (
            "urn:uuid:"
            + str(uuid.uuid5(uuid.NAMESPACE_URL, f"codinal:{lock_digest}"))
        ),
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "Codinal Python runtime",
                "version": version,
            },
            "properties": [
                {
                    "name": "codinal:requirements-lock:sha256",
                    "value": lock_digest,
                }
            ],
        },
        "components": components_from_lock(lock),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("lock", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    lock = args.lock.read_text(encoding="utf-8")
    sbom = build_sbom(lock, args.version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(sbom, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
