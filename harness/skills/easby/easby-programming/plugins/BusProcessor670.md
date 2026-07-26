# Bus Processor 670 — Softube (Fairchild-670-style vari-mu bus compressor)

| | |
|---|---|
| Vendor / ver | Softube ("Flow Mastering Suite") · VST3 |
| Type | Vari-mu bus compressor + transformer/tube saturation + spatializer (3 toggled stages) |
| Tech | C++; PACE-iLok (Eden) |
| Binary | arm64 (`BusProcessor670_VST_AU_Protect`); `__Pace_Eden.bundle`; 13 syms → static **WALL** |
| Provenance | **CLEAN** (REAPER, iLok authorized). No REF (PACE). |
| Measured on | REAPER · 48 kHz · `mcdsp_sysid.py` · 2026-06-26 |
| Source | `private-research/McDSP_PACE/{Tools,work}` |

## NOT the McDSP engine
Separate vendor (Softube). Vari-mu control law: Threshold/Time/Calibration are **0–10 vari-mu units (not
dB/ms)**, dual mono L/R channels, Comp Mode Classic/Modern. Strong program-dependent GR (default staircase
showed −7 → −31 dB across −30→−3 dBFS in). PDC = **7 samples** (light oversampling).

## Signal chain
```
x → [Compressor (vari-mu, L/R)] → [Saturator (transformer+tube)] → [Spatializer (width/mono-bass/air)] → y
   (each stage independently on/off)
```

## Parameters (CLEAN — norm→real)
| param | unit | range / map | notes |
|---|---|---|---|
| L/R Input Gain | dB | drive into compressor | |
| L/R Threshold | vari-mu | 0 … 10 | not dB — vari-mu control |
| L/R Time | enum-ish | 1 … 6 | Fairchild 6-position time constant |
| L/R Output Gain | dB | makeup | |
| Calibration | — | 0 … 10 | tube/level calibration |
| Knee | enum | **Hard → 1…9 → Soft** | |
| Comp Mode | enum | **Classic / Modern** | |
| S/C Link | % | 0 … 100 | L/R sidechain link |
| S/C Low Cut | Hz | 10 … (HPF) | sidechain HPF |
| S/C Tone | — | sidechain tilt | |
| Ext S/C | bool | external key | |
| Comp. Wet/Dry | % | parallel comp | |
| **Transformer** | — | 0 … 10 | saturation: transformer drive |
| **Tube** | — | 0 … 10 | saturation: tube drive |
| Sat. Tone / Sat. Wet/Dry | — | saturation tilt / parallel | |
| Air | dB | HF air shelf | |
| Width / Mono Bass | % / Hz | spatializer | |
| Compressor / Saturator / Spatializer | bool | stage enables | |
| Mid/Side Mode / Link Channels | enum | routing | |

## Why / design rationale
- **Vari-mu (Threshold/Time as 0–10/1–6)** → emulates the 670's tube-bias gain-cell where "threshold" is a
  bias point, not a hard dB knee → smooth, level-dependent, program-adaptive compression.
- **6-position Time** → classic Fairchild dual-time-constant program dependence (fast+slow recovery).
- **Transformer + Tube as separate drives** → independent iron vs valve harmonic coloration.
- **Spatializer (width/mono-bass/air)** → mastering-bus finishing (keep lows mono, add top air, widen).

## To implement
Vari-mu detector→gain-cell with 6 program-dependent time constants, Classic/Modern topologies, optional
transformer+tube saturation stages, M/S + width + mono-bass + air shelf. Light OS (≈7-sample PDC).
CLEAN-only; Softube code PACE-walled.

---
**CLEAN** = REAPER black-box of a licensed plugin. **No REF** (PACE wall).
