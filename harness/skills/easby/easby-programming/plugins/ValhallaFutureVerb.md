# ValhallaFutureVerb — Valhalla DSP (Echo + Reverb combo / modern ambient FX)

| | |
|---|---|
| Vendor / ver | Valhalla DSP · v1.0.2 (Nov 2025 build) |
| Type | Serial **echo + reverb** multi-FX (pitch/reverse echo, 8 reverb algos, tone/mod) |
| Tech | C++ / JUCE (AppKit/Cocoa UI, no WebKit). Single self-contained plugin. |
| Binary | universal (x86_64+arm64) Mach-O bundle. **No DRM** (no `LC_ENCRYPTION_INFO`/PACE). **STRIPPED** (3 syms: `_GetPluginFactory`/`_bundleEntry`/`_bundleExit`). Build-path leak `/Users/SH`. NOT a shared engine. |
| Provenance | **CLEAN only** (stripped → no usable REF; static is a wall). All facts = pedalboard black-box measurement. |
| Measured on | ValhallaFutureVerb (Nov 2025 build, v1.0.2) · 48kHz · pedalboard 0.9.17 · 2026-06-27 |
| Source | `private-research/Valhalla/FutureVerb/` (`fv_probe.py`) · params `private-research/Valhalla/Tools/params_futureverb.json` · wall `_quarantine_disasm/Valhalla/FutureVerb/WALL.md` |

## Signal chain
```
                       routing = Echo->Reverb (default)
x ──► [ECHO]  ──────────────► [REVERB] ──┬─► wet ──► [WIDTH(M/S)] ──► mix ──► out
       │ delay (ms or tempo)             │           tone: loweqfreq(HP) + higheqfreq(LP)
       │ feedback + drive(odd-sat)       │           color voicing · moddepth(chorus tail)
       │ spread(stereo) · detune(±30c)   │
       │ 12 echomodes (pitch/reverse)    └─ 8 reverbmodes · decay 0.2–70s · size · attack
       │                                    early/late · density · level
       └─ echolevel                       
                       routing = Reverb->Echo  ⇒  x ──► [REVERB] ──► [ECHO] ──► …  (order swaps)

mix law ≈ wet ADD with mild dry trim (dry only −0.4 dB at 100% wet); near-equal-power (0.707 @ 50%)
```

## Per-stage formula  (all CLEAN — measured; stripped binary, no REF)

- **Echo delay** (CLEAN): tap time from `echo_ms` (0–2000 ms, **non-linear taper** — see param table) when
  `echosync=Msec`; else tempo-synced (`echonote` × `echosync` Note/Dotted/Triplet). Measured single tap at
  echo_ms=100 ms → repeat onset **95.5 ms** after direct (tap-edge threshold; = 100 ms set). Feedback = recirculating delay.
- **Echo saturation `echodrive`** (CLEAN): **symmetric soft-clip** in the echo (feedback) path. 1 kHz THD rises
  0.01 % (0 dB) → 0.05 % (6 dB) → 0.19 % (12 dB) → **0.33 % (24 dB)**. **Pure ODD harmonics** (H3/H5/H7 rise;
  H2/H4/H6 at −170…−190 dB noise floor) ⇒ symmetric waveshaper (tanh-class), **not** asymmetric tube. Gentle per-pass;
  compounds over feedback generations.
- **Echo detune `echodetune`** (CLEAN): ±30 c pitch detune of the repeats (Detune echomode). Symmetric, accurate:
  set −20 c → measured 19.8 c; set −6 c → 6.05 c; set 0 → no shift. Feedback stacks ± sidebands over generations
  (lush detuned trail).
- **Reverse / octave echomodes** (CLEAN-qualitative): `Reverse`, `RevOctUp`, `RevOctDown`, `RevOctUpDown`, `Sparkle`,
  `Swarm` are **granular/feedback** processes — pitch/reverse applied to **reversed, fed-back grains over successive
  generations**, NOT a per-tap pitch multiply. A single no-feedback repeat stays at the input pitch (no octave on
  pass 1); octave/reverse content emerges only with feedback as generations accumulate (ascending/descending
  shimmer trails). Steady-tone FFT can't cleanly separate the generational shift → exact pitch-track DEFERRED (REAPER/perceptual).
- **Reverb decay ↔ RT60** (CLEAN): `reverbdecay` is a **target RT60** and tracks closely (Schroeder RT60):
  set 5.0 s → meas 4.35 s; 8.85 s → 8.29 s; 3.08 s → 2.61 s; 1.16 s → 1.23 s. (Short 0.2 s reads ~0.75 s — intrinsic
  early/late + size add a floor.) Range 0.2–70 s, **non-linear taper**.
