# C0 gate — true Rust read-only bootstrap

- owner: Codinal runtime + native desktop
- dependencies: `docs/plan/rust-native-runtime-cutover.md`, ADR 0004
- fixture/credential class: empty temporary data directory; 32-character test bearer; no provider credential
- environment: Darwin arm64; Rust toolchain from `rust-toolchain.toml`
- status: passed

## Exact fresh commands

```text
cargo test --manifest-path crates/codinal-runtime/Cargo.toml read_only -- --nocapture
cargo test --manifest-path desktop/native-host/Cargo.toml read_only -- --nocapture
cargo test --manifest-path desktop/gpui/Cargo.toml --bin codinal-gpui -- --nocapture
cargo build --release --locked --manifest-path crates/codinal-runtime/Cargo.toml
TOOLCHAINS=Metal cargo build --release --locked --manifest-path desktop/gpui/Cargo.toml
CODINAL_SKIP_CARGO_BUILD=1 scripts/build-macos-release.sh
CODINAL_SKIP_CODESIGN_CHECK=1 scripts/smoke-macos-release.sh desktop/gpui/target/release/bundle/macos/Codinal.app
```

## Observed result

- Runtime read-only filter: 1 focused integration test passed; no failures.
- Native-host read-only filter: 1 focused launch-mode test passed; `ReadOnly` is accepted without being `Ready`.
- GPUI binary tests: 18 passed; no failures.
- Bootstrap audit: health reported `mode=read_only`, `reason_code=owner_bootstrap_deferred`, `migration.state=not_started`, `writer_lock.state=not_acquired`, and both Run/mutation reasons; the data-directory fingerprint was unchanged and no `.codinal-runtime.lock` was created.
- Packaged smoke: app launched with one Rust runtime process; direct-child audit found no Python, Tauri, WebKit, or WebView process.
- Static launch audit: `desktop/gpui/src/main.rs` and `desktop/native-host/src/host.rs` contain no Python sidecar/Tauri/WebView launch symbols.

## Artifact checksums

```text
125108b6611adf1e5ca481faf9819832582afee2d02ddbda5c76f3b917bfc286  desktop/gpui/target/release/bundle/macos/Codinal.app/Contents/MacOS/codinal
2037cb83399d6e30d6b68190d635096214d5ff077abf676b5bf947a0e9ed3884  desktop/gpui/target/release/bundle/macos/Codinal.app/Contents/Resources/codinal-runtime
6bac90c65517a889a0050a87a42f8c85399d83ce37e89710329d2c54068f219c  desktop/gpui/target/release/bundle/Codinal-0.1.0-macos-arm64.zip
```

## Rollback and stop condition

- Rollback: stop the app/runtime and restore the pre-C0 Rust sources; the packaged outputs are under ignored `target/` paths and are disposable.
- Stop if any Python/Tauri/WebView process appears, the read-only data fingerprint changes, the writer lock appears, a writable database handle is opened, or Run/mutation controls lose their typed disabled reason.
