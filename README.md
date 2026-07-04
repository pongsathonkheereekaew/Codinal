# easby-workflow

My consolidated agent setup — one coding spine, one memory, lean token use, no context loss across projects. Portable to any new machine, usable from **any tool** (Claude Code, Cursor, Codex).

## One setup, all tools

`~/.claude` is the single source of truth; other tools read from it (via native discovery or symlinks the installer creates):

| Layer | Source of truth | Claude Code | Cursor (IDE + CLI) | Codex |
|---|---|---|---|---|
| Skills | `~/.claude/skills/` | native | auto-discovers `~/.claude/skills` + `~/.codex/skills` | native (`~/.codex/skills`) |
| Subagents | `~/.claude/agents/` | native | auto-discovers `~/.claude/agents` | auto-discovers |
| Slash commands | `~/.claude/commands/` | native | symlink `~/.cursor/commands` → there (installer does it) | mirror to `~/.codex/prompts` if wanted |
| Global instructions | `claude/CLAUDE.md` → `~/.claude/CLAUDE.md` | native | no global file — per-project `AGENTS.md`/`CLAUDE.md` picked up; put durable prefs in Cursor User Rules | `~/.codex/AGENTS.md` |
| Memory | claude-mem (+ curated `~/.claude/projects/-/memory/`) | native | claude-mem MCP + curated files readable by any tool | curated files |

Rule of thumb: **add new skills/commands/agents under `~/.claude/` only** — every other tool picks them up. Don't fork per-tool copies.

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
| `hermes/` | **phone side** — Hermes Agent + Telegram bot (mobile coding bridge). See [`hermes/README.md`](hermes/README.md) |

## The stack (winner per job)

memory → **claude-mem** · coding spine → **superpowers** · deep review → **/ecc:review-pr** · spec/issues/handoff → **matt pocock** · web design → **ui-ux-pro-max** · native mac → **macos-design** · code-trim → **ponytail** (on-demand) · token → **rtk + lowfat + caveman** · quality overlay → **karpathy-guidelines** · docs → **ecc context7**.
Disabled on purpose: claude-code-harness, claudeclaw, ECC heavy hooks. Full rationale in `claude/projects/-/memory/workflow-stack.md`.

## Install on a new machine

```bash
git clone <your-remote>/easby-workflow.git
cd easby-workflow
./install.sh    # one command: files → ~/.claude, brew CLIs, AND plugins (headless)
```

**One command, no other repos to hunt down.** `install.sh` copies all files, then auto-installs the CLIs (`brew install rtk lowfat jq node`) and every plugin (`claude plugin install ...` — superpowers, caveman, claude-mem, karpathy, clangd-lsp) via the headless `claude plugin` CLI. Idempotent; backs up overwrites to `*.bak-<timestamp>`.

Not vendored on purpose: claude-mem (node app + DB), rtk/lowfat (compiled binaries), and the skill plugins stay as real installs so they keep getting **updates** — but install.sh pulls them for you, so it *feels* self-contained. See **MANIFEST.md** only if a step fails.

## Update the repo from this machine

```bash
cp -R ~/.claude/CLAUDE.md ~/.claude/RTK.md claude/
cp -R ~/.claude/scripts/. claude/scripts/   # (statusline.sh too)
cp -R ~/.claude/commands/. ~/.claude/templates/. ~/.claude/projects/-/memory/. claude/...   # mirror back
sed -e "s|$HOME|__HOME__|g" \
    -e 's|\("ANTHROPIC_AUTH_TOKEN"[^"]*\)"[^"]*"|\1"__ZAI_TOKEN__"|' \
    ~/.claude/settings.json > claude/settings.template.json   # never commit the real token
git add -A && git commit -m "sync from $(hostname)"
```

## Goal-loop (no context loss on long tasks)

1. `cp ~/.claude/templates/GOAL.md ./GOAL.md` and fill the objective
2. work normally → at ≥80% context the Stop hook forces `/handoff` (writes GOAL.md + HANDOFF.md)
3. open a **fresh** `claude` (not `-c`) → SessionStart hook re-injects state → type `continue`

## Full setup on a new machine (desk + phone)

**Prereqs (install first, by hand):** `git`, `node`, [Claude Code CLI](https://code.claude.com), [Hermes Agent](https://nousresearch.com) (`~/.local/bin/hermes`), **9router** running on `127.0.0.1:20128`, a Telegram bot token from [@BotFather](https://t.me/BotFather).

```bash
git clone git@github.com:pongsathonkheereekaew/easby-workflow.git
cd easby-workflow

# 1) desk side — claude code (CLAUDE.md, hooks, plugins, z.ai GLM routing)
./install.sh

# 2) phone side — hermes + telegram bot + launchd auto-start
cd hermes && TELEGRAM_BOT_TOKEN=<your_bot_token> ./install.sh && cd ..
#   (also prompts for z.ai ANTHROPIC_AUTH_TOKEN — same key as desk side)
```

That's it. Verify: `claude --version` works; `curl http://127.0.0.1:20128/dashboard` answers; in Telegram your bot responds; `hermes-handoff list` finds projects.

## Desk ↔ phone workflow (the whole point)

| Where | Tool | Why |
|---|---|---|
| **Desk** | `claude` directly in the project dir | full-power worker (z.ai GLM, opusplan, superpowers, TDD). Don't go through hermes at the desk — it's just a middleman there |
| **Phone** | Telegram → bot → hermes → (hermes resumes claude) | hermes exists only as the mobile bridge |
| **Cross** | `/handoff` then `continue` | same claude session ID continues on both ends |

```
DESK:   cd ~/Downloads/AURIC && claude          # work here
LEAVE:  /handoff                                 # writes GOAL.md + HANDOFF.md (or ctx-guard auto at 80%)
PHONE:  Telegram → topic "Auric" → "continue"   # hermes lists sessions → pick → resumes claude --resume <id>
BACK:   claude -c                                # continue latest session in this dir
```

Token rule: **claude thinks (it's the worker); hermes is a thin router for coding** (don't double-plan). Switch model tier any time: `/model light` (cheap chat) · `/model heavy` (deepseek-v4-pro) · `/model think` (claude-sonnet-thinking).
