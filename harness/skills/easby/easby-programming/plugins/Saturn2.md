# Saturn 2 — FabFilter (Multiband saturation / distortion)

| | |
|---|---|
| Vendor / ver | FabFilter · Saturn 2 · VST3 (Fx) · no DRM |
| Type | **Multiband saturation / distortion** — up to 6 bands, per-band selectable distortion **style** (28 models: tube / tape / amp / saturation / transformer / fold / rectify / lo-fi), per-band **drive**, **dynamics** (program-dependent drive), resonant **feedback**, post-distortion **tone** stack, and a deep **modulation matrix** (XLFO / envelope-gen / envelope-follower / MIDI / XY → any param) |
| Tech | VST3 (FabFilter), C++ (vendor). **STRIPPED** universal Mach-O bundle — 6 defined ext syms (VST3 factory entry points), 455 undefined are all system frameworks (CoreFoundation/CoreGraphics/Accelerate). NO PACE/iLok. → **black-box only** |
| Binary | universal Mach-O bundle (x86_64 + arm64), ~4.4 MB, stripped, no DRM, no leaked dev paths |
| Provenance | **100% CLEAN** (black-box `pedalboard`, `saturn2_sysid.py`). No disasm. Every fact below is a measurement or self-reported param metadata. No REF facts. |
| Measured on | Saturn 2 (FabFilter, current install) · SR 192 kHz (harmonics) + 48 kHz (aliasing) · `private-research/Saturn2/Tools/saturn2_sysid.py` (pedalboard host) · **2026-06-22** |
| Source | `private-research/Saturn2/` — `Tools/saturn2_sysid.py`, `docs/` |

## Signal chain (CLEAN — measured behaviour)
```
inL,inR
  → input_gain (±36 dB)  → input_pan
  → split into N active bands (1..6) by Linkwitz-Riley crossover (−6 dB/leg @ fc, sum-flat;
       6/12/24/36/48 dB/oct; band_N_crossover_frequency = shared upper edge of band N)
       (Minimum-Phase or Linear-Phase crossover/processing; L/R or M/S)
  ┌── per band b ────────────────────────────────────────────────────────────┐
  │  band_b: drive (0..100%) [+ drive_pan]                                     │
  │       → dynamics (program-dependent drive modulation, −1..+1)             │
  │       → WAVESHAPER core  = band_b_style  (1 of 28 distortion models)       │
  │              (memoryless static nonlinearity; runs inside internal OS)     │
  │       → resonant FEEDBACK loop  (feedback_amount %, tuned feedback_freq)   │
  │       → TONE stack  (bass / mid / treble / presence shelves+bell, POST)    │
  │       → ×mix  (parallel dry/wet blend of this band)                        │
  │       → ×level (−∞..+36 dB)  → pan                                         │
  └────────────────────────────────────────────────────────────────────────────┘
  → sum bands
  → output coupling HPF (~20 Hz DC-blocker, +1 dB LF shelf)
  → global mix (parallel dry/wet) → output_gain → output_pan → outL,outR
modulation matrix (50 slots) routes XLFO/EG/EF/MIDI/XY → any band/global param (not in audio path itself).
```
Key insight (CLEAN): the per-band distortion **core is a memoryless waveshaper** (a fixed static
transfer curve). THD is strongly **input-level-dependent** (more level ⇒ further up the curve ⇒ more
THD + gain compression) but **frequency-INDEPENDENT within a band** (flat 50 Hz–2 kHz) — i.e. NO
reactive/inductor coloration (contrast AS-1, which had frequency-dependent H2). Any *time-varying*
behaviour comes from the explicit **`dynamics`** knob (envelope-keyed drive), not from the curve itself.
`high_quality_mode` is the **internal oversampling** control (Off/Good/Superb).

