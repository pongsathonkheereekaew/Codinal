"use strict";

const HTTP = window.__CODINAL_HTTP__;
const WS = window.__CODINAL_WS__;
const TOKEN = window.__CODINAL_TOKEN__;
const invoke = window.__TAURI__?.core?.invoke;
// Tauri event listener shim: returns an unlisten function, or null if the
// Tauri event API isn't available (web/preview context).
const __codinalListen = window.__TAURI__?.event?.listen
  ? async (name, handler) => {
      const unlisten = await window.__TAURI__.event.listen(name, handler);
      return () => { try { unlisten(); } catch { /* noop */ } };
    }
  : null;
window.__codinalListen = __codinalListen;
const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;
const MAX_ATTACHMENTS = 5;
const ATTACHMENT_TYPES = new Set([
  "image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf",
]);
const BRANCH_SETTINGS = Object.freeze({
  fork: Object.freeze({
    endpoint: "fork",
    busy: "Stop the active turn before forking",
    created: "Forked task created",
    missing: "Forked task could not be loaded",
    opened: "Forked task from selected message",
  }),
  side: Object.freeze({
    endpoint: "side-conversations",
    busy: "Stop the active turn before opening a side conversation",
    created: "Side conversation created",
    missing: "Side conversation could not be loaded",
    opened: "Opened side conversation",
  }),
});

const state = {
  online: false,
  busy: false,
  sessions: [],
  sessionId: null,
  parentSessionId: null,
  workspace: null,
  messages: [],
  messageRenderCache: new Map(),
  socket: null,
  liveAssistant: null,
  liveAssistantFrame: null,
  activities: new Map(),
  settings: null,
  diff: "",
  selectedFiles: new Set(),
  selectedHunks: new Set(),
  previewUrl: "",
  devserverUrls: [],
  annotating: false,
  annotationStart: null,
  checkpoints: [],
  managedSession: null,
  updateVersion: null,
  attachments: [],
  attachmentsPending: 0,
  attachmentGeneration: 0,
  attachmentQueue: Promise.resolve(),
  attachmentReader: null,
  sessionSearchGeneration: 0,
  sessionSearchTimer: null,
  highlightedMessageIndex: null,
  threadSearchMatches: [],
  threadSearchCursor: -1,
  sessionSelectionGeneration: 0,
  roots: [],
  treeGeneration: 0,
  projectSearchGeneration: 0,
  projectSearchTimer: null,
  projectSearchController: null,
  projectSearchResults: null,
  projectIndexStatus: null,
  projectIndexGeneration: 0,
  projectIndexBusySession: null,
  rootMutationPending: false,
  contextItems: [],
  contextGeneration: 0,
  contextPending: false,
  workers: [],
  workerGeneration: 0,
  utilityView: "environment",
  plans: [],
  planBuilds: [],
  planBuildGeneration: 0,
  managedPlan: null,
  candidateDiffs: new Map(),
  goals: [],
  goalGeneration: 0,
  managedGoal: null,
  routingResolution: null,
  routingPending: false,
  terminalRunning: false,
  terminal: null, // { term, fitAddon, sessionId, resizeObserver, unlisten* }
  terminalLoad: null,
  terminalOpening: null,
  terminalViewGeneration: 0,
  mcpServers: [],
  mcpLoadGeneration: 0,
  artifacts: [],
  artifactLoadGeneration: 0,
  artifactPreviewGeneration: 0,
  editorReady: false,
  editorLoad: null,
  lspDocuments: new Map(),
  lspClosing: new Map(),
  lspServers: new Map(),
  palette: {
    mode: null, items: [], selected: 0, returnFocus: null, filesForSession: null,
    symbolGeneration: 0, symbolRequestGeneration: 0, symbolTimer: null,
  },
  mention: null,
  mentionGeneration: 0,
};

const el = Object.fromEntries(
  [
    "startup", "startup-status", "app", "sidebar", "new-task",
    "session-search", "refresh-sessions", "session-list", "theme-toggle",
    "open-settings", "toggle-sidebar", "task-header", "task-title", "workspace-path",
    "stirling-url", "save-stirling-url", "test-stirling-url", "stirling-status",
    "runtime-status", "review-button", "subagents-button", "change-count", "conversation",
    "empty-state", "message-list", "prompt", "attach-files",
    "attachment-input", "attachment-list", "choose-workspace",
    "workspace-label", "agent-mode", "routing-profile", "model-select",
    "routing-resolution", "stop-turn",
    "send-turn", "review-panel", "close-review", "review-summary",
    "utility-eyebrow", "utility-title", "utility-environment-tab",
    "utility-subagents-tab", "utility-environment", "utility-subagents",
    "conversation-context", "conversation-summary",
    "environment-open-review", "environment-details",
    "terminal-panel", "terminal-status",
    "terminal-restart", "terminal-clear", "terminal-host",
    "preview-panel", "preview-url", "preview-open", "preview-annotate",
    "preview-attach-console", "preview-frame", "annotation-overlay",
    "devserver-chips", "preview-evidence",
    "refresh-diff", "diff-view", "apply-changes", "settings-dialog",
    "settings-dialog-title",
    "settings-toggle-theme", "settings-back", "close-settings",
    "settings-search",
    "checkpoint-select", "restore-scope", "restore-checkpoint",
    "git-branch", "git-graph", "git-push",
    "github-create-pr", "github-pr-status",
    "commit-message", "git-stage", "git-commit", "git-log",
    "model-summary", "model-catalog", "update-status", "check-update",
    "install-update", "refresh-ollama-models", "ollama-status",
    "diagnostics-status", "audit-chain-status", "audit-log",
    "copy-support-bundle",
    "provider-list", "toast-region",
    "mcp-server-list", "mcp-server-name", "mcp-transport", "mcp-url",
    "mcp-command", "mcp-args", "mcp-cwd", "mcp-include-tools",
    "mcp-exclude-tools", "connect-mcp-server",
    "artifact-list", "artifact-empty", "artifact-preview",
    "artifact-preview-path",
    "session-dialog", "session-title-input", "rename-session",
    "pin-session", "archive-session", "delete-session",
    "context-panel", "context-roots", "project-tree", "add-context-root",
    "project-search", "project-search-mode", "project-search-status",
    "project-search-results",
    "project-index-status", "project-index-build", "project-index-clear",
    "thread-search", "thread-search-previous", "thread-search-next",
    "export-thread", "return-to-parent",
    "context-items",
    "worker-panel", "worker-summary", "worker-list", "new-worker",
    "worker-dialog", "worker-task", "worker-ownership", "create-worker",
    "worker-dependencies",
    "plan-panel", "plan-summary", "plan-list",
    "plan-build-panel", "plan-build-summary", "plan-build-list",
    "plan-build-dialog", "plan-build-tasks", "plan-build-models",
    "create-plan-build",
    "goal-panel", "goal-summary", "goal-list", "new-goal",
    "editor-panel", "editor-strip", "editor-pane",
    "goal-dialog", "goal-objective", "goal-requirements",
    "command-palette", "command-palette-close", "command-palette-input",
    "command-palette-status", "command-palette-results",
    "mention-picker",
    "goal-continuation", "goal-token-budget", "goal-time-budget",
    "create-goal", "goal-evidence-dialog", "goal-evidence-requirement",
    "goal-evidence-kind", "goal-evidence-summary",
    "goal-evidence-result", "save-goal-evidence",
  ].map((id) => [id, document.getElementById(id)])
);

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

function shortPath(path) {
  if (!path) return "No project selected";
  const parts = path.split("/").filter(Boolean);
  return parts.length > 3 ? `…/${parts.slice(-3).join("/")}` : path;
}

function basename(path) {
  return path?.split("/").filter(Boolean).at(-1) || "Add project";
}

function formatAge(value) {
  if (!value) return "";
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "";
  const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
  if (seconds < 60) return "now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${TOKEN}`);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${HTTP}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Runtime returned HTTP ${response.status}`);
  }
  return payload;
}

function toast(message, kind = "") {
  const item = node("div", `toast ${kind}`.trim(), message);
  let timer = window.setTimeout(() => item.remove(), 6000);
  // Hover-to-pause: SR users and pointer users get more time to read.
  item.addEventListener("mouseenter", () => window.clearTimeout(timer));
  item.addEventListener("mouseleave", () => {
    timer = window.setTimeout(() => item.remove(), 3000);
  });
  el["toast-region"].append(item);
}

function setRuntimeStatus(label, kind = "online") {
  const indicator = el["runtime-status"];
  indicator.classList.toggle("is-online", kind === "online");
  indicator.classList.toggle("is-busy", kind === "busy");
  indicator.classList.toggle("is-offline", kind === "offline");
  indicator.querySelector("span").textContent = label;
  // Live region announcement for SR users.
  indicator.setAttribute(
    "aria-label",
    `Runtime status: ${label.toLowerCase()}`
  );
}

async function connect(attemptsRemaining = 30) {
  try {
    await api("/v1/health");
    state.online = true;
    setRuntimeStatus("Local runtime", "online");
  } catch (error) {
    if (attemptsRemaining <= 1) throw error;
    await new Promise((resolve) => window.setTimeout(resolve, 200));
    return connect(attemptsRemaining - 1);
  }
}

function resolveActiveModel(defaultModel, sessionModel) {
  return sessionModel || defaultModel || null;
}

async function loadSettings() {
  state.settings = await api("/v1/settings");
  const routing = state.settings.routing || {};
  const catalog = new Map(
    (routing.models || []).map((model) => [model.id, model])
  );
  const models = Array.isArray(state.settings.models)
    ? state.settings.models
    : [state.settings.model].filter(Boolean);
  const activeSession = state.sessions.find(
    (session) => session.session_id === state.sessionId
  );
  const selectedModel = resolveActiveModel(
    state.settings.model,
    activeSession?.model
  );
  el["model-select"].replaceChildren();
  for (const model of models) {
    const metadata = catalog.get(model);
    const label = metadata
      ? `${model} · ${metadata.provider} · ${metadata.cost_class}`
      : model;
    const option = node("option", "", label);
    option.value = model;
    option.selected = model === selectedModel;
    el["model-select"].append(option);
  }
  if (!models.length) {
    const option = node("option", "", "Default model");
    el["model-select"].append(option);
  }
  if (selectedModel) selectModel(selectedModel);
  el["routing-profile"].replaceChildren();
  for (const profile of routing.profiles || []) {
    const option = node("option", "", profile.label || profile.id);
    option.value = profile.id;
    option.title = profile.description || "";
    option.selected = profile.id === routing.profile;
    el["routing-profile"].append(option);
  }
  if (!el["routing-profile"].options.length) {
    const option = node("option", "", "Manual");
    option.value = "manual";
    el["routing-profile"].append(option);
  }
  state.routingResolution = null;
  renderRoutingResolution();
  el["model-catalog"].replaceChildren();
  for (const metadata of routing.models || []) {
    const capabilities = Object.entries(metadata.capabilities || {})
      .filter(([, enabled]) => enabled)
      .map(([name]) => name.replaceAll("_", " "))
      .join(", ");
    const row = node("div", "model-catalog-row");
    row.append(
      node("strong", "", metadata.id),
      node(
        "small",
        "",
        `${metadata.provider} · ${metadata.cost_class} · `
        + `${metadata.configured ? "configured" : "credential missing"} · `
        + `${metadata.auto_eligible ? "auto eligible" : "manual only"} · `
        + (capabilities || "capabilities unknown")
      )
    );
    el["model-catalog"].append(row);
  }
  el["model-summary"].textContent = state.settings.model
    ? (
      `Current model: ${state.settings.model}. `
      + `Routing: ${routing.profile || "manual"}.`
    )
    : "The runtime will use its configured default model.";
  el["stirling-url"].value = state.settings.stirling_url || "";
  el["stirling-status"].textContent = state.settings.stirling_url
    ? "Endpoint saved. Test the connection before previewing Office files."
    : "Not configured.";
}

