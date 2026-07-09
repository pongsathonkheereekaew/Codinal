# ValhallaSpaceModulator — Valhalla DSP (Modulation Multi-FX: barberpole freq-shift / through-zero flanger / chorus)

| | |
|---|---|
| Vendor / ver | Valhalla DSP · v1.2.8 (Dec 2022 build) |
| Type | Modulation multi-FX — barberpole (Shepard) frequency-shift, through-zero flanger, multi-voice chorus/ensemble. NOT a dynamics processor (off-axis from ES-L). |
| Tech | C++/JUCE (legacy `AudioProcessor`, float `getParameter`/`setParameter` API — pre-AudioProcessorValueTreeState). DSP engine `VPlug_SpaceModulator` over a modulated fractional-delay line `VMod_DelayLine`. WebKit UI present but DSP fully reachable headless. |
| Binary | Mach-O universal (x86_64 + arm64), MH_BUNDLE. **NOT stripped** (9530 syms → REF roster). **No DRM / no PACE** (no `LC_ENCRYPTION_INFO`, no Eden/PACE bundle). Links Accelerate/vDSP. |
| Provenance | All DSP behavior + param maps = **CLEAN** (pedalboard black-box). Class/method names = **REF** (symbol table, quarantined). NOT a shared engine (0 `VPlug` overlap with siblings; only the tiny `VMod_DelayLine` primitive is shared with ValhallaFreqEcho). |
| Measured on | ValhallaSpaceModulator (Dec 2022 build) · 48kHz · pedalboard 0.9.17 · 2026-06-27 |
| Source | `private-research/Valhalla/SpaceModulator/` (probe.py, track.py, shift.py, shiftf.py, lfo3.py, comb.py, final.py, demo WAVs); REF `private-research/_quarantine_disasm/Valhalla/SpaceModulator/syms.txt` |

## Signal chain
```
                        ┌─────────────────────────────────────────────┐
                        │  modulated fractional delay line (VMod_DelayLine) │
x ──┬───────────────────┤  center delay = manual ± LFO/ramp excursion(depth) │──┬── feedback (±100%, recirculate) ──┐
    │ (dry)              │  LFO/ramp freq = rate (Hz)                    │  │                                    │
    │                    │  mode = how the delay is driven (ramp vs tri  │  └────────────────────────────────────┘
    │                    │         vs multi-tap) + voice count/spread    │
    │                    └─────────────────────────────────────────────┘
    │                                                  │ (wet)
    └──────────── equal-power crossover (wetdry) ──────┴──→ y
```
Core: **one modulated delay line**. Every mode is the same delay-line trick with a different LFO/ramp shape and number of voices. Net frequency motion comes from **delay derivative (Doppler), not a Hilbert/Bode SSB shifter** (proven below by carrier-frequency dependence).

## Per-stage formula  (tag each CLEAN or REF)

- **Modes** (CLEAN — full enumeration, 11 values, ordered raw bands):
  `Up` · `Up/Down` · `TZFlange+` · `TZFlange-` · `TriFlange` · `Ocho` · `Doubler` · `VariUp` · `VariUpDown` · `Ensemble360` · `Symphonic`.
  (Note: this is **11**, not the 10 in the brief — `Ensemble360` sits between VariUpDown and Symphonic.) Dispatched internally by `VPlug_SpaceModulator::CalcParameter` REF; only one block proc `ProcessBlockUp` is exported REF.

