# CEDIA — AI Coding Desktop

> **CEDIA (formerly Codinal/Aidel/CEDIA, renamed 2026-08-07).** This repo is
> the SSOT for the CEDIA harness plus the plan for the CEDIA Code-OSS IDE
> fork. The IDE fork lives at `pongsathonkheeereekaew/CEDIA-IDE` and reads
> harness content here read-only.

## CEDIA repos

- `pongsathonkheeereekaew/CEDIA` — harness SSOT, policy, skills, agent config,
  and this repo.
- `pongsathonkheeereekaew/CEDIA-IDE` — Code-OSS fork (`~/cedia-ide`) with the
  bundled `cedia-agent` extension.
- `pongsathonkheeereekaew/CEDIA-BrowserOS` — BrowserOS fork (`~/cedia-browser`)
  providing the agentic browser layer over MCP.

> **⚠️ Repo repurposed to CEDIA (2026-07-25).** This repo is now the **CEDIA** product repo (macOS coding-agent desktop). Harness content still lives here — now under `harness/` — and the `~/.agents/` install contract is **unchanged**. Existing harness users see [`MIGRATING.md`](MIGRATING.md); to stay on the last harness-only release: `git checkout last-harness-only`. Architecture/plan: [`docs/decisions/`](docs/decisions/) + [`docs/plan/`](docs/plan/).

**ตรา:** multi-AI harness alignment — นโยบายบางร่วมกันทุกเครื่องมือ + สกิลเรียกเมื่อใช้ (ไม่ยัดทุกโดเมนเข้า always-on)

**นโยบาย + สกิลร่วม** สำหรับทุก coding agent  
ติดตั้งครั้งเดียว → เปิด Cursor / Claude / ZCode / Gemini แล้วทำงานได้เลย ไม่ต้องจูน harness ทีละตัว

| คำ | ความหมาย |
|----|----------|
| **Agent Harness** | นโยบายสั้นที่โหลดเสมอ + สกิลเรียกเมื่อใช้ |
| **`AGENTS.md`** | นโยบายร่วม (lingua franca) |
| **`~/.agents/`** | SSOT สดหลังติดตั้ง |
| **CEDIA** | repo นี้ — git SSOT ของเนื้อหานั้น |