## Per-stage formula (all CLEAN)
- **Waveshaper core** (CLEAN): static `y = f_style(drive·x)` per band. 28 named curves; fingerprints below.
  Even-harmonic content (H2, even/odd ratio) ⇒ asymmetric curve; pure odd ⇒ symmetric. Drive 0% is **not**
  bypass — every style has a baseline nonlinearity (e.g. Warm Tube THD 4.1 % at drive 0, 1 kHz −6 dBFS).
- **dynamics** (CLEAN): envelope-keyed *drive* modulation. On a steady tone it does nothing (THD flat vs
  dynamics); on a quiet→loud burst it scales the **quiet/sustained** portion's drive: `dyn=+1` raises
  low-level THD toward the loud level (compresses dynamics / more sustain saturation), `dyn=−1` lowers it
  (preserves transients, less low-level grit). Loud-segment THD is unchanged by dynamics.
- **Tone stack** (CLEAN, POST-distortion — boosting it amplifies *already-generated* harmonics):
  `bass` low-shelf ~40–80 Hz · `mid` bell ~640 Hz · `treble` high-shelf ~5 kHz↑ · `presence`
  steeper high-shelf, engages >5 kHz. Each ±24 dB.
- **Feedback** (CLEAN): resonant loop around the band; `feedback_amount` 0..100 %, tuned to
  `feedback_frequency` (10–1000 Hz). At ≥~90 % a strong resonant tone at the feedback frequency appears
  (−37 dBc at fb=90 %); low amounts inaudible. Amp-style controlled feedback/howl.
- **Mix** (CLEAN): per-band AND global parallel **dry/wet blend** (monotonic; mix=0 ≈ clean band).
- **Output HPF** (CLEAN): ~20 Hz highpass (−3 dB @ 20 Hz) DC-blocker, with a small +1 dB shelf 50–200 Hz.

## Parameters (CLEAN — pedalboard exposes the full automation surface: **956 params**)

### Per-band (×6 identical banks: `band_1_*` … `band_6_*`)
| param | unit / range | default | notes |
|---|---|---|---|
| `style` | enum, **28** | Warm Tape | distortion model (TYPE enum — see list) |
| `drive` | % 0..100 (0.1) | 20 % | input gain into the curve; 0 % ≠ bypass (baseline nonlinearity) |
| `drive_pan` | −1..+1 (0.002) | 0 | L/R asymmetry of drive |
| `dynamics` | −1..+1 (0.002) | 0.02 | program-dependent drive (+ = compress/sustain, − = preserve transients) |
| `feedback_amount` | % 0..100 | 0 | resonant feedback amount |
| `feedback_frequency` | Hz 10..1000 | 250 | feedback resonance tuning |
| `bass` | dB −24..+24 | 0 | post-dist tone: low shelf ~40–80 Hz |
| `mid` | dB −24..+24 | 0 | post-dist tone: bell ~640 Hz |
| `treble` | dB −24..+24 | 0 | post-dist tone: high shelf ~5 kHz↑ |
| `presence` | dB −24..+24 | 0 | post-dist tone: steeper HF shelf >5 kHz |
| `mix` | % 0..100 (0.1) | 100 % | parallel dry/wet for this band |
| `level` | dB −∞..+36 | 0 | per-band output level |
| `pan` | L/R | center | per-band pan |
| `crossover_frequency` | Hz 40..18000 | 40 (floor) | **UPPER edge of band N** = boundary N→N+1 (band N+1 shares the same fc as its lower edge); last band's value is unused. **Writes DO reach DSP** (verified by audio); the GUI auto-spread is NOT reflected in the automation read (all bands read 40 Hz). See *Crossover* below. |
| `crossover_slope` | enum: 6/12/24/36/48 dB/oct | 24 dB/oct | per-crossover steepness (verified: measured roll-off = label) |
| `state` | enum: Normal/Solo/Mute/Solo(Mute) | Normal | band solo/mute |
| `enabled` | bool | Enabled | band on/off |

