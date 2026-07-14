# ValhallaVintageVerb — Valhalla DSP (Algorithmic Reverb)

| | |
|---|---|
| Vendor / ver | Valhalla DSP · v4.0.5 (Mar 2024 build; CFBundleVersion 4.0.5) |
| Type | Algorithmic reverb (early-digital / Lexicon-EMT lineage); delay-network (allpass-diffuser + feedback-delay tank), frequency-dependent decay, era "color" converters |
| Tech | C++/JUCE (VST3/AU), WebKit-free native JUCE editor (ComboBox/Slider), Accelerate/vDSP. Single internal reverb engine — NOT a shared engine (0 symbol overlap with sibling Valhallas) |
| Binary | `…/MacOS/ValhallaVintageVerb` — Mach-O universal (x86_64 + arm64), MH_BUNDLE, **NOT stripped of shell** (10 886 syms: JUCE + Steinberg VST3 SDK + `ValhallaVintageVerb*` AudioProcessor/Editor). **No PACE / no `LC_ENCRYPTION_INFO`**. DSP kernel is local-stripped (only AudioProcessor surface exported). Soft license gate (`isUserInfoValid`/`displayUnauthorizedAlertWindow`) — measured path fully open, real DSP confirmed. No leaked dev paths. |
| Provenance | Behavior (enums, RT60↔decay, bassmult/highshelf freq-dependent decay, predelay onset, mode/color character, filters, mix) = **CLEAN** (pedalboard black-box). Architecture (delay-network class, JUCE shell, in-app help text) = **REF** (symbol/string roster, quarantined). |
| Measured on | ValhallaVintageVerb (Mar 2024 build) · 48kHz · pedalboard 0.9.17 · 2026-06-27 |
| Source | `private-research/Valhalla/VintageVerb/` (probes `vv_probe.py`); harness `Valhalla/Tools/valhalla_sysid.py`; REF `_quarantine_disasm/Valhalla/VintageVerb/` |

## Signal chain
```
x ──► PreDelay (0–500 ms, exact) ──► [ Early-reflection / diffuser stage ]
                                         EarlyDiffusion = initial echo density
                                         Attack = early-vs-late balance / onset slope
                                              │
                                              ▼
                              [ Late reverb tank: feedback delay network ]
                                 LateDiffusion = echo-density build rate
                                 Size = reflection spacing / modal density
                                 DECAY = base mid-band decay time (tank feedback)
                                 BassMult @ BassXover  = LF decay-time shelf (in-tank)
                                 HighShelf @ HighFreq  = HF damping shelf (in-tank, per-pass)
                                 Mod (Rate/Depth)      = delay-line LFO chorus/vibrato
                                              │
                                              ▼
                       LowCut ── HighCut  (post output EQ on wet)
                                              │
                  ColorMode (70s/80s/now: bandwidth + alias character)
                                              │
                              Mix (dry/wet, dry→0 at 100%)  ──► y
```

