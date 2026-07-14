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

Prefer catalog skills below when they match (e.g. `grilling`, `tdd`, `diagnosing-bugs`) — the loop is the fallback when no better skill fits.

## Where content lives (one install place)

| What | Path |
|------|------|
| Skills | `~/.agents/skills/<name>/` only |
| Shared rules (bodies) | `~/.agents/standards/` |
| Shared slash commands | `~/.agents/commands/` |
| This policy | `~/.agents/AGENTS.md` |

After adding/moving a skill:

```bash
~/.agents/scripts/harness sync
```

After editing standards:

```bash
~/.agents/scripts/harness rules
```

Health check:

```bash
~/.agents/scripts/harness doctor
```

**Never** maintain parallel real copies under tool skill dirs (`~/.claude/skills`, `~/.cursor/skills`, `~/.openclaw/skills`, `~/.gemini/skills`, `~/.zcode/skills`) — those are symlink adapters. Codex/Gemini/OpenCode also read this `skills/` folder natively. Never write into `~/.cursor/skills-cursor/` (product-managed).

## Standards (load when relevant)

- Writing / typography / grilling vs AFK: `~/.agents/standards/ui-writing.md`
- Easby DSP / verify gates: `~/.agents/standards/easby-dsp.md`
- Easby UI: `~/.agents/standards/easby-ui.md`

Cursor also gets these via generated `~/.cursor/rules/*.mdc` (`harness rules`).

On Easby plugins: never weaken `./verify.sh` / `Tools/verify.py` to force a green run.

## Skills (shared catalog)

Prefer skills under `~/.agents/skills/` when the task matches their description. **Do not install a second full suite** (e.g. Superpowers) that duplicates Matt Pocock flows already here — map to the skill below instead.

Useful defaults:

| Job | Skill |
|-----|--------|
| Unsure which flow | `ask-matt` |
| Stress-test a plan | `grilling` (+ `domain-modeling` in a real repo) |
| Huge multi-session work | `wayfinder` |
| Conversation → spec / tickets | `to-spec` → `to-tickets` |
| Implement / TDD | `implement`, `tdd` |
| Two-axis review | `code-review` |
| Hard bugs | `diagnosing-bugs` |
| Before claiming done | `verification-before-completion` |
| Isolated feature worktree | `using-git-worktrees` → then `finishing-a-development-branch` |
| Compact for a fresh session | `handoff` |
| Research / throwaway prototype | `research`, `prototype` |
| UI / macOS UI | `ui-ux-pro-max`, `macos-design` |
| Insurance (Thai) | `nuiny`, `insurance-commission`, `insurance-premium-finding` |
| Audio plugin RE / mix / master | `easby-*` under `skills/easby/` |
| GCP / GKE / Gemini Agent Platform | matching `gcloud`, `gke-*`, `agent-platform-*`, `gemini-*` skills |

Project overlays (`./AGENTS.md` / `./CLAUDE.md`) win for repo-specific constraints.

## Context hygiene

- Don't re-read what is already in context. Prefer narrow reads over whole-file dumps.
- Broad / unfamiliar exploration (>~3 files or sweeping search) → use an explore/subagent path when the harness supports it; return conclusions, not raw dumps.
- Independent sub-tasks → run in parallel when the harness allows.
- Known exact file + symbol → just read it; don't fan out for a single lookup.

## Out of scope for this file

Claude-only memory (claude-mem), Claude hooks/goal-loop, plugin marketplaces, model IDs (`opusplan`, etc.), and RTK hooks belong in `~/.claude/CLAUDE.md` (or that tool's settings) — not here.

Hermes + AgentMonitor live in the separate `agentmonitor` repo (install → `~/.hermes` + office). Skills attach via `skills.external_dirs` → `~/.agents/skills` — do not maintain a second skill tree under Hermes except Hermes-native bundles.
