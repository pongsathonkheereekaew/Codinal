Status: resolved
Type: research

## Question

Which pinned GPUI revision, Rust toolchain, macOS/Linux support constraints,
and native shell bootstrap can safely start and stop Codinal's authenticated
sidecar without changing Tauri's signed release path?

## Answer

Use GPUI `0.2.2` (Apache-2.0) in a new standalone development-shell crate and
keep it out of the Tauri release dependency graph. Upstream is pre-1.0 and
requires Rust 1.95.0; Codinal's Rust 1.97.1 satisfies that floor. macOS uses
Metal; Linux remains a separately verified packaging target. Evidence and the
bootstrap boundary are recorded in
[`g1-compatibility-research.md`](../g1-compatibility-research.md).
