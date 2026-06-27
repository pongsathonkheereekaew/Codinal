# Volcano 3 — FabFilter (Modulating multimode filter bank)

| | |
|---|---|
| Vendor / ver | FabFilter · Volcano 3 · VST3 (Fx) · licensed, no DRM |
| Type | **Modulating multimode filter bank** — up to 4 filters (8 shapes × 11 styles × 4 slopes), 50-slot mod matrix driven by 6 XLFO step-seqs / 6 DAHDSR EGs / 4 envelope-followers / 6 XY / 10 MIDI |
| Tech | VST3 (FabFilter). Custom GPU UI (Cocoa/AppKit/Metal/QuartzCore). Own DSP (no vDSP exported). |
| Binary | universal Mach-O bundle (x86_64+arm64), **STRIPPED** (~6 ext syms: FF/VST/GetPluginFactory), **no PACE/iLok** |
| Provenance | **100% CLEAN** — black-box only (impulse→FFT transfer fn, swept harmonics). No r2/Ghidra (binary stripped → static is a wall). |
| Measured on | Volcano 3 · VST3 · SR 48 kHz · `Volcano3/Tools/volcano3_sysid.py` (pedalboard 0.9.17) · 2026-06-22 |
| Source | `private-research/Volcano3/` — `Tools/volcano3_sysid.py`, `docs/measurements.md` |

## Signal chain (CLEAN behaviour)
```
inL,inR → input_gain/pan
  → filter bank: 4 filters, combined per `routing` (8 graph presets) × routing_mode {Stereo|Per-Ch|Mid/Side}
       each filter:  ×drive(-18..+18 dB) → [SVF: shape×slope×peak, with per-style nonlinearity in-loop]
                     → output_level(-INF..+36) · output_pan · delay(0..50 ms)
  → output_gain/pan → mix(0..100% wet/dry) → outL,outR

modulation (control-rate, sums into targets via 50 slots; each slot = source→target×level, bipolar/invert):
  sources(39): XY1..6 hor/ver · XLFO1..6 (16-step seq) · EG1..6 (DAHDSR) · EF1..4 (env-follow) · MIDI1..10
  targets(182): every filter param, all XLFO/EG/EF params, slot levels, global gains/mix
high_quality = oversample the nonlinear filter stage (alias −30 dB, +14 samp latency)
```
Key: this is FabFilter's modular synth-filter — a clean **state-variable multimode filter** whose
*character* is set by an in-loop nonlinearity (the "style"), modulated by a deep matrix.

## CLEAN measurements

### Filter freq (filter_N_freq, exponential): 4.81 Hz … 75.6 kHz
raw 0.30→87 · 0.50→603 · 0.60→1585 · 0.70→4166 · 0.7675→8000 · 0.90→28.8k · 1.0→75.6k Hz.

### Shapes (8) @1 kHz, Clean, 24 dB, peak=0 (neutral)
LP (−3 dB@corner, −24/oct) · HP (mirror) · BP (peak@corner) · **Bell/LoShelf/HiShelf (flat at peak=0 →
peak = gain)** · Notch (deep null@corner) · AllPass (flat magnitude, phase-only).

### Slope enum → measured roll-off (LP, Clean)
| slope | 2k→4k | −3 dB corner | poles |
|---|---|---|---|
| 6 dB | 5.5/oct | 1000 Hz | 1-pole |
| 12 dB | 12.1/oct | 992 Hz | 2-pole |
| 24 dB | 24.2/oct | 796 Hz | 4-pole |
| 48 dB | 48.4/oct | 655 Hz | 8-pole |

### peak (filter_N_peak ∈ −1..+1)
- **Bell/Shelf** → gain, linear: −1→−20 dB · 0→0 · +1→+20 dB.
- **LP/HP** → resonance: ≤0 none · +0.5→+3.2 dB · +0.85→+12.5 · +1.0→+29 dB (≈ self-osc).

