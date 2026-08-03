# Omnigent vs Codinal: SSOT และ model-agnostic runtime

Research date: 2026-08-03
Scope: `omnigent-ai/omnigent` บน `main` และ Codinal workspace ปัจจุบัน
Status: อ่าน/วิเคราะห์เท่านั้น; ไม่แก้ source/runtime

## Executive summary

**ไม่ใช่ระบบเดียวกัน และไม่มีผู้ชนะทุกแกน**

- **Omnigent** เป็น meta-harness: orchestration layer ที่รวม Claude Code, Codex,
  Cursor, OpenCode, Hermes, Pi และ custom agents แล้วเปลี่ยน harness/model ได้จาก
  agent spec เดียว [README](https://github.com/omnigent-ai/omnigent/blob/main/README.md)
- **Codinal** เป็น native local product/runtime ที่เน้น authority: Rust runtime,
  single writer, durable approval/receipt, deterministic recovery และ projection ที่
  ตรวจ drift ได้ [decision 0004](../decisions/0004-rust-only-runtime-and-harness-boundary.md)

ดังนั้น Omnigent **ดีกว่าใน breadth/orchestration/collaboration วันนี้** ส่วน Codinal
**ดีกว่าใน local authority, write safety และการทำให้ consequence ตรวจสอบย้อนหลังได้**
แต่ Codinal ยังแพ้ Omnigent ด้านจำนวน model/harness ที่รันได้จริงใน Rust runtime ปัจจุบัน

## 1. SSOT เหมือนกันไหม

**เหมือนกันในหลัก “declarative contract + derived projection” แต่ไม่เหมือนในขอบเขต**

Omnigent ให้ agent YAML เป็น portable declaration ของ prompt, harness, model, tools,
sub-agents, OS access และ policies [Agent YAML spec](https://github.com/omnigent-ai/omnigent/blob/main/docs/AGENT_YAML_SPEC.md)
และมี model resolution ตามลำดับ explicit choice → configured default → live catalog →
static fallback [model resolver](https://github.com/omnigent-ai/omnigent/blob/main/omnigent/model_resolver.py)

แต่ Omnigent **ยังไม่ใช่ SSOT เดียวสำหรับทุกอย่าง**: เอกสาร conformance ของเขาระบุเองว่า
capability เดียวกันเคยมีสามแหล่งที่ไม่ตรงกัน—spreadsheet, executor flags และ
`model_override.py`—แล้วใช้ live bench reconcile ให้เกิด `DRIFT` เมื่อ declaration
ไม่ตรง behavior [harness bench design](https://github.com/omnigent-ai/omnigent/blob/main/docs/harness-bench-design.md)
นอกจากนี้ harness registry ยังมี seam แบบ hardcoded อยู่ใน source [harness registry](https://github.com/omnigent-ai/omnigent/blob/main/omnigent/runtime/harnesses/__init__.py)

Codinal มี SSOT ที่ชัดกว่าในระบบที่ตัวเองควบคุม:

- repo เป็น git SSOT ของ portable policy + skills; `~/.agents` เป็น live path ที่ติดตั้ง
  แล้ว [MANIFEST](../../MANIFEST.md)
- `source bundle`, `user overlay`, `live projection` และ `host projection` ถูกแยกเป็น
  คนละ ownership boundary [CONTEXT](../../CONTEXT.md) · [Rust harness manager](../../crates/codinal-harness/src/lib.rs)
- Rust inventory คำนวณ drift, วางแผน write, ออก receipt, verify และ rollback โดยไม่ลบ
  path ที่ไม่ได้เป็นเจ้าของ [inventory](../../crates/codinal-harness/src/inventory.rs)

ข้อสรุปที่ถูกต้องจึงไม่ใช่ “SSOT หนึ่งก้อนสำหรับทุกอย่าง” แต่คือ **หนึ่ง authority ต่อ
bounded domain แล้วให้ทุก projection derive จาก authority นั้น**. Codinal เข้าใกล้หลักนี้
มากกว่า; Omnigent มี model/harness catalog ที่ยืดหยุ่นกว่าแต่ยังมีหลาย declaration seam.

## 2. รันได้ทุกโมเดลไหม

### Omnigent

Omnigent กว้างกว่าชัดเจน: รองรับ first-party API key, subscription CLI, OpenAI/Anthropic
compatible gateway, Ollama/vLLM/LiteLLM/Azure และ Databricks ตาม configuration
[README model setup](https://github.com/omnigent-ai/omnigent/blob/main/README.md)
อีกทั้งมี `ModelIntent` (`default`, `fast`, `balanced`, `powerful`), capability/context/
wire-API filter และ tri-state metadata ที่แยก unknown ออกจาก unsupported
[model metadata](https://github.com/omnigent-ai/omnigent/blob/main/omnigent/model_metadata.py)

แต่คำว่า **ทุกโมเดลเป็น marketing shorthand ไม่ใช่ universal guarantee**:

- harness แต่ละตัวมี backend/auth/model-family ของตนเอง
- Cursor, Antigravity, Copilot และ Kiro มีข้อจำกัด backend/credential เฉพาะ และไม่ใช่
  gateway เดียวกันทั้งหมด [Agent YAML executor constraints](https://github.com/omnigent-ai/omnigent/blob/main/docs/AGENT_YAML_SPEC.md)
- model override และ capability ต้องผ่าน harness/provider ที่เลือก; ถ้า model ไม่มี
  metadata การเลือกแบบ explicit ทำได้ แต่ระบบไม่ควรอ้าง capability ที่ยังไม่รู้

### Codinal

Codinal วาง abstraction ถูกทิศ: มี provider profile, model catalogue, capability snapshot,
probe status และ role profile/fallback ใน model ของ workflow [CONTEXT providers](../../CONTEXT.md)
· [workflow profiles](../../crates/codinal-harness/src/workflow.rs)

แต่ **ความสามารถที่รันได้จริงใน Rust ตอนนี้ยังแคบ**:

- `ExecutionProfile` มีเพียง OpenCode Go และ DeepSeek [runtime profiles](../../crates/codinal-runtime/src/lib.rs)
- bundled model catalogue มีสอง entry คือ OpenCode Go และ DeepSeek [catalogue](../../crates/codinal-providers/src/catalogue.rs)
- มี Ollama direct path แยกต่างหาก แต่ไม่ใช่ generic provider path เดียวกัน
- `ProviderId`/secret registry และ Python router รับ provider มากกว่านี้ แต่ตาม decision
  Rust-only แล้ว Python เป็น behavior/fixture reference ไม่ใช่ app dependency; provider ID
  ที่ parse ได้จึง **ไม่เท่ากับ** provider ที่ Rust execution รันได้

สรุป: **Omnigent model/harness-agnostic กว่าในวันนี้; Codinal model-agnostic กว่าใน
เป้าหมายเชิง contract แต่ยัง deliver ไม่ครบ**.

## 3. ใครดีกว่าในแต่ละแกน

| แกน | ผู้ได้เปรียบ | เหตุผล |
|---|---|---|
| รวมหลาย harness/vendor ใน session | Omnigent | YAML executor + SDK/CLI/ACP/native transports |
| จำนวน model/provider ที่ใช้งานได้วันนี้ | Omnigent | gateway + live catalog + provider-specific adapters |
| model selection แบบไม่ผูก id | Omnigent | intent, metadata, capability filter, provenance/fallback |
| local single-writer correctness | Codinal | Rust owner lock และ runtime authority เดียว |
| approval ที่ผูกกับ consequence | Codinal | approval ID/turn/source state และ one-shot consumption |
| audit/recovery ของ local data | Codinal | durable receipt, operation lifecycle, migration/recovery contract |
| org policy / cloud sandbox / multi-user / phone | Omnigent | server/agent/session policies, sandbox providers, shared sessions |
| capability drift testing | Omnigent วันนี้ | harness bench มี live/offline matrix และ DRIFT verdict |
| provider execution boundary แบบ fail-closed | Codinal เป้าหมาย | readiness/probe gate และ native runtime chokepoint |

Omnigent policies มี ALLOW/DENY/ASK, server-wide/agent/session layering, spend cap,
sandbox, PII และ tool restrictions [policy guide](https://github.com/omnigent-ai/omnigent/blob/main/docs/POLICIES.md)
ซึ่งกว้างและพร้อมใช้กว่า Codinal ตอนนี้. ในทางกลับกัน Codinal ไม่ควรยก authority ของ
local write ไปไว้ใน prompt/policy layer เพียงอย่างเดียว; decision ของเราระบุชัดว่า
prompt policy แทน runtime approval boundary ไม่ได้.

## 4. สิ่งที่ควรยืมจาก Omnigent

1. เพิ่ม `ModelIntent` + provider-neutral resolver ให้ `RoleProfile` ขอ `fast/balanced/
   powerful` และ capability แทนการผูกกับ model ID โดยตรง
2. ใช้ tri-state capability (`supported`, `unsupported`, `unknown`) และบันทึก source,
   revision, TTL, probe result ใน receipt/catalogue
3. ทำ harness/provider conformance bench ที่รัน behavior จริงและทำ declaration drift ให้
   fail—not just static matrix
4. รวม model catalog, harness capability, auth mode และ wire protocol ใน contract เดียว
   ต่อ adapter หนึ่งตัว แต่ยังคง generated projection แยกตาม host

## 5. สิ่งที่ไม่ควรยืม

- อย่าเปลี่ยน Codinal เป็น Python meta-harness หรือให้หลาย process มีสิทธิ์เขียน history
  เดียวกัน
- อย่าเรียก provider ที่ parse ได้ว่า “รองรับแล้ว” จนกว่าจะมี probe/conformance evidence
- อย่าใช้ “หนึ่ง SSOT สำหรับทุก object” จนรวม source code, live projection, user overlay,
  provider metadata และ runtime receipts เป็นไฟล์/registry เดียว; จะสร้าง conflict และ
  ทำให้ ownership ไม่ชัด

## Final verdict

ถ้าโจทย์คือ **“ใช้ agent/model/vendor อะไรก็ได้ และรวมทีม/มือถือ/cloud ให้เร็ว”** ให้เลือก
Omnigent; ตอนนี้มันดีกว่า Codinal อย่างชัดเจน.

ถ้าโจทย์คือ **“desktop runtime ที่ local consequence ต้องมีเจ้าของเดียว, approval ต้อง
ตรวจสอบได้, recovery ต้อง deterministic และ projection ต้องไม่ drift เงียบ”** Codinal
เป็นฐานที่ดีกว่า.

กลยุทธ์ที่เหมาะคือ **adopt Omnigent’s model resolver + conformance ideas, retain Codinal’s
Rust authority/SSOT boundaries**. อย่า merge product topology กัน.

## Caveat

การเทียบ Codinal ใช้ current working tree ซึ่งมี uncommitted migration/cutover changes;
จึงเป็นสถานะ WIP ไม่ใช่ release benchmark. มีหลักฐานของ cutover ที่ยังไม่ converge เช่น
contract fixture บางจุดยังชี้ owner เป็น Python ขณะที่ Rust health ระบุ owner เป็น Rust และ
ยังมี route ที่ตอบ `501 Not Implemented`. Omnigent README ระบุสถานะ alpha และเอกสาร bench
เองแยก live observation จาก declared/offline matrix; ยังไม่มี benchmark อิสระเรื่อง latency,
cost หรือ reliability ในรายงานนี้.
