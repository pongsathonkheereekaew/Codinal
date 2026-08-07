# CEDIA → Cursor: full docs parity plan

Status: proposed (2026-08-07). Source of truth: `docs/evidence/parity/cursor-docs-audit.md`
(crawled from `cursor.com/docs/sitemap.xml`, 200 URLs; 35 core pages rendered).
Every row in that audit is a requirement here. A row is "done" only when its
gate artifact exists (test, E2E, or measured evidence) and `verify.sh` passes.

## Intent

Make CEDIA able to complete the workflows Cursor documents, for a self-hosted
local IDE. **Definition of done:** every local IDE surface row in
`cursor-docs-audit.md` reaches its gate; hosted surfaces (Cloud Agents,
Bugbot/PR automation, marketplace, enterprise SSO, integrations) are either
approximated locally or deferred with a recorded reason. This plan does not
claim hosted-infra parity.

## Simpler-alternative pass (mandatory)

- For every capability, prefer the existing VS Code / BrowserOS / harness
  surface before writing new code:
  - editor, terminal, diff, search, LSP, debugger, extensions → upstream
    Code-OSS (already in fork).
  - browser automation, console/network, session persistence → BrowserOS MCP
    (already connected; expand tool mapping).
  - skills/rules/hooks → harness `skills/`, `standards/`, `commands/` SSOT;
    extension should load them rather than duplicate.
  - permissions/sandbox → implement a CEDIA `permissions.json`/`sandbox.json`
    that mirrors Cursor's file contract and maps to the harness risk baseline.
- Anything that is a marketing/usage-pool/team feature (pricing pools,
  leaderboards, marketplace) is deferred and documented, not faked.
- Hosted-only surfaces are deferred with reason in P8, not silently dropped.
  A future "match all including hosted" plan must add infra/ops phases.

## Phase plan

Each phase ends with: extension tests green, `cedia-ide/verify.sh` PASS,
`CEDIA/verify.sh` PASS, and evidence committed under
`docs/evidence/parity/<phase>/`. Phases are ordered by dependency and value
for self-use; later phases may be deferred by owner decision, but a deferral
must be recorded here, not silent.

### P1 — Agent loop completeness (missing core rows)

Requirements:

- Remove the fixed `MAX_TOOL_ROUNDS = 10` loop cap (`src/core.ts:28`) as the
  only stop condition. Parity is "no arbitrary task cap"; safety is a runtime
  budget, not a round count: `cediaAgent.maxToolRounds` (default 50),
  `cediaAgent.maxToolTokens` (default 200k), and stop/cancel always win.
  Gate: loop test up to the configured cap, plus a budget-exhausted stop test.
- Web search tool: provider-backed search (DuckDuckGo HTML as fallback, no
  API key) with bounded output and approval; results feed context.
- Fetch Rules tool: load `AGENTS.md`, `harness/standards/*`, project rules
  `.mdc`, and `rules/*.md` by description/type; add to system prompt.
- Clarifying questions: when plan/ambiguous prompt, agent asks up to N
  questions before tool use; UI renders question blocks and resumes on answer.
- Queued messages: chat input queue while running; drain after turn end.
- Auto-checkpoints: before each write/shell tool, snapshot workspace diff to
  a local timeline (limit 20); restore from chat timeline rows.
- Image input payload: extend `ChatMessage.content` to OpenAI content parts
  (`{type:"text"}`, `{type:"image_url", image_url:{url:dataURL}}`) in
  `provider.ts toWireMessage`; vision-capable profiles receive the image
  part; vision-less profiles get a text note with a local temp path.

Gates:

- `agent-loop.test.ts` covers >10 rounds, web search fixture, clarifying
  question flow, queued messages, auto-checkpoint restore, image payload
  serialization.
- E2E: send → queue → drain → checkpoint restore.

### P2 — Modes + agent review depth

Requirements:

- Mode model: `agent | plan | ask | debug`; Shift+Tab / `Cmd+.` cycles; mode
  stored per session. Modes are a permission mask passed to `ToolExecutor`
  (ask = read/search only; debug = read + write + shell + log tool), not a
  UI-only flag.
- Debug Mode design: local instrumentation server is a file-based log sink
  (`.cedia/debug/<session>/logs.jsonl`) written by a `debug_log` tool; agent
  adds log statements, asks user to reproduce, reads logs, fixes, removes
  instrumentation. No external server daemon in v1.
- Agent Review: auto-run after task (config), quick/deep depth levels, diff
  review panel gains "review all changes" against main.
- Agent Review design: quick = heuristic pass (lint-style checks + diff
  summary); deep = agent loop with `code-review` skill over the diff; both
  report findings into the review panel with accept/reject. Auto-run is
  config-gated, manual by default.
- Plan persistence: save plan to workspace `.cedia/plans/` + reopen list.
- Design Mode approximation: in browser panel, element pick via BrowserOS
  `evaluate` returning element + screenshot; add selection to prompt.
