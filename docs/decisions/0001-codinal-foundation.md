---
number: 0001
title: Codinal foundation — product identity, topology, fork, security, git, provider, ownership, distribution, MVP scope, repo layout, license
status: accepted
date: 2026-07-25
deciders: user (product owner) + grilling session
supersedes: []
---

# ADR-0001 — Codinal Foundation

## Context

สร้าง desktop app ของเราเองโดยยืนภาพ UX จาก Codex Desktop, เปลี่ยน AI model/provider ได้โดย workflow เดิม, ใช้ harness-flow เป็น policy/orchestration SSOT, และ reuse ส่วนที่คุ้มจาก `andrewyng/openworker@54b4bfd` (รีวิวแล้วใน session ก่อน — ดู handoff ต้นฉบับ).

OpenWorker มี UI/shell ที่ดี (React + Tauri, sidebar, transcript, composer, provider picker, MCP) แต่:
- เป็น general coworker ไม่ใช่ coding agent — ไม่มี Git/worktree/inline review
- `SessionManager` เป็น god-object ~3,300+ บรรทัด รวม provider/policy/storage/connectors/automation/socket
- มี P0/P1 security blockers: shell allowlist argv-prefix bypass, local control plane ไม่มี auth, OAuth `app_state` ไม่ consume, ไม่มี OS sandbox, WebView CSP ปิด, `xlsx` advisory

การเริ่มจาก zero หรือ full-fork ไม่คุ้ม; reuse modules เฉพาะส่วน + rewrite ส่วนที่เป็น boundary จึงเป็นทางตรง.

## Decisions

### D1 — Product identity: Coding-agent เป็นแกน
Codinal คือ coding-agent desktop ก่อน. connector/inbox/schedule ใช้ในฐานะ coding-context (PR, issue, runbook) เท่านั้น ไม่ใช่ general assistant. ขยายไป general-coworker ในรอบหลัง.

### D2 — Execution topology: Local-first + optional remote
Policy / TurnEngine / git / worktree รันในเครื่องผู้ใช้. Remote worker (CI-like, batch eval, cloud inference) เป็น opt-in plugin ภายหลัง. ปิด secret exposure นอกเครื่อง.

**Future tension กับ D7 (M5):** เมื่อ remote worker มาถึง (post-MVP), transport ต้องขยายจาก loopback-only เป็น authenticated remote — เป็น known evolution; ใน MVP remote worker เป็น non-goal.

### D3 — Fork strategy: Reuse modules in new product (vendor list VERIFIED)
Vendor-copy จาก OpenWorker เฉพาะ: React/Tauri UI components, TurnEngine, provider adapters, MCP transport, conversation storage (พร้อม provenance note ในแต่ละไฟล์ที่ vendor). Rewrite ใหม่ทั้งหมด: SessionManager (แยก), policy/permissions (ใช้ harness), shell executor (sandbox), local control plane API (auth). ไม่ full-fork; ไม่แบกหนี้ upstream merge.

**Verified by Phase 0a.4 spike (2026-07-25) — see `docs/plan/openworker-boundary-map.md`:**
- **VENDOR (clean):** `engine.py` (TurnEngine 1,033 — zero server deps), `sessions.py` (36), `providers/{base,router,anthropic,openai,gemini}` (zero leakage, `secrets:Any`, tool-call normalize 1 shape), `mcp/*` transport, UI `components/*`
- **EXTRACT (5 slices จาก `server/manager.py:SessionManager` ~3,300):** sessions / events / automations / connectors-gateway / settings — แต่ละ slice หลัง interface, provider/MCP inject
- **REWIRE (3 UI seam files):** `api.ts` + `App.tsx:556-699` WS switch + `itemsFromMessages.ts` + `lib.rs` spawn model
- **REWRITE (ทิ้งเดิม):** ทั้ง `server/app.py` control plane (P0s ครบ — ทุก route unauthenticated, 2 WS spoofable-Origin, `/oauth/callback` CSRF), `permissions.py`/`risk.py` → harness risk-class, `__init__` + policy/approval glue ใน manager.py
- **OUT of v1:** `connectors/integration_tools.py` (4,892 — connector นอก PR/issue เป็น non-goal)

Handoff อ้าง "SessionManager ~3,300" ถูกขนาด แต่ผิดไฟล์: จริงคือ `server/manager.py` ไม่ใช่ `sessions.py` (36 บรรทัด).

