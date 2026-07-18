# Shared policy (all tools) — load first
@../.agents/AGENTS.md

# Claude-only adapter below

# Routing — prefer SSOT skills (~/.agents/skills); avoid dual Matt+Superpowers for the same job
- Unsure which flow → ask-matt
- Plan stress-test → grilling (+ domain-modeling in a real repo)
- Huge multi-session design → wayfinder
- Spec/PRD → to-spec   • tickets → to-tickets   • implement → implement (+ tdd)   • handoff → handoff
- TDD / write tests → tdd
- Hard debug → diagnosing-bugs
- Code review (two-axis) → code-review   • deep PR stack → /review-pr
- Create / optimize a skill → skill-creator   • skill writing principles → writing-great-skills
- Web UI → ui-ux-pro-max   • native macOS → macos-design   • Figma → Figma MCP   • a11y → a11y-architect agent
- Trim over-engineered diff → /ponytail-review (on demand only)
- Library/API docs → WebFetch official docs
- Do NOT install GSD whole pack / full Superpowers dump / ultra-review / context-mode into ~/.agents

# Isolation / done (same for all tools via AGENTS.md)
- Worktrees → using-git-worktrees   • finish branch → finishing-a-development-branch
- Done gate → verification-before-completion (fresh evidence before any success claim)

# Claude plugin only (orchestration — not duplicated into SSOT)
- Multi-agent fan-out → superpowers: subagent-driven-development / dispatching-parallel-agents

# Memory
- Episodic → claude-mem plugin (auto capture/recall). Manual recall → mem-search if available.
- Durable facts/preferences → `~/.agents/memory/` (also linked at `~/.claude/projects/-/memory/`).
- Per-project constraints → that project's `./CLAUDE.md` or `./AGENTS.md`.
- **claude-mem is the only episodic memory.** Never add a second auto-capture stack.

# Token / stdout (if installed)
- Prefer `rtk` / `lowfat` for high-stdout shell; use `/compact` when the convo bloats.

# Delegation
- Broad unfamiliar reads (>~3 files) → Explore subagent; return conclusions, not dumps.
- Independent sub-tasks → dispatch concurrently in one message.
