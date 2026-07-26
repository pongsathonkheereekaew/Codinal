# Radiator — Soundtoys (Saturation / tube mixer emulation)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Saturation — Altec 1567A tube mixer emulation: input + output tube gain stages, 2-band tone, modeled hum/noise |
| Tech | C++ VST3, shared Soundtoys framework (load one plugin per process). AAX = PACE; VST3 pedalboard-hostable. |
| Binary | universal x86_64 + arm64 MH_BUNDLE; effectively stripped; `__Pace_Eden.bundle` present (REF, wraps AAX). |
| Provenance | **CLEAN** — all numbers = black-box measurement of the licensed VST3. (Binary line = REF.) |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (`Tools/st_sysid.py`, `Tools/st_custom.py`, `out/Radiator_{params,probe,custom}.json`) |

## Signal chain
```
x → [MIC/LINE input sensitivity (small level offset)]
  → INPUT tube gain stage (input_db −15..+15) → asymmetric tube shaper (memoryless, H2-led)
  → BASS low shelf (±10 dB, corner ~300–500 Hz)
  → TREBLE high shelf (±10 dB, corner ~2–3 kHz)
  → OUTPUT tube gain stage (output_db −15..+15) → same nonlinearity (also saturates)
  → [NOISE: modeled mains hum 50/100/150 Hz + hiss, summed in]
  → MIX dry/wet
y
```
Reported latency 65 samples.

## Per-stage formula  (all CLEAN — black-box measured)
- **Input tube stage (CLEAN):** memoryless asymmetric shaper. THD vs frequency is flat (28.5–34 % across 50–5000 Hz at input +12) ⇒ NOT a stateful/reactive circuit. Drive law (LINE): 0.18 % @−15 → 0.83 % @−3 → 3.7 % @+6 → 15 % @+9 → 28.6 % @+12 → 38.7 % @+15 — a long clean region then a sharp tube-clip onset above ~+6.
- **Asymmetry / harmonic character (CLEAN):** **H2-dominant (even)** through the musical range — single-ended-triode signature. even/odd ratio +18 dB @−15, +7.7 @0, still +6 @+3; H2 ≈ −40 dB @0 dB in, rising to −9.6 dB @+15. As it hard-clips at the very top, odd harmonics catch up. Growing DC offset is **not** present here (input stage stays ~0 DC; cf. LittleRadiator bias) — asymmetry is mild and AC.
- **Mic/Line (CLEAN):** MIC vs LINE harmonic curves are near-identical (MIC output ~0.3 dB lower at matched input); MIC is a small input-sensitivity/level offset, not a separate circuit topology.
- **Bass shelf (CLEAN):** low shelf, corner ≈300–500 Hz, ±~10 dB. −10 → −9 dB shelf flat below ~150 Hz, returns to 0 by ~1 kHz; +10 → +11 dB @20 Hz tapering to 0 by ~1 kHz.
- **Treble shelf (CLEAN):** high shelf, corner ≈2–3 kHz, ±~10 dB. +10 → +8 dB @16 kHz; −10 → −9…−11 dB @8–20 kHz.
- **Baseline coloration (CLEAN):** inherent "box" tone with all flat = slight LF lift (+1–2 dB @20–40 Hz) and HF lift (+2–3 dB @14–20 kHz); midband within ±0.5 dB.
- **Output tube stage (CLEAN):** NOT a clean trim — it drives a second saturation. output_db −15 → THD 0.45 %; 0 → 1.1 %; +15 → THD 39 %. So input and output knobs *both* add distortion (gain-staging: push input for one flavor of clip, output for another / for level-into-the-output-tube).
- **Noise / hum (CLEAN):** silence-in produces a modeled mains-hum ladder — 50/100/150 Hz at −11/−12/−10 dB rel its own peak (plus 60/120/180 components and hiss). Total noise floor: peak −68.6 dBFS, RMS −78.8 dBFS. Toggled by `noise`.

