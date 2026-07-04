---
name: easby-data-topology
description: "Easby plugin data = 3-layer pipeline (source→derived→spec); Easby Studios is the SOURCE, not a duplicate — do not delete"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2cc48522-6636-4890-9c32-1aa0434da3e1
---

The easby (audio-plugin RE/DSP) data is a 3-layer pipeline, NOT duplicated stores. Looks redundant (per-vendor folders appear in multiple places) but each layer is different content:

1. **Source (raw):** `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Easby Studios/Plug-Ins/` — 262 files, raw vendor PDF manuals + screenshots by vendor. This is the Obsidian personal vault "Easby Studios" (also holds a `.base` db + notes).
2. **Derived:** `~/.claude/skills/easby/shared/plugins/<vendor>/*.md` — agent-extracted per-product notes (verified DIFFERENT content from the source).
3. **Spec (final):** `~/.claude/skills/easby/easby-programming/plugins/*.md` (~85) — DSP algorithm specs, formulas, FFI contracts + BuildSpec.json.

The agent's raw manuals now live LOCAL at `~/.claude/skills/easby/shared/plugins/manuals/vault/` (427M, real dir, gitignored per the skill's `.gitignore` rule "raw source stays local, distilled *.md commit"). **As of 2026-06-28 this is a real local copy, NOT a symlink** — it was previously `vault → Easby Studios/Plug-Ins` (iCloud), which risked silent agent failures when iCloud evicted files to dataless stubs. Copied local to kill that dependency permanently (no Finder-pin / SSD-mount needed).

`Easby Studios` (iCloud) is now just the Obsidian `.base` db + a few notes (272K) — the `Plug-Ins/` manuals were DELETED from iCloud on 2026-06-28 to reclaim 427M (the agent no longer needs them there). The `#Software & Plugins.base` view there is now empty by design. Manuals survive in 2 places: local `manuals/vault/` (70 pdf, agent working copy) + SSD repo (74 pdf, superset) + TimeMachine.

Separately, the full easby RE dev repo (31G: ES-* plugin projects, binaries, .git, private-research) lives on external SSD `/Volumes/rLTI/MUSIC PRODUCTION/05_SOFTWARE/Easby Plugins` — that is the working repo, a different layer from both the manuals and the distilled specs.

**Why this matters:** the three layers look redundant (vendor folders recur) but are source→derived→spec, different content. Don't "delete the duplicate."

**How to apply:** agent manuals are self-contained local now — safe. If regenerating, the source-of-truth manuals are the local `manuals/vault/` (and the iCloud/SSD copies are backups). See [[obsidian-view-layer]] (Easby Studios = personal vault, separate from the agent memory folder).
