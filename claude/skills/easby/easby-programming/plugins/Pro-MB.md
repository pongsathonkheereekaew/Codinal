# Pro-MB — FabFilter (Multiband dynamics — up/down compressor + expander, dynamic EQ-style)

| | |
|---|---|
| Vendor / ver | FabFilter Pro-MB · VST3 (FabFilter) · no DRM |
| Type | **Multiband dynamics** — up to 6 bands, each an independent up/down **compressor + expander** (dynamic, EQ-style); allpass-summed crossovers; Linear / Dynamic / Minimum phase |
| Tech | VST3 (FabFilter), C++; Metal UI (`default.metallib`), Cocoa license dialog. Stripped — **black-box only** |
| Binary | universal Mach-O (x86_64+arm64), **STRIPPED** (6 exported syms; 449 imported = CoreFoundation/AppKit/AudioToolbox/libz), **NO PACE/iLok/DRM**. ~3.2 MB |
| Provenance | CLEAN body = pedalboard black-box measurement only. A static Ghidra REF pass exists for understanding (quarantined; see REF section at end) — **never cited in the CLEAN body or product**. Firewall enforced |
| Measured on | Pro-MB · SR 44.1/48/96 kHz · `private-research/Pro-MB/Tools/promb_sysid.py` (pedalboard 0.9.17, macOS arm64) · 2026-06-22 |
| Source | `private-research/Pro-MB/` — `Tools/promb_sysid.py`, `docs/{sysid-notes.md, range_model.json}` |

## Signal chain (CLEAN behaviour)
```
in (stereo) → input_level / input_pan
  → split into up to 6 BANDS (each band = independent band-pass region defined by its OWN
        low_crossover + high_crossover, with selectable slope 6..48 dB/oct; bands are
        ALLPASS-SUMMED → flat reconstruction ±0.10 dB regardless of split/slope)
     each band, in parallel:
        band-pass region → DYNAMICS (clean envelope-controlled gain, NO waveshaping)
            detector: per-band side-chain (Band-internal or Free filtered; Plug-in or External input;
                      stereo-link Mid/Side, link %)
            curve: dynamics_mode {Compression|Expansion} × sign(range) → up/down × above/below thr
            time:  attack/release (program-dependent %), per-band lookahead (≤20 ms)
        → band level (makeup ±30) → band pan (Mid/Side) → solo/mute
  → SUM bands → output_level / output_pan → mix (dry/wet 0..200 %)
processing_mode {Linear | Dynamic | Minimum} sets crossover PHASE (not magnitude).
oversampling {Off | 2× | 4×}. analyzer = metering only.
```
Key insight (CLEAN): the dynamics is a **clean VCA gain-ride** — 1 kHz at −3 dBFS with instant
attack and 100:1 produces H2..H5 all **< −160 dBc** (no distortion). The four processing quadrants
(up/down × comp/expand) are all reached by ONE control pair: `dynamics_mode` + signed `range`.

## Per-stage formula (all CLEAN — measured)
- **Crossover** (CLEAN): allpass-summed filterbank. Soloed band rolloff = labelled slope
  (12→−11, 24→−24, 48→−48 dB/oct; −96 dB at 2 octaves for 48 = LR-cascade). Magnitude flat through
  crossover in all 3 modes; **phase at crossover: Linear 0° · Dynamic 0° · Minimum 180°**.
- **Dynamics curve** (CLEAN — the UNIFIED `range` model): `|range|` = max gain change (depth limit),
  `ratio` = slope of the gain-changing segment from threshold (offset by `knee`) toward the `|range|` floor:

  | dynamics_mode | range sign | acts on | direction |
  |---|---|---|---|
  | Compression | + | **below** threshold | **UP boost** (upward compression) |
  | Compression | 0 | — | transparent |
  | Compression | − | **above** threshold | **DOWN cut** (classic downward compression) |
  | Expansion | + | **above** threshold | **UP boost** (upward expansion) |
  | Expansion | 0 | — | transparent |
  | Expansion | − | **below** threshold | **DOWN cut** (downward expansion / gate) |

  (COMP/− ≡ EXP/+ act above thr; COMP/+ ≡ EXP/− act below thr. `range`=0 → fully transparent.)
