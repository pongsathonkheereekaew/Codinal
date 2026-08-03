---
stage: C2a
owner: codinal-providers/runtime/gpui
dependencies: [C1]
status: pending
---

# C2a OpenCode Go execution gate

Exact fixture commands:

```text
cargo test --manifest-path crates/codinal-providers/Cargo.toml -- --nocapture
cargo test --manifest-path crates/codinal-runtime/Cargo.toml --lib -- --nocapture
cargo test --manifest-path crates/codinal-runtime/Cargo.toml opencode_go_read_file_tool_round_trips_through_the_same_turn -- --nocapture
cargo test --manifest-path crates/codinal-runtime/Cargo.toml --lib opencode_go_apply_patch_approval_resumes_the_same_turn -- --nocapture
cargo test --manifest-path desktop/control-plane-client/Cargo.toml -- --nocapture
cargo test --manifest-path desktop/gpui/Cargo.toml -- --nocapture
```

Fixture/credential class: pinned local Chat Completions SSE fixtures with no
live credential. The manual gate must additionally run the complete GPUI path
with `CODINAL_EXPERIMENTAL_EXECUTION=1` and a separately approved OpenCode Go
credential.

Expected result: provider/model/effort is visible, Run→Interrupt works,
approval shows the full one-file diff, approve-once/deny/expiry are durable,
and a terminal receipt reloads after reconnect/restart.

Rollback: delete only the isolated GPUI/runtime fixture directory.

Stop condition: capability drift, approval bypass, missing receipt, or a
headless/JSON-only path substituted for the GPUI flow.

Live API smoke (2026-08-01, credential redacted): OpenCode Go `/models`
returned HTTP 200. A one-shot `kimi-k2.7-code` streaming completion using the
Rust adapter request shape (`stream=true`, `reasoning_effort=medium`) returned
HTTP 200, 38 SSE events, a terminal `[DONE]`, and the exact sentinel response
`LIVE_OK`. This validates the provider endpoint contract; the full approved
GPUI/runtime flow remains required before this gate can pass.

The repeatable Rust-runtime live probe is intentionally ignored by default and
reads only from the macOS Keychain item used by the desktop host (or the
process-only `CODINAL_LIVE_OPENCODE_GO_API_KEY` override). It does not write the
credential to the repository:

```text
bash scripts/smoke-opencode-go-runtime.sh
```

Expected result: the runtime route returns `202 Accepted`, the real provider
stream reaches `[DONE]`, and the durable terminal receipt contains exactly
`LIVE_OK`. The GPUI packaged-app run remains a separate manual gate.

Current live preflight (2026-08-02): the script failed closed with exit `2`
because the `opencode-go` Keychain item was unavailable; no provider request
was made.

Live preflight recheck during the final verification run returned the same
exit `2` and the same fail-closed message; no request or spend occurred.

Fresh credentialed live smoke (2026-08-02, key redacted) passed after the
bounded capability probe was raised from 32 to 64 output tokens for the live
Kimi reasoning profile. The real stream completed, the probe returned the
required `codinal_capability_probe` tool call, and the terminal receipt matched
`LIVE_OK`, `opencode-go`, `kimi-k2.7-code`, and `medium`. The key was supplied
only through the process environment and was not persisted. The complete GPUI
Safety UI path remains the separate manual gate.

The live response also exposed nullable continuation fields (`id` and function
`name`) in a tool-call fragment. The OpenCode Go parser now ignores those
nullable continuation fields while preserving the initial validated identity;
the pinned SSE fixture covers that exact fragment shape.

Live runtime smoke (2026-08-01, credential redacted): passed. The Rust
runtime route returned `202 Accepted`; the real OpenCode Go stream completed;
and the durable terminal receipt matched `LIVE_OK`, `opencode-go`,
`kimi-k2.7-code`, and `medium`. The credential was supplied through transient
stdin for this run and was not persisted.

