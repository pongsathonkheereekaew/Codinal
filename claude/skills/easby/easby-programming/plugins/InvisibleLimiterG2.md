# Invisible Limiter G2 — A.O.M. (AudioOptimization&Mastering) (Limiter / brickwall + compressor front-end)

| | |
|---|---|
| Vendor / ver | A.O.M. (AudioOptimization&Mastering) · v1.18.9 |
| Type | Dynamics — transparent mastering brickwall limiter (2nd gen) + compressor-style front stage; manual + adaptive(shape) attack/release, dither, sidechain HPF, DC removal, M/S, dry/wet |
| Tech | JUCE C++ (AppKit/CoreGraphics/CoreText UI, no Accelerate/vDSP linkage, no FFI). Universal x86_64+arm64 MH_BUNDLE |
| Binary | **Stripped** (3 exported syms, 447 total). **No DRM** — no `LC_ENCRYPTION_INFO`, no PACE/Eden. Static = a wall, ~no REF possible → **pure black-box**. Bundled help-text resource manifest (param semantics + enum lists) is readable strings = CLEAN (same class as ParamXML) |
| Provenance | **100% CLEAN** (black-box measurement + bundled resource manifest). No disasm. |
| Measured on | v1.18.9 · SR 44.1/48/96 kHz · pedalboard 0.9.17 (param surface, curves, times, TP) + REAPER ReaScript (PDC cross-check) · 2026-06-26 |
| Source | `private-research/AOM_InvisibleLimiter/Tools/g2_sysid.py` (+ `g2_pdc_probe.lua`), tables in `private-research/AOM_InvisibleLimiter/data/` |

## Signal chain (CLEAN, inferred from measured behavior + bundled help manifest)
```
x → [Gain −20..+20 dB] → [DC-Cut HPF (audio path, opt)] → [M/S encode (opt)]
  → detector: [SC-HPF (detector path, opt)] → envelope/gain-computer (ceiling, soft_knee, channel_link)
  → gain trajectory: manual {attack_time, release_time, manual_release_mode} OR adaptive {attack_shape, release_shape, sigmoidal, shape_mode}
  → apply gain over LOOKAHEAD-delayed signal (fixed ~88 ms PDC; internal OS = quality tier)
  → limit_mode kernel {Modern I–V brickwall | Suppress | Clip | Through(soft-comp)}
  → [bias even-harmonic, opt] → [M/S decode] → [dry/wet parallel mix] → [Dither @ bit-depth] → out
```

## Per-stage formula (all CLEAN — measured)

