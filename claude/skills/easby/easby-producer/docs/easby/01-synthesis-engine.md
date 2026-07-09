# Synthesis Engine

> Synthesis is harmonic sculpting. I pick a source rich in harmonics (sawtooth, FM with high index, or a wavetable), then I carve away or modulate what doesn't belong. Filter and envelope are the chisels. Everything else is finish work.

> Rule-of-thumb voice: tables and decision rows below are imperative — what Easby should reach for, not first-person narration.

---

## Sound = 3 Perceptual Axes

| Perception | Physical | What I touch |
|---|---|---|
| Pitch | Frequency (Hz) | Oscillator tuning, glide, vibrato |
| Loudness | Amplitude | VCA envelope, tremolo |
| Timbre | Harmonic content | Oscillator wave, filter, modulation |

⚡ Most "this doesn't sound right" problems are timbre problems, not pitch or level. Reach for the filter before the fader.

> Parametric base knowledge (Bessel math, Carson derivation, wavetable theory) is stripped from this file — base models already carry it. What remains is the our-specific decision content: cheatsheets, formulas in use, and the choices Easby actually makes.

---

## Waveforms — Harmonic Fingerprint

| Waveform | Harmonics | Decay | Character | First-choice for |
|---|---|---|---|---|
| Sine | Fundamental only | — | Pure, flute-like, no edge | Sub-bass, kicks, FM operators |
| Triangle | Odd only | 1/n² | Softer than square, hollow | Round basses, soft leads |
| Square | Odd only | 1/n | Hollow, nasal, clarinet-like | Acid bass, retro lead |
| Sawtooth | All | 1/n | Bright, buzzy | Strings, brass, pads — *the workhorse* |
| Pulse | All (ratio-dependent) | varies | Thin/reedy at narrow width | PWM pads, animated leads |
| White noise | All flat | — | Air, wind | Snares, hats, breath layers |

⚡ **When in doubt, start with sawtooth.** It's the richest source for subtractive synthesis. Filter it back down to what you actually need.

---

## Harmonic Series — the rule that governs everything

- nth harmonic = n × fundamental frequency
- **Open pipe / string:** all harmonics (1, 2, 3, 4...). Strings, brass, sawtooth.
- **Closed pipe (clarinet):** odd harmonics only (1, 3, 5...). Square wave models this.
- Higher harmonics = brightness. Lower harmonics = body and character.

⚡ **Welsh's rule:** Get the lowest 3–5 harmonics exactly right. Higher harmonics matter collectively, not individually. Don't waste time tuning the 17th partial.

⚡ **Missing harmonics define character.** Alto flute fundamental is ~40 dB below 2nd harmonic. Rhodes odd harmonics are ~30 dB below even. The absence is the identity.

---

## Subtractive Synthesis — Signal Flow

```
VCO (waveform) → VCF (filter) → VCA (amplitude)
      ↑                ↑              ↑
   Keyboard CV      EG (Cutoff)    EG (Volume)
   LFO (vibrato)    LFO (sweep)    LFO (tremolo)
```

### VCO — pitch & timbre source
- Detune a second oscillator slightly (5–10 cents) for natural chorus/movement.
- **Oscillator sync** — slave resets to master cycle → harsh harmonic distortion. Use for leads and industrial sounds.
- **PWM** — LFO modulates pulse width → animated, "living" sound. The signature of detuned-saw-and-PWM pads.
- Pitch bend: ±2 semitones default, ±12 for portamento-style extremes.

#### Detune mathematics (cents → beat rate)

Detune amount in cents → audible beat frequency (`f_beat = f_carrier × (2^(cents/1200) − 1)`):

| Cents detune | Beat rate at 440 Hz | Character |
|---|---|---|
| ±2 | 0.5 Hz | Imperceptible width, slight chorus tail |
| ±5 | 1.3 Hz | Classic analog-poly width (warm) |
| ±10 | 2.5 Hz | Beating audible, "thicker" |
| ±15 | 3.8 Hz | Phasing, edges into out-of-tune |
| ±25 | 6.4 Hz | Wide unison, frankly detuned |
| > ±30 | > 7 Hz | Out-of-tune territory; use only as effect |

⚡ For **supersaw** stacks (7-voice unison): cent spread 12–25 cents total range, evenly distributed across voices. Pan-spread the outer voices to amplify width.

#### Glide / Portamento Curve

