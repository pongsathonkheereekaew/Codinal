---
stage: C3
owner: desktop/gpui
status: pending
frozen_at: 2026-08-02
---

# C3 measurement ticket

This ledger freezes the measurement contract before optimization. It does not
turn an unmeasured target into a pass. A row is `unknown` until the listed
runner records a fresh result on the target hardware and fixture.

## Fixture and sample plan

- Rust GPUI deterministic workbench fixture; no Python process and no live
  provider credential in the local runner.
- Three fresh sessions, 30 turns per session (90 turns total). The first turn
  in each session is cold; the remaining turns are warm. The exact transcript,
  tool-schema, policy, model, endpoint profile, and region must be checksummed.
- Live provider rows must record the exact provider/model/effort, cache fields,
  uncached input, output, cost classification, request bytes, CPU, RSS,
  retries, and fallback state. Without an approved credential and budget these
  fields stay `unknown`.
- Hardware observed for this ticket: Apple M3 MacBook Air, 8 GB RAM,
  2560×1664 built-in display. `system_profiler` exposed no 120 Hz mode on this
  host; no target-120 Hz result is claimed.

## Frozen budgets

| Metric | Frozen threshold | Current result | Evidence/runner |
|---|---:|---|---|
| transcript blocks | ≤4,096 | not measured | `desktop/gpui/src/workbench.rs` bound |
| transcript bytes | ≤4 MiB | not measured | `desktop/gpui/src/workbench.rs` bound |
| published delta bytes | ≤16 KiB/event | implemented, not timed | `crates/codinal-runtime/src/lib.rs` bound |
| published stream rate | ≤120 events/s | 83.03 assistant-delta events/s in the local fixture; passes locally, not a target-hardware claim | `fixture_cold_warm_benchmark` |
| local first-delta forwarding | ≤10 ms P95 after provider chunk | latest fixture outcome telemetry p95 cold=5 ms/warm=1 ms; provider-chunk forwarding component not isolated | live/replay telemetry required |
| E2E first-delta regression | ≤5% vs same-provider baseline | latest fixture p95 cold=5 ms/warm=1 ms; same-provider baseline unavailable | fixed cold/warm benchmark; baseline required |
| input-to-paint | ≤50 ms P95 | not measured | target-hardware UI runner required |
| typing latency | ≤50 ms P95 | not measured | target-hardware UI runner required |
| frame time at 120 Hz | ≤8.33 ms P95 | unavailable on current host | target-120-Hz runner required |
| frame time at 60 Hz | ≤16.67 ms P95 | not measured | target-hardware UI runner required |
| idle wakeups | ≤1/s while idle | not measured | Instruments/activity trace required |
| fixture RSS | ≤250 MiB | not measured | target-hardware process sample required |
| warm cache reuse | ≥ same-provider bare baseline | endpoint-only comparison observed: 128 cache-hit tokens on the repeated prefix; runtime/release baseline still pending | provider cache telemetry required |
| warm cache cost delta | < equivalent no-cache sequence when reported | endpoint-only catalogue estimate 18 USD µ versus 73 USD µ for the same-prefix no-cache seed; provider-reported cost unavailable | provider pricing + runtime usage reconciliation required |
| editor bundle raw bytes | ≤892,815 (30% below 1,275,451) | not applicable to Rust package; legacy source measured separately | `scripts/measure-rust-release-artifacts.sh` |
| native GPUI binary | record baseline; no unreviewed regression | 16,119,344 bytes | `scripts/measure-rust-release-artifacts.sh` |
| runtime binary | record baseline; no unreviewed regression | 9,815,216 bytes | `scripts/measure-rust-release-artifacts.sh` |
| app archive | record baseline; no unreviewed regression | ZIP 10,271,740; tar.gz 10,266,781 bytes | `scripts/measure-rust-release-artifacts.sh` |
| debug symbols | record baseline; no unreviewed regression | 0 bytes; no `.dSYM` present under the release bundle | `scripts/measure-rust-release-artifacts.sh` |

Latest Developer ID-signed artifact runner result (2026-08-03): app bundle
26,209,428 bytes,
SBOM 157,979 bytes, legacy editor source 2,005,304 bytes, and legacy editor
raw bundle 1,278,411 bytes; release debug symbols 0 bytes because no `.dSYM`
is present. The Rust package has no editor bundle; the legacy
raw artifact therefore remains above the frozen target and does not pass it.

Fresh deterministic cold/warm benchmark (2026-08-02) passed with the exact
command `cargo test --manifest-path crates/codinal-runtime/Cargo.toml
fixture_cold_warm_benchmark -- --ignored --nocapture`. It ran three sessions
with 30 turns each (90 total), using fixture hash
`sha256:bd70cc211cb7529c1e757e117e410c958c9901776c808e3070031a9172274f04`.
Cold E2E p95 was 27 ms and warm E2E p95 was 15 ms; first-delta outcome p95
was 5 ms cold and 1 ms warm; 90 assistant-delta events measured 83.03/s;
provider request bytes were 75,030 total (833–834 bytes/request). Fixture
cache and provider cost fields remain `unknown`, and target-hardware UI
metrics remain unmeasured.

