# LittleRadiator — Soundtoys (Saturation / one-knob tube mixer)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Saturation — reduced one-knob **Radiator** (Altec 1567A tube). Single `heat` drive + DC-`bias` asymmetry toggle. |
| Tech | C++ VST3, shared Soundtoys framework (same engine as Radiator; load one plugin per process). AAX = PACE; VST3 pedalboard-hostable. |
| Binary | universal x86_64 + arm64 MH_BUNDLE; effectively stripped; `__Pace_Eden.bundle` present (REF, wraps AAX). |
| Provenance | **CLEAN** — all numbers = black-box measurement of the licensed VST3. (Binary line = REF.) |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (`Tools/st_sysid.py`, `Tools/st_custom.py`, `out/LittleRadiator_{params,probe,custom}.json`) |

## Relationship to Radiator (sibling decode)
LittleRadiator is **Radiator's tube saturation collapsed to one knob**, same memoryless engine family:
- `heat_db` = single drive that ganged Radiator's input+output stages into one (−15…+15, same 0.03 step, same unit as Radiator input/output).
- **Dropped** from Radiator: separate input/output gains, bass/treble shelves, MIC/LINE.
- **Added**: `bias` toggle — an explicit DC-bias-before-shaper switch that turns the harmonic character from odd-led (default) to strongly even-led (H2). This *exposes as a button* the single-ended-triode asymmetry that Radiator's input stage produced inherently.
- THD-vs-freq flat (memoryless), and the per-harmonic curves track Radiator's family.

## Signal chain
```
x → [BIAS: add DC offset pre-shaper (bool)]
  → HEAT tube gain stage (heat_db −15..+15) → memoryless shaper → DC-block
  → [NOISE: modeled mains hum 50/120/180 Hz + hiss]
  → MIX dry/wet
y
```
No tone controls, no separate I/O trims. Frequency response is flat and **independent of heat** (drive does not retune EQ). Reported latency 48 samples.

## Per-stage formula  (all CLEAN — black-box measured)
- **Heat shaper (CLEAN):** memoryless — THD vs frequency flat (≈25 % across 50–5000 Hz at heat +12 ⇒ no circuit memory). Drive law (bias OFF): 0.52 % @−15 → 1.4 % @−3 → 2.6 % @0 → 11.6 % @+6 → 25.2 % @+12 → 29.8 % @+15.
- **Default character (bias OFF) (CLEAN):** **odd/H3-led** through most of the range (even/odd −10…−18 dB; H3 −12 to −25, H2 weaker). DC offset grows with heat (−0.008 @0 → −0.017 @+15) ⇒ the shaper itself is mildly asymmetric/odd, output DC-blocked. (Note: this is *more odd* than Radiator's input stage, which is even-led — LittleRadiator's neutral voicing leans into the transformer/odd side until you flip bias.)
- **Bias ON (CLEAN):** injects a DC offset *before* the shaper → strongly **even/H2-dominant, asymmetric** waveshaping. even/odd jumps to +27…+39 dB at low heat; H2 = −24 @−15 rising to −15 @+15. Adds distortion even at minimum heat (THD 6.3 % @−15 with bias vs 0.5 % without). Output DC stays ~0 (post-shaper DC-block) — the asymmetry is in the AC harmonic spectrum, classic "bias the tube for 2nd-harmonic warmth."
- **Frequency response (CLEAN):** flat, within ±1 dB 20 Hz–10 kHz, **identical at heat −15/0/+15** → heat changes only the nonlinearity, not tone; no autogain-EQ. (No bass/treble shelves exist.)
- **Noise / hum (CLEAN):** modeled mains hum + hiss; lines 50:−13, 120:−21, 180:−16 dB rel peak; floor peak −66.4 dBFS, RMS −75.7 dBFS. Toggled by `noise`.

