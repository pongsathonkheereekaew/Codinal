# ValhallaUberMod — Valhalla DSP (multi-tap modulated delay / chorus / flanger / echo engine)

| | |
|---|---|
| Vendor / ver | Valhalla DSP · v1.2.8 (Jan 2023 build) |
| Type | Multi-tap modulated delay → chorus / flanger / ensemble / echo / Dimension-D superset (16-voice modulated tap bank + allpass diffuser + in-loop drive) |
| Tech | C++ / JUCE + WebKit (HTML) UI. Engine `VPlug_Chorus` over shared `VMod_DelayLine` primitive (REF). No FFI. |
| Binary | universal x86_64+arm64 MH_BUNDLE, **not stripped** (full local symbol table), **no DRM** (no `LC_ENCRYPTION_INFO`; serial-key only → pedalboard loads unauthorized). pdc=0. |
| Provenance | All DSP numbers CLEAN (pedalboard black-box). Class/method roster + arch = REF (`nm`+`c++filt`, no Ghidra). |
| Measured on | ValhallaUberMod v1.2.8 · 48 kHz · pedalboard 0.9.17 · 2026-06-27 |
| Source | `private-research/Valhalla/UberMod/` (probe.py, wetdiff.py, typesweep.py, measurements.json) · REF `_quarantine_disasm/Valhalla/UberMod/` |

## Signal chain
```
                        ┌─ (drive Pre) ──┐
x → inputpan-route → [ saturate? ] → MULTI-TAP DELAY BANK (1..16 wet taps; type 0-9)
                                          │   tap times: delay(longest)×spread, ±skew(L/R), ±random jitter
                                          │   tap gains: slope ramp (fade-in↔out) ×tapgain
                                          │   pitch mod per tap: detune(dual-voice) + vibrato(FM), ×overmod
                                          ▼
                                     [ feedback ] ──(loop: lowcut HP + highcut LP + feedbackrotate stereo matrix)──┐
                                          │                                                                          │
                                          ▼                                                                          │
                                  [ diffusion allpass cloud (diffenable) ]  ←──────────────────────────────────────┘
                                          │
                              [ drive (Post) + noise ] → stereowidth (M/S) → colormode (Bright/Dark) → MIX(dry+wet)
```
- `colormode` (Bright/Dark) and `speed` (1X / 1/2X) are GLOBAL toggles selecting per-mode `processBlock*` variants (REF), not separate stages.

