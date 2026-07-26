"use strict";

const HTTP = window.__CODINAL_HTTP__;
const WS = window.__CODINAL_WS__;
const TOKEN = window.__CODINAL_TOKEN__;
const invoke = window.__TAURI__?.core?.invoke;
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
  socket: null,
  liveAssistant: null,
  activities: new Map(),
  settings: null,
  diff: "",
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
  rootMutationPending: false,
  contextItems: [],
  contextGeneration: 0,
  contextPending: false,
  workers: [],
  workerGeneration: 0,
};

const el = Object.fromEntries(
  [
    "startup", "startup-status", "app", "sidebar", "new-task",
    "session-search", "refresh-sessions", "session-list", "theme-toggle",
    "open-settings", "toggle-sidebar", "task-title", "workspace-path",
    "runtime-status", "review-button", "change-count", "conversation",
    "empty-state", "message-list", "prompt", "attach-files",
    "attachment-input", "attachment-list", "choose-workspace",
    "workspace-label", "agent-mode", "model-select", "stop-turn",
    "send-turn", "review-panel", "close-review", "review-summary",
    "refresh-diff", "diff-view", "apply-changes", "settings-dialog",
    "checkpoint-select", "restore-scope", "restore-checkpoint",
    "model-summary", "update-status", "check-update", "install-update",
    "provider-list", "toast-region",
    "session-dialog", "session-title-input", "rename-session",
    "pin-session", "archive-session", "delete-session",
    "context-roots", "project-tree", "add-context-root",
    "thread-search", "thread-search-previous", "thread-search-next",
    "export-thread", "return-to-parent",
    "context-items",
    "worker-panel", "worker-summary", "worker-list", "new-worker",
    "worker-dialog", "worker-task", "worker-ownership", "create-worker",
    "worker-dependencies",
  ].map((id) => [id, document.getElementById(id)])
);

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

function shortPath(path) {
  if (!path) return "Choose a workspace to begin";
  const parts = path.split("/").filter(Boolean);
  return parts.length > 3 ? `…/${parts.slice(-3).join("/")}` : path;
}

function basename(path) {
  return path?.split("/").filter(Boolean).at(-1) || "Workspace";
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
  el["toast-region"].append(item);
  window.setTimeout(() => item.remove(), 4200);
}

