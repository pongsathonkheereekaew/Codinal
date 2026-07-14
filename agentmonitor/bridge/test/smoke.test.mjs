import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';

// fake Cursor API
const fake = http.createServer((req, res) => {
  res.setHeader('Content-Type', 'application/json');
  if (req.method === 'POST' && /followup/.test(req.url)) return req.resume(), req.on('end', () => res.end('{"id":"ok"}'));
  if (req.method === 'GET' && /\/v0\/agents\//.test(req.url)) return res.end(JSON.stringify({ id: 'x', status: 'RUNNING' }));
  res.end('{"agents":[]}');
});
await new Promise((r) => fake.listen(0, '127.0.0.1', r));

process.env.CURSOR_API_BASE = `http://127.0.0.1:${fake.address().port}`;
process.env.CURSOR_API_KEY = 'test-key';
process.env.INTAKE_MODE = 'notify'; // ยังไม่ config intake — ต้องได้ 501 ชัดๆ ไม่ใช่พัง

const db = await import('../src/db.js');
const { createApp } = await import('../src/server.js');

db.init(path.join(os.tmpdir(), `townhall-smoke-${Date.now()}.db`));
const server = http.createServer(createApp());
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;

async function call(method, p, body) {
  const res = await fetch(base + p, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  return { status: res.status, data: await res.json().catch(() => ({})) };
}

test('healthz + empty state', async () => {
  assert.equal((await call('GET', '/healthz')).data.ok, true);
  const { data } = await call('GET', '/api/state');
  assert.deepEqual(data.missions, []);
  assert.equal(data.config.max_agents, 3);
});

test('full mission flow over HTTP — events → rooms → gate → approve', async () => {
  // 1. Hermes ลงทะเบียน mission
  const created = await call('POST', '/api/events', {
    source: 'hermes',
    type: 'mission.created',
    mission: { title: 'ES-Q: soft clip curve', topic: 'Easby', tasks: [{ name: 'implement', stage: 'build' }] },
  });
  assert.equal(created.status, 200);
  const taskId = created.data.task_ids[0].task_id;

  // 2. ผูก cursor agent → ตัวละครเข้าห้อง build
  await call('POST', '/api/events', { type: 'task.assigned', task_id: taskId, cursor_agent_id: 'smoke-agent', character: 'Bee' });
  let state = (await call('GET', '/api/state')).data;
  let task = state.tasks.find((t) => t.id === taskId);
  assert.equal(task.room, 'build');
  assert.equal(task.character, 'Bee');

  // 3. verify แดง → approve ต้องโดน gate (409)
  await call('POST', '/api/events', { type: 'task.verify_result', task_id: taskId, result: 'red' });
  const blockedReq = await call('POST', '/api/events', { type: 'approval.requested', task_id: taskId });
  assert.equal(blockedReq.status, 409);
  const gateBlock = await call('POST', '/api/approve', { task_id: taskId, decision: 'approved' });
  assert.equal(gateBlock.status, 404); // ไม่มี approval pending เพราะโดน block ตั้งแต่ขอ

  // 4. verify เขียว → ขอ approve → state เห็น waiting_boss + approval โผล่
  await call('POST', '/api/events', { type: 'task.verify_result', task_id: taskId, result: 'green' });
  await call('POST', '/api/events', { type: 'approval.requested', task_id: taskId, pr_url: 'https://github.com/x/pr/9' });
  state = (await call('GET', '/api/state')).data;
  task = state.tasks.find((t) => t.id === taskId);
  assert.equal(task.room, 'boss');
  assert.equal(state.approvals.length, 1);
  assert.equal(state.approvals[0].current_verify, 'green');

  // 5. บอสกด approve → merging
  const approved = await call('POST', '/api/approve', { approval_id: state.approvals[0].id, decision: 'approved' });
  assert.equal(approved.status, 200);
  state = (await call('GET', '/api/state')).data;
  assert.equal(state.tasks.find((t) => t.id === taskId).status, 'merging');

  // 6. task จบ → mission ปิด → archive
  await call('POST', '/api/events', { type: 'task.done', task_id: taskId });
  await call('POST', '/api/events', { type: 'mission.report', mission_id: created.data.mission_id, summary: 'merged fine' });
  state = (await call('GET', '/api/state')).data;
  assert.equal(state.missions.find((m) => m.id === created.data.mission_id).status, 'done');
  assert.equal(state.tasks.find((t) => t.id === taskId).room, 'archive');
});

test('command endpoint — 501 พร้อม hint เมื่อ intake ยังไม่ config', async () => {
  const r = await call('POST', '/api/command', { text: 'ES-L: test command', topic: 'Easby' });
  assert.equal(r.status, 501);
  assert.equal(r.data.error, 'INTAKE_NOT_CONFIGURED');
  assert.ok(r.data.hint);
});

test('resume / cancel mission endpoints', async () => {
  const created = await call('POST', '/api/events', {
    type: 'mission.created', mission: { title: 'pause-flow', tasks: [{ name: 'x' }] },
  });
  const mid = created.data.mission_id;
  const resumed = await call('POST', `/api/missions/${mid}/resume`);
  assert.equal(resumed.status, 200);
  const cancelled = await call('POST', `/api/missions/${mid}/cancel`);
  assert.equal(cancelled.status, 200);
  const state = (await call('GET', '/api/state')).data;
  assert.equal(state.missions.find((m) => m.id === mid).status, 'cancelled');
});

test('characters — archive + local-only toggle + assign block (Q5/Q6)', async () => {
  const state = (await call('GET', '/api/state')).data;
  const bee = state.characters.find((c) => c.name === 'Bee');
  assert.ok(bee);
  await call('POST', `/api/characters/${bee.id}/local-only`, { value: true });
  let after = (await call('GET', '/api/state')).data;
  assert.equal(after.characters.find((c) => c.id === bee.id).locked_local_only, 1);

  const created = await call('POST', '/api/events', {
    type: 'mission.created', mission: { title: 'locked-char', tasks: [{ name: 'secret' }] },
  });
  const taskId = created.data.task_ids[0].task_id;
  const blocked = await call('POST', '/api/events', {
    type: 'task.assigned', task_id: taskId, cursor_agent_id: 'blocked-agent', character: 'Bee',
  });
  assert.equal(blocked.status, 409);
  assert.equal(blocked.data.error, 'LOCAL_ONLY_VIOLATION');

  await call('POST', `/api/characters/${bee.id}/archive`, {});
  after = (await call('GET', '/api/state')).data;
  assert.equal(after.characters.find((c) => c.id === bee.id), undefined);
});

test('unknown event type — เก็บ log ไม่ตีตก (LLM tolerance)', async () => {
  const r = await call('POST', '/api/events', { type: 'hermes.custom_ping', hello: 1 });
  assert.equal(r.status, 200);
});

test.after(() => { server.close(); fake.close(); });
