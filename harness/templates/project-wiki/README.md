# Project Wiki template

Karpathy-style engineering wiki for a **single git repo**: durable incident / pattern pages under `docs/wiki/`, maintained by the agent after validated bug fixes.

## Not a second memory system

| System | Role |
|--------|------|
| **claude-mem** | Session episodic capture/recall (memory SSOT) |
| **`docs/wiki/`** | Per-repo engineering lessons in git |
| **Obsidian** | Optional read/graph view over `docs/wiki/` — does not capture |

Do not install a competing vault or LLM-wiki app as a capture engine.

## Init into a project

From the harness-flow repo root:

```bash
bash templates/project-wiki/init-wiki.sh /path/to/your-plugin-or-app-repo
```

Creates `docs/wiki/` + `.cursor/rules/project-wiki.mdc` in the target. Refuses if `docs/wiki/SCHEMA.md` already exists.

## Agent behavior (after init)

- Validated non-trivial bug fix → write `docs/wiki/incidents/<slug>.md`, update `index.md` + `log.md`, then declare done.
- Similar symptom later → read `index.md` first.
- Trivial typo/one-liner fixes skip the wiki.

Schema details: [`SCHEMA.md`](SCHEMA.md).
