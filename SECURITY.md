# CEDIA security

CEDIA is a local-first harness. Secrets stay in OS secret storage or local
env files (`~/.config/cedia/env`, chmod 600); never commit API keys.

Telemetry defaults to opt-out and is local-only. Sandbox/run modes are
best-effort guardrails, not a hard security boundary.

To report a vulnerability, open a private issue in the repository or contact
the maintainer directly with a minimal reproduction.
