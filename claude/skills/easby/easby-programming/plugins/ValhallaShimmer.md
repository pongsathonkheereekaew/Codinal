# ValhallaShimmer — Valhalla DSP (Pitch-Shifted Feedback Reverb / "Shimmer Reverb")

| | |
|---|---|
| Vendor / ver | Valhalla DSP · v1.3.0 (Jan 2023 build) |
| Type | Algorithmic feedback reverb with a pitch-shifter inside the regeneration loop (the canonical "shimmer reverb") |
| Tech | C++/JUCE (AudioProcessor + WebKit/Cocoa UI). DSP = Valhalla `VMod_*` toolkit: H949-style pitch shifter + allpass-diffusion delay tank + tri-LFO chorus. Accelerate/vDSP linked. |
| Binary | universal (x86_64 + arm64), Mach-O bundle, **no DRM** (no LC_ENCRYPTION/PACE), **not stripped** (7992 syms). Build TUs `ValhallaShimmer2013.cpp` / `…Editor2013.cpp`. |
| Provenance | All DSP behavior/numbers below = **CLEAN** (pedalboard black-box). Class names / topology hints = **REF** (symbol roster, quarantined). Every fact tagged inline. |
| Measured on | ValhallaShimmer (Jan 2023 build, v1.3.0) · 48kHz · pedalboard 0.9.17 · 2026-06-27 |
| Source | `private-research/Valhalla/Shimmer/` (shim_probe.py, shim_filt.py, measured_shimmer.json, *.wav); REF `private-research/_quarantine_disasm/Valhalla/Shimmer/` |

## Signal chain
```
                 ┌──────────────────── feedback loop (gain = feedback) ─────────────────┐
 x ─► [input] ─►(+)─► allpass-diffusion delay tank ─► chorus-mod delays ─► [LPF highcut] ─┤
                 ▲      (size = delay-line scale,      (TriOsc: modrate,    [HPF lowcut]   │
                 │       reverbmode = density config)   moddepth)            (in-loop damp) │
                 │                                                                          │
                 └──────────── H949-style PITCH SHIFTER ◄───────────────────────────────────┘
                              (shift = interval ±1 oct, shiftmode = up/down/dual/off)
                              → each pass re-pitches → octave cascade = shimmer

 wet tap ─► [colormode bright/dark] ─► equal-power crossfade (wetdry) ─► out
```
- **CLEAN:** pitch shift is INSIDE the feedback path (proven: feedback>0 produces a stack of octaves at f·2^k; feedback=0 produces almost none). REF roster (`VMod_PitchShiftH949`, `VMod_DelayLine::AllpassiBlock`, `VMod_DiffChorus`) corroborates topology but is reference-only.
- PDC = **0 samples** (reported_latency_samples; CLEAN).

## Per-stage formula (tag each CLEAN or REF)

- **Pitch shifter — `shift` interval law (CLEAN):** `shift` raw 0→1 is a **bidirectional interval, LINEAR IN SEMITONES**, fit `semitones = 24.19·raw − 12.33` (max residual **0.20 st**). So raw 0 = **−1 octave** (ratio 0.49), raw ≈ 0.51 = **unison**, raw 1.0 = **+1 octave** (ratio 2.005). Measured ratios at raw {0,.1,.2,.3,.4,.6,.7,.8,.9,1.0} = {0.493,0.564,0.651,0.746,0.856,1.121,1.292,1.5,1.729,2.005} → semitones {−12.2,−9.9,−7.4,−5.1,−2.7,+2.0,+4.4,+7.0,+9.5,+12.0}. ~2.4 st per 0.1 raw. shiftmode selects how this interval is routed (up / down / both).
- **Pitch shifter — `shiftmode` (CLEAN, 5 discrete modes; measured at shift=1.0, f=500):**
  | raw band | behavior (cluster dB vs fundamental) |
  |---|---|
  | 0.00–0.19 | **Octave Up** (up_oct −13, down absent). Dual-delay-line voicing — more intermediate artifacts (up_5th −65). |
  | 0.20–0.39 | **Octave Up + Down (dual)** (up_oct −16, down_oct −18, near-equal) |
  | 0.40–0.59 | **Octave Up** (up_oct −14, down absent). *Cleaner* single-shifter voicing (up_5th −76). |
  | 0.60–0.79 | **Octave Up + Down (dual)**, variant (up_oct −17, down_oct −17) |
  | 0.80–1.00 | **No shift / reverb only** (all non-fundamental clusters < −85) |
  Boundaries at 0.2/0.4/0.6/0.8 (5 even bands).
