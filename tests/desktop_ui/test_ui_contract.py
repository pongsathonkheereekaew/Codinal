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
    assert 'id="project-search"' in html
    assert 'id="project-search-mode"' in html
    assert 'id="project-search-results"' in html
    assert 'id="add-context-root"' in html
    assert 'id="thread-search"' in html
    assert 'id="thread-search-next"' in html
    assert 'id="thread-search-previous"' in html
    assert 'id="export-thread"' in html
    assert 'id="return-to-parent"' in html
    assert 'id="worker-panel"' in html
    assert 'id="worker-list"' in html
    assert 'id="new-worker"' in html
    assert 'id="worker-dialog"' in html
    assert 'id="worker-task"' in html
    assert 'id="worker-ownership"' in html
    assert 'id="worker-dependencies"' in html
    assert 'id="plan-build-panel"' in html
    assert 'id="plan-build-list"' in html
    assert 'id="plan-build-dialog"' in html
    assert 'id="plan-build-tasks"' in html
    assert 'id="plan-build-models"' in html
    assert 'id="new-task"' in html
    assert 'id="send-turn"' in html
    assert 'id="attach-files"' in html
    assert 'id="attachment-input"' in html
    assert 'id="attachment-list"' in html
    assert 'id="context-items"' in html
    assert 'id="checkpoint-select"' in html
    assert 'id="restore-scope"' in html
    assert 'id="restore-checkpoint"' in html
    assert 'accept="image/png,image/jpeg,image/gif,image/webp,application/pdf"' in html
    assert 'data-tauri-drag-region' in html
    assert "<style" not in html
    assert 'href="./app.css"' in html


def test_desktop_client_wires_runtime_approval_diff_and_shortcuts():
    html = (UI / "index.html").read_text(encoding="utf-8")
    script = (UI / "startup.js").read_text(encoding="utf-8")

    assert "/approvals/" in script
    assert "/interactions" in script
    assert "question_requested" in script
    assert "plan_proposed" in script
    assert "plan-editor" in script
    assert "plan-task-select" in script
    assert "selected_task_ids" in script
    assert "verification" in script
    assert 'id="plan-panel"' in html
    assert "/plans" in script
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
    assert "BRANCH_SETTINGS" in script
    assert 'endpoint: "side-conversations"' in script
    assert "message_index" in script
    assert "Fork task from here" in script
    assert "Open side conversation" in script
    assert "/export.md" in script
    assert "threadSearchMatches" in script
    assert "findThreadMatches" in script
    assert "origin_session_id" in script
    assert "returnToParentSession" in script
    assert "isSafeForkBoundary(index)" in script
    assert "state.highlightedMessageIndex = null" in script
    assert "sessionSelectionGeneration" in script
    assert "/tree?" in script
    assert "/project/search?" in script
    assert "renderProjectSearchResults" in script
    assert "cancelProjectSearch" in script
    scheduled_search = script.split(
        "function scheduleProjectSearch()",
        1,
    )[1].split("async function loadProjectSearch()", 1)[0]
    assert "cancelProjectSearch()" not in scheduled_search
    assert "projectSearchController?.abort()" in scheduled_search
    assert "Search unavailable" in script
    assert "/roots" in script
    assert "loadRootsAndTree" in script
    assert "Root unavailable — reconnect or remove it" in script
    assert "root.available === false" in script
    assert "/context" in script
    assert "/project/open" in script
    assert "contextItems" in script
    assert "content_part" in script
    assert "fingerprint" in script
    assert "Add file context" in script
    assert "Add folder context" in script
    assert "Add Git context" in script
    assert "Open in default app" in script
    assert "Reveal in Finder" in script
    assert "_codinal_context" in script
    assert "requestInput" in script
    assert "displayTurnInput" in script
    assert "/workers" in script
    assert "/steer" in script
    assert "/cancel" in script
    assert "/adopt" in script
    assert "worker_status" in script
    assert "renderWorkers" in script
    assert "/plan-builds" in script
    assert "plan_build_status" in script
    assert "renderPlanBuilds" in script
    assert '(build) => build.state === "ready"' in script
    assert "selected_worker_id" in script
    assert "Start parallel comparison" in script
    assert "/candidates/" in script
    assert "Review diff" in script
    assert "candidateDiffs" in script
    assert "/goals" in script
    assert "goal_status" in script
    assert "Continue goal" in script
    assert "Add evidence" in script
    assert "Audit complete" in script
    assert "Audit blocked" in script
    assert "goalCompletionMapping" in script
    assert "goalBlockerSummary" in script
    assert '["completed", "blocked"].includes(goal.state)' in script
    assert "goal.requirement_evidence" in script
    assert "Audit evidence ·" in script
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