Deterministic C2a increment (2026-08-02, fresh): providers `16 passed`; runtime
`113 passed, 3 ignored` (two credentialed live probes plus the opt-in local
benchmark); storage `28 passed`; control-plane client `15 passed`;
and GPUI `85 passed`. The exact read-file continuation and apply-patch
approval-resume tests each passed, as did the full verifier and all-target
`-D warnings` checks for the C2a crates. OpenCode Go SSE is parsed incrementally; the runtime
compiles a bounded deterministic prompt envelope, persists `prompt_compiled`
cache-prefix telemetry, and preserves provider cache fields as unknown when a
provider does not report them. It persists bounded `assistant_delta` events
with `first_delta_ms` before the terminal receipt; the fixture read-file loop
sends a `read_file` result back through the same turn ID; and an approved
`apply_patch` resumes the same durable turn with an assistant tool call plus
bounded mutation result. Provider transport coverage also proves an HTTP 429
fails closed without emitting deltas and cancellation after a partial SSE chunk
stops before provider usage or `[DONE]`. A repeated completed `turn_id` returns
the authoritative receipt without a new provider request. The complete GPUI
Safety UI manual path remains required, so this gate stays `pending` even though
the separately credentialed runtime smoke now passes.

Native GPUI observation (2026-08-02, packaged `/Applications/Codinal.app`):
after the OpenCode Go credential was saved through the native Keychain prompt
and the app/runtime were restarted, the UI showed `Ready`, `Full access`, and
`opencode-go · kimi-k2.7-code · medium`. A composer turn asking for the exact
sentinel `GPUI_LIVE_OK` completed; the runtime `turn_receipts` row recorded a
completed OpenCode Go turn with that text and one receipt was shown in the
Environment pane. This proves the packaged UI can reach the live Rust runtime
and persist a terminal receipt.

The same UI session requested a one-file `apply_patch` diff. The provider first
returned the complete diff as assistant text without creating a pending approval;
an explicit confirmation then returned `provider_request_failed`, with no file
written. No `Run -> Interrupt` observation, full diff approval/deny/expiry
transaction, or reconnect/restart receipt reload was obtained in this session.
The manual Safety UI gate therefore remains `pending`; the deterministic
read-file and apply-patch approval-resume tests remain the authoritative local
coverage for those branches.

Latest credential state (2026-08-02): OpenCode Go was saved through the native
Keychain UI and DeepSeek was saved to the same Keychain service for the next
native/provider smoke. Credential values are not recorded here.

The Rust provider catalogue now carries the pinned OpenCode Go/DeepSeek
profiles, typed effort variants, wire-field mapping, bundled revision, and
explicit `models.dev`/endpoint-probe status. An unconfigured health response
remains `probe_status=not_run`; deterministic fixture turns use the explicit
bounded probe lease and record `probe_status=passed`. Endpoint conformance is
still not implied by synchronized metadata, and the approved live probe remains
required for this gate.

Artifact checksums (deterministic slice):

```text
11afbe4bd8ecb8a88b8a2c007c0a1b2b5b57a2b16136d5bf67cf901210c62eda  crates/codinal-providers/src/prompt.rs
0f958f301efc7d52117fc8de5493aba755b56ade18eb93eb591c4baca5751849  crates/codinal-providers/src/lib.rs
0bf93d4aa02b15751077bd2796842abf1ef36e16324ab752ba7a0c8996191af5  crates/codinal-providers/src/catalogue.rs
ded3d5b05b1d34430d9c9515a718d639b7b6252ced5ebb6bb81e9300ac92cda3  crates/codinal-runtime/src/lib.rs
8f2561e67bdbac9cd931e617bb499a1c4e373138d2c577293eadd701bae6e184  crates/codinal-storage/src/lib.rs
2dff003e04bdf827bfbc47d742a7d2dfd0e19b94074bdaf4f28bfcceb097e35b  desktop/control-plane-client/src/lib.rs
```

Manual/live artifact checksum: pending.

