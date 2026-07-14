# AGENTS.md — universal agent policy

Shared always-on instructions for **every** coding agent that can load this file
(Claude Code, Cursor, Codex, Gemini CLI, OpenCode, Openclaw, ZCode, Hermes via skills, …).

Tool-private runtime (hooks, auth, memory plugins, gateways) stays **outside** `~/.agents/`.

**Precedence (high → low within instruction layers):**  
tool safety → tool settings → **this file** → tool adapter → project `./AGENTS.md` or `./CLAUDE.md` → invoked skill → user message → model.

---

## Communication

- Be extremely concise. No filler.
- Answer in the language of the user's message.
- Prefer specific diffs over dumping whole files.

## Autonomy & done

- Run long tasks to completion.
- Never declare done on assumed behavior — prove it (command output, tests, visible UI, measured value).
- Surgical changes. Surface assumptions. Name the verification *before* claiming success.

## Default loop (non-trivial work)

Skip only when trivial (one file, ~<10 lines, no new behavior): do it, one check, two sentences.

1. **Classify** — question vs task vs plan-first (ambiguous / irreversible → plan and wait).
2. **Define done** — name the verification.
3. **Evidence** — primary sources; intent before behavior-changing edits.
4. **Decide** — one recommendation; act surgically.
5. **Verify** — observe step 2; fresh evidence before any success claim.
6. **Report** — outcome first, honest caveats.

Prefer a matching skill from the catalog when one fits; the loop is the fallback.

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

**Never** maintain parallel real copies under tool skill dirs — adapters are symlinks (or native readers of `~/.agents/skills`).

## Standards (load when relevant)

- Example writing rules: `~/.agents/standards/writing.md`
- Add your domain files next to it; map them in `standards/cursor.meta.yaml` for Cursor.

## Skills (shared catalog)

<!-- CUSTOMIZE: map jobs → skill folder names you actually install -->

| Job | Skill |
|-----|--------|
| Unsure which engineering flow | *(your router skill, e.g. ask-matt)* |
| Stress-test a plan | *(your grilling skill)* |
| Implement / TDD | *(your implement / tdd skills)* |
| Before claiming done | *(verification-before-completion or equivalent)* |

Project overlays (`./AGENTS.md`) win for repo-specific constraints.

## Context hygiene

- Don't re-read what's already in context.
- Broad exploration (>~3 files) → explore/subagent when available; return conclusions.
- Known exact file → read it directly.

## Out of scope for this file

Tool-only memory, hooks, model IDs, messenger gateways, and product identity prompts belong in that tool's adapter (`CLAUDE.md`, `SOUL.md`, settings) — not here.
