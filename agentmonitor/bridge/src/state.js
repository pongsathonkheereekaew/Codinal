import * as db from './db.js';
import { cfg } from './config.js';

// ห้องในเกม — ตัวละครย้ายห้องตาม state จริง ไม่ใช่ animation ล้วน
// server | crawl | test | break | build | archive | lobby | boss
export function roomForTask(t) {
  if (!t) return 'lobby';
  if (t.status === 'done' || t.status === 'cancelled') return 'archive';
  if (t.status === 'waiting_boss' || t.status === 'merging') return 'boss';
  if (t.status === 'stalled' || t.status === 'paused' || t.status === 'failed') return 'break';
  if (t.status === 'queued') return 'lobby';
  const byStage = { crawl: 'crawl', build: 'build', test: 'test' };
  return byStage[t.stage] || 'build';
}

// meter ต่อ mission (Q9): เขียว < 30 นาที, เหลือง 30–45 หรือใช้ agent เกือบเต็ม,
// แดง ≥ 45 นาที / agent เต็ม / verify แดงซ้ำ
export function meterForMission(mission, tasks, nowMs = Date.now()) {
  const c = cfg();
  const elapsedMin = (nowMs - mission.created_at) / 60000;
  const assigned = tasks.filter((t) => t.cursor_agent_id).length;
  const redTwice = tasks.some((t) => t.verify_red_count >= 2 && t.status !== 'done');
  const redOnce = tasks.some((t) => t.verify_status === 'red' && t.status !== 'done');

  if (elapsedMin >= c.pauseMinutes || assigned >= c.maxAgentsPerMission || redTwice) return 'red';
  if (elapsedMin >= 30 || assigned >= c.maxAgentsPerMission - 1 || redOnce) return 'yellow';
  return 'green';
}

export function getState() {
  const c = cfg();
  const nowMs = Date.now();
  const missions = db.listMissions(30);
  const characters = db.listCharacters();
  const charById = new Map(characters.map((ch) => [ch.id, ch]));

  const missionViews = missions.map((m) => {
    const tasks = db.listTasksByMission(m.id);
    return {
      ...m,
      meter: meterForMission(m, tasks, nowMs),
      elapsed_ms: nowMs - m.created_at,
      agents_used: tasks.filter((t) => t.cursor_agent_id).length,
      max_agents: c.maxAgentsPerMission,
      task_count: tasks.length,
    };
  });
  const missionById = new Map(missionViews.map((m) => [m.id, m]));

  const tasks = db.listTasks(200).map((t) => ({
    ...t,
    room: roomForTask(t),
    character: charById.get(t.character_id)?.name || null,
    mission_title: missionById.get(t.mission_id)?.title || null,
  }));
  const taskById = new Map(tasks.map((t) => [t.id, t]));

  const approvals = db.listPendingApprovals().map((a) => {
    const t = taskById.get(a.task_id) || db.getTask(a.task_id);
    return {
      ...a,
      task_name: t?.name || null,
      mission_id: t?.mission_id || null,
      mission_title: t ? missionById.get(t.mission_id)?.title : null,
      pr_url: t?.pr_url || null,
      current_verify: t?.verify_status || 'none',
      character: t?.character_id ? charById.get(t.character_id)?.name : null,
    };
  });

  const events = db.listEvents(30).map((e) => ({
    ...e,
    payload: e.payload ? JSON.parse(e.payload) : null,
  }));

  return {
    characters,
    missions: missionViews,
    tasks,
    approvals,
    health: db.listHealth(),
    events,
    config: {
      topics: Object.keys(c.topics),
      stall_minutes: c.stallMinutes,
      pause_minutes: c.pauseMinutes,
      max_agents: c.maxAgentsPerMission,
    },
  };
}
