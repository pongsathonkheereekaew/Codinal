# Codinal settings and ecosystem surface

## Goal

Make Settings read like a complete coding-agent product while exposing only
capabilities that Codinal can execute, secure, audit, and test locally.

## Boundary

Codinal remains the routing and policy authority. OmniRoute is an optional
OpenAI-compatible gateway, not a bundled dependency or a replacement for
Codinal's provider, failover, audit, and permission layers.

Controls that do not yet have a local runtime contract are shown only in a
non-interactive **Planned** catalogue. They must not look enabled or mutate
state.

## Delivery order

### 1. Settings information architecture

- Keep **General**, **Models & Gateway**, **Providers**, **Agents & Skills**,
  **Connections**, **Workspace**, **Developer tools**, **Updates**, and **Diagnostics** as
  navigable, searchable categories.
- General owns appearance, routing profile, and automatic failover.
- Models & Gateway explicitly presents OmniRoute, Ollama, and registered
  OpenAI-compatible gateways; it does not claim to manage upstream accounts.
- Workspace links to the selected task's existing Environment/Git/worktree
  view rather than maintaining a second worktree state.

### 2. Functional ecosystem controls

- Add a Rust Harness Manager under **Agents & Skills**. Its first surface is a
  read-only inventory of the Harness Source Bundle, User Overlay, Live
  Projection, Host Projections, capability evidence, and drift. Write controls
  remain unavailable until the Rust planner can show an ownership-aware diff,
  obtain approval, apply atomically, verify, receipt, and roll back.
- Enable host writes adapter by adapter, beginning with OpenCode after Rust
  conformance. Never invoke the Bash/Python installer from the app, treat prompt
  policy as runtime enforcement, overwrite non-owned host paths, or delete a
  User Overlay during an update.
- Add an Extension manager backed solely by `/v1/extensions`: list, local
  manifest registration, enable/disable, provenance verification, removal.
- Add a keyboard-shortcuts reference generated from the existing application
  key map. It is reference-only until shortcut remapping has a persisted,
  conflict-checked runtime contract.
- Preserve the existing MCP manager; place it under Connections.

### 3. Planned catalogue, not fake controls

- Show Browser/dev-server evidence, Computer use, Voice, Account, and Usage
  as planned capabilities with their required backend contract.
- Do not add toggles, login forms, billing links, credential fields, or
  install-from-network actions for those entries.

### 4. Deferred runtime work before activation

- Browser/computer use: approval, audit, screenshot/console/network evidence.
- Voice: local/remote audio handling, consent, retention, and transcript audit.
- Account/usage: identity, entitlement, billing ledger, privacy boundary.
- Shortcut remapping: persisted key map, reserved-key conflict detection, and
  recovery/reset behavior.

## Verification

1. UI contracts cover each visible Settings category and prove planned cards
   have no interactive state-changing control.
2. Extension manager tests cover invalid manifest, enable/disable, verification,
   remove, and 404/error rollback.
3. Keyboard reference tests enumerate every active document shortcut.
4. Live macOS smoke: Settings navigation, OmniRoute/custom-provider screen,
   extension lifecycle, and workspace deep link.
5. Release build remains Developer-ID signed; no provider credential is written
   outside the Keychain path.

## Explicit non-goals for this phase

- Bundling, cloning, or automatically installing OmniRoute.
- A plugin marketplace or network package installer.
- Pretending Account, billing, browser, voice, or computer-use features exist.
