---
name: model-routing
description: "Opus/Fable for planning+thinking (max effort), Sonnet for writing"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fe96aa50-cf94-4d29-80ab-25d38c5d1917
---

The model split the user wants: expensive model for REASONING, cheap for EXECUTION.

- Plan / think / debug → Opus (Fable 5 `claude-fable-5` when chosen); raise effort to max ON-DEMAND (`/effort max` or "ultrathink") in Plan Mode.
- Write / execute code → Sonnet (via `opusplan`: the exec phase runs Sonnet), default effort.
- Configured in settings.json: `model=opusplan`, effort is DYNAMIC (env `CLAUDE_EFFORT` unset — no global pin).

**Correction (2026-06-27):** earlier pinned `CLAUDE_EFFORT=max` globally — it made EVERY turn (incl. trivial "ok"/"commit") think at max depth = noticeably slow, esp. on full Opus + a large session. Removed the pin → dynamic. Max effort is a per-task tool, not an always-on setting. Big sessions (>400k tokens) are slow regardless — rotate to fresh.

**Why:** keeps reasoning quality high where it matters (planning) while cutting cost/latency on mechanical writing — chosen instead of a separate local cheap model (qwen was rejected). Stays in-family, no extra infra.

**How to apply:** for hard problems, enter Plan Mode (Opus, max effort) to think/design; exit to execute so Sonnet writes the code. See [[workflow-stack]] · [[goal-loop]].