### `style` enum (28, in order) — the saturation TYPE list
`Subtle Tube · Clean Tube · Warm Tube · Broken Tube · Subtle Tape · Clean Tape · Warm Tape · Old Tape · American Tweed Amp · American Plexi Amp · British Rock Amp · British Pop Amp · Smooth Amp · Crunchy Amp · Lead Amp · Screaming Amp · Power Amp · Subtle Saturation · Gentle Saturation · Heavy Saturation · Subtle Transformer · Gentle Transformer · Warm Transformer · Smudge · Breakdown · Foldback · Rectify · Destroy`

### Global
| param | unit / range | default | notes |
|---|---|---|---|
| `input_gain` | dB −36..+36 | 0 | |
| `input_pan` / `output_pan` | L/R | center | |
| `output_gain` | dB −36..+36 | **−1.0 dB** | factory default trims −1 dB |
| `mix` | % 0..100 | 100 % | global parallel dry/wet |
| `num_active_bands` | 1..6 | **1** | default = single full-range band |
| `high_quality_mode` | enum: **Off / Good / Superb** | Off | **internal oversampling** (see aliasing) |
| `processing_mode` | enum: Minimum Phase / Linear Phase | Min Phase | crossover/OS phase mode (Linear adds large latency) |
| `channel_mode` | enum: Left/Right / Mid/Side | L/R | per-band processing domain |
| `audition_signal` | enum: Output / Side Chain / Band 1..6 | Output | solo-listen tap |

### Modulation surface (854 non-band params; NOT in the audio path — routes to params)
6 × **XLFO** (16-step, `frequency`, `sync_mode`, `snap`, `glide`, `balance`, `phase_offset`, per-step
`value`/`glide`/`random`) · 6 × **envelope generator** (DAHDSR + slopes + `threshold`/`triggering`/`range`) ·
4 × **envelope follower** (`attack`/`release`/`mode`/`input`) · 10 × **MIDI source** (`controller_number`,
`response_curve`) · 6 × **XY controller** · **50 modulation slots** (`source`→`target`, `level`, `inverted`,
`bypassed`). Standard FabFilter modular system. (Audio core = the band + global params above.)

## CLEAN measurements