async function saveStirlingUrl() {
  const button = el["save-stirling-url"];
  button.disabled = true;
  try {
    const result = await api("/v1/settings/stirling", {
      method: "PATCH",
      body: JSON.stringify({ url: el["stirling-url"].value }),
    });
    state.settings = { ...(state.settings || {}), stirling_url: result.stirling_url };
    el["stirling-url"].value = result.stirling_url || "";
    el["stirling-status"].textContent = result.stirling_url
      ? "Endpoint saved. Test the connection before previewing Office files."
      : "Office previews through Stirling are disabled.";
  } catch (error) {
    el["stirling-status"].textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function testStirlingUrl() {
  const button = el["test-stirling-url"];
  button.disabled = true;
  el["stirling-status"].textContent = "Testing local Stirling endpoint…";
  try {
    const result = await api("/v1/settings/stirling/health", { method: "POST" });
    el["stirling-status"].textContent = result.version
      ? `Connected to Stirling PDF ${result.version}.`
      : "Connected to Stirling PDF.";
  } catch (error) {
    el["stirling-status"].textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function refreshOllamaModels() {
  const button = el["refresh-ollama-models"];
  button.disabled = true;
  el["ollama-status"].textContent = "Checking local Ollama…";
  try {
    const result = await api("/v1/settings/ollama/refresh", { method: "POST" });
    await loadSettings();
    el["ollama-status"].textContent = result.available
      ? result.models.length
        ? `${result.models.length} local model${result.models.length === 1 ? "" : "s"} ready in the picker.`
        : "Ollama is running, but it has no downloaded models."
      : "Ollama is not running at 127.0.0.1:11434.";
  } catch (error) {
    el["ollama-status"].textContent = "Could not refresh local models.";
    toast(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function loadDiagnostics() {
  try {
    const status = await api("/v1/status");
    const components = status.components || {};
    const providers = (components.providers || [])
      .filter((p) => p.configured)
      .map((p) => p.provider);
    const providerText = providers.length
      ? providers.join(", ")
      : "none configured";
    el["diagnostics-status"].textContent = (
      `Codinal ${status.version} · uptime `
      + `${Math.round(status.uptime_seconds || 0)}s · providers: ${providerText}`
    );
    const chain = components.audit_chain || "unavailable";
    el["audit-chain-status"].textContent = `Audit chain: ${chain}.`;
    el["audit-chain-status"].classList.toggle(
      "is-tampered",
      chain === "tampered"
    );
  } catch (error) {
    el["diagnostics-status"].textContent = "Diagnostics unavailable.";
  }
}

async function loadAuditLog() {
  try {
    const result = await api("/v1/audit?limit=50");
    renderAuditLog(result.events || []);
  } catch (error) {
    el["audit-log"].replaceChildren();
  }
}

function renderAuditLog(events) {
  el["audit-log"].replaceChildren();
  if (!events.length) {
    el["audit-log"].append(
      node("li", "audit-row audit-row-empty", "No audit events recorded.")
    );
    return;
  }
  for (const event of events) {
    const row = node("li", "audit-row");
    const when = event.at
      ? new Date(event.at * 1000).toLocaleTimeString()
      : "";
    row.append(
      node("span", "audit-domain", event.domain || ""),
      node("span", "audit-action", event.action || ""),
      node("span", "audit-subject", event.subject || ""),
      node("span", "audit-time", when)
    );
    el["audit-log"].append(row);
  }
}

async function copySupportBundle() {
  try {
    const [status, audit] = await Promise.all([
      api("/v1/status"),
      api("/v1/audit?limit=200"),
    ]);
    const bundle = {
      bundle_version: 1,
      generated_at: Date.now() / 1000,
      health: status,
      audit,
    };
    const text = JSON.stringify(bundle, null, 2);
    await navigator.clipboard.writeText(text);
    toast("Support bundle copied (secrets redacted)");
  } catch (error) {
    toast(error.message, "error");
  }
}

function renderRoutingResolution() {
  const resolution = state.routingResolution;
  const profile = el["routing-profile"].value || "manual";
  const model = el["model-select"].value;
  const degradations = resolution?.degradations || [];
  el["routing-resolution"].classList.toggle(
    "has-degradation",
    Boolean(degradations.length)
  );
  el["routing-resolution"].classList.toggle("is-hidden", !degradations.length);
  const chain = Array.isArray(resolution?.failover_chain) ? resolution.failover_chain : [];
  const chainText = chain.length > 1
    ? ` · fallback: ${chain.slice(1).join(" → ")}`
    : "";
  el["routing-resolution"].textContent = resolution
    ? (
      `${resolution.profile} → ${resolution.provider} · `
      + `${resolution.selected_model} · ${resolution.cost_class}`
      + `${degradations.length ? ` · ${degradations.join("; ")}` : ""}`
      + `${chainText}`
    )
    : profile === "manual"
      ? `Manual → ${model || "selected model"}`
      : `${profile} routing · exact provider, model, cost, and fallback appear here`;
}

function parseCommaList(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function validateName(name) {
  return /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(name);
}

function renderMcpServers() {
  el["mcp-server-list"].replaceChildren();
  if (!state.sessionId) {
    el["mcp-server-list"].append(
      node("p", "settings-copy", "Open a task to view MCP servers.")
    );
    return;
  }
  if (!state.mcpServers.length) {
    el["mcp-server-list"].append(
      node("p", "settings-copy", "No MCP servers connected for this task.")
    );
    return;
  }
  for (const server of state.mcpServers) {
    const row = node("div", "mcp-server-row");
    const tools = server.tools || [];
    const included = (server.include_tools || []).join(", ") || "all";
    const excluded = (server.exclude_tools || []).join(", ") || "none";
    const enabled = server.enabled !== false;
    const details = node("details", "mcp-server-details");
    const summary = node("summary", "", "Tools");
    const toolList = node("div", "mcp-tool-list");
    if (tools.length) {
      for (const tool of tools) {
        toolList.append(node("span", "mcp-tool", tool));
      }
    } else {
      toolList.append(node("span", "mcp-tool", "No tools discovered"));
    }
    details.append(summary, toolList);
    const status = node(
      "small",
      "mcp-server-meta",
      enabled ? "Enabled" : "Disabled"
    );
    const toggle = node(
      "label",
      "mcp-server-toggle",
      node("input", "", ""),
      node("span", "", "Enabled")
    );
    const checkbox = toggle.querySelector("input");
    checkbox.type = "checkbox";
    checkbox.checked = enabled;
    checkbox.setAttribute(
      "aria-label",
      `Enable MCP server ${server.name}`
    );
    checkbox.addEventListener("change", () => {
      toggleMcpEnabled(server.name, checkbox.checked).catch((error) => {
        toast(error.message, "error");
        checkbox.checked = !checkbox.checked;
      });
    });
    row.append(
      node("strong", "", server.name),
      node(
        "small",
        "mcp-server-meta",
        `${server.transport}${server.transport === "http"
          ? ` · ${server.url || ""}`
          : ` · ${server.command || ""}`}`
      ),
      node("small", "mcp-server-meta", `${tools.length} tools`),
      node("small", "mcp-server-meta", `Includes: ${included}`),
      node("small", "mcp-server-meta", `Excludes: ${excluded}`),
      status,
      details,
      node(
        "div",
        "mcp-server-actions",
        toggle,
        node(
          "button",
          "",
          "Disconnect"
        )
      )
    );
    const button = row.querySelector(".mcp-server-actions > button");
    button.type = "button";
    button.addEventListener("click", () => {
      disconnectMcpServer(server.name).catch((error) => {
        toast(error.message, "error");
      });
    });
    el["mcp-server-list"].append(row);
  }
}

function toggleMcpConnectorFields() {
  const transport = el["mcp-transport"].value;
  el["mcp-url"].parentElement.hidden = transport !== "http";
  el["mcp-command"].parentElement.hidden = transport !== "stdio";
  el["mcp-args"].parentElement.hidden = transport !== "stdio";
  el["mcp-cwd"].parentElement.hidden = transport !== "stdio";
}

function normalizeMcpPayload() {
  const name = el["mcp-server-name"].value.trim();
  const transport = el["mcp-transport"].value;
  const includeTools = parseCommaList(el["mcp-include-tools"].value);
  const excludeTools = parseCommaList(el["mcp-exclude-tools"].value);
  if (!name) {
    throw new Error("MCP server name is required");
  }
  if (!validateName(name)) {
    throw new Error("Server name must be 1-64 chars: letters, numbers, _, -");
  }
  if (transport !== "http" && transport !== "stdio") {
    throw new Error("Transport must be http or stdio");
  }
  const server = {
    name,
    transport,
    ...(includeTools.length ? { include_tools: includeTools } : {}),
    ...(excludeTools.length ? { exclude_tools: excludeTools } : {}),
  };
  if (transport === "http") {
    const url = el["mcp-url"].value.trim();
    if (!url) {
      throw new Error("HTTP MCP requires URL");
    }
    if (!/^https?:\/\/[^\s/$.?#].[^\s]*$/.test(url)) {
      throw new Error("Invalid MCP URL");
    }
    server.url = url;
    return server;
  }
  const command = el["mcp-command"].value.trim();
  if (!command) {
    throw new Error("stdio MCP requires command");
  }
  if (/\s/.test(command)) {
    throw new Error("std io command must not contain spaces");
  }
  const args = parseCommaList(el["mcp-args"].value);
  server.command = command;
  server.args = args;
  const cwd = el["mcp-cwd"].value.trim();
  if (cwd) server.cwd = cwd;
  return server;
}

async function loadMcpServers(sessionId = state.sessionId) {
  if (!sessionId) {
    state.mcpServers = [];
    renderMcpServers();
    return;
  }
  const generation = ++state.mcpLoadGeneration;
  try {
    const servers = await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/mcp/servers`
    );
    if (sessionId !== state.sessionId || generation !== state.mcpLoadGeneration) return;
    state.mcpServers = servers;
    renderMcpServers();
  } catch (error) {
    if (sessionId === state.sessionId && generation === state.mcpLoadGeneration) {
      state.mcpServers = [];
      renderMcpServers();
      throw error;
    }
  }
}

function formatArtifactSize(size) {
  const units = ["B", "KB", "MB", "GB"];
  let value = Number(size);
  let unit = 0;
  while (Number.isFinite(value) && value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  if (!Number.isFinite(value)) return "unknown size";
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function renderArtifacts() {
  state.artifactPreviewGeneration += 1;
  el["artifact-list"].replaceChildren();
  el["artifact-preview"].replaceChildren();
  el["artifact-preview-path"].textContent = "";
  if (!state.sessionId) {
    el["artifact-empty"].textContent = "Open settings with an active task to load artifacts.";
    return;
  }
  if (!state.artifacts.length) {
    el["artifact-empty"].textContent = "No artifacts discovered for this task.";
    return;
  }
  el["artifact-empty"].textContent = "";
  for (const artifact of state.artifacts) {
    const row = node("div", "artifact-row");
    const kind = artifact.kind || "file";
    const size = artifact.size;
    const modified = artifact.modified_at
      ? formatAge(artifact.modified_at * 1000)
      : "";
    const path = artifact.path || "";
    const previewButton = node("button", "", "Preview");
    const openButton = node("button", "", "Open");
    const revealButton = node("button", "", "Reveal");
    const actions = node("div", "artifact-actions");
    previewButton.type = "button";
    openButton.type = "button";
    revealButton.type = "button";
    previewButton.addEventListener("click", () => {
      readArtifact(path).catch((error) => {
        toast(error.message, "error");
      });
    });
    openButton.addEventListener("click", () => {
      revealArtifact(path, "open").catch((error) => {
        toast(error.message, "error");
      });
    });
    revealButton.addEventListener("click", () => {
      revealArtifact(path, "reveal").catch((error) => {
        toast(error.message, "error");
      });
    });
    actions.append(previewButton, openButton, revealButton);
    row.append(
      node("strong", "", artifact.name || path || "artifact"),
      node(
        "small",
        "artifact-meta",
        `${kind} · ${formatArtifactSize(size)}`
          + `${modified ? ` · ${modified}` : ""}`
      ),
      node("small", "artifact-meta", path),
      actions
    );
    el["artifact-list"].append(row);
  }
}

function clearArtifactPreview() {
  state.artifactPreviewGeneration += 1;
  el["artifact-preview"].replaceChildren();
  el["artifact-preview-path"].textContent = "";
}

async function loadArtifacts(sessionId = state.sessionId) {
  if (!sessionId) {
    state.artifacts = [];
    renderArtifacts();
    return;
  }
  const generation = ++state.artifactLoadGeneration;
  try {
    const artifacts = await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/artifacts`
    );
    if (sessionId !== state.sessionId || generation !== state.artifactLoadGeneration) {
      return;
    }
    state.artifacts = artifacts;
    renderArtifacts();
  } catch (error) {
    if (
      sessionId === state.sessionId
      && generation === state.artifactLoadGeneration
    ) {
      state.artifacts = [];
      renderArtifacts();
      throw error;
    }
  }
}

async function readArtifact(path) {
  if (!state.sessionId || state.busy) return;
  const sessionId = state.sessionId;
  const generation = ++state.artifactPreviewGeneration;
  el["artifact-preview"].textContent = "Loading preview…";
  const query = new URLSearchParams({ path }).toString();
  let result;
  try {
    result = await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/artifacts/read?${query}`
    );
  } catch (error) {
    if (
      state.sessionId === sessionId
      && generation === state.artifactPreviewGeneration
    ) {
      clearArtifactPreview();
      throw error;
    }
    return;
  }
  if (
    state.sessionId !== sessionId
    || generation !== state.artifactPreviewGeneration
  ) return;
  el["artifact-preview-path"].textContent = `${result.path} (${result.kind})`;
  const preview = el["artifact-preview"];
  preview.replaceChildren();
  if (result.kind === "image" && result.data_url?.startsWith("data:image/")) {
    const image = document.createElement("img");
    image.src = result.data_url;
    image.alt = result.path;
    image.className = "artifact-preview-image";
    preview.append(image);
    return;
  }
  if (result.kind === "pdf" && result.data_url?.startsWith("data:application/pdf")) {
    const viewer = document.createElement("iframe");
    viewer.src = result.data_url;
    viewer.sandbox = "";
    viewer.title = `Preview: ${result.path}`;
    viewer.className = "artifact-preview-pdf";
    preview.append(viewer);
    return;
  }
  if (result.kind === "sheet" || result.kind === "office") {
    const messages = {
      unconfigured: "Set a local Stirling endpoint to preview this file.",
      unsupported: "This Office file cannot be previewed.",
      failed: "Local Office conversion failed. The original file was not changed.",
    };
    preview.textContent = messages[result.preview_status]
      || "Local Office preview requires a configured Stirling endpoint.";
    return;
  }
  if (typeof result.content !== "string") {
    preview.textContent = "(artifact content unavailable)";
    return;
  }
  const text = document.createElement("pre");
  text.textContent = result.truncated
    ? `${result.content}\n[truncated for preview]`
    : result.content;
  preview.append(text);
}

async function revealArtifact(path, mode) {
  if (!state.sessionId || state.busy) return;
  await api(
    `/v1/sessions/${encodeURIComponent(state.sessionId)}/artifacts/reveal`,
    {
      method: "POST",
      body: JSON.stringify({ path, mode }),
    }
  );
  if (mode === "open") {
    el["artifact-preview"].textContent = `Opened ${path} in default app.`;
  } else {
    el["artifact-preview"].textContent = `Revealed ${path} in Finder.`;
  }
  el["artifact-preview-path"].textContent = path;
}

// --- Code editor (Phase 49: load CodeMirror only when a file is opened) ---

function loadEditorBundle() {
  if (window.CodinalEditor?.mount) return Promise.resolve();
  if (state.editorLoad) return state.editorLoad;
  state.editorLoad = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "./dist/editor.js";
    script.async = true;
    script.onload = () => {
      if (window.CodinalEditor?.mount) resolve();
      else reject(new Error("Editor module did not initialize"));
    };
    script.onerror = () => reject(new Error("Could not load editor module"));
    document.head.append(script);
  }).catch((error) => {
    state.editorLoad = null;
    throw error;
  });
  return state.editorLoad;
}

function lspLanguageForPath(path) {
  const extension = path.split(".").pop()?.toLowerCase();
  return {
    js: "javascript", jsx: "javascript", mjs: "javascript", cjs: "javascript",
    ts: "typescript", tsx: "typescript", py: "python", rs: "rust",
    json: "json", css: "css", scss: "css", html: "html", htm: "html",
  }[extension] || null;
}

function lspServerKey(language, workspaceRoot) {
  return `${workspaceRoot}\u0000${language}`;
}

async function lspOpenDocument(path, text) {
  const language = lspLanguageForPath(path);
  const workspaceRoot = state.workspace;
  if (!invoke || !language || !workspaceRoot) return;
  const document = {
    language, workspaceRoot, version: 1, timer: null, queue: Promise.resolve(),
    cancelled: false, closing: false, opened: false, latestText: text,
  };
  state.lspDocuments.set(path, document);
  enqueueLsp(document, async () => {
    const priorClose = state.lspClosing.get(path);
    if (priorClose) await priorClose;
    await invoke("lsp_start", { language, workspaceRoot });
    state.lspServers.set(lspServerKey(language, workspaceRoot), { language, workspaceRoot });
    if (document.cancelled || state.workspace !== workspaceRoot || state.lspDocuments.get(path) !== document) {
      if (!hasActiveLspDocument(document)) {
        state.lspServers.delete(lspServerKey(language, workspaceRoot));
        await invoke("lsp_stop", { language, workspaceRoot }).catch(() => {});
      }
      return;
    }
    await invoke("lsp_document_open", {
      language, workspaceRoot, path, text: document.latestText, version: document.version,
    });
    document.opened = true;
  });
}

function hasActiveLspDocument(document) {
  return [...state.lspDocuments.values()].some((candidate) => (
    candidate !== document
    && !candidate.cancelled
    && candidate.language === document.language
    && candidate.workspaceRoot === document.workspaceRoot
  ));
}

function enqueueLsp(document, action) {
  document.queue = document.queue.then(action).catch(() => {});
  return document.queue;
}

function queueLspChange(path, document, text) {
  const version = ++document.version;
  const snapshot = text;
  return enqueueLsp(document, async () => {
    if (document.cancelled || !document.opened || state.workspace !== document.workspaceRoot) return;
    await invoke("lsp_document_change", {
      language: document.language,
      workspaceRoot: document.workspaceRoot,
      path,
      text: snapshot,
      version,
    });
  });
}

function lspChangeDocument(path, text) {
  const document = state.lspDocuments.get(path);
  if (!document || !invoke || state.workspace !== document.workspaceRoot) return;
  document.latestText = text;
  clearTimeout(document.timer);
  document.timer = setTimeout(() => {
    document.timer = null;
    if (document.opened) queueLspChange(path, document, text);
  }, 250);
}

function lspSaveDocument(path) {
  const document = state.lspDocuments.get(path);
  if (!document || !invoke || state.workspace !== document.workspaceRoot) return;
  if (document.timer) {
    clearTimeout(document.timer);
    document.timer = null;
    if (document.opened) queueLspChange(path, document, document.latestText);
  }
  enqueueLsp(document, () => invoke("lsp_document_save", {
    language: document.language, workspaceRoot: document.workspaceRoot, path,
  }));
}

function lspCloseDocument(path) {
  const document = state.lspDocuments.get(path);
  if (!document) return;
  if (document.timer) {
    clearTimeout(document.timer);
    document.timer = null;
    if (document.opened) queueLspChange(path, document, document.latestText);
  }
  state.lspDocuments.delete(path);
  if (!document.opened) {
    document.cancelled = true;
    return;
  }
  document.closing = true;
  if (!invoke || state.workspace !== document.workspaceRoot) return;
  const closing = enqueueLsp(document, () => invoke("lsp_document_close", {
    language: document.language, workspaceRoot: document.workspaceRoot, path,
  }));
  state.lspClosing.set(path, closing);
  closing.finally(() => {
    document.cancelled = true;
    if (state.lspClosing.get(path) === closing) state.lspClosing.delete(path);
  });
}

function stopLspWorkspace(workspaceRoot) {
  const documents = [...state.lspDocuments.entries()]
    .filter(([, document]) => document.workspaceRoot === workspaceRoot);
  const languages = new Set();
  for (const [path, document] of documents) {
    clearTimeout(document.timer);
    document.cancelled = true;
    state.lspDocuments.delete(path);
    languages.add(document.language);
  }
  for (const [key, server] of state.lspServers) {
    if (server.workspaceRoot === workspaceRoot) {
      languages.add(server.language);
      state.lspServers.delete(key);
    }
  }
  if (invoke) {
    for (const language of languages) {
      invoke("lsp_stop", { language, workspaceRoot }).catch(() => {});
    }
  }
}

function initEditor() {
  if (state.editorReady || !window.CodinalEditor?.mount) return;
  window.CodinalEditor.mount(el["editor-strip"], el["editor-pane"]);
  window.CodinalEditor.onSave(async (path, content) => {
    if (!state.sessionId) return;
    try {
      await api(
        `/v1/sessions/${encodeURIComponent(state.sessionId)}/artifacts/write`,
        { method: "POST", body: JSON.stringify({ path, content }) }
      );
      lspSaveDocument(path);
      toast(`Saved ${path.split("/").pop()}`);
    } catch (error) {
      toast(`Save failed: ${error.message}`, "error");
      throw error;
    }
  });
  // When the last tab closes, hide the editor panel so it doesn't show
  // as an empty void (Phase 49 follow-up — matches Codex/VS Code behavior).
  window.CodinalEditor.onEmpty(() => {
    el["editor-panel"].classList.add("is-hidden");
  });
  window.CodinalEditor.onDocumentOpen((path, text) => {
    lspOpenDocument(path, text);
  });
  window.CodinalEditor.onDocumentChange((path, text) => {
    lspChangeDocument(path, text);
  });
  window.CodinalEditor.onDocumentClose((path) => {
    lspCloseDocument(path);
  });
  // Phase 50: listen for LSP diagnostic notifications → forward to editor.
  if (__codinalListen) {
    __codinalListen("lsp-notification", (event) => {
      const msg = event?.payload;
      if (!msg || msg?.message?.method !== "textDocument/publishDiagnostics")
        return;
      if (!state.workspace || msg.workspaceRoot !== state.workspace) return;
      const uri = msg.message.params?.uri || "";
      const path = uri.startsWith("file://") ? uri.slice(7) : uri;
      if (!path) return;
      const diags = (msg.message.params?.diagnostics || []).map((d) => ({
        from: d.range?.start?.line ?? 0,
        to: d.range?.end?.line ?? 0,
        severity: d.severity === 1 ? "error" : d.severity === 2 ? "warning" : "info",
        message: d.message || "",
      }));
      window.CodinalEditor?.setDiagnostics?.(path, diags);
    });
  }
  // Phase 50: goto-def opens the target file in a new editor tab.
  window.CodinalEditor.onGotoDef((path, line, _col) => {
    openEditorTab(path).then(() => {
      // Could scroll to line; CM6 scrollIntoView needs the view ref.
      // For Phase 50 we just open the file; line-jump is a follow-up.
    }).catch(() => {});
  });
  // Phase 51: inline completion — debounce + ghost text via the model API.
  window.CodinalEditor.onComplete(async (doc, pos) => {
    if (!state.sessionId || state.busy) return null;
    // Build a minimal completion prompt: prefix + suffix around the cursor.
    const prefix = doc.slice(0, pos);
    const suffix = doc.slice(pos);
    // Only trigger if the cursor is mid-line (not at very start of empty doc).
    if (!prefix.trim()) return null;
    try {
      const result = await api(
        `/v1/sessions/${encodeURIComponent(state.sessionId)}/complete`,
        {
          method: "POST",
          body: JSON.stringify({
            prefix: prefix.slice(-2000), // last 2K chars for context
            suffix: suffix.slice(0, 500), // next 500 chars for continuity
            language: "auto",
          }),
        }
      );
      return result.suggestion || null;
    } catch {
      return null; // silent — completion is best-effort
    }
  });
  // Phase 52: inline edit (Cmd-K) — select code → Cmd-K → type instruction → AI replaces.
  window.CodinalEditor.onInlineEdit(async (selectedText, instruction, from, to) => {
    if (!state.sessionId) return null;
    try {
      const result = await api(
        `/v1/sessions/${encodeURIComponent(state.sessionId)}/inline-edit`,
        {
          method: "POST",
          body: JSON.stringify({
            selected_text: selectedText,
            instruction,
            language: "auto",
          }),
        }
      );
      return result.replacement || null;
    } catch {
      return null;
    }
  });
  state.editorReady = true;
}

async function openEditorTab(path) {
  const sessionId = state.sessionId;
  if (!sessionId) {
    toast("Select a task first", "error");
    return;
  }
  try {
    await loadEditorBundle();
  } catch (error) {
    toast(`Editor unavailable: ${error.message}`, "error");
    return;
  }
  // A task can change while CodeMirror is loading. Never open a path from the
  // old task against the newly selected one.
  if (state.sessionId !== sessionId) return;
  initEditor();
  el["editor-panel"].classList.remove("is-hidden");
  // If tab already open, just focus it.
  if (window.CodinalEditor?.hasTab?.(path)) {
    window.CodinalEditor.setActive(path);
    return;
  }
  try {
    const result = await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/artifacts/read?path=${encodeURIComponent(path)}`
    );
    if (state.sessionId !== sessionId) return;
    if (result.kind === "text" || result.content !== undefined) {
      window.CodinalEditor.openTab(path, result.content || "");
    } else {
      toast(`${path} is not a text file`, "error");
    }
  } catch (error) {
    toast(`Could not open ${path}: ${error.message}`, "error");
  }
}

async function connectMcpServer() {
  const sessionId = state.sessionId;
  if (!sessionId) {
    toast("Select a task before connecting MCP");
    return;
  }
  let server;
  try {
    server = normalizeMcpPayload();
  } catch (error) {
    toast(error.message, "error");
    return;
  }
  try {
    el["connect-mcp-server"].disabled = true;
    await api(`/v1/sessions/${encodeURIComponent(sessionId)}/mcp/connect`, {
      method: "POST",
      body: JSON.stringify({ server }),
    });
    await loadMcpServers(sessionId);
    el["mcp-server-name"].value = "";
    el["mcp-url"].value = "";
    el["mcp-command"].value = "";
    el["mcp-args"].value = "";
    el["mcp-cwd"].value = "";
    el["mcp-include-tools"].value = "";
    el["mcp-exclude-tools"].value = "";
    toast(`Connected ${server.name}`);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    el["connect-mcp-server"].disabled = false;
  }
}

async function disconnectMcpServer(name) {
  const sessionId = state.sessionId;
  if (!sessionId) return;
  if (!window.confirm(`Disconnect MCP server ${name}?`)) return;
  await api(
    `/v1/sessions/${encodeURIComponent(sessionId)}/mcp/servers/`
      + encodeURIComponent(name),
    { method: "DELETE" }
  );
  await loadMcpServers(sessionId);
  toast(`Disconnected ${name}`);
}

async function toggleMcpEnabled(name, enabled) {
  const sessionId = state.sessionId;
  if (!sessionId) return;
  await api(
    `/v1/sessions/${encodeURIComponent(sessionId)}/mcp/servers/`
      + encodeURIComponent(name),
    {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }
  );
  await loadMcpServers(sessionId);
  toast(enabled ? `Enabled ${name}` : `Disabled ${name}`);
}

async function loadSessions() {
  const query = el["session-search"].value.trim();
  const generation = ++state.sessionSearchGeneration;
  const path = query
    ? `/v1/sessions/search?q=${encodeURIComponent(query)}&limit=50`
    : "/v1/sessions";
  const sessions = await api(path);
  if (generation !== state.sessionSearchGeneration) return;
  state.sessions = sessions;
  const active = state.sessions.find(
    (session) => session.session_id === state.sessionId
  );
  if (active) syncAgentMode(active);
  renderSessions();
  renderWorkers();
}

function syncAgentMode(session) {
  el["agent-mode"].value = session.mode === "plan"
    ? "plan"
    : session.mode === "discuss"
      ? "review"
      : session.agent === "review"
        ? "review"
        : "code";
}

function renderSessions() {
  const query = el["session-search"].value.trim().toLowerCase();
  const sessions = state.sessions.filter(
    (session) => query || !session.archived
  );
  el["session-list"].replaceChildren();
  if (!sessions.length) {
    el["session-list"].append(
      node("p", "session-empty", query ? "No matching tasks" : "No tasks yet")
    );
    return;
  }
  for (const session of sessions) {
    const item = node("div", "session-item");
    item.classList.toggle("is-active", session.session_id === state.sessionId);
    item.dataset.sessionId = session.session_id;
    const button = node("button", "session-main");
    button.type = "button";
    button.append(
      node("strong", "", session.title || "New task"),
      node("time", "", formatAge(session.updated_at)),
      node(
        "small",
        "",
        session.match_excerpt
          ? `${basename(session.workspace)} · ${session.match_excerpt}`
          : `${basename(session.workspace)}${session.archived ? " · Archived" : ""}`
      )
    );
    button.addEventListener("click", () => selectSession(session));
    const menu = node("button", "icon-button session-menu-button", "•••");
    menu.type = "button";
    menu.setAttribute("aria-label", `Options for ${session.title || "task"}`);
    menu.addEventListener("click", () => openSessionOptions(session));
    item.append(button, menu);
    el["session-list"].append(item);
  }
}

async function loadWorkers() {
  if (!state.sessionId) {
    state.workers = [];
    renderWorkers();
    return;
  }
  const sessionId = state.sessionId;
  const generation = ++state.workerGeneration;
  const workers = await api(
    `/v1/sessions/${encodeURIComponent(sessionId)}/workers`
  );
  if (
    state.sessionId !== sessionId
    || state.workerGeneration !== generation
  ) return;
  state.workers = workers;
  renderWorkers();
}

function updateWorker(worker) {
  if (!worker || worker.parent_session_id !== state.sessionId) return;
  const index = state.workers.findIndex(
    (candidate) => candidate.worker_id === worker.worker_id
  );
  if (index < 0) state.workers.push(worker);
  else state.workers[index] = worker;
  renderWorkers();
}

function renderWorkers() {
  const visible = state.sessions.some(
    (session) => session.session_id === state.sessionId
  );
  el["worker-panel"].classList.toggle("is-hidden", !visible);
  el["worker-list"].replaceChildren();
  const active = state.workers.filter(
    (worker) => !["succeeded", "adopted", "failed", "cancelled"]
      .includes(worker.state)
  ).length;
  const done = state.workers.filter((worker) => ["succeeded", "adopted"]
    .includes(worker.state)).length;
  el["subagents-button"].setAttribute(
    "data-active-count", active ? String(active) : ""
  );
  el["subagents-button"].setAttribute(
    "aria-label",
    active ? `Open subagents, ${active} active` : "Open subagents"
  );
  el["subagents-button"].title = active
    ? `Open subagents (${active} active)`
    : "Open subagents";
  el["worker-summary"].textContent = state.workers.length
    ? `${active} active · ${done} done`
    : "No active subagents";
  for (const worker of state.workers) {
    const card = node("article", "worker-card");
    const identity = node("div", "worker-identity");
    identity.append(
      node("strong", "", worker.task),
      node(
        "small",
        "",
        `${worker.state} · ${worker.worker_id} · ${
          (worker.ownership || []).join(", ")
        }${worker.dependencies?.length
          ? ` · after ${worker.dependencies.join(", ")}`
          : ""}`
      )
    );
    const actions = node("div", "worker-actions");
    if (worker.state === "running") {
      const steer = node("button", "secondary-button", "Steer");
      steer.type = "button";
      steer.addEventListener("click", () => {
        steerWorker(worker).catch((error) => toast(error.message, "error"));
      });
      const cancel = node("button", "secondary-button", "Cancel");
      cancel.type = "button";
      cancel.addEventListener("click", () => {
        cancelWorker(worker).catch((error) => toast(error.message, "error"));
      });
      actions.append(steer, cancel);
    }
    if (worker.state === "succeeded" && worker.commit && !worker.build_id) {
      const adopt = node("button", "primary-button", "Adopt");
      adopt.type = "button";
      adopt.addEventListener("click", () => {
        adoptWorker(worker).catch((error) => toast(error.message, "error"));
      });
      actions.append(adopt);
    }
    card.append(identity, actions);
    el["worker-list"].append(card);
  }
}

async function createWorker() {
  const task = el["worker-task"].value.trim();
  const ownership = el["worker-ownership"].value
    .split(",")
    .map((path) => path.trim())
    .filter(Boolean);
  const dependencies = el["worker-dependencies"].value
    .split(",")
    .map((workerId) => workerId.trim())
    .filter(Boolean);
  if (!state.sessionId || !task || !ownership.length) {
    toast("Enter a task and at least one owned path", "error");
    return;
  }
  const worker = await api(
    `/v1/sessions/${encodeURIComponent(state.sessionId)}/workers`,
    {
      method: "POST",
      body: JSON.stringify({
        task,
        ownership,
        dependencies,
        model: el["model-select"].value,
      }),
    }
  );
  updateWorker(worker);
  el["worker-dialog"].close();
  el["worker-task"].value = "";
  el["worker-ownership"].value = "";
  el["worker-dependencies"].value = "";
  toast("Background worker started");
}

async function steerWorker(worker) {
  const text = window.prompt("Steer this worker");
  if (!text?.trim()) return;
  await api(`/v1/workers/${encodeURIComponent(worker.worker_id)}/steer`, {
    method: "POST",
    body: JSON.stringify({ text: text.trim() }),
  });
  toast("Steering queued");
}

async function cancelWorker(worker) {
  await api(`/v1/workers/${encodeURIComponent(worker.worker_id)}/cancel`, {
    method: "POST",
  });
  await loadWorkers();
}

async function adoptWorker(worker) {
  await api(`/v1/workers/${encodeURIComponent(worker.worker_id)}/adopt`, {
    method: "POST",
  });
  await Promise.all([loadWorkers(), loadDiff(false)]);
  toast("Worker changes adopted");
}

async function loadPlanBuilds() {
  if (!state.sessionId) {
    state.planBuilds = [];
    renderPlanBuilds();
    return;
  }
  const sessionId = state.sessionId;
  const generation = ++state.planBuildGeneration;
  const builds = await api(
    `/v1/sessions/${encodeURIComponent(sessionId)}/plan-builds`
  );
  if (
    state.sessionId !== sessionId
    || state.planBuildGeneration !== generation
  ) return;
  state.planBuilds = Array.isArray(builds) ? builds : [];
  renderPlanBuilds();
}

function updatePlanBuild(build) {
  if (!build || build.parent_session_id !== state.sessionId) return;
  const index = state.planBuilds.findIndex(
    (candidate) => candidate.build_id === build.build_id
  );
  if (index < 0) state.planBuilds.push(build);
  else state.planBuilds[index] = build;
  renderPlanBuilds();
}

function renderPlanBuilds() {
  el["plan-build-list"].replaceChildren();
  el["plan-build-panel"].classList.toggle(
    "is-hidden",
    !state.planBuilds.length
  );
  const actionable = state.planBuilds.filter(
    (build) => build.state === "ready"
  ).length;
  el["plan-build-summary"].textContent = state.planBuilds.length
    ? `${actionable} awaiting selection · ${state.planBuilds.length} total`
    : "No parallel builds";
  for (const build of state.planBuilds) {
    const card = node("article", "plan-build-card");
    card.append(
      node("strong", "", `Build ${build.build_id.slice(-8)}`),
      node("span", "saved-plan-status", build.state.replace("_", " "))
    );
    if (build.error) card.append(node("p", "plan-build-error", build.error));
    for (const task of build.tasks || []) {
      const selected_worker_id = task.selected_worker_id || "";
      const taskCard = node("section", "plan-build-task");
      taskCard.append(
        node("strong", "", task.title),
        node("small", "", `Verify: ${task.verification}`)
      );
      for (const candidate of task.candidates || []) {
        const diffKey = `${build.build_id}:${candidate.worker_id}`;
        const row = node(
          "div",
          `plan-build-candidate ${
            candidate.worker_id === selected_worker_id ? "is-selected" : ""
          }`
        );
        const details = node("div", "plan-build-candidate-details");
        details.append(
          node("strong", "", candidate.model),
          node(
            "small",
            "",
            `${candidate.state}${candidate.summary
              ? ` · Candidate report: ${candidate.summary}`
              : ""}`
          )
        );
        row.append(details);
        if (candidate.commit) {
          const review = node("button", "secondary-button", "Review diff");
          review.type = "button";
          review.addEventListener("click", () => {
            reviewPlanBuildCandidate(build, candidate).catch(
              (error) => toast(error.message, "error")
            );
          });
          row.append(review);
        }
        if (
          ["ready", "selected"].includes(build.state)
          && candidate.selectable
        ) {
          const select = node(
            "button",
            candidate.selected ? "primary-button" : "secondary-button",
            candidate.selected ? "Selected" : "Select"
          );
          select.type = "button";
          select.disabled = candidate.selected;
          select.addEventListener("click", () => {
            selectPlanBuildCandidate(build, candidate).catch(
              (error) => toast(error.message, "error")
            );
          });
          row.append(select);
        }
        taskCard.append(row);
        const reviewed = state.candidateDiffs.get(diffKey);
        if (reviewed) {
          const evidence = node("div", "candidate-diff");
          evidence.append(
            node("strong", "", `Verification: ${reviewed.verification}`),
            node("small", "", `Candidate report: ${
              reviewed.summary || "No report"
            }`),
            node("pre", "", reviewed.diff || "No code changes")
          );
          if (reviewed.output_truncated) {
            evidence.append(node("small", "", "Diff output truncated"));
          }
          taskCard.append(evidence);
        }
      }
      card.append(taskCard);
    }
    if (build.state === "selected") {
      const adopt = node(
        "button",
        "primary-button",
        "Adopt selected results"
      );
      adopt.type = "button";
      adopt.addEventListener("click", () => {
        adoptPlanBuild(build).catch((error) => toast(error.message, "error"));
      });
      card.append(adopt);
    }
    el["plan-build-list"].append(card);
  }
}

function openPlanBuildDialog(plan) {
  state.managedPlan = plan;
  el["plan-build-tasks"].replaceChildren();
  const selected = new Set(plan.selected_task_ids || []);
  for (const task of plan.tasks || []) {
    if (!selected.has(task.id)) continue;
    const row = node("label", "plan-build-dialog-task");
    row.dataset.taskId = task.id;
    row.append(node("strong", "", task.title));
    const input = node("input");
    input.placeholder = "Owned paths, comma separated";
    input.setAttribute("aria-label", `Owned paths for ${task.title}`);
    row.append(input);
    el["plan-build-tasks"].append(row);
  }
  const models = [
    el["model-select"].value,
    ...Array.from(el["model-select"].options, (option) => option.value),
  ].filter((model, index, all) => model && all.indexOf(model) === index);
  if (models.length === 1) models.push(models[0]);
  el["plan-build-models"].value = models.slice(0, 3).join(", ");
  el["plan-build-dialog"].showModal();
  el["plan-build-tasks"].querySelector("input")?.focus();
}

async function createPlanBuild() {
  const plan = state.managedPlan;
  const models = el["plan-build-models"].value
    .split(",")
    .map((model) => model.trim())
    .filter(Boolean);
  const tasks = Array.from(
    el["plan-build-tasks"].querySelectorAll("[data-task-id]")
  ).map((row) => ({
    task_id: row.dataset.taskId,
    ownership: row.querySelector("input").value
      .split(",")
      .map((path) => path.trim())
      .filter(Boolean),
    candidates: models.map((model) => ({ model })),
  }));
  if (
    !state.sessionId
    || !plan
    || models.length < 2
    || models.length > 4
    || tasks.some((task) => !task.ownership.length)
  ) {
    toast("Enter owned paths and 2–4 candidate models", "error");
    return;
  }
  const build = await api(
    `/v1/sessions/${encodeURIComponent(state.sessionId)}/plan-builds`,
    {
      method: "POST",
      body: JSON.stringify({ plan_id: plan.plan_id, tasks }),
    }
  );
  updatePlanBuild(build);
  state.managedPlan = null;
  el["plan-build-dialog"].close();
  await loadWorkers();
  toast("Parallel comparison started");
}

async function selectPlanBuildCandidate(build, candidate) {
  const selected = await api(
    `/v1/plan-builds/${encodeURIComponent(build.build_id)}/select`,
    {
      method: "POST",
      body: JSON.stringify({ worker_id: candidate.worker_id }),
    }
  );
  updatePlanBuild(selected);
}

async function reviewPlanBuildCandidate(build, candidate) {
  const reviewed = await api(
    `/v1/plan-builds/${encodeURIComponent(
      build.build_id
    )}/candidates/${encodeURIComponent(candidate.worker_id)}/diff`
  );
  state.candidateDiffs.set(
    `${build.build_id}:${candidate.worker_id}`,
    reviewed
  );
  renderPlanBuilds();
}

async function adoptPlanBuild(build) {
  const adopted = await api(
    `/v1/plan-builds/${encodeURIComponent(build.build_id)}/adopt`,
    { method: "POST" }
  );
  updatePlanBuild(adopted);
  await Promise.all([loadWorkers(), loadDiff(false)]);
  toast("Selected plan results adopted");
}

async function loadGoals() {
  if (!state.sessionId) {
    state.goals = [];
    renderGoals();
    return;
  }
  const sessionId = state.sessionId;
  const generation = ++state.goalGeneration;
  const goals = await api(
    `/v1/sessions/${encodeURIComponent(sessionId)}/goals`
  );
  if (
    state.sessionId !== sessionId
    || state.goalGeneration !== generation
  ) return;
  state.goals = Array.isArray(goals) ? goals : [];
  renderGoals();
}

function updateGoal(goal) {
  if (!goal || goal.session_id !== state.sessionId) return;
  const index = state.goals.findIndex(
    (candidate) => candidate.goal_id === goal.goal_id
  );
  if (index < 0) state.goals.push(goal);
  else state.goals[index] = goal;
  renderGoals();
}

function renderGoals() {
  el["goal-list"].replaceChildren();
  el["goal-panel"].classList.toggle("is-hidden", !state.sessionId);
  const active = state.goals.filter(
    (goal) => goal.state === "active"
  ).length;
  el["goal-summary"].textContent = state.goals.length
    ? `${active} active · ${state.goals.length} total`
    : "No persistent goals";
  for (const goal of state.goals) {
    const card = node("article", "goal-card");
    const header = node("div", "goal-card-header");
    header.append(
      node("strong", "", goal.objective),
      node(
        "span",
        "saved-plan-status",
        goal.continuation_running ? "running" : goal.state
      )
    );
    const budget = [
      goal.token_budget
        ? `${goal.tokens_used}/${goal.token_budget} est. tokens`
        : `${goal.tokens_used} est. tokens`,
      goal.time_budget_seconds
        ? `${Math.ceil(goal.elapsed_seconds / 60)}/${
          Math.ceil(goal.time_budget_seconds / 60)
        } min`
        : `${Math.ceil(goal.elapsed_seconds / 60)} min`,
      `${goal.continuation_count} continuations`,
    ].join(" · ");
    card.append(header, node("small", "", budget));
    const requirements = node("div", "goal-requirements");
    for (const requirement of goal.requirements || []) {
      const passing = (goal.evidence || []).some(
        (item) => item.requirement_id === requirement.requirement_id
          && item.kind === "verification"
          && item.passed
      );
      requirements.append(
        node(
          "div",
          "goal-requirement",
          `${passing ? "✓" : "○"} ${requirement.text}`
        )
      );
    }
    card.append(requirements);
    const ledger = node("div", "goal-evidence-ledger");
    const visibleEvidence = ["completed", "blocked"].includes(goal.state)
      ? (goal.evidence || [])
      : (goal.evidence || []).slice(-5);
    for (const evidence of visibleEvidence) {
      ledger.append(
        node(
          "div",
          "goal-evidence-item",
          `#${evidence.turn_index} ${evidence.kind} · ${
            evidence.summary
          } · ${evidence.result || "recorded"}`
        )
      );
    }
    if (ledger.childNodes.length) card.append(ledger);
    if (
      goal.state === "completed"
      && Object.keys(goal.requirement_evidence || {}).length
    ) {
      const auditDetails = node("div", "goal-evidence-ledger");
      for (const requirement of goal.requirements || []) {
        const mapped = (
          goal.requirement_evidence?.[requirement.requirement_id] || []
        ).map((evidenceId) => (
          (goal.evidence || []).find(
            (item) => item.evidence_id === evidenceId
          )
        )).filter(Boolean);
        auditDetails.append(
          node(
            "div",
            "goal-evidence-item",
            `Audit evidence · ${requirement.text}: ${
              mapped.map((item) => `${item.summary} — ${item.result}`).join("; ")
            }`
          )
        );
      }
      card.append(auditDetails);
    }
    if (goal.audit_summary) {
      card.append(node("small", "", `Audit: ${goal.audit_summary}`));
    }
    if (!["completed", "blocked"].includes(goal.state)) {
      const actions = node("div", "goal-actions");
      const continuation = node(
        "button",
        "primary-button",
        goal.continuation_running ? "Continuing…" : "Continue goal"
      );
      continuation.type = "button";
      continuation.disabled = (
        goal.continuation_running || goal.state !== "active"
      );
      continuation.addEventListener("click", () => {
        continueGoal(goal).catch((error) => toast(error.message, "error"));
      });
      const evidence = node(
        "button",
        "secondary-button",
        "Add evidence"
      );
      evidence.type = "button";
      evidence.disabled = goal.continuation_running;
      evidence.addEventListener("click", () => openGoalEvidence(goal));
      const complete = node("button", "secondary-button", "Audit complete");
      complete.type = "button";
      complete.disabled = (
        goal.continuation_running || !goalCompletionMapping(goal)
      );
      complete.addEventListener("click", () => {
        auditGoalComplete(goal).catch((error) => toast(error.message, "error"));
      });
      const blocked = node("button", "secondary-button", "Audit blocked");
      blocked.type = "button";
      blocked.disabled = (
        goal.continuation_running || !goalBlockerSummary(goal)
      );
      blocked.addEventListener("click", () => {
        auditGoalBlocked(goal).catch((error) => toast(error.message, "error"));
      });
      actions.append(continuation, evidence, complete, blocked);
      card.append(actions);
    }
    el["goal-list"].append(card);
  }
}

function openGoalDialog() {
  el["goal-objective"].value = "";
  el["goal-requirements"].value = "";
  el["goal-continuation"].value = (
    "Continue this goal, verify remaining requirements, and report evidence."
  );
  el["goal-token-budget"].value = "";
  el["goal-time-budget"].value = "";
  el["goal-dialog"].showModal();
  el["goal-objective"].focus();
}

async function createGoal() {
  const objective = el["goal-objective"].value.trim();
  const continuation_prompt = el["goal-continuation"].value.trim();
  const requirements = el["goal-requirements"].value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const separator = line.indexOf(":");
      return {
        requirement_id: separator > 0
          ? line.slice(0, separator).trim()
          : "",
        text: separator > 0 ? line.slice(separator + 1).trim() : "",
      };
    });
  const tokenValue = el["goal-token-budget"].value.trim();
  const minuteValue = el["goal-time-budget"].value.trim();
  const token_budget = tokenValue ? Number(tokenValue) : null;
  const minutes = minuteValue ? Number(minuteValue) : null;
  if (
    !state.sessionId || !objective || !continuation_prompt
    || !requirements.length
    || requirements.some((item) => !item.requirement_id || !item.text)
    || token_budget !== null
      && (!Number.isInteger(token_budget) || token_budget < 1)
    || minutes !== null && (!Number.isInteger(minutes) || minutes < 1)
  ) {
    toast("Enter an objective and requirements as id: description", "error");
    return;
  }
  const goal = await api(
    `/v1/sessions/${encodeURIComponent(state.sessionId)}/goals`,
    {
      method: "POST",
      body: JSON.stringify({
        objective,
        requirements,
        continuation_prompt,
        token_budget,
        time_budget_seconds: minutes === null ? null : minutes * 60,
      }),
    }
  );
  updateGoal(goal);
  el["goal-dialog"].close();
  toast("Persistent goal created");
}

async function continueGoal(goal) {
  const updated = await api(
    `/v1/goals/${encodeURIComponent(goal.goal_id)}/continue`,
    { method: "POST" }
  );
  updateGoal(updated);
  toast("Goal continuation started");
}

function openGoalEvidence(goal) {
  state.managedGoal = goal;
  el["goal-evidence-requirement"].replaceChildren();
  for (const requirement of goal.requirements || []) {
    const option = node("option", "", requirement.text);
    option.value = requirement.requirement_id;
    el["goal-evidence-requirement"].append(option);
  }
  el["goal-evidence-kind"].value = "verification";
  el["goal-evidence-summary"].value = "";
  el["goal-evidence-result"].value = "";
  el["goal-evidence-dialog"].showModal();
  el["goal-evidence-summary"].focus();
}

async function saveGoalEvidence() {
  const goal = state.managedGoal;
  const kind = el["goal-evidence-kind"].value;
  const summary = el["goal-evidence-summary"].value.trim();
  const result = el["goal-evidence-result"].value.trim();
  if (!goal || !summary || !result) {
    toast("Enter an evidence summary and observed result", "error");
    return;
  }
  await api(
    `/v1/goals/${encodeURIComponent(goal.goal_id)}/evidence`,
    {
      method: "POST",
      body: JSON.stringify({
        requirement_id: el["goal-evidence-requirement"].value,
        kind,
        summary,
        result,
        passed: kind === "verification",
      }),
    }
  );
  state.managedGoal = null;
  el["goal-evidence-dialog"].close();
  await loadGoals();
  toast("Goal evidence saved");
}

function goalCompletionMapping(goal) {
  const mapping = {};
  for (const requirement of goal.requirements || []) {
    const evidence = (goal.evidence || [])
      .filter((item) => (
        item.requirement_id === requirement.requirement_id
        && item.kind === "verification"
        && item.passed
      ))
      .map((item) => item.evidence_id);
    if (!evidence.length) return null;
    mapping[requirement.requirement_id] = evidence;
  }
  return mapping;
}

function goalBlockerSummary(goal) {
  if ((goal.continuation_count || 0) < 3) return "";
  const recent = [goal.continuation_count - 2, goal.continuation_count - 1,
    goal.continuation_count];
  const summaries = recent.map((turn) => (
    (goal.evidence || []).find(
      (item) => item.kind === "blocker" && item.turn_index === turn
    )?.summary || ""
  ));
  return summaries.every(
    (summary) => summary
      && summary.toLocaleLowerCase() === summaries[0].toLocaleLowerCase()
  ) ? summaries[0] : "";
}

async function auditGoalComplete(goal) {
  const requirement_evidence = goalCompletionMapping(goal);
  if (!requirement_evidence) return;
  const updated = await api(
    `/v1/goals/${encodeURIComponent(goal.goal_id)}/audit`,
    {
      method: "POST",
      body: JSON.stringify({
        status: "complete",
        summary: "All goal requirements have passing evidence.",
        requirement_evidence,
      }),
    }
  );
  updateGoal(updated);
  toast("Goal completion audit passed");
}

async function auditGoalBlocked(goal) {
  const summary = goalBlockerSummary(goal);
  if (!summary) return;
  const updated = await api(
    `/v1/goals/${encodeURIComponent(goal.goal_id)}/audit`,
    {
      method: "POST",
      body: JSON.stringify({
        status: "blocked",
        summary,
        requirement_evidence: {},
      }),
    }
  );
  updateGoal(updated);
  toast("Goal blocked audit passed");
}

function scheduleSessionSearch() {
  window.clearTimeout(state.sessionSearchTimer);
  state.sessionSearchGeneration += 1;
  state.sessionSearchTimer = window.setTimeout(() => {
    loadSessions().catch((error) => toast(error.message, "error"));
  }, 180);
}

function openSessionOptions(session) {
  state.managedSession = session;
  el["session-title-input"].value = session.title || "";
  el["pin-session"].textContent = session.pinned ? "Unpin task" : "Pin task";
  el["archive-session"].textContent = session.archived
    ? "Unarchive task"
    : "Archive task";
  el["session-dialog"].showModal();
  el["session-title-input"].select();
}

async function patchManagedSession(update) {
  const session = state.managedSession;
  if (!session) return;
  const result = await api(
    `/v1/sessions/${encodeURIComponent(session.session_id)}`,
    { method: "PATCH", body: JSON.stringify(update) }
  );
  Object.assign(session, update, result);
  if (session.session_id === state.sessionId && update.title) {
    el["task-title"].textContent = result.title || update.title;
  }
  await loadSessions();
  el["session-dialog"].close();
}

async function selectSession(session) {
  state.highlightedMessageIndex = Number.isInteger(
    session.match_message_index
  )
    ? session.match_message_index
    : null;
  if (state.sessionId === session.session_id) {
    renderConversation();
    return;
  }
  const selectionGeneration = ++state.sessionSelectionGeneration;
  const sessionId = session.session_id;
  const previousWorkspace = state.workspace;
  if (previousWorkspace && previousWorkspace !== session.workspace) {
    stopLspWorkspace(previousWorkspace);
    window.CodinalEditor?.dispose?.();
    state.editorReady = false;
  }
  disconnectSocket();
  cancelProjectSearch(state.sessionId);
  el["thread-search"].value = "";
  state.threadSearchMatches = [];
  state.threadSearchCursor = -1;
  state.sessionId = sessionId;
  state.parentSessionId = session.origin_session_id || null;
  el["return-to-parent"].classList.toggle(
    "is-hidden",
    !state.parentSessionId
  );
  state.workspace = session.workspace;
  state.messages = [];
  state.messageRenderCache.clear();
  state.checkpoints = [];
  state.workers = [];
  state.workerGeneration += 1;
  state.plans = [];
  state.planBuilds = [];
  state.planBuildGeneration += 1;
  state.candidateDiffs.clear();
  state.mcpServers = [];
  state.mcpLoadGeneration += 1;
  state.artifacts = [];
  state.artifactLoadGeneration += 1;
  state.goals = [];
  state.goalGeneration += 1;
  state.roots = [];
  state.treeGeneration += 1;
  invalidateProjectSearch();
  invalidateAttachments();
  invalidateContextItems();
  state.liveAssistant = null;
  state.activities.clear();
  state.routingResolution = null;
  el["task-title"].textContent = session.title || "New task";
  closeTerminalView();
  clearArtifactPreview();
  syncAgentMode(session);
  selectModel(session.model);
  updateWorkspaceLabel();
  setTerminalBusy(false);
  renderSessions();
  renderConversation();
  renderCheckpoints();
  renderContextRoots();
  renderProjectTree();
  renderWorkers();
  renderPlans();
  renderPlanBuilds();
  renderGoals();
  updateThreadSearchControls();
  try {
    const messages = await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/messages`
    );
    if (
      state.sessionId !== sessionId
      || state.sessionSelectionGeneration !== selectionGeneration
    ) return;
    state.messages = messages;
    renderConversation();
    connectSocket();
    await Promise.all([
      loadPendingApprovals(),
      loadPendingInteractions(),
      loadDiff(false),
      loadRootsAndTree(),
      loadWorkers(),
      loadPlans(),
      loadPlanBuilds(),
      loadGoals(),
      loadMcpServers(sessionId),
      loadArtifacts(sessionId),
    ]);
    if (
      state.sessionId !== sessionId
      || state.sessionSelectionGeneration !== selectionGeneration
    ) return;
  } catch (error) {
    if (
      state.sessionId === sessionId
      && state.sessionSelectionGeneration === selectionGeneration
    ) toast(error.message, "error");
  }
}

function selectModel(model) {
  if (!model) return;
  let option = [...el["model-select"].options]
    .find((candidate) => candidate.value === model);
  if (!option) {
    option = node("option", "", model);
    option.value = model;
    el["model-select"].append(option);
  }
  el["model-select"].value = model;
  renderRoutingResolution();
}

async function newTask() {
  if (state.busy) {
    toast("Stop the active turn before changing workspace", "error");
    return;
  }
  const workspace = await pickWorkspace();
  if (!workspace) return;
  switchWorkspace(workspace);
  el.prompt.focus();
}

function paletteScore(query, label) {
  const needle = query.trim().toLocaleLowerCase();
  if (!needle) return 0;
  let cursor = 0;
  let score = 0;
  for (const character of needle) {
    const found = label.toLocaleLowerCase().indexOf(character, cursor);
    if (found < 0) return -1;
    score += found === cursor ? 4 : 1;
    cursor = found + 1;
  }
  return score;
}

function renderPalette() {
  const query = el["command-palette-input"].value;
  const filtered = state.palette.items
    .map((item) => ({ item, score: paletteScore(query, item.label) }))
    .filter(({ score }) => score >= 0)
    .sort((a, b) => b.score - a.score || a.item.label.localeCompare(b.item.label))
    .slice(0, 100)
    .map(({ item }) => item);
  state.palette.filtered = filtered;
  state.palette.selected = Math.min(state.palette.selected, Math.max(0, filtered.length - 1));
  el["command-palette-results"].replaceChildren();
  if (!filtered.length) {
    el["command-palette-status"].textContent = query ? "No matching results" : "No results available";
    return;
  }
  el["command-palette-status"].textContent = `${filtered.length} result${filtered.length === 1 ? "" : "s"}`;
  filtered.forEach((item, index) => {
    const option = node("button", `command-palette-option${index === state.palette.selected ? " is-selected" : ""}`, item.label);
    option.type = "button";
    option.role = "option";
    option.setAttribute("aria-selected", String(index === state.palette.selected));
    option.addEventListener("click", () => selectPaletteItem(index));
    el["command-palette-results"].append(option);
  });
}

function closePalette() {
  if (!el["command-palette"].open) return;
  el["command-palette"].close();
  state.palette.returnFocus?.focus?.();
  state.palette.returnFocus = null;
}

async function selectPaletteItem(index = state.palette.selected) {
  const item = state.palette.filtered?.[index];
  if (!item) return;
  closePalette();
  await item.run();
}

async function openPalette(mode) {
  state.palette.mode = mode;
  state.palette.selected = 0;
  state.palette.returnFocus = document.activeElement;
  el["command-palette-input"].value = "";
  el["command-palette-title"].textContent = mode === "files" ? "Quick Open" : "Command Palette";
  el["command-palette-input"].placeholder = mode === "files" ? "Search files" : "Search commands";
  if (mode === "files") {
    if (!state.sessionId) {
      state.palette.items = [];
      el["command-palette-status"].textContent = "Select a task first";
    } else {
      try {
        if (state.palette.filesForSession !== state.sessionId) {
          const result = await api(`/v1/sessions/${encodeURIComponent(state.sessionId)}/workspace/files?limit=1000`);
          state.palette.files = result.paths || [];
          state.palette.filesForSession = state.sessionId;
        }
        state.palette.items = state.palette.files.map((path) => ({ label: path, run: () => openEditorTab(path) }));
      } catch (error) {
        state.palette.items = [];
        el["command-palette-status"].textContent = error.message;
      }
    }
  } else {
    state.palette.items = [
      { label: "New task", run: newTask },
      { label: "Focus composer", run: () => el.prompt.focus() },
      { label: "Open settings", run: openSettings },
      { label: "Toggle sidebar", run: () => el.app.classList.toggle("sidebar-collapsed") },
      { label: "Open diff", run: () => loadDiff(true) },
      { label: "Open terminal", run: () => showTerminalView().catch((error) => toast(String(error), "error")) },
    ];
  }
  if (!el["command-palette"].open) el["command-palette"].showModal();
  renderPalette();
  el["command-palette-input"].focus();
}

function symbolRange(value) {
  return value?.selectionRange || value?.range || value?.location?.range || null;
}

function relativeSymbolPath(uri) {
  if (typeof uri !== "string" || !state.workspace) return null;
  try {
    const path = decodeURIComponent(new URL(uri).pathname);
    const root = state.workspace.endsWith("/") ? state.workspace : `${state.workspace}/`;
    return path.startsWith(root) ? path.slice(root.length) : null;
  } catch {
    return null;
  }
}

function symbolItem(symbol, path) {
  const range = symbolRange(symbol);
  if (!path || !range?.start) return null;
  const line = (range.start.line || 0) + 1;
  return {
    label: `${symbol.name || "Unnamed symbol"} · ${path}:${line}`,
    run: async () => {
      await openEditorTab(path);
      window.CodinalEditor?.revealRange?.(
        path,
        range.start.line || 0,
        range.start.character || 0,
        range.end?.line ?? (range.start.line || 0),
        range.end?.character ?? (range.start.character || 0),
      );
    },
  };
}

function documentSymbolItems(symbols, path) {
  const items = [];
  const visit = (symbol) => {
    const item = symbolItem(symbol, path);
    if (item) items.push(item);
    for (const child of symbol.children || []) visit(child);
  };
  for (const symbol of Array.isArray(symbols) ? symbols : []) visit(symbol);
  return items;
}

async function openSymbolPalette(scope) {
  const generation = (state.palette.symbolGeneration || 0) + 1;
  state.palette.symbolGeneration = generation;
  state.palette.mode = scope;
  state.palette.selected = 0;
  state.palette.returnFocus = document.activeElement;
  state.palette.items = [];
  el["command-palette-input"].value = "";
  el["command-palette-title"].textContent = scope === "document-symbols" ? "Document Symbols" : "Workspace Symbols";
  el["command-palette-input"].placeholder = "Search symbols";
  if (!el["command-palette"].open) el["command-palette"].showModal();
  el["command-palette-status"].textContent = "Loading symbols…";
  renderPalette();
  el["command-palette-input"].focus();
  if (!invoke || !state.workspace) {
    el["command-palette-status"].textContent = "Language services are unavailable";
    return;
  }
  if (scope === "document-symbols") {
    const path = window.CodinalEditor?.getActivePath?.();
    const document = path && state.lspDocuments.get(path);
    if (!path || !document) {
      el["command-palette-status"].textContent = "No language server for the active document";
      return;
    }
    try {
      const symbols = await invoke("lsp_document_symbols", {
        language: document.language, workspaceRoot: document.workspaceRoot, path,
      });
      if (generation !== state.palette.symbolGeneration) return;
      state.palette.items = documentSymbolItems(symbols, path);
    } catch {
      if (generation !== state.palette.symbolGeneration) return;
      state.palette.items = [];
      el["command-palette-status"].textContent = "Document symbols are unavailable";
    }
    renderPalette();
    return;
  }
  await loadWorkspaceSymbols("");
}

async function loadWorkspaceSymbols(query) {
  const generation = state.palette.symbolGeneration;
  const requestGeneration = (state.palette.symbolRequestGeneration || 0) + 1;
  state.palette.symbolRequestGeneration = requestGeneration;
  const servers = [...state.lspServers.values()];
  if (!servers.length) {
    el["command-palette-status"].textContent = "No workspace language servers are active";
    return;
  }
  const results = await Promise.all(servers.map(async (server) => {
    try {
      return await invoke("lsp_workspace_symbols", { ...server, query });
    } catch {
      return [];
    }
  }));
  if (
    generation !== state.palette.symbolGeneration
    || requestGeneration !== state.palette.symbolRequestGeneration
    || state.palette.mode !== "workspace-symbols"
  ) return;
  state.palette.items = results.flat().flatMap((symbol) => {
    if (!symbol || typeof symbol !== "object") return [];
    const path = symbol.codinalPath || relativeSymbolPath(symbol.location?.uri);
    return [symbolItem(symbol, path)].filter(Boolean);
  });
  state.palette.selected = 0;
  renderPalette();
}

function closeMentionPicker() {
  state.mentionGeneration += 1;
  state.mention = null;
  el["mention-picker"].replaceChildren();
  el["mention-picker"].classList.add("is-hidden");
  el.prompt.setAttribute("aria-expanded", "false");
  el.prompt.removeAttribute("aria-activedescendant");
}

async function updateMentionPicker() {
  const generation = ++state.mentionGeneration;
  const sessionId = state.sessionId;
  const beforeCaret = el.prompt.value.slice(0, el.prompt.selectionStart);
  const match = /(?:^|\s)@([^\s@]*)$/.exec(beforeCaret);
  if (!match || !sessionId || state.busy) return closeMentionPicker();
  try {
    if (state.palette.filesForSession !== sessionId) {
      const result = await api(`/v1/sessions/${encodeURIComponent(sessionId)}/workspace/files?limit=1000`);
      if (generation !== state.mentionGeneration || sessionId !== state.sessionId) return;
      state.palette.files = result.paths || [];
      state.palette.filesForSession = sessionId;
    }
    const query = match[1].toLocaleLowerCase();
    const files = state.palette.files.filter((path) => path.toLocaleLowerCase().includes(query));
    const folders = [...new Set(files.flatMap((path) => {
      const parts = path.split("/");
      return parts.slice(0, -1).map((_, index) => parts.slice(0, index + 1).join("/"));
    }))];
    const root = state.roots.find((candidate) => candidate.primary && candidate.available !== false) || state.roots.find((candidate) => candidate.available !== false);
    if (!root) return closeMentionPicker();
    const items = [
      ...files.slice(0, 20).map((path) => ({ path, kind: "file" })),
      ...folders.slice(0, 20).map((path) => ({ path, kind: "folder" })),
    ];
    if (!items.length) return closeMentionPicker();
    if (generation !== state.mentionGeneration || sessionId !== state.sessionId) return;
    state.mention = { start: beforeCaret.lastIndexOf("@"), end: beforeCaret.length, root, items, selected: 0, sessionId };
    renderMentionPicker();
  } catch {
    closeMentionPicker();
  }
}

function renderMentionPicker() {
  const mention = state.mention;
  if (!mention) return;
  el["mention-picker"].replaceChildren();
  mention.items.forEach((item, index) => {
    const option = node("button", `mention-option${index === mention.selected ? " is-selected" : ""}`, `${item.kind === "folder" ? "Folder" : "File"} · ${item.path}`);
    option.type = "button";
    option.role = "option";
    option.id = `mention-option-${index}`;
    option.setAttribute("aria-selected", String(index === mention.selected));
    option.addEventListener("mousedown", (event) => event.preventDefault());
    option.addEventListener("click", () => selectMention(index));
    el["mention-picker"].append(option);
  });
  el["mention-picker"].classList.remove("is-hidden");
  el.prompt.setAttribute("aria-expanded", "true");
  el.prompt.setAttribute("aria-activedescendant", `mention-option-${mention.selected}`);
}

async function selectMention(index = state.mention?.selected) {
  const mention = state.mention;
  const item = mention?.items[index];
  if (!mention || !item) return;
  const previous = el.prompt.value;
  const inserted = `${previous.slice(0, mention.start)}@${item.path}${previous.slice(mention.end)}`;
  el.prompt.value = inserted;
  const caret = mention.start + item.path.length + 1;
  el.prompt.setSelectionRange(caret, caret);
  closeMentionPicker();
  resizePrompt();
  try {
    await addProjectContext(mention.root, item.path, item.kind);
    if (!state.contextItems.some((context) => context.kind === item.kind && context.root === mention.root.path && context.path === item.path)) {
      throw new Error("Project context could not be captured");
    }
  } catch (error) {
    if (state.sessionId === mention.sessionId && el.prompt.value === inserted) {
      el.prompt.value = previous;
    }
    toast(error.message, "error");
  }
}

function switchWorkspace(workspace) {
  if (state.busy) {
    toast("Stop the active turn before changing workspace", "error");
    return false;
  }
  disconnectSocket();
  if (state.workspace && state.workspace !== workspace) {
    stopLspWorkspace(state.workspace);
    window.CodinalEditor?.dispose?.();
    state.editorReady = false;
  }
  cancelProjectSearch(state.sessionId);
  state.sessionId = `session-${crypto.randomUUID()}`;
  state.parentSessionId = null;
  el["return-to-parent"].classList.add("is-hidden");
  state.sessionSelectionGeneration += 1;
  state.workspace = workspace;
  state.routingResolution = null;
  renderRoutingResolution();
  state.messages = [];
  state.highlightedMessageIndex = null;
  el["thread-search"].value = "";
  state.threadSearchMatches = [];
  state.threadSearchCursor = -1;
  state.roots = [];
  state.treeGeneration += 1;
  invalidateProjectSearch();
  invalidateAttachments();
  invalidateContextItems();
  state.liveAssistant = null;
  state.activities.clear();
  state.diff = "";
  state.selectedFiles.clear();
  state.selectedHunks.clear();
  state.checkpoints = [];
  state.workers = [];
  state.workerGeneration += 1;
  state.plans = [];
  state.planBuilds = [];
  state.planBuildGeneration += 1;
  state.candidateDiffs.clear();
  state.mcpServers = [];
  state.mcpLoadGeneration += 1;
  state.artifacts = [];
  state.artifactLoadGeneration += 1;
  state.goals = [];
  state.goalGeneration += 1;
  el["task-title"].textContent = "New task";
  closeTerminalView();
  clearArtifactPreview();
  updateWorkspaceLabel();
  renderSessions();
  renderConversation();
  renderDiff();
  renderCheckpoints();
  renderContextRoots();
  renderProjectTree();
  renderWorkers();
  renderPlans();
  renderPlanBuilds();
  renderGoals();
  updateThreadSearchControls();
  connectSocket();
  return true;
}

async function pickWorkspace() {
  try {
    if (invoke) return await invoke("pick_workspace");
    const fallback = window.prompt("Enter an absolute workspace path");
    return fallback?.startsWith("/") ? fallback : null;
  } catch (error) {
    if (!String(error).toLowerCase().includes("cancel")) {
      toast(String(error), "error");
    }
    return null;
  }
}

function updateWorkspaceLabel() {
  el["workspace-path"].textContent = shortPath(state.workspace);
  el["workspace-label"].textContent = basename(state.workspace);
  updateContextPanelVisibility();
  updateComposer();
}

function updateContextPanelVisibility() {
  // Project controls are useful only after a turn has created an approved root.
  // Keeping this quiet makes an empty workspace read like a focused Codex task.
  el["context-panel"].classList.toggle(
    "is-hidden",
    !state.workspace || !state.roots.length
  );
}

function invalidateAttachments() {
  state.attachmentGeneration += 1;
  state.attachments = [];
  state.attachmentReader?.abort();
  state.attachmentReader = null;
  renderAttachments();
}

function invalidateContextItems() {
  state.contextGeneration += 1;
  state.contextItems = [];
  state.contextPending = false;
  renderContextItems();
}

function connectSocket() {
  if (!state.sessionId || !state.online) return;
  disconnectSocket();
  const session = encodeURIComponent(state.sessionId);
  const socket = new WebSocket(
    `${WS}/ws/session/${session}`,
    ["codinal.v1", `codinal.auth.${TOKEN}`]
  );
  state.socket = socket;
  socket.addEventListener("message", (message) => {
    try {
      handleEvent(JSON.parse(message.data));
    } catch {
      toast("Received an invalid runtime event", "error");
    }
  });
  socket.addEventListener("close", () => {
    if (state.socket === socket) state.socket = null;
  });
}

function disconnectSocket() {
  if (state.socket) state.socket.close();
  state.socket = null;
}

function setBusy(busy) {
  state.busy = busy;
  el["model-select"].disabled = busy;
  el["routing-profile"].disabled = busy || state.routingPending;
  el["agent-mode"].disabled = busy;
  el["new-task"].disabled = busy;
  el["choose-workspace"].disabled = busy;
  el["terminal-restart"].disabled = busy || !state.workspace;
  el["terminal-clear"].disabled = busy;
  el["add-context-root"].disabled = (
    busy || state.rootMutationPending || !state.roots.length
  );
  el["project-search"].disabled = busy || !state.roots.length;
  el["project-search-mode"].disabled = busy || !state.roots.length;
  renderProjectIndexStatus();
  el["restore-checkpoint"].disabled = (
    busy || !el["checkpoint-select"].value
  );
  el["stop-turn"].classList.toggle("is-hidden", !busy);
  el["send-turn"].classList.toggle("is-hidden", busy);
  setRuntimeStatus(busy ? "Codinal is working" : "Local runtime", busy ? "busy" : "online");
  updateThreadSearchControls();
  updateComposer();
}

function handleEvent(event) {
  switch (event.type) {
    case "turn_start":
      setBusy(true);
      break;
    case "assistant_delta":
      state.liveAssistant = (state.liveAssistant || "") + (event.text || "");
      scheduleLiveAssistantRender();
      break;
    case "assistant_message":
      state.liveAssistant = event.text || null;
      renderConversation();
      break;
    case "tool_proposed":
      addActivity(event.name, "Proposed");
      break;
    case "tool_started":
      addActivity(event.name, "Running", true);
      break;
    case "tool_finished":
      addActivity(event.name, event.status || "Finished");
      break;
    case "permission_required":
      renderApproval(event);
      break;
    case "plan_proposed":
      loadPlans().catch((error) => toast(error.message, "error"));
      loadPendingInteractions().catch((error) => {
        toast(error.message, "error");
      });
      break;
    case "directory_requested":
    case "question_requested":
      loadPendingInteractions().catch((error) => {
        toast(error.message, "error");
      });
      break;
    case "error":
      toast(event.error || "Turn failed", "error");
      setBusy(false);
      break;
    case "interrupted":
      toast("Turn stopped");
      finishTurn();
      break;
    case "turn_end":
      finishTurn();
      break;
    case "worker_status":
      updateWorker(event.worker);
      loadPlanBuilds().catch((error) => toast(error.message, "error"));
      break;
    case "plan_build_status":
      updatePlanBuild(event.build);
      break;
    case "goal_status":
      updateGoal(event.goal);
      break;
    default:
      break;
  }
}

async function finishTurn() {
  setBusy(false);
  state.liveAssistant = null;
  try {
    state.messages = await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/messages`
    );
    await Promise.all([
      loadSessions(),
      loadDiff(false),
      loadRootsAndTree(),
      loadWorkers(),
      loadPlans(),
      loadPlanBuilds(),
      loadGoals(),
    ]);
  } catch (error) {
    toast(error.message, "error");
  }
  renderConversation();
}

async function loadRootsAndTree() {
  const sessionId = state.sessionId;
  const generation = ++state.treeGeneration;
  if (!sessionId) {
    state.roots = [];
    renderContextRoots();
    renderProjectSearchResults();
    renderProjectTree();
    return;
  }
  const roots = await api(
    `/v1/sessions/${encodeURIComponent(sessionId)}/roots`
  );
  if (
    state.sessionId !== sessionId
    || state.treeGeneration !== generation
  ) return;
  state.roots = roots;
  const availableRoots = new Set(
    roots
      .filter((root) => root.available !== false)
      .map((root) => root.path)
  );
  const retainedContext = state.contextItems.filter(
    (item) => availableRoots.has(item.root)
  );
  if (retainedContext.length !== state.contextItems.length) {
    state.contextItems = retainedContext;
    state.contextGeneration += 1;
    renderContextItems();
  }
  el["add-context-root"].disabled = (
    state.busy || state.rootMutationPending || !roots.length
  );
  renderContextRoots();
  el["project-search"].disabled = state.busy || !availableRoots.size;
  el["project-search-mode"].disabled = state.busy || !availableRoots.size;
  loadProjectIndexStatus(sessionId);
  if (el["project-search"].value.trim()) scheduleProjectSearch();
  else renderProjectSearchResults();
  renderProjectTree(generation);
}

function renderContextRoots() {
  updateContextPanelVisibility();
  el["add-context-root"].disabled = (
    state.busy || state.rootMutationPending || !state.roots.length
  );
  el["context-roots"].replaceChildren();
  for (const root of state.roots) {
    const chip = node("div", "context-root");
    chip.classList.toggle("is-unavailable", root.available === false);
    chip.title = root.path;
    const label = node("span", "context-root-label");
    label.append(
      node("strong", "", root.label || basename(root.path)),
      node(
        "small",
        "",
        `${root.available === false
          ? "Unavailable"
          : root.writable ? "Read and write" : "Read only"} · ${shortPath(root.path)}`
      )
    );
    chip.append(label);
    if (!root.primary) {
      const remove = node("button", "context-root-remove", "×");
      remove.type = "button";
      remove.setAttribute(
        "aria-label",
        `Remove ${root.path}`
      );
      remove.addEventListener("click", () => {
        removeContextRoot(root).catch(
          (error) => toast(error.message, "error")
        );
      });
      chip.append(remove);
    }
    el["context-roots"].append(chip);
  }
}

function invalidateProjectSearch() {
  window.clearTimeout(state.projectSearchTimer);
  state.projectSearchController?.abort();
  state.projectSearchController = null;
  state.projectSearchGeneration += 1;
  state.projectSearchResults = null;
  state.projectIndexStatus = null;
  state.projectIndexGeneration += 1;
  state.projectIndexBusySession = null;
  el["project-search"].value = "";
  el["project-search-status"].textContent = "";
  el["project-search-results"].replaceChildren();
  el["project-tree"].classList.remove("is-hidden");
  el["session-list"].classList.remove("is-project-searching");
  el["project-search"].disabled = true;
  el["project-search-mode"].disabled = true;
  renderProjectIndexStatus();
}

function cancelProjectSearch(sessionId = state.sessionId) {
  state.projectSearchController?.abort();
  state.projectSearchController = null;
  if (!sessionId) return;
  api(
    `/v1/sessions/${encodeURIComponent(sessionId)}/project/search`,
    { method: "DELETE" }
  ).catch(() => {});
}

function scheduleProjectSearch() {
  window.clearTimeout(state.projectSearchTimer);
  state.projectSearchController?.abort();
  state.projectSearchController = null;
  state.projectSearchGeneration += 1;
  if (!el["project-search"].value.trim()) {
    state.projectSearchResults = null;
    renderProjectSearchResults();
    return;
  }
  state.projectSearchTimer = window.setTimeout(() => {
    loadProjectSearch().catch((error) => {
      if (error.name !== "AbortError") toast(error.message, "error");
    });
  }, 180);
}

async function loadProjectIndexStatus(sessionId = state.sessionId) {
  if (!sessionId || !state.roots.length) {
    state.projectIndexStatus = null;
    renderProjectIndexStatus();
    return;
  }
  const generation = ++state.projectIndexGeneration;
  const rootSnapshot = state.roots
    .map((root) => `${root.path}:${root.available !== false}`)
    .join("\n");
  let result;
  try {
    result = await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/project/index`
    );
  } catch (_error) {
    if (
      state.sessionId === sessionId
      && state.projectIndexGeneration === generation
      && state.roots
        .map((root) => `${root.path}:${root.available !== false}`)
        .join("\n") === rootSnapshot
    ) {
      state.projectIndexStatus = null;
      renderProjectIndexStatus();
    }
    return;
  }
  if (
    state.sessionId !== sessionId
    || state.projectIndexGeneration !== generation
    || state.roots
      .map((root) => `${root.path}:${root.available !== false}`)
      .join("\n") !== rootSnapshot
  ) return;
  state.projectIndexStatus = result;
  renderProjectIndexStatus();
}

function renderProjectIndexStatus() {
  const status = state.projectIndexStatus;
  const available = state.roots.some((root) => root.available !== false);
  const indexBusy = state.projectIndexBusySession === state.sessionId;
  const busy = state.busy || indexBusy;
  const files = (status?.roots || [])
    .reduce((total, root) => total + Number(root.files || 0), 0);
  const chunks = (status?.roots || [])
    .reduce((total, root) => total + Number(root.chunks || 0), 0);
  el["project-index-status"].textContent = (
    indexBusy
      ? "Building local index…"
      : status?.state === "ready"
        ? `Semantic · ${files} files · ${chunks} chunks`
        : status?.state === "partial"
          ? `Semantic index limited · ${chunks} chunks`
          : "Semantic index not built"
  );
  el["project-index-build"].textContent = chunks ? "Reindex" : "Index";
  el["project-index-build"].disabled = busy || !available;
  el["project-index-clear"].disabled = busy || !chunks;
}

async function rebuildProjectIndex() {
  const sessionId = state.sessionId;
  if (!sessionId || state.projectIndexBusySession === sessionId) return;
  state.projectIndexBusySession = sessionId;
  renderProjectIndexStatus();
  try {
    const result = await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/project/index`,
      { method: "POST" }
    );
    if (state.sessionId !== sessionId) return;
    await loadProjectIndexStatus(sessionId);
    toast(
      `Indexed ${result.indexed_files} files · ${result.indexed_chunks} chunks`
    );
    if (
      el["project-search-mode"].value === "semantic"
      && el["project-search"].value.trim()
    ) scheduleProjectSearch();
  } finally {
    if (state.projectIndexBusySession === sessionId) {
      state.projectIndexBusySession = null;
    }
    renderProjectIndexStatus();
  }
}

async function clearProjectIndex() {
  const sessionId = state.sessionId;
  if (
    !sessionId
    || state.projectIndexBusySession === sessionId
    || !window.confirm("Delete the local semantic index for this project?")
  ) return;
  state.projectIndexBusySession = sessionId;
  renderProjectIndexStatus();
  try {
    await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/project/index`,
      { method: "DELETE" }
    );
    if (state.sessionId !== sessionId) return;
    state.projectSearchResults = null;
    renderProjectSearchResults();
    await loadProjectIndexStatus(sessionId);
    toast("Local semantic index deleted");
  } finally {
    if (state.projectIndexBusySession === sessionId) {
      state.projectIndexBusySession = null;
    }
    renderProjectIndexStatus();
  }
}

async function loadProjectSearch() {
  const sessionId = state.sessionId;
  const query = el["project-search"].value.trim();
  const mode = el["project-search-mode"].value;
  if (!sessionId || !query || !state.roots.length) return;
  const generation = ++state.projectSearchGeneration;
  state.projectSearchController?.abort();
  const controller = new AbortController();
  state.projectSearchController = controller;
  el["project-search-status"].textContent = "Searching…";
  const parameters = new URLSearchParams({
    q: query,
    mode,
    limit: "50",
  });
  let result;
  try {
    result = await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/project/search?${parameters}`,
      { signal: controller.signal }
    );
  } catch (error) {
    if (
      error.name !== "AbortError"
      && state.sessionId === sessionId
      && state.projectSearchGeneration === generation
    ) {
      state.projectSearchController = null;
      state.projectSearchResults = null;
      el["project-search-results"].replaceChildren();
      el["project-search-status"].textContent = "Search unavailable";
    }
    throw error;
  }
  if (
    state.sessionId !== sessionId
    || state.projectSearchGeneration !== generation
  ) return;
  state.projectSearchController = null;
  state.projectSearchResults = result;
  renderProjectSearchResults();
}

function renderProjectSearchResults() {
  const query = el["project-search"].value.trim();
  const result = state.projectSearchResults;
  el["session-list"].classList.toggle(
    "is-project-searching",
    Boolean(query)
  );
  el["project-tree"].classList.toggle("is-hidden", Boolean(query));
  el["project-search-results"].classList.toggle(
    "is-active",
    Boolean(query)
  );
  el["project-search-results"].replaceChildren();
  if (!query) {
    el["project-search-status"].textContent = "";
    return;
  }
  if (!result) return;
  const scanLabel = result.mode === "semantic"
    ? `semantic · ${result.duration_ms} ms`
    : `${result.files_scanned} files · ${result.duration_ms} ms`;
  el["project-search-status"].textContent = (
    `${result.count} match${result.count === 1 ? "" : "es"} · `
    + scanLabel
    + `${result.stale_chunks ? ` · ${result.stale_chunks} stale` : ""}`
    + `${result.truncated ? " · limited" : ""}`
  );
  for (const match of result.matches || []) {
    const root = state.roots.find(
      (candidate) => candidate.path === match.root
    );
    const button = node("button", "project-search-result");
    button.type = "button";
    button.disabled = !root;
    button.setAttribute(
      "aria-label",
      `Add ${match.path} to project context`
    );
    button.append(
      node(
        "strong",
        "",
        `${match.root_label}/${match.path}:${match.line}`
      ),
      node(
        "small",
        "",
        `${match.kind ? `${match.kind} · ` : ""}${match.text}`
      )
    );
    button.addEventListener("click", () => {
      if (!root) return;
      addProjectContext(root, match.path, "file").catch(
        (error) => toast(error.message, "error")
      );
    });
    el["project-search-results"].append(button);
  }
}

function renderProjectTree(generation = state.treeGeneration) {
  el["project-tree"].replaceChildren();
  if (!state.roots.length) {
    el["project-tree"].append(
      node("p", "tree-empty", "Project files appear after the first turn")
    );
    return;
  }
  for (const root of state.roots) {
    const section = node("section", "tree-root");
    const title = node(
      "strong",
      "tree-root-title",
      root.label || basename(root.path)
    );
    title.title = root.path;
    const heading = node("div", "tree-root-heading");
    heading.append(title);
    heading.append(
      projectTreeAction("Git", "Add Git context", () => {
        addProjectContext(root, "", "git").catch(
          (error) => toast(error.message, "error")
        );
      })
    );
    section.append(heading);
    const entries = node("div", "tree-entries");
    section.append(entries);
    el["project-tree"].append(section);
    if (root.available === false) {
      entries.append(
        node("p", "tree-empty", "Root unavailable — reconnect or remove it")
      );
      continue;
    }
    loadTreeDirectory(entries, root, "", generation).catch(
      (error) => {
        if (state.treeGeneration === generation) {
          entries.replaceChildren(
            node("p", "tree-empty", error.message)
          );
        }
      }
    );
  }
}

async function loadTreeDirectory(container, root, path, generation) {
  const sessionId = state.sessionId;
  if (!sessionId) return;
  const query = new URLSearchParams({
    root: root.path,
    path,
    limit: "200",
  });
  const result = await api(
    `/v1/sessions/${encodeURIComponent(sessionId)}/tree?${query}`
  );
  if (
    state.sessionId !== sessionId
    || state.treeGeneration !== generation
  ) return;
  container.replaceChildren();
  for (const entry of result.entries || []) {
    if (entry.kind === "directory") {
      const details = node("details", "tree-directory");
      const summary = node("summary");
      summary.append(
        node("span", "tree-entry-label", entry.name),
        projectTreeAction("+", "Add folder context", () => {
          addProjectContext(root, entry.path, "folder").catch(
            (error) => toast(error.message, "error")
          );
        }),
        projectTreeAction("↗", "Open in default app", () => {
          openProjectPath(root, entry.path, "folder", "open").catch(
            (error) => toast(error.message, "error")
          );
        }),
        projectTreeAction("⌕", "Reveal in Finder", () => {
          openProjectPath(root, entry.path, "folder", "reveal").catch(
            (error) => toast(error.message, "error")
          );
        })
      );
      const children = node("div", "tree-children");
      details.append(summary, children);
      details.addEventListener("toggle", () => {
        if (!details.open || details.dataset.loaded) return;
        details.dataset.loaded = "true";
        loadTreeDirectory(
          children,
          root,
          entry.path,
          generation
        ).catch((error) => {
          delete details.dataset.loaded;
          children.replaceChildren(
            node("p", "tree-empty", error.message)
          );
        });
      });
      container.append(details);
    } else {
      const row = node(
        "div",
        `tree-file${entry.kind === "symlink" ? " is-symlink" : ""}`
      );
      row.append(
        node(
          "span",
          "tree-file-icon",
          entry.kind === "symlink" ? "↗" : "·"
        ),
        node("span", "tree-entry-label", entry.name)
      );
      if (entry.kind === "file") {
        row.append(
          projectTreeAction("+", "Add file context", () => {
            addProjectContext(root, entry.path, "file").catch(
              (error) => toast(error.message, "error")
            );
          }),
          projectTreeAction("↗", "Open in default app", () => {
            openProjectPath(root, entry.path, "file", "open").catch(
              (error) => toast(error.message, "error")
            );
          }),
          projectTreeAction("⌕", "Reveal in Finder", () => {
            openProjectPath(root, entry.path, "file", "reveal").catch(
              (error) => toast(error.message, "error")
            );
          })
        );
      }
      // Click the file row (not an action button) → open in editor tab.
      row.style.cursor = "pointer";
      row.addEventListener("click", (event) => {
        // Don't intercept clicks on action buttons.
        if (event.target.closest("button")) return;
        if (entry.kind === "file") {
          openEditorTab(entry.path).catch((error) =>
            toast(error.message, "error")
          );
        }
      });
      container.append(row);
    }
  }
  if (result.truncated) {
    container.append(
      node("p", "tree-empty", "More entries are hidden")
    );
  }
}

function projectTreeAction(text, title, action) {
  const button = node("button", "tree-entry-action", text);
  button.type = "button";
  button.title = title;
  button.setAttribute("aria-label", title);
  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    action();
  });
  return button;
}

