# CEDIA parity gate evidence

Date: 2026-08-07. Every row is a fresh command output, not a claim.

## Unit + component gates

```text
$ npm test
pass 36
fail 0
```

Includes:

- axe-core run against chat, review, and product views (jsdom via
  `scripts/axe-html.js`): 0 violations. Fixed `select-name` by binding
  `<label for>` + `aria-label`.
- Performance budgets:
  - semantic index build: 52.6 ms (budget 3000 ms)
  - avg semantic search: 0.42 ms (budget 250 ms)
  - avg plan parse: 0.076 ms (budget 5 ms)

## GUI E2E (VS Code extension host)

```text
$ npm run test:e2e
Extension host with pid ... exited with code: 0
```

The suite opens a real Code window via `@vscode/test-electron`, activates
`cedia-agent`, and executes `cediaAgent.chat`. Non-modal commands only;
modal approval/status prompts are excluded from headless runs.

## Review-fix evidence (2026-08-07)

- Plan approval is now bound to execution: `AgentSession.setPlan` rejects a
  run while any step is unapproved (unit test covers gate + allowed run).
- Review apply is real: accepted hunks are rebuilt into a filtered unified
  diff and applied with `git apply --check` + `git apply`; rejected hunks stay
  in the session.
- Inline edit: multi-line suggestion text, Alt+Tab alternative cycling,
  and conflict invalidation when the user types inside the proposed range.
- Settings/onboarding load provider profiles and MCP servers from the harness
  `agent.yaml`; telemetry opt-out persists in global state.
- Retrieval is honest: keyword-hash vector is documented as non-semantic and
  tested so synonym-only queries do not outrank exact overlap.
- Keybindings contributed (Tab/Esc/Alt+Tab inline, Cmd+Alt+C C/R), inline SVG
  icon set added; browser panel now has an address bar that mirrors
  BrowserOS navigation.
- E2E suite additionally exercises browser panel, settings, and inline reject
  commands without modal prompts; exit 0.

## Live parity gates

- `~/CEDIA/verify.sh` → PASS (Rust contracts, policy invariants,
  `browseros smoke: PASS`).
- `~/cedia-ide/verify.sh` → PASS (compile, 36 tests, VSIX package, harness
  config).
- DeepSeek live provider → PASS (`live-provider-smoke.sh`).
- BrowserOS neo native MCP → PASS (`browseros-smoke.sh`).

## Native in-IDE browser panel (2026-08-07)

- `cediaAgent.browserPanel` now opens a Codex-style in-IDE browser:
  address bar, back/forward/reload, tab strip, screenshot refresh, console
  output, and "open in BrowserOS" button.
- All actions drive BrowserOS MCP (`tabs`, `navigate`, `screenshot`,
  `read format=console`); page id ownership is respected (new tab returns the
  page id before navigation).
- Unit tests cover page/tab/image parsing (66 extension tests pass). Live MCP
  handshake verified against BrowserOS neo at `127.0.0.1:9010`; page actions
  require a BrowserOS browser window to be open in the app.

## True native WebContentsView browser (2026-08-07)

- `cediaAgent.nativeBrowser` opens a real editor browser tab via the fork's
  proposed `window.openBrowserTab` API (`extensions/cedia-agent` enables
  `"browser"` API proposal). This is a WebContentsView inside the CEDIA
  window, not an iframe or screenshot preview.
- `CediaNativeBrowser` attaches a CDP session (`Page.enable`,
  `Page.captureScreenshot`, `Runtime.evaluate`, `Page.navigate`) so the agent
  and UI can read console, screenshot, navigate, and evaluate JS directly.
- E2E suite exercises the command (exit 0; headless may skip native view
  render); extension tests 66 pass.
- Kept the BrowserOS MCP panel as the login/profile-rich fallback.
