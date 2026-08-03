# Codinal Codex-Like Light Shell Design

**Approved:** 2026-08-02

**Implemented contract:** `desktop/gpui/UI_CONTRACT.md` supersedes the initial
fixed-width measurements below where they differ.

## Goal

Make the native Codinal workbench visually match the supplied Codex light-theme reference while preserving every existing Rust runtime, provider, approval, updater, and terminal capability.

## Baseline that was corrected

`WorkbenchState` defaults to `Appearance::Light`, but the live GPUI renderer does not consume that state. The renderer instead hardcodes a dark palette, a fixed three-column developer-console layout, a full-width composer, and a full-height context pane. Conversation messages are rendered as uniformly boxed diagnostic blocks rather than a centered conversational timeline.

## Approved presentation

- The default window is 1440×900 with a 48 px top bar.
- A pale-gray task sidebar has a 314 px preferred width, resizes from 220–420
  px, and collapses fully to 0 px without losing its preference.
- The main canvas is white. Conversation content is centered and capped at 840 px.
- User messages are right-aligned light-gray bubbles; assistant messages use the open white canvas.
- Runtime and stream details are reduced to quiet secondary labels instead of a dedicated status strip.
- Context is a 336 px floating card at the upper-right of the canvas, with a subtle border, large radius, and shadow. It is visible initially and remains toggleable with `⌘K`; pending approvals force it visible.
- The composer is a centered floating card near the bottom of the canvas. Provider/model/access details and the send action live inside the card.
- A structural right Workbench resizes from 320–720 px, docks when space
  permits, and overlays at narrow widths. Review, Terminal, Browser, Files, and
  Side chat are ordered tabs; closing Terminal hides the view without stopping
  its PTY.
- The Files detail/tree split is independently resizable from 140–320 px.
- Preferred widths persist atomically; responsive collapse/overlay state does
  not overwrite them.
- Light mode is designed independently. Dark mode is intentionally deferred and must not be produced by direct color inversion.

## Pure-Rust boundary

The implementation uses the existing pinned GPUI revision and Rust source only. It adds no web runtime, HTML, CSS, JavaScript, WebView, Tauri, Python, or new dependency. The authenticated native Rust runtime remains the only execution authority, and presentation state never promotes a disabled capability.

## Verification

- Theme/layout unit tests assert the approved dimensions and WCAG contrast floor for primary and secondary text.
- Existing GPUI and workspace tests remain green.
- `cargo clippy` passes with warnings denied.
- A release bundle passes the repository pure-Rust audit and packaged smoke test.
- The installed `/Applications/Codinal.app` is replaced only after successful verification, then launched and captured for visual comparison.
