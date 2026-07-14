# Soundtoys 5.5 — SoundToys (effects bundle / suite — meta card)

| | |
|---|---|
| Vendor / ver | SoundToys · v5.5 (User Guide "Version 5.5: For Mac and Windows") |
| Type | Bundle / suite — 21 creative-effect plug-ins + Effect Rack host. Covers delay, reverb, saturation, modulation (filter/phaser/tremolo/pan), pitch/doubling, leveling/compression, EQ |
| Format | AU · VST2 · VST3 · AAX (Native + AudioSuite) — Mac & Windows. macOS 10.14+, Windows 10+, **no Linux**. License via iLok (2 activations; account optional for first) |
| Source | manual: `SoundToys/Soundtoys 5.5.pdf` (bundle User Guide) · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

> **This is a meta/index card for the whole 5.5 bundle.** It covers what ships, the GUI/preset/tempo conventions shared by *every* Soundtoys plug-in, and the v5.5-specific resizing feature. **Per-plugin controls live in their own cards** under `easby/shared/plugins/SoundToys/` — see the index below. The bundle PDF does **not** document individual plug-in parameters.

## What it does
Soundtoys 5.5 is SoundToys' flagship creative-effects collection: a set of dedicated, character-rich processors modeled on (and inspired by) classic/rare studio hardware, plus **Effect Rack**, a host that chains up to 6 of them into one savable multi-effect. The musical job is *character and movement* — analog warmth/distortion, tape & analog echoes, lush plate/space reverbs, rhythmic filter/pan/tremolo modulation, pitch doubling/shifting, and aggressive leveling — rather than transparent corrective processing. Everything shares a consistent analog-style GUI, a cross-plugin preset manager (pattern presets can be shared between plug-ins), a unified tempo/MIDI-sync system, and (new in 5.5) resizable interfaces. Distinct for: musical, vibe-forward "secret sauce" effects trusted across pro mixing/production, and the Effect Rack's drag-and-drop chaining with a global feedback/recycle loop.

## What's in the bundle (full plug-in roster — each has its own card)
Per the manual's "The Effects" list (`*` = also ships a smaller "Little" version):

| plug-in | one-line job | card |
|---|---|---|
| **Crystallizer** | H3000-esque pitch-based granular + reverse delays | `SoundToys Crystallizer.md` |
| **Decapitator** | Analog saturation / harmonic distortion (5 hardware styles) | `SoundToys Decapitator.md` |
| **Devil-Loc / Devil-Loc Deluxe** `*` | Vintage analog audio leveler / crusher-compressor | `SoundToys Devil-Loc.md`, `SoundToys Devil-Loc Deluxe.md` |
| **EchoBoy / EchoBoy Jr.** `*` | Echo & delay — tape, vintage, modern styles | `SoundToys EchoBoy.md`, `SoundToys EchoBoy Jr.md` |
| **FilterFreak 1 & 2** | Single/dual-band resonant modulated filter w/ rhythm | `SoundToys FilterFreak.md` |
| **Little AlterBoy** | Voice manipulation (pitch/formant/robot) | `SoundToys LittleAlterBoy.md` |
| **MicroShift / Little MicroShift** `*` | Micro-pitch shift / widening | `SoundToys MicroShift.md`, `SoundToys Little MicroShift.md` |
| **PanMan** | Rhythmic auto-panning | `SoundToys PanMan.md` |
| **PhaseMistress** | Rich analog-style phaser w/ programmable modulation | (no dedicated card present) |
| **PrimalTap / Little PrimalTap** `*` | Retro delay with Freeze | `SoundToys PrimalTap.md`, `SoundToys Little PrimalTap.md` |
| **Radiator / Little Radiator** `*` | Analog tube mix channel (warmth/EQ/drive) | `SoundToys Radiator.md`, `SoundToys Little Radiator.md` |
| **Sie-Q** | Vintage German (Siemens-style) EQ | `SoundToys Sie-Q.md` |
| **SpaceBlender** | Experimental reverb w/ envelope-shaping (5.x) | (no dedicated card present) |
| **SuperPlate** | 5 electromechanical plate reverbs w/ Auto-Decay (5.x) | (no dedicated card present) |
| **Tremolator** | Tremolo / rhythmic amplitude modulation | (no dedicated card present) |
| **Little Plate** | Simple EMT-140-style plate reverb | `SoundToys Little Plate.md` |
| **Effect Rack** | Host that chains up to 6 of the above + global controls | `SoundToys EffectRack.md` |