### Per-style harmonic fingerprint (1 kHz, in −6 dBFS, drive 50 %, HQ=Superb, flat tone)
THD% and H2/H3/H5 ladder (dBc); even/odd ratio >0 ⇒ even-dominant/asymmetric; gain = measured level change.
| style | THD% | H2 | H3 | H5 | even/odd | gain dB | character |
|---|---|---|---|---|---|---|---|
| Subtle Tube | 0.6 | −53 | −46 | −62 | −7.6 | +0.2 | barely-there, asym |
| Clean Tube | 6.0 | −30 | −26 | −40 | −3.9 | +0.1 | gentle asym tube |
| Warm Tube | 13.0 | −29 | −18 | −38 | −7.6 | −0.6 | classic asym tube (H3>H2) |
| Broken Tube | 38.0 | −23 | −11 | −16 | −12.6 | −17.8 | gnarly, gain-comp'd |
| Subtle Tape | 0.0 | −175 | −75 | −152 | −92.7 | +0.1 | symmetric, ~clean |
| Clean Tape | 22.1 | −152 | −13 | −27 | −130.5 | −3.7 | **pure odd** symmetric tape |
| Warm Tape | 23.6 | −138 | −13 | −25 | −122.8 | −3.2 | pure odd, slightly more |
| Old Tape | 35.0 | −136 | −10 | −17 | −122.5 | −9.8 | heavier odd, compressed |
| American Tweed Amp | 70.8 | −21 | −3 | −15 | −15.8 | −17.0 | hot amp, heavy gain-comp |
| American Plexi Amp | 61.9 | −27 | −4 | −21 | −20.0 | −18.2 | amp crunch |
| British Rock Amp | 51.1 | −49 | −6 | −19 | −40.3 | −18.4 | odd-leaning amp |
| British Pop Amp | 108.7 | −29 | −0 | −7 | −21.9 | −20.4 | >100% THD (heavy clip) |
| Smooth Amp | 38.1 | −10 | −14 | −29 | **+4.5** | −10.3 | **even-dominant** (H2>H3) |
| Crunchy Amp | 117.3 | −30 | −0 | −5 | −25.5 | −23.7 | hard clip, odd |
| Lead Amp | 121.9 | −27 | −0 | −5 | −23.3 | −25.8 | hot lead, hard clip |
| Screaming Amp | 79.9 | −40 | −6 | −5 | −35.0 | −19.5 | high-gain odd |
| Power Amp | 16.8 | −50 | −16 | −26 | −29.4 | −9.0 | power-section sag |
| Subtle Saturation | 0.3 | −174 | −51 | −68 | −117.6 | −0.0 | symmetric near-clean |
| Gentle Saturation | 21.4 | −150 | −14 | −28 | −129.7 | −3.4 | **pure odd** symmetric |
| Heavy Saturation | 38.4 | −146 | −10 | −16 | −129.6 | −15.1 | pure odd, strong |
| Subtle Transformer | 0.0 | −174 | −88 | −165 | −78.5 | +0.1 | symmetric clean |
| Gentle Transformer | 2.5 | −35 | −36 | −47 | **+2.0** | −0.0 | **even-dominant** (transformer H2) |
| Warm Transformer | 26.4 | −43 | −12 | −22 | −23.3 | −5.7 | odd-leaning transformer |
| Smudge | 0.4 | −74 | −48 | −98 | −25.9 | −4.9 | subtle blur |
| Breakdown | 292.8 | −18 | −13 | +3 | −0.0 | −6.2 | **destructive** (THD≫100%, H5>fund) |
| Foldback | 499.9 | −194 | −11 | +2 | −191.7 | −18.1 | **symmetric WAVEFOLDER** (pure odd, H3/H5/H7 ≈ fund) |
| Rectify | (∞) | +104 | 0 | 0 | +103.3 | −43.1 | **full-wave RECTIFIER** — even-only, freq-doubles, fundamental vanishes (THD undefined) |
| Destroy | (erratic) | −88 | −34 | −36 | −55.9 | −6.5 | **lo-fi decimator/bit-crush** (S&H, 93% repeated samples — see aliasing) |

Distinct curve families (CLEAN): **Tube/Amp/Transformer-warm = asymmetric** (even harmonics, H2 prominent);
**Tape/Saturation/Subtle-Transformer = symmetric** (pure odd, H2 < −120 dBc). Special: **Foldback**=wavefolder,
**Rectify**=rectifier, **Destroy**=sample-rate/bit reducer, **Breakdown/Crunchy/Lead/Pop**=hard clip (THD>100%).
Heavily-driven amp styles apply large internal **gain compensation** (−17 to −26 dB) to keep output sane.

### Drive → THD% (1 kHz, in −6 dBFS, HQ=Superb)
| drive% | 0 | 5 | 10 | 20 | 30 | 40 | 50 | 60 | 70 | 80 | 90 | 100 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Warm Tube | 4.1 | 4.6 | 5.3 | 6.9 | 8.0 | 9.7 | 13.0 | 18.4 | 24.3 | 28.8 | 31.9 | 33.8 |
| Clean Tape | 1.8 | 2.1 | 2.4 | 3.7 | 6.3 | 12.6 | 22.1 | 29.4 | 34.7 | 38.5 | 41.3 | 43.2 |
| Heavy Saturation | 6.8 | 8.7 | 11.3 | 18.0 | 25.8 | 33.0 | 38.4 | 41.9 | 43.9 | 44.9 | 45.3 | 45.5 |
| Foldback | 2.2 | 2.7 | 5.3 | 42.8 | 140 | 173 | 500 | 267 | 240 | 3175 | 238 | 244 |
| Destroy | 3.6 | 4.5 | 5.6 | 8.1 | 6.8 | 13.0 | 2.6 | 34.2 | 11.1 | 65.9 | 32.6 | 33.5 |
Drive 0 % is a real (low) operating point, not bypass. Smooth saturators rise monotonically and saturate
(Heavy Sat plateaus ~45 %). Foldback/Destroy are non-monotonic (folding / decimation artifacts).