- **Barberpole / freq-shift modes** (`Up`, `Ocho`, `VariUp`, and the up-half of `Up/Down`/`VariUpDown`) — **CLEAN, decisive**:
  A sawtooth-ramped delay produces a **constant Doppler frequency shift**. Measured law (1 kHz carrier, Ocho = cleanest):
  **`Δf = f₀ · depth_seconds · rate_Hz`**  ⇔  **`Δf / f₀ = depth_s · rate_Hz`** (a *ratio*, not a fixed Hz).
  - Shift is **proportional to carrier frequency** → ratio constant 0.0282 at f₀ = 500/1000/2000 Hz (14.1/28.3/56.4 Hz). A true Bode/Hilbert SSB shifter would give the *same Hz* at every carrier — it does not ⇒ **Doppler-ramp barberpole, NOT a frequency shifter.**
  - Ocho is an essentially **clean single-sideband (upper)** result: lower sideband **−80 dB**, carrier leakage **−80 dB**, asymmetry **+80 dB** (textbook-clean SSB *appearance* from a ramped delay).
  - `Up` vs `Ocho`: identical shift law; Ocho is the smoother/cleaner single-voice glide (lower inst-freq jitter, std ≈ 1.2 Hz vs Up ≈ 1.4–3 Hz), `Up/Down`/`VariUpDown` add a triangle (rises then falls) so the glide reverses each half-cycle. `VariUp`/`VariUpDown` = variable/multi-voice barberpole (sideband fan visible).

- **Through-zero flange modes** (`TZFlange+`, `TZFlange-`, `TriFlange`) — **CLEAN**:
  Net shift **≈ 0 Hz**; carrier **oscillates around f₀** (TZFlange+ ptp ≈ 72 Hz, std ≈ 16; TriFlange ptp ≈ 200+ Hz). The delay sweeps **through zero** → momentary perfect null (deepest cancellation) as the modulated path crosses the dry path. `+`/`-` = polarity of the sweep/mix; `TriFlange` = wider triangle excursion (3-way / deeper sweep).

- **Chorus / ensemble modes** (`Doubler`, `Symphonic`, `Ensemble360`) — **CLEAN**:
  Net shift ≈ 0 Hz, multiple detuned voices → symmetric sideband fan around f₀ (Doubler ptp ≈ 43 Hz; Symphonic/Ensemble360 = many voices, dense ±5%-wide fan, ~−4 dB spread of comps). Multi-voice width, not a single comb.

- **rate** (CLEAN): **= the literal LFO frequency in Hz** (validated in chorus modes by pitch-oscillation FFT): raw→Hz 0.44/0.95/1.77/2.99/4.70 measured **0.436/0.958/1.742/3.005/4.704**. Bipolar **±10 Hz**; **sign = LFO/ramp direction** (up-glide vs down-glide for barberpole; sweep direction for flange). Taper is symmetric exp around 0 (fine resolution near 0, fast at the rails). For barberpole modes the rate also sets the shift magnitude via `Δf = f₀·depth·rate`.

- **depth** (CLEAN): **delay-line modulation excursion, 0–50 ms**, exp taper (raw 0.5→10.3 ms, raw 1.0→50 ms). In barberpole modes it co-scales the shift (`Δf ∝ depth`). depth = 0 → no modulation (carrier passes; barberpole shift → 0).

- **manual** (CLEAN, ±50 ms, exp taper symmetric about 0): **static center-delay offset / bias point** of the modulated delay line (the delay the LFO sweeps around). It is **not** a clean fixed-comb generator at depth = 0 (the wet path is a modulated/multi-tap structure, not a single static tap), so a simple `notch = k/τ` comb does not cleanly fall out of `manual` alone — manual shifts the operating delay; the audible comb forms from the *modulation*.

- **feedback** (CLEAN, bipolar **±100 %**, linear taper): **resonant recirculation of the delay output.** `|feedback|` sets resonance/decay **symmetrically** (impulse RT to −40 dB: 0%→0.2 ms, ±14%→0.7–0.9, ±49%→1.2–1.6, ±80%→3.8–6.4, **±100%→680–985 ms, near self-oscillation**). **Sign sets comb polarity** (positive vs negative feedback interleave the resonant teeth: peaks of one = notches of the other). Both rails → resonant flanger / runaway.

