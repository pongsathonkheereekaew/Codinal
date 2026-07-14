# MC2000 MC202/MC303/MC404 — McDSP (Multiband Compressor; shared McDSP engine)

| | |
|---|---|
| Vendor / ver | McDSP · VST3 |
| Type | Multiband compressor — MC202 = 2-band, MC303 = 3-band, MC404 = 4-band |
| Tech | C++; PACE-iLok (Eden) all formats |
| Binary | arm64; `__Pace_Eden.bundle`; ~6 syms → static **WALL** |
| Provenance | **CLEAN** (REAPER, iLok authorized). No REF (PACE). |
| Measured on | REAPER · 48 kHz · `mcdsp_sysid.py` · 2026-06-26 |
| Source | `private-research/McDSP_PACE/{Tools,work}` |

## Shared-engine verdict
MC2000's per-band compressor is the **same McDSP dynamics core as CompressorBank** — band-1 sweeps are
byte-identical: Threshold −48…0 dB linear, Ratio 1–10, Attack 0.25–250 ms exp, Release 25–2500 ms exp,
plus the McDSP **BITE** + **Time-Constant** controls. The **crossover frequency ladder is identical to the
FilterBank filter-freq ladder** (20–20k log, same 11-point lattice). MC202/303/404 differ only in band count
(1/2/3 crossovers). → one McDSP engine spans CB*, MC*, FB* (decode-once family).

## Signal chain
```
x → N-band crossover (X-Over freqs) → per-band [comp core] → sum → output
```

## Parameters per band (CLEAN — norm→real)
| param | unit | range / map |
|---|---|---|
| Band n Threshold | dBFS | −48 … 0, linear |
| Band n Ratio | :1 | 1 … 10, linear |
| Band n Knee | dB | signed (as CB) |
| Band n Attack | ms | 0.25 … 250, exp |
| Band n Release | ms | 25 … 2500, exp |
| Band n BITE | — | transient emphasis |
| Band n TCType Group | enum | Type 1/2/Auto |
| Band n Gain / Solo / Enable | — | makeup / monitor / on |
| X-Over k Freq | Hz | 20 … 20000, **log** (same ladder as FilterBank) |
| Input Gain / Output Gain / Band Meter Mode | — | global |

PDC = **0 samples** (IIR crossover, no FIR/lookahead).

## CLEAN measurements
- Band-1 param maps identical to CB101/202/303 (confirms shared core).
- Crossover ladder identical to FilterBank freq ladder.
- Latency 0 → crossover is IIR (not linear-phase).

## Why / design rationale
- IIR crossover (0 latency) → low-latency tracking/mix use; trades phase-coherence for zero delay.
- Reusing the CB comp core per band → consistent "McDSP sound" mono→multiband; BITE keeps multiband
  compression from dulling transients.

## To implement
N-band IIR crossover (log freq ladder) → per-band CB-style feed-forward comp (linear thr, exp atk/rel,
BITE HF-tilt detector, selectable ballistics) → makeup → sum. CLEAN-only; McDSP code PACE-walled.

---
**CLEAN** = REAPER black-box of a licensed plugin. **No REF** (PACE wall).
