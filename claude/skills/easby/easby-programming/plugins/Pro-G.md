# Pro-G — FabFilter (Gate / downward expander — multi-style, lookahead)

| | |
|---|---|
| Vendor / ver | FabFilter · Pro-G · VST3 (Fx) · no DRM |
| Type | **Gate / downward expander (multi-style, lookahead)** — also does upward expansion + ducking; sidechain HP/LP EQ, hysteresis, OS |
| Tech | **VST3 (FabFilter), stripped, black-box only** — universal Mach-O bundle (x86_64+arm64), STRIPPED (6 defined syms), **NO PACE/iLok**, no C FFI. No static analysis used or permitted. |
| Binary | `/Library/Audio/Plug-Ins/VST3/FabFilter Pro-G.vst3` · self-contained (libz/libc++ + system frameworks only) |
| Provenance | **100% CLEAN** — every fact below is black-box MEASUREMENT (signal in → measure out) via pedalboard. No disasm. |
| Measured on | Pro-G (installed 2026-06) · SR 96 kHz · `private-research/Pro-G/Tools/prog_sysid.py` (pedalboard host) · **2026-06-22** |
| Source | `private-research/Pro-G/` — `Tools/prog_sysid.py`, `docs/measurements.md` |

## Signal chain (CLEAN behaviour)
```
inL,inR ─┬─────────────────────────────────────────────────────► [audio path: GAIN ONLY] ─► ×g(t) ─► out
         │                                                                                        ▲
         └─► DETECTOR path  ──► side_chain_level (±36 dB) ──► SC HP filter ──► SC LP filter ──►   │
              (internal key, or external "Side chain input")    (expert_mode only)                │
                       │                                                                          │
                       └─► level detect ──► gain computer (style-dependent static curve) ──► ─────┘
                            ── attack/hold/release dB-domain smoother ── (hysteresis open≠close)
              [lookahead delays AUDIO so detector "sees ahead"; fixed 441-smp PDC when enabled]
              [OS 2x/4x runs the detector/gain at higher rate; +62/+68 smp PDC]
```
Key insight (CLEAN, confirmed): the gate is a **pure time-varying gain** g(t) on the audio — steady tone
above threshold shows **all harmonics < −160 dBc** (no waveshaping/distortion). All the character is in the
detector + gain-computer + smoother. The SC HP/LP filters act on the **DETECTOR ONLY** (audio path unaffected).

## Per-stage formula (all CLEAN)
- **Downward-expander gain law** (below threshold), styles Classic/Clean/Vocal/Guitar:
  `gain_dB = (R − 1)·(in_dB − thr_dB)`, clamped to a floor of `−range_dB`; **unity (0 dB) above threshold**.
  Measured slope = exactly (R−1): R=2→slope1, R=4→3, R=10→9 (linear fit, r≈1.0). Textbook downward expander.
- **Knee** (0..30 dB): symmetric soft knee centred on thr. knee=0 → hard onset at thr; knee=30 → onset/floor
  spread ~±15 dB around thr (gradual bend). (Giannoulis soft-knee with width W = `knee`.)
- **Upward-expander gain law** (style = **Upward**), above `threshold_upward`:
  `gain_dB = (R_up − 1)·(in_dB − thr_up)` for in > thr_up, **unity below** → boosts loud parts (expansion up).
  Measured: thr_up −12, R_up 2.5 → +6 dB @ −8 dBFS, +12 @ −4, +18 @ 0 = (2.5−1)·(in−thr_up). Exact.
- **Ducking** (`ex_style` = Ducking): **inverts** the gate — attenuates ABOVE thr by `range`, passes BELOW thr.
- **Smoother**: gain rides in the **dB domain** (release falls through equal-dB checkpoints at ~equal time/setting).
  Attack opens fast, hold holds the plateau, release closes over the set time (see timing table).
- **Hysteresis**: gate opens at `threshold` but **closes lower** (open−close gap, style-dependent — prevents chatter).

