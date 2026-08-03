# Fully Rust: Codex/Cursor scale roadmap (v2)

> Status: supporting operational backlog. The canonical runtime, provider,
> harness, UI, and gate decisions live in
> [`rust-native-runtime-cutover.md`](rust-native-runtime-cutover.md) and win on
> conflict. This roadmap retains later editor/Cursor parity detail only.
> All Python commands and Python synthetic smoke steps below are inactive
> historical notes; current gates must use the Rust-only canonical plan.

สถานะปัจจุบัน: runtime เดิมยังมีเส้นทาง `GET /v1/health` + บางส่วนของ `sessions/messages` และการจัดการ secret ใน Rust runtime ในขณะที่ UI GPUI ยัง prototype และ `desktop/src-tauri` ยังถูกใช้เป็นการอ้างอิง/รัน sidecar บางส่วน.

เป้าหมาย: ทำให้ **ทุกโมเดล runtime, CLI, terminal, provider/router, storage, policy, editor surface, review loop** ใช้ Rust 100% ทั้งตัวบนโครงข่าย loopback เดียวกัน และลบ Tauri/Python ออกจาก production path โดยคงคุณสมบัติระดับ Codex/Cursor ไว้ครบ

## หลักยืนยัน (Definition of Done)
1. ทางเลือก Rust เท่านั้น: route, workspace, policy, provider, storage, UI state และ event อิงเดียวบน Rust listener.
2. Tauri/WebView และ embedded Python runtime ถูกลบจาก release artifact (binary, bundle, updater manifest, SBOM).
3. Feature parity ที่เป็น "agentic coding workflow" ตรงระดับ Cursor/Codex:
   - Session + conversations + fork/side-conversation + search/restart
   - แก้ไขไฟล์ผ่าน editor + diff/apply/selective+hunk
   - Review, terminal, MCP, workers, Git/PR loop, goals/plan, evidence
   - LSP + completion + inline edit
4. โหมด fallback ไม่มี: ไม่มี runtime dual writer; ownership lock และ migration เป็นแบบ deterministic และ recoverable.

## ขอบเขตแยกเป็นรอบ

### R0 — Lock contract & evidence (2–3 สัปดาห์)
- Freeze Python/JavaScript route surface เป็น golden fixtures (`runtime/control_plane/app.py`, `runtime/control_plane/test_*`) และคัดทิ้งการเรียกที่ไม่อยู่ใน v1 baseline
- สร้าง `contracts/v1/control-plane.generated.json` โดย auto-derive จาก Python decorator route ทั้งหมด (ปัจจุบัน Python app มี ~105 HTTP route + 2 WS ตามการสแกนเดิม)
- เพิ่ม conformance harness ที่อ่าน route fixture นี้และรันจาก Rust/GPUI/CLI เดียวกัน
- Gate: route fixture และ websocket/events fixture สอดคล้องกัน, ไม่มี secret รูปแบบใหม่หลุดในการ assertions

### R1 — Rust runtime bootstrap hardening + ownership model (2–4 สัปดาห์)
- ย้ายการเป็นเจ้าของ data directory ออกจาก read-only แบบเดิมของ Rust storage ให้เป็น write-capable แบบ migration-safe
  - ใช้ `prepare_owned_data_directory`, `pre_migration_backup`, integrity/recovery hooks ที่มีอยู่แล้วใน `codinal_storage`
- สร้าง `RuntimeOwnerLock` และ writer lease ชัดเจนสำหรับ production path
- ทำ health + bootstrap และ secret bootstrap ให้เป็น deterministic และ reject malformed payload ตามแนว security
- Gate: boot และ recovery สอดคล้อง contract (`/v1/health`, token auth, readiness), migration/recovery test ผ่าน

### R2 — API parity blast radius (4–8 สัปดาห์)
- สร้าง route handler อัตโนมัติจาก route-spec เพื่อให้ Rust ครอบคลุม route ตาม Python:
  - status/audit/policy/settings/extensions/integrations
  - sessions (search, context, forks, side-conversations, interruption, plans, goals, evidence, artifacts, tree/open/search, git, terminal, mcp, worker, preview)
  - providers/secrets/OAuth callback/shim routes
  - websocket/events endpoints (global/session) พร้อม sequence+reconnect semantics
