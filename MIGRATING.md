# Migrating from harness-only to Codinal layout

This repo was originally a harness-only SSOT (skills/policy/memory installed to `~/.agents/`). It has been repurposed as the **Codinal** product repo (a macOS coding-agent desktop app). The harness content still lives here — now under `harness/` — and the `~/.agents/` install contract is **unchanged**.

## For existing harness users

You have two options:

### Option A — stay on the last harness-only release (no change to your workflow)

```bash
git fetch --tags
git checkout last-harness-only
./install.sh   # unchanged behavior, installs to ~/.agents as before
```

The tag `last-harness-only` points to the final commit with the old flat layout. Nothing further will land there, but it remains a stable harness-only source.

### Option B — follow Codinal forward (harness content still installs the same way)

```bash
git pull
./install.sh   # now reads harness/* → installs to ~/.agents (identical result)
harness doctor # should still report READY
```

The install **target** (`~/.agents/`) and its layout are identical. Only the **source** layout inside this repo changed (content moved from root to `harness/`). `install.sh`, `bootstrap.sh`, `verify.sh`, `backup.sh` were updated to read from `harness/`.

## What changed

| Before (flat) | After (Codinal) |
|---|---|
| `AGENTS.md`, `scripts/`, `skills/`, `memory/`, `standards/`, `commands/`, `adapters/`, `config/`, `schemas/`, `templates/` at repo root | same content under `harness/` |
| `hermes/REVIEW-HOME.md` (stray) | removed |
| no product code | `desktop/` (Tauri) + `runtime/` (Python) skeletons added (Phases 1+) |
| no `LICENSE` / `NOTICE` | MIT `LICENSE` + `NOTICE` (attribution to OpenWorker, python-build-standalone) |
| — | `docs/decisions/` (ADR-0001) + `docs/plan/` (implementation plan + boundary map) |

## If something breaks

```bash
harness doctor          # diagnose
git checkout last-harness-only   # roll back to known-good harness-only
```

Then file an issue. The migration is designed to be invisible to `~/.agents/` consumers; if `harness doctor` regressed, that's a bug.
