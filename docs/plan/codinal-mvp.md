---
title: Codinal MVP — Implementation Plan
status: draft (awaiting user greenlight)
date: 2026-07-25
depends_on: [ADR-0001]
---

# Codinal MVP — Implementation Plan

อ้างอิง decision ใน [`docs/decisions/0001-codinal-foundation.md`](../decisions/0001-codinal-foundation.md). plan นี้ยังไม่ implement จนกว่าผู้ใช้ไฟเขียว.

## 0. โครง target

```text
harness-flow/                       ← product repo "Codinal"
├── desktop/                        ← Tauri app (Rust shell + React UI)
│   ├── src-tauri/                  ← Rust: policy host, worktree, sandbox launcher (sandbox-exec + fallback)
│   └── ui/                         ← React (vendored from OpenWorker + new)
├── runtime/                        ← Python runtime (OpenWorker-derived mechanics)
│   ├── turn_engine/                ← vendored
│   ├── providers/                  ← vendored (Anthropic/OpenAI/Gemini/Ollama)
│   ├── mcp/                        ← vendored transport
│   ├── tools/                      ← tool implementations (manifest อยู่ใน harness)
│   ├── conformance/                ← suite RUNNER (execute provider calls) — M4
│   └── storage/                    ← vendored conversation/event mechanics
├── harness/                        ← control plane SSOT (policy/skills/memory/standards)
│   ├── policy/                     ← risk-class engine + approval port
│   ├── conformance/                ← suite CASES/SPEC (policy) — M4
│   ├── sessions/                   ← session/event store contract
│   ├── git/                        ← worktree service contract
│   ├── sandbox/                    ← sandbox profile (sandbox-exec) + manifest + fallback policy
│   └── ... (skills/memory/standards ที่ย้ายมาจาก root)
├── docs/                           ← decisions/ plan/ wiki/ eval/
├── NOTICE                          ← attribution (OpenWorker ฯลฯ)
├── LICENSE                         ← MIT
└── (scripts/bootstrap.sh อัปเดต)
```

สะพานสำคัญ: **loopback HTTP+WS + mandatory per-session bearer token** — Rust host mint token + spawn Python sidecar + inject token ผ่าน spawn channel (เดียวกับที่วันนี้ inject port). Policy enforcement = `PermissionEngine` collaborator ใน `engine.py` (harness-controlled, engine.py:60-78) — runtime ห้าม bypass `harness/policy` (D7/D4 ฉบับแก้ F1-reopen).

## 1. Phase breakdown

### Phase 0a — De-risking spikes  (gate: 3 hardest unknowns พิสูจน์ก่อนแตะ public repo; ทำบน scratch branch)

**Prereq (procurement, ต้องมีก่อน 0a.2/0a.3):** Apple Developer account (team ID + app-specific password) + macOS build mac ที่ codesign/notarytool ใช้ได้. ถ้าไม่มี → 0a.2/0a.3/Phase 5 ไม่สามารถ spike จริง ต้อง resolve ก่อน.

