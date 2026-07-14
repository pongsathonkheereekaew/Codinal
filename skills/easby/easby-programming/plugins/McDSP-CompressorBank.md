# CompressorBank CB101/CB202/CB303 — McDSP (Compressor; shared McDSP engine)

| | |
|---|---|
| Vendor / ver | McDSP · VST3 (v6-era) |
| Type | Compressor (CB101 = comp; CB202/CB303 add pre-filter/EQ-sidechain bands) |
| Tech | C++; PACE-iLok (Eden) on every format |
| Binary | arm64; `__Pace_Eden.bundle`; ~6 exported syms → static **WALL** (no REF possible) |
| Provenance | **CLEAN** (black-box via REAPER, iLok authorized). No REF (PACE-encrypted). |
| Measured on | REAPER (notarized host) · 48 kHz · `mcdsp_reaper_probe.lua`+`mcdsp_sysid.py` · 2026-06-26 |
| Source | `private-research/McDSP_PACE/{Tools,work}` |

## Shared-engine verdict (KEY finding)
CB101 ≡ CB202 ≡ CB303 share **one identical compressor core** — byte-identical static GR curve and
identical param norm→real maps. CB202/CB303 only add a sidechain **Pre-Filter** (type + Frequency + Q)
and more bands; the gain-computer/detector is the same. **The same core also drives MC2000 (MC202/303/404)**
— MC band-1 sweeps are identical to CB (see McDSP-MC2000.md). One McDSP dynamics engine, decode-once.

## Signal chain
```
x → [sidechain pre-filter (CB202/303)] → detector → gain computer (thr/ratio/knee/bite) → smoother(atk/rel, TC type) → makeup → y
```

## Parameters (CLEAN — REAPER norm→real sweeps, 48 kHz)
| param | unit | range / map | notes |
|---|---|---|---|
| Threshold | dBFS | −48 … 0, **linear** in norm | |
| Comp (Ratio) | :1 | 1 … 10, linear | label "Comp" = ratio |
| Knee | dB | −10 … +15, linear | signed; negative = harder |
| Attack | ms | 0.25 … 250, **exponential** | |
| Release | ms | 25 … 2500, **exponential** | |
| Bite | — | 1 … 10, linear | transient-emphasis (McDSP "BITE") |
| Time Constant | enum | Type 1 / Type 2 / Auto | detector ballistics mode |
| Output | dB | makeup/trim | |
| Key Enable / Key Listen | bool | external sidechain | |
| Pre Filter / Type / Frequency / Q | — | CB202/303 only; Freq 20–20k log | sidechain shaping |
| Phase / Phase Right | bool | polarity (per ch) | |
| Wet / Delta | — | mix / delta-listen | |

PDC = **0 samples** (no oversampling / lookahead).

## CLEAN measurements
- Static GR curve identical across CB101/202/303 (default state shows makeup-dominated region then hard
  limiting at −3/0 dB cells: gr −2.09 / −240). The curve shape is set by Threshold/Comp/Knee per the maps above.
- Attack 0.25–250 ms exp, Release 25–2500 ms exp (calibration sweeps).

## Why / design rationale
- **Bite** → adds high-frequency transient emphasis to the detector → preserves attack/snap while compressing
  body — McDSP's signature "punch" control.
- **Time Constant {Type1/2/Auto}** → selectable detector ballistics (peak-ish vs RMS-ish vs program-adaptive)
  → one comp covers fast peak control and smooth leveling.
- **Pre-filter sidechain** (CB202/303) → frequency-conscious compression (e.g. de-ess, de-mud) without a
  separate plugin.

## To implement
Feed-forward dB-domain compressor: linear Threshold, ratio 1–10, signed knee, exp attack/release smoother,
selectable ballistics, HF-tilt detector for "Bite", optional sidechain biquad. CLEAN-only — McDSP code is PACE-walled.

---
**CLEAN** = black-box measurement of a licensed plugin in REAPER. **No REF** (PACE-encrypted, static wall).
