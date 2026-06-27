# ValhallaRoom — Valhalla DSP (Algorithmic Room / Hall Reverb)

| | |
|---|---|
| Vendor / ver | Valhalla DSP · v2.0.5 (Mar 2024 build) |
| Type | Algorithmic reverb — **separate early-reflection engine + modulated late FDN/loop tank**; 3-band frequency-dependent RT60 |
| Tech | C++ / JUCE (WebKit-less classic UI: `ValhallaRoomLookAndFeel2016`). Accelerate/vDSP. Per-topology DSP kernels. |
| Binary | universal (x86_64 + arm64), **NOT stripped** (10079 syms), **no DRM** (no `LC_ENCRYPTION_INFO`, no PACE/iLok), no external deps |
| Provenance | Behaviour (curves/times/3-band RT60/ER-late/filters) = **CLEAN** (pedalboard). Architecture/class graph = **REF** (symbol roster only; no Ghidra). |
| Measured on | ValhallaRoom (Mar 2024 build, v2.0.5) · 48kHz · pedalboard 0.9.17 · 2026-06-27 |
| Source | `private-research/Valhalla/Room/` (probes+WAVs) · `private-research/Valhalla/Tools/valhalla_sysid.py` · REF `private-research/_quarantine_disasm/Valhalla/Room/` |

## Signal chain
```
                     ┌─ predelay (0–500 ms, literal delay) ─┐
x → [dry] ───────────┤                                      │
                     └→ EARLY engine: allpass-diffuser net  │
                          (earlysize, diffusion, earlymod)  ├─ earlylatemix ─→ [hicut LP] → [locut HP] → wet
                          earlysend ──────────┐             │      (tank EQ + 3-band RT60 damping inside)
                                              ▼             │
                        LATE engine: modulated FDN/loop tank│
                          (type, decay, latesize, latecross,│
                           latemod, space, 3-band RT60) ────┘
wet ── mix (linear dry/wet) ── out          latency = 0 (pure IIR feedback; no FIR/OS block)
```
- **Two independent engines summed by `earlylatemix`** (CLEAN: at elm=0 late tank is silent / ER-only; late energy rises monotonically 0→0.035→0.121→0.203→0.224 as elm 0→25→50→75→100, ER bed ~constant ~0.023). `earlysend` injects ER output into the tank input (extra density/feedback seed).
- 3-band RT60 damping + hicut/locut act **on the wet/tank path only** (dry passes clean: at mix=0, residual-vs-dry ≈ 0.011 ≈ pass-through).

