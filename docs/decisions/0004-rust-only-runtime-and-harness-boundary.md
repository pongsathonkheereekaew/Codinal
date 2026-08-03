---
status: accepted
date: 2026-08-01
---

# Rust-only runtime and harness boundary

Codinal ships GPUI and a separate execution runtime entirely in Rust, with no
Python/Tauri fallback. The universal agents/skills harness remains declarative
content, but its planning, projection, ownership, verification, and rollback
become a Rust subsystem; prompt policy never replaces the runtime's enforced
approval boundary. This rejects the lower initial cost of a Python sidecar and
script-driven installer in exchange for one process authority, one writer
model, deterministic recovery, and an auditable product surface.

## Consequences

- The immediate product may be read-only while the safe Rust execution slice
  is incomplete.
- Existing Bash/Python harness code is a behavior and fixture reference, not an
  app dependency.
- Exactly one Rust runtime owns each data history, and existing data migrates
  in place before mutation.
- Host support is enabled adapter by adapter after Rust conformance; universal
  content does not imply universal enforcement.
