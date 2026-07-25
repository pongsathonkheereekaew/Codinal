from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "desktop" / "ui"
TAURI_CONFIG = ROOT / "desktop" / "src-tauri" / "tauri.conf.json"


def test_desktop_ui_has_native_three_pane_product_structure():
    html = (UI / "index.html").read_text(encoding="utf-8")

    assert 'id="sidebar"' in html
    assert 'id="conversation"' in html
    assert 'id="review-panel"' in html
    assert 'id="settings-dialog"' in html
    assert 'id="session-dialog"' in html
    assert 'id="new-task"' in html
    assert 'id="send-turn"' in html
    assert 'data-tauri-drag-region' in html
    assert "<style" not in html
    assert 'href="./app.css"' in html


def test_desktop_client_wires_runtime_approval_diff_and_shortcuts():
    script = (UI / "startup.js").read_text(encoding="utf-8")

    assert "/approvals/" in script
    assert "always_tool" in script
    assert "always_command" in script
    assert "/git/diff?against_base=true" in script
    assert "/git/apply" in script
    assert 'JSON.stringify({ model:' in script
    assert "delete_provider_secret" in script
    assert '"DELETE"' in script
    assert "pick_workspace" in script
    assert "event.metaKey" in script
    assert ".innerHTML" not in script


def test_desktop_csp_does_not_allow_inline_script_or_styles():
    config = TAURI_CONFIG.read_text(encoding="utf-8")

    assert '"withGlobalTauri": true' in config
    assert "'unsafe-inline'" not in config
