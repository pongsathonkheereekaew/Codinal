# Little PrimalTap — Soundtoys (delay / reduced Lexicon PrimeTime lo-fi)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Delay — single-tap lo-fi digital (reduced PrimalTap = Lexicon Prime Time): sample-rate-reduced delay, input drive, feedback/Surge |
| Tech | C++ VST3, shared "Soundtoys" static framework (one plugin per process). AAX = PACE; VST3 = pedalboard-hostable |
| Binary | universal (x86_64 + arm64) MH_BUNDLE, 36.4 MB; not measured statically (CLEAN-only task) |
| Provenance | **CLEAN** — black-box measurement (pedalboard). Subset of PrimalTap; carries the **fully-measured** feedback & lo-fi engine (its big-sibling's recirculation was inert in this host, so Little is the reference for the loop). |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (`Tools/st_sysid.py`, `Tools/delay_probe.py`, `out/LittlePrimalTap_*.json`) |

## Signal chain
```
x → inputgain (0..32 dB, drives lo-fi clipper)
  → delay line [time × multiply(1/2/4/8) ⇒ delay-line SAMPLE-RATE reduction] × adjust(fine)
  → feedback (0..125 %; ≥~100 % = Surge self-oscillation)
  → mix (dry/wet) → y
```
One delay tap, no VCO/freeze/algorithm/pan controls — the stripped PrimeTime: drive, time (×multiply), feedback, mix.

## Per-stage formula (tag each CLEAN / REF)
- **Delay time → actual** (CLEAN): `time_msec` ∈ [0,511] is **linear / true-ms** (no taper, unlike full PrimalTap's long range): 16→15.1, 50→49.1, 113→112.1, 128→127.1, 256→255.1, 383→382.1, 511→510.1 — ratio ≈ 1.00 (constant ~−1 ms PDC offset). PDC latency = **99 samples** (`reported_latency_samples`).
- **`multiply` = sample-rate reduction + delay multiplier (core lo-fi)** (CLEAN): 1×/2×/4×/8× multiplies the delay time cleanly (100 ms → 105.9 / 208.3 / 407.1 / 801.8 ms = ×1/2/4/8) **and** crushes bandwidth by running the converter at 1/N rate: a 7 kHz tone → 1× clean (alias −74 dB @3 k), 2× → image at 3 kHz −13 dB, 4× → **folds to 1 kHz at +54 dB** (alias louder than original, output level collapses), 8× → +57 dB with noise floor up to ~−99 dB. ⇒ longer = grungier (authentic Prime Time). The 511 ms / 1× base limit + multiply is how it reaches ~4 s of (very lo-fi) delay.
- **Input drive / lo-fi clip** (CLEAN): `inputgain_db` 0…32 = **symmetric (odd-harmonic) clipper** into the converter. THD of the wet (1 k): 0 dB→0.14 %, 8→0.66 %, 16→**14.6 %**, 24→21.4 %, 32→22.5 %. Sharp knee at ~16 dB, H3 ≫ H2 (−16.8 vs −51.5 dB at 16 dB) ⇒ hard symmetric digital clip. (Identical knee & harmonic profile to PrimalTap ⇒ same engine.)
- **Feedback / Surge** (CLEAN — fully measured here): `feedback` ∈ [0,125] %. Steady-state decay per repeat and inferred loop gain g = 10^(decay/20):
  | fb % | dB/repeat | g (lin) | behaviour |
  |---|---|---|---|
  | 25 | −5.72 | 0.52 | decays |
  | 50 | −3.19 | 0.69 | decays |
  | 62.5 | −2.17 | 0.78 | decays |
  | 75 | −1.44 | 0.85 | long decay |
  | 90 | −0.31 | 0.97 | near-sustain |
  | **100** | **+0.59** | **1.07** | **Surge onset (builds)** |
  | 110 | +1.40 | 1.18 | self-oscillation |
  | 125 | +1.50 | 1.19 | runaway |
  Repeat count grew 5→9→12→19→30 over fb 25→90 %, tail energy rose monotonically. **Self-oscillation ("Surge") begins at ~100 %** — past unity the echo regenerates and grows without input. This is the reference law for the whole PrimalTap family (the full plugin's `feedback_a` was inert in pedalboard).

## Why / design rationale (music ↔ code)
- **Linear short time line (≤511 ms) × multiply for length** → the simple-but-deep Prime Time control: a fine short range for slap/double-track, multiply to jump into long grungy territory → keeps the one-knob feel while reaching seconds-long lo-fi.
- **Sample-rate-reduced delay** → same defining PrimeTime lo-fi as the full plugin: longer delays are darker/aliased because the converter slows down → the dirt is the feature.
- **Hard symmetric clip at ~16 dB drive** → instant lo-fi crunch on the way in → grit for drums/vocals without a separate distortion.
- **Surge at ~100 % feedback** → turn the simple delay into a self-oscillating drone/riser → the performance payoff that makes PrimeTime delays iconic, exposed even in the "Little" version.
- **Minimal surface (4 knobs)** → drive / time / feedback / mix is all you need for the PrimeTime sound → the fast, no-menu version of the engine.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| time_msec | ms | 0…511 | linear true-ms delay (×multiply for longer) |
| adjust | ratio | 0.5…1.0 | fine time scaler |
| multiply | × | 1/2/4/8 | **delay × N AND sample-rate ÷ N (lo-fi)** |
| inputgain_db | dB | 0…32 | drives lo-fi clipper; THD knee ~16 dB |
| feedback | % | 0…125 | regeneration; **≥~100 % = Surge self-oscillation** |
| mix | % | 0…100 | dry/wet |

## CLEAN measurements
- Delay-time map: linear true-ms (16–511 ms, ratio ≈ 1.00); PDC 99 samp.
- `multiply`: ×N delay + ÷N sample-rate (aliasing table above; 4×/8× fold 7 kHz to +54/+57 dB baseband).
- Input drive THD: 0/8/16/24/32 dB → 0.14/0.66/14.6/21.4/22.5 % (odd-harmonic, knee ~16 dB).
- **Feedback/Surge law table above** (g vs fb %; self-osc onset ~100 %) — reference for the PrimalTap family.

## To implement (CLEAN-only)
- **Variable-rate delay line** with `multiply` as real sample-rate reduction (÷N, no scaled anti-aliasing) → longer-is-grungier lo-fi; short true-ms range × N for length.
- **Front-end symmetric clipper**, knee ~16 dB drive → ~22 % THD ceiling.
- **Feedback law** per the measured table; **Surge** = feedback ≥ ~100 % self-oscillates (add an in-loop soft-limiter so it builds musically instead of digital-overflowing).
- This is the **smallest clone target** for a PrimeTime-style lo-fi delay: 4 controls, the measured feedback curve, and the multiply=sample-rate-crush trick.
- No tempo-sync exposed (pure ms) → nothing deferred here.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). Feedback/Surge law measured directly here and is the family reference. Prime Time lineage = public history. **REF** = none (no disasm performed).
