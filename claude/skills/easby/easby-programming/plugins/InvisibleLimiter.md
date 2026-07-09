# Invisible Limiter — A.O.M. (Audio Optimization & Mastering / AOM Factory) (Limiter — transparent brickwall)

| | |
|---|---|
| Vendor / ver | A.O.M. Factory · v1.18.9 (bundle id `jp.aom-factory.vst3.InvisibleLimiter`) |
| Type | Dynamics — mastering **brickwall limiter** ("transparent / invisible"); lookahead, sample-exact ceiling, oversampled true-peak |
| Tech | C++/JUCE (AppKit + CoreText UI). No FFI, no Rust. Single self-contained DSP. |
| Binary | universal (x86_64 + arm64), MH_BUNDLE. **Stripped**: 3 exported syms (VST3 factory only), 434 total. **No DRM** (no `LC_ENCRYPTION_INFO`, no PACE/`__Pace_Eden`). No leaked build paths. → static is a wall, **no usable REF**; the CLEAN behavioral spec below is the complete deliverable. |
| Provenance | **100% CLEAN** (black-box measurement + public DSP literature). Zero disasm-derived facts. |
| Measured on | v1.18.9 · SR 48000 · pedalboard 0.9.17 · 2026-06-26 |
| Source | `private-research/AOM_InvisibleLimiter/Tools/il_sysid.py`, `…/data/measured_tables.txt` |

## Signal chain
```
x → [input_gain] → [M/S encode (if channel_mode=M/S)]
   → OVERSAMPLE ↑(x1..x16) → lookahead peak detector → adaptive minimal gain-reduction curve (Shape Linear/Log)
   → gain ·  → Overshoot policy on oversampled residual ISP (Thru / Clip / Suppress) → DOWNSAMPLE ↓
   → [M/S decode] → [output_gain] → y
   (unity_gain_monitoring: applies −input_gain at the very end for level-matched A/B)
```

## Per-stage formula (all CLEAN)
- **Static gain law (brickwall)** (CLEAN): pure hard-knee brickwall. Below ceiling: unity (gain_red = −0.00 dB, measured to ±0.00). At/above ceiling: output clamped to `limit_level` exactly; gain_red = −(in − ceiling). **Ceiling accuracy = 0.00 dB** (sample-peak) at 1 kHz, confirmed −30…+12 dBFS sweep. **Knee = 0 dB** (no soft-knee region on a steady tone). Identical for Shape Linear and Log on steady/slow signals (0.000 dB difference).
- **Lookahead / latency** (CLEAN): host-reported PDC = **2496 samples = 52.000 ms @ 48 kHz** (help-doc "approx. 53 ms"). **OS-independent** (same 2496 at x1…x16). Lookahead is defined in ms (round number) → at other SR it scales to ≈52 ms. Proven real by a silent→loud step producing **zero overshoot** (output never exceeds ceiling even on a single-sample +20 dB spike).
- **Release** (CLEAN): **no traditional release tail and no program ducking.** Gain reduction is **time-localized to each peak** (within its lookahead window) and recovers to unity within ~2–4 ms of the transient. A −30 dBFS probe tone surrounding a loud burst shows ≈0 dB ducking outside the burst window; a held carrier shows no post-burst level dip. This is the minimal-gain-reduction-"area" behavior that makes it "invisible" — opposite of a release-knob limiter (Pro-L2). No release control is exposed.
- **Oversampled true-peak** (CLEAN): true-peak control is achieved by **oversampling**, not a separate TP mode. HF tone (7 kHz) clamped to −1 dB ceiling:
  - **OS x1: true-peak overshoots +0.64 dB** (sample-peak only — inter-sample peaks leak).
  - **OS x8: true-peak +0.04 dB** (essentially TP-safe).
  - Higher OS = finer internal sampling → the lookahead/clip stage catches inter-sample peaks. Monotonic: x1→+0.64, x8→+0.04.
