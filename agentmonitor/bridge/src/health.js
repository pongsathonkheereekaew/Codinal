import { execFile } from 'node:child_process';
import * as db from './db.js';
import { cfg } from './config.js';
import { changed, notify } from './bus.js';

// Health (Q4): 9router HTTP, Hermes launchd (macOS), heartbeat ของ bridge เอง
// "คอมดับให้แจ้งเตือน" — แจ้งแบบ hard power-off ตอนดับไม่ได้ (ไม่มี process เหลือส่ง)
// สิ่งที่ทำได้จริง: ตอน bridge บูตกลับมา ถ้า heartbeat ขาดช่วง + มีงานค้าง → แจ้ง Telegram ทันที
let timer = null;

function setAndAnnounce(component, status, detail) {
  const prev = db.getHealth(component);
  db.setHealth(component, status, detail);
  if (prev && prev.status !== status && (status === 'down' || prev.status === 'down')) {
    notify(status === 'down' ? `⚠️ ${component} ล่ม${detail ? ` — ${detail}` : ''}` : `✅ ${component} กลับมาแล้ว`, null);
    changed('health');
  }
}

async function checkRouter() {
  const c = cfg();
  try {
    const res = await fetch(c.routerUrl, { signal: AbortSignal.timeout(3000) });
    setAndAnnounce('9router', res.ok ? 'ok' : 'down', `HTTP ${res.status}`);
  } catch (e) {
    setAndAnnounce('9router', 'down', e.message);
  }
}

function checkHermes() {
  if (process.platform !== 'darwin') {
    db.setHealth('hermes', 'unknown', 'launchctl check is macOS-only');
    return;
  }
  execFile('launchctl', ['list', 'com.nousresearch.hermes'], { timeout: 5000 }, (err) => {
    setAndAnnounce('hermes', err ? 'down' : 'ok', err ? 'launchd job not loaded' : null);
  });
}

export async function tick() {
  await checkRouter();
  checkHermes();
  db.setMeta('heartbeat', db.now());
  db.setHealth('bridge', 'ok');
}

// เรียกครั้งเดียวตอนบูต — ตรวจว่า bridge/เครื่องดับไปนานแค่ไหน มีงานค้างไหม
export function bootCheck() {
  const last = Number(db.getMeta('heartbeat') || 0);
  const gapMs = last ? db.now() - last : 0;
  if (last && gapMs > 5 * 60000) {
    const hanging = db.listActiveAgentTasks().length;
    const mins = Math.round(gapMs / 60000);
    if (hanging > 0) {
      notify(`🔌 Bridge กลับมาออนไลน์ — หายไป ~${mins} นาที (เครื่องดับ/หลับ?) มีงานค้าง ${hanging} งาน — เปิดเกมเช็ค แล้วกด Continue ถ้าจะไปต่อ`, null);
    } else {
      notify(`🔌 Bridge กลับมาออนไลน์ — หายไป ~${mins} นาที ไม่มีงานค้าง`, null);
    }
  }
  db.setMeta('heartbeat', db.now());
}

export function start() {
  const c = cfg();
  tick().catch((e) => console.warn('[health]', e.message));
  timer = setInterval(() => tick().catch((e) => console.warn('[health]', e.message)), c.healthSeconds * 1000);
  timer.unref?.();
}

export function stop() { if (timer) clearInterval(timer); }
