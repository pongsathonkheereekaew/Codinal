# Comet -> Codinal adoption review

Research date: 2026-08-01
Upstream snapshot: [`zeronsh/comet@fb22e269`](https://github.com/zeronsh/comet/tree/fb22e269ac57331ee7aa4a9673530acf3299a886)

## Bottom line

**Yes: adopt Comet's interaction grammar and selected Rust/GPUI patterns. Do not fork Comet or reproduce its product wholesale.** The highest-value transfer is a dense native coding workbench: session rail, stable streaming transcript, stateful composer, terminal below, and review/diff pane beside the conversation. Codinal should keep its stricter Rust runtime boundary, durable approval model, receipts, provider routing, and local-first ownership rules.

Comet is an especially relevant reference because its device-side application is Rust, its viewport is GPUI, and its engine/UI boundary uses the same typed RPC contract across attached frontends. Its own architecture explicitly separates the engine backend from the UI viewport. [README](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/README.md) · [architecture, lines 16-65](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/ARCHITECTURE.md#L16-L65)

Visual references: [main screenshot](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/docs/screenshot.png) · [sessions + terminal + changes layout](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/docs/reference/original-comet-2-changes.png)

## Adopt

1. **The workbench layout, reinterpreted for Codinal.** Use a compact session rail, conversation center, resizable terminal below, and contextual review pane on the right. In Codinal, that right pane should unify pending approval, exact diff, source hashes, receipt, and recovery status rather than being only a Git diff viewer. Comet already models terminal/changes visibility per session and keeps panel state separate from global settings. [shell panel state](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/shell.rs#L169-L210) · [changes pane](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/changes.rs)

2. **A single composer that morphs with turn state.** Adopt `Send -> Steer -> Stop` behavior and the combined provider/model/effort control near the send action. For Codinal's first vertical slice, map this to `Run -> Interrupt`, make unavailable actions visibly disabled with a readiness reason, and change provider/model/effort only for the next turn. Comet represents send modes explicitly and keeps composer events typed. [composer modes](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/composer.rs#L307-L321) · [composer state/events](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/composer.rs#L1572-L1637) · [model/effort picker](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/pickers.rs#L1900-L2020)

3. **Transcript performance and continuity.** Adopt block-granularity virtualized rows with stable IDs, optimistic user echoes that reconcile by ID, per-row layout caching, coalesced stream updates, scroll-anchor preservation, and a user-interruptible follow-bottom spring. These address the production-smoothness gap already noted in Codinal's comparison evidence. [transcript design](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/ARCHITECTURE.md#L168-L193) · [stick spring](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/transcript.rs#L105-L190) · [row model](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/transcript.rs#L192-L270) · [Codinal gap](../evidence/phase49-gpui-vs-comet.md)

4. **Pure shared view derivations plus thin GPUI glue.** Comet keeps sorting, attention ranking, stale-status gating, grouping, and boot gating in `proto::view`, while `AppState` uses testable reducer methods and GPUI subscriptions layer on top. Codinal should use the same separation for runtime readiness, session state, approval state, event replay, and provider capability projections. [shared view contract](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/proto/src/view.rs#L1-L180) · [AppState reducers](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/state.rs#L288-L492)

5. **Sequence-based replay and exclusive ownership as implementation references.** Comet appends sequenced events, replays after a cursor, tolerates a torn final journal line, and acquires a lifetime data-directory lock before opening stores. These patterns directly support Codinal's locked reconnect and writer-ownership decisions. Reimplement against Codinal's SQLite receipt/event contracts rather than copying the JSONL store. [run journal replay](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/engine/src/run_journal.rs#L121-L185) · [instance lock](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/engine/src/instance_lock.rs#L1-L88)

## Adapt

1. **Typed UI/engine protocol, but preserve Codinal's process topology.** Comet can embed its engine or attach to a daemon through one RPC abstraction. Codinal has decided that GPUI and the Rust runtime remain separate processes over authenticated loopback HTTP/WebSocket. Keep that decision; adopt only the shared typed request/response/event types and transport-independent view projections. [Comet bootstrap abstraction](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/state.rs#L169-L285) · [Codinal cutover SSOT](../plan/rust-native-runtime-cutover.md)

2. **Review pane as an approval transaction, not passive diff chrome.** Reuse Comet's virtualized file/hunk/line presentation, collapse behavior, and background highlighting, but bind the rendered diff to Codinal's `approval_id`, patch digest, source hashes, workspace boundary result, and immutable receipt. Comet's pane handles incremental diff frames and fold state but does not define Codinal's approval invariants. [diff data and phases](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/changes.rs#L58-L114) · [incremental diff frame](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/changes.rs#L346-L411)

3. **Visual language, not pixel cloning.** Adapt the restrained monochrome hierarchy, hairline separators, compact chips, pane resizing, sparse meaningful motion, and reduced-motion support. Give Codinal its own accent and safety semantics: neutral for information, amber for pay-per-use/fallback, red for consequential or failed readiness, green only for verified completion. Comet is intentionally always-dark and uses custom frost/edge-fade effects; Codinal should remain native to macOS appearance and accessibility expectations. [theme](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/theme.rs) · [motion catalog](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/ARCHITECTURE.md#L205-L213)

4. **Catalog UX, not harness semantics.** Comet's picker groups harness, model, and reasoning controls. Codinal should render OpenCode Go and DeepSeek profiles through its provider capability catalog, showing only probed model/effort combinations and clearly labeling DeepSeek pay-per-use and auto-fallback budgets. Do not import Comet's Claude/Codex/Cursor account model. [picker state](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/pickers.rs#L49-L112) · [harness/model popover](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/pickers.rs#L1900-L2020)

## Avoid

1. **Do not adopt Loro, Cloudflare Durable Objects, multi-device rooms, or the remote-control command plane now.** They solve Comet's cross-device product and would add a new source of truth, sync conflict model, cloud dependency, and authorization boundary to Codinal's local Rust vertical slice. [Comet topology/data model](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/ARCHITECTURE.md#L16-L123)

2. **Do not adopt Comet's crash auto-resume behavior.** Comet can pick a stale run back up; Codinal explicitly requires a streaming turn found after restart to end as `interrupted`, with retry creating a new linked turn. Automatic replay could duplicate pay-per-use requests or side effects. [Comet recovery description](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/engine/src/sessions.rs#L453-L571)

3. **Do not take the custom GPUI fork by default.** Comet pins `wingleeio/zed` for line-wrap changes and a custom `EdgeFade` primitive. That creates a long-lived rebase/security burden. Codinal should first implement the UX with its current GPUI dependency; accept a fork only after a measured blocker, a minimal patch, and an upstreaming plan. [dependency pin and fork rationale](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/Cargo.toml#L41-L54)

4. **Do not copy Comet's large component files as architecture.** `shell.rs`, `composer.rs`, and `transcript.rs` concentrate many responsibilities. Adopt their behavior contracts while splitting Codinal into state/reducers, protocol adapters, and small pane components. Exact upstream paths: [`shell.rs`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/shell.rs), [`composer.rs`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/composer.rs), [`transcript.rs`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/transcript.rs).

5. **Do not copy branding or third-party assets blindly.** The repository is MIT, but its icon module separately identifies most glyphs as Solar Icons under CC BY 4.0; Claude/OpenAI/Cursor marks have trademark concerns, and bundled Geist font files have no adjacent license file in this snapshot. Use Codinal-owned branding and an already-approved icon/font source, or audit and preserve every upstream notice before importing. [root MIT license](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/LICENSE) · [icon provenance](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/icons.rs#L1-L15) · [asset tree](https://github.com/zeronsh/comet/tree/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/assets)

## Licensing constraints

- Comet's original code is MIT. Copying substantial code requires retaining the copyright and MIT permission notice. Prefer clean reimplementation of behavior unless a component is truly cheaper to vendor. [LICENSE](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/LICENSE#L1-L20)
- Solar Icons are called out by Comet as CC BY 4.0 and require attribution; the root MIT license does not replace that asset license. [icons.rs](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/icons.rs#L1-L15)
- Provider/company marks should not be treated as generic MIT UI assets. Use official marks under their applicable brand terms or Codinal's own neutral provider glyphs.
- The custom GPUI dependency is a Git revision of a third-party fork, not Comet-owned UI code. Review the fork's own license and patch delta independently before any reuse. [Cargo dependency](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/Cargo.toml#L41-L54)

## Recommended Codinal sequence

1. Refactor GPUI state into pure projections/reducers and pane-specific entities while keeping the current typed control-plane client.
2. Ship the composer state machine plus provider/model/effort control and explicit disabled readiness reasons.
3. Add the virtualized stable-row transcript, cursor replay, optimistic echo reconciliation, and measured scroll/typing budgets.
4. Replace the current approval display with the review transaction pane: diff, hashes, boundary result, decision, and receipt in one surface.
5. Add terminal and wider Git review polish only after the Rust execution vertical slice passes its safety and recovery gates.

## Exact upstream source map

| Concern | Source |
|---|---|
| Product and architecture | [`README.md`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/README.md), [`ARCHITECTURE.md`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/ARCHITECTURE.md) |
| Root UI state and reducers | [`crates/ui/src/state.rs`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/state.rs) |
| Shell/pane composition | [`crates/ui/src/shell.rs`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/shell.rs) |
| Streaming transcript | [`crates/ui/src/transcript.rs`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/transcript.rs), [`rail.rs`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/rail.rs) |
| Composer and configuration | [`composer.rs`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/composer.rs), [`pickers.rs`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/pickers.rs) |
| Diff/review rendering | [`crates/ui/src/changes.rs`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/changes.rs) |
| Shared view model | [`crates/proto/src/view.rs`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/proto/src/view.rs) |
| Durable replay and ownership | [`run_journal.rs`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/engine/src/run_journal.rs), [`instance_lock.rs`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/engine/src/instance_lock.rs) |
| Theme, motion, and assets | [`theme.rs`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/theme.rs), [`motion.rs`](https://github.com/zeronsh/comet/blob/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/src/motion.rs), [`assets`](https://github.com/zeronsh/comet/tree/fb22e269ac57331ee7aa4a9673530acf3299a886/crates/ui/assets) |
