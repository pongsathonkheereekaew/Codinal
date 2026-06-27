# AS-1 — Naturl Audio (Saturation / Harmonics — virtual-analog clipper)

| | |
|---|---|
| Vendor / ver | Naturl Audio · v0.1.0 · VST 3.8 (Fx\|Distortion) · no DRM |
| Type | Saturation / harmonic distortion — **virtual-analog circuit-modelled clipper** (selectable diode / transistor / differential), per-channel, with oversampling |
| Tech | JUCE 8 C++ shell (`AC1AudioProcessor`, copy-pasted name) → Rust `harmonics` crate via flat C FFI (24 `harmonics_*` exports); WebKit UI; uses an internal `circuit::breadboard` nodal solver |
| Binary | universal Mach-O bundle (x86_64+arm64), **not stripped** (~45k syms); dev crate names leak (`harmonics`, `harmonics_ffi`, `circuit`, `oversample::hybrid_fc`) |
| Provenance | param table, transfer curve, THD/harmonics, OS/aliasing, gain-staging = **CLEAN** (FFI black-box, `as1_ffi.py`). Engine = nodal circuit solver, diode = Shockley-type, struct field *order* = **REF** (r2; confirmed CLEAN by perturb-and-measure) |
| Measured on | AS-1 v0.1.0 · SR 48 kHz · `private-research/AS-1/Tools/as1_ffi.py` (ctypes direct-FFI, no host) · 2026-06-22 |
| Source | `private-research/AS-1/` — `Tools/as1_ffi.py`, `decomp/{NOTICE.md,ffi-surface.md,PsuDiodeClipper.disasm.txt}` |

## Signal chain (CLEAN behaviour; engine names REF)
```
inL,inR (f64, stereo, separate buffers)
  → ×drive (linear)
  → per channel: HybridOversampler ↑ (Off/2/4/8/16×)
       → CalibratedClipper engine  [Diode | Transistor | Differential]   ← circuit::breadboard solver
            (nonlinear device(s) + series INDUCTOR → reactive, frequency-dependent)
       → HybridOversampler ↓ (anti-alias FIR; adds latency)
  → ×output_trim (linear)
  → outL,outR
ref_level scales the clip CEILING (headroom into the device). unity = gain-comp toggle.
metering: 4 f64 (L/R level taps). NO internal mute — set_params commits immediately.
```
Key insight (CLEAN, confirmed): this is **not a memoryless waveshaper**. THD is strongly
**input-level dependent** (a real clip threshold) AND **frequency dependent** (low-freq H2 rises
from the inductor) — a virtual-analog clipper circuit, re-solved per sample.

## Clipper models — how they differ (CLEAN, 1 kHz, in≈0 dBFS, ref_level=−24 dBFS, 16× OS)
- **Diode** (`clipper_type=0`): **symmetric** soft-clip — uses `diode_model` for BOTH halves;
  `diode_neg` is **ignored**. Odd harmonics dominate (H3≫H5≫H7), H2 ≈ −90 dB. THD ramps 0→~40 %.
- **Differential** (`=2`): independent **pos/neg** diodes → identical to Diode when matched, but
  `diode_neg` ≠ `diode_model` makes it **asymmetric** (adds 2nd-harmonic; THD 12.9→14.6 % as neg varies).
- **Transistor** (`=1`): BJT pair clip — **more aggressive** (THD 18.9 % vs 12.9 %), stronger H3,
  `bjt_pair` selects device: power pairs (MJE15030) are more asymmetric (H2 −52 dB vs −90 dB).

### Diode-model fingerprints (Diode mode, symmetric, in 0 dBFS, THD%)
| model | THD | H3 | character |
|---|---|---|---|
| 1N34A Ge | 12.9 | −18 | softest (germanium) |
| BAV99W/BZX55C Zener | 15.3 | −16 | medium |
| 1N4148 Si | 15.4 | −16 | medium |
| Generic Si | 16.1 | −16 | harder |
| BAT41/BAT54 Schottky | 16.3 | −16 | hardest knee |

## Static transfer curve (CLEAN, Diode/1N34A, ref_level=−24 dBFS, drive=1, OS off)
Symmetric soft-clip: linear slope **0.9009 (−0.91 dB fixed insertion loss)**, smooth knee at |in|≈0.5,
saturating to **±0.676** ceiling. `ref_level` scales the ceiling (≈ +6 dB/step):
| ref_level | −24 | −18 | −12 | −6 | 0 dBFS |
|---|---|---|---|---|---|
| + ceiling | 0.676 | 1.334 | 2.645 | 5.250 | 7.207 |

slope is **0.9009 at every ref_level** — ref_level only moves the clip threshold (how hard you hit the device).