## Why / design rationale (music ↔ code)
- **Two gain stages (input + output) both nonlinear** → models a real tube mixer channel where you can overdrive the *first* tube (grit on the way in) or slam the *output* tube (fatter, level-dependent compression-y clip). Gives two textures of the same circuit and a built-in gain-staging game — the core "mixer mojo" workflow.
- **H2-dominant asymmetry** → 2nd-harmonic = octave-up "warmth/richness," the flattering tube color engineers reach for to thicken DI bass, vocals, drum bus. Single-ended (not push-pull) topology is *why* it's even-led, and Soundtoys kept that.
- **Long clean region then sharp onset** → lets the unit sit transparent at unity and bloom into saturation only when pushed — musically you "lean into" it, matching how a real preamp behaves and giving wide usable gain range before it gets dirty.
- **2-band shelves (not parametric)** → broad "tone" sculpting in the spirit of a vintage console's bass/treble, voiced around the saturation so you tilt warmth/air rather than surgically EQ.
- **Modeled hum/noise as a defeatable feature** → part of the analog vibe (low-level mains hum + hiss = "it's a real box"); defeatable because in a modern mix you often don't want it. The deliberate 50/100/150 Hz ladder is the recognizable signature of mains-coupled tube gear.
- **Memoryless shaper** → like Decapitator, predictable + cheap; the frequency shaping is explicit (shelves + baseline curve) rather than emergent from reactive components.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| bass_db | cont | −10…+10 | low shelf, corner ~300–500 Hz |
| treble_db | cont | −10…+10 | high shelf, corner ~2–3 kHz |
| input_db | cont | −15…+15 (0.03) | input tube drive (saturates) |
| output_db | cont | −15…+15 (0.03) | output tube drive (also saturates, NOT a clean trim) |
| mix | cont | 0–100 % | dry/wet |
| micline | enum | LINE(def), MIC | input sensitivity offset (~0.3 dB), same circuit. Latches one block late — warmup-render. |
| noise | bool | On(def)/Off | modeled mains hum (50/100/150 Hz) + hiss |

## CLEAN measurements
**Input drive law — THD% + harmonics (input −12 dBFS @1 kHz, LINE, output 0, tone flat, noise off):**
| input_db | THD% | H2 | H3 | even/odd dB | out_pk |
|---|---|---|---|---|---|
| −15 | 0.18 | −55 | −74 | +18.6 | −26.7 |
| −9 | 0.37 | −49 | −62 | +13.5 | −20.7 |
| −3 | 0.83 | −42 | −51 | +8.7 | −14.8 |
| 0 | 1.08 | −40 | −48 | +7.7 | −11.8 |
| +3 | 1.65 | −37 | −43 | +6.0 | −8.9 |
| +6 | 3.74 | −39 | −30 | −7.1 | −6.7 |
| +9 | 15.2 | −20 | −19 | −1.2 | −5.0 |
| +12 | 28.6 | −13 | −17 | +4.4 | −4.0 |
| +15 | 38.7 | −10 | −19 | +9.9 | −3.4 |

(MIC column near-identical, ~0.3 dB lower out — see `out/Radiator_custom.json` → `drive_MIC`.)

**Memoryless confirmation (input +12):** THD 34→29→29→29→29→29→28 % at 50/100/200/500/1k/2k/5k Hz; harmonic ratios constant ⇒ memoryless.

**Output stage (input 0):** output_db −15/0/+15 → THD 0.45/1.08/39.1 % ⇒ output tube also saturates.

**Tone shelves (low-amp, ref 1 kHz):** bass −10/+10 → −9 dB / +11 dB @20 Hz, flat by ~1 kHz (corner ~300–500 Hz). treble −10/+10 → −11 dB / +8 dB @16–20 kHz (corner ~2–3 kHz). Baseline (all flat): +1–2 dB @LF, +2–3 dB @HF, ±0.5 dB mid.

**Noise/hum:** peak −68.6 dBFS, RMS −78.8 dBFS; hum lines (rel own peak) 50:−11, 100:−12, 150:−10, 60:−13, 120:−13 dB. **Latency:** 65 samples.

## To implement (CLEAN building blocks for ES-L)
- **Two cascaded asymmetric memoryless tube stages** (input + output), each H2-led — e.g. `f(x)=tanh(g·x + b·(g·x)²)`-style or a soft asymmetric clip with even-harmonic emphasis; DC-block between/after. Calibrate the `g` (drive) map to the long-clean-then-sharp THD curve above (≈ unity to +6, then steep). Output stage uses the same shaper but its own drive.
- **2 shelves** voiced around the saturator: low shelf @~400 Hz (±10 dB), high shelf @~2.5 kHz (±10 dB).
- **Fixed baseline tone curve**: gentle LF + HF lift (the "box" color) applied always-on.
- **Optional modeled-hum generator**: sum of 50/100/150 Hz (+60/120/180) sinusoids at ≈−68 dBFS + low-level pink hiss, defeatable — reusable for any "vintage gear" vibe in ES-X/ES-L.
- **Gain-staging design pattern**: expose input *and* output as independent drives into nonlinearities (not a trim) so the user dials grit vs level-into-output-clip separately. All CLEAN — reproduce from the curves above.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (only the binary arch/strip/PACE one-liner here).