- **Shimmer cascade (CLEAN — the headline mechanism):** pitch-shift-in-loop ⇒ octave stacking f·2^k. Octave-cluster levels (dB vs fundamental) vs feedback (shiftmode=octave-up, shift=+1oct):
  | feedback | oct+1 | oct+2 | oct+3 | oct+4 | oct+5 |
  |---|---|---|---|---|---|
  | 0.0 | −78.8 | −98 | — | — | — |
  | 0.5 | −5.7 | −12.3 | −19.1 | −25.9 | −34.0 |
  | 0.95 | −0.1 | −1.0 | −2.3 | −3.6 | −5.1 |
  At fb=0.5, a clean **−6.5 dB/octave** ladder; at fb=0.95 a near-flat tower of 6 octaves = "endless ascending" shimmer.
- **Reverb tank — `feedback` → RT60 (CLEAN):** fb {0,.4,.6,.8,.9,.95} → RT60 {4.5, 5.6, 8.3, 17.1, 18.9, 18.9} s. Exponential; saturates ~19 s near fb≥0.9 (quasi-freeze). Note a base ~4.5 s tank decay exists even at fb=0 (feedback knob adds the *shimmer regeneration* on top of the tank's intrinsic decay).
- **Reverb tank — `size` → RT60 + predelay (CLEAN):** size {0,.25,.5,.75,1} → RT60 {1.3, 4.3, 6.5, 9.8, 11.6} s AND predelay {0.13, 0.29, 0.41, 0.47, 0.57} s, peak-build index 9.7k→102k. Size scales the delay-line lengths → bigger space = longer pre-delay + longer decay.
- **`reverbmode` (CLEAN, 4 discrete density/decay configs):** at fixed fb/size, predelay-to-peak and RT shift in steps: 0.00–0.29 → predelay 0.41 s (sparsest/slowest build); 0.30–0.59 → 0.25 s; 0.60–0.79 → 0.17 s; 0.80–1.00 → 0.07 s (fastest/densest, short). 4 even bands (boundaries 0.3/0.6/0.8) = distinct tank topologies (delay-set / diffusion-stage count).
- **`diffusion` (CLEAN, continuous):** raises early echo density / wet energy (wet RMS 0.0025→0.0126, ~5×, monotonic); centroid ~flat (~10.5 kHz). Allpass-diffusion amount (smear), not a tone control.
- **`colormode` (CLEAN, 2 modes):** **Bright** (raw 0.00–0.52, wet centroid 2503 Hz) / **Dark** (0.53–1.00, 1859 Hz). Binary brightness/character of the recirculated signal.
- **`lowcut` = in-loop HPF (CLEAN):** ~1st-order (≈6–10 dB/oct). −3 dB corner sweeps up: raw 0 ≈ flat (DC); 0.33 ≈ 1.0 kHz; 0.66 ≈ 1.3 kHz; 1.0 ≈ 1.5 kHz (with −33 dB at 40 Hz).
- **`highcut` = in-loop LPF (CLEAN):** ~1st-order (≈6 dB/oct). −3 dB corner opens up: raw 0 ≈ 250 Hz (very dark, −40 dB @16k); 0.33 ≈ 3.3 kHz; 0.66 ≈ 7.5 kHz; 1.0 ≈ flat past 16 kHz.
- **`modrate` / `moddepth` (CLEAN, continuous, chorus on tank delays):** widen the spectral line (FM/vibrato of delay taps). moddepth 0→1 ⇒ −20 dB bandwidth 1→120 Hz; modrate 0→1 ⇒ 1→90 Hz (at fixed depth). De-correlates the feedback → lush, non-metallic shimmer.
- **`wetdry` (CLEAN):** **equal-power crossfade** — dry peak = 0.0412·cos at midpoint (0.0291 = 0.0412·0.707), wet rises monotonically. 0 = dry, 1 = wet.
- **`program` (CLEAN, 8 presets, snapshot not a stage):** BlackHole, ConcertHall, BrightHall, DeepBlueDay, Chorus, BigReverse, TajMahal, OctaveUpDown. Sets a combo of the 13 params above; with params pinned, RT60/peak read identical across all 8 ⇒ pure preset selector, no independent DSP.

## Why / design rationale (music ↔ code)
- **Pitch shifter INSIDE the feedback loop, not after it** → musical effect: every regenerated reverb tail is re-pitched, so a single note blooms into an *ascending* (or descending) cascade of octaves that builds as it decays = the ethereal, organ/choir-like "shimmer" pad. Purpose: turn a transient/sustained source into an evolving harmonic wash. (Putting the shifter *after* the reverb would shift the whole tail once — a static transpose, not a cascade. The in-loop placement is the entire point.)
- **±1 octave, linear-in-semitones interval (not just fixed octave)** → lets you dial fifths, fourths, minor-thirds etc. for harmonic-shimmer flavors beyond the classic octave; linear-semitone law = musically intuitive "interval" control.
- **shiftmode up / down / up+down** → octave-up = bright lift (classic "shimmer"); octave-down = sub/dark drone; dual = simultaneous over+under = thick, symmetric harmonic cloud. Two voicings each (single clean vs dual-delay-line) trade artifact texture for smoothness.
- **feedback = shimmer regeneration AND decay** → low fb = a couple of shifted layers (subtle sparkle); high fb = self-sustaining octave tower (drone/pad that never ends). One knob spans "spice" to "infinite generator."
- **In-loop lowcut/highcut + colormode (bright/dark)** → tame the metallic, ever-brightening buildup that octave-up feedback naturally causes (each pass pushes energy up an octave → HF piles up); damping filters bleed off HF per pass so the shimmer stays musical instead of turning into a screaming sine. This is *why* an in-loop LPF is essential to a shimmer reverb.
- **Chorus modulation (TriOsc) of the tank delays** → de-correlates the recirculating copies so the dense octave stack sounds lush/animated rather than a static comb/metallic ring; the lifeblood of Valhalla's "smooth" reverb character.
- **reverbmode density configs + size** → choose the spatial canvas (sparse cathedral vs dense plate) the shimmer paints on; size sets the time-scale of the bloom.
- **equal-power wetdry** → constant perceived loudness across the blend (standard for send/insert reverb).

## Parameters
| param | unit | range (raw) | notes |
|---|---|---|---|
| wetdry | mix | 0..1 | equal-power; 0=dry, 1=wet |
| shift | semitones | 0..1 → −12.3…+11.9 st | linear in semitones, ±1 octave; unison at raw≈0.51. `st = 24.19·raw − 12.33` |
| feedback | regen/decay | 0..1 | RT60 4.5→~19 s; drives octave cascade |
| diffusion | density | 0..1 | allpass smear; wet energy ~5× across range |
| size | tank scale | 0..1 | RT60 1.3→11.6 s; predelay 0.13→0.57 s |
| lowcut | HPF corner | 0..1 → ~DC…1.5 kHz | in-loop, ~1st-order |
| highcut | LPF corner | 0..1 → ~250 Hz…>16 kHz | in-loop, ~1st-order |
| modrate | LFO rate | 0..1 | chorus on tank delays; bw 1→90 Hz |
| moddepth | LFO depth | 0..1 | bw 1→120 Hz |
| reverbmode | enum (4) | bands 0/.3/.6/.8 | density/decay configs (predelay 0.41/0.25/0.17/0.07 s) |
| shiftmode | enum (5) | bands 0/.2/.4/.6/.8 | UpA / Up+Down / UpB(clean) / Up+Down(var) / None |
| colormode | enum (2) | bands 0/.53 | Bright (2503 Hz) / Dark (1859 Hz) |
| bypass | bool | off/on | |
| program | enum (8) | preset selector | snapshot of the 13 params above (not a DSP stage) |

All 14 params are exposed to the host as raw **[0,1]** (VST3 normalized = native range here); `string_value` only echoes the float (no human units exposed for continuous params, no labels for the 3 internal enums) → every number above is by measurement.

## FFI contract
N/A — JUCE C++, no clean C FFI boundary. Black-box via pedalboard.

## CLEAN measurements
See `private-research/Valhalla/Shimmer/measured_shimmer.json` for the full data record. Reference renders:
`shimmer_octup_fb085.wav` (octave-up cascade, fb 0.85), `shimmer_dualoct_fb07.wav` (up+down dual). Harness gotcha confirmed: pitch shifter can cold-start NaN like sibling FreqEcho → single render/process + isfinite re-exec.

## To implement (CLEAN-only path for product — OFF-AXIS from ES-L dynamics; KB coverage)
Clone-ready primitive set:
1. **Allpass-diffusion reverb tank** (cascaded allpass delays, sized by `size`; 4 selectable density configs = `reverbmode`).
2. **Pitch shifter in the feedback path** — delay-line/crossfade (PSOLA-free, H949-style) transposer, interval = `24.19·raw − 12.33` semitones, routing = up / down / up+down (`shiftmode`).
3. **Feedback summer** with `feedback` gain (RT60 4.5→19 s), in-loop **1st-order HPF (`lowcut`) + LPF (`highcut`)** to bleed off the octave-up HF pileup, plus a **bright/dark color** tilt.
4. **Tri-LFO chorus** modulating the tank delays (`modrate`/`moddepth`) to de-correlate the octave stack.
5. **Equal-power wet/dry** crossfade. PDC = 0.
Building blocks to reuse: allpass diffusion (Schroeder/Dattorro), fractional-delay pitch shifter (crossfaded two-tap), 1st-order shelving/cut filters, triangle LFO.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (reproduce black-box before shipping). Here all numeric/behavioral facts are CLEAN; only the `VMod_*` class-name topology hints are REF (quarantined under `_quarantine_disasm/Valhalla/Shimmer/`).