## Per-stage formula  (tag each CLEAN or REF)
- **type / mode select** (CLEAN): declared 0-24 (25 values, continuous raw=N/24) but **ONLY type 0-9 produce DSP**; `type ≥ 10` is bit-exact dry (wetdiff = −240 dB, verified at factory defaults). 10 distinct active behaviors. Wet-tap counts (excl. direct) modes 0→9 = **1,1,2,3,3,3,4,8,8,16** (geometric ladder; 0≈1 and 3≈4 are raw→index quantization dups). REF families (9): `8Tap/16Tap/32Tap/6TapRandom/16Phase/DimD/DualEnsemble/SuperSix/VP330`.
- **delay** (CLEAN): sets the **longest** tap time, ms. ≈1:1 with displayed ms at mid/high values (raw 0.5→497 ms, 1.0→938 ms); low end compressed by spread. Range 0-1000 ms.
- **spread** (CLEAN): tap **time distribution** between 0 and longest. 0% = all taps clustered at the far end (slapback cluster); 50% = evenly spaced; 100% = clustered toward the front (dense early onset).
- **slope** (CLEAN, ±100%): tap **gain envelope vs time** (times fixed). −100% = fade-IN (early quiet → late loud, −27→−4 dB); 0% = flat (~−12 dB); +100% = fade-OUT (early loud → late quiet, −7→−24 dB = natural echo decay).
- **skew** (CLEAN, ±100%): per-channel tap-time scale = **stereo offset** (Haas). <0 shortens LEFT taps (lean left), 0 = L≡R, >0 shortens RIGHT taps. e.g. raw 0 → L first tap 104.7 ms vs R 118.6 ms.
- **random** (CLEAN): pseudo-random per-tap **time jitter** (organic irregularity). Each tap perturbed up to a few ms, scaling with %.
- **tapgain** (CLEAN, ±12 dB): output gain trim on the wet/delayed taps only.
- **feedback** (CLEAN): recirculates the longest tap → repeating echoes (fb 0.5 → 72 echoes, 0.9 → 505).
- **feedbackrotate** (CLEAN, 0-100%): stereo feedback **rotation matrix**. 0% = parallel mono (L→L only, R−L = −147 dB); 50% = full L/R mix (R−L = 0 dB); 100% = ping-pong (L→R fully, R−L = +45 dB). Continuous interpolation.
- **detune** (CLEAN): **dual-voice symmetric detune** (one sharp + one flat voice, equal amplitude) via triangle-LFO-modulated delay read (REF `VMod_TriOsc`→`ReadiBlockSmoothed`). `detunedepth` = pitch deviation: at 2 kHz, depth 0.3→±13 Hz, 0.7→±30 Hz, 1.0→±43 Hz (≈±37 cents, Δf ∝ carrier). `detunerate` (0.01-10 Hz) = LFO speed (sideband smear).
- **vibrato** (CLEAN): faster **single-voice FM warble** LFO (rate 0.05-20 Hz). depth deviation at 2 kHz/6 Hz: 0.3→±24 Hz, 0.6→±48 Hz, 1.0→±90 Hz (carrier collapses = true vibrato).
- **overmod** (CLEAN, 1-100×): **linear multiplier on detune deviation** (extreme through-zero/barberpole). At depth 0.5: 1×→±18 Hz, 10.9×→±124 Hz, 30.7×→±336 Hz, 100×→±1083 Hz (2 kHz → 915..3082 Hz).
- **drive** (CLEAN): symmetric **odd-harmonic soft-clip** (tanh-class; H2/H4 ≈ −130 dB = no even harmonics). THD vs `driveingain`: 0 dB→1.1 %, 6→3.7 %, 12→10.4 %, 18→20.4 %, 24→29.9 % (H3 dominant −39→−11 dB). `driveprepost`: **Pre** = saturate input to delays; **Post** = saturate delay output. Oversampled (REF `VMod_Upsample/IIRPolyphase/Downsample`). `driveoutgain` −24..0 dB makeup.
- **drivenoisegain** (CLEAN, −120..−30 dB): additive **broadband noise floor** (lo-fi/tape hiss), gated by `drive` ON. 1:1 calibrated (set −90 dB → −90.0 dB out).
- **lowcut / highcut** (CLEAN): **in the feedback loop** (cumulative across repeats). lowcut = highpass (raw 0.3 ~1 kHz → 200-500 Hz −35 dB); highcut = lowpass (raw 0.3 → 6-10 kHz −35 dB, darkens each repeat).
- **diffusion / diffenable / diffsize / diffmodrate / diffmoddepth** (CLEAN): allpass **diffuser** (REF `VMod_DiffChorus2`/`AllpassiBlockSmoothed`) adding echo density — off=2 taps, 0.5→487, 1.0→1540 echoes. diffsize 10-500 ms = diffuser length; diffmod* chorus the allpass.
- **speed** (CLEAN): 1X = full SR (brighter); 1/2X = engine at half SR (darker + delays ~doubled, 163.7→396.6 ms).
- **stereowidth** (CLEAN, 0-200%): M/S width on wet. 0% = mono (corr 1.0), 100% = stereo (0.32), 200% = super-stereo (corr −0.55, side > mid +5.4 dB).
- **colormode** (CLEAN): Bright = full bandwidth; Dark = HF damped per repeat (6-10 kHz −12 dB).
- **inputpan** (CLEAN, 0-8): discrete routing of L/R inputs into the delay lines (9 modes) — *sampled, not exhaustively mapped*.
- **smoothingtime** (CLEAN/REF tooltip, 1-1000 ms): rate delay-time changes are smoothed — short = fast/clicky, long = tape pitch-glide. *Documented, not separately swept.*
- **delaysync** (0-17): tempo subdivision — **DEFERRED to REAPER** (needs host transport).

