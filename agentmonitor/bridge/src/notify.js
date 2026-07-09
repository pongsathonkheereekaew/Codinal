import { cfg } from './config.js';
import { bus } from './bus.js';

// โหมด C — แจ้งเตือนทาง Telegram ด้วย bot token เดิมของ Hermes ได้:
// bridge เรียก sendMessage อย่างเดียว (ไม่ getUpdates) จึงไม่ชนกับ gateway ที่ polling อยู่
// ข้อจำกัดของ Telegram: Hermes จะไม่เห็น/ไม่ตอบข้อความจากบอท — เส้นนี้ใช้แจ้งเตือนเท่านั้น
export async function sendTelegram(text, topicName = null) {
  const c = cfg();
  if (!c.telegramBotToken || !c.telegramChatId) {
    console.log('[notify skipped]', text.replace(/\n/g, ' | '));
    return { skipped: true };
  }
  const thread = c.topics[topicName || c.notifyTopic];
  const body = {
    chat_id: c.telegramChatId,
    text,
    ...(thread ? { message_thread_id: thread } : {}),
  };
  const res = await fetch(`https://api.telegram.org/bot${c.telegramBotToken}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(`telegram sendMessage ${res.status}: ${detail.slice(0, 200)}`);
  }
  return res.json();
}

let registered = false;
export function register() {
  if (registered) return;
  registered = true;
  bus.on('notify', ({ text, topic }) => {
    sendTelegram(text, topic).catch((e) => console.warn('[notify]', e.message));
  });
}
