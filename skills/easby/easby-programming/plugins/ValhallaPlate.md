# ValhallaPlate — Valhalla DSP (Plate Reverb)

| | |
|---|---|
| Vendor / ver | Valhalla DSP, LLC · v1.6.8 (Jan 2023 build) |
| Type | Algorithmic **plate reverb** (EMT-140-style) — 12 "material" algorithms, dense diffusion, no discrete early reflections |
| Tech | C++ / JUCE (WebKit-capable UI, 3 LookAndFeel eras 1970s/1980s/2010s); Accelerate/vDSP linked. Engine class `VPlug_Plate` + `VMod_*` DSP building blocks. NO FFI boundary. |
| Binary | Universal (x86_64 + arm64) MH_BUNDLE. **No DRM** (no PACE/iLok/Eden). **Not stripped** (10513 syms → full REF roster). |
| Provenance | All behavior **CLEAN** (pedalboard black-box). Internal class/method names **REF** (symbol table, quarantined — names only, no decompile). |
| Measured on | ValhallaPlate (Jan 2023 build, v1.6.8) · 48kHz · pedalboard 0.9.17 · 2026-06-27 |
| Source | `private-research/Valhalla/Plate/` (scripts `plate_probe.py`, `plate_eq2.py`; `measured_summary.json`, `impulse_chrome_decay3s.wav`); REF `private-research/_quarantine_disasm/Valhalla/Plate/` |

## Signal chain
```
x(stereo) ──► [predelay  0–500 ms]  (+ ~21.3 ms intrinsic diffusion build-in)
          ──► PLATE TANK  (1 of 12 'material' algorithms; modulated delay network,
                           dense allpass-style diffusion, instant build-up, NO early reflections)
                 • decay  → tail length (RT60)
                 • size   → modal density / mode spacing (early)
                 • intrinsic freq-dependent damping: HF decays ~3× faster than LF (baked, per type)
                 • mod (TriOsc → smoothed delay read) → tail chorusing / pitch wobble
          ──► width  (M/S side-channel gain: 0 = mono, 100 = natural, >100 = over-wide)
          ──► loweq shelf (±12 dB @ loweqfreq) · higheq shelf (±12 dB @ higheqfreq)  [STATIC output tone]
          ──► mix  (dry/wet blend, ~linear)  ──► y
```
PDC = **0 samples** (reported & impulse-confirmed; not a linear-phase/lookahead design).

