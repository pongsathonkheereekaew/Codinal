# Pro-Q 4 — FabFilter (Parametric EQ — dynamic, multi-phase, per-band M/S)

| | |
|---|---|
| Vendor / ver | FabFilter · Pro-Q 4 v4.12 · VST3 (Fx) · no DRM |
| Type | **Parametric EQ (dynamic, linear/natural/zero-phase, per-band M/S)** — 24 bands, 10 shapes, continuous slope, per-band dynamics + side-chain, per-band stereo placement, analog "character" saturation |
| Tech | **VST3 (FabFilter), stripped, black-box only.** Universal Mach-O bundle (x86_64+arm64), 6 ext syms (`VSTPluginMain`/`GetPluginFactory`/`bundleEntry`…), **no FFI surface**, no PACE/iLok. Links libz + system frameworks (Cocoa/Metal/AudioToolbox). UI = native Cocoa/Metal. |
| Binary | stripped (`nm -U` = 6), no leaked build paths; static disasm NOT performed (firewall: black-box only) |
| Provenance | **Product-facing content here is CLEAN** (black-box host measurement via `proq4_sysid.py`). A Ghidra REF pass (2026-06-22) corroborates the design classification but is quarantined under `_quarantine_disasm/Pro-Q4/` (reference-only; see REF section at bottom) — no coefficients reproduced in this file. |
| Measured on | Pro-Q 4 v4.12 · SR 96 kHz (cramping @44.1k; latency cross-checked 44.1/48/192k) · `private-research/Pro-Q4/Tools/proq4_sysid.py` (pedalboard 0.9.17) · 2026-06-22 (incl. spectral/dyntime/cramp/speakers resolution pass) |
| Source | `private-research/Pro-Q4/` — `Tools/proq4_sysid.py`, `docs/measurements.md` |

## Signal chain (CLEAN behaviour)
```
inL,inR (stereo; up to surround via per-band `speakers`)
  → [global gain_scale ×]  (scales every band's gain in dB; 0..200%)
  → 24 parallel/cascaded EQ bands, each:
        pick channel axis  {Stereo | Left | Right | Mid | Side}   (M/S matrix per band)
          → biquad/high-order filter  {Bell, Low/High Shelf, Tilt Shelf, Flat Tilt,
                                        Low/High Cut (0–96 dB/oct or Brickwall),
                                        Notch, Band Pass, All Pass}
          → optional per-band DYNAMICS: detector (band SC | free SC filter | external SC)
                → gain rides 0..dynamic_range dB across threshold (down if range<0, up if >0)
                → if spectral_enabled: dynamic gain is computed PER FFT-BIN (surgical),
                  density=bin resolution, tilt=HF-weighted; atk/rel adaptive only in Auto
        re-encode channel axis
  → [global: output_level, output_pan (L/R or M/S), invert_phase, auto_gain]
  → [character nonlinearity: Clean=bypass | Subtle≈transparent | Warm=2nd-harmonic soft-sat]
  → outL,outR
Phase engine selects the whole filter realization:
  Zero Latency  = min-phase IIR (0 smp, CRAMPS near Nyquist)  Natural Phase = analog-matched min-phase (320 smp fixed, uncramped)
  Linear Phase  = symmetric FIR (latency ∝ SR, set by processing_resolution Low..Maximum)
```
No FFI: drive only through the host (pedalboard). First 1–2 process blocks = warmup (discard).

## Per-stage formula (all CLEAN — black-box)
- **Bell** (CLEAN): peak lands exactly on `frequency`, peak gain = `gain`. Measured −3 dB bandwidth is
  **wider than RBJ**; empirical **BW_oct ≈ 2.04 / Q** for Q≳1 (Q·BW → ~2.0). RBJ cookbook biquad is the
  starting point but Q→BW must be matched to the measured table, not the textbook constant.
- **Proportional-Q** (CLEAN): with Q fixed, the −3 dB bandwidth **narrows as |gain| rises**
  (Q=2: 1.00 oct @+6 → 0.26 oct @+24 dB) — analog variable-Q character, not constant-Q.
- **Shelves** (CLEAN): half-gain (−3 dB rel) at fc; reach full `gain` in the band. Tilt Shelf = symmetric ±tilt
  pivoting at fc; Flat Tilt = gentler broadband spectral tilt.
- **Cuts** (CLEAN): −3 dB at fc; asymptotic roll-off tracks the set slope (6→−5.3, 12→−11.4, 24→−23.7,
  48→−48.2 dB/oct measured). Slope is continuous 0–96 dB/oct; **Brickwall** = near-vertical cliff at fc.
