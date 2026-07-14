import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';

// fake Cursor API — เก็บ followup ที่ถูกยิงเข้ามาไว้ตรวจ
const followups = [];
const fake = http.createServer((req, res) => {
  let body = '';
  req.on('data', (d) => { body += d; });
  req.on('end', () => {
    res.setHeader('Content-Type', 'application/json');
    if (req.method === 'POST' && /\/v0\/agents\/.+\/followup/.test(req.url)) {
      followups.push({ url: req.url, body: JSON.parse(body || '{}') });
      return res.end(JSON.stringify({ id: 'ok' }));
    }
    if (req.method === 'GET' && /\/v0\/agents\//.test(req.url)) {
      return res.end(JSON.stringify({ id: req.url.split('/').pop(), status: 'RUNNING' }));
    }
    if (req.method === 'GET' && req.url.startsWith('/v0/agents')) {
      return res.end(JSON.stringify({ agents: [] }));
    }
    if (req.method === 'GET' && /\/repos\/.+\/pulls\//.test(req.url)) {
      return res.end(JSON.stringify({ head: { sha: 'abc123deadbeef' } }));
    }
    if (req.method === 'GET' && /\/repos\/.+\/commits\//.test(req.url)) {
      return res.end(JSON.stringify({ state: 'failure' }));
    }
    res.end(JSON.stringify({}));
  });
});
await new Promise((r) => fake.listen(0, '127.0.0.1', r));
process.env.CURSOR_API_BASE = `http://127.0.0.1:${fake.address().port}`;
process.env.CURSOR_API_KEY = 'test-key';
process.env.MAX_AGENTS_PER_MISSION = '3';
process.env.PAUSE_MINUTES = '45';
process.env.STALL_MINUTES = '10';

const db = await import('../src/db.js');
const { roomForTask, meterForMission } = await import('../src/state.js');
const { handleEvent } = await import('../src/events.js');
const { decide } = await import('../src/gate.js');

db.init(path.join(os.tmpdir(), `townhall-unit-${Date.now()}.db`));

test('roomForTask maps state → room (blueprint)', () => {
  assert.equal(roomForTask({ status: 'queued', stage: 'build' }), 'lobby');
  assert.equal(roomForTask({ status: 'running', stage: 'crawl' }), 'crawl');
  assert.equal(roomForTask({ status: 'running', stage: 'build' }), 'build');
  assert.equal(roomForTask({ status: 'running', stage: 'test' }), 'test');
  assert.equal(roomForTask({ status: 'waiting_boss', stage: 'test' }), 'boss');
  assert.equal(roomForTask({ status: 'merging', stage: 'test' }), 'boss');
  assert.equal(roomForTask({ status: 'stalled', stage: 'build' }), 'break');
  assert.equal(roomForTask({ status: 'paused', stage: 'build' }), 'break');
  assert.equal(roomForTask({ status: 'failed', stage: 'test' }), 'break');
  assert.equal(roomForTask({ status: 'done', stage: 'test' }), 'archive');
});

test('meterForMission — green/yellow/red per Q9', () => {
  const nowMs = Date.now();
  const mission = { created_at: nowMs - 5 * 60000 };
  const t = (over = {}) => ({ cursor_agent_id: null, verify_status: 'none', verify_red_count: 0, status: 'running', ...over });

  assert.equal(meterForMission(mission, [t()], nowMs), 'green');
  assert.equal(meterForMission({ created_at: nowMs - 31 * 60000 }, [t()], nowMs), 'yellow');
  assert.equal(meterForMission({ created_at: nowMs - 46 * 60000 }, [t()], nowMs), 'red');
  // agent เต็มเพดาน 3 → แดง
  const full = [t({ cursor_agent_id: 'a' }), t({ cursor_agent_id: 'b' }), t({ cursor_agent_id: 'c' })];
  assert.equal(meterForMission(mission, full, nowMs), 'red');
  // verify แดงซ้ำ ≥ 2 → แดง
  assert.equal(meterForMission(mission, [t({ verify_red_count: 2, verify_status: 'red' })], nowMs), 'red');
  // verify แดงครั้งเดียว → เหลือง
  assert.equal(meterForMission(mission, [t({ verify_red_count: 1, verify_status: 'red' })], nowMs), 'yellow');
});

