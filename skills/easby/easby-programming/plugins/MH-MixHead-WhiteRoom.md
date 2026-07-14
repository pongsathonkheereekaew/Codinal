# MB MixHead / MB White Room — Metric Halo (saturating clipper / reverb)

| | |
|---|---|
| Vendor / ver | Metric Halo (MH) · VST3 (MBMixHead, MBWhiteRoom) |
| Type | MixHead = drive + tape-speed-tilt + **output hard clipper** (OS); White Room = algorithmic reverb |
| Tech | C++ (`MBMixHeadPlugIn`, `MBWhiteRoomPlugIn`); PACE-iLok (Eden) |
| Binary | arm64; `__Pace_Eden.bundle`; ~14 syms → static **WALL** |
| Provenance | **CLEAN** (REAPER, iLok authorized). No REF (PACE). |
| Measured on | REAPER · 48 kHz · `mcdsp_sysid.py` · 2026-06-26 |
| Source | `private-research/McDSP_PACE/{Tools,work}` |

## MB MixHead — drive + hard clipper
PDC = **8 samples** (oversampling). DC-ramp transfer flattens to **±1.0 ceiling** at high Drive (hard clip,
matches "Enable Output Hard Clip"). Steady 1 kHz tone at high Drive → **4.6 % THD, pure H3 (odd, symmetric)**
= classic hard clipper (no even harmonics). True-peak: sample-peak = true-peak (−1.39 dB), so the OS clipper
controls inter-sample peaks at the clip ceiling.

### Parameters (CLEAN)
| param | unit | range / map |
|---|---|---|
| In Gain / Out Gain | dB | trim |
| Drive | dB | 0 … (feeds clip) |
| High Tape Speed | enum | 15 IPS / … (HF tilt voicing) |
| HF Adjust | dB | high-frequency shelf |
| Enable Output Hard Clip | bool | hard clip on/off |
| OS Ratio | enum | None / … (oversampling) |
| Invert Gain Link / AB Blend / Wet / Delta | — | |

**Why:** Drive into an oversampled symmetric hard clip = loud, transparent-ish "console head" loudness
without even-harmonic mud; tape-speed HF tilt adds the analog top-end voicing. Odd-only H3 = clean clipping,
not tube warmth.

## MB White Room — reverb
PDC = **0**. Param surface only (reverb tail = stochastic, not characterized by a single impulse beyond IR).

### Parameters (CLEAN)
| param | unit | range / map |
|---|---|---|
| Wet/Dry | % | 0 … 100 |
| Predelay | ms | **−30 … +130** (negative = pre-roll/align) |
| Length | % | 0 … 100 (decay scale) |
| AB Blend / Master Bypass / Wet / Delta | — | |

**Why:** minimal-control "one knob" room — Length scales decay, Predelay (incl. negative) places the room
forward/back. Designed for fast mastering/mix ambience, not surgical reverb design.

## To implement
- MixHead: oversampled symmetric hard clipper (odd harmonics) + HF-tilt shelf + tape-speed voicing + drive.
- White Room: algorithmic room reverb (predelay incl. negative align, decay scale). Both CLEAN-only; MH code PACE-walled.

## Open questions
- White Room reverb topology (FDN? convolution?) and exact decay times vs Length (IR capture needed).
- MixHead exact OS ratio options and clip curve (hard vs soft-knee at threshold).

---
**CLEAN** = REAPER black-box of a licensed plugin. **No REF** (PACE wall).
