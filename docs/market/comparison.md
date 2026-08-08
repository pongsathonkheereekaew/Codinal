# CEDIA vs OpenCode + VS Code vs Cursor vs Claude Code

Date: 2026-08-08. Honest status vocabulary: `supported`, `partial`,
`unsupported`, `deferred`. Evidence links under `docs/evidence/market/`.

| Surface | CEDIA | OpenCode + VS Code | Cursor | Claude Code |
| --- | --- | --- | --- | --- |
| MCP | supported (stdio + streamable HTTP, tools only) | supported (tools/prompts/resources) | supported | partial |
| Skills | supported (harness skills, bounded catalog) | supported | partial | supported |
| Subagents | partial (basic runner, no parallel isolation) | supported | supported | supported |
| Prompt cache | partial (`long`/`auto` headers + usage surface) | partial (provider-dependent) | supported | supported |
| Enterprise | deferred | partial | supported | supported |
| Self-host | supported | supported | unsupported | supported |
| Cloud agent | deferred | partial (opencode cloud) | supported | supported |
| Native IDE | supported (Code-OSS fork) | supported | supported | unsupported |
| Privacy | local-first, telemetry opt-out | provider-dependent | partial | partial |

Honest gaps are marked `partial`/`deferred`; see
`docs/evidence/parity/cursor-docs-audit.md` for the full Cursor audit.