## Parameters (CLEAN — pedalboard, 40 params; gate-relevant subset + globals)
| param | unit / range (displayed) | mapping | notes |
|---|---|---|---|
| `threshold` | dB −60..0 | linear | gate/expander threshold (downward acts below it) |
| `ratio` | 1:1 .. 100:1 | **nonlinear** (raw0.4→2, 0.6→4, 0.9→10, 0.95→24, 1→100) | expansion ratio R; slope below thr = (R−1) |
| `range` | 0..100 dB | **nonlinear** (raw0.5→16, 0.7→36, 1→100) | **max attenuation floor** = −range dB (measured exact: 60→−60) |
| `style` | enum 0..4 | — | **Classic / Clean / Vocal / Guitar / Upward** (see fingerprints) |
| `attack` | 0..1 sec | **nonlinear/cubic** (raw0.2→1.6ms, 0.5→62ms, 1→1s) | open time; τ(10→90%)≈**0.49×set** ms (≥~0.3 ms); ≤0.05 ms = resolution-bounded≈instant |
| `hold` | 0..250 ms | nonlinear | plateau held open after signal drops, before release |
| `release` | 0..**5 sec** | nonlinear (raw0.1→3.4ms, 0.5→429ms, 1→5s) | close time (bounds attr wrongly says 999) |
| `knee` | 0..30 dB | linear | soft-knee width around threshold |
| `lookahead` | 0..10 ms | nonlinear | detector look-ahead; **PDC fixed 441 smp (4.59 ms @96k) when enabled, regardless of value** |
| `lookahead_enabled` | Disabled/Enabled | — | master toggle for lookahead |
| `threshold_upward` | dB −30..0 | linear | upward-expansion threshold (Upward style) |
| `ratio_upward` | 1:1 .. 3:1 | **linear** (raw0.5→2.0, 1→3.0) | upward expansion ratio R_up |
| `left/right_side_chain_level` | dB ±36 | linear | detector gain → shifts **effective threshold** (+12 dB SC ⇒ −12 dB eff thr) |
| `left/right_side_chain_mix` | −1..1 | — | per-channel SC blend |
| `high_pass_frequency` | 5..30000 Hz | log | **SC HP** (detector-only); needs `expert_mode=On` |
| `low_pass_frequency` | 5..30000 Hz | log | **SC LP** (detector-only); needs `expert_mode=On` → SC bandpass for selective gating |
| `side_chain_input_signal` | Normal / Side chain input | — | external SC bus selector; **HOST-BLOCKED** (needs DAW w/ separate SC input) — swaps only the detector source bus, detector law identical |
| `audition_side_chain` | Off/On | — | monitor the (filtered) detector signal |
| `ex_style` | (Other) / **Ducking** | — | hidden: **Ducking** inverts the gate (attenuate above thr) |
| `expert_mode` | Off/On | — | **enables the SC HP/LP filter section** (off ⇒ filters inert) |
| `channel_mode` | Left/Right / Mid/Side | — | detection/processing topology |
| `oversampling` | Off / 2x / 4x | — | PDC +0/+62/+68 smp @96k; little aliasing on clean material |
| `wet_level`/`dry_level`(±∞..36 dB), `wet_pan`/`dry_pan` | | | parallel wet/dry mix + pan |
| `input_level`/`output_level`(±∞..36), `input_pan`/`output_pan`, `bypass`, `host_bypass` | | | I/O trim, pan, bypass |
| (midi_state, midi_cc, pitch_bend, channel_pressure, internal, interface_show_display) | | | MIDI/UI plumbing — not DSP |

## CLEAN measurements (SR 96 kHz)

**Static downward curve** (Classic, thr −30, range 60, ratio 10): unity for in ≥ −28 dBFS; below thr drops
steeply to the −60 dB floor (−32→−10.9 dB gain, −36→−47, ≤−40→−60). Above thr = 0.00 dB exactly.

**Floor vs `range`** (thr −30, ratio 10, deep input): floor gain = −range exactly →
| range | 10 | 20 | 40 | 60 | 90 |
|---|---|---|---|---|---|
| floor gain (dB) | −9.9 | −20.0 | −40.1 | −60.1 | −90.3 |

**Slope vs `ratio`** (asymptotic linear fit below thr, below knee, above floor): slope = **(R−1)** exactly →
| ratio R | 2 | 3 | 4 | 6 | 8 | 10 |
|---|---|---|---|---|---|---|
| slope (dB/dB) | 1.00 | 2.00 | 3.00 | 5.00 | 7.00 | 9.00 |

