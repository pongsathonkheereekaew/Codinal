# Project Wiki Schema (agent-owned)

Karpathy-style llm-wiki adapted for **engineering lessons** — one wiki per git repo.
This is **not** a second memory engine. Session memory stays with claude-mem.
This wiki is durable project documentation under `docs/wiki/`, committed with the code.

## Layout

```
docs/wiki/
  SCHEMA.md          # this file (copied from template; edit per-repo notes only at bottom)
  index.md           # table of contents — update on every write
  log.md             # append-only ingest/fix log
  raw/               # immutable evidence (logs, repro notes, dumps) — agents NEVER edit
  incidents/         # one validated bug fix → one page
  code-map/          # modules / invariants that are easy to forget
  patterns/          # reusable "when you see X → do Z" lessons
```

## Page conventions

- YAML frontmatter required: `type:` (`incident` | `code-map` | `pattern` | `source-summary`)
- Prefer `[[wikilinks]]` between related pages
- Keep dates: `date_updated:` (ISO date)
- Incidents also include: `slug:`, `status: fixed`, optional `commit:`, `pr:`
- Code identifiers welcome (paths, functions, gates) — they are the search index

## Operations

### Query (before rediscovering)

When the user reports a symptom that might recur:

1. Read `docs/wiki/index.md`
2. Open matching `incidents/` and `patterns/` pages
3. Only then dig into unfamiliar code paths

### Ingest (raw evidence)

- Drop evidence into `docs/wiki/raw/` (append-only once committed).
- Agents read raw; they never modify it.
- Compile lasting knowledge into `incidents/`, `code-map/`, or `patterns/` — not into raw.

### Auto-after-fix (done gate)

When `docs/wiki/SCHEMA.md` exists in the project:

1. Fix lands and is **validated** (tests / `./verify.sh` prove it).
2. Four post-mortem inputs are met (repro, root cause, fix, validation).
3. **Before declaring done:** write `docs/wiki/incidents/<slug>.md`, then update `index.md` and append `log.md`.
4. If the fix reveals a reusable invariant, also upsert a short page under `patterns/` or `code-map/`.

**Skip** trivial fixes (typo, obvious one-liner) — PR description is enough.

### Lint

Periodically (or when wiki feels stale):

- No empty stubs left from abandoned drafts
- Every `[[wikilink]]` resolves or is fixed/removed
- Orphans not linked from `index.md` get linked or deleted
- Contradictions between pages noted explicitly (do not silently overwrite)

## Boundaries vs claude-mem / Obsidian

| System | Role |
|--------|------|
| claude-mem | Session episodic capture/recall — **only** memory SSOT |
| `docs/wiki/` | Per-repo engineering lessons in git |
| Obsidian | Optional graph/read view over this folder — not a capture engine |

---

<!-- Per-repo notes below this line (optional) -->