### Input-level dependence (memoryless waveshaper signature) — Warm Tube, drive 50 %, 1 kHz
| in dBFS | −36 | −30 | −24 | −18 | −12 | −6 | −3 | 0 |
|---|---|---|---|---|---|---|---|---|
| THD% | 0.6 | 1.3 | 2.5 | 5.0 | 8.1 | 13.0 | 19.6 | 26.1 |
| gain dB | +1.98 | +1.98 | +1.98 | +1.97 | +1.68 | −0.56 | −2.56 | −4.96 |
| H3 dBc | −97 | −85 | −73 | −60 | −33 | −18 | −15 | −12 |
THD climbs monotonically with level; gain compresses as you drive harder — a **fixed nonlinear curve**
(memoryless). Clean Tape behaves identically (0.0 % @ −36 → 34.7 % @ 0 dBFS). No hysteresis attributable
to the nonlinearity (apparent ramp "hysteresis" is the ~20 Hz output HPF phase, not memory).

### Frequency dependence — Warm Tube, drive 50 %, in −6 dBFS
| freq | 50 | 100 | 200 | 500 | 1k | 2k | 4k | 8k |
|---|---|---|---|---|---|---|---|---|
| THD% | 10.2 | 10.0 | 10.5 | 11.2 | 13.0 | 12.0 | 11.7 | 6.2 |
| H2 dBc | −26 | −28 | −27 | −27 | −29 | −28 | −27 | −29 |
Essentially **flat 50 Hz–2 kHz** ⇒ no reactive/frequency-dependent distortion (unlike AS-1's inductor).
8 kHz drop = harmonics filtered/beyond useful range. Curve is frequency-flat → confirms memoryless.

### Aliasing vs `high_quality_mode` (at **SR 48 kHz**, 7 kHz tone, drive 100 %, in −3 dBFS)
Worst non-harmonic alias image, relative to fundamental:
| style | Off | Good | Superb |
|---|---|---|---|
| Heavy Saturation (clean odd) | −14 dBc | −35 dBc | −48 dBc |
| Crunchy Amp | −19 dBc | −39 dBc | −48 dBc |
| Destroy (lo-fi) | +30 dBc (thousands of images) | +31 | +29 — OS does NOT clean it |
`high_quality_mode` = the **internal oversampling** control: each step pushes the alias floor down ~17 dB
(Off→Good→Superb ≈ −34 dB total). At SR ≥ 96 kHz the per-band waveshaper images already sit above Nyquist,
so OS has no audible effect there. **Destroy is an intentional aliaser/decimator** — its broadband junk is
by design and is unaffected by OS (93.6 % consecutive-equal samples ⇒ sample-rate decimation / S&H + mild
bit reduction). Use **Superb** to match the lowest measured alias floor for the clean saturator styles.

### Crossover — recovered behaviourally (CLEAN, solo+sweep @ 48 kHz, 2026-06-22)
The param read floors at 40 Hz for every band; the **audio** is ground truth. Method: N active bands,
all clean (drive 0), `band_N_state=Solo` to isolate each band, sweep a probe tone, find passband edges.
- **Type = Linkwitz-Riley** (constant-power): each adjacent leg is **−6.5 dB at the crossover frequency**
  (measured −6.53 / −6.56 dB at fc=1000), and the legs **sum flat** (no ±3 dB bump/dip across the split —
  Butterworth would bump +3 dB). True in both Minimum-Phase and Linear-Phase (LinPhase also −6.4 dB @ fc).
- **Slope label = measured roll-off** (band_1_xover=1000 Hz, solo each leg, slope ≈ 1 oct into stopband):
  | label | 6 | 12 | 24 | 36 | 48 dB/oct |
  |---|---|---|---|---|---|
  | measured LP leg | −5.5 | −11.0 | −24.3 | −37.0 | −49.3 dB/oct |
  (At low orders the −3 dB points splay around fc — e.g. 6 dB/oct LP −3 dB ≈ 610 Hz, HP ≈ 1330 Hz for
  fc=1000; at 48 dB/oct they tighten to ≈ 800 / 1195 Hz, geomean ≈ fc.)
- **3-band split** (band_1_xover=300, band_2_xover=3000, 24 dB/oct): band1 LP −5 dB @300; band2 bandpass
  −5 dB @300 & @3000; band3 HP −5 dB @3000 — i.e. `band_N_crossover_frequency` is the **shared upper edge**
  of band N. **4-band** (200/1000/5000) reconstructs identically (each crossover −5 to −6 dB, legs sum flat).
- **Default split = 40 Hz floor** (NOT auto-spread in the API): with `num_active_bands≥2` untouched, band1
  LP −3 dB ≈ 38–40 Hz and band2+ carry the full range — the GUI's visual auto-distribution does not write
  the automation params. To get a real split you must set `band_N_crossover_frequency` (writes do take).

### Latency / PDC (host-reported + impulse, CLEAN — 2026-06-22)
Host PDC **IS exposed**: pedalboard `plugin.reported_latency_samples` (no HOST-BLOCKED needed). Confirmed by
matching impulse peak-shift. Reported PDC (samples), `num_active_bands=1`, clean band:
| SR | MinPhase Off / Good / Superb | LinPhase Off / Good / Superb |
|---|---|---|
| 44.1 kHz | 0 / 8 / 9 | 3072 / 3212 / 3220 |
| 48 kHz | 0 / 8 / 9 | 3072 / 3156 / 3164 |
| 96 kHz | 0 / 7 / 8 | 5120 / 5156 / 5164 |
| 192 kHz | 0 / 7 / 8 | 9216 / 9248 / 9256 |
**Minimum-Phase** PDC = 0 (Off) or ~7–9 samp (Good/Superb OS group delay), roughly SR-independent in samples.
**Linear-Phase** PDC is a large symmetric-FIR latency that scales with SR (~3072 @ ≤48 k → 5120 @ 96 k → 9216
@ 192 k for the crossover FIR; +OS adds ~90–150 samp), with pre-ringing. Impulse peak-shift agrees with the
reported value (MinPhase off-by-≤1 = group-delay vs peak-pick; LinPhase exact).

### Feedback (Warm Tube, drive 30 %, 1 kHz, feedback_frequency 250 Hz)
| feedback_amount | 0 % | 50 % | 90 % |
|---|---|---|---|
| 250 Hz tone / fund | −146 dBc | −136 dBc | −37 dBc |
Resonant feedback loop tuned to `feedback_frequency`; only audible at high amounts (amp-style howl/resonance).

## To implement (CLEAN path for product — ES-L)
Multiband saturator = **crossover split → per-band {drive → memoryless waveshaper(style) → resonant
feedback → post tone EQ → parallel mix → level} → sum → OS-quality-matched anti-aliasing**:
- **Waveshaper bank**: fit each style as a static curve from the CLEAN fingerprint table — match THD%,
  H2/H3/H5 ladder and the even/odd ratio. Symmetric families (Tape/Saturation) = odd-only shaper
  (`tanh`/cubic-soft-clip); asymmetric families (Tube/Amp/Transformer) = add even content via DC bias /
  asymmetric clip; **Foldback** = triangle/sine wavefolder; **Rectify** = `|x|`/half-wave; **Destroy** =
  sample-rate decimator + bit quantizer; hard styles (Crunchy/Lead/Pop/Breakdown) = hard clip with the
  measured gain-compensation. Drive→THD and level→THD tables give the curve gain-staging.
- **dynamics**: envelope-follow the input and scale drive (positive ⇒ raise sustained-level drive toward
  peak drive, negative ⇒ reduce it) — reproduce the measured quiet-vs-loud THD spread.
- **Tone stack POST waveshaper**: bass low-shelf ~50 Hz, mid bell ~640 Hz, treble HS ~5 kHz, presence
  steeper HS >5 kHz; ±24 dB each. Output ~20 Hz DC-blocker HPF.
- **Oversampling**: poly-phase, switchable like Off/Good/Superb; target ≥ the Superb alias floor (−48 dBc
  at 7 kHz/48 k) for clean styles; run the waveshaper inside the OS region. Linear-phase crossover optional.
- **Literature**: Yeh/Pakarinen virtual-analog (tube/diode shaping), Zölzer *DAFX* (nonlinear processing,
  wavefolding, distortion), Kahles/Esqueda **antiderivative anti-aliasing (ADAA)** for the hard/folding
  curves, **Linkwitz-Riley** band split (measured-confirmed: −6 dB/leg @ fc, sum-flat, 6–48 dB/oct) with an
  optional linear-phase variant (symmetric-FIR, large PDC).
- Build from CLEAN tables + public literature only. The REF block below is static-disasm corroboration,
  quarantined and never shipped — every product number stays from the CLEAN fingerprint tables.

## REF — static-disasm corroboration (TAINTED / reference-only — NEVER ship; see quarantine)
> Provenance: **REF (TAINTED)**. Ghidra 12.1.2 / radare2 RTTI static decompile of the arm64 VST3 slice,
> EULA clean-room — quarantined under `private-research/_quarantine_disasm/Saturn2/`. Reference/education
> ONLY; the product path above stays 100% CLEAN. Coefficients/addresses live ONLY in quarantine.
- Stripped (6 ext syms) but RTTI/cstring debug names survived. Recovered the saturation kernel classes
  (`SoftClipper`, `FunctionTableClipper`+`Softube::IGetCurveData`, `FoldBackClipper`, `BitCrusher`;
  primitives `WaveShaperVec[B/PB/LL]::vectorClip{ArcTan,DivAbs,Sine,Polynome2/3,Tube,Triode,Rectify,
  TanHyperbolic}Fast`), the `*Style` model roster, the multiband `CrossoverFilter`/`AnalogFilterPrototype`,
  and the `Convolver` oversampler.
- **Confirmed the waveshaper is a memoryless per-style `switch`** (fn `0x16a720`): drive-prescale →
  soft-knee core/remainder split → 14-case shape (atan/logistic/divabs/algebraic/tanh/identity/sine/
  poly2-5/Tube/Triode/Rectify) → 2-table blend → ratio `powf`. **Byte-identical shaper core to Pro-G**
  (same cases + same hard-poly constants) → strong cross-check of the CLEAN harmonic fingerprints.
  Asymmetry = bias wrappers (even harmonics); Softube/analog amps+cabinets = runtime-built LUT path;
  Foldback = smooth `r·sinf(r·x²)`; Destroy = `exp2f(24−bits)` quantize + decimate. Crossover =
  analog-prototype biquad (complex s→z, slope-selectable, phase-compensated). OS = partitioned/FFT
  Convolver (no fixed FIR `__const`). Full detail + coeff tables: `_quarantine_disasm/Saturn2/`.
- Nothing above changes the CLEAN spec — it independently confirms the memoryless-waveshaper finding,
  the style families, and the Linkwitz-Riley-class crossover that were already measured.

---
Provenance tags: **CLEAN** = black-box measurement (`saturn2_sysid.py`, pedalboard) / self-reported param
metadata / public DSP literature / own voicing — all product-safe. **REF** = the single static-disasm
corroboration block above (Ghidra/RTTI, quarantined under `_quarantine_disasm/Saturn2/`, never shipped).
