from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zlib


ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "desktop" / "ui"
TAURI_CONFIG = ROOT / "desktop" / "src-tauri" / "tauri.conf.json"


def _png_top_left_alpha(path: Path) -> int:
    """Read the top-left alpha byte from our non-interlaced RGBA PNGs."""
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    idat = []
    while offset < len(data):
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + size]
        if kind == b"IHDR":
            _width, _height, bit_depth, color_type, compression, filter_, interlace = (
                struct.unpack(">IIBBBBB", payload)
            )
            assert (bit_depth, color_type, compression, filter_, interlace) == (
                8,
                6,
                0,
                0,
                0,
            )
        elif kind == b"IDAT":
            idat.append(payload)
        offset += size + 12
    row = zlib.decompress(b"".join(idat))
    assert row[0] in {0, 1, 2, 3, 4}
    return row[4]


def test_desktop_ui_has_native_three_pane_product_structure():
    html = (UI / "index.html").read_text(encoding="utf-8")

    assert 'id="sidebar"' in html
    assert 'id="conversation"' in html
    assert 'id="review-panel"' in html
    assert 'id="settings-dialog"' in html
    assert 'class="settings-nav"' in html
    assert 'class="settings-content"' in html
    assert 'id="settings-toggle-theme"' in html
    assert 'id="settings-search"' in html
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
    assert 'id="mcp-server-list"' in html
    assert 'id="mcp-server-name"' in html
    assert 'id="mcp-transport"' in html
    assert 'id="mcp-url"' in html
    assert 'id="mcp-command"' in html
    assert 'id="mcp-args"' in html
    assert 'id="mcp-include-tools"' in html
    assert 'id="mcp-exclude-tools"' in html
    assert 'id="connect-mcp-server"' in html
    assert 'id="artifact-list"' in html
    assert 'id="artifact-empty"' in html
    assert 'id="artifact-preview"' in html
    assert 'id="artifact-preview-path"' in html
    assert 'id="send-turn"' in html
    assert 'id="attach-files"' in html
    assert 'id="attachment-input"' in html
    assert 'id="attachment-list"' in html
    assert 'id="context-items"' in html
    assert 'id="checkpoint-select"' in html
    assert 'id="restore-scope"' in html
    assert 'id="restore-checkpoint"' in html
    assert 'id="terminal-host"' in html
    assert 'id="terminal-restart"' in html
    assert 'id="terminal-clear"' in html
    assert 'id="terminal-status"' in html
    assert 'accept="image/png,image/jpeg,image/gif,image/webp,application/pdf"' in html
    assert 'data-tauri-drag-region' in html
    assert "<style" not in html
    assert 'href="./app.css"' in html


def test_desktop_ui_has_accessibility_floor():
    html = (UI / "index.html").read_text(encoding="utf-8")

    # Skip-link is the first focusable element.
    assert 'class="skip-link"' in html
    assert html.index('class="skip-link"') < html.index('id="app"')
    # Runtime status chip is an announced live region.
    assert 'id="runtime-status"' in html
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html
    # Every dialog is modal + labelled.
    for dialog in (
        "settings-dialog",
        "session-dialog",
        "worker-dialog",
        "plan-build-dialog",
        "goal-dialog",
        "goal-evidence-dialog",
    ):
        assert f'id="{dialog}"' in html
        assert f'aria-labelledby="{dialog}-title"' in html
    # Diff / terminal regions carry role + label.
    assert 'id="diff-view"' in html and 'role="log"' in html
    assert 'id="terminal-host"' in html and 'aria-label="Interactive terminal"' in html


def test_desktop_ui_has_diagnostics_and_audit_surface():
    html = (UI / "index.html").read_text(encoding="utf-8")
    script = (UI / "startup.js").read_text(encoding="utf-8")

    for element in (
        "diagnostics-status",
        "audit-chain-status",
        "audit-log",
        "copy-support-bundle",
        "rollback-update",
    ):
        assert f'id="{element}"' in html
    assert "/v1/status" in script
    assert "/v1/audit" in script
    assert "loadDiagnostics" in script
    assert "loadAuditLog" in script
    assert "renderAuditLog" in script
    assert "copySupportBundle" in script
    assert "secrets redacted" in script


