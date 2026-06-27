# McDSP FilterBank — McDSP (EQ / filter)

| | |
|---|---|
| Vendor / ver | McDSP · v7 (manual © 2022) |
| Type | Equalizer — shelving + parametric EQ, high/low-pass filters (3 configs: E606, F202, P606) |
| Format | AAX Native/DSP, AU, VST3 (Mac Intel + Apple Silicon, Win). VST discontinued as of v7. Mono & stereo. |
| Source | manual: `McDSP FilterBank/McDSP FilterBank.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
McDSP's first product (debut 1998) — a flexible analog-modeled EQ that "rivals any analog EQ." Three plug-ins ship under one name: **E606** (the full one: HPF + LPF + low shelf + high shelf + 2 parametrics), **F202** (HPF + LPF only, with resonance), and **P606** (six parametric bands). Its signature feature is the **Peak-Slope-Dip (P-S-D)** shelving control set — beyond gain/freq, the shelf shape is sculpted with extra punch (Peak), transition gradient (Slope), and adjacent-band warmth/scoop (Dip), letting one shelf emulate a wide range of vintage and modern EQ curves. Constant-Q proprietary parametrics, double-precision processing, zero latency (Native/AU/VST3; 16-sample delay on AAX DSP).

## Controls (every param → musical effect)

### Global (all configs)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Input (Gain) | -24 to +24 dB | Gain into the EQ, before processing | drive/trim signal before EQ; gain-stage |
| Output (Gain) | -24 to +24 dB | Make-up gain after the EQ | compensate level after boosts/cuts (E606, P606; F202 has no output) |
| Ø Phase | On/Off | Polarity invert of final output (180°); yellow LED = engaged | phase-align multi-mic sources |
| Input/Output meters | -60 to 0 dB | Show in/out level; red LED = clip (click LED to clear) | watch headroom; clear clip indicators |

### High & Low Pass Filters (E606 = bands 1 & 6; F202 = bands 1 & 2)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| HPF Freq | 20 Hz – 20 kHz | Cutoff where low-frequency attenuation begins (−3 dB at corner) | clean up rumble/plosives, band-limit |
| LPF Freq | 20 Hz – 20/21 kHz | Cutoff where high-frequency attenuation begins | tame fizz/hiss, band-limit tops |
| Slope | E606: −6 / −12 dB/oct · F202: −6 / −12 / −18 / −24 dB/oct | Steepness of the filter roll-off | gentle (musical) vs steep (surgical) cut |
| Peak (resonance) | F202 only, up to +24 dB | Resonant emphasis at the cutoff frequency | synth-style filter sweeps; accentuate corner. Note: no resonance at −6 dB/oct slope |

### Low & High Shelf EQ (E606 = bands 2 & 5)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Gain | -12 to +12 dB (effective up to ±17 dB at full peaking) | Boost/cut of the shelved band | broad tonal lift/cut (air, warmth) |
| Freq | LS 40–160 Hz · HS 4k–16 kHz | Corner frequency where shelf gain applies | place the shelf |
| Peak | 0–100% (up to +5 dB) | Adds punch/brightness near the shelf corner; interacts with Dip | emphasize the shelf edge; vintage "lift" |
| Slope | 0–100% (6 → 12 dB/oct) | Transition gradient of the shelf; steeper = more defined. At min, Peak & Dip have no effect | smooth/gentle vs defined/aggressive shelf |
| Dip | 0–100% (up to −5 dB) | Adds warmth — undershoot just outside the shelf band; interacts with Peak | scoop adjacent freqs; classic Pultec-style boost+dip |

### Parametric EQ (E606 = bands 3 & 4; P606 = bands 1–6)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Gain | -12 to +12 dB | Boost/cut at the band's center frequency | corrective or tonal peak/notch |
| Freq | E606: P1 40 Hz–4 kHz, P2 80 Hz–8 kHz · P606: 20 Hz–20 kHz (all 6) | Center frequency of the band | target a resonance/tone |
| Q | 0.2 to 4.0 (1 = one octave; 0.2 ≈ 5-octave bandwidth) | Bandwidth (constant-Q). High Q = narrow/surgical, low Q = wide/broad | wide tonal shaping vs narrow notch. Low Q (0.2–0.3) mimics broad shelving-like analog curves |

## Use by lens
- **Producer (create):** F202's resonant HPF/LPF (raise Peak, steep slope, sweep Freq) makes synth-style filter sweeps — automate Freq for movement. Use the E606 shelf P-S-D to print character on tracks while recording: low-shelf with Dip for warmth, high-shelf with Peak for sheen.
- **Mixing (balance):** E606 is the workhorse — HPF plosives/rumble off vocals (12 dB/oct, ~80–120 Hz; nudge Dip for warmth), parametrics to carve resonances, shelves for broad tone. Kick/snare separation: big low-shelf boost on kick, max the Peak/Slope/Dip and tune Freq to the fundamental; steeper Slope (≈10) isolates kick from snare. Bass: low-shelf for weight, parametric scoop 800 Hz–8 kHz to fit the mix, touch of high-shelf for fret/pick detail.
- **Mastering (finalize):** P606 (six wide-Q parametrics, Q 0.2–0.4) for gentle broadband tonal balance and analog-style curves; low-Q parametrics emulate shelving without phase artifacts. Use small ±dB moves with Output make-up; Ø for polarity checks. Constant-Q + double precision keeps curves clean across the spectrum.

## Notes / gotchas
- **Three separate plug-ins**, one product: E606 (full), F202 (filters + resonance only), P606 (6 parametrics). Pick by task.
- **Peak/Dip are interactive** on shelves: increasing Peak reduces Dip and vice-versa. **At minimum Slope, Peak & Dip do nothing.**
- **F202 resonance** (Peak, up to +24 dB) requires slope ≥ −12 dB/oct; none at −6 dB/oct.
- **Presets interchangeable** across E606/P606/F202 — but copying only transfers controls the target config has (e.g., F202→P606 copies just in/out gain). Preset library models Neve 1084 (E-classic1), Avalon 2055 (P-classic2), GML 8200 (P-classic3), Manley, Pultec — McDSP makes no claim of identity.
- **Latency:** zero on AAX Native/AU/VST3; **16 samples** on AAX DSP (HDX). DSP usage doubles at 88.2/96 kHz.
- **Editing controls:** Cmd-drag = fine; click text box to type exact value (out-of-range clamps to nearest); Option-click = default. No control-linking. Fully automatable.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
