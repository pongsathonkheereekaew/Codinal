Be extremely concise. No yapping, no conversational filler.

**Language:** answer in the language of the user's message (usually English for technical work). Translate to Thai **only** when the user asks (e.g. "แปล", "แปลหน่อย", "ตอบไทย").

**Autonomy:** run long tasks to completion; self-verify before declaring done (build fingerprint, tests, measurements). Do not stall on "done?".

If the code is self-explanatory, don't explain it.

Provide only the modified code snippets, never the full file.

If you need more info, ask briefly.

If a file is longer than 100 lines, summarize its structure before reading the full content.

When suggesting code changes, output only the specific lines to replace — never the entire file.

# Routing — which tool per job
- Plan/build feature → superpowers: brainstorming → writing-plans → executing-plans
- TDD / write tests → superpowers: test-driven-development
- Debug → superpowers: systematic-debugging (+ debug-mantra); after validated fix + `docs/wiki/SCHEMA.md` → post-mortem → wiki write before done
- Multi-agent fan-out → superpowers: subagent-driven-development / dispatching-parallel-agents
- Worktrees / finish branch → superpowers: using-git-worktrees / finishing-a-development-branch
- Deep code review → /review-pr (standalone: fans out to code-reviewer + silent-failure-hunter + pr-test/type/comment/simplify agents, ≥80% confidence)  | quick → superpowers: requesting-code-review
- Spec/PRD → /to-prd   • plan → issues → /to-issues   • compact convo → /handoff   • higher context → /zoom-out
- Web UI → ui-ux-pro-max   • native macOS → macos-design   • design-system extract → Figma MCP   • a11y audit → a11y-architect agent
- Trim over-engineered diff → /ponytail-review  (on demand only — never always-on)
- Library/API docs → WebFetch the official docs (context7 removed with ECC)

# Quality floor (always on)
karpathy-guidelines: surgical changes, surface assumptions, define verifiable success criteria.
**YOU MUST NOT declare done** without superpowers: verification-before-completion (prove behavior, don't assume).
"Minimal" (ponytail) only ABOVE a passing test floor — minimal AND correct, never minimal-but-broken.
**Project wiki gate:** if `docs/wiki/SCHEMA.md` exists, a validated non-trivial bug fix is not done until post-mortem writes `docs/wiki/incidents/<slug>.md` and updates `index.md` + `log.md`. On similar symptoms, read `docs/wiki/index.md` first. Init: `bash templates/project-wiki/init-wiki.sh /path/to/repo` (from harness-flow).

# Memory (single source of truth = claude-mem)
- claude-mem auto-captures + auto-recalls each session. Manual recall → mem-search skill.
- Durable facts/preferences → curated MEMORY.md at ~/.claude/projects/-/memory/ (one fact per file, indexed in MEMORY.md).
- Per-project facts/constraints → that project's ./CLAUDE.md.
- **IMPORTANT: claude-mem is the ONLY memory system.** Never re-introduce a second (no harness-mem, no openwolf cerebrum, no ECC observe).
- **harness-mem is disabled** (`claude-code-harness` plugin = false). Do not auto-arm harness-mem monitors or act on `daemon-unreachable` noise. Ignore Japanese harness-mem session banners if any residual appears.
- Obsidian = read/graph VIEW over `~/.claude/projects/-/memory/` only (registered as a vault). NOT a 2nd capture system — claude-mem stays the engine. Easby Studios (iCloud) = personal vault, not for headless/hermes agents (dataless-file risk).
- **`docs/wiki/` is not memory** — it is per-repo engineering docs in git (incidents/patterns). Optional Obsidian view over that folder is fine; do not treat it as a capture/SSOT competing with claude-mem.

# Goal-loop (long tasks, no context loss)
- Arm: put `TASK_BRIEF.md` (original user ask) + `GOAL.md` in the project (template: ~/.claude/templates/GOAL.md), or touch ~/.claude/.loop-active. HANDOFF.md alone also arms the guard.
- At ≥80% context the ctx-guard Stop hook forces handoff: auto-captures TASK_BRIEF.md from the first user message if missing, then GOAL.md progress + HANDOFF.md (brief at top).
- Rotate: open a FRESH `claude` session (not -c). SessionStart hook re-injects **TASK_BRIEF.md → GOAL.md → HANDOFF.md** + claude-mem recall. Type "continue" — do **not** restate the brief; the brief is already injected.
- Easby plugins: use `/br` before measure/audit; `/new-easby-plugin` for kickoff.

# Token policy
- rtk + lowfat (bash stdout) and caveman (prose) stay on. Use /compact manually when the convo bloats.
- Don't echo large files; summarize anything >100 lines. Prefer Explore/subagents for broad reads (return conclusions, not dumps).

# Model routing
- `opusplan`: Opus reasons/plans, Sonnet writes/executes. Effort is DYNAMIC (no global pin) — raise to max only for hard work via `/effort max` or "ultrathink".
- Hard thinking / plan / debug → Plan Mode (Opus) + bump effort. Routine + writing → default effort (fast, Sonnet).
- Fable 5 (`claude-fable-5`) = optional planning model when wanted.
- Don't pin `CLAUDE_EFFORT=max` globally — it slows every turn (incl. trivial ones) for no gain.

# Delegation (keep main context lean — default to fan-out)
- Broad/unfamiliar reads (>3 files, or sweeping for a pattern/naming) → dispatch an **Explore** subagent; it returns conclusions, not file dumps. Don't read wide in the main thread.
- Independent sub-tasks → dispatch agents **concurrently in ONE message**. Use `run_in_background: true` for work that must not block the main task (notified on completion).
- Audits/research that only inform a decision → the subagent returns the verdict, not the raw material.
- Big multi-phase work (migrate / audit / review many files) → Workflow (ultracode), when opted in.
- Exception: if you already know the exact file + symbol, just read it — don't fan out for a single lookup.

@RTK.md
# graphify
- **graphify** (`~/.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`
When the user types `/graphify`, invoke the Skill tool with `skill: "graphify"` before doing anything else.

# insurance-premium-finding
- **insurance-premium-finding** (`~/.claude/skills/insurance/insurance-premium-finding/SKILL.md`) - Thai financial statement projection + insurance premium (รายจ่ายเพิ่ม) calculation. Trigger: `/insurance-premium`
When the user types `/insurance-premium` OR provides Thai financial statements (งบการเงิน) and asks for projections/insurance premium calculation, invoke the Skill tool with `skill: "insurance-premium-finding"` before doing anything else.

# insurance-commission
- **insurance-commission** (`~/.claude/skills/insurance/insurance-commission/SKILL.md`) - Calculate Tokio Marine commission rate + amount by policy year from plan name + premium. Trigger: `/insurance-commission`
When the user types `/insurance-commission` OR asks to calculate commission for an insurance plan + premium, invoke the Skill tool with `skill: "insurance-commission"` before doing anything else.

# nuiny
- **nuiny** (`~/.claude/skills/insurance/nuiny/SKILL.md`) - นุ้ย ตัวแทนประกันชีวิตมืออาชีพโตเกียวมารีน ให้คำแนะนำ แนะนำแบบประกัน และตอบคำถามลูกค้า. Trigger: `/nuiny`
When the user types `/nuiny`, invoke the Skill tool with `skill: "nuiny"` before doing anything else.