- **Detector timing** (CLEAN): program-dependent, % → time; attack ~0.5 ms (≤20 %) rising to ~166 ms
  (100 %), release ~77 ms → >1 s. t63 table in CLEAN measurements. The % control sets a *base* time
  that the detector then **adapts to the program** (overshoot-dependent attack, GR-depth-dependent
  release — adaptation law measured below).

## Parameters (CLEAN — pedalboard; 156 total = 24 global + 6 bands × 22)
**Per band** `band_N_…`, N=1..6 (each band identical):
| param | unit | range | notes |
|---|---|---|---|
| state | enum | Disabled / Enabled / **Unused** | default Unused → band off; set Enabled to engage |
| low_crossover | Hz | 30..30000 | log: `f=30·1000^raw`; band lower edge |
| low_slope | dB/oct | 6/9/12/18/24/30/36/42/48 | default 24 (raw .5) |
| high_crossover | Hz | 30..30000 | band upper edge |
| high_slope | dB/oct | 6..48 | default 24 |
| dynamics_mode | enum | Compression / Expansion | + range sign → quadrant |
| threshold | dB | −90..0 | linear in dB |
| range | dB | **−30..+30 (signed)** | max gain change; **0 = transparent**; sign picks direction |
| ratio | :1 | 1 / 1.25 / 2 / 2.75 / 4 / 6 / 8 / 10 / 100 | slope of gain-change segment (default 4:1) |
| attack | % | 0..100 | program-dependent; ~0.5..166 ms |
| release | % | 0..100 | ~77 ms..>1 s |
| knee | dB | 0..48 | 0 = hard; softens corner up to ~12 dB pre-thr |
| lookahead | ms | 0..20 | within global reserve (no extra PDC) |
| level | dB | −30..+30 | per-band makeup |
| pan | Mid/Side | −inf..0 each | per-band M/S balance |
| side_chain_filtering | enum | Band / Free | detector source: band-internal vs free filter |
| side_chain_low_frequency | Hz | 30..30000 | free-filter SC HP |
| side_chain_high_frequency | Hz | 30..30000 | free-filter SC LP |
| side_chain_input | enum | Plug-in Input / External Input | external SC |
| stereo_link | % | 0..100 | detector L/R link (100 % = Mid-only) |
| stereo_link_mode | enum | Mid / Side | |
| solo_mute_state | enum | Normal / Solo / Mute / Solo(Mute) | |

**Global** (24): audition_side_chain (Off/Band 1..6), mix (0..200 %), input_level/output_level
(−inf..+36 dB), input_pan/output_pan, bypass, host_bypass, **processing_mode** (Linear/Dynamic/Minimum
Phase), **oversampling** (Off/2×/4×), **lookahead_enabled** (On/Off), expert_mode, midi_state,
display_range, analyzer (Off/Pre/Post/Pre+Post), analyzer_resolution/speed/tilt/freeze/side_chain,
internal/midi_cc/pitch_bend/channel_pressure (MIDI-learn stubs).

Max **6 bands** (no band_7; audition lists Band 1..6; all 6 solo to a passband).

