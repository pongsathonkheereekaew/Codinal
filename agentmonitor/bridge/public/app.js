/* AgentMonitor dashboard v0 — render state จาก bridge (monitor + approve + command)
   เกม Phaser (Phase 1) ใช้ WS + endpoint ชุดเดียวกันนี้ */
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (ch) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[ch]));

const STATUS_EMOJI = {
  queued: '⏳', running: '', stalled: '💤', paused: '⏸',
  waiting_boss: '❗', merging: '🔀', failed: '🔴', done: '✅', cancelled: '🚫',
};
const STAGE_EMOJI = { crawl: '🌐', build: '🔨', test: '🧪' };
const ROOMS = ['server', 'crawl', 'test', 'break', 'build', 'archive', 'lobby', 'boss'];

let state = null;

function toast(msg, ms = 3500) {
  const el = $('#toast');
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.hidden = true; }, ms);
}

const TOKEN_KEY = 'am_api_token';

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

function setToken(tok) {
  if (tok) localStorage.setItem(TOKEN_KEY, tok);
  else localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(extra = {}) {
  const h = { ...extra };
  const tok = getToken();
  if (tok) h.Authorization = `Bearer ${tok}`;
  return h;
}

async function api(path, body, retried = false) {
  const res = await fetch(path, {
    method: body ? 'POST' : 'GET',
    headers: authHeaders(body ? { 'Content-Type': 'application/json' } : {}),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && !retried) {
    const entered = prompt('Bridge ต้องการ API token (ค่า API_TOKEN ใน .env):');
    if (entered?.trim()) {
      setToken(entered.trim());
      return api(path, body, true);
    }
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || res.status), { data });
  return data;
}

function fmtElapsed(ms) {
  const m = Math.floor(ms / 60000);
  return m < 60 ? `${m}m` : `${Math.floor(m / 60)}h${m % 60}m`;
}

function chipFor(task) {
  const emoji = STATUS_EMOJI[task.status] ?? '';
  const stage = task.status === 'running' ? (STAGE_EMOJI[task.stage] || '') : '';
  const verify = task.verify_status === 'red' ? ' v-red' : '';
  return `<div class="chip st-${esc(task.status)}${verify}" title="${esc(task.name)} — ${esc(task.status)} / verify: ${esc(task.verify_status)}">
    <span class="who">${esc(task.character || '?')} ${stage}${emoji}</span>
    <small>${esc(task.mission_title || '')}${task.name ? ' · ' + esc(task.name) : ''}</small>
  </div>`;
}

function renderOffice() {
  const byRoom = Object.fromEntries(ROOMS.map((r) => [r, []]));
  const recentDoneCutoff = Date.now() - 24 * 3600 * 1000;

  for (const task of state.tasks) {
    if (task.room === 'archive' && (task.updated_at || 0) < recentDoneCutoff) continue;
    (byRoom[task.room] || byRoom.lobby).push(task);
  }
  // ตัวละครว่างงาน (ไม่มี task active) แสดงใน lobby
  const busy = new Set(state.tasks.filter((t) => !['done', 'cancelled'].includes(t.status)).map((t) => t.character).filter(Boolean));
  const idle = state.characters.filter((c) => !busy.has(c.name));

  for (const room of ROOMS) {
    const el = document.querySelector(`.room[data-room="${room}"] .chips`);
    let html = byRoom[room].map(chipFor).join('');
    if (room === 'lobby') {
      html += idle.map((c) => `<div class="chip" title="idle"><span class="who">${esc(c.name)}${c.locked_local_only ? ' 🔒' : ''}</span><small>ว่าง</small></div>`).join('');
    }
    if (room === 'archive') {
      const doneMissions = state.missions.filter((m) => m.status === 'done').length;
      html += `<div class="chip"><span class="who">🗂 ${doneMissions}</span><small>missions จบแล้ว</small></div>`;
    }
    el.innerHTML = html;
  }

  const hermes = state.health.find((h) => h.component === 'hermes');
  $('#manager-led').className = `manager ${hermes?.status === 'down' ? 'down' : ''}`;
}

function renderApprovals() {
  const el = $('#approvals');
  if (!state.approvals.length) {
    el.innerHTML = '<div style="color:var(--dim);font-size:11px">— ไม่มีงานรออนุมัติ —</div>';
    return;
  }
  el.innerHTML = state.approvals.map((a) => {
    const green = a.current_verify === 'green';
    return `<div class="approval">
      <div class="title">❗ ${esc(a.mission_title || '')} / ${esc(a.task_name || '')}</div>
      <div class="meta">
        ${esc(a.character || '')} · verify: <span class="verify-${green ? 'green' : 'red'}">${esc(a.current_verify)}</span>
        ${a.pr_url ? ` · <a href="${esc(a.pr_url)}" target="_blank">PR ↗</a>` : ''}
      </div>
      <button class="btn small" data-approve="${a.id}" ${green ? '' : 'disabled title="verify ต้องเขียวก่อน (hard gate)"'}>✅ Approve merge</button>
      <button class="btn small ghost" data-reject="${a.id}">↩️ Reject</button>
    </div>`;
  }).join('');
}

function renderMissions() {
  const el = $('#missions');
  const active = state.missions.filter((m) => !['done', 'cancelled'].includes(m.status)).slice(0, 12);
  const recent = state.missions.filter((m) => ['done', 'cancelled'].includes(m.status)).slice(0, 5);
  const row = (m) => `<div class="mission">
    <div class="row">
      <div class="meter ${esc(m.meter)}" title="meter: ${esc(m.meter)}"></div>
      <div class="title">${esc(m.title)}</div>
      <span style="color:var(--dim);font-size:10px">${esc(m.status)} · ${fmtElapsed(m.elapsed_ms)} · 🤖${m.agents_used}/${m.max_agents}</span>
      ${m.status === 'paused' ? `<button class="btn small" data-resume="${m.id}">▶️</button>` : ''}
      ${['planning', 'running', 'paused'].includes(m.status) ? `<button class="btn small danger" data-cancel="${m.id}">🛑</button>` : ''}
    </div>
    ${m.summary ? `<div class="meta">${esc(m.summary).slice(0, 160)}</div>` : ''}
  </div>`;
  el.innerHTML = (active.map(row).join('') || '<div style="color:var(--dim);font-size:11px">— ยังไม่มี mission — พิมพ์สั่งใน Telegram หรือช่องด้านล่าง —</div>')
    + (recent.length ? `<div style="margin-top:6px;color:var(--dim);font-size:10px">ล่าสุด:</div>${recent.map(row).join('')}` : '');
}

function renderHealth() {
  $('#health-leds').innerHTML = state.health.map((h) =>
    `<span class="led ${esc(h.status)}" title="${esc(h.detail || '')}">${esc(h.component)}</span>`
  ).join('');
}

function renderLog() {
  $('#log').innerHTML = state.events.map((e) => {
    const t = new Date(e.ts).toLocaleTimeString('th-TH', { hour12: false });
    return `<div><span class="t">${t}</span> [${esc(e.source)}] ${esc(e.type)}</div>`;
  }).join('');
}

function renderTopics() {
  const sel = $('#cmd-topic');
  if (sel.options.length) return;
  for (const t of state.config.topics) {
    const opt = document.createElement('option');
    opt.value = t; opt.textContent = t;
    if (t === 'Coding') opt.selected = true;
    sel.appendChild(opt);
  }
}

function render() {
  if (!state) return;
  renderOffice(); renderApprovals(); renderMissions(); renderHealth(); renderLog(); renderTopics();
}

// ---- interactions ----
document.addEventListener('click', async (ev) => {
  const btn = ev.target.closest('button');
  if (!btn) return;
  try {
    if (btn.dataset.approve) {
      btn.disabled = true;
      await api('/api/approve', { approval_id: Number(btn.dataset.approve), decision: 'approved' });
      toast('✅ อนุมัติแล้ว — ส่ง followup ให้ agent merge');
    } else if (btn.dataset.reject) {
      const note = prompt('เหตุผล / สิ่งที่ให้แก้ (ส่งกลับไปหา agent):') || '';
      await api('/api/approve', { approval_id: Number(btn.dataset.reject), decision: 'rejected', note });
      toast('↩️ ปฏิเสธแล้ว — agent กลับไปแก้ต่อ');
    } else if (btn.dataset.resume) {
      await api(`/api/missions/${btn.dataset.resume}/resume`);
      toast('▶️ mission ไปต่อ');
    } else if (btn.dataset.cancel) {
      if (!confirm('ยกเลิก mission นี้?')) return;
      await api(`/api/missions/${btn.dataset.cancel}/cancel`);
      toast('🛑 ยกเลิกแล้ว');
    } else if (btn.id === 'btn-restart') {
      btn.disabled = true;
      await api('/api/restart-gateway', {});
      toast('↻ สั่ง restart gateway แล้ว');
      btn.disabled = false;
    } else if (btn.id === 'btn-send') {
      await sendCommand();
    }
  } catch (e) {
    const d = e.data || {};
    toast(`⚠️ ${d.error || e.message}${d.detail ? ` — ${d.detail}` : ''}${d.hint ? `\n${d.hint}` : ''}`, 6000);
    if (btn.dataset.approve || btn.id === 'btn-restart') btn.disabled = false;
  }
});

async function sendCommand() {
  const text = $('#cmd-text').value.trim();
  if (!text) return;
  const res = await api('/api/command', { text, topic: $('#cmd-topic').value });
  $('#cmd-text').value = '';
  toast(`🎮 ส่งเข้า Hermes แล้ว (${res.via})`);
}
$('#cmd-text').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') sendCommand().catch((err) => toast(`⚠️ ${err.data?.error || err.message}`, 6000));
});

// ---- live state: WS + fallback polling ----
function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const tok = getToken();
  const qs = tok ? `?token=${encodeURIComponent(tok)}` : '';
  const ws = new WebSocket(`${proto}://${location.host}/ws${qs}`);
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'state.sync') { state = msg.state; render(); }
  };
  ws.onclose = () => setTimeout(connectWs, 3000);
}

(async function boot() {
  try { state = await api('/api/state'); render(); } catch { /* bridge เพิ่งบูต */ }
  connectWs();
  setInterval(async () => { // fallback กัน WS เงียบ + อัปเดต elapsed
    try { state = await api('/api/state'); render(); } catch { /* ข้ามรอบ */ }
  }, 30000);
})();
