---
stage: C3
owner: desktop/gpui
dependencies: [C2a]
status: pending
---

# C3 GPUI workbench gate

Required evidence:

```text
cargo test --manifest-path desktop/gpui/Cargo.toml -- --nocapture
cargo clippy --manifest-path desktop/gpui/Cargo.toml --all-targets -- -D warnings
```

Fresh packaged approval-expiry observation (2026-08-03): the signed
`/Applications/Codinal.app` rendered the durable `approval_expired` event as a
typed terminal receipt, announced “Approval expired; session turn failed,”
and reset the composer to `Run turn`. The approval review exposed the persisted
expiry timestamp before the decision. This adds live evidence for the UI-4
terminal-state projection and running-state reset, but it does not replace the
missing VoiceOver traversal, target-120-Hz frame/input telemetry, idle/RSS
workload, or provider cache/cost baseline; C3 remains `pending`.

Fresh verification refresh (2026-08-03): the GPUI suite passed `86/86`,
`clippy -D warnings` and formatting passed, and the full `bash verify.sh` gate
passed. The latest signed candidate measured `app_bundle_bytes=26,209,428`,
`native_gpui_bytes=16,117,296`, `native_runtime_bytes=9,815,216`, and
`archive_zip_bytes=10,268,794`; the Rust-only audit passed for both the bundle
and the installed `/Applications/Codinal.app`. These measurements are local
release evidence only and do not close the target-hardware or external-release
gates.

The attached live matrix must cover keyboard-only navigation, VoiceOver
labels/announcements, focus restoration, contrast, Light/Dark, reduced motion,
reconnect, transcript scale, typing latency, scrolling, and memory. The ledger
must freeze numeric transcript, stream-rate, input-to-paint P95, frame-time
P95, idle-wakeup, and RSS budgets before optimization.

The checked-in [accessibility and interaction matrix](accessibility-matrix.md)
maps the local executable contracts separately from the required live VoiceOver
and target-hardware evidence.

The UI-0 [legacy contract classification](ui-test-classification.md) accounts
for all 49 `tests/desktop_ui/test_ui_contract.py` tests. Supported behavior is
marked for Rust/GPUI migration; deferred, unavailable, and legacy-only
assertions have explicit replacement or removal conditions. No legacy test has
been deleted.

Stop condition: inaccessible safety surface, UI state bypassing runtime
readiness/approval, unlicensed copied code, or a performance budget regression.

Deterministic result (2026-08-02):

- `cargo fmt --manifest-path desktop/gpui/Cargo.toml -- --check`: passed.
- `cargo test --manifest-path desktop/gpui/Cargo.toml -- --nocapture`: 86 passed.
- `cargo clippy --manifest-path desktop/gpui/Cargo.toml --all-targets -- -D warnings`:
  passed.
- `bash verify.sh`: passed; product 1048 passed/1 skipped, desktop 86 passed,
  and Rust cutover suites include Harness 14, tools 24, providers 16, storage
  28, policy 18, and runtime 116 passed/3 ignored. Two separately credentialed
  live-provider tests and the opt-in local benchmark remain ignored by default.
- Release build, Rust-only audit, Developer ID codesign verification, and
  packaged smoke passed.

UI-1/UI-2 extraction increment (2026-08-02):

- `desktop/gpui/src/ui_model.rs` now owns bounded typed timeline, approval,
  receipt, stream-watermark, command-state, `UiAction`, `UiEvent`, and
  `UiEffect` projections around the existing `WorkbenchState` kernel.
- `desktop/gpui/src/session_projection.rs` is the single parser/order gate for
  live and replayed session events; malformed, duplicate, unordered, and
  missing-identity events are covered by no-I/O tests.
- `desktop/gpui/src/conversation.rs`, `composer.rs`, and `context_panel.rs`
  own the typed transcript, composer, and approval leaf views. Runtime calls
  remain composition-root effects through the existing authenticated client.
- `desktop/gpui/src/dock.rs` and `dock_view.rs` now own typed dock state and
  bounded Review/Terminal/Browser/Files/Side Chat presentation. Dock actions
  preserve ordered tabs, keep the PTY presentation alive when hidden, and
  isolate pane preferences by selected session without storing runtime data.