async function addProjectContext(root, path, kind) {
  if (
    !state.sessionId
    || state.busy
    || state.contextPending
  ) return;
  if (state.contextItems.length >= 8) {
    toast("Add up to 8 project context items", "error");
    return;
  }
  const sessionId = state.sessionId;
  const generation = state.contextGeneration;
  state.contextPending = true;
  updateComposer();
  try {
    const result = await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/context`,
      {
        method: "POST",
        body: JSON.stringify({ root: root.path, path, kind }),
      }
    );
    if (
      state.sessionId !== sessionId
      || state.contextGeneration !== generation
    ) return;
    const item = result.item;
    if (!item?.fingerprint || !item?.content_part) {
      throw new Error("Project context could not be captured");
    }
    const existing = state.contextItems.findIndex(
      (candidate) => (
        candidate.kind === item.kind
        && candidate.root === item.root
        && candidate.path === item.path
      )
    );
    if (existing >= 0) {
      state.contextItems.splice(existing, 1, item);
    } else {
      state.contextItems.push(item);
    }
    renderContextItems();
  } finally {
    state.contextPending = false;
    updateComposer();
  }
}

async function openProjectPath(root, path, kind, mode) {
  if (!state.sessionId || state.busy) return;
  await api(
    `/v1/sessions/${encodeURIComponent(state.sessionId)}/project/open`,
    {
      method: "POST",
      body: JSON.stringify({ root: root.path, path, kind, mode }),
    }
  );
}

async function addContextRoot() {
  const sessionId = state.sessionId;
  if (
    !sessionId
    || state.busy
    || state.rootMutationPending
    || !state.roots.length
  ) return;
  const path = await pickWorkspace();
  if (!path || state.sessionId !== sessionId) return;
  if (
    !window.confirm(
      "Add this folder as readable project context for this task?"
    )
  ) return;
  const writable = window.confirm(
    "Also allow Codinal to edit files in this folder?\n\n"
    + "Cancel keeps the folder read-only."
  );
  state.rootMutationPending = true;
  renderContextRoots();
  try {
    await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/roots`,
      {
        method: "POST",
        body: JSON.stringify({ path, writable }),
      }
    );
    if (state.sessionId === sessionId) await loadRootsAndTree();
  } finally {
    state.rootMutationPending = false;
    renderContextRoots();
  }
}

