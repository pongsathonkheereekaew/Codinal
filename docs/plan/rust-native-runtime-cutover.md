# Codinal Rust-only product plan and execution specification

Status: accepted
Decision date: 2026-08-01
Role: canonical runtime, desktop, provider, harness, and rollout SSOT
Performance/cache amendment: 2026-08-02
Scrutinize verdict: OK (pass 6, 2026-08-02)

This document supersedes every hybrid Python/Tauri runtime plan. Supporting
roadmaps may expand delivery details but may not weaken the invariants or gates
defined here.

Five independent outsider scrutiny passes were completed on 2026-08-01. Their
blocking findings are incorporated below: explicit read-only bootstrap,
concurrent interrupt topology, durable multi-database migration and event
journals, provider contract spikes, cost reservation, Safety UI in the first
vertical slice, executable gates, and post-release separation of Harness writes
and multi-model orchestration.

### Document authority

| Document | Authority |
|---|---|
| This file | Canonical product architecture, sequence, and gates |
| `fully-rust-codex-cursor-cutover-plan.md` | Supporting later editor backlog; Python commands are inactive historical notes |
| `codinal-parity-roadmap.md` | Historical parity inventory only |
| `codinal-mvp.md` | Superseded hybrid MVP history |
| `codinal-adoption-tickets.md` | Superseded implementation status; reusable ideas must be re-ticketed under this plan |
| `codinal-cursor-parity.md` | Later editor research only; sidecar/release guidance is superseded |

Frozen Python-generated fixtures may be consumed as historical input by Rust
tests. No Python process is part of Codinal startup, execution, conformance, or
release gating, and no new gate depends on running the Python reference app.

### Verified starting point (working-tree snapshot: 2026-08-02)

- The native host already has a Rust runtime launch path and the GPUI/client
  surface consumes typed Rust readiness/capability data; C0 still has to remove
  stale Python-owner fixtures, documentation, and release references.
- Rust has storage ownership/migration, runtime-store, policy, approval,
  receipt, event-replay, provider, and GPUI scaffolding, but the capability
  matrix still contains many intentionally unavailable routes.
- Rust turn ingress, WebSocket replay, and `assistant_delta` GPUI rendering
  exist as partial paths; the provider now parses SSE incrementally and the
  runtime persists bounded first-delta events. The apply-patch approval path
  now resumes the same durable turn after mutation, receipt replay is
  idempotent by `turn_id`, and deterministic prompt compilation/cache telemetry
  plus the bounded operation lifecycle are implemented. The full Safety UI
  manual/live path, provider live evidence, and release evidence remain gated.
- The universal harness has a conformed OpenCode CLI host adapter in
  Bash/Python, but other host adapters and app-facing Rust write paths remain
  unverified. Python is reference input only, never a product dependency.
- The current runtime suite passes under both default-parallel and serial
  execution (`116 passed, 3 ignored`: two credentialed live probes plus one
  opt-in local benchmark); C1 evidence records the isolation proof
  and the two ignored separately credentialed live-provider probes.

### Current trace anchors

The implementation order follows the real seams, not a parallel architecture:

1. Native host launches the Rust child and sends bootstrap material through
   memory/stdio ([host.rs](/Users/pongsathonkheeereekaew/harness-flow/desktop/native-host/src/host.rs:83)); runtime entry consumes it before serving ([main.rs](/Users/pongsathonkheeereekaew/harness-flow/crates/codinal-runtime/src/main.rs:1)).
2. GPUI sends `StartTurn` through the authenticated client ([control client](/Users/pongsathonkheeereekaew/harness-flow/desktop/control-plane-client/src/lib.rs:592)); the runtime validates profile, creates the durable turn/budget reservation, and spawns the provider job ([runtime](/Users/pongsathonkheeereekaew/harness-flow/crates/codinal-runtime/src/lib.rs:4240)).
3. The current job reads the full session history and calls a provider that
   incrementally parses SSE and persists bounded deltas before returning an
   `AssistantTurn` ([provider job](/Users/pongsathonkheeereekaew/harness-flow/crates/codinal-runtime/src/lib.rs:4586) · [provider transport](/Users/pongsathonkheeereekaew/harness-flow/crates/codinal-providers/src/lib.rs:433) · [history read](/Users/pongsathonkheeereekaew/harness-flow/crates/codinal-storage/src/lib.rs:202)). The bounded read-file loop, prompt compiler/cache telemetry, and apply-patch approval resume reuse the same turn context; remaining C2a work is the manual/live evidence gate.
4. GPUI already has an `assistant_delta` reducer and bounded live buffer ([GPUI reducer](/Users/pongsathonkheeereekaew/harness-flow/desktop/gpui/src/main.rs:1552)); C2a completes the runtime event producer and contract rather than adding a second UI streaming path.

