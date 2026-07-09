# FilterFreak1 — Soundtoys (analog multimode filter, x1)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Analog-modeled multimode resonant filter (single filter) + LFO/envelope/rhythm modulation |
| Tech | C++ VST3, shared Soundtoys framework (statically links one "Soundtoys" lib → one plugin per process). AAX = PACE; VST3 = pedalboard-hostable, no DRM wall. |
| Binary | universal VST3; not PACE-encrypted in the VST3 slice (loads headless in pedalboard). |
| Provenance | **CLEAN** — all numbers below are black-box measurement of the licensed VST3 + public filter-DSP literature. No disassembly. |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (harness `Tools/st_sysid.py`, `Tools/ff_probe.py`, `Tools/ff_refine.py`, `Tools/ff_order2.py`; out `Soundtoys/out/FilterFreak1_*.json`) |

## Signal chain
```
x → inputgain (±24 dB) → [Analog: input saturation] → multimode resonant filter
      (shape ∈ {LP,BP,HP,Notch}, fc, resonance, order=2..8 poles)
      ← modulated by {LFO (free Hz) | envelope follower | rhythm/sync}
  → [Analog: output saturation] → outputgain (±24 dB) → dry/wet mix → y
```

## Per-stage formula  (all CLEAN — black-box)
- **Multimode filter** (CLEAN): cascaded resonant SVF-class topology, four selectable shapes.
  - Slope ∝ `filterorder`: measured −12 dB/oct @ order 2, −24 @ order 3–4, −36 @ order 5–7, −48 @ order 8
    (≈ 6 dB/oct per pole; the order param is the **pole count**, odd orders read like the next even in magnitude
    slope). LP −3 dB corner tracks `frequency_hz` (e.g. order 2 set 1000 Hz → measured −3 dB @ 1004 Hz).
  - **Resonance law (CLEAN, crisp):** `resonance_db` param produces a peak boost of **exactly ½ its value** up
    to ~40: param 1→+0.52 dB, 10→+5.0 dB, 20→+10.0 dB, 40→+20.0 dB. Above ~40 it goes super-linear toward
    self-oscillation (60→+37, 120→+69, 180→+95 dB). So peak_dB ≈ 0.50·resonance_db (low/mid), accelerating near top.
  - **Cutoff law (CLEAN):** logarithmic. Measured −3 dB freq vs normalized param: 0→31 Hz, 0.2→81, 0.4→317,
    0.5→633, 0.6→1270, 0.8→5218, 1.0→19 kHz. ~2.0 oct per 0.2 norm = log taper over 20 Hz–20 kHz.
- **Analog vs Digital (`inoutmode`)** (CLEAN): the headline modeled behavior.
  - **Digital** = clean (passband THD ≈ 0 % even at 0 dBFS; ~0.25 % only when clipping the output).
  - **Analog** = adds input/output **saturation**: a 300 Hz tone in the LP passband (res 0) measured
    **THD 2 % @ −12 dBFS → 17.6 % @ 0 dBFS**, H2-dominant at low drive (H2 −60→−41 dB), H3 rising with level —
    i.e. a level-dependent, mostly-even-harmonic analog drive stage wrapping the filter.
  - **Self-oscillation:** at `resonance_db`=180, **Analog mode sustains** (silence/tick in → −31 dB sustained
    tone tail) while **Digital decays** (−53 dB). Analog mode's saturation supplies the limiting nonlinearity that
    lets the resonant pole sit on the oscillation boundary.
- **Latency** (CLEAN): reported 45 samples (0.94 ms @ 48k) in both modes — a small fixed processing/anti-alias delay.
- **Modulation** (CLEAN where free-running): `lfo_rate_hz` is a **free Hz** LFO (0.01–256 Hz) → fully measurable
  cutoff-sweep modulation, depth via `modulationdepth` (0–1). Envelope follower (`trigger`) and **rhythm/tempo-sync**
  (`tempo_bpm`, sync grid) need host transport → **UNMEASURED** in pedalboard (no transport); mark for REAPER.

## Why / design rationale (music ↔ code)
- **SVF multimode (LP/BP/HP/Notch) with selectable order** → one filter covers gentle tone-shaping (2-pole) to
  aggressive synth-style sweeps (8-pole/48 dB) → the classic "analog filter" creative-FX role (acid sweeps,
  vocal/synth movement), not a surgical EQ.