def test_desktop_ui_defers_editor_bundle_until_a_file_is_opened():
    """Keep the 1.2MB CodeMirror bundle off the initial startup critical path."""
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert '<script src="./dist/editor.js"></script>' not in html
    script = (UI / "startup.js").read_text(encoding="utf-8")
    assert 'function loadEditorBundle()' in script
    assert 'script.src = "./dist/editor.js"' in script
    assert "await loadEditorBundle();" in script
    assert "window.CodinalEditor" in script


def test_desktop_ui_defers_terminal_bundle_until_terminal_is_needed():
    """Keep xterm off the initial startup critical path too."""
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert '<script src="./vendor/xterm.js"></script>' not in html
    assert '<script src="./vendor/xterm-addon-fit.js"></script>' not in html
    script = (UI / "startup.js").read_text(encoding="utf-8")
    assert 'function loadTerminalBundle()' in script
    assert 'loadScript("./vendor/xterm.js")' in script
    assert 'await loadTerminalBundle();' in script
    assert "terminalOpening" in script
    assert "openTerminalViewInner" in script
    assert "const opening = state.terminalOpening" in script
    assert 'await invoke("pty_kill", { sessionId }).catch(() => {});' in script
    assert 'cursor: "#a78bfa"' not in script
    assert 'cursor: "#6d4aff"' not in script


def test_terminal_stays_out_of_the_initial_conversation_layout():
    """A blank terminal should not push the Codex-style composer upward."""
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert 'id="terminal-panel" class="terminal-panel is-hidden"' in html
    script = (UI / "startup.js").read_text(encoding="utf-8")
    assert "function showTerminalView()" in script
    assert "function hideTerminalView()" in script
    assert 'classList.remove("is-hidden")' in script
    assert 'classList.add("is-hidden")' in script
    assert 'el.prompt.focus();' in script
    assert 'classList.contains("is-hidden")' in script
    assert "terminalViewGeneration" in script
    assert "if (state.terminal)" in script


def test_wide_mac_layout_uses_a_codex_style_reading_column():
    """Large windows must not stretch conversation content edge to edge."""
    css = (UI / "app.css").read_text(encoding="utf-8")
    assert "clamp(248px, 18.75vw, 360px)" in css
    assert "@media (min-width: 1440px)" in css
    assert "width: min(840px, calc(100% - 44px));" in css
    assert "margin-left: clamp(72px, 9.6vw, 188px);" in css
    assert ".app-shell.review-open .message-list" in css


def test_environment_panel_is_a_codex_style_right_utility_rail():
    """The wide layout reserves a persistent rail for task context and subagents."""
    css = (UI / "app.css").read_text(encoding="utf-8")
    markup = (UI / "index.html").read_text(encoding="utf-8")
    assert ".app-shell {\n  position: relative;" in css
    assert "grid-template-columns: clamp(248px, 18.75vw, 360px) minmax(0, 1fr) clamp(300px, 18.75vw, 360px);" in css
    assert "grid-column: 3;" in css
    assert "border-left: 0.5px solid var(--line);" in css
    assert "visibility: hidden;" in css
    assert "pointer-events: none;" in css
    assert ".review-open .review-panel" in css
    assert "visibility: visible;" in css
    assert 'aria-label="Environment and changes"' in markup
    assert 'class="environment-overview"' in markup
    assert 'id="environment-details"' in markup
    assert 'aria-label="Subagents"' in markup
    assert ">Subagents<" in markup


def test_utility_rail_has_separate_environment_and_subagents_views():
    """Context and delegation must be first-class peer views, not nested chrome."""
    html = (UI / "index.html").read_text(encoding="utf-8")
    script = (UI / "startup.js").read_text(encoding="utf-8")
    css = (UI / "app.css").read_text(encoding="utf-8")

    assert 'id="utility-tabs"' in html
    assert 'id="utility-environment-tab"' in html
    assert 'id="utility-subagents-tab"' in html
    assert 'id="utility-environment"' in html
    assert 'id="utility-subagents"' in html
    assert "function selectUtilityView" in script
    assert "function moveUtilityTab" in script
    assert "ArrowRight" in script and "ArrowLeft" in script
    assert "Home" in script and "End" in script
    assert '"subagents"' in script
    assert ".utility-tabs" in css
    assert ".utility-view.is-hidden" in css


