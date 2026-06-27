Be extremely concise. No yapping, no conversational filler.

If the code is self-explanatory, don't explain it.

Provide only the modified code snippets, never the full file.

If you need more info, ask briefly.

If a file is longer than 100 lines, summarize its structure before reading the full content.

When suggesting code changes, output only the specific lines to replace — never the entire file.

# Routing — which tool per job
- Plan/build feature → superpowers: brainstorming → writing-plans → executing-plans
- TDD / write tests → superpowers: test-driven-development
- Debug → superpowers: systematic-debugging
- Multi-agent fan-out → superpowers: subagent-driven-development / dispatching-parallel-agents
- Worktrees / finish branch → superpowers: using-git-worktrees / finishing-a-development-branch
- Deep code review → /ecc:review-pr (fans out to lang + security + silent-failure)  | quick → superpowers: requesting-code-review
- Spec/PRD → /to-prd   • plan → issues → /to-issues   • compact convo → /handoff   • higher context → /zoom-out
- Web UI → ui-ux-pro-max   • native macOS → macos-design   • design-system extract → Figma MCP   • a11y audit → ecc a11y-architect
- Trim over-engineered diff → /ponytail-review  (on demand only — never always-on)
- Library/API docs → ecc context7 MCP

# Quality floor (always on)
karpathy-guidelines: surgical changes, surface assumptions, define verifiable success criteria.
**YOU MUST NOT declare done** without superpowers: verification-before-completion (prove behavior, don't assume).
"Minimal" (ponytail) only ABOVE a passing test floor — minimal AND correct, never minimal-but-broken.

# Memory (single source of truth = claude-mem)
- claude-mem auto-captures + auto-recalls each session. Manual recall → mem-search skill.
- Durable facts/preferences → curated MEMORY.md at ~/.claude/projects/-/memory/ (one fact per file, indexed in MEMORY.md).
- Per-project facts/constraints → that project's ./CLAUDE.md.
- **IMPORTANT: claude-mem is the ONLY memory system.** Never re-introduce a second (no harness-mem, no openwolf cerebrum, no ECC observe).

# Goal-loop (long tasks, no context loss)
- Arm: put a GOAL.md in the project (template: ~/.claude/templates/GOAL.md), or touch ~/.claude/.loop-active.
- At ≥80% context the ctx-guard Stop hook forces /handoff → writes GOAL.md progress + HANDOFF.md.
- Rotate: open a FRESH `claude` session (not -c). SessionStart hook re-injects GOAL.md + HANDOFF.md + claude-mem recall. Type "continue".

# Token policy
- rtk + lowfat (bash stdout) and caveman (prose) stay on. ECC strategic-compact nudges /compact.
- Don't echo large files; summarize anything >100 lines. Prefer Explore/subagents for broad reads (return conclusions, not dumps).

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