- `desktop/gpui/src/terminal_view.rs`, `settings_view.rs`, and
  `accessibility.rs` isolate native PTY presentation, provider/updater leaves,
  and stable keyboard/label contracts. All consequential callbacks still route
  to the composition root and existing native Rust owners.
- The GPUI unit suite now passes 85 tests, including six typed UI-model
  transition/replay tests plus dock/session-isolation and accessibility
  contracts. `main.rs` is 4,562 lines and remains above the advisory 1,200-line
  extraction target; boot/runtime effects and the release-only evidence gates
  remain explicit follow-on work.
- No VoiceOver, target-120-Hz, numeric performance, notarization, or live
  provider evidence is claimed by this extraction.

Live local UI result (Computer Use, 2026-08-02): the accessibility tree exposed
the Navigation, Context, Workbench, Review, Terminal, Browser, Files, Side chat,
and all three resize handles. Keyboard resizing changed Navigation 314→338 px,
Workbench 424→448 px, and Files tree 140→164 px; the atomic preference file
retained those values across process restart. Narrow-window Navigation collapse,
independent Context+Workbench rendering, workspace file listing, and bounded
read-only file preview were observed in the release bundle.

A fresh observation of the rebuilt signed candidate exposed the native `Codinal`
window, `Session stream connected`, `Run turn` disabled with `Turn execution is
not ready`, the signed-updater readiness card, no pending approvals, and
unconfigured provider cards. This confirms the local safety/readiness projection
only; it does not claim live provider, VoiceOver, target-refresh, or performance
evidence.

Follow-up review added deterministic coverage that an overlaid Workbench leaves
the Context card unoccluded and that Files preserves a 160 px detail region.
Rapid keyboard-resize stress produced the exact final 378 px preference, and a
restart restored it before the three preferences were returned to their
314/424/140 px defaults.

The host used for the existing local UI run did not expose a 120 Hz display
mode. VoiceOver announcement/focus traversal and numeric input-to-paint P95,
frame-time P95, idle-wakeup, and RSS measurements on target 120 Hz hardware
remain required; no fresh live VoiceOver or target-120 Hz evidence is claimed.
Therefore C3 remains `pending` rather than being promoted from local release
candidate to public release.

The frozen measurement contract is checked in at
[`measurement-ticket.md`](measurement-ticket.md). The Python-free artifact
runner is `scripts/measure-rust-release-artifacts.sh`; its latest local result
on the latest Developer ID-signed candidate was `native_gpui_bytes=16,117,296`,
`native_runtime_bytes=9,797,408`, `app_bundle_bytes=26,191,620`,
`archive_zip_bytes=10,261,788`, `archive_tar_gz_bytes=10,257,654`, and
`editor_bundle_raw_bytes=1,278,411` against the frozen `892,815` target;
`debug_symbols_bytes=0` because no `.dSYM` is present in the release bundle.
These are measurements, not a performance or bundle-size pass; the target UI
hardware matrix is still absent.

The fixed cold/warm benchmark is now executable and passed locally with
`cargo test --manifest-path crates/codinal-runtime/Cargo.toml
fixture_cold_warm_benchmark -- --ignored --nocapture`. It covered three fresh
sessions and 90 fixture turns with the checksummed fixture
`sha256:bd70cc211cb7529c1e757e117e410c958c9901776c808e3070031a9172274f04`.
Fresh rerun recorded cold/warm E2E p95 of 27/15 ms, first-delta outcome p95 of
5/1 ms, and an assistant-delta stream of 90 events at 83.03 events/s. The
fixture emitted no
provider cache or cost fields, so those rows remain unknown; this run does not
replace VoiceOver, target-refresh, input-to-paint, frame-time, idle-wakeup, or
RSS evidence.

Fresh local `xctrace` diagnostic (2026-08-02) launched the rebuilt release
executable with a temporary `HOME` and no execution/provider credential. The
6.363-second Game Performance trace on the Apple M3 MacBook Air recorded
375 built-in-display presentation intervals at P95 16.667 ms, with a 60 Hz
display path, plus two Metal intervals of 4.739 ms and 3.269 ms. This is a
local presentation/GPU observation only; it is not input-to-paint or frame
render P95, does not cover VoiceOver/idle/RSS, and cannot substitute for the
required 120 Hz target. The trace remains an ephemeral `/tmp` diagnostic.

