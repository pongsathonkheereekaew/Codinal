# Timeless 3 — FabFilter (Tape/analog delay — filtered feedback, modulation, ducking, drive)

| | |
|---|---|
| Vendor / ver | FabFilter · Timeless 3 · v3.10 · VST3 · no DRM (no PACE/iLok) |
| Type | **Tape / analog delay** — filtered feedback loop (filter INSIDE the loop), in-loop saturation/drive, multi-tap, ping-pong/stereo time-offset, Tape vs Stretch read modes, diffusion, lo-fi, bipolar wet-dynamics (ducking), pitch-shift, deep modulation system (XLFOs / envelope generators / followers / XY) |
| Tech | VST3 (FabFilter), universal Mach-O **bundle** (x86_64 + arm64), **stripped** (6 defined ext syms: `_GetPluginFactory`, `_VSTPluginMain`, `_bundleEntry/Exit`, `_FFPluginMain`, `_main_macho`), **black-box only** (no r2/Ghidra). Links only system frameworks + libz. UI = Cocoa/Metal/QuartzCore |
| Binary | `…/FabFilter Timeless 3.vst3/Contents/MacOS/FabFilter Timeless 3` · 4.9 MB · stripped (no symbols leak) |
| Provenance | **100% CLEAN** — every fact is black-box measurement (pedalboard host) or the binary's own self-reported param metadata (names/ranges/enum strings). No disasm anywhere |
| Measured on | Timeless 3 v3.10 · SR 48 kHz · pedalboard 0.9.17 · `private-research/Timeless3/Tools/{timeless3_sysid.py,timeless3_measure.py}` · 2026-06-22 |
| Source | `private-research/Timeless3/` — `Tools/timeless3_sysid.py` (param surface + enum sweep), `Tools/timeless3_measure.py` (audio probes: `…pitch`, `…dynamics`, `…modmatrix`, `…sync` added), `out/*.json` (raw results) |

## Signal chain (CLEAN — measured topology)
```
inL,inR (stereo)
  │            ┌─────────────────── FEEDBACK LOOP ───────────────────┐
  ▼            │                                                       │
 ──►(+)──► DELAY LINE ──┬──► [filter bank ×6: serial/parallel/per-ch] ─┤
      ▲    (Tape|Stretch│     (each: shape LP/HP/BP/Bell/LoSh/HiSh/    │
      │     read mode)  │      Notch · slope 6/12/24/48 · 11 styles =  │
      │                 │      analog/saturation character · freq/Q/gain)
      │                 ├──► [drive]  (odd-dominant soft saturation)   │
      │                 ├──► [lo-fi]  (bandwidth/bit reduction)        │
      │                 ├──► [diffuse] (allpass smear)                 │
      │                 ├──► [pitch_shift] (inside-fb option)          │
      │                 └──► [dynamics] (bipolar duck/swell on wet)    │
      └──────── ×feedback (0–200%) ◄── cross-mix / invert L|R / pan ◄──┘
                 (in-loop saturation/limiter bounds >100% self-osc)
  ▼
 multi-tap reads (main + tap 1..15: level/pan/time_factor) → stereo_width → wet_level/wet_pan
  ▼
 mix (dry/wet)  →  outL,outR
```
**Key measured insight:** the filter and saturation are **inside the feedback loop** — successive
echoes get progressively darker/more-coloured (cumulative), the defining tape/analog-delay topology.
Whether `pitch_shift` sits inside or outside the loop is a user switch (`pitch_shift_routing`).

## Per-stage formula (all CLEAN — black-box)
- **Delay line** (CLEAN): echo spacing == `delay_time`. Free mode range **5 ms … 5.0 s** (raw 0..1,
  nonlinear taper — fine <15 ms, near-linear ~95 ms…800 ms, coarser to 5 s). Tempo-sync via `delay_sync`
  (Free / 1·2·4·8·16 Note) — **deterministic mapping** `delay_s = note_fraction·(4·60/BPM) = beats·60/BPM`,
  note→beats {1/2→2, 1/4→1, 1/8→0.5, 1/16→0.25}; absolute seconds **HOST-BLOCKED** (needs DAW BPM — pedalboard
  has no transport hook, renders at its ~80 BPM default). Latency ≈ **7 samples** (no big OS FIR).
