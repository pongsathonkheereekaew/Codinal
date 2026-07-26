# Gaffel — Klevgrand (4-band LR4 crossover splitter)

| | |
|---|---|
| Vendor / ver | Klevgrand · AAX v1.0.6 / **VST3 v1.0.7** |
| Type | 4-band frequency splitter (Linkwitz-Riley crossover, per-band enable; zero-latency, phase-coherent) |
| Tech | JUCE C++, no FFI; VST3 SDK 3.7.8, AAX SDK 2.4.1; UI WebKit/Metal |
| Binary | Universal `[x86_64,arm64]`. **VST3 = clean** (not stripped, 617 syms, **no PACE**) → measurable. AAX = stripped + **PACE-iLok** (`__Pace_Eden.bundle`) → static wall (irrelevant, VST3 hosts fine). |
| Provenance | **CLEAN** (pedalboard black-box on VST3). REF (strings/RTTI) only corroborates names. |
| Measured on | Gaffel **VST3 1.0.7** · SR 48 kHz · pedalboard 0.9.17 · 2026-06-22 · `Gaffel/Tools/gaffel_sysid.py` |
| Source | `private-research/Gaffel/Tools/{gaffel_sysid.py,gaffel_measured.json}`; REF: `_quarantine_disasm/Gaffel/` |

## Signal chain (CLEAN)
```
x → LR4 split @ f1,f2,f3 → 4 bands (band_n_active gates each) → Σ → bypass → y
    band1 LP<f1 · band2 BP f1..f2 · band3 BP f2..f3 · band4 HP>f3
```
Pure linear splitter — no per-band gain/saturation/dynamics params exist (the `Input #`/`Output #`
strings are bus pin names, not controls). All bands active + unity = bit-flat passthrough.

## Per-stage formula (CLEAN)
- **Crossover bank** (CLEAN): **Linkwitz-Riley 4th-order (LR4)** = cascaded 2× Butterworth-2.
  Measured **−6.0 dB crossing** at each split (LR signature; Butterworth would be −3), **~24 dB/oct**
  skirts (meas −21.8…−22.4 / +23.4, asymptotic 24), **zero added latency** (IR peak @ idx 0 → IIR).
- **Reconstruction** (CLEAN): all 4 bands → **0.000 dB ripple, flat 20 Hz–20 kHz** → phase-coherent
  allpass sum (no polarity trick needed → confirms LR4, not LR2). Magnitude-perfect; phase rotates (IIR).
- **Band gate** (CLEAN): `band_n_active` 0/1 includes/excludes that band from the sum (hard, no crossfade artifacts in magnitude).

## Why / design rationale (music ↔ code)
- **LR4 (24 dB/oct, −6 dB cross) over steeper/linear-phase** → flat-magnitude recombination with zero
  latency → bands re-sum transparently → ideal for a *router/splitter* (send each band elsewhere, mute a
  band) where phase-coherence on recombine matters more than brickwall separation or linear phase.
- **Zero latency** → usable live / on the main bus without PDC cost; the IIR (not FFT) choice trades
  linear phase for latency-free, CPU-cheap operation — correct for a utility splitter.
- **No per-band gain in the DSP** → Gaffel is a pure *band selector/splitter*, not a multiband EQ; the
  `GaffelMultiSlider`/`FreqView` GUI just drags the 3 crossover points on a spectrum.

## Parameters (CLEAN — pedalboard host API; 8 total)
| param | unit | range | notes |
|---|---|---|---|
| crossover_frequency_1 | norm 0..1 | ~130 Hz–1.7 kHz | default 0.0837 → **159.7 Hz** |
| crossover_frequency_2 | norm 0..1 | ≳1 kHz (clamped by nbrs) | default 0.2215 → **999.8 Hz** |
| crossover_frequency_3 | norm 0..1 | ~5 kHz+ (clamped by nbrs) | default 0.4992 → **4999.5 Hz** |
| band_1..4_active | bool (0/1) | on/off | gates band into the sum |
| bypass | bool | on/off | master bypass |

norm→Hz taper smooth-monotonic per crossover; crossovers constrained to stay ordered (f1<f2<f3) so per-band
ranges overlap/clamp. Default split = **160 Hz / 1 kHz / 5 kHz**. Exact GUI taper = UI detail, not DSP.

## FFI contract
None — pure JUCE C++, no exported DSP ABI.

## CLEAN measurements
| crossover | default norm | measured Hz | cross level | slope |
|---|---|---|---|---|
| f1 (band1↔2) | 0.0837 | 159.7 Hz | −6.02 dB | LP −22 dB/oct |
| f2 (band2↔3) | 0.2215 | 999.8 Hz | −5.59 dB | — |
| f3 (band3↔4) | 0.4992 | 4999.5 Hz | −6.03 dB | HP +23 dB/oct |

Reconstruction (all active): ripple **0.000 dB** (20 Hz–20 kHz), IR peak idx 0 → **latency 0**, phase-coherent.

## To implement
- Reusable CLEAN building block: **LR4 4-band crossover** (cascaded Butterworth-2 pairs → LP/BP/BP/HP,
  −6 dB cross, flat phase-coherent sum, zero latency). Public DSP (Linkwitz-Riley; Zölzer DAFX). Drop-in
  if ES-L ever goes multiband. Verify clone vs Gaffel: per-band magnitude + 0-dB recon null.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = static-inspection-derived (reference only — reproduce black-box before shipping).
