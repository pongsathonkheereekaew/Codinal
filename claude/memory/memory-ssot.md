---
name: memory-ssot
description: claude-mem is the only memory system — never add a second
metadata: 
  node_type: memory
  type: feedback
  originSessionId: facadea4-6150-49fc-b019-43bee62266f9
---

claude-mem is the single source of truth for episodic memory (auto-capture + auto-recall). Curated durable facts live in this MEMORY.md folder. Per-project facts in project CLAUDE.md.

**Why:** the original setup ran 3 memory systems in parallel (claude-mem + harness-mem 7.3GB + ECC observe), triple-capturing every action into incompatible stores → wasted I/O + fragmented recall = felt like "context loss." Consolidating to one fixed it.

**How to apply:** never enable a competing memory/second-brain system (harness-mem, openwolf cerebrum, ECC continuous-learning observe, etc.). If a tool bundles its own memory, disable that part. See [[workflow-stack]].