- 0a.1 ✅ **PASSED 4/4 (2026-07-25)** — Control-plane auth spike: Rust host mint bearer token + spawn Python sidecar + inject token ผ่าน env (spawn channel); loopback HTTP ปฏิเสธ no-token/wrong-token (401); valid-token+read → 200; **valid-token+exec → 403 (PermissionEngine denies → no-bypass ผ่าน Policy)**. Proves D7/F1-reopen. Spike code: `/tmp/codinal-spike-0a1/` (scratch, ไม่ใน repo)
- 0a.2 ✅ **PASSED (notarized 2026-07-25, submission 835067ea…)** — Sandbox spike: mini .app invokes `/usr/bin/sandbox-exec` (deny-write-`/Users` profile). **Evidence:** local run blocks `$HOME` write, hardened-runtime compatible, Developer ID codesign valid, **notarization status=Accepted**, stapler validate OK, `spctl: accepted, source=Notarized Developer ID`. **Closes F3/D4: sandbox-exec is shippable** (Apple notarization ยอมรับ sandbox-exec; deprecation risk documented but not blocking). Zip: `/tmp/codinal-spike-0a2/CodinalSandboxSpike.app.zip`
- 0a.3 ✅ **PASSED (notarized 2026-07-25, submission 29c5596d…)** — Embedded Python spike: cpython-3.12.13 (python-build-standalone) ใน `.app/Resources/python` + pip dep `requests` + C launcher. **Evidence:** bundled python launches (PY 3.12.13), requests 2.34.2 imports, `codesign --deep` + hardened runtime valid, **notarization status=Accepted**, stapler validate OK, `spctl: accepted, source=Notarized Developer ID`, runs post-notarize. **Closes F5/D8: embedded-Python bundle shippable.** Zip: `/tmp/codinal-spike-0a3/CodinalPythonSpike.app.zip`
- 0a.4 **OpenWorker boundary spike:** map โครง `andrewyng/openworker@54b4bfd` จริง → ระบุ module ไหน clean-vendorable (copy ได้สะอาด) vs entangled-ใน-`SessionManager` (ต้อง extract/rewrite). ส่งออก `docs/plan/openworker-boundary-map.md`: vendor-list ชัด + rewrite-list ชัด + effort flag. **verify D3/Phase 2/4 ก่อนลงทุน**

**Gate (go/no-go สถาปัตยกรรม):** ✅ **4 spikes ผ่านครบ (2026-07-25)** — 0a.1 auth 4/4, 0a.2 sandbox-exec notarized Accepted, 0a.3 embedded-Python notarized Accepted, 0a.4 boundary map. **GO → Phase 0b.**

### Phase 0b — Repo migration & scaffolding  (gate: ทุกอย่างใน `harness/` ยัง `harness doctor` ผ่าน + `~/.agents/` contract ไม่เปลี่ยน)
- 0b.1 ย้าย harness content → `harness/` (รายการเต็มใน §0b map ด้านล่าง); root เก็บ product + docs
- 0b.2 อัปเดต `install.sh` `bootstrap.sh` `scripts/harness*` ให้ map `harness/*` → `~/.agents/*` (**external contract เดิม**, idempotent)
- 0b.3 **Migration comms (F6):** git tag `last-harness-only` ที่ commit ก่อนย้าย; README banner → `MIGRATING.md`; CHANGELOG entry
- 0b.4 สร้าง `desktop/` (Tauri) + `runtime/` (Python) skeleton
- 0b.5 `LICENSE` (MIT) + `NOTICE` (attribution OpenWorker © 2024 Andrew Ng + อื่น ๆ)
- 0b.6 CI skeleton: lint, typecheck, `npm audit --omit=dev`, Python lockfile + SBOM
- 0b.7 ตัด/แทนที่ `xlsx` (แก้ supply-chain advisory)

**Gate:** `harness doctor` ผ่านหลัง migrate; `~/.agents/` layout ตรวจเท่าเดิม; tag `last-harness-only` อยู่; CI green; `npm audit` ไม่มี high/critical.

#### §0b.map — migration map (ครบตาม install.sh จริง)