## Per-stage formula (tag each CLEAN or REF)
- **Engine dispatch** (REF, symbols only): `VPlug_Plate::processBlock{Material}[Filter]Plate(float const**, float**, int, int)` — 12 hand-written per-material kernels, each with a `…DoubleDownsampled` 2× sibling (oversampled path, e.g. high-SR). Per-type `setDecay{Material}Plate()` + `setReverbSize{Material}Plate(float)`. Building blocks: `VMod_DelayLine` (`ReadaiBlockSmoothed` = fractional/smoothed interpolated read ⇒ **modulated delay**), `VMod_Biquad`, `VMod_TriOsc` (triangle LFO), `VMod_Rotate` (stereo/feedback rotation), `VMod_Upsample`/`Downsample`/`IIRPolyphase` (2× oversampling). **Names only — not decompiled; reproduce black-box to ship.**
- **decay → RT60** (CLEAN): near-1:1. decay 0.5 s→RT60 0.73 s, 1.0→0.99, 3.0→2.58, 8.0→7.96, 30.0→32.4. ⇒ **RT60 ≈ decay (k≈1.0)**; the knob is calibrated directly in RT60 seconds. (Tighten at long decays; ~+10–45 % scatter at short.)
- **size (0–200 %)** (CLEAN): RT60 ~constant (≈2.58 s across 0→200 %); controls **early density / mode spacing only** — density-fraction in first 30 ms falls 0.46→0.32→0.18→0.07→0.00 as size 0→50→100→150→200 %. Larger plate = sparser, more-spaced early modes (longer delays between reflections); smaller = denser, more metallic flutter. Decoupled from decay.
- **width (0–200 %)** (CLEAN): **M/S side-channel gain**. LR-corr 1.00(0 %)/0.72(50)/0.02(100)/−0.22(150)/−0.38(200); side−mid energy −137/−7.9/−0.2/+1.95/+3.48 dB. 0 %=mono collapse, 100 %=naturally decorrelated stereo (side≈mid), >100 %=side boosted past unity ⇒ synthetic over-wide (anti-correlated).
- **predelay (0–500 ms)** (CLEAN): **onset = predelay_param + 21.3 ms intrinsic**, slope exactly 1.0 (Δ 21.2–21.4 ms across the whole range). The intrinsic 21 ms = the diffusion ramp-in before the tank reaches level (impulse peak lands ~130 ms in at decay 3 s).
- **loweq / higheq (±12 dB @ tunable freq)** (CLEAN, **DECISIVE**): **static low/high shelving filters on the wet output — NOT decay-rate EQ.** low_boost+12@700Hz tilts the steady wet spectrum +11.9 dB@100Hz → +0.3 dB@10k (low-shelf, corner ≈ loweqfreq); high_boost+12@8k = +10.5 dB@10k → 0 dB@LF (high-shelf). loweqfreq **sweep moves the corner** (20 Hz→inert, 700 Hz→acts <700, 2 kHz→acts <2 k). Per-band **RT60 is unchanged** by the EQ params (4.52→4.54 s low; 1.60→1.62 s high) ⇒ magnitude/tone only, not decay rate.
- **intrinsic frequency-dependent decay** (CLEAN): with EQ flat the tank itself damps HF: band RT60 ≈ **4.5 s @200 Hz, 3.7 s @1 k, 1.6 s @8 k** (Chrome, decay 0.6). This "material absorption" is baked per type (separate from user EQ) and is what distinguishes the 12 algorithms tonally.
- **mod (rate 0.05–5 Hz, depth 0–100 %)** (CLEAN): **tail chorusing / pitch wobble** via `VMod_TriOsc`-driven smoothed delay reads. Inst-freq deviation of a sustained 1 kHz carrier in the tail: std 2.6 Hz (off) → 15.4 Hz (50 %) → 23.4 Hz (100 %). Monotone with depth; smooths metallic ringing and adds lush movement.
- **mix** (CLEAN): dry/wet blend, ~linear crossfade. corr-with-dry 0.99→0.98→0.92→0.71→0.00 at 0/25/50/75/100 %; at 100 % output is pure wet (corr→0). Wet is decorrelated from dry, so summed RMS dips mid-travel (0.098→0.074→0.039) rather than equal-power.

## 12 material algorithms (CLEAN measured; tier descriptions cross-checked vs in-binary marketing strings = REF)
Type enum is normalized **raw ∈ [0, 0.5]** in 1/24 steps (band centers below); raw > 0.5417 wraps to Chrome. Measured at decay 3 s, size/width 100 %, EQ flat:

| # | type | raw center | RT60 s | centroid Hz (bright→dark) | early density | character (REF string ↔ measured) |
|---|---|---|---|---|---|---|
| 0 | Chrome | 0.0208 | 2.58 | 3852 | med | medium attack, bright |
| 1 | Steel | 0.1042 | 2.72 | 3684 | high | medium attack, darker than Chrome |
| 2 | Cobalt | 0.1458 | 2.81 | 3936 | low/slow build | soft attack, dark, resonant |
| 3 | Brass | 0.1875 | 2.78 | 3171 | high, fast build (34 ms) | sharp attack, bright (darkest centroid here = strong LF) |
| 4 | Copper | 0.2292 | 3.35 | 3665 | high | soft attack, high modal density, dark |
| 5 | Aluminum | 0.2708 | 3.21 | 3745 | high, fast build | medium attack, high modal density, bright |
| 6 | Unobtanium | 0.3125 | 3.50 | 4578 | high | soft attack, high density, longer HF decay |
| 7 | Osmium | 0.3542 | **4.44** | **3018** (super dark) | slow build (81 ms) | mono in, soft attack, super dark, long bass decay |
| 8 | Adamantium | 0.3958 | 2.56 | **6773** (airy) | med | mono in, medium attack, bright, airy |
| 9 | Titanium | 0.4375 | 2.94 | **7652** (brightest) | slow build | mono in, soft attack, darker?? — measured brightest HF |
| 10 | Radium | 0.4792 | 2.58 | 6594 | med | parallel stereo, medium attack, bright |
| 11 | Lithium | 0.5 | 2.92 | 3571 | high | soft attack, high density, dark |