## Outcome

Codinal is a macOS-first, Rust-only coding-agent desktop. A GPUI process is the
viewport and a separate Rust runtime process owns execution, policy, durable
state, and authenticated local control-plane APIs. Python, Tauri, WebView, and
silent fallback are absent from every product path from the first corrective
change onward.

The first executable release is intentionally narrow: OpenCode Go and DeepSeek
through one OpenAI-compatible adapter, streaming turns, durable approvals,
interrupt, one bounded file mutation, atomic receipts, and crash/reconnect
recovery. Until that slice passes its gates, Codinal remains useful as an
explicit Rust read-only application.

## Non-negotiable invariants

1. Rust is the only product runtime and the only control plane. No Python
   process starts from Codinal in development, dogfood, release, recovery,
   conformance, or fallback.
2. Exactly one Rust runtime owns writes for a data directory. `Run` and all
   mutations require a lifetime writer lock; failure to acquire it produces a
   diagnostic read-only state.
3. GPUI never executes consequential work. Every mutation passes through one
   Rust policy and approval chokepoint and is recorded in an immutable receipt.
4. The local API binds only `127.0.0.1`, uses a random port and per-launch
   bearer token, and never persists or logs that token or provider secrets.
5. Existing data is migrated in place with a pre-migration backup, a versioned
   forward-only transaction, integrity checks, and fail-closed recovery. A
   failed migration never creates or resets a replacement database.
6. Provider credentials live only in macOS Keychain. SQLite, config, events,
   diagnostics, receipts, argv, and logs contain credential references only.
7. Prompt policy and skills guide models but are not a security boundary. Rust
   runtime policy remains authoritative even when a host ignores instructions.
8. User-visible completion means runtime state and persisted audit/receipt state
   agree. UI optimism never turns a pending or failed action into success.

## Process and ownership topology

```text
GPUI viewport
    |
    | authenticated HTTP + WebSocket on 127.0.0.1
    v
Rust runtime process
    |-- writer lock + SQLite migrations
    |-- provider adapters + turn coordinator
    |-- policy / approval / audit / receipts
    |-- event sequence + cursor replay
    `-- tools and Harness Manager
```

The native host spawns the runtime, passes bootstrap material through memory,
checks readiness, and owns graceful shutdown. GPUI and runtime stay separate so
UI failure cannot become data ownership or execution failure. Writer-lock
diagnostics may expose PID, process start time, and data-directory identity, but
never secrets. A stale lock is not removed from PID evidence alone; process
identity and an explicit recovery flow are required.

### Runtime readiness

- `booting`: runtime exists but storage/provider capability is unresolved.
- `read_only`: sessions, messages, receipts, and diagnostics are readable;
  `Run` and `Apply` are visibly disabled with an actionable reason.
- `ready`: writer lock, migration, provider probe, policy, events, and receipt
  writer gates have passed.
- `degraded`: an active capability became unavailable; existing local data
  remains readable and unsafe actions fail closed.

Offline startup uses the bundled or cached model catalogue for display only,
marks it stale, and keeps `Run` disabled until the selected provider probe
succeeds.

Health is a typed readiness contract, not `status == ok`. It includes
`mode`, stable `reason_code`, migration state, writer-lock state/owner metadata,
event-store readiness, execution owner, and receipt writer. Native host accepts
`read_only` as a successful launch but never aliases it to `ready`.

`ReadOnlyBootstrap` is a distinct path: it does not acquire the writer lock,
run migration, open writable SQLite handles, repair files, or publish events.
It is the only C0 production bootstrap. `OwnerBootstrap` is unavailable on
production data until C1 gates pass on copied data.

## Durable data and migration contract

Rust preserves the existing SQLite identities and schemas rather than creating
a parallel database. Before the first Rust write it must:

1. acquire the exclusive writer lock;
2. fingerprint the data directory and schema versions;
3. create and verify a restorable backup;
4. run the forward migration in a transaction;
5. run integrity and compatibility checks;
6. publish readiness only after all checks pass.

Because the data directory contains multiple SQLite databases, directory-wide
atomicity is implemented with a durable migration journal rather than claimed
from independent SQLite transactions. The journal records the ordered database
set, source/target versions, backup checksum, per-database stage, commit marker,
and reconciliation result. APIs remain read-only until every database is at a
compatible target state. Bootstrap resumes or rolls back from the journal after
a crash; a mixed-version directory is never published as ready.

Shadow validation is allowed only against immutable snapshots or copied data.
There is no Python writer period and no dual-write cutover. Downgrade to a
Python-owned schema is unsupported after migration.

On failure, preserve the original data and backup, refuse the writer role, and
enter diagnostic read-only mode. Recovery is explicit; Codinal never silently
resets, imports into a new database, or chooses between divergent histories.

Binary rollback is allowed only while the installed binary declares the
migrated schema within its readable range. Release manifests carry minimum and
maximum readable schema versions. After an incompatible migration, rollback
means explicit backup recovery with a preview of post-backup data that would be
lost; an older binary must refuse startup rather than open a newer schema.

## Turn and event contracts

The runtime coordinator is the only authority allowed to transition a turn:

```text
created -> streaming -> awaiting_approval -> applying
                                      |          |
                                      v          v
                          completed | interrupted | failed