- **Read mode** (CLEAN): `Tape` vs `Stretch`. Same static echo time at a fixed setting; they differ on
  *time changes* — Tape re-pitches buffered audio (Doppler/varispeed), Stretch retimes without pitching.
- **Feedback** (CLEAN): **linear feedback gain** — measured echo-to-echo decay ratio ≈ feedback %
  (10%→0.091, 20%→0.200, 35%→0.342, 50%→0.498, 90%→0.895). Range 0–200%; >100% = **sustained self-osc**
  that is **bounded** (130% click → peak grows 2.3→4.8 then stabilises ~4.5; in-loop saturation/limit caps runaway).
- **Filter (in loop)** (CLEAN): high/low band tilt drops monotonically per echo (−8.4 → −15.6 dB over 8
  echoes for LP ~2 kHz/24 dB) → cumulative ⇒ **filter is inside the feedback path**. 6 filters, routing
  Serial/Parallel/Per-Channel. `style` = nonlinear analog character (see table).
- **Drive** (CLEAN): odd-dominant soft saturation (tanh-like). H3 ≫ H2; THD −27.8 → −10.7 dB as drive 0→100%.
- **lo-fi** (CLEAN): bandwidth/bit reducer — centroid 8.6 kHz → 300 Hz at 100% (heavy LP + degradation).
- **diffuse** (CLEAN): allpass diffusion — smears the echo in time (peak moves earlier, ~363→254 ms) without
  changing spectral centroid → reverb-ish smear, not a tone filter.
- **dynamics** (CLEAN, FULLY MAPPED): bipolar wet **expander** keyed off the input/sidechain envelope.
  **Threshold = −6 dBFS** (sine RMS): at/above, gain = 0 dB (no effect). Below threshold the wet is
  gain-modulated with **slope exactly 1.0 dB/dB** (the unity line crosses 0 dB at −12 dBFS; soft knee
  ≈ −15…−6 dBFS), **clamped at ±35.8 dB** max depth (reached below ≈ −42 dBFS). Polarity = sign(dynamics):
  − ducks (attenuate quiet passages), + swells (boost). Magnitude scales **linearly** with the control:
  `wet_gain_dB = dynamics × clamp(0, 35.8, knee[−6 − input_dBFS])`, mirror-symmetric duck/expand.
- **stereo / ping-pong** (CLEAN): `delay_time_pan` = independent L/R time multiplier (each 100%↔400%, no
  cross-feed). `ping_pong` (Off / L-R / R-L) routes feedback to bounce channel-to-channel. `feedback_cross_mix`
  + `feedback_invert_left/right` add cross-feed / polarity per side.