- **wetdry** (CLEAN, 0–100 %): **equal-power (constant-power) crossover.** At 50 % both legs ≈ **−3 dB** (dry 0.714 / wet 0.700 of total RMS); at 25 % dry −0.66 / wet −8.5 dB; symmetric at 75 %. dry ≈ cos(π/2·mix), wet ≈ sin(π/2·mix). 0 % = dry only; 100 % = wet only (dry leak −52 dB).

- **Latency** (CLEAN): **0 samples** (`reported_latency_samples = 0`, pdc = 0). Real-time modulated delay, no oversampling FIR.

## Why / design rationale (music ↔ code)
- **Barberpole via ramped delay (not a Bode/Hilbert shifter)** → an **endless Shepard-tone-like glide** (pitch seems to rise — or fall — forever) that costs one delay line instead of two Hilbert chains + quadrature oscillator. Trade-off the measurements reveal: the shift is **proportional to frequency** (`Δf ∝ f₀`), so unlike a true SSB shifter it stays *roughly musically consonant* (a near-constant interval rather than an inharmonic fixed-Hz offset) — arguably nicer on tonal material, and the reason it is voiced as "Space Modulator" rather than a clinical frequency shifter. The sawtooth ramp + crossfade hides the wrap discontinuity → the "endless" illusion.
- **Through-zero flange** → emulates **two tape machines sliding through coincidence** (the classic "jet plane" flange). The defining feature is the **momentary perfect null when the modulated delay crosses the dry path at zero** (deepest possible cancellation, −∞ notch through DC) — only achievable when the wet delay can go to/through zero relative to dry, which a normal positive-only delay flanger cannot. `+`/`-` give the two polarities of that null.
- **depth·rate shift coupling** → on the same control surface, *slow + deep* = lush slow glide, *fast + shallow* = subtle shimmer; the user dials musical motion, the Doppler math falls out. Designer exposes intuitive (rate Hz, depth ms) controls instead of "shift Hz."
- **Equal-power mix** → keeps **perceived loudness constant** as you blend dry↔wet (no −6 dB dip at 50 % that a linear mix would give) — important because flange/chorus is usually run partly wet.
- **Bipolar feedback** → positive vs negative feedback **flip which frequencies resonate** (teeth vs gaps), doubling the timbral palette from one knob; pushing to ±100 % turns the flanger into a **resonant / self-oscillating** comb for dramatic metallic sweeps.
- **Multi-voice ensemble (Symphonic/Ensemble360/Ocho)** → many slightly-detuned delayed copies → **chorus width / richness** (string-ensemble shimmer) vs the single-voice precision of Up/Doubler.

## Parameters
| param | unit | range | taper | notes |
|---|---|---|---|---|
| wetdry | % | 0–100 | linear | **equal-power** dry/wet crossover (−3 dB each @ 50%). raw = real/100. |
| rate | Hz | −10 … +10 | symmetric exp (fine near 0) | **= LFO/ramp freq in Hz** (verified). Sign = direction. Drives barberpole shift via Δf=f₀·depth·rate. |
| depth | ms | 0 … 50 | exp (raw0.5→10.3ms) | delay modulation excursion. 0 = no modulation. Co-scales barberpole shift. |
| feedback | % | −100 … +100 | linear | resonance (|fb|, symmetric) + comb polarity (sign). ±100% ≈ self-oscillation. raw0.5 = 0%. |
| manual | ms | −50 … +50 | symmetric exp | static center-delay/bias of the modulated line. Not a clean static comb at depth=0. |
| mode | enum | 11 values | — | Up, Up/Down, TZFlange+, TZFlange-, TriFlange, Ocho, Doubler, VariUp, VariUpDown, **Ensemble360**, Symphonic. |
| bypass | bool | Off/On | — | |

