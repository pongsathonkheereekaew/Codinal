# dynamics — shared public technique

CLEAN (public DSP). Compressor / limiter / gate / expander core. Stage decisions live in Mixing (per-track/bus)
and Mastering (glue + final limit). This is the *how*.

## Gain computer (the law)
- **Compressor**: above threshold, `GR = (in−thr)·(1−1/ratio)`; **knee** softens the corner (soft-knee blends over a dB window). ratio 1=none, ∞=limiter.
- **Limiter**: ratio ≫ (∞) with low/zero attack + **lookahead** → brickwall ceiling; true-peak variant oversamples to catch inter-sample peaks.
- **Expander / gate**: below threshold, downward `gain = (in−thr)·(ratio−1)` (expander) or hard cut (gate); **Range** sets max attenuation (Range=0 → no effect — common trap).

## Detector + timing
- **Peak** (fast, catches transients) vs **RMS / boxcar window** (smooth, loudness-like). Release floor often = the RMS window length, not the release param.
- **Attack** = time to engage GR; **release** = time to recover. Program-dependent / dual release = two time constants (fast for transients, slow for body).
- Feed-forward (modern) vs feedback (vintage) detector.

## Auto-gain / makeup
Compensate the level lost to GR so A/B is level-matched (else "louder = better" bias).

## True-peak (limiter/master)
Sample peak ≤ 0 dBFS can still inter-sample-overshoot. 4× oversample to read true-peak; ceiling typically −1 dBTP for lossy codecs (ITU-R BS.1770).

## Stage application (don't duplicate here)
Mixing = control/effect/glue per track or bus (ratio/attack/release to taste; `purpose: control|effect|glue`). Mastering = ≤3 dB bus glue + final true-peak limiter + optional multiband (`type: broadband|multiband|parallel|dynamic_eq`). Shared core ranges: `../schemas/dsp-blocks.md`. Target a researched comp/limiter via handoff (`easby-programming/plugins/{AC-1,AL-1,Pro-L2,Pro-C3,ML8000}.md`). Public lit: Giannoulis et al. JAES 2012; Zölzer DAFX.
