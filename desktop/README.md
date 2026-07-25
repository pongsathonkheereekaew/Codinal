# Codinal desktop

Codinal is a native macOS Tauri v2 application backed by an authenticated
Python sidecar.

- `src-tauri/` owns process launch, one-time bearer credentials, macOS
  Keychain provider secrets, OAuth deep links, the native titlebar, and the
  workspace folder picker.
- `ui/` is a dependency-free WebView client with a task sidebar, transcript,
  composer, risk-scoped approval cards, session/model controls, and an inline
  Git review/apply panel.
- The UI can reach only the random loopback sidecar under the production CSP.
  Mutations still pass through runtime policy, sandbox, and Git worktree
  isolation.

Run the development app:

```bash
cargo run --manifest-path desktop/src-tauri/Cargo.toml
```

Run all acceptance gates from the repository root:

```bash
bash verify.sh
```

Architecture and release gates are documented in
`docs/decisions/0001-codinal-foundation.md` and
`docs/plan/codinal-mvp.md`.