| ต้นทาง (root) | ปลายทาง | หมายเหตุ |
|---|---|---|
| `AGENTS.md` | `harness/AGENTS.md` | install.sh:15 |
| `scripts/` | `harness/scripts/` | install.sh:29 (รวม `harness` CLI, `harness_host.py`, `lib/`, `adapters/`) |
| `config/` | `harness/config/` | install.sh:34 (hosts.yaml, skills.yaml) |
| `schemas/` | `harness/schemas/` | install.sh:35 |
| `standards/` | `harness/standards/` | install.sh:39 |
| `commands/` | `harness/commands/` | install.sh:40 |
| `skills/` | `harness/skills/` | install.sh:44 |
| `memory/` | `harness/memory/` | install.sh:48 |
| `adapters/` | `harness/adapters/` | install.sh:74,95 (CLAUDE.md, claude-settings.defaults.json) |
| `templates/` | `harness/templates/` | harness content (agents-harness, project-wiki, verify.sh) |
| `hermes/REVIEW-HOME.md` | **ลบ** | stray — README บอก hermes live ใน `agentmonitor` repo |
| `verify.sh` | คง root (product) | เรียก `harness/` content — อัปเดต path ref |
| `backup.sh` `CHANGELOG.md` `MANIFEST.md` `NEW_MACHINE.md` `README.md` `requirements-dev.txt` | คง root (product) | อัปเดตเนื้อหาให้สอดคล้อง layout ใหม่ |
| `docs/` | คง root | เพิ่ม `docs/decisions/` `docs/plan/` (อยู่แล้ว) |
| `tests/` `.github/` `.githooks/` `.cursor/` `.zcode/` | คง root | product/test infra |

`install.sh` ใหม่อ่าน `$ROOT/harness/{AGENTS.md,scripts,config,schemas,standards,commands,skills,memory,adapters}` ทั้งหมด — ครบตามที่เดิม rsync. Phase 0a.1 spike จะ verify mapping นี้จริงใน scratch branch ก่อน 0b.1.

### Phase 1 — Control plane core  (gate: policy ห้าม bypass ได้)
- 1.1 `harness/policy` risk-class engine (read/write_local/exec/external) + approval port
- 1.2 แยก `SessionManager` (`server/manager.py` ~3,300 จริง, ไม่ใช่ `sessions.py`) → EXTRACT 5 slices (sessions/events/automations/connectors-gateway/settings) + REWRITE glue (per `docs/plan/openworker-boundary-map.md`). ทำทีละ vertical slice พร้อม test/commit แยก โดยเริ่ม `sessions`; checkout source ที่ pin ใน `/tmp` แล้ว copy เฉพาะ module ที่ใช้พร้อม provenance header (ไม่ commit source tree ทั้งก้อน). **Progress:** `sessions` และ `events` อยู่ใน `runtime/` แล้ว; อีก 3 slices + glue ยัง pending.
- 1.3 Control plane auth (F1-reopen): สร้าง Tauri skeleton ขั้นต่ำใน phase นี้; loopback HTTP+WS **+ mandatory per-session bearer token** บนทุก `/v1/*` route + 2 WS; Rust host mint token + inject ผ่าน spawn channel (เดียวกับ `lib.rs:576-583` ที่ inject port). P0 #2 แก้ด้วย auth ไม่ใช่ด้วยการเอา server ออก (stdio บังคับ rewrite UI bridge — แพง; spike 0a.4)
- 1.4 Keychain secret adapter (แก้ P1 plaintext)
- 1.5 OAuth module: consume `app_state` ให้ถูก (แก้ P0)
- 1.6 `harness/conformance` **cases/spec** (policy) + `runtime/conformance` **runner** (mechanics, M4) — **Tier-1 gate แค่ 2 แกน (F7):** (1) tool-call schema ที่ policy port parse ได้, (2) system-prompt fidelity; streaming + JSON mode = informational (Tier-1.5, โชว์ใน picker ไม่ block)

**Gate:** negative test ว่าทุก `/v1/*` route + WS ปฏิเสธ request ไม่มี/ผิด bearer token; runtime sidecar ไม่สามารถ exec tool โดยไม่ผ่าน `PermissionEngine` (harness-controlled); conformance runner รันได้.

### Phase 2 — Runtime (OpenWorker-derived mechanics)  (gate: Tier-1 turn สมบูรณ์ผ่าน policy)
- 2.1 vendor TurnEngine + providers (Anthropic/OpenAI/Gemini/Ollama) พร้อม provenance header
- 2.2 vendor MCP transport + conversation storage
- 2.3 tool registry: manifest ใน `harness/policy`, impl ใน `runtime/tools`
- 2.4 wire runtime → control plane (subscribe model; ห้าม direct exec)
- 2.5 รัน conformance → ประกาศ Tier-1 เบื้องต้น (≥ 3 cloud; local = tier-best-effort ตามผล suite จริง)

