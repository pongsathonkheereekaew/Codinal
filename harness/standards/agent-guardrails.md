# Agent Guardrails (on-demand)
<!-- spec-version: 1.0.0 -->

Load when doing destructive work, handling secrets, touching verify gates, installing skills/spines, proposing mass deletes, gating consequential tool actions, parking approvals, or running scheduled/unattended work. Not always-on.

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

## Risk classes

Classify proposed tool actions before running them:

| Class | Meaning | Default gate |
|-------|---------|--------------|
| `read` | No side effects (read file, search, fetch public info) | Allow |
| `write_local` | Mutates the workspace (edit/write under allowed roots) | Ask unless mode allows |
| `exec` | Runs shell / process commands | Ask; never standing-auto |
| `external` | Side effects off the machine (send message, API write, calendar change) | Ask; standing rules may apply |

Anything but `read` is **consequential**.

## Permission surface (host-real)

There is no harness-defined mode enum. Hosts expose their own permission surface — a CLI flag, a session setting, a Cursor/Codex/Gemini approval prompt, or a Hermes SOUL rule. Use whichever the current host already provides; **do not invent a parallel permission product in this harness.**

Operating rules, regardless of host surface:

- Ask before `write_local` / `exec` / `external`. `read` is always allowed.
- Path-scope `write_local` to writable roots when the host defines them.
- Never grant silent standing-auto for `exec` / shell.
- Read-only postures (however the host names them) still deny consequential classes.

## Inbox contract (unattended / away)

- **Unattended ≠ higher autonomy.** Same risk gates; only the delivery surface changes (inline chat → parked approval/question queue).
- Park approvals and clarifying questions; suspend work until resolved.
- **First-responder-wins** — resolving an item once from any surface is final and idempotent.
- `exec` / shell never gets silent standing approval.

## Standing rules

- Allowed only for `external` risk, bound to an **exact target** (channel, recipient, repo, URL named by the call).
- Never for `exec` or open-ended write_local.
- Additive on top of the current mode — read-only modes still deny.

## Scheduler policy

When a surface runs recurring/cron work (Hermes cron, host scheduler, automation):

- **Catch-up once** on wake for missed due runs — do not replay a backlog of every missed tick.
- **Skip-on-overlap** — if the previous run is still going, do not stack another.
- Each run leaves a transcript or `handoff` artifact the human can open.

## Artifact convention

When the deliverable is a file, end the reply with a markdown link the user can open (`[Title](relative/or/absolute/path)`). If the surface has a native artifact URI, prefer that.

## Spines & installs

- Do not install competing full spines into `~/.agents` (GSD whole pack, full Superpowers dump, ultra-review duplicates, second episodic memory).
- New portable skills → harness-flow repo → `harness sync`. Never `skills add -a '*'` real copies into adapter dirs.
- Do not use vendor installers that write real copies under `~/.codex/skills` or similar when a harness SSOT path exists.
- Do not port a second coworker/desktop-agent runtime into this harness (policy/skills only).

## Scope

- Surgical changes. Surface assumptions. One classify path (never grilling + wayfinder together).
- If the same approach fails ≥3 turns → stop, name the bad assumption, one diagnostic question (see AGENTS.md Autonomy).
