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
| `coworker/server/manager.py` (SessionManager) | 3,505 | **EXTRACT 5 slices + REWRITE glue** | god-object 1 class ~110 methods — see §server |
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
