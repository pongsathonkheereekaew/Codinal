# AE-1b — Naturl Audio (Baxandall tone-shaper)

| | |
|---|---|
| Vendor / ver | Naturl Audio · v0.1.0 · VST 3.8 · **no DRM** |
| Type | Broad **Baxandall bass/treble** program EQ (shelves only — no presence, no resonance) |
| Tech | JUCE 8 C++ shell → Rust `tone` crate via flat C FFI (`tone_*`, 110 exports); WebKit UI. Shared engine with AE-1a/p — variant set by `AE1VariantManifest` |
| Binary | universal Mach-O bundle, **not stripped** (~45.8k syms); distinct hash from a/p (same engine, different manifest/UI) |
| Provenance | curves/tables = **CLEAN** (FFI + pedalboard); per-sample chain + struct map = **REF** (r2/Ghidra) |
| Measured on | v0.1.0 · 48 kHz · `Tools/ae1_ffi.py` + `Tools/ae1_pb.py` (pedalboard 0.9.17) · 2026-06-22 |
| Source | `private-research/AE-1/` — `docs/algorithm-decode.md`, `decomp/{dsp.c,ffi-surface.md}`, `Tools/ae1_*.py` |

## What makes it the "b" variant (CLEAN)
**Only 16 VST3 params** — the minimal console tone tilt. Exposes the Baxandall section + makeup:
`bass`/`treble` (±6 dB, 0.25 step), `bass_freq` (active 16.35–1050 Hz), `treble_freq` (1050–66980 Hz),
`passive_bass_freq` (16/32/64/128 Hz), `passive_treble_freq` (20–60 kHz), `bax_engine`
(Legacy Passive / Op-Amp Active), `baxandall`/`baxandall_bass`/`baxandall_treble` on/off,
`makeup_gain` (Digital/Tube/Transformer), input/output (±24), reference_level, oversampling, bypass.
**No presence section, no bass-resonance.** Same `tone` DSP as a/p (default-params + tables identical).

## Signal chain (REF, confirmed CLEAN)
```
in → Baxandall bass+treble shelf (pre + post; presence/resonance disabled by manifest) → out
```

## Per-stage (CLEAN)
- **Baxandall bass shelf** (corner default 32 Hz): symmetric, gentle. Knob ±N dB is linear-in-dB:
  | bass | @20Hz | @50Hz | @100Hz | @200Hz |
  |---|---|---|---|---|
  | +6 | +4.35 | +1.86 | +0.63 | +0.18 |
  | −6 | −4.34 | −1.85 | −0.63 | −0.18 |
  | ±3 | ≈ ±2.18 | ±0.91 | ±0.30 | ±0.09 |
- **Baxandall treble shelf** (corner default 16.74 kHz active): treble +6 → +0.82@8k/+1.81@12k/+2.76@16k;
  −6 → −0.92@8k/−2.02@12k/−3.16@16k. Slight ~−0.36 dB 1 kHz interaction when boosting (real Baxandall net).
- **bax_engine** = Legacy Passive vs Op-Amp Active: Op-Amp Active is the default & measures as above.
  (Legacy Passive toggled live showed a large attenuation — likely a re-prime artifact, not a confirmed
  curve; see open questions.)
- **Makeup** Digital/Tube/Transformer: no measurable THD change on a 1k tone in v0.1.0 (modeled, inert).

## FFI contract (CLEAN — identical engine to AE-1a/p)
`tone_create(sr:f64)` → `tone_default_params()` (sret Structure) → mutate ToneParams → `tone_set_params`
→ `tone_process_audio_stereo_f64(h, inL,inR, outL,outR, n)` (f64, separate in/out). Latency 976@48k
(internal lane). For b, the bass/treble live at ToneParams +0x10/+0x14 (gain idx into the 33-step ±6 dB
ladder) and +0x18/+0x1c/+0x20/+0x24 (freq indices). Full map: `decomp/ffi-surface.md` (REF). Harness:
`Tools/ae1_ffi.py`.

## To implement (CLEAN-only)
A symmetric Baxandall bass+treble shelf pair with a stepped ±6 dB gain ladder and selectable corner
freqs — straight from the measured curves + public Baxandall/shelving DSP. Skip the inert makeup
character. REF rows reference-only.

---
Provenance: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (reproduce black-box before shipping).