- Agents Window approximation: multi-root view listing open workspaces,
  parallel agent sessions, new diffs list; local-only.

Gates:

- mode switch E2E, ask mode read-only test, debug-mode instrument→fix fixture,
  plan persist E2E, agents-window parallel sessions test.

### P3 — Tools depth: search, browser, worktrees, canvases

Requirements:

- Search: regex grep tool (Instant Grep-like) with word-boundary + regex,
  encrypted-path note (obfuscate absolute paths in UI logs), Explore subagent
  auto-spawn for broad queries (uses subagent runner).
- Browser: map full BrowserOS tool set (click/type/scroll/screenshot/console/
  network via `read format=console`, tabs, session persistence is BrowserOS
  native); agent consumes screenshots as images.
- Worktrees: `git worktree add` per task with `.cedia/worktrees.json`
  equivalent config; apply-back / PR flow; multi-root note.
- Canvases: markdown/HTML artifacts rendered beside chat (webview panel),
  saved under `.cedia/canvases/`, reopen list, rerun source. Canvas source is
  a runnable file (`canvas.md` + optional `run.sh`); rerun executes the script
  and refreshes the render. Gate requires a rerun producing changed output.

Gates:

- search regex fixture, Explore subagent test, browser console/network fixture
  against local server, worktree create/apply E2E, canvas create/reopen E2E.

### P4 — Security: permissions.json, sandbox.json, run modes, trust

Requirements:

- `permissions.json` reader (user + workspace, JSONC): `mcpAllowlist`,
  `terminalAllowlist`, `autoRun` natural-language instructions; merge into
  harness risk baseline; watch-file reload.
- `autoRun` v1 mapping: natural-language allow/block instructions are matched
  with keyword/pattern rules (e.g. "every AWS CLI command" → block pattern);
  an LLM classifier is an opt-in later step. This is a guardrail, matching
  Cursor's own "best-effort" framing.
- `sandbox.json`: `workspace_readwrite` default, `workspace_readonly`,
  `additionalReadonlyPaths`, `additionalReadwritePaths`, `networkPolicy`
  default deny, `disableTmpWrite`; enforce in shell executor (zsh wrapper or
  `sandbox-exec` on macOS when available; degrade to deny-by-default network
  env).
- Run Modes: `auto-review | allowlist | run-everything`; auto-review uses a
  deterministic classifier (rule-based first; LLM classifier optional) and
  surfaces approval fallback. Not a hard security boundary (documented).
- Sandbox honesty: this is a guardrail approximation, not OS sandbox parity.
  Enforce in order: macOS `sandbox-exec` profile when available; else
  workspace-relative path allowlist + `deny` network env + `ulimit`; always
  label "best-effort, not a security boundary" (same disclaimer Cursor makes
  for auto-review). A true OS sandbox across platforms is a separate
  workstream and is deferred with reason.
- `.cursorignore` equivalent: `.cediaignore` + `.cursorignore` reading.
- Workspace trust: prompt on untrusted workspace; restricted mode disables
  agent tools.

Gates:

- unit tests for permission merge/precedence, sandbox network deny fixture,
  run-mode allowlist/deny behavior, ignore file, trust prompt E2E.

### P5 — Prompting + context

Requirements:

- @ mentions: files/folders, terminals (attach active terminal output), past
  chats (persisted to `.cedia/chats/*.json` so they survive reload), git diff
  (working state / branch), browser context.
- Context ring + breakdown: compute token estimate per category
  (system/tools/rules/skills/MCP/subagents/conversation); render ring + tray.
- Voice input: investigate a stable dictation API (VS Code Speech / native
  macOS). If none is stable, defer with reason; do not ship a fake mic UI.

Gates:

- mention resolution E2E per category, context breakdown unit test (token
  estimator fixture), voice enabled/absent path.

### P6 — Subagents + customization (skills, commands, hooks, plugins-lite)

Requirements:

- Subagents: custom definitions under `.cedia/subagents/*.md`; parallel
  foreground/background; isolated context (already per-session).
- Skills: load harness `skills/**/SKILL.md` into agent catalog; `/` invocation
  list; progressive load = include name+description only until invoked.
- Commands: `/` slash commands from `harness/commands/*` + `.cedia/commands/*`.
- Rules: `.cursor/rules/*.mdc` reader (frontmatter description/globs/
  alwaysApply) + user rules; team rules deferred.
- Hooks: implement the hook contract subset used by self-use:
  `sessionStart/End`, `preToolUse/postToolUse`, `beforeShellExecution`,
  `beforeMCPExecution`, `beforeFileEdit`, `subagentStart/Stop`; run scripts
  from `.cedia/hooks.json`; block/modify semantics.
- Hook contract: JSON-RPC over stdio, 15 s timeout, exit-code failures are
  logged and surfaced; hook scripts are trusted-user scripts (same trust
  class as Cursor); block results stop the tool and render a reason.
