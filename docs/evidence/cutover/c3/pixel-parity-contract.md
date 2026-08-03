---
stage: C3
owner: desktop/gpui
parent: gate.md
status: fixture-manifest-captured-native-actual-pending
---

# GPUI pixel-parity contract

This is a sub-contract of the C3 workbench gate. It freezes the comparison
profile and the review matrix; it is not a second release gate. The native
Rust/GPUI renderer and the existing runtime/control-plane contracts remain the
only authorities.

## Reference profile

The user-supplied Codex golden fixtures are now copied immutably under
`docs/evidence/cutover/c3/golden/` and listed in the parity review. A native
Codinal actual capture is still missing; the fixtures are the target, not proof
that the current renderer matches them:

| Field | Frozen target | Current evidence |
|---|---|---|
| Viewport | 1,710 × 1,112 logical px | Contract test in `light_theme.rs` and `shell_layout.rs` |
| Capture scale | 2× | Not captured in the checked-in JPEG |
| Appearance | macOS Light, active window | Candidate screenshot is light appearance |
| Fonts | macOS system UI font; SF Mono for code/terminal | Native GPUI font selection; OS rasterization may differ |
| Primary state | selected chat, provider ready, idle composer, no pending approval | Missing deterministic golden capture |
| User-supplied golden set | `golden/window/*.png`, `golden/overlay/*.png` | 11 immutable PNG fixtures; dimensions and SHA-256 are recorded in `codex-surface-parity-review-2026-08-03.md` |
| Candidate baseline | `ui-contract-aligned-2026-08-03.jpeg` | SHA-256 `49a39c563e6ec9538e5456a8571b718e1f44bb4b50e605d4cb88264285392c21`; 1,229 × 768 px; legacy candidate only |
| Historical comparison | `ui-visual-pass-2026-08-03.jpeg` | Indigo experiment; never use as the target |

The golden asset must be checked in under `docs/evidence/cutover/c3/` or
identified by an immutable external artifact before a parity result can be
reported. A screenshot with a different viewport, scale, appearance, font
set, or UI state is a separate fixture.

## Shell geometry

These values are the source of truth for the fixed Light/ready comparison
profile. Responsive behavior is tested separately and must not overwrite
persisted preferences.

| Region | Target | Source / verification |
|---|---:|---|
| Native header/title row | 48 px | `light_theme::layout::TOP_BAR_HEIGHT` |
| Navigation width | 314 px; clamp 220–420 px | `shell_layout::{NAVIGATION_*}` |
| Conversation max width | 840 px | `light_theme::layout::CONTENT_MAX_WIDTH` |
| Message max width | 620 px | `light_theme::layout::MESSAGE_MAX_WIDTH` |
| Environment card | 336 px; 16 px inset | `light_theme::layout::CONTEXT_WIDTH`, `shell_layout::CONTEXT_PANEL_INSET` |
| Workbench width | 424 px; clamp 320–720 px | `shell_layout::{WORKBENCH_*}` |
| Files tree width | 140 px; clamp 140–320 px | `shell_layout::{FILE_TREE_*}` |
| File detail minimum | 160 px | `shell_layout::FILE_DETAIL_MIN_WIDTH` |
| Conversation minimum | 560 px | `shell_layout::CONVERSATION_MIN_WIDTH` |
| Overlay margin | 16 px horizontal | `shell_layout::OVERLAY_HORIZONTAL_MARGIN` |
| Content edge padding | 24 px | GPUI `px_6()` in conversation/composer leaves |

Acceptance: structural edges are within 2 logical px of the golden reference;
no supported state clips, overlaps, or moves a persisted divider while the
window is resized.

## Visual tokens

Flat-color samples must match these packed RGB values. Text rasterization is
compared by geometry and semantic color, not by requiring identical
antialiasing across macOS builds.

| Token | RGB | Use |
|---|---|---|
| Canvas / elevated | `#FFFFFF` | Main conversation and floating surfaces |
| Sidebar | `#F5F5F5` | Navigation background |
| Surface | `#F2F2F2` | Cards and quiet controls |
| Hover / selected | `#EDEDED` / `#E7E7E7` | Local interaction states |
| Border / strong border | `#E6E6E6` / `#D8D8D8` | Dividers and composer edge |
| Primary / secondary / tertiary text | `#202124` / `#686868` / `#989898` | Type hierarchy |
| Accent / muted accent | `#1677FF` / `#EAF2FF` | Links, receipt state, focus feedback |
| Success / warning / danger | `#1B8F45` / `#A85600` / `#C9362B` | Capability and terminal states |

| Role | Size | Weight / font |
|---|---:|---|
| Section | 15 px | Semibold, system UI |
| Body | 13 px | Regular, system UI |
| Control/tab/sidebar | 12 px | Regular, system UI |
| Metadata | 11 px | Regular, system UI |
| Code/terminal | 12 px | SF Mono |

Interactive targets remain at least 28 px high. The target uses low-contrast
single-pixel borders, restrained shadows, and native-looking monoline glyphs;
Unicode glyph substitutions must not change runtime meaning or accessibility
labels.

## State and interaction matrix

`Local proof` means deterministic Rust/GPUI evidence. `Visual proof` requires a
golden capture at the reference profile. `pending` is not a parity pass.

