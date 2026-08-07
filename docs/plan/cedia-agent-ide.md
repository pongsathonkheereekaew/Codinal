# Plan — Code-OSS fork with full Cursor-class parity

Goal: a fork of `microsoft/vscode` (MIT, the same editor base Cursor uses)
with our own agent loop and a full Cursor-class feature surface: native
agent chat/plan/diff/review, IDE-grade editing, terminal, Git/worktree,
search, LSP, provider BYOK, permissions, checkpoints, and a self-hosting
acceptance gate.

## Parity model

Cursor is not one feature; it is three surfaces that must be planned and gated
separately. A feature is only "parity" after its own gate evidence exists; the
word is never a marketing label in this repo.

| Surface | Cursor-class capability | Our implementation | Phase | Gate evidence |
| --- | --- | --- | --- | --- |
| Agent loop | Chat/composer with streaming, stop/restart, model/profile picker | `extensions/cedia-agent` view + provider adapter | 1 | scripted turn E2E |
| Agent loop | Plan mode with editable structured plan and selective approval | markdown plan + plan diff | 1 | plan→approve→apply test |
| Agent loop | Tool calls: read/write/shell/git/search/terminal; bounded output | VS Code workspace APIs + approved terminal/process runner | 1 | tool conformance tests |
| Agent loop | MCP servers (stdio/HTTP), catalog and per-project config | VS Code MCP extension API | 2 | MCP round-trip tests |
| Agent loop | Subagents/multitask, child threads, handoff | thread model in agent store | 2 | delegated task test |
| Agent loop | Checkpoints and undo of agent changes | snapshot/restore service over workspace files | 2 | restart restore test |
| Agent loop | Context sources: @files, @symbols, image input, selected text | VS Code context APIs | 2 | context projection tests |
| Agent loop | Review panel: changed files, inline diffs, accept/reject per change | diff review view + workspace edit API | 2 | accept/reject E2E |
| Agent loop | Cursor Tab-style inline completions/edits in the editor | Monaco inline edit + completion provider | 3 | inline edit E2E |
| Agent loop | Semantic codebase index and symbol-aware retrieval | local index over workspace | 2 | indexed retrieval test |
| Agent loop | Native in-program browser the agent can drive | Electron BrowserView/WebContentsView + CDP bridge | 1 | browser navigate/inspect E2E |
| Agent loop | Browser MCP for all providers | Playwright MCP server (opt-in) | 2 | browser MCP round-trip |
| Editor | Full VS Code editor: tabs, multi-cursor, code actions, rename, debugger | upstream Code-OSS untouched | 0 | upstream `yarn test` smoke |
| Editor | Integrated terminal with shell integration | upstream terminal | 0 | terminal smoke |
| Editor | Search, LSP, extensions marketplace, settings sync, keybindings | upstream Code-OSS | 0 | upstream smoke |
| Editor | Git graph, worktrees, commit/push from agent loop | VS Code git API + agent git tools | 2 | worktree E2E |
| Product | Onboarding, settings, model provider BYOK, secret storage | welcome/settings views + SecretStorage | 2 | settings E2E |
| Product | Permission model: read auto, write/exec/external approve | harness risk spine + approval UI | 1 | approval E2E |
| Product | Packaging/signing/updates for macOS | electron-builder + release workflow | 3 | signed bundle smoke |
| Product | Telemetry opt-out, privacy posture | local-only telemetry, opt-out default | 3 | policy test |

## Acceptance (in order)

1. Phase 0: fork builds, `yarn watch` opens, upstream focused test passes.
2. Phase 1: bundled `cedia-agent` completes plan → approve → tool → diff →
   apply in a scratch workspace without another editor AI.
3. Phase 2: review, MCP, subagents, checkpoints, context sources, worktrees
   pass their individual gates.
4. Phase 3: signed macOS bundle plus update path exists and passes smoke.
5. Self-hosting: the harness, pointed at this repository, implements a real
   change and `bash verify.sh` passes with that change.

## Phase 0 — Fork and dev baseline

- Fork from `~`: `gh repo fork microsoft/vscode --clone --fork-name cedia-ide --default-branch-only`, producing `~/cedia-ide`.
- Add `microsoft/vscode` as `upstream`; work on `codex/agent-ide`.
- Pin the upstream commit before local edits; keep the fork diff minimal.
- Use the upstream toolchain exactly: Node from `.nvmrc`, `yarn install --frozen-lockfile`, then `yarn watch`.

Verification: `yarn watch` opens the Electron shell; `yarn test` focused pass;
no editor-core source file changed in this phase.

## Phase 1 — Agent loop (must-have parity)

Create `extensions/cedia-agent`:

- Chat/composer view with streaming, stop, model/profile selection, and turn
  receipts.
- Plan mode as an editor-visible markdown plan; selective approval per step.
- Provider credential path is part of phase 1, not phase 2: at least one
  working OpenAI-compatible BYOK profile (or local Ollama) with
  SecretStorage-backed keys, because the agent loop cannot run without a
  provider.
- Tool executor: `read`, `write`, `shell`, `git status/diff`, `search`, and
  bounded terminal output, all behind the harness risk spine.
- Native browser: Electron's bundled Chromium via a browser panel and CDP
  bridge; no Chromium/Firefox/BrowserOS fork (see ADR-0006).
- Provider adapter: OpenAI-compatible HTTP streaming, BYOK profile config,
  provider availability status, and profile picker.
- Provider profiles come from `harness/config/agent.yaml`; switching models is
  a one-field change (`active_model`) consumed by `harness agent check`.
- Apply flow: agent writes a session branch, user reviews diff, user
  accepts/rejects each change, then apply-back to the working tree; full
  worktree isolation arrives with the phase 2 Git gate.