## Parameters (CLEAN — pedalboard + FFI; 10 params → 0x2d-byte struct)
| UI param | unit / range | struct off | type | notes |
|---|---|---|---|---|
| drive | dB −24..+24 (UI) | 0x00 | f64 | **linear gain in struct** (`g_dB=20·log10(field)−0.91`); JUCE converts dB→lin |
| output_trim | dB −24..+24 | 0x08 | f64 | linear gain, post-clip |
| reference_level | enum 0..4 | 0x10 | i32 | −24/−18/−12/−6/0 dBFS (=+4 dBu); sets clip **headroom/ceiling** |
| clipper_type | enum 0..2 | 0x14 | i32 | Diode / Transistor / Differential |
| diode_model | enum 0..6 | 0x18 | i32 | 7 diodes; +half (and both halves in Diode mode) |
| diode_neg | enum 0..6 | 0x1c | i32 | −half diode (**Differential only**; asymmetry) |
| bjt_pair (transistor) | enum 0..2 | 0x20 | i32 | 2N3904/06, 2N6517/20, MJE15030/31 (**Transistor only**) |
| (inductor, hidden) | enum 0..2 | 0x24 | i32 | internal fixed component; **no measured audio effect** |
| oversampling | enum 0..4 | 0x28 | i32 | Off/2×/4×/8×/16×; adds latency 0/560/976/1888/2156 @48k |
| unity | bool | 0x2c | u8 | gain-comp / asymmetry toggle (subtle: tiny H2 change) |
| bypass | bool | — | — | exposed by host; handled in JUCE shell, **not in the Rust struct** |

Enum option strings are self-reported by the binary (`harmonics_<kind>_count`/`_name`) and match pedalboard.

## Oversampling / aliasing (CLEAN)
OS FIR is a half-band anti-alias (latency above). At 7 kHz hard-clipped: OS=Off → images to −37 dB
(5 kHz, 11 kHz); 2×/4× reduce; **OS ≥ 8× drives all aliasing < −60 dB**. The clip itself runs inside
the OS region. (At 1 kHz, harmonics already exceed Nyquist by ~H24, so OS effect is inaudible there.)

## FFI contract (CLEAN — drives the real DSP, no host)
`ctypes.CDLL(binary)`; dlsym drops the leading `_`. **Struct-based** (one `set_params`, not per-param
setters like AC-1). AArch64 ABI. See `Tools/as1_ffi.py` (`Params` = 0x2d-byte `#[repr(C)]` struct).
- `harmonics_create(sample_rate:f64) -> *handle`   (SR in d0; builds L/R `CalibratedClipper`s)
- `harmonics_default_params() -> Params`            (**sret/x8** — ctypes `restype=Params`, no args)
- `harmonics_set_params(handle, *Params)`           — **commits immediately** (no separate un-mute)
- `harmonics_reset(handle)`                          — resets clippers, re-commits cached params
- `harmonics_set_sample_rate(handle, f64)`
- `harmonics_process_audio_stereo_f64(h, inL*, inR*, outL*, outR*, len)` — **separate in/out, f64, stereo**; first block = warmup (discard)
- `harmonics_get_latency_samples(h) -> i32`          ; `harmonics_get_metering_ptr(h, out[4]*)` (4 f64 L/R taps)
- enum: `harmonics_{clipper_type,diode,bjt_pair,inductor,oversample,ref_level}_{count() -> i32, name(i32) -> &str}` (&str = x0 ptr,x1 len)
- Flow: `create(SR) → set Params fields → set_params(p) → reset() → process(block0=warmup) → process(...)`
Full surface: `private-research/AS-1/decomp/ffi-surface.md`. Harness: `Tools/as1_ffi.py`.

## To implement (CLEAN path for product)
Saturation stage = **input-level-keyed soft clipper with selectable device curves + asymmetry + OS**:
- Per-device static curve from CLEAN measurement (transfer table above) — fit a smooth-knee soft-clip
  (e.g. parametric `tanh`/diode-shape) per model to match measured THD & H3/H5 ladder; literature:
  Yeh/Pakarinen virtual-analog diode-clipper, Zölzer DAFX (nonlinear processing), Kahles antiderivative AA.
- Reactive 1st-order pre-emphasis (the inductor) to reproduce the measured low-freq H2 rise (CLEAN).
- Symmetric (Diode) vs independent pos/neg shapers (Differential) for even-harmonic control.
- Oversample (poly-phase half-band) ≥ 8× to match the measured aliasing floor; gain-stage drive→ceiling.
- Build from CLEAN tables + public literature only. REF (circuit solver internals, exact Shockley
  Is/n/Vt constants) is reference-only — reproduce each curve black-box and null against `as1_ffi.py`.

---
Provenance tags: **CLEAN** = black-box measurement (`as1_ffi.py`) / public DSP / own voicing (product-safe).
**REF** = disasm-derived (struct field order, nodal-solver architecture — reference only, reproduce black-box before shipping).