- Plugins-lite: a plugin = directory with `plugin.json` bundling skills/
  commands/rules/hooks/MCP; install from local dir; marketplace deferred.
- Customize page: webview listing components by scope (user/workspace), with
  enable/disable; team scope deferred.

Gates:

- skills catalog + invocation test, commands test, `.mdc` parse test, hook
  lifecycle test (preToolUse blocks), plugin install test, customize E2E.

### P7 — CLI, SDK, evals

Requirements:

- CLI: `cedia` command with `agent | plan | ask` modes, `-p` print mode,
  `--model`, `--output-format`, CI-friendly exit codes; interactive TUI
  minimal (prompt loop), shell/ACP deferred with reason.
- SDK: `@cedia/sdk` TypeScript: run agent loop, typed message events, final
  `RunResult`; local runtime only. Simpler alternative adopted: SDK is a thin
  wrapper over the existing `AgentSession` core (no separate runtime
  process), built after CLI proves the contract.
- Evals: `scripts/eval-run.ts` feeding tasks and scoring pass/fail on
  `verify.sh`; harness `cases.json` reuse.

Gates:

- CLI print-mode E2E on a fixture repo, SDK run test, eval run produces
  evidence JSON.

### P8 — Deferred with explicit reason (not implemented locally)

- Cloud Agents / computer use / remote desktop / mobile / web: requires
  hosted VM + connectivity infra; out of scope for self-hosted local IDE.
- Bugbot / Security Agents / PR Routing / Merge Queue / Cursor Review:
  cloud PR automation; local approximation = `code-review` skill + CLI
  `git` review script (harness already has `review-pr`).
- Integrations (Slack/Teams/Jira/Linear/Notion/GitHub/etc.): use MCP servers
  when user adds them; no first-party connectors.
- Enterprise SSO/SCIM/admin API/pooled usage/privacy modes: infra + licensing;
  out of scope.
- Marketplace/leaderboards/shared canvases/pricing pools: product infra;
  out of scope.

## Cross-cutting invariants

- `bash verify.sh` green in both repos after every phase.
- Extension tests stay under ~5 s (current 37 ≈ 2 s leaves headroom); axe 0
  violations on new views.
- Every capability has a named gate artifact; no "UI presence only" claims.
- Self-hosting: at least one real repo change per phase authored by CEDIA's
  own agent and verified.
- Security rows are implemented as best-effort guardrails and labeled as such
  (mirrors Cursor's own disclaimer for auto-review).

## Risks and guardrails

- Scope is intentionally large; phase order favors self-use value. Deferring a
  phase is allowed only via this doc (owner decision), not silently.
- No hard security boundary claims: sandbox/run modes are guardrails.
- BrowserOS is the browser engine; avoid reimplementing CDP/console/network.
- VS Code upstream churn: keep changes in the extension until P7+.
- Voice/Web-search/classifier may use external services; make them opt-in.
- P1 cost: removing the round cap must land with the token/cost budget in the
  same change, or hosted-provider spend is unbounded.
- Dependencies: P3 Explore subagent depends on the existing subagent runner
  (P6); sequence P3 after P6's runner hardening or reuse the current runner
  with a documented note.

## Immediate next step

Start P1: remove hard tool cap, add web search + fetch rules + clarifying
questions + queued messages + auto-checkpoints + image payload, then P1 gates.

## Execution status (2026-08-07)

- P1 done: budget-based loop (50 rounds / 200k tokens), web search, fetch
  rules, clarifying questions, queued messages, auto-checkpoints, real image
  payload; 43 tests.
- P2 done: agent/plan/ask/debug modes (permission mask), debug log tool,
  Agent Review quick/deep, plan persistence, Agents Window; 45 tests.
- P3 done: regex search, explore, worktrees, canvases, BrowserOS action
  mapping; 49 tests.
- P4 done: permissions.json, sandbox.json, run modes (auto-review/allowlist/
  run-everything), ignore file, workspace trust; 55 tests.
- P5 done: mentions (past/terminal/git/file), context ring + token
  breakdown, past-chat persistence, voice detection (deferred backend); 57
  tests.
- P6 done: skills/commands/rules/subagents loader, hooks lifecycle,
  plugins-lite, customize view; 61 tests.
- P7 done: CLI modes + JSON output, SDK wrapper, evals runner; 63 tests.
- P8: hosted surfaces deferred with reason (Cloud Agents/computer use,
  Bugbot/PR automation, marketplace/leaderboards, enterprise SSO/admin,
  first-party integrations). Local approximations: code-review skill +
  MCP connectors as users add them.

Remaining honest gaps for true "all docs" parity: hosted infra, real
embedding model (keyword-hash fallback only), OS-level sandbox (guardrail
only), stable voice dictation, full plugin marketplace. Each is recorded as
deferred with reason rather than silently dropped.
