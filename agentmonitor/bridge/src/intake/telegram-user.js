import { cfg } from '../config.js';

// โหมด B — ส่งข้อความ "ในนามบัญชี Telegram ของคุณ" (MTProto ผ่าน GramJS)
// จำเป็นเพราะข้อจำกัดของ Telegram: บอทไม่รับข้อความจากบอทด้วยกัน — Hermes จะเห็นเฉพาะข้อความจาก user จริง
// ติดตั้งครั้งเดียว: npm i telegram && node ../scripts/tg-login.mjs → ใส่ TG_USER_SESSION ใน .env
let clientPromise = null;

async function loadGramJs() {
  const tg = await import('telegram');
  const sessions = await import('telegram/sessions/index.js').catch(() => import('telegram/sessions'));
  const TelegramClient = tg.TelegramClient || tg.default?.TelegramClient;
  const StringSession = sessions.StringSession || sessions.default?.StringSession;
  if (!TelegramClient || !StringSession) throw new Error('gramjs exports not found');
  return { TelegramClient, StringSession };
}

async function getClient() {
  if (clientPromise) return clientPromise;
  clientPromise = (async () => {
    const c = cfg();
    const { TelegramClient, StringSession } = await loadGramJs();
    const client = new TelegramClient(
      new StringSession(c.tgUserSession), Number(c.tgApiId), c.tgApiHash,
      { connectionRetries: 3 },
    );
    await client.connect();
    return client;
  })();
  clientPromise.catch(() => { clientPromise = null; });
  return clientPromise;
}

export async function sendViaTelegramUser(text, topicName) {
  const c = cfg();
  if (!c.tgApiId || !c.tgApiHash || !c.tgUserSession) {
    return { ok: false, status: 501, error: 'TG_USER_NOT_CONFIGURED', hint: 'npm i telegram && node scripts/tg-login.mjs' };
  }
  try {
    const client = await getClient();
    const thread = c.topics[topicName];
    const target = c.tgBotUsername || Number(c.telegramChatId);
    await client.sendMessage(target, { message: text, ...(thread ? { replyTo: thread } : {}) });
    return { ok: true, via: 'telegram-user' };
  } catch (e) {
    return { ok: false, status: 502, error: 'TG_USER_FAILED', detail: String(e.message || e).slice(0, 300) };
  }
}
