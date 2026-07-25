---
title: OpenWorker boundary map — vendor / extract / rewrite
status: spike deliverable (Phase 0a.4)
date: 2026-07-25
source: andrewyng/openworker@54b4bfd82d75704a4079ecea4f8f622aa152dbde
---

# OpenWorker boundary map

ผล Phase 0a.4 spike: map โครง OpenWorker จริงเพื่อ verify D3 (vendor/rewrite split). แต่ละโมดูล → VENDOR (copy สะอาด) / EXTRACT (แยกได้มี seam) / REWRITE (ฝังลึกเขียนใหม่ทิ้งเก่า).

## สรุป verdict

| โมดูล | ขนาด | Verdict | หมายเหตุ |
|---|---|---|---|
| `coworker/engine.py` (TurnEngine) | 1,033 | **VENDOR** | ไม่ import server/socket/manager; 4 collaborators + 7 optional callables |
| `coworker/sessions.py` | 36 | **VENDOR** | pure dataclass `SessionRecord` |
| `coworker/providers/{base,router,anthropic,openai,gemini}_provider.py` | ~1,800 | **VENDOR** | zero `coworker.server` leakage; `secrets:Any`; tool-call normalize 1 shape |
| `coworker/providers/capabilities.py` `registry.py` | ~450 | **EXTRACT** | heuristic table + descriptor menu — edit ตอน probe models |
| `coworker/tools/*` | — | **EXTRACT/REWRITE** | tool impl ใช้ได้; manifest ย้ายไป harness/policy |
| `coworker/permissions.py` `risk.py` | 296 | **VENDOR + light-adapt** | already risk-class-based + stdlib-only; Codinal adaptation = drop the `connectors.tool_defs` import in `standing_rule_candidate` (connectors deferred). Vendored 2026-07-25 into `runtime/policy/` (20 tests green). |
| `coworker/mcp/*` | — | **VENDOR (transport)** | แยก transport จาก policy |
| `coworker/server/manager.py` (SessionManager) | 3,505 | **EXTRACT slices + REWRITE glue** | `sessions` + `events` + `settings` ✅; `automations` deferred; scoped connectors + glue pending |
| `coworker/server/app.py` (control plane) | 1,773 | **REWRITE (reject as unit)** | ทุก `/v1/*` unauthenticated; 2 WS เช็คแค่ spoofable Origin; `/oauth/callback` CSRF P0 |
| `coworker/server/run.py` orphan-watcher | 156 | **REUSE logic** | orphan-kill; launcher entry ทิ้ง |
| `coworker/connectors/integration_tools.py` | 4,892 | **REWRITE / out-of-scope v1** | connector นอก PR/issue เป็น non-goal |
| `surfaces/gui/src/components/*` | 45 files | **VENDOR (REWIRE seam)** | components ทั้งหมดรับ local TS contract — ไม่แตะ |
| `surfaces/gui/src/api.ts` | 1,774 | **REWIRE** | ~90 fetch + 1 WS → repoint endpoint/shape |
| `surfaces/gui/src/App.tsx:556-699` | WS switch | **REWIRE** | 20-event vocabulary = coworker.server contract |
| `surfaces/gui/src/itemsFromMessages.ts` | 101 | **REWIRE** | OpenAI-shaped transcript + `_display` sidecar |
| `surfaces/gui/src-tauri/src/lib.rs:576-583` | spawn model | **REWIRE** | spawn Python + inject port/token globals |

## รายละเอียดสำคัญ

### TurnEngine vendorable — contract ที่ host ต้อง provide

engine.py พูดกับ 4 abstractions เท่านั้น (host implement หรือ re-vendor):
1. **`ProviderClient`** — `.stream(model, messages, tools, **settings) → chunked AssistantTurn deltas` + `.capabilities(model)`
2. **`ToolRegistry`** — `.schemas()`, `.get(name)→spec` (metadata มี `risk_level`/`requires_approval`/`category`), `.execute(name, args)`
3. **`PermissionEngine`** — `.evaluate(name, args, metadata) → Decision` (`.allowed`/`.reason`/`.needs_user`/`.rule`), `.mode`, `.allow_*_for_session`, `.risk_overrides`
4. **`Event`/`EventType`** — tiny event bus type