A bounded idle-startup RSS sample on the same temporary-HOME release launch
recorded 50 samples over 5 seconds: app peak `69.33 MiB`, runtime peak
`6.69 MiB`, combined peak `74.55 MiB`. This is below the frozen `250 MiB`
ceiling for the idle slice, but it is not the required 90-turn fixture-RSS
or target-hardware workload evidence.

The separate credentialed DeepSeek receipt sample recorded cache hit/miss
counters and a `193` USD-microdollar Codinal estimate, but provider cost was
`unavailable` and no same-provider bare baseline was collected. The C3 cache
reuse/cost rows therefore remain unknown.

Fresh UI correction (2026-08-02): the blank-center case was reproduced against
the packaged Rust UI after a completed turn. The runtime had a durable receipt
but zero persisted message rows; the UI cleared its streaming buffer and
reloaded only messages. Receipt projection/rendering is now bounded and typed,
and focused GPUI tests plus the full verifier pass. A fresh recheck of the
signed `/Applications/Codinal.app` after native Keychain authorization showed
`Ready`, `Full access`, `Provider capability verified`, an enabled `Run turn`,
and a completed visible `GPUI_LIVE_OK` terminal receipt; the durable row also
reported `probe_status=passed`. The first probe failed transiently with
`Resource temporarily unavailable (os error 35)` and the retry passed. The
required VoiceOver, target-refresh, input-to-paint, idle-wakeup, RSS, and
provider-reported-cost/release-baseline evidence remain unavailable, so C3
remains `pending`.

Artifact checksums:

```text
b7b79be8c621822ed8d483292e6df23debfad40d5c54f22465938be99a1e55af  desktop/gpui/src/main.rs
1788cc9e8a801aab0417ec4addc2b85c352b81c820c4f212b6e540f6e4031dba  desktop/gpui/src/workbench.rs
125a234e9ee4aac83d63b9d19a0c409d91cb3090d4c304d2902a7b5ea350ff4a  desktop/gpui/src/session_projection.rs
8bbb937b9797481e8c86f00884ee406282f67f76060a7c413da294f0889ef63a  desktop/gpui/src/ui_model.rs
a488c00c03f02acd40cb83be7e3eafd1961eec58df69e270eebf823a934800df  desktop/gpui/src/shell.rs
1590d5e822e4220440ff109a45ea1019fda4bd21b6b3d6eb151a87e74d91209e  desktop/gpui/src/navigation.rs
d1f973a43b58fe659d2e7bf9784724eb93e2a8919b90ed7067cb62d6141a1c18  desktop/gpui/src/conversation.rs
50f69ba6ff5a00f28cce552a7f03abc774bc4463cc31fb2a4b514055cbd53517  desktop/gpui/src/composer.rs
d28c90e8dc3d0e780df4d260cb64633680b5a95ac617218ff53dcbfa6bb7d2f8  desktop/gpui/src/context_panel.rs
f7c4eed23922a57196357ff0e5075e617529f01bc34ceb2697bfbefd175d78d8  desktop/gpui/src/dock.rs
90dc5a073d2b61156b74c3f9a4bab4f6d270bfb62f15d47f968ce92fa922abe5  desktop/gpui/src/dock_view.rs
1628ad4cd7ab76dd57b61c1ea723223fd17aff3601248bf251c6aec090b79be0  desktop/gpui/src/settings_view.rs
fdd719b36790e1c155454e30c5ccc19d9057501c8a1d8e6a6b1576d18eb126d6  desktop/gpui/src/terminal_view.rs
301679175d3aa6f3634ba3eb937f4c459ce2766c930a3f5436efdbc66fba8aec  desktop/gpui/src/accessibility.rs
d1275b268abb55b8d57ebe14b84ba85c9ba10d22baca62b01603d75fc59f5903  desktop/gpui/src/light_theme.rs
a0ec787b8870f76228d478ddeb75d9269ef714dedc0eee0c32bdc5950d1c5c7f  desktop/gpui/UI_CONTRACT.md
9244120afdf3a86736327072ce83a7ab08622da1cb84e75bd28c88d95675a8ee  desktop/gpui/src/side_panel.rs
343d8d1df1b6ea8c54d97e0906724ba60b4a50078b2d2128277ddb1e8a5380bf  desktop/gpui/src/shell_layout.rs
5c93a0ffca5c1e952831cd9d6aabcf33acd6f726bf20b34a81493f55cea60d39  desktop/gpui/SAFETY.md
```