## Parameters (CLEAN — names/ranges/enums self-reported by binary; 1012 params total)
Core DSP (modulation banks summarised below). `_enabled`/`_used` are per-section on/off toggles.
| param | unit / range | type | notes (CLEAN) |
|---|---|---|---|
| `delay_time` | 5 ms … 5.0 s (Free) | float | nonlinear taper; echo spacing == this. Sync replaces with note values |
| `delay_sync` | Free / 1·2·4·8·16 Note | enum[5] | tempo-sync; `delay_s=beats·60/BPM`, note→beats {½→2,¼→1,⅛→.5,1/16→.25}; abs s HOST-BLOCKED (DAW BPM) |
| `delay_read_mode` | Tape / Stretch | enum[2] | varispeed-pitch vs clean-retime on time change |
| `delay_offset` | 50% … 200% (triplet/dotted marks) | float | time factor (e.g. dotted/triplet rhythmic offset) |
| `delay_time_pan` | L 400%..100% / R 100%..400% | float | independent L/R delay-time multiplier (stereo spread) |
| `delay_freeze` | Off / On | bool | hold/infinite-repeat the buffer |
| `ping_pong` | Off / L-R / R-L | enum[3] | cross-channel feedback bounce |
| `feedback` | 0 … 200% | float | **linear feedback gain**; >100% bounded self-osc |
| `feedback_pan` | −1..+1 (0 ctr) | float | pan the feedback signal |
| `feedback_cross_mix` | 0 … 100% | float | L↔R cross-feed in loop |
| `feedback_invert_left` / `_right` | Normal / Inverted | bool×2 | per-channel feedback polarity |
| `auto_mute_self_osc` | Off / On | bool | auto-mute when loop self-oscillates |
| `channel_mode` | Left/Right · Mid/Side | enum[2] | processing basis |
| `filter_1..6_freq` | 4.8 Hz … 75.6 kHz | float×6 | filter cutoff/centre |
| `filter_1..6_shape` | LP·HP·BP·Bell·LoShelf·HiShelf·Notch | enum[7]×6 | filter type |
| `filter_1..6_slope` | 6 / 12 / 24 / 48 dB/oct | enum[4]×6 | rolloff |
| `filter_1..6_style` | Classic·Gentle·Raw·Tube·Metal·EasyGoing·Smooth·Hard·Hollow·Extreme·Clean | enum[11]×6 | **nonlinear analog character** (see table) |
| `filter_1..6_gain` | ±dB | float×6 | shelf/bell gain |
| `filter_1..6_peak` | 0..1 (Q/resonance) | float×6 | resonance |
| `filter_1..6_pan` | −1..+1 | float×6 | per-filter pan (for per-channel routing) |
| `filter_routing` | Serial / Parallel / Per Channel | enum[3] | filter-bank topology |
| `drive` / `drive_enabled` | 0 … 100% · On/Off | float+bool | odd-dominant in-loop saturation |
| `lo_fi` / `lo_fi_enabled` | 0 … 100% · On/Off | float+bool | bandwidth/bit reduction (darkening) |
| `diffuse` / `diffuse_enabled` | 0 … 100% · On/Off | float+bool | allpass diffusion smear |
| `dynamics` / `dynamics_enabled` | −1 … +1 (0 ctr) · On/Off | float+bool | bipolar wet expander: threshold −6 dBFS, slope 1 dB/dB, clamp ±35.8 dB, linear control (see law) |
| `pitch_shift` / `_enabled` | **−12 … +12 semitones** · On/Off | float+bool | raw 0..1 LINEAR: `semitones = 24·raw − 12` (measured pitch matches ≤0.13 st) |
| `pitch_shift_routing` | Inside / Outside Feedback | enum[2] | shimmer when inside loop |
| `pitch_shift_mirroring` | Off / On | bool | dual up/down |
| `stereo_width` | 0 … 100%+ | float | wet width |
| `wet_level` | −inf … 0 dB | float | wet output trim |
| `wet_pan` | L/R dB | float | wet pan |
| `mix` | 0 … 100% | float | dry/wet blend |
| `lock_mix` | Unlocked / Locked | bool | keep mix on preset change |
| `delay_tap_main_{level,pan,enabled}` + `delay_tap_1..15_{level,pan,time_factor,enabled,used}` | — | — | **multi-tap** delay (main + up to 15 extra taps; each its own level/pan/rhythmic time-factor) |
| `bypass`, `audition_signal` (Output/Side Chain), `channel_pressure` | — | — | host/aux |

**Modulation system (CLEAN, large banks — counts gate active units):**
- `num_active_xlfos` 0..6 → `xlfo_1..6_*`: each an **XLFO step-sequencer LFO** — `frequency` (0.02–500 Hz),
  `sync_mode` (Free + 16…1/64), `balance`, `phase_offset`, `glide`, `snap`, `midi_trigger`, plus **16 steps**
  (`step_N_{value,glide,glide_function∈{Linear,Sqr,Sqrt,Sine},random}`) and `num_active_xlfo_N_steps`.
- `eg_1..6_*`: **envelope generators** — delay/attack/hold/decay/sustain/release (+ per-segment slope),
  range, threshold, triggering.
