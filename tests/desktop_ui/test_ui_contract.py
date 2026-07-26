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
    assert 'id="context-roots"' in html
    assert 'id="project-tree"' in html
    assert 'id="add-context-root"' in html
    assert 'id="new-task"' in html
    assert 'id="send-turn"' in html
    assert 'id="attach-files"' in html
    assert 'id="attachment-input"' in html
    assert 'id="attachment-list"' in html
    assert 'id="checkpoint-select"' in html
    assert 'id="restore-scope"' in html
    assert 'id="restore-checkpoint"' in html
    assert 'accept="image/png,image/jpeg,image/gif,image/webp,application/pdf"' in html
    assert 'data-tauri-drag-region' in html
    assert "<style" not in html
    assert 'href="./app.css"' in html


def test_desktop_client_wires_runtime_approval_diff_and_shortcuts():
    script = (UI / "startup.js").read_text(encoding="utf-8")

    assert "/approvals/" in script
    assert "/interactions" in script
    assert "question_requested" in script
    assert "plan_proposed" in script
    assert "directory_requested" in script
    assert "always_tool" in script
    assert "always_command" in script
    assert "/git/diff?against_base=true" in script
    assert "/git/apply" in script
    assert "/checkpoints" in script
    assert "/restore" in script
    assert 'JSON.stringify({ scope:' in script
    assert 'JSON.stringify({ model:' in script
    assert "delete_provider_secret" in script
    assert '"DELETE"' in script
    assert "pick_workspace" in script
    assert "FileReader" in script
    assert "attachmentsPending" in script
    assert "attachmentQueue" in script
    assert "invalidateAttachments()" in script
    assert "state.attachmentReader?.abort()" in script
    assert "switchWorkspace(workspace)" in script
    assert "switchWorkspace(path)" in script
    assert 'el["agent-mode"].value === "plan"' in script
    assert '? "plan"' in script
    assert "const sessionId = state.sessionId" in script
    assert "state.sessionId !== sessionId" in script
    assert "interactionSession" in script
    assert "/v1/sessions/search" in script
    assert "/fork" in script
    assert "message_index" in script
    assert "Fork task from here" in script
    assert "isSafeForkBoundary(index)" in script
    assert "state.highlightedMessageIndex = null" in script
    assert "sessionSelectionGeneration" in script
    assert "/tree?" in script
    assert "/roots" in script
    assert "loadRootsAndTree" in script
    assert "Root unavailable — reconnect or remove it" in script
    assert "root.available === false" in script
    load_sessions = script.split(
        "async function loadSessions() {",
        1,
    )[1].split("\n}", 1)[0]
    assert "syncAgentMode(active)" in load_sessions
    workspace_switch = script.split(
        "function switchWorkspace(workspace) {",
        1,
    )[1].split("\n}", 1)[0]
    assert "if (state.busy)" in workspace_switch
    assert "disconnectSocket()" in workspace_switch
    assert "state.sessionId = `session-${crypto.randomUUID()}`" in workspace_switch
    assert "state.messages = []" in workspace_switch
    assert "state.workspace = workspace" in workspace_switch
    assert 'el["new-task"].disabled = busy' in script
    assert 'el["choose-workspace"].disabled = busy' in script
    assert "queueAttachments(event.target.files)" in script
    assert '"type": "image_url"' in script
    assert '"type": "file"' in script
    assert "event.metaKey" in script
    assert ".innerHTML" not in script


def test_desktop_csp_does_not_allow_inline_script_or_styles():
    config = TAURI_CONFIG.read_text(encoding="utf-8")

    assert '"withGlobalTauri": true' in config
    assert "'unsafe-inline'" not in config
