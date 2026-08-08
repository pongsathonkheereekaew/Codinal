# CEDIA Market, All-Harness Support, and Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CEDIA win in the market against OpenCode + VS Code and closed harnesses by (1) proving performance with real benchmarks, (2) supporting every host in `harness/config/hosts.yaml` with verified adapters, and (3) shipping a production-grade IDE with measurable prompt-cache/context efficiency.

**Architecture:** Extend the existing CEDIA harness SSOT (`~/CEDIA`) and the Code-OSS IDE fork (`~/cedia-ide`). Keep all product code in `extensions/cedia-agent` until the packaging phase; add one benchmark suite and one perf-budget gate shared by both repos. Do not rewrite the VS Code editor core.

**Tech Stack:** Python (harness adapters), TypeScript (cedia-agent), Bash (gates), JSON/JSONC/YAML (config), GitHub Actions (CI), macOS codesign/notarytool (release).

## Global Constraints

- `bash ~/CEDIA/verify.sh` and `bash ~/cedia-ide/verify.sh` must both be green after every phase.
- Capability statuses use the locked vocabulary: `supported`, `partial`, `unsupported`, `unverified`. A host may be claimed as "supported" only when its own smoke evidence exists; otherwise record `partial` or `unsupported` honestly.
- Every capability ships a named gate artifact under `~/CEDIA/docs/evidence/market/<phase>/`; "UI presence only" is never evidence.
- Keep the VS Code fork diff minimal; agent work stays in `extensions/cedia-agent` through Phase D.
- Telemetry must default to opt-out and remain local-only; no API keys or tokens in git.
- Benchmark data must be reproducible: fixed task set, fixed model profile, fixed machine; cache-hit ratios come from provider usage fields, not estimates.
- This plan extends `docs/plan/cedia-full-cursor-parity.md`; it does not reopen P1-P8. Hosted-only parity stays deferred with reason.
- Each phase ends with a self-hosted dogfood run: CEDIA's own agent authors at least one real change in this repo and `verify.sh` passes.

---

## Phase A — Baseline Evidence

### Task A1: Market benchmark task set

**Files:**
- Create: `~/CEDIA/harness/eval/cases/market-bench.json`
- Create: `~/CEDIA/harness/eval/README.md`

**Interfaces:**
- Consumes: existing `harness` CLI layout only.
- Produces: `MarketBenchCase` array of `{id, repo, setup, prompt, expect, budget_ms}` used by A2/A3 and C4.

- [ ] **Step 1: Write the fixture file**

```json
{
  "schema_version": 1,
  "cases": [
    { "id": "hello-ts", "repo": "fixtures/hello-ts", "setup": "npm install", "prompt": "Add a failing test for isEven and make it pass", "expect": "npm test green", "budget_ms": 120000 },
    { "id": "refactor-py", "repo": "fixtures/refactor-py", "setup": "true", "prompt": "Extract duplicate validation into one helper", "expect": "pytest green + no duplication", "budget_ms": 120000 },
    { "id": "docs-md", "repo": "fixtures/docs-md", "setup": "true", "prompt": "Rewrite README with a usage section", "expect": "markdown lint passes", "budget_ms": 60000 }
  ]
}
```

- [ ] **Step 2: Add fixtures**

Create `harness/eval/fixtures/hello-ts`, `harness/eval/fixtures/refactor-py`, `harness/eval/fixtures/docs-md` as small repos (each with a passing baseline test). Do not reuse CEDIA itself as a fixture yet.

- [ ] **Step 3: Verify the fixture contract**

Run: `python3 -c "import json; d=json.load(open('harness/eval/cases/market-bench.json')); assert len(d['cases'])==3"`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add harness/eval
git commit -m "feat(eval): market benchmark case set"
```

### Task A2: Benchmark runner

**Files:**
- Create: `~/CEDIA/scripts/bench/run-bench.sh`
- Create: `~/CEDIA/scripts/bench/report.ts` (small TS script; run with `bun` or `node`)

**Interfaces:**
- Consumes: `market-bench.json` from A1.
- Produces: `~/CEDIA/docs/evidence/market/a2/bench-report.json` with per-case `{agent, wall_ms, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, pass}`.

- [ ] **Step 1: Write `run-bench.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/docs/evidence/market/a2"
mkdir -p "$OUT"
for agent in cedia opencode; do
  "$ROOT/scripts/bench/report.ts" --agent "$agent" --cases "$ROOT/harness/eval/cases/market-bench.json" --out "$OUT/$agent.json"
