import { cfg } from './config.js';

// Cursor Background Agents API — ใช้ poll สถานะ (ground truth) + followup ตอน approve/pause
async function req(method, path, body) {
  const { cursorApiBase, cursorApiKey } = cfg();
  if (!cursorApiKey) {
    throw Object.assign(new Error('CURSOR_API_KEY not set'), { code: 'NO_KEY' });
  }
  const res = await fetch(cursorApiBase + path, {
    method,
    headers: {
      Authorization: `Bearer ${cursorApiKey}`,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(15000),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw Object.assign(new Error(`cursor api ${res.status}`), { status: res.status, body: text.slice(0, 300) });
  }
  return res.json().catch(() => ({}));
}

export const me = () => req('GET', '/v0/me');
export const listAgents = (limit = 50) => req('GET', `/v0/agents?limit=${limit}`);
export const getAgent = (id) => req('GET', `/v0/agents/${encodeURIComponent(id)}`);
export const followup = (id, text) =>
  req('POST', `/v0/agents/${encodeURIComponent(id)}/followup`, { prompt: { text } });

export const FOLLOWUP_TEXT = {
  approve: '✅ Boss approved the merge. Merge the PR now (follow repo convention, e.g. squash), confirm the merge landed, then reply with a one-line result summary.',
  reject: (note) => `❌ Boss rejected the merge${note ? `: ${note}` : ''}. Return to implementation, address the feedback, re-run ./verify.sh, and request approval again when green.`,
  pause: (minutes) => `⏸ Boss timeout (${minutes} min) — pause work: stop making changes, commit/push current progress to the branch, and reply with a short status summary. Wait for further instructions.`,
  resume: '▶️ Boss says continue the mission.',
  cancel: '🛑 Boss cancelled this mission. Stop work, push any WIP to the branch for the record, and reply with final status.',
};