ออฟฟิศ / Hermes อยู่ repo แยก: [agentmonitor](https://github.com/pongsathonkheereekaew/agentmonitor) — **ไม่จำเป็น** สำหรับเครื่องเขียนโค้ดล้วนๆ

---

## ลำดับติดตั้งที่ถูก

```text
[1] ระบบ + git + python3
[2] ติด AI ที่จะใช้ + login          ← Claude / Cursor / ZCode / Gemini / …
[3] รัน harness bootstrap            ← ครั้งเดียว
[4] เปิด AI แล้วทำงาน                ← ไม่ต้องจูน harness เพิ่ม
```

**ติดตั้ง AI ก่อน → แล้วค่อยติดตั้ง harness**

Harness เป็นชั้นกลาง (`~/.agents`) ที่ผูกเข้ากับเครื่องมือ  
ติด harness ก่อนก็ได้ (idempotent) แต่แนะนำให้แอปพร้อม login ก่อน แล้ว bootstrap ทีเดียวจบ

สำเนาขั้นตอนยาว: [`NEW_MACHINE.md`](NEW_MACHINE.md)

---

## ขั้นที่ 1 — พื้นฐานเครื่อง

| ต้องมี | หมายเหตุ |
|--------|----------|
| macOS หรือ Linux (bash) | |
| `git` | `xcode-select --install` หรือ `brew install git` |
| `python3` | macOS มีมาแล้ว |
| GitHub SSH หรือ HTTPS | clone repo นี้ได้ |

ไม่บังคับ: Homebrew, Node, `skills` CLI

---

## ขั้นที่ 2 — ติดตั้ง AI (เลือกเฉพาะตัวที่ใช้)

ติดตั้งแอป / CLI แล้ว **login ให้เรียบร้อย** ก่อนรัน harness  
เปิดแอปสักครั้งให้สร้างโฟลเดอร์ config ก็พอ — **ไม่ต้องตั้ง skill เอง**

| เครื่องมือ | ทำอะไร | harness ผูกยังไง |
|------------|--------|------------------|
| **Claude Code** | ติด + login | `~/.claude/CLAUDE.md`, skills symlink, plugin defaults (claude-mem / superpowers / caveman) |
| **Cursor** | ติด + login | `~/.cursor/skills`, `rules` (รวม `agents-policy.mdc` จาก AGENTS.md), commands |
| **ZCode** | ติด + login | `~/.zcode/AGENTS.md` + skills |
| **Gemini CLI** | ติด + login | `~/.gemini/GEMINI.md` + skills |
| **Codex** | ติด + login | อ่าน `~/.agents/skills` native + `AGENTS.md` |
| **OpenCode** | ติด + login | `~/.config/opencode/AGENTS.md` |
| **Openclaw** | ถ้าใช้ | skills symlink |
| **Antigravity / AI อื่น** | ตามผู้ขาย | ไม่ใช่ adapter หลัก — ดูด้านล่าง |

### Antigravity / AI นอกตาราง

Harness **ไม่** ลิงก์ skill เข้า Antigravity อัตโนมัติ

1. ถ้าเครื่องมืออ่าน `~/.agents/skills` เอง → รัน harness พอ  
2. **อย่า** ใช้ `skills add -a '*'` ก๊อปปี้ไปทั่วเครื่อง  
3. ให้ชี้ไป `~/.agents/skills` (symlink / `external_dirs`) หรือขอเพิ่ม adapter ใน harness

---

## ขั้นที่ 3 — ติดตั้ง harness (ครั้งเดียว)

```bash
git clone git@github.com:pongsathonkheereekaew/CEDIA.git ~/CEDIA && ~/CEDIA/bootstrap.sh
```

SSH ไม่ได้ — ใช้ HTTPS:

```bash
git clone https://github.com/pongsathonkheereekaew/CEDIA.git ~/CEDIA && ~/CEDIA/bootstrap.sh
```

`bootstrap.sh` ทำครบ:

1. clone / pull  
2. `install.sh` → `~/.agents/` (นโยบาย, skills, memory, standards, commands)  
3. ลิงก์เข้า Claude / Cursor / ZCode / Gemini / …  
4. ใส่คำสั่ง `harness` ที่ `~/.local/bin`  
5. เติม Claude plugin defaults (ไม่ทับของเดิม)  
6. `verify` + `doctor` → ขึ้น **READY**

ถ้า `harness: command not found` — เปิด shell ใหม่ หรือ:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### ถ้าติด harness ก่อน AI

ใช้ได้ — พอติด AI ทีหลัง รันซ้ำ:

```bash
cd ~/CEDIA && ./install.sh
```

---

## ขั้นที่ 4 — เปิด AI แล้วทำงาน

1. เปิด **Cursor** หรือ **Claude Code** (หรือตัวอื่นที่ติดไว้) ในโปรเจกต์  
2. Claude Code ครั้งแรก: ยอมให้ติดตั้งปลั๊กอินที่ settings เปิดไว้  
3. เริ่มงานได้เลย — ไม่ต้องไปตั้ง skill / `AGENTS.md` ในแต่ละเครื่องมืออีก

ตรวจเมื่อสงสัย:

```bash
harness doctor
bash ~/CEDIA/verify.sh
```

---

## อัปเดต harness ภายหลัง

```bash
harness update
```

หรือ:

```bash
cd ~/CEDIA && git pull && ./install.sh
```

---

## ได้อะไรบ้าง

- **ตรา:** multi-AI harness alignment — นโยบายบางร่วมกัน + สกิลเรียกเมื่อใช้  
- **นโยบายสั้นเสมอ** — classify งาน, ชี้ skill, verify ก่อนบอกทำเสร็จ, 3-fail recovery  
- **Durable memory ร่วม** — `~/.agents/memory/`  
- **สกิล ~100+** — Matt spine, `skill-creator`, Superpowers แบบคัดแล้ว; แพ็ก GCP/Google เป็น **user-invoked** (ไม่กิน Level-1)  
- **standards + slash commands** ซิงก์เข้า adapter (รวม `agent-guardrails` แบบ on-demand)  
- **Cursor** ได้ policy ผ่าน `agents-policy.mdc` (ไม่มี global `AGENTS.md` ใน Cursor)  
- **Claude defaults** — claude-mem + superpowers + caveman  

### สกิลตัวอย่างที่ vendored

| Skill | ใช้เมื่อ | หมายเหตุ |
|-------|---------|----------|
| [`mac-storage-cleanup`](skills/mac-storage-cleanup/) | สแกนพื้นที่ว่าง macOS / เสนอรายการลบ | audit ก่อนลบ; **อย่า** `npx codex-mac-storage-cleanup` (ทำลาย SSOT) — อัปเดตใน repo นี้แล้ว `harness sync` |

ลำดับ precedence:

```text
tool safety → tool settings
  → ~/.agents/AGENTS.md
  → adapter ของเครื่องมือ (CLAUDE.md, Cursor rules, …)
  → project ./AGENTS.md หรือ ./CLAUDE.md
  → skill ที่เรียก → ข้อความ user → model
```

---

## Skill priority / Level-1

Anthropic Agent Skills โหลดแบบ progressive disclosure:

1. **Level 1** — `name` + `description` ของทุก skill ที่ model เรียกได้ (อยู่ใน context ตอน startup)  
2. **Level 2** — ตัว `SKILL.md` เต็ม เมื่อ skill ถูก trigger  
3. **Level 3** — `references/` / scripts เมื่อจำเป็น  

ที่ ~100 skill แบบ harness นี้ Level 1 ยังรับได้ — **ไม่ต้อง** ใช้ SkillPointer / hidden vault  
Priority ที่ถูกสำหรับ desk นี้:

- Router แกนอยู่ใน [`AGENTS.md`](AGENTS.md) และ `ask-matt`  
- เขียน `description` ให้สั้นและชัด (trigger จริง ไม่ซ้ำใน body)  
- skill ที่ใช้น้อยมาก ตั้ง `disable-model-invocation: true` เองได้ (GCP/Google packs ใน repo นี้ตั้งไว้แล้ว)  
- ดูงบประมาณประมาณการ: `harness doctor` → ส่วน **Level-1 skill budget**  
- หลังแก้ policy/rules: ดู smoke มือที่ [`docs/eval/harness-smoke/`](docs/eval/harness-smoke/)

---

## โครง repo

| พาธ | บทบาท |
|-----|--------|
| [`AGENTS.md`](AGENTS.md) | lingua franca |
| [`memory/`](memory/) | ข้อเท็จจริงถาวร |
| [`skills/`](skills/) | Agent Skills |
| [`standards/`](standards/) | → Cursor `.mdc` |
| [`commands/`](commands/) | slash commands |
| [`scripts/`](scripts/) | `harness` CLI (`sync` / `rules` / `doctor` / `update`) |
| [`adapters/`](adapters/) | CLAUDE.md + Claude settings defaults |
| [`bootstrap.sh`](bootstrap.sh) | เครื่องใหม่ — คำสั่งเดียว |
| [`install.sh`](install.sh) | repo → `~/.agents` |
| [`verify.sh`](verify.sh) | ตรวจใน repo |
| [`NEW_MACHINE.md`](NEW_MACHINE.md) | เช็กลิสต์เครื่องใหม่ (รายละเอียด) |

---

## ใช้ประจำวัน (แก้เนื้อหา harness)

แก้ใน **git นี้** แล้ว install (repo คือ SSOT):

```bash
./install.sh
harness doctor
```

ถ้าแก้ที่ `~/.agents` โดยตรง ให้ดึงกลับก่อน install ครั้งถัดไปทับ:

```bash
./backup.sh
git status
./install.sh
```

CLI:

```bash
harness sync      # symlink สกิล → adapter
harness rules     # standards → Cursor rules
harness doctor    # ตรวจสุขภาพ
harness update    # pull + install
```

---

## ทางเลือก — AgentMonitor + Hermes (ออฟฟิศ)

ไม่จำเป็นสำหรับ desk เขียนโค้ด  
ถ้าต้องการ Pixel office / Telegram — ทำ **หลัง** harness:

```bash
git clone git@github.com:pongsathonkheereekaew/agentmonitor.git ~/agentmonitor && cd ~/agentmonitor && ./install.sh
```

- Pixel office: http://127.0.0.1:4777  
- Hermes อ่านสกิลผ่าน `skills.external_dirs → ~/.agents/skills`

---

## สิ่งที่ harness ไม่ทำแทนคุณ

| รายการ | ใครดูแล |
|--------|---------|
| Login / API key ของ Cursor, Claude, Gemini, … | คุณในแต่ละแอป |
| RTK / lowfat | optional (`brew`) |
| goal-loop hooks แบบเครื่องเก่า | Claude-private ถ้าต้องการภายหลัง |
| Antigravity adapter เฉพาะ | ยังไม่อยู่ใน harness |
| secrets / tokens | ห้าม commit |

| อย่าใส่ใน CEDIA | เก็บที่ไหน |
|------------------------|-----------|
| Hermes / office | `agentmonitor` |
| Claude hooks runtime bodies | `~/.claude` (defaults ใส่ให้อัตโนมัติ) |
| API keys / Telegram tokens | นอก git |