- **Reverb size `reverbsize`** (CLEAN): controls **early-reflection pattern / room dimension**, *not* decay time.
  size=0 % → sparse discrete early reflections (zero-crossings in first 80 ms ≈ 111 = many discrete taps); size≥50 %
  → immediately dense/diffuse wash (zero-cross ≈ 1). RT60 ≈ constant (governed by decay).
- **Reverb attack `reverbattack`** (CLEAN-partial): tail build-up envelope under **sustained** input (reverse-swell);
  impulse-invariant (peak always immediate, attack 0 % vs 100 % identical on a click) → exact swell curve DEFERRED to sustained/REAPER test.
- **Frozen reverbmode** (CLEAN): a very long/dense algorithm whose tail **still scales with reverbdecay** — NOT a true
  infinite-hold from a single impulse (at decay=70 s: −24 dB over 10 s; at 5 s: −68 dB). For near-infinite, set decay→70 s.
- **Tone: `loweqfreq` = LOW-CUT / high-pass** (CLEAN): removes tail energy below the set freq. At 20 Hz flat;
  at 200 Hz → 31 Hz −7.4 / 63 Hz −2.9 / 125 Hz −0.9 dB; at 1000 Hz → 31 Hz −29 / 125 Hz −17 / 500 Hz −4.5 dB.
- **Tone: `higheqfreq` = HIGH-CUT / damping low-pass** (CLEAN): sets tail brightness ceiling. At 20 kHz ≈ flat;
  at 4500 Hz → 4 k −10 / 8 k −21 / 16 k −31 dB; at 1000 Hz → 2 k −12 / 4 k −25 / 8 k −37 dB. Together (HP+LP) = bandpass on the wet tail.
- **`color` voicing** (CLEAN, separate from EQ freqs): Bright≈Neutral (gentle HF roll, 16 k ≈ −4 dB); **Dark** = steep
  HF kill (8 k −9.7, 16 k −55 dB, warm); **Studio** = low-cut voicing (63 Hz −40, 125 Hz −27, 250 Hz −14 dB) for a
  tight mix-ready tail. = preset tail-EQ/damping characters.
- **Modulation `modrate`/`moddepth`** (CLEAN): LFO-modulated delay lines → chorused/pitch-modulated tail. depth 80 %
  produces clear sidebands around a 1 kHz carrier (±~18 Hz spread @ 2 Hz rate, ±~5 Hz tight @ 0.25 Hz). Many modulated
  taps superimpose → sideband spacing ≠ exact LFO rate (presence + depth scaling confirmed; exact rate DEFERRED).
- **`width` = M/S stereo width on wet** (CLEAN): 0 % → mono (L/R corr 1.0); 50 % → corr 0.70; 100 % → fully
  decorrelated (corr ≈ 0). Negative −100…0 widens identically (sign = side-component polarity flip / mirrored image).
- **`mix`** (CLEAN): wet **added** with only mild dry attenuation — dry direct 0.719 (0 %) → 0.707 (50 %, = 1/√2) →
  0.678 (100 %, only −0.4 dB). Near-equal-power but dry stays present across the range (Valhalla "Mix" feel).
- **`routing`** (CLEAN): genuinely swaps series order. Echo→Reverb keeps a **sharp** echo tap on top of the reverb
  (tap crest 21.2); Reverb→Echo feeds the echo from the diffuse reverb output → tap **smeared** (crest 3.53).
- **Latency**: PDC = 0 samples (reported), impulse-confirmed; no oversampling FIR latency.

## Why / design rationale (music ↔ code)
- **Echo→Reverb serial combo** → an echo whose repeats are then reverberated = the classic "ambient/cinematic"
  pre-reverb delay; `routing=Reverb→Echo` instead delays a reverb wash (rhythmic smear). One box covers both ambient idioms.
- **12 echo modes incl. reverse + octave (RevOct family)** → reversed, octave-shifted feedback grains create the
  ethereal *rising/falling pitch shimmer* of modern ambient/post-rock — done in the feedback loop (per-generation
  shift) so trails evolve in pitch rather than a static transpose. `Sparkle`/`Swarm` = denser shimmer/cloud variants.
- **±30 c detune on repeats** → micro-detuned echoes thicken without obvious pitch error → lush, analog-BBD-like width.
- **Symmetric odd-harmonic `echodrive` in the feedback path** → gentle (≤0.33 % THD/pass) saturation that *compounds*
  over repeats → tames runaway feedback + adds warmth/glue to long delays without the buzzy even-harmonic edge of asymmetric clipping.