async function removeContextRoot(root) {
  const sessionId = state.sessionId;
  if (
    !sessionId
    || state.busy
    || state.rootMutationPending
    || root.primary
  ) return;
  if (
    !window.confirm(
      `Remove ${root.label || basename(root.path)} from this task?`
    )
  ) return;
  state.rootMutationPending = true;
  renderContextRoots();
  try {
    await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/roots`,
      {
        method: "DELETE",
        body: JSON.stringify({ path: root.path }),
      }
    );
    if (state.sessionId === sessionId) await loadRootsAndTree();
  } finally {
    state.rootMutationPending = false;
    renderContextRoots();
  }
}

function pruneMessageRenderCache(visible) {
  const visibleIndexes = new Set(visible.map(({ index }) => index));
  for (const index of state.messageRenderCache.keys()) {
    if (!visibleIndexes.has(index)) state.messageRenderCache.delete(index);
  }
}

function renderConversation() {
  if (el["thread-search"].value) {
    syncThreadSearchMatches();
  } else {
    updateThreadSearchControls();
  }
  const visible = state.messages
    .map((message, index) => ({ message, index }))
    .filter(
      ({ message }) => (
        message.role === "user" || message.role === "assistant"
      )
    );
  renderConversationContext(visible.length);
  pruneMessageRenderCache(visible);
  el["empty-state"].classList.toggle(
    "is-hidden",
    Boolean(visible.length || state.liveAssistant || state.activities.size)
  );
  const fragment = document.createDocumentFragment();
  for (const { message, index } of visible) {
    fragment.append(renderPersistedMessage(message, index));
  }
  if (state.liveAssistant) {
    fragment.append(renderMessage("assistant", state.liveAssistant, true));
  }
  for (const activity of state.activities.values()) {
    fragment.append(renderActivity(activity));
  }
  el["message-list"].replaceChildren(fragment);
  const highlighted = el["message-list"].querySelector(
    ".message.is-search-match"
  );
  if (highlighted) {
    highlighted.scrollIntoView({ block: "center" });
  } else {
    el.conversation.scrollTop = el.conversation.scrollHeight;
  }
}

function renderConversationContext(messageCount) {
  const active = state.liveAssistant || state.activities.size;
  el["conversation-summary"].textContent = active
    ? "Working"
    : messageCount
      ? `${messageCount} messages`
      : "No messages yet";
  el["conversation-context"].classList.toggle(
    "has-activity", Boolean(active)
  );
  el["conversation-context"].classList.toggle(
    "is-empty", !messageCount && !active
  );
  el["empty-state"].classList.toggle(
    "is-empty-workspace", !messageCount && !active
  );
}

function renderPersistedMessage(message, index) {
  const forkable = isSafeForkBoundary(index);
  const routing = message.source?.routing || null;
  const cached = state.messageRenderCache.get(index);
  let article;
  if (
    cached
    && cached.message === message
    && cached.forkable === forkable
    && cached.routing === routing
  ) {
    article = cached.article;
  } else {
    article = renderMessage(
      message.role,
      contentText(message.content),
      false,
      index,
      forkable,
      routing
    );
    state.messageRenderCache.set(index, {
      message, forkable, routing, article,
    });
  }
  article.classList.toggle(
    "is-search-match",
    index === state.highlightedMessageIndex
  );
  return article;
}

function scheduleLiveAssistantRender() {
  if (state.liveAssistantFrame !== null) return;
  const schedule = window.requestAnimationFrame
    ? window.requestAnimationFrame.bind(window)
    : (callback) => window.setTimeout(callback, 16);
  state.liveAssistantFrame = schedule(() => {
    state.liveAssistantFrame = null;
    const liveContent = el["message-list"].querySelector(
      ".message.is-streaming .message-content"
    );
    if (!state.liveAssistant || !liveContent) {
      renderConversation();
      return;
    }
    // Keep streaming cheap: markdown is parsed once when the persisted message
    // arrives, not for every token over the socket.
    liveContent.textContent = state.liveAssistant;
    const highlighted = el["message-list"].querySelector(
      ".message.is-search-match"
    );
    if (highlighted) {
      highlighted.scrollIntoView({ block: "center" });
    } else {
      el.conversation.scrollTop = el.conversation.scrollHeight;
    }
  });
}

function findThreadMatches(query = el["thread-search"].value) {
  syncThreadSearchMatches(query, true);
  renderConversation();
}

function syncThreadSearchMatches(
  query = el["thread-search"].value,
  reset = false
) {
  const needle = query.trim().toLocaleLowerCase();
  const matches = needle
    ? state.messages
      .map((message, index) => ({ message, index }))
      .filter(
        ({ message }) => (
          (message.role === "user" || message.role === "assistant")
          && contentText(message.content).toLocaleLowerCase().includes(needle)
        )
      )
      .map(({ index }) => index)
    : [];
  const currentIndex = reset ? null : state.highlightedMessageIndex;
  state.threadSearchMatches = matches;
  const retainedCursor = matches.indexOf(currentIndex);
  state.threadSearchCursor = retainedCursor >= 0
    ? retainedCursor
    : matches.length ? 0 : -1;
  state.highlightedMessageIndex = (
    state.threadSearchMatches[state.threadSearchCursor] ?? null
  );
  updateThreadSearchControls();
}

function moveThreadSearch(direction) {
  if (!state.threadSearchMatches.length) return;
  state.threadSearchCursor = (
    state.threadSearchCursor + direction + state.threadSearchMatches.length
  ) % state.threadSearchMatches.length;
  state.highlightedMessageIndex = (
    state.threadSearchMatches[state.threadSearchCursor]
  );
  renderConversation();
}

function updateThreadSearchControls() {
  const hasMatches = state.threadSearchMatches.length > 0;
  el["thread-search-previous"].disabled = !hasMatches;
  el["thread-search-next"].disabled = !hasMatches;
  el["export-thread"].disabled = !state.sessionId || state.busy;
}

function contentText(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  const text = content
    .filter(
      (part) => (
        part
        && part.type === "text"
        && !part._codinal_context
      )
    )
    .map((part) => part.text || "")
    .join("\n");
  const files = content
    .filter((part) => part?.type === "image_url" || part?.type === "file")
    .map((part) => part.type === "file" ? part.file?.filename : "Image")
    .filter(Boolean);
  return [text, files.length ? `Attached: ${files.join(", ")}` : ""]
    .filter(Boolean)
    .join("\n");
}

function renderMessage(
  role,
  content,
  streaming = false,
  messageIndex = null,
  forkable = false,
  routing = null
) {
  const article = node("article", `message ${role}`);
  article.classList.toggle("is-streaming", streaming);
  if (Number.isInteger(messageIndex)) {
    article.dataset.messageIndex = String(messageIndex);
    article.classList.toggle(
      "is-search-match",
      messageIndex === state.highlightedMessageIndex
    );
  }
  const who = role === "assistant" ? "C" : "You";
  article.append(node("div", "message-avatar", role === "assistant" ? "C" : "Y"));
  const body = node("div", "message-body");
  body.append(
    node("div", "message-meta", streaming ? "Codinal · Writing…" : who),
  );
  // Assistant messages get markdown rendering; user messages stay plain text.
  const contentEl = node("div", "message-content");
  if (role === "assistant" && window.marked) {
    try {
      // Sanitize: marked doesn't execute scripts by default (no raw HTML pass).
      contentEl.innerHTML = window.marked.parse(content || "", { breaks: true });
    } catch {
      contentEl.textContent = content;
    }
  } else {
    contentEl.textContent = content;
  }
  body.append(contentEl);
  if (role === "user" && routing?.selected_model) {
    const degradations = routing.degradations || [];
    const badge = node(
      "div",
      "message-routing",
      `${routing.profile} → ${routing.provider} · `
      + `${routing.selected_model} · ${routing.cost_class}`
      + `${degradations.length ? ` · ${degradations.join("; ")}` : ""}`
    );
    badge.classList.toggle("has-degradation", Boolean(degradations.length));
    body.append(badge);
  }
  if (Number.isInteger(messageIndex) && forkable) {
    const actions = node("div", "message-actions");
    const fork = node("button", "message-action", "Fork task from here");
    fork.type = "button";
    fork.addEventListener("click", () => {
      forkSessionAt(messageIndex).catch(
        (error) => toast(error.message, "error")
      );
    });
    actions.append(fork);
    const side = node("button", "message-action", "Open side conversation");
    side.type = "button";
    side.addEventListener("click", () => {
      createSideConversationAt(messageIndex).catch(
        (error) => toast(error.message, "error")
      );
    });
    actions.append(side);
    body.append(actions);
  }
  article.append(body);
  return article;
}

function isSafeForkBoundary(messageIndex) {
  const pending = new Set();
  for (const message of state.messages.slice(0, messageIndex + 1)) {
    if (!message || typeof message !== "object") return false;
    if (pending.size) {
      if (message.role !== "tool"
        || typeof message.tool_call_id !== "string"
        || !pending.has(message.tool_call_id)) return false;
      pending.delete(message.tool_call_id);
      continue;
    }
    if (message.role === "tool") return false;
    if (message.role !== "assistant" || !message.tool_calls?.length) continue;
    if (!Array.isArray(message.tool_calls)) return false;
    for (const call of message.tool_calls) {
      if (!call || typeof call.id !== "string" || !call.id
        || pending.has(call.id)) return false;
      pending.add(call.id);
    }
  }
  return pending.size === 0;
}

async function forkSessionAt(messageIndex) {
  return branchSessionAt(messageIndex, "fork");
}

async function createSideConversationAt(messageIndex) {
  return branchSessionAt(messageIndex, "side");
}

async function branchSessionAt(messageIndex, kind) {
  if (!state.sessionId) return;
  const settings = BRANCH_SETTINGS[kind];
  if (!settings) throw new Error("Unknown conversation branch type");
  if (state.busy) {
    toast(settings.busy, "error");
    return;
  }
  const sourceSessionId = state.sessionId;
  const sourceSelectionGeneration = state.sessionSelectionGeneration;
  const sourceSearchGeneration = state.sessionSearchGeneration;
  const result = await api(
    `/v1/sessions/${encodeURIComponent(sourceSessionId)}/${settings.endpoint}`,
    {
      method: "POST",
      body: JSON.stringify({ message_index: messageIndex }),
    }
  );
  if (
    state.sessionId !== sourceSessionId
    || state.sessionSelectionGeneration !== sourceSelectionGeneration
  ) {
    loadSessions().catch((error) => toast(error.message, "error"));
    toast(settings.created);
    return;
  }
  if (!result.session) {
    throw new Error(settings.missing);
  }
  if (state.sessionSearchGeneration === sourceSearchGeneration) {
    el["session-search"].value = "";
  }
  await selectSession(result.session);
  await loadSessions();
  toast(settings.opened);
}

async function exportThread() {
  if (!state.sessionId || state.busy) return;
  const response = await fetch(
    `${HTTP}/v1/sessions/${encodeURIComponent(state.sessionId)}/export.md`,
    { headers: { Authorization: `Bearer ${TOKEN}` } }
  );
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(
      payload.detail || `Runtime returned HTTP ${response.status}`
    );
  }
  const disposition = response.headers.get("Content-Disposition") || "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1]
    || "codinal-conversation.md";
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
  toast("Exported conversation as Markdown");
}

async function returnToParentSession() {
  const parentSessionId = state.parentSessionId;
  if (!parentSessionId || state.busy) return;
  el["session-search"].value = "";
  await loadSessions();
  const parent = state.sessions.find(
    (session) => session.session_id === parentSessionId
  );
  if (!parent) throw new Error("Parent task is unavailable");
  await selectSession(parent);
}

function addActivity(name, status, running = false) {
  const key = `${name}-${state.activities.size}`;
  for (const [existingKey, activity] of state.activities) {
    if (activity.name === name && activity.running) {
      state.activities.set(existingKey, { name, status, running });
      renderConversation();
      return;
    }
  }
  state.activities.set(key, { name, status, running });
  renderConversation();
}

function renderActivity(activity) {
  const card = node("div", `activity-card${activity.running ? " is-running" : ""}`);
  card.append(
    node("span", "activity-icon", activity.running ? "◌" : "◇"),
    node("strong", "", activity.name),
    node("span", "activity-status", activity.status)
  );
  return card;
}

async function loadPendingApprovals() {
  const sessionId = state.sessionId;
  if (!sessionId) return;
  const pending = await api(
    `/v1/sessions/${encodeURIComponent(sessionId)}/approvals`
  );
  if (state.sessionId !== sessionId) return;
  for (const approval of pending) renderApproval(approval);
}

function renderApproval(approval) {
  if (document.querySelector(`[data-approval-id="${approval.approval_id}"]`)) return;
  const card = node("section", "approval-card");
  card.dataset.approvalId = approval.approval_id;
  const content = node("div", "approval-content");
  const title = node("div", "approval-title");
  title.append(node("span", "", "⚠"), node("strong", "", "Approval required"));
  content.append(
    title,
    node("p", "", `${approval.tool_name || approval.name} wants to run.`),
    node("p", "", approval.reason || "This action changes local state.")
  );
  const args = approval.arguments || {};
  content.append(node("pre", "approval-arguments", JSON.stringify(args, null, 2)));
  const actions = node("div", "approval-actions");
  const deny = node("button", "", "Deny");
  const once = node("button", "approve-once", "Allow once");
  deny.type = once.type = "button";
  deny.addEventListener("click", () => resolveApproval(card, approval, "deny"));
  once.addEventListener("click", () => resolveApproval(card, approval, "once"));
  actions.append(deny);
  const persistent = approval.risk === "exec"
    ? "always_command"
    : approval.risk === "write_local"
      ? "always_tool"
      : null;
  if (persistent) {
    const always = node("button", "", "Allow for task");
    always.type = "button";
    always.addEventListener(
      "click",
      () => resolveApproval(card, approval, persistent)
    );
    actions.append(always);
  }
  actions.append(once);
  card.append(content, actions);
  el["message-list"].append(card);
  el.conversation.scrollTop = el.conversation.scrollHeight;
}

async function resolveApproval(card, approval, outcome) {
  for (const button of card.querySelectorAll("button")) button.disabled = true;
  try {
    await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/approvals/${approval.approval_id}`,
      { method: "POST", body: JSON.stringify({ outcome }) }
    );
    card.remove();
  } catch (error) {
    for (const button of card.querySelectorAll("button")) button.disabled = false;
    toast(error.message, "error");
  }
}

