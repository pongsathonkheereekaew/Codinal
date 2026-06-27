# SoundToys EffectRack — SoundToys (multi-effect host / creative effects chainer)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 (Soundtoys 5 generation, manual © 2015) |
| Type | Multi-effect rack / container — chains up to 6 of the 14 bundled Soundtoys effects with global level, mix, tempo & feedback |
| Format | VST / VST3 / AU / AAX (Mac & Windows) |
| Source | manual: `SoundToys EffectRack/SoundToys EffectRack.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Effect Rack is a self-contained host plug-in that turns the Soundtoys effect collection into a single creative multi-effects unit. You drag and drop up to **6 effects** from a Gear List into a vertical rack, reorder/insert/swap them, and the signal flows top-to-bottom through the chain. A small **Control Panel** at the top wraps the whole chain in **global** Input, Output, Mix, Feedback (recycle), and Tempo controls, so a custom chain behaves like one effect — savable and recallable as a single preset across DAWs. It ships preloaded with **14 effects**: Crystallizer, Decapitator, Devil-Loc Deluxe, EchoBoy, EchoBoy Jr., FilterFreak, FilterFreak 2, MicroShift, PanMan, PhaseMistress, PrimalTap, Radiator, Sie-Q, and Tremolator (SuperPlate and SpaceBlender can be added if separately licensed). The distinct trick is the **global Feedback / Recycle** loop — routing rack output back into its input to build lush echoes, runaway saturation, and DIY modulated ambiences that no single effect produces. These bundled effects run **only inside Effect Rack** (for standalone instances, Soundtoys 5 is the product). Each bundled effect has its own capability card / manual; this card covers the **rack container** itself.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Tempo** (LCD display) | BPM (e.g. 120.0); 3 entry modes: MIDI sync (default), Tap, manual | Master tempo fed to every loaded effect for rhythmic sync — delays, modulation rates, rhythm patterns all lock to this | Sync the whole chain to the song; manual-enter or tap to dial a "feel" for unrecorded/free-time material |
| **Sync** (Free / MIDI) | toggle pair | MIDI = lock to host project tempo; Free = run effects at the manually set/tapped BPM, ignoring host | MIDI for in-time effects; Free to deliberately drift off-grid or set a fixed feel |
| **Tap Tempo** (grey button) | tap repeatedly | Sets BPM by tapping; useful for live/click-less tracks and finding modulation feel | Tracks with no click; quick "by ear" tempo |
| **Input** | MIN…MAX (level into first slot) | Sets the level going *into* the first effect in the rack | Drive the chain harder/softer into the first unit; manage gain staging at the front |
| **Output** | MIN…MAX (level after last slot) | Sets the level *leaving* the rack after the last effect | Trim a too-hot chain or match bypassed level without re-tweaking every plug-in |
| **Feedback** (a.k.a. Recycle) | MIN…MAX | Routes a portion of rack **output back into its input** — builds repeating echoes, increases resonant presence/saturation; extreme = runaway self-oscillation | Lush/over-the-top delays, thickening, modulated reverbs and ambiences. **Boosts level a lot — careful with high-gain units (Decapitator, Radiator, Devil-Loc) loaded** |
| **Mix** (global) | DRY…WET, 12 o'clock = 50/50 | Dry/wet blend of source vs. processed rack output; left = less wet, right = more wet | Parallel/blended effects on inserts. On aux/buss sends: set **100% wet** and use send level instead |
| **Toolbox — Show/Hide Gear** | toggle | Shows or hides the Gear List panel (the 14-effect palette on the right) | Show to drag effects in; hide to reclaim screen space once the chain is built |
| **Rack slots (1–6)** | drag & drop | Each slot hosts one effect; signal runs top→bottom. Drag from Gear List to add; drag above/below to insert; drop onto an item (highlights yellow) to replace; drag back to Gear List to remove | Build/reorder the chain. Order matters — each unit feeds the next, so watch per-effect Input/Output when driving hard |
| **Per-slot — Effects Preset Menu** (gear icon) | per effect | Loads/modifies/saves presets for that individual effect inside the rack (in standalone this menu lives at top) | Quickly audition factory tones for one unit without leaving the rack |
| **Per-slot — Power** (green) | on/off | Per-unit bypass; stored with the preset | A/B whether one effect earns its place; automate a unit on/off for arrangement moments (e.g. a long delay) |
| **Per-slot — Solo** (red S) | on/off | Mutes every *other* rack item so you hear one in isolation | Focus on/dial in a single effect in the chain quickly |
| **Preset header** (top bar) | prev/next ◄►, save, A/B | Browse, save and recall the whole rack as one Soundtoys preset (hundreds of factory presets, categorized) | Recall a full chain instantly; portable across supported DAWs as insert or send |

## Use by lens
- **Producer (create):** This is a sound-design playground. Stack effects for signature chains — Decapitator + EchoBoy slap + MicroShift for fat vocals; Crystallizer + PhaseMistress for swirling pitched lead-guitar delays; FilterFreak + Tremolator + PanMan rhythm modes for remix/rhythmic chaos. Lean on the **Feedback/Recycle** knob to invent modulated reverbs and runaway ambiences. Start from the categorized factory presets (Guitar/Vocals/Drums/Sound Design/Spaces/Modulation) as launch pads, then rearrange.
- **Mixing (balance):** Use as a single insert with global **Mix** for parallel character (saturation/echo) without a separate buss, or on an aux at **100% wet** fed by sends. Global **Input/Output** make gain-staging the whole chain one move. Per-slot **Power/Solo** speed up deciding what's actually helping. Keep an eye on per-effect Input/Output when any unit is driven hard, since each feeds the next.
- **Mastering (finalize):** Not a mastering tool — it's a creative/character chain of colored effects with no metering, M/S, or transparent processing. At most a light parallel-blended texture on a stem via low global Mix; reach for dedicated mastering plug-ins for actual finalizing.

## Notes / gotchas
- **Max 6 slots.** Signal is strictly serial, top→bottom.
- **Feedback = level boost.** High Feedback significantly raises output, dangerous with high-gain units (Decapitator/Radiator/Devil-Loc) at high monitor volume.
- **Bundled effects are rack-only** — they don't appear as standalone plug-ins (that's Soundtoys 5). **SuperPlate** and **SpaceBlender** show in the rack and in some presets but their params are locked unless separately licensed.
- **Automation:** 128 generic automatable params, auto-assigned to loaded effects and renamed live as `S<slot>: <Effect>: <Param>` (e.g. `S1: Decapitator: Drive`). All params are forced **continuous** (discrete ones like Decapitator Style still show string values when the DAW supports it). **Heavy EchoBoy chains can exhaust the 128 slots.** Pro Tools may need automation params disabled/re-enabled to refresh names.
- **Automation is locked once written** — re-ordering/adding/removing effects after writing automation misroutes it; the only fix is to erase automation (save preset, remove & reload a fresh Effect Rack). Recommendation: **settle the patch before writing automation.**
- **Tempo defaults to MIDI sync**; switch to Free to ignore host tempo.
- Self-contained design means a custom chain saves/recalls as one preset and travels between DAWs as an insert or send.

## Deep spec (Programmer only)
not reverse-engineered — capability only. (The container itself is unmodeled; individual bundled effects have their own capability cards under `easby/shared/plugins/SoundToys/`, e.g. Crystallizer, Decapitator, Devil-Loc Deluxe.)