**Gate:** Tier-1 turn ครบ (prompt → tool-call → approval → result) โดยผ่าน policy port ทุกขั้น.

### Phase 3 — Shell + Git services  (gate: sandbox block + worktree lifecycle + Apply สมบูรณ์)
- 3.1 **Sandbox (F3):** `sandbox-exec` profile จำกัดเฉพาะ Python sidecar shell worker (workspace+tmp writable, network off default); **notarization spike ก่อนเขียนเต็ม** — ยืนยันว่า signed/notarized build ที่ใช้ `sandbox-exec` ผ่าน Gatekeeper จริง; ถ้าไม่ผ่านย้อน App Sandbox (พร้อมข้อจำกัด shell-out) หรือ Seatbelt API ที่ supported — แก้ P0 shell-prefix + P1 no-sandbox
- 3.2 `harness/git` worktree service: 1 session = 1 worktree = 1 branch
- 3.3 git status/diff/stage backend + **Apply-back endpoint (F4):** ผู้ใช้กด Apply → merge session branch เข้า working branch (default = branch ที่ forked จาก: fast-forward ถ้าได้ มิฉะนั้น merge commit); optional "Open as PR" ผ่าน `gh`; ไม่ auto-push
- 3.4 **Conflict = abort + flag (F9):** conflict ตอน Apply (merge session→working) → abort Apply, session branch + worktree intact; ห้าม auto-resolve

**Gate:** negative test เขียนนอก workspace ถูก block; notarization spike ผ่าน; E2E สร้าง worktree → commit → Apply ไป working branch → user's main branch ไม่ถูกแตะ.

### Phase 4 — UI  (gate: E2E success scenario ผ่าน)
- 4.1 reuse sidebar/composer/transcript/provider-picker จาก OpenWorker (filter Tier-1)
- 4.2 approval UI ตาม risk-class
- 4.3 **inline git diff/review ใน WebView — net-new build (F8, ไม่ใช่ vendored)** + CSP on (แก้ P1)
- 4.4 session/worktree management UI
- 4.5 model swap mid-session

**Gate:** E2E ใน §3 ผ่าน.

### Phase 5 — Distribution  (gate: signed .app เปิดได้ ไม่มี Gatekeeper warning)
- 5.1 macOS signing + notarization ของทั้ง bundle — embedded Python (D8/F5) + `sandbox-exec` profile (Phase 3.1) codesign ครบ
- 5.2 Tauri updater + update channel
- 5.3 build pipeline CI (release artifact)
- 5.4 smoke E2E บน clean macOS user

**Gate:** .app signed/notarized เปิดบนเครื่องสะอาดผ่าน.

## 2. Security fix mapping (handoff → phase)

| handoff | ระดับ | แก้ที่ |
|---|---|---|
| shell allowlist argv-prefix bypass | P0 | Phase 3.1 (Seatbelt) |
| local control plane ไม่มี auth | P0 | Phase 1.3 — mandatory bearer token บน loopback HTTP+WS (F1-reopen) |
| OAuth `app_state` ไม่ consume | P0 | Phase 1.5 |
| ไม่มี OS sandbox | P1 | Phase 3.1 |
| secrets plaintext JSON | P1 | Phase 1.4 (Keychain) |
| WebView CSP ปิด | P1 | Phase 4.3 |
| `xlsx` advisory | supply | Phase 0b.7 |
| Python dep ไม่มี lock/SBOM | supply | Phase 0b.6 |

## 3. Success Criteria (verifiable — ถือเป็น "MVP done")

