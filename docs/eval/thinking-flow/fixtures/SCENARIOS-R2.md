# Fixtures — Round 2 (held-out)

## S4 — docs SKILL-MAP.md?

User: “อยากย้ายรายการ skill จาก ask-matt ไปไฟล์ `docs/SKILL-MAP.md` แล้วให้ AGENTS ชี้ไป ลด token ได้อีกไหม?”

Constraints: AGENTS already thin; ask-matt has full flow; progressive disclosure; `disable-model-invocation` on ask-matt.

## S5 — auto-run scrutinize via Cursor hook?

User: “ทำ Cursor hook / Claude Stop hook ให้รัน scrutinize อัตโนมัติทุกครั้งก่อนจบคำตอบที่มีคำว่า plan”

Constraints: hooks are tool-private; universal AGENTS can’t own hooks; false positives on short answers.

## S6 — merge scrutinize into grilling?

User: “รวม scrutinize เข้าท้าย grilling จะได้ไม่ต้องจำสองสกิล”

Constraints: scrutinize also reviews PRs/diffs; grilling is interview; Matt vocabulary separation.
