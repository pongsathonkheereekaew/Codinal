# Decapitator — Soundtoys (Saturation / analog-distortion modeler)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Saturation — 5-model analog distortion (tape / transformer / tube), memoryless waveshaper + tone shaping |
| Tech | C++ VST3, shared Soundtoys framework (one static framework → load one plugin per process). AAX slice = PACE; VST3 is pedalboard-hostable. |
| Binary | universal x86_64 + arm64 MH_BUNDLE; `nm -U`=16 (effectively stripped); `__Pace_Eden.bundle` present (REF) — wraps AAX, VST3 loads clean in pedalboard. |
| Provenance | **CLEAN** — every number below = black-box measurement of the licensed VST3. (Binary arch/strip/PACE = REF, one line only.) |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (`Tools/st_sysid.py`, `Tools/st_custom.py`, `out/Decapitator_{params,probe,custom}.json`) |

## Signal chain
```
x → input drive gain (drive 0..10, ~+15 dB at 10)
  → LOWCUT HPF (1st-order, 20..1000 Hz)
  → STYLE waveshaper (A/E/N/T/P — memoryless, model-specific transfer + bandwidth)
  → [PUNISH] extra hard-clip stage (bool)
  → TONE tilt EQ (±~16 dB, pivot ~1 kHz)
  → HIGHCUT LPF (Gentle ≈6 dB/oct | Steep ≈24+ dB/oct, 1k..20k)
  → [LOWTHUMP] sub-LF shelf boost (bool, <~40 Hz)
  → AUTOGAIN inverse-drive makeup (bool) → OUTPUTTRIM (−24..0 dB)
  → MIX dry/wet (0..100 %)
y
```
Zero reported latency (0 samples) → no oversampling-FIR PDC reported by the plugin.

## Per-stage formula  (all CLEAN — black-box measured)
- **Drive (CLEAN):** input gain into the shaper. With autogain ON, output is held ~constant (drive 0→8 = only +2.2 dB out); with autogain OFF, drive 0→8 = +14.9 dB out ⇒ drive ≈ +1.5…+1.9 dB/step input gain. THD rises monotonically (see table).
- **Style shaper (CLEAN):** memoryless — THD/harmonic *ratios* are flat vs frequency (A: 33–37 % across 50–2000 Hz; P: 49–61 %), only the modeled bandwidth rolls off HF. Two families:
  - **A (Ampex 350 tape) & N (Neve 1057 transformer):** ODD/H3-dominant. At drive 7: A H3=−11.3, H2=−17.9 (even/odd −4.5 dB); N H3=−11.3, H2=−17.7 (−5.2 dB). Classic transformer/tape 3rd-harmonic. At high drive a soft odd ladder (H3/H5) dominates. **N is the cleanest at low drive** (THD 0.64 % @drive0 vs A 3.2 %).
  - **E (EMI/Chandler TG), T (triode), P (pentode):** EVEN/H2-dominant (tube). At drive 7: E H2=−7.3 (even/odd +14), T H2=−8.1 (+23), P H2=−6.9 (+12). P (pentode) is the hottest — measurable THD even at drive 0 (6.8 %). E has a low-drive "clean shelf" then snaps into distortion ~drive 4.
- **Lowcut (CLEAN):** ~1st-order HPF (≈6 dB/oct), tunable 20–1000 Hz (100 Hz setting: −9.5 dB @58 Hz, −1.5 dB @98 Hz; 300 Hz: −6.5 dB @200 Hz).
- **Highcut (CLEAN):** Gentle ≈ 6 dB/oct (2 kHz setting → −18 dB @20 kHz); Steep ≈ 24+ dB/oct (2 kHz setting → −8 dB @2.8k, −59 dB @7k). 1k–20k.
- **Tone (CLEAN):** symmetric TILT EQ, pivot ≈ 1 kHz (985 Hz reads 0 dB at every setting). tone=−12 → +9 dB @20 Hz / −10 dB @10 kHz; tone=+12 → −22 dB @20 Hz / +5 dB @16 kHz. Net ±~16 dB low-vs-high tilt.
- **Punish (CLEAN):** extra hard-clip stage. At style A drive 5: THD 16.7 %→37.7 %, injects a full odd ladder (H3 −10.3, H5 −15.5, H7 −19.5, H9 −22.9) on top of the model. "More clip, harder edge."
- **Lowthump (CLEAN):** LF shelf boost below ~40 Hz (+2…+4 dB @20–35 Hz, flat above ~50 Hz). Restores sub energy the drive/HPF thins.
- **Autogain (CLEAN):** inverse-drive makeup ≈ keeps loudness constant across drive (see Drive). ON by default.
- **DC (CLEAN):** output is DC-blocked — even for asymmetric (even-harmonic) tube styles, measured DC ≈ 0 (E shows ~−0.001 transient only). Asymmetry lives in the AC harmonic content, not a DC pedestal.