async function loadPendingInteractions() {
  const sessionId = state.sessionId;
  if (!sessionId) return;
  const pending = await api(
    `/v1/sessions/${encodeURIComponent(sessionId)}/interactions`
  );
  if (state.sessionId !== sessionId) return;
  const current = new Set(
    pending.map((interaction) => interaction.interaction_id)
  );
  for (const card of document.querySelectorAll("[data-interaction-id]")) {
    if (card.dataset.interactionSession === sessionId
      && !current.has(card.dataset.interactionId)) card.remove();
  }
  for (const interaction of pending) {
    renderInteraction(interaction, sessionId);
  }
}

async function loadPlans() {
  const sessionId = state.sessionId;
  if (!sessionId) {
    state.plans = [];
    renderPlans();
    return;
  }
  const plans = await api(
    `/v1/sessions/${encodeURIComponent(sessionId)}/plans`
  );
  if (state.sessionId !== sessionId) return;
  state.plans = Array.isArray(plans) ? plans : [];
  renderPlans();
}

function renderPlans() {
  el["plan-list"].replaceChildren();
  el["plan-panel"].classList.toggle("is-hidden", !state.plans.length);
  if (!state.plans.length) {
    el["plan-summary"].textContent = "No saved plan";
    return;
  }
  const latest = state.plans[0];
  el["plan-summary"].textContent = latest.status.replace("_", " ");
  for (const plan of state.plans) {
    const card = node("article", "saved-plan");
    const selected = new Set(plan.selected_task_ids || []);
    card.append(
      node("strong", "", plan.plan),
      node(
        "span",
        "saved-plan-status",
        `${plan.status.replace("_", " ")} · revision ${plan.revision}`
      )
    );
    for (const task of Array.isArray(plan.tasks) ? plan.tasks : []) {
      const item = node(
        "div",
        `saved-plan-task ${selected.has(task.id) ? "is-selected" : ""}`
      );
      item.append(
        node("span", "", selected.has(task.id) ? "✓" : "○"),
        node("strong", "", task.title),
        node("small", "", task.verification)
      );
      card.append(item);
    }
    if (
      plan.status === "approved"
      && (plan.selected_task_ids || []).length
    ) {
      const compare = node(
        "button",
        "secondary-button",
        "Start parallel comparison"
      );
      compare.type = "button";
      compare.addEventListener("click", () => openPlanBuildDialog(plan));
      card.append(compare);
    }
    el["plan-list"].append(card);
  }
}

