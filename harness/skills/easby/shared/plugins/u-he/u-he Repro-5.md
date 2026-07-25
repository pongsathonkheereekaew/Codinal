# u-he Repro-5 — u-he (synth)

| | |
|---|---|
| Vendor / ver | u-he · Repro v1.1.3 (User Guide HA1000D, Aug 2025) |
| Type | Virtual analogue synth — component-level model of a 1978 5-voice polysynth (the polyphonic sibling of Repro-1) |
| Format | VST / VST3 / AU / AAX / CLAP (CLAP recommended where available) |
| Source | manual: `u-he Repro/u-he Repro-5.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Repro-5 is a circuit-level recreation of a legendary 1978 analogue polysynth (a Prophet-5-class instrument): up to 8 voices, two multi-wave oscillators per voice, a self-oscillating 24 dB/oct lowpass filter, dedicated filter + amp ADSRs, an LFO, two polyphonic modulation routings (Voice Mod + Wheel Mod) plus a 2-slot mod matrix, a per-voice polyphonic distortion unit, and five built-in stomp-box effects (saturation, delay, EQ/resonator, plate reverb, sonic conditioner). It nails the original's character — fat unison leads, lush detuned pads, gritty basses — and adds modern niceties: more voices, per-voice panning, audio-rate voice modulation, a deep mod matrix, "Tweaks" for swapping circuit personalities, microtuning (.tun + MTS-ESP), and full MPE. The distinct value vs generic VA synths is authenticity (all the hardware quirks are modelled) plus the swappable filter/oscillator/envelope "characters" on the Tweaks page.

## Controls (every param → musical effect)

### Control bar (global)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| SYNTH / TWEAKS / PRESETS | view toggles | Switch the three main GUI pages | navigation; right-click row → "set current as default" |
| VOICES | 1–8 | Max voices before note-stealing; also # of stacked voices when UNISON on | lower for mono/CPU, max for huge unison |
| Key Control | on/off | Experimental: type numeric values to controls via cursor keys/numpad | precise value entry (WIP) |
| Data Display | — | Shows preset name / last-edited param; click middle to pick preset | quick preset switching |
| UNDO / REDO | 30 steps | Undo edits incl. preset changes | fix mistakes |
| PRESET ◄ ► | — | Step through all presets | browse sounds |
| SAVE | — | Store preset (right-click → format: native / h2p / h2p extended / nksf) | save patches |
| MCORE | on/off | Multicore: spread voices across CPU cores | heavy polyphony on i5/i7 (may hurt on Apple Silicon — test) |
| HQ | on/off | High-Quality oversampling; only for extreme FM/extreme pitch | leave off normally (big CPU saver) |
| TUNE | ±12 semitones | Master tune (SHIFT = fine) | pitch the whole preset |
| OUTPUT | 0–200% (≈12 o'clock = 100%) | Final post-FX volume; can boost to 2× | level matching / makeup |

### Oscillator A
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| FREQUENCY | ±12 semitones | Coarse pitch within two octaves | detune/transpose OSC A |
| FINE TUNING (trimmer) | ±20 cents | Fine pitch; sets beating rate vs OSC B | thicken via subtle detune |
| OCTAVE | 4-octave switch (0–3) | Transpose oscillator by octaves | range placement |
| SAWTOOTH SHAPE | on/off | Brassy waveform, all harmonics (odd+even) | bright/rich tones |
| PULSE SHAPE | on/off | Pulse wave, hollower than saw; harmonic content set by PW | hollow/nasal tones (**note: if neither shape is on, OSC A is silent**) |
| PULSE WIDTH | 0–100% (dbl-click=50%) | Duty cycle of pulse → harmonic content (extremes → silent DC) | square at 50; PWM for movement (no effect on saw) |
| SYNC | on/off | Hard-sync OSC A reset to OSC B (set OSC A freq higher than B) | aggressive sync sweeps |

### Oscillator B (same as A minus SYNC, plus extras)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| FREQUENCY / FINE / OCTAVE | as OSC A | Coarse/fine pitch, octave | detune layer / modulation pitch |
| SAW / TRIANGLE / PULSE SHAPE | on/off each | Waveform selectors; **triangle is bipolar** (no DC) and weak as audio but boosts fundamental | triangle for sub/LFO use |
| PULSE WIDTH | 0–100% | Pulse duty cycle | as OSC A |
| LO FREQ | on/off | Drops OSC B into sub-audio range → usable as a 2nd LFO | extra modulation source |
| KYBD | on/off | Off = disables keyboard follow → constant pitch regardless of note | drones / fixed-pitch modulator |

### Mixer
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| OSC A | 0–100 | Level of oscillator A | balance osc blend |
| OSC B | 0–100 | Level of oscillator B | balance osc blend |
| NOISE / FEEDBACK | 0–100 | White noise level **(default)**; a Tweaks jumper turns it into FEEDBACK = signal fed from after the amp back into the mixer | noise for wind/percussion; FB to fatten bass |

### Unison / Glide / Voice Detune
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| UNISON | on/off | Stacks all VOICES onto single notes | massive mono leads |
| GLIDE | 0–100 (>50 = very slow) | Portamento between notes — **only active with UNISON on** | legato lead slurs |
| VOICE DETUNE | 0–100 | Per-voice detune/offsets (works regardless of UNISON) | width/thickness; set Reallocate OFF (Tweaks) for repeatable detune |
| MPE | on/off | Enables MPE mode (see notes) | per-note expression from MPE controllers |

### Filter (24 dB/oct lowpass, self-oscillating)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| CUTOFF | 0–100 | Lowpass cutoff (tone control) | brightness/darkness |
| RESONANCE | 0–100 (self-osc >60) | Feedback/emphasis at cutoff; >60 self-oscillates into a sine; tends to thin/lower level (like the hardware) | squelch, acid, sine source |
| ENVELOPE AMOUNT | 0–100 | Depth of filter-envelope → cutoff (Tweaks "FILTER −/+" jumper inverts) | classic filter sweeps |
| KEYBOARD AMOUNT | 0–100 (75 = 1:1 track) | Cutoff tracks note pitch; 75 = play self-osc "in tune" | keytrack; resonant melodies |
| ATTACK | ~2 ms – >15 s | Filter-env rise time | pluck vs slow swell |
| DECAY | ~2 ms – >15 s | Filter-env fall to sustain | shape sweep tail |
| SUSTAIN | 0–100 | Filter-env hold level (decays to new value while adjusted) | steady filter level |
| RELEASE | 2 ms – ~55 s | Filter-env fall after key release | tail length |
| VEL (trimmer) | 0–max | Velocity → filter-env depth (at max, min velocity = zero env) | dynamic brightness |

### Amplifier (VCA ADSR)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| ATTACK | ~2 ms – >15 s | Volume rise time | pads vs plucks |
| DECAY | ~2 ms – >15 s | Fall to sustain level | shape body |
| SUSTAIN | 0–100 | Held volume level | sustained vs percussive |
| RELEASE | 2 ms – ~55 s | Volume fade after release | tail length |
| VEL (trimmer) | 0–max | Velocity → amp-env depth (at max, min velocity = silence) | dynamic playing |

### Voice Mod (polyphonic — per-voice, subtle note-to-note variation)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| FILT ENV (source amount) | 0–100 | Amount of filter envelope sent to selected destinations | env→pitch/PW/cutoff |
| OSC B (source amount) | 0–100 | Amount of OSC B sent to selected destinations (audio-rate FM/PWM) | FM bite, vibrato, audio-rate filter mod |
| DESTINATION: FREQ A / PW A / FILTER | on/off each | Routes the FiltEnv+OscB mixture to OSC A frequency, OSC A pulse width, and/or filter cutoff | classic mono-mod routing, but polyphonic |

### LFO
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| HOST SYNC | on/off | On = rate snaps to tempo divisions 8/1…1/64 (incl. triplet & dotted); off = 0.03–27.5 Hz free | rhythmic vs free modulation |
| RATE | 0–100 (or sync division) | LFO speed | vibrato/tremolo speed |
| SHAPE: SAW / TRIANGLE / PULSE | on/off each | Waveforms (addable, e.g. SAW+SQUARE); LFO pulse width fixed at 50% | shape modulation contour |

### Wheel Mod (global — one signal modulates all voices equally)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| SOURCE MIX | 0–100 (LFO↔Noise) | Blends 100% LFO → 50/50 → 100% pink noise (Tweaks jumper swaps noise→S&H) | organic/chaotic mod blend |
| DESTINATION: FREQ A / FREQ B / PW A / PW B / FILTER | on/off each | Routes mix to each osc's frequency & pulse width and filter cutoff | mod-wheel vibrato / growl |
| (depth) | mod wheel + WHEEL MOD LIMITS triangles | Amount set by mod wheel; the two triangles by the wheel set min (red) and max (white) | permanent min vibrato, capped max |

> Wheel Mod responds only to mod-wheel data on **MIDI channel 1** (v1.1.3+).

### Modulation Matrix (2 slots per page; MM A / MM B = 4 total)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| DEPTH (×2) | −100 … +100 | Bipolar modulation amount per slot | any custom routing |
| SOURCE | selector | Mod source (full list below) | choose modulator |
| DESTINATION | selector / drag-crosshair | Mod target (drag the crosshair onto any control) | choose target (effect params only appear if FX active) |
| Slot modifiers: Curve | very compressed → linear → very expanded (S-curve) | Reshapes the source curve | tame/exaggerate response |
| Slot modifiers: Rectify | none / half-wave ± / full-wave ± / unipolarize | Rectifies the source | unipolar mod, doubling, folding |
| Slot modifiers: Quantize (Q) | integer / steps-of-12 / scales (overtone, minor/major scale, chord, series, fifths+octaves) | Steps the modulation (applied after depth) | stepped or scale-locked pitch mod |
| Slot modifiers: S&H | source-crossing trigger | Samples & holds the value on positive zero-cross of chosen signal | random/stepped mod |
| Slot modifiers: SL (Slew Limiter) | none / fast / smooth / slow | Softens transitions | glide/smooth a modulator |

**Matrix sources:** Mod Wheel (CC#01), Pitch Wheel, Control A (user CC, default Breath/CC#02), Control B (user CC, default Expression/CC#11), LFO, Trigger (gate impulse), Gate, Key Follow, Key Follow+PB, Velocity, Aftertouch (Pressure = chan+poly combined), Filter Envelope, Amp Envelope, Voice Index (per-voice quasi-random).
**Matrix destinations:** LFO freq, Global Mod (LFO/Noise mix, lower/upper limit), Glide, Pitch (master tune), Filter Env (A/D/S/R/vel depth), Amp Env (A/D/S/R/vel depth), Osc A & B (frequency*/fine/PW), Voice Mod (OscB amt, FiltEnv amt), Voice Detune, Mixer (A/B/Noise-FB), Filter (cutoff/res/keytrack/env amt), Distortion (Amount/Tone/Mix/Rate/Crush), Stereo Pan (per-voice 1–8), and each active FX (Velvet input gain; Lyrebird time/regen/mix; ResQ all bands; Drench predelay/decay/tone/mix/pan; Sonic Conditioner gain/width/transient). *osc freq mod restricted to FREQUENCY range.

### Tweaks page — Jumpers (circuit-behaviour swaps)
| jumper | options | effect |
|---|---|---|
| LFO DC \| NO DC | DC / no DC | DC = saw+square unipolar; no DC = bipolar (triangle always bipolar) |
| LFO INV \| N | normal / inverted | Inverts LFO sawtooth (rising ↔ falling) |
| OSC B INV \| N | normal / inverted | Inverts OSC B sawtooth |
| WHEEL MOD S&H \| Noise | noise / S&H | S&H replaces pink noise with random steps at LFO rate |
| UNISON / NOTE PRIO | low / high / last | Note-priority when playing >1 note in unison (low=USA, high=EMS/Japanese, last=modern) |
| POLY VOICE / REALLOCATE | on / off (round-robin) | On = same note → same voice; off = round-robin (affects repeatable detune) |
| MIXER FB \| NOISE | noise / feedback | Swaps NOISE knob for post-amp FEEDBACK (bass boost) |
| FILTER − \| + | + / − | "−" inverts filter env (ENV AMOUNT) |
| FILTER KEY \| KEY+PB | key / key+pb | Whether pitchbend affects cutoff |
| MICROTUNING ON \| OFF | on / off | Engage microtuning selection |

### Tweaks page — Selectors (circuit personalities)
| selector | options | effect |
|---|---|---|
| PITCH RANGE (×2) | 0–24 semitones, then 36 / 48 | Pitch-bender up/down range |
| Oscillator tweak (both) | P5 / P1 / ideal / P5 Old | P5=default; P1=Repro-1 char (quieter when saw+pulse, inverted pulse); ideal=crisp/precise; P5 Old=heavily detuned P5 |
| Oscillator tweak (OSC B only) | + Bottom | Emphasizes the triangle shape |
| Filter tweak | Crispy / Rounded / Driven / Poly | Filter character: Crispy & Rounded model two real units (Rounded cutoff a few semis lower); Driven = novel 3320 flavour; Poly = grandad's filter (much lower cutoff, won't reach max unless modulated up) |
| Envelope tweak | Ideal / Analog / High Sustain / One Shot / Piano 1 / Piano 2 | Ideal=clean ADSR; Analog=imperfections; High Sustain=jumps last 15% above ~85; One Shot=ignores gate (percussion); Piano 1/2=CEM3310-style with true release (Piano 1 longer) |
| Microtuning | .tun presets | Load microtuning table |

### Tweaks page — Voice Panning
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Voice pan 1–8 (trimmers) | hard L … centre (dbl-click) … hard R | Stereo position per individual voice | spread chords across the stereo field |

### Distortion (polyphonic — per voice, pre-FX-chain)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| I/O | on/off | Distortion in/out of signal path | engage drive |
| TYPE | Soft Clip / Hard Clip / Foldback / Corrode | Soft=smooth peak compression; Hard=chops top/bottom; Foldback=reflects peaks back; Corrode=samplerate reducer + bitcrusher | choose drive flavour |
| AMOUNT | 0–60 (dB input gain) | Perceived distortion amount (→ RATE in Corrode) | drive intensity |
| RATE | (Corrode only) | Sample-rate reduction — grit (mid) to loud metallic (high) | lo-fi on soft/low-cutoff sounds |
| TONE | 0–100 | Frequency tilt (more bass vs treble distortion) (→ CRUSH in Corrode) | tone-shape the drive |
| CRUSH | (Corrode only) | Bit-crush amount → steppy signal | digital crunch (try on triangle) |
| MIX | 0–100 | Dry/wet of distortion (preserves original character without changing the distortion sound) | parallel grit |

### FX Chain & built-in stomp-boxes
The block beside Distortion activates/reorders the 5 effects (click cells on/off, drag to reorder; signal flows top→bottom). A bypass LED at the lower-left of the EFFECTS view compares wet/dry (leave on, "Bypass Off").

**Velvet (tape saturation)**
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| HISS MUTE | on/off | Defeats tape hiss | clean up |
| PRESET | selector | Choose tape-character preset | quick tone |
| INPUT GAIN | cut/boost | Amount of tape saturation/distortion (notes interact like a guitar amp — unlike per-voice Distortion) | sheen at chain end, or grit before ResQ |

**Lyrebird (BBD-style delay)**
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Sync (selector) | Chorus/Short, Unsync/Long, Sync 1/16, Sync 1/4 | Delay time base (first two = absolute, last two = tempo-synced) | flanging/chorus vs echo |
| Flavour (selector) | Clean / Bright / Dark | Tonal character of the decaying repeats | match the mix |
| MODE | Echo / Pingpong / Swing / Groove | L/R channel ratio (Echo=mono unless modulated; Swing=triplets; Groove=dotted) | stereo/rhythmic feel |
| MODULATION | Max / Med / Min / Off | Time-modulation LFO depth (Off = no LFO) | chorus/tape wow |
| TIME | 1–8× (sync) / wide (unsync) | Scales the delay time (modulate it → smooth pitch glide) | dial in the echo time |
| MIX | 0–100 | Dry/wet | echo presence |
| REGEN | 0–100 | Feedback / regeneration (max = near-infinite) | repeats / self-osc |

**ResQ (semi-parametric EQ / triple resonator)**
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| MODE | EQ / RES | EQ = 2 shelves + mid bell; RES = 3 bandpass resonators | tone-shape vs resonate |
| LOW / MID / HIGH FREQUENCY | LOW 45 Hz–3 kHz · MID 55 Hz–9 kHz · HIGH 130 Hz–10 kHz | Per-band cutoff (bands overlap freely) | place the bands |
| GAIN (EQ mode) | ±18 dB, centre-zero | Cut/boost per band (LOW & HIGH are shelves) | corrective/creative EQ |
| VOLUME (RES mode) | 0–max (positive only) | Amplitude of each resonant bandpass | vowel/formant/ring tones |
| Q / RES | — | Bandwidth/resonance (EQ mode: Q applies to MID only) | sharpen bands |

**Drench (plate reverb w/ pre-delay)**
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| PRE DELAY | — | Delay before reverb onset (keeps dry presence; can support a Lyrebird delay) | depth/separation |
| DECAY | 0–100 (max ≈ minutes) | Reverb tail length | space size |
| TONE | −100 (dark) … +100 (bright) | Tilt filter on the tail (extremes nearly remove wet) | match the room to the sound |
| DRY / WET | 0–100% | Reverb amount | wet/dry balance |
| (Pan) | hidden | Reverb pan — matrix destination only | stereo placement via mod |

**Sonic Conditioner (saturator + transient designer + width)**
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| GAIN | bipolar (centre=0) | Output level; above zero saturates (compensate w/ main OUTPUT) | level + glue saturation |
| TRANSIENT | bipolar | − reduces clicks, + adds punch (negative may crackle on bass/pads — back off till it stops) | shape attack |
| WIDTH | stereo spread | Narrow/widen the stereo field | focus delay/wavefolder mids, or widen |

## Use by lens
- **Producer (create):** This is a sound-design and patch instrument, not a mix processor. Start from the 950+ factory presets (or `1978 Historic` for the authentic vintage bank). Build leads with UNISON + max VOICES + VOICE DETUNE + GLIDE; pads with two slightly-detuned oscillators, slow amp ADSR, and Drench. Use the per-voice Distortion + Velvet for grit, Lyrebird for analogue echo/chorus, the matrix for evolving movement (Voice Index, LFO, Aftertouch). Tweaks page swaps the entire filter/oscillator/envelope personality — audition all filter characters per patch.
- **Mixing (balance):** As a synth, fit it in the mix with the built-in chain rather than reaching for external plugins where possible: ResQ in EQ mode for fast tone carving, Sonic Conditioner WIDTH to control stereo (keep mono-compatible bass narrow), TRANSIENT to add punch or de-click. Per-voice Distortion stays clean across chords (no inter-note IMD) — better than a buss distortion for polyphonic parts. Set OUTPUT for level matching.
- **Mastering (finalize):** Not a mastering tool — it is an instrument. Skip on the master buss.

## Notes / gotchas
- **OSC A is silent if neither SAW nor PULSE shape is on.** Pulse at extreme PW (near 0 or 100) also goes silent (DC).
- **GLIDE only works when UNISON is on.** VOICE DETUNE works independently.
- **MPE:** activate via [MPE] switch (mirrors a cogwheel dialog). For full per-note expression set both pitch-bend ranges to 48 and set Control A = CC#74 (Timbre). MPE auto-disables Multichannel MIDI. CLAP exposes Note Expressions / param modulation and permanently maps "Brightness" → Control A.
- **Multichannel MIDI** (non-MPE per-channel expression) needs no activation but requires the host to route multiple MIDI channels to one instance.
- **HQ** oversampling is rarely needed (extreme FM/pitch only) — big CPU saver left off. **MCORE** helps on Intel i5/i7 but can *reduce* performance on Apple Silicon — test per machine; disable host multicore if both are on.
- **Block processing** in n×16-sample chunks; if the host buffer is a multiple of 16 (64/128/256/512), set Preferences → Base Latency = off for latency-free operation.
- Knobs: vertical click-drag or mouse wheel (no click zones); SHIFT = fine (0.01). Right-click any control → Lock to keep a value across preset changes; right-click → assign MIDI CC.
- Two distortion flavours coexist: per-voice **Distortion** (no note interaction) vs **Velvet** (notes interact like a guitar amp) — use both for layered grit.
- The bundle installer is named "Repro-1" and Repro-5 shares Repro-1 resource folders — by design, not an error.

## Deep spec (Programmer only)
Not reverse-engineered — capability only.
