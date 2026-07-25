import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_release_builder_pins_and_verifies_embedded_python():
    script = (ROOT / "scripts" / "build-macos-release.sh").read_text(
        encoding="utf-8"
    )

    assert 'PYTHON_VERSION="3.12.13"' in script
    assert 'PYTHON_BUILD="20260718"' in script
    assert (
        'PYTHON_SHA256="9a1e9e06175c10efd8378b904b07fa21'
        'bd791ab3345d7cdffeb4a76c9ff55903"'
    ) in script
    assert "--require-hashes" in script
    assert "codesign --verify --deep --strict" in script
    assert "stapler validate" in script
    assert "spctl --assess" in script
    assert "--keychain-profile" in script
    assert "notarytool submit" in script
    assert "stapler staple" in script
    assert "TAURI_SIGNING_PRIVATE_KEY_PATH" in script
    assert 'UPDATER_SOURCE_SIGNATURE="$UPDATER_SOURCE.sig"' in script
    assert '"$TAURI_ROOT/Cargo.toml"' in script
    assert '"$TAURI_ROOT/tauri.conf.json" "$APP_VERSION"' in script
    assert 'if [ "$TAURI_VERSION" != "tauri-cli 2.11.4" ]' in script
    assert 'grep -q "updater secret key.*does not match"' in script


def test_release_config_maps_runtime_to_expected_bundle_paths():
    config = json.loads(
        (
            ROOT
            / "desktop"
            / "src-tauri"
            / "tauri.release.conf.json"
        ).read_text(encoding="utf-8")
    )

    assert config["bundle"]["active"] is True
    assert config["bundle"]["targets"] == ["app"]
    assert config["bundle"]["createUpdaterArtifacts"] is True
    assert config["bundle"]["resources"] == {
        "resources/python/": "python/",
        "resources/runtime/": "runtime/",
    }


def test_packaged_smoke_rechecks_signature_after_launch():
    script = (ROOT / "scripts" / "smoke-macos-release.sh").read_text(
        encoding="utf-8"
    )

    assert script.count("codesign --verify --deep --strict") == 2
    assert "-B -m runtime.control_plane" in script


def test_gatekeeper_smoke_uses_transported_quarantined_archive():
    script = (ROOT / "scripts" / "smoke-macos-gatekeeper.sh").read_text(
        encoding="utf-8"
    )

    assert "ditto -x -k" in script
    assert "com.apple.quarantine" in script
    assert "stapler validate" in script
    assert "spctl --assess --type execute" in script