+ 7 optional callables (default None/deny/no-op): `approver`, `audit_sink`, `context_provider`, `directory_requester`, `plan_approver`, `question_asker`, `interrupt_hooks`.

Dependency direction: `server/manager.py:39` imports engine; **engine never imports server.** สามารถ drop `server/` ทั้ง package ได้.

### Provider layer — tool-call normalization (สำคัญต่อ policy port)

ทุก provider emit **`ToolCall(id, name, arguments:dict)`** เดียว (base.py:15-21):
- Anthropic `tool_use` → ToolCall (input dict เดิม)
- OpenAI `tc.function` → ToolCall (arguments JSON string parse + `{"_raw":...}` fallback)
- Gemini `function_call` → ToolCall (synth `call_<n>` id; rebuild map ตอน result)

→ Codinal policy port parse **1 shape** เดียว (confirm D6 ทำได้).

Model swap mid-session ทำได้แล้ว: `engine.switch_model` (engine.py:180) + `router.invalidate(name)` (router.py:82). ไม่ต้อง restart (confirm success criterion #2).

### server/manager.py — 5 slices ที่ EXTRACT ได้

ปัจจุบัน `SessionManager` (~110 methods) ผสม 7 concerns. แยกได้เป็น 5 modules เบื้องหลัง interface (provider/MCP inject ไม่ own):
1. **sessions** — engine cache + persistence + roots/artifacts (manager.py:295,760,2974,3260-3364)
2. **events** — 6 pub/sub methods (2194-2227)
3. **automations** — CRUD + wakes + scheduled (2449-2972)
4. **connectors/gateway** — build/refresh + per-platform (1033-2193)
5. **settings** — prefs JSON (1532-1855)

REUSE stateless helpers: `_redact`, `_recent_files`, `_artifact_kind`, `_git_branch`, `_last_assistant_text`, Ollama/curated probes, `_grants_of`/`_approval_body`.

REWRITE (entangled): `__init__` (105-226 wires-everything), policy/approval glue (mint_task_rule, _scheduled_approver, approval_outcome, _apply_grants), inbox callbacks (650-760).

**Phase 1.2 progress (2026-07-26):** `sessions` ถูก extract เป็น public
`runtime.sessions.SessionService` หลัง injected `SessionStore`, engine factory/snapshotter,
delete callbacks และ artifact opener. Runtime ไม่ own provider/MCP และไม่เรียก OS opener
โดยตรง. `events` ถูก extract เป็น `runtime.events.EventHub` สำหรับ global/per-session
async fan-out พร้อม unsubscribe และ dead-listener pruning. `settings` ถูก extract เป็น
`runtime.settings.SettingsService` + atomic `JsonPreferenceStore`; JSON เก็บเฉพาะ
non-secret preferences ส่วน provider credentials เป็น Phase 1.4 Keychain port.
Core composition root อยู่ใน `runtime/composition.py`: ทุก engine build รับ
`PermissionEngine`, injected/default-deny `Approver`, shared roots, session event sink
และ live default-model settings จาก chokepoint เดียว. `automations` defer post-MVP
ตาม ADR D9; active remainder คือ connectors gateway ที่จำกัด PR/issue และ
session/composition route wiring; authenticated transport เสร็จใน Phase 1.3.

**Phase 1.3 progress (2026-07-26):** `server/app.py` ถูก rewrite เป็น
`runtime.control_plane` โดย auth middleware ครอบ ASGI app ก่อน routing ทำให้ route
ใหม่ในอนาคต deny-by-default ด้วย. HTTP ใช้ bearer header; WebSocket ใช้
`Sec-WebSocket-Protocol` เพื่อไม่วาง token ใน URL. Tauri v2 host สร้าง random
256-bit token ต่อ process, spawn sidecar บน random loopback port และ inject
credentials เข้า WebView memory. OpenAPI/docs ถูกปิดและ WebView CSP เปิด.

**Phase 1.4 progress (2026-07-26):** file-backed `coworker.secrets.SecretStore`
ถูกแทนด้วย native Rust `PlatformSecretVault` บน macOS Security.framework.
Python sidecar รับ provider credentials ผ่าน one-shot stdin bootstrap แล้วเก็บใน
`runtime.secrets.ProviderSecretService` แบบ memory-only. Hot updates persist ใน
Keychain และ sync เข้า runtime ผ่าน authenticated control plane พร้อม rollback.
ไม่มี endpoint หรือ status response ที่คืน raw secret.

**Phase 1.5 progress (2026-07-26):** managed OAuth callback เดิมที่รับ token
โดยไม่ validate `app_state` ถูกทิ้ง. `runtime.oauth` เพิ่ม bounded/expiring
one-time state service กับ injected handler coordinator. Native Tauri host
ลงทะเบียน static `codinal` scheme, parse callback แบบ exact และ relay เฉพาะ
authorization code ผ่าน route ที่ต้องมีทั้ง bearer และ native-only sync token.
Provider adapter จริงจะ register handler ผ่าน composition seam ใน Phase 2;
callback path นี้ไม่ persist หรือรับ access/refresh token จาก browser.

**Phase 2.1 progress (2026-07-26):** เริ่ม vendor
`coworker/providers/base.py` เป็น provider-neutral contract พร้อม provenance
header แต่ใช้ `runtime.policy.ToolCall` เป็น canonical type และ revalidate
ทุก `AssistantTurn` ด้วย strict parser. เพิ่ม bridge จาก provider contract ไป
conformance runner ที่รักษา system role/tool schema และ sanitize report.
SDK-specific adapters/router ยังไม่ถูก vendor ใน slice นี้ เพื่อแยก review
credential resolution ออกจาก contract.

**Phase 2.1 OpenAI adapter progress (2026-07-26):** vendor
`coworker/providers/openai_provider.py` พร้อม provenance, pin OpenAI SDK ใน
hashed runtime lock และคง text/tool/stream/reasoning normalization เดิม.
Codinal adaptation ลบ `OPENAI_API_KEY` environment fallback: production key
resolve จาก `ProviderSecretService` memory mirror เท่านั้น; error และ outbound
message ไม่ echo key/foreign provider sidecar.

**Phase 2.1 Anthropic adapter progress (2026-07-26):** vendor native Messages
adapter พร้อม provenance และ pin Anthropic SDK ใน hashed runtime lock. Converter
รักษา system role, parallel tool-result folding, thinking sidecar และ tool-use
normalization; Codinal ลบ `ANTHROPIC_API_KEY` env fallback และ resolve key จาก
memory-only service เท่านั้น.

**Phase 2.1 Gemini adapter progress (2026-07-26):** vendor native Google GenAI
adapter พร้อม provenance และ pin `google-genai` ใน hashed runtime lock.
Function-call/thought-signature normalization เดิมถูก revalidate ที่ provider
contract; Codinal ลบทั้ง `GEMINI_API_KEY` และ `GOOGLE_API_KEY` env fallback
และ resolve key จาก memory-only service เท่านั้น.

**Phase 2.1 router progress (2026-07-26):** replace upstream registry breadth
ด้วย fail-closed router สำหรับ OpenAI/Anthropic/Gemini และ loopback-only Ollama.
Unknown/ambiguous provider ids ถูก reject; Ollama URL ต้องเป็น HTTP loopback
exact `/v1` และ client ไม่ได้รับ cloud secret store. Secret hot update
transactionally invalidate cached SDK client ของ provider ที่เปลี่ยน.

**Phase 2 TurnEngine seam progress (2026-07-26):** vendor provider-neutral
`Event`/`EventType`; rewrite `ToolRegistry` โดยไม่พึ่ง aisuite reflection.
Registry รับเฉพาะ explicit strict schema, ชื่อ function/schema ต้องตรงและต้อง
declare อยู่ใน harness `ToolManifest`; arguments ถูก parse ด้วย policy contract
ก่อน invoke. นี่เป็น dependency seam ก่อน vendor TurnEngine loop.

**Phase 2.1 TurnEngine progress (2026-07-26):** vendor/adapt
`coworker/engine.py` เป็น runtime-owned loop แล้ว. ทุก model-requested tool
รวม interactive controls ต้องมี registry entry และผ่าน `PermissionEngine`
ก่อนทำงาน; manifest risk เป็น SSOT จึงไม่ลด `git_stage`/`git_commit` เป็น read.
Unknown tools fail closed, provider/tool exception details ไม่ถูกส่งเข้า event
หรือ conversation history, และมี fresh tests สำหรับ approval, streaming,
interrupt, max-iteration rail และ PDF adaptation. `coworker/pdf_support.py`
ถูก adapt เป็น local-only fallback พร้อม pinned/hash-locked `pypdf` และ
`pypdfium2`.

**Phase 2.4 control-plane turn seam (2026-07-26):** เพิ่ม `runtime.turns`
coordinator และ authenticated `POST /v1/sessions/{id}/turns|interrupt`.
หนึ่ง session มี active turn ได้หนึ่งงาน; events จาก TurnEngine ถูก serialize
เป็น `{type, ...data}` ไป session WebSocket และ snapshot ใน `finally`.
Payload/session id ถูก bound และ unexpected error ไม่ echo exception.
Standalone production composition ถูกปิดใน slice ถัดมา: ConversationStore,
ProviderRouter, TurnEngine และ bounded read registry ถูก wire เข้าด้วยกัน.

**Phase 2.2 conversation storage (2026-07-26):** adapt
`coworker/conversations.py` จาก SQLite-index + แยก JSONL มาเป็น SQLite
transaction เดียวสำหรับ session metadata และ ordered messages เพื่อตัด
split-brain ระหว่าง index/log. Store validate public session id ซ้ำ, reject
non-finite/non-JSON data ก่อน transaction, รองรับ append และ atomic replace
เมื่อ history diverge, เปิด foreign-key cascade และตั้ง directory/database
เป็น owner-only. MCP transport ยัง pending.

**Phase 2.4 production composition (2026-07-26):** standalone sidecar เลิกใช้
placeholder แล้ว. `build_services()` compose transactional store, secure
provider router, policy-bound TurnEngine, session coordinator และ core read
registry. `read_file`/`list_files`/literal `grep` validate live roots ซ้ำ,
block parent/symlink escape, จำกัด bytes/lines/files/results/time และไม่ spawn
subprocess. E2E test พิสูจน์ bearer turn → session WebSocket tool lifecycle →
snapshot → restart/load history. Mutation/shell tools รอ Phase 3 sandbox.

**Phase 2.2 MCP transport (2026-07-26):** adapt `coworker/mcp/{client,config,
tools}.py` บน official `mcp==1.28.1` ที่ pin/hash-lock. ตัด env/`.env` secret
resolution และ OAuth store ของ upstream ออก; connect ต้องรับ explicit host
approval. Remote HTTP จำกัด HTTPS หรือ loopback HTTP ไม่มี URL credentials/
query, stdio ใช้ executable+argv ไม่ผ่าน shell และ child env เป็น safe
allowlist. Dynamic names กัน collision ด้วย hash, schemas ถูก bound/strict,
manifest risk เป็น external+requires-approval เสมอ และ remote error body ไม่
เข้า model history.

**Phase 2.4 MCP session wiring (2026-07-26):** authenticated explicit-connect
route attach remote tools เข้าเฉพาะ idle live session; missing session ไม่เปิด
external connection และถ้า turn เริ่มระหว่าง connect จะไม่ mutate registry.
Server name reuse กับ definition อื่นถูก reject, app lifespan ปิด transports/
stdio children. Scripted production E2E พิสูจน์ prompt → dynamic MCP call →
external approval → result → final answer → persisted restart. UI server
management/disconnect อยู่ Phase 4; live provider tier ยังต้อง conformance จริง.

### server/app.py — REJECT as unit (P0s ครบ)

- Bind `127.0.0.1:8765` (config.py:51); desktop sidecar random port → `COWORKER_PORT` (run.py:146)
- **No auth middleware** — only CORSMiddleware (app.py:173). ไม่มี `Depends`, ไม่มี Bearer/API-key
- Origin regex `_ALLOWED_ORIGIN_RE` (app.py:30) เช็คเฉพาะ 2 WS; CORS ไม่ gate WS อยู่แล้ว; Origin spoof ง่าย
- ~95 routes ทั้งหมด unauthenticated: `/v1/sessions/*`, `/v1/chat/completions`, `/v1/providers*`, `/v1/settings/*` (รวม `model-key`!), `/v1/mcp*`, `/v1/connectors/*/connect`, `/v1/automations/*/run`, `/v1/cloud/login`
- 2 WS `/ws/session/{id}` (1372) + `/ws/events` (1721) = full agent control จาก loopback peer
- **`/oauth/callback` POST (1012) — CSRF P0:** `app_state` minted (cloud.py:363) แต่ **ไม่ validate ตอน return**; ใครก็ POST ฟุตง `access_token`/`installation_id` เข้า SecretStore ได้. (เทียบ: `/auth/callback` 926 และ `/mcp/oauth/callback` 634 validate state ถูก — เฉพาะ managed `/oauth/callback` เท่านั้นที่พัง)

→ no route handler มี authz เลย; business logic (ใน §slices) กู้ได้ แต่ handler ทิ้งทั้งหมด.

### UI coupling — 3 seam files

- React 18 + **Tauri v2** + Vite 5 + TS 5.5
- Bridge = HTTP REST (~90 fetch) + 1 WS ไป localhost sidecar (ไม่ใช่ Tauri command สำหรับ agent traffic)
- lib.rs:576-583 spawn Python บน free port, inject `window.__COWORKER_HTTP__`/`__COWORKER_WS__`
- State shape ผูก `coworker.server`: `SessionInfo` (types.ts:40-62 mirror manager.list_sessions), `WsEvent` 20 types (App.tsx:556-699 switch), `ConversationMessage` OpenAI-shaped
- `Item` union (types.ts:76-119) encode standing-rule/inbox/approval semantics ของ OpenWorker — ต้องตัดสินใจ trim/reproduce

Verdict: **REWIRE** (ไม่ rewrite). 45 components รอดทั้งหมด (รับ local TS contract). งานอยู่ใน `api.ts` + `App.tsx` event switch + `itemsFromMessages.ts` + `lib.rs` spawn.

## สิ่งที่ spike เปลี่ยนในสถาปัตยกรรม (re-open F1)

F1 ตัดสินใจ "in-process stdio IPC, ไม่มี network server" เพื่อ kill P0 #2 by construction. spike พบว่า UI ที่จะ reuse พูด HTTP+WS กับ localhost sidecar. stdio → rewrite UI bridge ทั้งหมด ( expensive ). 

**คำแนะนำ (revision):** กลับไป loopback HTTP+WS **+ mandatory per-session bearer token** (Rust host mint token + inject ผ่าน spawn channel เดียวกับที่วันนี้ inject port). P0 #2 แก้โดย token auth ทุก route + WS (defensible pattern — เหมือน Jupyter/VS Code), UI reuse เฉียบ ยังคง no-bypass เพราะ PermissionEngine ที่ engine.py รับเป็น collaborator เป็น harness-controlled chokepoint.

ดู ADR D7/D4 amendment.