## CLEAN measurements
**Latency** `reported_latency_samples` (3-band tile, LR24, lookahead On):
| SR | Linear (Off/2×/4×) | Dynamic | Minimum |
|---|---|---|---|
| 44100 | 3954 / 4016 / 4022 | 882 / 944 / 950 | 882 / 944 / 950 |
| 48000 | 4032 / 4066 / 4072 | 960 / 994 / 1000 | 960 / 994 / 1000 |
| 96000 | 7040 / 7050 / 7056 | 1920 / 1930 / 1936 | 1920 / 1930 / 1936 |
- `lookahead_enabled` reserves a fixed ~20 ms (960@48k / 1920@96k) regardless of per-band amount; Off → 0.
- OS anti-image FIR: +34/+40 @48k (2×/4×), +10/+16 @96k. Linear-phase adds symmetric FIR +3072 @48k /
  +5120 @96k (pre-ring impulse, correlation +1.000 → true zero-phase). Dynamic ≡ Minimum in latency,
  differ only in crossover phase (0° vs 180°).

**Attack/release** t63 (COMP 100:1, range −30, 2 kHz burst, fixed −3 dBFS over a −50 dBFS floor):
| % | 0 | 20 | 40 | 50 | 60 | 80 | 100 |
|---|---|---|---|---|---|---|---|
| attack | 0.5 | 0.5 | 7.5 | 17.5 | 36 | 104 | 166 ms |
| release | 77 | 124 | 235 | — | 431 | >500 | >1000 ms |

**Program-dependent adaptation law** (CLEAN — `progdep` probe; COMP 100:1 range −30, thr −30, 1 kHz
burst, control % held FIXED while the input transient depth is swept). The % is a *base* setting; the
detector then re-times itself to the program in two opposite directions:
- **Attack adapts to overshoot** — deeper transient over threshold → **faster** attack (bigger hits
  grab harder). t63 vs (peak − thr), at fixed attack %:

  | over thr → | +12 dB | +18 dB | +24 dB | +30 dB |
  |---|---|---|---|---|
  | attack 40 % | 15.5 | 10.5 | 9.0 | 8.5 ms |
  | attack 50 % | 35.5 | 25.0 | 21.5 | 19.5 ms |
  | attack 60 % | 65.5 | 49.5 | 43.0 | 40.0 ms |
  | attack 80 % | 140 | 127 | 122 | 118.5 ms |

  (~0.6× faster from +12→+30 dB overshoot; saturates at large overshoot → effective time-constant
  scales inversely with how far the signal is over threshold.)
- **Release adapts to GR depth** — more gain reduction applied → **slower** release (auto-release /
  hold: deep cuts recover gently, light cuts let go quickly). t63 vs gain reduction, at fixed release %:

  | GR reached → | −2 dB | −8 dB | −14 dB | −20 dB |
  |---|---|---|---|---|
  | release 30 % | 180 | 181 | 186 | 193 ms |
  | release 50 % | 268 | 277 | 299 | 330 ms |
  | release 70 % | 438 | 474 | 542 | 624 ms |

  (~1.4× slower at deep GR for high release %; near-flat at low release %.)
  Both effects are monotonic and frequency-consistent (the overshoot-dependence magnitude shrinks toward
  HF where one period ≪ the analysis window). To implement: drive the envelope time-constant from the
  instantaneous over-threshold amount (attack) and the current GR (release), not a fixed τ.

**Crossover** (solo low band, 1 kHz split): slope tracks label (12/24/48 → −11/−24/−48 dB/oct);
two bands sum flat ±0.10 dB at any split → allpass-summed.

**Harmonics**: clean gain-ride, H2..H5 < −160 dBc (no waveshaping); OS adds no aliasing at clean settings.

**External side-chain** (`extsc` probe) — **HOST-BLOCKED: needs DAW**. The per-band detector *law* is
fully measured CLEAN (source = `side_chain_filtering` Band/Free + free HP/LP 30..30000 Hz; stereo-link
0..100 % with Mid/Side mode — see param table). `side_chain_input` = {Plug-in Input | External Input}
only **swaps the detector's source bus** to the host aux input; it does not change the detector math.
pedalboard exposes a single main I/O bus, so the aux bus cannot be fed here → the External-Input
*routing/level/sum/link* behaviour is un-measurable in this harness. Semantics are documented; confirm
in a DAW with sidechain routing. (Internal `Plug-in Input` SC + free-filter + stereo-link are CLEAN.)

