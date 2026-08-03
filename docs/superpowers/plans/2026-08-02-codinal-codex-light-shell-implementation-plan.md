# Codinal Codex-Like Light Shell Implementation Plan

> **Status (2026-08-02): implemented and superseded.** This file preserves the
> original execution plan. The authoritative shipped geometry, resizable panel
> behavior, semantic typography, accessibility, and display-cadence contract is
> `desktop/gpui/UI_CONTRACT.md`; current evidence is
> `docs/evidence/cutover/c3/gate.md`. Do not use the initial 52/280 px examples
> below as current requirements.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded dark GPUI workbench shell with the approved Codex-like light shell without changing execution behavior or leaving the pure-Rust application boundary.

**Architecture:** Add a small, dependency-free Rust module containing light-palette and layout tokens, then consume those tokens from the existing GPUI renderer. Keep all control-plane operations in `WorkspacePrototype`; only shell composition and visual styling change.

**Tech Stack:** Rust 2021, pinned GPUI revision `ae394f3`, existing Codinal native runtime/control-plane client.

## Global Constraints

- Pure Rust application only: no HTML, CSS, JavaScript, WebView, Tauri, Python, or new dependency.
- Preserve runtime capability checks, approval authority, provider Keychain flow, updater signing flow, and terminal lifecycle.
- Light theme is the only visual mode in this change; dark mode is deferred.
- Preserve unrelated dirty-worktree changes; do not stage or commit unless the user requests it.
- Done requires fresh tests, Clippy, release bundle audit, packaged smoke, installation, launch, and screenshot evidence.

---

### Task 1: Light theme contract

**Files:**
- Create: `desktop/gpui/src/light_theme.rs`
- Modify: `desktop/gpui/src/main.rs`

**Interfaces:**
- Produces: `light_theme::color`, `light_theme::layout`, `contrast_ratio(u32, u32) -> f32`.
- Consumes: no runtime state and no external dependency.

- [ ] **Step 1: Write failing palette/layout tests**

```rust
#[test]
fn approved_shell_metrics_are_stable() {
    assert_eq!(layout::TOP_BAR_HEIGHT, 52.0);
    assert_eq!(layout::SIDEBAR_WIDTH, 280.0);
    assert_eq!(layout::CONTENT_MAX_WIDTH, 840.0);
    assert_eq!(layout::CONTEXT_WIDTH, 336.0);
}

#[test]
fn light_text_contrast_meets_accessibility_floor() {
    assert!(contrast_ratio(color::TEXT_PRIMARY, color::CANVAS) >= 7.0);
    assert!(contrast_ratio(color::TEXT_SECONDARY, color::CANVAS) >= 4.5);
}
```

- [ ] **Step 2: Run the targeted tests and observe the missing-module failure**

Run: `cargo test --manifest-path desktop/gpui/Cargo.toml light_theme`

Expected: compilation fails because `light_theme` does not exist.

- [ ] **Step 3: Implement tokens and contrast helper**

```rust
pub mod color {
    pub const CANVAS: u32 = 0xffffff;
    pub const SIDEBAR: u32 = 0xf5f5f5;
    pub const TEXT_PRIMARY: u32 = 0x202124;
    pub const TEXT_SECONDARY: u32 = 0x686868;
    pub const BORDER: u32 = 0xe6e6e6;
    pub const SURFACE: u32 = 0xf2f2f2;
    pub const ACCENT: u32 = 0x1677ff;
}

pub mod layout {
    pub const TOP_BAR_HEIGHT: f32 = 52.0;
    pub const SIDEBAR_WIDTH: f32 = 280.0;
    pub const CONTENT_MAX_WIDTH: f32 = 840.0;
    pub const CONTEXT_WIDTH: f32 = 336.0;
}
```

- [ ] **Step 4: Run the targeted tests to green**

Run: `cargo test --manifest-path desktop/gpui/Cargo.toml light_theme`

Expected: both theme tests pass.

### Task 2: Codex-like shell composition

