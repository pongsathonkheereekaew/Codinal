# CEDIA → Cursor parity roadmap (including UI/UX)

Status: proposed (2026-08-07). This plan supersedes the generic parity table in
`docs/plan/cedia-agent-ide.md` and adds the UI/UX work needed to match the
Cursor app experience, not just its feature list.

## Definition of "match"

CEDIA matches Cursor when a user can complete the same agent-driven coding
workflows with equivalent speed, confidence, and discoverability:

1. Open CEDIA on a real repo, pick a provider, and start a task with zero
   tutorial text.
2. Plan → approve → tool execution → diff review → accept/reject → apply is
   one continuous, keyboard-friendly flow.
3. Inline agent edits behave like Cursor Tab: suggest, Tab to accept, Esc to
   reject, without losing context.
4. Sidebar/chat/browser/permissions state is always visible, stable, and
   never overlaps or shifts layout.
5. Every claimed feature has a gate artifact (screenshot, E2E test, or
   measured interaction) in this repo.

## Gap analysis (from verified current state)

| Surface | Cursor | CEDIA today | Gap |
| --- | --- | --- | --- |
| Chat/composer | rich multi-turn, streaming, stop, model picker, history | webview chat with streaming/stop/model picker | no conversation history UI, no rich message blocks, no image input |
| Plan mode | editable structured plan, per-step approval | markdown plan command | not editable inline, no per-step approval |
| Diff review | inline diff, per-file/per-hunk accept/reject | `review` command opens diff text | no inline accept/reject UI |
| Cursor Tab | ghost-text inline edit, Tab/Esc | symbol completion only | no inline edit suggestion UX |
| Semantic context | embedding index, @-mentions | local word/symbol index | no embeddings, no @-mention picker |
| Browser | embedded agent browser | BrowserOS via MCP (separate app) | not embedded in IDE chrome |
| Permissions | contextual approval UI | modal warning prompts | no approval queue/audit panel |
| Onboarding/settings | polished provider setup | minimal commands | no welcome/settings views |
| Theme/UX | refined native shell | stock Code-OSS + custom chat | design token layer + shell polish |

## UX principles

- **Keyboard-first**: every agent action reachable without mouse; standard
  VS Code keybindings; Tab/Esc for inline edits.
- **State is visible**: running turn, pending approval, active model, MCP
  status, dirty changes always shown without modal blocking unless required.
- **Calm density**: workbench-style, not marketing-style. No hero panels,
  decorative gradients, or oversized type in tool surfaces.
- **Theme-native**: use VS Code theme tokens (`--vscode-*`) for every color;
  light/dark both must pass WCAG AA for text.
- **Stable layout**: fixed dimensions for composer, icon buttons, badges,
  tabs, and approval rows; no text-driven reflow that shifts controls.
- **Discoverability without text walls**: icons with tooltips, command
  palette entries, and contextual empty states; no feature-explainer copy in
  the product UI.

## Design tokens and components

Create `extensions/cedia-agent/src/ui/tokens.ts` + `components.ts`:

- Colors derived from theme background/foreground; explicit accents for
  agent/plan/approval/danger states.
- Type scale: 12/13/15/17/20 px only; letter-spacing 0; no viewport-scaled
  fonts.
- Icon set: existing CEDIA SVG set or lucide; every icon button has a
  `title`/tooltip.
- Components: `Composer`, `MessageBlock`, `ToolCallRow`, `PlanStep`,
  `DiffHunk`, `ApprovalCard`, `StatusBadge`, `EmptyState`, `ProviderPicker`.
- Webview layout uses CSS grid with stable min/max tracks; no nested cards.

Gate: token/component snapshot tests + accessibility color-contrast test
(extend `light_theme`-style tests from GPUI into the extension).

## Phase plan

Each phase ends with a gate: E2E (Playwright against `code.sh`), screenshot
artifacts under `docs/evidence/parity/<phase>/`, and the extension test suite
still green. Do not start the next phase until the current gate passes.

### P1 — UX foundation + chat/plan polish

- Design token/component library above.
- Chat: conversation history (in-memory first, persisted later), streaming
  markdown blocks, tool-call rows with status, stop/retry, model picker.
- Plan mode: editable structured plan rendered as steps; per-step
  approve/reject before execution.
- Empty state: one-line "Open a project, pick a provider, describe the task"
  with icons; no tutorial text.

Gate: chat E2E (send → stream → stop → retry), plan approve/reject E2E,
contrast test, screenshots.

### P2 — Diff review + apply

- Per-file changed list in sidebar with status (agent-modified/pending).
- Inline diff editor view: accept/reject per file and per hunk.
- Apply flow: selected hunks applied to working tree; rejected hunks stay in
  session branch.
- Snapshot timeline: restore any agent checkpoint from the review panel.

Gate: accept/reject E2E, apply E2E, restore E2E, screenshots.

### P3 — Cursor Tab-style inline edit

- Agent proposes edits with Monaco decorations/ghost text.
- Tab accepts, Esc rejects, Alt+Tab cycles suggestions.
- Works for line, multi-line, and small structural rewrites; bounded context.
- Conflicts with user typing invalidate suggestion without applying.

Gate: inline-edit E2E (propose/accept/reject/conflict), perf budget
(suggestion latency < 500 ms locally), screenshots.

### P4 — Semantic context + browser integration

- Upgrade indexer to embeddings (local model via Ollama, or hash-based
  fallback) with ranked retrieval.
- `@file` / `@symbol` / `@selection` mention picker in composer.
- Image input in chat (paste screenshot) passed to vision-capable profiles.
- Browser panel: embed BrowserOS preview in a CEDIA view (address bar, tab,
  live agent actions) instead of external app only.

Gate: retrieval quality fixture, mention E2E, image-input E2E, browser panel
screenshot + navigate E2E.

### P5 — Product UX + release

- Welcome/onboarding view: provider setup, key storage, model picker,
  permission defaults.
- Settings page: providers, MCP catalog, approvals, telemetry opt-out.
- Permission/approval queue panel with audit trail.
- Signed/notarized CEDIA.app + auto-update feed (needs Apple credentials).

Gate: onboarding E2E, settings E2E, approval audit E2E, signed bundle smoke,
telemetry policy test.

## Cross-cutting verification

- `bash verify.sh` in both repos stays green after every phase.
- Extension unit tests grow with each phase; keep runtime under ~1 s.
- Accessibility: run axe or equivalent against chat/plan/diff views; WCAG AA.
- Self-hosting: at least one real feature in this repo per phase authored by
  CEDIA's own agent and verified by `bash verify.sh`.
- Evidence artifacts committed under `docs/evidence/parity/` with date and
  command used to produce them.

## Risks and guardrails

- VS Code upstream churn: pin commits; keep extension-only changes until P5.
- Webview performance: bound history/plan sizes; virtualize long messages.
- Embeddings quality without cloud index: keep word fallback; treat quality
  as measured, not assumed.
- BrowserOS is a separate app: P4 embeds preview via MCP; do not fork
  Chromium (~100 GB build) for parity.
- Signing/updates remain owner-gated; parity UX can land unsigned first.

## Immediate next step

Start P1: scaffold `src/ui/` tokens/components, add first chat history +
plan-step UI, and write the P1 gate scripts.
