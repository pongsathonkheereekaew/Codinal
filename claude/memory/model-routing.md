---
name: model-routing
description: "Opus/Fable for planning+thinking (max effort), Sonnet for writing"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fe96aa50-cf94-4d29-80ab-25d38c5d1917
---

The model split the user wants: expensive model for REASONING, cheap for EXECUTION.

- Plan / think / debug → Opus (Fable 5 `claude-fable-5` when chosen), `CLAUDE_EFFORT=max`. Do the heavy thinking in Plan Mode.
- Write / execute code → Sonnet (via `opusplan`: the exec phase runs Sonnet).
- Configured in settings.json: `model=opusplan` + env `CLAUDE_EFFORT=max`.

**Why:** keeps reasoning quality high where it matters (planning) while cutting cost/latency on mechanical writing — chosen instead of a separate local cheap model (qwen was rejected). Stays in-family, no extra infra.

**How to apply:** for hard problems, enter Plan Mode (Opus, max effort) to think/design; exit to execute so Sonnet writes the code. See [[workflow-stack]] · [[goal-loop]].
