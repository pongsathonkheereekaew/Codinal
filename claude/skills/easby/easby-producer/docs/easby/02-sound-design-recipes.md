# Sound Design Recipes

> Every instrument is a harmonic fingerprint plus an envelope. Match the fingerprint, get the envelope right, the rest is finish. I work from the spectrum, not from a preset list.

> Rule-of-thumb voice: recipe rows are imperative for Easby, not first-person narration.

---

## The Reverse-Engineering Process (Welsh)

When Easby is asked to rebuild a target sound:

1. **FFT/spectrum analyze the target.**
2. **Read the harmonic diagram:** X = frequency, Y = amplitude (dB).
3. **Match waveform to harmonic content** — sawtooth (all), square (odd), sine (fundamental).
4. **Find dominant harmonics → set filter cutoff there.**
5. **Watch how high-freq harmonics change over time → that's the filter EG decay.**
6. **Map the attack shape → VCA attack time.**
7. **Map amplitude decay → VCA decay + sustain.**

⚡ **Welsh's principle:** Low harmonics (1st, 2nd, 3rd) = character. High harmonics = brightness. Get the low ones exactly right; treat the high ones collectively.

⚡ **Missing harmonics matter as much as present ones.** That's how Rhodes (odd suppressed) and alto flute (weak fundamental) get their identity.

---

## Tonal Palettes by Colour (Swedien)

Bruce Swedien hears frequency bands as colours. The mapping is synesthetic, but the EQ rules behind it are concrete and useful for Easby when an operator's brief is purely descriptive ("make it darker" / "I want this to feel warm").

| Colour brief | EQ / synth move | Result |
|---|---|---|
| **Dark / black** | Roll off > 4 kHz; boost 60–120 Hz +2 dB; LPF 24 dB/oct half-closed | Sub-heavy, no top-end sparkle. Dub, slow R&B. |
| **Warm / amber** | +1.5 dB shelf 200–400 Hz; gentle dip 2 kHz; HPF below 50 Hz | Vintage console feel, rounded mids. Soul, classic rock. |
| **Bright / yellow** | +2 dB shelf 8 kHz; gentle bump 2 kHz; HPF 80 Hz | Air, presence, cuts through mix. Modern pop lead. |
| **Cold / blue** | Dip 200–400 Hz; +3 dB shelf 10 kHz; HPF 100 Hz | Clinical, glassy. Synthwave, ambient. |
| **Sharp / red** | +4 dB narrow Q at 3 kHz; HPF 100 Hz; transient enhancement | Aggressive, forward. Punk, hip-hop snare, lead vox. |
| **Round / green** | +1 dB 250 Hz; +1 dB 1 kHz; LPF 24 dB/oct open | Friendly, smooth. Singer-songwriter, jazz. |
| **Hollow / purple** | Notch 500–800 Hz; +2 dB 100 Hz + 5 kHz | Resonant, mid-scooped. Stadium-rock guitar, metal. |

⚡ Use this when the brief is descriptive but vague. Match colour to genre context first (rock = warm/sharp; ambient = cold/dark) before EQing.

---

## Moving Timbre (Russ / Roads — avoid static-tone fatigue)

Static tone (same oscillator, same filter, no modulation) tires the ear within 8–16 bars. Build in *imperceptible* timbre drift so the listener hears "alive," not "processed."