## Why / design rationale (music ↔ code)
- **One modulated-tap engine spanning chorus→flanger→ensemble→echo→Dimension-D** → a "do-anything modulation box": short modulated taps = chorus/flanger; many gain-shaped taps = ensemble/string-machine; long fed-back taps = echo. The named modes (REF `SuperSix`=Roland Dimension-D/Juno six-voice, `VP330`=VP-330 string ensemble, `DimD`=Dimension-D, `DualEnsemble`) are *voicings* of the same tap bank → musicians get vintage-box character without separate plugins.
- **slope + skew + random + spread** → organic, non-uniform tap distribution. Real ensembles/strings aren't periodic; jitter (random) + amplitude ramps (slope) + stereo time-skew = lush, un-mechanical width instead of a comb-filtered metallic chorus.
- **detune as dual-voice symmetric (±) pitch** → the classic Valhalla "fat" detune: a sharp + flat voice beating against the dry → wide, shimmering thickness (vs single-voice vibrato which is a wobble). Triangle-LFO-driven constant-slope delay = near-constant pitch offset (barberpole-flavored), not a sine warble.
- **overmod 1-100×** → deliberate "break it" control: pushes detune into through-zero / barberpole / sci-fi pitch chaos. Musical purpose = sound-design extremes the normal depth range can't reach (tooltip literally warns "use caution").
- **drive (odd-harmonic) + noise, in/around the loop, Pre/Post** → lo-fi / tape / BBD character: symmetric soft-clip adds odd-harmonic grit, in-loop highcut/lowcut darken+thin each repeat (BBD/tape echo decay), added hiss completes the analog-degradation illusion. Pre vs Post chooses whether the *source* or the *echoes* are dirtied.
- **feedbackrotate (parallel→mix→ping-pong)** → evolving stereo feedback from a single knob — dual-mono for tight doubles, cross-mixed for swirling width, ping-pong for the bouncing-echo cliché — without rerouting.
- **diffusion (allpass cloud)** → blurs discrete echoes into a smooth reverberant smear → bridges delay and reverb (a "diffuse delay" / soft ambience) so one box covers both.
- **in-loop lowcut/highcut** → keeps feedback from accumulating mud (HP) or harshness (LP); the cumulative darkening per repeat is *the* tape/BBD echo signature.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| type | idx | 0-24 (raw N/24) | **only 0-9 active**; ≥10 = dry. 10 modes / 9 REF families. |
| mix | % | 0-100 | dry↔wet |
| depth | % | 0-100 | master modulation depth |
| delay | ms | 0-1000 | longest tap time |
| feedback | % | 0-100 | echo regen |
| spread | % | 0-100 | tap time distribution (late→even→early) |
| slope | % | −100..100 | tap gain ramp (fade-in↔flat↔fade-out) |
| skew | % | −100..100 | L/R tap-time offset (stereo) |
| random | % | 0-100 | per-tap time jitter |
| tapgain | dB | −12..12 | wet-tap trim |
| detunerate | Hz | 0.01-10 | detune LFO speed |
| detunedepth | % | 0-100 | detune pitch deviation (±, dual-voice) |
| vibratorate | Hz | 0.05-20 | vibrato LFO speed |
| vibratodepth | % | 0-100 | vibrato FM deviation |
| overmod | × | 1-100 | detune-depth multiplier (extreme) |
| diffenable | bool | Off/On | engage allpass diffuser |
| diffusion | % | 0-100 | echo density |
| diffsize | ms | 10-500 | diffuser length |
| diffmodrate | Hz | 0.01-10 | diffuser mod rate |
| diffmoddepth | % | 0-100 | diffuser mod depth |
| drive | bool | Off/On | engage drive+noise block |
| driveingain | dB | 0-24 | pre-shaper gain |
| driveoutgain | dB | −24..0 | makeup |
| drivenoisegain | dB | −120..−30 | additive noise floor |
| driveprepost | enum | Pre/Post | saturate input vs delay-output |
| lowcut | Hz | 10-2000 | highpass in feedback loop |
| highcut | Hz | 100-20000 | lowpass in feedback loop |
| spatialxover | Hz | 10-2000 | spatial crossover (default 300 Hz) — *not separately characterized* |
| feedbackrotate | % | 0-100 | stereo feedback matrix (parallel→mix→pingpong) |
| smoothingtime | ms | 1-1000 | delay-change smoothing (tape glide) |
| inputpan | idx | 0-8 | L/R→delayline routing (9 modes) |
| speed | enum | 1X / 1/2X | half-speed = darker, delays ~2× |
| colormode | enum | Bright/Dark | global HF damping toggle |
| stereowidth | % | 0-200 | M/S wet width |
| delaysync | idx | 0-17 | tempo subdivision (REAPER-deferred) |
| bypass | bool | Off/On | |

