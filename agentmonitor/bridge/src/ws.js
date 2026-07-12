import { WebSocketServer } from 'ws';
import { bus } from './bus.js';
import { getState } from './state.js';
import { cfg } from './config.js';

// Broadcast state.sync ทั้งก้อนทุกครั้งที่มีการเปลี่ยนแปลง (coalesce 150ms)
// ข้อมูลเล็กพอ — เกม/แดชบอร์ด render จาก snapshot เดียว ไม่ต้อง diff
export function attachWs(httpServer) {
  const wss = new WebSocketServer({
    server: httpServer,
    path: '/ws',
    verifyClient: (info, done) => {
      const { apiToken } = cfg();
      if (!apiToken) return done(true);
      const url = new URL(info.req.url || '/ws', 'http://localhost');
      const token = url.searchParams.get('token')
        || (info.req.headers.authorization || '').replace(/^Bearer\s+/i, '');
      done(token === apiToken);
    },
  });

  const snapshot = () => JSON.stringify({ type: 'state.sync', state: getState() });

  wss.on('connection', (socket) => {
    try { socket.send(snapshot()); } catch { /* socket ปิดไปแล้ว */ }
  });

  let pending = null;
  bus.on('changed', () => {
    if (pending) return;
    pending = setTimeout(() => {
      pending = null;
      const msg = snapshot();
      for (const client of wss.clients) {
        if (client.readyState === 1) {
          try { client.send(msg); } catch { /* ข้าม client ที่หลุด */ }
        }
      }
    }, 150);
    pending.unref?.();
  });

  return wss;
}
