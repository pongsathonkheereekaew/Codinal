# Handoff: Codinal — continue Phase 1 (1.2–1.6) → Phase 2+

## เป้าหมายของ session ใหม่

สานต่อ Codinal (macOS coding-agent desktop, model-agnostic, บน OpenWorker modules + harness-flow control plane) ต่อจาก Phase 1.1 ที่ commit แล้ว. **อย่าเริ่ม implement ก่อนอ่าน ADR + plan + boundary map ครบ** — สถาปัตยกรรมผ่าน grilling + 5 รอบ scrutinize + 4 de-risking spikes มาแล้ว.

## สถานะปัจจุบัน (ยืนยันด้วย `git log --oneline`)

| ขั้น | Commit | สถานะ |
|---|---|---|
| Grilling (10 การตัดสินใจ + repo/name/license) | — | ✅ ลง ADR-0001 |
| 5 รอบ scrutinize + แก้ F1–F9 + M1–M5 | — | ✅ |
| Phase 0a.1 control-plane auth | scratch (`/tmp/codinal-spike-0a1/`) | ✅ 4/4 PASS |
| Phase 0a.2 sandbox-exec notarization | scratch (`/tmp/codinal-spike-0a2/`) | ✅ Accepted + spctl |
| Phase 0a.3 embedded-Python notarization | scratch (`/tmp/codinal-spike-0a3/`) | ✅ Accepted + runs |
| Phase 0a.4 boundary map | `370b5fe` | ✅ (re-opened F1) |
| Phase 0b migration | `370b5fe` บน `codinal/phase-0b-migration` | ✅ committed ไม่ push |
| Phase 1.1 policy engine | `7cc163e` | ✅ 20 tests green |

Branch: `codinal/phase-0b-migration` (local). Tag: `last-harness-only` = `fd12b82`. **ยังไม่ push/merge.**

## สถาปัตยกรรม (อ่าน `docs/decisions/0001-codinal-foundation.md` ประกอบ)

สิบเอ็ด decision (D1–D11) + amendments ทั้งหมดอยู่ใน ADR. ข้อสำคัญสำหรับ Phase 1 ต่อ:

- **D4/F3:** `sandbox-exec` profile จำกัด sidecar shell worker (de-risked — notarization ยอมรับ)
- **D7/F1-reopen:** loopback HTTP+WS **+ mandatory per-session bearer token** (ไม่ใช่ stdio — UI reuse พูด HTTP+WS). Policy = `PermissionEngine` collaborator ใน `engine.py` (harness-controlled chokepoint)
- **D7/M6:** policy placement = `runtime/policy/` (engine, runs in sidecar) + `harness/policy/` (declarative manifest, user-editable)
- **D6/F7:** conformance Tier-1 = 2 แกน (tool-call schema + system-prompt fidelity); streaming/JSON = informational; cases ใน `harness/conformance`, runner ใน `runtime/conformance`

## Phase 1 ที่เหลือ (ตาม `docs/plan/codinal-mvp.md` §Phase 1)

- **1.2** EXTRACT 5 slices จาก `server/manager.py:SessionManager` (~3,300, ดู `docs/plan/openworker-boundary-map.md` §server): sessions / events / automations / connectors-gateway / settings — แต่ละ slice หลัง interface, provider/MCP inject. REWRITE glue (`__init__`, policy/approval glue, inbox callbacks) + ทั้ง `server/app.py` (P0). **ต้อง vendor OpenWorker source ก่อน** (clone `andrewyng/openworker@54b4bfd` → `runtime/`).
- **1.3** Control-plane auth: loopback HTTP+WS + bearer token middleware บนทุก route + WS (de-risked แล้วด้วย spike 0a.1). **ต้องการ Rust/Tauri host** (`desktop/src-tauri/`) — ติดตั้ง cargo แล้ว (`rustc 1.97.1`, aarch64).
- **1.4** Keychain secret adapter (แก้ P1 plaintext). Python `keyring` หรือ call `security` CLI.
- **1.5** OAuth module: consume `app_state` (แก้ P0 `/oauth/callback` CSRF ที่ cloud.py:363 mint แต่ไม่ validate).
- **1.6** Conformance cases/spec (`harness/conformance/`) + runner (`runtime/conformance/`) — Tier-1 = 2 แกน.

## Boundary ที่ verify แล้ว (ดู `docs/plan/openworker-boundary-map.md`)