**Style fingerprints** (thr −30, ratio 4, range 90, knee 0 — gain at in, dB):
| in dBFS | Classic | Clean | Vocal | Guitar | Upward |
|---|---|---|---|---|---|
| −32 | 0.0 | −2.0 | −5.3 | −6.0 | 0.0 |
| −36 | −10.3 | −14.0 | −17.3 | −18.0 | 0.0 |
| −40 | −22.3 | −26.0 | −29.3 | −30.0 | 0.0 |
| −44 | −34.3 | −38.0 | −41.3 | −42.0 | 0.0 |
Classic = gentlest (onset right at thr); Clean/Vocal/Guitar progressively **steeper + onset higher** (Guitar
hardest/deepest). **Upward** = no downward gating; instead boosts above `threshold_upward` (upward expansion).

**Knee** (thr −30, ratio 4, range 90; gain at in, dB):
| in dBFS | knee0 | knee6 | knee12 | knee24 | knee30 |
|---|---|---|---|---|---|
| −36 | −10.3 | −2.4 | 0.0 | 0.0 | 0.0 |
| −40 | −22.3 | −15.9 | −7.8 | −1.4 | −0.2 |
| −44 | −34.3 | −29.3 | −22.2 | −10.4 | −7.9 |
Larger knee → softer, the expansion onset spreads symmetrically (~±15 dB at knee 30).

**Upward expansion** (Upward style, thr_up −12, R_up 2.5): unity for in ≤ −12; above → +6 @ −8, +12 @ −4,
+18 @ 0 dBFS = (R_up−1)·(in − thr_up).

**Ducking** (`ex_style`=Ducking, thr −30, range 60, ratio 10): inverted — ~0 dB at in ≤ −40, **−60 dB at
in ≥ −20** (attenuates loud).

**Timing** (Classic, thr −20, range 90/60, ratio 100; relationship set→measured, dB-domain smoother):
- Attack (open): see absolute-τ table below.
- Hold: holds the open plateau for ~the set time before release begins (50 ms, 150 ms confirmed).
- Release (close): time to reach floor scales with setting — to −40 dB: set 10 ms→24.5 ms, 30→34, 100→61,
  300→135, 1000→449 ms. Roughly proportional; release is dB-domain (equal-dB checkpoints ≈ equal spacing).

**Absolute attack τ** (RESOLVED — Classic, thr −20, range 90, ratio 100; SR **192 kHz**, amp-step drive that
isolates gate gain g(t), Hilbert envelope, τ = 10→90% rise; carriers 2 k & 6 kHz cross-checked. gate opens to
−0.00 dB at every setting):
| set (ms) | 0 | 0.1 | 0.3 | 0.5 | 0.7 | 1 | 2 | 3 | 5 | 10 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| τ 10→90% (ms) | ~0.01* | ~0.12 | 0.15 | 0.25 | 0.35 | 0.50 | 0.99 | 1.48 | 2.46 | 4.91 | 9.83 |
- Clean law: **τ(10→90%) ≈ 0.49 × (displayed attack ms)** across the resolvable range (≥~0.3 ms), monotonic.
- *Floor: at set ≤ ~0.05 ms the rise completes within the envelope-follower / step-edge resolution (~2–5 smp
  @192k ⇒ ~0.01–0.03 ms), so the smallest settings are **resolution-bounded, not a real gate delay** — set=0 is
  effectively instantaneous. The monotonic set→measured map (and the 0.49× slope above the floor) is the solid
  deliverable; sub-0.1 ms wobble is sub-carrier-cycle crossing jitter, not gate behaviour.

**Hysteresis** (open vs close threshold, slow 4-s ramp, release 1–5 ms so the gap is true hysteresis):
| style | open | close | gap |
|---|---|---|---|
| Classic | thr | thr −7 | **+7 dB** |
| Vocal | thr | thr −9 | +9 dB |
| Guitar | thr | thr −11 | +11 dB |
| Clean | thr | thr −10..14 | **+10..14 dB** (largest — most chatter-resistant) |
Gate **opens at threshold, closes ~7–14 dB below** → built-in hysteresis (style-dependent).

**Sidechain HP/LP** (detector-only; **requires `expert_mode=On`**): with HP@2 kHz, tones 50–1000 Hz are
removed from the detector → gate stays **closed (−90 dB)** though 6 dB over thr; 5k–15k still open it. LP@800 Hz
cuts highs from the detector. Audio path is **unaffected** (gate-open output spectrum = input). `side_chain_level`
shifts effective threshold (+12 dB SC opens a tone 3 dB *under* thr; −12 dB keeps it shut).

