import 'dotenv/config';
import os from 'node:os';
import path from 'node:path';

const DEFAULT_TOPICS = { General: 215, Coding: 234, Easby: 219, Auric: 236 };

function expandHome(p) {
  if (!p) return p;
  return p.startsWith('~') ? path.join(os.homedir(), p.slice(1)) : p;
}

// อ่าน env สดทุกครั้ง — ทำให้ test ตั้งค่า env ก่อนเรียกได้ และไม่มี state ค้าง
export function cfg() {
  const env = process.env;
  let topics = DEFAULT_TOPICS;
  if (env.TELEGRAM_TOPICS) {
    try { topics = JSON.parse(env.TELEGRAM_TOPICS); } catch { /* คง default ไว้ */ }
  }
  return {
    port: Number(env.PORT || 4777),
    bind: env.BIND || '127.0.0.1',
    apiToken: env.API_TOKEN || '',
    dbPath: expandHome(env.DB_PATH) || path.join(process.cwd(), 'townhall.db'),

    cursorApiBase: env.CURSOR_API_BASE || 'https://api.cursor.com',
    cursorApiKey: env.CURSOR_API_KEY || '',

    githubToken: env.GITHUB_TOKEN || '',
    githubApiBase: env.GITHUB_API_BASE || 'https://api.github.com',

    telegramBotToken: env.TELEGRAM_BOT_TOKEN || '',
    telegramChatId: env.TELEGRAM_CHAT_ID || '',
    topics,
    notifyTopic: env.NOTIFY_TOPIC || 'Coding',

    intakeMode: env.INTAKE_MODE || 'auto', // auto | cli | user | notify
    hermesSendCmd: env.HERMES_SEND_CMD || '',
    tgApiId: env.TG_API_ID || '',
    tgApiHash: env.TG_API_HASH || '',
    tgUserSession: env.TG_USER_SESSION || '',
    tgBotUsername: env.TG_BOT_USERNAME || '',

    harnessFlowDir: expandHome(env.HARNESS_FLOW_DIR) || path.join(os.homedir(), 'harness-flow'),
    routerUrl: env.ROUTER_URL || 'http://127.0.0.1:20128/dashboard',

    stallMinutes: Number(env.STALL_MINUTES || 10),
    pauseMinutes: Number(env.PAUSE_MINUTES || 45),
    maxAgentsPerMission: Number(env.MAX_AGENTS_PER_MISSION || 3),
    pollSeconds: Number(env.POLL_SECONDS || 30),
    healthSeconds: Number(env.HEALTH_SECONDS || 60),
  };
}