Tiers vary along three axes: **brightness** (centroid 3018 Osmium … 7652 Titanium), **density / attack build-up** (34 ms Brass/Aluminum = sharp/dense … 81 ms Osmium = soft/slow), and **decay multiplier at fixed `decay`** (×0.85 Adamantium … ×1.48 Osmium). All tails fully decorrelate L/R (corr ≈ 0). "Mono input" types (Osmium/Adamantium/Titanium) and "parallel stereo" (Radium) are REF descriptions of their input summing.

## Why / design rationale (music ↔ code)
- **Dense diffusion, zero early reflections** → emulates a steel **plate** (EMT-140): a vibrating sheet has no "room geometry", so the impulse response is *immediately dense* (no discrete ER taps like a room/hall). Black-box confirms instant build-up (density fills within tens of ms, no isolated echoes). Purpose: smooth, lush sustain that sits behind vocals/drums without slap.
- **12 "metal" names = density + brightness + damping tiers**, not literal physics. Chrome/Aluminum/Adamantium = bright & airy (fast HF, high centroid) for vocals/snare sheen; Osmium/Cobalt/Copper = dark/resonant (low centroid, long bass) for pads/ambient; Brass = sharp/bright attack for percussive plates. Giving them material names (vs numbers) is UX so users pick by *feel*. Hand-written per-type kernels (12 distinct `processBlock*`) let each have its own diffuser topology/coefficients rather than one parametric engine — Valhalla's signature voicing-by-handcraft.
- **Intrinsic HF-faster decay (4.5 s LF / 1.6 s HF) baked into the tank** → real plates/rooms absorb highs faster (air + material loss); modeling it in the feedback (frequency-dependent damping) gives a *natural* darkening tail. Keeping this separate from the user EQ means the reverb always sounds "right" before you touch tone.
- **User loweq/higheq = STATIC output shelves, deliberately NOT decay-rate EQ** → simpler, predictable tone control (cut mud / add air to the *whole* wet signal) without re-tuning the tank's damping per band. Trade-off vs FabFilter Pro-R2 (which does frequency-dependent RT60): Valhalla puts the artful damping in the algorithm and gives the user a plain tone tilt — fewer knobs, more "it just sounds good".
- **size decoupled from decay** (density vs length) → lets users dial plate *dimension*/character independent of tail length; >100 % exaggerates beyond a physical plate for synthetic huge-plate sounds. Modulated delay reads (`ReadaiBlockSmoothed` + TriOsc) → **tail chorusing** breaks up metallic resonances and adds shimmer/lushness — the classic "Valhalla movement". Triangle LFO (not sine) gives a more even, less periodic-sounding sweep.
- **width as M/S side-gain, 0–200 %** → mono-compatible at 0 %, natural decorrelated stereo at 100 %, hyped width >100 % for modern wide productions; cheap and phase-safe (operates on the already-decorrelated wet, so >100 % stays usable rather than collapsing).
- **2× oversampled (`DoubleDownsampled`) sibling per type** → suppresses aliasing from the nonlinear/modulated delay network at the cost of CPU; switched by SR/quality.

