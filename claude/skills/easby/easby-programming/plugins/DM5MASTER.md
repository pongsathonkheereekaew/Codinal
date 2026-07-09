# DM5MASTER — livemau5 / deadmau5 (one-knob mastering maximizer)

| | |
|---|---|
| Vendor / ver | livemau5 (deadmau5) · 0.1.0 (early) |
| Type | Mastering maximizer / brickwall: heavy makeup gain → odd-harmonic soft-clip → ceiling ≈ 0 dBFS |
| Tech | JUCE C++ (built `/Users/livemau5/Desktop/AF/…`) + WebKit UI; 116k syms, NOT stripped, no PACE |
| Binary | **arm64-only** (no x86_64 slice) |
| Provenance | **CLEAN** (pedalboard, black-box). No disasm. No exposed params → behavior-only. |
| Measured on | DM5MASTER 0.1.0 · 48 kHz · pedalboard 0.9.17 · 2026-06-26 |
| Source | `private-research/CleanMisc/Tools/cleanmisc_sysid.py` |

## Signal chain (inferred from behavior)
```
x → [large input/makeup gain ~+22..+25 dB] → [odd-harmonic soft-clipper / maximizer]
  → [brickwall ceiling ≈ −0.05 dBFS] → out
```
**Only `bypass` is host-exposed** — all controls live in the internal web UI (preset/macro driven). Black-box = the default-state transfer.

## Per-stage formula (CLEAN, default state)
- **Makeup / gain** (CLEAN): small inputs lifted hard. −40 dB tone → out −20.4 dB rms (**+22.6 dB** makeup). Slow ramp slope @ 0 ≈ ×25 (≈ +28 dB small-signal).
- **Ceiling** (CLEAN): full-scale ramp output peak = **−0.05 dB**; loud 1 kHz @ 0.99 → out peak **−0.065 dB** → hard brickwall just under 0 dBFS.
- **Distortion = odd-dominant soft-clip** (CLEAN): 1 kHz THD measured 22–35 % with **H3 ≫ H2** (H3 ≈ −10..−14 dBc, H2 ≈ −51..−65 dBc) → symmetric (odd-only) clipper, tube/clip character, very aggressive at default.
- **Latency**: impulse peak un-shifted (pedalboard PDC-compensated) — true lookahead unknown (read REAPER `pdc` if needed).

## Why / design rationale
- One-knob "make it loud" mastering tool: fixed aggressive maximizer voicing (deadmau5's loudness target) — push gain into a near-0 brickwall with built-in odd-harmonic saturation for density. v0.1.0 = minimal surface, opinionated default.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | | **only host param**; all DSP controls internal (web UI) |

## Open questions
- All internal controls (amount/ceiling/character) not host-automatable → can't sweep via pedalboard. To map them: drive the web UI, or check if AU exposes more. True-peak vs sample-peak ceiling untested. Exact lookahead via REAPER `pdc`.

## To implement
Maximizer = makeup gain → odd waveshaper (e.g. `x - x³/3`-class / tanh-odd) → lookahead brickwall ceiling at ≈ −0.05 dBFS. Behavior-target only; sweepable params unavailable. CLEAN.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing.