- Always-on instruction source: read this repo's `harness/AGENTS.md`,
  standards, and skills (read-only install path).

Verification: extension unit tests + scripted E2E in a scratch workspace.

## Phase 2 — Cursor-class depth

Add in this order:

1. Review panel with per-file accept/reject.
2. MCP client + catalog.
3. Semantic codebase index and context sources (`@file`, `@symbol`, image,
   selection).
4. Subagents/multitask and handoff.
5. Checkpoints + restart recovery.
6. Git graph/worktree integration.
7. Settings/onboarding and provider management.

Each item gets its own gate test before the next starts. No item is marked
complete on UI presence alone.

## Phase 3 — Product shell

- Decide GPUI/Rust disposition only here: keep as diagnostic shell, repurpose
  as optional engine, or delete.
- Electron packaging, signing, notarization, and update feed.
- Telemetry policy, privacy posture, and opt-out.
- Release workflow mirroring the current `release.yml` Rust gates.

## Self-hosting loop (cross-cutting)

Phase 1 is built by this Codex session (the harness is not yet self-hosting).
Starting at phase 2, each phase's real change to this repository is authored
by `cedia-agent`, then verified with `bash verify.sh`.

## Repository boundaries

- `~/cedia-ide` owns the editor fork, its bundled `extensions/cedia-agent`,
  packaging, and release workflow.
- `~/cedia-browser` owns the BrowserOS fork (AGPL-3.0) as the agentic
  browser layer; the IDE talks to it over MCP (`cedia-browser`).
- This repo (`CEDIA`) remains the SSOT for policy, standards, skills,
  and the acceptance/verify gates; the extension reads it read-only.
- Do not copy harness content into the fork; install/symlink it.

## Guardrails

- Keep the fork diff minimal; never rewrite editor internals in phases 1-2.
- Do not claim Cursor parity without the gate evidence row in this plan.
- Do not delete the GPUI/Rust baseline until phase 3 has a working replacement.
- Keep disk hygiene: `target/` and editor build dirs are gitignored and cleaned
  before handoff (this repo dropped from ~25 GB to ~82 MB by removing Rust
  `target/` and venvs).
- Keep VS Code MIT notices; no Microsoft product branding for the custom app.

## Scrutiny log

Reviewer findings and resolutions (2026-08-07):

1. **Ambiguity:** "exactly like Cursor" without a matrix made the scope
   unmeasurable. Resolved with the parity model above and per-phase gates.
2. **Scope ordering:** forking first delays the agent loop. Resolved by keeping
   the fork diff minimal and making the extension the primary deliverable from
   phase 1; the fork exists so the shell and UX stay under our control.
3. **GPUI/Rust dual-maintenance risk:** resolved by deferring the disposition
   decision to phase 3 instead of carrying both shells indefinitely.
4. **Missing security/checkpoint/product gates:** added explicit rows for
   permission, secret, checkpoint, packaging, telemetry, and updates.
5. **Unverifiable marketing claims:** parity claims now require a named gate
   artifact; UI presence alone is not evidence.
6. **Phase-1 provider gap:** the agent loop cannot run without credentials, so
   BYOK/Ollama secret storage moved from phase 2 into phase 1.
7. **Worktree inconsistency:** phase 1 apply flow now means a session branch
   with diff review; full worktree isolation moved to phase 2 where the Git
   tooling gate lives.
8. **Missing Cursor Tab/index:** added inline completions and semantic index
   as explicit phase 2/3 gates instead of leaving them implied.
9. **Self-hosting sequencing:** phase 1 is built by this session; the harness
   only starts authoring its own changes at phase 2.

## Progress (2026-08-07)

- Phase 0 done: VS Code fork builds with `npm install` + `npm run watch`
  (client/extensions/copilot compile with 0 errors), dev shell launcher at
  `~/cedia-ide/scripts/cedia-dev.sh`.
- Phase 1 core done in `extensions/cedia-agent`: chat/composer webview,
  streaming OpenAI-compatible provider from `agent.yaml`, plan mode, approved
  read/write/shell/git/search tools, BrowserOS MCP browser calls, review
  command. Extension compile + 4 unit tests pass.
- Browser layer wired through MCP (`cedia-browser` →
  `http://127.0.0.1:9200/mcp`).
- Agent loop proven headlessly: extension test drives user → tool call →
  approval → write → finish against a local SSE provider; 6 extension tests
  pass.
- BrowserOS MCP server (`browseros-claw-server-rs`) compiles and starts its
  SQLite migrations, but requires the BrowserOS Chromium fork for CDP
  (`Browser.getTabs`); stock Chrome/Brave cannot seed it. Building that
  Chromium fork needs ~100 GB and is deferred. Until then, BrowserOS remains
  the primary browser layer; a Playwright MCP fallback can be enabled in
  `agent.yaml` for local browser tool coverage.
- Extension tests now prove the full headless agent loop (7 tests): streaming
  provider, tool-call merge, approved write, and an MCP HTTP browser call.
- Browser tool now speaks MCP streamable HTTP correctly (initialize +
  session-id + notifications/initialized + tools/call); 8 extension tests pass.
- Review workflow gained per-file revert; apply creates a session branch;
  snapshot/restore covers checkpoints.
- `harness agent list-mcp` exposes configured MCP servers to the extension;
  `cediaAgent.status` shows active model + workspace + MCP servers.
- Remaining: live provider round-trip (needs a real API key), BrowserOS fork
  Chromium build (~100 GB) or verified fallback, full review/MCP/checkpoints/
  apply parity, packaging, and the self-hosting gate.