### D4 — Security boundary: macOS sandbox + harness risk class + in-process policy
- **Shell sandbox (v1):** direct distribution (ไม่ Mac App Store) + **ไม่ใช้ App Sandbox** เพราะ coding agent ต้อง shell-out ไปยัง CLIs ของ user (homebrew git, nvm, cargo…) ซึ่ง App Sandbox จำกัด; ใช้ `sandbox-exec` profile จำกัดเฉพาะ Python sidecar shell worker (workspace + tmp writable, network off default) — แก้ P0 shell-prefix bypass ตรง ๆ (sandbox ไม่ใช่ allowlist). **รับความเสี่ยง deprecation** ของ `sandbox-exec`. **DE-RISKED 2026-07-25 (Phase 0a.2):** spike notarization status=Accepted, `spctl: accepted (Notarized Developer ID)` — Apple ยอมรับ sandbox-exec usage ใน signed/notarized app (F3 ปิด)
- Approval ตาม harness risk class: `read` auto · `write_local` per-session scope · `exec` & `external` ถามเสมอ (from `standards/agent-guardrails`)
- Secrets เก็บใน macOS Keychain (plaintext JSON ห้าม)
- **Local control plane (amended by F1-reopen, 2026-07-25):** loopback HTTP+WS **+ mandatory per-session bearer token** บนทุก route + WS. P0 #2 แก้ด้วย token auth (defensible pattern — เหมือน Jupyter/VS Code) **ไม่ใช่** ด้วยการเอา network server ออก. เหตุผล: spike 0a.4 พบว่า UI ที่จะ reuse พูด HTTP+WS กับ localhost sidecar (`api.ts` ~90 fetch + 1 WS, `lib.rs:576-583` inject port) — stdio IPC บังคับ rewrite UI bridge ทั้งหมด (expensive). Rust host mint token + inject ผ่าน spawn channel เดียวกับที่วันนี้ inject port. No-bypass ยังคง: `PermissionEngine` ที่ `engine.py` รับเป็น collaborator เป็น harness-controlled chokepoint (engine.py:60-78)
- OAuth callback: ใช้ app URL scheme หรือ loopback HTTP ชั่วคราว — consume `app_state` ให้ถูก (แก้ P0 `/oauth/callback` CSRF ที่ cloud.py:363 mint แต่ไม่ validate)
- WebView CSP เปิด

### D5 — Git lifecycle: Worktree per session + approval apply-back
- 1 session = 1 worktree = 1 branch (สอดคล้อง skill `using-git-worktrees`)
- Subagent หลักรันใน worktree เดียวกัน; ที่ fork/sandbox ได้ nested worktree
- Session commits ลง session branch เท่านั้น (worktree-isolated)
- **Apply-back endpoint (v1):** ผู้ใช้กด Apply → merge session branch เข้า working branch ที่เลือก (default = branch ที่ worktree forked จาก): fast-forward ถ้าได้, มิฉะนั้น merge commit; ทางลัด "Open as PR" ผ่าน `gh` (optional)
- **Conflict = abort + flag; ห้าม auto-resolve** — conflict เกิดตอน Apply (merge session→working branch); abort Apply, session branch + worktree ยัง intact ให้ user แก้ใน session แล้ว retry
- User's main branch ไม่ถูกแตะโดย session; user เป็นคน Apply เท่านั้น

### D6 — Provider contract: Tiered conformance-gated (minimal viable)
- **Tier-1 gate (v1, แกนที่จำเป็นต่อ approval/safety):** (1) tool-call schema ที่ policy port parse ได้, (2) system-prompt fidelity — ผ่าน 2 แกนนี้ = คุมสมบูรณ์ + skill/subagent
- Streaming + JSON mode = **informational** (Tier-1.5, โชว์ใน picker แต่ไม่ block Tier-1) เพื่อไม่ให้ scope suite บานใน MVP
- Tier-2: ผ่าน tool-call schema อย่างเดียว = chat+tools + banner "degraded"
- Tier-3/unknown: chat-only + warning
- **Local (Ollama) = tier-best-effort:** ไม่ fix ว่าถึง Tier-1 (หลาย model tool-calling อ่อน); ตั้งตามผล suite จริง
- **Ownership split (M4):** cases/spec = policy → `harness/conformance/`; runner (execute provider calls, network, credentials) = mechanics → `runtime/conformance/`. คงเส้น D7 (harness=control, runtime=mechanics)