## Per-stage formula (tag each CLEAN or REF)
- **type → internal topology kernel** (REF roster / CLEAN dispatch behaviour): the 12 UI names select 1 of 12 distinct `VPlug_Room::processBlock<Topo>` kernels. Mapping (REF symbol names, not 1:1 to UI order): `Big32, DarkBig32, Medium16, Bright8, Chamber32, DarkChamber32, DenseRoom32, DeepFDN4, DarkFDN16, DarkLoop4, DarkLoop8, Vintage8`. Numeric suffix (4/8/16/32) = **delay-line count (FDN/loop order)** → larger = denser tail. "Dark*" kernels = pre-darkened (extra HF damping). Each has its own `setReverbSize<Topo>` (late tank scale) + `setEarlySize<Topo>` (ER spread) + some a `setDecay<Topo>`/`setDecayLf<Topo>` (e.g. `DarkFDN16` has an explicit LF-decay setter = the bass-multiply path). REF only; behaviour confirmed black-box.
- **decay → mid-band RT60** (CLEAN): **1:1 calibrated** over the usable range. Measured mid-band (500–2 kHz) RT60: decay 0.1→0.099 s, 0.5→0.526, 1→0.995, 2→2.02, 4→4.03, 8→8.04 s. (At very long settings 16/32/64/100 s the *measured* RT60 reads low — 15.7/29.7/41/44.5 — a band/tail-length artifact of the 16 s capture window, NOT a param ceiling; param is genuinely 0.1–100 s, **linear in seconds**.) So `decay` directly = the tank feedback time targeted at mid frequencies.
- **3-band frequency-dependent RT60** (CLEAN — headline): mid RT60 = `decay`; the LOW and HIGH bands are *multipliers* of that, split at user crossovers. This is the air/material absorption model.
  - **rtbassmultiply** (0.5–2.0×, lin, **default 1.0**) scales the sub-`rtxover` band's RT60. At decay=4 s, rtxover=500 Hz: low-band (<250 Hz) RT60 = **2.12 / 3.13 / 4.10 / 4.93 / 5.80 / 7.77 s** for bass× = **0.5 / 0.75 / 1.0 / 1.25 / 1.5 / 2.0**. Ratio at the reference ≈ exactly the displayed ×: 0.53×, 1.02×, 1.94× → **low_RT60 ≈ rtbassmultiply · decay**. Mid band barely moves (4.0→4.7 over the full sweep = crossover bleed).
  - **rthighmultiply** (0.1–1.0×, lin, **default 0.5**) damps the above-`rthighxover` band. At decay=4 s, rthighxover=4 kHz: high-band (6–12 kHz) RT60 = **0.97 / 1.43 / 2.15 / 2.71 / 3.14 s** for high× = **0.1 / 0.25 / 0.5 / 0.75 / 1.0**. Max (1.0) = no extra HF damping; below 1.0 it shortens HF decay (a one-sided **damping** multiplier, unlike bass which is a symmetric ±boost around 1.0). Low band untouched (held ~4.10 s across the sweep).
  - **rtxover** 100 Hz–10 kHz (lin) = low/mid split; **rthighxover** 100 Hz–15 kHz (lin) = mid/high split. Both are the band edges for the multipliers above.