test('mission.created — เกิน 3 subtasks ถูกปฏิเสธ (ต้องถามบอส)', () => {
  const r = handleEvent({
    type: 'mission.created',
    mission: { title: 'too-big', tasks: [{ name: 'a' }, { name: 'b' }, { name: 'c' }, { name: 'd' }] },
  });
  assert.equal(r.ok, false);
  assert.equal(r.error, 'TOO_MANY_TASKS');
});

test('E2E events + hard gate: verify แดง approve ไม่ได้, เขียวแล้ว approve → followup + merging', async () => {
  const created = handleEvent({
    type: 'mission.created',
    mission: { title: 'ES-L: fix gain clamp', topic: 'Easby', tasks: [{ name: 'implement', stage: 'build' }, { name: 'verify', stage: 'test' }] },
  });
  assert.equal(created.ok, true);
  const taskId = created.task_ids[0].task_id;

  const assigned = handleEvent({ type: 'task.assigned', task_id: taskId, cursor_agent_id: 'agent-001', character: 'Ash' });
  assert.equal(assigned.ok, true);
  assert.equal(assigned.character, 'Ash');
  assert.equal(roomForTask(db.getTask(taskId)), 'build');

  // verify แดง → ขอ approve → โดน block ตั้งแต่ event
  handleEvent({ type: 'task.verify_result', task_id: taskId, result: 'red', log_tail: 'assert fail' });
  const reqRed = handleEvent({ type: 'approval.requested', task_id: taskId, pr_url: 'https://github.com/x/pr/1' });
  assert.equal(reqRed.ok, false);
  assert.equal(reqRed.error, 'VERIFY_NOT_GREEN');
  const gateNoPending = await decide({ taskId, decision: 'approved' });
  assert.equal(gateNoPending.ok, false);
  assert.equal(gateNoPending.error, 'NO_PENDING_APPROVAL');

  // เขียวแล้ว → approval pending → approve ผ่าน gate → followup ถูกยิง + task merging
  handleEvent({ type: 'task.verify_result', task_id: taskId, result: 'green' });
  const reqGreen = handleEvent({ type: 'approval.requested', task_id: taskId, pr_url: 'https://github.com/x/pr/1' });
  assert.equal(reqGreen.ok, true);
  assert.equal(db.getTask(taskId).status, 'waiting_boss');

  const before = followups.length;
  const ok = await decide({ taskId, decision: 'approved', via: 'game' });
  assert.equal(ok.ok, true);
  assert.equal(followups.length, before + 1);
  assert.match(followups.at(-1).url, /agent-001\/followup/);
  assert.match(followups.at(-1).body.prompt.text, /approved the merge/i);
  assert.equal(db.getTask(taskId).status, 'merging');
});

test('gate — REJECTED_BY_GATE เมื่อ verify กลับแดงหลังขอ approve', async () => {
  const created = handleEvent({
    type: 'mission.created',
    mission: { title: 'auric-task', topic: 'Auric', tasks: [{ name: 'impl', stage: 'build' }] },
  });
  const taskId = created.task_ids[0].task_id;
  handleEvent({ type: 'task.assigned', task_id: taskId, cursor_agent_id: 'agent-002' });
  handleEvent({ type: 'task.verify_result', task_id: taskId, result: 'green' });
  handleEvent({ type: 'approval.requested', task_id: taskId });
  // verify พังทีหลัง (เช่น มี commit ใหม่) — gate ต้องกันตอนกดจริง
  handleEvent({ type: 'task.verify_result', task_id: taskId, result: 'red' });
  const r = await decide({ taskId, decision: 'approved' });
  assert.equal(r.ok, false);
  assert.equal(r.error, 'REJECTED_BY_GATE');
});

