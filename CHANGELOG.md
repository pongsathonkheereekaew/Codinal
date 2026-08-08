# Changelog

All notable changes to the harness-flow agent harness. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions track the
policy surface (standards + core skills); adapter wiring and peripheral skills
bump independently.

## [0.2.0] - 2026-08-08

### Added
- Market benchmark case set, runner, and baseline report
  (`harness/eval`, `scripts/bench`, `docs/market/benchmark-2026-08.md`).
- Host verification gate (`harness host verify --all`) and per-host smoke
  scripts with evidence under `docs/evidence/market/b2-b5`.
- Provider prompt-cache controls (`none | auto | long`), usage surface
  (`cacheReadInputTokens`, `cacheWriteInputTokens`, `costUsd`), and context
  compaction budgets in the CEDIA agent.
- Perf budget registry and opt-in `CEDIA_PERF=1` lane.
- Bounded skill catalog and on-demand `skill_view` tool.
- Comparison matrix, landing page, roadmap, contribution, and security docs.
- Cursor-style agent UI: segmented mode switcher, searchable model picker,
  recent-chat empty state, hidden VS Code chrome, and Cursor-style start page.
- opencode-go model profiles routed through the local opencode router with
  effort selection.

### Deferred
- Hosted-only Cursor surfaces (Cloud Agents, Bugbot, enterprise SSO,
  marketplace) remain out of scope with reason.

## [Unreleased]

### Changed — repo repurposed to Codinal (Phase 0b migration)
- This repo is now the **Codinal** product repo (macOS coding-agent desktop).
  Harness content moved from repo root into `harness/` subpath. The `~/.agents/`
  install target and its layout are **unchanged**; only the in-repo source
  layout changed.
- `install.sh`, `bootstrap.sh`, `verify.sh`, `backup.sh` updated to read from
  `harness/`.
- Removed stray `hermes/REVIEW-HOME.md` (hermes lives in `agentmonitor`).
- Added: `LICENSE` (MIT), `NOTICE` (attribution: OpenWorker © 2024 Andrew Ng,
  python-build-standalone), `MIGRATING.md`, `desktop/` + `runtime/` skeletons,
  `docs/decisions/0001-codinal-foundation.md` (ADR),
  `docs/plan/codinal-mvp.md`, `docs/plan/openworker-boundary-map.md`.
- Tagged `last-harness-only` at the final harness-only commit for rollback.

### Phase 0a de-risking spikes (all PASSED 2026-07-25)
- 0a.1 control-plane auth (loopback HTTP+WS + bearer token + PermissionEngine
  no-bypass): 4/4.
- 0a.2 sandbox-exec notarization: Accepted + `spctl: Notarized Developer ID`.
- 0a.3 embedded-Python bundle notarization: Accepted + runs post-notarize.
- 0a.4 OpenWorker boundary map → re-opened F1 (control plane back to
  loopback+token; in-process stdio would have forced full UI bridge rewrite).

### Added — capability-driven harness (Phases 1–3 of the cross-agent plan)
- `config/hosts.yaml` + `schemas/host-capability.schema.json`: central
  capability manifest. Each host declares tier, paths, discovery rules, native
  permission mechanism, and per-capability status
  (`supported`/`partial`/`unsupported`/`unverified`). Adapters and the CLIs
  read this; edit here, never in generated output.
- `scripts/lib/`: `manifest.py` (loader + baseline→host permission mapping),
  `jsonc.py` (comment-preserving JSONC editor — inserts/replaces a top-level
  key without destroying user comments), `ownership.py` (ownership journal +
  atomic writes + timestamped backups), `symlink.py` (idempotent relative
  links).
- `scripts/adapters/`: `OpenCodeAdapter` (Tier-1, behaviorally verified) wires
  `~/.config/opencode/{AGENTS.md,commands/,opencode.jsonc}` and merges the
  universal permission baseline; `PolicyLinkAdapter` gives every other host
  (claude-code, codex, cursor, gemini-cli, zcode, openclaw, hermes) honest
  config-driven provisioning + verification.
- `harness host list|inspect|provision|uninstall`, `harness verify
  [--host|--tier|--project|--json]`: effective-state verification. Tier-1 gate
  returns NOT-READY while any required capability is unsupported/unverified.
