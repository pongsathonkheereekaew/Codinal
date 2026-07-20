# Harness smoke eval (manual)

Lightweight checks after changing **policy / standards / rule generation** (`AGENTS.md`, `standards/`, `scripts/gen-cursor-rules.sh`, Level-1 skill flags). Not CI. Not a substitute for [thinking-flow](../thinking-flow/).

## When to run

- After editing `AGENTS.md` or regenerating Cursor bridges
- After flipping many skills to `disable-model-invocation`
- After changing `cursor.meta.yaml` alwaysApply flags

## Scenarios

### S1 — Classify XOR

Ask (in a fresh agent turn): “Plan a multi-week greenfield + also grill the ambiguous API.”

**Pass:** agent picks **one** of `wayfinder` or `grilling`, not both in the same path. Cites AGENTS Default loop.

### S2 — Cursor policy bridge

```bash
test -f "$HOME/.cursor/rules/agents-policy.mdc"
rg -n 'Action-first|3-fail recovery' "$HOME/.cursor/rules/agents-policy.mdc"
```

**Pass:** file exists, `alwaysApply: true`, both strings present (after `harness rules`).

### S3 — GCP not in Level-1

```bash
harness doctor 2>&1 | rg 'GCP/Google-ish share|model-invoked'
```

**Pass:** `GCP/Google-ish share: (none detected)` (or ~0%). `gcloud` still on disk under `~/.agents/skills/gcloud` for manual invoke.

### S4 — Guardrails not always-on

```bash
rg -n 'alwaysApply' "$HOME/.cursor/rules/agent-guardrails.mdc"
```

**Pass:** `alwaysApply: false`.

## Record

Copy results into `runs/YYYY-MM-DD.md` (optional). Pass = all scenarios that apply to the change.
