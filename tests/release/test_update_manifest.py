from scripts.generate_update_manifest import build_manifest
import json
import subprocess
import sys
from pathlib import Path


def test_update_manifest_targets_signed_apple_silicon_bundle():
    manifest = build_manifest(
        version="1.2.3",
        url="https://example.test/Codinal-1.2.3-macos-arm64.app.tar.gz",
        signature="signature\n",
        notes="Security and reliability fixes.",
        pub_date="2026-07-26T12:00:00Z",
    )

    assert manifest == {
        "version": "1.2.3",
        "notes": "Security and reliability fixes.",
        "pub_date": "2026-07-26T12:00:00Z",
        "schema": {"min_readable": 1, "max_readable": 1},
        "platforms": {
            "darwin-aarch64": {
                "signature": "signature",
                "url": (
                    "https://example.test/"
                    "Codinal-1.2.3-macos-arm64.app.tar.gz"
                ),
            }
        },
    }


def test_update_manifest_cli_generates_json_file(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    signature = tmp_path / "app.tar.gz.sig"
    signature.write_text("sig-line-1\nsig-line-2\n", encoding="utf-8")
    output = tmp_path / "latest.json"

    subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "generate_update_manifest.py"),
            "--version",
            "2.0.0",
            "--url",
            "https://example.test/Codinal-2.0.0-macos-arm64.app.tar.gz",
            "--signature-file",
            str(signature),
            "--notes",
            "CLI manifest generation smoke",
            "--pub-date",
            "2026-07-27T10:00:00Z",
            "--output",
            str(output),
        ],
        check=True,
    )

    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["version"] == "2.0.0"
    assert manifest["notes"] == "CLI manifest generation smoke"
    assert manifest["pub_date"] == "2026-07-27T10:00:00Z"
    assert manifest["schema"] == {"min_readable": 1, "max_readable": 1}
    assert "darwin-aarch64" in manifest["platforms"]
    assert manifest["platforms"]["darwin-aarch64"]["url"].endswith(
        "Codinal-2.0.0-macos-arm64.app.tar.gz"
    )
