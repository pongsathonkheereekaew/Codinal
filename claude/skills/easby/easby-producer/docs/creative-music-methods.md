# Creative Music Methods — Master Reference

Synthesized from 14 books across synthesis, acoustics, recording, and creative philosophy.
Sources: Roland (1978), ARP/Friend (1974), Welsh (2006, 2010), Scarr/Virus (2002–2004), Reid/SOS, DeSantis/Ableton, Rubin, Kleon, Huang, Timothy, Rosiński, Swedien, Roads (1996).

---

## 1. Creative Philosophy & Mindset

### The Art Object as Living Thing (Rubin — *The Creative Act*)
- Art is not made; it is *noticed*. The artist is a receiver, not a manufacturer.
- Beginner's mind: forget what a "good" song is supposed to sound like. Listen with fresh ears.
- Serve the work, not the ego. If a part sounds better muted, mute it.
- Constraints are generative: fewer choices → faster creative decisions → better flow.
- Don't analyze while creating. Analysis and creation use different modes. Switch consciously.
- "Finished" is a decision, not a state. Art is abandoned, not completed.
- Return to inspiration sources (playlists, films, images) when stuck — don't force new material.

### Steal With Intent (Kleon — *Steal Like an Artist*)
- Nothing is original. Every sound, every melody has a lineage.
- Map your influences: who influenced your influences? Go one level deeper.
- **Good theft vs bad theft:**
  - Good: transform, remix, credit, study deeply
  - Bad: imitate surface, plagiarize, copy wholesale
- Keep a **swipe file**: collect anything that moves you. Reference it when stuck.
- Work in multiple projects simultaneously — boredom in one feeds another.
- Share your process publicly. The act of showing work attracts collaborators and ideas.
- "Fake it till you make it" = act like the artist you want to become before you are.

### Create First, Refine Later (Huang — *Make Your Own Rules*)
- There are only 12 notes. Everything is nuance: **timing**, **dynamics**, **timbre**.
- Create NOW — don't wait for the perfect setup, plugin, sample.
- **Specific > generic.** A bass that sounds like "a wet slap at 2am in a parking garage" is better than "a dark bass."
- Constrain your palette deliberately: 4 sounds only, 8 bars only, one key only.
- Rules you make yourself → rules you can break with intention.
- Study WHY things work, not just THAT they work. Internalize the principle, discard the rule.
- Learn music theory as a vocabulary, not a cage.

### The Mental Game (Timothy — *Mental Game of Electronic Music Production*)
- Perfectionism = fear wearing a productivity mask. Ship imperfect work.
- Creative blocks are symptom, not disease. Investigate the real cause (tired, comparing, wrong time of day).
- Establish a **making ritual**: same place, same time, same first action (open DAW, play one chord).
- Separate "idea sessions" (no editing) from "refinement sessions" (no new ideas).
- Comparison kills creativity. Stop listening to reference tracks during composition.
- The producer who finishes 100 mediocre tracks beats the one who never finishes the perfect one.

---

## 2. Sound Fundamentals

### Three Properties of Sound (Roland — *Foundation for Electronic Music*)
| Perception | Physical Property | Controls |
|---|---|---|
| Pitch | Frequency (Hz) | Oscillator tuning |
| Loudness | Amplitude | VCA, envelope level |
| Timbre | Waveform / harmonic content | Oscillator wave, filter |

### Waveforms & Harmonic Content
| Waveform | Harmonics Present | Character |
|---|---|---|
| Sine | Fundamental only | Pure, flute-like, no edge |
| Triangle | Odd only (1/n² amplitude) | Softer than square, hollow |
| Square | Odd only (1/n amplitude) | Hollow, nasal, clarinet-like |
| Sawtooth | All (1/n amplitude) | Bright, buzzy, strings/brass |
| Pulse | All (ratio adjustable) | Thin/reedy at narrow width |
| White noise | All at equal amplitude | Air, wind, percussion transients |

**Key insight:** Sawtooth = richest source for subtractive synthesis. Start here for most acoustic instrument emulations.

