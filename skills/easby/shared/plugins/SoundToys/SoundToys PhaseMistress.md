# SoundToys PhaseMistress — SoundToys (analog phase shifter)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 (manual "Version 5", © 2015) |
| Type | Modulation — analog-modeled phaser / phase shifter (all-pass notch network) |
| Format | VST3/AU/AAX (Mac & Windows; iLok authorized) |
| Source | manual: `SoundToys PhaseMistress/SoundToys PhaseMistress.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
PhaseMistress is a deep, fully-modeled analog phaser that recreates the silky, swirling sound of classic hardware (Uni-Vibe, MXR Phase 90, EH Small Stone, Mutron Bi-Phase, Maestro PS-1A, Moogerfooger 12-stage, Boss Super Phaser, Trine, and more) and then extends them far past hardware. It builds notches by cascading all-pass "stages" and mixing the phase-shifted signal back with the dry; sweeping the notches up/down the spectrum gives the classic whoosh. Distinct from typical phasers: the "circuit" is fully editable (2–24 stages incl. odd counts, independent resonant-peak count, color, intensity, phase polarity) via 69 built-in Styles, and the sweep is driven by SIX selectable modulation engines (LFO, Rhythm, Envelope, Random, Step, ADSR) including draw-your-own LFO shapes and programmable rhythmic step patterns. Input/Output stages add analog saturation (pre- or post-phasing) for grit.

## Controls (every param → musical effect)

### Common front-panel controls (all modes)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Mix | Dry…Wet (0–100%) | Balance of phased+saturated signal vs. dry. Input/Output sat only affect the wet path; dry stays clean. | 50% or less for insert use; 100% on aux send/return |
| Frequency | 5 Hz – 20 kHz | Sets the center ("initial") frequency of the notches — where the sweep is biased. | Tune the effect to the source; 12 o'clock as a neutral start |
| Resonance | Min…Max | Adds resonant peaks at each notch, exaggerating harmonics — sharper, "churning" phasing. Cranked → self-oscillation (can obscure source). | More bite/throatiness; ⚠ extreme = very high level, watch speakers |
| Mod | Min…Max | Scales how much the active modulation sweeps Frequency. Directly linked to/scaled by Freq Mod (Tweak); direction set there. | Sweep depth; lower it at fast rates to avoid out-of-tune vibrato |
| Style | menu (69 presets + Custom) | Picks the virtual phasing "circuit" (stages/res/color/etc.) without changing Mix/Freq/Res/Mod. Each = a different piece of gear. | Fast tonal recharacterization; audition by stepping through |
| Style Edit | button | Opens slide-out Style Edit menu to build/modify the circuit (see below). | Designing your own phaser |
| Modulation indicator | blue LED row (display) | Visual of the phase sweep position L→R and back; moves to the rate. | Visual feedback only |
| Input | −24…+24 dB | Boosts/attenuates the wet input stage; drives Analog-Style saturation **pre-phasing** (distortion then gets phased). LED: yellow = −6 dB to clip, red = clipping. | Add harmonics so phasing is more pronounced |
| Output | −24…+24 dB | Wet output level; drives saturation **post-phasing** (signal phased first, then dirtied). | Color the result differently; tame level when Resonance is high |
| Tweak | button | Opens the slide-out Tweak Menu (mode-dependent deep params). | Access all advanced phasing controls |

### Tweak Menu — first row (shared by LFO, Rhythm, Envelope, Random, Step, ADSR)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Freq Mod | −10.00…+10.00 Oct (+ REV switch) | Sets direction AND max depth of Frequency modulation when Mod knob is full up. 12 o'clock/0 = no mod. +/− = sweep above/below center. REV flips polarity. | Define modulation range; presets often use ~8 Oct default |
| Res Mod | Min…Max (dB) (+ REV switch) | Modulates the **number of resonant peaks** independently of Stages — big changes to resonance character when Resonance is up. REV flips. | Animate/morph the resonance tone |
| Res Ofs Mod | center ± (dB) (+ REV switch) | Modulates the Resonance **Offset** (peak-vs-notch tuning) with the active mod source. 12 o'clock = none. REV flips. | Sweep the peak/notch detune; invert vs. Freq/Res mod |
| L/R Offset | center ± (oct) | Static frequency offset between L and R channels. 12 o'clock = identical. CW = right higher than left → wide stereo. | Big/wide stereo phasing; extreme = "sucked out of your head" |
| L/R Mode | Normal / Reverse | Affects only the modulation: Normal = L/R sweep together; Reverse = L/R inverse → swirling stereo pan. | Stereo movement / auto-pan feel |
| Analog Style | 7 choices (radio) | Saturation algorithm driven by Input/Output. Clean = max undistorted then hard clip · Fat = smooth LF distortion · Squash = like Fat but more compressed · Dirt = smooth broadband sat · Crunch = exaggerated high-end clip · Shred = lots of asymmetric clip · Pump = extreme pumping compression. | Choose the flavor of grit/saturation |

### Shape editor section (LFO & Rhythm Tweak Menu)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Shape Editor | drawable curve | Draw custom LFO waveshape. Click = add point, Option-click = remove, drag = move. Default sine has 3 points. | Bespoke sweep curves |
| Smoothing | None…Max | Rounds the transitions between points. 0 = stair-step jumps; Max = fully smooth. | Soften/harden the waveform |
| Smoothing Mode | Lin / Sin / Exp / Sym / Rev | Curve type connecting points: Linear (straight), Sine (very smooth), Exp (scooped, rises quickly), Sym (even symmetrical curve), Rev (rises slow, falls fast). | Shape the contour between nodes |
| Shape Preset | menu + Save (floppy) | Load/save custom shapes; edits switch readout to "Custom". Save As stores in the Shape pop-up. | Recall your own LFO shapes |

### LFO Mode (front panel adds)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Rate | 1 Hz – 100 Hz | Speed of the repeating LFO sweep (wider than hardware; 100 Hz = audio-rate territory). | Classic free-running phaser sweep |
| Shape | menu (Sine, Triangle, … + custom) | Selects the LFO waveshape; custom shapes edited in Tweak. | Pick/define sweep waveform |

### Rhythm Mode (tempo-synced LFO; front panel adds)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Tap Tempo | BPM readout + tap button + MIDI sync toggle | Sets BPM by tapping; toggle syncs to host/MIDI tempo. | Lock sweep to song tempo/feel |
| Rhythm | menu (1/2, 1/4, 1/8… + Custom) | Rhythmic transition rate — how often phase steps to a new position. Custom = pattern from Rhythm Editor (overrides Rhythm controls). | Musical, beat-locked phasing |
| Shape | menu (sine, triangle, square… + custom) | Built-in/custom LFO shape used per step. | Waveform of each rhythmic move |
| Groove | Shuffle ↔ 0 ↔ Swing | 12 o'clock = none; CCW adds shuffle, CW adds swing — relative to set Rhythm; applies regardless of mod type/rate. | Humanize/groove the pattern |

### Rhythm Editor (Rhythm Tweak Menu, below shared row)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Rhythm Editor | drum-machine-style grid | Program unique rhythmic patterns; each event triggers one full cycle of the LFO Shape. Click sections to add/remove dividers (need blank space to add). | Custom rhythmic phase patterns |
| Num Bars | count | Number of bars the pattern spans. | Match pattern length to song |
| Beats/Bar | count | Beats per bar. | Set meter |
| Bar | selector | Pick one bar at a time to edit (multi-bar patterns). | Edit long patterns |
| Grid | 1/4, 1/8, 1/16… | Spacing/length of LFO shapes added when clicking empty space (length = grid value, not the gap). | Resolution of placed events |
| Rhythm Preset | menu + Save | Load/save factory & user rhythm patterns. | Recall pattern presets |

### Envelope Mode (envelope follower; front panel adds)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Threshold | knob | Level at which the follower starts tracking input. Higher = only loud peaks modulate; too low = overmodulated. | Dial in dynamic tracking sweet spot |
| Gain | knob | Follower sensitivity / "ratio" — boosts signal exceeding threshold. High = gate-like on/off; low = responsive/dynamic. | Adjust how hard the envelope reacts |
| Attack | 0.1 ms – 1 sec | How fast phase reacts to rising level. Fast = staccato/dynamic; slow = hazy/lazy. | Transient response of the sweep |
| Release | 0.1 ms – 1 sec | How fast phase reacts as level falls. Fast = dynamic; slow = smooth decay. | Tail behavior |

### Random Mode (sample & hold; front panel adds)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Tap Tempo | BPM + tap + MIDI sync | Sets/sync tempo for the S&H steps. | Tempo-locked random jumps |
| Smoothing | Min…Max | Rounds transitions between random values. 0 = hard jumps; Max = smooth "drunken walk". | Glide vs. step the randomness |
| Rhythm | menu (1/4 note…, + Custom) | Rhythmic rate at which a new random value is chosen. Custom overrides. | Rate of S&H changes |

### Step Mode (triggered sample & hold; front panel adds)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Trigger | manual button + Trigger knob | New random value fires on: manual press, MIDI note, OR input exceeding the Trigger threshold (knob; live level shown in red around it). | Event/transient-driven phase jumps (drums, percussion) |
| Smoothing | Min…Max | Rounds transitions between stepped values (0 = jump; Max = smooth). | Glide vs. hard step |

### ADSR Mode (synth-style envelope generator; front panel adds)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Trigger | manual button + Trigger knob | Fires the ADSR on manual press, MIDI note, or input over threshold (knob; live level in red). | Triggered, repeatable envelope shape |
| A — Attack | 0.1 ms – ~5 s | Time for envelope to rise 0→100% after trigger. | Fast = snappy, slow = swell |
| D — Decay | 0.1 ms – ~5 s | Time to fall from peak to Sustain level. Full up = no decay. | Shape post-attack contour |
| S — Sustain | 0–100% | Hold level while trigger held / input above threshold. | Steady-state sweep position |
| R — Release | 0.1 ms – ~5 s | Time to fall from Sustain to 0 after trigger released / input below threshold. | Decay tail of the sweep |

### Style Edit Menu (defines the phasing "circuit"; modifying any → Style = "Custom", saved with preset)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Style Presets | 69 entries (Super 12, Rezo 6 Low, Classic 4, Phase 90, BiPhase, Uni-Vibe-ish "Vacuum", DOD 201, The Trine, Scoopy, etc.) | Base circuit recipes from classic gear + originals. | Starting point for circuit design |
| Stages | 2 – 24 (incl. odd) | Number of all-pass stages = number of notches. More stages = more pronounced/intense (even = classic; odd = stuttered, inherent lowpass, effect-heavy). | Core character: 2-stage washy → 12+ thick |
| Res Mode | Norm – 24 | Number of resonant peaks independent of Stages. Norm = matches stages. Decoupling = brand-new circuits. | Unusual resonance behavior |
| Res Offset | −10 … +10 | Tunes resonant-peak frequency vs. the notches. Lower = peaks toward bass. Audible only with some Resonance dialed in. | Detune peaks vs. notches |
| Color | Classic / Modern | How resonance interacts with notches: Classic = notches weaken as resonance rises; Modern = preserves deep notches. A/B against source. | Notch depth behavior under resonance |
| Intensity | Normal / High | High = steeper peaks/valleys → more intense, pronounced effect. | Make any circuit stronger |
| Phase | Positive / Negative | Polarity of the phasing circuit. Positive (common) = more bass/fuller; Negative = thinner, less low end. | Tonal weight of the effect |
| Res Phase | Positive / Negative | Polarity of the notches. Positive = stronger low end/fuller. | Fine tonal weight of resonance |

## Use by lens
- **Producer (create):** The creative powerhouse. Use Envelope/Step mode for funky auto-wah-style triggered phasing on drums, slap bass, rhythm guitar; Random for sci-fi bleeps/ELP-style S&H; ADSR for note-triggered swells; Rhythm + Rhythm Editor for tempo-locked rhythmic phase patterns that move with the track. Drive Input + pick Crunch/Shred/Dirt for gritty "radio guitar." Draw custom LFO shapes for sweeps hardware can't do. Start from gear-style presets (Phase 90, Uni-Vibe-ish, Bi-Phase) then tweak Stages/Color/Phase.
- **Mixing (balance):** Use as an insert at Mix 50% or less for tasteful movement on guitars, keys, vocals (think Queen/ELO/Pink Floyd), pads, and synths. LFO mode at a slow Rate with modest Mod and Resonance ~9 o'clock for classic gentle whoosh. L/R Offset / L/R Mode Reverse to widen and add stereo motion. Keep Resonance moderate to avoid harshness; lower stages (2–4) for subtle, higher for obvious.
- **Mastering (finalize):** Not a mastering tool — it's a creative effect that alters phase/tone heavily and can self-oscillate. Avoid on the 2-bus except deliberate sound-design/transition moves; if ever used, very low Mix, low Stages, Resonance off, mono-safe settings (avoid extreme L/R Offset), and watch level (high Resonance can spike output dangerously).

## Notes / gotchas
- **6 modulation engines**, each reshapes the center section AND its Tweak Menu, but all share the same first Tweak row (Freq/Res/Res-Ofs Mod, L/R Offset, L/R Mode, Analog Style).
- **Resonance can self-oscillate and produce very high levels** — turn Output down when cranking it; it can damage speakers at high monitor volume.
- **Mod knob is a scaler** of the Freq Mod depth set in Tweak (Mod full up = full Freq Mod range); direction lives in Freq Mod (+ REV).
- **Input vs. Output saturation** color the sound differently (pre- vs. post-phasing) and only touch the wet path; the dry signal stays clean.
- **Odd stage counts** (rare in hardware) add inherent lowpass + a stuttered, effect-heavy character — a key "PhaseMistress can do what hardware can't" feature.
- **69 Styles** are circuit recipes (named after gear or sonic traits); editing any Style param → "Custom", saved inside the preset (not as separate shape/rhythm files). Custom **shapes** and custom **rhythms** save separately via their own floppy-disk Save menus.
- **Tap Tempo** (Rhythm/Random) syncs to host/MIDI tempo via the toggle; Groove (Shuffle/Swing) applies regardless of mod type or rate.
- No oversampling/latency or sidechain-input controls documented; "trigger" sources are the plugin's own audio level or MIDI notes.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
