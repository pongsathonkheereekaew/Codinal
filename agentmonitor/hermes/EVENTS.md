# Event protocol — Hermes → TownHall bridge

Hermes รายงาน lifecycle ของ mission มาที่ `POST http://127.0.0.1:4777/api/events` ด้วย exec tool (curl)
กติกาสำคัญ: **curl ล้มเหลว = ทำงานต่อ** — ห้าม block งานเพราะ bridge ล่ม (bridge เป็น monitor ไม่ใช่ dependency)

Poller ฝั่ง bridge ดึงสถานะจริงจาก Cursor API เป็น ground truth อยู่แล้ว — event จาก Hermes เติม "ความหมาย"
(อยู่ห้องไหน ทำ stage อะไร) ถ้า Hermes ลืมรายงาน agent จะถูก adopt เข้า mission `(untracked)` อัตโนมัติ

## 1. `mission.created` — ก่อน launch agent ตัวแรกเสมอ

```bash
curl -s -X POST http://127.0.0.1:4777/api/events -H 'Content-Type: application/json' -d '{
  "source": "hermes",
  "type": "mission.created",
  "mission": {
    "title": "ES-L: fix filter gain clamping",
    "topic": "Easby",
    "tasks": [
      {"name": "research clamp approach", "stage": "crawl"},
      {"name": "implement clamp", "stage": "build"}
    ]
  }
}'
# → {"ok":true,"mission_id":7,"task_ids":[{"task_id":12,"name":"research clamp approach"}, ...]}
# จำ mission_id + task_id ไว้ใช้กับ event ถัดไป
# เกิน 3 subtasks → 400 TOO_MANY_TASKS — แตกใหม่หรือถามบอส
```

`stage` ที่รองรับ: `crawl` (research/อ่าน docs) · `build` (เขียนโค้ด) · `test` (verify)

## 2. `task.assigned` — หลัง launch Cursor agent ต่อ subtask

```bash
curl -s -X POST http://127.0.0.1:4777/api/events -H 'Content-Type: application/json' -d '{
  "source": "hermes", "type": "task.assigned",
  "task_id": 12, "cursor_agent_id": "bc-abc123", "character": "Ash", "branch": "cursor/fix-clamp"
}'
# agent ตัวที่ 4 ใน mission เดียว → 409 SPAWN_CAP
```

## 3. `task.stage_changed` — ตัวละครย้ายห้อง

```bash
curl -s -X POST http://127.0.0.1:4777/api/events -H 'Content-Type: application/json' \
  -d '{"source":"hermes","type":"task.stage_changed","task_id":12,"stage":"test"}'
```

## 4. `task.verify_result` — หลังรัน ./verify.sh ทุกครั้ง

```bash
curl -s -X POST http://127.0.0.1:4777/api/events -H 'Content-Type: application/json' \
  -d '{"source":"hermes","type":"task.verify_result","task_id":12,"result":"green","log_tail":"All tests passed"}'
# result: "green" | "red"
```

## 5. `approval.requested` — PR เปิด + verify เขียว → หยุดรอบอส

```bash
curl -s -X POST http://127.0.0.1:4777/api/events -H 'Content-Type: application/json' \
  -d '{"source":"hermes","type":"approval.requested","task_id":12,"pr_url":"https://github.com/x/y/pull/9"}'
# verify ยังไม่เขียว → 409 VERIFY_NOT_GREEN (hard gate — แก้ให้เขียวก่อนค่อยขอใหม่)
# สำคัญ: ห้าม merge เอง — คำตัดสินของบอสจะไปถึง agent ตัวนั้นเป็น followup จาก bridge โดยตรง
```

## 6. `task.done` / `mission.report` — ปิดงาน

```bash
curl -s -X POST http://127.0.0.1:4777/api/events -H 'Content-Type: application/json' \
  -d '{"source":"hermes","type":"task.done","task_id":12}'

curl -s -X POST http://127.0.0.1:4777/api/events -H 'Content-Type: application/json' \
  -d '{"source":"hermes","type":"mission.report","mission_id":7,"summary":"clamp fixed, verify green, PR merged"}'
```

## Fallback lookup

ถ้าจำ id ไม่ได้ ทุก task event รับ `cursor_agent_id` หรือ `mission_title` + `name` แทน `task_id` ได้
type ที่ไม่รู้จักจะถูกเก็บลง event log เฉยๆ (ไม่ error) — เปิดดูได้ที่ `GET /api/events`