## Per-stage formula  (tag each CLEAN or REF)
- **DSP class** (REF): single internal reverb engine in `ValhallaVintageVerb` (JUCE `AudioProcessor`); `prepareToPlay`/`processBlock(AudioBuffer<float>&)`. Kernel local-stripped → algorithm = allpass-diffuser + feedback-delay-network inferred from behavior + in-app help strings. **NOT a shared engine** (no `Generic*.dylib`, no overlap with FreqEcho/SpaceModulator/Supermassive).
- **DECAY → RT60** (CLEAN): exponential param taper 0.20 s → 70 s (raw 0→1; raw 0.5 ≈ 7 s). **Measured mid-band (1 kHz) RT60 ≈ 1.35× the DECAY label** (label is a nominal tuning value, ~74% of the true −60 dB time): label 1.42 s→RT60 1.90 s · 3.99→5.31 · 7.0→9.45. Broadband RT60 tracks the same ~1.35× factor across the whole range; relationship is monotonic and proportional.
- **PreDelay → onset** (CLEAN): **exact & linear.** wet onset = PreDelay_ms + **9.06 ms** fixed intrinsic offset (algorithm early-path latency at Size 50%). 0→9.06 · 2.38→11.46 · 11.91→20.98 · 100→109.06 · 500→509.06 ms. Param taper is exponential-ish (raw 0.5 = 100 ms). PDC reported = **0 samples** (IIR feedback reverb, zero host latency).
- **BassMult → LF decay shelf** (CLEAN): frequency-dependent RT60 below BassXover. At fixed mid/high RT60 (≈5.3 s, 2–4 kHz), the LF band (150–350 Hz) RT60 scales with the multiplier: **0.25×→1.41 s · 1.0×→4.84 s · 1.89×→8.54 s · 4.0×→15.9 s** (low/high ratio 0.31/0.91/1.52/2.72, ~proportional; HF band stays 4.5→5.85 s, ~unaffected). Crossover at BassXover is a **gentle shelf transition**, not brickwall (xover 300 Hz @4×: 170 Hz=11.0 s → 300 Hz=9.2 s → 550 Hz=6.6 s → 1.1 kHz=5.7 s).
- **HighShelf → HF damping** (CLEAN): per-pass HF decay shelf at HighFreq. Low-mid (300–600 Hz) RT60 constant ≈5.0–5.15 s; HF band (6–9 kHz @ HighFreq 6 kHz) RT60 collapses with shelf gain: **0 dB→5.52 s · −7.2 dB→2.49 s · −12 dB→2.21 s · −24 dB→2.09 s**. More-negative dB = faster HF decay (air-absorption model). HighFreq sets the damping corner; HighShelf dB = damping depth/steepness.
- **Size** (CLEAN): reflection spacing / modal density — at fixed RT60 (~5.6–5.9 s), larger Size = sparser early density (zc 14.6 kHz→3.3 kHz) and later build-up (2.5→14.5 ms). Spreads the network wider without changing decay time.
- **EarlyDiffusion** (CLEAN): initial echo density (0–40 ms): 0%→~525–775 zc (crest 27, spiky) → 100%→2725 zc (crest 12.6, smooth/dense).
- **LateDiffusion** (CLEAN): echo-density build rate (200–400 ms): 100%→16–17 k zc → 0%→6 k. Both diffusions at 0% → near-discrete echo network (130 zc, crest 32).
- **Attack** (CLEAN, mode-dependent): early-reverb envelope shaping / early-vs-late balance (help: "larger Attack % = longer attack time"; in Ambience/Sanctuary/Nonlin it remaps to ER level / slope). Reshapes the initial ~3–16 ms onset.
- **Mod (Rate/Depth)** (CLEAN): delay-line LFO chorus/vibrato in the tank. Depth scales LFO excursion → detected coherent mod-rate rises with depth (2.7→4.7→10.7 Hz at Rate≈2.5 Hz); base instantaneous-freq jitter ~260–285 Hz from inherent random/chorused modulation. ModRate linear 0.1–10 Hz.
- **HighCut / LowCut** (CLEAN): post-reverb output filters on the wet (distinct from in-tank HighShelf/BassMult). HighCut = gentle LP (1280 Hz drops 4k/10k/16k by 12/19/22 dB, ~6–12 dB/oct). LowCut = HP (760 Hz drops 30/60/120 Hz by 24/18/12 dB). Output-stage EQ only — does not alter decay rate.
- **ColorMode** (CLEAN): **3 eras = converter/bandwidth models.** **seventies** = steep HF band-limit (12–20 kHz tail = **−29 dB** vs eighties/now's +5.5 dB ⇒ ≈34 dB darker top octave) **plus** a low-level alias/imaging product (10.25 kHz image + 250 Hz, ≈−59 dB on an 11 kHz tone) absent in the others. **eighties** & **now** = full bandwidth, spectrally near-identical at tail level (their documented difference is finer mod/internal-processing era, below black-box resolution here). Residual noise floor all clean: 70s −93.4, 80s/now −90.6 dBFS (color is bandwidth/alias, not added hiss).
- **Mix** (CLEAN): dry/wet blend; **dry fully removed at 100%** (−151 dB = true zero). Dry attenuation 0→100%: −9.1 → −9.8 → −12.1 → −17.5 → −∞ dB (steeper than linear near top ⇒ ≈equal-power crossfade on dry); wet roughly constant. Mix-lock UI flag exists (help string) but does not alter the law.

## Why / design rationale (music ↔ code)
- **Algorithmic delay-network (not convolution)** → infinite/continuous decay, real-time-tweakable size & decay, modulated tail → the lush "Valhalla" sound. Convolution can't morph RT60/size live or self-modulate. Lexicon/EMT lineage = allpass diffusers feeding a feedback tank.
- **DECAY label < measured RT60 (~0.74×)** → the knob is calibrated to *musical* perceived decay (the audible "tail length" reads shorter than the −60 dB physics time), and is the tank-feedback tuning parameter, not a literal RT60 readout. Designer-voiced, not metrological.
- **BassMult (LF decay shelf) + HighShelf (HF damping) = frequency-dependent RT60** → models real-room absorption: air absorbs highs fast (HighShelf shortens HF tail), large rooms ring longer in the bass (BassMult > 1 lengthens LF tail). Two independent shelves around mid DECAY give natural, tunable spectral decay tilt — the single biggest realism lever in algorithmic reverb.
- **PreDelay (exact, +9 ms floor)** → depth/distance cue + separates dry transient from wet wash for clarity on vocals/drums. Linear & accurate because it's a literal pre-tank delay line.
- **Early vs Late Diffusion split** → EarlyDiffusion = smoothness of the onset (high = creamy, low = grainy/discrete echoes for "vintage" or special FX); LateDiffusion = how fast the tail thickens to a smooth wash. Decoupling them lets one dial density independently of attack texture.
- **Size = reflection spacing (decoupled from decay)** → physically scales the room (delay lengths) without retuning decay; bigger = sparser/later early energy = sense of a larger space. Keeping RT60 constant under Size lets the user set "how big" and "how long" independently.
- **Mod (delay-line LFO chorus)** → de-correlates/animates the tail → avoids metallic ringing & flutter in long decays, adds the signature "chorused" shimmer; depth-scaled excursion trades realism (subtle) vs lush effect (heavy).
- **ColorMode = era converters** → the headline "Vintage" hook: **70s = dark + band-limited + slight aliasing** (early digital reverbs' low sample rate / converter grit → warm, smaller-sounding), **80s = brighter/grittier** (next-gen converters), **now = clean HD** (modern full-bandwidth). One control time-travels the *fidelity*, not the algorithm — bandwidth + alias character carry the vintage feel while RT60/diffusion stay constant.
- **HighCut/LowCut as output EQ (separate from in-tank damping)** → lets the user tame the wet's spectral footprint in a mix (carve mud / fizz) without changing the *decay-rate* shaping — mixing EQ vs physics EQ kept distinct.

## Parameters
| param | unit | range | taper / notes (raw = VST3 NORMALIZED [0,1]) |
|---|---|---|---|
| mix | % | 0–100 | linear; dry→0 (true) at 100%, ≈equal-power crossfade on dry. raw=real/100 |
| predelay | ms | 0–500 | exp-ish (raw 0.5≈100 ms); onset = value + 9.06 ms floor, exact/linear |
| decay | s | 0.20–70 | **exponential** (raw 0.5≈7 s); mid RT60 ≈ 1.35× label. raw≠linear — use taper |
| size | % | 0–100 | reflection spacing/density; RT60-independent |
| attack | % | 0–100 | early-envelope shape / ER balance (mode-dependent meaning) |
| bassmult | × | 0.25–4.0 | LF decay multiplier below bassxover; ~proportional. raw 0.5=1.0× (exp taper) |
| bassxover | Hz | 100–10000 | LF/mid split for bassmult; exp taper (raw 0.5≈700 Hz). gentle shelf transition |
| highshelf | dB | −24–0 | HF damping depth (in-tank); linear in dB. 0 dB=no damping, −24=fast HF decay |
| highfreq | Hz | 100–20000 | HF damping corner; exp taper (raw 0.5=6000 Hz) |
| earlydiffusion | % | 0–100 | initial echo density |
| latediffusion | % | 0–100 | echo-density build rate |
| modrate | Hz | 0.1–10 | LFO rate (linear; raw 0.5≈5 Hz) |
| moddepth | % | 0–100 | LFO excursion → tail chorus/vibrato amount |
| highcut | Hz | 100–20000 | output LP on wet; exp taper (raw 0.5=6000 Hz) |
| lowcut | Hz | 10–1500 | output HP on wet; near-linear (raw 0.5=760 Hz) |
| colormode | enum(3) | seventies / eighties / now | raw 0–0.66=70s, 0.67–0.99=80s, 1.0=now |
| reverbmode | enum(22) | see list | 22 algorithms; each raw band ≈0.046 wide |
| bypass | bool | Off/On | raw ≥0.5 = On |

### reverbmode — COMPLETE ordered list (22) [CLEAN]
`raw ≈ index/21.5`; per-value raw centers below.
| idx | name | raw center | idx | name | raw center |
|---|---|---|---|---|---|
| 0 | Concert Hall | 0.000 | 11 | Smooth Plate | 0.52 |
| 1 | Plate | 0.10 | 12 | Smooth Room | 0.56 |
| 2 | Room | 0.14 | 13 | Smooth Random | 0.61 |
| 3 | Chamber | 0.18 | 14 | Nonlin | 0.65 |
| 4 | Random Space | 0.23 | 15 | Chaotic Chamber | 0.69 |
| 5 | Chorus Space | 0.27 | 16 | Chaotic Hall | 0.73 |
| 6 | Ambience | 0.31 | 17 | Chaotic Neutral | 0.77 |
| 7 | Bright Hall | 0.35 | 18 | Cathedral | 0.81 |
| 8 | Sanctuary | 0.39 | 19 | Palace | 0.86 |
| 9 | Dirty Hall | 0.44 | 20 | Chamber1979 | 0.90 |
| 10 | Dirty Plate | 0.48 | 21 | Hall1984 | 0.94 |

### colormode — COMPLETE list (3) [CLEAN]
seventies (raw 0.0–0.66) · eighties (0.67–0.99) · now (1.0).

## FFI contract
N/A — JUCE VST3, no clean C ABI exposed; driven via pedalboard host (normalized params only).

## CLEAN measurements
- **decay→RT60** (Concert Hall, Size 50%, mid 1 kHz): 1.42 s→1.90 · 3.99→5.31 · 7.0→9.45 (≈1.35×). Broadband: 0.23 s→0.82 · 1.42→1.93 · 3.99→5.40 · 7.0→9.49 · 12.75→17.3.
- **predelay→onset** (ms): 0→9.06 · 2.38→11.46 · 11.91→20.98 · 100→109.06 · 500→509.06 (= label + 9.06 ms).
- **bassmult LF RT60** (150–350 Hz, mid≈5.3 s): 0.25×→1.41 · 1.0×→4.84 · 1.89×→8.54 · 4.0×→15.9 s.
- **highshelf HF RT60** (6–9 kHz @ 6 kHz; lowmid 300–600 Hz≈5.1 s const): 0 dB→5.52 · −7.2→2.49 · −12→2.21 · −24→2.09 s.
- **mode character** (DECAY 3.99 s eq.): Concert Hall RT60 5.40 s / buildup 14.5 ms / zc 6.3 kHz · Plate 3.76 / 33.6 / 15.2 k · Chamber 4.18 / 28.4 / 16.4 k · Cathedral 4.62 / 2.5 / 2.6 k.
- **colormode tail spectrum** 12–20 kHz band: seventies −29 dB · eighties +5.5 · now +5.5 dB. seventies alias product ≈−59 dB (10.25 kHz + 250 Hz); 80s/now none.
- **mix dry attenuation**: 0%→−9.1 · 25→−9.8 · 50→−12.1 · 75→−17.5 · 100→−∞ dB.
- **output filters**: HighCut 1280 Hz → 4k/10k/16k −12/−19/−22 dB; LowCut 760 Hz → 30/60/120 Hz −24/−18/−12 dB.

## To implement
CLEAN-only path (off-axis from ES-L's dynamics core — reverb building block for the KB):
- **Topology**: allpass-diffuser input chain (EarlyDiffusion = #stages/coeff) → feedback delay network tank (LateDiffusion = nested-allpass build; Size = delay lengths; DECAY = feedback gain tuned so mid RT60 ≈ 1.35× the displayed value). Add modulated delay lines (Mod) to de-correlate the tail.
- **Frequency-dependent decay** = two shelves in the feedback path: a **LF shelf** at BassXover scaled by BassMult (LF feedback gain × multiplier) and a **HF damping shelf** at HighFreq with depth = HighShelf dB (lossy 1-pole LP per delay tap). This is the core realism lever — reuse the shelf-in-feedback pattern.
- **PreDelay** = simple pre-tank delay line (sample-exact) + ~9 ms intrinsic ER offset.
- **Output EQ** = post LP (HighCut) + HP (LowCut), gentle 1st/2nd-order.
- **Color/era** = optional bandwidth-limit + mild alias model (downsample-and-up or band-limit) for "vintage"; bypass for "now".
- **Mix** = equal-power dry/wet crossfade, dry→0 at 100%.
- Building blocks to add to `building-blocks/`: nested-allpass diffuser, FDN with damped feedback, shelf-in-feedback (freq-dependent RT60), modulated fractional delay.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (reference only — reproduce black-box before shipping).
