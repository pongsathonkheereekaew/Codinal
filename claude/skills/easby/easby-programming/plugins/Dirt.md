# Dirt — Native Instruments (Saturation / distortion)

| | |
|---|---|
| Vendor / ver | Native Instruments · Dirt **v1.3.7** (build NI_6_8_4_R2) |
| Type | Dual-stage waveshaping saturation/distortion (2 stages A/B, 3 modes each, serial/parallel routing) |
| Tech | C++ "**Effekt Rig**" engine (`ni::effektrig::dsp::dirt::Dirt` on `ModulatableDSPCore<2u,2u,16u>`), Qt6.8.4 QML. **Shared engine** (Bite/Dirt/Freak/Raum). No FFI. |
| Binary | Mach-O universal, ~119 MB, not stripped, no PACE, Accelerate-linked |
| Provenance | CLEAN = pedalboard measurement. REF = symbol roster (quarantined). |
| Measured on | Dirt v1.3.7 · 48 kHz · pedalboard 0.9.17 · `NI_ModFX/Tools/ni_sysid.py` · 2026-06-26 |
| Source | `private-research/NI_ModFX/Tools/ni_sysid.py` · REF `_quarantine_disasm/NI_ModFX/Dirt.dsp_symbols.ref.txt` |

## Shared engine
Same family as Bite/Freak/Raum (see `Bite.md` + NOTICE). DSP class = one `Dirt` on `ModulatableDSPCore<2,2,16>`.

## Signal chain
```
x → [Stage A: tilt → drive → bias(DC) → waveshaper(mode_a) → amount → gainComp]
  → routing(A>B | A<B | A+B) →
    [Stage B: tilt → drive → bias → waveshaper(mode_b) → amount → gainComp]
  → fx_trim → mix(dry/wet)
```
(two identical stages; REF: `setMode1/2`, `setGainCompensation1/2`, `setRouting`. Behaviour CLEAN.)

## Per-stage formula (CLEAN/REF)
- **Waveshaper modes I/II/III** (CLEAN): **odd-harmonic-only** at bias=0 (symmetric shaper).
  Measured H2/H4/H6 = −185…−210 dBc (null); odd harmonics dominate:
  - Mode **I** (drive 60, 1k): H3 −13, H5 −26, H7 −37 dBc → **fastest harmonic roll-off** (softest/most rounded clip).
  - Mode **II** ≈ **III** (drive 60): H3 −10, H5 −19, H7 −27 dBc → **richer / slower roll-off** (harder clip / more grind). II & III diverge at higher drive / via the fold path.
- **Wavefolder behaviour** (CLEAN): at drive=100 mode II the transfer curve is **non-monotonic /
  fold-back** — `out(in=+0.8) = −0.379` (input goes up, output folds back down). ⇒ a **wavefolder**,
  not just a clipper, at high drive. THD reaches ~100%+.
- **drive** (CLEAN, 0–100%): input gain into the shaper; transfer curve sweep
  (modeII): drive0 ≈ linear (×0.94), drive30 onset of compression, drive60 hard knee, drive100 folds.
- **bias** (CLEAN, 0–100%): **DC offset into the shaper → adds even harmonics** (asymmetry).
  H2: −190 dBc (bias0) → −24 (bias50) → −15 (bias100). The even/odd-mix "warmth" control.
- **tilt** (CLEAN, −100…+100%): **spectral pre/de-emphasis tilt** around the shaper, ≈±6.5 dB
  span 200 Hz↔5 kHz (−100 → −5.1 dB hi/lo, +100 → +1.4 dB) — pivots high-vs-low energy into distortion.
- **amount** (CLEAN, 0–100%): wet/dry of that stage's distortion. **safety** (bool): per-stage output
  brickwall/limiter. **gainComp** (REF `setGainCompensation`): auto level-match vs drive.
- **routing** (CLEAN): `A > B` serial, `A < B` serial reversed, `A + B` parallel sum.
- **fx_trim** (CLEAN, −18…+6 dB) post-FX trim; **mix** dry/wet.

## Why / design rationale
- **Two stages + routing** → stack two different distortion characters (e.g. soft mode I → hard mode II)
  serially, or blend in parallel — a full "dirt rig" not a single shaper.
- **bias = even-harmonic dial** → asymmetric clipping = tube/transformer 2nd-harmonic warmth on demand,
  while bias=0 keeps it odd-only (transistor/op-amp "buzz").
- **tilt around the shaper** → distortion is frequency-weighted: tilt-low pushes bass into the fold (fuzzy
  low end), tilt-high crisps the top — far more musical than flat full-band drive.
- **wavefold at high drive** → extreme harmonic generation / ring-mod-like metallic tones, NI's "destruction" range.

## Parameters (CLEAN)
| param | unit | range | notes |
|---|---|---|---|
| mode_a / mode_b | enum | I / II / III | shaper character (odd-harmonic decay rate / fold) |
| amount_a / amount_b | % | 0 – 100 | per-stage distortion wet |
| drive_a / drive_b | % | 0 – 100 | input gain into shaper (fold ≳ 60–100) |
| bias_a / bias_b | % | 0 – 100 | DC asymmetry → even harmonics |
| tilt_a / tilt_b | % | −100 – +100 | spectral tilt around shaper (±~6.5 dB 200↔5k) |
| safety_a / safety_b | bool | On/Off | per-stage output limiter |
| routing | enum | A>B / A<B / A+B | serial / serial-rev / parallel |
| fx_trim | dB | −18 – +6 | post-FX trim |
| mix | % | 0 – 100 | dry/wet |
| bypass | bool | | |

## CLEAN measurements
Harmonic tables above (modes, bias). Transfer curves (modeII drive 0/30/60/100) confirm fold-back at 100.

## To implement (ES-L CLEAN path)
Two cascaded waveshaper stages: each = tilt biquad (pre) → drive gain → +DC bias → odd-symmetric
shaper (tanh/poly for I, harder/cubic-with-fold for II/III) → amount blend → auto-gain. Routing matrix
serial/parallel. Oversample to control fold aliasing. Match measured H3/H5/H7 ratios + bias→H2 curve to null.

---
Provenance: **CLEAN** = measurement / public DSP / own voicing. **REF** = symbol roster (reference only).
