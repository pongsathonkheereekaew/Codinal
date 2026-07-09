import { cfg } from '../config.js';
import { sendViaHermesCli } from './hermes-cli.js';
import { sendViaTelegramUser } from './telegram-user.js';
import * as db from '../db.js';
import { changed } from '../bus.js';

const NOT_CONFIGURED = {
  ok: false, status: 501, error: 'INTAKE_NOT_CONFIGURED',
  hint: 'ตั้ง HERMES_SEND_CMD (โหมด A — รัน scripts/spike-hermes-cli.sh ก่อน) หรือ TG_API_ID/TG_API_HASH/TG_USER_SESSION (โหมด B — node scripts/tg-login.mjs) — ระหว่างนี้พิมพ์สั่งใน Telegram ได้ตามปกติ',
};

// สั่งงานจากเกม → Hermes — prefix 🎮 [game] เพื่อให้แยกออกในประวัติ + SOUL ใช้ dedup
export async function sendCommand({ text, topic = 'Coding', character = null }) {
  if (!text || !text.trim()) return { ok: false, status: 400, error: 'EMPTY_TEXT' };
  const c = cfg();
  const msg = `🎮 [game]${character ? ` @${character}` : ''} ${text.trim()}`;

  let result;
  if (c.intakeMode === 'cli') result = await sendViaHermesCli(msg, topic);
  else if (c.intakeMode === 'user') result = await sendViaTelegramUser(msg, topic);
  else if (c.intakeMode === 'notify') result = NOT_CONFIGURED;
  else {
    // auto: ลองโหมด A ก่อน (สะอาดสุด) แล้วค่อยโหมด B
    if (c.hermesSendCmd) result = await sendViaHermesCli(msg, topic);
    else if (c.tgApiId && c.tgApiHash && c.tgUserSession) result = await sendViaTelegramUser(msg, topic);
    else result = NOT_CONFIGURED;
  }

  db.logEvent({
    source: 'game', type: result.ok ? 'command.sent' : 'command.failed',
    payload: { topic, character, text: text.slice(0, 300), via: result.via || null, error: result.error || null },
  });
  changed('command');
  return result;
}