### Filter STYLES (11) — harmonic fingerprint (LP24, ~2 kHz, peak=0.85, drive=+12 dB, 1 kHz @−6 dBFS)
| style | THD% | H2 | H3 | character |
|---|---|---|---|---|
| **Clean** | 0.00 | −156 | −155 | **perfectly linear** — pristine non-saturating SVF |
| Tube | 6.7 | −26 | −27 | softest analog, even≈odd, low order |
| Metal | 12.1 | −18 | −47 | strong H2, H3 suppressed (even-only, hard) |
| Hollow | 12.9 | −18 | −38 | even-dominant, hollow/asym |
| Easy Going | 22.0 | −14 | −20 | asym soft-clip |
| Gentle | 22.9 | −14 | −19 | asym soft-clip |
| Hard | 23.2 | −14 | −19 | asym soft-clip (harder knee) |
| Classic | 23.5 | −14 | −18 | asym soft-clip (default) |
| Extreme | 30.1 | −17 | −13 | odd-leaning (H3>H2), aggressive |
| Smooth | 31.0 | −17 | −13 | odd-leaning, aggressive |
| Raw | 31.5 | −17 | −12 | odd-leaning, most aggressive |
Even-dominant cluster (asym soft-clip): Classic/Hard/Gentle/Easy Going/Hollow/Metal/Tube. Odd cluster
(symmetric, harder): Smooth/Raw/Extreme. **Clean** = the only linear style (use as the transparent SVF base).

### Per-style generating function — static-curve fit + harmonic ladder (CLEAN fingerprint)
Static transfer measured by slow triangle sweep through a resonant LP (24 dB, ~2 kHz cutoff, peak=0.85 — the
in-loop shaper engages in the resonant feedback, not the flat passband). Curve normalised (small-signal gain→1),
least-squares fit vs tanh / atan / hard-clip. `asym` = |f(x)+f(−x)| index (0=odd-symmetric); `comp` = full-scale
compression; `E-O` = even-vs-odd harmonic energy at drive +12 dB. Drive sets level INTO the shaper.
| style | family | shape fit (k=sharpness) | asym | comp | E-O@+12dB | hint |
|---|---|---|---|---|---|---|
| **Clean** | linear | none (g0=1.0) | 0 | 0 | — | bypass shaper; transparent SVF |
| Tube | asym soft, even | atan k≈0.8 (very soft) | .16 | .04 | +6.2 | gentlest; even>odd, low THD |
| Hollow | asym soft, even | atan k≈1.6 | .37 | .16 | **+10.7** | strongly even/asym → "hollow" |
| Metal | asym soft, even | atan k≈1.5 | .34 | .15 | **+14.2** | most even-dominant (H2≫H3) |
| Easy Going | asym soft | atan k≈3.6 | .55 | .49 | +4.4 | mid-knee asym clip |
| Gentle | asym soft | atan k≈4.0 | .57 | .53 | +3.5 | mid-knee asym clip |
| Hard | asym soft | atan k≈5.5 | .60 | .63 | +4.1 | harder asym knee |
| Classic | asym soft (default) | atan k≈7.2 (hardest asym) | .62 | .70 | +3.8 | default; hard asym clip |
| Smooth | symmetric, odd | **tanh** k≈6.4 | — | .79 | **−4.3** | odd>even at drive (H3>H2) |
| Raw | symmetric, odd | **tanh** k≈6.8 | — | .80 | **−4.8** | hardest/most symmetric |
| Extreme | symmetric, odd | atan k≈8.0 | — | .77 | **−3.4** | aggressive symmetric clip |
Three generating families: **(1)** Clean = linear. **(2)** even-dominant asymmetric saturators (Tube→Classic,
atan-shaped, knee hardness k rises 0.8→7.2; Metal/Hollow push the asymmetry hardest → big even-harmonic colour).
**(3)** symmetric odd clippers (Smooth/Raw = tanh, Extreme = steep atan; E-O flips negative under drive).
Fit is a CLEAN shape *hint* for voicing (asym shaper vs symmetric tanh/atan + k), not the plugin's internal formula.

### Drive → THD (style=Classic, LP24): 0.36%(−18 dB) · 11%(0 dB) · 24.6%(+12) · 28.3%(+18 dB)
H2/H3 ladder rises ~6 dB per +6 dB drive in the soft region; drive feeds the in-loop nonlinearity.

### Routing graphs — full 4-filter enumeration (CLEAN)
`routing` = 8 distinct graphs (enum displays "0".."7", no names). Topology decoded by 3 black-box probes:
**(a)** deep Notch per filter w/ others flat → null reaches output ⇒ series-spine, null filled ⇒ parallel branch;
**(b)** +20 dB Bell per filter w/ others flat → bump dilution `20log10((10+K)/(K+1))` pins #parallel-siblings K
(K0=+20, K1=+14.8, K2=+12.0, K3=+10.2 dB); **(c)** LP@3k∥HP@700 per pair → clean band-pass ⇒ that pair is series.

