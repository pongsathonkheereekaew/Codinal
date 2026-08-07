# Cursor docs audit — CEDIA parity matrix

Date: 2026-08-07. Sources: crawled from `https://cursor.com/docs/sitemap.xml`
(200 URLs) and rendered 35 core app pages via headless Chromium. CEDIA status
is based on the committed extension source (`~/cedia-ide/extensions/cedia-agent`)
and harness config (`~/CEDIA`).

Status legend: **match** = equivalent user-facing behavior verified;
**partial** = exists but materially weaker or only a scaffold; **missing** =
not present.

## Agent core

| Cursor doc capability | Source | CEDIA | Status |
| --- | --- | --- | --- |
| Sidepanel agent chat, streaming, stop, model picker | agent/overview, prompting | Chat webview with streaming/stop/model picker | partial |
| Unlimited tool calls in a task | agent/overview | `MAX_TOOL_ROUNDS = 10` | missing |
| File search, read (incl. images), edit, shell | agent/overview | read/write/shell/search tools; image paste is text-only context | partial |
| Web search | agent/overview | no web search tool | missing |
| Fetch rules by type/description | agent/overview | reads `AGENTS.md` only | missing |
| Image generation | agent/overview | no | missing |
| Ask clarifying questions mid-task | agent/overview | no | missing |
| Queued follow-up messages | agent/overview | no | missing |
| Checkpoints: auto-snapshot + restore from timeline | agent/overview | manual snapshot/restore commands, no auto checkpoint timeline | partial |

## Agent modes

| Cursor doc capability | Source | CEDIA | Status |
| --- | --- | --- | --- |
| Plan Mode: clarifying questions, research, editable plan, build when ready | agent/plan-mode | plan text + per-step approve/reject; no clarifying questions, no plan persistence | partial |
| Agent Review: local diff review, auto/manual, quick/deep | agent/agent-review | manual diff review panel with accept/reject/apply | partial |
| Debug Mode: hypotheses, instrumentation, reproduce, logs, fix | agent/debug-mode | no | missing |
| Design Mode: browser element select/draw/voice | agent/design-mode | no | missing |
| Agents Window: multi-workspace, parallel agents, new diffs, cloud/local | agent/agents-window | no | missing |
| Mode rotation Shift+Tab | reference/keyboard-shortcuts | no modes | missing |

## Tools

| Cursor doc capability | Source | CEDIA | Status |
| --- | --- | --- | --- |
| Terminal runs in your terminal + sandbox | agent/tools/terminal | shell tool spawns zsh, no sandbox | partial |
| Run Modes: Auto-review / Allowlist / Run Everything + classifier | agent/security/run-modes | approval-only prompts | missing |
| Browser: native pane/window, click/type/scroll/screenshot/console/network, session persistence | agent/tools/browser | BrowserOS/Playwright MCP navigate + embedded panel; no console/network/session in agent | partial |
| Search: Instant Grep regex + embeddings, Explore subagent, encrypted paths | agent/tools/search | keyword-hash index (explicitly non-semantic), no subagent auto-spawn | missing |
| Canvases: interactive artifacts next to chat, share/iterate | agent/tools/canvas | no | missing |
| Worktrees: isolated checkouts, worktrees.json | configuration/worktrees | session-branch apply only | missing |

## Security and permissions

| Cursor doc capability | Source | CEDIA | Status |
| --- | --- | --- | --- |
| Read/search auto; edits auto except config files; terminal requires approval by default | agent/security | read auto; write/shell require approval | partial |
| MCP connection approval + per-call approval + allowlist | agent/security, mcp | per-call approval; no connection approval or allowlist | partial |
| Network requests restricted to GitHub/direct-link/search | agent/security | agent has arbitrary fetch only through shell | partial |
| `.cursorignore` / ignore file | reference/ignore-file | no ignore file | missing |
| `permissions.json`: mcp/terminal allowlists + autoRun | reference/permissions | harness `permission_baseline` in config; no JSON file | partial |
| `sandbox.json`: workspace read/write/readonly, network policy, tmp | reference/sandbox | no sandbox | missing |
| Workspace trust | agent/security | no | missing |

## Prompting and context

| Cursor doc capability | Source | CEDIA | Status |
| --- | --- | --- | --- |
| @ mentions: files/folders, terminals, past chats, git diffs, browser | agent/prompting | @ files only | partial |
| Image input: drag/paste screenshots to vision models | agent/prompting | paste stored as text note, not image payload | missing |
| Voice input | agent/prompting | no | missing |
| Context ring + token breakdown (system/tools/rules/skills/MCP/subagents) | agent/prompting | no | missing |
| Switch model mid-conversation | agent/prompting | model picker per session | partial |

