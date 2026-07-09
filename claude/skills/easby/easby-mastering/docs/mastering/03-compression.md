> 📎 Technique core (shared/public): [../../../shared/dynamics.md](../../../shared/dynamics.md). This file = **mastering application only** — don't duplicate the technique here.

# 03 — Compression in Mastering

## Two Purposes

- **Compressor** → changes inner dynamics, adds body and punch; changes the *character*
- **Limiter** → raises average loudness without changing sound character; ceiling control

Use compressor for punch/body. Use limiter for loudness. Never substitute one for the other.

## Mastering Compressor Settings

| Parameter | Typical range | Notes |
|---|---|---|
| Ratio | 1.5:1 – 3:1 | Above 4:1 = too aggressive for full-mix; 10:1+ = limiter territory |
| Threshold | -20 to -10 dBFS | Invisible mode: -30 to -40 dBFS at 1.01:1–1.1:1 (barely moves needle, adds subtle glue) |
| Attack | 50–300ms (avg 100ms) | Too short → snare transient softened; start slower |
| Release | 50–500ms (avg 150–250ms) | Too fast (<50ms both attack+release) → waveform-following distortion |
| Gain reduction | 2–4 dB typical; rarely >6 dB | |

## Attack/Release Interaction

- Attack too short: dulls transient snap (kick, snare lose punch)
- Release too short: distortion artifacts (compressor can't recover before next transient)
- Release too long: pumping, unnatural breathing
- Goal: compressor breathes invisibly in time with the song's pulse

**Hardware references:** Shadow Hills, Manley SLAM Master, Maselec MLA-2, Fairchild 670 (plugin)

**Compression destroys stereo depth.** It brings up inner voices and collapses ambience/width. Use as little as possible.

## Dynamic EQ — Preferred Modern Default (Katz / Owsinski)

**Dynamic EQ before Multiband.** Both Katz and Owsinski recommend dynamic EQ over multiband compression for any band-specific dynamics work — it is significantly more transparent and easier to dial in musically.

| Why dynamic EQ wins | Detail |
|---|---|
| Q parameter | Targets a narrow musical band (sibilance at 6 kHz, mud at 250 Hz) without smearing adjacent bands |
| Threshold per band | Engages only when needed; passes through cleanly otherwise |
| No crossover phase | Multiband crossovers add phase distortion; dynamic EQ does not |
| Reads as "EQ" not "compression" | Easier to debug audibly — operator hears it as tonal correction |

**Plugins:** FabFilter Pro-Q3, Sonnox Oxford Dynamic EQ, TDR Nova, Soothe2 (dynamic resonance suppression — a specialised dynamic EQ).

**Use dynamic EQ for:**
- Sibilance (5–9 kHz, fast attack, narrow Q)
- Boomy bass resonance (60–120 Hz, slow attack)
- Harsh midrange peaks (1.5–3 kHz)
- Boxiness (200–500 Hz, medium attack)

**Reach for multiband ONLY when** dynamic EQ has been tried and the problem is genuinely broadband (not a single resonance) — e.g. an entire 80–250 Hz bass region is pumping.

## Multiband Compression — Use Rarely

Multiband is powerful and dangerous. Each band operates independently; the mix can become unnatural quickly.

**Use multiband only when:**
- Isolated bass drum is pumping the entire mix (low band only, slow attack)
- Sibilance must be controlled without de-essing individual tracks (3–9kHz band, fast attack/medium release)
- The mix is unfixable without a remix and you must isolate a problem frequency range

**Never use multiband when:**
- Single-band with slower attack would solve the issue (try this first)
- Upward expansion would restore dynamics better (try second)
- You want "more control" — that is not a multiband job

**Max 2 bands** in most mastering situations. Start with the widest possible band settings.

**Hardware references:** Maselec MLA-3 / **Plugins:** Waves C6, UAD Precision Multiband, FabFilter Pro-MB

<!-- Dynamic EQ section moved above Multiband — superseded -->


## Hypercompression — The Enemy

Hypercompression = dynamic inversion (loud passages become quieter than quiet passages due to over-limiting). Symptoms:
- Boring, lifeless, fatiguing listen
- Lost transients (kicks and snares "wimpy loud" not "punchy loud")
- Stereo depth collapsed to mono-like wall
- Listener fatigue within 30 seconds

**If the mix needs hypercompression to be competitive → the mix is wrong. Redirect to Mixing.**

## Saturation Pre-Limiter (Owsinski + Katz)

| Type | Harmonics | Sound character | Source |
|---|---|---|---|
| Even-order | 2nd, 4th, 6th | Warm, pleasant, euphonic | Tube (triode) |
| Odd-order | 3rd, 5th, 7th | Bold, aggressive, forward | Solid-state, transistor |
| Tape | Even + odd + HF rolloff | Warm, dense, slightly dark | Analog tape |

**Why even = warm:** even harmonics = octave/5th relationships → musical; ear perceives as "fuller" not "distorted."
**Why odd can be harsh:** 5th + 7th → dissonance at high amounts; low amounts perceived as "presence" and "character."

### Saturation Type Selection by Genre (Owsinski)

| Genre | First-choice saturation | Why |
|---|---|---|
| Classical / acoustic / jazz | None, or very subtle tube (≤ 0.2 dB) | Preserve transient + harmonic accuracy |
| Singer-songwriter / folk | Light tube (even-order) | Warmth without forwardness |
| Pop (modern) | Tape | Density + HF rolloff = "polished" |
| Rock / indie | Tape + light transistor | Tape glue + transistor presence |
| Hip-hop / R&B | Tape (heavy on 808s/bass) | Even-order density on low end |
| EDM / electronic | Transistor / odd-order | Forward edge cuts club PAs |
| Metal | Transistor / hard clip pre-limiter | Aggression without limiter brick-wall artifacts |

**Soft clipping:** gradual rounding of peaks (analog-like) vs. hard digital clip; use pre-limiter on harsh digital masters to smooth transients without inharmonic aliasing.

**Practical use:**
- Pre-limiter saturation: warms AND softens peaks → limiter needs less GR
- Tape on full mix: HF rolloff + density; keep < 0.5dB visible saturation on peak meter
- Analog simulation: Cranesong HEDD-192 (hardware: Triode/Pentode/Tape knobs); plugins: Slate VTM, Softube Tape, Waves J37

**Inharmonic digital distortion (Katz):** truncation + aliasing → distortion products beat against sample rate → very harsh; no musical relationship to signal. Always dither; always use 64-bit float internally; never use single-precision (32-bit int) processing chain.