| routing | topology (4 filters) | evidence |
|---|---|---|
| **0** | **F1→F2→F3→F4** (full series) | K=0 all; every co-notch deep; bump +20; LP→HP = bandpass |
| **1** | **F1∥F2∥F3∥F4** (4-way parallel) | K=3 all; no co-notch survives; bump ≈+10.5 |
| **2** | **(F1→F2) → (F3∥F4)** | f1,f2 K=0 (series spine), f3,f4 K=1; all 4 bells pass; no LP/HP bandpass |
| **3** | **(F1∥F2) → (F3∥F4)** | K=1 all (2-path junctions); chained pair-of-pairs; all bells pass |
| **4** | **(F1∥F2) ∥ (F3∥F4)** | K=1 all; only f3–f4 co-notch deep (the one chained pair); else parallel |
| **5** | **(F1∥F2∥F3) → F4** | f4 K=0 + deep-chained w/ f1,f2,f3; f1,f2,f3 mutually parallel; F4 HP cut appears downstream |
| **6** | parallel mesh, K=2 (3-path junctions) | all 4 bells pass equally; no series chain |
| **7** | **(F1∥F2) → (F3→F4)** | f3&f4 = clean SERIES bandpass; f1,f2 parallel; K=[2,1,0,0] |

2-filter probe confirmed: even routings (0,2,4,6)=series F1→F2, odd (1,3,5,7)=parallel F1∥F2.
3-filter: 0/4 full-series, 1/5 3-way parallel, 2/6 parallel, 3/7 (F1∥F2)→F3. routing_mode {Stereo|Per-Channel|Mid/Side}
selects how the chosen graph is instanced (single graph vs per-L/R vs per-M/S); held = Stereo for these measurements.

### XLFO (6×, 16-step sequencer): rate 0.02…500 Hz (raw 0.248=1 Hz) · sync Free…1/64 bars ·
freq_offset ×0.5…×2 · per-step value/glide/glide_function{Linear,Sqr,Sqrt,Sine}/random · midi_trigger{Off,Retrig,Legato}.

### Modulation DEPTH on Filter Freq (slot_level → octaves, static DC source ±1, base 1 kHz)
0.16(default)→0.42 oct span · 0.25→1.0 · 0.5→3.2 · 0.75→7.7 oct (saturates at range limits). Bipolar.

### Envelope Follower (EF 4×): attack 1 ms…1 s · release 50 ms…5 s · {Envelope,Transient} · {Normal,SideChain}.
Depth (EF→Freq): louder input opens filter — tilt rises +46 dB as input goes −40→−4 dBFS (auto-wah).

### EG (6×, DAHDSR): attack 1.45 ms…3 s · decay/release 1.45 ms…5 s · hold 0…19 s · sustain −INF…0 dB ·
threshold −90…0 dB · per-stage slope ±1 (curvature) · trigger {Normal,SideChain,MIDI}.