### Harmonic Series
- nth harmonic = n × fundamental frequency
- Open pipe / string: all harmonics present (1st, 2nd, 3rd, 4th...)
- Closed pipe (clarinet): odd harmonics only (1st, 3rd, 5th...)
- Higher harmonics = brightness. Lower harmonics = body/character.
- **Practical rule (Welsh Vol.2):** Get the lowest 3–5 harmonics exactly right. Higher harmonics matter collectively but not individually.

### Resonance
- String resonance: body resonates at string's fundamental AND harmonics → warm sustain
- Air column resonance: pipe resonates at wavelength multiples
- Resonance peak at filter cutoff (Q/resonance knob) mimics natural body resonance → adds life

### Spatial Perception
- **Dry + loud = close.** Wet + soft = distant.
- Reverb controls apparent **room size** and **listener distance** simultaneously.
- Soft sound + heavy reverb = far away in large space.
- Loud + dry = in-your-face, close.
- **Echo** (>100ms distinct repeats) vs **reverb** (blurred multiple reflections) vs **chorus** (slight pitch detune recombined).

---

## 3. Synthesis — Core Concepts

### Subtractive Synthesis Signal Flow
```
VCO (waveform) → VCF (filter) → VCA (amplitude)
      ↑                ↑              ↑
   Keyboard CV      EG (Cutoff)    EG (Volume)
   LFO (vibrato)    LFO (sweep)    LFO (tremolo)
```

### VCO — Voltage Controlled Oscillator
- Keyboard → pitch CV (1V/octave standard)
- Pitch bend: ±2 semitones typical, ±12 for extreme effect
- Detune second oscillator slightly for natural chorus/movement
- **Oscillator sync:** slave resets to master cycle → harsh harmonic distortion → leads, industrial sounds
- **Pulse Width Modulation (PWM):** LFO modulates pulse width → animated, living sound

### VCF — Voltage Controlled Filter
- **LPF (Low Pass):** most used. Removes high harmonics. Brightens on open, darkens on close.
- HPF: removes bass. Good for thinning pads, creating space.
- BPF: bandpass — telephony, nasal vocal sounds.
- BRF: band reject (notch) — phaser-like, specific frequency removal.
- **Slope:** 6 dB/oct (1-pole, gentle) vs 12 dB/oct (2-pole) vs 24 dB/oct (4-pole Moog) — steeper = more dramatic filter effect.
- **Resonance / Q:** peak at cutoff frequency. At high Q → self-oscillation = sine wave at cutoff pitch.
- **Key tracking:** filter cutoff tracks keyboard pitch so high notes stay bright (usually 50–100% tracking).

### ADSR Envelope
```
Attack → Decay → Sustain (level) → Release
  ↑          ↑         ↑               ↑
time       time      level (0–100%)   time
```
- Fast attack = percussive, hard
- Slow attack = bowed strings, pad swells
- High sustain = organs, strings
- Zero sustain + medium decay = plucked strings, piano
- Long release = reverb-like natural tail

**ADSR on filter (VCF EG):** separate envelope modulates cutoff over time. Classic: sharp attack opens filter bright → decays to sustain level. Critical for brass, piano transients.

### LFO — Low Frequency Oscillator
| LFO Target | Effect | Use |
|---|---|---|
| VCO pitch | Vibrato | Strings, voice expression |
| VCA level | Tremolo | Electric piano, organ |
| VCF cutoff | Filter sweep | Autowah, evolving pads |
| Pulse width | PWM | Animated lead/pad |
| LFO rate | Rate modulation | Complex organic movement |

- LFO rate: ~0.1–10 Hz (sub-audio)
- LFO waveform: sine = smooth; square = stuttering; S&H = random stepped (arp-like)
- Delay on LFO: vibrato kicks in only after note held — more realistic expression

### FM / AM / Ring Modulation
- **FM (Frequency Modulation):** modulator oscillator modulates carrier frequency → complex inharmonic sidebands → metallic, bell, electric piano
  - Carrier:Modulator ratio determines harmonic relationship. Integer ratios = harmonic. Non-integer = inharmonic (bell, gong).
- **AM (Amplitude Modulation):** modulator at audio rate → sidebands at carrier ± modulator freq
- **Ring modulation:** multiplier circuit → outputs ONLY sidebands (not carrier or modulator) → metallic, alien, Dalek

