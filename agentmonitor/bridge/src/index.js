import http from 'node:http';
import * as db from './db.js';
import { cfg } from './config.js';
import { createApp } from './server.js';
import { attachWs } from './ws.js';
import * as poller from './poller.js';
import * as timers from './timers.js';
import * as health from './health.js';
import * as notify from './notify.js';

const c = cfg();
db.init(c.dbPath);
notify.register();

const app = createApp();
const server = http.createServer(app);
attachWs(server);

server.listen(c.port, c.bind, () => {
  console.log(`TownHall bridge — http://${c.bind}:${c.port} (dashboard + /ws + /api)`);
  console.log(`  db: ${c.dbPath}`);
  console.log(`  cursor api: ${c.cursorApiKey ? 'configured' : 'NOT SET (poller disabled)'}`);
  console.log(`  telegram notify: ${c.telegramBotToken ? 'configured' : 'NOT SET (log only)'}`);
});

health.bootCheck();
poller.start();
timers.start();
health.start();