- `ef_1..4_*`: **envelope followers** — input/mode/attack/release.
- `num_active_xy_controllers` 0..6 → `xy_controller_1..6_*`: macro Slider/XY (hor/ver, range Positive/Centered).
- **Mod matrix IS on the param surface (CLEAN — corrects prior "UI-only" note):** `num_active_slots` 0..50 →
  `slot_1..50_{source,target,level,inverted,bypassed}`. Each slot = one routing **edge**: `source` (39 opts),
  `target` (240 opts = every core-DSP param + EG/EF segments + Slot-N-Level for chaining), `level` = depth
  (0..1), `inverted` (Normal/Inverted), `bypassed`. Sources (39) = `< Source >` · XY 1..6 Hor/Ver (12) ·
  XLFO 1..6 (6) · EG 1..6 (6) · EF 1..4 (4) · MIDI 1..10 (10). Edges + depths are fully settable/measurable
  by raw-index (string-set is blocked for choice params). Confirmed live black-box: `XLFO 1 (8 Hz) → Delay Time`
  @ full slot level widens a delayed 2 kHz tone's spectral spread 118→1406 Hz vs the same route bypassed.

## CLEAN measurements (key tables)
**Delay-time taper** (raw → displayed, Free mode):
| raw | 0.0 | 0.1 | 0.15 | 0.2 | 0.25 | 0.3 | 0.4 | 0.5 | 0.6 | 0.7 | 0.8 | 1.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ms/s | 5 ms | 15 ms | 95 ms | 175 ms | 255 ms | 365 ms | 584 ms | 804 ms | 1.30 s | 1.80 s | 3.18 s | 5.0 s |
Measured first-echo ≈ displayed (e.g. raw 0.293→"349 ms"→L 347 / R 351 ms; R 1% longer = default `delay_time_pan`).

**Feedback = linear gain** (decay ratio per echo, delay 30 ms):
| fb % | 10 | 20 | 30 | 35 | 40 | 50 | 60 | 70 | 80 | 90 | 100 | 130 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ratio/echo | .091 | .200 | .290 | .342 | .380 | .498 | .598 | .697 | .795 | .895 | self-osc | bounded |

**Filter inside loop** (LP ~2 kHz/24 dB; hi/lo tilt dB per echo): −8.4, −9.0, −9.4, −10.5, −11.6, −12.8, −14.1, −15.6 → monotonic ⇒ in-loop.

**Drive harmonics** (1 kHz, single pass, fb=0):
| drive | 0% | 20% | 50% | 70% | 100% |
|---|---|---|---|---|---|
| THD dB | −27.8 | −20.5 | −18.0 | −13.2 | −10.7 |
| H2 / H3 dBc | −41/−28 | −39/−21 | −43/−18 | −41/−14 | −30/−12 |
Odd-dominant (H3≫H2) ⇒ symmetric soft clip. Baseline H3≈−28 dB at 0% drive = tape read-path colour.

**Filter `style` nonlinearity** (LP, high resonance + 90% fb, 300 Hz tone):
| style | THD dB | character |
|---|---|---|
| Clean | −26 | cleanest, lets resonance ring (peak 1.46) |
| Tube | −23 | smooth, low odd (H3 −58) |
| Metal | −20 | harder, H3 −36 |
| Classic | −14 | saturated, limits ~0.46, full H2/H3 ladder |
| Extreme | −6.7 | most aggressive, hard-limit ~0.43, rich ladder |

**Tone shapers:** `lo_fi`=100% → centroid 8.6 kHz→300 Hz (bandwidth crush). `diffuse`=100% → echo peak 363→254 ms (time smear, centroid unchanged).