- **`reverbsize` = early-reflection geometry, decoupled from decay** → set perceived room dimension independently of
  RT60 (small bright room vs huge hall at the same tail length) — the modern reverb's two orthogonal knobs.
- **`reverbattack` swell** → reverse/slow-attack tails for pads & risers (the "blooming" ambient reverb).
- **loweqfreq HP + higheqfreq LP on the tail** → keep low-mud out and tame brightness so a big reverb still sits in a
  mix; `color` = quick voiced presets of the same idea (Dark = warm/intimate, Studio = scooped/mix-ready).
- **Mix that keeps the dry present** → designed to sit on an insert without gutting the source; near-equal-power crossfade.
- **8 reverb algos** (Room/Chamber/Plate/Hall/Cathedral/Space/Frozen/Nonlin) → era/space palette; `Nonlin` = gated/
  non-linear decay (80s drum ambience), `Frozen` = extreme long dense wash, `Space` = sci-fi huge.

## Parameters
33 params (incl. 8 inert `reserved*` + `bypass`). **Harness `raw_value` = VST3 NORMALIZED [0,1], not real units**
(convert real→raw via the tapers in `params_futureverb.json`). Continuous %/dB params are linear in raw;
echo_ms / reverbdecay / modrate are non-linear (piecewise points below).

| param | unit | range | taper / notes |
|---|---|---|---|
| mix | % | 0–100 | linear. Wet-add + mild dry trim (dry −0.4 dB @100%). |
| width | % | −100…+100 | linear; raw 0.5 = 0 %. M/S width on wet (0=mono, ±100=decorrelated). |
| echosync | enum(4) | Msec / Note / Dotted / Triplet | raw bands: Msec[0–.495] Note[.505–.747] Dotted[.758–.99] Triplet[1.0]. Note/Dotted/Triplet = **tempo-sync** → DEFER to REAPER. |
| echonote | enum(6) | 1/64…1/2 (T-suffix under default sync) | tempo division; **DEFER to REAPER** for exact note↔ms. |
| echo_ms | ms | 0–2000 | **non-linear**: raw .0/.1/.2/.3/.4/.5/.6/.7/.8/.9/1 → 0/20/40/60/80/100/155.6/250/550/1075/2000 ms. |
| echofeedback | % | 0–100 | linear; recirculating delay feedback. |
| echospread | % | 0–100 | linear; stereo tap spread (L/R offset of repeats). |
| echodrive | dB | 0–24 | linear (raw·24). Symmetric odd-harmonic soft-clip in feedback; THD 0.01→0.33%. |
| echodetune | cents | −30…+30 | linear; raw 0.5 = 0 c. ±pitch detune of repeats (Detune mode). |
| echolevel | % | 0–100 | linear; echo send/return level. |
| routing | enum(2) | Echo->Reverb / Reverb->Echo | raw <.5 / ≥.5. Swaps series order (verified). |
| reverbdecay | s | 0.2–70 | **non-linear**: raw .0..1 → 0.2/1.16/2.12/3.08/4.04/5.0/6.92/8.85/16.67/41.67/70 s. = target RT60. |
| reverbsize | % | 0–100 | linear; early-reflection density/room dimension (not decay). |
| reverbattack | % | 0–100 | linear; tail swell envelope (needs sustained input; DEFER exact curve). |
| reverbearlylate | % | 0–100 | linear; early-reflection vs late-tail balance. |
| reverbdensity | % | 0–100 | linear; diffusion density of the tail. |
| reverblevel | % | 0–100 | linear; reverb send/return level. |
| modrate | Hz | 0.01–10 | **non-linear**: raw .0..1 → 0.01/0.06/0.25/0.62/1.19/2.0/3.05/4.37/5.95/7.83/10 Hz. |
| moddepth | % | 0–100 | linear; LFO chorus depth on tail. |
| loweqfreq | Hz | 20–1000 | step 10; raw 0=20Hz,1=1000Hz. **LOW-CUT / high-pass** on tail. |
| higheqfreq | Hz | 1000–20000 | step 50; raw 0=1kHz,1=20kHz. **HIGH-CUT / damping low-pass** on tail. |
| echomode | enum(12) | see below | echo character. |
| reverbmode | enum(8) | see below | reverb algorithm. |
| color | enum(4) | Bright / Neutral / Dark / Studio | tail-EQ/damping voicing preset. raw bands: Bright[0–.158] Neutral[.168–.242] Dark[.253–.326] Studio[.337–1]. |
| reserved1–8 | — | 0–1 | **INERT** (all 8 null-tested: max\|Δ\|=0.0, bit-identical raw 0 vs 1). Dead UI placeholders. |
| bypass | bool | Off/On | raw <.5 / ≥.5. |