| Movement technique | Mechanism | Speed |
|---|---|---|
| **Slow LFO on wavetable position** | LFO 0.05–0.2 Hz on `wavetable_pos` → spectrum evolves over multiple bars | 4–16 bars per cycle |
| **Per-partial decay variance** | Additive: high partials decay faster than low (10 ms vs 200 ms) | Per-note |
| **Grain density drift** | AGS cloud: density slowly ramps 50 → 100 grains/sec across section | 8–32 bars |
| **Filter cutoff slow swing** | LFO 0.1 Hz on VCF cutoff, small depth (±5%) | 8–16 bars |
| **Multi-pass stacking with slight EQ shift** | Each layered take: progressively wider stereo + warmer EQ + longer tail (Swedien's multi-pass technique) | Per stack |

⚡ Reach for a movement technique whenever a `SoundDesignTarget` is intended to play for ≥ 8 bars without re-trigger. Without movement, the patch will sound "loop-locked."

---

## Strings (sawtooth family)

| Instrument | Approach |
|---|---|
| Violin / viola / cello / DB | Sawtooth, slow VCA attack, filter EG tracks bow pressure |
| Pizzicato | Fast attack, fast decay, near-zero sustain |
| Electric guitar | Sawtooth or PWM, moderate attack, long sustain, very fast filter EG |
| Acoustic guitar | "Dynamic" harmonics — use PWM or osc sync with EG-modulated slave pitch. Add noise burst for pluck transient. |

### Recipe — Bowed Violin
- Osc: 2× sawtooth, detuned ±7 cents
- VCA: A 80 ms / D — / S 100% / R 600 ms
- VCF: 24 dB LPF, cutoff at ~3 kHz, key tracking 75%
- VCF EG: A 60 ms / D 200 ms / S 60% / R 500 ms (filter opens with bow pressure)
- LFO: sine on pitch, 5 Hz, delay 400 ms (vibrato kicks in after sustain)

### Recipe — Pizzicato
- Same osc as bowed, but VCA: A 1 ms / D 200 ms / S 0% / R 100 ms
- Filter EG closes fast — pluck has bright instant then darkens

---

## Woodwinds (hollow, odd-harmonic-leaning)

| Instrument | Approach |
|---|---|
| Flute (concert) | Near-sine at low harmonics, 10–15% white noise for breath |
| Flute (alto) | Fundamental ~40 dB below 2nd harmonic — synthesize at 2nd harmonic pitch |
| Clarinet | Square (odd harmonics), fairly flat spectrum |
| Oboe / Sax | Sawtooth with resonant filter peak around 1–3 kHz, content above 4 kHz |
| Recorder | Strong fundamental, few high harmonics — LPF nearly closed |
| Shakuhachi | Breathy — fundamental + strong noise component |

### Recipe — Flute
- Osc: sine + white noise (mix noise at 12%)
- VCA: A 30 ms / D — / S 100% / R 200 ms
- VCF: gentle 12 dB LPF at 4 kHz, key tracking 100%
- LFO: vibrato 5 Hz, delay 300 ms

---

## Brass (sawtooth + hard filter attack)

| Instrument | Approach |
|---|---|
| Trumpet / trombone / horn | Sawtooth, filter opens sharply on attack, decays slightly |
| Muted brass | BPF with high Q at 1–3 kHz |
| French horn | Rounder, filter more closed, more 2nd harmonic body |

### Recipe — Brass (Chowning FM method)
- C:M = 1:1
- I sweeps 0 → 5 on attack (fast — adds brightness on hit)
- I decays from 5 → 0.5 on sustain (harmonic falloff)
- VCA: A 8 ms / D 80 ms / S 80% / R 200 ms
- Result: bright attack with spectral decay — real brass behaviour.

### Recipe — Brass (subtractive)
- Osc: 2× sawtooth
- VCF: 24 dB LPF, resonance ~30% (the "blat")
- VCF EG: A 5 ms / D 150 ms / S 40% / R 100 ms — opens fast, decays to mid
- VCA: A 8 ms / D 80 ms / S 80% / R 200 ms

---

## Keyboards

### Rhodes Electric Piano
- ⚡ **Odd harmonics suppressed ~30 dB below even harmonics.** This is the entire Rhodes identity.
- Method A (subtractive): sawtooth → notch-filter the odd harmonics.
- Method B (FM, the DX7 way): C:M = 1:1 or 2:1, I starts ~2, decays slowly to 0.
- Velocity → I depth (soft = bell-like, hard = bright).

### Hammond Organ
- Pure additive — drawbars = partial levels.
- Footages: 16', 8', 5⅓', 4', 2⅔', 2', 1⅗', 1⅓', 1' → sine partials at those harmonics.
- Sine waves only. No filter. Vibrato/chorus optional.

### Harpsichord
- Fast attack, near-zero sustain, strong upper harmonics.
- LPF bright; VCA A 1 ms / D 400 ms / S 0% / R 200 ms.

### Grand Piano
- "Dynamic" harmonics across register. High notes = brighter. Low notes = more fundamental weight.
- Better captured by sampling than synthesis. If synthesizing: FM with C:M = 1:1, I modulated by velocity AND key position.

---

## Voice

- Vowels = resonant peaks (formants). 2–3 formant frequencies per vowel.

| Vowel | F1 | F2 |
|---|---|---|
| Ah | 800 Hz | 1200 Hz |
| Ee | 270 Hz | 2300 Hz |
| Oo | 300 Hz | 870 Hz |

### Recipe — Choir Pad
- 3× sawtooth, detuned ±10 cents each
- 2× BPF in parallel at F1 and F2 of target vowel
- LFO: independent slow vibrato per voice (4–6 Hz, randomized phase)
- Long reverb (3 s+)
- VCA: A 600 ms / D — / S 100% / R 1.5 s

---

## Percussion — Tuned

| Instrument | Approach |
|---|---|
| Bell / chime | RM or FM with non-integer ratio (1:1.4), fast exponential decay, zero sustain |
| Marimba | Sine + FM mod, short decay |
| Vibraphone | Same as marimba but longer decay + tremolo LFO on VCA |
| Steel drum | FM with specific C:M ratios (try 1:1.7) |

### Recipe — Tubular Bell (Chowning)
- FM: C:M = 1:1.4
- I = 1.5–3.0 (rich inharmonic sidebands)
- VCA: A 1 ms / D exponential 4 s / S 0% / R 0
- No filter movement — let the inharmonic spectrum decay naturally.

---

## Percussion — Untuned

### Kick (acoustic-style)
- Osc: sine + small noise burst
- Pitch EG: high → low (e.g., 100 Hz → 50 Hz over 80 ms)
- VCA: A 1 ms / D 200 ms / S 0% / R 50 ms

### Snare
- Layer: noise (top) + short sine (bottom, ~200 Hz)
- VCA: A 1 ms / D 180 ms / S 0% / R 100 ms

### Hi-hat
- White noise → HPF at 6–8 kHz
- Closed: VCA D 50 ms
- Open: VCA D 400 ms

### Cymbal
- FM with multiple complex non-integer ratios
- Long decay (2–4 s)
- HPF to remove low-end mud

---

## 808 / 909 — drum machine reference

| Machine | Character | Key sounds |
|---|---|---|
| 808 | Smooth analog, sub-heavy | Sine bass kick, noise+sine snare, deep claps |
| 909 | Snappier, more digital click | Punchier kick (shorter, more transient), tighter snare |

### 808 Bass Kick
- Pure sine, pitch EG (100 Hz → 40 Hz over 80 ms)
- VCA: A 0 / D long (400–800 ms) / S 0 / R 0
- ⚡ The long decay is the 808 signature. Don't choke it.

### 808 Snare
- Noise + 180 Hz sine
- Medium decay (~250 ms)

### 909 Kick
- Shorter than 808, more click transient on top (~1 ms transient layer above the body)

---

## Bass

### General rules
- Sawtooth = full, growling bass
- Triangle = round, sub-leaning bass
- Square = TB-303 acid territory

### Recipe — Sub Bass
- Sine + slight noise (5%) for definition
- VCA: A 5 ms / D — / S 100% / R 100 ms
- LPF closed but for the noise layer

### Recipe — TB-303 Acid Bass
- Osc: square OR sawtooth
- VCF: 24 dB LPF, **resonance very high** (near self-osc, ~85%)
- VCF EG: A 1 ms / D 200 ms / S 0% / R 50 ms (short decay = squelch)
- Accent: velocity opens filter more on accented notes
- Slide: portamento on overlapping notes (~80 ms glide)
- ⚡ Acid character = filter resonance + decay length + accent dynamics. Not the oscillator.

---

## Leads

### Recipe — Classic Saw Lead
- 2× sawtooth, detune ±8 cents (unison thickening)
- VCF: 24 dB LPF, medium-open cutoff, medium resonance
- VCF EG: A 1 ms / D 120 ms / S 50% / R 100 ms (pluck attack)
- Portamento: 60 ms glide between notes
- Optional: oscillator sync slave for screaming/aggressive variant

### Recipe — Narrow Pulse Lead
- Single pulse, width ~15%
- PWM LFO at 4 Hz, depth low
- Same filter setup as saw lead

---

## Pads

### Recipe — Detuned Saw Pad
- 3× sawtooth, detune ±10 cents (one center, one up, one down)
- VCF: 24 dB LPF, open ~5 kHz, slow filter LFO sweep
- VCA: A 600 ms / D — / S 100% / R 2 s
- Layer: one saw + one square underneath = hollow middle frequency body
- ⚡ Long release on BOTH VCF and VCA — pads breathe.

### Recipe — PWM Pad
- Pulse, PWM LFO at 0.3 Hz, depth 40%
- Filter slightly open
- Slow attack, long release

---

## Classic Synth Character Reference

| Synth | Year | Character | Key feature |
|---|---|---|---|
| Minimoog | 1971 | Fat, punchy | 24 dB Moog ladder filter |
| ARP 2600 | 1972 | Flexible, semi-modular | Normalled patch routing |
| ARP Odyssey | 1972 | Bright, aggressive | Duophonic, ring mod |
| EMS VCS3 | 1969 | Chaotic, experimental | Pin matrix, random source |
| Korg MS-20 | 1978 | Gritty, filter distortion | HPF+LPF cascade, ext audio input |
| Prophet 5 | 1978 | Warm poly | First programmable poly |
| TB-303 | 1982 | Acid squelch | Accent + slide + resonant filter |
| DX7 | 1984 | Bright metallic, FM | 6-op FM, no filter |
| Access Virus C | 2002 | Everything | VA + FM + wavetable |

⚡ Pick the *character* first, then the architecture that produces it. Don't shop synths; shop fingerprints.

---

## Welsh's Harmonic Fingerprint Cheatsheet

| Instrument | Fingerprint |
|---|---|
| Flute (alto) | Fundamental very weak; 2nd dominates |
| Clarinet | Odd harmonics dominant |
| Electric piano (Rhodes) | Even dominate; odd suppressed ~30 dB |
| Pipe organ | Pure additive — drawbars = partials |
| Bowed strings | All present, amplitude falls with n |
| Plucked strings | "Dynamic" — unstable harmonics over time |
| Trumpet / trombone | Dense to 8–10 kHz on attack; filter rolls off fast |
| Flute (concert) | Strong fundamental, smooth rolloff |
| Shakuhachi | Breathy — fundamental + noise |

---

## Stacking vs Layering (Russ §7.2–7.3)

These are different techniques that serve different purposes.

**Stack = composite sound, static blend:**
- Multiple voices with *similar* envelopes playing simultaneously.
- Result: richer, thicker version of the same character.
- Use for: making a thin pad big, doubling a lead for width, sub + click kick.

**Layer = sound that changes character over time:**
- Multiple voices with *different* envelopes — timbre evolves as it plays.
- Result: one "sound" that transforms as it decays.
- Use for: piano (bright attack → warm sustain), brass stab (sharp → warm), bowed strings (slow→ full).
- ⚡ Envelope *difference* between components = the motion. This is why acoustic instruments feel alive.

**3-layer template (Russ §7.1):**
1. Attack transient — short, bright (fast A, fast D, 0 S)
2. Body — main sustain character (medium A, long S)
3. Tail — filtered slow decay, reverb-fed (slow R, low cutoff)

---

## Hocketing (Russ §7.4)

Route MIDI notes to different instruments by criterion. The melody emerges from the ensemble, no single instrument plays it whole.

**7 hocketing criteria:**

| Criterion | How it routes | Musical result |
|---|---|---|
| Order | Alternate notes 1→A, 2→B, 3→C... | Mechanical arpeggio feel |
| Number | Specific note numbers → instrument | Controlled polyphony split |
| Velocity | Soft→A, loud→B | Dynamic timbral shift |
| Beat | On-beat→A, off-beat→B | Rhythmic separation |
| Time | Bars 1–2→A, bars 3–4→B | Call-and-response |
| Controller | CC value routes destination | Real-time performer control |
| Key-switch | Specific keys trigger channel switch | Layer switching on keyboard |

⚡ Hocketing turns "two instruments playing together" into "one composite instrument." Use when a single timbre lacks the rhythmic energy the part needs.

---

## Cross-references

- For the math underneath these recipes → `01-synthesis-engine.md`
- For mic technique on recording the real version → `04-recording-production.md`
- For fast "what waveform for X?" → `05-quick-decisions.md`
