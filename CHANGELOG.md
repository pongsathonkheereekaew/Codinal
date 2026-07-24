# Changelog

All notable changes to the harness-flow agent harness. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions track the
policy surface (standards + core skills); adapter wiring and peripheral skills
bump independently.

## [Unreleased]

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
