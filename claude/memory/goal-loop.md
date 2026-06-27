---
name: goal-loop
description: Semi-auto goal-loop with 80% context auto-handoff
metadata: 
  node_type: memory
  type: project
  originSessionId: facadea4-6150-49fc-b019-43bee62266f9
---

For long tasks that outrun one context window. Semi-auto (user rotates the session; everything else automated).

**Arm:** drop a GOAL.md in the project (template ~/.claude/templates/GOAL.md) or `touch ~/.claude/.loop-active`.
**Trigger:** Stop hook ~/.claude/scripts/ctx-guard.sh. The Stop payload has NO `context_window` field (verified 2026-06-27), so it reads `transcript_path` and sums recent `usage.input+cache` = current context tokens; fires once at `CTX_GUARD_TOKENS` (default 800000 ≈ 80% of Opus 4.8's 1M window), forcing /handoff → prune+append GOAL.md + write HANDOFF.md.
**Resume:** open a FRESH `claude` session (NOT `claude -c` — that keeps the full context and defeats the reset). SessionStart hook ~/.claude/scripts/sessionstart-resume.sh clears the fired-marker and re-injects GOAL.md + HANDOFF.md; claude-mem adds episodic recall. Type "continue".

**Why:** a Claude session can't spawn its own successor natively, so full-auto needs a daemon; semi-auto (user rotates) is reliable, zero runaway cost, and the user explicitly chose to stay in control. Gating on GOAL.md/.loop-active keeps normal sessions from getting surprise handoffs at 80%.

**How to apply:** tune `CTX_GUARD_TOKENS` to your model's window (e.g. 160000 for a 200k-context model; 800000 for Opus 1M). If it never fires, check the transcript actually carries `message.usage` and that a loop is armed (GOAL.md / `.loop-active`). Full-auto upgrade path: claudeclaw heartbeat or a cron routine to spawn the fresh session. See [[workflow-stack]].

**Loop hygiene** (distilled from cobusgreyling/loop-engineering, 2026-06-27 — discipline only, no tooling adopted; their CLIs/LOOP.md/STATE.md conventions skipped as overlap):
- **Attempt-cap:** GOAL.md carries `Attempts: N/3`; escalate to human at 3 → kills infinite-fix spirals across rotations.
- **State rot:** prune done/merged items every handoff + stamp `Last run`, so a resumed session never re-acts on finished steps.
- **Verifier theater:** verification-before-completion must actually RUN tests/lint and show output; default stance = find reasons to REJECT.
- **Human-gate / denylist:** never auto-touch `.env*`/secrets/auth/payments/billing/migrations/prod; stop + ask on >10-file changes, dependency upgrades, infra, PII. (Lives in the GOAL.md template.)
- **Comprehension debt:** read what the loop produced — build like the engineer who intends to stay.