- แยกไฟล์ต่อกลุ่มฟีเจอร์ (read/write/tooling/security/worker/review) แล้วเพิ่ม integration tests ต่อ route cluster
- Gate: ในแต่ละ cluster ต้องผ่าน fixture roundtrip และ golden negative tests (unauthorized/invalid id/path/invalid workspace)

### R3 — Service parity: policy, providers, tools, turns, storage writers (6–8 สัปดาห์)
- Port planner/turn engine skeleton ที่จำเป็นที่สุดให้เป็น Rust:
  - provider failover router (ยังรักษา OpenAI/Anthropic/Gemini/Ollama/OmniRoute/custom)
  - sandboxed command runner, Git, MCP transport, checkpoints/recovery
  - policy+approvals+audit redaction end-to-end
- เพิ่มอีเวนต์ stream และ persistence อย่างน้อยตาม v1 + reconciliation ระหว่าง restart/interrupt
- Gate: conformance live test matrix + kill/restart tests ครอบคลุม turn/approval/parallel-tools/plan

### R4 — UI parity at scale (GPUI first-class; 6–10 สัปดาห์)
- ทำให้ GPUI เป็น production shell แทน web-shell flow:
  - Sidebar/workspace/panel ให้ตำแหน่งสำคัญเหมือนโหมด production ปัจจุบัน (sessions tree, transcript, composer, terminal, diff/review, evidence panel)
  - Composer, terminal, review, provider settings คิดเป็น production surface (ยกเลิกข้อความ prototype ที่แสดงให้ใช้ Web UI)
  - รองรับแผง cursor-like: editor/editor-tabs/project tree + command pallet + shortcut map
- Add accessible keyboard/focus lifecycle + live metrics (FIP, typing P95, terminal/diff throughput)
- Gate: GPUI E2E + accessibility + perf budget (มี evidence ใน repo `docs/evidence`)

### R5 — Editor intelligence + Cursor-like workflows (8–12 สัปดาห์)
- สร้าง editor/LSP stack ที่ maintain ได้จริง:
  - symbol navigation/diagnostics/goto-definition
  - inline multi-line completion + prompt-aware cancellation/back-pressure
  - inline edit command (`Cmd/Ctrl+K` flow) + diff preview + selective accept/reject
  - artifacts read/write route ตาม security policy
- บริหาร dependency แบบ external binary (rust-analyzer/pyright/tsserver optional on PATH) และลดความซับซ้อนบน build pipeline
- Gate: throughput/latency bench + completion success + zero path traversal/cross-root write

### R6 — Hardening, cutover, and deletion (2–4 สัปดาห์)
- รวบรวมสแต็กที่เหลือให้ผ่าน production readiness:
  - updater/notary/sbom, quarantine + rollback, installer hygiene
  - हट Tauri/Python จาก dependency graph, script, docs, evidence trails
- ลบโค้ดรันไทม์เดิมแบบชิ้น: `SidecarLaunch` path, Python bundle expectation, docs runtime startup reference
- Gate: release dry run สะอาด: binary scan ไม่เจอ Tauri/Python artifacts, runtime path ไม่มี fallback ไป Python

## Mapping ไปยัง Codex/Cursor scale

| ส่วน | แนว Codex | แนว Cursor | ระดับความสำคัญ |
| --- | --- | --- | --- |
| ควบคุมเซสชัน | audit/restart/workspace/goal/plan | thread/fork/review | สูง |
| Diff/apply & commit | selective apply + hunk apply | inline edit + editor diff | สูง |
| Terminal + context | sandbox policy boundary | session workspace + symbol-aware edits | สูง |
| Preview/review evidence | preview+log+assertion artifact | screenshot/console evidence + annotation | กลาง |
| Remote/parallel | worker protocol + adopt | local execution पहले, remote ต่อภายหลัง | กลาง |

## ความเสี่ยงสำคัญ
- ลำดับการย้าย route หนัก: ย้ายรวมใน batch ใหญ่ทำให้ regression แอบมีจำนวนมาก
- แผน migration ของไฟล์/ฐานข้อมูลผิดพลาดอาจทำให้ rollback ไม่ restore ได้
- GPUI พฤติกรรม performance ถ้าเพิ่ม editor/LSP ตั้งแต่ต้นอาจทำให้ launch latency ผิด budget
- แพลตฟอร์มอื่นนอก macOS อาจมีอุปสรรคจาก runtime/PTY/packaging

