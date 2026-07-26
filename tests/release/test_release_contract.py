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
        'PYTHON_SHA256="62aeee6161d57303a71a138b75fd5cc6f'
        'b8c89c4b1d9c7f0a052d89fa0b6652b"'
    ) in script
    assert "--require-hashes" in script
    assert "codesign --verify --deep --strict" in script
    assert "stapler validate" in script
    assert "spctl --assess" in script
    assert "--keychain-profile" in script
    assert "--apple-id \"$APPLE_ID\"" in script
    assert "--password \"@env:APPLE_PASSWORD\"" in script
    assert "--team-id \"$APPLE_TEAM_ID\"" in script
    assert "notarytool submit" in script
    assert "stapler staple" in script
    assert "TAURI_SIGNING_PRIVATE_KEY_PATH" in script
    assert "TAURI_SIGNING_PUBLIC_KEY" in script
    assert "TAURI_SIGNING_PUBLIC_KEY_PATH" in script
    assert 'UPDATER_SOURCE_SIGNATURE="$UPDATER_SOURCE.sig"' in script
    assert 'shasum -a 256 "$ARTIFACT" > "$ARTIFACT.sha256"' in script
    assert (
        'shasum -a 256 "$UPDATER_ARTIFACT" > "$UPDATER_ARTIFACT.sha256"'
        in script
    )
    assert "CODINAL_UPDATE_MANIFEST_URL" in script
    assert "CODINAL_UPDATE_MANIFEST_PATH" in script
    assert "CODINAL_UPDATE_MANIFEST_NOTES" in script
    assert "CODINAL_UPDATE_MANIFEST_PUB_DATE" in script
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
    assert "/v1/sessions/.*/mcp/connect" in script
    assert "/v1/sessions/.*/mcp/servers" in script


def test_gatekeeper_smoke_uses_transported_quarantined_archive():
    script = (ROOT / "scripts" / "smoke-macos-gatekeeper.sh").read_text(
        encoding="utf-8"
    )

    assert "ditto -x -k" in script
    assert "com.apple.quarantine" in script
    assert "CODINAL_REQUIRE_NOTARIZATION" in script
    assert 'CODINAL_SKIP_APP_LAUNCH=1' in script
    assert 'CODINAL_SKIP_EMBEDDED_IMPORTS=1' in script

def test_smoke_release_script_controls_resource_and_launch_checks():
    script = (ROOT / "scripts" / "smoke-macos-release.sh").read_text(
        encoding="utf-8"
    )

    assert "CODINAL_SKIP_EMBEDDED_IMPORTS" in script
    assert "CODINAL_SKIP_APP_LAUNCH" in script
    assert "-B -m runtime.control_plane" in script
