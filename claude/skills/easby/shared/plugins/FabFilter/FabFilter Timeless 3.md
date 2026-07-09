# FabFilter Timeless 3 — FabFilter (tape/analog delay)

| | |
|---|---|
| Vendor / ver | FabFilter · Timeless 3 (v3.x) |
| Type | Delay — vintage tape/analog delay with in-loop filters, effects & deep modulation |
| Format | VST, VST3, CLAP, AU (macOS only), AAX Native, AudioSuite |
| Source | manual: `FabFilter Timeless 3/FabFilter Timeless 3.pdf` · deep spec: `easby-programming/plugins/Timeless3.md` (RE'd) |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
A versatile, vintage-sounding tape/stereo delay built on two independent, programmable delay lines whose feedback signal is routed through up to **six analog-style filters** and **five color effects** (Drive, Lo-Fi, Diffuse, Dynamics, Pitch Shift) — all *inside* the feedback loop, so successive echoes get progressively coloured (the defining tape topology). On top sits FabFilter's unlimited **drag-and-drop modulation** system (XLFOs, envelope generators, envelope followers, MIDI sources, XY/sliders) where almost any parameter is a target. Ranges from clean everyday slaps and dreamy echoes to ducking/wow-flutter/diffusion and full sound-mangling. Interactive delay display (with up to 16 taps) and filter display (with spectrum analyzer) make programming visual and fast.

## Controls (every param → musical effect)
### Delay (center)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Delay Time | ~5 ms … 5.0 s (or synced note) | main base delay time; tap the DELAY label to set by ear | the core echo spacing |
| Delay Time Pan (ring) | L/R up to 400% of base | per-channel delay-time multiplier → stereo spread | wide, drifting stereo echoes |
| Delay Sync | Free / synced note values | locks time to host tempo; when on, knob becomes Delay Offset | rhythmic, tempo-locked delays |
| Delay Offset | 50% … 200% (dotted/triplet marks) | time factor relative to synced grid | dotted/triplet feels |
| Delay Read Mode | Tape / Stretch | how the buffer reacts to *time changes*: Tape re-pitches (varispeed/Doppler), Stretch retimes without pitch change | tape warble vs clean retime |
| Freeze | Off / On (modulatable) | holds the buffer — ignores new input, repeats pattern forever | infinite sustain, glitch fx |
| Ping Pong | Off / start-L / start-R | feeds one channel only; cross-feedback bounces L↔R | classic bouncing delay |
| Feedback | 0 … 200% | amount of output fed back; >100% drives self-oscillation (bounded by in-loop saturation) | repeat length / runaway drones |
| Feedback Pan (ring) | L↔R | feedback amount per channel; can "cut off" repetitions on one side | asymmetric/stereo repeats |
| Cross Feedback Mix | 0 … 100% | blend of normal vs cross-feedback (one channel → the other) | widening, ping-pong-like spread |
| Feedback Invert L / R | Normal / Inverted (×2) | inverts polarity of L/R feedback → phase coloration | evolving, hollow feedback tones |
| Stereo Width | 0 … 100%+ | width of final wet output; low values collapse toward mono | mono-compat to ultra-wide |
| Wet Level (knob) | level, with L/R or M/S pan ring | final level of delayed signal; pan ring follows Channel Mode | balance wet in the mix; modulate w/ EF to duck |
| Mix | 0 … 100% | dry/wet blend (set 100% on a send/aux) | insert blend |
| Lock Mix | Unlocked / Locked | keeps Mix from changing when loading presets | send-effect workflows |

### Effects (left of delay — each has on/off + amount, all modulatable)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Drive | 0 … 100% | level the delay input is driven into internal saturation; warm vintage grit, keeps feedback in check | tape warmth, taming runaway fb |
| Lo-Fi | 0 … 100% | combined sample-rate + bit-depth reduction; subtle edge → total crush | degraded/vintage/destroyed echoes |
| Diffuse | 0 … 100% | allpass diffusion that smears/blurs the delayed & fed-back audio (affects transients first) | lush reverb-like tails (modulate w/ EG) |
| Dynamics | -1 … +1 (0 = off) | bipolar dynamics on incoming/wet audio: right = compression, left = gating/expansion | gate noisy echoes / pump for groove |
| Pitch Shift | -12 … +12 semitones | pitch-shifts the delay; raises min delay to 45 ms when on | octave/shimmer/detune echoes |
| ↳ Pitch Shift Routing | Inside / Outside Feedback | inside loop = pitch climbs each repeat (shimmer); outside = applied once to wet | shimmer reverb vs single detune |
| ↳ Pitch Shift Mirroring | Off / On | inverts pitch direction in the right channel (up/down) | chorus-like / dual-pitch effects |

### Filters (top-right display — up to 6, created/deleted in display like Pro-Q/Pro-R)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Filter Shape | LP / HP / BP / Bell / Low Shelf / High Shelf / Notch | LP/HP/BP = analog-like, self-oscillating, saturating; Bell/Shelf/Notch = clean EQ | tone-shape the feedback |
| Filter Freq | ~5 Hz … >20 kHz | cutoff / center frequency (drag dot horizontally) | darken/brighten repeats |
| Filter Gain | ±dB | gain for bell/shelf shapes | EQ the wet path |
| Filter Q / Peak | resonance | slope of LP/HP or Q/width of others (mouse-wheel on dot) | resonant sweeps, surgical cuts |
| Filter Slope | 6 / 12 / 24 / 48 dB/oct | rolloff steepness of LP/HP | gentle tilt vs brick |
| Filter Style | Classic / Gentle / Raw / Tube / Metal / Easy Going / Smooth / Hard / Hollow / Extreme / Clean | nonlinear analog character of LP/HP/BP (Clean = no saturation EQ) | flavour of the resonant filter |
| Filter Pan | -1 … +1 | filters L/R channels at different freqs (stereo balance of center freq) | stereo filtering effects |
| Filter Routing | Serial / Parallel / Per-Channel | serial = chained EQ; parallel = summed; per-channel = odd filters→L, even→R | creative multi-filter / wide fx |

### Delay display & taps (top-left)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Drag a bar | horiz = time, vert = feedback | edit delay time & feedback graphically | quick visual tweaks |
| TAPS / Tap Edit mode | up to 15 extra taps (+ main) | each tap: time factor (0–100% of delay), level, pan; double-click/+/right-click to add | rhythmic multi-tap patterns, reverb-ish clouds |
| Tap menu | load/save/randomize/ramp/space | bulk actions on taps (random pattern, even spacing, ramp up/down) | generate complex tap sets fast |

### Modulation system (bottom — drag source button onto any target)
| source | what it does |
|---|---|
| XLFO | LFO "on steroids": free 0.02–500 Hz or tempo-synced (16…1/64), with a 16-step sequencer (per-step value/glide/curve/random), Balance, Phase Offset, Glide, MIDI Sync (Retrigger/Legato), Snap (arpeggiator over 2 octaves) |
| Envelope Generator (EG) | ADSR (Delay/Attack/Hold/Decay/Sustain/Release) with per-segment slope (lin/log/exp); triggered by input, side-chain, or MIDI; Range = Normal (0..1) or Neutral (centered on 0) |
| Envelope Follower (EF) | tracks loudness of input or side-chain; Envelope vs Transient mode; attack/release |
| MIDI Source | turns velocity / pitch-bend / mod-wheel / any CC into modulation, with response curve (lin/exp/log/sqr/sqrt/sine) |
| XY Controller / Slider | macro control: XY (two dims) or Slider (one dim); range Bipolar (-1..1) or Unipolar (0..1); up to 6; MIDI-assignable |
| Mod slots | each connection = source→target with Level (depth), Invert, Bypass; slots can modulate other slots' levels (chaining) |

### Bottom bar / I/O
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Channel Mode | Left/Right · Mid/Side | process basis (M/S converts in & back out) | M/S widening / mono-center delays |
| Auto Mute Self-Osc | Off / On | auto-mutes filter self-oscillation when input goes silent | prevents endless ringing |
| Input level / pan | -36 … +36 dB | drive into filters/saturation harder (modulatable) | overdrive trick (boost in, cut out) |
| Output level / pan | -36 … +36 dB | final trim (modulatable) | gain-stage the wet |
| Global Bypass | — | soft-bypass whole plug-in (red line shown) | A/B against dry |
| MIDI Learn | — | map any CC to any parameter (Enable/Clear/Revert/Save) | hardware control |
| Resize / Full Screen / Scaling | Small/Med/Large/XL · 100–300% | UI size; Full Screen for precise filter/analyzer work | big-display editing |

## Use by lens
- **Producer (create):** the playground engine — synced echoes with Tape mode for warble, Pitch Shift *inside* the loop for shimmer-reverb risers, Freeze (modulated) for glitch holds, Diffuse modulated by an EG for lush ambient clouds, multi-tap patterns + XLFO step sequencers for rhythmic/arpeggiated mangling. Ping-Pong + Cross Feedback for instant width.
- **Mixing (balance):** put on a send at Mix 100% with Lock Mix on. Use an Envelope Follower → Wet Level to **duck** the delay under the dry vocal (or the Dynamics knob to gate noisy tails). In-loop LP filter + Drive keeps repeats dark and out of the way; Stereo Width / per-channel filters control how wide the echoes sit.
- **Mastering (finalize):** not a mastering tool — it's a creative/feedback delay. At most used very subtly on a parallel/aux for depth or stereo glue; Mid/Side mode + low Mix can add air to sides. Filters/Drive add gentle analog color if used as an insert effect.

## Notes / gotchas
- **Filters & saturation are inside the feedback loop** → each repeat is darker/more coloured (cumulative); this is the core tape character. Pitch Shift can be placed inside *or* outside the loop.
- **Feedback >100%** = sustained self-oscillation, kept bounded by in-loop saturation/limiting; enable **Auto Mute Self-Osc** to silence ringing when input stops.
- **Pitch Shift on** raises the minimum delay time from ~5 ms to 45 ms.
- **External side-chain** (for triggering EG/EF, or for the Dynamics keying / ducking) is easiest in the VST3/AU; per-host routing differs (Pro Tools key-input bus, Studio One/Ableton/Logic/Cubase side-chain menus). Use the EG/EF Audition button to confirm the SC signal.
- **Almost everything is a modulation target** — including Delay Time, Freeze, effect amounts, tap params, filter params, EG threshold, XLFO balance/frequency, and Input/Output gain. Modulation routing is drag-and-drop, no matrix grid.
- Presets from Timeless 1/2 load (via V1/V2 Preset Folders) but may sound slightly different; **old Timeless 1 automation cannot be read** by v3.
- VST2 = wider host compatibility; VST3 = easy side-chaining + sometimes lighter CPU. Both auto-adapt to mono/stereo track layout.

## Deep spec (Programmer only)
`/Users/pongsathonkheeereekaew/.claude/skills/easby/easby-programming/plugins/Timeless3.md` — black-box RE: measured delay-time taper, linear feedback gain, fully-mapped Dynamics law (threshold -6 dBFS, slope 1 dB/dB, clamp ±35.8 dB), in-loop filter/saturation confirmation, pitch-shift linear mapping, and full self-reported parameter surface (1012 params incl. mod banks). **REF — do not read from a CLEAN seat.**