### Musique Concrète Techniques
- Record any sound → manipulate: reverse, pitch-shift (speed change), splice, loop, layer
- Tape loop = earliest sampler
- Granular synthesis = slice any sound into tiny grains → resequence → clouds, pads, textures

---

## 4. Synthesis — Patch Programming

### Reverse Engineering Any Sound (Welsh — *Synthesizer Cookbook*)
**Process:**
1. Get FFT/spectrum analyzer on target sound
2. Read harmonic diagram: X = frequency, Y = amplitude (dB)
3. Match waveform to harmonic content (sawtooth = all harmonics, square = odd only)
4. Note which harmonics dominate → set filter cutoff there
5. Observe how high-frequency harmonics change over time → set filter EG decay
6. Map attack shape → set VCA attack time
7. Map amplitude decay → set VCA decay + sustain

**Key principle:** Low harmonics (fundamentals, 2nd, 3rd) = character. High harmonics = brightness. Collectively important; individually not critical.

### Instrument Categories & Synthesis Approach

#### Strings (Sawtooth-based)
- Violin, viola, cello, double bass: sawtooth waveform, slow attack VCA, filter EG tracks bow pressure
- Pizzicato: fast attack, fast decay, near-zero sustain
- Electric guitar: sawtooth or PWM, moderate attack, long sustain, filter EG very fast
- Acoustic guitar: complex (use "Dynamic" harmonic model — unstable harmonics), add noise for pluck transient

#### Woodwinds (Hollow — odd-harmonic-leaning)
- Flute: near-sine at low harmonics, add white noise for breath (mix 10–15%)
- Clarinet: square wave (odd harmonics), fairly flat harmonic spectrum
- Oboe/Saxophone: sawtooth with resonant filter peak, lots of harmonic content above 4kHz
- Recorder: soft, strong fundamental, few high harmonics — LPF nearly closed

#### Brass (Sawtooth + hard filter EG attack)
- Trumpet, trombone, horn: sawtooth, filter opens sharply on attack then decays slightly
- Muted brass: BPF with high Q peaks around 1–3kHz
- French horn: rounder, filter more closed, more 2nd harmonic body

