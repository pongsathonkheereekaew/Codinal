# Quick Decisions

> Fast lookup. Producer's intuition compressed into tables. When the question is "which one?", this is the first place I look. When the answer here is wrong for the context, I cross-reference the deeper files.

> Rule-of-thumb voice: rows below are imperative — what Easby reaches for. Hot-path lookup file: ALWAYS loaded.

---

## Sound → Waveform Start Point

| Target Sound | Start Waveform | Key Modification |
|---|---|---|
| Strings (bowed) | Sawtooth | Slow attack, filter EG |
| Brass | Sawtooth | Fast filter EG attack |
| Flute | Sine + noise | Blend 10–15% white noise |
| Clarinet | Square | Moderate LPF |
| Electric piano | Sawtooth → FM | Suppress odd harmonics |
| Organ | Additive sines | Drawbar levels |
| Kick drum | Sine + pitch EG | High → low pitch drop |
| Snare | Noise + sine | Fast decay |
| Hi-hat | White noise + HPF | Decay length = open/closed |
| Pad | Detuned saw + PWM | Slow attack, long release |
| Acid bass | Square + resonant LPF | High Q, accent, slide |
| Lead | Sawtooth or narrow pulse | Portamento, sync option |
| Bell / chime | FM C:M = 1:1.4 OR RM non-integer | Fast exponential decay |
| Sub bass | Sine | Tiny noise layer for definition |
| Choir | 3× detuned saw + formant filters | Slow attack, long reverb |

---

## Filter Slope Reference

| Slope | Poles | Character | Default for |
|---|---|---|---|
| 6 dB/oct | 1-pole | Gentle, shelving-like | Subtle correction |
| 12 dB/oct | 2-pole | Moderate | Strings, pads |
| 24 dB/oct | 4-pole (Moog) | Dramatic, musical | ⚡ default synthesis workhorse |

---

## ADSR Presets by Sound Type

| Type | Attack | Decay | Sustain | Release |
|---|---|---|---|---|
| Percussive (pluck) | Fast | Short | 0% | Short |
| Piano | Fast | Medium | 60–70% | Medium |
| Strings (bowed) | Slow | — | 100% | Long |
| Brass | Med-fast | Short | 80% | Medium |
| Pad | Slow | — | 80–100% | Long |
| Organ | Instant | — | 100% | Instant |
| Bell | Instant | Long exp | 0% | 0 |

---

## FM C:M Ratio — Quick Choice

| Need | C:M | Notes |
|---|---|---|
| Bright organ / rich | 1:1 | All harmonics |
| Clarinet-like | 1:2 | Odd partials |
| Hollow / flute | 2:1 | Alternating missing |
| Bell / metallic | 1:1.4 | Non-integer |
| Gong | 1:1.5 (2:3) | Compound |
| Brass | 1:1 + I-sweep | I 0→5 attack, decay to 0.5 |
| Electric piano | 1:1 or 2:1 | I ~2, decays slow to 0 |

⚡ Integer ratio = harmonic = pitched. Non-integer = inharmonic = bell/metallic.

---

## Stereo Mic Choice Matrix

| Priority | Technique |
|---|---|
| Mono compatibility (broadcast) | X-Y or M-S |
| Widest stereo image | A-B spaced pair |
| Natural, immersive | Blumlein |
| Orchestral / classical | Decca Tree |
| Surround film | OCT or INA-5 |
| Variable width in post | M-S |
| Live drum room | A-B or Blumlein |
| Acoustic guitar | X-Y at 12th fret |

---

## Mic-Per-Source Quick Picks

| Source | First pick | Distance |
|---|---|---|
| Loud lead vocal | SM7B | 3–4", 15° off-axis |
| Intimate vocal | LDC condenser | 6–8" |
| Snare top | SM57 | 1–2" above rim, 30° |
| Kick (inside) | D6 / β52 | Near beater |
| Hi-hat | SDC | 4–6" above edge |
| Drum overheads | SDC pair (X-Y or spaced) | 3–4 ft above |
| Guitar amp | SM57 + R-121 ribbon blend | On grille + 6" |
| Acoustic guitar | LDC or SDC pair | 8–12", at 12th fret |
| Brass | Ribbon | 12"+ off-axis |
| Room | LDC pair | 6–12 ft |

---

## "What chord trick should I use?" Decision Tree

```
Want surprise resolution?         → Deceptive cadence (I → vi)
Want forward momentum?            → Secondary dominant (V7 of next)
Want cinematic warmth?            → Borrowed bVII or bVI
Want smooth chromatic bass?       → Tritone substitution (bII7 for V7)
Want colour without changing fn?  → Add 7ths, 9ths, sus2/sus4
```

---

## "I need to develop this melody" Decision Tree

