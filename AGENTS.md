# AGENTS.md — universal agent policy

Shared always-on instructions for **every** coding agent / CLI / IDE that can load this file (Claude Code, Cursor, Openclaw, and others). Tool-private runtime (hooks, auth, chats, plugin markets) stays outside `~/.agents/`.

**Precedence (high → low within instruction layers):**  
tool safety → tool settings → **this file** → tool adapter (e.g. `~/.claude/CLAUDE.md`, Cursor `.mdc`) → project `./AGENTS.md` or `./CLAUDE.md` → invoked skill → user message → model.

---

## Communication

- Be extremely concise. No yapping, no conversational filler.
- Answer in the language of the user's message. Translate to Thai **only** when asked (e.g. "แปล", "ตอบไทย").
- If you need more info, ask briefly.
- If code is self-explanatory, don't explain it.
- When suggesting edits: prefer specific diff hunks, not entire files. If a file is >100 lines, summarize structure before reading it whole. Don't dump large files into the reply.

## Autonomy & done

- Run long tasks to completion. Self-verify before declaring done (build fingerprint, tests, measurements, or the observation the task named).
- Do not stall on "done?".
- Surgical changes. Surface assumptions. Define verifiable success criteria before claiming success.
- Never declare done on assumed behavior — prove it (command output, test pass, visible UI, measured value).
- "Minimal" only above a passing verification floor — minimal **and** correct, never minimal-but-broken.
- Before claiming complete / fixed / passing: use `verification-before-completion` (fresh command evidence).

## Default loop (non-trivial work)

Skip this only when the task is trivial (one file, ~<10 lines, no new behavior, no searching): do it, one obvious check, two sentences.

Otherwise:

1. **Classify** — question/assessment (change nothing) vs task vs plan-first (ambiguous/irreversible → plan and wait).
2. **Define done** — name the verification (test, build, measured value, visible result).
3. **Evidence** — primary sources; parallel lookups when the harness allows; intent before behavior-changing edits.
4. **Decide** — one recommendation; then act surgically (smallest correct change).
5. **Verify** — observe the Step-2 criterion; use `verification-before-completion` before any success claim.
6. **Report** — outcome first, honest caveats.

Prefer a matching skill under `~/.agents/skills/` when one fits; the loop is the fallback. Unsure which skill → `ask-matt`.

## Where content lives (one install place)

| What | Path |
|------|------|
| Skills | `~/.agents/skills/<name>/` only |
| Shared rules (bodies) | `~/.agents/standards/` |
| Shared slash commands | `~/.agents/commands/` |
| This policy | `~/.agents/AGENTS.md` |

```bash
~/.agents/scripts/harness sync    # after adding skills
~/.agents/scripts/harness rules   # after editing standards
~/.agents/scripts/harness doctor  # health check
```

**Never** maintain parallel real copies under tool skill dirs — those are symlink adapters (or native readers of `~/.agents/skills`). Never write into `~/.cursor/skills-cursor/` (product-managed).

## Standards (load when relevant)

- Writing / typography: `~/.agents/standards/ui-writing.md`
- Easby DSP / verify gates: `~/.agents/standards/easby-dsp.md`
- Easby UI: `~/.agents/standards/easby-ui.md`

Cursor also gets these via generated `~/.cursor/rules/*.mdc` (`harness rules`). On Easby plugins: never weaken `./verify.sh` / `Tools/verify.py` to force a green run.

## Skills (core router — keep always-on thin)

Prefer skills under `~/.agents/skills/` when the task matches their `SKILL.md` description. Do not install a second full suite that duplicates flows already there.

| Job | Skill |
|-----|--------|
| Unsure which flow | `ask-matt` |
| Stress-test a plan | `grilling` |
| Implement / TDD | `implement`, `tdd` |
| Hard bugs | `diagnosing-bugs` |
| Before claiming done | `verification-before-completion` |
| Compact for a fresh session | `handoff` |
| Huge multi-session work | `wayfinder` |

Everything else (UI, insurance, easby, GCP, …): match by skill description under `~/.agents/skills/` or ask `ask-matt`. Project overlays (`./AGENTS.md`) win for repo-specific constraints.

## Context hygiene

- Don't re-read what is already in context. Prefer narrow reads over whole-file dumps.
- Broad / unfamiliar exploration (>~3 files) → explore/subagent when available; return conclusions.
- Independent sub-tasks → parallel when the harness allows.
- Known exact file → read it directly.
- **Depth:** trivial → short path; hard/ambiguous → plan first or a heavier model in the *tool adapter* — do not paste hidden chain-of-thought into the user reply.
- **Survive context limits:** long work → `handoff` / GOAL before rotating the session.
- **Stdout:** if `rtk` is on `PATH`, prefer `rtk <cmd>` for high-stdout commands (git, grep, find, ls, tree, docker). RTK *hooks* stay Claude-only — not here.

## Out of scope for this file

Claude-only memory (claude-mem), Claude hooks/goal-loop, plugin marketplaces, model IDs, and RTK hooks belong in `~/.claude/CLAUDE.md` (or that tool's settings) — not here.

Hermes + AgentMonitor live in the separate `agentmonitor` repo (install → `~/.hermes` + office). Skills attach via `skills.external_dirs` → `~/.agents/skills`.