**`pitch_shift` raw → semitones** (LINEAR `24·raw − 12`; measured pitch ratio = 2^(st/12), tone 1 kHz, Outside-FB single copy):
| raw | 0.0 | 0.125 | 0.25 | 0.375 | 0.5 | 0.625 | 0.75 | 0.875 | 1.0 |
|---|---|---|---|---|---|---|---|---|---|
| displayed st | −12 | −9 | −6 | −3 | 0 | +3 | +6 | +9 | +12 |
| measured st | −12.04 | −9.13 | −5.94 | −2.98 | 0.00 | +2.96 | +6.01 | +9.05 | +11.96 |
Full range **±12 st** (prior "±36" was wrong). Max |err| ≤ 0.13 st ⇒ displayed = real pitch.

**`dynamics` wet-gain law** (wet RMS dynamics-on ÷ neutral, dB, vs input dBFS; sine, fb=0):
| in dBFS | −60 | −48 | −42 | −36 | −30 | −24 | −18 | −15 | −12 | −9 | −6 | ≥−5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| duck(−1) dB | −35.8 | −35.8 | −30.0 | −24.0 | −18.0 | −12.0 | −6.0 | −3.4 | −1.5 | −0.4 | 0.0 | 0.0 |
| expand(+1) dB | +35.8 | +35.7 | +29.9 | +24.0 | +18.0 | +12.0 | +6.0 | +3.4 | +1.5 | +0.4 | 0.0 | 0.0 |
⇒ **threshold −6 dBFS**, **slope 1.0 dB/dB** (unity line 0-cross at −12 dBFS), soft knee −15…−6, **clamp ±35.8 dB**, mirror-symmetric.
Control is a **linear scalar** (input −30 dBFS → gain = dynamics×18.0 dB: −1.0→−18.0, ±0.2 step = ±3.60 dB).

**`delay_sync` note→time** (DETERMINISTIC; absolute s HOST-BLOCKED — needs DAW BPM; pedalboard default ≈ 80 BPM, shown below):
| sync | beats (whole=4) | `delay_s` | pb-default render (≈80 BPM) |
|---|---|---|---|
| 1/2 Note | 2 | 2·60/BPM | 1496 ms |
| 1/4 Note | 1 | 1·60/BPM | 748 ms |
| 1/8 Note | 0.5 | 0.5·60/BPM | 376 ms |
| 1/16 Note | 0.25 | 0.25·60/BPM | 188 ms |
General: `delay_s = note_fraction·(4·60/BPM) = beats·60/BPM`; abs ms = beats·60000/BPM. (XLFO `sync_mode` enum = Free,16,8,4,2,1,1/2,1/4,1/8,1/16,1/32,1/64 — same formula, also HOST-BLOCKED.)

## To implement (CLEAN path for product — public DSP literature only)
A filtered-feedback tape/analog delay. All targets above are measured; build from them + public DSP:
- **Fractional delay line** (modulatable read pointer for Tape varispeed + LFO warble): Laakso, Välimäki,
  Karjalainen, Lassfolk, *Splitting the Unit Delay* (IEEE SP Mag 1996) — Lagrange/allpass interpolation;
  Välimäki & Laakso fractional-delay surveys.
- **Effect/delay/chorus architecture & in-loop filtering**: Dattorro, *Effect Design Part 1 (delay-line
  modulation) & Part 2 (reverberation/diffusion allpass)*, JAES 1997 — diffusion-allpass cluster ⇒ `diffuse`.
- **General delay/feedback, saturation, lo-fi, modulation**: Zölzer (ed.), *DAFX: Digital Audio Effects*
  (delay/feedback, nonlinear processing, modulation chapters).
- **Tape model** (read-mode varispeed/Doppler, wow/flutter, head saturation/loss): Arnardóttir et al. /
  Chowdhury *Real-time tape model* (DAFx-19); for product, fit to the measured baseline H3 + lo-fi curve.
- **In-loop soft saturation** (odd-dominant): tanh / parametric soft-clip with antiderivative anti-aliasing
  (Parker/Zavalishin/Bright; Kahles) — match the measured THD/H3 ladder; the same nonlinearity bounds >100% fb.
- **Filter `style` flavours**: virtual-analog SVF/biquad ladder (6/12/24/48 dB) with per-style nonlinear
  drive — match each style's measured THD/harmonic fingerprint (table). Zölzer DAFX (filters), Zavalishin
  *The Art of VA Filter Design*.
