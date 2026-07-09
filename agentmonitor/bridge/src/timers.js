import * as db from './db.js';
import * as cursor from './cursor.js';
import { cfg } from './config.js';
import { changed, notify } from './bus.js';

// Resilience (Q4) + budget (Q9): stalled 10 นาที, auto pause 45 นาที
let timer = null;

async function bestEffortFollowup(task, text) {
  if (!task.cursor_agent_id) return;
  try { await cursor.followup(task.cursor_agent_id, text); } catch { /* best effort — ไม่ block */ }
}

export async function tick(nowMs = Date.now()) {
  const c = cfg();
  let anyChange = false;

  // stalled — งานที่ run อยู่แต่เงียบเกิน N นาที
  for (const task of db.listTasksByStatus(['running'])) {
    const last = task.last_event_at || task.started_at;
    if (last && nowMs - last > c.stallMinutes * 60000) {
      db.updateTask(task.id, { status: 'stalled' });
      db.logEvent({ source: 'bridge', type: 'task.stalled', mission_id: task.mission_id, task_id: task.id });
      notify(`💤 "${task.name}" เงียบเกิน ${c.stallMinutes} นาที — เช็คในเกม หรือเปิด Cursor ดู`, null);
      anyChange = true;
    }
  }

  // auto pause — mission อายุเกิน N นาที (Q9: auto pause + ถามบอส)
  for (const mission of db.listMissionsByStatus(['planning', 'running'])) {
    if (mission.paused_notified) continue;
    if (nowMs - mission.created_at > c.pauseMinutes * 60000) {
      db.updateMission(mission.id, { status: 'paused', paused_notified: 1 });
      for (const task of db.listTasksByMission(mission.id)) {
        if (['queued', 'running', 'stalled'].includes(task.status)) {
          db.updateTask(task.id, { status: 'paused' });
          await bestEffortFollowup(task, cursor.FOLLOWUP_TEXT.pause(c.pauseMinutes));
        }
      }
      db.logEvent({ source: 'bridge', type: 'mission.auto_paused', mission_id: mission.id });
      notify(`⏸ mission "${mission.title}" เกิน ${c.pauseMinutes} นาที — auto pause แล้ว กด Continue ในเกมถ้าจะไปต่อ`, mission.topic);
      anyChange = true;
    }
  }

  if (anyChange) changed('timers');
}

export async function resumeMission(missionId, via = 'game') {
  const mission = db.getMission(missionId);
  if (!mission) return { ok: false, status: 404, error: 'MISSION_NOT_FOUND' };
  // รีสตาร์ทนาฬิกา budget — ถือว่าบอสให้เวลาเพิ่มอีกรอบ
  db.updateMission(missionId, { status: 'running', paused_notified: 0, created_at: db.now() });
  for (const task of db.listTasksByMission(missionId)) {
    if (task.status === 'paused' || task.status === 'stalled') {
      db.updateTask(task.id, { status: 'running', last_event_at: db.now() });
      await bestEffortFollowup(task, cursor.FOLLOWUP_TEXT.resume);
    }
  }
  db.logEvent({ source: 'bridge', type: 'mission.resumed', mission_id: missionId, payload: { via } });
  notify(`▶️ mission "${mission.title}" ไปต่อ (${via})`, mission.topic);
  changed('mission.resumed');
  return { ok: true, mission_id: missionId };
}

export async function cancelMission(missionId, via = 'game') {
  const mission = db.getMission(missionId);
  if (!mission) return { ok: false, status: 404, error: 'MISSION_NOT_FOUND' };
  db.updateMission(missionId, { status: 'cancelled' });
  for (const task of db.listTasksByMission(missionId)) {
    if (!['done', 'cancelled', 'failed'].includes(task.status)) {
      db.updateTask(task.id, { status: 'cancelled', last_event_at: db.now() });
      await bestEffortFollowup(task, cursor.FOLLOWUP_TEXT.cancel);
    }
  }
  db.logEvent({ source: 'bridge', type: 'mission.cancelled', mission_id: missionId, payload: { via } });
  notify(`🛑 ยกเลิก mission "${mission.title}" (${via})`, mission.topic);
  changed('mission.cancelled');
  return { ok: true, mission_id: missionId };
}

export function start() {
  timer = setInterval(() => tick().catch((e) => console.warn('[timers]', e.message)), 30000);
  timer.unref?.();
}

export function stop() { if (timer) clearInterval(timer); }