| State / interaction | Required visual behavior | Local proof | Visual proof |
|---|---|---|---|
| Empty chat list | Sidebar explains the empty state; composer is truthful and bounded | `navigation` and `conversation` unit contracts | pending golden |
| Ready chat | Selected chat, readable transcript canvas, enabled Run turn, provider/model/effort visible | capability and composer contracts | pending golden |
| Streaming | Working status and live assistant block; no duplicate/reordered content | `session_projection` / `ui_model` replay tests | pending golden |
| Approval pending | Environment remains visible; review action and reason are distinct | approval projection/reducer tests | pending golden |
| Receipt/error | Terminal outcome is typed, bounded, and does not masquerade as success | receipt/recovery tests | candidate baseline only |
| Setup/provider unavailable | Disabled actions explain the stable reason; no optimistic Run turn | capability/readiness tests | candidate baseline only |
| Context/workbench open | Environment card may remain co-visible with the dock; Sources is a secondary drawer; one Workbench detail tool is active; dock tabs preserve order | `shell_layout` composition tests and dock tests | pending native actual capture/diff |
| Terminal/diff/files | Native PTY/read-only projections remain labeled and bounded | dock/terminal/file projection tests | pending golden |
| Keyboard focus | Tab/Shift-Tab reaches labeled controls; focus styling is visible | accessibility matrix and focus tests | pending VoiceOver/manual |
| Resize/narrow window | Preferred widths persist; overlay placement is deterministic; no clipping | `shell_layout` resize tests | pending golden at narrow profile |
| Light/Dark/reduced motion | Separate palette/behavior contracts; no direct color inversion | theme/workbench contracts | pending live matrix |

## Verification protocol

1. Capture the same deterministic ready-chat fixture at 1,710 × 1,112 logical
   px and 2× scale with the active macOS Light appearance and the agreed font
   set. Record OS build, GPUI revision, window state, and fixture checksum.
2. Compare dimensions exactly, structural edges at ≤2 logical px, flat token
   samples at ≤1 RGB code, and normalized image error at MAE ≤0.02 with no
   more than 2% of pixels differing by >16/255. Text antialiasing is excluded
   from the flat-token sample and is reviewed by geometry/legibility.
3. Repeat the capture for every required state in the matrix. A state passes
   only when its interaction contract and visual comparison both pass.
4. Run the existing C3 commands and record fresh output in `gate.md`; do not
   promote C3 based on this document alone.

The repo now has a comparison runner plus a native launch/capture wrapper. The
wrapper is fixture-driven: it requires an isolated `codinal.db`, never points
at the production data directory by default, and never writes a golden. The
user-supplied golden fixture set is checked in and hashed. A native capture may
exist at a non-reference display size, but until a target-profile actual is
captured and reviewed, report mismatches by category and do not claim exact
parity.

The comparison runner is now available at
`scripts/verify-gpui-pixel-parity.py`. It never writes to a golden path and
emits `diff.png`, `overlay.png`, and `metrics.json` beside the requested
actual capture. For a native macOS main-display capture, run:

```bash
python3 scripts/verify-gpui-pixel-parity.py \
  --capture \
  --profile window-1710x1112@2x \
  --state ready-chat \
  --golden docs/evidence/cutover/c3/golden/window/primary-chat-environment-1710x1112@2x.png \
  --actual /tmp/codinal-parity/ready-chat.png \
  --expected-width 3420 \
  --expected-height 2224
```

For a repeatable native launch, use the wrapper with an isolated fixture data
directory. It disables Keychain bootstrap only for this capture process and
terminates the exact GPUI/runtime process group after the diff:

```bash
python3 scripts/capture-gpui-pixel-parity.py \
  --data-dir /tmp/codinal-capture-ready-chat \
  --golden docs/evidence/cutover/c3/golden/window/primary-chat-environment-1710x1112@2x.png \
  --actual /tmp/codinal-parity/ready-chat.png \
  --output-dir /tmp/codinal-parity/ready-chat \
  --gpui desktop/gpui/target/debug/codinal-gpui \
  --runtime crates/codinal-runtime/target/debug/codinal-runtime
```

This supplies launch, window-readiness, focus, idle-settle, capture, and diff
orchestration. The wrapper maps `window-1710x1112@2x` to a 3420×2224 physical
capture and `window-1280x720@2x` to a 2560×1440 physical capture; the GPUI
window uses the same profile bounds. Fixture seeding and state-specific native
captures still remain required before the contract can change from pending to
pass.

Latest native preflight on 2026-08-03: the QHD `window-1280x720@2x` profile
captured at the exact expected 2560×1440 dimensions, but the supplied golden
diff failed (`MAE 0.016755`, `11.7348%` of pixels over the 16/255 threshold).
The capture is evidence that launch/focus/dimension orchestration works, not a
parity pass; the fixture content and app/menu chrome still differ, and the
primary 3420×2224 profile cannot be accepted on this display.

## Change policy

- Change one visual slice at a time: shell/chrome, sidebar, conversation,
  composer, context, then dock/states.
- Keep runtime readiness, approval, receipts, Keychain boundaries, and native
  PTY ownership untouched by visual work.
- Use existing GPUI/Rust dependencies before adding tooling.
- Any copied/adapted visual asset or upstream behavior needs provenance in
  `NOTICE` and the C3 ledger.

## Current implementation slice

The first local chrome slice normalizes the header navigation-toggle radius to
the existing 6 px control treatment (`rounded_md`) in
`desktop/gpui/src/shell.rs`. This is a small, reversible visual adjustment;
its golden-image result remains `pending` until the reference capture and
live comparison path exist.
