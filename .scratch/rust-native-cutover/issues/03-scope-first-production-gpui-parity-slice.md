Type: grilling
Status: resolved
Blocked by: 02

## Question

Which production GPUI slice should replace the corresponding Tauri surface
first, and what testable parity, accessibility, and rollback evidence must it
meet before Tauri code is removed?

## Decision

The first slice is the safety-first session workspace: authenticated session
tree, ordered conversation, and live approval review/deny. It runs only against
an isolated Rust snapshot until write-owner cutover and keeps Tauri as an
explicit restart fallback.

## Evidence

- Tickets 06–08 provide authenticated Rust routes and GPUI panes for sessions,
  messages, and live pending approvals without Python or Tauri UI calls.
- Native confirmation, durable audit-before-resolution, post-result reload,
  public-session isolation, and stale-action clearing are regression tested.
- `PARITY.md` retains measurable replay/live, performance, accessibility, and
  rollback evidence requirements. Tauri deletion remains gated on R4/R5.