- **Notch/BandPass/AllPass** (CLEAN): notch deep null at fc; band-pass −3 dB ±skirts; all-pass flat magnitude (phase-only).
- **Character = Warm** (CLEAN): memoryless **asymmetric even-order soft-saturation** — H2 dominates
  (−48 dBc @in 0.1 → −28 dBc @in 0.95, monotonic with level), H3..H7 ≤ −120 dBc. Clean = bypass; Subtle ≈ dither floor.

## Parameters (CLEAN — pedalboard; 605 params = 24 bands × 24 + 29 global)
**Per-band (×24)** — fields `band_<N>_<name>`:
| field | unit / range | notes |
|---|---|---|
| used | enum Unused/Used | band slot active |
| enabled | bool | bypass this band |
| frequency | Hz 10..30000 | |
| gain | dB −30..+30 (0.06 step) | bell/shelf/tilt gain |
| q | 0.025..40 | shape param; effective BW≈2.04/Q (gain-dependent, proportional-Q) |
| shape | enum 10 | Bell, Low Shelf, Low Cut, High Shelf, High Cut, Notch, Band Pass, Tilt Shelf, Flat Tilt, All Pass |
| slope | 0–96 dB/oct (0.1 step) + Brickwall | cut steepness; 663 values ≈ continuous |
| stereo_placement | enum 5 | Left, Right, Stereo, Mid, Side (per-band M/S) |
| speakers | enum 15 | per-band surround routing. On 2-ch host only `All Speakers`/`L/R (Front)` route (+gain L&R); Center/LFE/Surround groups inert. **HOST-BLOCKED: needs >stereo DAW** (full enum below) |
| dynamic_range | dB −30..+30 | **<0 downward, >0 upward** dynamic EQ depth |
| dynamics_enabled | enum Disabled/Enabled | |
| dynamics_auto | enum Auto/Manual | auto vs manual threshold |
| threshold | dB string −90..0 | manual dynamics threshold |
| attack / release | % 0..100 | dynamics time-constants. **ACTIVE only in Dynamics Auto**; INERT in Manual (fixed ~4 ms atk / ~150 ms rel). Auto map below |
| external_side_chain | bool | use external SC bus |
| side_chain_filtering | enum Band/Free | SC follows band, or free SC filter |
| side_chain_low_frequency / _high_frequency | Hz 10..20000 | free SC band edges |
| side_chain_audition | bool | listen to SC |
| spectral_enabled | bool | **Spectral Dynamics** = per-FFT-bin dynamic gain (vs whole-band). ON → ducks/boosts ONLY hot bins |
| spectral_density | % 0..100 | per-bin GR **resolution**: higher = sharper/narrower bin selectivity |
| spectral_tilt | bool | **frequency bias** of per-bin GR: ON pivots near fc → less action below, more above (HF-emphasized) |
| solo | bool | solo this band |

**Global (29)** — key ones:
| param | unit / range | notes |
|---|---|---|
| processing_mode | Zero Latency / Natural Phase / Linear Phase | filter realization (see latency table) |
| processing_resolution | Low/Medium/High/Very High/Maximum | only affects Linear-Phase FIR length/latency |
| character | Clean / Subtle / Warm | harmonic saturation (Warm = 2nd-harm) |
| gain_scale | % 0..200 | linear multiplier on ALL band gains (dB) |
| output_level | dB −inf..+36 | output trim |
| output_pan / output_pan_mode | — / L-R or M/S | output pan |
| output_invert_phase | Normal/Inverted | |
| auto_gain | bool | |
| solo_gain | −20..+20 | |
| analyzer_* (10), spectrum_grab, display_range, receive_midi, bypass, host_bypass | — | UI/metering/MIDI, no DSP effect on audio path |

## CLEAN measurements (key tables — full in `docs/measurements.md`)
- **Q→BW (−3 dB), +6 dB bell:** Q 0.5/1/2/4/8/40 → 3.31/1.90/1.00/0.51/0.255/0.053 oct. Fit **BW≈2.04/Q** (Q≳1).
- **Cut slope:** set 6/12/24/48 dB/oct → measured −5.3/−11.4/−23.7/−48.2; Brickwall = vertical cliff.
- **Phase-mode latency @96k:** Zero=0, Natural=320 (fixed all SR), Linear=3072/5120/9216/17408/66560 smp
  (Low→Maximum). Natural fixed-delay (SR-independent); Linear FIR latency ∝ SR (~107 ms group delay @ Medium).
- **Dynamic EQ static:** gain → full `dynamic_range` above threshold, 0 below; range sign sets up/down.
- **M/S:** Left/Right isolate one channel; Mid/Side operate on M=(L+R)/2 or S=(L−R)/2 then re-encode (true matrix).
- **Warm character:** H2 −48→−28 dBc with level; odd harmonics ≤ −120 dBc → asymmetric soft-sat.