Initial packaged UI correction (2026-08-02, before native Keychain
authorization): the GPUI projection now renders
bounded terminal receipts as typed `TimelineKind::Receipt` blocks when the
runtime has no durable message rows, so a completed live turn no longer leaves
the conversation center blank. The provider settings surface also exposes an
explicit capability-probe action; the native host now admits an owner runtime
in `degraded`/`capability_probe_required` mode so the UI can perform that
explicit probe after restart. Focused UI-model, control-plane-client, and
native-host tests passed; the full `bash verify.sh` passed. The rebuilt signed
candidate was packaged and installed at `/Applications/Codinal.app`, but the
initial live UI recheck was held by the macOS Keychain permission dialog
for the existing OpenCode Go item. No C2a manual Safety UI pass is claimed
until that local re-authorization and the Run/Interrupt, approval, and
reconnect/reload observations complete.

Fresh packaged GPUI recheck after native Keychain authorization (2026-08-02,
signed `/Applications/Codinal.app`): the first capability probe failed closed
with `provider_request_failed` / `Resource temporarily unavailable (os error
35)`; an immediate retry succeeded. The UI then showed `Ready`, `Full access`,
`Provider capability verified`, and an enabled `Run turn` action. A composer
turn asking for the exact sentinel `GPUI_LIVE_OK` completed. The visible
transcript rendered six blue `Terminal receipt` cards, and the latest
`turn_receipts` row recorded `status=completed`, `text=GPUI_LIVE_OK`,
`provider=opencode-go`, `model=kimi-k2.7-code`, `effort=medium`, and
`capability_snapshot.probe_status=passed`. This proves the repaired packaged
GPUI projection reaches the live Rust runtime and reloads the terminal receipt
projection for the current session. A follow-up bounded live turn was started
from the same composer and the control visibly changed to `Interrupt turn`;
clicking it returned the UI to `Run turn`. The newest `turn_receipts` row then
recorded `status=interrupted` and `reason=cancellation`, proving the interrupt
path reaches a durable terminal state. The full diff approve/deny/expiry
transaction and reconnect/restart receipt reload remain unobserved; C2a
therefore remains `pending`.

Fresh session-reload observation (2026-08-02): selecting the current task again
after the interrupted turn caused the signed GPUI session to synchronize and
reload the durable projection. The UI visibly restored the interrupted receipt
(`cancellation`) and the earlier completed `GPUI_LIVE_OK` receipt, while the
Environment pane reported the selected session synchronized and no pending
approvals. This proves receipt reload after a session reconnect/reload. The
full approval review/decision/expiry transaction is still unavailable in the
live provider path: the probe returned no `pending_approvals` row and no file
was created, so C2a remains `pending` at the approval boundary.

Process-restart confirmation (2026-08-02): the exact signed app process was
terminated and reopened against the same runtime data directory. It restored
the interrupted `cancellation` receipt and the completed `GPUI_LIVE_OK` receipt
without another Keychain prompt, initially showed `capability_probe_required`,
and disabled `Run turn` as designed. The first post-restart capability probe
again failed transiently with `Resource temporarily unavailable (os error
35)`; retrying it returned `Ready`/`Full access`, `Provider capability
verified`, and an enabled `Run turn`. This is fresh restart-level receipt
reload and explicit-readiness evidence; approval review/decision/expiry remains
the only unobserved C2a UI branch.

Live approval/expiry correction (2026-08-03, signed packaged app): a first
approve-once attempt exposed a real approval-identity defect. The provider
reused `apply_patch_0` on a later turn; approval IDs were derived only from
`session_id + tool_call_id`, so the UI sheet showed a fixture diff while the
runtime applied an earlier test-only `gate.md` request. The test-only line was
restored immediately and the runtime now binds approval IDs to the durable
turn ID. Policy regression coverage proves the same tool-call ID produces
distinct IDs across turns; the runtime approval-resume test still passes.

After rebuilding and reinstalling the signed candidate, the live GPUI path
created a distinct approval for an isolated existing fixture. The approval
sheet visibly showed `write_local`, `apply_patch`, exact path, source hash,
patch hash, full bounded diff, and explicit Approve/Deny controls. Deny
persisted `approval_denied` with no mutation. A subsequent approve-once request
persisted a different turn-bound approval ID, changed only the isolated fixture,
and produced a completed receipt: `Patch applied successfully to
docs/evidence/cutover/c2a/live-approval-fixture.txt`. The fixture was then
moved to `/tmp` as a recoverable test artifact; no probe file remains in the
workspace.

