# MB White Room — Make Believe Studios (reverb)

| | |
|---|---|
| Vendor / ver | Make Believe Studios (DSP by Metric Halo) · v4.0.95.259 (manual rev 4.1.00, Feb 2026) |
| Type | Reverb — fixed-algorithm digital reverb emulation ("Detroit classic" hip-hop hardware verb) |
| Format | AU, AAX, VST2, VST3 (macOS) · AAX, VST2, VST3 (Windows); Metric Halo hardware DSP via MIOConsole3d. AAX is Native-only (no HDX/Carbon DSP). |
| Source | manual: `MB White Room/MB White Room.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
A one-knob-philosophy reverb that recreates a single, specific classic digital-reverb sound — the deep, polished, slightly bright space heard on landmark late-'90s/early-'00s hip-hop and pop records out of F.B.T. Studios (Eminem, Dr. Dre, the Bass Brothers; Brad Paisley too). The DSP is a fixed algorithm: there is no decay-character, size, EQ, or diffusion menu. Instead of giving you a blank reverb to design, it hands you *one great reverb* already tuned, and exposes just three controls to place it: wet/dry **Mix**, **Pre-Delay**, and reverb **Length** (decay scaling). At defaults it reproduces the original studio signal path exactly ("that Dr. Dre reverb sound"); the parameter controls let it range from the original huge dense space down to tight explosive slap-backs, on a bus or in-line. Built on Metric Halo's MHShell, so it carries the full MH header (A/B snapshots, Blend morph, Undo/Redo, Compare, soft Bypass) despite the tiny control surface.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Mix** | 0 → 100 (% wet) · default **100%** | Dry/wet ratio. 0 = fully dry (no reverb); 100 = 100% wet (no dry signal). Standard linear wet/dry. | Default 100% wet is designed for a **send/bus** (aux return). For an **in-line insert** on a track, pull down toward ~10–35% to blend reverb under the dry source. |
| **Pre-Delay** | −30 ms → +130 ms · default **0** (= original processor delay) | Time offset before the reverb tail starts, relative to the original hardware's built-in delay. **0 = the original processor delay.** Positive pushes the tail later (more separation, vocal clarity, sense of size); negative pulls it earlier/tighter than the original. | Increase (+20–80 ms) to keep vocals/lead clear and let the verb bloom behind the transient; set toward 0 / negative for tight, immediate, in-your-face slaps. |
| **Length** | 0 → 100 (% of original decay) · default **100%** | Scales reverb decay time as a percentage of the original processor's reverb decay. 100% = full original tail; lower = shorter decay. | Pull down for tight rooms, drum ambience, and "explosive slap-backs"; leave high for the big, dense, classic space. |

**Defaults reproduce the F.B.T. original** verbatim (Mix 100%, Pre-Delay 0, Length 100%). Controls appear on mouse-over anywhere in the window. Knob values show as a tooltip overlay while dragging. **Right-click a control to type an exact value.**

### MHShell header controls (shared across all Metric Halo / Make Believe plugins)
| control | what it does |
|---|---|
| **A / B snapshot registers** | Two parameter snapshots vs. the loaded preset. Light grey = empty, dark grey = filled/unselected, blue = filled/selected. Click empty = capture current; click filled/unselected = recall; click selected = toggle to the other. Option-click = overwrite. Stored in plug-in state, not saved as presets. |
| **Copy (N/C → A>B / B>A)** | Copies the selected register into the other, overwriting it. Inactive (N/C) until a register is in use. |
| **Blend** | Smoothly interpolates (morphs) parameters between A and B on **one** instance (not parallel processing). MIDI-mappable + DAW-automatable for A→B sweeps. Does not affect Bypass state. Works best when A and B share the same indexed/stepped settings and differ only in smooth params; classic trick: load same setting in both, flatten one toward "off," blend to dial the perfect amount. |
| **Undo / Redo** | Per-plugin parameter undo/redo from the header (white = available, grey = none). |
| **Help (?)** | Toggles tooltip display; hold the `?` key to see tooltips while disabled. |
| **UI Size** | Pull-down UI scale (e.g. 90–140%); remembered for next insert. |
| **Compare** | Lit when current settings differ from the loaded preset; click to A/B against the saved preset. Requires a preset loaded first. |
| **Bypass** | Soft (click-free) bypass. |
| **MH logo icon** | Opens sidebar: About (version, web/support/manual links, Reveal Plug-In File), Current Release Notes, and an Update tab (+ red dot) when an update is available. |
| **Preset row** | Hamburger menu (load/save/manage), step-through ◀ ▶ buttons, and preset name/selector menu (auditions on select). |

## Use by lens
- **Producer (create):** This is the fast "make it sound like the record" button. Drop it on a vocal or drum bus at defaults for the instant classic Detroit verb — no tweaking. For beats, shorten **Length** and zero/negative **Pre-Delay** for tight slap-backs that sit forward; for hooks, raise **Pre-Delay** so the vocal stays crisp over a long tail. Use **Blend** to automate a dry verse → washed-out chorus in one instance.
- **Mixing (balance):** Use as a **send** (Mix 100%) so multiple sources share one cohesive space and you control level with the aux fader. **Pre-Delay** is the depth/clarity knob — push it up to pull the wet behind the dry and protect intelligibility; **Length** matches the verb to tempo/density (shorter on busy/up-tempo material). As an insert, drop **Mix** to ~15–30%. No built-in EQ/damping, so high-pass/duck the return externally if it clouds the low-mids.
- **Mastering (finalize):** Not a mastering tool — it's a fixed-character send reverb with no width/tone shaping or detented subtlety. Avoid on a 2-bus. (If a mix arrives needing glue ambience, that belongs in the mix stage, not mastering.)

## Notes / gotchas
- **Fixed algorithm, three knobs.** No size/decay-shape/diffusion/EQ/modulation/width controls — the *sound* is the product; you only place it (Mix), offset it (Pre-Delay), and scale its tail (Length). Length is a *percentage of the original decay*, not an absolute time in seconds; Pre-Delay is *relative to the original processor delay* (hence the −30 ms floor).
- **Default = send/100% wet.** Pull Mix down for inserts. Defaults are intentionally the exact F.B.T. studio settings.
- **No oversampling / latency notes** in the manual (the header diagram references generic MHShell "Oversampling modes," but White Room exposes no oversampling control); treat reported plug-in latency as the host value. Pre-Delay is a time control, not added processing latency.
- **A/B + Blend are stored in plug-in state, not in presets.** Blend is one-instance interpolation, not parallel A∥B.
- **AAX is Native-only** in v4 — no HDX/Carbon DSP executables. v4 requires the updated v4 license; its installer overwrites earlier versions.
- Right-click any knob to type exact values; mouse-over reveals the controls (they're hidden at rest by design).

## Deep spec (Programmer only)
not reverse-engineered — capability only.
