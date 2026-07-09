import * as db from './db.js';
import * as cursor from './cursor.js';
import { changed, notify } from './bus.js';
import { maybeCloseMission } from './events.js';

// Hard gate (Q2/Q8): approve merge ได้เฉพาะ verify เขียว — ไม่มี flag ข้าม gate โดยเจตนา
export async function decide({ approvalId, taskId, decision, note = '', via = 'game' }) {
  const approval = approvalId
    ? db.getApproval(approvalId)
    : (taskId ? db.latestPendingApprovalForTask(taskId) : null);
  if (!approval) return { ok: false, status: 404, error: 'NO_PENDING_APPROVAL' };
  if (approval.decided) return { ok: false, status: 409, error: 'ALREADY_DECIDED', decided: approval.decided };

  const task = db.getTask(approval.task_id);
  if (!task) return { ok: false, status: 404, error: 'TASK_NOT_FOUND' };

  if (decision === 'approved') {
    if (task.verify_status !== 'green') {
      db.logEvent({
        source: 'bridge', type: 'approve.rejected_by_gate',
        mission_id: task.mission_id, task_id: task.id,
        payload: { verify_status: task.verify_status, via },
      });
      changed('approve.rejected_by_gate');
      return {
        ok: false, status: 409, error: 'REJECTED_BY_GATE',
        detail: `verify_status is "${task.verify_status}" — ./verify.sh must be green before merge`,
      };
    }
    if (!task.cursor_agent_id) {
      return { ok: false, status: 422, error: 'NO_AGENT_ATTACHED', detail: 'task has no cursor agent to send the merge followup to' };
    }
    try {
      await cursor.followup(task.cursor_agent_id, cursor.FOLLOWUP_TEXT.approve);
    } catch (e) {
      return { ok: false, status: 502, error: 'CURSOR_API_ERROR', detail: e.message };
    }
    db.updateApproval(approval.id, { decided: 'approved', decided_via: via, decided_at: db.now(), note });
    db.updateTask(task.id, { status: 'merging', last_event_at: db.now() });
    db.logEvent({ source: 'bridge', type: 'approve.approved', mission_id: task.mission_id, task_id: task.id, payload: { via } });
    notify(`🔀 อนุมัติ merge แล้ว (${via}) — "${task.name}" กำลัง merge`, null);
    changed('approval.decided');
    return { ok: true, decision: 'approved', task_id: task.id };
  }

  // reject — ส่ง note กลับให้ agent แก้ต่อ
  if (task.cursor_agent_id) {
    try {
      await cursor.followup(task.cursor_agent_id, cursor.FOLLOWUP_TEXT.reject(note));
    } catch (e) {
      return { ok: false, status: 502, error: 'CURSOR_API_ERROR', detail: e.message };
    }
  }
  db.updateApproval(approval.id, { decided: 'rejected', decided_via: via, decided_at: db.now(), note });
  db.updateTask(task.id, { status: 'running', stage: 'build', last_event_at: db.now() });
  db.logEvent({ source: 'bridge', type: 'approve.rejected', mission_id: task.mission_id, task_id: task.id, payload: { via, note } });
  notify(`↩️ ปฏิเสธ merge — "${task.name}" กลับไปแก้ต่อ${note ? ` (${note})` : ''}`, null);
  changed('approval.decided');
  return { ok: true, decision: 'rejected', task_id: task.id };
}

export { maybeCloseMission };
