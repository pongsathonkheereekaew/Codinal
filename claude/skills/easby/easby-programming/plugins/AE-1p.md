# AE-1p — Naturl Audio (Passive Pultec-style program EQ)

| | |
|---|---|
| Vendor / ver | Naturl Audio · v0.1.0 · VST 3.8 · **no DRM** |
| Type | Passive program EQ — 6-band **Pultec-style presence (stepped freq, W/M/N Q, M/S, Drive)** + WDF bass-resonance |
| Tech | JUCE 8 C++ shell → Rust `tone` crate via flat C FFI (`tone_*`, 110 exports); WebKit UI. Shared engine with AE-1a/b — variant set by `AE1VariantManifest` |
| Binary | universal Mach-O bundle, **not stripped** (~45.8k syms); distinct hash from a/b (same engine, different manifest/UI) |
| Provenance | curves/Q/tables/latency = **CLEAN** (FFI + pedalboard); per-sample chain + struct map = **REF** (r2/Ghidra) |
| Measured on | v0.1.0 · 48 kHz · `Tools/ae1_ffi.py` + `Tools/ae1_pb.py` (pedalboard 0.9.17) · 2026-06-22 |
| Source | `private-research/AE-1/` — `docs/algorithm-decode.md`, `decomp/{dsp.c,ffi-surface.md}`, `Tools/ae1_*.py` |

## What makes it the "p" variant (CLEAN)
68 VST3 params. The **passive/Pultec** voicing: 6-band Presence with **stepped Pultec frequencies**,
**passive Q (W/M/N)**, M/S routing, a per-band **Drive** control, plus the **Bass Resonance** (inductor)
section. **No Active-Q, no JFET, no Air band** (that's the "a" variant). Bass/treble shelf knobs not
exposed (fixed). Same `tone` DSP as a/b (default-params + all band tables byte-identical).

## Signal chain (REF, confirmed CLEAN end-to-end)
```
in → pre Baxandall (fixed shelves)
   → if presence_m_s: presence on M=0.5(L+R), S=0.5(L−R); else L,R  (6-band, passive-Q bells)
   → post Baxandall
   → BassResonanceEQ (WDF inductor bell, min-phase, LAST)  → out + true-peak meter
```

## Per-stage (CLEAN)
- **Presence 6-band** (CLEAN): each band `*_mix` = gain (±6 dB), clean min-phase bell at the selected
  stepped center. Bands & freq tables: Low 200–770, Low-Mid 570–1600, Mid 1480–3150, Hi-Mid 2500–7050,
  Hi 5300–15500 Hz (Pultec-style discrete steps). **Passive Q** measured @2 kHz: **W→0.94, M→1.59, N→3.61**.
  M/S: with L/R routing, L-only input → R output silent (no crosstalk); M/S routing splits to mid/side.
- **Bass Resonance EQ** (REF model / CLEAN curve): physically-modeled **WDF circuit** (Thevenin +
  inductor w/ DCR + JFET/Diamond buffer). Min-phase bell on selected freq:
  | freq | peak @ +6 |
  |---|---|
  | 30 Hz | +5.83 @30.0 | 50 | +5.72 @49.8 | 60 | +5.70 @60.1 | 80 | +5.58 @80.6 | 125 | +5.37 @126 |
  Q≈1.7 @ Q-knob 1.0 (range 0.5–2.5). Inductor Tight/Modern/Alive: **no steady-state magnitude diff** (dynamic only).
- **Presence Drive** (0–60 dB): **no measurable harmonics in v0.1.0** even at 60 dB / centered hot tone
  → inert/placeholder (or needs active-device path not enabled by the passive manifest). Shipped behavior
  = clean linear EQ.

## Parameters (CLEAN)
68 params: input/output (±24 dB), reference_level, oversampling, bypass; per-band presence on/off
(M & S), `*_mix` (±6 dB, ~0.25 step), `*_drive` (0–60 dB), `*_q` (W/M/N), `*_freq` (stepped Pultec) +
Side mirror; `bass_resonance` on/off, `_gain` (0–6 dB), `_q` (0.5–2.5), `_freq` (30–125 Hz), `_inductor`
(Tight/Modern/Alive). Full dump: `docs/algorithm-decode.md`. ToneParams field map: `decomp/ffi-surface.md` (REF).

## FFI contract (CLEAN — identical engine to AE-1a/b)
`tone_create(sr:f64)` → `tone_default_params()` (**sret Structure**) → mutate ToneParams → `tone_set_params`
(applies immediately) → `tone_process_audio_stereo_f64(h, inL,inR, outL,outR, n)` (f64, separate in/out).
Bass-resonance master enable = ToneParams **+0x240** (gates the WDF), gain f64 +0x248, q f64 +0x250,
freq idx +0x258, inductor +0x25c. Latency 976@48k (internal lane). Harness `Tools/ae1_ffi.py`; full
list `decomp/ffi-surface.md`.

## To implement (CLEAN-only)
6-band parametric bells with **fixed Pultec freq steps** + 3-way Q (≈0.94/1.59/3.61), M/S routing, and a
min-phase low-resonance bell (Q≈1.7) — from measured curves + public DSP (RBJ peaking, Pultec layout).
Skip the inert v0.1.0 Drive/inductor-character. REF rows (WDF model, struct map) reference-only.

---
Provenance: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (reproduce black-box before shipping).
