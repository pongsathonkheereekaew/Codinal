from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_release_builder_checks_genuine_runtime_packaging_contract():
    script = (ROOT / "scripts" / "build-macos-release.sh").read_text(
        encoding="utf-8"
    )

    assert 'GPUI_ROOT="$ROOT/desktop/gpui"' in script
    assert 'RUNTIME_ROOT="$ROOT/crates/codinal-runtime"' in script
    assert "codesign --verify --deep --strict" in script
    assert "stapler validate" in script
    assert "spctl --assess" in script
    assert "--keychain-profile" in script
    assert "--apple-id \"$APPLE_ID\"" in script
    assert "--password \"$APPLE_PASSWORD\"" in script
    assert "--team-id \"$APPLE_TEAM_ID\"" in script
    assert "notarytool submit" in script
    assert "stapler staple" in script
    assert "CODINAL_UPDATE_SIGNING_PRIVATE_KEY_PATH" in script
    assert "CODINAL_UPDATE_SIGNING_PASSWORD" in script
    assert "UPDATE_KEY_PATH_VALUE=\"${CODINAL_UPDATE_SIGNING_PRIVATE_KEY_PATH:-}\"" in script
    assert "UPDATE_PASSWORD_VALUE=\"${CODINAL_UPDATE_SIGNING_PASSWORD:-}\"" in script
    assert 'shasum -a 256 "$ARTIFACT" > "$ARTIFACT.sha256"' in script
    assert (
        'shasum -a 256 "$UPDATER_ARTIFACT" > "$UPDATER_ARTIFACT.sha256"'
        in script
    )
    assert "CODINAL_UPDATE_MANIFEST_URL" in script
    assert "CODINAL_UPDATE_MANIFEST_PATH" in script
    assert "CODINAL_UPDATE_MANIFEST_NOTES" in script
    assert "CODINAL_UPDATE_MANIFEST_PUB_DATE" in script
    assert "install -m 755 \"$GPUI_ROOT/target/release/codinal-gpui\"" in script
    assert "install -m 755 \"$RUNTIME_ROOT/target/release/codinal-runtime\"" in script
    assert "install -m 644 \"$ROOT/desktop/assets/Codinal.icns\"" in script


def test_packaged_smoke_rechecks_signature_after_launch():
    script = (ROOT / "scripts" / "smoke-macos-release.sh").read_text(
        encoding="utf-8"
    )

    assert script.count("codesign --verify --deep --strict") == 2


def test_gatekeeper_smoke_uses_transported_quarantined_archive():
    script = (ROOT / "scripts" / "smoke-macos-gatekeeper.sh").read_text(
        encoding="utf-8"
    )

    assert "ditto -x -k" in script
    assert "com.apple.quarantine" in script
    assert "CODINAL_REQUIRE_NOTARIZATION" in script
    assert "bash \"$ROOT/scripts/smoke-macos-release.sh\" \"$APP\"" in script

def test_smoke_release_script_controls_resource_and_launch_checks():
    script = (ROOT / "scripts" / "smoke-macos-release.sh").read_text(
        encoding="utf-8"
    )

    assert "CODINAL_SKIP_EMBEDDED_IMPORTS" in script
    assert "CODINAL_SKIP_APP_LAUNCH" in script


def test_live_provider_smokes_bound_keychain_lookup():
    for name in ("smoke-opencode-go-runtime.sh", "smoke-deepseek-runtime.sh"):
        script = (ROOT / "scripts" / name).read_text(encoding="utf-8")

        assert "read_keychain_secret()" in script
        assert '"security"' in script
        assert "subprocess.run" in script
        assert "timeout=5" in script
        assert "read_keychain_secret" in script