Choice of curve shape matters as much as time:

| Curve | Behavior | Use |
|---|---|---|
| **Linear** | Constant rate | Mechanical leads, sequenced ascents |
| **Exponential** | Fast start, slow end (or vice versa) | Natural voice/expressive leads, acid bass |
| **Smooth (S-curve)** | Ease-in + ease-out | Pad transitions, soft modulation |
| **Instant** | 0 ms time | Pluck/percussive (no glide at all) |

Glide time guideline by sound: pluck = instant; lead = 20–80 ms exp; acid bass = 30–150 ms exp; pad = 100–500 ms smooth.

### VCF — the chisel
| Filter | Use case |
|---|---|
| LPF (low-pass) | 90% of the time. Removes high harmonics; brightens on open, darkens on close. |
| HPF | Thinning pads, creating space, removing rumble |
| BPF | Telephony, nasal, mid-focused leads |
| BRF (notch) | Phaser-like, surgical removal |

**Slopes:**
- 6 dB/oct (1-pole) — gentle, shelving-like
- 12 dB/oct (2-pole) — moderate, good on strings/pads
- ⚡ **24 dB/oct (4-pole Moog)** — the synthesis workhorse. Dramatic, musical.

**Resonance / Q:** peak at cutoff. At high Q → self-oscillation = sine wave at cutoff pitch. Used for acid bass, whistle leads.

**Key tracking:** filter cutoff tracks pitch so high notes stay bright. Default 50–100%.

### ADSR Envelope

```
Attack → Decay → Sustain (level) → Release
  ↑          ↑         ↑               ↑
time       time      0–100%          time
```

| Sound | A | D | S | R |
|---|---|---|---|---|
| Pluck/percussive | Fast | Short | 0% | Short |
| Piano | Fast | Medium | 60–70% | Medium |
| Bowed strings | Slow | — | 100% | Long |
| Brass | Med-fast | Short | 80% | Med |
| Pad | Slow | — | 80–100% | Long |
| Organ | Instant | — | 100% | Instant |

⚡ **Filter EG (VCF EG) is separate from amp EG.** Classic brass/piano patch: sharp filter attack opens cutoff bright, decays to sustain level. The filter envelope is where the *expression* lives.

### Velocity → Timbre Mapping (Scarr, Reid)

Velocity changes more than amplitude — it should also change *timbre*. Default Easby behavior:

| Velocity range | Filter cutoff offset | Attack time offset | Result |
|---|---|---|---|
| Soft (1–40) | Cutoff low (dark) | Attack slow (10–30 ms) | Muted, breathy |
| Medium (41–90) | Mid cutoff | Default attack | Neutral |
| Hard (91–127) | Cutoff open (bright) | Attack snap (0–5 ms) | Bright, percussive |

⚡ **Curve shape matters:** Piano patches want exponential velocity curve (hard strikes much brighter than medium). Acid-bass patches want linear or switched (binary on/off articulation, no in-between).

### LFO — Low Frequency Oscillator (0.1–10 Hz)

| Target | Effect | Use |
|---|---|---|
| VCO pitch | Vibrato | Strings, voice |
| VCA level | Tremolo | EP, organ |
| VCF cutoff | Filter sweep | Autowah, evolving pads |
| Pulse width | PWM | Animated lead/pad |
| LFO rate | Rate mod | Organic, complex motion |

- Sine LFO = smooth; square = stuttering; S&H = random stepped (arp-like).
- ⚡ **Delay on LFO** — vibrato kicks in only after note is held. Realistic singer/violinist behaviour.

---

## Modulation Synthesis — Exact Math

### Ring Modulation (RM)

```
output(t) = A_carrier(t) × A_modulator(t)   [both bipolar]
```

- Output = sum and difference sidebands ONLY: `(C+M)` and `(C−M)`.
- ⚡ Carrier and modulator **disappear** from the output. This is what makes RM sound alien.
- **Integer C:M** → harmonic sidebands (pitched, musical).
- **Non-integer C:M** → inharmonic (bell, metallic, alien).
- Stockhausen used this in *Mantra* (1970) and *Mixtur* (1964).

⚡ **Bell recipe:** C=200 Hz, M=281 Hz (≈ 1:1.4). Add fast exponential decay. Done.

### Amplitude Modulation (AM)

