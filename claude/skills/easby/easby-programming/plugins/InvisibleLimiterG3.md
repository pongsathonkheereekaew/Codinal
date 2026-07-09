# Invisible Limiter G3 — A.O.M. (AudioOptimization&Mastering) (Two-stage soft compressor/leveler → true-peak brickwall)

| | |
|---|---|
| Vendor / ver | A.O.M. (AudioOptimization&Mastering) · Invisible Limiter G3 **v1.18.9** |
| Type | **Two-stage serial dynamics**: SOFT (compressor/leveler, M/S, parallel) → BRICKWALL (oversampled, optional true-peak limiter). The ES-X(leveler)→ES-L(brickwall) reference. |
| Tech | C++/JUCE, universal (x86_64 + arm64). No FFI, no Rust. UI not measured (params via host). |
| Binary | `Invisible_Limiter_G3` Mach-O universal bundle, **STRIPPED** (3 exported syms, ~447 total), **NO DRM / NO `LC_ENCRYPTION_INFO`** → static is a wall (~zero REF available). 100 MB (large internal oversampling FIR tables, up to 32× = 1.41 MHz). |
| Provenance | **100% CLEAN** — every fact below is black-box measurement (signal in → measure out). No disassembly performed (stripped + undrmed = nothing to gain). |
| Measured on | v1.18.9 · SR 48 kHz & 96 kHz base · pedalboard 0.9.17 · 2026-06-26 |
| Source | `private-research/AOM_InvisibleLimiter/Tools/g3_sysid.py` · data in `private-research/AOM_InvisibleLimiter/data/` |

## Signal chain (CLEAN — series order proven)
```
x → input_gain (dB) → [SOFT stage] → [BRICKWALL stage] → out
                         │                  │
   SOFT = (M/S split?)→detector(peak, channel_link, ms_balance)→gain-computer(thr,ratio|∞,knee,range cap)
          →envelope(attack/release dial, or program-adaptive when time_auto)→makeup→parallel wet_mix
   BRICKWALL = lookahead(~0.16–0.27 ms)→sample-peak ceiling (exact) ; optional true-peak (ITU-style)
               + internal oversampling 1×…32× ; channel_link
   unity_gain_monitor = A/B level-match toggle (cancels input_gain/makeup), NOT in production path
```
**Series order proven** (`chain2`): soft with +10 dB makeup pushes a tone to +16 dB; with both stages engaged the
output clamps to the brickwall ceiling (−6) → `out = brickwall(soft(x))`, soft is unambiguously FIRST.

## Per-stage formula (all CLEAN)

### input_gain (CLEAN)
Pure dB gain at the very front: `out = x · 10^(input_gain/20)` (−12 dBin + 12 dB = 0.00 dBFS, exact). Drives the soft detector.

### SOFT stage — compressor / leveler (CLEAN)
- **Static gain law (downward compression):** above threshold, `out_dB = thr + (in−thr)/ratio`.
  Verified exact at in = 0 dBFS, thr = −20: R=2→−9.97 (pred −10.00), R=4→−14.99 (−15.00), R=8→−17.50 (exact), R=30→−19.33 (exact).
  The `soft_ratio` displayed value **is** the ratio in that formula. Below threshold = unity (NO upward expansion measured — it is a pure *downward* compressor/leveler at all tested settings).
- **soft_ratio_inf = ∞:1 (hard):** output clamps exactly at threshold (limiter-style); `out_dB = thr` for in ≥ thr.
- **soft_knee (dB):** soft-knee width centred on threshold. knee=0 = hard corner. knee=24 → GR begins ~knee/2 (≈12 dB) below thr and the curve eases smoothly into the ratio line (measured GR at −24 in / −20 thr already −1.0 dB).
- **soft_range (dB) = MAXIMUM gain-reduction cap (downward limit on GR):** GR rises with the ratio law until it
  reaches `range` dB, then **freezes** — beyond that the output tracks the input 1:1 offset by −range.
  Measured (thr=−20, ∞:1): range=6 → GR pins at −6.01 dB then flat; range=12 → pins at −12.00. `soft_range_inf` removes the cap (unbounded GR).