## CLEAN measurements — resolved open questions (2026-06-22)
- **Spectral Dynamics** (`spectral_enabled`): turns a dynamic band from whole-band into a **per-FFT-bin**
  dynamic processor. Decisive test (strong 1 kHz tone on a quiet noise bed, dynamic AUTO, range −18):
  spectral OFF ducks the **entire bell** (−8.7 @700 … −17 @1k … −10.7 @1300 Hz); spectral ON ducks **only the
  hot bin** (~0 @700/1100, −16 @1k). `spectral_density` = per-bin **resolution** (Q0.5 wide bell: dens=10 ducks a
  wider skirt −12 @950→0 by 800; dens=100 tighter/sharper at the exact bin) — density, not the band Q, sets the
  GR width. `spectral_tilt` ON = **frequency bias** of the per-bin GR pivoting near fc: tones below fc ducked
  ~1.4 dB LESS (@300 Hz), tones above fc ~0.7 dB MORE (@3k) → HF-emphasized dynamics. Sign carries over:
  range>0 = surgical **upward** (boosts only the hot bin, +12 @1k, ~0 elsewhere).
- **Dynamic-EQ attack/release %→ms:** the % controls are **ACTIVE only in `Dynamics Auto`**; in `Dynamics
  Manual` the band uses a **fixed program-dependent envelope** (~4 ms attack, ~150 ms release t63) and the %
  sliders are **INERT** (0% and 100% give identical step responses). Auto-mode set→ms (t63 of band GR, 1 kHz Q2,
  range −18; attack step −30→−6, release −70→−6 dBFS):
  | set % | 0 | 20 | 40 | 50 | 60 | 70 | 80 | 90 | 100 |
  |---|---|---|---|---|---|---|---|---|---|
  | attack t63 ms | (≤4*) | (≤4*) | (≤4*) | ~5 | 5.0 | 8.5 | 14.0 | 21.7 | 32.6 |
  | release t63 ms | 120 | 148 | 243 | 304 | 365 | 426 | 554 | 694 | 834 |
  (*attack ≤50% sits at the ~4 ms demod-window floor; the resolved monotonic range is set≥50% → 5–33 ms. Release
  is monotonic across the whole range, ~120 ms→834 ms; roughly exponential map, t90 ≈ 2×t63.)
- **HF cramping @ 44.1 kHz, Zero-Latency vs Natural Phase** (15 kHz Bell +6 Q1): **Zero-Latency cramps**, Natural
  doesn't. Zero peak pulled DOWN to **14981 Hz** (off-target) with a near-Nyquist lift (**+5.17 dB @21k** vs
  Natural **+4.81**, Δ +0.35 dB; +0.19 @20k); Natural keeps the peak on fc (15000.6 Hz) and rolls off correctly.
  Both still hit exactly +6.00 dB @fc. Contrast @96k (Nyquist=48k far away): Zero/Natural agree within 0.06 dB
  at 15k and ±0.14 dB out to 30k → cramping is a SR/Nyquist effect (worst at low SR), and Natural Phase is the
  analog-matched (uncramped) realization. Magnitude Δ at 44.1k is small (<0.4 dB) but **asymmetric** (HF-only),
  the signature of digital bilinear cramping.
- **Surround `speakers` routing — HOST-BLOCKED (needs >stereo DAW/UI):** 15 channel-group routings (enum below).
  On pedalboard's 2-ch stereo host only `All Speakers` and `L/R (Front)` apply gain (both channels); `Center`,
  `LFE`, `Ls/Rs (Surround)`, etc. are **inert** (0 dB) — the band targets channels the host doesn't expose.
  `speakers` enum: All Speakers · All (excl. LFE) · LFE · Center · L/R (Front) · Lc/Rc (Front Center) ·
  Lss/Rss (Surround Side) · Ls/Rs (Surround) · Lsr/Rsr (Surround Rear) · Cs or S (Center Surround) ·
  Lts/Rts (Top Surround) · L/C/R (Front + Center) · Lw/Rw (Wide) · Ltf/Rtf (Top Surround Front) ·
  Ltr/Rtr (Top Surround Rear). **EQ-Sketch** (draw a curve), **collision/instrument intelligence**, and
  **per-band soloing of surround groups** are **UI gestures** that write ordinary band params (freq/gain/Q/shape)
  or need a multichannel host — no separate DSP path; **HOST-BLOCKED: needs DAW/UI**, semantics documented only.

## FFI contract
None. Classic VST3 (`VSTPluginMain`/`GetPluginFactory` only); stripped; no clean C ABI. Host-driven measurement only.

