---
name: project-wiki
description: Per-repo docs/wiki is engineering lessons in git — not a second memory SSOT
metadata:
  node_type: memory
  type: feedback
---

When a project has `docs/wiki/SCHEMA.md`, that folder holds durable bug-fix lessons (incidents, code-map, patterns) committed with the repo. Agents write there after validated non-trivial fixes (post-mortem skill). Query `docs/wiki/index.md` before rediscovering.

**Why:** Fable/Obsidian/llm_wiki stacks helped others by compiling knowledge into markdown — we want that for code/bugs without stacking another capture engine on claude-mem (see [[memory-ssot]]).

**How to apply:** init with `bash templates/project-wiki/init-wiki.sh /path/to/repo`. Obsidian may open `docs/wiki/` as a graph view only. Never treat project wiki as session memory; claude-mem stays the only memory system. See [[obsidian-view-layer]] · [[workflow-stack]].
