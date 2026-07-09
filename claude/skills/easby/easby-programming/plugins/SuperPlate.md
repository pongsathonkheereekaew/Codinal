# SuperPlate — Soundtoys (Reverb · multi-model EMT-140-style plate)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Reverb — multi-model vintage plate (5 plate voicings × 3 analog drive styles) with auto-decay ducking, dual EQ, width |
| Tech | C++ VST3, shared "Soundtoys" framework (statically linked → one plugin per process). AAX = PACE; VST3 = pedalboard-hostable, no DRM wall. |
| Binary | universal2 (arm64+x86_64); VST3 not PACE-encrypted. |
| Provenance | **CLEAN** (all facts = black-box measurement of the licensed VST3 + public plate/FDN literature). No disasm. |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys/` (harness `Tools/{st_sysid.py,st_rev_run.py,sp_models.py}`; data `out/SuperPlate_*.json`) |

## Signal chain
```
x → input gain → analog-style drive (Tube/SolidState/Clean nonlinearity)
  → low-cut HP (selectable slope) → [plate tank, voicing = plate_style, time = decay,
      intrinsic HF damping, modulation chorus] → high-cut LP (selectable slope)
  → auto-decay (decay ducks toward target_decay when input > threshold, recovery_time)
  → dual parametric EQ (eq1, eq2) → width / balance → output gain → mix(wet/dry) → stereo out