function setRuntimeStatus(label, kind = "online") {
  const indicator = el["runtime-status"];
  indicator.classList.toggle("is-online", kind === "online");
  indicator.classList.toggle("is-busy", kind === "busy");
  indicator.querySelector("span").textContent = label;
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

async function loadSettings() {
  state.settings = await api("/v1/settings");
  const models = Array.isArray(state.settings.models)
    ? state.settings.models
    : [state.settings.model].filter(Boolean);
  el["model-select"].replaceChildren();
  for (const model of models) {
    const option = node("option", "", model);
    option.value = model;
    option.selected = model === state.settings.model;
    el["model-select"].append(option);
  }
  if (!models.length) {
    const option = node("option", "", "Default model");
    el["model-select"].append(option);
  }
  el["model-summary"].textContent = state.settings.model
    ? `Current model: ${state.settings.model}`
    : "The runtime will use its configured default model.";
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
  el["worker-summary"].textContent = state.workers.length
    ? `${active} active · ${state.workers.length} total`
    : "No background work";
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
    if (worker.state === "succeeded" && worker.commit) {
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
  disconnectSocket();
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
  state.checkpoints = [];
  state.workers = [];
  state.workerGeneration += 1;
  state.roots = [];
  state.treeGeneration += 1;
  invalidateAttachments();
  invalidateContextItems();
  state.liveAssistant = null;
  state.activities.clear();
  el["task-title"].textContent = session.title || "New task";
  syncAgentMode(session);
  selectModel(session.model);
  updateWorkspaceLabel();
  renderSessions();
  renderConversation();
  renderCheckpoints();
  renderContextRoots();
  renderProjectTree();
  renderWorkers();
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

function switchWorkspace(workspace) {
  if (state.busy) {
    toast("Stop the active turn before changing workspace", "error");
    return false;
  }
  disconnectSocket();
  state.sessionId = `session-${crypto.randomUUID()}`;
  state.parentSessionId = null;
  el["return-to-parent"].classList.add("is-hidden");
  state.sessionSelectionGeneration += 1;
  state.workspace = workspace;
  state.messages = [];
  state.highlightedMessageIndex = null;
  el["thread-search"].value = "";
  state.threadSearchMatches = [];
  state.threadSearchCursor = -1;
  state.roots = [];
  state.treeGeneration += 1;
  invalidateAttachments();
  invalidateContextItems();
  state.liveAssistant = null;
  state.activities.clear();
  state.diff = "";
  state.checkpoints = [];
  state.workers = [];
  state.workerGeneration += 1;
  el["task-title"].textContent = "New task";
  updateWorkspaceLabel();
  renderSessions();
  renderConversation();
  renderDiff();
  renderCheckpoints();
  renderContextRoots();
  renderProjectTree();
  renderWorkers();
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
  updateComposer();
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
  el["agent-mode"].disabled = busy;
  el["new-task"].disabled = busy;
  el["choose-workspace"].disabled = busy;
  el["add-context-root"].disabled = (
    busy || state.rootMutationPending || !state.roots.length
  );
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
      renderConversation();
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
    case "directory_requested":
    case "plan_proposed":
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
  renderProjectTree(generation);
}

function renderContextRoots() {
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
  el["empty-state"].classList.toggle(
    "is-hidden",
    Boolean(visible.length || state.liveAssistant || state.activities.size)
  );
  el["message-list"].replaceChildren();
  for (const { message, index } of visible) {
    el["message-list"].append(
      renderMessage(
        message.role,
        contentText(message.content),
        false,
        index,
        isSafeForkBoundary(index)
      )
    );
  }
  if (state.liveAssistant) {
    el["message-list"].append(renderMessage("assistant", state.liveAssistant, true));
  }
  for (const activity of state.activities.values()) {
    el["message-list"].append(renderActivity(activity));
  }
  const highlighted = el["message-list"].querySelector(
    ".message.is-search-match"
  );
  if (highlighted) {
    highlighted.scrollIntoView({ block: "center" });
  } else {
    el.conversation.scrollTop = el.conversation.scrollHeight;
  }
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
  forkable = false
) {
  const article = node("article", `message ${role}`);
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
    node("p", "message-content", content)
  );
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
    content.append(node("pre", "approval-arguments", args.plan || ""));
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
    approve.addEventListener("click", () => resolveInteraction(
      card,
      interaction,
      { approved: true, mode: "interactive" }
    ));
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
    || !state.workspace || !state.sessionId || state.busy
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
  state.messages.push({ role: "user", content: displayTurnInput });
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
    await api(`/v1/sessions/${encodeURIComponent(state.sessionId)}/turns`, {
      method: "POST",
      body: JSON.stringify({
        input: requestInput,
        workspace: state.workspace,
        agent: el["agent-mode"].value,
        mode: el["agent-mode"].value === "plan"
          ? "plan"
          : el["agent-mode"].value === "review"
            ? "discuss"
            : "interactive",
        model: el["model-select"].value,
        ...(contexts.length ? {
          context: contexts.map((context) => ({
            kind: context.kind,
            root: context.root,
            path: context.path,
            fingerprint: context.fingerprint,
          })),
        } : {}),
      }),
    });
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

function updateComposer() {
  const hasInput = Boolean(el.prompt.value.trim() || state.attachments.length);
  el["send-turn"].disabled = !state.online || !state.workspace
    || !state.sessionId || !hasInput || state.busy
    || state.attachmentsPending > 0 || state.contextPending;
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
  await loadCheckpoints(sessionId);
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
  const files = lines.filter((line) => line.startsWith("diff --git ")).length;
  el["change-count"].textContent = String(files);
  el["change-count"].classList.toggle("is-hidden", files === 0);
  el["review-button"].disabled = !state.sessionId;
  el["review-summary"].textContent = files
    ? `${files} changed ${files === 1 ? "file" : "files"}`
    : "No un-applied changes";
  el["apply-changes"].disabled = !state.diff;
  el["diff-view"].replaceChildren();
  if (!lines.length) {
    el["diff-view"].append(node("span", "diff-line", "No changes to review."));
    return;
  }
  for (const line of lines) {
    let kind = "";
    if (line.startsWith("diff --git ") || line.startsWith("@@")) kind = "header";
    else if (line.startsWith("+") && !line.startsWith("+++")) kind = "add";
    else if (line.startsWith("-") && !line.startsWith("---")) kind = "delete";
    el["diff-view"].append(node("span", `diff-line ${kind}`.trim(), line));
  }
}

function openReview() {
  el.app.classList.add("review-open");
  el["review-panel"].setAttribute("aria-hidden", "false");
}

function closeReview() {
  el.app.classList.remove("review-open");
  el["review-panel"].setAttribute("aria-hidden", "true");
}

async function applyChanges() {
  if (!state.sessionId || !state.diff) return;
  el["apply-changes"].disabled = true;
  try {
    await api(`/v1/sessions/${encodeURIComponent(state.sessionId)}/git/apply`, {
      method: "POST",
    });
    toast("Changes applied to the source workspace");
    await loadDiff(false);
  } catch (error) {
    toast(error.message, "error");
    el["apply-changes"].disabled = false;
  }
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme;
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("codinal-theme", next);
}

async function openSettings() {
  el["settings-dialog"].showModal();
  try {
    await loadSettings();
    await renderProviders();
  } catch (error) {
    toast(error.message, "error");
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
  const providers = await invoke("list_provider_secret_status");
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
    const save = node("button", "", provider.configured ? "Update" : "Save");
    save.type = "button";
    save.addEventListener("click", async () => {
      if (!input.value) return;
      save.disabled = true;
      try {
        await invoke("set_provider_secret", {
          provider: provider.provider,
          apiKey: input.value,
        });
        input.value = "";
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
    row.append(label, input, actions);
    el["provider-list"].append(row);
  }
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
  el["session-search"].addEventListener("input", scheduleSessionSearch);
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
  el["open-settings"].addEventListener("click", openSettings);
  el["check-update"].addEventListener("click", checkForUpdate);
  el["install-update"].addEventListener("click", installUpdate);
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
        state.sessionId = null;
        state.workspace = null;
        state.messages = [];
        state.roots = [];
        state.treeGeneration += 1;
        invalidateAttachments();
        invalidateContextItems();
        el["task-title"].textContent = "New task";
        updateWorkspaceLabel();
        renderConversation();
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
      toast(`Model changed to ${result.model}`);
    } catch (error) {
      selectModel(session.model);
      toast(error.message, "error");
    }
  });
  el.prompt.addEventListener("input", resizePrompt);
  el["attach-files"].addEventListener("click", () => {
    el["attachment-input"].click();
  });
  el["attachment-input"].addEventListener("change", (event) => {
    queueAttachments(event.target.files);
  });
  el.prompt.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && event.metaKey) {
      event.preventDefault();
      sendTurn();
    }
  });
  el["send-turn"].addEventListener("click", sendTurn);
  el["stop-turn"].addEventListener("click", stopTurn);
  el["review-button"].addEventListener("click", () => loadDiff(true));
  el["refresh-diff"].addEventListener("click", () => loadDiff(false));
  el["close-review"].addEventListener("click", closeReview);
  el["apply-changes"].addEventListener("click", applyChanges);
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
    await Promise.all([loadSettings(), loadSessions()]);
    el.startup.classList.add("is-hidden");
    el.app.classList.remove("is-hidden");
    const first = state.sessions.find((session) => !session.archived);
    if (first) await selectSession(first);
    else updateWorkspaceLabel();
  } catch (error) {
    el["startup-status"].textContent = `Runtime unavailable: ${error.message}`;
  }
}

boot();