function renderInteraction(interaction, sessionId) {
  const id = interaction.interaction_id;
  if (!id || document.querySelector(`[data-interaction-id="${id}"]`)) return;
  const args = interaction.arguments || {};
  const card = node("section", "approval-card interaction-card");
  card.dataset.interactionId = id;
  card.dataset.interactionSession = sessionId;
  const content = node("div", "approval-content");
  const title = node("div", "approval-title");
  const labels = {
    directory: "Directory access",
    plan: "Review plan",
    question: "Question",
  };
  title.append(
    node("span", "", interaction.kind === "plan" ? "◇" : "?"),
    node("strong", "", labels[interaction.kind] || "Input required")
  );
  content.append(title);
  const actions = node("div", "approval-actions");

  if (interaction.kind === "plan") {
    const planEditor = node("textarea", "interaction-input plan-editor");
    planEditor.value = args.plan || "";
    planEditor.maxLength = 32768;
    planEditor.setAttribute("aria-label", "Editable plan summary");
    content.append(planEditor);
    const taskEditors = [];
    for (const task of Array.isArray(args.tasks) ? args.tasks : []) {
      const row = node("fieldset", "plan-task");
      const select = node("input", "plan-task-select");
      select.type = "checkbox";
      select.checked = true;
      select.setAttribute(
        "aria-label",
        `Select task ${task.title || task.id}`
      );
      const titleInput = node("input", "interaction-input");
      titleInput.value = task.title || "";
      titleInput.maxLength = 512;
      titleInput.setAttribute("aria-label", `Task ${task.id} title`);
      const description = node("textarea", "interaction-input");
      description.value = task.description || "";
      description.maxLength = 4096;
      description.placeholder = "Task description";
      description.setAttribute(
        "aria-label",
        `Task ${task.id} description`
      );
      const verification = node("input", "interaction-input");
      verification.value = task.verification || "";
      verification.maxLength = 2048;
      verification.placeholder = "Verification criterion";
      verification.setAttribute(
        "aria-label",
        `Task ${task.id} verification criterion`
      );
      const legend = node("legend", "plan-task-heading");
      legend.append(select, node("span", "", task.id));
      row.append(legend, titleInput, description, verification);
      content.append(row);
      taskEditors.push({
        id: task.id,
        select,
        titleInput,
        description,
        verification,
      });
    }
    const feedback = node("textarea", "interaction-input");
    feedback.placeholder = "Optional revision feedback";
    feedback.setAttribute("aria-label", "Plan revision feedback");
    content.append(feedback);
    const revise = node("button", "", "Request revision");
    const approve = node("button", "approve-once", "Approve and build");
    revise.type = approve.type = "button";
    revise.addEventListener("click", () => resolveInteraction(
      card,
      interaction,
      { approved: false, feedback: feedback.value }
    ));
    approve.addEventListener("click", () => {
      const tasks = taskEditors.map((editor) => ({
        id: editor.id,
        title: editor.titleInput.value.trim(),
        ...(editor.description.value.trim()
          ? { description: editor.description.value.trim() }
          : {}),
        verification: editor.verification.value.trim(),
      }));
      const selected_task_ids = taskEditors
        .filter((editor) => editor.select.checked)
        .map((editor) => editor.id);
      if (
        !planEditor.value.trim()
        || tasks.some((task) => !task.title || !task.verification)
      ) {
        toast("Plan tasks need a title and verification criterion", "error");
        return;
      }
      if (tasks.length && !selected_task_ids.length) {
        toast("Select at least one plan task", "error");
        return;
      }
      resolveInteraction(
        card,
        interaction,
        {
          approved: true,
          mode: "interactive",
          plan: planEditor.value.trim(),
          tasks,
          selected_task_ids,
        }
      );
    });
    actions.append(revise, approve);
  } else if (interaction.kind === "question") {
    content.append(node("p", "", args.question || "Input required"));
    const answer = node("textarea", "interaction-input");
    answer.placeholder = "Type your answer";
    answer.setAttribute("aria-label", "Answer");
    content.append(answer);
    for (const option of Array.isArray(args.options) ? args.options : []) {
      const choice = node("button", "", option);
      choice.type = "button";
      choice.addEventListener("click", () => resolveInteraction(
        card,
        interaction,
        { answer: String(option) }
      ));
      actions.append(choice);
    }
    const submit = node("button", "approve-once", "Answer");
    submit.type = "button";
    submit.addEventListener("click", () => {
      if (answer.value.trim()) {
        resolveInteraction(
          card,
          interaction,
          { answer: answer.value.trim() }
        );
      }
    });
    actions.append(submit);
  } else if (interaction.kind === "directory") {
    content.append(
      node("p", "", args.reason || "Codinal needs another directory."),
      node(
        "p",
        "",
        args.writable ? "Requested access: read and write" : "Requested access: read-only"
      ),
      node("pre", "approval-arguments", args.path || "Choose a folder")
    );
    const deny = node("button", "", "Decline");
    const choose = node("button", "approve-once", "Choose folder");
    deny.type = choose.type = "button";
    deny.addEventListener("click", () => resolveInteraction(
      card,
      interaction,
      { granted: false }
    ));
    choose.addEventListener("click", async () => {
      const path = await pickWorkspace();
      if (path) {
        await resolveInteraction(card, interaction, {
          granted: true,
          path,
          writable: Boolean(args.writable),
        });
      }
    });
    actions.append(deny, choose);
  } else {
    return;
  }
  card.append(content, actions);
  el["message-list"].append(card);
  el.conversation.scrollTop = el.conversation.scrollHeight;
}

async function resolveInteraction(card, interaction, response) {
  for (const button of card.querySelectorAll("button")) button.disabled = true;
  try {
    await api(
      `/v1/sessions/${encodeURIComponent(card.dataset.interactionSession)}/interactions/`
        + interaction.interaction_id,
      { method: "POST", body: JSON.stringify(response) }
    );
    card.remove();
  } catch (error) {
    for (const button of card.querySelectorAll("button")) button.disabled = false;
    toast(error.message, "error");
  }
}

async function sendTurn() {
  const input = el.prompt.value.trim();
  if ((!input && !state.attachments.length)
    || !state.sessionId || state.busy
    || state.attachmentsPending || state.contextPending) return;
  const attachments = state.attachments;
  const contexts = state.contextItems;
  const requestParts = [];
  if (input) requestParts.push({ "type": "text", "text": input });
  for (const attachment of attachments) {
    if (attachment.type === "application/pdf") {
      requestParts.push({
        "type": "file",
        "file": {
          "filename": attachment.name,
          "file_data": attachment.data,
        },
      });
    } else {
      requestParts.push({
        "type": "image_url",
        "image_url": { "url": attachment.data },
      });
    }
  }
  const requestInput = attachments.length ? requestParts : input;
  const displayTurnInput = contexts.length
    ? [...contexts.map((context) => context.content_part), ...requestParts]
    : requestInput;
  state.highlightedMessageIndex = null;
  const optimisticMessage = { role: "user", content: displayTurnInput };
  state.messages.push(optimisticMessage);
  el.prompt.value = "";
  state.attachments = [];
  state.contextItems = [];
  state.contextGeneration += 1;
  renderAttachments();
  renderContextItems();
  resizePrompt();
  renderConversation();
  setBusy(true);
  try {
    const started = await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/turns`,
      {
      method: "POST",
      body: JSON.stringify({
        input: requestInput,
        ...(state.workspace ? { workspace: state.workspace } : {}),
        agent: el["agent-mode"].value,
        mode: el["agent-mode"].value === "plan"
          ? "plan"
          : el["agent-mode"].value === "review"
            ? "discuss"
            : "interactive",
        model: el["model-select"].value,
        routing_profile: el["routing-profile"].value,
        ...(contexts.length ? {
          context: contexts.map((context) => ({
            kind: context.kind,
            root: context.root,
            path: context.path,
            fingerprint: context.fingerprint,
          })),
        } : {}),
      }),
      }
    );
    if (started.routing) {
      state.routingResolution = started.routing;
      optimisticMessage.source = { routing: started.routing };
      const session = state.sessions.find(
        (candidate) => candidate.session_id === state.sessionId
      );
      if (session) session.model = started.routing.selected_model;
      selectModel(started.routing.selected_model);
      renderRoutingResolution();
      renderConversation();
    }
  } catch (error) {
    state.messages.pop();
    state.attachments = attachments;
    state.contextItems = contexts;
    renderAttachments();
    renderContextItems();
    setBusy(false);
    renderConversation();
    toast(error.message, "error");
  }
}

async function stopTurn() {
  if (!state.sessionId || !state.busy) return;
  try {
    await api(`/v1/sessions/${encodeURIComponent(state.sessionId)}/interrupt`, {
      method: "POST",
    });
  } catch (error) {
    toast(error.message, "error");
  }
}

// --- Interactive PTY terminal (xterm.js + Rust pty backend) ---
//
// The terminal is a real persistent PTY owned by the Rust shell. We mount an
// xterm.js Terminal into #terminal-host lazily on first show, open a PTY
// session via the `pty_open` command, and stream bytes both ways:
//   - input:  term.onData → invoke("pty_input")
//   - output: "pty-data" event → term.write
//   - exit:   "pty-exit" event → show banner, offer Restart
// Resize is observed via ResizeObserver and forwarded via `pty_resize`.
// Teardown on workspace/session switch kills the PTY and disposes the term.

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Could not load ${src}`));
    document.head.append(script);
  });
}

function loadTerminalBundle() {
  if (window.Terminal && window.FitAddon?.FitAddon) return Promise.resolve();
  if (state.terminalLoad) return state.terminalLoad;
  state.terminalLoad = loadScript("./vendor/xterm.js")
    .then(() => loadScript("./vendor/xterm-addon-fit.js"))
    .then(() => {
      if (!window.Terminal || !window.FitAddon?.FitAddon) {
        throw new Error("Terminal module did not initialize");
      }
    })
    .catch((error) => {
      state.terminalLoad = null;
      throw error;
    });
  return state.terminalLoad;
}

function updateTerminalStatus(status) {
  el["terminal-status"].textContent = status;
}

function clearTerminalOutput() {
  if (state.terminal?.term) {
    state.terminal.term.clear();
  }
  updateTerminalStatus("Ready");
}

async function showTerminalView() {
  state.terminalViewGeneration += 1;
  el["terminal-panel"].classList.remove("is-hidden");
  if (state.terminal) {
    state.terminal.term.focus();
    return;
  }
  const opening = state.terminalOpening;
  if (opening) {
    try { await opening; } catch { /* retry below when the earlier open failed */ }
    if (state.terminal) {
      state.terminal.term.focus();
      return;
    }
  }
  await openTerminalView();
  el["terminal-restart"].focus();
}

async function hideTerminalView() {
  const generation = ++state.terminalViewGeneration;
  el["terminal-panel"].classList.add("is-hidden");
  await closeTerminalView();
  const opening = state.terminalOpening;
  if (opening) {
    try { await opening; } catch { /* closing should remain best-effort */ }
    if (
      state.terminalViewGeneration !== generation
      || !el["terminal-panel"].classList.contains("is-hidden")
    ) return;
    await closeTerminalView();
  }
  if (state.terminalViewGeneration !== generation) return;
  el.prompt.focus();
}

function setTerminalBusy(running) {
  // Kept as a no-op shim for legacy callers (session switch resets). The new
  // terminal has no "busy" state — it's always interactive.
  void running;
}

/** Decode a base64 string into a Uint8Array for xterm.write. */
function decodeBase64ToBytes(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

/** Mount xterm.js + open a PTY session for the current workspace. */
async function openTerminalView() {
  if (!invoke || !state.workspace) return;
  if (state.terminalOpening) return state.terminalOpening;
  state.terminalOpening = openTerminalViewInner().finally(() => {
    state.terminalOpening = null;
  });
  return state.terminalOpening;
}

async function openTerminalViewInner() {
  const host = el["terminal-host"];
  // If a term is already mounted, dispose it first.
  if (state.terminal?.term) {
    await closeTerminalView();
  }
  try {
    await loadTerminalBundle();
  } catch (error) {
    updateTerminalStatus("Terminal unavailable");
    host.textContent = error.message;
    return;
  }
  if (el["terminal-panel"].classList.contains("is-hidden")) return;
  const TermCtor = window.Terminal;
  const FitCtor = window.FitAddon?.FitAddon;
  if (!TermCtor || !FitCtor) {
    updateTerminalStatus("Terminal unavailable");
    host.textContent = "Terminal libraries failed to load.";
    return;
  }
  const term = new TermCtor({
    cursorBlink: true,
    fontFamily: "var(--mono, ui-monospace, Menlo, monospace)",
    fontSize: 12,
    theme: document.documentElement.dataset.theme === "dark"
      ? { background: "#171717", foreground: "#f5f5f5", cursor: "#f5f5f5" }
      : { background: "#ffffff", foreground: "#171717", cursor: "#171717" },
    allowProposedApi: true,
  });
  const fitAddon = new FitCtor();
  term.loadAddon(fitAddon);
  term.open(host);
  try { fitAddon.fit(); } catch { /* host not laid out yet */ }
  const cols = term.cols || 80;
  const rows = term.rows || 24;
  const sessionId = `pty-${state.sessionId || "default"}-${Date.now()}`;
  let unlistenData = null;
  let unlistenExit = null;
  const writeData = (event) => {
    if (event?.payload?.session_id !== sessionId) return;
    if (typeof event.payload.data === "string") {
      term.write(decodeBase64ToBytes(event.payload.data));
    }
  };
  const handleExit = (event) => {
    if (event?.payload?.session_id !== sessionId) return;
    term.write("\r\n\x1b[2m— session exited —\x1b[0m\r\n");
    updateTerminalStatus("Exited");
  };
  if (typeof window.__codinalListen === "function") {
    unlistenData = await window.__codinalListen("pty-data", writeData);
    unlistenExit = await window.__codinalListen("pty-exit", handleExit);
  }
  term.onData((text) => {
    invoke("pty_input", { sessionId, data: text }).catch((error) => {
      toast(String(error), "error");
    });
  });
  // Resize observer → fit + pty_resize.
  let resizeTimer = null;
  const resizeObserver = new ResizeObserver(() => {
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      try {
        fitAddon.fit();
        invoke("pty_resize", {
          sessionId,
          cols: term.cols,
          rows: term.rows,
        }).catch(() => { /* best-effort */ });
      } catch { /* host hidden */ }
    }, 80);
  });
  resizeObserver.observe(host);
  state.terminal = {
    term,
    fitAddon,
    sessionId,
    resizeObserver,
    unlistenData,
    unlistenExit,
  };
  updateTerminalStatus("Starting…");
  try {
    await invoke("pty_open", {
      sessionId,
      workspace: state.workspace,
      cols,
      rows,
    });
    // The view may have been closed while the PTY was starting (for example,
    // Restart or a task switch). Tear down that orphaned session instead of
    // reviving a disposed terminal.
    if (state.terminal?.sessionId !== sessionId) {
      await invoke("pty_kill", { sessionId }).catch(() => {});
      return;
    }
    updateTerminalStatus("Live");
    term.focus();
  } catch (error) {
    if (state.terminal?.sessionId !== sessionId) return;
    updateTerminalStatus("Failed");
    term.write(`\x1b[31mFailed to open terminal: ${String(error)}\x1b[0m\r\n`);
  }
}

/** Kill the PTY + dispose the xterm instance. */
async function closeTerminalView() {
  const t = state.terminal;
  if (!t) return;
  state.terminal = null;
  try { t.resizeObserver?.disconnect(); } catch { /* noop */ }
  try { t.unlistenData?.(); } catch { /* noop */ }
  try { t.unlistenExit?.(); } catch { /* noop */ }
  if (t.sessionId && invoke) {
    try { await invoke("pty_kill", { sessionId: t.sessionId }); }
    catch { /* best-effort */ }
  }
  try { t.term.dispose(); } catch { /* noop */ }
}

async function restartTerminalView() {
  await closeTerminalView();
  // If Restart interrupted an in-flight PTY open, let that operation settle
  // before creating the replacement. Otherwise openTerminalView would return
  // the old promise and leave no mounted terminal after it finishes.
  const opening = state.terminalOpening;
  if (opening) {
    try { await opening; } catch { /* the replacement below may still open */ }
  }
  await openTerminalView();
}

function updateComposer() {
  const hasInput = Boolean(el.prompt.value.trim() || state.attachments.length);
  el["send-turn"].disabled = !state.online || !state.sessionId || !hasInput || state.busy
    || state.attachmentsPending > 0 || state.contextPending
    || state.routingPending;
  el["attach-files"].disabled = state.busy
    || state.attachmentsPending > 0;
}

function readAttachment(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    state.attachmentReader = reader;
    reader.addEventListener("load", () => resolve(String(reader.result || "")));
    reader.addEventListener("error", () => reject(new Error(`Could not read ${file.name}`)));
    reader.addEventListener("abort", () => reject(new Error("Attachment read cancelled")));
    reader.addEventListener("loadend", () => {
      if (state.attachmentReader === reader) state.attachmentReader = null;
    });
    reader.readAsDataURL(file);
  });
}

async function addAttachments(files, generation) {
  for (const file of Array.from(files)) {
    if (generation !== state.attachmentGeneration) return;
    if (state.attachments.length >= MAX_ATTACHMENTS) {
      toast(`Attach up to ${MAX_ATTACHMENTS} files`, "error");
      break;
    }
    if (!ATTACHMENT_TYPES.has(file.type)) {
      toast(`${file.name} is not a supported image or PDF`, "error");
      continue;
    }
    const nextBytes = state.attachments.reduce(
      (total, attachment) => total + attachment.size,
      file.size
    );
    if (file.size === 0 || nextBytes > MAX_ATTACHMENT_BYTES) {
      toast("Attachments must total 10 MB or less", "error");
      continue;
    }
    try {
      const data = await readAttachment(file);
      if (generation !== state.attachmentGeneration) return;
      state.attachments.push({
        name: file.name,
        type: file.type,
        size: file.size,
        data,
      });
    } catch (error) {
      if (generation === state.attachmentGeneration) {
        toast(error.message, "error");
      }
    }
  }
}

function queueAttachments(files) {
  const selected = Array.from(files);
  if (!selected.length) return;
  const generation = state.attachmentGeneration;
  state.attachmentsPending += 1;
  updateComposer();
  state.attachmentQueue = state.attachmentQueue
    .then(() => addAttachments(selected, generation))
    .catch((error) => toast(error.message, "error"))
    .finally(() => {
      state.attachmentsPending = Math.max(0, state.attachmentsPending - 1);
      renderAttachments();
      el["attachment-input"].value = "";
    });
}

function renderAttachments() {
  el["attachment-list"].replaceChildren();
  el["attachment-list"].classList.toggle("is-hidden", !state.attachments.length);
  state.attachments.forEach((attachment, index) => {
    const chip = node("div", "attachment-chip");
    const kind = attachment.type === "application/pdf" ? "PDF" : "Image";
    const remove = node("button", "", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${attachment.name}`);
    remove.addEventListener("click", () => {
      state.attachments.splice(index, 1);
      renderAttachments();
      updateComposer();
    });
    chip.append(
      node("span", "attachment-kind", kind),
      node("span", "attachment-name", attachment.name),
      remove
    );
    el["attachment-list"].append(chip);
  });
  updateComposer();
}

function renderContextItems() {
  el["context-items"].replaceChildren();
  el["context-items"].classList.toggle(
    "is-hidden",
    !state.contextItems.length
  );
  state.contextItems.forEach((context, index) => {
    const chip = node("div", "attachment-chip context-item");
    chip.title = `${context.label}\n${context.fingerprint}`;
    const remove = node("button", "", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${context.label}`);
    remove.addEventListener("click", () => {
      state.contextItems.splice(index, 1);
      state.contextGeneration += 1;
      renderContextItems();
    });
    chip.append(
      node(
        "span",
        "attachment-kind",
        context.kind === "folder"
          ? "Folder"
          : context.kind === "git" ? "Git" : "File"
      ),
      node("span", "attachment-name", context.label),
      node(
        "span",
        "context-fingerprint",
        context.fingerprint.slice(0, 7)
      ),
      remove
    );
    el["context-items"].append(chip);
  });
  updateComposer();
}

function resizePrompt() {
  el.prompt.style.height = "auto";
  el.prompt.style.height = `${Math.min(el.prompt.scrollHeight, 180)}px`;
  updateComposer();
}