```
AM(t) = A_c × cos(2πCt) × [1 + I × cos(2πMt)]
     = A_c·cos(C) + (I·A_c)/2·cos(C+M) + (I·A_c)/2·cos(C−M)
```

- Modulator is **unipolar** (0 to +1). Carrier *remains* in output (unlike RM).
- Modulation index `I` (0–1): controls sideband amplitude vs carrier.
- At I=0: pure carrier. At I=1: sidebands = half carrier amplitude.
- Use for: subtle chorus-like animation, tremolo at audio rate.

### FM Synthesis (Chowning 1973 → DX7 1983)

`FM(t) = A × sin(2π·C·t + I × sin(2π·M·t))`. C carrier, M modulator, I modulation index. `BW ≈ 2(D + M) = 2M(I + 1)` (Carson). ⚡ **I is the FM brightness knob.**

#### Bessel sideband amplitudes — cheatsheet only

Sideband pair `(C ± n·M)` has amplitude `Jn(I)`. The values Easby actually uses:

- I ≈ 0: carrier dominates.
- ⚡ **I = 2.4**: J0 = 0 → carrier vanishes. Pure sideband shimmer for bells.
- Higher I: energy spreads to higher-order sidebands.

#### C:M Ratio Table

| C:M | Harmonics produced | Character |
|---|---|---|
| 1:1 | All (1, 2, 3...) | Bright, rich, organ-like |
| 1:2 | Odd (1, 3, 5...) | Clarinet-like |
| 2:1 | Every other missing | Hollow, flute-like |
| 1:1.4 | Non-integer → inharmonic | Bell, metallic |
| 1:1.5 (2:3) | Compound: harmonics + sub | Gong-like |
| N:1 (N>1) | Sub-harmonics present | Bass with bite |

⚡ **Non-integer C:M = inharmonic = bell/gong/metallic/alien.** This is the entire DX7 percussion playbook.

### FM vs AM vs RM — Decision Table

| Property | RM | AM | FM |
|---|---|---|---|
| Modulator polarity | Bipolar | Unipolar | (carrier phase) |
| Carrier in output? | No | Yes | Yes (J0) |
| Sidebands | C±M only | C, C±M | C±nM (infinite) |
| Index → spectrum | Fixed shape | Linear | Bessel (non-linear) |
| Best for | Bell, metallic, alien | Subtle animate, chorus | Rich controllable spectra — brass, EP, bell |

---

## Digital Oscillator Fundamentals

### Wavetable Synthesis
- ⚡ **Always interpolate.** Linear interpolation between `table[i]` and `table[i+1]` → SNR 109 dB vs 48 dB non-interpolating. Never ship the non-interpolating path.

### Wavetable Crossfading (Vector Synthesis)
- Crossfade between 2+ wavetables across note duration → time-varying timbre. Use for: evolving pads, morphing leads, breath-to-overdrive transitions.

### Wavestacking
- Multiple wavetables layered, independent amp envelopes. Additive synthesis using complex waveforms.

### Wave Terrain (WT) Synthesis
- Orbit shape over a 3D surface = the timbre. Orbit types: circle (periodic), Lissajous (complex periodic), random walk (noise), spiral (sweeping).

⚡ Morphing orbits = cleanest path to organic evolving textures.

---

## Granular Synthesis

Grain = 1–100 ms audio particle with envelope, waveform, duration, pitch, amplitude, spatial location. Sound = thousands of grains.

### Grain Envelopes

| Envelope | Character | Use |
|---|---|---|
| Gaussian | Smooth bell — no clicks | Most musical default |
| Quasi-Gaussian (Tukey) | Flat top + Gaussian tails | Sustain + smooth edges |
| Three-stage linear (trapezoid) | Attack/sustain/decay | Most flexible |
| Pulse (rectangular) | Harsh, buzzy | Stutter/glitch |
| Narrow impulse | Click | Percussive, transient-like |

### 5 Granular Organization Types

| Type | Organization | Result |
|---|---|---|
| Fourier/wavelet grid | Grains at precise time/freq cells | Resynthesis of arbitrary spectra |
| Pitch-synchronous (PSGS) | Aligned to pitch period | Clean pitch-shift, no artifacts |
| Quasi-synchronous (QSGS) | Near-periodic + jitter | Vocal textures, natural choir |
| Asynchronous cloud (AGS) | Random scatter time/freq | Clouds, atmospheres, noise masses |
| Time-granulated stream | Chop sample, reshuffle | Stretch, freeze, stutter |

