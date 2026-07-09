// สร้าง TG_USER_SESSION สำหรับโหมด B (ส่งข้อความในนามบัญชีคุณ — MTProto)
// ติดตั้งก่อน: cd agentmonitor/bridge && npm i telegram
// รัน:        node ../scripts/tg-login.mjs
// เอา api_id + api_hash จาก https://my.telegram.org → API development tools
import readline from 'node:readline/promises';

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

let tg, sessions;
try {
  tg = await import('telegram');
  sessions = await import('telegram/sessions/index.js').catch(() => import('telegram/sessions'));
} catch {
  console.error('❌ ยังไม่ได้ติดตั้ง gramjs — รัน: cd agentmonitor/bridge && npm i telegram');
  process.exit(1);
}
const TelegramClient = tg.TelegramClient || tg.default?.TelegramClient;
const StringSession = sessions.StringSession || sessions.default?.StringSession;

const apiId = Number(await rl.question('TG_API_ID (จาก my.telegram.org): '));
const apiHash = (await rl.question('TG_API_HASH: ')).trim();

const client = new TelegramClient(new StringSession(''), apiId, apiHash, { connectionRetries: 3 });
await client.start({
  phoneNumber: async () => (await rl.question('เบอร์โทร (เช่น +66812345678): ')).trim(),
  password: async () => (await rl.question('รหัส 2FA (ถ้ามี — enter ข้าม): ')).trim(),
  phoneCode: async () => (await rl.question('โค้ดที่ Telegram ส่งมา: ')).trim(),
  onError: (e) => console.error('login error:', e.message),
});

console.log('\n✅ login สำเร็จ — คัดลอกบรรทัดนี้ลง bridge/.env แล้ว chmod 600 .env:');
console.log('TG_USER_SESSION=' + client.session.save());
console.log('\n⚠️  session นี้ = สิทธิ์เต็มบัญชี Telegram ของคุณ — เก็บบน Mac เครื่องเดียว ห้าม commit');
await client.disconnect();
process.exit(0);
