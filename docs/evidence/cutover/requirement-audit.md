---
scope: C2-C5 acceptance requirements
owner: runtime cutover
status: incomplete-pending-external-evidence
checked_at: 2026-08-03
---

# C2–C5 requirement audit

This is the requirement-level audit for
[`rust-native-runtime-cutover.md`](../../plan/rust-native-runtime-cutover.md).
It does not promote a stage merely because its deterministic unit suite is
green. `pending` means the required evidence is absent or explicitly blocked.

| Requirement | Current evidence | Status | Remaining proof or blocker |
|---|---|---|---|
| OpenCode Go and DeepSeek streaming/tool conformance | Provider/runtime fixture suites cover incremental SSE, invalid frames, rate limits, interrupted usage, fallback cutoff, read-file continuation, approval resume, and idempotent receipts; fresh credentialed OpenCode Go and DeepSeek runtime smokes pass; the signed packaged GPUI now shows live `GPUI_LIVE_OK`, capability verification, durable interrupt/reload, full diff review, deny, approve-once mutation, and expiry receipts; see [C2a](c2a/gate.md) and [C2b](c2b/gate.md). | pending | C2a still needs formal keyboard/VoiceOver evidence; release notarization remains tracked under C3b. |
| Prompt-prefix determinism, cache telemetry, cost reconciliation, first-delta ordering, and cold/warm benchmark | Prompt compiler/cache events, first-delta-before-receipt, durable reservations, fallback settlement, bounded deltas, the fresh 3-session/90-turn fixture benchmark, credentialed live provider turns, and a same-provider DeepSeek no-cache/repeated-prefix comparison pass locally; the estimator now uses explicit cache-miss tokens. | pending | DeepSeek provider-reported cost remains unavailable; target-hardware/runtime-release reconciliation and the C2a dependency remain open. |
| Kill/restart recovery across turn and migration states | Runtime restart, receipt recovery, cancellation, writer-lock, migration journal, and host shutdown suites pass in `bash verify.sh`. | passed locally | No remaining deterministic failure; production credentialed turn smoke is covered by the C2a/C2b live gate. |
| Writer-lock exclusion, stale-lock diagnostics, migration history, and backup recovery | C1 migration corpus, lock, journal, shadow, and bootstrap tests pass; C1 gate is `passed`. | passed | None in the local fixture scope. |
| WebSocket ordering, cursor replay, reconnect, terminal receipt reload, and bounded retention | Runtime WebSocket/replay tests and GPUI stream/reducer tests pass; the latest runtime suite has 117 passed, 3 credentialed/benchmark tests ignored, and the full verifier passes. | passed locally | Live provider session replay remains part of the pending C2 live gate. |
| Approval durability/idempotence, hash drift, workspace/symlink boundaries, atomic writes, redaction, and Keychain isolation | Policy, storage, runtime, GPUI, and tools suites pass; C4a-c and C5 are `passed`; actual updater rollback is also isolated and verified. The native Keychain UI stored the OpenCode Go credential, and the DeepSeek Keychain-backed smoke passed without a process override. | passed locally | Credential values are intentionally not recorded; the C2a manual approval transaction remains separate. |
| GPUI keyboard/focus/accessibility/reduced-motion/transcript/typing/scroll/reconnect/performance | GPUI 87-test suite, including root Tab/Shift-Tab routing, UI contract, accessibility matrix, local observation, artifact measurement, 3-session/90-turn fixture benchmark, same-provider cache comparison, and fresh signed-app receipt/probe/interrupt/reload/approval-expiry observations pass their local or packaged portions. | pending | Fresh VoiceOver traversal (the Computer Use AX bridge exposed only the window), target 120 Hz/frame/idle/RSS/input-to-paint telemetry, and target-hardware/runtime-release cache-cost reconciliation remain unavailable; current M3 built-in display has no 120 Hz mode. |
| Rust-only signed/notarized package, process/SBOM inspection, install/upgrade/schema rollback | Developer ID-signed release, SBOM audit, process smoke, isolated ZIP extraction, current-candidate `.app.tar.gz` upgrade/rollback test (`1/1`), and fresh rebuilt `/Applications/Codinal.app` audit/process smoke pass; see [C3b](c3b/gate.md). | pending | Notary profile is absent (`notarytool` exit `69`); stapler/Gatekeeper fail closed (`65`/`3`); notarized installed-app upgrade/rollback remains unverified. |

## Stage summary

