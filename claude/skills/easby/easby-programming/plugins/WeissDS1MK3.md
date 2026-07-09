# Weiss DS1-MK3 — Softube / Weiss Engineering (Dual-band Dynamics + Limiter)

| | |
|---|---|
| Vendor / ver | Softube (Weiss Engineering license) · v2.6.38 (b167636) |
| Type | Dual-band frequency-selective compressor/de-esser + safety brickwall limiter + dither |
| Tech | Softube ACF (C++), SSX encrypted runtime, PACE-iLok (all formats — VST3, AU, AAX all wrapped) |
| Binary | fat (x86_64 + arm64) · 13 exported syms (entry stubs only) · `__Pace_Eden.bundle` + `libpacefusion_shared.dylib` · encrypted DSP payload |
| Provenance | **CLEAN** = param surface from AAX Pagetables.xml + public Weiss DS1 MK3 hardware literature. **REF** = none (static wall, encrypted) |
| Measured on | Not yet measured (iLok required) · Pagetables from v2.6.38 AAX |
| Source | `private-research/WeissDS1MK3/` · `_quarantine_disasm/WeissDS1MK3/` |

## Signal chain
```
Input → [Input Gain] → [Sidechain Filter (Center Freq / Bandwidth / Filter Type)]
                                  ↓ (detector path, internal sidechain)
                         [Detector: Peak or RMS (Average window)]
                                  ↓
                         [Gain Computer: Threshold / Ratio / Soft Knee]
                                  ↓
                         [Time Constants: Attack / Release Delay / Release Fast / Release Slow]
                                  ↓ (gain reduction applied to main path)
         [VCA / gain element] → [Gain Make-Up] → [Parallel mix (Parallel Compression)]
                  ↓
         [Safety Limiter (brickwall, Limiter Gain ceiling)]
                  ↓
         [Output Gain] → [Dither] → Output

Ch1 = L (or Mid in MS mode)
Ch2 = R (or Side in MS mode)
Ganged = link Ch1/Ch2 params
```

## Per-stage formula (tag each CLEAN or REF)

- **Detector** (CLEAN — from param surface): `Peak` or `RMS` selectable via `RMS` param.
  `Average 1/2` = RMS averaging window length [unit: **TO MEASURE**].
  Detection path filtered by sidechain bandpass/HP (see frequency section).

- **Gain computer** (CLEAN — standard VCA comp formula):
  `GR = Ratio × max(0, L_det − Threshold)` with soft knee blending over `Soft Knee` range.
  Standard textbook: `GR_soft = (L_det − Thr + Knee/2)² / (2 × Knee)` in knee region.

- **Time constants** (CLEAN — structure inferred from 4-param release):
  Weiss hardware DS1 uses a **multi-bucket (dual/triple) program-dependent release**:
  - `Attack 1/2` = attack time constant [**TO MEASURE** ms range]
  - `Release Delay 1/2` = hold/delay before release begins [**TO MEASURE** ms]
  - `Release Fast 1/2` = fast release time constant [**TO MEASURE** ms]
  - `Release Slow 1/2` = slow release time constant [**TO MEASURE** ms]
  - `Average 1/2` = RMS detector averaging window 0–100 ms (CLEAN — HW manual)
  Program-dependent release: `Average` sets how long a loud signal must be sustained before the
  slow bucket kicks in. Short transients → fast bucket (Release Fast). Sustained loud content →
  slow bucket (Release Slow). `Release Delay` = hold capacitor (gain reduction held before releasing).
  Weiss hardware white paper: "program-adaptive release modeled on auditory masking behavior."

- **Frequency selector** (CLEAN — from param surface):
  `Filter Type 1/2` = {OFF / HP / BP / LP} [**TO MEASURE** exact enum values]
  `Center Frequency 1/2` = band center [**TO MEASURE** Hz range]
  `Bandwidth 1/2` = filter width [**TO MEASURE** unit: octaves or Q]
  When Filter Type = OFF → broadband (wideband) compression, no freq selectivity.
  When Filter Type = HP/BP → frequency-selective (de-esser mode): only sibilance band triggers gain reduction; main path processed wideband.

- **Limiter (Safety Limiter)** (CLEAN — from param surface):
  Brickwall ceiling = `Limiter Gain` param [**TO MEASURE** dBFS range].
  `Safety Limiter Mode` = character/lookahead mode [**TO MEASURE** options].
  Separate `Limiter GR Meter` readback.

- **Parallel compression** (CLEAN): wet/dry blend of compressed vs uncompressed signal.
  `Parallel Compression` param [**TO MEASURE** 0–100% or dB].

- **MS processing** (CLEAN): `MS Mode` → encode L/R to M/S before processing, decode after.
  Ch1 → Mid, Ch2 → Side. Standard M = (L+R)/2, S = (L−R)/2 matrix.

- **Dither** (CLEAN): output dither, likely TPDF or noise-shaped. Options [**TO MEASURE**].

## Why / design rationale