Approval expiry increment (2026-08-03): pending approvals now persist a
bounded expiry timestamp in the durable request, expire through the runtime
route with an `approval_expired` event/receipt, and expose the timestamp in the
GPUI review sheet. For the isolated live expiry test, the persisted test row's
expiry was set to `0` to exercise the terminal branch without waiting five
minutes. The signed GPUI rendered `approval_expired`, showed “Approval expired;
session turn failed,” and returned the composer to `Run turn`. Runtime and
GPUI regression tests cover expiry parsing, WebSocket event mapping, and the
running-turn reset. C2a remains `pending` only until the remaining keyboard/
VoiceOver and final release evidence are reconciled; the live approval,
approve, deny, expiry, interrupt, receipt, and restart branches are now
observed.

Fresh verification refresh (2026-08-03): the policy suite passed `18/18`, the
runtime library suite passed `116` with `3` ignored tests, and the GPUI suite
passed `86/86`. Formatting checks and all-target `clippy -D warnings` passed
for policy, runtime, and GPUI. After regenerating the runtime-truth artifacts,
the complete `bash verify.sh` gate passed: `1048` Python tests passed with one
skip, the desktop shell passed `86/86`, and all Rust cutover contract suites
passed. The latest changed-source checksums are
`a411dd75d6c22d5c1c3196e925b914d038c3dd081c7791774540056ef980a3ec` for
`crates/codinal-policy/src/lib.rs`,
`1d5543c690e5763fc6874cde930c454e82ca3449773756843ad2e53a6ba4f8f0` for
`crates/codinal-runtime/src/lib.rs`, and
`8bbb937b9797481e8c86f00884ee406282f67f76060a7c413da294f0889ef63a` for
`desktop/gpui/src/ui_model.rs`. No credential or secret is recorded here.

Keyboard-focus implementation refresh (2026-08-03): the signed GPUI root now
handles unmodified `Tab` and `Shift-Tab` by calling GPUI's
`Window::focus_next`/`focus_prev`; platform/control/alternate-modified Tab is
left untouched. The new routing test is covered by the 87-test GPUI suite, and
the exact signed candidate was installed at `/Applications/Codinal.app` after
the release build, Rust-only audit, and deep strict code-sign verification all
passed. Computer Use's AX snapshot continued to report only the window after
six Tab presses and after a button click; the screenshot remained usable, but
this bridge did not expose the focused child. This is therefore an
inconclusive live AX result, not a VoiceOver/focus pass. Formal VoiceOver
announcements and traversal remain pending, so C2a is not promoted.

Latest UI source checksum for this refresh:
`206255e6b64f3a01e8e480e3bad05aa12c92b52486686b00364d92052d2ab7af`
(`desktop/gpui/src/main.rs`).

Bounded current-provider recheck (2026-08-03): the process override was
absent, and a five-second read-only Keychain lookup for `opencode-go` timed
out. The longer smoke was stopped before the runtime test began; no provider
request or spend occurred. This is a Keychain-access blocker, not a provider
conformance failure, and the earlier credentialed packaged GPUI evidence
remains the authoritative OpenCode Go live observation.

Latest focus/accessibility implementation refresh (2026-08-03): reachable
navigation rows, task creation, navigation toggle, disabled approval/run/
interrupt controls, and the Environment control now expose keyboard-visible
focus styling. The composer is now an explicit GPUI `TextInput` with the
accessible label `Composer input` and a tab stop. The exact signed candidate
passed GPUI `87/87`, all-target `clippy -D warnings`, and the complete
`bash verify.sh` gate (`1048` Python tests passed, one skipped). Its desktop
binary hash is
`19cf3b026a4bdb3f3bc0ef3a54b627595811309257e0d3f1b65dbc78e4915a02`, and the
installed `/Applications/Codinal.app` contains the same hash. Package smoke,
Rust-only audit, deep strict code-sign verification, archive updater rollback
(`1/1`), and the fresh DeepSeek live smoke (`1/1`) passed.

