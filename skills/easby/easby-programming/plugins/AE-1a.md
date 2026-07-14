# AE-1a — Naturl Audio (Active program EQ)

| | |
|---|---|
| Vendor / ver | Naturl Audio · v0.1.0 · VST 3.8 · **no DRM** |
| Type | Program/"tone" EQ — Baxandall shelves + 6-band **Active (ERB-Q, JFET, Air)** presence + WDF bass-resonance |
| Tech | JUCE 8 C++ shell → Rust `tone` crate via flat C FFI (`tone_*`, 110 exports); WebKit UI. Shared engine with AE-1b/p — variant set by `AE1VariantManifest` |
| Binary | universal Mach-O bundle, **not stripped** (~45.8k syms); CID `…4E414E414354`; leaked: `ae1::processor`, `tone::baxandall::eq`, `tone::bass_resonance::eq` (WDF circuit model) |
| Provenance | curves/Q/tables/latency = **CLEAN** (FFI + pedalboard measure); struct field map + per-sample chain = **REF** (r2/Ghidra) |
| Measured on | v0.1.0 · 48 kHz · `Tools/ae1_ffi.py` (direct FFI) + `Tools/ae1_pb.py` (pedalboard 0.9.17) · 2026-06-22 |
| Source | `private-research/AE-1/` — `docs/algorithm-decode.md`, `decomp/{dsp.c,ffi-surface.md,set_params_full.txt}`, `Tools/ae1_*.py` |

## What makes it the "a" variant (CLEAN)
75 VST3 params. The **active/modern** voicing: 6-band Presence with **ERB-proportional Active Q**,
per-band **JFET** option, an extra **Air band**, and the widest continuous freq ranges. Bass/treble
shelf + bass-resonance are fixed (not exposed). Same `tone` DSP as b/p (default-params + all band
tables byte-identical; identical FFI settings → bit-identical output).

## Signal chain (REF, confirmed CLEAN end-to-end)
```
in → pre Baxandall (bass+treble shelf + active shelf)
   → if M/S: presence on M=0.5(L+R), S=0.5(L−R); else presence on L,R  (6-band parametric)
   → post Baxandall
   → BassResonanceEQ (WDF inductor bell, min-phase, LAST)  → out + true-peak meter
```

## Per-stage (tag each)
- **Baxandall shelves** (CLEAN): symmetric boost/cut, linear-in-dB w/ a 33-step ±6 dB ladder. Bass corner
  {16,32,64,128} Hz, treble {20–60 kHz}. Gentle — bass +6 → +4.4@20Hz/+1.9@50/+0.7@100; treble +6 →
  +1.2@8k/+2.1@12k/+2.95@16k. Active shelves use musical-note centers (16.35 Hz–67 kHz).
- **Presence 6-band** (CLEAN): each band `*_mix` = gain (±6 dB), clean bell at selected center.
  **Active Q = ERB(fc)/divisor** (measured @351 Hz: ERB/8→Q0.70, ERB/5→Q1.12, ERB/3→Q1.87, ERB→Q5.60).
  Bands: Low 200–770, Low-Mid 570–1600, Mid 1480–3150, Hi-Mid 2500–7050, Hi 5300–15500, **Air ~3.6–33 kHz**.
- **Bass Resonance** (REF model / CLEAN curve): physically-modeled **WDF circuit** (Thevenin source +
  inductor w/ DCR + JFET/Diamond buffer), not a biquad. Min-phase bell, Q≈1.7 @ Q=1.0; +6 → ~+5.7 dB.
- **JFET / Makeup character** (CLEAN): **no measurable harmonics in v0.1.0** (JFET on/off, makeup
  Digital/Tube/Transformer all null on a 1k tone) — modeled but inert. Shipped behavior = clean linear EQ.

## Parameters (CLEAN)
75 params; all `presence_*` + `input/output` (±24 dB), `reference_level` (−24/−18/−12/−6/0 dBFS),
`oversampling` (Off/2x/4x/8x/16x), `bypass`. Presence: per-band on/off, M & S band toggles, `*_mix`
(±6 dB), `*_active_q` (ERB/13…ERB), `*_jfet`, `*_freq` (wide continuous), + Side mirror. Full dump:
`docs/algorithm-decode.md`. ToneParams (616 B) field map: `decomp/ffi-surface.md` (REF).

## FFI contract (CLEAN — drives the real DSP, no host)
`ctypes.CDLL(binary)`; names drop leading `_`. AArch64: f64 in d0, i32 in w1; SR in d0.
- `tone_create(sample_rate:f64) -> *mut handle` (~152 KB)
- `tone_default_params() -> ToneParams[616]` — **struct-return (sret)**; ctypes needs a `Structure`
  restype or it segfaults. Mutate fields by offset, then:
- `tone_set_params(handle, *const ToneParams)` — **applies immediately (no separate commit)**
- `tone_process_audio_stereo_f64(handle, inL*, inR*, outL*, outR*, n)` — f64, **separate in/out**
- `tone_set_sample_rate(h,f64)`, `tone_reset(h)`, `tone_get_latency_samples(h)`→976@48k (internal lane)
- introspection (pure, CLEAN tables): `tone_<grp>_count/hz/db/name/default`.
Working harness: `Tools/ae1_ffi.py`. Full 110-fn list: `decomp/ffi-surface.md`.

## To implement (CLEAN-only for product)
Baxandall shelf pair (symmetric, gentle, dB-ladder) + per-band parametric bells with
**ERB-proportional Q** (band BW = ERB(fc)/n) + a min-phase low-resonance bell. All achievable from
the measured curves + public DSP (Baxandall, RBJ bells, ERB formula Glasberg&Moore). Skip the inert
v0.1.0 nonlinear paths. REF rows (WDF model, struct map) are reference only.

---
Provenance: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (reproduce black-box before shipping).
