# Shared policy (all tools) — load first
@../.agents/AGENTS.md

# Claude-only adapter (do not restate AGENTS.md router / done loop)

# Claude plugin only (orchestration — not in SSOT)
- Multi-agent fan-out → superpowers: subagent-driven-development / dispatching-parallel-agents

# Memory (Claude-private episodic)
- Episodic → claude-mem plugin (auto capture/recall). Manual recall → mem-search if available.
- Durable facts/preferences → `~/.agents/memory/` (also linked at `~/.claude/projects/-/memory/`).
- Per-project constraints → that project's `./CLAUDE.md` or `./AGENTS.md`.
- **claude-mem is the only episodic memory.** Never add a second auto-capture stack.

# Token / stdout (if installed)
- Prefer `rtk` / `lowfat` for high-stdout shell; use `/compact` when the convo bloats.
- caveman stays on when the plugin is enabled.

# Delegation (Claude subagents)
- Broad unfamiliar reads (>~3 files) → Explore subagent; return conclusions, not dumps.
- Independent sub-tasks → dispatch concurrently in one message.