**Raw↔real conversions (CLEAN, harness uses NORMALIZED [0,1]):** convert via the measured tapers in `params_spacemod.json` / `params spacemod --taper-n 80`. Mode raw band-centers: Up 0.09 · Up/Down 0.23 · TZFlange+ 0.32 · TZFlange- 0.41 · TriFlange 0.50 · Ocho 0.59 · Doubler 0.68 · VariUp 0.77 · VariUpDown 0.86 · Ensemble360 0.95 · Symphonic 1.00.

## FFI contract (if clean C ABI)
None used (JUCE C++, hosted via pedalboard — no direct-FFI route taken; not needed). REF engine entry points (symbol table, reference only): `VPlug_SpaceModulator::{SetSampleRate(int), Reset(), CalcParameter(int), ProcessBlockUp(const float**, float**, int, int)}`, `VMod_DelayLine::{ctor, Clear}`, `VMod_Parameter::WarpVSTParameter(int)` (the norm→real warp). Process ABI (REF): separate in/out planar `float**`, `(in, out, numChannels, numSamples)`.

## CLEAN measurements
- **Mode count:** 11 (full list above).
- **Latency:** 0 samples.
- **Barberpole shift (Ocho, f₀=1 kHz, depth raw0.6=16.5 ms):** rate 0.44/0.95/1.77/2.99/4.70 Hz → shift **7.0 / 15.25 / 28.25 / 47.75 / 75.4 Hz**; SSB purity: lower SB & carrier both **≈ −80 dB**.
- **Shift law:** `Δf/f₀ = depth_s · rate_Hz` — carrier-freq independent *ratio* 0.0282 (500/1000/2000 Hz) ⇒ Doppler, not Bode.
- **LFO rate (chorus, pitch FFT):** raw→Hz 0.44/0.95/1.77/2.99/4.70 measured **0.436/0.958/1.742/3.005/4.704** (rate = literal Hz).
- **Feedback resonance (impulse RT−40dB, manual≈20 ms):** 0%→0.2 ms · ±14%→~0.8 · ±49%→~1.4 · ±80%→~5 · **±100%→0.68–0.98 s** (near self-oscillation, both polarities). Sign interleaves comb teeth.
- **Mix:** equal-power (−3 dB each @ 50%; dry 0.714 / wet 0.700 of RMS).
- Demo WAVs (1 kHz tone): `spacemod_Up_barberpole.wav`, `spacemod_TZFlangePlus.wav`, `spacemod_Symphonic.wav` (all finite).

## To implement
Off-axis from ES-L (dynamics) — this is a KB modulation reference. CLEAN-only path to clone the behavior:
- **One modulated fractional-delay line** (linear/allpass-interp read pointer) is the whole engine. Building blocks: fractional delay (Lagrange/allpass), LFO bank (sawtooth for barberpole/ramp, triangle for flange/UpDown, multiple phase-offset LFOs for ensemble).
- **Barberpole glide:** ramp the read-delay linearly (sawtooth) with smooth wrap crossfade → `Δf = f₀·(dτ/dt)`, and `dτ/dt = depth_s·rate_Hz`. Crossfade two delay taps a half-cycle apart to mask the sawtooth reset (the "endless" trick). This reproduces the measured proportional-to-f₀ shift exactly (do NOT use a Hilbert shifter — that would give the *wrong* fixed-Hz behavior).
- **Through-zero flange:** let the modulated tap delay go to/through the dry-path delay so they coincide → momentary null; mix dry+wet with ± polarity.
- **Feedback:** recirculate the delay output, gain = feedback (signed, ±1); |g|→1 gives resonant/self-osc comb. Sign flips tooth polarity.
- **Mix:** equal-power `out = cos(θ)·dry + sin(θ)·wet`, θ = (π/2)·mix.
- Latency 0; no oversampling needed at these mod depths.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (reproduce black-box before shipping). All numeric DSP facts here are CLEAN (pedalboard); only the `VPlug_*`/`VMod_*`/`WarpVSTParameter` names are REF (symbol table).