### MIDI sources (10×) + keyboard tracking — `HOST-BLOCKED: needs MIDI host` (semantics from enums, CLEAN)
Each MIDI source is a mod-matrix source (`MIDI 1..10` in slot source list). 3 params each:
`midi_source_N_input` = {Mod Wheel, Pitch Bend, Velocity, Aftertouch, **KB Track**, Controller};
`midi_source_N_controller_number` = 0…127 (CC# when input=Controller); `midi_source_N_response_curve`
= {Linear, Exp, Log, Sqr, Sqrt, Sine} (maps the 0…1 source through a curve). Gated by global `receive_midi`
{Enabled|Disabled}. **KB-track filter cutoff** = a MIDI source with input=**KB Track** (played note number → 0…1),
routed via a slot to `Filter N Freq` with `slot_level` (octaves, same exp depth map as §"Modulation DEPTH on
Filter Freq"); `response_curve` shapes the note→depth law (Linear = 100% key-follow at full level).
**Cannot be measured in pedalboard**: plugin is an Fx (`is_instrument=False`); pedalboard rejects `midi_messages`
on effects (no note input) → no KB-track / velocity / pitch-bend / aftertouch scaling numbers. Needs a MIDI-capable
host (AU/VST3 MIDI-FX bridge) to drive note-on and measure cutoff-vs-note slope. Param semantics above are CLEAN
(enum dump); the scaling magnitudes are unmeasured (blocked), NOT fabricated.

### Global: input/output_gain ±36 dB · mix 0..100% · filter output −INF…+36 dB · delay 0…50 ms ·
**high_quality** = oversample nonlinear stage (alias −21→−51 dBc on driven 7 kHz; latency Off=1 / On=15 samp).

## To implement (CLEAN path for product — ES-L)
Modulating multimode filter = three reusable building blocks, all from CLEAN tables + public DSP literature:
1. **Multimode SVF core** (LP/HP/BP/Notch/Bell/LoShelf/HiShelf/AllPass, cascade for 6/12/24/48 dB/oct,
   `peak`=Q/gain): Zavalishin *The Art of VA Filter Design* (TPT/zero-delay SVF, ladder); RBJ EQ cookbook
   (bell/shelf coeffs). Match the measured corner/slope/peak tables above. "Clean" style = this, untouched.
2. **In-loop style nonlinearity** (the 11 styles): use the measured per-style fingerprint (shape fit table) —
   Clean=linear bypass; even-dominant=asymmetric atan shaper (knee k 0.8→7.2, Metal/Hollow = strongest asymmetry);
   odd cluster=symmetric tanh/steep-atan (Smooth/Raw=tanh, Extreme=atan); `drive` sets input level into it. Literature:
   Zölzer *DAFX* (nonlinear processing), Yeh/Pakarinen VA waveshaping, Kahles antiderivative anti-aliasing.
   Oversample ≥4–8× to hit the HQ-on alias floor (−51 dBc). Reproduce each style's THD% null vs `volcano3_sysid.py`.
3. **Mod matrix**: control-rate sources (LFO/step-seq, DAHDSR env, env-follower with the measured atk/rel +
   octave-depth map) summing into targets; `slot_level`→exponential depth (octaves on freq). Zölzer DAFX
   (modulation/LFO), standard ADSR. Bipolar/invert per slot.
All numbers above are CLEAN (measured) — safe to ship. No disasm was performed (binary stripped).

---
## REF (reference/education ONLY — NOT product-safe; do NOT cite in ES-L/BuildSpec)
> Quarantined Ghidra pass 2026-06-22: `_quarantine_disasm/Volcano3/`. The binary is stripped of exports
> but **C++ RTTI typenames survived in `__const`** → a static decompile WAS possible (the earlier "static is
> a wall" note applies only to symbol-level navigation). All facts here are TAINTED REF; the shippable spec
> stays the CLEAN measurement above.
- Filter type confirmed **State-Variable Filter, TPT/ZDF (Zavalishin)** — class `19StateVariableFilter` with
  `g` (`FreqFunction`) + `k=2R` (`DampLimitFunction`) function-objects, `PeakLimitFunction`/`DampLimit2Function`
  self-osc clamps, `ClipTable::ClipFunction` in-loop nonlinearity. Shapes/slopes built by a shared FabFilter
  analog-prototype cascade (Butterworth/Chebyshev/elliptic; same fixed constants as Pro-Q4).
- In-loop style nonlinearity (REF) = `t=2^x; t=min(t,1); out=2·sin(t·π/3)`; **Clean** style bypasses it
  (only linear style) — corroborates the CLEAN TPT-SVF + per-style-nonlinearity classification above.
- Self-osc mechanism: damping `2R→0` via `2(1−R^¼)` → matches measured resonance→self-osc.
- Full REF detail: `_quarantine_disasm/Volcano3/{architecture-findings.md, decomp/ghidra/{svf_kernel.c,coeff_table.md}}`.

---
Provenance tags: **CLEAN** = black-box measurement (`Volcano3/Tools/volcano3_sysid.py`) / public DSP / own voicing (product-safe).
**REF** = quarantined Ghidra disasm (`_quarantine_disasm/Volcano3/`) — reference/education only, never product.
RESOLVED 2026-06-22 (all CLEAN, harness subcommands `routing_topo` / `routing_gain` / `routing_adj` / `style_curve`):
4-filter routing→topology table (8 graphs) · per-style generating-function classification (3 families + shape fit).
**HOST-BLOCKED** (not REF, not fabricated): MIDI/KB-track cutoff scaling — semantics documented from enums;
magnitudes need a MIDI host (pedalboard Fx has no note input). No remaining OPEN questions.
