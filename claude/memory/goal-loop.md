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
**Trigger:** Stop hook ~/.claude/scripts/ctx-guard.sh reads `.context_window.used_percentage`; at ≥80% it blocks stop once, forcing /handoff → append progress to GOAL.md + write HANDOFF.md.
**Resume:** open a FRESH `claude` session (NOT `claude -c` — that keeps the full context and defeats the reset). SessionStart hook ~/.claude/scripts/sessionstart-resume.sh clears the fired-marker and re-injects GOAL.md + HANDOFF.md; claude-mem adds episodic recall. Type "continue".

**Why:** a Claude session can't spawn its own successor natively, so full-auto needs a daemon; semi-auto (user rotates) is reliable, zero runaway cost, and the user explicitly chose to stay in control. Gating on GOAL.md/.loop-active keeps normal sessions from getting surprise handoffs at 80%.

**How to apply:** if ctx-guard never fires, verify the Stop hook payload actually contains `context_window.used_percentage` (newer Claude Code); if absent, switch trigger to a transcript-size estimate or PreCompact. Full-auto upgrade path: claudeclaw heartbeat or a cron routine to spawn the fresh session. See [[workflow-stack]].

**Loop hygiene** (distilled from cobusgreyling/loop-engineering, 2026-06-27 — discipline only, no tooling adopted; their CLIs/LOOP.md/STATE.md conventions skipped as overlap):
- **Attempt-cap:** GOAL.md carries `Attempts: N/3`; escalate to human at 3 → kills infinite-fix spirals across rotations.
- **State rot:** prune done/merged items every handoff + stamp `Last run`, so a resumed session never re-acts on finished steps.
- **Verifier theater:** verification-before-completion must actually RUN tests/lint and show output; default stance = find reasons to REJECT.
- **Human-gate / denylist:** never auto-touch `.env*`/secrets/auth/payments/billing/migrations/prod; stop + ask on >10-file changes, dependency upgrades, infra, PII. (Lives in the GOAL.md template.)
- **Comprehension debt:** read what the loop produced — build like the engineer who intends to stay.
