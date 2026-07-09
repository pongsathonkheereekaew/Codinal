import Database from 'better-sqlite3';

let db;
export const now = () => Date.now();

const SCHEMA = `
CREATE TABLE IF NOT EXISTS missions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  source TEXT DEFAULT 'telegram',
  topic TEXT,
  status TEXT DEFAULT 'planning',
  summary TEXT,
  paused_notified INTEGER DEFAULT 0,
  created_at INTEGER,
  updated_at INTEGER
);
CREATE TABLE IF NOT EXISTS tasks(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mission_id INTEGER,
  name TEXT,
  stage TEXT DEFAULT 'build',
  status TEXT DEFAULT 'queued',
  character_id INTEGER,
  cursor_agent_id TEXT UNIQUE,
  cursor_status TEXT,
  verify_status TEXT DEFAULT 'none',
  verify_red_count INTEGER DEFAULT 0,
  pr_url TEXT,
  branch TEXT,
  started_at INTEGER,
  last_event_at INTEGER,
  updated_at INTEGER
);
CREATE TABLE IF NOT EXISTS characters(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE,
  sprite TEXT,
  locked_local_only INTEGER DEFAULT 0,
  archived INTEGER DEFAULT 0,
  created_at INTEGER,
  updated_at INTEGER
);
CREATE TABLE IF NOT EXISTS approvals(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER,
  action TEXT DEFAULT 'merge',
  requested_at INTEGER,
  verify_status_at_request TEXT,
  decided TEXT,
  decided_via TEXT,
  decided_at INTEGER,
  note TEXT
);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER,
  source TEXT,
  type TEXT,
  mission_id INTEGER,
  task_id INTEGER,
  payload TEXT
);
CREATE TABLE IF NOT EXISTS health(
  component TEXT PRIMARY KEY,
  status TEXT,
  detail TEXT,
  last_ok_at INTEGER,
  updated_at INTEGER
);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
`;

export function init(dbPath) {
  db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.exec(SCHEMA);
  return db;
}

function updateRow(table, id, fields, allowed) {
  const keys = Object.keys(fields).filter((k) => allowed.includes(k));
  if (!keys.length) return;
  const sets = keys.map((k) => `${k} = ?`).join(', ');
  db.prepare(`UPDATE ${table} SET ${sets}, updated_at = ? WHERE id = ?`)
    .run(...keys.map((k) => fields[k]), now(), id);
}

// ---- missions ----
const MISSION_FIELDS = ['title', 'source', 'topic', 'status', 'summary', 'paused_notified', 'created_at'];

export function createMission({ title, source = 'telegram', topic = null }) {
  const t = now();
  const r = db.prepare(
    'INSERT INTO missions(title, source, topic, status, created_at, updated_at) VALUES(?,?,?,?,?,?)'
  ).run(title, source, topic, 'planning', t, t);
  return getMission(r.lastInsertRowid);
}
export const getMission = (id) => db.prepare('SELECT * FROM missions WHERE id = ?').get(id);
export const findMissionByTitle = (title) =>
  db.prepare('SELECT * FROM missions WHERE title = ? ORDER BY id DESC').get(title);
export const updateMission = (id, fields) => updateRow('missions', id, fields, MISSION_FIELDS);
export const listMissions = (limit = 30) =>
  db.prepare('SELECT * FROM missions ORDER BY updated_at DESC LIMIT ?').all(limit);
export const listMissionsByStatus = (statuses) =>
  db.prepare(`SELECT * FROM missions WHERE status IN (${statuses.map(() => '?').join(',')})`).all(...statuses);

// ---- tasks ----
const TASK_FIELDS = ['name', 'stage', 'status', 'character_id', 'cursor_agent_id', 'cursor_status',
  'verify_status', 'verify_red_count', 'pr_url', 'branch', 'started_at', 'last_event_at'];

export function createTask({ mission_id, name, stage = 'build' }) {
  const t = now();
  const r = db.prepare(
    'INSERT INTO tasks(mission_id, name, stage, status, updated_at) VALUES(?,?,?,?,?)'
  ).run(mission_id, name, stage, 'queued', t);
  return getTask(r.lastInsertRowid);
}
export const getTask = (id) => db.prepare('SELECT * FROM tasks WHERE id = ?').get(id);
export const findTaskByAgent = (agentId) =>
  db.prepare('SELECT * FROM tasks WHERE cursor_agent_id = ?').get(agentId);
export const findTaskByName = (missionId, name) =>
  db.prepare('SELECT * FROM tasks WHERE mission_id = ? AND name = ? ORDER BY id DESC').get(missionId, name);
export const updateTask = (id, fields) => updateRow('tasks', id, fields, TASK_FIELDS);
export const listTasks = (limit = 200) =>
  db.prepare('SELECT * FROM tasks ORDER BY updated_at DESC LIMIT ?').all(limit);