**Files:**
- Modify: `desktop/gpui/src/main.rs`
- Modify: `desktop/gpui/src/workbench.rs`

**Interfaces:**
- Consumes: Task 1 constants via `use light_theme::{color, layout};`.
- Produces: light `header`, `session_pane`, `conversation_pane`, floating `context_panel`, and floating `composer_pane` while keeping existing element IDs and callbacks.

- [ ] **Step 1: Update the anatomy test before renderer changes**

```rust
assert_eq!(state.layout_anatomy().top_bar_height, 52);
assert_eq!(state.layout_anatomy().sidebar_width, 280);
```

- [ ] **Step 2: Run the anatomy test and observe the old 50/232 values**

Run: `cargo test --manifest-path desktop/gpui/Cargo.toml layout_anatomy`

Expected: failure showing the old metrics.

- [ ] **Step 3: Rewrite presentation while preserving callbacks**

Use a relative white canvas, render the floating context card after the conversation, place the composer inside a centered `max_w(px(layout::CONTENT_MAX_WIDTH))` wrapper, and replace hardcoded dark colors with Task 1 tokens. Retain IDs including `new-task`, `context-toggle`, `composer-input`, `run-turn`, `terminal-toggle`, and approval/provider/updater IDs.

- [ ] **Step 4: Set approved initial geometry**

```rust
let bounds = Bounds::centered(None, size(px(1440.0), px(900.0)), cx);
// Initial context matches the approved reference and remains ⌘K-toggleable.
context_panel_open: true,
```

- [ ] **Step 5: Run GPUI tests**

Run: `cargo test --manifest-path desktop/gpui/Cargo.toml`

Expected: all tests pass.

### Task 3: Contract and static boundary checks

**Files:**
- Modify: `desktop/gpui/UI_CONTRACT.md`

**Interfaces:**
- Consumes: approved design and implemented element anatomy.
- Produces: durable documentation of the light shell and unchanged safety boundary.

- [ ] **Step 1: Update the layout contract**

Document the 52 px top bar, 280 px sidebar, 840 px conversation column, floating context card, floating composer, and collapsed terminal affordance.

- [ ] **Step 2: Check formatting and prohibited technologies**

Run: `cargo fmt --manifest-path desktop/gpui/Cargo.toml -- --check`

Run: `rg -n "tauri|webview|webkit|python|javascript|html|css" desktop/gpui/src desktop/gpui/Cargo.toml`

Expected: formatting passes; no application dependency or source integration for a web/Python runtime.

- [ ] **Step 3: Run Clippy with warnings denied**

Run: `cargo clippy --manifest-path desktop/gpui/Cargo.toml --all-targets -- -D warnings`

Expected: exit 0.

### Task 4: Release build, install, and visual verification

**Files:**
- Modify only generated release artifacts under `desktop/gpui/target/release/bundle/macos/Codinal.app` and the installed `/Applications/Codinal.app` after all checks pass.

**Interfaces:**
- Consumes: verified Task 1–3 source.
- Produces: one installed, signed, pure-Rust Codinal bundle and screenshot evidence.

- [ ] **Step 1: Run the repository verification gate**

Run: `bash verify.sh`

Expected: exit 0 with the current documented skip count only.

- [ ] **Step 2: Build and audit the macOS release bundle**

Run the repository's existing macOS release build/audit commands discovered from `desktop/build.mjs` and `.github/workflows/release.yml` without weakening either gate.

Expected: release bundle contains native `codinal` and `codinal-runtime`, passes codesign verification, and contains no Python/Tauri/WebView runtime.

- [ ] **Step 3: Run packaged smoke**

Launch the bundle against an isolated data directory, wait for runtime health, and confirm the app remains alive long enough for the smoke window.

Expected: app and authenticated Rust runtime are both healthy.

- [ ] **Step 4: Install the single verified bundle and capture the UI**

Replace `/Applications/Codinal.app` with the verified bundle, launch it with the requested workspace, and capture a screenshot.

Expected: only one installed Codinal app remains; screenshot shows the approved light shell with sidebar, centered conversation, floating context card, and floating composer.
