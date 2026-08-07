---
number: 0005
title: Replace GPUI shell with a Code-OSS fork and build an in-house agent harness
status: proposed
date: 2026-08-07
deciders: user (product owner) + grilling session
supersedes: []
---

# ADR-0005 — Code-OSS fork agent IDE

## Context

CEDIA's GPUI desktop shell reached a passing Rust-only baseline
(`verify.sh` + ~445 Rust tests), but the owner wants a Cursor-like result:
a fork of the real editor core with an in-house agent harness, using the best
existing tool per domain instead of a custom Rust UI. The success criterion is
self-hosting: this harness writes and refactors this repository end-to-end
without relying on another editor AI product.

`get-bb/bb` was evaluated as a possible base. It is an MIT agent-orchestration
workspace (Electron shell + React web app + server + host daemon) that drives
external agents (Claude Code, Codex CLI, Pi, Cursor via ACP). It has no
VS Code-style editor core, terminal, or LSP engine, so it cannot by itself
produce the requested "exactly like Cursor" IDE result.

## Decisions

### D1 — Editor base: fork Code-OSS (microsoft/vscode, MIT)

- Use the upstream VS Code repository as the editor core, exactly the pattern
  Cursor uses.
- Keep the fork in a separate repo (`cedia-ide`) rather than nesting the
  ~1.3 GB upstream history inside this harness repo.
- This repo (`harness-flow`) remains the harness/policy/skills SSOT.

### D2 — First implementation surface: bundled agent extension

- Start inside the fork as a bundled extension (`extensions/cedia-agent`)
  rather than rewriting editor internals.
- The agent loop is ours: conversation model, plan mode, tool execution,
  policy approval, diff review, and apply. It calls provider APIs directly and
  does not depend on Cursor/Claude Code/Codex editor features.
- Existing Rust runtime is not a v1 dependency. Keep it in this repo as an
  optional future engine instead of deleting it now.

### D3 — bb is inspiration, not a base

- Adopt bb's useful ideas later (threads, orchestration, CLI/SDK parity) only
  after the editor fork and agent extension prove the self-hosting loop.
- Do not embed bb's server/daemon model into the editor fork in phase 1.

### D3a — Browser layer: BrowserOS (AGPL-3.0), not Chromium/Firefox engines

- CEDIA ships a full agentic browser surface. Fork `browseros-ai/BrowserOS`
  (TypeScript, AGPL-3.0) as the browser layer in a separate repo
  (`~/cedia-browser`), and connect it to the IDE and agent through MCP.
- Do not fork Chromium (BSD-3, ~65 GB source) or Firefox (~5.2 GB source);
  they are full browser engines and are the wrong weight for an agent
  browser surface. VS Code's built-in webview is not a browser product and
  does not cover tabs/navigation/DOM-to-agent by itself.

### D4 — Self-hosting is the acceptance gate

- "Done" means this fork + bundled harness can plan, execute, review, and apply
  real changes to this repository, verified by its own test suites.
- Editor AI products are not used in the agent loop; terminal/provider CLIs may
  be used only as user-approved tools.

## Consequences

- Large upstream merge/update burden (VS Code is a fast-moving upstream).
- Electron/extension/signing maintenance replaces GPUI maintenance.
- The existing GPUI code stays in history and can be removed later after the
  fork reaches parity, or kept as a lightweight diagnostic shell.
