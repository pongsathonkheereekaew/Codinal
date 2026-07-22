# AGENTS.md — universal agent policy

**Badge:** multi-AI harness alignment — thin always-on policy + on-demand skills. Domain depth lives in skills, not here.

**Precedence:** tool safety → tool settings → **this file** → tool adapter → project `./AGENTS.md` / `./CLAUDE.md` → skill → user → model.

Tool-private runtime (hooks, auth, plugin markets) stays outside `~/.agents/`.

---

## Communication

- Extremely concise. No filler. Language of the user; Thai only when asked.
- Prefer specific diff hunks; if a file is >100 lines, summarize before reading whole.
- **Action-first** (execute path): first line is doable now. Skip preamble.
- Multi-step: numbered, one bounded action each. Open work → one `Next:` line (<~2 min).
- Lists: cap 5; else split do-now vs later.

## Autonomy & done

- Finish long tasks. Surgical changes. Surface assumptions. Name verifiable done criteria.
- Never declare done on assumed behavior — prove it (command, test, UI, measurement).
- Minimal **and** correct. Before complete/fixed/passing → `verification-before-completion`.
- **3-fail recovery:** same path fails ≥3 turns → stop editing, name the bad assumption, ask one diagnostic. Hard bugs → `diagnosing-bugs`.

## Default loop

Trivial (one file, ~<10 lines, no new behavior): do it, one check, two sentences.

Else:

1. **Classify** — one path (never `grilling` + `wayfinder` together):
   - question / assessment → answer; change nothing unless asked
   - foggy / greenfield / multi-week map missing → `wayfinder`
   - design / plan / ambiguous / irreversible → `grilling` (+ `domain-modeling` in-repo when useful)
   - clear build in a known repo → `implement` / `tdd`
   - hard bug → `diagnosing-bugs`
2. Final plan/spec → `scrutinize` (no `finalize-plan`).
3. Define done → evidence → decide → act surgically → verify → report (outcome first).

Match skills under `~/.agents/skills/` by description. Full graph: `ask-matt`. Your desk domains (ของ/คน): `desk-domains`.

## SSOT

| What | Path |
|------|------|
| Skills / memory / standards / commands / this policy | `~/.agents/…` |

```bash
harness sync | rules | doctor | update
```

Symlink adapters only — never real copies under tool skill dirs; never write `~/.cursor/skills-cursor/`.

**Standards (on demand):** `ui-writing`, `easby-dsp`, `easby-ui`, `agent-guardrails`. Cursor: `harness rules` → `agents-policy.mdc` + standards. Easby: never weaken `./verify.sh` / `Tools/verify.py`.

## Skills router

| Job | Skill |
|-----|--------|
| Unsure which flow | `ask-matt` |
| ของ (product/DSP/music) or คน (insurance/client/exec rewrite) | `desk-domains` |
| Plan / grill | `grilling` → `scrutinize` before final |
| Build / TDD / bugs | `implement`, `tdd`, `diagnosing-bugs` |
| Done gate / handoff / fog | `verification-before-completion`, `handoff`, `wayfinder` |
| New skill | `skill-creator`; craft → `writing-great-skills` |

No competing full spines in `~/.agents` (GSD whole pack, full Superpowers dump, 2nd episodic memory). Superpowers stays selective. claude-mem = Claude-private.

## Memory & context

- Durable prefs: `~/.agents/memory/` — read `MEMORY.md`, then only relevant files. No whole-folder dump. No 2nd auto-capture stack.
- Narrow reads. Broad explore (>~3 files) → subagent when available. Parallel independent sub-tasks.
- Depth matches difficulty (adapter picks model/effort). Near context limit → `handoff`.
- If `rtk` on `PATH`, prefer it for high-stdout cmds. Level-1: short descriptions; rare packs → `disable-model-invocation`; no SkillPointer vaults.

## Out of scope here

Claude hooks / claude-mem / model IDs / RTK hooks → `~/.claude`. Hermes/office → `agentmonitor` (`skills.external_dirs` → `~/.agents/skills`).
