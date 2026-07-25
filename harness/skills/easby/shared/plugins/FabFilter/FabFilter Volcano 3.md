# FabFilter Volcano 3 — FabFilter (modulating multimode filter)

| | |
|---|---|
| Vendor / ver | FabFilter · Volcano 3 |
| Type | Creative multimode filter bank + deep modulation (vintage / non-linear filtering) |
| Format | VST, VST3, CLAP, AU (macOS), AAX Native, AudioSuite (also iOS) |
| Source | manual: `FabFilter Volcano 3/FabFilter Volcano 3.pdf` · deep spec: `easby-programming/plugins/Volcano3.md` (RE'd) |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Up to four analog-sounding, self-oscillating filters with internal drive/saturation, freely routed in series/parallel and modulated by an enormous drag-and-drop matrix (XLFOs, envelope generators, envelope followers, MIDI sources, XY controllers/sliders). Each filter offers eight shapes (LP/HP/BP, plus the new non-linear Bell/Low-shelf/High-shelf/Notch/All-pass EQ-type shapes), four slopes, eleven character "styles", and per-filter drive/peak/delay/level/pan. The distinct thing vs a normal EQ: the filters are deliberately non-linear (drive + style add saturation, grit and self-oscillation), so they color and move the sound rather than surgically EQ it. Built for filter sweeps, rhythmic gating, auto-wah, dubstep wobbles, comb/Haas/chorus/flanger textures and creamy vintage cutoff tones.

## Controls (every param → musical effect)

### Filter (per filter, up to 4; set in display + filter-controls strip)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Frequency | ~5 Hz – 75 kHz (exp) | center/cutoff of the filter band | the main sweep/tuning control; #1 modulation target |
| Pan (freq panning) | L↔R ring around Frequency | filters L and R at different cutoffs (stereo balance of center freq) | stereo-widening filter moves; Ctrl-drag horizontally. Stereo routing only |
| Peak | LP/HP: resonance (0→self-osc) · Bell/Shelf: gain ± (also sets Q) | resonance / EQ gain at the band | add bite/whistle/self-oscillation; for bell/shelf it's the dB boost-cut |
| Slope | 6 / 12 / 24 / 48 dB/oct | roll-off steepness (band width for bell/shelf) | gentle tone-shaping (6/12) vs surgical/aggressive cut (24/48). 6 dB n/a for BP & Notch |
| Shape | Low Pass, High Pass, Band Pass, Bell, Low Shelf, High Shelf, Notch, All Pass | filter response type — note Bell/Shelf here are non-linear, character-rich (not clean EQ) | pick the filtering job; double-click in display areas to auto-create the right shape |
| Style | Classic, Smooth, Raw, Hard, Hollow, Extreme, Gentle, Tube, Metal, Easy Going, **Clean** | the saturation/character flavor of the filter (see Notes) | Clean = transparent EQ; others add color/drive/self-osc personality |
| Drive | internal saturation amount | how clean vs gritty the filter sounds (level into the non-linearity) | dial in analog grit / harmonics; pairs with Style |
| Delay | 0 – 50 ms | small delay on that filter's output | comb-filtering, Haas, chorus, flanging (best with parallel routing + Mix + modulation) |
| Level | per-filter output level | level of each filter independently | balance parallel/per-channel filter branches |
| Output Pan | L↔R per filter | pan each filter's output | spread parallel filters across the stereo field. Stereo routing only |
| Enabled (bypass) | on / off | enable/bypass the selected filter(s) | A/B a band; Alt-click its dot in the display |

### Routing & global filter options
| control | options | what it does | when to reach for it |
|---|---|---|---|
| Routing | 8 graphs (series ↔ parallel mixes; layout depends on # of filters) | how the 1–4 filters are interconnected | series = stacked cuts/bandpass; parallel = multi-band, comb, Haas effects |
| Routing mode | Stereo · L/R (per-channel) · Mid/Side | whether one graph processes the stereo pair, or separate graphs per L/R or M/S | independent L/R or M/S filtering; note: filter panning disabled in L/R & M/S |
| High Quality | on / off | oversamples the non-linear filter stage (less aliasing, more CPU) | enable on driven/self-oscillating filters or when rendering |
| Auto Mute Self-Osc | on / off | mutes self-oscillation automatically when input goes silent | keep self-oscillating filters from ringing on forever |
| Global Bypass | on / off | soft-bypasses the whole plug-in (click-free); analyzer stops | clean true-feel bypass from the bottom bar |

### Modulation sources (add via **+** in mod section; drag the top "source drag button" onto any target)
| source | key params | what it does |
|---|---|---|
| **XLFO** (×many) | Frequency (0.02–500 Hz free, or synced 1/64–16 bars), Offset (×0.5–×2 sync multiplier), Balance (skews 1st/2nd half of cycle), Glide (global + per-step), Phase offset, Snap (arpeggiator, snaps to 2-oct keyboard), MIDI sync (Retrigger/Legato); per step: Value, Curve (Linear/Sqr/Sqrt/Sine), Glide, Random; add/remove steps (up to 16-step sequencer) | LFO on steroids — anything from a smooth sine to a 16-step rhythmic/random/arpeggiated sequence; tempo-syncable |
| **Envelope Generator (EG)** | Trigger input (main / ext side-chain / MIDI), Threshold, Range (0..1 or "neutral" ±around sustain), DAHDSR: Delay, Attack, Decay, Sustain (level), Hold, Release, + per-curve slope dots (lin/log/exp) | classic ADSR triggered by audio level or MIDI; shapes one-shot/keyed movement |
| **Envelope Follower (EF)** | Trigger input (main / ext side-chain), Mode (Envelope / Transient), attack & release dots, Audition | tracks loudness or transients of a signal → auto-wah, ducking-style filter moves, transient-triggered effects |
| **MIDI source** (×up to many) | Input (Mod Wheel / Pitch Bend / Velocity / Aftertouch / KB Track / Controller), Controller number (0–127 CC), Response curve (Linear/Exp/Log/Sqr/Sqrt/Sine) | turns MIDI (incl. key-tracking for cutoff, mod wheel, velocity, sustain pedal) into modulation. VST3 has no per-note aftertouch |
| **XY Controller / Slider** | Mode (XY 2-D / Slider 1-D), Range (bipolar −1..1 / unipolar 0..1), X & Y source drag buttons | hands-on macro control — manually morph one or two targets, MIDI-Learnable to a hardware XY pad |

### Modulation slots & matrix
| element | what it does |
|---|---|
| Drag-and-drop slot | drag a source's drag-button onto any target knob/display dot → creates a connection; almost every param is a target (filter freq/peak/drive/pan/delay/level, input/output/mix, even XLFO freq, offset, balance, EG threshold, other slot levels) |
| Slot Level slider | amount/depth of that modulation (Shift = fine, Ctrl/Cmd-click = reset) |
| Invert (+/−) | flips the modulation polarity |
| On/off | temporarily disable a slot |
| Modulation indicator | colored dot near a modulated control; click to open the slot panel for that target/source |
| Show/Hide sources, Auto-Collapse, Show Source Flow | declutter the mod section (hide sources except XY/sliders; collapse expanded sources; toggle the diffuse flow visualization) |

### Input / output (bottom bar, output button popup)
| control | range | what it does |
|---|---|---|
| Input level / pan | −36…+36 dB | (wet) input gain into filters; modulation target — overdrive filters by raising input, lower output |
| Output level / pan | −36…+36 dB | output gain; modulation target |
| Mix | 0–100% | dry/wet blend; modulation target (note phase cancellation possible with delays/filtering) |
| MIDI Learn | mode + menu (Enable, Clear, Revert, Save) | map any hardware controller to any parameter |
| Undo / Redo / A·B / Copy | — | edit history; A/B compare two states; Copy A→B |
| Resize / Scaling / Full Screen | Small/Medium/Large/XL · scaling % · full screen | UI size for precise display work |

## Use by lens
- **Producer (create):** the headline tool — assign an XLFO (tempo-synced, 16-step) to Filter Frequency for dubstep wobbles, rhythmic gates and arpeggiated sequences; sweep cutoff with an XY slider for risers/drops; crank Drive + a gritty Style (Raw/Hard/Extreme) for distorted guitar/synth filter tones; use Snap to turn an XLFO into an arpeggiator. Self-oscillating peaks (high Peak on LP/HP) give pitched "laser" tones.
- **Mixing (balance):** tame or excite with the non-linear Bell/Shelf shapes for character EQ a clean EQ can't do; envelope-follower → cutoff for auto-wah on guitars/keys or movement on pads; ext side-chain EF/EG for rhythmic, source-triggered filtering; parallel routing + per-filter Delay + Mix for comb/Haas widening; Mid/Side mode to filter sides vs center independently.
- **Mastering (finalize):** niche/creative only — Volcano is a colored, modulated filter, not a transparent mastering EQ (use Pro-Q). If used on a bus, prefer Clean style, gentle slopes, low Drive, High Quality on, and subtle Mix; M/S routing for broad stereo tone-shaping. Watch self-oscillation and dry/wet phase.

## Notes / gotchas
- **Styles** (character): Classic (default, FabFilter One flavor); Smooth (creamy); Raw (heavy overdrive, guitar-distortion); Hard (moderate, clean whistle); Hollow (juicy mod distortion + low-end self-osc); Extreme (wild); Gentle (smooth general-purpose); Tube (warm, good for synths); Metal (rough/sharp); Easy Going (softer Tube); **Clean** = the only linear, non-saturating style — use it as a transparent EQ/filter base.
- **Per-channel routing creates/deletes filters in pairs** (L/R and M/S). Filter panning is disabled in L/R and M/S modes (stereo only).
- **Self-oscillation**: high Peak settings on LP/HP push to self-oscillation; enable Auto Mute Self-Osc so it stops when input is silent.
- **Latency / CPU**: High Quality adds internal oversampling latency (small) and CPU; off = lowest latency. Turn it on for driven/self-osc filters and renders.
- **MIDI routing** requires the host to feed MIDI to the effect (per-host setup: Pro Tools/Logic AU MIDI-controlled Effects/Ableton/Cubase MIDI track). MIDI sources enable key-tracking the cutoff, mod-wheel macros, velocity dynamics, sustain-pedal hold.
- **Presets**: factory bank is "smartly organized"; section presets (Save As Default) let you set defaults per source type / filter. Can load Volcano 1/2 presets (may sound slightly different).

## Deep spec (Programmer only)
`/Users/pongsathonkheeereekaew/.claude/skills/easby/easby-programming/plugins/Volcano3.md` — TPT/ZDF state-variable filter core, measured shape/slope/peak/freq tables, 11-style harmonic fingerprints + generating-function fits, 8-graph routing topology, XLFO/EG/EF/MIDI/mod-matrix depth measurements. (CLEAN measured layer; REF/disasm quarantined within that file — do not cite REF in product specs.)
