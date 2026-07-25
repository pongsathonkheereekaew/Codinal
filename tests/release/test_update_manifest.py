from scripts.generate_update_manifest import build_manifest


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
