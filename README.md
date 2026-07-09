# harness-flow (formerly: easby-workflow)

โฟลเดอร์สำหรับเก็บไฟล์ตั้งค่า คอนฟิก และกฎการทำงานของ AI (SSOT) สำหรับ Cursor IDE และ Hermes Agent เพื่อย้ายเครื่องและตั้งค่าระบบได้ง่ายที่สุด

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

สคริปต์จะคัดลอกไฟล์กฎการทำงาน (Rules) ไปยังโฟลเดอร์ Global ของ Cursor และจัดแจงไฟล์คอนฟิกหลักของ Hermes Agent ให้เข้าพิกัดทันทีโดยอัตโนมัติ

---

## 4. AgentMonitor — pixel office (ใหม่)

`agentmonitor/` — ศูนย์มอนิเตอร์ทีม AI แบบออฟฟิศ pixel: Hermes แตกงานให้ Cursor Cloud Agents แล้วรายงาน event เข้า bridge, แดชบอร์ดแสดงตัวละครเดินเข้าห้อง crawl/build/test, บอสกด approve merge ได้เฉพาะเมื่อ `./verify.sh` เขียว (hard gate) — ดู `agentmonitor/README.md`

โปรเจกต์นี้ออกแบบให้แยกไปเป็น repo ของตัวเองได้ด้วย `agentmonitor/scripts/extract-repo.sh` — กติกาฝั่ง Hermes อยู่ใน `hermes/SOUL.md` (ส่วน "Mission protocol")
