# Devil-Loc Deluxe — Soundtoys (Compressor / Crusher)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Extended **Shure Level-Loc** AGC compressor + clipper, with parallel mix, tone (dark) and release options |
| Tech | C++ VST3, shared "Soundtoys" framework (one plugin per process). AAX = PACE; VST3 = pedalboard-hostable, clean |
| Binary | `/Library/Audio/Plug-Ins/VST3/Soundtoys/Devil-Loc_Deluxe.vst3`. Not measured statically (CLEAN-only) |
| Provenance | **100% CLEAN** — black-box measurement (pedalboard) + public DSP literature + own description |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (harness `Soundtoys/Tools/st_sysid.py`, custom probes in scratchpad) |

## Signal chain
```
x ──┬─────────────────────────────────────────────── dry ──┐
    └─ [AGC comp + ceiling] → [crunch clipper] → [darkness LP] → wet ─┤── mix ──→ out
                              (release toggle: fast/slow)
```
**Same core engine as Devil-Loc** (crush/crunch byte-identical behavior, see Devil-Loc.md) plus three controls:
`mix` (parallel dry/wet), `darkness_hz` (wet-path LP tone), `release` (fast/slow toggle).

## Per-stage formula (all CLEAN)
- **AGC comp + crunch clipper** (CLEAN): **identical to base Devil-Loc** — same makeup law
  (≈ +3.35 dB/crush unit, +36 dB at crush 10 / low input), same fixed-output ceiling + abrupt clamp crossover
  at in ≈ −24/−25 dB, same atk ≈ 2.8 ms, same odd-harmonic crunch ladder (THD up to ~41 %). Confirmed by
  identical iocurve and THD measurements on both plugins. → see Devil-Loc.md for the full stage tables.
- **`mix` — parallel blend** (CLEAN): wet/dry crossfade, **100 % = full processed, 0 % = dry**.
  - At low input (in −50 dB, crush 10): mix 0 → gain −3 dB (≈ dry), 25 → +19.9, 50 → +24.8, 75 → +27, 100 → +27.6 dB.
    (Blend is amplitude-summing; because the wet path has huge makeup, even 25 % wet dominates the quiet dry.)
  - At hot input (in −6 dB): mix 0 → out −6 (dry), 50 → −6.5, 75 → −9.3, 100 → −15.7 dB (full squash).
  - Use: **parallel compression** — keep transients from the dry path, glue/loudness from the slammed wet path.
- **`darkness_hz` — low-pass tone on the WET path** (CLEAN): a **~12 dB/oct (2nd-order) low-pass**. The labeled
  value is a guide; the measured −3 dB corner sits ~1.3–1.6× above the label and tracks it monotonically:
  | darkness label | measured −3 dB | rolloff |
  |---|---|---|
  | 20 kHz | none (open) | — |
  | 12 kHz | ~16 kHz | gentle |
  | 8 kHz | ~12 kHz | |
  | 5 kHz | ~8 kHz | |
  | 3 kHz | ~5 kHz | −15.6 dB from 3→8 k, −13.6 dB 8→16 k ≈ **12–13 dB/oct** |
  | 1 kHz | ~2 kHz | steep |
  | 500 Hz | ~2 kHz | (floors) |
  (A small +1.5 dB bump at 1–3 kHz is wet/crunch coloration, not the filter.)
- **`release` — fast/slow toggle (bool)** (CLEAN): switches the AGC release time.
  - Off → release ≈ **460 ms** (same as base Devil-Loc). On → release ≈ **316 ms** (faster).
  - Attack unchanged (~2.8 ms) and gain-reduction depth unchanged (~40 dB). So the button = "release faster",
    tightening pump recovery for busier material.

## Why / design rationale (music ↔ code)
- **Same destructive AGC core, made usable** → the base Devil-Loc is a one-trick smasher; Deluxe wraps it with the
  three controls a mix engineer actually needs to *place* that smash in a mix: blend it in (mix), tame its harsh
  top (darkness), and fit its pump to the tempo (release). Same crazy engine, mix-ready.
- **`mix` parallel blend** → musical: New-York/parallel compression — dry keeps punch & transient detail, wet adds
  density and the room-mic "wall." Cheapest way to get loudness without killing dynamics. Implemented as a simple
  dry/wet crossfade because the effect *is* additive parallel processing.
- **`darkness` LP on the wet path only** → the crunch clipper makes harsh odd harmonics up high (H5/H7 fizz); a
  2nd-order LP on just the wet path rolls that fizz off without dulling the dry transients (which stay full-band).
  12 dB/oct = gentle, musical "darkening" rather than a brickwall — keeps body, kills only the buzz.
- **`release` fast/slow** → two presets instead of a continuous knob keeps the UI simple and on-brand (Level-Loc
  had no release control); fast for dense/fast material (less pumping smear), slow for sustained room glue.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| crush | — | 0–10 (def 1.0) | AGC drive/makeup ≈ +3.35 dB/unit (identical to base Devil-Loc) |
| crunch | — | 0–10 (def 1.0) | post-AGC symmetric clipper, odd-harmonic; THD 0→41 % over 0→10 |
| mix | % | 0–100 (def 100) | parallel dry/wet; 100 = full wet, 0 = dry. Linear |
| darkness_hz | Hz | 500–20000 (def 20000) | 2nd-order (~12 dB/oct) LP on wet path; label ≈ 0.65× true corner. Log taper |
| release | bool | Off/On (def Off) | release time: Off ≈ 460 ms, On ≈ 316 ms (faster). Attack fixed ≈ 2.8 ms |

Reported PDC latency = 63 samples (impulse 0 after pedalboard auto-comp).

## CLEAN measurements
- **Core curves / THD / ceiling**: identical to Devil-Loc (see Devil-Loc.md tables).
- **mix @ in −50 dB (crush 10)**: gain 0 %→−3, 25 %→+19.9, 50 %→+24.8, 75 %→+27.0, 100 %→+27.6 dB.
- **mix @ in −6 dB (crush 10)**: out 0 %→−6, 50 %→−6.5, 75 %→−9.3, 100 %→−15.7 dBFS.
- **darkness LP**: see corner table above; slope ≈ 12 dB/oct.
- **release**: Off ≈ 460 ms, On ≈ 316 ms (attack ≈ 2.8 ms both).

## To implement (CLEAN-only)
- Reuse the **Devil-Loc AGC + crunch core** (Devil-Loc.md "To implement"), then wrap:
  1. **parallel mix**: `out = (1−m)·dry + m·wet`, m = mix/100 (sum the slammed wet over the dry).
  2. **darkness**: one 2nd-order (Butterworth/biquad) low-pass on the wet branch, cutoff ≈ darkness_label×1.4
     (or expose true corner directly). 12 dB/oct.
  3. **release toggle**: two release coefficients for the AGC envelope follower (≈ 460 ms / ≈ 316 ms).
- Building blocks: dry/wet crossfade, 2nd-order LP biquad, one-pole envelope with switchable release — all in
  easby-programming building-blocks. The parallel-mix + tone-LP wrapper is a reusable pattern for any
  "destructive front-end made mix-ready" stage in ES-X.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (none used here).
