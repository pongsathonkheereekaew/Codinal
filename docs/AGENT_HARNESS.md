# Agent Harness — naming & how to use it

## Names (use these consistently)

| Term | What it is | Example |
|------|------------|---------|
| **Agent Harness** | The *method*: one content hub + thin per-tool adapters | “We run Agent Harness at home” |
| **Lingua franca** | The shared always-on policy file | `~/.agents/AGENTS.md` (name stays **AGENTS.md** — tool ecosystem standard) |
| **SSOT / content hub** | Directory that owns skills, standards, commands, policy | `~/.agents/` |
| **Adapter** | Tool-private glue; never a second full copy of skills | `~/.claude/CLAUDE.md`, `~/.hermes/SOUL.md`, Cursor `.mdc` |
| **harness-flow** | *This repo* — bootstrap kit, templates, personal packs, docs | GitHub `…/harness-flow` |

Do **not** rename the lingua franca to something quirky (`POLICY.md`, `BRAIN.md`). Other agents already look for `AGENTS.md`.

---

## Optimal daily use (you)

```text
Edit once → live in ~/.agents → adapters stay thin
```

| Job | Do this |
|-----|---------|
| Add a skill | `cp -R <skill> ~/.agents/skills/<name>` → `~/.agents/scripts/harness sync` |
| Change shared policy / loop | Edit `~/.agents/AGENTS.md` only |
| Change writing / domain rules | Edit `~/.agents/standards/*.md` → `harness rules` |
| Claude-only (mem, hooks, RTK) | `~/.claude/CLAUDE.md` / settings — not AGENTS.md |
| Hermes-only (cursor-agent, AgentMonitor) | `~/.hermes/SOUL.md` — point to AGENTS.md, don’t duplicate |
| Hermes skills | `skills.external_dirs: [~/.agents/skills]` in `config.yaml` |
| Health check | `~/.agents/scripts/harness doctor` |

**Precedence (remember this):**

```text
tool safety → tool settings
  → ~/.agents/AGENTS.md          ← lingua franca
  → tool adapter                 ← Claude / Hermes / Cursor
  → project ./AGENTS.md
  → invoked skill
  → user message
  → model
```

**Rule of thumb:** if a sentence applies to *every* coding agent → AGENTS.md.  
If it only works on *one* product → adapter.

---

## Optimal use for others (adopters)

1. Copy [`templates/agents-harness/`](../templates/agents-harness/) (or run its `install.sh`).
2. Fill **placeholders** in their `AGENTS.md` (language, verify command, skill favorites).
3. Keep their identity file thin (`CLAUDE.md` / `SOUL.md`).
4. Do **not** paste your private skills, API keys, or Easby paths into a public fork — ship policy + scripts + empty `skills/`.

Personal machine migrate (Claude packs, Hermes SOUL, AgentMonitor) stays on **this** repo’s `install.sh` — that path is *your* kit, not the generic starter.

---

## What belongs where

| Content | Home |
|---------|------|
| Communication, done/verify loop, skill catalog map | `AGENTS.md` |
| Agent Skills (SKILL.md trees) | `~/.agents/skills/` only |
| Long rule bodies + Cursor frontmatter meta | `standards/` |
| Slash commands shared by tools | `commands/` |
| Memory, auth, hooks, gateway, sessions | Tool private (`~/.claude`, `~/.hermes`, …) |

---

## Publishing strategy for harness-flow

**Yes — keep using `harness-flow` as the repo name.** It’s the delivery vehicle (“flow” = install → sync → doctor).

Suggested layout of intent:

| Layer | Visibility | Contents |
|-------|------------|----------|
| A. Method + starter | Can be public later | `docs/AGENT_HARNESS.md`, `templates/agents-harness/` |
| B. Your machine kit | Prefer **private** | `claude/`, `hermes/`, AgentMonitor glue, personal skills |
| C. Live runtime | Never “the git SSOT alone” | `~/.agents` on each machine (install *from* repo, then live-edit) |

Until you strip secrets/personal IP: keep the GitHub repo **private**. Optionally later split `agents-harness` as a public sub-repo of layer A only.