**External sidechain** (`side_chain_input_signal` = Side chain input) — **HOST-BLOCKED** (`needs DAW: separate SC
input`): pedalboard exposes ONE input bus, so the external-key detector source cannot be fed independently
(toggling the param with no separate bus leaves the main tone keying the gate → +0.00 dB either way; not
distinguishable here). Documented semantics (NOT fabricated): the external option **swaps only the detector
SOURCE bus** — the detector LAW is identical to the internal key already measured (`side_chain_level`
effective-thr shift + HP/LP @ `expert_mode`); the audio path is untouched. To measure external-SC curves,
re-run in a DAW that routes a separate sidechain input.

**Harmonics**: steady tone above thr → H2..H7 all **< −160 dBc** ⇒ pure gain, **no distortion**.

**Latency (reported PDC, host-compensated; measured group delay = 0)**:
| config | reported PDC @96k |
|---|---|
| base (no LA, OS off) | 0 smp |
| lookahead enabled (any value 0–10 ms) | **441 smp (4.59 ms) fixed** |
| OS 2x | 62 smp |
| OS 4x | 68 smp |

## To implement (CLEAN path for product — ES-L)
Downward gate/expander = **detector → dB-domain gain computer → asymmetric smoother → gain multiply**:
- **Gain computer**: `g_dB = 0` above thr; below thr `g_dB = (R−1)·(in_dB − thr)` clamped to `−range`; add a
  symmetric soft knee of width `knee` (quadratic blend over [thr−W/2, thr+W/2]). This is the textbook downward
  expander — **Giannoulis, Massberg & Reiss, "Digital Dynamic Range Compressor Design", JAES 60(6) 2012**
  (expander/gate static-curve + soft-knee equations) and **Zölzer, DAFX** (dynamics chapter).
- **Smoother**: branched (attack≠release) dB-domain one-pole with a **hold** stage; add **hysteresis** (separate
  open/close thresholds, ~7–14 dB gap) to stop chatter — see Zölzer DAFX gate topology.
- **Upward expander**: same computer mirrored above `thr_up` with slope `(R_up−1)` (own voicing for "Upward").
- **Ducking**: invert the comparator (attenuate above thr).
- **Sidechain key**: detector gain (`side_chain_level`) + **detector-only** HP/LP bandpass (Butterworth/SVF)
  for frequency-selective gating; keep it out of the audio path. Optional external SC bus.
- **Lookahead**: delay the audio by the look-ahead so the detector leads the transient; report fixed PDC.
- **Styles** = preset shapes of {knee softness, effective ratio onset, hysteresis gap, attack/release feel} —
  reproduce the measured per-style fingerprint tables above with own voicing. **No saturation** (pure gain).
- Build from these CLEAN tables + the cited public literature only. (Nothing here is REF — no disasm was done.)

---
## REF — static-disasm corroboration (TAINTED / reference-only — NEVER ship; see quarantine)
> Provenance: **REF (TAINTED)**. Ghidra/RTTI static decompile, EULA clean-room — quarantined under
> `private-research/_quarantine_disasm/Pro-G/`. Reference/education ONLY; the product path above stays
> 100% CLEAN. Coefficients/addresses live ONLY in quarantine (not reproduced here).
- A Ghidra pass (2026-06-22) **independently confirms** the CLEAN spec: same modular `DynamicsEngine::`
  class graph as Pro-L 2/Pro-C, a dB-domain gain computer (`20·log10` in / `exp2` out via system libm,
  **not** Pro-L 2's vectorized Cephes poly), the `(R−1)(in−thr)` law via a `powf(.,1/R)`, a Giannoulis
  soft-knee core/remainder split, and ~14 internal per-style waveshapes (soft atan/tanh ↔ hard piecewise).
- **Hysteresis mechanism** = a dual-threshold Schmitt-trigger state machine in the Capacitor/Detector
  smoother; the exact close-threshold offset is behind an unrecovered jumptable, so the 7–14 dB gap stays
  **CLEAN-measurement only**. Full REF: `_quarantine_disasm/Pro-G/architecture-findings.md`.

Provenance tags: **CLEAN** = black-box measurement (`prog_sysid.py`) / public DSP literature / own voicing
(product-safe). The single **REF** block above is static-disasm corroboration, quarantined and never shipped.
