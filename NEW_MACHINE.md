# เครื่องใหม่ — Agent Harness อย่างเดียว

ตั้งค่าเขียนโค้ดล้วนๆ **ไม่ต้องมี Telegram** ออฟฟิศเป็นทางเลือก

## 0. ต้องมีก่อน
- macOS, Homebrew, `git`
- coding agent ที่ใช้ (Cursor / Claude Code / Codex / …)
- SSH เข้า GitHub (หรือวิธี clone private repo ได้)

## 1. คำสั่งเดียว — clone + install + doctor

```bash
git clone git@github.com:pongsathonkheereekaew/harness-flow.git ~/harness-flow && cd ~/harness-flow && ./install.sh && ~/.agents/scripts/harness doctor
```

ได้ที่ `~/.agents/`: `AGENTS.md`, `skills/`, `standards/`, `commands/`, `scripts/` + symlink adapter

อัปเดตภายหลัง: `cd ~/harness-flow && git pull && ./install.sh`

## 2. ทางเลือก — AgentMonitor + Hermes (ออฟฟิศ)

```bash
git clone git@github.com:pongsathonkheereekaew/agentmonitor.git ~/agentmonitor && cd ~/agentmonitor && ./install.sh
```

- Pixel office: http://127.0.0.1:4777/
- Hermes kit → `~/.hermes` พร้อม `skills.external_dirs: [~/.agents/skills]`
- 9router ที่ `:20128` ถ้าโมเดลใช้

## 3. ตรวจว่าติดแล้ว

```bash
cd ~/harness-flow && bash ./verify.sh
~/.agents/scripts/harness doctor
```

## ใช้ประจำวัน

| งาน | ที่ไหน |
|-----|--------|
| นโยบาย / สกิล | `~/harness-flow` → `./install.sh` (หรือแก้ `~/.agents` แล้ว `./backup.sh`) |
| เขียนโค้ดที่โต๊ะ | Cursor / Claude ที่โหลด `~/.agents` |
| มิชชันออฟฟิศ | repo `agentmonitor` (ทางเลือก) |
