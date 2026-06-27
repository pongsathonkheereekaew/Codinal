# claude-workflow

My consolidated Claude Code setup — one coding spine, one memory, lean token use, no context loss across projects. Portable to any new machine.

> **PRIVATE repo** — bundles personal skills (insurance, nuiny, easby, graphify).

## What's inside

| Path | Role |
|------|------|
| `claude/CLAUDE.md` | global **router** — which tool per job + quality floor + token/memory policy |
| `claude/RTK.md` | rtk token-killer reference (imported by CLAUDE.md) |
| `claude/settings.template.json` | Claude Code config (plugins, hooks, ECC-minimal env). `__HOME__` → real path on install |
| `claude/scripts/` | `ctx-guard.sh` (80% auto-handoff), `sessionstart-resume.sh` (goal-loop resume), `lowfat-rtk-router.sh` (bash token compress), `statusline.sh` |
| `claude/commands/` | `/ponytail-review`, `/ponytail-audit` (on-demand minimalism) |
| `claude/templates/GOAL.md` | goal-loop arming template |
| `claude/projects/-/memory/` | curated memory (Obsidian-compatible `[[links]]`) — the durable-facts layer |
| `claude/agents/` | 57 curated dev/design agents (pruned from 210) |
| `claude/skills/` | bundled skills incl. ui-ux-pro-max + macos-design |
| `agents-keep.txt` + `prune-agents.sh` | reproduce the 210→57 prune if you install a full agent pack |

## The stack (winner per job)

memory → **claude-mem** · coding spine → **superpowers** · deep review → **/ecc:review-pr** · spec/issues/handoff → **matt pocock** · web design → **ui-ux-pro-max** · native mac → **macos-design** · code-trim → **ponytail** (on-demand) · token → **rtk + lowfat + caveman** · quality overlay → **karpathy-guidelines** · docs → **ecc context7**.
Disabled on purpose: claude-code-harness, claudeclaw, ECC heavy hooks. Full rationale in `claude/projects/-/memory/workflow-stack.md`.

## Install on a new machine

```bash
git clone <your-remote>/claude-workflow.git
cd claude-workflow
./install.sh                 # copies into ~/.claude, backs up anything it overwrites
# then follow MANIFEST.md: brew install rtk lowfat jq node + /plugin installs
```

`install.sh` is idempotent and backs up existing files to `*.bak-<timestamp>`. See **MANIFEST.md** for the CLI + plugin steps it can't do itself.

## Update the repo from this machine

```bash
cp -R ~/.claude/CLAUDE.md ~/.claude/RTK.md claude/
cp -R ~/.claude/scripts/. claude/scripts/   # (statusline.sh too)
cp -R ~/.claude/commands/. ~/.claude/templates/. ~/.claude/projects/-/memory/. claude/...   # mirror back
sed "s|$HOME|__HOME__|g" ~/.claude/settings.json > claude/settings.template.json
git add -A && git commit -m "sync from $(hostname)"
```

## Goal-loop (no context loss on long tasks)

1. `cp ~/.claude/templates/GOAL.md ./GOAL.md` and fill the objective
2. work normally → at ≥80% context the Stop hook forces `/handoff` (writes GOAL.md + HANDOFF.md)
3. open a **fresh** `claude` (not `-c`) → SessionStart hook re-injects state → type `continue`
