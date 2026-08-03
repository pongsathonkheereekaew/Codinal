---
stage: C2b
owner: codinal-providers/runtime/storage
dependencies: [C2a]
status: pending
---

# C2b DeepSeek fallback and budget gate

Exact fixture commands:

```text
cargo test --manifest-path crates/codinal-providers/Cargo.toml -- --nocapture
cargo test --manifest-path crates/codinal-storage/Cargo.toml --lib -- --nocapture
cargo test --manifest-path crates/codinal-runtime/Cargo.toml --lib -- --nocapture
```

Fixture/credential class: independent local DeepSeek-compatible SSE fixtures;
live smoke, if approved, uses a short TTL and the hard per-turn/daily token
caps. The fallback is off by default and only starts before user-visible
output.

Expected result: exact DeepSeek model/effort and thinking contract, concurrent
reservation limits, settlement on known/unknown usage, and opt-in fallback
all pass without exceeding the approved budget.

Rollback: release any reservation and remove only the isolated test store.

Stop condition: unbounded spend, post-output fallback, or requested/effective
effort mismatch.

Fresh deterministic result (2026-08-02): providers `16 passed`; storage
`28 passed`; runtime `116 passed, 3 ignored` (two credentialed live probes plus
the opt-in local benchmark). The exact
`capability_probe_requires_approval_is_bounded_and_expires_on_drift` test and
all-target `-D warnings` checks passed. DeepSeek fixture parsing verifies
the pinned `deepseek-v4-pro`/high-thinking request and prompt-cache hit/miss
normalization; independent opt-in pre-output fallback settles the same durable
reservation (fixture totals 18 tokens for direct DeepSeek and 12 for fallback);
and storage enforces concurrent active and daily reservations. Unsupported
Provider-reported cost remains `unavailable` rather than being fabricated;
the bundled catalogue now pins the synchronized `models.dev` API digest and
USD-per-million price snapshot for metadata-only cost estimates.
Fresh credentialed live smoke (2026-08-02):
`CODINAL_LIVE_DEEPSEEK_API_KEY=<redacted> bash scripts/smoke-deepseek-runtime.sh`
passed. The run performed the bounded capability probe and one real turn
against `https://api.deepseek.com/chat/completions`; the runtime receipt
asserted `completed`, exact `deepseek` / `deepseek-v4-pro` / `high` identity,
and a settled durable budget reservation with positive usage. The credential
was supplied through the process environment only and was not written to
Keychain or disk. The redacted receipt recorded `358` prompt tokens, `41`
completion tokens, `399` total tokens, `256` prompt-cache-hit tokens, `102`
prompt-cache-miss tokens, provider cost `unavailable`, and a Codinal catalogue
estimate of `193` USD microdollars using models.dev revision
`973d58dc69d845b3959493afc16025115eab123bee879594d9d3cedb640beeea`.

Artifact checksums (deterministic slice):

```text
0f958f301efc7d52117fc8de5493aba755b56ade18eb93eb591c4baca5751849  crates/codinal-providers/src/lib.rs
0bf93d4aa02b15751077bd2796842abf1ef36e16324ab752ba7a0c8996191af5  crates/codinal-providers/src/catalogue.rs
1d5543c690e5763fc6874cde930c454e82ca3449773756843ad2e53a6ba4f8f0  crates/codinal-runtime/src/lib.rs
8f2561e67bdbac9cd931e617bb499a1c4e373138d2c577293eadd701bae6e184  crates/codinal-storage/src/lib.rs
0b516b90222d847097f1b73cab2509d76921fa63e5663a463b3575434f60cb44  docs/evidence/cutover/c2b/models-dev-snapshot.json
```

The runtime now exposes an authenticated `POST /v1/capabilities/probe` route
that requires an explicit `approved: true` precondition, sends a bounded
profile-specific no-side-effect tool probe (`max_tokens=64` for OpenCode Go and
`max_tokens=256` for DeepSeek), and grants a five-minute in-memory lease only
after the pinned tool call completes. OpenCode Go keeps the 64-token bound;
DeepSeek's enabled high-reasoning profile needs the larger finite bound so the
required tool-call JSON is not truncated by reasoning tokens. The fresh
`capability_probe_requires_approval_is_bounded_and_expires_on_drift` test
proves the approval boundary, bounded request, `passed` health promotion,
endpoint-drift invalidation, and TTL-expiry readiness removal. A restart
conservatively returns to `not_run`; synchronized catalogue metadata does not
enable endpoint capabilities by itself.

The capped live endpoint/model/effort and provider-cache telemetry slice is
now proven. DeepSeek did not report provider cost, and a same-provider
baseline/reconciliation plus the C2a dependency remain pending; those are
required before promoting this stage.

Historical live preflight (2026-08-02): `bash scripts/smoke-deepseek-runtime.sh`
failed closed with exit `2` because the `deepseek` Keychain item was
unavailable; that run made no provider request or spend. It was superseded by
the credentialed process-only smoke above.

