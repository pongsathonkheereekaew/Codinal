# FabFilter Simplon — FabFilter (filter)

| | |
|---|---|
| Vendor / ver | FabFilter · (version not stated in manual) |
| Type | Dual multimode resonant filter (LP/HP/BP · 12/24/48 dB/oct · 3 characteristics · serial/parallel) |
| Format | VST, VST3, CLAP, AU (Audio Units, macOS only), AAX Native, AudioSuite |
| Source | manual: `FebFilter Simplon/FabFilter Simplon.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
FabFilter Simplon is a stripped-down, affordable filter plug-in: a simplified version of FabFilter Volcano with two independent multimode filters and none of Volcano's modulation rig (no LFOs, envelope generators, followers, or modulation matrix). Each filter offers low-pass / high-pass / band-pass responses at 12, 24, or 48 dB/octave, with a Frequency (5 Hz–75 kHz) and Peak (resonance) control that runs from gentle warming to full self-oscillation. The defining feature is the filter *character*: each filter picks one of three algorithms — **FabFilter One** (the original synth filter, good general-purpose), **Gentle** (smooth, clean), and **Raw** (lots of overdrive, self-oscillating, over-the-top) — the same fat, analog-sounding self-oscillating filters used in FabFilter One and Volcano. The two filters run **serial or parallel**, giving up to 27 filter-type combinations, and they're driven from a large interactive display where you drag the filter curves (separately, in parallel, or in opposite directions). Built for rich, harmonic-heavy material (synths, distorted guitar, full mixes) where you want musical resonant sweeps, deep bass, and creative tone-shaping rather than surgical EQ.

## Controls (every param → musical effect)

### Per filter (Filter 1 and Filter 2 — identical controls)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Frequency** | 5 Hz – 75 kHz (type e.g. `1k`, `A4`, `C#3+13`) | Center / cut-off frequency of the filter. | Main tone control — sweep for filter movement, or park to carve a band. |
| **Peak** | min → max resonance | Filter resonance. A little = warmer, more characterful tone; at max the filter **self-oscillates** (produces a tone of its own). | Add bite/emphasis at the cutoff; crank for acid squelch, vocal/formant timbres, or self-oscillation drones. |
| **Characteristic** | FabFilter One / Gentle / Raw (drop-down button per filter) | Selects the filter algorithm = its sound + overdrive flavor. **FabFilter One** = original synth filter, general-purpose. **Gentle** = smooth, clean. **Raw** = heavy overdrive, aggressive, its own character. | One for clean/musical filtering; Gentle for transparent shaping; Raw for dirt, grit, and over-the-top resonance. |
| **Response** | LP / HP / BP (three buttons) | Filter shape. **Low Pass** passes below the frequency, **High Pass** passes above, **Band Pass** passes only around the frequency. | LP to roll off highs / shape low end; HP to thin/remove mud; BP for telephone/formant/isolated-band tones and sweeps. |
| **Slope** | 12 / 24 / 48 dB/octave (switch) | Steepness — how aggressively frequencies past the corner are filtered. 12 = gentle, leaves more through; 48 = steep, near-brickwall. | 12 for subtle musical shaping; 48 for tight, dramatic cuts and surgical sweeps. |
| **Bypass** | on / off (small power button left of the characteristic menu, one per filter) | Switches that filter on/off. Bypassed filter looks disabled but its controls still work; bypass is click-free. | A/B a filter in/out; run a single-filter setup by bypassing the other. |

### Global
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Serial / Parallel** | Serial ↔ Parallel (switch) | Routing of the two filters. **Serial** = filter 1 → filter 2 (cascade; e.g. stack slopes, or HP then LP for a band). **Parallel** = both filters process the input independently and sum (e.g. two resonant peaks at once). | Serial to build steeper/compound shapes; Parallel for dual-peak, formant, and "two filters at once" textures. |
| **Input Gain** | −20 … +20 dB (default 0; type e.g. `+6dB`, `2x`) | Gain into the filters. Driving harder pushes the (especially Raw) characteristic into more saturation/overdrive. | Push up to dirty up / saturate the sound and drive the filter; back off to clean up. |
| **Output Gain** | −20 … +20 dB (default 0) | Output level, to compensate for gain changes from input drive or resonance. | Bring level back to sane after driving/resonating; final gain stage. |
| **Effect Mix** | 0 % … 100 % | Dry/wet mix between the unprocessed input and the filtered signal. | Parallel/“New York” style filtering — blend filtered character under the dry source; tame extreme settings. |