#### Keyboards
- Rhodes Electric Piano: **odd harmonics suppressed** (1st, 3rd, 5th ~30dB lower than 2nd, 4th, 6th). Use sawtooth → notch-filter the odd harmonics OR use FM (DX7 algorithm).
- Hammond organ: additive — draw bars = partial levels (16', 8', 5⅓', 4', 2⅔', 2', 1⅗', 1⅓', 1'). Sine waves only.
- Harpsichord: fast attack, near-zero sustain, strong upper harmonics, bright LPF setting
- Grand piano: complex — "Dynamic" harmonics across register; high notes = brighter, lower notes = more fundamental weight

#### Voice
- Vowels = resonant peaks (formants): each vowel has 2–3 formant frequencies
- Ah ≈ 800Hz + 1200Hz; Ee ≈ 270Hz + 2300Hz; Oo ≈ 300Hz + 870Hz
- Choir: layer detuned voices + reverb + vibrato LFO on each

#### Percussion — Tuned
- Bell/Chime: ring mod or FM with non-integer ratio + fast decay + no sustain
- Marimba/Vibraphone: marimba = shorter decay, vibraphone = long decay + tremolo LFO on VCA
- Steel drum: FM with specific carrier/modulator ratios

#### Percussion — Untuned
- Kick: sine + noise, pitch drop envelope (fast pitch EG: high→low), punchy VCA
- Snare: noise + short sine, fast attack/decay
- Hi-hat: noise through HPF, short decay (closed) vs medium (open)
- Cymbal: FM with complex non-integer ratios, long decay

#### Drum Machines (808/909 reference — Welsh Vol.2)
- **808 Bass:** sine wave, pitch envelope (high→low fast), long decay — sub-heavy
- **808 Snare:** noise + sine mix, medium decay
- **909 Kick:** shorter, punchier than 808, more transient click
- **808 vs 909:** 808 = smooth analog, 909 = snappier digital feel

### Classic Synth Character Reference (Scarr — *Programming Analogue Synths*)
| Synth | Year | Character | Key Feature |
|---|---|---|---|
| Minimoog | 1971 | Fat, punchy | 24dB Moog ladder filter |
| ARP 2600 | 1972 | Flexible, semi-modular | Patchable with normalled routing |
| ARP Odyssey | 1972 | Bright, aggressive | Duophonic, ring mod |
| EMS VCS3/Synthi | 1969 | Chaotic, experimental | Pin matrix, random source |
| Korg MS-20 | 1978 | Gritty, filter distortion | HPF+LPF cascade, external audio input |
| Prophet 5 | 1978 | Warm poly | Poly with memory — first programmable |
| TB-303 | 1982 | Acid squelch | Accent + slide + resonant filter |
| DX7 | 1984 | Bright metallic, FM | 6-operator FM, no filter |
| Access Virus C | 2002 | Everything | Virtual analogue + FM + wavetable |

### Programming Leads
- Oscillator: sawtooth or pulse (narrow) for aggression
- Filter: medium-open, resonance medium, filter EG fast attack/fast decay (pluck)
- Portamento/glide: smooth pitch slide between notes — sets synth lead character
- Unison: detune multiple oscillators — thickens lead

### Programming Bass
- Oscillator: sawtooth (full bass) or triangle (round bass) or square (TB-303 acid)
- Filter: closed-ish, filter EG short decay for pluck; accent = velocity opens filter more
- TB-303 acid: resonance very high (near self-osc), short decay, slide between notes = portamento

### Programming Pads
- Oscillator: 2–3 detuned voices, medium attack
- LFO: slow sine on pitch (gentle vibrato) or PWM (animation)
- Filter: open but not too bright, slight filter LFO sweep
- Long release on both VCF and VCA
- Layer: one saw + one square = hollow middle frequency

### Programming Brass
- Oscillator: sawtooth
- Filter: fast attack (opens on hit), slight decay to mid position
- VCA: fast attack (not instant), slight decay to sustain
- Resonance: medium — adds "blat" on attack

---

## 5. Harmonic Catalog — Instrument FFT Reference (Welsh Vol.2)

**Vol.2 is a visual harmonic reference** — FFT amplitude spectra for 123+ real instruments. Use to:
- Identify which harmonics matter for each instrument category
- Know what filter settings and waveforms to target
- Match synth output to real instrument harmonic fingerprint

### Methodology (from Usage section)
1. Low harmonics appear first on attack, die last on decay → sculpt with **LPF + envelope first**, then add VCA envelope
2. Harmonic structure sometimes requires: oscillator sync, PWM, FM, ring mod — mixing waveforms alone not always sufficient
3. "**Dynamic**" instruments (plucked/hammered strings) = harmonics fluctuate independently over time → replicate via PWM, oscillator sync slave pitch modulated by EG/LFO, or FM with modulated depth
4. **Missing harmonics** are equally important: Alto Flute fundamental is ~40dB below 2nd harmonic. Electric Piano odd harmonics ~30dB below even harmonics — these absences define the character.
5. Graph reading: amplitude on Y (0 to −100dB), frequency on X (up to 20kHz). Focus on left (low) harmonics — they define character. High harmonics define brightness collectively.

### Key Harmonic Fingerprints
| Instrument | Harmonic Profile |
|---|---|
| Flute (alto) | Fundamental very weak; 2nd harmonic dominates — synthesize at 2nd harmonic pitch |
| Clarinet | Odd harmonics dominant (square wave model) |
| Electric Piano (Rhodes) | Even harmonics dominate; odd suppressed ~30dB |
| Pipe organ | Pure harmonic additive — draw bars = partials |
| Bowed strings | All harmonics, amplitude falls with n |
| Plucked strings | "Dynamic" — harmonics unstable over time |
| Trumpet/Trombone | Dense harmonics to 8–10kHz on attack; filter rolls off quickly |
| Flute (concert) | Strong fundamental, smooth rolloff — near-sine |
| Shakuhachi | Breathy — fundamental + strong noise component |

---

## 6. Recording & Production

### The Acusonic Recording Process (Swedien — *Recording Michael Jackson*)
- SMPTE-sync multiple 24-track tape machines simultaneously → capture everything
- Record in **stereo at the source** whenever possible (not mono-then-widen later)
- **SM7 dynamic mic on MJ lead vocals** — handles extreme SPL, smooth top-end
- **Minimal compression:** preserve transients. Compression = last resort, not default.
- **Anti-mono philosophy:** every element should exist in stereo space. Mono collapses magic.
- **Synaesthesia mixing:** assign colors to sounds. Bright yellow = hi-hat, deep blue = bass. Helps with spatial placement decisions.
- **Blumlein pair** (two figure-8 mics at 90°) for stereo room capture — most natural stereo field.

### Dennis DeSantis / Ableton (*Making Music*)
- 74 creative strategies organized by problem type (starting, developing, finishing)
- **Intention + surprise = interesting music.** All intention = boring. All surprise = noise.
- **Develop musical ideas by constraining changes:** change rhythm but not pitch, or pitch but not rhythm.
- **Limitations force creativity.** Remove one element; see if it's missed.
- Arrangement is subtractive: start with everything playing, remove until it breathes.
- Use automation to tell the story: sounds should evolve, not loop statically.

---

## 7. Microphone Techniques (Rosiński — *Microphone Techniques*)

### Stereo Techniques Reference
| Technique | Mics | Angle | Spacing | Character |
|---|---|---|---|---|
| X-Y (coincident) | 2× cardioid | 90° | 0 (coincident) | Focused center, mono-compatible |
| A-B (spaced pair) | 2× omni | 0° | 20–100cm | Wide, phase issues in mono |
| M-S | 1× cardioid + 1× fig-8 | 90° | 0 (coincident) | Variable width, mono-compatible |
| Blumlein | 2× fig-8 | 90° | 0 (coincident) | Natural, full-frequency stereo |
| ORTF | 2× cardioid | 110° | 17cm | Approximates human ears |
| NOS | 2× cardioid | 90° | 30cm | Wider than ORTF |
| Decca Tree | 3× omni | — | LCR arrangement | Orchestral, wide + center fill |
| INA-3/INA-5 | 3–5× cardioid | Splayed | Center + flanks | Surround capture |
| OCT | 1× super-cardioid + 2× cardioid | — | Spaced flanks | Surround, tight center |

### Instrument Miking Principles
- **Distance = brightness + room.** Close mic = more direct, more low-end (proximity effect). Far mic = more room, less proximity.
- **On-axis = bright.** Off-axis = warmer, reduced high-frequency.
- **Room = part of the sound.** Recording in a dead room then adding reverb ≠ recording in a live room.
- Acoustic guitar: XY at 12th fret (balanced body + attack) or A-B (body + soundhole) for width
- Drums: close mics (kick, snare) + overhead stereo pair + room mic at distance — blend for desired live/close ratio
- Vocals: cardioid dynamic (SM7/SM58) for control; condenser for air + detail; pop filter mandatory

---

## 8. Compositional Methods

### Melodic Development
- **Sequence:** repeat a motif starting on a different scale degree
- **Inversion:** flip the melodic contour upside-down
- **Retrograde:** play the phrase backwards
- **Augmentation:** stretch note durations (2× or 4×)
- **Diminution:** compress note durations (÷2 or ÷4)
- **Fragmentation:** take 2–3 notes from a phrase, develop those alone

### Rhythmic Development
- Shift phrase by one 16th note = polyrhythmic feel without changing notes
- **Hemiola:** imply 3-beat groupings within 4/4 (3+3+2 or 3+3+3+3+4)
- Add/remove one note from a repeating pattern → evolving pattern
- Displace kick or snare by one 16th → groove shift

### Harmony & Chord Variation
- **Deceptive cadence:** replace final I with vi (or bVI in minor) → surprise resolution
- **Secondary dominants:** V7 of the next chord (e.g., A7 → D in C major)
- **Borrowed chords (modal mixture):** bVII, bVI from parallel minor/major
- **Tritone substitution:** replace V7 with bII7 (same tritone, different bass)
- **Add extensions:** turn triads into 7ths, 9ths, sus2, sus4 for color without changing function

### Texture & Arrangement
- **Density contrast:** full→sparse→full. Ears reset during sparse sections.
- **Register contrast:** all-high section followed by all-low = instant drama.
- **Tension via unresolved dissonance:** tritone, major 7th interval hanging unresolved.
- **Call and response:** melodic question left, answer right.

---

## 9. Production Workflow Principles

### The Swipe File → Production Pipeline (Kleon + Huang synthesis)
1. Collect: keep a folder of sounds, references, images that move you
2. Analyze: WHY does each reference work? Identify the specific element
3. Extract: isolate the technique (not the sound itself)
4. Reconstruct: build that technique with your own materials
5. Combine: combine 2–3 extracted techniques from different sources = your sound

### Constraint-First Production (Huang)
- Session constraint examples:
  - One instrument, one BPM, one key
  - No reverb/delay allowed
  - Must finish in 1 hour
  - 4 sounds maximum
- Constraints surface what you actually know vs what you've been hiding behind complexity

### Iterative Layering Method
1. Start with **rhythm only** — get groove locked first
2. Add **bass** — define harmonic rhythm
3. Add **chords** — confirm harmony
4. Add **melody** — work above locked foundation
5. Add **texture + atmosphere** — last, not first
6. Remove anything that doesn't serve the whole

### Quality Signals (Rubin synthesis)
- If you're bored listening to your own track → the listener will be bored sooner
- If you keep playing a section on repeat because it feels good → that's the hook
- If you're avoiding finishing → ask what you're afraid of hearing
- Get feedback from one person whose taste you trust. Ignore crowd opinions during creation.

---

## 10. Quick Reference Tables

### Sound → Waveform Start Points
| Target Sound | Start Waveform | Key Modification |
|---|---|---|
| Strings (bowed) | Sawtooth | Slow attack, filter EG |
| Brass | Sawtooth | Fast filter EG attack |
| Flute | Sine + noise | Blend 10–15% white noise |
| Clarinet | Square | Moderate LPF |
| Electric piano | Sawtooth → FM | Suppress odd harmonics |
| Organ | Additive sines | Draw bar levels |
| Kick drum | Sine + pitch EG | High→low pitch drop |
| Snare | Noise + sine | Fast decay |
| Hi-hat | White noise + HPF | Decay length = open/closed |
| Pad | Detuned saw + PWM | Slow attack, long release |
| Acid bass | Square + resonant LPF | High Q, accent, slide |
| Lead | Sawtooth or narrow pulse | Portamento, sync option |

### Filter Slope Reference
| Slope | Poles | Character |
|---|---|---|
| 6 dB/oct | 1-pole | Gentle, high-end shelving |
| 12 dB/oct | 2-pole | Moderate — useful for strings, pads |
| 24 dB/oct | 4-pole (Moog) | Dramatic — synthesis workhorse |

### ADSR Presets by Sound Type
| Type | Attack | Decay | Sustain | Release |
|---|---|---|---|---|
| Percussive (pluck) | Fast | Short | 0% | Short |
| Piano | Fast | Medium | 60–70% | Medium |
| Strings (bowed) | Slow | — | 100% | Long |
| Brass | Med-fast | Short | 80% | Med |
| Pad | Slow | — | 80–100% | Long |
| Organ | Instant | — | 100% | Instant |

### Stereo Mic Choice Matrix
| Priority | Technique |
|---|---|
| Mono compatibility (broadcast) | X-Y or M-S |
| Widest stereo image | A-B spaced pair |
| Natural, immersive | Blumlein |
| Orchestral/classical | Decca Tree |
| Surround film | OCT or INA-5 |
| Variable width in post | M-S |

---

---

## 11. Digital Oscillator Fundamentals (Roads — *Computer Music Tutorial*)

### Table-Lookup Synthesis
- **Wavetable:** one cycle of a waveform stored in a memory array of length L (typically 512–8192 samples)
- **Phase increment** (P): `P = (L × frequency) / sampleRate`
- Each sample: read `table[phase]`, advance `phase += P`, wrap at L
- **Interpolating oscillator:** linear interpolation between table[i] and table[i+1] → SNR 109 dB vs 48 dB non-interpolating. Always interpolate.
- **Unit generators (UGs):** modular synthesis blocks (oscillators, filters, envelopes) interconnected as patches. Concept from Music III (Mathews, 1960). Foundation of Csound, SuperCollider, Max/MSP.

### Multiple Wavetable Synthesis
- **Wavetable crossfading (Vector Synthesis):** oscillator smoothly crossfades between 2+ wavetables over note duration → time-varying timbre. First commercial: Sequential Prophet VS (1985).
  - Applications: evolving pads, morphing lead tones, breath-to-overdrive transitions
  - Implementation: `out = (1−t)×wave_A[phase] + t×wave_B[phase]` where t sweeps 0→1

- **Wavestacking:** layer multiple wavetables, each with its own independent amplitude envelope → additive synthesis using complex waveforms (not just sines). Each layer contributes its full harmonic content independently.

### Wave Terrain (WT) Synthesis
- **Concept:** define a 3D surface `wave(x, y)` → scan along an "orbit" path `(x(t), y(t))` → output signal = z values along orbit
- **Periodic orbit** → periodic sound. **Time-varying orbit** → evolving, moving timbre.
- Orbit types: circles (periodic, steady), Lissajous figures (complex periodic), random walks (noise-like), spirals (sweeping timbre)
- **Creative use:** orbit shape directly controls timbre; morph between orbit shapes for organic evolving textures

---

## 12. Granular Synthesis — Complete Reference (Roads)

### What Is a Grain
- Grain = 1–100ms audio particle with: envelope shape, waveform content, duration, frequency/pitch, amplitude, spatial location
- Sound = assemblage of many thousands of grains
- Grain envelope types:
  | Envelope | Character |
  |---|---|
  | Gaussian | Smooth bell curve — no clicks, most musical |
  | Quasi-Gaussian (Tukey window) | Flat top + Gaussian tails — sustain + smooth edges |
  | Three-stage linear (trapezoid) | Attack / sustain / decay — most flexible |
  | Pulse | Rectangular — harsh, buzzy |
  | Narrow impulse | Click — percussive, transient-like |

### 5 Granular Organization Types
| Type | How grains are organized | Resulting sound |
|---|---|---|
| **Fourier/wavelet grid** | Grains at precise time/frequency cells | Resynthesis of arbitrary spectra |
| **Pitch-synchronous (PSGS)** | Grains aligned to pitch period | Clean pitch-shifting without artifacts |
| **Quasi-synchronous (QSGS)** | Near-periodic with slight jitter | Vocal-like textures, natural choir |
| **Asynchronous cloud (AGS)** | Random scatter in time/freq space | Clouds, atmospheric textures, noise-like masses |
| **Time-granulated stream** | Chop sampled audio into grains, reshuffle | Granular time-stretching, freeze, stutter |

### AGS Cloud Parameters (Asynchronous Granular Synthesis)
| Parameter | Controls |
|---|---|
| Cloud start time | When the cloud begins |
| Cloud duration | Total length of the event |
| Frequency band | Min/max pitch range of grains |
| Grain density | Grains per second (overlapping at high density) |
| Amplitude envelope | Overall loudness shape of cloud |
| Grain duration | Individual grain length (1–100ms) |
| Grain waveform | Content inside each grain |
| Spatial location | Stereo/multichannel pan per grain |

**Key insight (Xenakis 1960, Roads 1974):** grain density controls texture density independent of pitch. Low density = individual grains audible as rhythm. High density = fused cloud. At medium density = granular shimmer.

### Practical Granular Applications
- **Time-stretch without pitch change:** increase cloud duration while holding frequency band constant
- **Pitch-shift without time change:** shift frequency band while holding cloud duration
- **Freeze:** set grain position to fixed point in source → infinite sustain of any moment
- **Stutter/glitch:** very short grain duration + high density + narrow time-scatter = stutter
- **Scatter effect:** increase position scatter → smeared, blurred version of source
- **Granular pad:** long grain duration + Gaussian envelope + wide frequency band + high density = cloud pad

---

## 13. Modulation Synthesis — Deep Reference (Roads)

### Ring Modulation (RM) — Exact Formula
```
output(t) = A_carrier(t) × A_modulator(t)     [both bipolar signals]
```
- Produces ONLY sum and difference sidebands: `(C+M)` and `(C−M)`
- Carrier and modulator themselves disappear from output
- **Integer C:M ratio** → harmonic sidebands (pitched, musical)
- **Non-integer C:M** → inharmonic sidebands (metallic, bell-like, alien)
- **Stockhausen:** used RM extensively in *Mantra* (1970), *Mixtur* (1964) — orchestra through ring modulators live
- **Analog vs digital RM:** analog = real multiplication of two signals. Digital = same, exact multiplication.

**Creative recipe — Bell/Gong:** C=200Hz, M=281Hz (ratio ≈ 1:1.4) → non-integer → inharmonic sidebands → bell quality. Add fast exponential decay.

### Amplitude Modulation (AM) — Exact Formula
```
AM(t) = A_c × cos(2πC×t) × [1 + I × cos(2πM×t)]
      = A_c×cos(C) + (I×A_c)/2×cos(C+M) + (I×A_c)/2×cos(C−M)
```
- Modulator is **unipolar** (0 to +1), carrier retained in output (unlike RM)
- Modulation index `I` (0 to 1): controls sideband amplitude relative to carrier
- At I=0: pure carrier. At I=1: sidebands = half carrier amplitude.
- AM ≠ RM: AM retains carrier; RM does not.

### FM Synthesis — Exact Formula (Chowning 1973 → Yamaha DX7 1983)
```
FM(t) = A × sin(2π×C×t + I × sin(2π×M×t))
```
- **C** = carrier frequency, **M** = modulator frequency
- **I** = modulation index = `D / M` (where D = peak frequency deviation in Hz)
- **Bandwidth (Carson's rule):** `BW ≈ 2 × (D + M) = 2 × M × (I + 1)`
- As I increases: energy redistributes from carrier into sidebands — sound brightens dramatically

#### Bessel Function Sideband Amplitudes
Each sideband pair `(C ± n×M)` has amplitude `Jn(I)` (nth-order Bessel function):
- `J0(I)` = carrier amplitude
- `J1(I)` = 1st sideband pair amplitude
- `J2(I)` = 2nd sideband pair amplitude
- At I≈0: carrier dominates (J0≈1, all others ≈0)
- At I=2.4: carrier nulls (J0=0) — carrier vanishes, sidebands dominant
- At higher I: energy spreads further, higher-order sidebands grow

#### C:M Ratio Rules
| C:M Ratio | Harmonic relationship | Character |
|---|---|---|
| 1:1 | All harmonics present (1st, 2nd, 3rd...) | Bright, rich, organ-like |
| 1:2 | Even harmonics: 1st, 3rd, 5th... (odd partials) | Clarinet-like |
| 2:1 | Every other harmonic missing | Hollow, flute-like |
| 1:1.4 | Non-integer → inharmonic | Bell, metallic |
| 1:1.5 (2:3) | Compound: harmonics + sub | Gong-like |
| N:1 (N>1) | Carrier multiple of modulator | Sub-harmonics present |

**Non-integer ratios → inharmonic spectra → bell, gong, metallic, alien sounds.**

#### FM Recipe — Brass-Like Sound (after Chowning)
- C:M = 1:1 (same frequency ratio)
- I sweeps 0 → 5 on attack (fast rise → adds brightness on hit)
- I decays from 5 → 0.5 on sustain (harmonics reduce over time = natural brass falloff)
- VCA: fast attack, medium decay, high sustain, medium release
- Result: bright attack with spectral decay mimics real brass harmonic rolloff

#### FM Recipe — Electric Piano (DX7)
- C:M = 1:1 or 2:1
- I starts moderate (~2), decays slowly to 0 (harmonics fade as note rings out)
- Soft, bell-like quality at low velocities; bright at high velocities (velocity → I depth)

#### FM Recipe — Bell/Tubular (after Chowning)
- C:M = 1:1.4 (non-integer)
- I = 1.5–3.0 (generates rich inharmonic sidebands)
- VCA: instant attack, exponential decay, zero sustain, zero release
- Result: metallic, inharmonic, natural decay profile

### FM vs AM vs RM Summary
| Property | Ring Mod | AM | FM |
|---|---|---|---|
| Modulation target | Amplitude (bipolar) | Amplitude (unipolar) | Frequency |
| Carrier in output? | No (disappears) | Yes | Yes (as J0 component) |
| Sidebands | C±M only | C, C+M, C−M | C±nM (infinite series) |
| Complexity with I | Fixed | Scales linearly | Bessel function (non-linear) |
| Best for | Metallic, bell, alien | Chorus, subtle animate | Rich, controllable spectra |

---

*Sources: 14 books read 2026-06-03. Devarahi (164.9MB) inaccessible — exceeds 100MB Read tool limit.*
