---
name: memory-ssot
description: One durable memory folder + one episodic engine — never a second stack
metadata:
  node_type: memory
  type: feedback
---

**Durable facts (shared):** `~/.agents/memory/` — one fact per file, indexed in `MEMORY.md`.  
SSOT after install = CEDIA `memory/` → `./install.sh`. Load `MEMORY.md` then only relevant files — do not dump the folder every turn.

**Episodic (Claude-only):** claude-mem auto-capture/recall. Hooks/plugins stay under `~/.claude`. Not in this folder.

**Why:** previously ran 3 memory systems in parallel (claude-mem + harness-mem 7.3GB + ECC observe) → fragmented recall. One durable hub + one episodic engine fixed it.

**How to apply:** never enable a competing durable/second-brain capture system (harness-mem, openwolf cerebrum, ECC observe, etc.). Obsidian may *view* this folder — it is not a second capture SSOT. See [[workflow-stack]].