1. **E2E scenario:** เปิด repo → สร้าง session ใน worktree → model แก้ไฟล์ → approval gate ไฟ → diff โชว์ inline → commit ลง session branch → ผู้ใช้กด Apply → merge ไป working branch → **`git log` ของ user's main branch ไม่เปลี่ยน**
2. **Provider swap:** เปลี่ยน Tier-1 model **ระหว่าง turn เท่านั้น** (ปิด tool-sequence ที่รันอยู่บน model เดิมก่อน) โดยไม่ restart; turn ถัดไปใช้ model ใหม่, tool-call ยัง parse ผ่าน policy port ได้
3. **Sandbox negative test (state-based):** สคริปต์พยายามเขียนนอก workspace → **ไฟล์ไม่ถูกสร้างบนดิสก์** (primary); exit code ≠ 0 (secondary — ยอมรับว่าเครื่องมือบางตัวจับ EPERM แล้ว exit 0)
4. **Conformance:** suite ผ่าน 2 แกน Tier-1 (tool-call schema + system-prompt fidelity) สำหรับ ≥ 3 cloud models; local ผ่านตามผลจริง (tier-best-effort)
5. **Distribution:** `.app` signed + notarized (embedded Python + sandbox) เปิดบน macOS user สะอาด **ไม่มี** Gatekeeper warning (ต้องมี Apple Developer account — Phase 0a prereq)
6. **Supply chain:** `npm audit --omit=dev` ไม่มี high/critical; Python lockfile + SBOM อยู่ใน release
7. **No P0/P1 คงค้าง:** ตาราง §2 ทุกแถว status = fixed หรือ by-construction (มี negative test ยืนยัน)
8. **Migration:** git tag `last-harness-only` อยู่; `~/.agents/` layout หลัง install เท่าเดิม; MIGRATING.md ตีพิมพ์

## 4. สิ่งที่ตั้งใจ **ไม่** ทำใน v1 (non-goals)

remote worker runtime · subagent fan-out เต็มรูปแบบ · connector นอก PR/issue · schedule/inbox · Windows/Linux · plugin marketplace · team collab · mobile · self-host server mode · inline review นอก coding artifacts

## 5. Risks & mitigations

| risk | mitigation |
|---|---|
| `sandbox-exec` deprecated; notarization reject (F3) | Phase 3.1 notarization spike ก่อนเขียนเต็ม; fallback App Sandbox / Seatbelt supported API |
| `sandbox-exec` profile ซับซ้อน | profile contract test ต่อ tool; ปิด network default; allowlist path ไม่ใช่ prefix |
| embedded Python bundle signing/notarization หนัก (F5) | Phase 0a.3 spike ก่อน migration; python-build-standalone + codesign ทุก binary; reproducible build |
| conformance suite scope creep | Tier-1 แค่ 2 แกน (F7); streaming/JSON = informational |
| OpenWorker module license/attribution drift | `NOTICE` + provenance header ทุกไฟล์ที่ vendor; license = MIT verified |
| Tauri WebView diff perf กับไฟล์ใหญ่ | virtualization + size cap + แจ้ง "too large to inline" |
| migration ทำลาย harness users เดิม (F6) | preserve `~/.agents/` contract + tag `last-harness-only` + README banner + MIGRATING.md |
| apply-back conflict สับสน (F4/F9) | Apply = merge session→working branch; conflict abort + flag; session/worktree intact |

## 6. Open questions (resolve ก่อน/ระหว่าง implement — ไม่บล็อก plan)

- Tauri version pin + Rust toolchain pin
- per-provider Keychain item layout
- update channel default (stable/beta) + auto-update on/off
- telemetry/crash policy (default opt-in)
- หาก Phase 3.1 spike ไม่ผ่าน: เลือก App Sandbox (รับข้อจำกัด shell-out) หรือ Seatbelt supported API — เป็น decision gate ไม่ใช่ open question

## 7. ลำดับการไฟเขียว

1. plan นี้ผ่าน `scrutinize` (5 รอบ)
2. ผู้ใช้ยืนยัน plan
3. Phase 0a spikes (บน scratch branch, ไม่แตะ public) → go/no-go gate
4. Phase 0b public migration → แต่ละ phase ยังหยุด confirm ได้
