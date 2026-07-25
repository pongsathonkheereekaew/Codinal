# PrimalTap — Soundtoys (delay / Lexicon PrimeTime lo-fi)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Delay — lo-fi digital (Lexicon Prime Time 93/95 emulation): dual A/B taps, sample-rate-reduced delay, VCO modulation, Surge self-oscillation, Freeze |
| Tech | C++ VST3, shared "Soundtoys" static framework (one plugin per process). AAX = PACE; VST3 = pedalboard-hostable |
| Binary | universal (x86_64 + arm64) MH_BUNDLE, 37 MB; not measured statically (CLEAN-only task) |
| Provenance | **CLEAN** — black-box measurement (pedalboard). Hardware lineage (Prime Time) = public. No disasm. |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (`Tools/st_sysid.py`, `Tools/delay_probe.py`, `out/PrimalTap_*.json`) |

## Signal chain
```
x → input_gain (0..32 dB, drives the lo-fi converter into clip)
  → two delay taps A & B, each: [time × multiply(1/2/4/8) ⇒ delay-line SAMPLE-RATE reduction]
      → VCO pitch modulation (shape/rate/depth, per-tap depth & polarity)
      → feedback_a/b (×g, with rolloff in loop) → freeze/Surge (≥100 % = self-osc)
      → output_gain_a/b, output_pan_a/b, output_polarity_a/b
  → routing by algorithm (Classic / Parallel / Series / Reverb / CrissCross / Ping-Pong)
  → high_cut (LP 800..15k) / low_cut (HP 0.1..1k), rolloff_mode = in-Feedback or on-Output
  → mix (dry/wet) → y
```

