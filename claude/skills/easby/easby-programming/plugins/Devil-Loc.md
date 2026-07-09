# Devil-Loc — Soundtoys (Compressor / Crusher)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Extreme automatic-level compressor + clipper ("destruction" comp). Emulation of the **Shure Level-Loc** (M62/M67 broadcast AGC) |
| Tech | C++ VST3, shared "Soundtoys" framework (one static framework across all 23 plugins → one plugin per process). AAX = PACE; VST3 = pedalboard-hostable, clean |
| Binary | `/Library/Audio/Plug-Ins/VST3/Soundtoys/Devil-Loc.vst3`. Not measured statically (CLEAN-only mandate) |
| Provenance | **100% CLEAN** — black-box measurement (pedalboard) + public DSP literature + own description. No disasm |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (harness `Soundtoys/Tools/st_sysid.py`, custom probes in scratchpad) |

## Signal chain
```
x → [AGC compressor: huge low-level makeup + hard output ceiling, atk≈3ms / rel≈460ms]
  → [crunch waveshaper: symmetric soft→hard clip, odd-harmonic]
  → out  (fixed output band, ~ -8…-15 dBFS peak ceiling)
```
Only 3 params total: `bypass`, `crush`, `crunch`. No mix/output/tone (those are Deluxe-only).

## Per-stage formula (all CLEAN)
- **AGC / automatic-level compressor** (CLEAN): a fixed-output-target leveler, not a threshold/ratio comp.
  `crush` sets the **low-level makeup gain** (= how hard it drives into its ceiling); output asymptotes to a
  roughly fixed band regardless of input.
  - Measured makeup at very low input (in = −60 dB, crunch = 0): crush 0 → **+2.5 dB**, 2.5 → **+11.6 dB**,
    5 → **+20.2 dB**, 7.5 → **+28 dB**, 10 → **+36 dB**. (≈ linear in dB: ~+3.35 dB makeup per crush unit.)
  - Above a level-dependent knee the gain folds back so OUTPUT stays bounded. At crush = 10 the static gain
    crosses unity near in ≈ −24 dB and the **output peak ceiling sits ≈ −8…−12 dBFS** (rms ≈ −11…−15 dB) for
    hot inputs (see curve below). At crush = 0 the ceiling is ≈ −17 dBFS pk.
  - **Internal hard limiter / clamp**: at crush = 10 there is an abrupt gain drop around in ≈ −25→−24 dB
    (gain jumps from +5 dB to ≈ −10 dB over 1 dB of input) — the makeup-vs-ceiling crossover where the
    internal clamp seizes control. This program-dependent "seize" is the signature Level-Loc pumping artifact.
  - Time constants (level step −50→−6→−50 dB, crush 10): **attack ≈ 2.8 ms**, **release ≈ 460 ms**, gain
    reduction up to ~40 dB. Fast-grab / slow-recover = broadcast AGC behavior.
  - The AGC path itself contributes ~3 % THD (H2-dominant, ≈ −29 dB) from gain modulation, independent of crunch.
- **`crunch` waveshaper** (CLEAN): a **symmetric clipper** after the AGC. Inert for crunch ≲ 2, then engages.
  THD@1k (crush 0, in −12 dB): crunch 3 → 6 %, 4 → 14 %, 5 → 23 %, 6 → 30 %, 8 → 38 %, 10 → **40.7 %**.
  Harmonic structure is **odd-dominant** (H3 ≫ H2; H5, H7 climb) → soft-knee saturation hardening toward a
  square wave. At crunch 10: H3 = −9.6, H5 = −14.3, H7 = −17.5 dB rel fundamental (clear odd ladder).

## Why / design rationale (music ↔ code)
- **Fixed-output AGC (not threshold/ratio)** → musical effect: anything you feed it comes out *loud and even*,
  drums/room mics slammed flat. Purpose: faithfully recreates the **Shure Level-Loc**, a 1960s broadcast level
  control whose abuse on drum room mics (famous on countless records) is the whole point. A normal comp can't
  reproduce the "everything pinned to one loudness" behavior; an AGC with massive makeup + a hard ceiling can.
