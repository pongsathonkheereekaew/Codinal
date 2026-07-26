# Upstream

| Field | Value |
|-------|-------|
| Source | https://github.com/Kappaemme-git/codex-mac-storage-cleanup |
| Upstream path | `skill/` |
| npm | `codex-mac-storage-cleanup@1.0.0` |
| License | MIT |
| Vendored | 2026-07-20 |

## Local changes vs upstream

- Script path uses `$HOME/.agents/skills/mac-storage-cleanup/...` (upstream hard-coded a personal Codex path).
- Description generalized beyond Codex-only wording.
- Protected wording says "agent history" instead of Codex-only.

Do not use `npx codex-mac-storage-cleanup` on this machine — that copies into `~/.codex/skills` as a real copy and breaks harness SSOT. Update via this repo + `harness sync`.
