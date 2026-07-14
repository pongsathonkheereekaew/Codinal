# harness-flow

Machine kit + templates for **Agent Harness** — one content hub (`~/.agents`) and thin per-tool adapters.

| Name | Meaning |
|------|---------|
| **Agent Harness** | The method |
| **`AGENTS.md`** | Lingua franca (shared policy — keep this filename) |
| **`~/.agents/`** | Live SSOT for skills / standards / commands / policy |
| **harness-flow** | This repo (bootstrap, templates, personal packs) |

**How to use (day to day):** edit `~/.agents` → `harness sync` / `harness rules` / `harness doctor`.  
Claude-only → `~/.claude/CLAUDE.md`. Hermes-only → `~/.hermes/SOUL.md`.  
Full guide: [`docs/AGENT_HARNESS.md`](docs/AGENT_HARNESS.md).

**Share with others (no personal skills):** [`templates/agents-harness/`](templates/agents-harness/) → `bash templates/agents-harness/install.sh`.

**Your machine migrate (private kit):** `./install.sh` below still installs Claude/Hermes packs from this repo.

---

## 1. โครงสร้างระบบ (System Structure)

ระบบทำงานร่วมกันอย่างง่ายและปลอดภัย ปราศจากความซับซ้อน:

```
[ผู้ใช้ / โทรศัพท์มือถือ]
       │
       ├──► โค้ดดิ้งหลัก (Desktop & iOS) ──► Cursor IDE (อ่านกฎจาก ~/.cursor/rules)
       │
       └──► สั่งรันเทส (Telegram) ────────► Hermes Agent ──► รัน ./verify.sh
```

- **Cursor IDE**: รับหน้าที่รันโค้ดดิ้งผ่านคีย์ DeepSeek สำรอง หรือโควตา Cursor Pro โดยจะคอยสแกนอ่านกฎ Global ตลอดเวลา
- **Hermes Agent**: รับหน้าที่เป็นสะพานสั่งการระยะไกลผ่าน Telegram คอยรัน `./verify.sh` และรายงานผลเสียง/รูปคลื่นกลับมา

---

## 2. กฎการทำงานร่วมกัน (AI Rules & SSOT)

เราแบ่งขอบเขตของกฎ (Rule Scoping) เพื่อไม่ให้รบกวนเวลาสร้างโปรเจกต์ประเภทอื่นๆ เช่น เกม หรือแอปพลิเคชันทั่วไป:

### กฎระดับเครื่อง (Global Rules - `~/.cursor/rules/`)
1. `ui-design-standards.mdc` (ทั่วไป):
   - คุมเรื่องฟอร์แมตตัวอักษรทั่วไป เช่น บังคับ Em Dash (`—`) และการห้ามใส่คำโฆษณาอวยเกินจริง (No marketing fluff) มีผลกับทุกโปรเจกต์บนเครื่อง
2. `easby-ui-standards.mdc` (เฉพาะปลั๊กอิน):
   - คุมเรื่องสีส้ม active curve, ขนาดอักษร 10px, และปุ่ม undo/redo `↰/↱` ทำงานเฉพาะโฟลเดอร์ `Downloads/Easby Plugins/`
3. `dsp-standards.mdc` (เฉพาะปลั๊กอิน):
   - คุมข้อกำหนด DSP ความปลอดภัยสัญญาณเสียง และการบังคับรันสคริปต์ `./verify.sh` ทำงานเฉพาะโฟลเดอร์ `Downloads/Easby Plugins/`

### กฎการสแกนข้ามไฟล์ขยะ (Local `.cursorignore`)
- อยู่ที่ Root ของแต่ละ Repo เพื่อข้ามการสแกน `build/` และ `.venv/` ช่วยประหยัด Token และเร่งความเร็ว

---

## 3. วิธีการนำไปติดตั้งบนเครื่องใหม่ (Setup / Migrate)

เมื่อโคลน Repository นี้ลงเครื่องใหม่แล้ว รันคำสั่งเดียวเพื่อติดตั้งการตั้งค่าทั้งหมด:

```bash
./install.sh
```

สคริปต์จะ:
1. คัดลอก Cursor rules → `~/.cursor/rules/`
2. ติดตั้ง Claude workflow จาก `claude/` → `~/.claude/` (skills, agents, hooks, commands)
3. ติดตั้ง external packs (mattpocock / google / caveman) ผ่าน `skills` CLI
4. คัดลอก Hermes config → `~/.hermes/`

**Skills & agents SSOT:** `claude/` ใน repo นี้ (เดิมแยกอยู่ที่ `claude-skills` — เลิกใช้แล้ว ดู `MANIFEST.md`)

---

## 4. AgentMonitor — pixel office (ใหม่)

`agentmonitor/` — ศูนย์มอนิเตอร์ทีม AI แบบออฟฟิศ pixel: Hermes แตกงานให้ Cursor Cloud Agents แล้วรายงาน event เข้า bridge, แดชบอร์ดแสดงตัวละครเดินเข้าห้อง crawl/build/test, บอสกด approve merge ได้เฉพาะเมื่อ `./verify.sh` เขียว (hard gate) — ดู `agentmonitor/README.md`

โปรเจกต์นี้ออกแบบให้แยกไปเป็น repo ของตัวเองได้ด้วย `agentmonitor/scripts/extract-repo.sh` — กติกาฝั่ง Hermes อยู่ใน `hermes/SOUL.md` (ส่วน "Mission protocol")

---

## 5. Project Wiki (engineering lessons ต่อ repo)

Karpathy-style wiki สำหรับบันทึกบั๊กที่แก้แล้ว + invariants — อยู่ที่ `docs/wiki/` ใน **git ของแต่ละโปรเจกต์** (ไม่ใช่ memory ระบบที่ 2; claude-mem ยังเป็น SSOT ของ session memory)

harness-flow มี live wiki ที่ [`docs/wiki/`](docs/wiki/) และ template ที่ [`templates/project-wiki/`](templates/project-wiki/)

เปิดในปลั๊กอิน/แอปอื่น:

```bash
bash templates/project-wiki/init-wiki.sh /path/to/your-repo
```

หลังแก้บั๊กแบบมี repro + root cause + verification ผ่าน — agent ต้องเขียน `docs/wiki/incidents/<slug>.md` และอัปเดต `index.md` / `log.md` ก่อนบอก done (ข้าม typo/one-liner)
