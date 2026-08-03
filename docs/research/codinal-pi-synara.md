# Codinal, Pi, and Synara: primary-source comparison

Research date: 2026-08-02
Repository convention: `docs/research/`
Scope: source, README, package manifests, tests, and repository documentation only. No application/source code was modified.

## Executive summary

**Synara is not an independent implementation of the same complete system as Codinal or Pi.** It is a broader desktop orchestration product that embeds Pi directly as one provider/runtime and also wraps other provider runtimes. Its Pi path is therefore *essentially Pi’s agent engine*, with Synara’s adapter, session lifecycle, event translation, gateway tools, and UI around it. That narrow overlap is real; it is not evidence that Synara and Codinal have the same architecture.

The important distinctions are:

- **Pi** is a TypeScript/Bun monorepo with a unified provider API, agent core, coding-agent session/CLI, TUI, and optional remote protocol packages. It has first-class provider prompt-cache controls (`cacheRetention`, `sessionId`, provider cache markers/keys), usage accounting, and cache-waste/cost instrumentation.
- **Synara** is a Node/WebSocket + React/Vite + Electron desktop shell. Its `PiAdapter` lazy-loads and calls the Pi SDK directly; it reads Pi’s `cacheRead` usage and model cache pricing, but the adapter does not explicitly set Pi’s cache-retention or session-affinity options. Synara’s other caches—WebSocket compression, cursor replay, normalized UI state, and static assets—are transport/UI caches, not model prompt caches.
- **Codinal** is a local macOS Rust/GPUI host with an authenticated loopback HTTP/WebSocket Python sidecar. It has explicit policy, approval, Seatbelt sandbox, Git worktree, bounded-worker, conversation-storage, provider-router, semantic-index, PDF, and outbound-message mechanisms. Its canonical provider contract does not expose first-class prompt-cache controls, cache-read/write usage, or cost fields; its Anthropic adapter sends ordinary system/messages payloads without Pi-style cache markers.

No apples-to-apples benchmark was found or run for model cache-hit rate, first-token latency, model latency, CPU/RSS, or end-to-end runtime throughput. The report therefore distinguishes repository facts from inference. The only numeric observations below are either measurements of the current local Codinal release artifact or values explicitly documented by the repositories.

## Reproducibility and evidence labels

The GitHub comparisons were made from clean clones pinned to:

