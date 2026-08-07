---
number: 0006
title: Native in-program browser for the Aidel agent
status: proposed
date: 2026-08-07
deciders: user (product owner)
supersedes: []
---

# ADR-0006 — Native in-program browser

## Context

Aidel (the Code-OSS fork) needs a native browser surface the agent can drive,
with MCP and other tool integrations, while staying lightweight. The owner
asked to evaluate forking `browseros-ai/BrowserOS`, `chromium/chromium`, or
`mozilla-firefox/firefox`.

## Facts from upstream repos (2026-08-07)

| Option | Size | License | Embeddability |
| --- | --- | --- | --- |
| BrowserOS | ~199 MB repo; separate agentic browser app | AGPL-3.0 | Not a library; secondary browser app with MCP board |
| Chromium mirror | ~65 GB repo | BSD-3-Clause | Full browser engine; huge fork/build burden |
| Firefox | ~5.2 GB repo | NOASSERTION | Not designed as an embeddable in-IDE component |
| Electron (already in Code-OSS) | bundled Chromium | BSD/MIT dependencies | Native BrowserView/WebContentsView + CDP |

## Decision

Use Electron's bundled Chromium as the native browser. Code-OSS already ships
Electron 42.x, so this adds no browser binary, no fork, and no new license
surface. The agent drives it through a local Chrome DevTools Protocol bridge,
and AI/MCP integration uses a Playwright MCP server (disabled by default, opt-in
per project).

- Do not fork Chromium or Firefox.
- Do not vendor BrowserOS code: AGPL-3.0 would force license changes for a
  derivative product. BrowserOS may inform UX (live dashboard, session replay)
  only.
- A "browser for agents" can be implemented later as a separate companion
  surface if needed; the in-IDE browser stays first.

## Consequences

- Zero extra browser runtime, smaller install and update surface.
- Browser state and logins need a secure profile directory and explicit user
  approval for navigation and network actions.
- Session replay/audit (BrowserOS-style) is a later phase, not v1.