## Subagents and customization

| Cursor doc capability | Source | CEDIA | Status |
| --- | --- | --- | --- |
| Subagents: isolated context, parallel, foreground/background, custom definitions | subagents | basic background runner, no custom defs/parallel | partial |
| Rules: project `.mdc` (description/globs/alwaysApply), user, team, AGENTS.md | rules | `AGENTS.md` only | partial |
| Hooks: session/tool/subagent/shell/MCP/file lifecycle, block/modify | hooks | no | missing |
| Plugins: bundle rules/skills/agents/commands/MCP/hooks, marketplace | plugins, customize-cursor | one bundled extension; no plugin runtime/marketplace | missing |
| Skills: SKILL.md standard, discovery, progressive load, `/` invocation | skills | harness skills exist for agents; extension does not load them | partial |
| Commands: `/` slash commands | customize-cursor | no | missing |
| Customize page with scopes | customize-cursor | static settings panel | missing |

## MCP

| Cursor doc capability | Source | CEDIA | Status |
| --- | --- | --- | --- |
| stdio / SSE / streamable HTTP transports | mcp | stdio + streamable HTTP | partial |
| Tools, Prompts, Resources, Roots, Elicitation | mcp | tools only | partial |
| `mcp.json` + Customize management + per-call approval | mcp | harness `agent.yaml` + `harness agent list-mcp` | partial |
| MCP allowlist | mcp | no | missing |

## Editor, models, CLI, cloud

| Cursor doc capability | Source | CEDIA | Status |
| --- | --- | --- | --- |
| Keyboard shortcuts: Cmd+I/L, Cmd+E, Cmd+., Cmd+/, Tab/Shift+Tab, accept/reject all, clipboard context | reference/keyboard-shortcuts | Tab/Esc/Alt+Tab inline + Cmd+Alt+C R/C only | partial |
| Models: frontier multi-provider, Router, BYOK, usage pools | models-and-pricing | 6 profiles from agent.yaml, DeepSeek verified | partial |
| CLI: interactive `agent`, print mode, modes, ACP, CI | cli/overview | headless self-host CLI (print-like), no interactive/shell/ACP | partial |
| Cloud Agents: computer use, artifacts, remote desktop, mobile/web | cloud-agent/capabilities | no | missing |
| Evals/SDK: run agent loop in harness, typed streams | evals | no SDK | missing |
| Bugbot / Security Agents / PR Routing / Cursor Review / Merge Queue | bugbot, security-agents, approval-agents, cursor-review | no | missing |
| Integrations: GitHub/GitLab/Bitbucket/Azure, Slack/Teams/Jira/Linear/Notion, Xcode/JetBrains | integrations/* | no | missing |
| Enterprise: SSO/SCIM, admin API, pooled usage, privacy modes | enterprise/* | no | missing |

## Verdict

**No — CEDIA does not match all Cursor app capabilities.** It matches or
partially matches the core local agent loop, diff review, inline edit, and MCP
surfaces, but most Cursor-specific surfaces are missing: web search, image
generation, clarifying questions, queued messages, unlimited tool loops,
auto checkpoints timeline, Agent Review auto/deep, Debug Mode, Design Mode,
Agents Window, Canvases, worktrees, sandbox/run modes/classifier,
permissions.json/sandbox.json, hooks, plugins, marketplace, skills loading,
voice, context ring, Cloud Agents/computer use, SDK/evals, Bugbot/security
agents/PR routing, integrations, and enterprise controls.

Realistic framing: CEDIA is a credible local coding-agent IDE baseline (self-
hosted, verified), not a full Cursor clone. "Match all" requires closing the
missing rows above, which is multi-quarter work even for a team; for a
self-use product the highest-value next targets are: unlimited/auto tools,
web search, auto checkpoints, Agent Review depth, sandbox + run modes,
skills/commands loading, and context ring.

## Evidence

- Crawled pages: `/tmp/cursor-rendered/*.html` (35 pages) + sitemap
  `/tmp/cursor-doc-urls.txt`.
- CEDIA: extension tests 37, GUI E2E exit 0, verify PASS both repos;
  source paths in `~/cedia-ide/extensions/cedia-agent/src`.