## Why / design rationale (music ↔ code)
- **One knob = "the right amount of Radiator"** → for users who want tube glue without gain-staging two stages and EQ; `heat` ganged input+output so a single move adds the whole channel's saturation. The "Little" UX is *commit to the vibe, set the amount.*
- **Bias as a 2nd-harmonic toggle** → makes the choice between odd (transformer-ish, harder/grittier, default) and even (tube warmth, octave-up, flattering) a single A/B button — the most consequential tonal decision in tube saturation, surfaced for non-experts. Implementing it as a *pre-shaper DC offset* is the textbook way to convert a symmetric curve into an even-harmonic generator (asymmetry → even harmonics), then DC-block so no thump leaks out.
- **No tone controls** → deliberately minimal; you EQ elsewhere. Keeps the box to its one job (color), the opposite end of Decapitator's "full control surface."
- **Heat doesn't touch EQ** → predictable: turning it up never changes your tonal balance, only harmonic density — easy to ride to taste on a bus.
- **Same modeled hum/hiss** → keeps the analog identity consistent with big Radiator.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| heat_db | cont | −15…+15 (0.03) | single tube drive (= Radiator input+output ganged) |
| mix | cont | 0–100 % | dry/wet |
| bias | bool | Off(def)/On | pre-shaper DC bias → flips odd-led → even/H2-led (asymmetry) |
| noise | bool | On(def)/Off | modeled mains hum + hiss |

## CLEAN measurements
**Heat drive law — THD% + harmonics (input −12 dBFS @1 kHz, noise off):**
| heat_db | bias OFF THD | H2 | H3 | even/odd | DC | bias ON THD | H2 | H3 | even/odd |
|---|---|---|---|---|---|---|---|---|---|
| −15 | 0.52 | −46 | −72 | −? (clean) | −0.0005 | 6.26 | −24 | −58 | +33.8 |
| −3 | 1.40 | −38 | −45 | +7.1 | −0.004 | 17.3 | −15 | −42 | +27.1 |
| 0 | 2.55 | −37 | −34 | −3.3 | −0.008 | 21.1 | −14 | −41 | +26.8 |
| +6 | 11.6 | −38 | −19 | −17.8 | −0.015 | 25.7 | −12 | −29 | +16.7 |
| +12 | 25.2 | −23 | −13 | −10.6 | −0.017 | 28.7 | −13 | −18 | +6.5 |
| +15 | 29.8 | −22 | −12 | −10.2 | −0.016 | 31.0 | −14 | −15 | +3.0 |

(bias OFF = odd/H3-led with growing −DC; bias ON = even/H2-led, asymmetric, THD even at min heat. Full tables: `out/LittleRadiator_custom.json`.)

**Memoryless confirmation (heat +12, bias off):** THD 26→25→25→25→25→25→24 % at 50/100/200/500/1k/2k/5k Hz; ratios constant.

**Frequency response:** flat ±1 dB, identical at heat −15/0/+15 (heat does not retune). **Noise/hum:** peak −66.4 dBFS, RMS −75.7 dBFS; 50/120/180 Hz lines −13/−21/−16 dB. **Latency:** 48 samples.

## To implement (CLEAN building blocks for ES-L)
- **One-knob saturation macro**: a single `heat` mapping to a memoryless asymmetric shaper (reuse Radiator's tube curve); drive map per the THD table (≈unity to −3, blooms to ~30 % by +15).
- **Bias = pre-shaper DC offset + post-shaper DC-block**: the canonical even-vs-odd toggle — add `bias` before `f(x)`, subtract running-mean / 1-pole HPF after. CLEAN, trivially reproducible; gives a "warm (even) / gritty (odd)" switch for any ES-L saturation stage.
- **Heat must NOT alter EQ** (decouple drive from tone) — design pattern for predictable ride.
- Reuse Radiator's modeled-hum generator (defeatable). All CLEAN — reproduce from curves above.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (only the binary arch/strip/PACE one-liner here).
