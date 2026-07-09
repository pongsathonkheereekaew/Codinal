# DSP building blocks — verified public primitives (CLEAN)

Reusable, public-domain DSP primitives. All **CLEAN** (textbook/AES — citable, product-safe). BuildSpec
stages assemble these instead of re-describing per plugin. Implement once, verify once, reuse everywhere.
Cite the literature, not any reference plugin's code.

## Level / conversion
- **dB↔linear:** `lin = 10^(dB/20)`, `dB = 20·log10(max(|x|, 1e-12))`. Floor to avoid −inf.
- **One-pole smoother (ballistics):** `y += a·(x − y)`, `a = 1 − exp(−1/(τ·fs))`. Asymmetric: pick
  `a_att` when `x>y` else `a_rel` → attack/release. (AC-1 maps a knob → `a` exponentially.)
- **Param ramp:** linear or one-pole toward target over N samples; kills zipper noise.

## Detectors
- **Peak:** `|x|`, optional one-pole release. **RMS (boxcar):** running-sum ring `Σx²/N` (AC-1 uses two
  windows = program-dependent). **RMS (one-pole):** `p += a(x²−p)`, level=`√p`.
- **Program-dependent release:** blend fast+slow detectors (dual-window or dual one-pole).

## Gain computers
- **Hard-knee comp (Giannoulis 2012):** over = `L_db − thr`; `GR = over>0 ? over·(1−1/ratio) : 0`.
- **Soft knee (width W):** quadratic interp over `[thr−W/2, thr+W/2]`.
- **Limiter:** ratio→∞ → `GR = max(0, L_db − ceil_db)`; combine over lookahead by **max** (AL-1).
- **RMS leveler / "lift":** push level toward a target, bound by min-of-ceilings (AC-1 `RmsLift` family —
  the *technique* is public AGC; AC-1's exact form is REF).

## Time / peak
- **Lookahead delay line:** ring buffer length = lookahead samples; report as latency.
- **True-peak (BS.1770):** ≥4× polyphase upsample, take max |·| → inter-sample peak.
- **Oversampler:** polyphase FIR (linear-phase) or IIR (lower latency); band-limit before nonlinearities.

## Shaping
- **Soft-clip:** `y = x − k·x³` (cubic) or `tanh(g·x)/g` (drive g). Odd-symmetric (MELD MixHead). Oversample.
- **Biquad (RBJ cookbook):** LP/HP/peak/shelf; f64 state (TDF-II) for stability.

## Mapping → plugins
| primitive | used by |
|---|---|
| one-pole asymmetric smoother | AC-1 (twin), AL-1 (release pole) |
| dual-window RMS | AC-1 detector |
| max-combine + lookahead | AL-1 limiter |
| true-peak FIR | Pro-L2, AC-1 maximizer |
| soft-clip tanh/cubic | MELD MixHead + Loudness |
| RMS leveler (AGC) | AC-1 RmsLift |

Each primitive has a `null_test` when wired into a BuildSpec — verify the assembled stage vs the reference
(easby-decomp harness), residual below threshold. See [implementation-doctrine.md](../implementation-doctrine.md).