- **Static gain law / ceiling** (CLEAN): perfect brickwall. Below ceiling → unity (0.00 dB GR). At/above ceiling → output peak pinned to **exactly the ceiling** (measured −6.00 dBFS hard, GR = in − ceiling, linear 1:1 with input above thr). Ceiling accuracy: exact to measurement floor (±0.0 dB). `gain` and `ceiling` are **linear in dB** (gain −20..+20, ceiling −40..0; raw 0.5 = gain 0 dB / ceiling −20 dB).
- **Soft knee** (CLEAN): `soft_knee` 0 % = hard knee (GR onset exactly at ceiling). 100 % = GR begins **~18 dB below** ceiling, smooth quadratic-ish transition merging to hard limiting ~4 dB above ceiling. Measured (ceiling −6, knee 100): −24 in → −0.28 GR; −13 in → −1.00 GR; −2 in → −4.00 GR (= hard). Classic interpolated soft knee centered on threshold, width ≈ 2×knee%.
- **Lookahead / latency** (CLEAN): **fixed ~88 ms**, quality-INDEPENDENT. `reported_latency_samples` = 3912 @ 44.1k (88.71 ms), 4224 @ 48k (88.00 ms), 7856 @ 96k (81.83 ms). Zero-overshoot on loud onsets confirms real lookahead. Very long window → smooth, ultra-transparent gain trajectory (the "Invisible" design). pedalboard auto-PDC hides it on an impulse (reads 0); read it from `reported_latency_samples` / REAPER `pdc`.
- **Quality (oversampling)** (CLEAN): 10 tiers, **OS factor = 2^(N−1)** (#1 = 1×, #2 = 2×, … #10 = 512×). Displayed "internal kHz" = host_SR × OS (string tracks actual SR: at 48k, "#4" reads "384 kHz" = 8×). Latency-neutral; OS only refines alias-free clamping. IR reconstruction span ~58 samp for tiers ≥ #3.
- **True-peak** (CLEAN): **SAMPLE-PEAK limiter, NOT ITU true-peak.** Sample-peak clamped exactly to ceiling (−1.00) at every tier; 8× true-peak **overshoots +0.16…+1.86 dB** (worst at HF 17 kHz). Higher OS does NOT remove ISP overshoot (#10/24.6 MHz still +0.7 dB at HF) → ceiling enforced on the (oversampled) sample grid, not reconstructed inter-sample peaks. Contrast: TDR Limiter 6 = genuine TP (Δ +0.04). Like Ozone Maximizer (sample-peak).
- **limit_mode** (CLEAN, 8 modes — G2's core voicing): all produce **0.000 % THD on a steady clamped sine** (lookahead gain-reduction limiter, gain envelope is DC for a steady tone → no harmonics; NOT a steady-state shaper):
  - **Modern, Modern II, III, IV, V** — G2's original transparent brickwall flavors. All clamp to exactly ceiling on sine/square/spike. Differ only in subtle transient GR-smoothing (Modern V shows marginally most RMS reduction / crest on a square: −6.06 vs −6.03 dB) → program-dependent voicings, near-identical on synthetic signals.
  - **Suppress, Clip** — true brickwall (clamp exactly to ceiling). = the original Invisible Limiter's algorithms.
  - **Through** — NOT a brickwall: a **soft compressor that lets peaks exceed the ceiling** ("CompressorStyle: allows peak exceeding"). Measured (ceiling −6, gain 0): in −6 → out −6 (unity); in 0 → out −3.33; in +6 → out +0.88; in +12 → out +5.85. **out-RMS held ~constant ≈ −9 dBFS** across −12…+12 in (strong soft compression). Ceiling still scales it. crest preserved (0.84 dB vs 0.03 for brickwall). = the original IL "Thru" soft-limit algorithm.
- **Attack** (CLEAN, manual path = `attack_enabled` ON): `attack_time` **10 µs … 10 s**, exp/log taper (raw 0.5 = 10 ms; ≈1 decade per 0.1 raw). Genuinely controls GR onset slew: at 10 µs GR is ~instant (lookahead pre-loads); at 10 ms GR ramps in over ~5–10 ms; at ≥316 ms the attack is too slow to fully catch fast transients (partial GR). Fast attack = tight clamp, slow attack = lets transients through (punch).
- **Release** (CLEAN, manual path = `release_enabled` ON): `release_time` **100 µs … 180 s**, exp/log taper (raw 0.5 = 134 ms; raw 0.48 = 100 ms). Monotonic recovery on a held carrier after a transient burst: 100 ms setting → t63 ≈ 29 ms, full recovery ~100 ms; 566 ms → t63 ≈ 121 ms. `manual_release_mode` A/B/C (effective in Modern modes only): A≈B, **C slightly faster** (different recovery curvature). "Effective only in Modern modes."
- **Adaptive (shape) path** (CLEAN, manual attack/release OFF): internal **program-dependent auto attack/release**, very fast & transparent (held-tone recovers to steady GR within ~1–2 ms of a burst end). `attack_shape`/`release_shape` 0..100 and `sigmoidal_attack`/`sigmoidal_release` sculpt the **micro-shape/curvature** of the GR transition (exponential vs sigmoidal per help text) — measured effect is **sub-0.1 dB on steady tones / single bursts** (fine voicing, matters on real program, near-inaudible on synthetic). `shape_mode` A/B/C selects adaptive-behavior family (subtle). This is the limiter's transparent default engine.
- **Sidechain / detector HPF** (CLEAN, `detector_hpf` + `detector_hpf_frequency` 5 Hz..16 kHz log): a **detector-path** highpass (NOT audio path). Removes bass from the level detector → bass escapes limiting → **passes louder**. Measured (ceiling −6, +12 in): OFF → 50 Hz & 5 kHz both −6.00; ON cutoff 1.42 kHz → 50 Hz out +12.00 (fully unlimited) while 5 kHz still −5.56 (limited). Audio path of the bass is untouched.
- **DC removal** (CLEAN, `dc_removal` + `dc_removal_frequency` 0.1..200 Hz log): a **steep audio-path subsonic highpass** before limiting. Asymptotic slope ≈ **16–18 dB/oct (≈3rd order)** in the deep stopband. Corner tracks the labeled freq (−3 dB point ≈ 1.5–2× the label, e.g. label 1 Hz → −3 dB ≈ 1.5 Hz; label 9.56 Hz → −3 dB ≈ 18 Hz).
- **Dither** (CLEAN): `dither_type` {None, Flat (2-LSB TPDF), Acoustic (colored), Electronic (noise-shaped), Truncate (no noise)}; `dither_bit_depth` {8, 16, 24}. Noise added at the LSB of selected depth: silence floor = **−48 / −96 / −144 dBFS** for 8/16/24-bit (exactly 6.02 dB/bit). Flat = white TPDF (−96.3 @ 16b); Electronic = noise-shaped (more total RMS, pushed to HF); Acoustic = colored. `dither_auto_black`: mutes dither on very-low-level/silent input (silence → −240 dBFS) while keeping it on signal. Confirmed CLEAN; don't over-model.
- **Bias** (CLEAN, `bias` bool): "makes sound fat/warm a bit." Extremely subtle even-harmonic addition — H2 rises only −157 → −150.7 dB on a limited sine, DC stays ~0, no peak asymmetry. Flavor tweak; near-inaudible on synthetic, operates at the limiter stage on program material.
- **Channel link** (CLEAN, 0..100 %): linear L/R GR coupling. link 0 → channels independent (loud-L doesn't duck R); link 100 → R gets identical GR to L (fully linked). Measured (L +6, R −12, ceiling −6): R_GR = 0 / −2.52 / −5.41 / −12.00 dB at 0/25/50/100 % → `gain_R = lerp(own_R, max(L,R)_gain, link)`.
- **M/S mode** (CLEAN, `m_s_mode` bool): encode L/R→M/S before the dynamics, decode after. Confirmed active (mid/side test shows the √2 encode/decode round-trip). "Most of signal path works for M/S pair instead of L/R."
- **Dry/wet** (CLEAN, 0..100 %): linear **parallel mix** of dry input + wet (limited) output. 0 % = dry, 100 % = wet; intermediate peaks confirm signal mixing (not gain crossfade).
- **Unity gain monitor** (CLEAN, per manifest): adds −(input gain) to output so you A/B at matched loudness. **Bypass**: full passthrough (default state = true passthrough, maxdiff −229 dB until params engaged).

## Why / design rationale (music ↔ code)
- **Fixed ~88 ms lookahead + very long, smooth gain trajectory** → the GR envelope changes so gradually that limiting is inaudible ("Invisible") → transparent mastering loudness without pumping/distortion. Long lookahead is the price of transparency (vs a punchy short-lookahead limiter).
- **Sample-peak (not true-peak) + huge oversampling ladder (up to 512×)** → A.O.M.'s philosophy: oversample the *limiting nonlinearity* itself to kill aliasing/clamp artifacts, rather than chase ITU inter-sample ceiling. Gives extremely clean clamping on the internal grid; for codec-safe ISP margin the user lowers the ceiling. (Counter-design to TDR L6's ITU-TP approach.)
- **5 "Modern" flavors near-identical on tones** → they are program-dependent transient voicings (how aggressively micro-transients are smoothed), not different transfer curves — a "pick the character that suits the source" control, deliberately all transparent.
- **Through/Suppress/Clip carried over from the original IL** → backward-compatible voicings: Through = "I want glue/peak-rounding, not a wall"; Clip/Suppress = original brickwall behavior.
- **Adaptive shape + sigmoidal vs manual attack/release** → two operating philosophies: trust the program-dependent auto engine (default, hands-off transparency) OR dial exact times manually for surgical control. Sigmoidal curve option softens the GR onset/offset knee → fewer micro-distortion sidebands.
- **Detector SC-HPF** → stop bass transients from triggering full-band GR (kick/bass don't duck the whole mix) → louder, punchier low end → standard mastering-limiter move.
- **Steep DC-cut before limiting** → subsonic/DC rumble wastes headroom and skews peak detection; removing it pre-limiter lets the limiter work on musical content only.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| gain | dB | −20..+20 | linear in dB; raw 0.5 = 0 dB |
| ceiling | dB | −40..0 | brickwall ceiling/threshold; linear in dB; raw 0.5 = −20 dB; exact |
| channel_link | % | 0..100 | linear L/R GR coupling; 0=indep, 100=fully linked |
| limit_mode | enum | 8 | raw bounds: Modern 0.0 / Modern II 0.072 / Modern III 0.215 / Modern IV 0.357 / Modern V 0.500 / Suppress 0.645 / Clip 0.787 / Through 0.930 |
| soft_knee | % | 0..100 | 0=hard knee, 100=knee width ≈ ±18 dB around thr |
| attack_enabled | bool | | engages MANUAL attack (else adaptive shape path) |
| attack_time | scaled | 10 µs..10 s | exp taper; raw 0.5=10 ms (≈1 decade/0.1 raw) |
| attack_shape | % | 0..100 | adaptive GR-onset micro-shape (manual OFF); subtle |
| sigmoidal_attack | bool | | adaptive attack curve exp→sigmoidal |
| release_enabled | bool | | engages MANUAL release |
| release_time | scaled | 100 µs..180 s | exp taper; raw 0.5=134 ms, raw 0.48=100 ms |
| release_shape | % | 0..100 | adaptive GR-offset micro-shape; subtle |
| sigmoidal_release | bool | | adaptive release curve exp→sigmoidal |
| manual_release_mode | enum | A/B/C | manual-release internal behavior (Modern only); C slightly faster |
| shape_mode | enum | A/B/C | adaptive-shape family (Modern only); subtle |
| quality | enum | #1..#10 | OS factor 2^(N−1) (1×..512×); latency-neutral; string = SR×OS |
| bias | bool | | tiny even-harmonic "warmth" |
| dc_removal | bool | | audio-path subsonic HPF before limiting |
| dc_removal_frequency | Hz | 0.1..200 | log; ≈3rd-order HPF corner (−3 dB ≈ 1.5–2× label) |
| detector_hpf | bool | | DETECTOR-path (sidechain) HPF |
| detector_hpf_frequency | Hz | 5..16000 | log; raw 0.5 = 283 Hz |
| dither_type | enum | 5 | None / Flat(TPDF) / Acoustic(colored) / Electronic(shaped) / Truncate |
| dither_bit_depth | enum | 8/16/24 | floor −48/−96/−144 dBFS |
| dither_auto_black | bool | | mute dither on silence/low-level |
| m_s_mode | bool | | M/S encode before / decode after dynamics |
| dry_wet | % | 0..100 | linear parallel mix (0=dry, 100=wet) |
| unity_gain_monitor | bool | | output += −(input gain) for matched A/B |
| bypass | bool | | full passthrough |

## FFI contract
None (pure JUCE C++, stripped, no exported DSP ABI). Black-box only.

## CLEAN measurements (headline tables)
- **Ceiling**: exact brickwall; GR = max(0, in_dB − ceiling_dB), below thr = unity. Hard at soft_knee=0; soft_knee=100 spreads onset ±~18 dB around thr.
- **Latency**: 3912@44.1k / 4224@48k / 7856@96k samp → fixed **≈88 ms**, quality-independent.
- **True-peak**: sample-peak = ceiling exact; 8× TP overshoot +0.16…+1.86 dB (HF), unchanged by OS → **sample-peak limiter**.
- **limit_mode**: Modern I–V / Suppress / Clip = exact brickwall (0 % THD on sine); Through = soft comp (RMS≈const −9 dB, peaks exceed ceiling).
- **attack_time** 10 µs–10 s exp; **release_time** 100 µs–180 s exp; adaptive path = very fast program-dependent.
- **SC-HPF** = detector path (bass passes louder). **DC-cut** = steep audio HPF (~3rd order). **Dither** TPDF/colored/shaped at LSB, auto-black works.
- Enum maps + norm→real tables saved: `data/enums.json`, `data/limitmode.json`, `data/latency.json`.

## To implement (CLEAN path → ES-L / ES-X mastering chain)
A.O.M. G2 is a strong template for a **transparent mastering brickwall** stage in ES-L:
1. **Lookahead brickwall core**: fixed long-ish lookahead (try ~5–20 ms for lower latency, A.O.M.'s 88 ms is at the extreme transparent end) + smooth gain-reduction envelope. Per-sample `gain = min(1, ceiling_lin / peak_lookahead)`, smoothed by attack/release.
2. **Two release engines**: (a) manual exp attack/release with our existing one-pole, (b) an **adaptive/program-dependent** auto-release (dual time-constant or histogram-driven) as the default "transparent" mode — this is G2's signature. Add a **shape/curvature** control (exp↔sigmoidal GR transition) for fine voicing.
3. **Soft-knee on the threshold** (interpolated, width = 2×knee) for the comp-style front behavior.
4. **Sample-peak vs true-peak as a toggle**: G2 is sample-peak + heavy OS; ES-L can offer ITU-TP (like TDR L6) AND a high-OS sample-peak mode. Reuse our oversampling block; OS factor ladder (2^N) is latency-neutral.
5. **Detector sidechain HPF** (1st/2nd-order HPF in the detector path only) — cheap, big musical payoff (bass punch).
6. **Steep DC/subsonic HPF on the audio path** (≈3rd-order Butterworth, corner ~20 Hz) pre-limiter.
7. **M/S routing + channel-link + parallel dry/wet** — all standard linear primitives we already have (building-blocks).
8. **Dither stage** (TPDF + optional noise-shaping + auto-black) for the final output bit-depth — see `building-blocks/`.
9. **"Through" soft-comp voicing**: a non-brickwall mode that soft-compresses peaks (constant-RMS feel) for glue rather than wall — a good alternate character.
All shippable from CLEAN measurement + public limiter/dither literature; no REF involved.

---
Provenance tags: **CLEAN** = black-box measurement / bundled resource manifest / public DSP (product-safe). No REF (binary stripped + unencrypted → static is a wall, intentionally not disassembled).