## เชิงดำเนินการตามลำดับ (แบบย่อ)
1. เริ่มจาก R0+R1 พร้อมทำ shadow production dogfood
2. แยกงานตาม route cluster ตอน R2 (เช่น status/provider/session/git/terminal)
3. ทำ GPUI ให้ production core ก่อน แล้วเพิ่ม editor/LSP/Cmd+K ใน R5
4. Hardening และ deletion R6 จัดท้ายพร้อมกฎหมายการปล่อย

## R0 → R1 → R2 immediate execution track (next 2 phases)

### Immediate execution board (R0 → R1 → R2)

Use this as the next set of tasks with deterministic gate checks. Keep each row as an independent PR target.

#### Row A — R0 contract freeze (Day 1–2, hard gate)

1. Owner: runtime migration lead
2. Deliverable: route + WS contract snapshots only from Python control-plane source of truth.
3. Commands (once per freeze run):
   - `python -m pytest runtime/control_plane/tests` (or equivalent project fixture scanner) to enumerate route definitions.
   - generate:
     - `docs/contracts/r0/control-plane.v1.routes.json`
     - `docs/contracts/r0/control-plane.v1.events.json`
     - `docs/contracts/r0/negative-cases.md`
     - optional checksum `docs/contracts/r0/control-plane-v1-manifest.sha`
4. Gate:
   - static diff vs previous snapshot = 0,
   - auth/method/path ordering matches baseline,
   - 1 synthetic smoke run against Python app for status/middleware order.
5. Stop condition: no next-row work until all artifacts exist and snapshot hash is recorded in git notes.

#### Row B — R1 ownership hardening (Day 2–3, hard gate)

1. Owner: runtime/bootstrap lead
2. Deliverables:
   - writer lease + startup FSM in runtime (`crates/codinal-runtime/src/lib.rs` and adjacent ownership module).
   - `desktop/native-host/src/host.rs` rejects legacy Python/Tauri sidecar path in Rust-owned mode.
3. Hard checks (write evidence file only, no code bypass):
   - `docs/evidence/r1/r1-bootstrap-matrix.md` includes fresh install, reused install, interrupted-migration recovery.
   - invariants documented:
     - `owner_lock_mode == owned`
     - writable DB path only under active owner
     - migration lock held during bootstrap/recover
4. Stop condition: no R2 slice starts without matrix + recovery proof + signed owner lock transition logs.

#### Row C — R2 slice A (status/security) (Day 3–6)

1. Owner: control-plane route owner
2. Scope:
   - `GET /v1/health`, `GET /v1/version`, `GET /v1/config`
   - `/v1/secrets/*` (read/update/delete)
3. Validation:
   - parity fixture: `docs/contracts/r2/route-slice-A.json`
   - conformance: `docs/evidence/r2/slice-A-conformance.md`
   - negative: `docs/evidence/r2/slice-A-negative.md`
4. Stop condition: auth matrix and contract fixture parity pass.

#### Row D — R2 slice B (sessions/messages/plans/goals) (Day 6–9)

1. Owner: session/turn owner
2. Scope:
   - `GET/POST /v1/sessions*`, `/v1/messages*`, `/v1/plans*`, `/v1/goals*`
3. Validation:
   - parity fixture: `docs/contracts/r2/route-slice-B.json`
   - conformance: `docs/evidence/r2/slice-B-conformance.md`
   - negative: `docs/evidence/r2/slice-B-negative.md`
4. Mandatory live test:
   - turn lifecycle with websocket replay and event-id continuity.
5. Stop condition: event continuity + fixture parity + rollback proof.

#### Row E — R2 slice C (provider/policy/integrations) (Day 9–12)

1. Owner: provider & policy owner
2. Scope:
   - provider registry/routing/failover, OAuth callback shim, rate-limit + policy settings/evaluations.
3. Validation:
   - parity fixture: `docs/contracts/r2/route-slice-C.json`
   - conformance: `docs/evidence/r2/slice-C-conformance.md`
   - negative: `docs/evidence/r2/slice-C-negative.md`