def test_task_workspace_keeps_conversation_context_visible_before_messages():
    """An empty task still reads as a workspace rather than a landing page."""
    html = (UI / "index.html").read_text(encoding="utf-8")
    script = (UI / "startup.js").read_text(encoding="utf-8")
    css = (UI / "app.css").read_text(encoding="utf-8")

    assert 'id="conversation-context"' in html
    assert 'id="conversation-summary"' in html
    assert "renderConversationContext" in script
    assert ".conversation-context" in css
    assert ".empty-state.is-empty-workspace" in css


def test_workspace_picker_uses_a_native_dialog_not_an_apple_script_bridge():
    source = (ROOT / "desktop/src-tauri/src/workspace.rs").read_text(encoding="utf-8")
    manifest = (ROOT / "desktop/src-tauri/Cargo.toml").read_text(encoding="utf-8")

    assert "rfd::FileDialog" in source
    assert "osascript" not in source
    assert 'rfd = "=0.17.2"' in manifest


def test_sidebar_uses_quiet_codex_navigation_primitives():
    """Task navigation must not visually dominate the workspace."""
    css = (UI / "app.css").read_text(encoding="utf-8")
    new_task = css.split(".new-task {", 1)[1].split("}\n\n.new-task:hover", 1)[0]
    assert "background: transparent;" in new_task
    assert ".new-task:hover {\n  background: var(--surface-hover);" in css


def test_header_and_composer_use_compact_mac_primitives():
    css = (UI / "app.css").read_text(encoding="utf-8")
    assert ".task-header {" in css
    assert "min-height: 52px;" in css
    assert ".composer {" in css
    assert "border-radius: 16px;" in css
    assert ".composer select {\n  appearance: none;" in css


def test_composer_preserves_all_controls_at_the_minimum_macos_window_width():
    css = (UI / "app.css").read_text(encoding="utf-8")
    assert "@media (max-width: 900px)" in css
    assert ".composer-options {\n    gap: 2px;" in css
    assert "#model-select {\n    max-width: 112px;" in css
    assert ".shortcut-hint {\n    display: none;" in css


def test_every_visible_titlebar_zone_supports_native_window_zoom():
    script = (UI / "startup.js").read_text(encoding="utf-8")
    assert "function zoomFromTitlebar(event)" in script
    assert 'document.addEventListener("dblclick", (event) => {' in script
    assert 'event.target.closest("[data-tauri-drag-region]")' in script
    assert 'event.target.closest("button, input, select, textarea, a")' in script


def test_app_icon_uses_a_dock_safe_margin_around_the_monochrome_tile():
    icon = (ROOT / "desktop" / "src-tauri" / "icons" / "icon.svg").read_text(
        encoding="utf-8"
    )
    assert '<rect x="144" y="144" width="736" height="736"' in icon
    assert 'fill="#111111"' in icon
    png = ROOT / "desktop" / "src-tauri" / "icons" / "icon.png"
    assert _png_top_left_alpha(png) == 0
    if sys.platform != "darwin":
        return
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "icon.iconset"
        subprocess.run(
            [
                "iconutil",
                "-c",
                "iconset",
                str(ROOT / "desktop" / "src-tauri" / "icons" / "icon.icns"),
                "-o",
                str(output),
            ],
            check=True,
        )
        assert _png_top_left_alpha(output / "icon_512x512@2x.png") == 0


def test_settings_use_a_full_page_mac_layout_not_a_small_modal():
    css = (UI / "app.css").read_text(encoding="utf-8")
    script = (UI / "startup.js").read_text(encoding="utf-8")
    markup = (UI / "index.html").read_text(encoding="utf-8")
    assert ".settings-dialog {\n  width: 100vw;" in css
    assert "height: 100vh;" in css
    assert "grid-template-columns: clamp(238px, 18.75vw, 320px) minmax(0, 1fr);" in css
    assert "@media (max-width: 760px)" in css
    assert 'activateSettingsNav(link.getAttribute("href").slice(1));' in script
    assert "function filterSettings()" in script
    assert 'link.querySelector("span").textContent.trim()' in script
    assert 'href="#settings-office"' in markup
    assert 'event.key === ","' in script
    assert 'if (el["settings-dialog"].open)' in script


def test_empty_workspace_hides_secondary_sidebar_and_routing_chrome():
    script = (UI / "startup.js").read_text(encoding="utf-8")
    markup = (UI / "index.html").read_text(encoding="utf-8")
    assert "function updateContextPanelVisibility()" in script
    assert "!state.workspace || !state.roots.length" in script
    assert "updateContextPanelVisibility();" in script
    assert 'el["routing-resolution"].classList.toggle("is-hidden", !degradations.length);' in script
    assert 'class="routing-resolution is-hidden"' in markup


