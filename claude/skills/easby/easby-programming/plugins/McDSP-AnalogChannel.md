# Analog Channel AC101 / AC202 — McDSP (Console / Tape channel)

| | |
|---|---|
| Vendor / ver | McDSP · VST3 |
| Type | AC101 = analog **console-channel** (drive + comp-coupled saturation); AC202 = analog **tape** machine |
| Tech | C++; PACE-iLok (Eden) all formats |
| Binary | arm64; `__Pace_Eden.bundle`; ~6 syms → static **WALL** |
| Provenance | **CLEAN** (REAPER, iLok authorized). No REF (PACE). |
| Measured on | REAPER · 48 kHz · `mcdsp_sysid.py` · 2026-06-26 |
| Source | `private-research/McDSP_PACE/{Tools,work}` |

## Key CLEAN finding — saturation is DYNAMIC / clean at steady state
At a steady **1 kHz tone, both at −12 and −1 dBFS, with Drive/Input at MAX**, AC101 and AC202 produce
**~0 % THD** (H2/H3 all ≈ 0). The modeled nonlinearity is **not a memoryless waveshaper** — it does not
distort a held sine. Audible "analog" character is **program-/transient-dependent** (coupled to the channel
dynamics), and AC202 (tape) is **AC-coupled** (a slow DC ramp is fully blocked → output ≈ 0; AC101 partially
passes/attenuates DC, more so as Drive rises → Drive feeds the dynamics, not a clipper). This rules out a
static tanh/clip clone; the nonlinearity needs a stateful/envelope-driven model (open question — exact onset).

## Parameters (CLEAN — norm→real)
### AC101 (console channel)
| param | unit | range / map |
|---|---|---|
| Input / Output | dB | trim |
| Drive | dB | **−12 … +12**, linear (feeds saturation+dynamics) |
| Curve | — | 1 … 10, linear (saturation knee/shape) |
| Attack | ms | 0.10 … 10, exp |
| Release | ms | 10 … 1000, exp |
| Auto | bool | auto makeup/release |
| Phase / Phase Right / Wet / Delta | — | |

### AC202 (tape)
| param | unit | range / map |
|---|---|---|
| Input / Output | dB | trim |
| Bias | dB | **−12 … +12** (tape bias) |
| Tape Speed | enum | **7.5 / 15 / 30 ips** |
| Bump | % | 0 … 100 (low-freq head bump) |
| Rolloff | (×?) | 20 … 100 (HF rolloff freq) |
| Release | ms | exp |
| EQ Type | enum | IEC 1 / … (tape EQ standard) |
| Tape Type | enum | Vintage / … |
| Tape Head Type | enum | Swiss / … |

PDC = **0** (both).

## Why / design rationale
- **Tape Speed 7.5/15/30 ips + EQ standard (IEC) + head/tape type** → models the speed-dependent HF
  response, head bump, and bias-distortion tradeoff of real machines (faster = cleaner HF, less LF bump).
- **AC-coupling** (AC202 blocks DC) → faithful to a real tape path; means a DC/transfer-curve probe is the
  wrong tool — must drive with program material/transients.
- **Drive→dynamics coupling** (AC101) → console "glue" where pushing level engages the channel comp +
  subtle harmonic onset together, not a brickwall clip — the McDSP "Analog Channel" feel.

## To implement
Model as channel-dynamics + speed/bias-dependent EQ (head-bump shelf, HF rolloff per ips) + a
**level/transient-gated** nonlinearity (NOT a static shaper). Verify onset with program material null vs the
licensed plugin (steady tone shows nothing). CLEAN-only; McDSP code PACE-walled.

## Open questions
- Exact harmonic onset level/curve under program material (steady-tone probe shows ~0; needs transient/
  multitone drive to characterize).

---
**CLEAN** = REAPER black-box of a licensed plugin. **No REF** (PACE wall).
