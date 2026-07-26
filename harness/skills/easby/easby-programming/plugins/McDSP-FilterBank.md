# FilterBank E606 / F202 / P606 — McDSP (EQ / Filter; shared McDSP filter designer)

| | |
|---|---|
| Vendor / ver | McDSP · VST3 |
| Type | Linear EQ/filter — F202 = HPF+LPF filter, P606 = full parametric EQ, E606 = EQ + HPF/LPF + LF shelf |
| Tech | C++; PACE-iLok (Eden) all formats |
| Binary | arm64; `__Pace_Eden.bundle`; ~6 syms → static **WALL** |
| Provenance | **CLEAN** (REAPER param sweeps + impulse; iLok authorized). No REF (PACE). |
| Measured on | REAPER · 48 kHz · `mcdsp_sysid.py` · 2026-06-26 |
| Source | `private-research/McDSP_PACE/{Tools,work}` |

## Type note (linear EQ → the param surface + freq/Q/gain ladders ARE the spec)
PDC = **0** on all three → IIR (minimum-phase), not linear-phase FIR. Log-swept-sine deconvolution at
−12 dB had low SNR after PDC-trim (noisy magnitude floor) → the **clean spec is the norm→real ladders**
recovered by direct sweeps (a linear EQ is fully defined by its freq/Q/gain maps + topology).

## Shared filter designer
The **freq ladder is identical across all three FB plugins and matches MC2000's crossover ladder**
(20 → 20000 Hz, log, same 11-point lattice) → one shared McDSP filter/coefficient designer.

## Parameters (CLEAN — norm→real)
### F202 (filter)
| param | unit | range / map |
|---|---|---|
| HPF / LPF Frequency | Hz | 20 … 20000, log |
| HPF / LPF Slope | enum | 6 / 12 / 18 / 24 dB/oct |
| HPF / LPF Q | — | resonance |
| HPF / LPF Enable | bool | |
| Input / Output | dB | trim |

### P606 (full parametric, ≥6 bands P1..P6)
| param | unit | range / map |
|---|---|---|
| Pn Frequency | Hz | 20 … 20000, log |
| Pn Gain | dB | **−15 … +15**, linear |
| Pn Q | — | **0.1 … 10** (full parametric range) |
| Pn Enable | bool | |

### E606 (EQ: HPF/LPF + LF shelf + parametric bands)
| param | unit | range / map |
|---|---|---|
| HPF/LPF Frequency | Hz | 20 … 20000 log |
| HPF/LPF Slope | enum | 6 / 12 dB/oct (narrower than F202) |
| LF Frequency / Gain / Peak / Slope / Dip | — | LF shelf w/ peak+dip shaping |
| Pn Frequency / Gain / Q | dB / Hz | Gain ±15, **Q 0.4 … 4.0** (musical range, narrower than P606) |

## Why / design rationale
- **P606 Q 0.1–10** = surgical-to-broad parametric; **E606 Q 0.4–4.0** = musical "vibe" EQ → same designer,
  two voicings via param-range gating (mirrors the AE-1a/b/p one-engine, multi-subset pattern).
- IIR / 0-latency → tracking-friendly; min-phase (not linear) → natural EQ feel, no pre-ring.
- F202 selectable 6–24 dB/oct slopes → from gentle tone-shaping to brickwall-ish HP/LP.

## To implement
Min-phase biquad cascade: parametric bells (freq log, gain ±15, Q per voicing), HP/LP with selectable
order (6/12/18/24), LF shelf with peak/dip (E606). Shared coefficient designer across bands. CLEAN-only.

---
**CLEAN** = REAPER black-box of a licensed plugin. **No REF** (PACE wall).
