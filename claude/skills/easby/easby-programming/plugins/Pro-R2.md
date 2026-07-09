# Pro-R 2 — FabFilter (Algorithmic reverb — decay-rate EQ, ducking, modulated tail)

| | |
|---|---|
| Vendor / ver | FabFilter · Pro-R 2 · v2.06 · VST3 |
| Type | Algorithmic reverb (decay-rate EQ, ducking, modulated tail) — true-stereo, FDN-class, zero-latency |
| Tech | VST3 (FabFilter), stripped, **black-box only** |
| Binary | universal Mach-O bundle (x86_64+arm64), **stripped** (no own DSP syms; ~454 undefined = system frameworks only), **no PACE/iLok** (links libz + libc++ + Cocoa/Metal only) |
| Provenance | **100% CLEAN** — every fact below is black-box measurement (impulse/tone in → measure out). No r2/Ghidra used or needed. |
| Measured on | Pro-R 2 v2.06 · SR 48 kHz (latency identical @44.1/48/96k) · `private-research/Pro-R2/Tools/pror2_sysid.py` (pedalboard 0.9.17 host route) · 2026-06-22 |
| Source | `private-research/Pro-R2/` — `Tools/{pror2_sysid.py,pror2_params.py,pror2_plots.py}` (sysid has OQ probes: `duck_threshold`/`duck_depth`/`duck_time`/`long_tail`), `docs/{notes.md,ir_edc_default.png,decay_rate_map.png,perband_brightness.png,ducking_envelope.png,long_tails.png}` |

## Signal chain (CLEAN — measured behaviour; internal topology inferred, marked)
```
inL,inR (true-stereo, separate channels, cross-fed)
  → input_level (pre-reverb wet send, dB)
  → [EARLY field + LATE reverb tank]  (recursive/FDN-class; modulated tail)
        • space = size/time      • decay_rate = ×RT60 (25–400%)
        • distance = early↔late balance     • character = tail modulation depth (chorus)
        • style = Modern / Vintage / Plate  • brightness = decay-domain HF tilt
        • Decay-EQ ×6 = per-band decay-time multipliers (12.5–200%)
        • ducking = input-keyed wet gain reduction   • freeze = infinite hold
        • thickness = static spectral shaper          • stereo_width = tail decorrelation
  → Post-EQ ×6 (post-reverb, full parametric)
  → output_level (master trim, dB)
  → equal-power MIX with dry  → outL,outR
```
**Latency = 0 samples** (no oversampling FIR / lookahead — pure recursive reverb). True-stereo:
L-only impulse → outL peak 0.048 / outR 0.015 (decorrelated cross-feed), symmetric L↔R.