The fresh Computer Use accessibility tree now exposes `text field Composer
input`, which confirms the source-level accessibility improvement. It still
reports the window rather than a focused child after click/Tab checks, so this
remains an inconclusive AX bridge result and not formal VoiceOver evidence.

Current Keychain recheck (2026-08-03): a bounded five-second read-only lookup
for `opencode-go` again timed out. The OpenCode smoke was not allowed to run
past that credential-read boundary, so this recheck made no provider request or
spend. The previously recorded credentialed OpenCode Go GPUI/runtime evidence
remains authoritative; a fresh repeat requires local Keychain authorization.

Latest signed UI-control candidate refresh (2026-08-03): updater, provider
credential, provider capability, and delete-credential controls now expose
button roles, labels, tab stops, and visible keyboard-focus styling; workspace
tool tabs, file rows, and the workspace-tool add control received the same
focus treatment. The candidate desktop hash is
`d3afa61f734036a18dc2d7b68cbf5f1aa237db9be0bb2a5ce893423821eb1f8e`, matching
the installed `/Applications/Codinal.app` binary. GPUI `87/87`, all-target
clippy, the full verifier, package smoke, Rust-only audit, updater archive
rollback (`1/1`), installed-app smoke, and the fresh DeepSeek live smoke
(`1/1`) passed.

The fresh AX snapshot exposes the composer as `text field Composer input` and
the updater/provider controls as labeled buttons, including `Check for
updates`, `Restore previous signed version`, `Set opencode-go credential…`,
`Set deepseek credential…`, and `Add custom provider`. The Computer Use bridge
still reports the window rather than a focused child after Tab/click checks;
formal VoiceOver traversal and announcements therefore remain unverified.

Current live recheck (2026-08-03): the Keychain-only OpenCode Go lookup was
bounded at five seconds and timed out before the runtime test began. No
provider request or spend occurred; earlier credentialed packaged evidence
remains the authoritative live observation until local Keychain access is
available again.

Bounded credentialed live recheck (2026-08-03): using the user-authorized
process-only credential (not persisted or printed),
`bash scripts/smoke-opencode-go-runtime.sh` passed `1/1`. The real OpenCode Go
turn wrote the terminal receipt with no test failure. This supersedes the
Keychain-access-only timeout for provider conformance, but does not replace
the pending GPUI VoiceOver evidence or notarized release gate.

Latest startup and keyboard recheck (2026-08-03): the GPUI app now registers
`tab` and `shift-tab` as app-level actions bound to `Window::focus_next` and
`Window::focus_prev`; the existing modifier-guarded key-down path remains as a
fallback. The signed candidate was installed at `/Applications/Codinal.app`
with desktop hash
`af738dbdb3fd66a23e973e4b4e7c13c57558aba21fac9dd350571e9eabe05476`.
`Tab` followed by `Return` hid the navigation sidebar in the live app, proving
keyboard traversal and activation; the sidebar was restored. The Computer Use
AX bridge still reports the window rather than the focused child, so this is
not formal VoiceOver evidence.

The same candidate bounds startup Keychain bootstrap and provider-status reads
at two seconds. On the current host, `SecItemCopyMatching` still timed out, but
the app launched with an empty secret bootstrap, showed the explicit UI state
`Provider Keychain status unavailable · Keychain read timed out; provider state
is unavailable`, and kept `Run turn` disabled. No provider was claimed
configured. GPUI `87/87`, native-host `29 passed / 1 ignored`, the full
`bash verify.sh` gate (`1048 passed, 1 skipped, 53 warnings`), package smoke,
Rust-only audit, deep strict code-sign verification, and exact archive rollback
(`1/1`) passed. Formal VoiceOver and notarized release evidence remain pending.

Latest candidate after startup-truth correction (2026-08-03): the release was
rebuilt and installed after propagating a failed Keychain bootstrap into the
visible provider-unavailable state. Bundle and installed desktop hashes match
at `2bcf5991893e6b93e6771bee65385b8c9e2ce6726da0dab9e23de6f3ecf700a9`; the
runtime resource hash is
`74f18cb09e629b7a72e547b9e3afc7434b8b825bdbe16d5b78300d6204d59893`.
Fresh `bash verify.sh`, release build, installed-app smoke, strict codesign,
Rust-only audit, and exact archive rollback (`1/1`) passed. The live app again
showed `Provider Keychain status unavailable` and `Run turn unavailable`; a
live `Tab`+`Return` hid navigation and the sidebar was restored. Formal
VoiceOver and Apple notarization remain pending.

