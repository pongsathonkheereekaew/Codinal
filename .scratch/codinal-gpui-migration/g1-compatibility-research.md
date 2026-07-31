# G1 GPUI compatibility research — 2026-07-31

## Evidence

- GPUI's official README states that it is pre-1.0, has breaking changes, and
  requires current stable Rust on macOS or Linux.
- Official upstream at `ae394f3d474f4996d2cdef6ee97551fdb6748acd` declares
  package `gpui` version `0.2.2`, Apache-2.0, and Rust toolchain `1.95.0`.
- Codinal's installed Rust is `1.97.1`, meeting that floor. macOS uses Metal;
  Linux support is upstream-supported but needs a separate CI/package probe.

## Decision

Use the crates.io release `gpui = "=0.2.2"` in a new standalone development
shell crate, rather than adding it to the Tauri crate or tracking upstream
`main`. This bounds API churn and keeps the signed Tauri release dependency
graph unchanged. Pin the Rust floor at `1.95.0`; keep Codinal's `1.97.1`
toolchain for the initial spike.

The development shell receives only the sidecar port and bearer through its
native bootstrap; it must not create a WebView, inject credentials into UI
state, or expose a release selector. Sidecar ownership remains in the existing
native host until lifecycle tests prove a replacement.

## Sources

- <https://github.com/zed-industries/zed/blob/main/crates/gpui/README.md>
- <https://github.com/zed-industries/zed/tree/ae394f3d474f4996d2cdef6ee97551fdb6748acd/crates/gpui>
