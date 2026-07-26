# ADR 0003 — Durable bounded goals and evidence audits

Status: accepted

Date: 2026-07-26

## Context

Long-running coding work must survive application restart without turning a
goal into an unbounded autonomous loop. A completion label is not credible
unless every requirement maps to fresh observed evidence. Likewise, a blocked
label must describe a repeated impasse rather than one failed attempt.

Provider token-usage metadata is not portable across every supported model and
streaming SDK. Codinal therefore needs one deterministic accounting fallback
that remains enforceable for every provider.

## Decision

1. A goal belongs to one durable session and has one objective, one through
   twenty stable requirement IDs, a continuation instruction, and optional
   estimated-token and elapsed-time budgets.
2. Goal state is `active`, `exhausted`, `completed`, or `blocked`. Completion
   and blocking are terminal. Budget exhaustion stops new continuations but
   does not erase evidence or prevent a final audit.
3. Continuation is an explicit user action. It reuses the parent session's
   workspace, model, mode, policy, and conversation. A goal never creates,
   inherits, or widens authority.
4. A running continuation is persisted before turn start. Shutdown leaves that
   marker intact; startup first recovers the turn and then attaches one goal
   monitor. Each process-local turn has a stable ID and terminal receipt that
   bounds its outcome and message count, so a later turn cannot contaminate
   accounting. Exactly one terminal turn-evidence entry is recorded.
5. Token usage is a conservative deterministic estimate of newly persisted
   continuation messages: UTF-8 JSON bytes divided by four, rounded up. The UI
   labels it `est. tokens`. This model-agnostic counter is the enforced budget
   until every provider adapter supplies normalized trusted usage.
6. The evidence ledger is append-only while a goal is non-terminal. Passing
   verification evidence names one requirement. Blocker evidence is limited to
   one observation per continuation.
7. A `completed` audit must map every requirement to at least one passing
   verification evidence ID from the same goal. A `blocked` audit requires the
   same normalized blocker summary on the latest three consecutive
   continuations.
8. Goal payloads, evidence, mappings, budgets, and list sizes are bounded at
   both HTTP and model layers. Durable writes use optimistic version checks.

## Consequences

- Restart cannot duplicate continuation evidence or silently spend a new
  budget.
- Users can inspect why a goal is complete or blocked instead of trusting a
  status assertion.
- Estimated tokens are comparable and enforceable across providers but are not
  billing-grade usage. The UI and evidence must not present them as exact.
- Fully automatic unattended continuation remains out of scope; a future
  scheduler must preserve the same authority and audit boundaries.