*("Common Effects" cross-reference in the manual maps tasks → plug-ins: Reverb → SuperPlate/Little Plate/SpaceBlender/EchoBoy; Doubling → Crystallizer/EchoBoy/PrimalTap/MicroShift/Little MicroShift; Saturation/Distortion → Decapitator/Radiator/Devil-Loc; Pitch Transposition → Crystallizer/Little AlterBoy; Auto-pan → PanMan/Tremolator; Wah/Envelope filter → FilterFreak; Phasing → PhaseMistress/FilterFreak; etc.)*

## Controls (shared GUI conventions → how every Soundtoys plug-in behaves)
These behaviors are identical across the whole bundle (the per-plugin cards list each plug-in's *actual* parameters).

| control / convention | how it works | when / why it matters |
|---|---|---|
| **Knobs** | Click-drag up/right = increase, down/left = decrease | Standard rotary editing |
| **Knob — fine control** | Hold **Cmd** (Mac) / **Shift** (Win) while dragging | Precise values (e.g. wet/dry, time) |
| **Knob — exact value** | Click the knob's **title** to toggle title ↔ numeric readout | Read/verify the current value |
| **Knob — default** | **Double-click** the knob | Reset to factory default |
| **Knob — jump to marking** | Click a text marking (min/max/etc.) around the knob (not universal) | Snap to a labeled value |
| **Knob — Parameter Lock** | **Ctrl+Opt/Alt-click** a knob → turns **red**; that knob won't change when loading presets (still hand-editable). **Not saved** with the session | Audition presets while keeping wet/dry mix (or any param) fixed |
| **Switches** | Click to toggle; selection-style buttons deselect siblings; LED indicates engaged/mode | On/off and mode selection across all plug-ins |
| **LCD displays — nudge** | Up/down arrows step through value/preset lists | Increment params or presets |
| **LCD displays — type** | Click a numeric field (e.g. BPM) → type value → Return; or click-drag like a knob | Enter exact tempo/values from keyboard |
| **LCD displays — pop-up menu** | Click a text field → drop-down selection menu | Choose modulation source, style, etc. |
| **LED meters** | Around threshold knobs show input level | Set thresholds (e.g. Devil-Loc) by eye |
| **Sliders** | Variable; used for levels, wet/dry, frequency; can be grouped (e.g. PrimalTap Feedback A/B when A-B Link on) | Multi-value sections |
| **Tempo — 3 ways** | (1) **Tap** the Tempo button in time, (2) **type BPM** 30–240 into the LCD, (3) **MIDI sync** toggle = lock to host clock | Sync delays/modulation/rhythm to the song |
| **Tempo — gotcha** | Tap & manual-BPM only work when **FREE** is on and **not** synced to MIDI. MIDI switch disables Tap Tempo; manual BPM entry only in Effect Rack | Know why tap is greyed out |
| **Preset header** | Prev/Next ◄►, **Save** (floppy icon = Save As → file dialog), **Compare** (↺, lights red after edits — toggles original ↔ edits; **unsaved edits are lost on preset change**) | Browse/save/A-B presets |
| **Preset manager** | Click the name field → categorized folder menu (Basics/Places/Spaces/Effects/Vocals/Drums/Instruments/User). Hundreds of factory presets by SoundToys + guest producers; **Organize…** to create/rename/move folders; presets shareable between plug-ins | Fast recall; reuse pattern presets across the line |
| **Interface Size (NEW in 5.5)** | Drag the **lower-right corner**, or menu icon → **Interface Size**: 75 / 100 / 125 / 150 / 175 / 200 %. **Default 150 %.** Saved per-plugin, persists on relaunch. **All individual plug-ins except Effect Rack** are resizable | Fit your display / HiDPI; the headline 5.5 feature |
| **Bypass** | Top-bar BYPASS button | A/B effect vs. dry |

## Use by lens
- **Producer (create):** The bundle is a sound-design toolkit. Reach first for character: Decapitator/Radiator for analog grit & warmth, EchoBoy/Crystallizer/PrimalTap for echoes and granular/reverse textures, MicroShift/Little AlterBoy for fat doubles and vocal manipulation, FilterFreak/PhaseMistress/Tremolator/PanMan for rhythmic movement, SuperPlate/Little Plate/SpaceBlender for space. Use **Effect Rack** to stack signature chains and the global feedback loop for runaway/modulated ambiences. Start from the categorized factory presets as launch pads, then tweak with **Parameter Lock** on the wet/dry so browsing presets keeps your blend.
- **Mixing (balance):** Use individual plug-ins as inserts; rely on each one's wet/dry **Mix** for parallel character without extra busses, or set 100 % wet on aux sends. The shared **tempo/MIDI sync** keeps every time-based effect locked to the song. Devil-Loc / Decapitator add aggressive level and density on drums/vocals; Sie-Q / Radiator add tone & vibe. These are *flavor*, not surgical EQ/dynamics.
- **Mastering (finalize):** Generally not mastering tools — they are colored, character-forward creative effects with no M/S, no linear-phase, no metering suite. At most a *very* light parallel touch (Radiator/Decapitator warmth, a hair of MicroShift width) via low Mix on a stem. Use dedicated mastering plug-ins (e.g. FabFilter Pro-L 2 / Pro-Q for actual finalizing).

## Notes / gotchas
- **Compare/unsaved edits:** changes to a preset are **lost** if you switch presets without saving — Save As with a suffix ("…2", "…FINAL") before moving on.
- **Tempo tap is greyed** unless FREE is on and MIDI sync is off; manual-BPM typing is Effect-Rack-only (other plug-ins: tap or MIDI).
- **Resizing (5.5):** every plug-in *except Effect Rack* resizes (75–200 %, default 150 %), saved per-plugin.
- **iLok:** purchases include **2 activations**; you can activate one machine without an iLok account, but need the account for the second. Linux unsupported.
- **"Little" versions** (Devil-Loc, EchoBoy Jr., MicroShift, PrimalTap, Radiator + Little Plate / Little AlterBoy) are streamlined, lower-CPU, fewer-control variants of the full plug-ins — grab them for quick results / lighter sessions.
- **Effect Rack vs. standalone:** the older Soundtoys 5 Effect Rack manual implies bundled effects ran rack-only; in the 5.x line the effects also install as **standalone** plug-ins (each format folder lists them). Treat per-plugin cards as the source of truth for standalone availability.
- **File locations (Mac):** AU `…/Library/Audio/Plug-Ins/Components`; VST `…/VST/Soundtoys`; VST3 `…/VST3/Soundtoys`; AAX `…/Library/Application Support/Avid/Audio/Plug-Ins/Soundtoys`; **Presets** `/Users/Shared/Soundtoys/Soundtoys 5`; extras `/Applications/Soundtoys`. Uninstall via `RemoveSoundtoys.dmg`.
- **Support intake** wants: product version + serial, DAW version, interface/hardware, OS, problem description (`support.soundtoys.com`, `support@soundtoys.com`).

## Deep spec (Programmer only)
not reverse-engineered — capability only. (No bundle-level DSP model. Individual Soundtoys effects are unmodeled here; the `easby-programming/plugins/` deep specs are other-vendor plug-ins, none matching this bundle.)