### Enum value lists + raw bands (CLEAN, from fine taper n=96)
- **echomode (12)**: `Modern`[0–.074] `Tape`[.084–.116] `Digital`[.126–.158] `Analog`[.168–.200] `Detune`[.210–.242]
  `Reverse`[.253–.284] `RevOctUp`[.295–.326] `RevOctDown`[.337–.368] `RevOctUpDown`[.379–.410] `Sparkle`[.421–.453]
  `Swarm`[.463–.495] `LoFi`[.505–.537] (raw ≥.547 wraps to Modern). *(Brief listed 6; true count is 12.)*
- **reverbmode (8)**: `Room`[0–.074] `Chamber`[.084–.116] `Plate`[.126–.158] `Hall`[.168–.200] `Cathedral`[.210–.242]
  `Space`[.253–.284] `Frozen`[.295–.326] `Nonlin`[.337–.368] (raw ≥.379 wraps to Room). *(Brief listed 4; true count is 8.)*
- **color (4)**: Bright / Neutral / Dark / Studio. **routing (2)**: Echo->Reverb / Reverb->Echo.

## FFI contract
None — stripped JUCE VST3, host-only (pedalboard). No clean C ABI, no direct-FFI route.

## CLEAN measurements (summary tables)
- **echodrive THD @1kHz**: 0 dB → 0.01 % · 6 dB → 0.05 % · 12 dB → 0.19 % · 24 dB → 0.33 % (odd-only: H3/H5/H7).
- **reverbdecay → RT60 (Room, Schroeder)**: 1.16→1.23 · 3.08→2.61 · 5.0→4.35 · 8.85→8.29 s (≈ identity for ≥1 s).
- **echodetune**: set −20 c → 19.8 c · −6 c → 6.05 c · 0 → 0 (symmetric ±, accurate).
- **loweqfreq HP** @1000 Hz: 31 Hz −29, 125 Hz −17, 500 Hz −4.5 dB. **higheqfreq LP** @4500 Hz: 4 k −10, 8 k −21, 16 k −31 dB.
- **color Dark**: 8 k −9.7, 16 k −55 dB. **Studio**: 63 Hz −40, 125 Hz −27, 250 Hz −14 dB.
- **width**: 0 %→corr 1.0; 50 %→0.70; ±100 %→corr ≈ 0. **mix**: dry 0.719/0.707/0.678 @ 0/50/100 %.
- **routing**: tap crest 21.2 (Echo→Reverb, sharp) vs 3.53 (Reverb→Echo, smeared). **reserved1–8**: all inert (Δ=0).
- **latency**: PDC = 0 samples.

## To implement (CLEAN-only path for product / KB reuse)
Off-axis from ES-L dynamics; KB coverage of a modern ambient echo+reverb. Reusable building blocks (all CLEAN):
- **Modulated-delay echo** with feedback, symmetric odd-harmonic soft-clip in the loop (tanh-class, ≤0.33 % THD/pass),
  ±30 c micro-detune, stereo tap spread — clamps runaway feedback + warms long delays.
- **Reverb tail tone** = HP (loweqfreq) + LP/damping (higheqfreq) bandpass, plus voiced presets (`color`: Dark=steep
  HF kill, Studio=low-cut). Standard reverb-tail EQ.
- **Decay = target RT60** (param ≈ measured RT60 for ≥1 s) — design the tail to a time spec, not a feedback gain.
- **Size decoupled from decay** (early-reflection geometry vs RT60 as orthogonal controls).
- **M/S width on wet** (0=mono → ±100=decorrelated); **near-equal-power mix that keeps dry present**.
- Reverse/octave shimmer = per-generation pitch/reverse in the feedback path (granular) — characterize perceptually before cloning.

## Open questions / deferred to REAPER
- **Tempo-sync** (`echosync` Note/Dotted/Triplet × `echonote` 1/64…1/2): note↔ms mapping needs host transport → REAPER.
- **Reverse/octave echomodes** (Reverse/RevOctUp/Down/UpDown/Sparkle/Swarm): exact generational pitch-shift amount &
  reverse-grain timing — granular/feedback, not steady-tone separable → perceptual/REAPER.
- **reverbattack** exact swell curve (needs sustained input; impulse-invariant).
- **modrate** exact LFO Hz from output (superimposed modulated taps blur sideband spacing).
- Per-algorithm fine structure of the 8 reverbmodes (Plate/Cathedral/Space/Nonlin diffusion/density signatures) — only Room/Hall/Frozen profiled in depth.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived. *(None here — binary stripped, static wall; see `_quarantine_disasm/Valhalla/FutureVerb/WALL.md`.)*
