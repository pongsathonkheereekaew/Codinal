# u-he Diva — u-he (synth)

| | |
|---|---|
| Vendor / ver | u-he · v1.4.8 |
| Type | Virtual-analogue subtractive synth (mix-and-match modular, circuit-modelled) |
| Format | VST / VST3 / AU / AAX / CLAP (NKS-tagged presets; Linux too) |
| Source | manual: `u-he Diva/u-he Diva.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Diva ("Dinosaur Impersonating Virtual Analogue") models the oscillators, filters and envelopes of several classic mono- and poly-synths of the 1970s–80s and lets you mix-and-match them into one hybrid instrument. Its claim to fame is sound authenticity: it runs industrial-grade circuit-simulation plus **zero-delay-feedback (ZDF)** filters in realtime, so resonance and self-oscillation behave like real analogue hardware — at a notably high CPU cost. Signal path per voice: one of 5 oscillator modules → a central panel (filter-feedback or one of 3 high-pass models) → one of 5 main filters → amp, with two ADS(S)R-style envelopes (amp + mod), two host-syncable LFOs, an arpeggiator, and two series stereo FX slots. A global **Accuracy** switch (draft/fast/great/divine) trades CPU for fidelity. Distinct vs other VA synths: ZDF resonance realism, swappable hardware-flavoured modules on one panel, deep per-voice analogue "slop" (Trimmers), and modulation processors (Modifications) that go beyond the original hardware.

## Controls (every param → musical effect)

### Global / Control bar
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Accuracy | draft / fast / great / divine | Global DSP quality vs CPU; affects resonance/FM realism most. Fixed across all presets in an instance. | `great` for writing; `divine` only when you need top fidelity; `draft`/`fast` for many voices |
| OfflineAcc | same / best | Accuracy used for offline (bounce) render. | Set `best` to render highest quality regardless of live setting |
| Multicore | on / off | Spreads voices across CPU cores. Helps Intel i5/i7; can *hurt* on Apple Silicon / old CPUs. | Toggle per-machine; disable if host already does multicore |
| Output | gain | Final preset volume; does **not** affect tone. | Level-match presets here (not amp Volume) |
| Save format | h2p / h2p extended / native / nksf | Preset file format (right-click Save). h2p is cross-platform. | h2p for portability; nksf for Komplete Kontrol |
| GUI size | 70–200% | UI scale (temporary via right-click; permanent in Prefs Default Size). | — |
| Key Control | on/off | Type numeric values into clicked control (experimental). | Precise data entry via numpad |

### Oscillators (pick one module)
Shared idea: waveform/shape selection, octave switches, per-osc tune/detune, noise, and per-knob modulation (small grey-triangle labels reassign the mod source; default LFO2/ENV2). Osc output level strongly affects filter tone.

**TRIPLE VCO** (3 morphing oscillators; most CPU-hungry; includes its own Mixer)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| WAVEFORM 1/2/3 | continuous: ramp→tri→saw→square→narrow pulse | Per-osc shape, continuously variable (not stepped). | 8.00 = 25% pulse for max PWM (enable shape mod) |
| RANGE (octave) 1/2/3 | 32′ / 16′ / 8′ / 4′ / 2′ | Per-osc octave. | — |
| DETUNE 2/3 | 5-turn pot (±, can flip octave past ±5) | Fine detune osc 2 & 3 vs osc 1. | Thicken/beat oscillators; extreme = octave flip trick |
| TUNE MOD (knob + src + per-osc switches) | bipolar | Pitch-mod amount; upper switches arm each osc, label sets source. | Vibrato/PWM-siren per osc |
| SHAPE MOD (knob + src + switches) | bipolar | Waveform-mod amount; lower switches arm each osc. | Animate timbre; PWM (set 10.00 with 25% pulse) |
| FM 1→2/3 | 0–100 | Osc 1 frequency-modulates osc 2 & 3 equally. | Complex/dissonant/bell tones (modulatable in Modifications) |
| SYNC (2 / 3) | on/off | Hard-sync osc 2/3 to osc 1. | Classic sync sweeps (set osc1 32′, Transpose 24 for range) |
| VOLUME 1/2/3 (Mixer) | 0–100 | Per-osc level into filter. | Balance; low levels = more filter resonance character |
| FEEDBACK (Mixer) | 0–100 | Post-filter signal fed back to mixer. Low = bass boost; high = subharmonics/howl, lowers resonance. | Minimoog-style growl/bass |
| NOISE + PINK/WHITE (Mixer) | level + tone switch | Noise source; PINK = mostly lows, WHITE = full-range. | Breath, percussion, texture (level modulatable) |

**DUAL VCO** (2 multi-wave oscillators; independent/split pitch; PWM, sync, cross-mod)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| PW (fader) | ~50–100% nominal width | Pulse width for pulse waves. | Static pulse colour |
| PW-mod fader (LFO2 default) | bipolar (centre 0) | Depth of pulse-width modulation. | Classic PWM movement |
| PW target switch | 1 / 1+2 | Apply PW(M) to VCO1 only or both. | — |
| WAVEFORMS VCO1 | Triangle / Saw / Pulse(PWM) / Noise (multi-select) | VCO1 waves (stack multiple). | Rich single-osc tone |
| WAVEFORMS VCO2 | Triangle / Saw / Pulse / Sine (multi-select) | VCO2 waves. | — |
| OCTAVE 1/2 | 32′–2′ | Per-osc octave. | — |
| DETUNE (VCO2) | 5-turn pot | Detune VCO2 (can shift octave). | Beating/thickness |
| SYNC | on/off | Sync VCO2 to VCO1. | Sync leads (VCO2 pitch ≥ VCO1) |
| 1 / BOTH / 2 / SPLIT | 4-way | Pitch-mod target for the ENV2/LFO2 pair; SPLIT = modulate VCOs independently. | Independent osc pitch animation |
| CROSS MOD | 0–100 (+ src) | VCO1 FM's VCO2; amount directly modulatable here. | Metallic/FM textures |
| ENV2 / LFO2 pitch-mod knobs | bipolar | Pitch-mod amounts (sources reassignable). | — |
| MIX | VCO1↔VCO2 | Oscillator balance; modulatable (Noise & Dual VCO Mix). | Crossfade osc 1↔2 with env/LFO |
| SHAPE | ideal / analog1 / analog2 | Hardware-revision tone (most audible on triangles). | Vintage flavour select |

**DCO** (single multi-wave osc + sub + noise; brighter/crisper)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| PW + PW-mod fader | width + bipolar depth | Pulse width and its modulation. | PWM on pulse wave |
| TRANSPOSE | 32′–2′ | Octave. | — |
| PULSE selector | shapes (4th from top reacts to PW; top = off) | Pulse-family wave; summed into output. | — |
| SAWTOOTH selector | shapes (4th from top reacts to PW; top = off) | Saw-family wave; summed in. | — |
| SUBOSCILLATOR selector | 6 pulse-based shapes (top 4 = −1 oct, others −2 oct) | Sub waveform. | Add weight/bass |
| SUB level (fader) | 0–100 | Sub-osc volume. | — |
| NOISE level (fader) | 0–100 | Noise volume (modulatable). | — |
| ENV2 / LFO2 mod knobs | bipolar | Pitch/PW modulation (reassignable). | — |

**DUAL VCO ECO** (CPU-friendly, primitive; no PWM/FM; has ring mod)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| WAVE 1 | Tri / Saw / Pulse / Pulse+Pulse / Noise | VCO1 wave. | — |
| WAVE 2 | Pulse / (shapes) / RING | VCO2 wave; RING replaces output with ring-mod (VCO1 × VCO2 square). | Cheap clangorous tones |
| OCTAVE 1/2 | 32′–2′ | Per-osc octave. | — |
| PULSEWIDTH | 0–100 | Pulse width. | — |
| DETUNE | 5-turn pot | Detune VCO2. | — |
| VOLUME 1/2 | 0–100 | Per-osc level (VCO1 incl. noise; modulatable via Mix). | — |
| TUNE MOD (ENV2 / LFO2) | bipolar | Pitch mod of overall pitch (both oscs). | — |

**DIGITAL** (intentionally "digital"/aliased osc + extras)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| WAVE 1 & WAVE 2 | Multisaw / TriWrap / Noise / Feedback / Pulse / Sawtooth / Triangle | Wave per osc (selectors at far left/right). **Don't automate** — CPU spikes. | Multisaw=fat pads; Feedback=guitar-ish |
| OCTAVE (osc1) | octave steps | Osc1 pitch. | — |
| TUNE (osc2) | ±30 semitones (fine w/ SHIFT) | Precise osc2 pitch. | — |
| DETUNE | spread | Multisaw detune spread / general detune. | Fatter Multisaw |
| MULTI | balance | Multisaw: balance original vs detuned copies. (Per-wave: WRAP/BEND/Q/FEEDBACK/SPIKE UP/HARMONICS reuse these slots) | Pad richness; per-wave shaping |
| Central mod panel (PRESS / KYBD / LFO2 × 3 rows, ± switches) | bipolar | 3 shared mod slots (sources + L/R osc arm switches). Pitches can't be modulated fully independently. | Per-param modulation routing |
| SYNC | on/off | Hard-sync osc2→osc1 (turn up MIX + TUNE; none in Noise mode). | Digital sync |
| TUNE MOD | bipolar | Pitch-mod both oscs. | — |
| CROSS | 0–100 | Osc1 FM's osc2. | FM grit |
| RING | on/off | Replace osc2 with ring-mod of the two. | — |
| MIX | balance | Osc1↔osc2 level (modulatable). | — |
| HIGH QUALITY | on/off | Reduces aliasing (more CPU). | Cleaner highs when needed |

### Central panel — Feedback / High-pass (all models except Triple VCO mixer)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| NO HPF (Feedback) | 0–100 | Post-filter feedback into mixer (same as Triple's). | Bass boost → howl; alt to HPF (modulatable) |
| HPF \| POST | BOOST / 0 / 1 / 2 / 3 | HP actually *after* main filter; BOOST lifts bass, others cut lows. | Bass lift or thin the filtered tone |
| HPF \| PRE | continuous frequency | HP *before* main filter; sends fewer lows to it. | Tame DCO/noise; thin sound |
| HPF \| BITE | CUTOFF + PEAK(res) + mod (NO MOD/bipolar) + REV 1/2 | Full resonant HP before filter; most CPU-hungry; powerful shaping. | Aggressive HP sweeps/honk; "Big In The East" character |

### Main filters (pick one — "where the magic happens")
| filter | controls | what it does | when to reach for it |
|---|---|---|---|
| VCF \| LADDER | CUTOFF, EMPHASIS(res), 12dB/24dB switch, ENV2/LFO2/KYBD bipolar mod, FM[OSC1] | Classic 24dB (or 2-pole) ladder; bipolar filter-FM from osc1. | Moog-style bass/leads; FM grit (res & FM modulatable) |
| VCF \| CASCADE | CUTOFF, RES, 12dB switch, ROUGH/CLEAN, KYBD, ENV2/LFO2/FM[OSC1] | Cleaner ladder relative; Rough/Clean alters tone & top-end resonance. | Big smooth pads at high input levels |
| VCF \| MULTIMODE | CUTOFF, RES, mode (LP4/LP2/HP/BP), KYBD, ENV2/LFO2/FM[OSC1] | Multimode: 4-pole/2-pole LP, HP, BP. | When you need HP/BP, or brighter 2-pole LP |
| VCF \| BITE | CUTOFF, KYBD, PEAK(res), REV 1/2, ENV2/LFO2/FM[OSC1] | Sallen-Key character; very input-level dependent; 2-pole→screaming res. | Distinctive resonant character; low osc vol for max "Peak" |
| VCF \| UHBIE | CUTOFF (+2 mod), RES, KYBD, FM[VCO1], BR/BP switch, MIX (LP↔notch/BP↔HP), MIX mod src+amt | Silky 2-pole SVF morphing across LP–notch/BP–HP. | Sweepable filter-type morphs |

### Envelopes (two slots: amp + mod; pick a model each)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| ADS — ATTACK / DECAY / SUSTAIN | 0–100 each | Simplified ADSR; **decay & release share one time**. | Vintage mono-synth feel |
| ADS — RELEASE switch | on/off | Off = note stops on release even with long decay. | Set DECAY suitably *before* enabling Release |
| ADS — VEL (fader) | scaling | Velocity → envelope level. | Dynamics |
| ADS — KYBD (fader) | scaling | Note number scales A/D/R times (high notes shorter). | Natural key tracking |
| ANALOGUE — A D S R | full ADSR | Classic analogue ADSR shape. | General-purpose vintage env |
| ANALOGUE — VEL / KYBD | scaling | Velocity level scale / keyboard time scale. | — |
| DIGITAL — A D S R + VEL/KYBD | full ADSR | Cheaper-successor digital ADSR. | — |
| DIGITAL — Q (quantize) | on/off | Steppy envelope (Alpha Juno / Matrix-1000 flavour). | Lo-fi/stepped sweeps |
| DIGITAL — C (curve) | on/off | More "S"-shaped curvature. | Softer rounded contour |

### LFOs (two; LFO1 = vibrato, LFO2 = general "Mod")
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Waveform | sine / triangle / saw up / saw down / sqr hi-lo / sqr lo-hi / rand hold / rand glide | LFO shape. | rand glide = smooth random; saws = ramps |
| Restart | sync / gate / single / random | When LFO re-phases (sync=free; gate=per note; single=after all released; random=random phase). | Per-note vs free-running modulation |
| Phase | cycle position | Restart phase (ignored if Restart=random). | Align modulation start |
| Delay | immediate → ~20 s | Fade-in time (also usable as a ramp generator). | Delayed vibrato; ramp envelopes |
| Rate | bipolar offset | Speed offset from Sync value. | Fine speed tuning |
| Sync | 3 absolute times + 24 tempo-synced divisions | Rate / sync mode. | Tempo-locked movement |
| Rate Mod (+ src) | amount | Modulate LFO rate (e.g. ModWheel/KeyFollow). | Expressive speed control |
| Depth Mod (+ src) | amount | Modulate LFO level; set src=none to use knob as overall level trim. | Mod-wheel-controlled depth |
| Polarity | bipolar / unipolar | Unipolar shifts waveform up (positive-only). | Filter sweeps that don't go below |

### Effects (two series stereo slots, each on/off)
**Chorus** — Type: Classic/Dramatic/Ensemble · Rate · Depth (0 = static colour w/ Classic/Dramatic) · Wet. *Ensemble → string-machine.*
**Phaser** — Type: Stoned/Flanged · Rate/Beats (Sync = quarter-note divisions) · Depth · LFO Phase (0–360°) · Center (offsets delay times) · Feedback (≈resonance) · Wet · Stereo (bipolar width; Stoned max ±25). · Sync.
**Plate (reverb)** — PreDelay · Diffusion · Damp · Decay · Size (bathroom→cathedral) · Dry · Wet.
**Delay** — Left/Center/Right (tempo-relative; integer = semiquavers; Center = feedback tap) · Dry · Center Vol / Side Vol · Wow (tape wobble) · Feedback (100 = infinite if HP min/LP max) · HP / LP (in feedback path).
**Rotary** — Mix · Out · Stereo (mic separation) · Balance (horn vs bass) · Mode: Normal/SyncBass/NoBass · Controller (mod/CtrlA/CtrlB/Pressure) · RiseTime · Slow / Fast speeds (~10 s–0.2 s) · Drive (tube distortion, input-level dependent).

### MAIN — Tuning
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Vibrato | amount | Oscillator pitch-mod from LFO1 (also depends on LFO1 Depth Mod). | Global vibrato |
| Glide | rate | Portamento. | — |
| Glide2 | bipolar offset | Extra glide on VCO2 (Dual/Triple) / VCO3 (Triple). | Detuned/lagging slur on one osc |
| Range | strength | Portamento "strength"; low = slur begins nearer target (sloppy intonation). | Expressive imperfect glides |
| GlideMode | time / rate | Constant glide time vs constant rate (wide intervals = longer glide). | — |
| Fine | ±1 semitone | Fine tune. | — |
| Transpose | ±24 semitones | Coarse transpose. | — |
| Up / Down | 0 / 24 / 36 / 48 semitones | Independent pitch-bend ranges. | — |
| Microtuning (+ on/off) | .tun file | Load/enable microtuning table (also Oddsound MTS-ESP supported; .tun overrides MTS). | Alternate temperaments |

### MAIN — Amplifier & Pan
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| VCA | Env1 / gate | Amp driven by Env1 or a simple gate (frees Env1). | Organ-style gate; reuse Env1 elsewhere |
| Volume | gain | Amp gain; positive can subtly overdrive. | Tone-affecting drive (use Output for level-match) |
| Vol Mod (+ src) | amount | Modulate filter output level (can affect Feedback). | Tremolo/dynamics |
| Pan | L↔R | Voice pan position. | — |
| Pan Mod (+ src) | amount | Pan modulation (use StackIndex to spread stacked voices). | Auto-pan / stereo spread |

### MAIN — Voice
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Mode | poly / mono / legato / duo / poly2 | Voice mode (mono retriggers; legato doesn't; duo=split oscs; poly2 steals releasing voices first). | Mono leads, legato glides, CPU relief (poly2) |
| Note Priority | last / lowest / highest | Mono/legato priority. | Emulate USA(lowest)/Japanese(highest)/digital(last) behaviour |
| Voices | 2–16 | Max voices before stealing. | Guard against glitches on heavy patches |
| Stack | unison count | Unison voices per note (use Stack Tune / StackIndex to offset). | Supersaw/unison (heavy CPU) |
| MPE Support (+ Config) | on/off | Enable MPE; Config window mirrors MPE params. | Per-note expression |

### MAIN — Clock & Arpeggiator
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Clock | division | Arp clock interval (always host-synced; no absolute times). | — |
| Multiply | 0.50–2.00 | Scale clock interval. | — |
| Swing | 50% (2:1) → 100% (3:1) | Shuffle amount. | Groove |
| Arp | on/off | Arpeggiator on. | — |
| Sync | on/off | Strict host sync (align to beats vs restart on new note). | Locked vs responsive arps |
| Mode | played / up / down / up+dn 1 / up+dn 2 / random | Note order. | — |
| Progression | serial / round / leap / repeat | How it climbs octaves. | Octave-spanning patterns |
| Octaves | 1–4 | Octave range (with Progression). | — |
| Restart | none / 4–10,12,14,16,24,32 | Notes played before pattern restarts (keeps it in meter). | Try 8 for 4/4 |

### MODIFICATIONS (extra mod routings + processors)
Upper half — modulate params not on the main panels: **FM & Cross Mod Depth** (src), **Noise & Dual VCO Mix** (src; modulates noise level or osc-mix crossfade), **Resonance Mod** (Emphasis/Peak — no panel equivalent), **Filter FM Mod** (FM[OSC1] amount), **Feedback Mod** (Triple VCO / Feedback module only). The red **(M)** badge appears next to any main-panel control that's being modulated here.
Lower half — modulation processors (each with input selector): **Rectify** (negatives → positive), **Invert** (flip), **Quantize** (steps; value = division factor), **Lag** (smooth/round changes), **Multiply** (src × src), **Add** (src + src). Chain these to build complex/impossible modulation.

### TRIMMERS (per-voice analogue "slop" + stacking)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Oscillator Voice Detune | 3 rows (per osc) × 8 knobs (16 voices, reused) | Per-voice, per-osc detune. | Hand-crafted analogue drift |
| Voice Map Modulator | 8 knobs | Values for the **VoiceMap** mod source (use for any per-voice offset: pan, cutoff, res…). | Targeted per-voice modulation |
| Detune Amt | scaling | Master scaler for Oscillator Voice Detune. | Keep low for "good tuning" |
| Voice Drift | amount | Slow overall pitch wavering. | Subtle life (keep low) |
| Voices / Stack | mirror of Voice panel | Convenience copies. | Adjust Stack Tune without switching panels |
| Variance (Cutoff/Env/PW/Glide + buttons) | random offsets | Random "slop" to cutoff, env times, pulse width, glide; button randomizes the 8 values. | Organic per-voice variation |
| LED Colour | colour | All indicator-LED colour (automatable). | Cosmetic |
| Reset Phase Osc1/2/3 | phase | Osc reset phases (only if Transient Mode = osc reset). | Consistent percussive attacks |
| Transient Mode | analog / dc reset / vcf reset / osc reset | How first ms of new voices behave (punchy vs clicky); analog = nothing reset; vcf reset clears filter; osc reset uses Reset Phase. | Tune attack character (most audible at min attack) |
| Bipolar Noise | on/off | Leave on (compat for early presets). | — |
| Stack Tune 1–6 | ±2 octaves | Pitch of each stacked voice. | Megasaws (all near 0), one-finger chords |

### SCOPE
Oscilloscope of the output **before effects**. **Frequency** = horizontal resolution, **Scale** = vertical. Right-click for draw style: glow/fire/wind (prettier, more CPU) vs eco/fast (cheaper).

### Preferences (selected)
Default Size · Default Skin · Gamma (brightness) · Oscilloscope style · **Base Latency** (leave 16 samples unless host uses non-multiple-of-16 buffers; "off" can distort) · Control A/B Default (default MIDI CCs; A=CC2, B=CC11) · MIDI Control Slew (slow/fast smoothing of pitchbend/modwheel/CtrlA-B/Pressure) · Save Presets To · Auto Versioning · Scan On Startup · Auto-Tag Features.

### Modulation sources (assignable via grey-triangle labels)
MIDI/env/LFO: **default, Control A, Control B, Env1, Env2, Gate, KeyFollow, KeyFollow2, LFO1, LFO2, ModWheel, PitchWheel, Pressure, Velocity**. Esoteric: **Add, Alternate** (flip-flop per voice), **Invert, Lag, Multiply, Quantise, Random** (per-note), **Rectify, StackIndex** (spreads a value across stacked voices, −1…+1), **VoiceMap**.

## Use by lens
- **Producer (create):** Diva is a sound-design playground. Start from `8 TEMPLATES` / `INIT June-60` etc. Swap modules by clicking the module label to recreate or hybridise classic synths (Triple VCO + Ladder = Moog flavour; Dual VCO + Cascade = poly pads; DCO for crisp brass; Digital/Multisaw for fat supersaws). Use Stack + Stack Tune for unison leads/pads, the two LFOs + Modifications processors for evolving motion, and the arpeggiator for patterns. Trimmers add analogue life. Run `great`/`divine` for the final sound.
- **Mixing (balance):** As an instrument it sits on a track — shape it in context rather than insert it as FX. Use KYBD on filter/envelopes for even response across the keyboard, the built-in HPF \| PRE/POST to clean lows before bus EQ, and the series FX slots (Plate, Delay, Chorus) for in-patch space so the part glues. Level-match patches with **Output** (tone-neutral), not amp Volume. Drop **Accuracy** while mixing many tracks to save CPU; re-render with OfflineAcc = best.
- **Mastering (finalize):** Not a mastering tool — Diva is a sound source. The only finalize-stage relevance is rendering: set **OfflineAcc = best** so bounces use full ZDF quality, and freeze/print tracks (it's CPU-heavy) before the mastering chain.

## Notes / gotchas
- **CPU is the headline:** ZDF + circuit sim is expensive, especially `divine`, high resonance, complex/noise input, Stack/unison, and `wind`/`glow` scope modes. Mitigate with lower Accuracy, Poly2 mode, fewer Voices, Multicore (Intel only — can *hurt* Apple Silicon / old CPUs), `legato`/mono, and by freezing tracks.
- **Switch parameters are NOT host-automatable** (waveform/module switches) — automating them caused CPU spikes/crashes, so u-he omitted them; you *can* MIDI-learn them. The **Digital oscillator's WAVE switches in particular cause massive CPU spikes** — never automate.
- **Block processing:** audio is processed in chunks of n×16 samples; Base Latency 16 samples is the safe default.
- **Osc output level affects filter tone** — low oscillator volumes bring out more resonance ("Peak") on Bite/Ladder.
- **Decay/Release shared** on the ADS envelope; set Decay before enabling Release.
- **Mod routing reassignment:** small grey-triangle labels on knobs reassign the modulation source; non-default sources show as a "Dymo-tape" sticky label.
- MPE supported (defaults to ±48 st bend — consider ±2; Control A must be CC#74); also Multichannel MIDI, poly aftertouch (combined into `Pressure`), CLAP (Brightness→Control A), NKS, microtuning (.tun + Oddsound MTS-ESP). Over 1200 factory presets; demo = intermittent crackle.

## Deep spec (Programmer only)
Not reverse-engineered — capability only.