- `config/skills.yaml` + `harness skill list|enable|disable|reset|audit`:
  explicit core/catalog model. Disabling never deletes source skills; for
  OpenCode it adds a native `permission.skill.<name>: deny` rule. Respects
  user-owned permission blocks (never overwrites).
- `tests/contracts/` (pytest): manifest/schema validation, JSONC editor, the 7
  locked OpenCode smoke probes (isolated temp HOME), skill model + journal,
  PolicyLinkAdapter behavior, and the CLI end-to-end. `verify.sh` now runs the
  suite.

### Changed
- `install.sh`: rsyncs `scripts/` recursively (carries `lib/` + `adapters/`)
  and deploys `config/` + `schemas/` so the runtime CLI can read the manifest.
- `scripts/harness`: dispatches `host`/`verify`/`skill`/`install`/`uninstall`
  to the Python CLIs; help text updated.

### Fixed
- Ownership journal no longer follows symlinks when keying paths — previously
  a harness link back to `~/.agents/AGENTS.md` was recorded as the source, so
  `uninstall` would have deleted the policy file. Regression-locked by
  `test_uninstall_removes_only_owned`.

### Added — Codinal runtime and desktop (Phases 1–4)
- Model-agnostic OpenAI, Anthropic, and Gemini turn adapters; persistent
  conversations; authenticated HTTP/WebSocket control plane; MCP tools.
- Harness risk-class approval chokepoint, macOS Seatbelt execution, bounded
  atomic mutation tools, and per-session Git worktree isolation with verified
  apply-back and conflict rollback.
- Native Tauri desktop shell with macOS Keychain credentials, folder picker,
  task sidebar, transcript/composer, approval cards, model switching, and
  inline Git diff/review.

### Pending (next session — Phase 4/5)
- gemini-cli user-policy TOML permission mapping; deeper project-override
  detection for non-OpenCode hosts; `harness migrate` catalog/ enabled-view
  layout split (`--dry-run`, backup, idempotent).

## [1.0.0] - 2026-07-24

### Changed
- Tightened OpenWorker→harness adoption so claims match delivery paths
  (scrutinize×5 verdict: fix-then-ship).
- `standards/agent-guardrails.md`: dropped the fictional Mode enum
  (`discuss|plan|interactive|auto|custom`) — no host exposes a `Mode` type.
  Replaced with a host-real "Permission surface" section.
- `AGENTS.md`: added always-on "Risk spine" subsection (3 bullets) so the
  load-bearing risk policy no longer depends on a Cursor rule that never
  loads (`alwaysApply:false` + no globs).
- `AGENTS.md`: collapsed the duplicate `orchestrating-workers` pointer in
  Context hygiene (Orchestration already covers it).
- `skills/orchestrating-workers/SKILL.md`: worker ceiling now framed as a
  RiskClass ceiling (`read`/`write_local`/`exec`/`external`), default `read`,
  not the removed permission Mode.
- `standards/persona-manifest.md`: deleted the false "Invalid manifests should
  fail loudly" claim (no parser exists); `default_permission_mode` row no
  longer cites the removed enum.
- `~/.hermes/SOUL.md`: appended "Away / unattended / scheduled" distill
  (machine-local apply; existing content preserved).

### Added
- Behavioral policy-invariant assertions in `verify.sh` — guard against
  regression of the Mode-enum removal, the always-on risk spine, the
  persona "fail loudly" claim, the worker-ceiling wording, and H1-only
  standards headers. CI runs these via the existing `verify` workflow.
- `CHANGELOG.md` (this file).
- `spec-version: 1.0.0` comment on the five live `standards/*.md`.
- `version: 1.0.0` frontmatter on the ten core skills (ask-matt, grilling,
  scrutinize, implement, tdd, diagnosing-bugs, verification-before-completion,
  handoff, wayfinder, orchestrating-workers).

### Removed
- `standards/writing.md` — 5-line subset of `ui-writing.md`, drift risk.
  The `templates/agents-harness/` snapshot keeps its own copy.

## Pre-1.0.0

Earlier history lives in `git log` — the repo predated versioned policy.
