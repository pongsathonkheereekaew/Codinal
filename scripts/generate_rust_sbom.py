#!/usr/bin/env python3
"""Generate a release SBOM from the Rust package metadata graphs."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import uuid
from pathlib import Path


def metadata(manifest: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            "cargo",
            "metadata",
            "--format-version",
            "1",
            "--locked",
            "--manifest-path",
            str(manifest),
            "--filter-platform",
            "aarch64-apple-darwin",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def build_sbom(manifests: list[Path], version: str) -> dict[str, object]:
    packages: dict[tuple[str, str], dict[str, object]] = {}
    for manifest in manifests:
        document = metadata(manifest)
        resolved_ids = {
            node["id"] for node in document["resolve"]["nodes"]
        }
        for package in document["packages"]:
            if package["id"] not in resolved_ids:
                continue
            key = (package["name"], package["version"])
            packages[key] = package
    package_rows = [
        {
            "type": "library",
            "name": name,
            "version": package["version"],
            "purl": f"pkg:cargo/{name}@{package['version']}",
            "properties": [
                {
                    "name": "codinal:source",
                    "value": package["source"] or "workspace",
                }
            ],
        }
        for (name, _version), package in sorted(packages.items())
    ]
    canonical = json.dumps(package_rows, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'codinal-rust:{digest}')}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "Codinal Rust runtime",
                "version": version,
            },
            "properties": [
                {"name": "codinal:rust-package-graph:sha256", "value": digest},
                {"name": "codinal:runtime-owner", "value": "rust"},
            ],
        },
        "components": package_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", action="append", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build_sbom(args.manifest, args.version), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