test('spawn cap — agent ตัวที่ 4 ใน mission เดียวถูก block', () => {
  const created = handleEvent({
    type: 'mission.created',
    mission: { title: 'big-mission', tasks: [{ name: 't1' }, { name: 't2' }, { name: 't3' }] },
  });
  const ids = created.task_ids.map((t) => t.task_id);
  handleEvent({ type: 'task.assigned', task_id: ids[0], cursor_agent_id: 'sp-1' });
  handleEvent({ type: 'task.assigned', task_id: ids[1], cursor_agent_id: 'sp-2' });
  handleEvent({ type: 'task.assigned', task_id: ids[2], cursor_agent_id: 'sp-3' });
  // มี task โผล่เพิ่ม (Hermes พลาด) — พยายาม assign ตัวที่ 4
  const extra = db.createTask({ mission_id: created.mission_id, name: 'extra' });
  const r = handleEvent({ type: 'task.assigned', task_id: extra.id, cursor_agent_id: 'sp-4' });
  assert.equal(r.ok, false);
  assert.equal(r.error, 'SPAWN_CAP');
});

test('task.assigned — local-only character ห้ามผูก Cursor agent', () => {
  const created = handleEvent({
    type: 'mission.created',
    mission: { title: 'insurance-local', tasks: [{ name: 'premium-calc' }] },
  });
  const taskId = created.task_ids[0].task_id;
  handleEvent({ type: 'task.assigned', task_id: taskId, character: 'Nuiny' });
  const nuiny = db.listCharacters().find((c) => c.name === 'Nuiny');
  db.updateCharacter(nuiny.id, { locked_local_only: 1 });
  const r = handleEvent({
    type: 'task.assigned', task_id: taskId, cursor_agent_id: 'cloud-agent-99', character: 'Nuiny',
  });
  assert.equal(r.ok, false);
  assert.equal(r.error, 'LOCAL_ONLY_VIOLATION');
  assert.equal(db.getTask(taskId).cursor_agent_id, null);
});

test('parsePrUrl + poller CI override — Hermes เขียวแต่ GitHub CI แดง → downgrade', async () => {
  const { parsePrUrl } = await import('../src/github.js');
  assert.deepEqual(parsePrUrl('https://github.com/acme/repo/pull/42'), { owner: 'acme', repo: 'repo', pullNumber: 42 });

  const created = handleEvent({
    type: 'mission.created',
    mission: { title: 'ci-check', tasks: [{ name: 'impl' }] },
  });
  const taskId = created.task_ids[0].task_id;
  handleEvent({ type: 'task.assigned', task_id: taskId, cursor_agent_id: 'agent-ci' });
  handleEvent({ type: 'task.verify_result', task_id: taskId, result: 'green' });
  db.updateTask(taskId, { pr_url: 'https://github.com/acme/repo/pull/1' });

  process.env.GITHUB_API_BASE = `http://127.0.0.1:${fake.address().port}`;
  const { tick } = await import('../src/poller.js');
  await tick();
  assert.equal(db.getTask(taskId).verify_status, 'red');
});

test('reject → agent กลับไปแก้ (build) + followup มี note', async () => {
  const created = handleEvent({
    type: 'mission.created',
    mission: { title: 'reject-flow', tasks: [{ name: 'impl' }] },
  });
  const taskId = created.task_ids[0].task_id;
  handleEvent({ type: 'task.assigned', task_id: taskId, cursor_agent_id: 'agent-003' });
  handleEvent({ type: 'task.verify_result', task_id: taskId, result: 'green' });
  handleEvent({ type: 'approval.requested', task_id: taskId });
  const r = await decide({ taskId, decision: 'rejected', note: 'ขอ clamp แบบ soft-knee' });
  assert.equal(r.ok, true);
  const task = db.getTask(taskId);
  assert.equal(task.status, 'running');
  assert.equal(task.stage, 'build');
  assert.match(followups.at(-1).body.prompt.text, /soft-knee/);
});

test.after(() => fake.close());