| OpenWorker module | Verdict |
|---|---|
| `engine.py` (TurnEngine 1,033) | **VENDOR** — zero server deps; 4 collaborators + 7 callables |
| `sessions.py` (36), `providers/{base,router,anthropic,openai,gemini}` | **VENDOR** — tool-call normalize 1 shape; live model swap |
| `permissions.py` + `risk.py` | **VENDOR + adapt** ✅ (done in 7cc163e → `runtime/policy/`) |
| `server/manager.py` SessionManager | EXTRACT 5 slices + REWRITE glue |
| `server/app.py` | **REJECT as unit** (P0: ทุก route unauth, WS spoofable Origin, `/oauth/callback` CSRF) |
| UI `surfaces/gui/src/components/*` | **VENDOR** (45 components รอด) |
| UI seam: `api.ts` + `App.tsx:556-699` + `itemsFromMessages.ts` + `lib.rs` spawn | **REWIRE** |

## Verification ที่ทำแล้ว (fresh evidence)

- Phase 0a.1: 4/4 (no-token→401, wrong→401, valid+read→200, valid+exec→403)
- Phase 0a.2/0a.3: notarization `Accepted` + stapler + `spctl: accepted (Notarized Developer ID)`
- Phase 1.1: 20 policy tests + 35 contracts = **55 passed**; `verify.sh` PASS
- OpenWorker boundary map: fan-out 3 explore workers, cite file:line

## Environment

- macOS arm64; Xcode CLT OK; `rustc 1.97.1` + cargo (installed this session); Python 3.9.6 (system) + 3.12.13 (python-build-standalone, bundled in spike)
- Apple Developer account: Team ID `BL28MB2PM9`, "Developer ID Application: Pongsathon Kheereekaew"
- notarytool keychain profile `codinal-spike` stored (ใช้ได้ — **แต่ app-specific password ที่ใช้สร้างมัน transited session เดิม ผู้ใช้ควร revoke + re-store ใหม่ก่อน Phase 5 notarize จริง**)

## สิ่งที่ต้องถาม/ตัดสินใจก่อน Phase 1.2

1. **Vendor strategy:** clone OpenWorker ที่ `runtime/vendor/openworker@54b4bfd/` (read-only reference) หรือ `git mv` เฉพาะไฟล์ที่ vendor เข้า `runtime/` พร้อม provenance header?
2. **1.2 scope per session:** EXTRACT ทั้ง 5 slices ใน session เดียว หรือทีละ slice (sessions ก่อน)?
3. **1.3 ต้องการ Tauri:** สร้าง `desktop/` Tauri skeleton ใน session นี้เลย หรือรวมกับ Phase 4?

## ลำดับแนะนำ

1. `cd ~/harness-flow && git log --oneline -3` ยืนยัน `7cc163e` อยู่บน `codinal/phase-0b-migration`
2. อ่าน `docs/decisions/0001-codinal-foundation.md` + `docs/plan/codinal-mvp.md` + `docs/plan/openworker-boundary-map.md`
3. ถามผู้ใช้ 3 ข้อ决策 above (ใช้ `grilling` — one question at a time)
4. ตัดสินใจเสร็จ → เริ่ม Phase 1.2 (vendor + extract) หรือ 1.3 (Tauri host) ตามคำตอบ
5. ก่อน claim ว่า phase ไหน done → ใช้ `verification-before-completion` (pytest + verify.sh)
6. ห้าม push/merge โดยไม่ได้รับอนุมัติ; commit แต่ละ phase บน branch นี้

## Skills ที่ใช้ต่อ

- `implement` / `tdd` — Phase 1.2/1.4/1.6 (Python)
- `scrutinize` — ก่อนนำเสนอแต่ละ phase ว่า "final"
- `verification-before-completion` — ก่อน claim done
- `handoff` — ถ้า session ยาวอีก

## ข้อควรระวัง

- ห้าม commit secrets/tokens; `.env`/credentials ไม่มีใน repo
- `sandbox-exec` profile ใน spike 0a.2 เป็น simplistic (deny `/Users`) — Phase 3 ต้องเขียน profile เต็ม (allow workspace+tmp, deny rest, network off)
- UI bridge คือ HTTP+WS ไม่ใช่ Tauri commands (อย่าหละไหลไป stdio)
- `xlsx` ไม่มีใน repo นี้ (0b.7 no-op); CI skeleton (0b.6) defer จนกว่า desktop/runtime จะมี code
- ก่อน Phase 5 notarize จริง: ผู้ใช้ต้อง re-store `codinal-spike` keychain profile ด้วย app-specific password ใหม่ (อันเดิม revoke แล้ว)
