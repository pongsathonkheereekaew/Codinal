# Agent Guardrails (on-demand)

Load when doing destructive work, handling secrets, touching verify gates, installing skills/spines, or proposing mass deletes. Not always-on.

## Verify & acceptance

- Never weaken, bypass, or comment out assertions/tests in `Tools/verify.py`, `./verify.sh`, or equivalent acceptance suites to force a green run.
- "Done" requires fresh evidence (`verification-before-completion`).

## Secrets & credentials

- Do not commit `.env`, keys, tokens, or credential JSON.
- Do not paste secrets into chat, logs, or wiki `raw/` dumps.
- Prefer env vars / secret managers already used by the project.

## Destructive actions

- Confirm before: `rm -rf`, force-push, hard reset, schema drop/migration that destroys data, mass file deletes.
- Skills that delete or move user files (e.g. `mac-storage-cleanup`) must audit read-only first and list exact paths before any delete.
- Prefer Trash / reversible moves for user-visible files; permanent delete only for approved caches/artifacts.

## Spines & installs

- Do not install competing full spines into `~/.agents` (GSD whole pack, full Superpowers dump, ultra-review duplicates, second episodic memory).
- New portable skills → harness-flow repo → `harness sync`. Never `skills add -a '*'` real copies into adapter dirs.
- Do not use vendor installers that write real copies under `~/.codex/skills` or similar when a harness SSOT path exists.

## Scope

- Surgical changes. Surface assumptions. One classify path (never grilling + wayfinder together).
- If the same approach fails ≥3 turns → stop, name the bad assumption, one diagnostic question (see AGENTS.md Autonomy).