## Why / design rationale (music ↔ code)
- **Five fixed models, no "amount of model" knob** → a producer picks a *character* (tape glue vs transformer iron vs tube warmth) and drives it; the curve identity is the product, drive is the dose. Matches how engineers think ("put it through the Neve").
- **Odd-harmonic A/N vs even-harmonic E/T/P** → transformers/tape add 3rd-harmonic "thickness/grit" (compression-like, can sound harder); single-ended tubes add 2nd-harmonic "warmth/sheen" (octave-up, flattering on vocals/bass). Giving both lets one plugin cover the two canonical analog colors.
- **Memoryless shaper (not a circuit solver)** → cheap, zero-latency, totally predictable; Soundtoys traded the frequency-dependent reactance of a real transformer for a static curve + explicit tone/cut filters, which is *more* controllable for mixing (you dial the EQ yourself instead of it being baked into the iron).
- **Tone as a 1 kHz tilt (not a parametric)** → one knob trades "dark/fat" for "bright/edgy," the single most common move when re-balancing a saturated source; pivot at 1 kHz keeps vocal/snare body as the fulcrum.
- **Punish = explicit second clip stage** → lets the user go past the model's natural ceiling into aggressive square-wave territory on demand without changing the base tone.
- **Autogain + lowthump** → make drive *safe to sweep*: loudness stays put (honest A/B) and the low end the HPF+drive eats can be put back, so saturation doesn't automatically mean "thinner and louder."

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| style | enum | A, E, N, T, P | A=Ampex tape, E=EMI/Chandler TG, N=Neve 1057, T=triode, P=pentode. **Latches one block late — warmup-render.** Set FIRST. |
| drive | cont | 0.0–10.0 (0.1) | input gain into shaper; ≈+15 dB at 10 |
| punish | bool | Off/On | extra hard-clip stage |
| lowcut_hz | cont | 20–1000 | 1st-order HPF (≈6 dB/oct) |
| tone_db | cont | −12…+12 | tilt EQ, pivot ≈1 kHz |
| highcut_hz | cont | 1000–20000 | LPF, slope set by highslope |
| highslope | enum | Gentle, Steep | ≈6 dB/oct vs ≈24+ dB/oct |
| mix | cont | 0–100 % | dry/wet |
| autogain | bool | On(def)/Off | inverse-drive makeup |
| lowthump | bool | Off/On | sub-LF shelf boost (<~40 Hz) |
| outputtrim_db | cont | −24…0 | output trim |

## CLEAN measurements
**Drive law — THD% (input −12 dBFS @1 kHz, autogain on):**
| drive | A THD | A H3/H2 | N THD | N H3/H2 | E THD | E H2/H3 | T THD | T H2/H3 | P THD | P H2/H3 |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 3.2 | −66/−30 | 0.64 | −60/−44 | 2.6 | −32/−46 | 2.2 | −36/−37 | 6.8 | −23/−39 |
| 3 | 6.4 | −30/−25 | 3.9 | −36/−30 | 2.1 | −38/−42 | 4.6 | −43/−27 | 9.3 | −27/−22 |
| 5 | 16.7 | −18/−20 | 18.5 | −15/−25 | 28.1 | −13/−16 | 22.8 | −14/−20 | 29.6 | −12/−17 |
| 7 | 34.4 | −11/−18 | 33.1 | −11/−18 | 46.7 | −7/−31 | 40.6 | −8/−38 | 49.3 | −7/−35 |
| 10 | 35.6 | −11/−27 | 41.0 | −11/−17 | 58.4 | −7/−29 | 64.6 | −5/−17 | 65.0 | −5/−12 |

(A/N = odd/H3-led; E/T/P = even/H2-led. Full 0..10 per-harmonic tables in `out/Decapitator_custom.json` → `drive_law`.)

**Memoryless confirmation — THD vs frequency (drive 7, fixed):** A: 37→34→34→34→34→33→25 % at 50/100/200/500/1k/2k/5k Hz (HF dip = bandwidth). P: 61→53→53→52→49→48→46 %. Harmonic *ratios* constant ⇒ memoryless shaper, NOT a stateful circuit.

**Tone tilt (pivot ≈985 Hz):** −12 → +9 dB @20 Hz, 0 @1k, −10 dB @10k. +12 → −22 dB @20 Hz, 0 @1k, +5 dB @16k.

**Lowcut:** 100 Hz → −9.5/−1.5 dB @58/98 Hz (≈6 dB/oct). **Highcut:** Gentle 2 kHz → −18 dB @20k (≈6 dB/oct); Steep 2 kHz → −59 dB @7k (≈24+ dB/oct).

**Punish (A, drive 5):** THD 16.7 %→37.7 %; adds odd ladder H3 −10.3, H5 −15.5, H7 −19.5, H9 −22.9.

**Autogain (A):** drive 0→8 = +2.2 dB out (ON) vs +14.9 dB out (OFF). **Lowthump (A):** +2…+4 dB @20–35 Hz, flat >50 Hz. **Latency:** 0 samples (reported, stable; ignore the noise-floor IR artifact of 62).

## To implement (CLEAN building blocks for ES-L)
- **Two memoryless transfer curves**: an odd-led shaper (tape/transformer — fit 3rd-harmonic-dominant, e.g. soft cubic/odd polynomial or tanh with odd emphasis) and an even-led shaper (tube — asymmetric so H2 leads, e.g. `x + a·x²` style or asymmetric tanh, then DC-block the output). Calibrate `a`/drive map to the THD-vs-drive tables above.
- **Per-model bandwidth** = a fixed LPF after the shaper (cheap stand-in for circuit reactance) — keeps THD flat in band, rolls HF.
- **1 kHz tilt EQ** (single low-shelf + high-shelf pivoting at 1 kHz, ±16 dB) as the post-shaper tone control.
- **HPF (6 dB/oct, swept) + LPF (selectable 6 vs 24 dB/oct)** as input/output band-limiting.
- **Punish** = a second hard-clip after the model (tanh→clip or simple symmetric clamp) for "go past the ceiling."
- **Autogain** = measure post-shaper RMS, apply inverse-drive makeup → constant loudness while sweeping drive (use for honest A/B in ES-L's saturation stage).
- **Lowthump** = low-shelf (<~40 Hz, +3 dB) to restore sub energy after drive/HPF. All CLEAN, reproduce from the curves above.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (only the binary arch/strip/PACE one-liner here).
