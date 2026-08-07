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

## Live parity gates

- `~/CEDIA/verify.sh` → PASS (Rust contracts, policy invariants,
  `browseros smoke: PASS`).
- `~/cedia-ide/verify.sh` → PASS (compile, 36 tests, VSIX package, harness
  config).
- DeepSeek live provider → PASS (`live-provider-smoke.sh`).
- BrowserOS neo native MCP → PASS (`browseros-smoke.sh`).
