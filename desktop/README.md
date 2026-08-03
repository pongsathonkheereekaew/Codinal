# Codinal desktop

Codinal desktop is a native Rust GPUI application backed by an authenticated
local control plane and Rust runtime.

- `desktop/gpui/` owns process launch, one-time bearer credentials, OAuth deep
  links, native titlebar behavior, and runtime integration.
- The control plane remains authenticated on loopback; mutable actions still pass
  through policy, sandbox, and Git worktree isolation.

Run the desktop app:

```bash
cargo run --manifest-path desktop/gpui/Cargo.toml
```

Run all acceptance gates from the repository root:

```bash
bash verify.sh
```

Architecture and release gates are documented in
`docs/decisions/0001-codinal-foundation.md` and
`docs/plan/codinal-mvp.md`.