### D7 — Harness ownership: Harness=control, Runtime=mechanics
- **Harness SSOT:** policy/approval, skills, memory (durable), subagent defs, session/event store, git/worktree service, sandbox policy, tool manifest (ชื่อ + perms)
- **Runtime SSOT (OpenWorker-derived):** provider adapters, TurnEngine loop, MCP transport, conversation persistence mechanics, tool implementations
- **Bridge (amended by F1-reopen):** loopback HTTP+WS **+ mandatory per-session bearer token** (Rust host mint + inject). Policy enforcement = `PermissionEngine` collaborator ใน `engine.py` (harness-controlled, engine.py:60-78) — runtime ห้าม bypass. spike 0a.4 พบว่า UI reuse พูด HTTP+WS; stdio บังคับ rewrite UI bridge → token auth ถูกกว่า

### D8 — Distribution: macOS-first, Tauri cross-platform later
- v1: macOS (Apple Silicon + Intel), **direct distribution** (ไม่ Mac App Store) → App Sandbox ไม่ถูกบังคับ (รองรับ D4 shell-out)
- Signing + notarization + Tauri updater ตั้งแต่ v1
- **Python runtime packaging (v1):** embedded Python (`python-build-standalone`) + pinned deps บรรจุใน `.app/Resources`, codesign ทุก binary ใน bundle, notarize ครั้งเดียว — เลือกแทน pyinstaller/venv-at-install เพราะ venv-at-install สร้าง binary ไม่ signed หลังติดตั้ง (ฝ่าฝืน notarization); pyinstaller reproducibility ยาก. **DE-RISKED 2026-07-25 (Phase 0a.3):** cpython-3.12.13 bundle + pip dep (requests) codesign --deep + notarization status=Accepted, `spctl: accepted`, runs post-notarize (F5 ปิด)
- Tauri เก็บทาง cross-platform โดยไม่ lock-in (Windows/Linux รอบหลัง)
- "OpenWorker" เป็น attribution ใน license/notice เท่านั้น — ห้ามใช้เป็นชื่อ product/trademark

### D9 — MVP scope: Lean coding
**In:**
- sidebar / composer / transcript พร้อม approval gates
- provider picker (Tier-1 only) ≥ 2 providers
- worktree per session lifecycle (D5)
- Seatbelt shell worker + harness risk-class approval (D4)
- inline git diff/review ใน WebView (**net-new build** — OpenWorker ไม่มี; ไม่ใช่ vendored)
- Keychain secrets (D4)
- macOS signing + notarization (D8)
- conformance suite runnable; ≥ 3 cloud Tier-1 (1 each: Anthropic / OpenAI / Gemini) + ≥ 1 local (tier-best-effort, อาจเป็น Tier-2)

**Out (non-goals v1):** remote worker runtime · subagent fan-out เต็มรูปแบบ · connector นอก PR/issue · schedule/inbox · Windows/Linux · plugin marketplace · team collab · mobile · self-host server mode · inline review นอก coding artifacts

### D10 — Repo layout: Product repo, harness เป็น subpath (contract-preserving migration)
repo `harness-flow` นี้กลายเป็น product repo "Codinal". harness policy/skills/memory/standards ย้ายไว้ใน `harness/` subpath ทำหน้าที่เป็น vendored control plane ของ Codinal เอง. root มี Tauri app + backend (Rust + Python). docs/ คงไว้ และเพิ่ม `docs/decisions/` (ที่นี่) กับ `docs/plan/`.

**External contract (preserve):** install target `~/.agents/` **ไม่เปลี่ยน** — เฉพาะ layout ใน repo ที่ย้าย; `install.sh` map `harness/*` → `~/.agents/*` เหมือนเดิม ผู้ใช้ harness เดิมไม่กระทบ.

**Migration artifacts (public repo = contract break ต้องสื่อสาร):**
- git tag `last-harness-only` ที่ commit ก่อน migration
- README banner ชี้ไป MIGRATING.md
- `MIGRATING.md` อธิบาย: harness-only users ใช้ tag `last-harness-only` ต่อได้, หรือเฟลิว `harness/` subpath (install path เดิม)
- CHANGELOG entry

### D11 — License: MIT
SPDX MIT. ไฟล์ NOTICE ระบุ attribution ไปยัง `andrewyng/openworker` (MIT) สำหรับ modules ที่ vendor, และบุคคล/โปรเจกต์อื่นตามจริง.

