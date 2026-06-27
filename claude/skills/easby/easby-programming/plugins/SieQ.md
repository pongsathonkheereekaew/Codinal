# SieQ — Soundtoys (EQ)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Musical 3-band "vintage console" EQ + analog drive. Minimum-phase IIR (biquads) |
| Tech | C++ VST3, shared "Soundtoys" framework (one plugin per process). AAX = PACE; VST3 = pedalboard-hostable, clean |
| Binary | `/Library/Audio/Plug-Ins/VST3/Soundtoys/SieQ.vst3`. Not measured statically (CLEAN-only) |
| Provenance | **100% CLEAN** — black-box measurement (pedalboard, impulse/multitone → FFT mag+phase) + public DSP |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (harness `Soundtoys/Tools/st_sysid.py probe_freq`, custom probes in scratchpad) |

## Signal chain
```
x → [low shelf] → [mid bell (sweepable)] → [high shelf] → [drive: input-trim + asymmetric soft-sat] → out
```
Linear-system EQ (zero latency, minimum phase) + one nonlinear stage (drive). The three EQ bands are
order-independent biquads; the frequency response IS the spec for them.

## Per-stage formula (all CLEAN)
- **Low band = low shelf** (CLEAN, biquad shelf): transition ~125–250 Hz, reaches the full set gain by ~50 Hz
  and below; flat by ~500 Hz–1 kHz. Symmetric boost/cut.
  - At +15: +13.9 dB @50, +8.1 @125, +3.9 @250, +1.4 @500, ~0 @1 k. At +7.5: +6.5 @50, +2.0 @125.
  - Below 50 Hz keeps rising slightly (+17 @20 Hz at the +15 setting) — gentle shelf, no brickwall.
- **Mid band = bell / peaking** (CLEAN, biquad peak): center swept by `mid_frequency` 700 Hz–5.6 kHz, **accurate**
  (set 700→peak 715, set 5600→peak 5610). **Q ≈ 1.2–1.4** (moderately broad, mild proportional-Q: Q ~1.17 @700 Hz
  rising to ~1.35 @3.5 kHz). Gain ±8 dB. Slightly asymmetric boost vs cut (boost a touch narrower) = console-style.
- **High band = high shelf** (CLEAN, biquad shelf): transition starts ~2–3 kHz, −3 dB knee ~8–10 kHz, plateau to
  Nyquist. Symmetric and smooth.
  - At +15: +2.3 @2 k, +4.0 @3 k, +7.1 @5 k, +10.3 @8 k, +13.1 @12 k, +15.2 @16 k, +16.8 @20 k.
  - At −15: mirror (−2.1 @2 k … −15.3 @16 k). At +7.5: +1.9 @5 k, +3.7 @8 k, +7.7 @16 k.
- **`drive` — input trim + asymmetric soft saturation** (CLEAN, two effects in one knob):
  - **Gain** (clean, low input): −15 → −17.9 dB, −10 → −12.9, −5 → −7.9, 0 → −2.9, +5 → +0.4, +10 → +3.8,
    +15 → +7.1 dB. ≈ +1 dB/unit below 0, tapering to ~+0.67 dB/unit above 0 (the saturator eats top-end gain).
    There is a built-in ~−2.9 dB offset at the center (drive 0 ≠ unity).
  - **Saturation** (nonlinear): an **asymmetric soft clipper** — slow-ramp transfer clamps to +0.56 on the
    positive half but −0.41 on the negative half (different limits → even + odd harmonics, + a DC term).
    THD@1 k rises with drive *and* input level: at hot input (−1 dB) THD 6.7 % (drive 0) → 28 % (drive +7.5)
    → 38.5 % (drive +15); harmonics H3/H5-dominant with significant H2 → asymmetric tube/tape-style saturation.
  - **No spectral tilt** — the drive spectrum is identical at −15/0/+15 (it is flat gain + a memoryless shaper,
    not a tone control).
- **Always-on analog coloration** (CLEAN): even at all controls flat, a gentle ~+2 dB LF lift below ~60 Hz and
  ~−0.4 dB at 16 kHz (vintage-console modeling); and drive 0 with a hot tone already shows ~6 % THD (the modeled
  circuit is never perfectly clean).

## Why / design rationale (music ↔ code)
- **3 fixed bands, broad Q, minimum-phase IIR** → musical "broad-stroke" tone shaping (the SiEQ models a classic
  console/Pultec-ish channel EQ). Wide Q (≈1.2) and shelves with gentle slopes = easy, flattering moves that sound
  "right" without surgical precision. Minimum-phase (zero latency, no pre-ring) = the natural, analog-like phase
  behavior engineers expect from a console EQ — linear-phase would smear transients and add latency for no benefit
  on broad musical curves.
- **High shelf transition ~2–3 kHz with a slow climb to +15 by 16 k** → "air"/presence the way a Baxandall/console
  treble control works: it opens up the top smoothly rather than spiking one band. Mirror cut darkens gently.