Latest Keychain-backed live smoke (2026-08-02):
`bash scripts/smoke-deepseek-runtime.sh` passed with the DeepSeek credential
read from the macOS Keychain and no process-only override. The one-turn
capability probe and real turn completed with the same exact provider/model/
effort and durable-budget assertions. This supersedes the earlier missing-
Keychain preflight but does not provide provider-reported cost or a
same-provider baseline.

The final pre-credential verification rechecked the same Keychain-only path;
it again exited `2` before any provider request or spend.

The bundled Rust catalogue records DeepSeek cache-read support, the typed
`high` effort variant, the synchronized `models.dev` API digest, and the
metadata price snapshot. The live smoke used the user-approved short test
credential and did not persist it.

Fresh Keychain-backed recheck (2026-08-02):
`bash scripts/smoke-deepseek-runtime.sh` passed again. It read the DeepSeek
credential from the native Keychain, ran the bounded capability probe and one
real turn, and asserted the exact `deepseek` / `deepseek-v4-pro` / `high`
identity plus durable budget settlement. Provider-reported cost and a
same-provider bare baseline remain unavailable, so C2b stays `pending`.

Fresh bounded C2b recheck (2026-08-03):
`bash scripts/smoke-deepseek-runtime.sh` passed with the Keychain credential;
the ignored live test also asserted that, when DeepSeek reports a cache-miss
counter, the durable cost estimate uses that counter rather than total prompt
tokens. A regression test covers the same rule (`151` total prompt tokens,
`128` cache-hit, `23` cache-miss, `8` output => `18` USD microdollars under the
pinned catalogue). The runtime still preserves total prompt/cache telemetry in
the receipt and records provider-reported cost as `unavailable`.

The same provider/model/effort endpoint comparison then established a fresh
no-cache and repeated-prefix baseline without persisting the credential or
response content:

| Request | Prompt tokens | Cache hit | Cache miss | Output tokens | Provider cost | Codinal estimate |
|---|---:|---:|---:|---:|---|---:|
| bare baseline | 12 | 0 | 12 | 8 | unavailable | 13 USD µ |
| stable-prefix seed | 150 | 0 | 150 | 8 | unavailable | 73 USD µ |
| stable-prefix repeat | 151 | 128 | 23 | 8 | unavailable | 18 USD µ |

The repeated-prefix request therefore produced live cache-hit telemetry and a
75% lower catalogue estimate than its same-prefix no-cache seed. This closes
the local cache/baseline comparison, but C2b remains `pending` because provider
cost is not reported, the C2a manual GPUI dependency is still open, and the
endpoint comparison is not a notarized release claim.

Current-runtime recheck (2026-08-03): `bash scripts/smoke-deepseek-runtime.sh`
passed again against the current worktree after the signed UI-focus rebuild
(`1` live test passed, `0` failed, `118` filtered). The Keychain-only path
still proves the pinned DeepSeek identity and durable budget settlement, while
provider-reported cost remains explicitly `unavailable`; no credential value
or response content was recorded. C2b therefore remains pending only on the
documented provider-cost/release reconciliation and the C2a dependency.

Current live recheck (2026-08-03): `bash scripts/smoke-deepseek-runtime.sh`
passed `1/1` against the pinned `deepseek` / `deepseek-v4-pro` / `high`
profile with durable budget settlement. Provider-reported cost remains
`unavailable`; no new credential or response content was recorded.

Fresh release-adjacent C2b recheck (2026-08-03): the same Keychain-backed
DeepSeek smoke passed `1/1` after the native visual-pass release rebuild.
Provider-reported cost remains explicitly `unavailable`; no credential value
or response content was recorded, so the documented C2b cost/release
reconciliation remains pending.

Latest DeepSeek probe correction (2026-08-03): an initial current-worktree
retry failed closed because the real endpoint returned `finish_reason=length`
while the 64-token high-reasoning probe was still emitting tool arguments. A
sanitized endpoint-shape check reproduced the incomplete JSON without recording
the credential or response content. The runtime now keeps OpenCode Go at 64
tokens and assigns DeepSeek a bounded 256-token probe budget; the profile limit
is exposed in the probe response and covered by a deterministic unit contract.
The refreshed Keychain-backed `bash scripts/smoke-deepseek-runtime.sh` then
passed `1/1`, including the real capability probe, exact
`deepseek`/`deepseek-v4-pro`/`high` identity, and durable budget settlement.
The current runtime source hash is
`7e609e4f4fa21dbbcbfcf082504f3b44946606e77d595c3102a45d5bd46008bb`.
Provider-reported cost remains `unavailable`, so C2b stays pending on cost /
release reconciliation and the C2a dependency.

Latest live-smoke helper recheck (2026-08-03): after the shared bounded
Keychain lookup change, the Keychain-backed DeepSeek smoke passed `1/1` again
with the exact `deepseek`/`deepseek-v4-pro`/`high` profile and durable budget
settlement. No credential or response content was recorded.

Latest user-directed provider recheck (2026-08-03 07:44 +07):
`bash scripts/smoke-deepseek-runtime.sh` passed `1/1` through the native
Keychain path, with durable budget settlement and no credential/response
content recorded. Provider-reported cost remains `unavailable`, so the
provider-cost portion of C2b remains pending.