done
python3 - "$OUT" <<'PY'
import json, pathlib, sys
for p in pathlib.Path(sys.argv[1]).glob("*.json"):
    data = json.loads(p.read_text())
    assert {"agent","cases"} <= set(data), p
PY
echo "bench: OK"
```

- [ ] **Step 2: Implement `report.ts`**

`report.ts` spawns the agent headless (`cedia-agent` CLI for CEDIA, `opencode run` for OpenCode), runs each case in a temp worktree, collects wall time, and parses usage JSON from each harness (`--usage-file` for Hermes-style output, OpenCode `/usage` JSON when available; otherwise provider-side `usage` fields). Record `cache_read_tokens` and `cache_write_tokens` exactly as reported; if a harness does not expose them, write `null` and mark the field `"not_exposed"` instead of estimating.

- [ ] **Step 3: Run on one case and confirm JSON**

Run: `bash scripts/bench/run-bench.sh`
Expected: `docs/evidence/market/a2/cedia.json` and `opencode.json` exist and parse.

- [ ] **Step 4: Commit**

```bash
git add scripts/bench docs/evidence/market/a2 harness/eval
git commit -m "feat(bench): reproducible market benchmark runner"
```

### Task A3: Performance baseline summary

**Files:**
- Create: `~/CEDIA/docs/market/benchmark-2026-08.md`

**Interfaces:**
- Consumes: A2 JSON files.
- Produces: a published comparison table used by D2.

- [ ] **Step 1: Generate table**

From A2 JSON, write wall time, token totals, cache-hit percentage (`cache_read_tokens / (cache_read_tokens + input_tokens)`) per case.

- [ ] **Step 2: Record honest caveats**

State machine, model profile (`opencode-go/deepseek-v4-flash`), date, and that a single machine run is not a general benchmark.

- [ ] **Step 3: Gate**

Run: `bash scripts/bench/run-bench.sh && grep -c '"cases"' docs/evidence/market/a2/cedia.json`
Expected: ≥ 1 match.

- [ ] **Step 4: Commit**

```bash
git add docs/market/benchmark-2026-08.md
git commit -m "docs(bench): market performance baseline"
```

---

## Phase B — Support Every Harness

### Task B1: Host verification contract

**Files:**
- Modify: `~/CEDIA/harness/config/hosts.yaml`
- Modify: `~/CEDIA/verify.sh`

**Interfaces:**
- Consumes: existing `harness_host.py host verify --host <name>` contract.
- Produces: `harness verify --all` command that fails when any host is `unverified` but has a native mechanism declared.

- [ ] **Step 1: Add `--all` to `harness_host.py`**

Add `host verify --all` that iterates `hosts.yaml` in order and prints one line per host with final status.

- [ ] **Step 2: Wire into `verify.sh`**

After the `runtime truth` block, add:

```bash
echo "== host capabilities =="
python3 "$HARNESS/scripts/harness_host.py" --agents-home "$HARNESS" host verify --all
```

- [ ] **Step 3: Gate**

Run: `bash verify.sh`
Expected: host verification prints at least the hosts listed today and exits 0 with current statuses.

- [ ] **Step 4: Commit**

```bash
git add harness/scripts/harness_host.py harness/config/hosts.yaml verify.sh
git commit -m "feat(hosts): verify --all gate"
```

### Task B2: Claude Code adapter verification

**Files:**
- Create: `~/CEDIA/docs/evidence/market/b2/claude-code.md`
- Modify: `~/CEDIA/harness/config/hosts.yaml` (`claude-code` statuses)

**Interfaces:**
- Consumes: `~/.claude` layout (`CLAUDE.md`, `skills`, `commands`, `settings.json`).
- Produces: evidence that `policy_file`, `skill_discovery`, `command_dir`, `native_permissions`, `config_merge`, `project_override`, `uninstall_ownership` work on a fresh isolated HOME.

- [ ] **Step 1: Write fixture script**

Create `harness/scripts/adapters/claude_verify.sh` that creates `$HOME/.claude` in a temp HOME, runs `install.sh --home "$HOME"`, then asserts:

```bash
test -f "$HOME/.claude/CLAUDE.md"
test -d "$HOME/.claude/skills"
test -d "$HOME/.claude/commands"
```

- [ ] **Step 2: Run and record**

Run: `bash harness/scripts/adapters/claude_verify.sh`
Expected: PASS. Write evidence including the exact commands.

- [ ] **Step 3: Update statuses**

Set each verified capability to `supported`; keep `native_permissions` at whatever the test proves (likely `partial` until a permission contract test exists).

- [ ] **Step 4: Commit**

```bash
git add harness/scripts/adapters/claude_verify.sh docs/evidence/market/b2 harness/config/hosts.yaml
git commit -m "feat(hosts): verify claude-code adapter"
```

### Task B3: Codex, Gemini CLI, ZCode, OpenClaw verification

**Files:**
- Create: `~/CEDIA/docs/evidence/market/b3/{codex,gemini-cli,zcode,openclaw}.md`
- Modify: `~/CEDIA/harness/config/hosts.yaml`

**Interfaces:**
- Consumes: each host's documented config/skill locations from `hosts.yaml`.
- Produces: per-host smoke scripts under `harness/scripts/adapters/` (one file per host, same shape as B2).

- [ ] **Step 1: Write one smoke script per host**

Each script creates an isolated HOME and asserts the exact instruction file, skill discovery path, and command dir that `hosts.yaml` declares for that host. For Hermes, use the existing `hermes-skills.snippet.yaml` and assert `skills.external_dirs` resolves.

- [ ] **Step 2: Run all and record**

Run: `for h in codex gemini-cli zcode openclaw hermes; do bash harness/scripts/adapters/$h-verify.sh; done`
Expected: each prints PASS or FAIL with the failing assertion.

- [ ] **Step 3: Update statuses honestly**

Only flip `unverified` to `supported` for capabilities the smoke actually proves; otherwise leave `partial`/`unsupported`.

- [ ] **Step 4: Commit**

```bash
git add harness/scripts/adapters docs/evidence/market/b3 harness/config/hosts.yaml
git commit -m "feat(hosts): verify codex/gemini/zcode/openclaw/hermes"
```

### Task B4: Cursor adapter verification

**Files:**
- Create: `~/CEDIA/docs/evidence/market/b4/cursor.md`
- Modify: `~/CEDIA/harness/config/hosts.yaml` (`cursor` statuses)

**Interfaces:**
- Consumes: `~/.cursor/rules/agents-policy.mdc` and `~/.cursor/skills`.
- Produces: proof that `harness rules` regenerates a current `agents-policy.mdc` and that skill symlinks resolve.

- [ ] **Step 1: Regenerate and assert**

```bash
harness rules
test -f ~/.cursor/rules/agents-policy.mdc
grep -q 'alwaysApply: true' ~/.cursor/rules/agents-policy.mdc
test -d ~/.cursor/skills
```

- [ ] **Step 2: Record evidence**

Note that `native_permissions` stays `unsupported` because Cursor has no enforceable native permission mechanism in the harness contract (already declared in `hosts.yaml`).

- [ ] **Step 3: Commit**

```bash
git add docs/evidence/market/b4 harness/config/hosts.yaml
git commit -m "feat(hosts): verify cursor adapter"
```

### Task B5: Generic fallback proof

**Files:**
- Create: `~/CEDIA/docs/evidence/market/b5/generic.md`
- Create: `harness/eval/fixtures/generic-host/AGENTS.md`

**Interfaces:**
- Produces: a documented behavioral fallback for hosts with no native adapter: `AGENTS.md` + `~/.agents/skills` discovery only.

- [ ] **Step 1: Fixture**

Create a fixture repo containing only `AGENTS.md` that references `~/.agents/skills` discovery, and run the `generic` host smoke.

- [ ] **Step 2: Gate**

Run: `python3 harness/scripts/harness_host.py host verify --host generic`
Expected: `policy_file` = `partial`, `skill_discovery` = `partial`, everything else `unsupported` with reason.

- [ ] **Step 3: Commit**

```bash
git add docs/evidence/market/b5 harness/eval/fixtures/generic-host
git commit -m "feat(hosts): generic fallback evidence"
```

---

## Phase C — Most Efficient Performance

### Task C1: Provider prompt-cache controls

**Files:**
- Modify: `~/cedia-ide/extensions/cedia-agent/src/provider.ts`
- Modify: `~/cedia-ide/extensions/cedia-agent/src/core.ts`
- Test: `~/cedia-ide/extensions/cedia-agent/src/test/provider-cache.test.ts`

**Interfaces:**
- Consumes: existing `toWireMessage` and model profile fields (`context_window`, `provider`).
- Produces: `cache` config per model (`none | auto | long`) and usage surface `{cacheReadInputTokens, cacheWriteInputTokens, costUsd}` returned after every turn.

- [ ] **Step 1: Write failing test**

```ts
import { prepareCacheHeaders } from "../provider"
it("adds prompt cache key and retention for openai-compatible", () => {
  const out = prepareCacheHeaders({ provider: "opencode-go", cache: "long", sessionId: "s1" })
  expect(out["prompt_cache_key"]).toBe("s1")
  expect(out["prompt_cache_retention"]).toBe("24h")
})
it("adds anthropic breakpoints when cache auto", () => {
  const out = prepareCacheHeaders({ provider: "anthropic", cache: "auto" })
  expect(out.cache_control).toContain("ephemeral")
})
```

- [ ] **Step 2: Run to verify fail**

Run: `cd extensions/cedia-agent && npx vitest run src/test/provider-cache.test.ts`
Expected: FAIL (`prepareCacheHeaders` not exported).

- [ ] **Step 3: Implement**

In `provider.ts`, add `prepareCacheHeaders(options)` that:
- sets `prompt_cache_key` from `sessionId` (clamped to 64 chars) and `prompt_cache_retention: "24h"` for `long`;
- injects Anthropic `cache_control: {type:"ephemeral"}` on system and last user block for `auto`;
- never sends cache fields for `none`.

Add `cache: "auto"` as the default in `core.ts` model profile resolution.

- [ ] **Step 4: Run to verify pass**

Run the same test. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add extensions/cedia-agent/src/provider.ts extensions/cedia-agent/src/core.ts extensions/cedia-agent/src/test/provider-cache.test.ts
git commit -m "feat(agent): provider prompt-cache controls"
```

