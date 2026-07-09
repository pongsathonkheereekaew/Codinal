import express from 'express';
import path from 'node:path';
import fs from 'node:fs';
import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import * as db from './db.js';
import { cfg } from './config.js';
import { getState } from './state.js';
import { handleEvent } from './events.js';
import { decide } from './gate.js';
import { resumeMission, cancelMission } from './timers.js';
import { sendCommand } from './intake/index.js';
import { changed } from './bus.js';

const PUBLIC_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'public');

function send(res, result) {
  if (result.ok) return res.json(result);
  return res.status(result.status || 500).json(result);
}

export function createApp() {
  const app = express();
  app.use(express.json({ limit: '1mb' }));

  // optional bearer token — เปิดใช้เมื่อ bind นอก 127.0.0.1 (PWA ผ่าน Tailscale)
  app.use('/api', (req, res, next) => {
    const { apiToken } = cfg();
    if (!apiToken) return next();
    const got = (req.headers.authorization || '').replace(/^Bearer\s+/i, '') || req.query.token;
    if (got === apiToken) return next();
    return res.status(401).json({ ok: false, error: 'UNAUTHORIZED' });
  });

  app.get('/healthz', (_req, res) => res.json({ ok: true, service: 'townhall-bridge' }));

  app.get('/api/state', (_req, res) => res.json(getState()));

  app.get('/api/events', (req, res) => {
    const limit = Math.min(Number(req.query.limit || 100), 500);
    res.json(db.listEvents(limit).map((e) => ({ ...e, payload: e.payload ? JSON.parse(e.payload) : null })));
  });

  // event sink — Hermes รายงาน mission lifecycle ที่นี่ (ดู SOUL mission protocol)
  app.post('/api/events', (req, res) => {
    try { send(res, handleEvent(req.body || {})); }
    catch (e) { res.status(500).json({ ok: false, error: 'EVENT_HANDLER_ERROR', detail: e.message }); }
  });

  // hard gate (Q2/Q8) — approve ได้เฉพาะ verify เขียว
  app.post('/api/approve', async (req, res) => {
    const { approval_id, task_id, decision, note } = req.body || {};
    if (!['approved', 'rejected'].includes(decision)) {
      return res.status(400).json({ ok: false, error: 'BAD_DECISION', detail: 'decision must be approved|rejected' });
    }
    send(res, await decide({ approvalId: approval_id, taskId: task_id, decision, note, via: req.body?.via || 'game' }));
  });

  // สั่งงานจากเกม → Hermes (โหมด A/B — ดู intake/)
  app.post('/api/command', async (req, res) => {
    const { text, topic, character } = req.body || {};
    send(res, await sendCommand({ text, topic, character }));
  });

  app.post('/api/missions/:id/resume', async (req, res) => send(res, await resumeMission(Number(req.params.id))));
  app.post('/api/missions/:id/cancel', async (req, res) => send(res, await cancelMission(Number(req.params.id))));

  // Q5: ลบ (archive) ตัวละคร/session ได้ — git ยังเป็น truth
  app.post('/api/characters/:id/archive', (req, res) => {
    db.updateCharacter(Number(req.params.id), { archived: 1 });
    changed('character.archived');
    res.json({ ok: true });
  });
  // Q6: toggle 🔒 local-only ต่อตัวละคร (enforcement อยู่ฝั่ง SOUL — Hermes ต้องไม่ส่งงานตัวนี้ขึ้น cloud)
  app.post('/api/characters/:id/local-only', (req, res) => {
    db.updateCharacter(Number(req.params.id), { locked_local_only: req.body?.value ? 1 : 0 });
    changed('character.local_only');
    res.json({ ok: true });
  });

  // ปุ่ม restart gateway (Q4) — เรียกสคริปต์ใน harness-flow
  app.post('/api/restart-gateway', (_req, res) => {
    const script = path.join(cfg().harnessFlowDir, 'hermes', 'restart-gateway.sh');
    if (!fs.existsSync(script)) {
      return res.status(404).json({ ok: false, error: 'SCRIPT_NOT_FOUND', detail: script });
    }
    execFile('bash', [script], { timeout: 30000 }, (err, stdout, stderr) => {
      if (err) return res.status(502).json({ ok: false, error: 'RESTART_FAILED', detail: (stderr || err.message).slice(0, 500) });
      res.json({ ok: true, detail: stdout.slice(-500) });
    });
  });

  app.use(express.static(PUBLIC_DIR));
  return app;
}
