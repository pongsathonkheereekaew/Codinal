# BandMatrix — dev.kojima (6-band up/down multiband compressor + matrix routing)

| | |
|---|---|
| Vendor / ver | dev.kojima · 1.6.0 |
| Type | Multiband dynamics: **6-band bipolar (down-comp ↔ up-expand) compressor**, per-band M/S, tone-shaper, internal/external sidechain, key filters |
| Tech | JUCE C++ + WebKit UI; 39.8k syms, NOT stripped, no PACE |
| Binary | universal (x86_64+arm64) |
| Provenance | **CLEAN** (pedalboard). No disasm done. |
| Measured on | BandMatrix 1.6.0 · 48 kHz · pedalboard 0.9.17 · 2026-06-26 |
| Source | `private-research/CleanMisc/Tools/cleanmisc_sysid.py` |

## Signal chain
```
x → 5-crossover split into 6 bands (120/400/1200/3500/9000 Hz)
  → per band: [key HP/LP] → detector(Peak/RMS) → gain-computer(thr,ratio±,knee)
             → [M/S bias, stereo-link, int/ext SC mix, tone-shaper] → makeup gain
  → recombine → [lookahead 0..5 ms] → out
```

## Per-stage formula (CLEAN)
- **Crossover** (CLEAN, param surface): 5 user crossovers default **120 / 400 / 1200 / 3500 / 9000 Hz** → 6 bands. (Linear impulse split not clean-measurable — it's a dynamics processor, gain-dependent; bands isolate by region under perturbation.)
- **Gain computer — bipolar ratio** (CLEAN): ratio range **−20..+20**. **Positive = downward compression**, **negative = upward expansion**. Measured band-4 (2 kHz), thr −24 dB:
  - ratio +4: in/out(GR) = −40/−41.4(1.4) · −24/−25.8(1.8) · −18/−23.9(5.9) · −6/−19.0(13.0) · 0/−15.8(15.8) → clean downward knee onset at thr.
  - ratio −4: in −6 dB → out **+6.2 dB** (GR −12.2) → gain ADDED above threshold (upward).
  - (~1.4 dB constant offset below thr = band-split insertion loss, subtract for true unity.)
- **knee** 0..24 dB soft; **attack** 0.1..200 ms, **release** 5..1000 ms (per band).
- **lookahead** 0..5 ms global.

## Why / design rationale
- Bipolar ratio in one knob → one band can compress peaks OR lift quiet detail (upward) without a separate expander → "matrix" of dynamic moves per band.
- Per-band M/S bias + int/ext SC + key filters → surgical, frequency-and-image-targeted dynamics (de-ess one band, widen another, duck a third from an external key).
- Tone-shaper per band → spectral tilt baked into the band, shaping while it compresses.

## Parameters (per band ×6 unless noted)
| param | unit | range | notes |
|---|---|---|---|
| source | enum | Int/Ext | sidechain source |
| detector | enum | Peak/RMS | |
| image | enum | Stereo/Mid/Side | M/S targeting |
| tone_shaper / sharpness / depth | bool / 0..1 / 0..1 | | per-band spectral tilt |
| threshold | dB | −60..0 | |
| ratio | ratio | **−20..+20** | sign = up vs down |
| attack / release | ms | 0.1..200 / 5..1000 | |
| knee | dB | 0..24 | |
| gain | dB | −18..+18 | makeup |
| key_hp / key_lp | Hz | 20..20k | SC filters |
| int_ext_mix / m_s_bias / stereo_link | 0..1 | | |
| listen_key / solo_band / bypass_band / inverse_sidechain | bool | | **solo = metering-only, not audio-isolating** |
| crossover_1..5 (global) | Hz | 20..20k | 120/400/1200/3500/9000 default |
| lookahead (global) | ms | 0..5 | |
| auto_makeup | bool | | |

## Open questions
- Crossover filter order/type (LR vs Butterworth) not isolated — solo is metering-only; needs a level-domain crossover probe (sweep one crossover to the rails, measure slope).
- Tone-shaper exact curve unmeasured.

## To implement
Standard 6-band LR crossover + per-band feed-forward gain computer with **signed ratio** (ratio>0: `(thr-x)(1-1/r)`; ratio<0: upward `(thr-x)(1-1/|r|)` with sign flipped above thr). Peak/RMS detector, soft knee, per-band M/S + SC. All CLEAN.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing.