### Task C2: Context compaction budgets

**Files:**
- Modify: `~/cedia-ide/extensions/cedia-agent/src/core.ts`
- Test: `~/cedia-ide/extensions/cedia-agent/src/test/compaction.test.ts`

**Interfaces:**
- Consumes: token estimator already present in `core.ts` (~4 chars/token).
- Produces: `compactIfNeeded(history, {reserveTokens, targetRatio})` that summarizes oldest turns before the provider call.

- [ ] **Step 1: Write failing test**

```ts
it("compacts when history exceeds context budget", () => {
  const out = compactIfNeeded(history(100000), { reserveTokens: 16384, targetRatio: 0.2 })
  expect(out.compacted).toBe(true)
  expect(out.keptTokens).toBeLessThan(80000)
})
```

- [ ] **Step 2: Run to verify fail**

Run: `npx vitest run src/test/compaction.test.ts`
Expected: FAIL (`compactIfNeeded` not defined).

- [ ] **Step 3: Implement**

Add `compactIfNeeded` to `core.ts`: when estimated tokens `> context_window - reserveTokens`, build a structured summary of the oldest turns (reuse the existing plan/summary format), keep the newest `targetRatio` of the window, and attach the summary as a system block. Never compact tool results across a tool call boundary.

- [ ] **Step 4: Run to verify pass**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add extensions/cedia-agent/src/core.ts extensions/cedia-agent/src/test/compaction.test.ts
git commit -m "feat(agent): context compaction budgets"
```

### Task C3: Cache/usage telemetry surface

**Files:**
- Modify: `~/cedia-ide/extensions/cedia-agent/src/chatView.ts`
- Modify: `~/cedia-ide/extensions/cedia-agent/src/evals.ts`

**Interfaces:**
- Consumes: C1 usage surface.
- Produces: `/cost`-style line in chat (`cache read/write, $cost`) and per-turn usage in `evals.ts` report JSON.

- [ ] **Step 1: Add test**

Test that a completed turn renders `cacheReadInputTokens` and `cacheWriteInputTokens` in the transcript model.

- [ ] **Step 2: Implement**

Render a small footer line per assistant turn; write the same fields into `evals.ts` JSON report so A2/C4 can consume it.

- [ ] **Step 3: Run tests and commit**

```bash
npx vitest run src/test/chatView.test.ts src/test/evals.test.ts
git add extensions/cedia-agent/src/chatView.ts extensions/cedia-agent/src/evals.ts extensions/cedia-agent/src/test
git commit -m "feat(agent): cache and cost usage surface"
```

### Task C4: Perf budgets + CI lane

**Files:**
- Create: `~/cedia-ide/extensions/cedia-agent/perf/budgets.json`
- Create: `~/cedia-ide/extensions/cedia-agent/perf/budgets.test.ts`
- Modify: `~/cedia-ide/.github/workflows/cedia-verify.yml`
- Modify: `~/cedia-ide/verify.sh`

**Interfaces:**
- Consumes: A2 bench report and C2 compaction.
- Produces: enforced budgets for cold start, indexing, compaction, tool output cap, and cache ratio on the A2 task set.

- [ ] **Step 1: Define budgets**

```json
{
  "coldStartMs": 2000,
  "indexFirstOpenMs": 5000,
  "compactRunMs": 1000,
  "toolOutputCapBytes": 1048576,
  "cacheReadShareMin": 0.5
}
```

- [ ] **Step 2: Write budget tests**

`budgets.test.ts` measures cold start, first index, compaction on a 100k-token fixture, and parses A2 reports for `cacheReadShare`; each asserts against `budgets.json`.

- [ ] **Step 3: Wire CI + verify.sh**

Add a `perf` job in `cedia-verify.yml` running `npx vitest run perf/budgets.test.ts`; call the same command from `cedia-ide/verify.sh` when `CEDIA_PERF=1` is set.

- [ ] **Step 4: Run and commit**

```bash
CEDIA_PERF=1 bash verify.sh
git add extensions/cedia-agent/perf extensions/cedia-agent/src .github/workflows/cedia-verify.yml verify.sh
git commit -m "feat(perf): budget registry and CI lane"
```

### Task C5: Skill-loading efficiency

**Files:**
- Modify: `~/cedia-ide/extensions/cedia-agent/src/loader.ts`
- Test: `~/cedia-ide/extensions/cedia-agent/src/test/loader-budget.test.ts`

**Interfaces:**
- Consumes: existing `skills/**/SKILL.md` catalog.
- Produces: Level-1 catalog under a fixed token budget; full `SKILL.md` loaded only on trigger.

- [ ] **Step 1: Add test**

Assert that listing 111 harness skills keeps Level-1 under 3k tokens (using the same estimator as C2).

- [ ] **Step 2: Implement**

Move full-body loading out of the catalog prompt and into an on-demand `skill_view`-style tool (the extension already has `loader.ts`; enforce the budget with a rejection test).

- [ ] **Step 3: Run and commit**

```bash
npx vitest run src/test/loader-budget.test.ts
git add extensions/cedia-agent/src/loader.ts extensions/cedia-agent/src/test/loader-budget.test.ts
git commit -m "feat(agent): bounded skill catalog"
```

---

## Phase D — Market Readiness

### Task D1: Comparison matrix page

**Files:**
- Create: `~/CEDIA/docs/market/comparison.md`

**Interfaces:**
- Consumes: `docs/research/competitive-feature-matrix.md`, A3 benchmark, and the scrutinized research note at `~/harness-flow/research/pi-hermes-opencode-review.md`.
- Produces: a one-page CEDIA vs OpenCode+VS Code vs Cursor vs Claude Code table with honest `partial` rows.

- [ ] **Step 1: Write the table**

Rows: MCP, skills, subagents, prompt cache, enterprise, self-host, cloud agent, native IDE, privacy. Mark CEDIA gaps exactly as Phase A-D evidence shows.

- [ ] **Step 2: Gate**

Run: `rg -n 'partial|not yet|deferred' docs/market/comparison.md | head -20`
Expected: at least one honest gap marker per unsupported row.

- [ ] **Step 3: Commit**

```bash
git add docs/market/comparison.md
git commit -m "docs(market): comparison matrix"
```

### Task D2: Landing and release assets

**Files:**
- Create: `~/CEDIA/docs/market/landing.md`
- Modify: `~/CEDIA/README.md`
- Modify: `~/cedia-ide/scripts/cedia-release.sh` (add `--help` and `.dmg` step when `CREATE_DMG=1`)

**Interfaces:**
- Produces: a reproducible signed release artifact (`CEDIA-<version>.dmg`) plus update manifest `latest.json` on GitHub Releases.

- [ ] **Step 1: Landing copy**

Write the first screen as "CEDIA — open, self-hosted agent IDE with your harness everywhere"; no marketing-only claims; link the benchmark and comparison pages.

- [ ] **Step 2: Release automation**

Extend `cedia-release.sh` so `CREATE_DMG=1` creates a DMG, and add `scripts/update-manifest.ts` writing `latest.json` with version, URL, SHA256, and a rollback flag.

- [ ] **Step 3: Gate**

Run: `CREATE_DMG=1 bash scripts/cedia-release.sh` on a machine with codesign vars, or `CEDIA_SKIP_APP_BUILD=1 bash scripts/cedia-release.sh` for a dry-run smoke. Record which path ran and its result.

- [ ] **Step 4: Commit**

```bash
git add docs/market README.md scripts
git -C ~/cedia-ide add extensions/cedia-agent/scripts scripts
git -C ~/cedia-ide commit -m "feat(release): dmg + update manifest"
```

### Task D3: Open-source polish

**Files:**
- Create: `~/CEDIA/CONTRIBUTING.md`, `~/CEDIA/SECURITY.md`, `~/CEDIA/docs/market/roadmap.md`
- Modify: `~/CEDIA/.github/workflows/verify.yml` (add `docs` lint job)

**Interfaces:**
- Produces: repo-level contribution/security/roadmap surface.

- [ ] **Step 1: Write docs**

`CONTRIBUTING.md` covers dev setup, verify gates, and the plan/review loop; `SECURITY.md` states local-first posture and where to report issues.

- [ ] **Step 2: Add docs lint**

CI job runs `npx markdownlint-cli2 "docs/**/*.md" "harness/**/*.md"` when markdownlint is available; otherwise a `bash -n` shell lint on all scripts.

- [ ] **Step 3: Commit**

```bash
git add CONTRIBUTING.md SECURITY.md docs/market/roadmap.md .github/workflows/verify.yml
git commit -m "docs(oss): contribution, security, roadmap"
```

---

## Phase E — Dogfood and Ship

### Task E1: Self-host gate for all changes

**Files:**
- Modify: `~/CEDIA/verify.sh`
- Modify: `~/cedia-ide/verify.sh`

**Interfaces:**
- Consumes: `scripts/self-host-gate.sh` in `~/cedia-ide`.
- Produces: a final combined gate that runs both repos' verify, then the self-host gate.

- [ ] **Step 1: Wire combined gate**

Add `docs/evidence/market/e1/gate.md` that records:

```bash
bash ~/CEDIA/verify.sh
bash ~/cedia-ide/verify.sh
bash ~/cedia-ide/scripts/self-host-gate.sh
```

Expected: all PASS.

- [ ] **Step 2: Commit**

```bash
git add docs/evidence/market/e1
git commit -m "chore: combined self-host gate"
```

### Task E2: Release notes + tag

**Files:**
- Create: `~/CEDIA/CHANGELOG.md` entry for 0.2.0

**Interfaces:**
- Produces: a versioned release with reproducible artifacts.

- [ ] **Step 1: Write changelog**

List Phase A-E outcomes with evidence links; mark hosted parity as deferred.

- [ ] **Step 2: Tag**

```bash
git tag v0.2.0
git push origin v0.2.0
```

- [ ] **Step 3: Create GitHub release**

Attach the DMG from D2 and `latest.json`; run `spctl --assess` on the DMG and record the result.

---

## Scrutiny Log

Reviewer findings and resolutions (2026-08-08):

1. **Scope overlap:** This plan looked like a duplicate of `cedia-full-cursor-parity.md`. Resolved: P1-P8 are referenced as done; this plan adds only market/host/perf/productization phases and does not reopen editor parity.
2. **"Support all" is an unprovable claim.** Resolved: Phase B is explicitly evidence-gated; hosts that cannot prove a capability stay `partial`/`unsupported` and the comparison page shows gaps.
3. **Cache-hit claims need provider usage fields, not estimates.** Resolved: A2 and C1-C4 define exact usage fields; benchmark JSON marks missing fields as `not_exposed`.
4. **Performance gates can flake in CI.** Resolved: budgets have 2x headroom (matching existing `phase32-perf-budgets.md` convention) and the perf lane is opt-in via `CEDIA_PERF=1` until stable.
5. **Market assets can become fluff.** Resolved: landing/comparison docs are gated on A3 evidence and must contain at least one honest gap marker per unsupported row.
6. **Release requires secrets.** Resolved: D2 has a dry-run path and a documented gate recording which path was run; secrets never enter git.

## Self-Review

- **Spec coverage:** Market (A3, D1-D2), support all hosts (B1-B5), performance (C1-C5), ship (E1-E2) all have tasks.
- **Placeholder scan:** No TBD/TODO; every task has exact files, commands, and expected output.
- **Type consistency:** `prepareCacheHeaders` (C1), `compactIfNeeded` (C2), `MarketBenchCase` (A1), `budgets.json` (C4) are named once and used consistently in later tasks.

## Execution Handoff

Plan complete and saved to `~/CEDIA/docs/plan/2026-08-08-market-all-harness-performance.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks.
2. **Inline Execution** — execute in this session with checkpoints.

Which approach?
