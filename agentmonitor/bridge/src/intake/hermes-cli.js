import { execFile } from 'node:child_process';
import { cfg } from '../config.js';

// โหมด A — inject เข้า Hermes ด้วย CLI/local API (รัน scripts/spike-hermes-cli.sh เพื่อหา syntax จริงก่อน)
// template ใช้ env var $AM_TEXT / $AM_TOPIC / $AM_CHAT เพื่อเลี่ยงปัญหา shell quoting
// ตัวอย่าง: HERMES_SEND_CMD=hermes send --chat {chat} --topic {topic} --text "$AM_TEXT"
export function sendViaHermesCli(text, topicName) {
  const c = cfg();
  if (!c.hermesSendCmd) {
    return Promise.resolve({ ok: false, status: 501, error: 'HERMES_SEND_CMD not set' });
  }
  const thread = c.topics[topicName] ?? '';
  const cmdline = c.hermesSendCmd
    .replaceAll('{chat}', String(c.telegramChatId))
    .replaceAll('{topic}', String(thread))
    .replaceAll('{topic_name}', topicName || '');

  return new Promise((resolve) => {
    execFile('bash', ['-lc', cmdline], {
      timeout: 20000,
      env: { ...process.env, AM_TEXT: text, AM_TOPIC: String(thread), AM_CHAT: String(c.telegramChatId) },
    }, (err, stdout, stderr) => {
      if (err) {
        resolve({ ok: false, status: 502, error: 'HERMES_CLI_FAILED', detail: (stderr || err.message).slice(0, 500) });
      } else {
        resolve({ ok: true, via: 'hermes-cli', detail: stdout.slice(0, 200) });
      }
    });
  });
}