- **Feedback = linear gain** (decay ratio ≈ fb%), **filter & saturation strictly inside the loop**,
  ping-pong = cross-channel feedback routing, `delay_time_pan` = independent L/R read-time multiplier.
- **Mod system** (CLEAN): drive `slot_N` (source→target×depth) from the 39 sources to 240 targets; the
  engine is a per-sample param-modulation summing matrix (depth = `slot_N_level`, signed by `inverted`).
  `dynamics` = wet expander with the measured threshold/slope/clamp law (implement as env-follower →
  gain in dB → linear). `pitch_shift` = ±12 st (granular/PSOLA or FFT phase-vocoder; `routing` selects
  in/out of feedback). Tempo-sync = `beats·60/BPM` from host transport.
- Null-test any clone against `timeless3_measure.py` (echo-train spacing, per-echo decay, per-echo tilt,
  drive THD ladder, `pitch` semitone map, `dynamics` gain law) before shipping. All four prior open
  questions are now CLEAN-measured; only absolute sync-seconds are host-BLOCKED (deterministic mapping known).

### Resolved (2026-06-22) + remaining host-blocks
- ✅ **`dynamics` law** — wet expander: threshold −6 dBFS, slope 1.0 dB/dB, clamp ±35.8 dB, linear control, mirror duck/expand (table above; `out/dynamics_law.json`).
- ✅ **`pitch_shift` range** — full ±12 st, linear `24·raw−12`, measured pitch matches ≤0.13 st (prior "±36" wrong; `out/pitch_shift.json`).
- ✅ **Mod-matrix edges** — fully on param surface: 50 `slot_N_{source,target,level,inverted,bypassed}`, 39 sources × 240 targets, depths settable/measurable; live route confirmed (`out/mod_matrix.json`). NOT UI-only.
- ⛔ **HOST-BLOCKED (needs DAW transport/BPM):** absolute tempo-sync **seconds** for `delay_sync` + XLFO `sync_mode`. pedalboard exposes no BPM/transport hook (renders at ~80 BPM default), so seconds can't be set/swept here. Mapping is deterministic: `delay_s = beats·60/BPM` (note→beats table above) — no fabricated seconds. Confirm in a DAW at known BPM if exact ms needed.

### REF (reference/education ONLY — NOT product-safe; do not cite from product/BuildSpec)
Static Ghidra/r2 disasm pass done 2026-06-22 (TAINTED, quarantined under
`private-research/_quarantine_disasm/Timeless3/` — see `architecture-findings.md` + `decomp/ghidra/`).
Corroborates (does NOT replace) the CLEAN measurements: interpolation = **polyphase FIR fractional
delay** (4-tap cubic / 8-tap & N-tap windowed-sinc; Tape vs Stretch select phase/length); in-loop filter
= **nonlinear TPT/State-Variable Filter** with cubic-saturated, state-clamped integrators @2× OS (the
cubic term = the 11 filter styles); drive = **memoryless waveshaper bank** (arctan, x/(1+|x|), poly2,
**poly3 cubic — matches measured odd-dominant**, log-tube, rational-triode; + asym B/PB variants);
pitch = **expf/pow resample ratio + grain crossfade**; gain math is **dB-domain** (logf×20/ln10 ↔
expf×ln10/20, byte-identical to Pro-L2/Pro-C3). Exact coeffs live ONLY in the quarantine. Open REF
walls: exact 4-tap polynomial (Lagrange-3 vs Hermite) undecidable from kernel; duck threshold/ratio law
not isolated. **Re-derive everything from `timeless3_measure.py` before any use — REF never ships.**

---
Provenance tags: **CLEAN** = black-box measurement (`timeless3_measure.py`) + binary self-reported metadata
+ public DSP literature (product-safe). **REF** = static disasm, quarantine-only (see REF section above +
`_quarantine_disasm/Timeless3/`); reference/education ONLY, never cited from product/ES-L/BuildSpec.