Fresh local `xctrace` diagnostic (2026-08-02) launched the rebuilt release
executable with a temporary `HOME` and no execution/provider credential:
`xcrun xctrace record --template 'Game Performance' --time-limit 8s --launch
-- <Codinal executable>`. The trace covered 6.363 seconds on the Apple M3
MacBook Air. Built-in-display presentation cadence was 375 intervals with
P95 16.667 ms (min 16.666 ms, max 50.000 ms), confirming the observed 60 Hz
display path; the trace contained only two Metal application intervals at
4.739 ms and 3.269 ms. These are presentation/GPU diagnostics, not
input-to-paint or frame-render P95, and they cannot prove the unavailable
120 Hz target. The trace was kept in `/tmp` only and is not promoted to a
release artifact.

Fresh bounded RSS sample (2026-08-02) launched the same release executable
with a temporary `HOME`, no provider credential, and execution disabled, then
sampled the app and native runtime every 100 ms for 5 seconds. Across 50
samples the peaks were app `69.33 MiB`, runtime `6.69 MiB`, and combined
`74.55 MiB`, below the frozen `250 MiB` ceiling for this idle-startup slice.
This is not a 90-turn fixture-RSS result and does not replace the required
target-hardware workload sample.

Fresh credentialed DeepSeek receipt telemetry (2026-08-02) recorded `358`
prompt tokens, `41` completion tokens, `399` total tokens, `256` cache-hit
tokens, `102` cache-miss tokens, provider cost `unavailable`, and a Codinal
catalogue estimate of `193` USD microdollars. This is one live sample rather
than a same-provider bare baseline or warm-cache comparison, so the warm-cache
reuse and cost-delta rows remain `unknown`.

Fresh direct DeepSeek cache comparison (2026-08-03) used the same
`deepseek`/`deepseek-v4-pro`/`high` endpoint contract and bounded `max_tokens=8`
requests. A bare baseline reported `12` prompt, `0` hit, and `12` miss tokens;
a stable-prefix seed reported `150` prompt and `150` miss tokens; and a
repeated stable-prefix request reported `151` prompt, `128` hit, and `23` miss
tokens. Provider-reported cost was absent in all three responses. The pinned
Codinal catalogue estimates were `13`, `73`, and `18` USD microdollars,
respectively, after the runtime estimator was corrected to use DeepSeek's
explicit cache-miss tokens for billable input. This is an endpoint-level
cache/cost comparison, not a target-hardware UI or provider-reported-cost
claim; the runtime receipt smoke and same-provider release baseline remain
required for C3 promotion.

Fresh signed UI-focus candidate measurement (2026-08-03): the root GPUI shell
now dispatches unmodified `Tab`/`Shift-Tab` through `Window::focus_next` and
`focus_prev`; GPUI tests passed `87/87`, and the signed installed app matched
the release desktop binary. The release runner measured native GPUI
`16,119,344` bytes, runtime `9,815,216` bytes, app bundle `26,211,476` bytes,
ZIP `10,271,740` bytes, tar.gz `10,266,781` bytes, SBOM `157,979` bytes, and
debug symbols `0` bytes. The Computer Use AX bridge still exposed only the
window rather than the focused child, so formal VoiceOver traversal remains
unverified.

The 50 ms input/typing, 120 events/s, 1 wakeup/s, and 250 MiB RSS values are
explicit product-budget assumptions frozen for measurement because the
canonical plan specifies the metrics but not numeric values. The desktop
owner must ratify or revise them with a dated decision before C3 can pass; a
revision must preserve the recorded old value and result.

## Commands

```text
cargo fmt --manifest-path desktop/gpui/Cargo.toml -- --check
cargo test --manifest-path desktop/gpui/Cargo.toml -- --nocapture
cargo clippy --manifest-path desktop/gpui/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path crates/codinal-runtime/Cargo.toml fixture_cold_warm_benchmark -- --ignored --nocapture
bash scripts/measure-rust-release-artifacts.sh
```

The [accessibility and interaction matrix](accessibility-matrix.md) records
which UI claims are static/local contracts and which require live macOS
evidence. The artifact runner is intentionally read-only and Python-free. It reports
zero for an inspected release bundle with no `.dSYM`, and `unknown` only when
an optional path cannot be measured. It never substitutes source bytes for a
built editor bundle. The UI accessibility matrix, VoiceOver
announcement/focus traversal, live provider rows, and target-120-Hz telemetry
remain manual/live evidence.

