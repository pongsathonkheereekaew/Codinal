# CEDIA — open, self-hosted agent IDE with your harness everywhere

CEDIA is a Code-OSS fork with a local-first agent harness: one policy, one
skill catalog, one model registry, and the same rules across every coding
agent you run.

## Evidence

- Benchmark: `docs/market/benchmark-2026-08.md`
- Comparison: `docs/market/comparison.md`
- Parity audit: `docs/evidence/parity/cursor-docs-audit.md`

## Scope

- Editor: Code-OSS fork with native browser tab and BrowserOS MCP panel.
- Harness: policy, skills, commands, rules, hooks, plugins, subagents, and
  MCP across all hosts in `harness/config/hosts.yaml`.
- Models: opencode-go via local router, DeepSeek, OpenAI-compatible profiles,
  and effort selection.

Hosted-only parity (Cloud Agents, Bugbot, enterprise SSO, marketplace) is
deferred with reason and is not claimed here.