## FFI contract
None — JUCE/WebKit plugin, hosted via pedalboard. No clean C ABI.

## CLEAN measurements
See `private-research/Valhalla/UberMod/measurements.json` for full tables. Headlines:
- **Active modes**: type 0-9 only (10 behaviors); type≥10 bit-exact dry. Wet-tap ladder 1,1,2,3,3,3,4,8,8,16.
- **Delay law**: delay = longest tap (≈1:1 ms at mid/high). **Spread** = late→even→early tap distribution. **Slope** = fade-in↔flat↔fade-out gain ramp. **Skew** = L/R Haas offset.
- **Detune**: dual-voice ±, ±43 Hz @ 2 kHz @ depth 1.0 (≈±37 cents). **Vibrato**: single-voice FM ±90 Hz @ depth 1.0/6 Hz. **Overmod**: ×100 → ±1083 Hz.
- **Drive**: odd-harmonic soft-clip, THD 1.1→29.9 % over 0-24 dB ingain; Pre vs Post placement; noise floor 1:1 calibrated −120..−30 dB.
- **Feedbackrotate**: parallel(0%)→mix(50%)→ping-pong(100%). **Filters** in-loop (cumulative). **Diffusion**: 2→1540 echoes. **Width**: M/S 0-200%.

## To implement (CLEAN-only path for product)
Reusable building blocks (all re-derivable from measurement + public DSP literature):
- **Modulated fractional-delay tap bank** (allpass/Lagrange interp, smoothed read pointer for pitch) — the core; lay N taps by `delay×f(spread)`, gains by a slope-ramp, jitter by random, L/R skew.
- **Triangle-LFO dual-voice detune** (± symmetric) + separate FM vibrato LFO; overmod = scalar gain on the LFO→delay path.
- **Stereo feedback rotation matrix** R(θ): θ=0 identity, θ=π/4 50/50, θ=π/2 swap (continuous param 0-1).
- **In-loop 1-pole HP + LP** for cumulative tape/BBD darkening; **Schroeder allpass diffuser chain** for the diffusion cloud.
- **Symmetric odd-harmonic waveshaper** (tanh / cubic) with oversampling + optional additive noise — for the lo-fi drive (mirrors AS-1's symmetric path but memoryless here).
- **M/S width** = scale side vs mid (>1 = super-stereo).
For ES-L (dynamics) this is OFF-AXIS — KB coverage of Valhalla's modulated-delay archetype; the shared `VMod_DelayLine` primitive note links FreqEcho/SpaceModulator/UberMod as one family.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (reference only — reproduce black-box before shipping).