restart -> recovering -> one valid durable state above
```

The exhaustive transition contract is:

| State | Event | Next state | Durable effect before publish |
|---|---|---|---|
| `created` | provider accepted | `streaming` | attempt + budget reservation |
| `created` | provider/fallback rejected | `failed` | terminal receipt + reservation release |
| `streaming` | answer completed without tool | `completed` | final usage + receipt |
| `streaming` | valid patch proposal | `awaiting_approval` | proposal, digest, hashes, approval row |
| `streaming` | provider failure/interrupt | `failed` or `interrupted` | usage reconciliation + receipt |
| `awaiting_approval` | approve | `applying` | idempotent decision + mutation journal |
| `awaiting_approval` | deny/expire/interrupt | `failed` or `interrupted` | decision + receipt; no mutation |
| `applying` | atomic commit | `completed` | committed mutation + receipt |
| `applying` | rollback/failure | `failed` | reconciled mutation journal + receipt |
| any non-terminal | restart | `recovering` | recovery attempt row |
| `recovering` | valid journal | deterministic state above | reconciled rows before events |
| `recovering` | invalid journal | `failed` | fail-closed diagnostic receipt |

Every event contains `turn_id` and a monotonically increasing per-turn
sequence. A reconnect supplies its last cursor and receives missing durable
events. Reloading the terminal receipt is the terminal-state fallback.

`turn_state`, `turn_events`, `pending_approvals`, `budget_reservations`, and
`mutation_journal` are durable. State/event writes commit before publication;
`(turn_id, sequence)` is unique. Active turns are never compacted. Terminal
events are retained for 30 days subject to a 50,000-event or 64 MiB per-turn
cap, after which the terminal receipt remains authoritative. Cursors include a
store generation; an unavailable cursor returns `cursor_expired` with the
receipt reload target instead of silently returning only future events.

Recovery rules are deterministic:

- a turn found in `streaming` becomes `interrupted`; no provider request is
  replayed automatically;
- `awaiting_approval` resumes the same durable approval;
- an atomic file commit already in progress is reconciled from its transaction
  record before a terminal receipt is written;
- retry always creates a new turn linked to the previous turn.

Interrupt aborts the provider request/stream, prevents new side effects, and
writes an `interrupted` receipt. An atomic file commit that has crossed its
commit boundary completes or rolls back as one operation; it is never stopped
mid-write.

The runtime must accept interrupt while a stream connection is active. Before
C2 it therefore needs bounded concurrent connection handling, a turn
coordinator independent of request tasks, one cancellation latch per turn, and
a graceful-shutdown handshake before native host may hard-kill the process.

## Provider and model specification

### First adapter and profiles

The target protocol is OpenAI-compatible Chat Completions with SSE, but sharing
an adapter is an outcome of conformance, not an assumption. C2 begins with a
contract spike that captures redacted request/response/SSE/tool/usage fixtures
for each endpoint. A shared parser or transport is extracted only for fixture
shapes proven identical. Responses API is a later, separate adapter. Initial
profiles are:

- `opencode-go`: primary subscription profile;
- `deepseek`: independent pay-per-use profile and credential.

Each profile keeps endpoint, auth header, credentials, model IDs, capability
quirks, pricing, and conformance evidence separate. `ProviderProfile::OpenCodeGo`
is distinct from `HostAdapter::OpenCodeCli`; provider conformance never grants
permission to mutate host configuration.

Settings define defaults; provider, model, and effort can be overridden per
session and only affect the next turn. Each receipt immutably records the
effective provider, endpoint profile, model, effort, capability snapshot, and
usage classification.

### Model catalogue and capability truth

Model/effort controls use three sources:

1. a bundled snapshot for startup/offline display;
2. synchronized `models.dev` metadata;
3. a runtime probe for the selected provider, endpoint, and model.

Provider evidence may reduce a catalogue capability but metadata never enables
a capability that the endpoint probe rejects. `Run` requires streaming and
tool-call conformance for the selected combination. Invalid tool-call JSON is
never repaired by the runtime; the model may self-correct once within budget,
then the turn fails with a redacted diagnostic.

Effort is a typed variant per `provider + endpoint + model + protocol`, not a
generic string. The catalogue stores allowed variants, default, wire mapping,
and conformance revision. Requests and receipts distinguish requested effort
from effective effort; unsupported or clamped values are visible and cannot be
silently recorded as requested.

### Auto fallback and cost controls

`Auto fallback` routes OpenCode Go to DeepSeek and defaults to `Off`. Enabling
it requires hard limits per turn and per day. Unknown or insufficient budget
stops the route and asks for approval. Automatic fallback is allowed only
before the first assistant output or tool proposal and before any side effect.
After output begins, retry is a new turn.

Hard limits use a durable cost ledger. Before dispatch, the runtime atomically
reserves the maximum estimated turn cost against both limits using a versioned
price snapshot, configured maximum output tokens, and the budget policy's IANA
timezone. Final provider usage commits the actual amount and releases the
remainder; interrupted or missing usage is reconciled conservatively from the
reserved estimate. Concurrent turns cannot reserve the same remaining budget.

When OpenCode Go recovers it becomes primary for the next turn; Codinal never
switches provider mid-turn. Receipts distinguish provider-reported usage,
Codinal-estimated usage, and unavailable usage; estimates are never presented
as billed totals.

Only explicitly selected file content and tool results are sent to providers.
Receipts store selected paths and content hashes, not duplicate source content.

## Best-overall Rust performance and cost envelope

This is a cross-cutting contract for the Rust runtime. It supplements the
security and compatibility gates above; it does not permit a faster path to
bypass policy, receipts, migration, or approval.

### Prompt and provider contract

The provider boundary owns two typed values:

```text
PromptEnvelope {
    stable_prefix,
    dynamic_suffix,
    stable_prefix_hash,
    cache_policy,
}