| Stage | Status | Evidence |
|---|---|---|
| C0 | passed | `docs/evidence/cutover/c0/gate.md` |
| C1 | passed | `docs/evidence/cutover/c1/gate.md` |
| C2a | pending | `docs/evidence/cutover/c2a/gate.md` |
| C2b | pending | `docs/evidence/cutover/c2b/gate.md` |
| C3 | pending | `docs/evidence/cutover/c3/gate.md` and `measurement-ticket.md` |
| C3b | pending | `docs/evidence/cutover/c3b/gate.md` |
| C4a-c | passed | `docs/evidence/cutover/c4a-c/gate.md` |
| C5 | passed | `docs/evidence/cutover/c5/gate.md` |

The overall cutover remains incomplete until every `pending` row has its
required live or target-hardware evidence. No production execution path is
promoted by this audit.

## Latest verification refresh — 2026-08-03

The current signed candidate contains the focus/accessibility patch: keyboard
reachable controls now have visible focus styling, and the composer is
exposed as the labeled AX text field `Composer input` with a tab stop. GPUI
tests passed `87/87`; all-target clippy, `bash verify.sh`, package smoke,
Rust-only audit, deep strict code-sign verification, archive updater rollback
(`1/1`), and the fresh DeepSeek live smoke (`1/1`) passed. The installed app
and release bundle contain matching desktop hash
`19cf3b026a4bdb3f3bc0ef3a54b627595811309257e0d3f1b65dbc78e4915a02`.

The Computer Use bridge still reports only the Codinal window as focused after
Tab/click checks, so formal VoiceOver traversal is not claimed. The current
M3 display remains 60 Hz; target-refresh/input-to-paint/frame/idle/RSS and
provider-reported cost evidence remain open. The current installed candidate
also remains unsigned by Apple notarization: notary profile `69`, stapler `65`,
and Gatekeeper `3`.

## Latest verification refresh — 2026-08-03 (current candidate)

The current signed candidate extends the UI accessibility implementation to
updater/provider/settings controls, workspace-tool tabs, file rows, and the
workspace-tool add control with roles, labels, tab stops where applicable, and
visible focus styling. The packaged and installed desktop hash is
`d3afa61f734036a18dc2d7b68cbf5f1aa237db9be0bb2a5ce893423821eb1f8e`.

GPUI `87/87`, all-target clippy, the complete `bash verify.sh` gate, package
smoke, installed-app smoke, Rust-only audit, deep strict codesign
verification, exact archive updater rollback (`1/1`), and fresh DeepSeek
live smoke (`1/1`) passed. The AX tree now exposes the composer as `Composer
input` plus labeled updater/provider buttons, but the Computer Use bridge still
reports only the window as focused after Tab/click checks. Formal VoiceOver,
target-120-Hz/input-to-paint/frame/idle/RSS, provider-reported cost, and
notarized installed upgrade/rollback evidence remain open; C2a/C2b/C3/C3b
therefore remain pending.

Fresh current-worktree verification rerun (2026-08-03): the runtime-truth
gate passed; `bash verify.sh` passed with `1048` Python tests passed and one
skip, GPUI `87/87`, Rust cutover contract suites passed, policy invariants
passed, and `Codinal verify: PASS`. The live AX recheck reproduced the
window-only focused-element limitation after six Tab presses while exposing
the labeled native controls. No pending C2/C3/C3b requirement is promoted by
this rerun because the missing evidence is external/manual rather than a
deterministic test failure.

Current external/live recheck (2026-08-03): DeepSeek capped live smoke passed
`1/1`; the bounded OpenCode Go Keychain lookup timed out before any request;
provider-reported cost remains unavailable; and notarization/stapling/
Gatekeeper remain blocked at `69`/`65`/`3`. These results preserve the pending
status of C2a/C2b/C3/C3b rather than promoting local-only evidence.

OpenCode Go live correction (2026-08-03): a bounded process-only smoke using
the user-authorized credential passed `1/1` and wrote the real terminal
receipt. This closes the current provider-conformance retry; C2a remains
pending on formal GPUI VoiceOver evidence and the release-level blockers.

Latest local progress (2026-08-03): the signed GPUI candidate now binds
app-level `tab`/`shift-tab` actions to GPUI focus traversal. A live `Tab` then
`Return` hid the navigation sidebar and the sidebar was restored. Startup
Keychain bootstrap/status reads are bounded at two seconds; the current
`SecItemCopyMatching` timeout now yields an explicit unavailable-provider UI
and conservative read-only readiness instead of blocking the app before its
window. The current candidate hashes are desktop
`af738dbdb3fd66a23e973e4b4e7c13c57558aba21fac9dd350571e9eabe05476` and runtime
`74f18cb09e629b7a72e547b9e3afc7434b8b825bdbe16d5b78300d6204d59893`.
GPUI `87/87`, native-host `29/1 ignored`, full verification (`1048/1 skip`),
package/install smoke, exact archive rollback (`1/1`), and strict signing
checks passed. C2a/C2b/C3/C3b remain pending only for formal VoiceOver,
target-hardware/provider-cost reconciliation, and Apple notarized distribution
evidence; no pending row is promoted by local behavior alone.

