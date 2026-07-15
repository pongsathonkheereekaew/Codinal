---
name: obsidian-view-layer
description: "Obsidian is a read/graph view over the memory folder, not a 2nd memory system"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2cc48522-6636-4890-9c32-1aa0434da3e1
---

Obsidian was added as a read/graph VIEW over the curated durable memory folder `~/.agents/memory/` (Claude adapter may symlink `~/.claude/projects/-/memory` → same path). claude-mem stays the episodic capture/recall engine — Obsidian does NOT capture; it only visualizes/edits the durable facts that are already there.

The personal vault `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Easby Studios` (iCloud) is for human browsing only — never wire headless/hermes agents to it, because iCloud can evict files to dataless stubs and break agent reads.

**Why:** user asked "Obsidian for memory"; making it the *main* memory would replace automatic capture/recall with manual note-writing (or rebuild claude-mem via an Obsidian MCP = the 2nd-SSOT trap that caused earlier context loss). View-layer gives graph + manual curation PLUS automatic capture. The agent-memory folder is local disk → reliable for future hermes agents; iCloud is not.

**How to apply:** point the [[obsidian-vault]] skill + any agent memory ops at the local memory folder; keep Easby Studios as a separate human vault opened in the app. Never let Obsidian become a competing capture store — see [[memory-ssot]] · [[workflow-stack]].