ProviderUsage {
    input_tokens,
    cache_read_tokens,
    cache_write_tokens,
    output_tokens,
    first_delta_ms,
    total_latency_ms,
    cost: provider_reported | codinal_estimated | unavailable,
}
```

Unknown provider fields remain `unknown`; they are never recorded as zero.
The stable prefix is deterministic policy, tool schemas, and genuinely static
project instructions. The dynamic suffix is the current user request,
changing tool results, timestamps, and ephemeral context. The prompt compiler
must preserve this ordering and must not pad the system prompt merely to reach
a provider threshold. OpenAI requires an identical prefix for reuse and
reports cached-token usage; Anthropic and Gemini expose different cache
controls and accounting, so retention and cache fields remain provider
capabilities rather than one universal switch. [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) · [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) · [Gemini context caching](https://ai.google.dev/gemini-api/docs/generate-content/caching)

The session prompt compiler reads an append-only message cursor, reuses the
serialized stable prefix and deterministic tool-schema bytes, and compacts by
tokens rather than message count. Compaction creates a versioned summary
boundary without rewriting unrelated stable content. A model response is not
served from a semantic cache for coding turns; only deterministic retrieval,
artifact, and provider transport caches may short-circuit work.

The turn coordinator owns the bounded tool loop. A `read_file` proposal is
validated and executed inside the workspace boundary, its redacted result is
appended to the prompt cursor, and the same turn may request the provider again
up to a fixed tool-round budget. A write proposal enters durable approval;
approve applies the idempotent mutation, appends the tool result, and resumes
the same turn only within its remaining budget. Deny, expiry, source-hash drift,
or cancellation terminates the turn without a hidden retry. Unsupported or
malformed tool calls fail closed. A turn never reports `completed` merely
because a tool call was classified as allowed.

### Latency, concurrency, and streaming

- One process-wide async runtime and one reusable HTTP client/connection pool
  exist per provider endpoint. Provider requests attach credentials per
  request; they do not construct a Tokio runtime or `reqwest::Client` per turn.
- The provider interface returns a streaming attempt/sink, not a completed
  `AssistantTurn` as its only result. Provider transport, turn coordination,
  tool-loop state, and terminal reconciliation are separate typed stages.
- SSE is parsed incrementally. The runtime publishes bounded, coalesced
  `assistant_delta` events while the stream is active; each coalesced event is
  persisted before publication and has a bounded payload. The terminal
  assistant message and receipt remain the durable authority. It never waits
  for the complete response before publishing the first delta.
- The v1 event contract defines `assistant_delta` ordering, turn/session
  identity, UTF-8 text, coalescing boundaries, replay, and terminal behavior.
  GPUI renders live and replayed deltas through the same reducer; a reconnect
  never duplicates text or loses the terminal receipt.
- The control plane enforces a configured maximum active-connection count and
  bounded turn workers, and a bounded tool-round count. A connection reserves
  capacity before spawning and releases it exactly once; overload is an
  explicit typed response. Unbounded thread-per-connection growth is not a
  capacity strategy. The current nonblocking accept loop's fixed sleep is not
  accepted as a latency budget; it must use an evented/blocking wakeup or be
  justified by measurement. A new HTTP/WebSocket framework is not introduced
  unless a benchmark proves the existing wire parser is the bottleneck.
- `StartTurn` carries a durable idempotency key. Retrying the same request
  returns the existing turn result rather than creating a second provider call;
  a session has at most one active prompt/tool loop, while independent sessions
  may run concurrently. This protects transcript order, cache-prefix reuse,
  approval provenance, and budget reservations.
- Interrupt cancels the provider stream, closes the bounded delta path, and
  reconciles usage and budget exactly once. Fallback is still allowed only
  before the first published assistant delta or tool proposal; the coordinator
  records `first_delta_seen` durably so an error path cannot accidentally retry
  after output.

Durable event writes remain ordered through the runtime store. Read-only
queries use read-only handles where safe; coalesced deltas, not individual
tokens, are the unit of event persistence. The prompt cache is an optimization
only: restart rebuilds the prompt from durable message/cursor state and
invalidates serialized prefixes on model, tool-schema, policy, or compaction
version changes.

### Measurement and economics

Before optimization, the gate ledger freezes a fixed fixture, prompt sequence,
provider/model/region, warm/cold condition, and supported macOS hardware. Each
condition runs at least 30 turns across 3 fresh sessions and records first
delta, p50/p95 turn latency, cache read/write tokens, uncached input tokens,
output tokens, cost, request bytes, CPU, RSS, and error/retry/fallback state.
The same harness may compare bare Pi, the Codinal Rust path, and the previous
reference path, but no winner is declared without identical inputs.

Cost is computed only from provider-supported fields:

```text
uncached_input * input_price
+ cache_write * cache_write_price
+ cache_read * cache_read_price
+ output * output_price
```

Initial comparative targets are explicit: warm-session cache reuse must meet or
exceed the bare-Pi baseline on the same provider sequence; warm-session cost
must be lower than the equivalent no-cache sequence when cache fields are
reported; local first-delta forwarding must be at or below 10 ms P95 after the
provider chunk is received; end-to-end first-delta latency must not regress
more than 5% against the same-provider baseline; and the editor bundle target
is at least 30% below the current 1,275,451-byte raw artifact before release.
If a provider or platform cannot support a target, the gate records `unknown`
and blocks a claim of superiority rather than lowering the target silently.

Cache creation/retention is enabled only when the measured reuse benefit is
positive for that provider/model/session profile. A short or changing prompt
does not pay for a cache entry. Thinking/effort is a typed profile: fast/edit
turns do not inherit the deepest reasoning budget by default; deep reasoning is
reserved for tasks that justify its latency and cost.

### Bundle and maintainability budget

The release measurement separates native app, runtime binary, editor bundle,
compressed archive, and debug symbols. The editor build enables minification
and lazy language packs before adding further UI dependencies. Code is split
along `PromptEnvelope`, provider transport/SSE decoding, usage normalization,
session prompt compilation, and runtime orchestration boundaries; provider JSON
does not leak into the policy or UI layers. No broad refactor is accepted
without a passing contract/conformance gate.

## Safe execution vertical slice

`Run` remains behind an Experimental setting that defaults to `Off` until every
gate below passes. There is no less-safe hidden path.

The first slice includes exactly:

- one selected OpenCode Go or DeepSeek model and effort;
- prompt, SSE streaming, sequence replay, interrupt, and terminal receipt;
- `read_file` within the selected workspace;
- `apply_patch` for one file per approval;
- durable policy, approval, recovery, and audit;
- reconnect and kill/restart behavior.

Shell, Git/worktrees, MCP, editor parity, remote execution, and collaboration
are excluded. After the slice, expansion order is shell sandbox, Git/worktree,
then MCP.

### Approval transaction

Every `apply_patch` requires a new approval; standing workspace/session grants
do not exist in the first slice. The approval binds:

- approval ID and expiry;
- exact path and full diff;
- patch digest and source-file hash;
- workspace-root and resolved-symlink boundary result;
- provider/model/turn provenance.

The review pane shows the full diff, path, changed-line count, hashes, and
boundary status. Paths or symlinks resolving outside the workspace are refused.
If source content changes after proposal, the approval is invalidated and a new
patch must be generated. Approval decisions are durable and idempotent.

## Universal Harness Manager and multi-model work

Codinal includes the universal agents/skills harness as a Rust subsystem, not
as embedded Bash or Python scripts. The existing declarative content and
contracts are inputs; `install.sh`, `backup.sh`, and Python host adapters are
reference implementations only.

Create `codinal-harness` with one deep interface:

```text
Scan -> Plan diff -> Approval -> Atomic apply -> Verify -> Receipt / Rollback
```

The Harness Manager distinguishes four concepts:

- `Harness Source Bundle`: the canonical, versioned policy/skill/standard
  content shipped or explicitly imported by Codinal;
- `User Overlay`: user-owned additions that an update cannot delete;
- `Live Projection`: the effective `~/.agents` tree produced from source plus
  overlay;
- `Host Projection`: minimal generated links/config for each coding host.

The app does not perform bidirectional automatic backup from generated/live
paths. Import and export are explicit operations with diffs and provenance.
Read-only inventory/doctor ships first. Write management starts only after the
Rust execution slice is safe, initially for the already-conformed OpenCode
adapter. Claude Code, Codex, Cursor, Gemini, and other hosts remain visible as
`unverified` or read-only until their Rust adapters pass the same contract.

Universal policy is semantic, not identical provider text. A thin invariant
core and task skill are translated through model-specific profiles for tool,
context, effort, and protocol capabilities.

### Multi-model workflow

The first workflow is sequential:

```text
Planner -> Implementer -> Reviewer
```

Users configure default model/effort per role. Routing may recommend a profile
from local evidence but cannot choose outside the authorized role profile.
Reviewer defaults to a different model or provider from Implementer; using the
same model is allowed but visibly marked as reduced independence.

Before execution, Codinal displays every role, model, effort, fallback, and the
estimated workflow budget for one approval. Adding a stage, retry, reviewer, or
fallback outside that plan requires new approval.

Durable handoff contains only objective, constraints, plan, changed artifacts,
evidence, and unresolved risks. Hidden chain-of-thought is neither requested
nor stored.

A local evaluation ledger records task class, provider/model/effort, cost,
latency, policy failures, rollback, and objective verification outcome. It does
not duplicate source content, has no default telemetry, and supports export and
clear. Routing scores weight tests, builds, policy outcomes, and rollback above
subjective feedback.

## GPUI product specification

Codex is the visual shell source of truth: native macOS hierarchy, project/task
sidebar, conversation center, contextual environment pane, and Light/Dark
appearance. Codinal uses its own tokens, icons, fonts, assets, and safety
semantics; it does not pixel-clone proprietary UI.

OpenCode Desktop contributes component behavior for model/effort controls and
plan visibility. Comet contributes selected MIT-compatible GPUI interaction and
performance mechanics, with provenance recorded for copied code:

- bottom-aligned virtualized transcript with stable block IDs;
- coalesced streaming updates, row-height caching, scroll-anchor absorption,
  and interruptible follow-bottom behavior;
- composer state machine mapped to `Run -> Interrupt` for the first slice;
- pure view projections/reducers under thin GPUI entities;
- contextual approval/diff/receipt pane and restrained motion.

Conversation remains the primary surface. Execution, tools, approval, recovery,
and receipt states appear in the timeline; the right pane opens contextually for
environment and the approval transaction. Disabled actions remain visible with
specific reasons such as writer lock unavailable, migration required, provider
not configured, capability probe failed, or Experimental execution disabled.

Comet's always-dark identity, Loro/Cloudflare topology, crash auto-resume,
custom GPUI fork, branding, and unaudited assets are excluded. Reduced-motion,
keyboard navigation, focus behavior, and screen-reader semantics are release
requirements rather than polish.

## Delivery sequence

### C0 - Correct the architecture and establish true read-only mode

- Add `ReadOnlyBootstrap` and the typed health/readiness schema first.
- Remove Python sidecar launch from GPUI/native-host and restore the release
  prohibition against Python sidecars.
- Connect every GPUI read path to the Rust runtime only.
- Advertise truthful capabilities and render explicit read-only reasons.
- Rewrite Python-owner fixtures, capability labels, and runtime documentation as
  historical/reference material; no product or release test may rely on a
  Python owner.

Gate: launching Codinal starts no Python/Tauri/WebView process; sessions and
receipts remain readable; no lock, migration, repair, writable handle, or other
mutation occurs; all consequential actions are unavailable.

### C1 - Writer ownership and in-place migration

- Implement the lifetime writer lock, process identity diagnostics, backup,
  forward migration, integrity checks, and diagnostic read-only recovery.
- Maintain a checked-in route ownership matrix. Only the current vertical slice
  may advertise execution; every other route remains explicitly unavailable
  until its Rust implementation and evidence exist. A `501` placeholder is not
  a completed capability and cannot be enabled by the UI.
- Add the durable migration journal, turn/event/approval/budget/mutation stores,
  event sequence storage, cursor replay, concurrent connection workers, turn
  coordinator, cancellation latches, and graceful shutdown.

Gate: migration corpus passes on anonymized copies of existing databases;
subprocess kill/restart at named boundaries (backup fsync, each database stage,
commit marker, publication, cleanup) preserves one history; a held stream can
be interrupted through a second connection; the relevant Rust test suites pass
both with default parallel execution and with `--test-threads=1`.

### C2a - One-provider end-to-end execution slice

- Capture and freeze the OpenCode Go contract, then implement one pinned
  OpenCode Go model/effort, Keychain reference, Chat Completions SSE, usage,
  and capability evidence. No automatic fallback is active in C2a.
- Implement the prompt compiler and provider usage/cache contract, persistent
  endpoint transport, incremental SSE parsing, bounded coalesced delta events,
  first-delta telemetry, and deterministic tool-schema serialization.
- Implement the bounded `read_file -> tool result -> provider` loop and the
  `apply_patch -> approval -> atomic apply -> tool result` resume path. Tool
  schemas, tool results, approvals, and provider attempts share one turn ID and
  durable sequence; no tool is executed from the UI.
- Implement turn coordinator, interrupt, policy, durable approval, single-file
  `apply_patch`, atomic receipt, and recovery.
- Include the minimum Safety UI kernel: provider/model/effort display,
  `Run -> Interrupt`, readiness reason, keyboard/VoiceOver-operable full diff,
  approve/deny/expire states, and terminal receipt.

Gate: the complete GPUI user path passes with Experimental execution enabled
manually; no JSON-only approval or headless-only substitute satisfies the gate.

### C2b - DeepSeek and budgeted fallback

- Capture and freeze the DeepSeek endpoint contract before sharing parser code.
- Add typed model/effort variants, provider-specific cache usage/cost fields,
  pinned catalogue snapshot, durable cost reservation/reconciliation,
  per-turn/daily limits, and pre-output fallback.
- Add budget-capped live conformance with a TTL and automatic readiness removal
  on capability drift.

Gate: deterministic fixtures pass for both profiles and capped live smoke proves
the exact endpoint/model/effort revisions without exceeding the approved test
budget.

### C3 - Codex-style GPUI workbench

- Freeze an owned Codinal UI contract: reference snapshots, layout anatomy,
  tokens, Light/Dark states, and model/effort/approval state transitions.
- Implement pure projections, stable transcript rows, frame coalescing, timeline
  states, and contextual approval/diff/receipt pane. Measure before porting more
  complex Comet virtualization or layout caching; adopt each technique only
  when the frozen performance budget requires it.
- Meet accessibility, reduced-motion, reconnect, typing, scrolling, memory,
  first-paint, first-delta, cache-cost, and bundle budgets on supported macOS
  hardware. The editor bundle must be minified and language modes lazy-loaded.

Gate: live and replayed turns are behaviorally identical and no UI state can
bypass runtime readiness or approval. The evidence matrix includes keyboard-only,
VoiceOver labels/announcements, focus trap and restoration, contrast,
Light/Dark, and reduced-motion. Any copied upstream code has a per-file source
manifest (commit/path, copied or clean reimplementation, license/copyright) and
NOTICE is updated before merge; third-party assets and provider marks require
separate approval.

### C3b - Rust-only release and retirement

- Remove obsolete Python/Tauri/WebView runtime code and release assets.
- Sign, notarize, staple, inspect, and exercise only schema-compatible updater
  rollback; incompatible rollback uses the explicit backup recovery contract.

Gate: fresh install and upgrade E2E pass; artifact/process/SBOM inspection
proves a Rust-only release. Harness Manager and multi-model work do not block
this release.

### C4a - Rust Harness Manager read-only inventory

- Ship read-only host/skill/policy inventory first.

Gate: Source Bundle, User Overlay, Live Projection, Host Projections, drift,
ownership, and capability evidence are visible without filesystem mutation.

### C4b - Multi-model workflow

- Add durable `WorkflowRun`, `StageAttempt`, immutable role-profile snapshot,
  handoff schema, workflow budget reservation, artifact ownership, and explicit
  stage retry/recovery rules.
- Add authorized role profiles, structured handoff, independent review, budget
  approval, and local evaluation ledger independently of host projection writes.

Gate: multi-model receipts reconstruct every stage, budget, artifact owner,
retry, and reduced-independence state without hidden reasoning or mutable
configuration lookup.

### C4c - Rust Harness Manager writes

- Port source/overlay/projection planning, ownership, atomic apply, rollback,
  and verification to Rust; enable `HostAdapter::OpenCodeCli` writes only after
  separate host-projection conformance.

Gate: malformed config is byte-preserved, non-owned paths are untouched,
updates cannot delete overlays, and uninstall removes only journal-owned paths.

### C5 - Tool expansion

- Add shell sandbox, then Git/worktrees, then MCP through the same policy path.

Gate: each tool class passes policy, boundary, interrupt, audit, receipt, and
recovery conformance before the next class starts.

## Acceptance gates

Execution cannot default to `On` until fresh evidence proves:

1. OpenCode Go and DeepSeek streaming/tool conformance for selected models and
   efforts, including invalid frames, rate limits, interrupted usage, and
   fallback cutoff, read-tool continuation, and approval-resume behavior;
2. prompt-prefix determinism, provider cache-read/write telemetry, cost
   reconciliation, first-delta-before-terminal-event, and the fixed cold/warm
   benchmark with no unmeasured performance claim;
3. kill/restart recovery from every turn state and every migration boundary;
4. writer-lock exclusion, stale-lock diagnostics, one-history migration, and
   backup recovery on real anonymized data copies;
5. WebSocket ordering, cursor replay, reconnect, terminal receipt reload, and
   bounded event retention;
6. approval durability/idempotence, patch/source hash drift, workspace and
   symlink boundaries, atomic write failure, redaction, and Keychain isolation;
7. GPUI keyboard, focus, reduced-motion, accessibility, transcript scale,
   typing latency, scrolling, and reconnect behavior;
8. native/editor/archive/debug-symbol size inspection and binary/process/SBOM
   inspection showing no Python/Tauri/WebView path.

The gate must be a fresh run. Historical evidence or a capability declaration
without an executable conformance result is insufficient.

### Executable gate ledger

Every stage owns a checked-in ledger under `docs/evidence/cutover/<stage>/gate.md`
with `owner`, dependencies, exact command, fixture/credential class,
environment, numeric threshold or exact expected result, artifact checksum,
rollback, stop condition, and `pending | passed | failed`. Required commands are
Rust-only targets implemented before their gate can pass:

| Stage | Required fresh command/evidence | Stop condition |
|---|---|---|
| C0 | `cargo test --manifest-path crates/codinal-runtime/Cargo.toml read_only`; `cargo test --manifest-path desktop/native-host/Cargo.toml read_only`; packaged process/write audit and Python-owner search | any Python/WebView process, release dependency, or filesystem mutation |
| C1 | runtime-bootstrap subprocess fault suite, default-parallel and serial Rust test runs, route-capability matrix, anonymized migration-corpus manifest/checksums, and connection-capacity fault test | mixed history, fixture/port/path race, unverified backup, missed interrupt, unbounded connections, or unreconciled journal |
| C2a | pinned OpenCode Go fixture suite, incremental-SSE/first-delta test, prompt/cache telemetry test, bounded read-tool loop, approval-resume/idempotency tests, capped live smoke, and GPUI Safety UI E2E | capability drift, buffered streaming, fabricated usage, tool-loop loss, duplicate provider call, approval bypass, missing receipt, or budget overrun |
| C2b | pinned DeepSeek fixture/live conformance, provider-cost/cache reconciliation, and concurrent reservation tests | unbounded spend, cache-cost regression, post-output fallback, or requested/effective effort mismatch |
| C3 | UI contract snapshots, accessibility matrix, fixed cold/warm latency/cache benchmark, and bundle-size runner | safety surface inaccessible, unlicensed provenance, missing numeric budget, or regression |
| C3b | signed/notarized package smoke, process/resource/SBOM scan, upgrade and schema-compatible rollback | legacy runtime artifact or incompatible rollback offered |
| C4a-c | Harness and workflow contract suites against isolated homes/data copies | non-owned mutation, overlay deletion, hidden stage, or unverifiable rollback |
| C5 | per-tool adversarial and recovery suites | any tool bypasses policy, boundary, receipt, or interrupt |

C3 starts with a measurement ticket that freezes numeric transcript size,
stream rate, first-delta P95, input-to-paint P95, frame-time P95, prompt/cache
tokens, cache-cost delta, request bytes, idle wakeups, RSS, native binary,
editor bundle, archive, and debug-symbol budgets in its gate ledger before
optimization work. C3 cannot pass with relative or unrecorded performance,
cache, cost, or size claims.

## Explicitly deferred

- Responses API and non-OpenAI-compatible provider adapters;
- multi-file approval transactions;
- standing approvals;
- editor/LSP parity and inline completion;
- remote execution, collaboration, CRDT sync, and cloud control planes;
- Linux and Windows releases;
- automatic parallel swarms or autonomous routing outside approved profiles.

## Supporting references

- `docs/plan/fully-rust-codex-cursor-cutover-plan.md`: operational backlog and
  later editor parity only; this document wins on conflict.
- `docs/plan/codinal-parity-roadmap.md`: historical parity inventory; not a
  runtime architecture authority.
- `docs/research/comet-adoption-review.md`: pinned Comet source map, adaptation,
  avoidance, and licensing evidence.
- `docs/research/codinal-pi-synara.md`: primary-source cache, latency, bundle,
  and architecture comparison; Pi is a reference for provider cache contracts,
  not a replacement for Codinal's policy boundary.
- `docs/plan/codinal-settings-ecosystem-surface.md`: Settings information
  architecture, constrained by the Harness Manager rules here.
- `docs/decisions/0004-rust-only-runtime-and-harness-boundary.md`: durable
  architectural rationale.