Latest source/release refresh (2026-08-03): startup now carries a failed
Keychain bootstrap result into the UI, preventing a later status read from
claiming configured credentials when the runtime started with an empty
bootstrap. Fresh full verification passed (`1048` passed, `1` skipped), GPUI
`87/87`, native-host `29 passed / 1 ignored`, release build/install smoke,
strict codesign, Rust-only audit, and exact archive rollback (`1/1`) passed.
The current desktop hash is
`2bcf5991893e6b93e6771bee65385b8c9e2ce6726da0dab9e23de6f3ecf700a9`; runtime
hash is
`74f18cb09e629b7a72e547b9e3afc7434b8b825bdbe16d5b78300d6204d59893`.
C2a/C2b/C3/C3b remain pending only for formal VoiceOver, target-hardware and
provider-cost evidence, and Apple notarized distribution evidence.

Latest startup-safety test refresh (2026-08-03): the native-host regression
asserts that a slow Keychain operation returns the explicit timed-out,
provider-unavailable error before the worker completes. The full native-host
suite passed `30` tests with `1` ignored plus `9` PTY tests, and all-target
clippy passed with `-D warnings`. This remains local evidence only; the stage
statuses and external blockers are unchanged.

Latest C3 measurement runner refresh (2026-08-03): the retained startup
benchmarks now launch the bundled Rust runtime and report
`native_runtime_to_listener` and `desktop_to_native_runtime_listener`; no
Python sidecar is treated as a product path. Five-sample installed-app runs
reported p95 values of `31.61 ms` and `2,217.09 ms`, respectively. Focused
perf tests passed `3/3`. This adds local startup evidence but does not satisfy
the still-missing first-paint/input-to-paint, target-120-Hz, idle/RSS,
VoiceOver, provider-cost, or notarized-release evidence.

Fresh canonical verification after the runner migration (2026-08-03):
runtime truth passed; product tests passed `1049` with `1` skipped and `53`
warnings; GPUI passed `87/87`; runtime passed `116` with `3` ignored; and
`Codinal verify: PASS`. The native-host timeout regression is included in the
full gate. No deterministic local failure remains; the listed external/manual
evidence is still required for promotion.

Latest runtime correction and release refresh (2026-08-03): the first current
DeepSeek retry exposed a real endpoint truncation at the 64-token
high-reasoning capability-probe limit (`finish_reason=length`). A bounded
profile-specific limit was implemented: OpenCode Go remains `64`, DeepSeek is
`256`, and the probe response reports the selected limit. Focused probe tests,
full runtime truth, fresh `bash verify.sh` (`1049` passed, `1` skipped;
GPUI `87/87`; runtime `117` passed, `3` ignored), release build/install,
packaged and installed smoke, Rust-only audit, strict codesign, and the exact
archive rollback (`1/1`) passed. The refreshed Keychain-backed DeepSeek smoke
passed `1/1` with durable budget settlement. Current signed desktop/runtime
hashes are `5e738590b634ae6b69e844711d579203c65c39c0e703e9a235f4d7a42c19b976`
and `4e2ff1e1859291ccf0f1c5303b191cbbb0f0d977eb9804b370fbe9c16ef7019c`.
Formal VoiceOver, target-hardware UI telemetry, provider-reported cost /
release reconciliation, and Apple notarized distribution remain unavailable;
the overall status therefore stays `incomplete-pending-external-evidence`.

Latest current-candidate UI/startup measurement (2026-08-03): installed
artifact sizes are native GPUI `16,285,296` bytes, native runtime `9,815,088`
bytes, app bundle `26,377,300` bytes, ZIP `10,312,983` bytes, tar.gz
`10,307,035` bytes, SBOM `157,979` bytes, and debug symbols `0` bytes.
Rust-native startup p95 is `40.90 ms` runtime-to-listener and `2,248.57 ms`
desktop-to-runtime-listener across five samples. The installed UI's AX tree
exposes the labeled native controls and the screenshot shows the intended
navigation/conversation/context anatomy; the Computer Use bridge still cannot
prove child VoiceOver focus announcements. No visual redesign was claimed by
the cutover, so the visible shell remains intentionally consistent with the
owned UI contract.