## Core parameters (CLEAN — pedalboard param table, v2.06)
| param | unit / range | measured behaviour |
|---|---|---|
| space | sec **0.2–10** (knob true max = 10 s) | headline size/time. **RT60 ≈ 0.83·space**, linear & r²≈1.0 across the WHOLE range, no saturation. (pedalboard's reported "1.005–1000" is a unit-parse artifact — set via raw 0..1; >10 s tails come from decay_rate, not space.) |
| decay_rate | % 25–400 | **linear RT60 multiplier**: RT60 ≈ 0.0204·decay% @space2.5 (100%→2.1 s, 400%→8.4 s) |
| predelay | ms 0–500 | linear & exact (onset = set + ~6.7 ms intrinsic build-up) |
| predelay_sync | enum | Free / 1/4 / 1/8 / 1/16 / 1/32 Note (tempo-sync) |
| predelay_offset | % 50–200 | sync predelay scaler |
| mix | % 0–100 | **equal-power** dry/wet (dry amp = cos(mix·π/2): 0.707@50%, 0.383@75%) |
| brightness | % −100..+100 | **decay-domain HF tilt**: 16 kHz RT60 1.05→1.95 s across range; LF≤500 fixed |
| character | % 0–100 | **tail modulation depth** (chorus): 1 kHz tail −20 dB BW 1.3 Hz→**36.7 Hz** @100% |
| distance | % 0–100 | early↔late balance: E/L +4.5 dB@0% (close) → −14.7 dB@100% (distant); Ts 68→260 ms |
| thickness | % −100..+100 | **static** spectral/level shaper (not decay): + attenuates outer bands (LF&HF) > mid |
| stereo_width | % 0–120 | tail L/R decorrelation: 0%→mono(corr 1.0), 70%(dflt)→corr≈0, 120%→corr −0.38 |
| ducking | dB 0–48 | input-keyed **downward expander** on wet path. **supp_dB = −(duck/36.9)·(key_dBFS − T), T≈−35 dBFS** fixed threshold (validated <0.15 dB). Continuous (no floor): +18 dBFS key → −35 dB. τ_attack≈34 ms (10–90% 35 ms), τ_release≈110 ms (10–90% 240 ms), single-pole, level-independent |
| freeze | enum | Off / On — **infinite hold** (tail sustains flat over 4 s vs −80 dB normal decay) |
| style | enum | **Modern** (cleanest tail, BW 1.3 Hz) / **Vintage** (most modulated, BW 10.7 Hz) / **Plate** (densest early, 13 ms build-up) |
| input_level | dB −inf..+36 | pre-reverb wet-send gain (scales wet exactly; leaves dry) |
| output_level | dB −inf..+36 | post-everything master trim (exact dB) |
| input_pan / output_pan | −1..+1 | pan |
| lock_mix | enum | Unlocked / Locked (lock mix on preset load) |
| analyzer_mode | enum | Off / Pre+Post / Reverb+Post (UI analyzer only) |

## Decay-EQ — the defining feature (CLEAN, 6 bands)
Each band: `enabled`, `frequency` (10–30 kHz), `q` (0.05–1.0), `shape` (Bell/LowShelf/HighShelf/Notch),
**`rate` (% 12.5–200) = per-band decay-time multiplier**. Verified: HighShelf @4 kHz, rate 12.5%→200%
moves 2–8 kHz RT60 from **0.66 s → 2.4 s** while 250 Hz stays 2.5 s. `speakers` = surround routing.

## Post-EQ (CLEAN, 6 bands — post-reverb, verified)
−24 dB bell @1 kHz → −20.8 dB notch in wet tail (500 Hz unaffected → confirms post-reverb placement).
Each band: `shape` Bell/LowShelf/LowCut/HighShelf/HighCut, `gain` ±30 dB, `q` 0.025–40,
cut `slope` 6/12/24/48/96 dB/oct, `stereo_placement` L/R/Stereo/Mid/Side, `speakers` surround routing.

## Frequency-dependent decay (CLEAN — measured RT60 per octave)
Default (Modern, space 2.5, decay 100%, neutral): natural HF rolloff, HF/LF≈0.69.
| band Hz | 125 | 250 | 500 | 1k | 2k | 4k | 8k | 16k |
|---|---|---|---|---|---|---|---|---|
| RT60 s | 2.75 | 2.56 | 2.29 | 2.14 | 2.05 | 1.90 | 1.78 | 1.73 |

## CLEAN measurements (key maps)
- **decay_rate → RT60** (space 2.5): 25%→0.62, 50%→1.02, 100%→2.12, 200%→4.09, 400%→8.36 s (linear).
- **space → RT60** (decay 100%, true range via raw): 0.2 s→0.20, 1.85→1.59, 2.5→2.16, 4.0→3.41, 7.0→5.96, 10.0→8.48 s (RT60≈0.83·space, r²≈1.0 throughout — no top saturation).
- **Long tails (>10 s)** (space=10 s, raise decay_rate): RT60 = 8.5 / 17.1 / 26.0 / **35.2 s** @ decay 100/200/300/400% — **combined law RT60 ≈ 0.83·space·decay%/100 holds to 35 s** (r²≈0.998). 40 s buffer; tail reaches −224 dB floor well inside it (not truncation-limited).
- **mix dry amp**: 10%→0.988, 25%→0.924, 50%→0.707, 75%→0.383, 90%→0.156 (cos law, equal-power).
- **ducking** (key 1 kHz, 100% wet): threshold T≈−35 dBFS (control-independent); supp slope = 0.0271 dB/dB·duck (duck=24→0.65, 48→1.31 dB/dB). Depth @key −3 dBFS: duck 6→−5.2, 24→−20.8, 48→−41.6 dB. Timing level/depth-invariant.
- Plots: `docs/{ir_edc_default,decay_rate_map,perband_brightness,ducking_envelope,long_tails}.png`.

## To implement (CLEAN path for product — public DSP only)
Algorithmic reverb = **late-field FDN + early reflections + post-EQ + ducking + modulation**:
- **Late reverb**: feedback delay network (Jot/Stautner-Puckette FDN) or Dattorro plate topology; set
  global RT60 from a `space`+`decay_rate` map (RT60 ≈ 0.83·space·decay%/100). Lit: Jot & Chaigne
  "Digital delay networks for designing artificial reverberators" (AES 1991); Dattorro "Effect Design
  Pt.1: Reverberator" (JAES 1997); Valimaki, Parker, Savioja, Smith, Abel **"Fifty Years of Artificial
  Reverberation"** (IEEE TASLP 2012) — survey of all of the above.
  **INFERRED (architecture; not black-box-recoverable):** FDN order (≈8–16 lines) and the tail-modulation
  LFO rate are internal topology — measurement gives only emergent behaviour (clean exponential EDC r²≈1.0
  ⇒ well-mixed network; tail-spectrum broadening ≤~37 Hz ⇒ slow chorus). Use any order/rate that reproduces
  the measured RT60, per-band decay, and modulation BW; do NOT treat a specific count/Hz as a recovered fact.
- **Frequency-dependent decay** = per-delay-line damping filters giving per-band RT60; expose as a
  multi-band **decay-time multiplier** EQ (the Decay-EQ: 12.5–200% per band) + a global HF-decay tilt
  (brightness). Realize via Schroeder/Moorer absorbent comb damping or Jot's tonal-correction + per-line
  lowpass. Lit: Moorer "About this reverberation business" (Computer Music J 1979); Jot loss-filter design.
- **Early reflections / distance**: tapped delay early field cross-faded against the late tank for the
  early↔late (distance) control; Ts sweep 68→260 ms target.
- **Modulated tail (character)**: slowly modulate delay-line lengths (chorused FDN) for de-metallization;
  scale depth to the measured tail-spectrum broadening (≤~37 Hz @ max). Lit: Dahl & Jot, Frenette thesis.
- **Ducking**: peak/RMS envelope-follower on the INPUT keys a **downward expander** on the wet send.
  Law (CLEAN): `supp_dB = −(duck_dB/36.9)·(key_dBFS − T)`, fixed **T≈−35 dBFS**, continuous (no floor);
  single-pole detector **τ_attack≈34 ms, τ_release≈110 ms** (level/depth-independent). One VCA on the wet path.
- **Equal-power mix** (cos/sin), **post-reverb parametric EQ** (biquad cascade), **width** = tail M/S or
  L/R decorrelation; **freeze** = open the FDN feedback to unity (loss→0) to hold the tail.
- Match each curve black-box against `Tools/pror2_sysid.py` (null the IR/EDC, per-band RT60, mix law).
  All targets above are CLEAN measurements — safe to ship; no disasm-derived facts exist for this plugin.

## Open questions — status (2026-06-22)
- ✅ **Ducking attack/release + threshold** — RESOLVED. Downward expander, T≈−35 dBFS (fixed), supp slope
  0.0271 dB/dB·duck, τ_atk≈34 ms / τ_rel≈110 ms (level-invariant). See ducking row + `ducking_envelope.png`.
- ✅ **Space tails >10 s** — RESOLVED. `space` true max = **10 s** (the old "1000 s" was a pedalboard
  unit-parse artifact, not a capture truncation). RT60≈0.83·space is linear to the top; >10 s tails come from
  decay_rate (space 10 s × 400% → **35 s**, law holds, r²≈0.998). 40 s buffer. See `long_tails.png`.
- ⚠️ **FDN order / internal LFO rate** — **INFERRED (architecture; not black-box-recoverable)**, label kept,
  not promoted to numbers (see late-reverb note).

## REF — static disasm pass (TAINTED, reference-only; NOT for product) — 2026-06-22
> Quarantine: `private-research/_quarantine_disasm/Pro-R2/`. EULA clean-room — do NOT cite from product/ES-L.
- Ghidra/r2 pass on v2.06 arm64 confirms the **inferred** topology by **intact RTTI**: late reverb =
  `FeedbackDelayNetwork` + **`HadamardFeedbackMatrix`** (NOT Householder) + in-loop `FeedbackDelayEQ`
  (multi-band matched-mag biquad bank) + `Diffuser`/allpass chain + separate `EarlyReflectionSimulator`
  + `ModulatingDelayLine`/`ModulationGenerator` (Character) + `Ducker`; 3 engines Modern/`VintageReverb`/`PlateReverb`.
- Crown recovered: decay-EQ biquad designer (`0x189738`, tan-prewarp + decayGain→matched-mag solve).
  Walls (still CLEAN-only): realtime FDN tick + Hadamard mix (dispatched/heap), delay-line lengths (runtime),
  **ducking constants NOT baked** (the −(duck/36.9)(key−T) law stays a measurement). REF confirms architecture; it ships nothing.

---
Provenance tags: **CLEAN** = black-box measurement (`pror2_sysid.py`) / public DSP literature / own voicing
(product-safe). **REF** = static disasm (Ghidra) under `_quarantine_disasm/Pro-R2/` — reference/education ONLY,
never enters product; the FDN/Hadamard/decay-EQ topology it confirms is generic textbook, re-derived CLEAN above.