### AGS Cloud Parameters

| Parameter | Controls |
|---|---|
| Cloud start time | When the cloud begins |
| Cloud duration | Total length |
| Frequency band | Min/max pitch range of grains |
| Grain density | Grains/sec (overlapping at high density) |
| Amplitude envelope | Overall loudness shape |
| Grain duration | 1–100 ms per grain |
| Grain waveform | Content per grain |
| Spatial location | Pan per grain |

⚡ **Xenakis/Roads key insight:** grain density controls texture density *independent of pitch*. Low density = audible rhythm. High density = fused cloud. Medium = granular shimmer.

### Density → Perceptual Threshold (Roads, *Microsound*)

| Grains / sec | Perceived as | Use |
|---|---|---|
| < 15 (dust) | Sparse scatter, individual events audible | Percussive clouds, ambient texture |
| 15–50 | Rhythm/shimmer (per-grain perception) | Granular leads, shimmer pads |
| 50–150 | Fused texture but still alive | Evolving pad, granular pluck |
| > 200 | Continuous mass (grains fused) | Drone, fused pad, "static" texture |

### Fill Factor (Roads p.105)

`FF = grain_density (grains/sec) × grain_duration (sec)`

- FF < 0.5 → **sparse** — audible silences between grains.
- 0.5 ≤ FF ≤ 1.0 → **covered** — grains touch but don't overlap.
- FF > 1.0 → **packed** — overlapping grains, smooth texture.

Choose FF first, then split density vs duration to taste. Same FF, different distribution = different timbral character.

### Frequency-dependent envelope correlation (Roads p.90)

Shorter envelopes are required for high-frequency grains to avoid muddiness. Rule of thumb: grain envelope length scales inversely with grain pitch. A 2 kHz grain wants a 5–10 ms envelope; a 100 Hz grain can sustain 50 ms+ before muddying.

---

## Pulsar Synthesis (Roads, *Microsound* Ch.4)

Asynchronous grain variant — a variable-width pulse train (the "pulsaret") whose inframetric (sub-audio) rhythm generates a formant. Different from straight granular: pulsars produce a **single audible band** at the inverse of the pulsar period, modulated by the envelope.

| Sub-class | Mechanism | Use |
|---|---|---|
| **Standard pulsar** | Variable-width pulse + envelope | Formants, vocal-like sweeps |
| **Glisson** | Frequency-modulated grains with pitch trajectory across each grain | Sliding pads, swept articulation |
| **Dust** | < 15 grains/sec, asynchronous scatter | Ambient texture, dust particles |

Pulse-width modulation artifact bound: subharmonics emerge at certain duty cycles (≤ 5% or ≥ 95%). Keep duty 10–90% unless artifact is the goal.

---

## Spectral Synthesis — Phase Vocoder / Additive Resynthesis

Phase-vocoder workflow: STFT analyze → manipulate bins (pitch / time / formant) → resynthesize. Different artifact profile from granular:

- **Phase vocoder pitch-shift artifacts:** spectral smearing above ±5 st regardless of grain duration. Roads p.235+.
- **Granular pitch-shift artifacts:** formant collapse on short grains (see `06d-dsp-wiring.md` § Rules of the proxy).

Easby chooses path based on source: tonal sustained material → phase vocoder; percussive/transient material → granular.

---

## Micromontage (Roads *Microsound* Ch.5)

Transformational granulation = extract grains from a source recording, rearrange in time. Distinct from generation (synthesizing new grains): the source identity persists at the grain level but the macro structure is composed. Useful for slice articulation that wants source character but new rhythmic placement.

### Granular Recipes

| Goal | How |
|---|---|
| Time-stretch w/o pitch change | Increase cloud duration, hold freq band |
| Pitch-shift w/o time change | Shift freq band, hold cloud duration |
| Freeze | Fix grain position → infinite sustain of any moment |
| Stutter/glitch | Very short grain duration + high density + narrow time-scatter |
| Scatter blur | Increase position scatter → smeared source |
| Granular pad | Long grain duration + Gaussian env + wide freq band + high density |

---

## Musique Concrète (the original sampling toolkit)

Record anything → manipulate: reverse, pitch-shift (speed change), splice, loop, layer. Tape loop = earliest sampler. Granular synthesis is the digital descendant.