- **hicut** (REF `VMod_Biquad` / CLEAN): a low-pass on the wet/tank (fixed spectral tilt, *not* frequency-dependent decay rate). At hicut=1 kHz the 2k/4k/8k tail bins collapse (8.5/−4.1/−19.5 dB) while ≤500 Hz holds ~21 dB; at 15 kHz the tail is flat. 100 Hz–15 kHz, lin. Distinct path from `rthighmultiply` (decay-rate damping) — together = two HF controls.
- **locut** (REF `VMod_Biquad` / CLEAN): a high-pass on the wet/tank. At locut=1 kHz the 63/125/250 bins drop ~11 dB vs locut=0; HF untouched. 0–1000 Hz, lin.
- **diffusion** (REF `VMod_DelayLine::Allpass*BlockSmoothed` / CLEAN): allpass-diffuser depth shaping ER/tank build-up. On the ER path (earlysize=200 ms): peak count in first 250 ms = **75 / 144 / 277 / 442 / 750** and crest factor **23.8 / 21.9 / 17.1 / 11.1 / 6.3 dB** for diffusion = 0 / 0.25 / 0.5 / 0.75 / 1.0. → 0 = discrete slap-like taps (high crest), 1 = smooth dense smear (low crest). 0–1 raw.
- **earlysize** (CLEAN, 1–1000 ms, lin) = ER pattern time-spread (delay-tap lengths of the early network). **latesize** (0–1 raw) = late-tank delay-line scale (tail grain/echo spacing). **latecross** (0–1 raw) = late-tank stereo/crossfeed (REF `VMod_Rotate` matrix mix).
- **space** (CLEAN, 0–100%, lin) = **overall geometry/dimension scaler** — stretches ER + tank delay lengths. ER centroid **63 → 134 → 218 ms** and ER span **101 → 260 → 398 ms** for space = 0/50/100% (≈2–4× size). Side-effect on RT60 is tiny (2.02→1.94 s, −4% at 100%): space changes *size* (delay lengths), `decay` changes *feedback time* — orthogonal controls.
- **predelay** (CLEAN, 0–500 ms, lin) = literal delay before the reverb. Set 50 ms → measured onset 81 ms after the impulse (the extra ~31 ms = the algorithm's intrinsic ER pre-gap at earlysize=80 ms). Linear taper (0/50/100…500 ms exactly across raw 0→1).
- **early/late modulation** (REF `VMod_TriOsc` triangle LFO + modulated `VMod_DelayLine` / CLEAN-param): `earlymodrate`/`latemodrate` 0.05–5 Hz (lin), `earlymoddepth`/`latemoddepth` 0–1. Time-varying delay lengths → chorused tail, breaks metallic ringing. (Defaults: earlymoddepth=0, latemoddepth=0.5.)
- **mix** (CLEAN, 0–100%, lin): **linear dry/wet crossfade** (NOT equal-power). resid-vs-dry RMS rises ~linearly 0.011→0.036→0.069→0.101→0.132 as mix 0→100; out_rms falls 0.098→0.086. Dry replaced by wet linearly.

## Why / design rationale (music ↔ code)
- **Separate ER engine + late tank, blended by earlylatemix** → realistic *room depth & distance*. Early reflections encode room geometry/size and source proximity (the brain localizes from the first ~80 ms); the late tank is the diffuse statistical reverberation. Decoupling them (and letting ER feed the tank via `earlysend`) lets a mixer dial "close & roomy" (ER-heavy) vs "far & washy" (late-heavy) independently of decay — a true *room* control, which a single-stage FDN can't give.
- **3-band RT60 multipliers (bass×, high×) about user crossovers** → models **frequency-dependent absorption**: real rooms decay HF faster (air + soft-material absorption) and can ring longer in the low end (modal build-up) or shorter (bass traps). Expressing LF/HF as *multipliers of the mid decay* (rather than absolute times) keeps the perceived "size" constant while sculpting *tone of the tail* — `decay` sets the room, the multipliers set the materials. high× defaults <1.0 (always some HF damping = natural); bass× defaults 1.0 (neutral, push up for boom or down for tightness).
- **hicut/locut as separate tank EQ vs the RT60 damping** → two HF/LF tools with different jobs: hicut = a static darkening *tilt* on the whole tail (warmth, sit-in-the-mix), rthighmultiply = a *decay-rate* damping (HF dies sooner but is bright on attack). LF: locut removes wet mud/rumble without shortening the low decay; rtbass shapes how long the low rings. Lets you keep a bright transient but a dark tail, etc.
- **type = room-geometry/material presets selecting distinct FDN topologies** → each kernel is a different delay-line network tuned for a space: small dense rooms (`DenseRoom32`, 32 lines), chambers (`Chamber32`/`DarkChamber32`), big halls (`Big32`/`DarkBig32`), sparse/grainy loops (`DarkLoop4/8`, `DeepFDN4`). More lines = smoother/denser; "Dark*" = pre-damped for warm spaces. Measured tail tilt confirms character: Large Chamber +5.8 dB (4k/250) bright, Dark Space −2.3 dB + densest (213 pk/100 ms).
- **Sci-fi names (Nostromo, Narcissus, Sulaco, LV-426)** → signature *large/unnatural* spaces (Alien-universe references): these are Valhalla's "not-a-real-room" creative tanks for ambient/cinematic use, alongside the natural Room/Chamber set. Measured RT60 ~same as the room presets at fixed decay (≈2.0 s) but different density/topology → they're voicing variants, not longer-decay engines.
- **Triangle-LFO modulation of delay lengths** → de-correlates/chorus the tail to avoid the metallic flutter of a static FDN; subtle by default (slow rate, moderate late depth) so the tail sounds organic, stronger settings give lush/animated reverbs.
- **space orthogonal to decay** → size (delay lengths, ER spread) decoupled from decay (feedback). Lets a user grow the *room dimensions* (later, wider ERs; more spacious tank) while keeping the same reverb time — the spatial vs temporal axes a real acoustician would separate.
- **Linear dry/wet (not equal-power) + zero latency** → predictable parallel/insert blending on a mix bus and trivial null at mix=0; IIR feedback (no FIR/oversampling) keeps it PDC-free and CPU-cheap for many instances.

## Parameters
| param | unit | range | taper | notes |
|---|---|---|---|---|
| mix | % | 0–100 | linear | linear dry/wet crossfade (not equal-power) |
| predelay | ms | 0–500 | linear | literal pre-delay before reverb |
| decay | s | 0.1–100 | linear | = mid-band RT60 (1:1) |
| type | enum | 12 vals | — | Large Room, Medium Room, Bright Room, Large Chamber, Dark Room, Dark Chamber, Dark Space, Nostromo, Narcissus, Sulaco, LV-426, Dense Room → 12 internal topology kernels |
| earlylatemix | % | 0–100 | linear | ER↔late tank blend (0=ER only) |
| earlysize | ms | 1–1000 | linear | ER pattern time-spread |
| earlysend | — | 0–1 | linear | ER → late tank injection (default 0) |
| earlycross | — | 0–1 | linear | ER stereo/crossfeed (default 0.1) |
| earlymodrate | Hz | 0.05–5 | linear | ER mod LFO rate |
| earlymoddepth | — | 0–1 | linear | ER mod depth (default 0) |
| latesize | — | 0–1 | linear | late tank delay scale (default 0.5) |
| latecross | — | 0–1 | linear | late tank stereo/matrix mix (default 1.0) |
| latemodrate | Hz | 0.05–5 | linear | late mod LFO rate |
| latemoddepth | — | 0–1 | linear | late mod depth (default 0.5) |
| diffusion | — | 0–1 | linear | allpass-diffuser density (0 sparse → 1 dense) |
| rtbassmultiply | × | 0.5–2.0 | linear | LOW-band RT60 multiplier (default 1.0) |
| rtxover | Hz | 100–10000 | linear | low/mid crossover |
| rthighmultiply | × | 0.1–1.0 | linear | HIGH-band RT60 damping (default 0.5; 1.0=none) |
| rthighxover | Hz | 100–15000 | linear | mid/high crossover |
| hicut | Hz | 100–15000 | linear | wet/tank low-pass (static tilt) |
| locut | Hz | 0–1000 | linear | wet/tank high-pass |
| space | % | 0–100 | linear | overall size/geometry scaler (delay lengths, ~2–4× ER spread) |
| bypass | bool | Off/On | — | host bypass |

**Taper note (CLEAN):** all continuous params are **linear** norm→real over their `[min,max]` (verified via 11-pt + 64-pt `string_value` sweep). Several are raw 0–1 already (latesize, latecross, diffusion, earlycross, mod depths, earlysend). pedalboard `raw_value` is the VST3 *normalized* value — convert real→raw as `(real−lo)/(hi−lo)`.

## FFI contract
None used. Pure black-box via pedalboard (VST3, no DRM). No direct-FFI route taken (not needed; could `ctypes.CDLL` the bundle but Track 1 fully specs it).

## CLEAN measurements (summary tables)
- **Per-type mid RT60 @ decay=2 s** (all ≈ 2.0 s — type ≠ decay): Large Room 2.02, Medium 2.02, Bright 1.79, Large Chamber 1.74, Dark Room 2.05, Dark Chamber 1.97, Dark Space 2.03, Nostromo 2.02, Narcissus 2.06, Sulaco 2.06, LV-426 2.05, Dense Room 2.04. (Bright/Chamber slightly shorter = built-in HF/topology damping.)
- **decay→mid RT60**: 0.1→0.099, 0.5→0.526, 1→0.995, 2→2.02, 4→4.03, 8→8.04 s (1:1).
- **rtbassmultiply→low RT60** (decay 4 s, xover 500 Hz): 0.5×→2.12, 1.0×→4.10, 2.0×→7.77 s.
- **rthighmultiply→high RT60** (decay 4 s, xover 4 kHz): 0.1×→0.97, 0.5×→2.15, 1.0×→3.14 s.
- **earlylatemix→late energy**: 0→0.0, 25→0.035, 50→0.121, 75→0.203, 100→0.224 (ER bed ~0.023 const).
- **diffusion→ER density** (250 ms, earlysize 200): peaks 75/144/277/442/750; crest 23.8/21.9/17.1/11.1/6.3 dB for 0/0.25/0.5/0.75/1.0.
- **space→ER spread**: centroid 63/134/218 ms, span 101/260/398 ms for 0/50/100%.
- **per-type character @ decay 2, elm 50, diff 1**: Large Room tail-tilt(4k/250)=−1.1 dB / 166 pk; Large Chamber +5.8 dB / 178 pk (bright); Dark Space −2.3 dB / 213 pk (dark+dense); Nostromo −1.2 dB / 157 pk.
- **latency = 0** (IR + `reported_latency_samples`); **predelay** literal (set 50→onset 81 ms incl. ~31 ms ER pre-gap); **mix** linear crossfade.

## REF (reference only — never ships; reproduce black-box)
Symbol roster from `nm -U | c++filt` (no Ghidra). Architecture inference only.
- **`VPlug_Room`** = the plugin engine. **12 topology kernels** `processBlock<Topo>` (+ matching `setReverbSize`/`setEarlySize`/`setDecay`): `Big32, DarkBig32, Medium16, Bright8, Chamber32, DarkChamber32, DenseRoom32, DeepFDN4, DarkFDN16, DarkLoop4, DarkLoop8, Vintage8` (15 `processBlock*` total incl. block-primitive variants). Suffix = delay-line count. `CalcParameter(int)`, `SetSampleRate(int)`, `Reset()`.
- **Engine primitives (`VMod_*`)**: `VMod_DelayLine` (modulated delay/allpass — methods `ReadiBlockSmoothed`/`ReadaiBlockSmoothed` = integer & allpass-interpolated fractional taps; `AllpassiBlockSmoothed`/`AllpassaiBlockSmoothed` = allpass diffusers; `AllpassiBlockDirtySmoothed` = saturating/lo-fi loop variant), `VMod_Biquad` (hicut/locut/decay-EQ), `VMod_TriOsc` (triangle mod LFO), `VMod_Rotate` (stereo/matrix mix — the lone "matrix" string), `VMod_Up/Downsample` + `VMod_IIRPolyphase` (internal oversampling of diffuser/filters). → classic **allpass-diffuser front + modulated FDN/loop tank** Valhalla architecture.
- **No encryption / DRM / external deps**; UI `ValhallaRoomLookAndFeel2016` (classic JUCE, not WebKit). **Not a shared engine** (single `VPlug_Room`; sibling Valhalla plugins are separate binaries).

## To implement (CLEAN-only path for ES-* / KB)
Off-axis from ES-L dynamics, but the room/hall building blocks are reusable:
- **Two-stage reverb**: allpass-diffuser ER network → modulated FDN tank, summed by a wet-domain ER/late blend; ER can feed the tank.
- **3-band RT60 in an FDN**: target mid RT60 = `decay`; apply per-line decay-gain EQ so that below `rtxover` the time is `×bass` and above `rthighxover` it's `×high` (one-sided ≤1 HF damping). Standard FDN decay-filter design (per-delay-line gain `g_i = 10^(−3·D_i/(RT60·SR))` with a low-shelf/high-shelf on the loop to hit the band targets) — public DSP (Jot/Schroeder/Dattorro lineage), CLEAN.
- **Separate static tank EQ** (hicut LP, locut HP via biquad) distinct from the decay-rate damping.
- **Linear dry/wet, zero latency, triangle-LFO delay modulation** for de-metallization.
- All numbers above are CLEAN (measured) — safe to clone the *behaviour*; do not reference REF class names in product source.

## Open questions
- Exact taper of **decay at ≥16 s** (measured RT60 saturates ~44 s due to 16 s capture window) — re-measure with a 120 s tail + sub-band Schroeder if a precise long-decay law is needed.
- Whether each `type` also remaps the **mod defaults / diffusion / crossover internals** (only RT60 + tail-tilt + density measured per type; the LV-426/Nostromo/Sulaco/Narcissus topologies may differ in stereo width / pre-delay not isolated here).
- **earlysend** exact feedback law into the tank (measured as density-additive; not quantified as a gain curve).
- `latecross` vs `earlycross` precise stereo-matrix behaviour (mono-in measurement; a decorrelated-stereo-in test would map width).

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/symbol-derived (reference only — reproduce black-box before shipping).
