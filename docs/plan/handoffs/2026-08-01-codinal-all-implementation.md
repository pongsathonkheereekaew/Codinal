---
source: /tmp/handoff-codinal-all-implementation-2026-08-01.md
freshness: 2026-08-01
status: active
---

# Codinal full implementation intake

The operator handoff is the intake source for the Rust-native cutover. The
canonical implementation authority remains
`docs/plan/rust-native-runtime-cutover.md`; the accepted boundary decision is
`docs/decisions/0004-rust-only-runtime-and-harness-boundary.md`.

The delivery order is C0 read-only ownership, C1 writer/migration recovery,
C2a OpenCode Go execution, C2b DeepSeek budgeted fallback, C3 GPUI workbench,
C3b Rust-only release, C4a-c Harness Manager and durable multi-model workflow,
then C5 shell, Git/worktrees, and MCP through the same policy path.

Current implementation notes:

- C0-C1 are implemented with fresh focused Rust recovery coverage.
- C2a has the pinned provider, durable approvals, bounded `apply_patch`,
  receipts, interrupt, and Safety UI kernel; manual GPUI/live-provider smoke is
  still a gate, not an assumption. The adapter now sends the OpenCode user-agent
  required by the live edge path, and `scripts/smoke-opencode-go-runtime.sh`
  provides a Keychain-backed, process-only live runtime probe. The live Rust
  runtime route passed with a redacted credential on 2026-08-01; packaged GPUI
  Run/Interrupt/reconnect evidence remains pending.
- C2b has the independently parsed DeepSeek profile, opt-in pre-output
  fallback, and durable per-turn/daily reservations. Fresh deterministic
  provider/storage/runtime coverage is green; the capped live smoke remains a
  gate because no separately approved DeepSeek credential is present.
- C3 has the pure Rust GPUI workbench reducer/projection, native layout
  contract, accessibility labels, reduced-motion state, stream coalescing,
  bounded transcript, and deterministic snapshot tests; live macOS matrix
  evidence remains required.
- C3b has the Rust-only bundle SBOM generator, artifact audit, CI publication,
  and retired embedded-runtime notice. A fresh ad-hoc signed package build,
  audit, `otool` dependency inspection, and launch smoke are green;
  signed/notarized install, upgrade, and rollback evidence remains required.
- C4a-c is implemented in `crates/codinal-harness` with read-only inventory,
  ownership-aware plans, approval-bound atomic writes, rollback receipts, and
  durable Planner/Implementer/Reviewer state.
- C5 has the deny-by-default shell, Git/worktree, and MCP gateway with bounded
  execution, shared approval, interrupt, receipt, restart recovery, output
  limits/timeouts, and malformed-response rejection; the broader
  adversarial/live host suite remains required.
