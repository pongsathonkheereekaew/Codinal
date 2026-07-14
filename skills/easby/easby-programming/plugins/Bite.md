# Bite — Native Instruments (Bit-crusher / lo-fi)

| | |
|---|---|
| Vendor / ver | Native Instruments · Bite **v1.3.7** (build NI_6_8_4_R2) |
| Type | Bit-crusher = sample-rate decimation + bit-depth quantization (+ pre/post filters, saturation, expander) |
| Tech | C++ "**Effekt Rig**" engine (`ni::effektrig::dsp::bite::Bite` on `ModulatableDSPCore<2u,2u,12u>`), statically-linked Qt 6.8.4 QML UI. **Shared engine across Bite/Dirt/Freak/Raum** (see below). No FFI. |
| Binary | Mach-O universal (x86_64+arm64), ~119 MB, **not stripped (144k syms)**, **no PACE/encryption**, Accelerate-linked |
| Provenance | CLEAN = pedalboard black-box measurement. REF = `nm`/`c++filt` symbol roster (quarantined). |
| Measured on | Bite v1.3.7 · 48 kHz · pedalboard 0.9.17 · `NI_ModFX/Tools/ni_sysid.py` · 2026-06-26 |
| Source | `private-research/NI_ModFX/Tools/ni_sysid.py` · REF `_quarantine_disasm/NI_ModFX/Bite.dsp_symbols.ref.txt` |

## Shared engine (cross-plugin — CLEAN structural / REF names)
Bite/Dirt/Freak/Raum are **one binary family**: 135,431 exported symbols common to all 4 (≈99.4%).
Shared core `ni::effektrig::dsp` + Qt6.8.4. Each plugin = its QML UI + one DSP class on
`ModulatableDSPCore<NIn,NOut,NParams>`. Decode-once. See `Dirt.md`/`Freak.md`/`Raum.md` and
`_quarantine_disasm/NI_ModFX/NOTICE.md`.

## Signal chain
```
x → HP filter (hp) → pre-filter LP (pre_flt) → [sample-rate decimate (freq, +jitter)
    → bit quantize (bit_depth, +dither, +crunch)] → saturation/boost → DC(dc) → expand
    → post-filter LP (post_flt) → mix(dry/wet)
```
(order REF-inferred from `preFilter`/`postFilter`/`updatePre/PostFilterCutoffs`; behaviour CLEAN.)

## Per-stage formula (tag CLEAN/REF)
- **Sample-rate reduction** (CLEAN): `freq` = target sample rate 100 Hz…44.1 kHz (sample-and-hold
  decimation). 8 kHz probe tone at `freq=6000` produces decimation aliases at 2.0k, 4.0k, 9.96k,
  13.99k, 15.94k (mirror images about freq/2) — classic zero-order-hold downsample, no anti-alias
  filter on the crush itself. `freq=44100` → tone passes clean (no decimation).
- **Bit depth** (CLEAN): `bit_depth` enumerated **2…16 bits** (15 steps) → amplitude quantization.
- **jitter** (REF name; CLEAN: modulates the sample/hold clock) — analog-clock instability on `freq`.
- **dither / crunch** (CLEAN params): noise-shaping / extra grit on the quantizer (0–100%).
- **Pre/post filter** (CLEAN): `pre_flt`,`post_flt` LP cutoffs 50 Hz…22.1 kHz around the crush block;
  `hp` high-pass 5/100/200 Hz (3-position). REF: `Bite::pre/postFilter`, `updatePre/PostFilterCutoffs`.
- **saturation** (CLEAN): 0…24 dB drive into a soft-clip; **boost** stage (REF `handleParameterBoost`).
- **dc** (CLEAN bool, REF `setDCShift`): DC-shift before quantizer → shifts quantization grid (adds bias).
- **expand** (CLEAN 0–100%): downward expander/gate to clean up crush-floor noise.

## Why / design rationale
- **No anti-alias on the decimator** → aliases fold audibly = the deliberate "digital/lo-fi" artifact;
  musical purpose is grit, not fidelity. Pre-filter LP lets you tame it; post-filter LP smooths output.
- **Separate freq (rate) vs bit_depth (amplitude)** → the two orthogonal axes of digital degradation;
  classic SP-1200/12-bit-sampler emulation.
- **jitter on the clock** → analog-tape/cheap-converter wow; humanizes the otherwise sterile decimation.
- **expand after crush** → quantization raises the noise floor; a gate restores silence between notes.

## Parameters (CLEAN — pedalboard surface)
| param | unit | range | notes |
|---|---|---|---|
| freq | Hz (target SR) | 100 – 44100 | sample-rate decimation; 44100 = off |
| jitter | % | 0 – 100 | clock jitter on `freq` |
| pre_flt | Hz | 50 – 22100 | pre-crush LP |
| post_flt | Hz | 50 – 22100 | post-crush LP |
| bit_depth | bits | 2 – 16 (enum, 15 steps) | amplitude quantization |
| crunch | % | 0 – 100 | extra quantizer grit |
| dither | % | 0 – 100 | dither/noise-shape |
| expand | % | 0 – 100 | downward expander (default 100) |
| dc | bool | On/Off | DC-shift into quantizer |
| hp | Hz | 5 / 100 / 200 | input high-pass (3-pos) |
| saturation | dB | 0 – 24 | drive |
| mix | % | 0 – 100 | dry/wet |
| bypass | bool | | |

## CLEAN measurements
- Decimation aliasing (8 kHz in): freq=6000 → 2015/3970/9955/13985 Hz images; freq=2000 → heavy
  fold to LF; freq=44100 → clean passthrough.
- 2–16 bit enumerated quantizer confirmed present (15 steps).

## To implement (ES-L CLEAN path)
Building blocks: ZOH decimator (hold counter from `Fs/freq`) → uniform mid-tread quantizer
(`round(x·2^(b-1))/2^(b-1)`) with optional TPDF dither + DC bias; one-pole/biquad pre & post LP;
3-pos HP; soft-clip drive; downward expander. All public-DSP; reproduce alias pattern to null-match.

---
Provenance: **CLEAN** = black-box measurement / public DSP / own voicing. **REF** = symbol-roster (reference only).