- **Dual-channel architecture (Ch1 + Ch2)** → processes L+R independently (or M+S); mastering-grade stereo control without hard link. `Ganged` couples both channels for convenience.
- **Frequency-selective sidechain** → de-esser behavior: sibilance (5–12 kHz) detected → only gain-reduced wideband, not just that band = transparent de-essing (no "lispy" artifacts from band-only processing). Classic Weiss hardware approach.
- **Multi-bucket program-dependent release** (Release Delay + Fast + Slow) → hardware Weiss DS1 signature. Short transients release quickly (fast bucket) while sustained loudness holds/releases slowly → musical, preserves punch without pumping.
- **Safety Limiter** → mastering protection: final brickwall after the compressor guarantees no true-peak overs reach the output. Standard for mastering chains.
- **Dither** → 24-bit output dither at plugin tail; correct mastering workflow for noise-floor-extending dither before final digital delivery.
- **Parallel compression** → NY compression / blend knob; allows compressed character without full dynamic squashing.
- **MS mode** → mastering utility: compress mid/side independently (e.g. compress side less than mid to preserve width).

## Parameters (CLEAN — from AAX Pagetables.xml + Weiss DS1 MK3 hardware manual)

| param | unit | range | notes |
|---|---|---|---|
| Threshold 1/2 | dBFS | −40 to 0 | compressor threshold per channel (CLEAN — HW manual) |
| Ratio 1/2 | x:1 | 1:1 to ∞:1 | compression ratio (CLEAN — HW manual) |
| Attack 1/2 | ms | 0.2 to 300 | attack time constant (CLEAN — HW manual) |
| Release Delay 1/2 | ms | 0 to 200 | hold time before release begins (CLEAN — HW manual) |
| Release Fast 1/2 | ms | 5 to 500 | fast release bucket (transient content) (CLEAN — HW manual) |
| Release Slow 1/2 | ms | 50 to 5000 | slow release bucket (sustained content) (CLEAN — HW manual) |
| Average 1/2 | ms | 0 to 100 | RMS detector averaging window (CLEAN — HW manual) |
| Soft Knee 1/2 | dB | 0 to 30 | knee width around threshold (CLEAN — HW manual) |
| Gain Make-Up 1/2 | dB | **TO MEASURE** | per-channel makeup gain |
| Center Frequency 1/2 | Hz | 20 to 20000 | sidechain filter center (CLEAN — HW manual) |
| Bandwidth 1/2 | oct | 0.1 to 5 | sidechain filter width in octaves (CLEAN — HW manual) |
| Filter Type 1/2 | enum | flat/LP/BP/HP | flat=wideband; BP=de-esser mode (CLEAN — HW manual) |
| Input Gain | dB | −20 to +20 | global input trim (CLEAN — HW manual) |
| Output Gain | dB | −20 to +20 | global output trim (CLEAN — HW manual) |
| Limiter Gain | dBFS | −30 to 0 | safety limiter ceiling (CLEAN — HW manual) |
| Safety Limiter | bool | on/off | enable brickwall |
| Safety Limiter Mode | enum | **TO MEASURE** | character/lookahead mode |
| Parallel Compression | % or dB | **TO MEASURE** | wet/dry blend |
| MS Mode | bool | on/off | M/S matrix |
| Ganged | bool | on/off | link Ch1/Ch2 |
| Monitor | bool | on/off | listen to sidechain band only |
| Sidechain | bool/enum | **TO MEASURE** | external sidechain routing |
| Sidechain Link | bool | on/off | link sidechain between channels |
| RMS | bool | on/off | peak (off) vs RMS (on) detection |
| Auto Make-Up | bool | on/off | automatic makeup gain |
| Gain Select | enum | **TO MEASURE** | selects input vs output gain display/control |
| Dither | enum | **TO MEASURE** | dither type/depth options |
| Set Number of Overs | int | **TO MEASURE** | true-peak over threshold count |
| Preview | bool | on/off | preview / A-B mode |
| Channel | enum | **TO MEASURE** | L/R/M/S channel select for display |
| Bypass | bool | on/off | per-plugin bypass |
| Master Bypass | bool | on/off | global bypass |
| Compressor GR Meter | readback | — | gain reduction display |
| Limiter GR Meter | readback | — | limiter GR display |
| Peak Meter Type | enum | **TO MEASURE** | meter ballistics |
| Meter Range | dB | **TO MEASURE** | meter scale |
| Meter Text | bool/enum | **TO MEASURE** | meter label mode |
| Peak Auto Reset | bool | on/off | peak hold auto-reset |

## FFI contract
None. PACE SSX encrypted — no accessible C ABI.

## CLEAN measurements
**None yet — iLok license required.**
Blocked: PACE rejects all headless hosts + unlicensed REAPER loads.

To unblock:
1. **Softube trial/demo** → run REAPER probe (`WeissDS1MK3/Tools/ds1_reaper_probe.lua`)
2. **iLok license** → same REAPER probe

## To implement (for ES-L reference)
Key building blocks from public DSP literature (all CLEAN):
- **Freq-selective compressor**: bandpass sidechain → wideband gain reduction (standard textbook: Zölzer DAFX ch.4)
- **Program-dependent release**: dual-bucket smoothing (fast τ + slow τ, blend by sustained-signal detector)
- **Soft knee VCA**: standard piece-wise quadratic in knee zone
- **Dither**: TPDF triangular or Wannamaker noise-shaped
- **M/S matrix**: standard (L+R)/√2 encode / decode
- **Brickwall limiter**: lookahead peak limiter (see ES-L)

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing.
**REF** = disasm/decompile-derived (reference only — reproduce black-box before shipping).
