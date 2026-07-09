# FabFilter Micro — FabFilter (filter / saturation)

| | |
|---|---|
| Vendor / ver | FabFilter · (version not stated in manual) |
| Type | Single resonant filter (LP/HP, 12 dB/oct) with envelope follower + analog-style saturation |
| Format | VST, VST3, CLAP, AU (Audio Units, macOS only), AAX Native, AudioSuite |
| Source | manual: `FebFilter Micro/FabFilter Micro.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
FabFilter Micro is a deliberately minimal single-filter plug-in built around the same smooth, resonant filter FabFilter first shipped in the FabFilter One synth (2004). One 12 dB/octave filter switchable between low-pass and high-pass, with a Peak (resonance) control that goes from gentle warming all the way to self-oscillation. What makes it more than a basic filter is its character: independent Input Gain and Output Gain let you push the filter into raw analog-style saturation/distortion, while a built-in envelope follower can modulate the cut-off frequency from the incoming signal (positive or negative, with adjustable speed). The whole thing is driven from a large interactive filter display where you just drag the peak around. Lightweight, CPU-cheap, and ideal for both clean utility filtering and creative screaming/saturating filter effects.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Frequency** | full audio range (Hz; type e.g. `1k`, `A4`, `C#3+13`) | Cut-off frequency of the filter. | Main tone control — sweep it for filter movement, or park it to carve lows/highs. |
| **Peak** | min → max resonance | Filter resonance. A little = warmer, more characterful tone; at max the filter **self-oscillates** at the cut-off frequency (produces a sine-like tone). | Add bite/emphasis around the cutoff; crank for acid-style squelch or pure self-oscillation drones. |
| **Response** | LP / HP (two buttons) | Selects filter shape: low-pass or high-pass. Always 12 dB/octave steepness. | LP to roll off highs / tame brightness; HP to thin out / remove mud and rumble. |
| **EF Level** (Level) | −/center/+ (bipolar; center = off) | Amount of cut-off **frequency modulation by the built-in envelope follower**. Left of center = negative (louder input lowers cutoff), right = positive (louder input raises cutoff), center = no modulation. Small reset button at top of the knob turns modulation fully off. | Make the filter "breathe" with the signal — auto-wah, dynamic openings on transients, ducking-style sweeps. |
| **EF Speed** (Speed) | fast (left) ↔ slow (right); center = good default | How quickly the envelope follower reacts. Full left = fast/aggressive response to changes; full right = slow/smooth; center = balanced. | Fast for snappy percussive auto-wah; slow for gentle evolving sweeps. |
| **Input Gain** | dB (type e.g. `+6dB`, `2x`; in bottom-right "In:" readout) | Gain applied **before** the filter. Drives the filter harder → more saturation/distortion. | Push it up to dirty up the sound and add analog grit; the core "distortion amount" control. |
| **Output Gain** | dB ("Out:" readout; drag the output button vertically) | Gain applied **after** the filter, to compensate for level changes from input drive or resonance. | Bring the level back to sane after saturating; gain-stage the output. |

**Linked drive trick:** hold **Alt** (Windows) / **Alt** (or **Shift** in Pro Tools) while dragging Input *or* Output Gain — they move together in opposite directions, so you change the **distortion amount in one move** without changing overall output level.

## Use by lens
- **Producer (create):** This is a sound-design filter. Map Frequency to a knob or automate it for builds/sweeps. Crank Peak toward self-oscillation for acid/squelch lines or to generate a tunable sine. Use the envelope follower (EF Level off-center, EF Speed to taste) for auto-wah and signal-reactive movement on bass, synths, drums, or guitars. Push Input Gain for raw analog saturation — great for grungy basses, lo-fi textures, and aggressive leads. Filter peak is fully automatable, and MIDI Learn lets you grab Frequency/Peak from a controller for live tweaking.
- **Mixing (balance):** Use as a clean, cheap utility filter — HP to remove rumble/mud, LP to tame harsh highs, with low Peak for a musical bump at the corner. Light Input Gain adds subtle harmonic warmth/saturation to thin sources. The envelope follower can act as a simple dynamic filter (e.g. open brightness only on louder hits). Keep Peak modest in a mix context to avoid ringing.
- **Mastering (finalize):** Not a mastering tool — single 12 dB/oct filter, no linear-phase/mid-side/metering. For broad tonal shaping or surgical EQ on a master, reach for Pro-Q; use Micro only for deliberate coloration/effect sends.

## Notes / gotchas
- **Filter slope is fixed at 12 dB/octave** — no steeper options.
- **Self-oscillation** at max Peak generates a tone on its own; watch output levels (use Output Gain to compensate).
- **Input/Output gain ARE the distortion controls** — Micro has no separate "drive" knob; saturation comes entirely from how hard Input Gain pushes the filter.
- **Envelope follower needs signal** to do anything; EF Level center = bypassed. The little **EF light** above the Level/Speed knobs shows how much frequency modulation is currently happening.
- **Interactive display:** drag the peak to set Frequency + Peak together; **Ctrl+click** (Windows) / **Cmd+click** (Mac) the peak toggles LP↔HP.
- **MIDI Learn** on any parameter (incl. Enable MIDI / Clear / Revert / Save submenu). Routing MIDI to an effect plug-in is host-specific (Pro Tools MIDI track → `FabFilter Micro -> channel 1`; Logic via AU MIDI-controlled Effects + Side Chain; Ableton via "MIDI to"; Cubase MIDI track output). In VST3, Micro appears in the host's **Filter** category.
- **Knob control:** vertical drag, rotate, mouse-wheel, or double-click for text entry. Reset to default = **Ctrl/Cmd+click**. Fine-tune = hold **Shift** while dragging (Pro Tools uses its own fine-tune shortcut).
- **Smart Parameter Interpolation** smooths parameter changes (no zipper noise); standard FabFilter **Undo/Redo** and preset system included. No reported oversampling/latency in the manual; very low CPU ("Micro" by design).

## Deep spec (Programmer only)
Not reverse-engineered — capability only. (No matching file under `easby-programming/plugins/`. Related FabFilter deep specs that exist: `Volcano3.md` — the larger multi-filter sibling with full modulation matrix; `Saturn2.md` for saturation reference.)