Fresh signed UI-focus candidate (2026-08-03): the release build containing
root-level Tab/Shift-Tab traversal passed GPUI tests `87/87`, all-target
`clippy -D warnings`, the complete `bash verify.sh` gate, Rust-only release
audit, and deep strict code-sign verification. The installed app and release
bundle contain the same desktop hash
`987638b3ea6f35d3fb9201ab5d775c1c53837b3c6f60625b5138139bdf57f35f`.
The fresh artifact measurements are `native_gpui_bytes=16,119,344`,
`native_runtime_bytes=9,815,216`, `app_bundle_bytes=26,211,476`,
`archive_zip_bytes=10,271,740`, `archive_tar_gz_bytes=10,266,781`,
`sbom_bytes=157,979`, and `debug_symbols_bytes=0`. The AX trace did not expose
child focus, so this closes the implementation gap but not the formal
VoiceOver/target-hardware acceptance evidence.

Current signed focus/a11y candidate refresh (2026-08-03): the release runner
measured native GPUI `16,120,528` bytes, runtime `9,815,216` bytes, app bundle
`26,212,660` bytes, ZIP `10,271,733` bytes, tar.gz `10,267,670` bytes, SBOM
`157,979` bytes, and debug symbols `0` bytes. The package and installed
desktop binary hash is
`19cf3b026a4bdb3f3bc0ef3a54b627595811309257e0d3f1b65dbc78e4915a02`; the
runtime resource hash is
`8f7f8c71f6f483af997bef0acc170360607f6edc848184256a98bb863e238d21`.
The full verifier, package smoke, updater archive test, and DeepSeek live
smoke passed. The AX tree exposes `Composer input` as a text field, but child
focus traversal is still not exposed by the Computer Use bridge. Target-120-Hz
and numeric input-to-paint/frame/idle/RSS evidence remain unavailable.

Latest installed UI-control candidate (2026-08-03): the signed release added
focus-visible treatment and AX button semantics to settings/updater/provider
controls, workspace-tool tabs, file rows, and the workspace-tool add control.
The current artifact runner measured native GPUI `16,140,448` bytes, native
runtime `9,815,216` bytes, app bundle `26,232,580` bytes, ZIP `10,275,139`
bytes, tar.gz `10,274,187` bytes, SBOM `157,979` bytes, and debug symbols
`0` bytes. The installed and packaged desktop hash is
`d3afa61f734036a18dc2d7b68cbf5f1aa237db9be0bb2a5ce893423821eb1f8e`; the
runtime resource hash is
`575b67e0d0dfca8e4a9ecdb8ca0cc53cabb8926b7aa8397baf1c5e591c7febd2`.
The full verifier, package and installed-app smoke, Rust-only audit, exact
archive updater rollback (`1/1`), and DeepSeek live smoke (`1/1`) passed.
The host is still an Apple M3 MacBook Air with a 60 Hz built-in display, so
formal VoiceOver and target-hardware performance evidence remain pending.

Latest focus/startup candidate (2026-08-03): app-level GPUI `tab` and
`shift-tab` actions now drive the pinned focus traversal API. A live
`Tab`+`Return` sequence hid the navigation sidebar and the sidebar was restored
afterward. The AX bridge continued to expose only the window as focused; formal
VoiceOver traversal/announcements therefore remain pending.

The candidate also bounds macOS Keychain reads during startup. The current host
still timed out in `SecItemCopyMatching`, but the packaged app launched within
the bounded path and visibly reported unavailable provider state instead of
claiming credentials or hanging before the UI. Latest metrics are:
`native_gpui_bytes=16,285,296`, `native_runtime_bytes=9,815,088`,
`app_bundle_bytes=26,377,300`, `archive_zip_bytes=10,312,015`,
`archive_tar_gz_bytes=10,306,897`, `sbom_bytes=157,979`, and
`debug_symbols_bytes=0`. Target-120-Hz, input-to-paint, frame, idle-wakeup,
RSS, provider-cost, and formal VoiceOver evidence remain unavailable.