- **Low shelf ~125–250 Hz corner** → weight/warmth control; corner low enough to add body without muddying the
  low-mids.
- **Sweepable mid bell 700 Hz–5.6 kHz** → the one "find the problem/feature" band, covering the vocal/guitar
  presence and body range; proportional-Q (wider at low gain) = gentle when nudging, tighter when carving.
- **`drive` = input gain + asymmetric saturation in one knob** → the "console push": running a vintage channel hot
  adds harmonics and a touch of compression-by-clipping = the "expensive analog" thickness. Asymmetric (even+odd)
  → warmer, more tube/transformer-like than a symmetric clipper. Combining trim + sat in one control makes
  "drive it harder = more color" intuitive, and the built-in −2.9 dB center offset gives headroom so you can push
  into the saturation without clipping the output.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| low_gain_db | dB | −15…+15 (def 0) | low shelf, corner ~125–250 Hz, ~6 dB/oct. Symmetric |
| mid_gain_db | dB | −8…+8 (def 0) | mid bell, Q ≈ 1.2–1.4 (mild proportional-Q) |
| mid_frequency | Hz | 700–5600 (def 1.5 k) | mid bell center; accurate. Log taper |
| high_gain_db | dB | −15…+15 (def 0) | high shelf, knee ~8–10 kHz, plateau to Nyquist. Symmetric |
| drive_db | dB | −15…+15 (def 0) | input trim (~+1 dB/unit low, tapering) + asymmetric soft saturation. ~−2.9 dB offset at 0. THD up to ~38 % at +15/hot. No spectral tilt |

**Latency = 0 samples** (reported_latency = 0; IR peak at impulse position, pre-impulse energy −128 dB) →
**minimum-phase IIR (biquads)**, not linear-phase.

## CLEAN measurements
**Low shelf gain ladder (dB rel flat):**
| set | 50 Hz | 125 | 250 | 500 | 1 k |
|---|---|---|---|---|---|
| −15 | −13.9 | −8.1 | −3.9 | −1.4 | −0.4 |
| +7.5 | +6.5 | +2.0 | −0.3 | −0.7 | −0.4 |
| +15 | +13.9 | +8.1 | +3.9 | +1.4 | +0.3 |

**High shelf gain ladder (clean multitone, dB rel flat):**
| set | 2 k | 3 k | 5 k | 8 k | 12 k | 16 k | 20 k |
|---|---|---|---|---|---|---|---|
| +7.5 | +0.4 | +0.8 | +1.9 | +3.7 | +5.9 | +7.7 | +9.0 |
| +15 | +2.3 | +4.0 | +7.1 | +10.3 | +13.1 | +15.2 | +16.8 |
| −15 | −2.1 | −3.8 | −6.9 | −10.5 | −13.7 | −15.3 | −15.5 |

**Mid bell** (center tracking & Q at +8): set 700→peak 715 Hz Q 1.17 · 1000→1022 Q 1.26 · 1500→1518 Q 1.21 ·
2300→2308 Q 1.34 · 3500→3537 Q 1.39 · 5600→5610 Q 1.30. (Gain at +8 reaches ~+7.9 dB at the center.)

**Drive** — gain law (low input): −15→−17.9, 0→−2.9, +15→+7.1 dB. THD@1 k (hot, in −1 dB): 0→6.7 %, +7.5→28 %,
+15→38.5 % (asymmetric: H2 present + H3/H5 ladder). Transfer clamps +0.56 / −0.41 (asymmetric).

## To implement (CLEAN-only)
- **3 biquads** in series: RBJ low-shelf (f0 ≈ 200 Hz), peaking bell (f0 = mid_frequency, **Q ≈ 1.2–1.4**,
  optionally proportional-Q rising with center freq), high-shelf (f0 ≈ 6–8 kHz so the −3 dB knee lands ~8–10 kHz).
  Match the gain ladders above (shelf gains are the *plateau*; the listed corners give the transition).
- **drive** = input gain `+1 dB/unit` (with ~−2.9 dB offset at 0, tapering above 0) **into an asymmetric soft
  clipper** (e.g. `tanh` with a bias, or a piecewise soft-clip with positive limit > negative limit → +0.56/−0.41)
  → even+odd harmonics, THD scaling to ~38 % at +15/hot. Place drive **after** the EQ (post-EQ saturation).
- **Always-on color**: optionally a tiny static shelf (+2 dB <60 Hz, −0.4 dB @16 k) + a mild ever-present soft-sat
  for the "analog" baseline.
- All minimum-phase, zero latency. Building blocks: RBJ biquads (shelf/peak), asymmetric soft-clipper, input trim
  — all in easby-programming building-blocks. Reuse the asymmetric-sat shaper for any "console push" tone stage.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (none used here).