- **Overshoot policy** (CLEAN): a **secondary stage acting on the oversampled residual** inter-sample overshoots that escape the primary (sample-exact) gain reduction. On a 1 kHz square (+6 over ceiling −1) at OS x8:
  - **Thru** = "do nothing" → out sample-pk **+0.22**, TP8x +1.25 (lets overshoots through).
  - **Clip** = "hard-clip overshoots" → out sample-pk **+0.00**, TP8x +1.07.
  - **Suppress** = "gradual reduction around overshoots" → out sample-pk **−0.84**, TP8x **+0.40** (best true-peak control; pulls slightly below ceiling). Default.
  (On tones/clicks the three are indistinguishable — the policy only engages on oversampled residual ISP, which a band-limited square's Gibbs overshoot exposes.)
- **Shape Linear vs Log** (CLEAN): "Reduction curve shape." Static input/output law and the slow-ramp gain-reduction trajectory are **identical (0.000 dB)**. The only measurable difference is a **sub-0.2 dB micro-shape change at fast-transient gain edges** (≈0.186 dB peak, at the lookahead transition). Interpretation: Linear = piecewise-linear gain interpolation in linear amplitude; Log = piecewise-linear in dB. It is a transient-character/distortion-shaping flavor, NOT a macroscopic curve change.
- **M/S routing** (CLEAN): `channel_mode = M/S` → **encode (M=(L+R)/2, S=(L−R)/2) → limit M and S independently → decode.** Verified: mid-only input (L=R) keeps the side channel silent (−240 dB) and vice-versa. L/R mode limits L and R independently. (M-channel output for a mid-only signal sits 3 dB below the L/R figure due to the mid sum/scale convention.)
- **Oversampling FIR / aliasing** (CLEAN): impulse at x1 is a single sample (no FIR) → the OS converter adds no separately-reported latency. Anti-alias quality (11 kHz hot tone, worst non-harmonic image): x1 −25.0, x2 −38.8, x4 −50.8, x8 −63.6, x16 −74.1 dBc (≈+12 dB rejection per doubling). OS label shows internal Fs = ratio × host SR (x1=48k, x2=96k, … x16=768k at 48k host).
- **input_gain / output_gain** (CLEAN): both pure linear-in-dB gains. input_gain 0..20 dB (pre, drives into the ceiling); output_gain −10..10 dB (post, after limiting — a make-up/trim, does NOT change the ceiling). unity_gain_monitoring applies the inverse of input_gain at the output for level-matched A/B.

## Why / design rationale (music ↔ code)
- **Minimal-area, time-localized gain reduction (no release tail)** → no pumping, no "breathing," surrounding program untouched → the defining "invisible/transparent" character. The designer optimizes the gain curve to remove exactly the over-ceiling energy and nothing more, rather than holding a release envelope. This is *why* it is the reference transparent mastering limiter and a prime ES-L target.
- **Long 52 ms lookahead (normal)** → ample time to pre-ramp the gain so even sharp transients are clamped with a smooth, low-distortion curve → 0% THD on tones, sample-exact ceiling, no clicks. The trade is latency (unusable for live monitoring) → hence the LL sibling.
- **Oversampling-as-true-peak** → rather than a dedicated ISP estimator, it runs the whole limiter at higher Fs so inter-sample peaks become real samples it can catch → simple, accurate, and the OS factor doubles as the quality/CPU knob. Safe for lossy codecs at OS≥8.
- **Overshoot Thru/Clip/Suppress** → lets the user choose the residual-ISP trade: maximum transparency vs hard safety vs gentle over-suppression → tailors the tiny amount of peak that survives the primary stage.
- **Shape Linear/Log** → fine control over the curvature of the gain transition → subtle harmonic/transient-edge flavor without altering loudness.
- **M/S processing** → limit the stereo image's center and sides independently → keep a wide mix from collapsing when the center is hot. Standard mastering routing.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| input_gain | dB | 0.0 … 20.0 (def 0) | pre-gain, linear-in-dB, drives into ceiling. **pedalboard raw is NORMALIZED [0,1]** → raw=(real−0)/20 |
| limit_level | dB | −20.0 … 0.0 (def 0) | ceiling/threshold (one knob; brickwall). raw=(real+20)/20 |
| output_gain | dB | −10.0 … 10.0 (def −0.10) | post trim/make-up, does not move ceiling. raw=(real+10)/20 |
| overshoot | enum | Thru / Clip / Suppress (def Suppress) | residual-ISP policy. norm: Thru[0–0.2475] Clip[0.25–0.7475] Suppress[0.75–1.0] |
| shape | enum | Log / Linear (def Linear) | reduction-curve interp. norm: Log[0–0.4975] Linear[0.5–1.0] |
| channel_mode | enum | L/R / M/S (def L/R) | norm: L/R[0–0.4975] M/S[0.5–1.0] |
| oversampling_factor | enum | x1 / x2 / x4 / x8 / x16 (def x1) | label shows internal Fs = ratio×hostSR. norm bands at 0/0.25/0.5/0.75/1.0 (±~0.06) |
| bypass | bool | OFF/ON (def OFF) | true unity passthrough when ON |
| unity_gain_monitoring | bool | OFF/ON (def OFF) | applies −input_gain at output for level-matched A/B |

## FFI contract
None — self-contained JUCE C++ plugin, no exported DSP ABI (stripped, 3 syms = VST3 factory).

## CLEAN measurements
See `private-research/AOM_InvisibleLimiter/data/measured_tables.txt` (full static sweep, latency, TP per OS, overshoot divergence, OS aliasing) + `.npy` envelopes (`step_il`, `release_il`, `shapetraj_{lin,log}_il`).
- Ceiling accuracy: **0.00 dB** (sample-peak, 1 kHz, −30…+12 dBFS). Knee: 0 dB.
- Lookahead: **2496 samp = 52.000 ms @ 48 k**, OS-independent.
- True-peak: OS x1 **+0.64 dB** over ceiling; OS x8 **+0.04 dB** (oversampling = the TP mechanism).
- Overshoot @ OS x8 on hot square: Thru +0.22 / Clip +0.00 / Suppress −0.84 dB (sample-peak).
- THD on +12-over steady 1 kHz tone: **0.000%** (transparent). No release tail; no program ducking.

## To implement (ES-L — prime reference for an adaptive transparent brickwall)
CLEAN-only path; everything above is measurement/public-DSP and product-safe.
1. **Architecture = lookahead minimal-gain-reduction brickwall** (NOT a release-time limiter). Per sample, compute the gain needed to keep the (optionally oversampled) signal at `ceiling` and apply a **smooth lookahead gain envelope** that (a) starts reducing before each peak, (b) reduces by the minimum required, (c) returns to unity right after the peak with **no held release**. Target: 0% steady-tone THD, sample-exact ceiling, no pumping.
2. **Lookahead window** sized in ms (e.g. a "normal/52 ms" and a "low/7 ms" mode → see InvisibleLimiterLL.md). Longer window → smoother curve → more transparent; shorter → lower latency. Report PDC = window length to the host (OS-independent).
3. **True-peak via oversampling**: run the detector+gain (and the clip/suppress residual stage) at x4/x8 to catch inter-sample peaks; expose an OS factor that doubles as quality/CPU. At x8 expect ≤0.05 dB true-peak error.
4. **Residual-overshoot policy** (Thru/Clip/Suppress) as a secondary oversampled stage on whatever the primary smooth gain leaves above ceiling — default = gentle Suppress.
5. **Shape (Linear/Log)** = choose linear-amplitude vs dB-linear interpolation of the lookahead gain ramp (sub-0.2 dB flavor — low priority).
6. **M/S option** = encode → two independent limiters on M & S → decode.
7. Building blocks: smoothed lookahead gain (max-hold + min-area smoothing), polyphase oversampler (≈+12 dB alias rejection/octave), linear-in-dB I/O gains, M/S matrix. See `building-blocks/` and `implementation-doctrine.md`. The AL-1 / Pro-L2 / Ozone-Maximizer entries contrast the release-time-limiter family; Invisible Limiter is the **no-release, minimal-area** archetype — and TDR Limiter 6's true-peak stage is the genuine-TP counterpart.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). **REF** = disasm-derived (none here — stripped, no DRM, static is a wall).