Latest startup-truth candidate (2026-08-03): bundle and installed desktop
hashes match at
`2bcf5991893e6b93e6771bee65385b8c9e2ce6726da0dab9e23de6f3ecf700a9`; runtime
resource hash is
`74f18cb09e629b7a72e547b9e3afc7434b8b825bdbe16d5b78300d6204d59893`.
Metrics are native GPUI `16,285,296` bytes, native runtime `9,815,088` bytes,
app bundle `26,377,300` bytes, ZIP `10,313,016` bytes, tar.gz `10,307,023`
bytes, SBOM `157,979` bytes, and debug symbols `0` bytes. Fresh full
verification, release build, installed-app smoke, strict codesign, Rust-only
audit, and exact archive rollback (`1/1`) passed. Target hardware, numeric
performance, provider-cost reconciliation, and formal VoiceOver evidence
remain pending.

Fresh Rust-native startup runners (2026-08-03) measured the installed
candidate: native runtime listener p95 `31.61 ms` and desktop-to-native
runtime listener p95 `2,217.09 ms` across five samples. The desktop p95
includes the bounded Keychain timeout on this host; it does not prove
first-paint, input-to-paint, 120-Hz frame, idle-wakeup, or VoiceOver budgets.
The old Python-sidecar benchmark wording was removed from the runners and
performance index; focused perf tests passed `3/3`.

Fresh canonical verification after the runner migration (2026-08-03):
runtime truth passed; product tests passed `1049` with `1` skipped and `53`
warnings; GPUI passed `87/87`; runtime passed `117` with `3` ignored; and
`Codinal verify: PASS`. The native-host timeout regression is included in the
full gate; no deterministic failure remains. External VoiceOver,
target-hardware, provider-cost, and notarization evidence remain pending.

Latest installed candidate after the DeepSeek probe-budget correction
(2026-08-03): native GPUI `16,285,296` bytes; native runtime `9,815,088`
bytes; app bundle `26,377,300` bytes; ZIP `10,312,983` bytes; tar.gz
`10,307,035` bytes; SBOM `157,979` bytes; and debug symbols `0` bytes.
Five-sample Rust-native startup measurements reported
`native_runtime_to_listener` p95 `40.90 ms` (median `33.52 ms`) and
`desktop_to_native_runtime_listener` p95 `2,248.57 ms` (median `2,209.28 ms`).
The desktop result includes the bounded Keychain timeout and does not claim
GPUI first-paint, input-to-paint, 120-Hz frame, idle-wakeup, RSS, or VoiceOver
acceptance. The signed app was installed and live AX-observed; the UI remains
the intentional three-zone native workbench described by the UI contract.

## Superseded native visual experiment — 2026-08-03

An earlier cool-light/indigo variant was captured for comparison but did not
match the approved light-shell contract. It is retained as historical evidence
only; the accepted candidate is recorded below.

Live Computer Use inspection of `/Applications/Codinal.app` exposed the
native `Composer input` text field, updater/provider controls, and
`Show workspace tools`/`Hide workspace tools`; toggling the workspace panel
and restoring it passed. The bridge still exposes only the window as focused,
so this is visual/AX observation, not formal VoiceOver announcement evidence.

## Latest contract-aligned UI candidate — 2026-08-03

The accepted candidate now follows the approved contract: white canvas,
pale-gray sidebar, light-gray right-aligned user bubbles, quiet secondary
runtime/stream labels, floating 336 px Environment card, centered floating
composer, and the existing 48 px / 314 px / 840 px / 424 px geometry. The
live screenshot is [here](ui-contract-aligned-2026-08-03.jpeg) (1229x768,
SHA-256 `49a39c563e6ec9538e5456a8571b718e1f44bb4b50e605d4cb88264285392c21`).

The release hashes are desktop
`127579778077854800aa2e6cdfd0f3ada040d6973a4bda3c58033e0dc30011ba`, runtime
`4e2ff1e1859291ccf0c1f5303b191cbbb0f0d977eb9804b370fbe9c16ef7019c`, ZIP
`350e2fb79a64e4608f9b9c7b478458bbdaed0c2148f1a538e348ebc79a3c4907`, and
tar.gz `2b07ed3e73bb07c5a4c437736003a750c59fa3f733b96c4a3a5db29d1d62d8b8`.
The approved palette contract test, clippy, full verifier, release-contract
tests `5/5`, canonical perf tests `19/19`, installed smoke, Rust-only audit,
strict codesign, and exact archive rollback `1/1` passed. External C3 gates
remain pending for formal VoiceOver and target-hardware telemetry.