⚡ Any real-world sound is a legitimate oscillator. The microphone is a synth.

---

## FM Algorithms (Russ / DX7 architecture)

Operators = oscillators acting as carrier OR modulator depending on wiring.

| Algorithm type | Structure | Result |
|---|---|---|
| Additive | All operators → output in parallel | Complex additive spectrum |
| Pairs | Modulator → carrier (repeated N×) | Multiple independent FM voices |
| Stacks | M1 → M2 → M3 → carrier | Deep chain; complex sidebands |
| Multiple carriers | Single M → multiple carriers | Layered FM voices |
| Multiple modulators | Multiple Ms → single carrier | Mixed sideband sets |
| Feedback | Operator modulates itself | Noise/distortion character |
| Combination | Any mix of above | Most DX7 presets |

**DX7 Rate/Level envelope (4-stage, per operator):**
- Rate = speed of change (0–99). Level = target amplitude (0–99).
- Attack: R1→L1, R2→L2. Sustain: R3/L3. Release: R4→L4.
- ⚡ High R1 + high L1 = percussive FM. Low R1 = FM pad swell.

---

## Resonant Filter Techniques (Russ §3.3)

**Filter ringing:** High-Q LPF + short noise burst → pitched exponential decay. Use for kick body without a sine VCO.

**Self-oscillation melody:** Raise Q to self-oscillation → keyboard-tracked sine generator with no VCO required. Use for blips, whistles, laser sweeps.

**Beats (heterodyning):** Two oscillators close in pitch → beat rate = |f1 − f2| Hz. Use for chorus depth calibration, detuned pad movement.

Vibrato = LFO → VCO pitch. Tremolo = LFO → VCA amplitude. Never confuse the target.

---

## Additive Filter Emulation (Russ §3.4)

Acoustic instruments: higher partials decay faster than lower ones → perceptual LPF tightens over time.

DSP proxy: in additive synthesis, shorter decay per partial as harmonic number rises.

| Partial | Relative decay |
|---|---|
| 1st | Longest |
| 2nd–3rd | Shorter |
| 4th–5th | Noticeably shorter |
| 6th+ | Decay first |

⚡ Static LPF cannot fake piano because the filtering is a per-partial decay function, not a fixed cutoff.

---

## Wavetable: Swept vs Random-Access (Russ §4.2)

| Mode | Behaviour | Use |
|---|---|---|
| Swept | Reads table at audio rate | Standard oscillator |
| Random-access (slider) | Manual read-head position | Sound morphing |
| Loop sequence | Wavetables concatenated + looped | Rhythmic pattern |
| Velocity switch | Different table per velocity layer | Acoustic emulation |

Always interpolate between table entries (linear minimum). Non-interpolating sweep aliases at every step boundary.

---

## Wavetable Synthesis

A wavetable = an *array* of single-cycle waveforms (frames). The oscillator reads one frame at a time, and the **position parameter** (0–1) scans through the table — frame 0 might be a sine, frame 64 a saw-with-formants, frame 127 a noisy pulse. Scanning between frames at audio rate creates *harmonic animation* without any filter movement. Flip-book analogy: the table is the book, each frame is a page, the position knob flips the pages.

⚡ **The position knob = the spectrum knob.** Modulating position with an LFO/envelope is the entire wavetable paradigm.

| Parameter | Function |
|---|---|
| Position | Which frame is being read (0–1, often quantised to N frames) |
| Morph mode | How adjacent frames interpolate (linear / spectral / no-morph) |
| Spectral warp | Hard-sync / FM / phase-shift / formant-shift applied at read time |
| Unison + detune | Stacked voices, each with its own position offset — supersaw analogue |
| Sub-osc | Independent low-octave sine/triangle, blended pre-filter |
| Noise osc | Separate noise layer (white/sample-playback), blended pre-filter |

**Serum/Vital paradigm:** two wavetable oscillators (A + B) each with independent position + warp + unison, plus a sub-osc and a noise/sampler oscillator. All four feed the filter stage. Each oscillator's position is a mod-matrix destination.

### Wavetable Design (audio → wavetable)
- Slice a sustained recorded tone into 2048-sample (or 256-/512-sample) single-cycle frames.
- Normalise each frame, optionally pitch-correct so every frame sits at the same fundamental.
- Stack N frames (typically 64–256) into the table file. The synth re-pitches and band-limits at playback.

