import * as db from './db.js';
import * as cursor from './cursor.js';
import { cfg } from './config.js';
import { changed, notify } from './bus.js';
import { maybeCloseMission } from './events.js';

// Poller = ground truth (Q5: git/สถานะจริงชนะแชท) — event จาก Hermes เป็นตัวเสริม
// ถ้า Hermes ลืมรายงาน agent ตัวไหน poller จะเจอและ adopt เข้าระบบเอง
let timer = null;
let tickCount = 0;

const TERMINAL = ['done', 'cancelled', 'failed'];

function applyCursorStatus(task, agent) {
  const status = agent?.status;
  if (!status || status === task.cursor_status) return false;

  const fields = { cursor_status: status, last_event_at: db.now() };
  if (agent?.target?.prUrl && !task.pr_url) fields.pr_url = agent.target.prUrl;
  if (agent?.target?.branchName && !task.branch) fields.branch = agent.target.branchName;

  if (status === 'RUNNING' && task.status === 'queued') fields.status = 'running';
  if (status === 'FINISHED' && task.status === 'merging') fields.status = 'done';
  if ((status === 'ERROR' || status === 'EXPIRED') && !TERMINAL.includes(task.status)) {
    fields.status = 'failed';
    notify(`🔴 Cursor agent ล้ม (${status}) — "${task.name}" ต้องสั่งใหม่หรือแก้มือ (Cursor IDE)`, null);
  }

  db.updateTask(task.id, fields);
  db.logEvent({
    source: 'poller', type: 'cursor.status_changed',
    mission_id: task.mission_id, task_id: task.id,
    payload: { from: task.cursor_status, to: status },
  });
  if (fields.status === 'done') {
    notify(`✅ merge เสร็จ — "${task.name}"`, null);
    maybeCloseMission(task.mission_id);
  }
  return true;
}

async function adoptUntracked() {
  const res = await cursor.listAgents(50);
  const agents = res.agents || res.items || (Array.isArray(res) ? res : []);
  let adopted = 0;
  for (const agent of agents) {
    if (!agent?.id || db.findTaskByAgent(agent.id)) continue;
    if (['FINISHED', 'ERROR', 'EXPIRED'].includes(agent.status)) continue; // ไม่เก็บซาก agent เก่าก่อนติดตั้ง bridge
    let mission = db.findMissionByTitle('(untracked)');
    if (!mission) mission = db.createMission({ title: '(untracked)', source: 'poller' });
    const task = db.createTask({ mission_id: mission.id, name: agent.name || agent.id, stage: 'build' });
    const character = db.getOrCreateCharacter();
    db.updateTask(task.id, {
      cursor_agent_id: agent.id, cursor_status: agent.status,
      character_id: character.id, status: 'running',
      started_at: db.now(), last_event_at: db.now(),
    });
    db.logEvent({ source: 'poller', type: 'task.adopted', mission_id: mission.id, task_id: task.id, payload: { agent_id: agent.id } });
    adopted += 1;
  }
  if (adopted) {
    notify(`👀 พบ Cursor agent ที่ Hermes ไม่ได้รายงาน ${adopted} ตัว — adopt เข้า mission "(untracked)" แล้ว`, null);
    changed('task.adopted');
  }
}

export async function tick() {
  const c = cfg();
  if (!c.cursorApiKey) {
    db.setHealth('cursor_api', 'disabled', 'CURSOR_API_KEY not set');
    return;
  }
  tickCount += 1;
  let anyChange = false;
  let apiOk = true;

  for (const task of db.listActiveAgentTasks()) {
    try {
      const agent = await cursor.getAgent(task.cursor_agent_id);
      if (applyCursorStatus(task, agent)) anyChange = true;
    } catch (e) {
      if (e.status === 404) {
        db.updateTask(task.id, { cursor_status: 'EXPIRED', status: 'failed', last_event_at: db.now() });
        anyChange = true;
      } else {
        apiOk = false;
      }
    }
  }

  if (apiOk && tickCount % 5 === 1) {
    try { await adoptUntracked(); } catch { apiOk = false; }
  }

  db.setHealth('cursor_api', apiOk ? 'ok' : 'down');
  if (anyChange) changed('poller');
}

export function start() {
  const c = cfg();
  tick().catch((e) => console.warn('[poller]', e.message));
  timer = setInterval(() => tick().catch((e) => console.warn('[poller]', e.message)), c.pollSeconds * 1000);
  timer.unref?.();
}

export function stop() { if (timer) clearInterval(timer); }