- **Resonance calibrated in dB of peak boost, ½:1 below self-osc** → predictable musical emphasis at a chosen
  frequency; the accelerating taper near the top gives a knob that "blooms" into self-oscillation like a real
  analog ladder, where the player *feels* the edge.
- **Analog mode = saturation wrapper (even-harmonic, level-dependent)** → musical "warmth/grit" and, crucially,
  the **soft-clip that tames the resonant peak** so max resonance self-oscillates without blowing up. This is the
  whole point of "Analog" vs "Digital": not a different filter math, but the nonlinear envelope around it.
- **Free-Hz LFO up to 256 Hz** → audio-rate modulation = FM/ring-mod-like timbres, beyond a normal sweep LFO →
  signals this is a *sound-design* filter (Soundtoys house style), not a mix-utility filter.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| inputgain_db | dB | −24..+24 | pre-filter trim; drives the Analog input saturation |
| outputgain_db | dB | −24..+24 | post-filter makeup |
| mix | % | 0..100 | dry/wet; 0 = pass-through |
| inoutmode | enum | Digital, Analog | **Analog = saturation + self-osc enable**; Digital = clean |
| frequency_hz | Hz | 20..20000 | cutoff; **log taper** |
| resonance_db | dB(of peak)/2 | 0..180 | peak boost ≈ ½ value (≤40), super-linear→self-osc above |
| filterorder | poles | 2..8 (int) | slope = 6 dB/oct·order (12/24/36/48 dB/oct @ 2/4/6/8) |
| filtershape | enum | Lowpass, Bandpass, Highpass, Notch | |
| modulationdepth | 0..1 | 0..1 | depth of the active modulator |
| trigger | bool | Off/On | envelope-follower trigger — **UNMEASURED** (needs program/transport context) |
| tempo_bpm | BPM | 30..240 | rhythm-sync rate — **UNMEASURED** (no transport in pedalboard) |
| lfo_rate_hz | Hz | 0.01..256 | **free-running LFO, fully measurable**; audio-rate at top |

## CLEAN measurements
- **Shapes @ order 2, fc 1000 Hz, res 0, Digital:** LP −3 dB @ 1004 Hz (−12.8 dB/oct stopband); HP +11.9 dB/oct
  skirt; BP peak 1002 Hz; Notch deep null at fc.
- **Order → slope (LP, octave just above fc):** 2→−12, 3/4→−24, 5/6/7→−36, 8→−48 dB/oct.
- **Resonance (BP @ 1 kHz):** param→peak dB = 1→0.5, 2→1.0, 3→1.5, 5→2.5, 8→4.0, 10→5.0, 15→7.5, 20→10.0,
  30→15.0, 40→20.0, 50→26.4, 60→37, 120→69, 180→95.
- **Cutoff law (norm→−3 dB Hz):** 0→31, 0.1→43, 0.2→81, 0.3→159, 0.4→317, 0.5→633, 0.6→1270, 0.7→2573,
  0.8→5218, 0.9→9997, 1.0→19161. ⇒ logarithmic, ≈ 20 Hz–20 kHz.
- **Analog saturation (300 Hz, LP passband, res 0):** Digital THD ≈0 %; Analog 2.0 % @ −12 dB → 17.6 % @ 0 dB,
  H2≫H3 at low drive. High-res+drive 1 kHz BP: Digital 0.7 % vs Analog 14.6 % (H2 −22, H3 −18).
- **Self-osc @ res 180:** Analog tail −31 dB (sustains) / Digital −53 dB (decays).
- **Latency:** 45 samp (0.94 ms).

## To implement (CLEAN-only path for ES-L/ES-X)
- **Filter core:** TPT/ZDF state-variable filter (Zavalishin) with LP/BP/HP/Notch taps; cascade N/2 SVF sections
  for order 2..8 → 6 dB/oct/pole. Resonance maps to SVF damping `k = 1/Q`; calibrate so peak_dB ≈ 0.5·param (≤40)
  with an accelerating curve toward self-oscillation at the top.
- **Cutoff:** log map fc = 20·(1000)^norm Hz (20 Hz–20 kHz).
- **Analog mode:** wrap the filter in a level-dependent, asymmetric (even-harmonic) soft-clip on input and output
  (a tanh/asymmetric shaper biased for H2 dominance); the same nonlinearity bounds the resonant pole → self-osc.
- **LFO:** free-running sine/tri up to 256 Hz, depth 0..1 modulating fc (log domain). Tempo-sync/env-follower =
  separate modulator sources (defer; not needed for the core filter color).

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm-derived (none used here).