def test_no_project_empty_state_invites_a_conversation_without_a_workspace():
    html = (UI / "index.html").read_text(encoding="utf-8")
    script = (UI / "startup.js").read_text(encoding="utf-8")

    assert "Start a conversation now, or add a project" in html
    assert "No project selected" in html
    assert 'return "No project selected";' in script
    assert '|| "Add project"' in script


def test_terminal_bundle_loader_retries_and_preserves_xterm_load_order(tmp_path):
    """Load xterm before its addon and allow a transient failure to retry."""
    import subprocess

    runner = tmp_path / "terminal-loader.mjs"
    runner.write_text(
        """
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync("desktop/ui/startup.js", "utf8");
const start = source.indexOf("function loadScript(src)");
const end = source.indexOf("\\n\\nfunction updateTerminalStatus", start);
assert.ok(start >= 0 && end > start, "terminal bundle loader source missing");
const loader = source.slice(start, end);
const requested = [];
const pending = [];
const context = {
  state: { terminalLoad: null },
  window: {},
  document: {
    createElement() { return {}; },
    head: {
      append(node) {
        requested.push(node.src);
        pending.push(node);
      },
    },
  },
};
vm.runInNewContext(`${loader}; globalThis.load = loadTerminalBundle;`, context);
const missingBridge = context.load();
pending.shift().onload();
await Promise.resolve();
pending.shift().onload();
await assert.rejects(missingBridge, /Terminal module did not initialize/);
assert.equal(context.state.terminalLoad, null, "a missing terminal bridge must retry");
const failed = context.load();
pending.shift().onerror();
await assert.rejects(failed, /Could not load/);
assert.equal(context.state.terminalLoad, null, "a failed terminal load must retry");
const first = context.load();
const second = context.load();
assert.equal(first, second, "concurrent callers must share the loader promise");
context.window.Terminal = function Terminal() {};
pending.shift().onload();
await Promise.resolve();
context.window.FitAddon = { FitAddon: function FitAddon() {} };
pending.shift().onload();
await Promise.all([first, second]);
assert.deepEqual(requested, [
  "./vendor/xterm.js",
  "./vendor/xterm-addon-fit.js",
  "./vendor/xterm.js",
  "./vendor/xterm.js",
  "./vendor/xterm-addon-fit.js",
]);
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["node", str(runner)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_editor_bundle_loader_loads_once_and_exposes_the_bridge(tmp_path):
    """Exercise the real lazy loader so concurrent file opens share one request."""
    import subprocess

    runner = tmp_path / "editor-loader.mjs"
    runner.write_text(
        """
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync("desktop/ui/startup.js", "utf8");
const start = source.indexOf("function loadEditorBundle()");
const end = source.indexOf("\\n\\nfunction lspLanguageForPath", start);
assert.ok(start >= 0 && end > start, "editor bundle loader source missing");
const loader = source.slice(start, end);
let appended = 0;
let pendingNode = null;
const context = {
  state: { editorLoad: null },
  window: {},
  document: {
    createElement() { return {}; },
    head: {
      append(node) {
        appended += 1;
        pendingNode = node;
      },
    },
  },
};
vm.runInNewContext(`${loader}; globalThis.load = loadEditorBundle;`, context);
const missingBridge = context.load();
pendingNode.onload();
await assert.rejects(missingBridge, /Editor module did not initialize/);
assert.equal(context.state.editorLoad, null, "a missing bridge must permit retry");
const failed = context.load();
pendingNode.onerror();
await assert.rejects(failed, /Could not load editor module/);
assert.equal(context.state.editorLoad, null, "a failed load must permit retry");
const first = context.load();
const second = context.load();
assert.equal(first, second, "concurrent opens must share the loader promise");
context.window.CodinalEditor = { mount() {} };
pendingNode.onload();
await Promise.all([first, second]);
assert.equal(appended, 3, "each failed load should permit one fresh retry");
assert.equal(context.state.editorLoad, first);
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["node", str(runner)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_streaming_deltas_are_frame_batched_without_rerendering_history():
    """Streaming must update only the live assistant message at display cadence."""
    script = (UI / "startup.js").read_text(encoding="utf-8")

    assert "scheduleLiveAssistantRender" in script
    assert "requestAnimationFrame" in script
    assert ".message.is-streaming .message-content" in script


def test_persisted_conversation_messages_reuse_rendered_dom():
    """Long histories should not reparse Markdown for unrelated rerenders."""
    script = (UI / "startup.js").read_text(encoding="utf-8")
    assert "messageRenderCache: new Map()" in script
    assert "function renderPersistedMessage(message, index)" in script
    assert "cached.message === message" in script
    assert "fragment.append(renderPersistedMessage(message, index));" in script
    assert "function pruneMessageRenderCache(visible)" in script


def test_message_render_cache_prunes_removed_history(tmp_path):
    """Execute the real pruning helper to prevent stale DOM retention."""
    import subprocess

    runner = tmp_path / "message-cache-prune.mjs"
    runner.write_text(
        """
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync("desktop/ui/startup.js", "utf8");
const start = source.indexOf("function pruneMessageRenderCache(visible)");
const end = source.indexOf("\\n\\nfunction renderConversation", start);
assert.ok(start >= 0 && end > start, "message cache prune source missing");
const prune = source.slice(start, end);
const context = { state: { messageRenderCache: new Map([[0, {}], [3, {}], [9, {}]]) } };
vm.runInNewContext(`${prune}; globalThis.prune = pruneMessageRenderCache;`, context);
context.prune([{ index: 0 }, { index: 3 }]);
assert.deepEqual([...context.state.messageRenderCache.keys()], [0, 3]);
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["node", str(runner)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_streaming_frame_batcher_updates_only_the_live_message(tmp_path):
    """Execute the real scheduler source against a tiny DOM-like harness."""
    import subprocess

    runner = tmp_path / "streaming-batcher.mjs"
    runner.write_text(
        """
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync("desktop/ui/startup.js", "utf8");
const start = source.indexOf("function scheduleLiveAssistantRender()");
const end = source.indexOf("\\n\\nfunction findThreadMatches", start);
assert.ok(start >= 0 && end > start, "streaming scheduler source missing");
const scheduler = source.slice(start, end);
const frames = [];
let historyRenders = 0;
let liveUpdates = 0;
let highlightedScrolls = 0;
const content = {
  _value: "",
  set textContent(value) { this._value = value; liveUpdates += 1; },
};
const highlighted = { scrollIntoView() { highlightedScrolls += 1; } };
const messageList = {
  live: content,
  highlighted: null,
  querySelector(selector) {
    if (selector === ".message.is-streaming .message-content") return this.live;
    if (selector === ".message.is-search-match") return this.highlighted;
    return null;
  },
};
const context = {
  state: { liveAssistant: "a", liveAssistantFrame: null },
  window: { requestAnimationFrame(callback) { frames.push(callback); return frames.length; } },
  el: { "message-list": messageList, conversation: { scrollTop: 0, scrollHeight: 99 } },
  renderConversation() { historyRenders += 1; },
};
vm.runInNewContext(`${scheduler}; globalThis.schedule = scheduleLiveAssistantRender;`, context);
context.schedule();
context.state.liveAssistant += "b";
context.schedule();
context.state.liveAssistant += "c";
context.schedule();
assert.equal(frames.length, 1, "multiple deltas share one frame");
frames.shift()();
assert.equal(content._value, "abc");
assert.equal(liveUpdates, 1, "only the live node changes");
assert.equal(historyRenders, 0, "history is not rebuilt");
assert.equal(context.el.conversation.scrollTop, 99);

messageList.highlighted = highlighted;
context.el.conversation.scrollTop = 7;
context.schedule();
frames.shift()();
assert.equal(highlightedScrolls, 1, "active search match keeps its position");
assert.equal(context.el.conversation.scrollTop, 7, "search does not force bottom scroll");

context.state.liveAssistant = null;
context.schedule();
frames.shift()();
assert.equal(historyRenders, 1, "final or switched stream flushes through normal render");
""",
        encoding="utf-8",
    )
    subprocess.run(["node", str(runner)], check=True, cwd=ROOT)


def test_boot_does_not_block_first_paint_on_noncritical_settings():
    script = (UI / "startup.js").read_text(encoding="utf-8")

    settings_start = script.index("const settingsLoad = loadSettings().catch")
    sessions_ready = script.index("await loadSessions();", settings_start)
    first_paint = script.index('el.app.classList.remove("is-hidden");', sessions_ready)
    assert settings_start < sessions_ready < first_paint


def test_session_model_wins_over_late_global_settings(tmp_path):
    import subprocess

    runner = tmp_path / "active-model.mjs"
    runner.write_text(
        """
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync("desktop/ui/startup.js", "utf8");
const resolverStart = source.indexOf("function resolveActiveModel");
const settingsEnd = source.indexOf("\\n\\nasync function saveStirlingUrl", resolverStart);
const selectStart = source.indexOf("function selectModel");
const selectEnd = source.indexOf("\\n\\nasync function newTask", selectStart);
assert.ok(resolverStart >= 0 && settingsEnd > resolverStart, "settings source missing");
assert.ok(selectStart >= 0 && selectEnd > selectStart, "model selection source missing");

function selectElement() {
  return {
    options: [], value: "", replaceChildren() { this.options = []; },
    append(option) { this.options.push(option); },
  };
}
function buildContext(sessionReady) {
  const modelSelect = selectElement();
  const routingProfile = selectElement();
  return {
    state: {
      settings: null, sessionId: "active", routingResolution: null,
      sessions: sessionReady ? [{ session_id: "active", model: "session-model" }] : [],
    },
    el: {
      "model-select": modelSelect, "routing-profile": routingProfile,
      "model-catalog": { replaceChildren() {}, append() {} },
      "model-summary": {}, "stirling-url": {}, "stirling-status": {},
      "ollama-status": {},
    },
    node(_tag, _className, text) { return { textContent: text, value: "", selected: false }; },
    renderRoutingResolution() {},
    async api() {
      return { model: "global-model", models: ["global-model", "session-model"],
        routing: { profiles: [], models: [] }, stirling_url: "" };
    },
  };
}
async function run(sessionReady) {
  const context = buildContext(sessionReady);
  vm.runInNewContext(`${source.slice(resolverStart, settingsEnd)}\\n${source.slice(selectStart, selectEnd)}\\nglobalThis.load = loadSettings; globalThis.select = selectModel;`, context);
  await context.load();
  if (!sessionReady) {
    context.state.sessions = [{ session_id: "active", model: "session-model" }];
    context.select("session-model");
  }
  return context.el["model-select"].value;
}
assert.equal(await run(true), "session-model", "late settings preserve an open session model");
assert.equal(await run(false), "session-model", "later session selection restores its model");
""",
        encoding="utf-8",
    )
    subprocess.run(["node", str(runner)], check=True, cwd=ROOT)


def test_conversation_history_is_committed_in_one_dom_batch():
    script = (UI / "startup.js").read_text(encoding="utf-8")
    start = script.index("function renderConversation()")
    end = script.index("\n\nfunction scheduleLiveAssistantRender", start)
    body = script[start:end]

    assert "document.createDocumentFragment()" in body
    assert 'el["message-list"].replaceChildren(fragment)' in body


def test_editor_has_native_find_replace_keybindings():
    """Phase 53: every CodeMirror tab exposes Cmd/Ctrl-F and Cmd/Ctrl-H."""
    editor = (ROOT / "desktop" / "ui-src" / "editor.ts").read_text(encoding="utf-8")

    assert 'from "@codemirror/search"' in editor
    assert "search()," in editor
    assert "...searchKeymap," in editor
    assert 'key: "Mod-h", run: openSearchPanel' in editor


def test_editor_enables_native_multi_cursor_selection():
    """Phase 57: CodeMirror exposes Cmd/Ctrl-D and modifier-click selections."""
    editor = (ROOT / "desktop" / "ui-src" / "editor.ts").read_text(encoding="utf-8")

    assert "EditorState.allowMultipleSelections.of(true)" in editor
    assert "drawSelection()," in editor
    assert "...searchKeymap," in editor


def test_lsp_diagnostics_are_scoped_to_the_active_workspace():
    script = (UI / "startup.js").read_text(encoding="utf-8")

    assert 'msg.workspaceRoot !== state.workspace' in script


def test_lsp_symbol_pickers_use_scoped_native_requests_and_shortcuts():
    script = (UI / "startup.js").read_text(encoding="utf-8")

    assert 'invoke("lsp_document_symbols"' in script
    assert 'invoke("lsp_workspace_symbols"' in script
    assert 'openSymbolPalette("document-symbols")' in script
    assert 'openSymbolPalette("workspace-symbols")' in script
    assert "symbolGeneration" in script
    assert "symbolRequestGeneration" in script
    assert "codinalPath" in script
    assert "revealRange" in script
    assert 'invoke("lsp_document_open"' in script
    assert 'invoke("lsp_document_change"' in script
    assert 'invoke("lsp_document_save"' in script
    assert 'invoke("lsp_document_close"' in script
    assert 'invoke("lsp_stop"' in script
    assert "lspServers" in script


def test_settings_offer_local_stirling_configuration_and_health_check():
    html = (UI / "index.html").read_text(encoding="utf-8")
    script = (UI / "startup.js").read_text(encoding="utf-8")

    assert 'id="stirling-url"' in html
    assert 'id="save-stirling-url"' in html
    assert 'id="test-stirling-url"' in html
    assert 'api("/v1/settings/stirling"' in script
    assert 'api("/v1/settings/stirling/health"' in script


def test_settings_offer_loopback_ollama_model_discovery():
    html = (UI / "index.html").read_text(encoding="utf-8")
    script = (UI / "startup.js").read_text(encoding="utf-8")

    assert 'id="refresh-ollama-models"' in html
    assert 'id="ollama-status"' in html
    assert "function refreshOllamaModels()" in script
    assert 'api("/v1/settings/ollama/refresh"' in script


def test_editor_exposes_exact_lsp_range_navigation():
    editor = (ROOT / "desktop" / "ui-src" / "editor.ts").read_text(encoding="utf-8")

    assert "revealRange(path" in editor
    assert "EditorSelection.range(from, to)" in editor
    assert "EditorView.scrollIntoView" in editor


def test_command_palette_has_separate_quick_open_and_safe_commands():
    html = (UI / "index.html").read_text(encoding="utf-8")
    script = (UI / "startup.js").read_text(encoding="utf-8")

    assert 'id="command-palette"' in html
    assert 'role="listbox"' in html
    assert "/workspace/files?limit=1000" in script
    assert 'openPalette("files")' in script
    assert 'openPalette("commands")' in script
    assert 'event.key === "ArrowDown"' in script
    assert 'event.key === "Enter"' in script
    assert "closePalette" in script


def test_artifact_preview_uses_typed_local_renderers():
    html = (UI / "index.html").read_text(encoding="utf-8")
    script = (UI / "startup.js").read_text(encoding="utf-8")

    assert '<div id="artifact-preview"' in html
    assert 'result.kind === "image"' in script
    assert 'result.kind === "pdf"' in script
    assert 'viewer.sandbox = ""' in script
    assert "artifact-preview-image" in script
    assert "artifact-preview-pdf" in script
    assert "Local Office preview requires a configured Stirling endpoint." in script
    assert "Set a local Stirling endpoint to preview this file." in script
    assert "The original file was not changed." in script
    assert "generation === state.artifactPreviewGeneration" in script
    assert "artifactPreviewGeneration" in script
    assert "state.sessionId !== sessionId" in script


def test_composer_mentions_create_bounded_project_context_not_attachments():
    html = (UI / "index.html").read_text(encoding="utf-8")
    script = (UI / "startup.js").read_text(encoding="utf-8")

    assert 'id="mention-picker"' in html
    assert 'aria-controls="mention-picker"' in html
    assert 'aria-expanded="false"' in html
    assert "updateMentionPicker" in script
    assert "selectMention" in script
    assert "await addProjectContext(mention.root, item.path, item.kind)" in script
    assert "mentionGeneration" in script
    assert "Project context could not be captured" in script
    assert 'beforeCaret.lastIndexOf("@")' in script
    assert 'aria-activedescendant' in script
    mention_handler = script[
        script.index("async function selectMention"):
        script.index("async function selectMention") + 800
    ]
    assert "state.attachments" not in mention_handler


def test_desktop_client_wires_runtime_approval_diff_and_shortcuts():
    html = (UI / "index.html").read_text(encoding="utf-8")
    script = (UI / "startup.js").read_text(encoding="utf-8")
    css = (UI / "app.css").read_text(encoding="utf-8")

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
    assert "/project/index" in script
    assert "renderProjectSearchResults" in script
    assert (
        'el["project-tree"].classList.toggle("is-hidden", Boolean(query))'
        in script
    )
    assert '"is-active",' in script
    assert ".project-search-results.is-active" in css
    assert '"is-project-searching",' in script
    assert ".session-list.is-project-searching" in css
    assert "renderProjectIndexStatus" in script
    assert "projectIndexGeneration" in script
    assert "projectIndexBusySession" in script
    assert "rootSnapshot" in script
    assert "Semantic index not built" in html
    assert 'option value="semantic"' in html
    assert 'id="routing-profile"' in html
    assert 'id="routing-resolution"' in html
    assert 'id="model-catalog"' in html
    assert "/v1/settings/routing" in script
    assert "/v1/sessions/" in script
    assert "pty_open" in script
    assert "pty_input" in script
    assert "pty_resize" in script
    assert "pty_kill" in script
    assert "pty-data" in script
    assert "pty-exit" in script
    assert "lsp-notification" in script
    assert "setDiagnostics" in script
    assert "/mcp/servers" in script
    assert "/artifacts" in script
    assert 'id="git-graph"' in html
    assert 'id="git-branch"' in html
    assert 'id="git-push"' in html
    assert 'id="commit-message"' in html
    assert 'id="git-stage"' in html
    assert 'id="git-commit"' in html
    assert 'id="git-log"' in html
    assert "/git/log" in script
    assert "/git/graph" in script
    assert "/git/stage" in script
    assert "/git/commit" in script
    assert "/git/push" in script
    assert "loadGitGraph" in script
    assert "loadGitLog" in script
    assert "loadGitStatus" in script
    assert "renderGitLog" in script
    assert "stageAll" in script
    assert "commitChanges" in script
    assert "pushBranch" in script
    assert "loadCommitDiff" in script
    assert "diff-file-select" in script
    assert "diff-file-block" in css
    assert "selectedFiles" in script
    assert "Apply selected" in script
    assert "updateApplyButton" in script
    assert 'id="github-create-pr"' in html
    assert 'id="github-pr-status"' in html
    assert "/github/pr" in script
    assert "/github/checks" in script
    assert "createPullRequest" in script
    assert "loadPullRequest" in script
    assert 'id="preview-panel"' in html
    assert 'id="preview-frame"' in html
    assert 'id="annotation-overlay"' in html
    assert "/preview/evidence" in script
    assert "openPreview" in script
    assert "attachConsoleEvidence" in script
    assert "renderDevserverChips" in script
    assert "toggleAnnotation" in script
    assert "loadArtifacts" in script
    assert "renderArtifacts" in script
    assert "readArtifact" in script
    assert "revealArtifact" in script
    assert "renderMcpServers" in script
    assert "connectMcpServer" in script
    assert "disconnectMcpServer" in script
    assert "toggleMcpEnabled" in script
    assert "mcp-server-toggle" in script
    assert 'JSON.stringify({ enabled })' in script
    assert '"PATCH"' in script
    assert "routing_profile" in script
    assert "started.routing.selected_model" in script
    assert "message.source?.routing" in script
    assert "optimisticMessage.source = { routing: started.routing }" in script
    assert "state.routingPending" in script
    assert "exact provider, model, cost, and fallback appear here" in script
    assert "credential missing" in script
    assert "auto eligible" in script
    assert ".routing-resolution.has-degradation" in css
    assert ".message-routing" in css
    assert ".message-routing.has-degradation" in css
    assert "58px repeat(3, auto) 0fr minmax(0, 1fr) auto auto" in css
    assert ".terminal-panel { grid-row: 7; }" in css
    assert "#terminal-stop," in css
    assert "grid-template-columns: minmax(0, 1fr) 130px auto auto auto;" in css
    assert ".composer-wrap { grid-row: 8; }" in css
    workspace_css = css.split(".workspace {", 1)[1].split("}", 1)[0]
    assert "min-height: 0" in workspace_css
    assert "overflow: hidden" in workspace_css
    assert "Delete the local semantic index" in script
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
    # innerHTML is allowed ONLY for sanitized markdown (marked.parse on assistant
    # messages). Raw user input must never reach innerHTML.
    assert "marked.parse" in script  # markdown rendering exists
    assert "innerHTML = content" not in script  # no raw-content injection or "marked.parse" in script  # markdown rendering is sanitized


def test_desktop_csp_does_not_allow_inline_script_or_styles():
    config = TAURI_CONFIG.read_text(encoding="utf-8")

    assert '"withGlobalTauri": true' in config
    assert "'unsafe-inline'" not in config