### Difference from Sample Playback
- Sample playback streams *real-time* PCM at a fixed read-rate determined by pitch.
- Wavetable reads a *single cycle* at a rate determined by the played pitch, repeating that cycle every period. The "evolution" comes from *position-scanning across frames*, not from playing through the recording's time.

### Typical Patches

| Patch | Recipe |
|---|---|
| Supersaw | One wavetable on a saw frame, 7-voice unison, ±10–20 cents detune, sub-osc at -12 |
| Evolving pad | Slow LFO (0.1–0.5 Hz) on position, long ADSR, low-Q LPF half-open |
| Morphing lead | Envelope on position so attack opens the spectrum, sustain settles a mid-frame |
| Pluck/snap | Fast envelope snaps position from a noisy frame to a tonal frame in 5–20 ms |
| Bass | Saw-frame position 0, fixed position, narrow LPF with fast filter env |

⚡ **When to choose wavetable over subtractive:** when you need *complex spectra that evolve* (position-scanning) or *spectral animation independent of filter cutoff*. Subtractive is one knob (cutoff) on a fixed source; wavetable is N knobs on N sources.

---

## Additive Synthesis

Fourier's principle: any periodic sound = sum of sinusoidal partials at integer multiples of a fundamental frequency. Additive synthesis builds the sound the way physics dismantles it — one partial at a time. Each partial has independent amplitude, frequency ratio, and (usually) its own envelope.

```
out(t) = Σ Aₙ(t) · sin(2π · n · f₀ · t + φₙ)
         n=1..N
```

| Parameter | Function |
|---|---|
| Partial count (N) | 32 / 64 / 128 — more partials, finer spectral control, higher CPU |
| Per-partial amplitude (Aₙ) | The harmonic spectrum at instant t |
| Per-partial frequency ratio | Integer = harmonic; non-integer = inharmonic (bells, gongs) |
| Per-partial envelope | Each Aₙ can have its own ADSR — see `Additive Filter Emulation` above |
| Formant groups | Clusters of high-amplitude partials around fixed frequencies — vocal/instrumental resonance |

### Formant Synthesis
Group several partials around a fixed Hz peak to model vocal-tract or instrument-body resonances. A vowel's identity = the position of 3 formant peaks (F1, F2, F3). Sliding formant centres across notes = the talking-synth effect. The Kawai K5000 includes a 128-band formant filter with its own envelope for exactly this.

### Brightness Control
- Energy in **low partials (1–4)** → dark, round, body.
- Energy in **high partials (8+)** → bright, edgy, presence.
- Static spectrum = static character. **Per-partial envelopes** (high partials decay first) → acoustic-like brightness fade. See `Additive Filter Emulation` above.

### Harmonic vs Inharmonic
- **Integer ratios** (n = 1, 2, 3, 4 …) → pitched, organ/string-like.
- **Inharmonic ratios** (n = 1, 1.4, 2.3, 3.7 …) → bells, gongs, metallic textures.

### Historical / Modern Implementations
- **Kawai K5000 (1996)** — first hardware true-additive synth at consumer price: 128 partials per source, 4-stage loopable per-partial envelopes, 128-band formant filter.
- **Image-Line Harmor** — modern software additive that *wears subtractive clothing*: filter/EQ controls actually drive the additive engine. Adds audio + image resynthesis (import audio or PNG → additive partials).
- **Camel Audio Alchemy** (now Apple), **Csound `oscbnk`/`adsynt`** — additive in research and modular environments.
- High CPU was the historic blocker; modern SIMD + GPU offloading makes 256+ partials per voice affordable.

### When to Choose Additive
- **Organ-like timbres** (Hammond drawbars are literal additive synthesis: 9 sinusoids at fixed ratios with per-bar amplitude).
- **Vowel-formant pads** where you need 3+ resonant peaks shaped independently.
- **Spectral precision** — when you need to specify exactly which partials are present, e.g. recreating a measured spectrum from a real instrument analysis.
- **Inharmonic bells/gongs** without the FM math — you set the ratios directly.

⚡ **Subtractive carves away. Additive builds up. FM modulates between.** Three different routes to the same harmonic destination — pick the one that matches how you *think* about the target sound.

---

## Modulation Routing and Matrix

A modulator on its own is silent. Modulation = **(source × destination × depth)**. The **mod matrix** is the patch bay: any source routed to any destination at any depth. Modern soft synths expose 8–32 matrix slots.