Latest canonical verification after bounding live-smoke Keychain access
(2026-08-03): product tests passed `1050` with `1` skipped and `53` warnings;
GPUI passed `87/87`; runtime passed `117` with `3` ignored; runtime truth,
Rust cutover contracts, policy invariants, and the complete `Codinal verify`
gate passed. Release-contract tests passed `5/5`. DeepSeek live smoke passed
`1/1`; OpenCode Go Keychain-only smoke now fails closed in `5.1s` with exit
`2` and no network request, while the earlier process-only OpenCode Go live
smoke remains the successful conformance evidence. External VoiceOver,
target-hardware, provider-cost, and notarization requirements remain pending.

## Superseded native visual-pass and release recheck — 2026-08-03

The earlier cool-light/indigo visual experiment is retained in the C3 ledger
for history but is not the accepted plan target. The contract-aligned
candidate is recorded below.

Fresh checks passed: runtime truth (`11` capabilities, `6` source files), the
complete `bash verify.sh` gate (`1050` passed, `1` skipped, `53` warnings;
GPUI `87/87`; runtime `117` passed, `3` ignored), release-contract tests
`5/5`, canonical perf tests `19/19`, packaged/installed smoke, Rust-only
release audit, strict codesign, and exact archive rollback `1/1`. The
Keychain-backed DeepSeek live smoke passed `1/1`. The current desktop/runtime
hashes are `25819a982620a982c6e7bc6d80555a59b065f49d578f3d5724451b3f2566113e`
and `4e2ff1e1859291ccf0c1f5303b191cbbb0f0d977eb9804b370fbe9c16ef7019c`.

The requirement status remains `incomplete-pending-external-evidence`:
formal VoiceOver and target-120-Hz/input-to-paint/frame/idle/RSS evidence are
unavailable on this host, provider-reported cost remains unavailable, and
notary/stapler/Gatekeeper checks remain `69`/`65`/`3`.

## Latest contract-aligned UI/release recheck — 2026-08-03

The installed candidate now follows the approved UI contract: white canvas,
pale-gray navigation, quiet status labels, light-gray user bubbles, floating
Environment card, centered floating composer, and the pinned shell geometry.
The live capture is [ui-contract-aligned-2026-08-03.jpeg](c3/ui-contract-aligned-2026-08-03.jpeg).
The AX tree still exposes `Composer input`, updater/provider controls, and the
workspace-tools toggle.

Fresh checks passed after this alignment: runtime truth; `bash verify.sh`
(`1050` passed, `1` skipped, `53` warnings; GPUI `88/88`; runtime `117`
passed, `3` ignored); GPUI clippy with `-D warnings`; release-contract tests
`5/5`; canonical perf tests `19/19`; installed/package smoke, Rust-only audit,
strict codesign, and exact archive rollback `1/1`. C2a/C2b/C3/C3b remain
pending only for the documented external/manual evidence.

Latest user-directed continuation (2026-08-03 07:44 +07): the full
`bash verify.sh` gate passed again with the same counts. Keychain-only
DeepSeek live smoke passed `1/1`; Keychain-only OpenCode Go smoke failed closed
with exit `2` because its Keychain item is unavailable, with no network request.
The release recheck still reports notary profile `69`, stapler `65`, and
Gatekeeper `3`. VoiceOver and target-120-Hz evidence remain intentionally
deferred by the user; provider-cost and notarized-distribution evidence remain
pending.

OpenCode credential follow-up (2026-08-03): after the Keychain item became
readable, the live capability probe and a separate sanitized endpoint check
both returned `HTTP 401 AuthError: Invalid API key.` The credential value was
never recorded, and no additional retries were made. OpenCode Go conformance
therefore remains pending on a valid provider credential.

Latest credential recheck (2026-08-03): after the user replaced the Keychain
value, the OpenCode Go smoke and sanitized endpoint check still returned
`HTTP 401 Unauthorized` / `AuthError: Invalid API key.` No secret value was
recorded and no further retry is warranted without a provider-accepted key.

Confirmed-active-key recheck (2026-08-03): the user confirmed the stored key is
active, but one bounded OpenCode Go smoke still failed at capability probe.
Together with the sanitized `401 AuthError: Invalid API key` response, this
keeps C2a pending on provider/account authorization rather than a local
implementation defect.

Endpoint contract correction (2026-08-03): the official OpenCode Go contract
was checked directly and confirms the existing `/zen/go/v1/chat/completions`
endpoint for Kimi K2.7 Code. The temporary `/zen/v1` experiment was reverted;
no runtime endpoint change remains in the worktree.

Latest OpenCode credentialed recheck (2026-08-03): Keychain-only
`bash scripts/smoke-opencode-go-runtime.sh` passed `1/1`; the capability probe,
real `kimi-k2.7-code` turn, and terminal receipt completed successfully. No
credential or response content was recorded. C2a's remaining pending evidence
is the documented manual VoiceOver/release dependency, not provider reachability.