- **soft_makeup (dB):** pure dB add, post-compression. Exact (−10…+10 dB in 5 dB steps = exact 5 dB output steps).
- **soft_wet_mix (%) = parallel ("New York"/upward) compression:** **linear-amplitude** blend
  `out = (1−w)·dry + w·wet`. Measured at 0 dBin (full comp = −17.5): 0%→0.00, 25%→−2.12, 50%→−4.93, 75%→−9.12, 100%→−17.50. Sub-threshold signal unchanged (wet=dry).
- **soft_ms_enabled / soft_ms_balance (dB):** M/S — when enabled, mid & side are processed independently
  (same mono input gives a different result, −20.1 vs −17.5). `ms_balance` tilts the detector/gain weighting
  between mid and side (≈0.875 dB output change per dB balance on a pure-mid signal; ±20 dB range).
- **soft_channel_link (%):** stereo detector link. Drive L hot, read a quiet R tone's gain: 0% = independent
  (R gain ≈ 0 dB), 50% → −12.5 dB, 100% → fully linked (R ducked −17.5 dB, same as L). Linear crossfeed of the side-chain.
- **Attack/Release timing — `soft_attack_time` / `soft_release_time` are a 0..10 LOGARITHMIC "speed" DIAL, NOT ms.**
  Measured 63 % time-constants (ratio 10:1, thr −30, GR envelope), CLEAN:

  | dial | attack (ms) | release (ms) |
  |---|---|---|
  | 0 | ~0.5 (fastest) | ~0.5 |
  | 1 | 0.72 | 0.60 |
  | 2 | 1.53 | 0.60 |
  | 3 | 4.06 | 2.0 |
  | 4 | 11.1 | 9.1 |
  | 5 | 30.0 | 28.0 |
  | 6 | 161 | 158 |
  | 7 | 435 | 431 |
  | 8 | 738 | 761 |
  | 9–10 | 738 (saturates) | 761 (saturates) |

  Law: roughly `t_ms ≈ 0.5·10^(0.32·dial)` (≈2–3× per dial unit, accelerating), saturating at **~750 ms** for dial ≥ 8.
  Attack and release share nearly the same curve (release slightly slower at the top). **The dial is a unitless
  perceptual "0=instant … 10=very slow" control; you MUST map it to a real RC time — passing "10" as ms is wrong.**
- **soft_time_auto (ON by default):** **program-adaptive timing** — overrides the manual dial. Attack becomes
  near-instant (63 % point unresolvable, sub-ms) and release becomes a fast-onset adaptive envelope (~0.6–1.2 ms
  initial 63 %, then slows). The **static curve is unchanged** (GR_final identical auto on/off, −27 dB); auto changes
  only the *time dynamics* → the transparent, "invisible" auto-release behavior. (A single burst doesn't expose the
  multi-stage adaptation fully; the load-bearing CLEAN fact is: auto = adaptive fast-attack / program-following release.)

### BRICKWALL stage — limiter (CLEAN)
- **Ceiling = exact sample-peak brickwall.** `out_samplepeak = bw_threshold` to **0.000 dB** at every tested ceiling
  (0, −1, −3, −6, −12) and every input level up to +12 dB over. No sample-peak overshoot ever.
- **Lookahead is SHORT:** zero-overshoot step shows GR begins **~26 samples (0.27 ms) before onset at OS#1/#2, ~15
  samples (0.16 ms) at OS#4/#6** (per-internal-block lookahead; pedalboard hides exact PDC). Output never exceeds
  ceiling at onset. This is a short-lookahead, heavily-oversampled limiter — NOT a long-lookahead clipper.
