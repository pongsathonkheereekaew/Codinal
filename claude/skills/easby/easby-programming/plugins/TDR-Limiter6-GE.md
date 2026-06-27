# TDR Limiter 6 GE — Tokyo Dawn Records (Multi-stage true-peak limiter)

| | |
|---|---|
| Vendor / ver | Tokyo Dawn Records / Limiter 6 GE (free edition) |
| Type | Multi-stage dynamics: HF Limiter + Compressor + Peak Limiter + Clipper + TP output stage |
| Tech | C++ (likely JUCE/own framework), WebKit UI. Not Rust, no clean FFI. |
| Binary | x86_64+arm64 fat, **stripped** (4 exported syms), **no PACE / no encryption** → pedalboard-open |
| Provenance | All facts below CLEAN (black-box). No static REF pulled (stripped; not worth it — fully measurable). |
| Measured on | Limiter 6 GE · SR 96 kHz · pedalboard 0.9.17 · 2026-06-26 |
| Source | `private-research/TDR_Limiter6/Tools/tdr6_sysid.py` |

## Signal chain
```
x → [HF Limiter] → [Compressor] → [Peak Limiter] → [Clipper] → [Output: drive → TP/PCM ceiling] → y
```
**`module_order` (0..119) reorders the 5 processing modules** — 120 = 5! permutations. Default order index 3.
Each module independently enable/bypass-able; each has its own dry-mix (parallel), M/S mode, and meter scale.

## Per-stage behaviour  (all CLEAN)
- **HF Limiter** (CLEAN): high-frequency-targeted limiter. `frequency_hz` 1500–18000 (def 5 k), `threshold_db`
  −40..+12, `range_db` −18..0 (max attenuation), `type` Abs./… , soloable. Tames de-ess/HF harshness pre-limit.
- **Compressor** (CLEAN): full comp. `mode` incl. **Nova** (def), `thresh_db` −36..+6, `ratio` 1.1–10:1,
  `attack_ms` 1–500 (def 50), `release_ms` 50–2000 (def 100), `gain_db` ±18, width (M/S) thresh+gain. Dry-amount parallel.
- **Peak Limiter** (CLEAN): brickwall. `threshold_db` −18..+6 (def −1), `b_wall` (brickwall) On, `multiband` On,
  `lookahead` 1x/2x/3x, `focus_db` ±6, `release_ms` (def 50). The main gain-reduction stage.
- **Clipper** (CLEAN): `mode` B.Wall/…, `threshold_db` −18..+6 (def −1), `knee_db` 0–12 (def 6 = soft knee),
  `separation` 0–100 (per-band clip independence). Hard/soft clip after limiting for loudness.
- **Output** (CLEAN): `output_drive_db` ±18, **dual ceiling** `output_ceiling_tp_db` & `output_ceiling_pcm_db`
  (−6..+6, def −1), `output_lim_pcm` = **True Peak** (def) / PCM. `auto_pad`, `dithering`, `quality` (Precise…).

## CLEAN measurements (96 kHz, defaults unless noted)
- **Static (1 kHz sine, in→out peak)**: unity ≤ −8 dBFS; soft knee from ≈ −6; **ceiling ≈ −1 dBFS** (= default
  TP ceiling). Past 0 dBFS-in the measured sine peak *drops* (−1.5→−2.9 @ +6) as comp + limiter + clipper GR stack.
- **True-peak**: 11 kHz tone clamped → sample-peak −3.85, 8×-oversampled true-peak −3.81, **Δ +0.04 dB ⇒ genuine
  true-peak (ISP) limiter.** (Contrast Ozone 11 Maximizer +3 dB = sample-peak only.) Matches `output_lim_pcm=True Peak`.
- **Lookahead / latency**: impulse → symmetric **~41-tap FIR**, pre-ring before the peak (idx 1012<1024) ⇒
  linear-phase oversampling + real lookahead; step shows gain pre-attenuating 2 samp *before* the transient.
  pedalboard PDC-auto-compensates → reports 0 latency (exact sample count is hidden).

## Why / design rationale
- **6 reorderable stages** → user sculpts the loudness pipeline (e.g. clip-before-limit vs limit-before-clip changes
  density vs transient feel). The permutation param is the product's signature flexibility.
- **HF limiter first option** → pre-tame sibilance/cymbals so the main limiter isn't triggered by HF transients → louder, cleaner masters.
- **True-peak output ceiling default −1 dB** → inter-sample-peak safe for lossy codecs (AAC/MP3) — the modern mastering default.
- **Soft-knee clipper (6 dB) after the limiter** → adds density/loudness while the TP stage guarantees the ceiling → "loud but safe."

## Parameters (key; full surface dumped by `tdr6_sysid.py params`)
| param | unit | range | notes |
|---|---|---|---|
| peak_lim_threshold_db | dB | −18..+6 | main limiter thr (def −1) |
| peak_lim_lookahead | × | 1/2/3x | lookahead multiplier |
| peak_lim_release_ms | ms | (def 50) | |
| comp_ratio | :1 | 1.1..10 | |
| comp_attack_ms / release_ms | ms | 1..500 / 50..2000 | **ms confirmed (string_value)** |
| hf_lim_frequency_hz | Hz | 1500..18000 | HF-limiter corner |
| clipper_knee_db | dB | 0..12 | soft-knee clip |
| output_ceiling_tp_db | dB | −6..+6 | true-peak ceiling (def −1) |
| output_lim_pcm | enum | TruePeak/PCM | ceiling mode |
| module_order | idx | 0..119 | 5! module permutations |
| quality | enum | Precise… | OS quality |

## Open questions
- Exact lookahead in samples per 1x/2x/3x — read via REAPER `TrackFX_GetNamedConfigParm(...,"pdc")` (pedalboard hides it).
- Per-stage isolation (use each module's `*_enabled` to A/B one stage at a time) for exact comp/clip curves.
- Compressor detector kind (peak vs RMS) per `comp_mode` (Nova vs others) — dual-burst probe.

## To implement (CLEAN path for ES-L)
Reusable: **true-peak oversampled ceiling** (linear-phase OS FIR + ISP detection) — the ES-L-relevant primitive,
here proven TP-clean. Soft-knee clipper + brickwall-limiter cascade for loudness. Reorderable-module architecture
is the product idea worth borrowing. All CLEAN-measured — safe to clone behavior.