## To implement (CLEAN path for product, ES-L)
Parametric EQ engine from CLEAN measurements + public DSP literature only (no disasm was used):
- **Biquad bands** (bell/shelf/notch/BP/AP): RBJ/**Bristow-Johnson EQ cookbook** as the kernel, but map the
  Q knob to the **measured** BW≈2.04/Q (not the textbook constant) and add **proportional-Q** (let effective Q
  rise with |gain|) to match the gain-dependent bandwidth table.
- **High-order cuts (to 96 dB/oct + Brickwall):** cascade/Butterworth-style sections or **Orfanidis high-order
  shelving/Butterworth** design; continuous slope = interpolate filter order. Brickwall = very-high-order or FIR.
- **Phase modes:** Zero Latency = direct-form min-phase IIR (accept HF cramping or bilinear pre-warp);
  **Natural Phase** = analog-prototype-matched min-phase (e.g. matched-Z / impulse-invariant or higher-order
  fit) with a small fixed delay; **Linear Phase** = symmetric **FIR EQ** (frequency-sampling / windowed design,
  latency = (N−1)/2, tap count ∝ SR; expose a resolution control).
- **Dynamic EQ:** per-band envelope detector (band-pass keyed or free SC), gain interpolates 0..range across
  threshold (down if range<0, up if >0) — Zölzer DAFX dynamics + per-band gain modulation. **Two timing modes:**
  Manual = fixed program-dependent envelope (~4 ms atk / ~150 ms rel, atk/rel % ignored); Auto = adaptive
  envelope where the % maps to time (measured Auto: attack 5–33 ms over 50–100%, release ~120–834 ms t63 over
  0–100%, ≈exponential). **Spectral Dynamics** = move the detector+gain to the **FFT domain** (per-bin GR):
  STFT/overlap-add, each bin gets its own threshold/GR; `density` sets bin resolution (frame size / smoothing),
  `tilt` applies an HF-emphasis weighting to the per-bin GR (pivot at fc) — phase-vocoder / spectral-processing
  literature; null against `proq4_sysid.py spectral`.
- **Per-band M/S:** encode L/R→M/S, process the selected axis, decode back.
- **Warm character:** asymmetric even-order soft-saturation (2nd-harmonic), level-dependent — fit to the
  measured H2 ladder; oversample to control aliasing (Zölzer DAFX nonlinear; Kahles antiderivative AA).
- Literature: **RBJ/Bristow-Johnson Audio-EQ Cookbook**, **Orfanidis** (high-order digital parametric/shelving
  EQ, *Introduction to Signal Processing* & AES "High-Order Digital Parametric Equalizer Design"),
  **linear-phase FIR EQ** (frequency-sampling), **Zölzer DAFX** (filters, dynamics, nonlinear).
- All facts above are CLEAN (measured) — null any implementation against `proq4_sysid.py` to confirm.

## Open questions
All four prior open questions RESOLVED 2026-06-22 (Spectral Dynamics, dynamic atk/rel %→ms, 44.1 kHz cramping,
speakers enum) — see "resolved open questions" above. Remaining HOST-BLOCKED (no DSP recoverable without a
multichannel/UI host): actual surround routing per group, EQ-Sketch draw gesture, collision/instrument
intelligence, external side-chain bus content. These write/operate on the already-documented band params; no
hidden DSP path. Nothing else open on the audio path.

## REF corroboration (quarantine only — `private-research/_quarantine_disasm/Pro-Q4/`, do NOT cite in product)
Ghidra static pass (2026-06-22) **confirms the CLEAN classification, adds nothing shippable.** Stripped but
C++ ABI typenames survive: class graph recovered (`AnalogFilterPrototype::BiquadPrototype`,
`EQFilter::CoefficientCalculation`, `BandCompander`/`Detector{KneeStyle}`, `Convolver`+`FFT*`+
`FrequencyResponseKernel`). The biquad designer **prewarps `tan(ω/2)` and matches a sampled analog `|H|²`
(vtable callback) at center/edges/Nyquist** → **Orfanidis-class analog-matched, NOT RBJ cookbook**; cuts/
high-order = Butterworth/Chebyshev/elliptic analog prototypes + bilinear cascade; lin-phase = partitioned-FFT
FIR from the magnitude grid (IFFT); proportional-Q floor matches measured BW≈2.04/Q. Coefficients/addresses
stay REF — re-derive from measurement (RBJ/Orfanidis/Butterworth literature) before any product use.

---
Provenance tags: **CLEAN** = black-box measurement (`proq4_sysid.py`) / public DSP literature / own voicing — product-safe.
**REF** = disasm-derived — quarantined under `_quarantine_disasm/Pro-Q4/` (Ghidra pass 2026-06-22); reference-only, never enters product/ES-L/BuildSpec. No coefficients reproduced in this CLEAN file.