## Per-stage formula (tag each CLEAN / REF)
- **Delay time → actual** (CLEAN — KEY QUIRK): the displayed `time_*_msec` is **not** the actual delay below ~800 ms. Measured displayed→actual (Classic, multiply 1×, settled): 50→11.6, 100→27.6, 150→51.3, 200→85.4, 300→187.4, 400→313, 500→436, 600→561, 800→786, **1000→1002, 1500→1504, 2000→1999.9, 4000→4018, 8000→8000** (ratio rises 0.23→1.0). Above ~1 s actual = displayed (linear 1:1); below, the engine compresses the requested time (a fixed nonlinear UI→delay taper modeling the Prime Time's range behaviour; no clean closed form — use the table or recalibrate). **For ES-L just use a normal linear time line** — this taper is a hardware-emulation quirk, not desirable DSP. PDC latency = **92 samples** (`reported_latency_samples`).
- **`multiply` = sample-rate reduction (the core lo-fi mechanism)** (CLEAN): values 1×/2×/4×/8× simultaneously (a) **multiply the delay time** (displayed 100 ms → ~208/407/802 ms at 2×/4×/8× on the sibling Little; PrimalTap 300 ms → 557/1200/2400 at 2/4/8×) and (b) **crush bandwidth by running the converter at 1/N rate**: a 7 kHz tone → 1× clean (alias −80 dB), 2× → strong image at 9 kHz −26 dB, 4× → **folds to 1 kHz at +55 dB** (alias louder than original), 8× → +57 dB with noise floor up to ~−46 dB. ⇒ longer delay is bought with N× worse aliasing/HF loss — the authentic Prime Time "grunge gets dirtier as it gets longer." Even 1× is not full-bandwidth (intrinsic lo-fi).
- **Input drive / lo-fi clip** (CLEAN): `input_gain_db` 0…32 drives a **symmetric (odd-harmonic) clipper** into the converter. THD of the wet path (1 k, Classic, T≈250): 0 dB→0.14 %, 8→0.7 %, 16→**15.6 %**, 24→23.1 %, 32→24.5 %. Sharp knee at ~16 dB (digital clipping), H3 ≫ H2 (−16 vs −51 dB at 16 dB) ⇒ hard symmetric clip = the gritty PrimeTime overload.
- **VCO modulation** (CLEAN, relative): a delay-time LFO (`vco_rate_hz` 0.1…256, `vco_depth` 0…1 global × per-tap `vco_depth_a/b`, `vco_shape` Triangle/Square/Sine/RampUp/RampDown, per-tap polarity). 1 kHz carrier inst-freq spread grows monotonically with depth: depth 0.1→slight, 0.3→moderate, **depth 1.0 → >800 Hz spread (>1 octave warble)**. Shape affects character (Square widest, ramps asymmetric). (Absolute cents estimator-limited; trend is solid: depth = modulation extent, max = extreme pitch wobble for chorus/vibrato/sci-fi.)
- **Feedback / Surge** (CLEAN law from sibling; host-limited here): `feedback_a/b` ∈ [0,125] %. On the byte-identical-engine **LittlePrimalTap** the measured loop-gain law is: 25 %→−5.7 dB/rep (g 0.52), 50 %→−3.2 (0.69), 62.5 %→−2.2 (0.78), 75 %→−1.4 (0.85), 90 %→−0.31 (0.97), **100 %→+0.59 dB/rep (g 1.07) = sustain/Surge onset**, 110 %→+1.4 (1.18), 125 %→+1.5 (1.19) = runaway. So **Surge = feedback ≥ ~100 % → self-oscillating, building delay** (the freeze-into-infinite-regeneration effect). In pedalboard PrimalTap's own `feedback_a`/`freeze` writes did not recirculate (param strings updated but no tail — same host-restart limitation as EchoBoy styles); the law above (from Little) is the spec. **Freeze** = lock the delay buffer (100 % feedback, input muted) → infinite sustain; **unmeasured in pedalboard, documented from the param + Prime Time behaviour.**
- **rolloff_mode** (CLEAN, param): `Feedback` = the HF/LF cuts sit *inside* the feedback loop (repeats darken progressively) vs `Output` = cut only the final wet (repeats keep their tone). high_cut 800–15 k LP, low_cut 0.1–1 k HP.
- **algorithm** (CLEAN, param + partial measure): Classic (single line / straightforward A→B), Parallel (A & B independent), Series (A feeds B; measured as 2 taps at T and ~2.4×T), Reverb (dense diffusion), CrissCross (A↔B cross-feedback), Ping-Pong (L↔R bounce). `delay_adjust` 0.5–1.0 = fine time scaler (measured: 1.0/0.841/0.707/0.595/0.5 → actual ×0.625/0.447/0.319/0.231/0.171 of displayed, i.e. multiplies the already-tapered actual time).

## Why / design rationale (music ↔ code)
- **Sample-rate-reduced delay (`multiply`)** → the defining Prime Time sound: to get a longer delay the original ran its converter slower, so long delays are darker, grainier, and aliased → PrimalTap reproduces this *deliberately* (no anti-alias filter scaling with rate) so the "lo-fi" is a feature, not a bug. Longer = dirtier is the whole vibe.
- **Hard symmetric input clip at ~16 dB** → drive the front end and the digital converter overloads into crunch → the aggressive, in-your-face PrimeTime distortion used for lo-fi drums/vocals.
- **Surge (≥100 % feedback self-oscillation) + Freeze** → turns the delay into a drone/oscillator/sustain pad → the legendary "infinite repeat that builds and screams" performance trick; Freeze captures a buffer to loop forever.
- **VCO with selectable shape/per-tap polarity** → pitch-modulate the delay for chorus, vibrato, detune clouds, and ring-mod-ish extremes (256 Hz rate) → a full modulation engine, not just wow/flutter.
- **rolloff in-Feedback vs on-Output** → choose whether the trail decays in tone (analog-tape feel) or stays bright (digital feel) → one switch covers both delay aesthetics.
- **Dual A/B taps + 6 routings + pan/polarity** → ping-pong, stereo spreads, comb/phase tricks → a creative multi-tap, not just a mono echo.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| ab_link | bool | Off/On | link A & B controls (default On) |
| sync_mode_a / sync_mode_b | enum | TIME, BEATS | per-tap sync; only TIME measurable (no transport) |
| time_a_msec / time_b_msec | ms | 0…8000 | **displayed ≠ actual below ~800 ms** (see taper table) |
| beats_a / beats_b | beats | 0…4 | sync delay in beats (tempo-sync: unmeasured) |
| delay_adjust | ratio | 0.5…1.0 | fine time scaler (multiplies actual delay) |
| multiply | × | 1/2/4/8 | **delay × N AND sample-rate ÷ N (lo-fi)** |
| input_gain_db | dB | 0…32 | drives lo-fi clipper; THD knee ~16 dB |
| algorithm | enum | Classic, Parallel, Reverb, Series, CrissCross, Ping-Pong | tap routing |
| feedback_a / feedback_b | % | 0…125 | regeneration; **≥~100 % = Surge self-osc** (law from Little) |
| output_gain_a / output_gain_b | dB | −40…0 | per-tap wet level |
| mix | % | 0…100 | dry/wet |
| vco_depth | norm | 0…1 | global modulation depth (max ≈ >1 octave) |
| vco_rate_hz | Hz | 0.1…256 | LFO rate (audio-rate at top) |
| vco_depth_a / vco_depth_b | norm | 0…1 | per-tap mod depth |
| vco_shape | enum | Triangle, Square, Sine, RampUp, RampDown | LFO shape |
| vco_polarity_a/b | enum | Positive, Negative | per-tap mod polarity |
| freeze | bool | Off/On | lock buffer → infinite sustain (unmeasured in pedalboard) |
| rolloff_mode | enum | Feedback, Output | place tone cuts in-loop vs on output |
| high_cut_hz | Hz | 800…15000 | LP tone |
| low_cut_hz | Hz | 0.1…1000 | HP tone |
| output_pan_a / output_pan_b | deg | −60…+60 | per-tap pan (defaults −45/+45 = stereo spread) |
| output_polarity_a/b | enum | Positive, Negative | per-tap phase invert |
| tempo_bpm | BPM | 30…240 | internal tempo (no host transport in pedalboard) |

## CLEAN measurements
- Delay-time taper table (displayed→actual) above; linear only ≥1 s. PDC 92 samp.
- `multiply` = ×N delay + ÷N sample-rate (aliasing table above): 4×/8× fold 7 kHz to baseband at +55/+57 dB.
- Input drive THD: 0/8/16/24/32 dB → 0.14/0.7/15.6/23.1/24.5 % (odd-harmonic, knee ~16 dB).
- VCO depth → pitch-mod extent (monotonic; max >1 octave).
- Feedback/Surge law (from LittlePrimalTap, shared engine): self-osc onset ~100 %.

## To implement (CLEAN-only)
- **Variable-rate delay line**: implement `multiply` as genuine internal sample-rate reduction (÷N) with NO matching anti-alias filter → reproduces the longer-delay-is-grungier aliasing. (For a "clean" mode, add anti-aliasing; for the PrimeTime vibe, omit it.)
- **Front-end symmetric clipper** with a knee near the converter ceiling (THD ~16 % once driven ~16 dB) for the lo-fi crunch.
- **Feedback ≥ 100 % self-oscillation** ("Surge") with an optional in-loop limiter so it builds musically; **Freeze** = mute input + lock feedback to ~unity (buffer loop).
- **VCO delay modulation**: 5 shapes, per-tap depth/polarity, rate to audio-rate; depth scales to >1 octave for extreme detune/ring-mod.
- Dual A/B taps with pan, per-tap output gain, polarity, and 6 routing topologies; rolloff selectable in-feedback vs on-output.
- For ES-L prefer a **normal linear ms time map** (skip the displayed≠actual taper) and add the lo-fi/Surge as optional character.
- tempo-sync (BEATS) = host BPM × beats; **unmeasured (needs REAPER transport)**.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). Feedback/Surge law measured on the byte-identical-engine sibling LittlePrimalTap. Prime Time lineage = public history. **REF** = none (no disasm performed).