**Verified (2026-07-25):** `andrewyng/openworker@54b4bfd` LICENSE = MIT, "Copyright (c) 2024 Andrew Ng" → MIT-to-MIT compatible; เงื่อนไขเดียวคือรักษา copyright notice ไว้ในไฟล์ที่ vendor + NOTICE. ไม่ใช่ blocker.

## Consequences

**บวก:**
- โครงสร้างสอดคล้องกัน (coding identity → harness policy spine → Seatbelt/risk-class → worktree → Tier-1 provider)
- แก้ P0/P1 ของ handoff ทั้งหมดก่อน ship; P0 #2 (unauthenticated control plane) แก้ด้วย mandatory bearer token บน loopback HTTP+WS (F1-reopen)
- ไม่แบกหนี้ god-object SessionManager และ upstream merge
- ทางขยาย (remote worker, general-coworker, cross-platform) ยังเปิดอยู่

**ลบ / trade-off:**
- ต้อง migration repo ครั้งใหญ่ (ย้าย harness content ไป `harness/`) — bootstrap.sh/install.sh/path ต่าง ๆ ต้องอัปเดต; preserve `~/.agents/` external contract + tag/banner/MIGRATING.md (F6)
- `sandbox-exec` deprecated โดย Apple; ใช้ใน v1 พร้อม notarization spike (Phase 3) — ถ้าไม่ผ่านต้องย้อน (F3)
- Embedded Python packaging (python-build-standalone) + bundle signing/notarization = งานหนัก; spike ใน Phase 0a.3 ก่อน migration; เป็น single biggest distribution risk (F5)
- Conformance suite minimal-viable (2 แกน Tier-1) — อาจขยายภายหลัง (F7)
- การ vendor OpenWorker modules ตัดประโยชน์จาก upstream bug fix; ต้อง track provenance และเลือก backport เอง

## Alternatives considered

- **D1 ทางเลือก:** general coworker ที่เพิ่ม coding workspace; hybrid สองโหมด — ปฏิเสธเพราะ smell ของ harness-flow เป็น coding spine อยู่แล้ว
- **D3 ทางเลือก:** full fork; upstream-friendly thin fork — ปฏิเสธเพราะ identity ต่างกันและต้อง rewrite boundary อยู่แล้ว
- **D4 ทางเลือก:** approval-only no sandbox; container per worker — ปฏิเสธเพราะฝ่าฝืน P0 และ heavyweight ตามลำดับ
- **D5 ทางเลือก:** in-place; worktree per agent — ปฏิเสธเพราะเสี่ยงเขียนทับ / coordination overhead
- **D6 ทางเลือก:** best-effort any model; conformance-only no fallback — ปฏิเสธเพราะ silent break / ปิด user choice
- **D7 ทางเลือก:** harness policy-only; harness owns everything — ปฏิเสธเพราะกลับสู่ god-object / ต้อง rewrite provider stack
- **D7/D4 network control plane (amended twice):** ฉบับ draft แรกวาง "Control Plane API: bind 127.0.0.1 + token auth" ตาม OpenWorker socket design → F1 (scrutinize r1) เปลี่ยนเป็น in-process stdio IPC เพื่อ kill P0 #2 by construction. **F1-reopen (Phase 0a.4 spike, 2026-07-25):** พบว่า UI ที่ reuse พูด HTTP+WS กับ localhost sidecar; stdio บังคับ rewrite UI bridge ทั้งหมด → กลับเป็น loopback HTTP+WS **+ mandatory per-session bearer token** (kill P0 #2 ด้วย auth ไม่ใช่ด้วยการเอา server ออก). no-bypass ยังคงผ่าน `PermissionEngine` collaborator.
- **D8 ทางเลือก:** cross-platform day 1; open beta — ปฏิเสธเพราะตัด surface / ภาระ support หลายสาย
- **D10 ทางเลือก:** harness SSOT + product subpath; monorepo — ปฏิเสธเพราะไม่สอดคล้อง D1/D7 และ overhead monorepo ตอน MVP

## Verification (จะใช้ยืนยันว่า decision ตกผล็อ)

แต่ละ decision ผูกกับ success criteria ที่ตรวจได้ใน `docs/plan/codinal-mvp.md` §"Success Criteria". ADR นี้ไม่ถือว่า "landed" จนกว่า plan จะผ่าน `scrutinize` และผู้ใช้ไฟเขียว.
