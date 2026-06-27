# soothe3 — oeksound (dynamic resonance suppressor, spectral)

| | |
|---|---|
| Vendor / ver | oeksound · VST3 (soothe3) |
| Type | Dynamic spectral resonance suppressor (frequency-selective, self-adaptive de-resonator) |
| Tech | C++ (`Soothe3AudioProcessor`, kali/kone framework); PACE-iLok (Eden) |
| Binary | arm64; `__Pace_Eden.bundle`; **1834 syms** (RTTI present) but PACE-encrypted text → static **WALL** for DSP |
| Provenance | **CLEAN** (REAPER param surface + latency; iLok authorized). No REF (PACE). |
| Measured on | REAPER · 48 kHz · `mcdsp_sysid.py` · 2026-06-26 |
| Source | `private-research/McDSP_PACE/{Tools,work}` |

## Type note — spectral, mostly param-surface CLEAN
soothe3 is a self-adaptive spectral processor: it tracks the input spectrum and dynamically cuts resonant
peaks. The transfer is **signal-dependent** → a static sweep/THD probe does not characterize the algorithm
(open question). What is fully CLEAN: the **147-param surface** (8 processing bands + per-band/per-channel
controls), the **norm→real maps**, and **latency**. The spectral kernel itself is PACE-walled → REF impossible.

## Latency (CLEAN)
PDC = **2304 samples** at default (Linear-phase OFF, Quality normal). Linear-phase + Quality + Low-latency
toggles will change this (FFT-based linear-phase mode adds the FFT window) — re-measure per mode.

## Parameters (CLEAN — selected, 147 total)
| param | unit | range / map |
|---|---|---|
| Depth | — | 0 … 10 (overall suppression amount) |
| Detail (Sharpness) | — | 0 … 10 (how narrow/selective the cuts) |
| Attack | — | 0 … 10 (ms-ish, normalized) |
| Release | — | 0 … 10 |
| Mode | enum | **soft / hard** (norm ≥ ~0.6 → hard) |
| Quality | enum | normal / … |
| Linear phase | bool | off → IIR-ish low latency; on → FFT lin-phase (bigger PDC) |
| Low latency | bool | reduces PDC |
| Detail/Attack/Release tilt (low/high) | ×  | 0.x … x (spectral tilt of each control) |
| Band 1..8: used/enabled/frequency/depth/q/slope/focus/channels/shape | — | per-band; shapes incl. Low cut / Bell / High cut |
| Stereo mode / link / focus | — | L/R, M/S, link % |
| Sidechain / Sidechain listen | bool | external key |
| Mix / Wet trim / Out trim / Max cut / Delta | — | output |
| (multichannel: LR/Center/LFE/Surround/Ceiling groups, 16 channel enables) | — | surround-capable |

## Why / design rationale
- **Depth + Detail** → amount vs selectivity: Depth sets how hard resonances are pulled down, Detail sets how
  surgically narrow the dynamic cuts are → "soothe harshness without dulling".
- **Per-band tilt of Attack/Release/Detail (low vs high)** → lets the de-resonator react faster/sharper in
  one spectral region than another (e.g. tame sibilance fast up top, gentle in the low-mids).
- **Linear-phase option** → mastering use (no phase smear) at the cost of latency; IIR for tracking.
- soft vs hard Mode → transparent vs aggressive suppression character.

## To implement
Public-DSP equivalent = adaptive spectral subtraction / dynamic multi-band de-resonance: STFT analysis →
per-bin/per-band threshold tracking the smoothed spectral envelope → dynamic gain reduction proportional to
local peak-over-envelope, with attack/release ballistics and selectable narrowness (Detail). Linear-phase
mode = symmetric FIR from the gain spectrum. CLEAN spec = param surface + this public method; exact oeksound
kernel is PACE-walled (no REF).

## Open questions
- Exact peak-detection/threshold law (per-bin vs per-band, how the spectral envelope is estimated).
- Per-mode latency (lin-phase / quality / low-latency variants).

---
**CLEAN** = REAPER black-box of a licensed plugin (param surface + PDC). **No REF** (PACE wall).