export const listTasksByMission = (missionId) =>
  db.prepare('SELECT * FROM tasks WHERE mission_id = ? ORDER BY id').all(missionId);
export const listActiveAgentTasks = () => db.prepare(
  `SELECT * FROM tasks WHERE cursor_agent_id IS NOT NULL
   AND status NOT IN ('done','cancelled','failed')`
).all();
export const listTasksByStatus = (statuses) =>
  db.prepare(`SELECT * FROM tasks WHERE status IN (${statuses.map(() => '?').join(',')})`).all(...statuses);
export const countAssigned = (missionId) => db.prepare(
  'SELECT COUNT(*) AS n FROM tasks WHERE mission_id = ? AND cursor_agent_id IS NOT NULL'
).get(missionId).n;

// ---- characters ----
const AUTO_NAMES = ['Ash', 'Bee', 'Cody', 'Dax', 'Eve', 'Fox', 'Gia', 'Hex', 'Ivy', 'Jax'];

export function getOrCreateCharacter(name) {
  if (name) {
    const found = db.prepare('SELECT * FROM characters WHERE name = ?').get(name);
    if (found) return found;
    const r = db.prepare('INSERT INTO characters(name, created_at) VALUES(?,?)').run(name, now());
    return db.prepare('SELECT * FROM characters WHERE id = ?').get(r.lastInsertRowid);
  }
  const used = new Set(db.prepare('SELECT name FROM characters').all().map((c) => c.name));
  const free = AUTO_NAMES.find((n) => !used.has(n)) || `Agent-${used.size + 1}`;
  return getOrCreateCharacter(free);
}
export const getCharacter = (id) => db.prepare('SELECT * FROM characters WHERE id = ?').get(id);
export const listCharacters = () =>
  db.prepare('SELECT * FROM characters WHERE archived = 0 ORDER BY id').all();
export const updateCharacter = (id, fields) =>
  updateRow('characters', id, fields, ['name', 'sprite', 'locked_local_only', 'archived']);

// ---- approvals ----
export function createApproval({ task_id, verify_status_at_request }) {
  const r = db.prepare(
    'INSERT INTO approvals(task_id, requested_at, verify_status_at_request) VALUES(?,?,?)'
  ).run(task_id, now(), verify_status_at_request);
  return getApproval(r.lastInsertRowid);
}
export const getApproval = (id) => db.prepare('SELECT * FROM approvals WHERE id = ?').get(id);
export const latestPendingApprovalForTask = (taskId) => db.prepare(
  'SELECT * FROM approvals WHERE task_id = ? AND decided IS NULL ORDER BY id DESC'
).get(taskId);
export const listPendingApprovals = () =>
  db.prepare('SELECT * FROM approvals WHERE decided IS NULL ORDER BY requested_at').all();
export function updateApproval(id, fields) {
  const allowed = ['decided', 'decided_via', 'decided_at', 'note'];
  const keys = Object.keys(fields).filter((k) => allowed.includes(k));
  if (!keys.length) return;
  const sets = keys.map((k) => `${k} = ?`).join(', ');
  db.prepare(`UPDATE approvals SET ${sets} WHERE id = ?`).run(...keys.map((k) => fields[k]), id);
}

// ---- events / health / meta ----
export function logEvent({ source = 'bridge', type, mission_id = null, task_id = null, payload = null }) {
  db.prepare('INSERT INTO events(ts, source, type, mission_id, task_id, payload) VALUES(?,?,?,?,?,?)')
    .run(now(), source, type, mission_id, task_id, payload ? JSON.stringify(payload) : null);
}
export const listEvents = (limit = 50) =>
  db.prepare('SELECT * FROM events ORDER BY id DESC LIMIT ?').all(limit);

export function setHealth(component, status, detail = null) {
  const t = now();
  db.prepare(`INSERT INTO health(component, status, detail, last_ok_at, updated_at)
    VALUES(?,?,?,?,?)
    ON CONFLICT(component) DO UPDATE SET
      status = excluded.status, detail = excluded.detail, updated_at = excluded.updated_at,
      last_ok_at = CASE WHEN excluded.status = 'ok' THEN excluded.updated_at ELSE health.last_ok_at END`)
    .run(component, status, detail, status === 'ok' ? t : null, t);
}
export const getHealth = (component) =>
  db.prepare('SELECT * FROM health WHERE component = ?').get(component);
export const listHealth = () => db.prepare('SELECT * FROM health ORDER BY component').all();

export const getMeta = (k) => db.prepare('SELECT v FROM meta WHERE k = ?').get(k)?.v;
export const setMeta = (k, v) => db.prepare(
  'INSERT INTO meta(k, v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v = excluded.v'
).run(k, String(v));