- **bw_true_peak_aware (KEY, OFF by default) — quantified:** ITU-style inter-sample-peak control. At base 96 k,
  ceiling −1.0 dB, HF tone @0.30·Nyquist, minimal OS (#1):
  - **TP=OFF → out sample-peak = −1.000 but reconstructed true-peak = −0.142 dB (overshoots ceiling by +0.86 dB).**
  - **TP=ON  → out sample-peak = −2.080, reconstructed true-peak = −1.277 dB (under ceiling).**
  - **TP-ON-vs-OFF true-peak delta ≈ 1.14 dB**, bought with ~1.08 dB extra sample-peak reduction.
  - Two independent knobs reduce true-peak: **(a) oversampling** (at OS#4/353 k, even TP=OFF keeps true-peak ≈ −0.96,
    i.e. at ceiling — high internal Fs resolves most ISPs), and **(b) the explicit `bw_true_peak_aware` flag**
    (an ITU-grade TP estimator inside the gain computer). Use both for codec-safe masters.
- **Oversampling enum — internal sample rate (44.1 k base × {1,2,4,8,16,32}):** `['#1 - 44.1kHz','#2 - 88.2kHz',
  '#3 - 176kHz','#4 - 353kHz','#5 - 706kHz','#6 - 1.41MHz']`. Aliasing ladder under heavy HF limiting (15 kHz into
  −12 ceiling) — each step ≈ **+12 dB alias rejection**: #1/#2 = −31 dBc, #3 = −43, #4 = −55, #5 = −67, #6 = −80 dBc.
  (#1 and #2 give identical aliasing → a minimum internal processing rate.) Default = **#4 (353 kHz)** = 8× at 44.1 k.
- **bw_channel_link (%):** stereo limiter link (default 90%); same crossfeed semantics as the soft stage.
- **bw_attack_bend / bw_attack_pivot / bw_release_bend / bw_release_pivot — INERT in the measured offline path.**
  Brute-force 7×7 (attack_bend × release_bend) and pivot 0…100 % null-diff (steady tones, transient bursts, slow
  ramps through the ceiling, TP on/off): output is **bit-identical (max|diff| = 0.0, −240 dB)** in all but two
  sporadic, non-deterministic cells (a6r5/a6r6 ≈ −6 dB, incoherent → a param-smoothing race, not a curve). The
  params commit and read back correctly (`bend 1..7`, `pivot 0..100%`) but do not alter rendered audio here. Treat
  as **modeled-but-NULL in this build/render path** (cf. the documented "inert/NULL params" gotcha; AE Drive/JFET).
  Their *intended* design (shapeable GR attack/release curvature: linear↔convex↔concave, pivot = knee position) is
  documented under "Why" for the clone, but do not claim a measured effect.

## Why / design rationale (music ↔ code — the two-stage musical intent)
This is the blueprint for **ES-X (leveler) → ES-L (brickwall)**: do the *musical* level-shaping gently and early,
then a *transparent safety* clamp last.
- **Two serial stages, soft first** → the soft compressor does the audible work (glue, leveling, density) with
  generous knee + program-adaptive time, so the brickwall only ever shaves the rare residual peak. A single hard
  limiter doing all the gain reduction sounds pumped/distorted; splitting "musical leveling" from "peak safety" is
  exactly why mastering chains run a leveler into a limiter. **Adopt this split for ES-X→ES-L.**
- **soft_range as a GR cap** → lets you commit to a fast/hard ratio (even ∞:1) for transients while guaranteeing the
  gain never ducks more than N dB → keeps the body from collapsing (limits "breathing"); the producer gets aggressive
  catch + a floor on how unnatural it can get. Cheap to implement (clamp `GR = min(GR, range)`), big musical payoff.
- **soft_wet_mix (linear-domain parallel)** → blends the uncompressed transients back in → upward-density/"NY" punch
  without losing snap. Linear (not dB) blend is the correct parallel-comp math and what gives the lift.
- **time_auto (program-adaptive release)** → the "Invisible" idea: a fixed release either pumps (too fast) or smears
  (too slow); an adaptive fast-attack/auto-release follows the material so the leveling is *inaudible*. This is the
  single most important behavior to port to ES-X's leveler.
- **M/S + channel_link + ms_balance** → process mid and side independently so a loud centred vocal doesn't duck the
  stereo width; balance trims how hard each is hit. Stereo-link crossfeed prevents image wander from one-sided ducking.
- **Short-lookahead, heavily-oversampled, exact sample-peak brickwall + optional ITU true-peak** → the safety stage is
  *transparent*: tiny lookahead (no smear), huge internal OS (no aliasing on the limiter's own gain-modulation
  sidebands), exact ceiling. **True-peak via two routes** (raw oversampling OR an explicit ITU estimator) is the key
  ES-L lesson: TP-aware buys ~1 dB of inter-sample headroom; pair it with ≥8× OS for codec-safe output. Contrast:
  Ozone Maximizer is sample-peak-only (+3 dB TP overshoot); TDR Limiter 6 and **G3-with-TP-ON** are true true-peak.

## Parameters (CLEAN — pedalboard raw is NORMALIZED [0,1] for every param)
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | OFF/ON | |
| unity_gain_monitor | bool | OFF/ON | A/B level-match: cancels input_gain/makeup for monitoring; NOT production path |
| input_gain | dB | −20…+20 (linear taper) | pure front gain; drives soft detector |
| oversampling | enum | #1 44.1k … #6 1.41 MHz (×1,2,4,8,16,32) | default #4 (353 k = 8×); +12 dB alias rej/step |
| **soft_engage** | bool | default ON | |
| soft_threshold | dB | −50…+10 (linear) | |
| soft_makeup | dB | −10…+10 (linear) | pure dB add, post-comp |
| soft_range_inf | bool | default ON | ON = no GR cap |
| soft_range | dB | 0.1…40 (exp taper) | **max gain-reduction cap** |
| soft_ratio_inf | bool | default OFF | ON = ∞:1 (clamp at threshold) |
| soft_ratio | — | 1.01…30 (exp taper) | ratio in `out=thr+(in−thr)/R` |
| soft_knee | dB | 0…40 (linear) | soft-knee width about threshold |
| soft_time_auto | bool | default ON | program-adaptive timing (overrides dials) |
| soft_attack_time | dial 0..10 | 0…10 (LOG speed, NOT ms) | dial→ms: 0≈0.5, 5≈30, 8≈738 (sat ~750 ms) |
| soft_release_time | dial 0..10 | 0…10 (LOG speed, NOT ms) | dial→ms: 0≈0.5, 5≈28, 8≈761 (sat ~760 ms) |
| soft_ms_enabled | bool | default OFF | mid/side independent processing |
| soft_ms_balance | dB | −20…+20 (linear) | tilt M vs S (~0.875 dB out/dB on pure-mid) |
| soft_channel_link | % | 0…100 | detector stereo link (0=indep,100=linked) |
| soft_wet_mix | % | 0…100 | parallel comp, **linear** blend |
| **bw_engage** | bool | default ON | |
| bw_threshold | dB | −20…0 (linear) | ceiling; exact sample-peak |
| bw_channel_link | % | 0…100 (default 90) | limiter stereo link |
| bw_true_peak_aware | bool | default OFF | ITU true-peak; ON buys ~1.1 dB TP headroom |
| bw_attack_bend | int | 1…7 (default 2) | **INERT in measured path** (modeled, no audio effect) |
| bw_attack_pivot | % | 0…100 (default 50) | **INERT in measured path** |
| bw_release_bend | int | 1…7 (default 2) | **INERT in measured path** |
| bw_release_pivot | % | 0…100 (default 50) | **INERT in measured path** |

(No `meter_type` param exists in v1.18.9 despite earlier expectation — 27 params total, all listed.)

## FFI contract
None — JUCE C++, stripped, no clean C ABI. Host-driven (pedalboard) only.

## CLEAN measurements (key tables)
- **Soft ratio law:** `out_dB = thr + (in−thr)/ratio`, verified exact (R=2/4/8/30, ≤0.03 dB error). ∞:1 = clamp at thr.
- **Soft range cap:** GR freezes at `range` dB (range=6→−6.01, range=12→−12.00), then unity-tracks; range_inf = uncapped.
- **Soft knee:** knee=24 → GR onset ~12 dB below thr, smooth easing into ratio line.
- **Soft dial→time:** table above; `t_ms ≈ 0.5·10^(0.32·dial)`, saturates ~750 ms at dial ≥8. time_auto → adaptive (attack sub-ms, release ~1 ms fast-onset then slows).
- **Soft parallel:** linear blend `(1−w)·dry + w·wet` (0/25/50/75/100% → 0.00/−2.12/−4.93/−9.12/−17.50 dB @0 dBin).
- **Brickwall ceiling:** exact to 0.000 dB (sample-peak), no overshoot.
- **Brickwall lookahead:** ~0.16–0.27 ms (15–26 samples), OS-dependent.
- **True-peak (96 k, −1 ceiling, HF .30·Nyq):** OFF → TP −0.14 (over +0.86); ON → TP −1.28 (under). Δ ≈ 1.14 dB. OS#4 alone keeps TP ≈ ceiling even with TP OFF.
- **Oversampling alias ladder:** −31/−31/−43/−55/−67/−80 dBc for #1…#6.
- Saved trajectories: `data/softtime_dial*.npy`, `data/bend2_*.npy` (bend arrays confirm flat/inert).

## To implement (CLEAN clone path — feeds ES-X leveler + ES-L brickwall)
**ES-X (soft leveler) — reuse directly:**
1. Peak detector with stereo `channel_link` crossfeed + optional M/S split (`ms_enabled`, `ms_balance` tilt).
2. Gain computer: `out=thr+(in−thr)/ratio` (hard-knee), soft-knee = quadratic spline of width `knee` about thr;
   `ratio_inf` ⇒ clamp at thr; clamp `GR ← min(GR, range)` for the range cap (`range_inf` ⇒ skip).
3. Envelope: branching attack/release one-poles; map the **0..10 dial logarithmically** to RC (≈`0.5·10^(0.32·dial)` ms,
   cap ~750 ms) — do NOT treat the dial as ms. Provide a `time_auto` mode = fast attack + adaptive (fast-onset,
   level/program-following) release (multi-stage release or auto-RC from crest factor) for the "invisible" feel.
4. `makeup` = post-gain dB; `wet_mix` = **linear** parallel blend with the dry. `input_gain` = front dB.
**ES-L (brickwall) — reuse directly:**
5. Short lookahead (~0.2 ms) gain envelope → exact sample-peak ceiling (`out_peak == ceiling`, no overshoot).
6. Internal oversampling (selectable ×2…×32) for the limiter's gain-modulation; ≈+12 dB alias rejection per octave.
7. True-peak mode = ITU-BS.1770 polyphase-FIR ISP estimate folded into the gain computer → buys ~1 dB inter-sample
   headroom; combine with ≥8× OS for codec-safe masters. (This is the TP design ES-L should ship — see TDR Limiter 6.)
8. **Skip bend/pivot** unless you specifically want a shapeable GR curve (they are inert in G3's measured path; if you
   add curve-bending, the intent is attack/release trajectory curvature linear↔convex↔concave with a pivot knee — but
   that is a design choice, not a measured G3 behavior).
9. Series order: leveler FIRST, brickwall LAST (out = brickwall(leveler(x))).

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (none here — binary stripped + undrmed, nothing extracted).
