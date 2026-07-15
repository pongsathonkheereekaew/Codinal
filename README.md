# harness-flow — Agent Harness

**นโยบาย + สกิลร่วม** สำหรับทุก coding agent ติดตั้งครั้งเดียว → SSOT สดที่ `~/.agents/`

| คำ | ความหมาย |
|----|----------|
| **Agent Harness** | วิธีทำงาน: นโยบายสั้นที่โหลดเสมอ + สกิลเรียกเมื่อใช้ |
| **`AGENTS.md`** | นโยบายร่วม (เก็บชื่อไฟล์นี้ — ให้สั้น) |
| **`~/.agents/`** | SSOT สดหลังรัน `./install.sh` |
| **harness-flow** | repo นี้ — git SSOT ของเนื้อหานั้น |

ออฟฟิศ / Hermes อยู่ repo แยก: [`agentmonitor`](https://github.com/pongsathonkheereekaew/agentmonitor) — ไม่จำเป็นสำหรับเครื่องเขียนโค้ดล้วนๆ

```text
tool safety → tool settings
  → ~/.agents/AGENTS.md
  → adapter ของเครื่องมือ (CLAUDE.md, Cursor rules, …)
  → project ./AGENTS.md หรือ ./CLAUDE.md
  → skill ที่เรียก → ข้อความ user → model
```

## ติดตั้งเครื่องใหม่ (คำสั่งเดียว)

ต้องมี `git` (macOS แนะนำ Homebrew) และสิทธิ์ clone repo นี้

```bash
git clone git@github.com:pongsathonkheereekaew/harness-flow.git ~/harness-flow && cd ~/harness-flow && ./install.sh && ~/.agents/scripts/harness doctor
```

จบแล้วได้ `~/.agents/` (นโยบาย, skills, **memory**, standards, commands, scripts) + symlink ไป Claude / Cursor / Codex / Gemini ฯลฯ

อัปเดตภายหลัง:

```bash
cd ~/harness-flow && git pull && ./install.sh
```

เช็กลิสต์ละเอียด: [`NEW_MACHINE.md`](NEW_MACHINE.md)

## ได้อะไรบ้าง

- **นโยบายสั้นเสมอ** — classify งาน, ชี้ skill, verify ก่อนบอกทำเสร็จ
- **Durable memory ร่วม** — `~/.agents/memory/` (preference / สแตกที่ล็อกไว้); episodic ยังอยู่เครื่องมือ (เช่น claude-mem)
- **สกิล Agent Skills ~100+** ใต้ `skills/` (Matt Pocock, แพ็กโดเมน, …)
- **standards + slash commands** ซิงก์เข้า adapter
- **flow เริ่มต้น** (ใน `AGENTS.md`): งานมืด/ใหญ่ → `wayfinder`; ออกแบบ/แพลน → `grilling`; สร้างชัด → `implement`/`tdd`; ก่อนส่งแพลน/สเปก**สุดท้าย** → `scrutinize`

รายละเอียดดีไซน์: [`docs/DESIGN-thinking-flow.md`](docs/DESIGN-thinking-flow.md) · eval: [`docs/eval/thinking-flow/`](docs/eval/thinking-flow/) · ชื่อเรียก: [`docs/AGENT_HARNESS.md`](docs/AGENT_HARNESS.md)

## โครง repo

| พาธ | บทบาท |
|-----|--------|
| [`AGENTS.md`](AGENTS.md) | lingua franca (แก้ที่นี่ แล้ว install) |
| [`memory/`](memory/) | ข้อเท็จจริงถาวรร่วม (index: `MEMORY.md`) — ไม่ใช่ episodic |
| [`skills/`](skills/) | Agent Skills (`SKILL.md`) |
| [`standards/`](standards/) | เนื้อกฎ → Cursor `.mdc` ผ่าน `harness rules` |
| [`commands/`](commands/) | slash commands ร่วม |
| [`scripts/`](scripts/) | `harness` — `sync` / `rules` / `doctor` |
| [`adapters/`](adapters/) | snippet บางๆ ต่อเครื่องมือ |
| [`install.sh`](install.sh) | repo → `~/.agents` (+ลิงก์ adapter) |
| [`backup.sh`](backup.sh) | สด `~/.agents` → repo นี้ |
| [`verify.sh`](verify.sh) | ตรวจคร่าวๆ |

## ใช้ประจำวัน

**แก้ใน git นี้ แล้ว install** (repo คือ SSOT):

```bash
# แก้ AGENTS.md / skills / standards / commands
./install.sh
~/.agents/scripts/harness doctor
```

`install.sh` คัดลอกนโยบาย/skills/standards/commands/scripts เข้า `~/.agents` สร้าง Cursor rules และ symlink สกิล ถ้า `AGENTS.md` สดต่างจาก git จะสำรองเป็น `~/.agents/AGENTS.md.bak.<timestamp>` แล้วค่อยทับ

ถ้าแก้ที่ `~/.agents` โดยตรง ให้ดึงกลับก่อน install ครั้งถัดไปทับ:

```bash
./backup.sh
git status   # ตรวจแล้ว commit ใน repo นี้
./install.sh # ซิงก์ adapter อีกครั้งถ้าต้องการ
```

CLI หลังติดตั้ง:

```bash
~/.agents/scripts/harness sync    # symlink สกิลไป adapter
~/.agents/scripts/harness rules   # standards → Cursor rules
~/.agents/scripts/harness doctor  # ตรวจสุขภาพ
```

## ทางเลือก: AgentMonitor + Hermes

```bash
git clone git@github.com:pongsathonkheereekaew/agentmonitor.git ~/agentmonitor && cd ~/agentmonitor && ./install.sh
```

- Pixel office: http://127.0.0.1:4777
- Hermes อ่านสกิลผ่าน `skills.external_dirs → ~/.agents/skills`
- ไม่บังคับ Telegram

## สิ่งที่ไม่ใส่ใน repo นี้

| อย่าใส่ใน harness-flow | เก็บที่ไหน |
|------------------------|-----------|
| Hermes identity / gateway / SOUL | `agentmonitor` → `~/.hermes` |
| Claude hooks, claude-mem, RTK hooks | `~/.claude` เท่านั้น |
| secrets / tokens / API keys | ห้าม commit |

## ตรวจว่าติดแล้ว

```bash
bash ./verify.sh
~/.agents/scripts/harness doctor
```
