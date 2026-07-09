# Implementation doctrine — RT-safety + DSP correctness

How to turn a CLEAN BuildSpec into shippable plugin code. All public engineering practice (CLEAN).
Applies to JUCE / iPlug2 / nih-plug / any format. Checklist — verify every box before commit.

## Real-time safety (audio thread = `processBlock`) — non-negotiable
The audio callback must never block. On the audio thread, **NO**:
- heap alloc / free (`new`, `malloc`, `std::vector` resize, `std::string`, lambda capture that allocates)
- locks / mutexes / spin on contention (use lock-free SPSC FIFO or atomics for UI↔audio)
- syscalls / file / network / logging / `printf`
- unbounded loops, exceptions, RTTI on the hot path
- denormals left unflushed (see below)
Pre-allocate all buffers in `prepareToPlay`/`prepare` (you get sampleRate + maxBlockSize there).

## Parameters
- Smooth every audible param (gain, freq, mix) — `juce::SmoothedValue` / one-pole ramp — to kill zipper noise.
- UI→audio: atomic or lock-free queue, never a lock. Audio→UI meters: atomic store, relaxed.
- Map normalized↔real with the plugin's real skew (log for freq/time). Watch units (seconds vs ms — see AC-1).
- Report latency (`setLatencySamples`) for any lookahead/oversampling, else PDC breaks.

## Numerical correctness
- **Denormals:** enable FTZ+DAZ (`ScopedNoDenormals`, or set MXCSR) around the block; feedback paths (smoothers,
  reverbs, one-poles) generate them → 100× CPU spikes without flush.
- **f32 vs f64:** state/accumulators/coefficients in f64 (recursive filters, RMS sums, phase); audio I/O may be f32.
  AC-1 keeps all DSP state f64 — match that for level accuracy.
- **NaN/Inf guards** at stage boundaries on feedback/division; sanitize before output.
- **Coefficient recompute** only when a param changes, not per-sample (cache; see AC-1 setters → `recompute_*`).
- **Oversampling:** polyphase FIR/IIR; account for group delay in latency; band-limit before nonlinearities
  (saturation/clip) to avoid aliasing — process the nonlinearity at the oversampled rate.

## True-peak / limiting
- Inter-sample peaks need ≥4× oversampled detection for true-peak ceilings (BS.1770). Sample-domain ceiling ≠ TP.
- Brickwall: lookahead = latency; smooth the gain, not the signal; release in dB-domain.

## Structure
- Stage objects with `prepare(spec)` + `reset()` + `process(block)`; no global state.
- Reuse one verified gain computer across stages where the reference does (AC-1's `RmsLift` = comp + maximizer).
- Keep a `reset()` that clears all state (smoothers, ring buffers, latency lines) — test it (silence→silence).

## Verify before commit (ties to BuildSpec.null_test)
1. **Null-test** vs reference via the easby-decomp harness — residual below the stage threshold (e.g. ≤ −36 dB).
2. **pluginval** strictness 10 (or format validator) — passes.
3. **Denormal/CPU** check — no spike on silent or decaying input.
4. **Reset/latency** — PDC correct, reset returns to silence.
5. **Firewall** — `assets/firewall_check.sh` green (no REF/quarantine references).

## Clean-room reminder
Build from CLEAN BuildSpec only. The *technique* (RMS leveler, true-peak FIR) is public DSP; the reference
plugin's *exact code* is REF — never inline it. When unsure why a curve looks a way, measure, don't decompile-paste.