4. Mandatory check:
   - one real provider adapter smoke path
   - signed-policy redaction boundary check.
5. Stop condition: provider failover and secret redaction evidence are present.

#### Row F — R2 slice D (git/terminal/mcp/workers) (Day 12–16)

1. Owner: execution/runtime tool owner
2. Scope:
   - tool execution, terminal + stream capture, mcp transport, worker control endpoints.
3. Validation:
   - parity fixture: `docs/contracts/r2/route-slice-D.json`
   - conformance: `docs/evidence/r2/slice-D-conformance.md`
   - negative: `docs/evidence/r2/slice-D-negative.md`
4. Mandatory check:
   - command replay
   - stderr/stdout schema validation
   - kill/restart + dedupe behavior.
5. Stop condition: deterministic stdout/stderr schema and worker/job state recovery.

#### Row G — R2 slice E (review/evidence/artifacts/preview) (Day 16–20)

1. Owner: review/evidence owner
2. Scope:
   - diff/review/evidence endpoints
   - tree/search/open
   - artifact attachment lifecycle + preview routes
3. Validation:
   - parity fixture: `docs/contracts/r2/route-slice-E.json`
   - conformance: `docs/evidence/r2/slice-E-conformance.md`
   - negative: `docs/evidence/r2/slice-E-negative.md`
4. Mandatory check:
   - idempotent artifact writes
   - rollback path.
5. Stop condition: artifact lifecycle + preview path is deterministic and contract-clean.

#### Governance during R0–R2
- No row can merge until: (a) fixture diff report, (b) negative-case report, (c) rollback evidence exist.
- Dual-writer hard-fail remains required in CI smoke for each row.
- Any newly touched route requires update to both fixture and negative-case bundle in same PR.
- If any row stalls >1 calendar week, pause next-row starts and run a one-line "cutover health check" before continuing.

#### Cross-row evidence path
- R0 evidence file: `docs/evidence/r0/r0-contract-freeze.md`
- R1 evidence file: `docs/evidence/r1/r1-bootstrap-matrix.md`
- R2 evidence file index: `docs/evidence/r2/r2-slice-index.md` (append each row on completion)

#### Kickoff tickets (start now)

1) Ticket R0-1 `Contract Scanner`
- Owner: runtime migration lead
- Scope: generate contract fixtures from `runtime/control_plane/app.py` into `docs/contracts/r0/*`
- Minimum commands:
  - `cd /Users/pongsathonkheeereekaew/harness-flow`
  - produce route/event snapshots under `docs/contracts/r0/`
- Deliverables:
  - `docs/contracts/r0/control-plane.v1.routes.json`
  - `docs/contracts/r0/control-plane.v1.events.json`
  - `docs/contracts/r0/negative-cases.md`
  - `docs/contracts/r0/control-plane-v1-manifest.sha`
  - `docs/evidence/r0/r0-contract-freeze.md` updated with checks pass/fail
- Gate to close: fixture diff report + synthetic smoke + contract signature line in evidence.

2) Ticket R1-1 `Owner-lock hardening`
- Owner: runtime/bootstrap lead
- Scope: implement deterministic owner lock FSM + remove Python/Tauri ambiguity in Rust-owned mode in:
  - `crates/codinal-runtime/src/lib.rs`
  - `desktop/native-host/src/host.rs`
- Deliverables:
  - owner FSM transitions and invariant checks
  - `docs/evidence/r1/r1-bootstrap-matrix.md` with Fresh/Upgrade/Interrupted rows complete
- Gate to close: all three matrix cases logged, dual-writer smoke hard-fail, migration lock held.

3) Ticket R2-A `Slice A parity`
- Owner: control-plane route owner
- Scope:
  - status/config/secrets routes
  - websocket readiness and auth ordering for those paths
- Deliverables:
  - `docs/contracts/r2/route-slice-A.json`
  - `docs/evidence/r2/slice-A-conformance.md`
  - `docs/evidence/r2/slice-A-negative.md`
- Gate to close: R0+R1 gates open + auth matrix + fixture parity for slice.