Latest startup-safety regression (2026-08-03): native-host now directly tests
that a slow platform Keychain operation returns the explicit timed-out,
provider-unavailable error before the worker completes. The focused test passed;
the full native-host suite passed `30` tests with `1` ignored plus `9` PTY tests,
and all-target clippy passed with `-D warnings`. This strengthens the local
startup/readiness evidence but does not replace formal VoiceOver or notarized
release evidence.

Latest live-smoke helper recheck (2026-08-03): both provider smoke scripts now
bound their macOS `security find-generic-password` lookup to five seconds using
a captured-output subprocess and fail closed without printing the credential.
The current OpenCode Go Keychain-only run exited `2` after approximately
`5.1s` with no provider request or spend, instead of hanging indefinitely.
The earlier user-authorized process-only OpenCode Go smoke remains the latest
successful live provider-conformance result (`1/1`); the GPUI VoiceOver and
notarized-release requirements remain separate pending gates.

Latest installed UI observation (2026-08-03): the visual-pass candidate was
live-observed at `/Applications/Codinal.app`; the screenshot is recorded in
the C3 evidence folder. The native AX tree exposed `Composer input`, labeled
provider/updater controls, and the workspace-tools toggle, which opened and
closed successfully. This strengthens local GPUI presentation evidence but
does not promote C2a because the bridge still cannot prove formal VoiceOver
focus/announcement behavior.

The accepted UI candidate now uses the contract-aligned light shell documented
in [C3](../c3/gate.md): white canvas, pale-gray navigation, quiet runtime
labels, and the centered floating composer/context card geometry. This changes
presentation only; C2a's live provider and approval evidence remains otherwise
unchanged.

Latest user-directed provider recheck (2026-08-03 07:44 +07):
`bash scripts/smoke-opencode-go-runtime.sh` was run Keychain-only and failed
closed with exit `2` because the `opencode-go` Keychain item is empty or
unavailable. No provider request or spend was made. The earlier explicitly
authorized process-only smoke remains the successful live conformance result;
the credential value was not copied from chat or persisted.

Follow-up after Keychain re-entry (2026-08-03): the item became readable
without exposing its value, but the bounded OpenCode Go capability probe failed
with `HTTP 401 AuthError: Invalid API key.` A sanitized direct endpoint check
confirmed the same response. No further retries were made; the current
Keychain credential is not accepted by the OpenCode Go endpoint.

Credential replacement recheck (2026-08-03): the latest Keychain value was
read successfully, but the live smoke and one bounded sanitized endpoint check
again returned `HTTP 401 Unauthorized` with `AuthError: Invalid API key.`
OpenCode Go remains blocked on a provider-accepted credential.

Confirmed-active-key recheck (2026-08-03): after the user confirmed that the
stored credential is an active OpenCode Go key, the bounded live smoke still
failed during the capability probe with `provider request failed`. The prior
sanitized endpoint result remains `HTTP 401 AuthError: Invalid API key`; this
is treated as an account/provider authorization mismatch, not a local code
failure.

Endpoint contract correction (2026-08-03): the official OpenCode Go
documentation lists `https://opencode.ai/zen/go/v1/chat/completions` for
`kimi-k2.7-code`; the repository retains that endpoint. A temporary
`/zen/v1` experiment was reverted after checking the Go-specific contract and
did not change the live-gate conclusion.

Latest credentialed live recheck (2026-08-03):
`bash scripts/smoke-opencode-go-runtime.sh` passed `1/1` through the native
Keychain path. The capability probe and real `kimi-k2.7-code` turn completed
and wrote the terminal receipt; no credential or response content was recorded.
The earlier `401` was caused by the empty/invalid Keychain value and is
superseded for provider conformance. Formal GPUI VoiceOver and notarized
release evidence remain separate pending gates.
