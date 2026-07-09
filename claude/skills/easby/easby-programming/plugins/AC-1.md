# AC-1 — Naturl Audio (Compressor + RMS Maximizer)

| | |
|---|---|
| Vendor / ver | Naturl Audio · v0.1.0 · VST 3.8 |
| Type | Compressor (RMS leveler) + RMS-ceiling Maximizer/limiter |
| Tech | JUCE 8.0.12 C++ shell → Rust `dynamics` crate via flat C FFI (108 `_dynamics_*` exports); WebKit UI |
| Binary | universal Mach-O bundle, **not stripped** (~46k syms); dev cargo path leaked: `andrewrynhard`; uses `meters` crate (EBU R128) |
| Source | `private-research/AC-1/` — `docs/algorithm-decode.md`, `docs/architecture-findings.md`, `decomp/{dsp.c,stage2.c,ffi-surface.md}`, `Tools/ac1_ffi.py` |
| Provenance | formulas below = **REF** (Ghidra); curves/times/round-trips = **CLEAN** (FFI black-box) |

## Signal chain (REF, confirmed CLEAN end-to-end)
```
x → CompressionDetector (dual-boxcar RMS)
  → RmsLift::desired_gain  (RMS leveler: twin asymmetric dB smoothers, min-of-ceilings)
  → LinkController         (dB-domain deviation-gated FIR target smoother)
  → ×OS → RmsLift again    (maximizer: RMS ceiling + auto-gain) → true-peak brickwall → ÷OS
```
Key insight: **`RmsLift::desired_gain` is ONE universal gain computer**, configured twice (gentle
comp + RMS-ceiling limiter). It is NOT threshold/ratio — explains the gentle, ratio-insensitive curve.

## Gain law — `RmsLift::desired_gain` (REF @0x52c460)
```
rms_db = (rms<=0) ? -90 : 20*log10(sqrt(rms))
lift   = max(0, target - rms_db)
g_db   = svf_smooth2( svf_smooth1(lift) )     # two cascaded asymmetric (attack≠release) dB smoothers
gain   = min( 10^(g_db/20), max_gain, ceiling )   # min-of-ceilings → can't reach a hard ratio line
```
Each smoother: deadband 1e-9, separate rise/fall coef, time-constant term → `dual_release` shaping.

## Link curve — `LinkController::process_target` (REF @0x53159c)
NOT stereo-link. A **dB-domain, deviation-gated FIR smoother of the gain target over time**:
```
t_db = 20*log10(max(target,1e-8))
filt = Σ coef[i]*ring[i]              # FIR over N=link_n taps; sharpness/curve_mode shape coef[]
if |t_db - filt| >= link_threshold: ring<<t_db; recompute    # else hold (gate)
return 10^(filt/20)
```
strength = blend; `get_last_block_lambda` = realized coeff (for CLEAN fitting).

## Detector + timing (REF + CLEAN)
- `CompressionDetector::process` (@0x52d524): `x²` → **two boxcar moving-avg RMS windows** (running-sum
  rings, different lengths) = fast+slow program-dependent timing. Release floor (~196 ms, CLEAN) = RMS
  **window length**, not `detector_release_time`.
- `set_window_normalized(w)` (@0x4e429c): smoother coef `α = clamp(exp((1−w)^4·7.5154)·5.4462e-4, 1e-6, 1)`.
- `set_detector_attack_time(t)` (@0x4e5538): **t in SECONDS** — `ctrl = clamp((t−0.0005)/0.0335, 0,1)`,
  useful 0.5–34 ms. CLEAN: set 5 ms → 63% in ~10.7 ms (≈2× linear).

## CLEAN measured compression curve (thr −30, knee 0)
| in dB | GR @r2 | GR @r4 | GR @r10 |
|---|---|---|---|
| −24 | −0.6 | −0.9 | −1.0 |
| −12 | −2.9 | −3.8 | −4.3 |
| 0 | −4.3 | −5.2 | ~−6 |

Ratio barely moves GR (leveler, not downward comp). `block_gain_reduction_*` getter = **linear gain** (0.684 = −3.3 dB).

## FFI contract (CLEAN — drives the real DSP, no host)
`ctypes.CDLL(binary)`; dlsym names drop leading `_`. AArch64: continuous=f64(d0), int/bool=i32(w1).
- `dynamics_create(sample_rate:f64) -> handle`  (SR=0 → `NoMem` panic)
- `dynamics_update_parameters(handle)` — **commits + un-mutes** (silent until called)
- `dynamics_set_<cont>(h, f64)` / `dynamics_set_<int>(h, i32)` ; `dynamics_get_<x>(h) -> f64|i32`
- `dynamics_process_audio_mono_f64(h, in*, out*, len)` — **separate in/out**; first block = warmup; latency 92 @48k
- Flow: `create(SR) → set… → update_parameters() → reset() → process(block)`
Full 108-fn list: `private-research/AC-1/decomp/ffi-surface.md`. Working harness: `Tools/ac1_ffi.py`.

## To reuse in our
One `RmsLift` gain computer (reuse for comp + limiter), dual-boxcar RMS detector, gated-FIR "Link"
smoother, true-peak ceiling brickwall. Build from CLEAN measurement + public literature (REF rows are
reference only — reproduce black-box before shipping).