4) Mandatory 5-point pre-Scrutiny checkpoint before any final plan lock
- Scope completeness: contract freeze -> row locks -> slice gate continuity
- No-go checks: any dual-writer path or missing evidence file blocks merge.

This is the exact order to execute next. No skipping.

### R0 contract freeze (สัปดาห์ 1)

1. Freeze control-plane contract from Python reference and emit fixture under `docs/contracts/r0/control-plane.v1.routes.json`.
2. Emit companion websocket contract under `docs/contracts/r0/control-plane.v1.events.json`.
3. Add `docs/contracts/r0/negative-cases.md` for auth/403/input-malformed/404/409.
4. Freeze and tag snapshot versions in git (`contract-r0-frozen`).
5. Validation gate: fixture parity against Python app by static scanner + one synthetic run to verify status code, method set, path param schema, and auth middleware order.

### R1 ownership hardening (สัปดาห์ 2)

1. Codify runtime owner in `crates/codinal-runtime/src/ownership.rs` (or adjacent existing module) with explicit lease + startup transitions: `cold_start`, `reconcile`, `locked_active`, `degraded_recovering`.
2. Remove write ambiguity in native host launch: `desktop/native-host/src/host.rs` should only allow Rust-only bootstrap after Rust owner lock is held.
3. Add invariant checks and event logs:
   - `owner_lock_mode == owned`
   - `seed_db_path` writable only by active owner
   - migration lock held during bootstrap and restore
4. Validation gate: 3-path boot matrix (fresh install, existing install, interrupted migration) and explicit evidence log under `docs/evidence/r1/r1-bootstrap-matrix.md`.

### R2 route parity slices (สัปดาห์ 3–6)

Run slices in this order; each slice blocks the next:

1. Slice A — status & security primitives
   - `GET /v1/health`, `GET /v1/version`, `GET /v1/config`, `/v1/secrets/*` (`read/update/delete`)
   - Gate: R0 fixture diff = 0 and auth matrix pass.
2. Slice B — session + messages + plans + goals
   - `GET/POST /v1/sessions*`, `/v1/messages*`, `/v1/plans*`, `/v1/goals*`
   - Gate: route parity + turn lifecycle integration test + websocket replay test for event sequence/ID continuity.
3. Slice C — provider + policy + integrations
   - provider registry, rate-limits, OAuth callback shim, policy settings/evaluations.
   - Gate: provider failover smoke test with at least one provider adapter and signed-policy test for redaction boundaries.
4. Slice D — git + terminal + mcp + workers
   - execution + stream capture endpoints and worker control endpoints.
   - Gate: command replay, stderr/stdout schema check, kill/restart + duplicate-job dedupe behavior.
5. Slice E — review/evidence + artifacts + preview
   - diff/review/evidence routes, tree/search/open endpoints, artifact attachment lifecycle.
   - Gate: deterministic idempotency tests on artifact writes and rollback path.

Per-slice minimum artifacts:
- `docs/contracts/r2/route-slice-<A-E>.json`
- `docs/evidence/r2/slice-<A-E>-conformance.md`
- `docs/evidence/r2/slice-<A-E>-negative.md`

### Audit trail rules (enforced across R0–R2)

1. Every code slice adds one evidence file at the exact moment gate passes.
2. No merge from slice N→N+1 without:
   - fixture diff report
   - negative-case report
   - rollback/restore proof
3. Dual-writer detection check (`native-host` + rust runtime active simultaneously) must remain hard-fail in CI smoke.

## วิธีตรวจว่า “fully rust agentic coding tools” จริงหรือยัง
ตอบสั้น: **ยังไม่** ในสถานะปัจจุบัน เพราะ Rust runtime ยังทำได้ไม่ครบ route/workflow และ editor/composition อิง Tauri/Python อยู่ตามแผน. หลังผ่าน R0–R6 ครบและมี conformance proof ตาม gate ข้างบน จะกลายเป็น fully Rust ได้ครับ.

## 5 scrutiny passes before final plan/spec lock (required)

1. Scope-first sanity
   - Verify objective, non-negotiables, and why each R0→R2 slice exists.
2. Trace-first conformance
3. Claim-vs-fact cross-check
4. Cutover risk audit (rollback, dual-writer, ownership, packaging)
5. Go/No-Go decision audit against objective and evidence thresholds