## Parameters
| param | unit | range | norm→real taper | notes |
|---|---|---|---|---|
| mix | % | 0–100 | linear | dry/wet, ~linear crossfade |
| predelay | ms | 0–500 | mild exp (0.1→2.4, 0.5→100, 0.9→391.5 ms) | onset = param + 21.3 ms intrinsic |
| decay | s | 0.5–30 | exp (0.5→0.73, 0.8→8, 0.9→15.7 s) | **= RT60 (k≈1.0)** |
| size | % | 0–200 | linear (0.5→100 %) | early density / mode spacing; RT60-independent |
| width | % | 0–200 | linear | M/S side gain; 100=natural, >100=over-wide |
| modrate | Hz | 0.05–5 | exp (0.5→1.0 Hz) | LFO speed (TriOsc) |
| moddepth | % | 0–100 | linear | tail pitch-wobble/chorus amount |
| loweqfreq | Hz | 20–2000 | ~linear (0.5→1000) | **static** low-shelf corner |
| loweqgain | dB | −12…+12 | linear | low shelf |
| higheqfreq | Hz | 200–20000 | ~linear (0.5→10 k) | **static** high-shelf corner |
| higheqgain | dB | −12…+12 | linear | high shelf |
| type | enum | 12 materials | raw∈[0,0.5], 1/24 steps; centers in table above | hand-written per-material kernels |
| bypass | bool | Off/On | — | |

**Harness note (CLEAN):** pedalboard `raw_value` is the VST3 NORMALIZED [0,1], not real units — convert real→raw via the tapers. The `type` enum: a raw landing exactly on a 1/24 boundary rounds DOWN to the prior band (read identical neighbors); probe at **band centers (2i+1)/48** to hit all 12 distinctly.

## FFI contract (if clean C ABI)
None — pure JUCE plugin, hosted via VST3. No exported C DSP entry points.

## CLEAN measurements
See `private-research/Valhalla/Plate/measured_summary.json` (full tables) + `impulse_chrome_decay3s.wav`. Headlines: 12 types (RT60 2.56–4.44 s, centroid 3.0–7.7 kHz @decay3s); RT60≈decay 1:1 (0.73 s@0.5 → 32.4 s@30); size = early density only (RT60 flat); width = M/S side gain (corr 1.0→−0.38 over 0–200 %); predelay = param+21.3 ms; EQ = static shelves (low ±12@700: +11.9 dB@100Hz; corner tracks freq); intrinsic HF-faster decay 4.5/3.7/1.6 s @200/1k/8k; mod = tail wobble std 2.6→23.4 Hz.

## To implement (CLEAN-only path for product)
Plate reverb is **OFF-AXIS** from ES-L (dynamics) — KB coverage, not a product target. If a plate is ever wanted, the CLEAN clone recipe (public-DSP building blocks, no vendor code):
- **Diffusion tank, no early reflections:** a chain/network of allpass diffusers (Schroeder/Dattorro-style figure-of-eight tank) tuned for *instant* density; verify density-fill in tens of ms (no discrete taps).
- **decay → RT60 ≈ 1:1** feedback-gain mapping (g = 10^(−3·loopDelay/RT60)); calibrate the knob directly in RT60 seconds.
- **Frequency-dependent damping in the loop** (one-pole LP in feedback) tuned to ~3× faster HF decay (≈4.5 s LF / 1.6 s HF) — this is the "material" tone; vary the LP cutoff + diffuser coefficients to make multiple "material" presets (brightness 3–7.7 kHz centroid tiers).
- **size = mode spacing** (scale the diffuser/loop delay lengths) decoupled from feedback gain.
- **Modulated delay reads** (fractional/interpolated, triangle-LFO driven) for tail chorusing; depth → pitch-wobble std.
- **Post: M/S width** (side gain 0–2×), **static low/high shelves** (tunable corner, ±12 dB), **linear dry/wet**.
- Building blocks to reuse from KB: allpass diffuser, one-pole damping LP, fractional delay (Lagrange/allpass interp), M/S matrix, shelving biquad. **No FabFilter Pro-R2-style decay-rate EQ needed** — Valhalla keeps tone static and damping internal.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (reference only — here: symbol-table class/method *names* only, no decompilation; reproduce black-box before shipping).