async function loadDiff(showPanel = true) {
  const sessionId = state.sessionId;
  if (!sessionId) return;
  try {
    const result = await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/git/diff?against_base=true`
    );
    if (state.sessionId !== sessionId) return;
    state.diff = typeof result.diff === "string" ? result.diff : "";
  } catch (error) {
    if (state.sessionId !== sessionId) return;
    if (!error.message.includes("not found")) {
      toast(error.message, "error");
    }
    state.diff = "";
  }
  renderDiff();
  await Promise.all([
    loadCheckpoints(sessionId),
    loadGitGraph(sessionId),
    loadGitLog(sessionId),
    loadGitStatus(sessionId),
    loadPullRequest(),
  ]);
  if (showPanel && state.sessionId === sessionId) openReview();
}

async function loadCheckpoints(sessionId = state.sessionId) {
  if (!sessionId) {
    state.checkpoints = [];
    renderCheckpoints();
    return;
  }
  try {
    const checkpoints = await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/checkpoints`
    );
    if (state.sessionId !== sessionId) return;
    state.checkpoints = checkpoints;
  } catch (error) {
    if (state.sessionId !== sessionId) return;
    if (!error.message.includes("not found")) {
      toast(error.message, "error");
    }
    state.checkpoints = [];
  }
  renderCheckpoints();
}

function renderCheckpoints() {
  const selected = el["checkpoint-select"].value;
  el["checkpoint-select"].replaceChildren();
  if (!state.checkpoints.length) {
    const option = node("option", "", "No checkpoints");
    option.value = "";
    el["checkpoint-select"].append(option);
  } else {
    for (const checkpoint of state.checkpoints) {
      const option = node(
        "option",
        "",
        `Turn ending at message ${checkpoint.after_message_count}`
        + (checkpoint.created_at
          ? ` · ${formatAge(checkpoint.created_at)}`
          : "")
      );
      option.value = checkpoint.checkpoint_id;
      el["checkpoint-select"].append(option);
    }
    if (state.checkpoints.some(
      (checkpoint) => checkpoint.checkpoint_id === selected
    )) {
      el["checkpoint-select"].value = selected;
    }
  }
  el["checkpoint-select"].disabled = !state.checkpoints.length;
  el["restore-checkpoint"].disabled = (
    state.busy || !el["checkpoint-select"].value
  );
}

async function restoreCheckpoint() {
  const checkpointId = el["checkpoint-select"].value;
  const scope = el["restore-scope"].value;
  if (!state.sessionId || !checkpointId || state.busy) return;
  const description = {
    both: "code and conversation",
    code: "code",
    conversation: "conversation",
  }[scope];
  if (!window.confirm(
    `Restore ${description} to the selected turn checkpoint?`
  )) return;
  el["restore-checkpoint"].disabled = true;
  try {
    await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}`
      + `/checkpoints/${encodeURIComponent(checkpointId)}/restore`,
      {
        method: "POST",
        body: JSON.stringify({ scope: scope }),
      }
    );
    state.messages = await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/messages`
    );
    renderConversation();
    await Promise.all([loadSessions(), loadDiff(false)]);
    toast(`Restored ${description}`);
  } catch (error) {
    toast(error.message, "error");
    renderCheckpoints();
  }
}

function renderDiff() {
  const lines = state.diff ? state.diff.split("\n") : [];
  el["diff-view"].replaceChildren();
  // Group lines into per-file blocks with a checkbox for selective apply.
  const blocks = [];
  let current = null;
  for (const line of lines) {
    if (line.startsWith("diff --git ")) {
      const match = line.match(/^diff --git a\/(.+?) b\/(.+)$/);
      const path = match ? match[2] : "";
      current = { path, lines: [line] };
      blocks.push(current);
    } else if (current) {
      current.lines.push(line);
    } else {
      // Header lines before any file (e.g. empty diff).
      if (!blocks.length) {
        current = { path: "", lines: [] };
        blocks.push(current);
      }
      blocks[0].lines.push(line);
    }
  }
  const fileBlocks = blocks.filter((b) => b.path);
  const files = fileBlocks.length;
  el["change-count"].textContent = String(files);
  el["change-count"].classList.toggle("is-hidden", files === 0);
  el["review-button"].disabled = !state.sessionId;
  el["review-summary"].textContent = files
    ? `${files} changed ${files === 1 ? "file" : "files"}`
    : "No un-applied changes";

  if (!lines.length || !fileBlocks.length) {
    el["diff-view"].append(
      node("span", "diff-line", "No changes to review.")
    );
    updateApplyButton();
    return;
  }

  for (const block of fileBlocks) {
    const wrap = node("div", "diff-file-block");
    const header = node("div", "diff-file-header");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "diff-file-select";
    checkbox.dataset.path = block.path;
    checkbox.checked = state.selectedFiles.has(block.path);
    checkbox.setAttribute(
      "aria-label",
      `Select ${block.path} for apply`
    );
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        state.selectedFiles.add(block.path);
      } else {
        state.selectedFiles.delete(block.path);
      }
      updateApplyButton();
    });
    header.append(
      checkbox,
      node("span", "diff-file-path", block.path)
    );
    wrap.append(header);
    // Split the file's lines into per-hunk groups at ``@@`` headers so each
    // hunk gets its own checkbox (Phase 43 hunk-level review). Lines before
    // the first ``@@`` (index/---/+++) attach to the file header.
    let hunkIndex = -1;
    let hunkWrap = null;
    for (const line of block.lines) {
      if (line.startsWith("@@")) {
        hunkIndex += 1;
        hunkWrap = node("div", "diff-hunk-block");
        const hunkRow = node("div", "diff-hunk-header");
        const hunkCheckbox = document.createElement("input");
        hunkCheckbox.type = "checkbox";
        hunkCheckbox.className = "diff-hunk-select";
        const hunkKey = `${block.path}::${hunkIndex}`;
        hunkCheckbox.dataset.path = block.path;
        hunkCheckbox.dataset.hunkIndex = String(hunkIndex);
        hunkCheckbox.checked = state.selectedHunks.has(hunkKey);
        hunkCheckbox.setAttribute(
          "aria-label",
          `Select hunk ${hunkIndex + 1} of ${block.path} for apply`
        );
        hunkCheckbox.addEventListener("change", () => {
          if (hunkCheckbox.checked) {
            state.selectedHunks.add(hunkKey);
          } else {
            state.selectedHunks.delete(hunkKey);
          }
          updateApplyButton();
        });
        hunkRow.append(
          hunkCheckbox,
          node("span", "diff-line header", line)
        );
        hunkWrap.append(hunkRow);
        wrap.append(hunkWrap);
        continue;
      }
      let kind = "";
      if (line.startsWith("diff --git ") || line.startsWith("@@"))
        kind = "header";
      else if (line.startsWith("+") && !line.startsWith("+++")) kind = "add";
      else if (line.startsWith("-") && !line.startsWith("---")) kind = "delete";
      const lineSpan = node("span", `diff-line ${kind}`.trim(), line);
      if (hunkWrap) {
        hunkWrap.append(lineSpan);
      } else {
        wrap.append(lineSpan);
      }
    }
    el["diff-view"].append(wrap);
  }
  updateApplyButton();
}

function updateApplyButton() {
  const selectedHunks = state.selectedHunks.size;
  const selectedFiles = state.selectedFiles.size;
  if (selectedHunks > 0) {
    el["apply-changes"].textContent = `Apply selected (${selectedHunks} hunks)`;
    el["apply-changes"].disabled = !state.sessionId;
  } else if (selectedFiles > 0) {
    el["apply-changes"].textContent = `Apply selected (${selectedFiles})`;
    el["apply-changes"].disabled = !state.sessionId;
  } else {
    el["apply-changes"].textContent = "Apply to workspace";
    el["apply-changes"].disabled = !state.diff;
  }
}

function selectUtilityView(view) {
  const subagents = view === "subagents";
  state.utilityView = subagents ? "subagents" : "environment";
  el["utility-environment"].classList.toggle("is-hidden", subagents);
  el["utility-subagents"].classList.toggle("is-hidden", !subagents);
  el["utility-environment-tab"].setAttribute("aria-selected", String(!subagents));
  el["utility-subagents-tab"].setAttribute("aria-selected", String(subagents));
  el["utility-environment-tab"].tabIndex = subagents ? -1 : 0;
  el["utility-subagents-tab"].tabIndex = subagents ? 0 : -1;
  el["utility-eyebrow"].textContent = subagents ? "Delegation" : "Environment";
  el["utility-title"].textContent = subagents ? "Subagents" : "Local workspace";
}

function moveUtilityTab(event) {
  const tabs = [el["utility-environment-tab"], el["utility-subagents-tab"]];
  const current = tabs.indexOf(event.currentTarget);
  const next = event.key === "Home" ? 0
    : event.key === "End" ? tabs.length - 1
    : event.key === "ArrowLeft" ? (current + tabs.length - 1) % tabs.length
    : event.key === "ArrowRight" ? (current + 1) % tabs.length
    : -1;
  if (next < 0) return;
  event.preventDefault();
  const view = next === 0 ? "environment" : "subagents";
  selectUtilityView(view);
  tabs[next].focus();
}

function openReview(view = state.utilityView) {
  selectUtilityView(view);
  el["environment-details"].open = true;
  el.app.classList.add("review-open");
  el["review-panel"].setAttribute("aria-hidden", "false");
}

function closeReview() {
  el.app.classList.remove("review-open");
  el["review-panel"].setAttribute("aria-hidden", "true");
  el["subagents-button"].setAttribute("aria-expanded", "false");
}

function openSubagents() {
  openReview("subagents");
  el["subagents-button"].setAttribute("aria-expanded", "true");
  el["worker-panel"].scrollIntoView({ block: "nearest" });
}

async function applyChanges() {
  if (!state.sessionId || !state.diff) return;
  el["apply-changes"].disabled = true;
  let body;
  let summary;
  if (state.selectedHunks.size) {
    const hunks = Array.from(state.selectedHunks).map((key) => {
      const [path, index] = key.split("::");
      return { path, hunk_index: Number(index) };
    });
    body = JSON.stringify({ hunks });
    summary = `Applied ${hunks.length} selected hunk(s)`;
  } else if (state.selectedFiles.size) {
    body = JSON.stringify({ paths: Array.from(state.selectedFiles) });
    summary = `Applied ${state.selectedFiles.size} selected file(s)`;
  } else {
    body = undefined;
    summary = "Changes applied to the source workspace";
  }
  try {
    await api(`/v1/sessions/${encodeURIComponent(state.sessionId)}/git/apply`, {
      method: "POST",
      body,
    });
    toast(summary);
    state.selectedFiles.clear();
    state.selectedHunks.clear();
    await loadDiff(false);
  } catch (error) {
    toast(error.message, "error");
    updateApplyButton();
  }
}

async function loadGitStatus(sessionId = state.sessionId) {
  if (!sessionId) return;
  try {
    const status = await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/git/status`
    );
    if (state.sessionId !== sessionId) return;
    state.gitStatus = status;
    renderGitStatus();
  } catch (error) {
    if (state.sessionId !== sessionId) return;
    state.gitStatus = null;
    renderGitStatus();
  }
}

function renderGitStatus() {
  const status = state.gitStatus;
  el["git-branch"].textContent = status?.branch || "—";
  const clean = Boolean(status?.clean);
  el["git-stage"].disabled = (
    !state.sessionId || clean || state.busy
  );
  el["git-commit"].disabled = (
    !state.sessionId || !el["commit-message"].value.trim() || state.busy
  );
  el["git-push"].disabled = !state.sessionId || state.busy;
}

async function loadGitGraph(sessionId = state.sessionId) {
  if (!sessionId) {
    state.gitGraph = "";
    renderGitGraph();
    return;
  }
  try {
    const result = await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/git/graph?limit=50`
    );
    if (state.sessionId !== sessionId) return;
    state.gitGraph = typeof result.graph === "string" ? result.graph : "";
  } catch (error) {
    if (state.sessionId !== sessionId) return;
    state.gitGraph = "";
  }
  renderGitGraph();
}

function renderGitGraph() {
  el["git-graph"].textContent = state.gitGraph || "No commits yet";
}

async function loadGitLog(sessionId = state.sessionId) {
  if (!sessionId) {
    state.gitLog = [];
    renderGitLog();
    return;
  }
  try {
    const result = await api(
      `/v1/sessions/${encodeURIComponent(sessionId)}/git/log?limit=50`
    );
    if (state.sessionId !== sessionId) return;
    state.gitLog = Array.isArray(result.commits) ? result.commits : [];
  } catch (error) {
    if (state.sessionId !== sessionId) return;
    state.gitLog = [];
  }
  renderGitLog();
}

function renderGitLog() {
  el["git-log"].replaceChildren();
  if (!state.gitLog.length) {
    el["git-log"].append(node("li", "git-log-empty", "No commits on this branch yet"));
    return;
  }
  for (const commit of state.gitLog) {
    const row = node("li", "commit-row");
    row.tabIndex = 0;
    row.setAttribute("role", "button");
    row.setAttribute(
      "aria-label",
      `Review commit ${commit.sha?.slice(0, 8) || ""} ${commit.subject || ""}`
    );
    const short = (commit.sha || "").slice(0, 8);
    row.append(
      node("span", "commit-sha", short),
      node("span", "commit-subject", commit.subject || ""),
      node("span", "commit-author", commit.author || "")
    );
    const sha = commit.sha;
    row.addEventListener("click", () => {
      loadCommitDiff(sha).catch((error) => toast(error.message, "error"));
    });
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        loadCommitDiff(sha).catch((error) => toast(error.message, "error"));
      }
    });
    el["git-log"].append(row);
  }
}

async function loadCommitDiff(sha) {
  if (!state.sessionId || !sha) return;
  try {
    const result = await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}`
        + `/git/diff?commit=${encodeURIComponent(sha)}`
    );
    state.diff = typeof result.diff === "string" ? result.diff : "";
    renderDiff();
    openReview();
  } catch (error) {
    toast(error.message, "error");
  }
}

async function stageAll() {
  if (!state.sessionId || state.busy) return;
  el["git-stage"].disabled = true;
  try {
    await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/git/stage`,
      { method: "POST", body: JSON.stringify({ path: "." }) }
    );
    toast("Staged all changes");
    await loadGitStatus(state.sessionId);
  } catch (error) {
    toast(error.message, "error");
    renderGitStatus();
  }
}

async function commitChanges() {
  const message = el["commit-message"].value.trim();
  if (!state.sessionId || !message || state.busy) return;
  el["git-commit"].disabled = true;
  try {
    await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/git/commit`,
      { method: "POST", body: JSON.stringify({ message }) }
    );
    el["commit-message"].value = "";
    toast("Committed to session branch");
    await Promise.all([
      loadGitLog(state.sessionId),
      loadGitGraph(state.sessionId),
      loadDiff(false),
    ]);
  } catch (error) {
    toast(error.message, "error");
    renderGitStatus();
  }
}

async function pushBranch() {
  if (!state.sessionId || state.busy) return;
  const branch = state.gitStatus?.branch || "session branch";
  if (!window.confirm(`Push ${branch} to origin?`)) return;
  el["git-push"].disabled = true;
  try {
    await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/git/push`,
      {
        method: "POST",
        body: JSON.stringify({ remote: "origin", set_upstream: false }),
      }
    );
    toast(`Pushed ${branch} to origin`);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    renderGitStatus();
  }
}

async function loadPullRequest() {
  if (!state.sessionId) {
    el["github-pr-status"].textContent = "";
    el["github-create-pr"].disabled = true;
    return;
  }
  try {
    const pr = await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/github/pr`
    );
    if (pr && pr.open) {
      const label = pr.draft ? "draft PR" : "PR";
      el["github-pr-status"].replaceChildren();
      const link = document.createElement("a");
      link.href = pr.url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = `${label} #${pr.number}: ${pr.title}`;
      el["github-pr-status"].append(link);
      el["github-create-pr"].disabled = true;
      await loadChecks();
    } else {
      el["github-pr-status"].textContent = "No open PR";
      el["github-create-pr"].disabled = !state.sessionId;
    }
  } catch (error) {
    el["github-pr-status"].textContent = "";
    el["github-create-pr"].disabled = true;
  }
}

async function createPullRequest() {
  if (!state.sessionId || state.busy) return;
  const title = el["commit-message"].value.trim()
    || window.prompt("PR title:");
  if (!title) return;
  el["github-create-pr"].disabled = true;
  try {
    const pr = await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/github/pr`,
      {
        method: "POST",
        body: JSON.stringify({ title }),
      }
    );
    toast(`Created PR #${pr.number}`);
    await loadPullRequest();
  } catch (error) {
    toast(error.message, "error");
    el["github-create-pr"].disabled = false;
  }
}

async function loadChecks() {
  if (!state.sessionId) return;
  try {
    const result = await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/github/checks`
    );
    const total = result.total || 0;
    if (total && Array.isArray(result.runs)) {
      const passed = result.runs.filter((r) => r.conclusion === "success").length;
      el["github-pr-status"].append(
        node(
          "span",
          "github-checks-summary",
          ` · CI: ${passed}/${total} passing`
        )
      );
    }
  } catch (_error) {
    // Checks are optional; ignore failures silently.
  }
}

function showPreviewPanel() {
  el["preview-panel"].classList.remove("is-hidden");
}

function hidePreviewPanel() {
  el["preview-panel"].classList.add("is-hidden");
}

function renderDevserverChips() {
  el["devserver-chips"].replaceChildren();
  if (!state.devserverUrls.length) return;
  for (const entry of state.devserverUrls) {
    const chip = node("button", "devserver-chip", entry.url);
    chip.type = "button";
    chip.addEventListener("click", () => {
      el["preview-url"].value = entry.url;
      openPreview();
    });
    el["devserver-chips"].append(chip);
  }
}

function openPreview() {
  const url = el["preview-url"].value.trim();
  if (!url) return;
  state.previewUrl = url;
  el["preview-frame"].src = url;
  showPreviewPanel();
}

async function loadPreviewEvidence() {
  if (!state.sessionId) return;
  try {
    const items = await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/preview/evidence`
    );
    renderPreviewEvidence(items);
  } catch (_error) {
    el["preview-evidence"].replaceChildren();
  }
}

function renderPreviewEvidence(items) {
  el["preview-evidence"].replaceChildren();
  if (!items || !items.length) return;
  for (const item of items) {
    const row = node("div", `preview-evidence-row preview-evidence-${item.kind}`);
    const content = typeof item.content === "string"
      ? item.content
      : JSON.stringify(item.content);
    row.append(
      node("span", "preview-evidence-kind", item.kind),
      node("span", "preview-evidence-content", content)
    );
    el["preview-evidence"].append(row);
  }
}

async function attachConsoleEvidence() {
  if (!state.sessionId) return;
  const text = window.prompt("Paste console output to attach as evidence:");
  if (!text || !text.trim()) return;
  try {
    await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/preview/evidence`,
      {
        method: "POST",
        body: JSON.stringify({ kind: "console", content: text }),
      }
    );
    toast("Console evidence attached");
    await loadPreviewEvidence();
  } catch (error) {
    toast(error.message, "error");
  }
}

async function clearPreviewEvidence() {
  if (!state.sessionId) return;
  try {
    await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/preview/evidence`,
      { method: "DELETE" }
    );
    renderPreviewEvidence([]);
    toast("Preview evidence cleared");
  } catch (error) {
    toast(error.message, "error");
  }
}

function toggleAnnotation() {
  state.annotating = !state.annotating;
  el["annotation-overlay"].classList.toggle("is-hidden", !state.annotating);
  el["preview-annotate"].textContent = state.annotating
    ? "Stop annotating"
    : "Annotate";
  if (!state.annotating) {
    el["annotation-overlay"].replaceChildren();
  }
}

function startAnnotationOverlay() {
  const overlay = el["annotation-overlay"];
  overlay.replaceChildren();
  let drawing = false;
  let startX = 0, startY = 0;
  let rect = null;

  overlay.addEventListener("pointerdown", (event) => {
    if (!state.annotating) return;
    drawing = true;
    startX = event.offsetX;
    startY = event.offsetY;
    rect = node("div", "annotation-rect");
    rect.style.left = `${startX}px`;
    rect.style.top = `${startY}px`;
    overlay.append(rect);
  });

  overlay.addEventListener("pointermove", (event) => {
    if (!drawing || !rect) return;
    const w = Math.abs(event.offsetX - startX);
    const h = Math.abs(event.offsetY - startY);
    rect.style.left = `${Math.min(startX, event.offsetX)}px`;
    rect.style.top = `${Math.min(startY, event.offsetY)}px`;
    rect.style.width = `${w}px`;
    rect.style.height = `${h}px`;
  });

  overlay.addEventListener("pointerup", async (event) => {
    if (!drawing || !rect) return;
    drawing = false;
    const x = parseInt(rect.style.left, 10) || 0;
    const y = parseInt(rect.style.top, 10) || 0;
    const w = parseInt(rect.style.width, 10) || 0;
    const h = parseInt(rect.style.height, 10) || 0;
    if (w < 5 || h < 5) {
      rect.remove();
      return;
    }
    const note = window.prompt("Annotation note:");
    if (!note) {
      rect.remove();
      return;
    }
    rect.append(node("span", "annotation-rect-note", note));
    if (state.sessionId) {
      try {
        await api(
          `/v1/sessions/${encodeURIComponent(state.sessionId)}/preview/evidence`,
          {
            method: "POST",
            body: JSON.stringify({
              kind: "annotation",
              content: { x, y, w, h, note },
            }),
          }
        );
        toast("Annotation saved");
      } catch (error) {
        toast(error.message, "error");
      }
    }
  });
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme;
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("codinal-theme", next);
}

async function toggleWindowZoom() {
  const windowApi = window.__TAURI__?.window?.getCurrentWindow?.();
  if (!windowApi?.toggleMaximize) return;
  try {
    await windowApi.toggleMaximize();
  } catch {
    // Browser previews intentionally have no native window API.
  }
}

function zoomFromTitlebar(event) {
  if (event.target.closest("button, input, select, textarea, a")) return;
  toggleWindowZoom();
}

async function openSettings() {
  if (el["settings-dialog"].open) {
    el["settings-search"].focus();
    return;
  }
  el["settings-dialog"].showModal();
  el["settings-search"].value = "";
  filterSettings();
  activateSettingsNav("settings-general");
  try {
    toggleMcpConnectorFields();
    await loadSettings();
    await Promise.all([
      renderProviders(),
      loadMcpServers(),
      loadArtifacts(),
      loadDiagnostics(),
      loadAuditLog(),
    ]);
  } catch (error) {
    toast(error.message, "error");
  }
}

function closeSettings() {
  el["settings-dialog"].close();
}

function activateSettingsNav(target) {
  const section = document.getElementById(target);
  if (!section) return;
  for (const link of el["settings-dialog"].querySelectorAll(".settings-nav a")) {
    const active = link.getAttribute("href") === `#${target}`;
    link.classList.toggle("is-current", active);
    if (active) {
      el["settings-dialog-title"].textContent = link.querySelector("span").textContent.trim();
    }
  }
  if (target === "settings-general") {
    el["settings-dialog"].querySelector(".settings-content").scrollTo({ top: 0 });
  } else {
    section.scrollIntoView({ block: "start" });
  }
}

function filterSettings() {
  const query = el["settings-search"].value.trim().toLocaleLowerCase();
  for (const section of el["settings-dialog"].querySelectorAll(".settings-content section")) {
    section.classList.toggle(
      "is-hidden",
      Boolean(query) && !section.textContent.toLocaleLowerCase().includes(query)
    );
  }
}