```
Repeat exactly?                   → Boring. Stop.
Same shape, different note?       → Sequence
Need a fresh angle?               → Inversion
Bridge/transition?                → Retrograde
Need epic?                        → Augmentation (stretch)
Need energy ramp?                 → Diminution (compress)
Need ambient section?             → Fragmentation (2–3 notes only)
```

---

## "Track sounds flat" Diagnostic

| Symptom | First check | Then |
|---|---|---|
| No groove | Quantize % too high? Swing? | Re-record with feel, or shift snare ±8 ms |
| No space | Too many mid-range elements | EQ HPF/LPF carve, or mute one element |
| No dynamics | Compression too heavy? | Reduce GR, re-record performance |
| No interest | All sections same density? | Subtract from verse, build into chorus |
| No bottom | Bass + kick fighting? | Sidechain kick into bass, or swap notes |
| No top | Hi-hat or vocal too closed? | Open filter, raise air EQ (10–15 kHz) |
| No story | Same texture throughout? | Automate filter/reverb across sections |

---

## "Should I use [X]?" Heuristics

| Question | Default answer |
|---|---|
| Should I add reverb to the kick? | No |
| Should I sidechain the bass to the kick? | Yes, lightly (2–3 dB GR) |
| Should I autotune the lead vocal? | Only if creative effect. Else: re-record. |
| Should I quantize the drums 100%? | No. 70–85% feel better. |
| Should I layer 3 kicks? | Try 2 first (sub + click). 3 if mix is dense. |
| Should I compress the master? | Light only (1 dB GR, 2:1, slow). Mastering glue, not master fader. |
| Should I open a new plugin? | Probably no — use what's already on the track. |
| Should I save and start over? | Almost never. Diagnose the one wrong thing. |

---

## "Granular — what setting for [X]?"

| Goal | Cloud duration | Grain duration | Density | Freq band |
|---|---|---|---|---|
| Time-stretch (no pitch) | Long | Medium (30–50 ms) | High | Fixed |
| Pitch-shift (no stretch) | Source length | Medium | High | Shifted |
| Freeze | Indefinite | 50–80 ms | High | Fixed position |
| Stutter / glitch | Short | Very short (<10 ms) | Very high | Narrow |
| Granular pad | Long | Long (80–100 ms) | High | Wide |
| Scatter blur | Source length | Medium | Medium | Wide scatter |

⚡ Default grain envelope = Gaussian. Reach for trapezoid if you need sustained body.

---

## "What's the right LFO target?"

| Want | LFO target | Rate |
|---|---|---|
| Vibrato | VCO pitch | 5 Hz, delay 300 ms |
| Tremolo | VCA level | 4–8 Hz |
| Filter sweep / autowah | VCF cutoff | 0.3–2 Hz |
| Animated pad | Pulse width (PWM) | 0.3 Hz |
| Random stepped | S&H to filter | 8 Hz, arp-feel |
| Slow evolution | LFO modulating LFO rate | 0.05–0.1 Hz |

---

## "What synth for what sound?"

| Need | Reach for |
|---|---|
| Fat analog bass | Minimoog or Minimoog emulation |
| Acid squelch | TB-303 emulation |
| Bright digital metallic | DX7 or FM8 |
| Warm poly pad | Prophet 5 emulation |
| Gritty filter distortion | Korg MS-20 |
| Aggressive lead | Access Virus |
| Anything goes / hybrid | Wavetable (Serum, Vital, Massive) |
| Organic evolving texture | Granular (Granulator, Padshop, Output Portal) |
| Bells, chimes, EP | FM with controlled C:M |
| Orchestral | Sampled libraries — don't fake this with synthesis |

---

## "Common mistakes — Easby refuses these by default"

- ✗ Starting with pads/atmosphere instead of groove
- ✗ Adding a new element when I should subtract an old one
- ✗ Compressing to make things louder (that's what faders are for)
- ✗ Opening a new plugin instead of solving with what's already there
- ✗ Referencing other tracks during composition (only during mix)
- ✗ Quantizing 100% (kills the groove)
- ✗ Mono-then-widen instead of capturing stereo at source
- ✗ EQ on the way in (bake-in bias is permanent)
- ✗ Tuning the 17th partial when the 2nd is wrong
- ✗ "Fixing it in the mix" — fix it at the source

> When in doubt, Easby defers: theory → `06`, recipes → `02`, math → `01`, arrangement → `03`, recording → `04`, taste → `00`.

---

## Cross-references

- For *why* any of these answers exist → `00-producer-mind.md`
- For the math behind synthesis answers → `01-synthesis-engine.md`
- For full instrument recipes → `02-sound-design-recipes.md`
- For composition development → `03-composition-methods.md`
- For recording details → `04-recording-production.md`