```
The "studio rack" version of LittlePlate: same plate core, plus model selection, an input-modeled drive stage, a decay-ducker, post EQ, and stereo controls.

## Per-stage formula  (all CLEAN — measured)
- **Plate models (`plate_style`: Stocktronics / E. Plate III / Audicon / Goldfoil 240 / Classic 140)** (CLEAN): each is a distinct plate voicing differing in **(a) decay multiplier** (same Decay setting → different actual RT60), **(b) echo/modal density**, **(c) intrinsic HF damping**. Measured at Decay≈4.4 s, low/high-cut wide, Clean drive (see table). Stocktronics = short & bright; **Classic 140** = the canonical EMT-140 (medium-long, dark); Goldfoil 240 = short & *very* dark (heaviest HF loss); E. Plate III = longest & densest; Audicon = medium.
- **Analog style (`analog_style`: Tube / Solid State / Clean)** = the **input/converter nonlinearity** of the modeled vintage hardware (CLEAN): a memoryless-ish saturation stage on the drive. Measured THD on a −6 dBFS 1 kHz tone (Classic 140): **Tube ≈ 14 % THD, H2-dominant** (even-harmonic tube warmth); **Solid State ≈ 0.6 % THD** (mild); **Clean ≈ 0.1 % THD** (transparent). Tube THD scales with model (14–59 %); H2 ≫ H3 for Tube ⇒ asymmetric/even-order coloration.
- **Decay → RT60** (CLEAN): displayed **Decay** label ≈ target RT60 s (continuous normalized param, ~24 named detents). At Decay≈4.44 the actual T30 depends on model (3.1 s Stocktronics … 7.0 s E. Plate III). Top = **Infinite** (freeze/sustain).
- **Predelay (`predelay_msec` 0–250)** (CLEAN): exact, linear — measured onset = set value to ±0.3 ms across 0/25/50/100/200 ms.
- **Modulation (`modulation` 0–100, `mod_rate_hz` 0.2–8, def 1.1 Hz)** (CLEAN): chorus on the tank delays. The plate modulates even at modulation=0 (default rate 1.1 Hz) and depth rises with the knob (held-tone wobble ptp 168→249 Hz from 0→100) → anti-flutter shimmer.
- **Low-cut (`low_cut_hz` 20–1000, `low_cut_slope` −6/−12/−24 dB/oct)** (CLEAN): HP on the wet, selectable order. Raising lc 100→1000 pulls 60 Hz from ≈−6 to ≈−18 dB.
- **High-cut (`high_cut_hz` 1000–20000, `high_cut_slope` −6/−12/−24)** (CLEAN): LP damping with **confirmed selectable slope** — at 2 kHz cutoff the 8 kHz tail attenuates −89 / −102 / −127 dB for −6/−12/−24 dB/oct. At hc=1000 the 2 kHz tail drops to −63 dB.
- **Auto-decay / decay-ducking (`target_decay`, `threshold_db` −40…0, `recovery_time_msec` 1–500)** (CLEAN, partially characterized): when the input level exceeds `threshold`, the running decay is pulled toward `target_decay` (shorter), recovering over `recovery_time` after the input falls — i.e. a *dynamic reverb* that gets out of the way during loud passages and blooms in gaps. A/B with threshold engaged vs off measurably changes post-burst tail length; exact gain/time law not fully resolved black-box (coarse-probe-limited) — documented behaviorally, not as a shipped formula.
- **Dual parametric EQ (`eq1_*`, `eq2_*`)** (CLEAN, from param surface): two bell bands, gain ±24 dB, freq 20–20000 Hz, Q 0.1–10 — post-reverb tone shaping (eq1 def 300 Hz, eq2 def 2 kHz).
- **Width / balance (`width` 0–100, `balance_deg` −45…45)** (CLEAN): width is a real stereo control — tail L/R correlation **1.0 → 0.68 → −0.06** at width 0/50/100 (mono → fully decorrelated). balance pans the wet.
- **Mix (`mix`)** (CLEAN): linear wet/dry; mix=0 → bit-exact dry (null −400 dB).

## Why / design rationale (music ↔ code)
- **Five plate models** → recreate the sonic fingerprints of different real plates (and a gold-foil) so users pick a *character*, not just a time. The orthogonal axes that actually differ between real plates — decay rate, modal density, HF damping — are exactly what's modeled, which is why the same Decay knob yields different RT60s per model.
- **Analog style = a drive/converter stage, not a tail effect** → vintage plate sends ran through tube or solid-state electronics that added harmonics *before* the tank; modeling it as an input nonlinearity (H2-dominant Tube) gives the "expensive hardware" warmth on the wet without touching the diffusion network. Even-order H2 = the universally pleasant "tube" signature.
- **Predelay 0–250 ms** → a plate has no geometric pre-delay, so an explicit one lets the dry transient speak before the wash → vocal clarity, the standard plate-on-vocals trick.
- **Auto-decay ducking** → the headline "Super" feature: a long lush reverb is gorgeous in gaps but muddies dense sections; ducking the decay toward a short `target` when the source is loud keeps mixes clean while still blooming in the spaces — a built-in "reverb that mixes itself" (vs an external ducking compressor on the return).
- **Selectable cut slopes + post EQ** → studio-grade tone control: steep cuts to surgically bracket the reverb band, gentle cuts for musical voicing, plus two bells to dial the timbre — the flexibility LittlePlate deliberately omits.
- **Width control** → unlike the always-wide LittlePlate, SuperPlate lets you collapse to mono (corr 1.0) for mix compatibility or open to full decorrelation (corr ≈ 0) for size — engineered via L/R tap/matrix-row divergence.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| plate_style | enum | Stocktronics, E. Plate III, Audicon, Goldfoil 240, **Classic 140**(def) | plate voicing |
| analog_style | enum | Tube, **Solid State**(def), Clean | input drive nonlinearity |
| decay | s (RT60) | ~0.50…51.83 + Infinite (def 3.00) | continuous; label ≈ RT60 s |
| predelay_msec | ms | 0–250 (def 0) | exact, linear |
| modulation | % | 0–100 (def 0) | chorus depth (plate modulates even at 0) |
| mod_rate_hz | Hz | 0.2–8 (def 1.1) | chorus rate |
| mix | % | 0–100 (def 100) | linear wet/dry |
| input_db / output_db | dB | −24…+24 (def 0) | I/O trim |
| low_cut_hz | Hz | 20–1000 (def 20) | wet HP |
| low_cut_slope | dB/oct | −6 / −12 / −24 (def −24) | |
| high_cut_hz | Hz | 1000–20000 (def 20000) | wet LP / damping |
| high_cut_slope | dB/oct | −6 / −12 / −24 (def −12) | confirmed selectable |
| target_decay | s (RT60) | same enum as decay (def 0.50) | duck target |
| threshold_db | dB | −40…0 (def 0) | auto-decay trigger |
| recovery_time_msec | ms | 1–500 (def 125) | duck recovery |
| width | % | 0–100 (def 100) | 0=mono tail, 100=decorrelated |
| balance_deg | ° | −45…45 (def 0) | wet pan |
| eq1_gain_db / eq2_gain_db | dB | −24…+24 (def 0) | post bells |
| eq1_freq_hz / eq2_freq_hz | Hz | 20–20000 (def 300 / 2000) | |
| eq1_q / eq2_q | Q | 0.1–10 (def 0.70 / 0.40) | |

## CLEAN measurements
**Per-model fingerprint** (Decay raw 0.45 ≈ label 4.44; low/high-cut wide):
| plate_style | RT60 T30 (s) | early density (taps/50 ms) | HF damping (8k − 250 Hz, dB) | THD @ Tube / SS / Clean |
|---|---|---|---|---|
| Stocktronics | ~3.2 | ~640 | −23…−28 (brightest) | 35.0 / 2.2 / 0.45 % |
| E. Plate III | ~7.0 | ~780 (densest) | −46…−51 | 45.7 / 1.8 / 0.63 % |
| Audicon | ~5.0 | ~630 | −28…−34 | 30.4 / 1.6 / 0.82 % |
| Goldfoil 240 | ~3.4 | ~500 (sparsest) | −98…−103 (darkest) | 59.3 / 2.8 / 0.45 % |
| **Classic 140** | ~5.1–6.3 | ~600 | −53…−58 | 13.9 / 0.6 / 0.14 % |

**Predelay**: set→measured 0→0.3, 25→25.3, 50→50.3, 100→100.3, 200→200.3 ms (linear, exact).
**High-cut slope** (hc=2 kHz): 8 kHz tail = −88.8 / −101.6 / −126.8 dB for −6/−12/−24 dB/oct.
**Width**: tail L/R corr 1.0 / 0.68 / −0.06 at width 0 / 50 / 100.
**Mod**: held-1 kHz wobble ptp 168 (modulation 0) → 249 Hz (100). **Mix**: 0 → null −400 dB. **Latency**: reported 32 samples.

## To implement (CLEAN-only path for ES-L family)
- **Plate core** = dense FDN / Dattorro plate (as LittlePlate). Implement **model = a preset of {decay-multiplier, line count/density, per-line HF-damp cutoff}** so one engine yields all 5 fingerprints (e.g. Goldfoil = aggressive damp + fewer/shorter lines; E. Plate III = many long lines, mild damp).
- **Analog drive** = a memoryless asymmetric waveshaper on the input: **Tube** = even-harmonic-rich (H2≫H3, ~10–60 % THD scalable), **Solid State** = gentle (~1–3 %), **Clean** = bypass. Reuse the AS-1/saturation building block.
- **Decay/predelay/mod/cuts/mix** = as LittlePlate, plus **selectable filter order** (cascade 1/2/4 one-poles for −6/−12/−24 dB/oct) on both low- and high-cut.
- **Auto-decay ducking** = an envelope follower on the input (threshold, recovery) that scales the FDN feedback gain toward the `target_decay` value when triggered — a "dynamic reverb". Own-voicing the exact time-constant law (measurement gave behavior, not a shippable curve).
- **Post EQ** = two bell biquads (±24 dB, 20–20 kHz, Q 0.1–10). **Width** = L/R decorrelation crossfade (mono tap-sum at 0 → independent matrix rows at 100). **balance** = wet pan.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). **REF** = disasm-derived (none used here).