## To implement (CLEAN path for product — ES-L)
Multiband up/down dynamics from CLEAN measurement + public literature only:
- **Crossover**: allpass-complementary / Linkwitz-Riley filterbank, selectable order (2nd..8th → 12..48
  dB/oct), magnitude-flat reconstruction. Offer 3 phase modes: minimum-phase IIR LR (180° at xover,
  low latency), **phase-corrected ("dynamic")** = LR + allpass to flatten phase through crossover at low
  latency, and **linear-phase FIR** (zero-phase, pre-ring, latency ≈ FIR half-length). Literature:
  Linkwitz "Active Crossover Networks" (JAES 1976), Lipshitz–Vanderkooy allpass crossovers, Zölzer DAFX.
- **Per-band detector + static curve**: feed-forward, log-domain. Implement the unified gain law
  `g(L) = f(L − threshold, ratio, knee, signed range)` covering all 4 quadrants (the CLEAN table above):
  smooth-knee soft-knee compressor/expander with a signed depth limit. Standard model: Giannoulis,
  Massberg & Reiss, *Digital Dynamic Range Compressor Design — A Tutorial and Analysis*, JAES 60(6) 2012
  (gain-computer + knee + ratio formulation; extend to upward + below-threshold direction).
- **Envelope**: branching/smooth-decoupled peak detector with program-dependent attack/release. Map a
  0..100 % control to the measured *base* t63 curves (attack ~0.5..166 ms, release ~77 ms..>1 s), THEN
  apply the measured adaptation law: shorten the attack τ as the instantaneous over-threshold amount
  grows (faster on bigger transients) and lengthen the release τ as the current GR deepens (auto-release
  /hold). See the "program-dependent adaptation law" tables above. Literature: Giannoulis et al. 2012
  (smoothed branching detector), Zölzer DAFX ch. dynamics.
- **Clean VCA** — apply gain without saturation (the measured H2..H5 < −160 dBc); add oversampling
  only for any optional nonlinear stage. Per-band makeup, M/S pan, side-chain (band-internal vs free
  HP/LP filter, external input), stereo-link %.
- Build from CLEAN tables + public DSP only. No REF (binary is stripped; nothing was disassembled).
  Re-measure/null against `Tools/promb_sysid.py` (`rangemodel`, `static`, `timing`, `crossovers`, `latency`).

---
Provenance tags: **CLEAN** = black-box measurement (`promb_sysid.py`) / public DSP literature / own
voicing (product-safe). The CLEAN body above carries NO coefficients or code from disassembly.

## REF (reference-only — DO NOT ship / cite from product, ES-L, or any BuildSpec)
A static Ghidra pass (2026-06-22) was performed for understanding only; artifacts are quarantined at
`private-research/_quarantine_disasm/Pro-MB/` (architecture-findings.md + decomp/ghidra/). REF confirms
the two crown jewels: (1) **crossover** = TPT/zero-delay-feedback state-variable biquads, complementary
LP/HP **plus allpass-recombination terms only in Dynamic Phase** (Minimum Phase omits them; Linear Phase
uses a separate Convolver FIR), with a Butterworth/LR (Q=1/√2, 0.5) damping ladder + an AGM/Landen
frequency warp for continuously-variable slope; (2) the **unified per-band gain computer** = one
feed-forward log-domain transfer curve over `{Compress,Expand}×sign(Range)` (the signed-Range 4-quadrant
model), quadratic soft-knee, ratio-as-slope, Range as a soft-knee'd max-gain clamp, via a shared dB
engine (`20·log10f` / `10^(x/20)`). This matches the CLEAN measurements — re-derive everything from
`promb_sysid.py` + public DSP theory before any product use. None of the REF detail enters the CLEAN
sections above or product code.
