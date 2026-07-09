import * as db from './db.js';
import { cfg } from './config.js';
import { changed, notify } from './bus.js';

const ACTIVE_TASK = ['queued', 'running', 'stalled', 'paused'];

function resolveMission(m = {}) {
  if (m.mission_id) return db.getMission(m.mission_id);
  if (m.mission_title) return db.findMissionByTitle(m.mission_title);
  return null;
}

function resolveTask(p = {}) {
  if (p.task_id) return db.getTask(p.task_id);
  if (p.cursor_agent_id) {
    const t = db.findTaskByAgent(p.cursor_agent_id);
    if (t) return t;
  }
  const mission = resolveMission(p);
  if (mission && p.name) return db.findTaskByName(mission.id, p.name);
  return null;
}

// รับ event จาก Hermes (และ poller ภายใน) — tolerant ต่อ field ที่ LLM ส่งมาไม่ครบ
export function handleEvent(evt) {
  const c = cfg();
  const type = evt?.type;
  if (!type) return { ok: false, status: 400, error: 'MISSING_TYPE' };
  const source = evt.source || 'hermes';

  switch (type) {
    case 'mission.created': {
      const m = evt.mission || {};
      if (!m.title) return { ok: false, status: 400, error: 'MISSING_TITLE' };
      const wanted = Array.isArray(m.tasks) && m.tasks.length ? m.tasks : [{ name: m.title, stage: 'build' }];
      if (wanted.length > c.maxAgentsPerMission) {
        db.logEvent({ source, type: 'mission.rejected', payload: { title: m.title, reason: 'TOO_MANY_TASKS' } });
        notify(`🚫 Hermes เสนอ ${wanted.length} subtasks สำหรับ "${m.title}" — เกินเพดาน ${c.maxAgentsPerMission} ต้องถามบอสก่อน`, m.topic);
        return {
          ok: false, status: 400, error: 'TOO_MANY_TASKS',
          detail: `max ${c.maxAgentsPerMission} subtasks per mission — re-plan or ask the boss`,
        };
      }
      const mission = db.createMission({ title: m.title, source: m.source || 'telegram', topic: m.topic || null });
      const tasks = wanted.map((t) => db.createTask({
        mission_id: mission.id, name: t.name || 'task', stage: t.stage || 'build',
      }));
      db.updateMission(mission.id, { status: 'running' });
      db.logEvent({ source, type, mission_id: mission.id, payload: m });
      changed(type);
      return { ok: true, mission_id: mission.id, task_ids: tasks.map((t) => ({ task_id: t.id, name: t.name })) };
    }

    case 'task.assigned': {
      const task = resolveTask(evt);
      if (!task) return { ok: false, status: 404, error: 'TASK_NOT_FOUND' };
      if (!task.cursor_agent_id && evt.cursor_agent_id) {
        const assigned = db.countAssigned(task.mission_id);
        if (assigned >= c.maxAgentsPerMission) {
          db.logEvent({ source, type: 'task.spawn_blocked', mission_id: task.mission_id, task_id: task.id });
          notify(`🚫 spawn เกินเพดาน ${c.maxAgentsPerMission} ตัว/mission — task "${task.name}" ถูก block`, null);
          return { ok: false, status: 409, error: 'SPAWN_CAP', detail: `max ${c.maxAgentsPerMission} agents per mission` };
        }
      }
      const character = db.getOrCreateCharacter(evt.character);
      db.updateTask(task.id, {
        cursor_agent_id: evt.cursor_agent_id || task.cursor_agent_id,
        character_id: character.id,
        status: 'running',
        branch: evt.branch || task.branch,
        started_at: task.started_at || db.now(),
        last_event_at: db.now(),
      });
      const mission = db.getMission(task.mission_id);
      if (mission && mission.status === 'planning') db.updateMission(mission.id, { status: 'running' });
      db.logEvent({ source, type, mission_id: task.mission_id, task_id: task.id, payload: evt });
      changed(type);
      return { ok: true, task_id: task.id, character: character.name };
    }

    case 'task.stage_changed': {
      const task = resolveTask(evt);
      if (!task) return { ok: false, status: 404, error: 'TASK_NOT_FOUND' };
      db.updateTask(task.id, {
        stage: evt.stage || task.stage,
        status: task.status === 'stalled' ? 'running' : task.status,
        last_event_at: db.now(),
      });
      db.logEvent({ source, type, mission_id: task.mission_id, task_id: task.id, payload: evt });
      changed(type);
      return { ok: true, task_id: task.id };
    }

    case 'task.verify_result': {
      const task = resolveTask(evt);
      if (!task) return { ok: false, status: 404, error: 'TASK_NOT_FOUND' };
      const result = evt.result === 'green' ? 'green' : 'red';
      const redCount = result === 'red' ? (task.verify_red_count || 0) + 1 : task.verify_red_count;
      db.updateTask(task.id, {
        verify_status: result,
        verify_red_count: redCount,
        stage: 'test',
        status: task.status === 'stalled' ? 'running' : (result === 'red' && task.status === 'waiting_boss' ? 'running' : task.status),
        last_event_at: db.now(),
      });
      db.logEvent({ source, type, mission_id: task.mission_id, task_id: task.id, payload: evt });
      if (result === 'red' && redCount >= 2) {
        notify(`🔴 verify แดงครั้งที่ ${redCount} — "${task.name}" อาจต้องให้บอสช่วยดู (เปิด Cursor IDE)`, null);
      }
      changed(type);
      return { ok: true, task_id: task.id, verify: result };
    }

    case 'approval.requested': {
      const task = resolveTask(evt);
      if (!task) return { ok: false, status: 404, error: 'TASK_NOT_FOUND' };
      db.updateTask(task.id, {
        pr_url: evt.pr_url || task.pr_url,
        branch: evt.branch || task.branch,
        last_event_at: db.now(),
      });
      const fresh = db.getTask(task.id);
      db.logEvent({ source, type, mission_id: task.mission_id, task_id: task.id, payload: evt });
      if (fresh.verify_status !== 'green') {
        notify(`🚫 "${task.name}" ขอ merge แต่ verify ยังไม่เขียว — ถูก block โดย gate (ต้องแก้ให้ผ่านก่อน)`, null);
        changed(type);
        return { ok: false, status: 409, error: 'VERIFY_NOT_GREEN', detail: 'run ./verify.sh until green, then request again' };
      }
      if (!db.latestPendingApprovalForTask(task.id)) {
        db.createApproval({ task_id: task.id, verify_status_at_request: fresh.verify_status });
      }
      db.updateTask(task.id, { status: 'waiting_boss' });
      const mission = db.getMission(task.mission_id);
      notify(`❗ รออนุมัติ merge — ${mission?.title || ''} / ${task.name}${fresh.pr_url ? `\n${fresh.pr_url}` : ''}`, mission?.topic);
      changed(type);
      return { ok: true, task_id: task.id, waiting: 'boss' };
    }

    case 'mission.report': {
      const mission = resolveMission(evt) || resolveMission(evt.mission || {});
      if (!mission) return { ok: false, status: 404, error: 'MISSION_NOT_FOUND' };
      const tasks = db.listTasksByMission(mission.id);
      const allDone = tasks.length > 0 && tasks.every((t) => ['done', 'cancelled', 'failed'].includes(t.status));
      db.updateMission(mission.id, { summary: evt.summary || mission.summary, status: allDone ? 'done' : mission.status });
      db.logEvent({ source, type, mission_id: mission.id, payload: evt });
      changed(type);
      return { ok: true, mission_id: mission.id, closed: allDone };
    }

    case 'task.done': {
      const task = resolveTask(evt);
      if (!task) return { ok: false, status: 404, error: 'TASK_NOT_FOUND' };
      db.updateTask(task.id, { status: 'done', last_event_at: db.now() });
      db.logEvent({ source, type, mission_id: task.mission_id, task_id: task.id, payload: evt });
      maybeCloseMission(task.mission_id);
      changed(type);
      return { ok: true, task_id: task.id };
    }

    case 'mission.cancelled': {
      const mission = resolveMission(evt);
      if (!mission) return { ok: false, status: 404, error: 'MISSION_NOT_FOUND' };
      db.updateMission(mission.id, { status: 'cancelled' });
      db.listTasksByMission(mission.id).forEach((t) => {
        if (ACTIVE_TASK.includes(t.status)) db.updateTask(t.id, { status: 'cancelled' });
      });
      db.logEvent({ source, type, mission_id: mission.id, payload: evt });
      changed(type);
      return { ok: true, mission_id: mission.id };
    }

    default: {
      // เก็บ event แปลกๆ ไว้ debug โปรโตคอลฝั่ง Hermes — ไม่ตีตก
      db.logEvent({ source, type, payload: evt });
      changed(type);
      return { ok: true, note: 'logged (unknown type)' };
    }
  }
}

export function maybeCloseMission(missionId) {
  const tasks = db.listTasksByMission(missionId);
  if (tasks.length && tasks.every((t) => ['done', 'cancelled', 'failed'].includes(t.status))) {
    const mission = db.getMission(missionId);
    if (mission && !['done', 'cancelled'].includes(mission.status)) {
      db.updateMission(missionId, { status: 'done' });
    }
  }
}