async function checkForUpdate() {
  if (!invoke) {
    el["update-status"].textContent = "Updates are available in the desktop app.";
    return;
  }
  el["check-update"].disabled = true;
  el["install-update"].classList.add("is-hidden");
  state.updateVersion = null;
  el["update-status"].textContent = "Checking for updates…";
  try {
    const update = await invoke("check_for_update");
    if (update.available) {
      state.updateVersion = update.version;
      el["update-status"].textContent =
        `Codinal ${update.version} is available. ${update.notes || ""}`.trim();
      el["install-update"].classList.remove("is-hidden");
    } else {
      el["update-status"].textContent =
        `Codinal ${update.currentVersion} is up to date.`;
    }
  } catch (error) {
    el["update-status"].textContent = "Could not check for updates.";
    toast(String(error), "error");
  } finally {
    el["check-update"].disabled = false;
  }
}

async function installUpdate() {
  if (!invoke || !state.updateVersion) return;
  el["check-update"].disabled = true;
  el["install-update"].disabled = true;
  el["update-status"].textContent = "Downloading and verifying update…";
  try {
    await invoke("install_update", {
      expectedVersion: state.updateVersion,
    });
  } catch (error) {
    el["check-update"].disabled = false;
    el["install-update"].disabled = false;
    el["update-status"].textContent = "Update installation failed.";
    toast(String(error), "error");
  }
}

async function renderProviders() {
  el["provider-list"].replaceChildren();
  if (!invoke) {
    el["provider-list"].append(
      node("p", "settings-copy", "Provider key management is available in the desktop app.")
    );
    return;
  }
  let providers;
  try {
    providers = await invoke("list_provider_secret_status");
  } catch (error) {
    el["provider-list"].append(
      node(
        "p",
        "settings-copy provider-error",
        `Unable to load provider credentials: ${String(error?.message || error)}`
      )
    );
    return;
  }
  for (const provider of providers) {
    const row = node("div", "provider-row");
    const label = node("label", "", provider.provider);
    const status = node(
      "span",
      `provider-state${provider.configured ? " is-configured" : ""}`,
      provider.configured ? "Configured" : "Not configured"
    );
    label.append(node("br"), status);
    const input = node("input");
    input.type = "password";
    input.autocomplete = "off";
    input.placeholder = provider.configured ? "Replace key…" : "API key";
    input.setAttribute("aria-label", `${provider.provider} API key`);
    // Self-hosted OpenAI-compatible providers (OmniRoute) also take a base_url.
    const wantsBaseUrl = provider.provider === "omniroute";
    let baseUrlInput = null;
    if (wantsBaseUrl) {
      baseUrlInput = node("input");
      baseUrlInput.type = "text";
      baseUrlInput.autocomplete = "off";
      baseUrlInput.placeholder = "http://localhost:20128/v1";
      baseUrlInput.setAttribute("aria-label", `${provider.provider} base URL`);
      baseUrlInput.classList.add("provider-base-url");
    }
    const save = node("button", "", provider.configured ? "Update" : "Save");
    save.type = "button";
    save.setAttribute(
      "aria-label",
      `${provider.configured ? "Update" : "Save"} ${provider.provider} key`
    );
    save.addEventListener("click", async () => {
      if (!input.value) return;
      save.disabled = true;
      try {
        const payload = {
          provider: provider.provider,
          apiKey: input.value,
        };
        if (wantsBaseUrl) {
          payload.baseUrl = baseUrlInput.value || null;
        }
        await invoke("set_provider_secret", payload);
        input.value = "";
        if (baseUrlInput) baseUrlInput.value = "";
        await renderProviders();
        toast(`${provider.provider} credential saved`);
      } catch (error) {
        toast(String(error), "error");
        save.disabled = false;
      }
    });
    const actions = node("div", "provider-actions");
    actions.append(save);
    if (provider.configured) {
      const remove = node("button", "remove-provider", "Remove");
      remove.type = "button";
      remove.addEventListener("click", async () => {
        if (!window.confirm(`Remove the ${provider.provider} credential?`)) return;
        remove.disabled = true;
        try {
          await invoke("delete_provider_secret", {
            provider: provider.provider,
          });
          await renderProviders();
          toast(`${provider.provider} credential removed`);
        } catch (error) {
          toast(String(error), "error");
          remove.disabled = false;
        }
      });
      actions.append(remove);
    }
    row.append(label, input);
    if (baseUrlInput) row.append(baseUrlInput);
    row.append(actions);
    el["provider-list"].append(row);
  }
  await renderCustomProviders();
}

async function renderCustomProviders() {
  const host = el["provider-list"];
  if (!host) return;
  const existing = host.querySelector("[data-custom-providers]");
  if (existing) existing.remove();
  const section = node("div", "provider-section");
  section.setAttribute("data-custom-providers", "");
  section.append(
    node("h4", "provider-section-title", "Custom OpenAI-compatible providers")
  );
  section.append(
    node(
      "p",
      "settings-copy",
      "Add any OpenAI-compatible gateway (OmniRoute, OpenRouter, OneAPI, local vLLM). Use as custom:<slug>:<model> in the model picker."
    )
  );
  let providers = [];
  if (invoke) {
    try {
      providers = await invoke("list_custom_providers");
    } catch (error) {
      section.append(
        node("p", "provider-error", `Unable to load custom providers: ${String(error?.message || error)}`)
      );
    }
  }
  for (const provider of providers) {
    const row = node("div", "provider-row");
    const label = node("label", "", `custom:${provider.slug}`);
    const status = node(
      "span",
      "provider-state" + (provider.failover_eligible ? " is-configured" : ""),
      provider.failover_eligible ? "Failover-eligible" : "Manual only"
    );
    label.append(node("br"), status);
    const url = node("span", "settings-copy", provider.base_url);
    const remove = node("button", "remove-provider", "Remove");
    remove.type = "button";
    remove.addEventListener("click", async () => {
      if (!window.confirm(`Remove custom:${provider.slug}?`)) return;
      remove.disabled = true;
      try {
        await invoke("delete_custom_provider", { slug: provider.slug });
        await renderProviders();
        toast(`custom:${provider.slug} removed`);
      } catch (error) {
        toast(String(error), "error");
        remove.disabled = false;
      }
    });
    row.append(label, url, remove);
    section.append(row);
  }
  const addRow = node("div", "provider-row custom-add");
  const slugInput = node("input");
  slugInput.type = "text";
  slugInput.placeholder = "slug (e.g. my-openrouter)";
  slugInput.setAttribute("aria-label", "Custom provider slug");
  const urlInput = node("input");
  urlInput.type = "text";
  urlInput.placeholder = "https://api.example.com/v1";
  urlInput.setAttribute("aria-label", "Custom provider base URL");
  const keyInput = node("input");
  keyInput.type = "password";
  keyInput.autocomplete = "off";
  keyInput.placeholder = "API key";
  keyInput.setAttribute("aria-label", "Custom provider API key");
  const failoverLabel = node("label", "custom-failover-toggle");
  const failoverCheck = node("input");
  failoverCheck.type = "checkbox";
  failoverLabel.append(failoverCheck, document.createTextNode(" Failover-eligible"));
  const addBtn = node("button", "secondary-button", "Add");
  addBtn.type = "button";
  addBtn.addEventListener("click", async () => {
    const slug = slugInput.value.trim();
    const baseUrl = urlInput.value.trim();
    const apiKey = keyInput.value;
    if (!slug || !baseUrl || !apiKey) {
      toast("slug, base URL, and API key are all required", "error");
      return;
    }
    addBtn.disabled = true;
    try {
      await invoke("set_custom_provider", {
        slug,
        baseUrl,
        apiKey,
        failoverEligible: failoverCheck.checked,
      });
      slugInput.value = "";
      urlInput.value = "";
      keyInput.value = "";
      failoverCheck.checked = false;
      await renderProviders();
      toast(`custom:${slug} saved`);
    } catch (error) {
      toast(String(error), "error");
      addBtn.disabled = false;
    }
  });
  addRow.append(slugInput, urlInput, keyInput, failoverLabel, addBtn);
  section.append(addRow);
  host.append(section);
}

function wireEvents() {
  el["new-task"].addEventListener("click", newTask);
  el["add-context-root"].addEventListener("click", () => {
    addContextRoot().catch((error) => toast(error.message, "error"));
  });
  el["refresh-sessions"].addEventListener("click", loadSessions);
  el["new-worker"].addEventListener("click", () => {
    el["worker-dialog"].showModal();
    el["worker-task"].focus();
  });
  el["create-worker"].addEventListener("click", () => {
    createWorker().catch((error) => toast(error.message, "error"));
  });
  el["create-plan-build"].addEventListener("click", () => {
    createPlanBuild().catch((error) => toast(error.message, "error"));
  });
  el["new-goal"].addEventListener("click", openGoalDialog);
  el["create-goal"].addEventListener("click", () => {
    createGoal().catch((error) => toast(error.message, "error"));
  });
  el["save-goal-evidence"].addEventListener("click", () => {
    saveGoalEvidence().catch((error) => toast(error.message, "error"));
  });
  el["session-search"].addEventListener("input", scheduleSessionSearch);
  el["project-search"].addEventListener("input", scheduleProjectSearch);
  el["project-search-mode"].addEventListener(
    "change",
    scheduleProjectSearch
  );
  el["project-index-build"].addEventListener("click", () => {
    rebuildProjectIndex().catch((error) => toast(error.message, "error"));
  });
  el["project-index-clear"].addEventListener("click", () => {
    clearProjectIndex().catch((error) => toast(error.message, "error"));
  });
  el["thread-search"].addEventListener("input", () => findThreadMatches());
  el["thread-search-previous"].addEventListener(
    "click",
    () => moveThreadSearch(-1)
  );
  el["thread-search-next"].addEventListener(
    "click",
    () => moveThreadSearch(1)
  );
  el["export-thread"].addEventListener("click", () => {
    exportThread().catch((error) => toast(error.message, "error"));
  });
  el["return-to-parent"].addEventListener("click", () => {
    returnToParentSession().catch((error) => toast(error.message, "error"));
  });
  el["theme-toggle"].addEventListener("click", toggleTheme);
  el["settings-toggle-theme"].addEventListener("click", toggleTheme);
  el["settings-back"].addEventListener("click", closeSettings);
  el["close-settings"].addEventListener("click", closeSettings);
  el["settings-search"].addEventListener("input", filterSettings);
  el["settings-dialog"].querySelector("form").addEventListener("submit", (event) => {
    event.preventDefault();
  });
  for (const link of el["settings-dialog"].querySelectorAll(".settings-nav a")) {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      activateSettingsNav(link.getAttribute("href").slice(1));
    });
  }
  el["open-settings"].addEventListener("click", openSettings);
  el["save-stirling-url"].addEventListener("click", () => {
    saveStirlingUrl().catch((error) => toast(error.message, "error"));
  });
  el["test-stirling-url"].addEventListener("click", () => {
    testStirlingUrl().catch((error) => toast(error.message, "error"));
  });
  el["refresh-ollama-models"].addEventListener("click", () => {
    refreshOllamaModels().catch((error) => toast(error.message, "error"));
  });
  el["mcp-transport"].addEventListener("change", toggleMcpConnectorFields);
  el["connect-mcp-server"].addEventListener("click", () => {
    connectMcpServer().catch((error) => toast(error.message, "error"));
  });
  el["check-update"].addEventListener("click", checkForUpdate);
  el["install-update"].addEventListener("click", installUpdate);
  el["copy-support-bundle"].addEventListener("click", () => {
    copySupportBundle().catch((error) => toast(error.message, "error"));
  });
  el["rename-session"].addEventListener("click", async () => {
    const title = el["session-title-input"].value.trim();
    if (!title) return;
    try {
      await patchManagedSession({ title });
    } catch (error) {
      toast(error.message, "error");
    }
  });
  el["pin-session"].addEventListener("click", async () => {
    try {
      await patchManagedSession({ pinned: !state.managedSession?.pinned });
    } catch (error) {
      toast(error.message, "error");
    }
  });
  el["archive-session"].addEventListener("click", async () => {
    try {
      await patchManagedSession({ archived: !state.managedSession?.archived });
    } catch (error) {
      toast(error.message, "error");
    }
  });
  el["delete-session"].addEventListener("click", async () => {
    const session = state.managedSession;
    if (!session || !window.confirm(`Delete “${session.title || "New task"}”?`)) return;
    try {
      await api(`/v1/sessions/${encodeURIComponent(session.session_id)}`, {
        method: "DELETE",
      });
      if (state.sessionId === session.session_id) {
        disconnectSocket();
        cancelProjectSearch(state.sessionId);
        state.sessionId = null;
        state.workspace = null;
        state.routingResolution = null;
        renderRoutingResolution();
        state.messages = [];
        state.mcpServers = [];
        state.artifacts = [];
        state.mcpLoadGeneration += 1;
        state.artifactLoadGeneration += 1;
        state.goals = [];
        state.goalGeneration += 1;
        state.roots = [];
        state.treeGeneration += 1;
        invalidateProjectSearch();
        invalidateAttachments();
        invalidateContextItems();
        clearArtifactPreview();
        el["task-title"].textContent = "New task";
        updateWorkspaceLabel();
        renderConversation();
        renderGoals();
        renderContextRoots();
        renderProjectTree();
      }
      state.managedSession = null;
      el["session-dialog"].close();
      await loadSessions();
      toast("Task deleted");
    } catch (error) {
      toast(error.message, "error");
    }
  });
  el["toggle-sidebar"].addEventListener("click", () => {
    el.app.classList.toggle("sidebar-collapsed");
  });
  document.addEventListener("dblclick", (event) => {
    if (!event.target.closest("[data-tauri-drag-region]")) return;
    zoomFromTitlebar(event);
  });
  el["command-palette-close"].addEventListener("click", closePalette);
  el["command-palette-input"].addEventListener("input", () => {
    state.palette.selected = 0;
    if (state.palette.mode === "workspace-symbols") {
      clearTimeout(state.palette.symbolTimer);
      state.palette.symbolTimer = setTimeout(() => {
        loadWorkspaceSymbols(el["command-palette-input"].value);
      }, 150);
      return;
    }
    renderPalette();
  });
  el["command-palette"].addEventListener("keydown", (event) => {
    if (event.key === "Escape") { event.preventDefault(); closePalette(); }
    if (event.target !== el["command-palette-input"]) return;
    if (event.key === "ArrowDown") { event.preventDefault(); state.palette.selected += 1; renderPalette(); }
    if (event.key === "ArrowUp") { event.preventDefault(); state.palette.selected = Math.max(0, state.palette.selected - 1); renderPalette(); }
    if (event.key === "Enter") { event.preventDefault(); selectPaletteItem(); }
  });
  el["command-palette"].addEventListener("close", () => {
    state.palette.returnFocus?.focus?.();
    state.palette.returnFocus = null;
  });
  el["choose-workspace"].addEventListener("click", async () => {
    const workspace = await pickWorkspace();
    if (!workspace) return;
    switchWorkspace(workspace);
  });
  el["model-select"].addEventListener("change", async () => {
    const session = state.sessions.find(
      (candidate) => candidate.session_id === state.sessionId
    );
    if (!session || state.busy) return;
    try {
      const result = await api(
        `/v1/sessions/${encodeURIComponent(state.sessionId)}`,
        {
          method: "PATCH",
          body: JSON.stringify({ model: el["model-select"].value }),
        }
      );
      session.model = result.model;
      state.routingResolution = null;
      renderRoutingResolution();
      toast(`Model changed to ${result.model}`);
    } catch (error) {
      selectModel(session.model);
      toast(error.message, "error");
    }
  });
  el["routing-profile"].addEventListener("change", async () => {
    if (state.routingPending) return;
    const previous = state.settings?.routing_profile || "manual";
    state.routingPending = true;
    el["routing-profile"].disabled = true;
    updateComposer();
    try {
      const result = await api("/v1/settings/routing", {
        method: "PATCH",
        body: JSON.stringify({
          profile: el["routing-profile"].value,
        }),
      });
      state.settings.routing_profile = result.routing_profile;
      if (result.routing) state.settings.routing = result.routing;
      state.routingResolution = null;
      renderRoutingResolution();
      toast(`Routing profile changed to ${result.routing_profile}`);
    } catch (error) {
      el["routing-profile"].value = previous;
      renderRoutingResolution();
      toast(error.message, "error");
    } finally {
      state.routingPending = false;
      el["routing-profile"].disabled = state.busy;
      updateComposer();
    }
  });
  el.prompt.addEventListener("input", () => {
    resizePrompt();
    updateMentionPicker();
  });
  el.prompt.addEventListener("blur", () => {
    setTimeout(closeMentionPicker, 120);
  });
  el["attach-files"].addEventListener("click", () => {
    el["attachment-input"].click();
  });
  el["terminal-restart"].addEventListener("click", () => {
    restartTerminalView().catch((error) => toast(String(error), "error"));
  });
  el["terminal-clear"].addEventListener("click", () => {
    hideTerminalView().catch((error) => toast(String(error), "error"));
  });
  // Lazy-mount the terminal the first time the panel becomes visible.
  const terminalPanel = el["terminal-panel"];
  if (typeof IntersectionObserver !== "undefined" && terminalPanel) {
    const termObserver = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (
          entry.isIntersecting
          && !terminalPanel.classList.contains("is-hidden")
          && !state.terminal
          && state.workspace
        ) {
          openTerminalView().catch((error) => toast(String(error), "error"));
        }
      }
    }, { threshold: 0.1 });
    termObserver.observe(terminalPanel);
  }
  el["attachment-input"].addEventListener("change", (event) => {
    queueAttachments(event.target.files);
  });
  el.prompt.addEventListener("keydown", (event) => {
    if (state.mention) {
      if (event.key === "ArrowDown") { event.preventDefault(); state.mention.selected = Math.min(state.mention.selected + 1, state.mention.items.length - 1); renderMentionPicker(); return; }
      if (event.key === "ArrowUp") { event.preventDefault(); state.mention.selected = Math.max(state.mention.selected - 1, 0); renderMentionPicker(); return; }
      if (event.key === "Enter") { event.preventDefault(); selectMention(); return; }
      if (event.key === "Escape") { event.preventDefault(); closeMentionPicker(); return; }
    }
    if (event.key === "Enter" && event.metaKey) {
      event.preventDefault();
      sendTurn();
    }
  });
  el["send-turn"].addEventListener("click", sendTurn);
  el["stop-turn"].addEventListener("click", stopTurn);
  el["review-button"].addEventListener("click", () => loadDiff(true));
  el["subagents-button"].addEventListener("click", openSubagents);
  el["utility-environment-tab"].addEventListener("click", () => selectUtilityView("environment"));
  el["utility-subagents-tab"].addEventListener("click", () => selectUtilityView("subagents"));
  el["utility-environment-tab"].addEventListener("keydown", moveUtilityTab);
  el["utility-subagents-tab"].addEventListener("keydown", moveUtilityTab);
  el["refresh-diff"].addEventListener("click", () => loadDiff(false));
  el["close-review"].addEventListener("click", closeReview);
  el["environment-open-review"].addEventListener("click", () => {
    el["environment-details"].open = true;
    el["environment-details"].scrollIntoView({ block: "nearest" });
  });
  el["apply-changes"].addEventListener("click", applyChanges);
  el["git-stage"].addEventListener("click", () => {
    stageAll().catch((error) => toast(error.message, "error"));
  });
  el["git-commit"].addEventListener("click", () => {
    commitChanges().catch((error) => toast(error.message, "error"));
  });
  el["git-push"].addEventListener("click", () => {
    pushBranch().catch((error) => toast(error.message, "error"));
  });
  el["github-create-pr"].addEventListener("click", () => {
    createPullRequest().catch((error) => toast(error.message, "error"));
  });
  el["preview-open"].addEventListener("click", openPreview);
  el["preview-url"].addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      openPreview();
    }
  });
  el["preview-annotate"].addEventListener("click", toggleAnnotation);
  el["preview-attach-console"].addEventListener("click", () => {
    attachConsoleEvidence().catch((error) => toast(error.message, "error"));
  });
  startAnnotationOverlay();
  el["commit-message"].addEventListener("input", renderGitStatus);
  el["checkpoint-select"].addEventListener(
    "change",
    renderCheckpoints
  );
  el["restore-checkpoint"].addEventListener(
    "click",
    restoreCheckpoint
  );
  for (const suggestion of document.querySelectorAll("[data-prompt]")) {
    suggestion.addEventListener("click", async () => {
      if (!state.workspace) await newTask();
      el.prompt.value = suggestion.dataset.prompt;
      resizePrompt();
      el.prompt.focus();
    });
  }
  document.addEventListener("keydown", (event) => {
    if (event.metaKey && !event.shiftKey && event.key === ",") {
      event.preventDefault();
      openSettings();
    }
    if (event.metaKey && !event.shiftKey && event.key.toLowerCase() === "p") {
      event.preventDefault();
      openPalette("files");
    }
    if (event.metaKey && event.shiftKey && event.key.toLowerCase() === "p") {
      event.preventDefault();
      openPalette("commands");
    }
    if (event.metaKey && event.shiftKey && event.key.toLowerCase() === "o") {
      event.preventDefault();
      openSymbolPalette("document-symbols");
    }
    if (event.metaKey && event.key.toLowerCase() === "t") {
      event.preventDefault();
      openSymbolPalette("workspace-symbols");
    }
    if (event.metaKey && event.key.toLowerCase() === "n") {
      event.preventDefault();
      newTask();
    }
    if (event.metaKey && event.shiftKey && event.key.toLowerCase() === "d") {
      event.preventDefault();
      loadDiff(true);
    }
    if (event.key === "Escape" && el.app.classList.contains("review-open")) {
      closeReview();
    }
  });
  document.addEventListener("dragover", (event) => {
    event.preventDefault();
    document.body.classList.add("is-dragging");
  });
  document.addEventListener("dragleave", (event) => {
    if (!event.relatedTarget) document.body.classList.remove("is-dragging");
  });
  document.addEventListener("drop", (event) => {
    event.preventDefault();
    document.body.classList.remove("is-dragging");
    const files = event.dataTransfer?.files;
    if (files?.length && Array.from(files).some((file) => ATTACHMENT_TYPES.has(file.type))) {
      queueAttachments(files);
      return;
    }
    const path = files?.[0]?.path;
    if (path?.startsWith("/")) {
      switchWorkspace(path);
    }
  });
}

async function boot() {
  const savedTheme = localStorage.getItem("codinal-theme");
  if (savedTheme === "light" || savedTheme === "dark") {
    document.documentElement.dataset.theme = savedTheme;
  }
  wireEvents();
  try {
    await connect();
    // Settings populate secondary controls; the first usable workspace should
    // not wait on them after the runtime and task list are ready.
    const settingsLoad = loadSettings().catch((error) => {
      toast(`Settings unavailable: ${error.message}`, "error");
    });
    await loadSessions();
    setTerminalBusy(false);
    el.startup.classList.add("is-hidden");
    el.app.classList.remove("is-hidden");
    const first = state.sessions.find((session) => !session.archived);
    if (first) await selectSession(first);
    else {
      state.sessionId = `session-${crypto.randomUUID()}`;
      updateWorkspaceLabel();
      connectSocket();
    }
    void settingsLoad;
  } catch (error) {
    el["startup-status"].textContent = `Runtime unavailable: ${error.message}`;
  }
}

boot();