- **Up to +36 dB makeup + abrupt clamp crossover** → the pumping/breathing "seize" as the makeup fights the
  ceiling = the Level-Loc's signature self-overload. The discontinuity is a *feature*, not a bug — it's the
  aggressive grab that makes it a "destruction box," so the model keeps it.
- **crunch = symmetric odd-harmonic clipper** → adds buzzy, square-ish edge (3rd/5th) on top of the squashed
  signal = aggressive "broken speaker"/distortion-amp grit. Symmetric (odd) rather than asymmetric (even) →
  hard, raspy character vs warm tube — matches the destructive intent.
- **atk ≈ 3 ms / rel ≈ 460 ms** → fast enough to clamp transients, slow enough to pump and pull up room tails
  → that breathing "suck" between hits.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| crush | — | 0–10 (step 0.1, def 1.0) | AGC drive = low-level makeup ≈ +3.35 dB/unit (2.5 dB→+36 dB span); harder squash + higher ceiling. Linear taper |
| crunch | — | 0–10 (step 0.1, def 1.0) | post-AGC symmetric clipper. Inert ≤2; THD 6 %→41 % over 3→10. Odd-harmonic. Linear taper |

Reported PDC latency = 48 samples (impulse measures 0 after pedalboard PDC auto-comp; lookahead is small/internal).

## CLEAN measurements
**Static gain curve — gain_db = out_rms − in (crunch = 0), per crush setting:**
| in dB | crush 0 | 2.5 | 5 | 7.5 | 10 |
|---|---|---|---|---|---|
| −60 | +2.5 | +11.6 | +20.3 | +28.0 | +34.5 |
| −48 | +2.5 | +11.6 | +19.9 | +24.2 | +25.9 |
| −36 | +2.6 | +10.3 | +13.2 | +14.3 | +15.0 |
| −24 | −0.3 | +1.9 | +2.7 | +3.3 | (clamp) |
| −12 | −9.7 | −9.0 | −8.5 | (clamp) | −12.2 |
| 0 | −20.7 | −20.2 | −27.6* | −21.0 | −14.8 |

**Output ceiling (crush 10, crunch 0), in → out:**
| in dB | −30 | −24 | −12 | −6 | 0 | +6 |
|---|---|---|---|---|---|---|
| out pk dBFS | −17.3 | −29.3† | −19.2 | −15.7 | −11.7 | −8.6 |
| out rms dBFS | −20.6 | −34.6† | −24.2 | −19.4 | −14.8 | −11.0 |

†abrupt clamp crossover at in ≈ −25→−24 dB (makeup-vs-ceiling seize). *crush-5 shows a similar mid-range dip.

**crunch THD ladder** (crush 0, in −12 dB, 1 kHz): 0→3.5 %, 3→6 %, 4→14 %, 5→23 %, 6→30 %, 8→38 %, 10→**40.7 %** (H3 −9.6 / H5 −14.3 / H7 −17.5 dB at crunch 10 — odd-harmonic).

**Time constants** (crush 10): attack ≈ **2.8 ms**, release ≈ **460 ms**.

## To implement (CLEAN-only)
- **AGC leveler** = feedforward gain computer driving toward a fixed output target: `makeup_dB(crush) ≈ 2.5 + 3.35·crush`
  applied, then a hard output limiter at a fixed ceiling (≈ −12 dBFS pk at high crush; scale ceiling slightly with
  crush). Detector: fast attack (~3 ms one-pole), slow release (~460 ms one-pole). Let makeup overshoot the ceiling
  so the limiter visibly seizes → reproduce the pumping discontinuity (don't smooth it out).
- **crunch** = symmetric odd-harmonic waveshaper after the AGC, engaging above ~20 % of range; map crunch→drive so
  THD goes 0→~40 %. Use a symmetric soft-clip hardening to near-clip (e.g. `tanh(k·x)` → `clip` blend, k∝crunch),
  or a polynomial that grows H3/H5/H7. Then trim back toward the ceiling.
- Building blocks: one-pole envelope follower, fixed-target gain computer, symmetric soft-clipper — all in
  easby-programming building-blocks. Reuse for the ES-X aggressive-front-end if a "smash" stage is wanted.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (none used here).