### Sources

| Source | Shape / Character |
|---|---|
| LFO sine | Smooth periodic — vibrato, tremolo, filter sway |
| LFO triangle | Smooth, slightly more presence at extremes |
| LFO square | Stuttering on/off — trance gate |
| LFO ramp / saw | Sweep then snap-back — auto-pan, riser |
| LFO sample & hold (S&H) | Random stepped — arp-like pitch jitter |
| Envelope (ADSR) | One-shot per-note shape — filter sweep, pitch drop, amp |
| Velocity | Per-note attack strength → brightness/loudness mapping |
| Mod wheel (CC1) | Performer-controlled depth — vibrato amount, filter sweep |
| Aftertouch / channel pressure | Post-attack pressure — expression bends, filter open |
| MPE pitch (X) / slide (Y) / pressure (Z) | Per-note continuous control — see below |
| Macro knob | Single physical knob mapped to N matrix rows |

### Destinations

Oscillator pitch · oscillator level · wavetable position · FM index · filter cutoff · filter resonance · VCA amplitude · pan · LFO rate · LFO depth · effect parameters · another matrix slot's depth (aux/meta routing).

### Typical Routings

| Source | Destination | Effect | Typical Depth |
|---|---|---|---|
| LFO (sine) | Filter cutoff | Tremolo filter | 10–40% |
| LFO (S&H) | Pitch | Random melody | 0–100 cents |
| Env (ADSR) | Filter cutoff | Filter sweep on attack | 50–100% |
| Env (ADSR) | Pitch | Drum-pitch drop on attack | -12 to -36 semitones |
| Velocity | Amplitude | Dynamics | 100% |
| Velocity | Filter cutoff | Brightness on hard hit | 20–60% |
| Velocity | FM index | Brighter spectrum on hard hit | 30–70% |
| Mod wheel | LFO depth | Vibrato on demand | 0–100% |
| Mod wheel | Filter cutoff | Performer filter sweep | 20–80% |
| Aftertouch | Pitch | Expression bend | ±1 semitone |
| Aftertouch | LFO depth | Vibrato swell on press | 0–100% |
| MPE pitch (X) | Oscillator pitch | Per-note bend | ±48 semitones |
| MPE slide (Y) | Filter cutoff / wavetable pos | Per-note timbre | full range |
| MPE pressure (Z) | Amplitude / filter | Per-note dynamics | full range |

### Polarity
- **Unipolar** modulator (0 → +1) only pushes the destination one way from its base.
- **Bipolar** modulator (-1 → +1) pushes both directions around the base — the default for LFOs into pitch/filter.
- Inverting depth flips direction; many synths expose this as a sign on the depth knob.

### MPE — MIDI Polyphonic Expression
Per-note continuous control by allocating each held note its own MIDI channel and broadcasting its expressive data on that channel:

| Axis | Message | Typical mapping |
|---|---|---|
| X — left/right slide | Pitch Bend | Per-note pitch bend, vibrato |
| Y — front/back position | CC74 (Timbre) | Filter cutoff, wavetable position, brightness |
| Z — finger pressure | Channel Pressure | Amplitude, filter open, FM depth |

Controllers: ROLI Seaboard, LinnStrument, Haken Continuum, Madrona Soundplane, Ableton Push 3. Synths must explicitly support MPE to route the per-channel data into per-voice modulation (Bitwig, Equator, Cypher 2, Pigments, Vital, recent versions of most modern soft synths).

⚡ **MPE is per-voice modulation.** Standard MIDI mod-wheel hits *all* held notes; MPE pressure hits *just the note your finger is on*. This is the unlock for keyboard-style expressive bends, slides, and dynamic swells on chords.

### Macro Knobs
One physical knob mapped to N matrix slots with N different depths. Examples:
- "Brightness" macro = filter cutoff +60% + wavetable position +30% + FM index +20% + reverb decay -10%.
- Single performance gesture moves the whole patch coherently. Essential for live performance and quick patch design.

⚡ **Rule of thumb:** if the patch sounds static, the mod matrix is empty. Every interesting voice has at least 3–5 active mod routings.

---

## Cross-references

- For instrument-specific recipes → `02-sound-design-recipes.md`
- For waveform-to-instrument quick lookup → `05-quick-decisions.md`
- For when to use which synthesis style musically → `00-producer-mind.md`