Latest signed UI-focus candidate (2026-08-03): native GPUI `16,120,528` bytes;
native runtime `9,815,216` bytes; app bundle `26,212,660` bytes; ZIP
`10,271,733` bytes; tar.gz `10,267,670` bytes; SBOM `157,979` bytes; debug
symbols `0` bytes. The candidate desktop binary hash is
`19cf3b026a4bdb3f3bc0ef3a54b627595811309257e0d3f1b65dbc78e4915a02` and the
runtime resource hash is
`8f7f8c71f6f483af997bef0acc170360607f6edc848184256a98bb863e238d21`.
The full verifier, package smoke, updater archive rollback, and DeepSeek live
smoke passed. The Computer Use AX tree exposes the composer as `TextInput`,
but formal child focus/VoiceOver traversal and target-hardware metrics remain
unmeasured.

Latest signed UI-control candidate (2026-08-03): native GPUI `16,140,448`
bytes; native runtime `9,815,216` bytes; app bundle `26,232,580` bytes; ZIP
`10,275,139` bytes; tar.gz `10,274,187` bytes; SBOM `157,979` bytes; debug
symbols `0` bytes. The packaged and installed desktop hash is
`d3afa61f734036a18dc2d7b68cbf5f1aa237db9be0bb2a5ce893423821eb1f8e`, and the
runtime resource hash is
`575b67e0d0dfca8e4a9ecdb8ca0cc53cabb8926b7aa8397baf1c5e591c7febd2`.
Package/install smoke, archive updater rollback, and the DeepSeek live smoke
passed. No numeric input-to-paint, target-120-Hz frame, idle-wakeup, or
90-turn RSS measurement was added by this UI-control refresh.

Latest candidate measurement (2026-08-03):
`native_gpui_bytes=16,285,296`, `native_runtime_bytes=9,815,088`,
`app_bundle_bytes=26,377,300`, `archive_zip_bytes=10,312,015`,
`archive_tar_gz_bytes=10,306,897`, `sbom_bytes=157,979`, and
`debug_symbols_bytes=0`. The desktop binary hash is
`af738dbdb3fd66a23e973e4b4e7c13c57558aba21fac9dd350571e9eabe05476` and the
runtime resource hash is
`74f18cb09e629b7a72e547b9e3afc7434b8b825bdbe16d5b78300d6204d59893`.
The candidate's global Tab action and bounded Keychain startup path were live
checked; target-hardware and VoiceOver metrics remain pending.

Latest measurement refresh after startup-truth correction (2026-08-03):
native GPUI `16,285,296` bytes; native runtime `9,815,088` bytes; app bundle
`26,377,300` bytes; ZIP `10,313,016` bytes; tar.gz `10,307,023` bytes; SBOM
`157,979` bytes; debug symbols `0` bytes. Bundle and installed desktop hash:
`2bcf5991893e6b93e6771bee65385b8c9e2ce6726da0dab9e23de6f3ecf700a9`.
Runtime resource hash:
`74f18cb09e629b7a72e547b9e3afc7434b8b825bdbe16d5b78300d6204d59893`.
The fresh full verifier, release build, package/install smoke, and exact
archive rollback passed; target-hardware, formal VoiceOver, numeric runtime
latency/idle/RSS, and provider-cost measurements remain open.

Fresh Rust-native startup measurement (2026-08-03): against the installed
candidate `/Applications/Codinal.app`,
`scripts/measure_runtime_startup.py --samples 5` reported native runtime
listener p95 `31.61 ms` (median `30.07 ms`, min `27.34 ms`), and
`scripts/measure_desktop_startup.py --samples 5` reported desktop-to-native
runtime listener p95 `2,217.09 ms` (median `2,208.15 ms`, min `2,195.53 ms`).
The desktop result includes the current host's bounded two-second Keychain
startup timeout and is not a GPUI first-paint or input-to-paint measurement.
Both runners now measure the Rust runtime rather than a retired Python
sidecar; the result is local M3/60-Hz evidence, not a target-120-Hz claim.

The post-test release archive refresh measured ZIP `10,313,016` bytes and
tar.gz `10,307,041` bytes; native GPUI remained `16,285,296` bytes, native
runtime `9,815,088` bytes, and debug symbols `0` bytes. The archive-size
change is packaging metadata only; the installed desktop and runtime binary
hashes remain the candidate hashes recorded above.

Latest current-candidate measurement (2026-08-03): native GPUI
`16,285,296` bytes; native runtime `9,815,088` bytes; app bundle
`26,377,300` bytes; ZIP `10,312,983` bytes; tar.gz `10,307,035` bytes; SBOM
`157,979` bytes; and debug symbols `0` bytes. The installed native runtime
listener p95 was `40.90 ms`; desktop-to-native-runtime listener p95 was
`2,248.57 ms`. These remain local M3/60-Hz startup measurements, not the
missing target-hardware UI frame/input/RSS or VoiceOver evidence.