### Linking the two filters (modifier moves, not separate params)
- **Frequency + Peak together (parallel):** hold **Alt** while turning a Frequency or Peak knob → both filters move in the **same** direction (e.g. dual resonant band-pass sweep).
- **Opposite directions:** hold **Ctrl+Alt** (Windows) / **Cmd+Alt** (Mac) while dragging a knob → the two filters move in **opposite** directions (great for vocal/formant timbres).
- On the display: drag a filter button (1 or 2) for that filter's Freq+Peak; drag the **center button** to move both in parallel (or Alt+drag a filter button); **Ctrl/Cmd+drag** a filter button to move both in opposite directions.

## Use by lens
- **Producer (create):** This is Simplon's home turf — a creative sound-design filter. Pick **Raw** for grit/self-oscillation, **FabFilter One** for fat musical sweeps. Automate Frequency (and Peak) for builds, drops, and filter risers; map them to MIDI for hands-on tweaking. Use **two filters in parallel + Alt-linked sweeps** for dual-peak/formant "vocal" movement, or **opposite-direction** linking for morphing timbres. Run **serial HP→LP** for a movable band-pass, or stack slopes for brutal 96 dB-equivalent cuts. Crank Peak to self-oscillation for tunable tones/drones. Feed it harmonic-rich material (synths, distorted guitar, full loops) for best results. No internal modulation though — all movement comes from automation/MIDI/host.
- **Mixing (balance):** Usable as a colored utility/effect filter rather than a corrective EQ. HP one filter to remove rumble/mud, LP the other to tame highs (serial), with modest Peak for a musical bump. **Effect Mix** lets you blend the filtered tone parallel with the dry signal so heavy settings stay subtle. Light Input Gain (esp. with Raw) adds harmonic saturation to thin sources. Keep resonance in check to avoid ringing. For clean, precise EQ moves reach for Pro-Q instead.
- **Mastering (finalize):** Not a mastering tool — no linear-phase, mid/side, spectrum analyzer, or metering, and the characteristics (especially Raw) intentionally color the sound. Use only for deliberate creative coloration on a bus/send, with low Peak and Effect Mix well under 100 %. For master-bus tonal shaping use Pro-Q / Pro-MB.

## Notes / gotchas
- **No modulation at all.** Unlike Volcano, Simplon has no LFOs, envelope generators, envelope followers, or mod matrix — filter movement only comes from automation, MIDI Learn, or the host. For modulation, step up to Volcano 3.
- **Three characteristics aren't EQ curves — they're algorithms** with different overdrive/saturation behavior. Raw self-oscillates and overdrives hard; Gentle is the cleanest; FabFilter One sits between.
- **Serial vs Parallel changes everything** about how the two filters interact — check both when a patch sounds off.
- **Self-oscillation** at max Peak generates a tone on its own; manage levels with Output Gain.
- **Frequency goes to 75 kHz** (above audio) — useful when sweeping or for high band-pass corners; at extreme settings, mind aliasing on bright/distorted sources.
- **Per-filter bypass buttons** are the small power buttons at the left of each filter's characteristic menu; bypassed filters still respond to control changes (click-free).
- **MIDI Learn** on any parameter (incl. **Enable MIDI**, **Clear**, **Revert**, **Save** submenu); also **MIDI Program Change / Bank Select** for preset recall. Routing MIDI to an effect plug-in is host-specific (Pro Tools: MIDI track → `FabFilter Simplon -> channel 1`; Logic: AU MIDI-controlled Effects + Side Chain; Ableton: "MIDI to" the audio track; Cubase: MIDI track output — VST3 only the first plug-in on a track receives MIDI). In VST3, Simplon appears in the host's **Filter** category.
- **Knob control:** vertical drag, rotate, mouse-wheel, or double-click for text entry. Reset to default = **Ctrl/Cmd+click**; fine-tune = hold **Shift** while dragging (Pro Tools uses its own shortcuts for both).
- **Smart Parameter Interpolation** smooths parameter/MIDI changes (no zipper noise/clicks). Standard FabFilter **Undo/Redo** and `.ffp` preset system; presets are cross-platform (Win/macOS), default folder `Documents/FabFilter/Presets/Simplon`. **Low CPU** — explicitly lighter than Volcano (AltiVec/SSE optimized); sample-accurate automation. No oversampling/latency control mentioned.

## Deep spec (Programmer only)
Not reverse-engineered — capability only. (No matching file under `easby-programming/plugins/`. Closest deep spec that exists: `Volcano3.md` — Simplon is essentially Volcano with the modulation section removed, so its filter-core/characteristic notes are the nearest reference; the FabFilter One filter is the shared origin of Simplon's "FabFilter One" characteristic.)
