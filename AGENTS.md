# AGENTS.md — universal agent policy

**Badge:** multi-AI harness alignment — one thin always-on policy + on-demand skills, same behavior across coding agents. Domain depth (UI, cloud, Easby, …) lives in skills, not in this file.

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
- **Action-first (execute path):** when the reply is a fix, command, or next step — first line is something doable now (command, path+line, or step 1). Skip preamble ("Great question", "Let me…", "Sure!"). Does not override `grilling`, "explain", or destructive-confirm paths.
- **Multi-step:** number the steps; one bounded action per step.
- **Open work:** if anything remains, end with one `Next:` line (under ~two minutes). No "hope this helps" / "let me know if…" closers.
- **Lists:** cap at 5; if more, split **do now** vs **later** (or must vs nice-to-have).

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

1. **Classify** — one path (never force grilling + wayfinder together):
   - question / assessment → answer; change nothing unless asked
   - foggy / greenfield / multi-week map missing → `wayfinder`
   - design / plan / ambiguous / irreversible → `grilling` (+ `domain-modeling` in-repo when useful)
   - clear build in a known repo → `implement` / `tdd`
   - hard bug → `diagnosing-bugs`
2. **Final plan gate** — before presenting a plan/spec as final → run `scrutinize`; fix or mark rework. No `finalize-plan` skill.
3. **Define done** — name the verification (test, build, measured value, visible result).
4. **Evidence** — primary sources; parallel lookups when the harness allows; intent before behavior-changing edits.
5. **Decide** — one recommendation; then act surgically (smallest correct change).
6. **Verify** — observe the done criterion; use `verification-before-completion` before any success claim.
7. **Report** — outcome first, honest caveats.

Prefer a matching skill under `~/.agents/skills/` by name (progressive disclosure — don't paste Ask Matt every turn). Full graph: user invokes `ask-matt`.

## Where content lives (one install place)

| What | Path |
|------|------|
| Skills | `~/.agents/skills/<name>/` only |
| Durable prefs / facts | `~/.agents/memory/` (index: `MEMORY.md`) |
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

Cursor also gets these via generated `~/.cursor/rules/*.mdc` (`harness rules`), including `agents-policy.mdc` (full `AGENTS.md` bridge — Cursor has no global AGENTS.md). On Easby plugins: never weaken `./verify.sh` / `Tools/verify.py` to force a green run.

## Skills (core router — keep always-on thin)

Prefer skills under `~/.agents/skills/` when the task matches their `SKILL.md` description. Do not install a second full suite that duplicates flows already there.

| Job | Skill |
|-----|--------|
| Unsure which flow (user) | `ask-matt` |
| Design / stress-test a plan | `grilling` |
| Before final plan / PR review | `scrutinize` |
| Implement / TDD | `implement`, `tdd` |
| Hard bugs | `diagnosing-bugs` |
| Before claiming done | `verification-before-completion` |
| Compact for a fresh session | `handoff` |
| Foggy / huge multi-session | `wayfinder` |
| Create / optimize a skill | `skill-creator` (Anthropic); principles → `writing-great-skills` |

Everything else (UI, insurance, easby, GCP, …): match by skill description under `~/.agents/skills/` or ask `ask-matt`. Project overlays (`./AGENTS.md`) win for repo-specific constraints.

Do **not** install competing full spines into this folder (GSD whole pack, full Superpowers dump, ultra-review duplicates). Superpowers stays selective (`verification-before-completion`, worktrees, finish-branch) + Claude plugin for fan-out. claude-mem / context-mode stay Claude-private.

## Durable memory (shared)

Long-lived prefs and locked decisions live in `~/.agents/memory/` (not episodic chat recall).

- When preference / stack / “never do X” / topology matters → read `MEMORY.md`, then only the relevant file(s).
- Do **not** dump the whole memory folder every turn.
- Do **not** add a second auto-capture memory system — episodic stays tool-private (e.g. claude-mem under `~/.claude`).

## Context hygiene

- Don't re-read what is already in context. Prefer narrow reads over whole-file dumps.
- Broad / unfamiliar exploration (>~3 files) → explore/subagent when available; return conclusions.
- Independent sub-tasks → parallel when the harness allows.
- Known exact file → read it directly.
- **Depth:** trivial → short path; hard/ambiguous → plan first or a heavier model in the *tool adapter* — do not paste hidden chain-of-thought into the user reply.
- **Survive context limits:** long work → `handoff` / GOAL before rotating the session.
- **Stdout:** if `rtk` is on `PATH`, prefer `rtk <cmd>` for high-stdout commands (git, grep, find, ls, tree, docker). RTK *hooks* stay Claude-only — not here.
- **Level-1 skills:** startup cost grows with *model-invoked* skill count (name + description only). Check `harness doctor` — do not install SkillPointer vaults into this folder.

## Out of scope for this file

Claude-only **episodic** memory (claude-mem), Claude hooks/goal-loop, plugin marketplaces, model IDs, and RTK hooks belong in `~/.claude/CLAUDE.md` (or that tool's settings) — not here. Durable facts belong in `~/.agents/memory/`.

Hermes + AgentMonitor live in the separate `agentmonitor` repo (install → `~/.hermes` + office). Skills attach via `skills.external_dirs` → `~/.agents/skills`.