| Project | Snapshot | Direct source |
|---|---|---|
| Pi | `aa0ec808b970db31822e07835a46647cb51d9d66` (`@earendil-works/pi` 0.83.0; latest commit at research time) | [Pi repository](https://github.com/earendil-works/pi/tree/aa0ec808b970db31822e07835a46647cb51d9d66) |
| Synara | `65f6684aa6ff88c8d57a9f11d541a54b41be1539` (lockfile resolves Pi 0.81.1) | [Synara repository](https://github.com/Emanuele-web04/synara/tree/65f6684aa6ff88c8d57a9f11d541a54b41be1539) |
| Codinal | local HEAD `86fd4c8445e3aa151f42c177d2554725cc61ff87` | [Codinal source snapshot](https://github.com/pongsathonkheereekaew/Codinal/tree/86fd4c8445e3aa151f42c177d2554725cc61ff87) |

`[Fact]` means directly visible in source, manifest, test, repository documentation, or a measurement run. `[Inference]` means a reasoned consequence that needs a controlled benchmark or additional source confirmation.

## Are they essentially the same thing?

| Question | Answer | Evidence |
|---|---|---|
| Is Synara’s Pi provider using the same underlying agent implementation as Pi? | **Yes, narrowly.** | Synara imports `@earendil-works/pi-coding-agent`, `@earendil-works/pi-agent-core`, and `@earendil-works/pi-ai`, then calls `createAgentSessionFromServices`, `createAgentSessionRuntime`, and `session.prompt()`. [Synara PiAdapter imports](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/apps/server/src/provider/Layers/PiAdapter.ts#L9-L21) · [runtime construction](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/apps/server/src/provider/Layers/PiAdapter.ts#L2029-L2091) |
| Is Synara a reimplementation of Pi? | **No.** | It is an adapter around the Pi SDK and a generic provider facade; the Pi SDK is lazy-loaded only when the Pi provider is used. [lazy import](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/apps/server/src/provider/Layers/PiAdapter.ts#L319-L324) |
| Is Synara the same complete product/runtime as Codinal? | **No.** | Synara’s documented topology is browser → WebSocket server → provider service/runtime, with React/Vite and Electron. Codinal’s local runtime is a Rust/GPUI host plus authenticated loopback Python sidecar and policy-bound tools. [Synara architecture](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/.docs/architecture.md#L1-L38) · [Codinal runtime](https://github.com/pongsathonkheereekaew/Codinal/blob/86fd4c8445e3aa151f42c177d2554725cc61ff87/runtime/README.md#L1-L24) |
| Is Synara’s Pi dependency identical to the current Pi snapshot? | **No.** | Synara’s lockfile resolves Pi packages to 0.81.1, while the researched Pi snapshot’s package manifests are 0.83.0. [Synara lockfile](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/bun.lock#L405-L409) · [Pi AI manifest](https://github.com/earendil-works/pi/blob/aa0ec808b970db31822e07835a46647cb51d9d66/packages/ai/package.json#L1-L4) |

## Architecture and concrete mechanisms

### Pi

`@earendil-works/pi-ai` is the provider-neutral API and includes Anthropic, Bedrock, Google, Mistral, OpenAI, and related provider dependencies. `@earendil-works/pi-agent-core` owns general agent state/loop mechanics, while `@earendil-works/pi-coding-agent` supplies the coding-agent CLI/session surface. The coding-agent package also builds a standalone Bun binary. [Pi AI manifest](https://github.com/earendil-works/pi/blob/aa0ec808b970db31822e07835a46647cb51d9d66/packages/ai/package.json#L1-L74) · [Pi coding-agent manifest](https://github.com/earendil-works/pi/blob/aa0ec808b970db31822e07835a46647cb51d9d66/packages/coding-agent/package.json#L1-L43)

Pi’s prompt-cache design is in the provider API, not an incidental UI feature:

- `CacheRetention` is `none | short | long`, with default `short`; `sessionId` is available for session-based caching/routing. [Pi stream options](https://github.com/earendil-works/pi/blob/aa0ec808b970db31822e07835a46647cb51d9d66/packages/ai/src/types.ts#L100-L142)
- Provider compatibility describes session-affinity headers and long-retention support, including the reason that routing requests to the same replica can maximize cache hits. [Pi compatibility settings](https://github.com/earendil-works/pi/blob/aa0ec808b970db31822e07835a46647cb51d9d66/packages/ai/src/types.ts#L564-L613)
- Anthropic requests translate retention into cache-control markers and parse cache-read/cache-write usage. [Anthropic cache controls](https://github.com/earendil-works/pi/blob/aa0ec808b970db31822e07835a46647cb51d9d66/packages/ai/src/api/anthropic-messages.ts#L49-L72) · [usage parsing](https://github.com/earendil-works/pi/blob/aa0ec808b970db31822e07835a46647cb51d9d66/packages/ai/src/api/anthropic-messages.ts#L533-L585) · [conversation/tool breakpoints](https://github.com/earendil-works/pi/blob/aa0ec808b970db31822e07835a46647cb51d9d66/packages/ai/src/api/anthropic-messages.ts#L1256-L1320)
- OpenAI-compatible paths derive a bounded prompt-cache key from the session id and parse `cached_tokens`. [OpenAI cache key](https://github.com/earendil-works/pi/blob/aa0ec808b970db31822e07835a46647cb51d9d66/packages/ai/src/api/openai-codex-responses.ts#L281-L330) · [usage parsing](https://github.com/earendil-works/pi/blob/aa0ec808b970db31822e07835a46647cb51d9d66/packages/ai/src/api/openai-responses-shared.ts#L541-L555)
- Compaction deliberately disables cache writes for standalone summaries and uses a fresh session id; default compaction reserves 16,384 tokens and retains roughly 20,000 recent tokens. [compaction request](https://github.com/earendil-works/pi/blob/aa0ec808b970db31822e07835a46647cb51d9d66/packages/agent/src/harness/compaction/compaction.ts#L118-L137) · [compaction defaults](https://github.com/earendil-works/pi/blob/aa0ec808b970db31822e07835a46647cb51d9d66/packages/agent/src/harness/compaction/compaction.ts#L163-L183)
- The coding-agent layer computes cache misses, missed tokens, missed dollars, idle time, and model changes. Its tests are synthetic/unit tests; they are not a workload benchmark. [cache-stats implementation](https://github.com/earendil-works/pi/blob/aa0ec808b970db31822e07835a46647cb51d9d66/packages/coding-agent/src/core/cache-stats.ts#L4-L30) · [miss/cost calculation](https://github.com/earendil-works/pi/blob/aa0ec808b970db31822e07835a46647cb51d9d66/packages/coding-agent/src/core/cache-stats.ts#L50-L89)

### Synara

Synara’s documented system is a React/Vite browser app, a Node.js WebSocket/HTTP server, ordered push/event orchestration, and provider runtimes. Its architecture document describes `codex app-server` over JSON-RPC/stdio as one runtime path; the current source additionally contains multiple provider adapters, including Pi. [Synara architecture](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/.docs/architecture.md#L1-L38)

The Pi adapter creates or opens a Pi `SessionManager`, constructs Pi services/runtime, subscribes to Pi session events, and invokes Pi’s `session.prompt()`/`session.compact()`. It also creates a Synara-managed Bash process supervisor and can add gateway tools. [session start](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/apps/server/src/provider/Layers/PiAdapter.ts#L2029-L2115) · [event subscription](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/apps/server/src/provider/Layers/PiAdapter.ts#L2235-L2250) · [prompt call](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/apps/server/src/provider/Layers/PiAdapter.ts#L2470-L2488) · [compaction delegation](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/apps/server/src/provider/Layers/PiAdapter.ts#L2664-L2679)

Synara reads Pi’s session usage, including `cacheRead`, and publishes it as `cachedInputTokens`. It also carries cache-read/cache-write prices in its model catalog metadata. This is telemetry and pricing integration; cache policy remains in Pi/provider code. [usage normalization](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/apps/server/src/provider/Layers/PiAdapter.ts#L710-L765) · [Anthropic model pricing](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/apps/server/src/provider/Layers/PiAdapter.ts#L117-L157)

The adapter source does not explicitly pass `cacheRetention` or `sessionId` when it calls `session.prompt()`. **Inference:** Synara receives whatever cache behavior the embedded Pi session establishes by default, but its adapter does not expose an independent cache policy layer comparable to Pi’s `pi-ai` API. This should be verified against the exact resolved Pi 0.81.1 runtime and a provider request trace before making a cache-hit claim.

Synara’s own cache/latency mechanisms are mostly outside the model request:

- WebSocket `permessage-deflate` uses context takeover; the repository documents roughly 79% reduction for representative orchestration frames.
- Static web assets are documented as 18.09 MB identity, 4.44 MB gzip, and 3.63 MB Brotli; hashed assets are immutable for one year while `index.html` is no-cache.
- Thread subscriptions can resume from a cursor instead of refetching a full snapshot.

These mechanisms can reduce UI/network transfer or replay work, but they are not provider KV/prompt-cache hits. [Synara transport documentation](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/.docs/transport.md#L37-L70)

Synara also intentionally lazy-loads the Pi coding-agent package because its native clipboard dependency could bloat the desktop backend before a Pi session exists. [lazy-load rationale](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/apps/server/src/provider/Layers/PiAdapter.ts#L319-L324)

### Codinal

Codinal’s local implementation is not Pi-derived at the agent-loop boundary. The native host starts a Python sidecar; the sidecar exposes authenticated loopback HTTP/WebSocket control, a provider-neutral turn engine, fail-closed provider router, MCP, bounded tools, Seatbelt sandbox, Git worktrees, and SQLite conversation storage. [Codinal runtime overview](https://github.com/pongsathonkheereekaew/Codinal/blob/86fd4c8445e3aa151f42c177d2554725cc61ff87/runtime/README.md#L1-L85)

The canonical provider contract returns text/tool calls/reasoning and model capabilities, but has no named cache-read, cache-write, prompt-cache-key, retention, or cost fields. [Codinal provider contract](https://github.com/pongsathonkheereekaew/Codinal/blob/86fd4c8445e3aa151f42c177d2554725cc61ff87/runtime/providers/base.py#L17-L91)

The Anthropic adapter converts messages, filters ordinary settings, sets thinking/max-token behavior, and sends a normal `system` plus `messages` request. The inspected implementation does not add Pi-style `cache_control` breakpoints or report provider cache usage. [Codinal Anthropic request builder](https://github.com/pongsathonkheereekaew/Codinal/blob/86fd4c8445e3aa151f42c177d2554725cc61ff87/runtime/providers/anthropic_provider.py#L371-L411)

Codinal does have caches, but they solve different problems:

- The provider router caches SDK client objects and invalidates them when secrets change. This avoids repeated client construction; it is not prompt caching.
- The semantic index is a bounded local SQLite retrieval index with a 10-second build budget, 2-second query budget, and 128 MiB database budget. It stores retrieval vectors/coordinates and file fingerprints; it is not provider KV cache.
- PDF extraction/rendering has a small local cache.
- The turn engine strips display-only sidecars, appends dynamic context to an outbound copy of the last user message, redacts secrets, and caps outbound history at 2,000 messages. This controls payload size and safety; it can also change prompt-prefix stability and therefore *could* affect provider cacheability, but no hit-rate measurement exists. [outbound construction](https://github.com/pongsathonkheereekaew/Codinal/blob/86fd4c8445e3aa151f42c177d2554725cc61ff87/runtime/turn_engine/engine.py#L1201-L1210) · [dynamic context and redaction](https://github.com/pongsathonkheereekaew/Codinal/blob/86fd4c8445e3aa151f42c177d2554725cc61ff87/runtime/turn_engine/engine.py#L1326-L1348) · [performance budgets](https://github.com/pongsathonkheereekaew/Codinal/blob/86fd4c8445e3aa151f42c177d2554725cc61ff87/docs/perf/budgets.md#L22-L35)

### Current working-tree audit (uncommitted Rust cutover)

The clean-HEAD comparison above is not the whole current workspace. The dirty tree contains an in-progress Rust runtime/provider cutover, so these observations are current implementation facts, not release benchmarks:

- The Rust profile path reads and deserializes the complete session message list on every turn, appends the new user message, recreates the two built-in tool schemas, and has no system-prompt/cache-key/cache-retention field in the request body. [turn path](/Users/pongsathonkheeereekaew/harness-flow/crates/codinal-runtime/src/lib.rs:1119) · [message reload](/Users/pongsathonkheeereekaew/harness-flow/crates/codinal-storage/src/lib.rs:202) · [tool schema construction](/Users/pongsathonkheeereekaew/harness-flow/crates/codinal-runtime/src/lib.rs:1210)
- The Rust OpenAI-compatible provider creates a Tokio runtime and `reqwest::Client` per request, sends `stream: true`, but buffers the complete SSE response before parsing it. This prevents true first-delta delivery and forfeits connection-pool reuse on that path. [request construction](/Users/pongsathonkheeereekaew/harness-flow/crates/codinal-providers/src/lib.rs:387) · [client and buffering](/Users/pongsathonkheeereekaew/harness-flow/crates/codinal-providers/src/lib.rs:523)
- The current editor bundle is 1,275,451 raw bytes; the build config has `bundle: true` but no `minify` or code-splitting setting, and the editor entry imports eight language packages plus extensions into one IIFE. [build](/Users/pongsathonkheeereekaew/harness-flow/desktop/build.mjs:15) · [editor imports](/Users/pongsathonkheeereekaew/harness-flow/desktop/ui-src/editor.ts:10)
- Existing performance budgets cover tool/search/index/storage/engine limits, but not provider first-token latency, prompt tokens, cache-read/write tokens, cache hit rate, request bytes, CPU/RSS, or artifact size. [budget registry](/Users/pongsathonkheeereekaew/harness-flow/runtime/perf/budgets.py:101)

Fresh targeted verification on this workspace: `codinal-providers` passed 10/10; `codinal-runtime` passed 110/112 with 2 ignored; Python hot-path/outbound tests passed 8/8. An earlier runtime run had one missing-fixture/path failure that did not reproduce on rerun. These results validate compilation and existing contracts only; they do not validate provider latency or cache behavior.

### Provider cache constraints that shape the design

- **OpenAI:** cache reuse requires an identical prefix, so static instructions, tools, schemas, and examples belong first; changing user/tool content belongs later. The current guide exposes `cached_tokens`, supports cache-key routing, and documents a minimum cacheable prefix for current models. Do not pad Codinal’s small system prompt just to cross the threshold; include only genuinely stable tools/context in the cacheable prefix. [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)
- **Anthropic:** explicit `cache_control` breakpoints and `cache_read_input_tokens`/`cache_creation_input_tokens` are part of the Messages API contract; a breakpoint on changing content destroys reuse. The TTL and minimum prefix are model-specific, so Codinal should make retention a provider capability rather than a universal boolean. [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- **Gemini:** implicit caching is model/API-dependent; explicit caches are created through the GenerateContent caching API and carry storage/TTL economics. Treat Gemini context-cache IDs and token usage as provider-specific fields, not as the same counter used for Anthropic/OpenAI. [Gemini context caching](https://ai.google.dev/gemini-api/docs/generate-content/caching) · [Gemini caching API](https://ai.google.dev/gemini-api/docs/caching)

The practical layout is: stable policy + deterministic tool schemas + stable project instructions → provider cache boundary → current user request + changing tool results + timestamps. Codinal already appends dynamic context to an outbound copy of the last user message; the missing pieces are provider controls, deterministic prefix hashing, and usage/cost telemetry.

## Evidence table

| Dimension | Pi | Synara | Codinal | Verdict |
|---|---|---|---|---|
| Architecture | Typed TypeScript/Bun monorepo: `pi-ai`, agent core, coding-agent, TUI, protocol/client/server packages. | Multi-provider desktop orchestration shell: React/Vite browser, Node WebSocket/HTTP server, queue-backed workers, adapters, Electron; Pi is one direct SDK adapter. | Native Rust/GPUI host + Python sidecar over authenticated loopback; explicit policy/tool/sandbox/worktree/storage boundaries. | **Same only at Synara’s embedded Pi runtime boundary. Not the same system.** |
| Cache hit rate | `[Fact]` Provider-aware retention/session affinity and usage (`cacheRead`, `cacheWrite`) exist; cache-waste instrumentation exists. `[Unknown]` No real workload hit-rate result in the inspected source. | `[Fact]` Reads Pi `cacheRead` and exposes cached-input telemetry. `[Fact]` UI/transport caches exist. `[Inference]` No independent Pi cache policy is configured in `PiAdapter`; actual behavior is delegated to resolved Pi. | `[Fact]` No first-class prompt-cache fields/controls in canonical contract or inspected Anthropic request path. Client, PDF, semantic, and UI/outbound caches are different layers. | Pi has the strongest built-in cache observability/control. Synara inherits it narrowly. Codinal currently cannot prove provider cache hits. |
| Latency | `[Fact]` In-process SDK/session/streaming architecture is visible. `[Unknown]` No first-token benchmark found. | `[Fact]` Adds browser/WebSocket/server/event translation around provider runtime; compression and cursor resume reduce transport/replay work. `[Unknown]` No end-to-end first-token benchmark. | `[Fact]` Docs record observed cold `build_services` ~0.3s and outbound transform ~5 ms for 1,000 messages on dev macOS; docs explicitly exclude first-model-token latency. | No fair latency winner can be stated. The paths measure different things. |
| Runtime performance | `[Fact]` Monorepo has package-level tests/builds; no cross-system runtime benchmark found. | `[Fact]` More orchestration layers and a broad React/Electron dependency surface; Pi import is lazy. `[Inference]` More process/event boundaries can add overhead. | `[Fact]` Hard budgets exist for tool I/O, search, index, engine, sandbox, MCP, storage; perf tests run in CI. | Codinal has the clearest explicit resource-budget discipline; measured model/runtime comparison remains unknown. |
| Bundle size | `[Fact]` Coding-agent can compile a Bun binary; no built binary size was measured here. | `[Fact]` Repository documents web static bundle sizes: 18.09 MB identity, 4.44 MB gzip, 3.63 MB Brotli. Electron desktop packaging is separate. | `[Measured]` Current workspace artifact: `Codinal-0.1.0-macos-arm64.zip` 9.6M disk / 9.5M listing; `Codinal.app` 24M disk. | Not apples-to-apples. Synara’s documented web bundle is smaller than its full desktop product, while Codinal’s value is a packaged native artifact. Pi needs a comparable built artifact measurement. |
| Code cleanliness | `[Inference]` Clear package boundaries and typed provider compatibility; broad provider-specific code is necessarily complex. | `[Fact]` Generic adapter contract plus provider-specific adapters; PiAdapter is a substantial translation/state-lifecycle boundary. `[Inference]` Clean layering, but higher architectural surface area. | `[Fact]` Explicit module boundaries and centralized policy/permission paths; Rust/Python split increases coordination surface. | Subjective and team-specific. Structural evidence favors Pi for focused agent-core reuse, Codinal for explicit safety boundaries, Synara for integration breadth. |
| Cache cost | `[Fact]` Usage cost tracks input/output/cache-read/cache-write; cache-waste computes extra dollars versus a cache hit. | `[Fact]` Pi model metadata includes cache-read/write costs; Pi usage is normalized. `[Unknown]` No Synara-owned cache-waste calculation found. | `[Fact]` Provider contract has no normalized usage/cost/cache fields. | Pi owns the most complete cost model; Synara displays/forwards a subset; Codinal needs a contract extension. |
| System-prompt/token overhead | `[Fact]` Default prompt includes role, selected tool descriptions, guidelines, Pi docs paths, optional project context, skills, and cwd; skills are name/description/location entries. No token count was measured. | `[Fact]` Synara prepends a harness policy to Pi prompt text and may add attachments/images/gateway tools; Pi then builds its own system prompt. No token count was measured. | `[Fact]` Instructions plus untrusted-output guidance enter a system message; dynamic context is appended ephemerally to the last user message; outbound history is bounded. No token count was measured. | Synara has the largest likely orchestration/prompt composition surface, but “largest” is an inference until tokenized under fixed scenarios. |

## Direct answers by requested comparison

### Cache hit rate

Pi is the reference implementation here. It exposes the controls needed to make cache reuse deliberate: stable session ids, retention, provider-specific cache markers/keys, session-affinity headers, and parsed cache-read/write usage. It still does not provide a universal hit-rate guarantee; providers, model support, prompt-prefix stability, idle TTL, compaction, and routing determine the result.

Synara inherits Pi’s provider cache behavior only through the embedded Pi session. Its visible adapter reads `cacheRead` and pricing but does not itself forward explicit cache settings. Synara’s WebSocket compression, cursor replay, static asset caching, and normalized UI state should not be counted as model cache hits.

Codinal currently has no reliable way to answer “what fraction of prompt input was served from provider cache?” Its provider-neutral `AssistantTurn` can carry arbitrary `extras`, but the contract does not define a normalized cache usage/cost schema. That is an implementation gap, not evidence of zero provider caching in every backend.

### Latency and runtime performance

Pi’s direct in-process session path has fewer application-level boundaries than Synara’s browser → WebSocket → Node orchestration → adapter path. **Inference:** for an otherwise identical provider call, Synara may add orchestration latency, although lazy Pi loading avoids paying the Pi dependency cost before Pi is used. No source-backed first-token or p50/p95 result proves the size of that effect.

Codinal’s documented local baselines cover sidecar composition, repository search, and message shaping—not provider network latency or first model token. They are useful local budgets, not a comparison against Pi or Synara.

### Bundle size

The available numbers are deliberately not presented as a winner. Synara documents its compressed web assets, not a complete Electron installer. Codinal has a measured current local macOS artifact. Pi’s repository describes a compiled Bun binary but no comparable artifact was built during this research. A fair result requires building all three release targets on the same machine and recording identical size categories.

### Code cleanliness

This is a maintainability assessment, not a benchmark. Pi’s decomposition is clean for embedding: provider API, agent core, coding-agent session, and TUI are independently named packages. Synara’s generic adapter facade is a sensible integration seam, but its Pi adapter must translate sessions, events, approvals, prompts, attachments, tools, usage, and compaction into Synara’s provider protocol. Codinal keeps consequential execution behind explicit policy and sandbox boundaries, at the cost of a Rust/Python coordination seam.

### Cache cost

Pi can compute cache-waste dollars from usage and model pricing. Synara receives Pi’s cache-read telemetry and has model cache pricing, but the inspected adapter does not expose Pi’s full cache-waste analysis. Codinal cannot calculate a trustworthy normalized cache cost until providers return cache-read/write usage and pricing through the canonical contract.

### System prompt and token overhead

Pi’s default prompt is relatively inspectable: tools, guidelines, documentation paths, optional project-context files, skills, and working directory. Pi also has compaction defaults and skill listing, which are explicit sources of tokens.

Synara adds harness-policy text to provider prompt text and can add attachment text/images and gateway tools before passing the request to Pi. Pi then adds its own system prompt. **Inference:** Synara’s combined prompt/tool surface is likely larger than a bare Pi session, but the repository contains no fixed-scenario token counts.

Codinal’s system prompt is explicit and safety-oriented, with a static untrusted-output fence. Its dynamic context is added only to an outbound copy of the last user message, not persisted into the canonical transcript. This can reduce history pollution, but any changing dynamic suffix can reduce exact prefix reuse; the effect is unknown without provider traces.

## Key risks and unknowns

1. **Version drift.** The comparison is Pi 0.83.0 source versus Synara’s locked Pi 0.81.1. Cache behavior, APIs, and model catalogs may differ between those versions.
2. **No cache-hit benchmark.** None of the three repositories supplies an apples-to-apples live workload result for cache-hit rate, first-token latency, or cache-cost savings.
3. **Cache-layer confusion.** Synara’s compressed frames, cursor replay, UI state reuse, and static asset caching improve transport/UI behavior but do not establish LLM prompt-cache reuse.
4. **Prompt instability.** Synara harness policy, attachments, gateway tools, Pi skills, and Codinal dynamic context can change request shape. Exact token and cache-prefix effects are unmeasured.
5. **Bundle non-equivalence.** Synara’s 18.09/4.44/3.63 MB figures are web assets; Codinal’s 9.5M zip/24M app figures are a local native release artifact; Pi was not built into a comparable artifact.
6. **Security model divergence.** Synara’s Pi service documentation explicitly calls Pi an unopinionated harness and says Synara does not add permissions or plan-mode semantics on top of it. Codinal makes policy, approval, root scope, Seatbelt, and worktree isolation central runtime boundaries. Do not use Pi/Synara cache or UX similarities as evidence of execution-safety parity. [Synara Pi service note](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/apps/server/src/provider/Services/PiAdapter.ts#L1-L20) · [Codinal sandbox boundary](https://github.com/pongsathonkheereekaew/Codinal/blob/86fd4c8445e3aa151f42c177d2554725cc61ff87/runtime/README.md#L44-L59)

## Prioritized recommendations and measurable acceptance criteria

1. **P0 — Add a first-class provider usage/cache contract to Codinal.**

   Extend the provider result/turn usage model with `input_tokens`, `cache_read_tokens`, `cache_write_tokens`, `output_tokens`, provider/model, and a cost breakdown; add explicit optional `cache_retention` and stable session-affinity/cache-key inputs. Preserve “unknown” when a provider does not report a field.

   Acceptance: conformance tests cover OpenAI, Anthropic, Gemini, and Ollama behavior; every provider either returns a verified field or `unknown`; a report computes `cache_read / (input + cache_read + cache_write)` only when the provider supplies all required counters; no fabricated zeroes.

2. **P0 — Run one controlled, apples-to-apples benchmark before choosing an architecture.**

   Use the same repository fixture, prompt sequence, model, credentials, tool schemas, system prompt, and network region for bare Pi, Synara’s Pi path, and Codinal. Run cold and warm sessions with at least 30 turns per condition, repeat on at least three independent sessions, and capture provider usage, cache-read/write tokens, first-token latency, turn latency p50/p95, total cost, process CPU, and RSS.

   Acceptance: checked-in raw JSON plus a script that reproduces the summary; report confidence intervals or exact sample distributions; no “faster” or “higher hit rate” recommendation unless the difference and measurement conditions are shown.

3. **P1 — Port Pi’s cache-waste accounting and compaction discipline conceptually, not wholesale.**

   Reuse the ideas of cache-miss detection, missed-cost calculation, model-change/idle-time attribution, and no-cache-write standalone summaries while keeping Codinal’s provider and policy boundaries.

   Acceptance: unit tests reproduce synthetic miss/cost cases; a replay test proves compaction summaries do not create reusable-session cache writes; a live benchmark reports missed tokens and dollars alongside hit-rate counters.

4. **P1 — Keep Synara as an integration/reference option, not a Codinal core replacement.**

   If Codinal needs Pi compatibility, integrate the Pi SDK behind the existing provider contract and a clearly owned policy/tool boundary. Do not import Synara’s browser/server/Electron orchestration stack merely to obtain Pi’s agent loop.

   Acceptance: Pi-backed Codinal sessions pass provider conformance, approval, Seatbelt, root-scope, worktree, interruption, and audit tests; Pi is lazy-loaded; the existing local runtime remains the authority for consequential tool execution.

5. **P2 — Establish real prompt and bundle budgets.**

   Tokenize a fixed set of system prompt, tool schema, skill, project-context, harness-policy, attachment, and dynamic-context scenarios. Separately build the three release artifacts and record identity/compressed sizes, startup, first paint/listener, and first token.

   Acceptance: a report records token counts by component and p50/p95 startup/first-token metrics; each budget has a named enforcement/test location; artifact categories are comparable before any size claim is made.

## Decision

**Synara is essentially Pi only inside its Pi adapter; it is not essentially Codinal, and it is not a drop-in replacement for Codinal’s safety-bound local runtime.** For Codinal, the highest-value lessons are Pi’s provider cache contract, usage/cost accounting, cache-waste instrumentation, and compaction discipline. Synara is useful as a reference for multi-provider orchestration and UI transport, but adopting its full application architecture would add substantial process, dependency, and product surface without proving better model latency, cache hit rate, or total cost.

## UI parity addendum (2026-08-02)

### Question

Can Codinal’s pure-Rust/GPUI UI look and behave like Synara because both are local AI coding workspaces?

### Findings

**Visual parity: yes. Interaction parity: mostly yes for the shared core. Capability parity: not yet.** The overlap is an information architecture, not merely a backend swap:

| Synara surface | Codinal Rust/GPUI equivalent | Current truth |
|---|---|---|
| Left project/thread sidebar | GPUI navigation/task sidebar | Present; Rust mutation readiness can disable create/select actions |
| Center chat timeline + composer | GPUI conversation pane + composer | Present; current reducer already models streaming, receipts, reconnect, and approval state |
| Resizable right dock with tabs | GPUI context panel + tool workbench | Present as a related pattern; needs a unified tabbed projection if exact Synara-style dock parity is desired |
| Terminal | Native GPUI PTY panel | Present locally; runtime/control-plane terminal routes are still incomplete |
| Files/explorer | GPUI bounded workspace projection/file preview | Present read-only; richer editor/LSP is outside the current Rust cutover |
| Diff/review | GPUI read-only Git review + approval diff | Present in bounded form; write/apply/commit flows need runtime capability completion |
| Browser preview | GPUI browser action/panel entry point | Not equivalent yet; Codinal currently opens an external browser rather than embedding Synara’s browser surface |
| Split chats/side chat, worktrees, handoff | Future Rust projections and runtime commands | Product/UI can be drawn, but the underlying Rust routes and state contracts are incomplete or deferred |

Synara’s source confirms that its chat shell is a left sidebar plus a chat content shell, with a separately resizable right dock. Its right dock is not a cosmetic panel: it owns persistent per-thread pane state, tab selection, collapse/open state, and pane kinds including browser, diff, explorer, file, terminal, sidechat, Git, and pull request. [Synara chat shell](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/apps/web/src/routes/_chat.tsx#L553-L606) · [Synara pane state](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/apps/web/src/rightDockStore.logic.ts#L9-L58) · [Synara right dock](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/apps/web/src/components/chat/RightDock.tsx#L173-L359)

Codinal already has the same high-level visual grammar in Rust: the GPUI render path creates a left session sidebar, center conversation/composer, contextual approval/environment panel, and docked or overlaid tool workbench. [Codinal GPUI shell](/Users/pongsathonkheeereekaew/harness-flow/desktop/gpui/src/main.rs:3270) · [Codinal workbench state](/Users/pongsathonkheeereekaew/harness-flow/desktop/gpui/src/workbench.rs:19) · [Codinal side-panel tools](/Users/pongsathonkheeereekaew/harness-flow/desktop/gpui/src/side_panel.rs:13)

The important difference is that Codinal intentionally makes approval, readiness, reconnect, bounded transcript state, and receipt state first-class in the UI reducer. Copying Synara’s shapes without copying those state boundaries would produce buttons that look complete while backend routes remain unavailable. [Codinal workbench transitions](/Users/pongsathonkheeereekaew/harness-flow/desktop/gpui/src/workbench.rs:169) · [Codinal Rust capability table](/Users/pongsathonkheeereekaew/harness-flow/docs/evidence/runtime-truth/capability-table.md)

### Recommended Rust UI shape

1. Keep the Synara-like shell: left workspace/thread rail, center conversation/composer, right contextual dock, bottom/embedded terminal.
2. Implement a pure-Rust `UiProjection`/reducer that consumes typed runtime events and capability snapshots; GPUI only renders it and dispatches typed commands.
3. Make each dock tab capability-backed. If a route is unavailable, show a disabled/experimental state with the actual reason; never render a fake successful action.
4. Reuse the useful Synara interaction ideas—resizable panes, persistent active tabs, kept-alive terminal panes, split chat, and bounded lazy mounting—without importing its React/Electron stack.
5. Add exact visual comparison only after the Rust runtime contract is stable: screenshot fixtures for layout, reducer tests for every action, and end-to-end tests for approval, terminal, diff, browser, and reconnect states.

### Provenance and licensing

Synara’s pinned repository declares MIT, so code reuse may be legally possible with the required copyright/license notice. That does not make React/TypeScript components directly portable to GPUI, and it does not transfer Synara’s provider/runtime semantics. Prefer reimplementing the interaction contract and visual tokens in Codinal; if any Synara code or assets are copied, record provenance and preserve the MIT notice. [Synara LICENSE](https://github.com/Emanuele-web04/synara/blob/65f6684aa6ff88c8d57a9f11d541a54b41be1539/LICENSE#L267-L297)

### Decision update

Codinal should target **Synara-like UX, not a Synara clone**: adopt the three-zone workspace and dock behaviors, while keeping Codinal’s Rust-owned execution policy, approval boundary, sandbox/worktree rules, audit receipts, and capability truth. This gives visual/interaction convergence without making the Rust UI promise features its runtime cannot yet execute.
