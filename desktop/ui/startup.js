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

const state = {
  online: false,
  busy: false,
  sessions: [],
  sessionId: null,
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
  state.sessions = await api("/v1/sessions");
  const active = state.sessions.find(
    (session) => session.session_id === state.sessionId
  );
  if (active) syncAgentMode(active);
  renderSessions();
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
  const sessions = state.sessions.filter((session) => {
    if (session.archived) return false;
    return !query || `${session.title} ${session.workspace}`
      .toLowerCase().includes(query);
  });
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
      node("small", "", basename(session.workspace))
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
  if (state.sessionId === session.session_id) return;
  disconnectSocket();
  state.sessionId = session.session_id;
  state.workspace = session.workspace;
  state.messages = [];
  state.checkpoints = [];
  invalidateAttachments();
  state.liveAssistant = null;
  state.activities.clear();
  el["task-title"].textContent = session.title || "New task";
  syncAgentMode(session);
  selectModel(session.model);
  updateWorkspaceLabel();
  renderSessions();
  renderConversation();
  renderCheckpoints();
  try {
    state.messages = await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/messages`
    );
    renderConversation();
    connectSocket();
    await Promise.all([
      loadPendingApprovals(),
      loadPendingInteractions(),
      loadDiff(false),
    ]);
  } catch (error) {
    toast(error.message, "error");
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
  state.workspace = workspace;
  state.messages = [];
  invalidateAttachments();
  state.liveAssistant = null;
  state.activities.clear();
  state.diff = "";
  state.checkpoints = [];
  el["task-title"].textContent = "New task";
  updateWorkspaceLabel();
  renderSessions();
  renderConversation();
  renderDiff();
  renderCheckpoints();
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
  el["restore-checkpoint"].disabled = (
    busy || !el["checkpoint-select"].value
  );
  el["stop-turn"].classList.toggle("is-hidden", !busy);
  el["send-turn"].classList.toggle("is-hidden", busy);
  setRuntimeStatus(busy ? "Codinal is working" : "Local runtime", busy ? "busy" : "online");
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
    await Promise.all([loadSessions(), loadDiff(false)]);
  } catch (error) {
    toast(error.message, "error");
  }
  renderConversation();
}

function renderConversation() {
  const visible = state.messages.filter(
    (message) => message.role === "user" || message.role === "assistant"
  );
  el["empty-state"].classList.toggle(
    "is-hidden",
    Boolean(visible.length || state.liveAssistant || state.activities.size)
  );
  el["message-list"].replaceChildren();
  for (const message of visible) {
    el["message-list"].append(renderMessage(message.role, contentText(message.content)));
  }
  if (state.liveAssistant) {
    el["message-list"].append(renderMessage("assistant", state.liveAssistant, true));
  }
  for (const activity of state.activities.values()) {
    el["message-list"].append(renderActivity(activity));
  }
  el.conversation.scrollTop = el.conversation.scrollHeight;
}

function contentText(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  const text = content
    .filter((part) => part && part.type === "text")
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

function renderMessage(role, content, streaming = false) {
  const article = node("article", `message ${role}`);
  const who = role === "assistant" ? "C" : "You";
  article.append(node("div", "message-avatar", role === "assistant" ? "C" : "Y"));
  const body = node("div", "message-body");
  body.append(
    node("div", "message-meta", streaming ? "Codinal · Writing…" : who),
    node("p", "message-content", content)
  );
  article.append(body);
  return article;
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
  if (!state.sessionId) return;
  const pending = await api(
    `/v1/sessions/${encodeURIComponent(state.sessionId)}/approvals`
  );
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
    || state.attachmentsPending) return;
  const attachments = state.attachments;
  const parts = [];
  if (input) parts.push({ "type": "text", "text": input });
  for (const attachment of attachments) {
    if (attachment.type === "application/pdf") {
      parts.push({
        "type": "file",
        "file": {
          "filename": attachment.name,
          "file_data": attachment.data,
        },
      });
    } else {
      parts.push({
        "type": "image_url",
        "image_url": { "url": attachment.data },
      });
    }
  }
  const turnInput = attachments.length ? parts : input;
  state.messages.push({ role: "user", content: turnInput });
  el.prompt.value = "";
  state.attachments = [];
  renderAttachments();
  resizePrompt();
  renderConversation();
  setBusy(true);
  try {
    await api(`/v1/sessions/${encodeURIComponent(state.sessionId)}/turns`, {
      method: "POST",
      body: JSON.stringify({
        input: turnInput,
        workspace: state.workspace,
        agent: el["agent-mode"].value,
        mode: el["agent-mode"].value === "plan"
          ? "plan"
          : el["agent-mode"].value === "review"
            ? "discuss"
            : "interactive",
        model: el["model-select"].value,
      }),
    });
  } catch (error) {
    state.messages.pop();
    state.attachments = attachments;
    renderAttachments();
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
    || state.attachmentsPending > 0;
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

function resizePrompt() {
  el.prompt.style.height = "auto";
  el.prompt.style.height = `${Math.min(el.prompt.scrollHeight, 180)}px`;
  updateComposer();
}

async function loadDiff(showPanel = true) {
  if (!state.sessionId) return;
  try {
    const result = await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/git/diff?against_base=true`
    );
    state.diff = typeof result.diff === "string" ? result.diff : "";
  } catch (error) {
    if (!error.message.includes("not found")) {
      toast(error.message, "error");
    }
    state.diff = "";
  }
  renderDiff();
  await loadCheckpoints();
  if (showPanel) openReview();
}

async function loadCheckpoints() {
  if (!state.sessionId) {
    state.checkpoints = [];
    renderCheckpoints();
    return;
  }
  try {
    state.checkpoints = await api(
      `/v1/sessions/${encodeURIComponent(state.sessionId)}/checkpoints`
    );
  } catch (error) {
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
  el["refresh-sessions"].addEventListener("click", loadSessions);
  el["session-search"].addEventListener("input", renderSessions);
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
        invalidateAttachments();
        el["task-title"].textContent = "New task";
        updateWorkspaceLabel();
        renderConversation();
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
