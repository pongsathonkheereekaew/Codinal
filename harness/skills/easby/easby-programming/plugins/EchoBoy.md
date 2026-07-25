# EchoBoy — Soundtoys (delay / multi-style echo)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Delay — multi-style (tape / analog / digital / lo-fi / chorus) echo, single / dual / ping-pong / rhythm |
| Tech | C++ VST3, shared "Soundtoys" static framework (one plugin per process). AAX = PACE; VST3 = pedalboard-hostable |
| Binary | universal (x86_64 + arm64) MH_BUNDLE, 38 MB; not measured statically (CLEAN-only task) |
| Provenance | **CLEAN** — black-box measurement (pedalboard). Style-list character = public/marketing (tagged). No disasm. |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (`Tools/st_sysid.py`, `Tools/delay_probe.py`, `out/EchoBoy_*.json`) |

## Signal chain
```
x → inputgain → [echo engine: Single / Dual / Ping-Pong / Rhythm]
                  per echo: fractional delay line (time) → tape/analog/digital STYLE model
                            (saturation + HF/LF coloration + wow/flutter) → feedback (×g, through style stage)
              → lowcut (HP) / highcut (LP) tone → wet
   x (dry) ──────────────────────────────────────────────────────────→ ┐
   wet ────────────────────────────────────────────────────────────────┴─ mix → outputgain → y
```
Two delay generators (echo1, echo2) + a separate Rhythm engine (multi-tap pattern). `mode` selects topology; `style` selects the colour model applied inside the delay/feedback loop.

## Per-stage formula (tag each CLEAN / REF)
- **Delay time → actual** (CLEAN): for the labelled-ms control (`echo*time_msec`, mode = Time), **actual ≈ displayed ms** across the useful range. Measured ratio meas/set: 100 ms→0.96, 250→0.983, 500→0.996, 1 k→0.999, 3 k→0.999, 7.5 k→1.001, 15 k→1.000. Only very short sets read low (38 ms→0.90, 10 ms→0.61) — min-buffer / fractional-tap floor. Treat as a **true linear ms delay** ≥ ~50 ms. Reported PDC latency = **32 samples** (`reported_latency_samples`).
- **Feedback** (CLEAN): `feedback` ∈ [0, 1.25] (125 %). Steady-state decay per repeat (Studio Tape, sat 0), and inferred per-repeat loop gain g = 10^(decay/20):
  | fb | dB/repeat | g (lin) |
  |---|---|---|
  | 0.25 | −14.4 | 0.19 |
  | 0.50 | −8.6 | 0.37 |
  | 0.75 | −5.1 | 0.56 |
  | 0.94 | −2.84 | 0.72 |
  | 1.00 | −1.89 | 0.80 |
  | 1.10 | growing (self-osc onset) | >1 |
  | 1.25 | runaway | ≫1 |
  Note g < fb numerically and **g stays < 1 even at fb = 1.0** — the in-loop tape saturation/compression bleeds energy, so the echo still decays at "100 %". Self-oscillation needs ~110 %+. (Repeat count grew monotonically 8→14→22→40→60 over fb 0.25→1.0, confirming real recirculation.)
- **Saturation (Studio Tape)** (CLEAN): `saturation_db` ∈ [0,24] = drive into a **symmetric soft-shaper** (odd-harmonic, tape-style). THD of the wet echo: 0 dB→0 %, 6→0.12 %, 12→0.46 %, 18→1.36 %, 24→2.95 %. H3 dominant (−90→−30 dB as drive rises), H2 negligible (~−105 dB ⇒ symmetric, no even harmonics), H5 rising. Gentle, program-level compression rather than hard clip.
- **Highcut (LP tone)** (CLEAN): `highcut` 0→1 = progressive gentle low-pass on the wet path. At highcut=1.0 (rel 1 k): 4 k −16.8, 8 k −20.8, 12 k −23 dB; ~1-pole-ish slope. Even at highcut=0 the Studio-Tape model already loses ~−6 dB @ 8 k (intrinsic tape HF roll-off).
- **Lowcut (HP tone)** (CLEAN): `lowcut` 0→1 = progressive gentle high-pass. At lowcut=1.0: 50 Hz −28.6, 100 −23, 250 −15.4 dB (~6 dB/oct). Removes rumble build-up in repeats.
- **Wow/flutter (Studio Tape)** (CLEAN): per-pass pitch instability that **compounds with feedback**. 1 kHz carrier instantaneous-frequency spread (p5–p95): single pass (fb 0) = 0.13 Hz (~0.2 cents, ~clean); fb 0.7 = 0.14 Hz; fb 0.94 (many repeats) = **18.3 Hz ≈ ±16 cents**, std 6.5 Hz. Dry reference = 0.001 Hz (host stable). ⇒ a genuine modeled tape-transport wobble in the echo path.
- **Style models** (CLEAN list; per-style DSP fingerprint **unmeasured** — see Open questions): `style` enum has **28** entries: Master Tape, Studio Tape, Space Echo, Tube Tape, Cheap Tape, DM-2, TelRay, Binsonette, Memory Man, AM Radio, FM Radio, Shortwave, Telephone, Transmitter, Digital Delay, Analog Delay, Digital/Analog/CE-1 Chorus, Vibrato, Saturated, Fat, Distressed, Limited, Distorted, Queeked, Ambient, Diffused, Splattered, Verbed, Edited Style. Each = a different saturation curve + HF/LF colour + mod amount applied in the loop (public/marketing description; only **Studio Tape** measured here, the boot default).

## Why / design rationale (music ↔ code)
- **True-ms delay line (linear time map)** → predictable, dialable echo times → unlike the PrimeTime-modeled PrimalTap, EchoBoy is a "studio" delay where the labelled time is the real time; musicality comes from the style/feedback colour, not from delay-range quantization.
- **Feedback into the saturation/colour stage (not before it)** → each repeat is re-coloured: HF rolls off and grit accumulates pass-over-pass → the classic "echoes get darker and warmer as they fade" tape sound. Placing the shaper *inside* the loop is what makes the trail evolve.
- **g < 1 at fb = 1.0 via in-loop compression** → you can crank feedback to "100 %+" for long sustained washes without instant runaway → the tape model self-limits, giving the prized "almost-infinite but controlled" repeat. Past ~110 % it tips into self-oscillation on purpose (sound-design tool).
- **Odd-harmonic symmetric saturator** → tape-like 3rd-harmonic warmth/thickening without the buzzy even-harmonic edge of asymmetric clipping → musical density on each repeat.
- **Gentle 1-pole tone cuts** → broad, musical darkening/thinning of the trail rather than surgical EQ → keeps repeats sitting under the dry signal.
- **Wow/flutter that compounds with feedback** → long feedback washes "smear" into a chorused, detuned cloud → the lush, slightly-out-of-tune character of real tape echo at high regeneration.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| inputgain_db | dB | −24…+24 | pre-engine gain |
| outputgain_db | dB | −24…+24 | post-mix gain |
| mix | % | 0…100 | dry/wet (0=dry, 100=wet-only) |
| mode | enum | Single, Dual, Ping-Pong, Rhythm | topology |
| echo1mode / echo2mode | enum | Time, Note, Dotted, Triplet, Beats | per-echo sync; **only Time measurable** (no host transport) |
| echo1note / echo2note | enum | 1/1…1/64 + trip/dot (21) | note value for sync modes (tempo-sync: unmeasured) |
| echo1time_msec / echo2time_msec | ms | 0…15000 | delay time (Time mode) — linear, actual≈displayed ≥50 ms |
| feedback | ratio | 0…1.25 | regeneration; g<1 to ~1.0, self-osc ≳1.10 |
| primenumbers | bool | Off/On | offsets dual times to prime ratios (avoid flutter-echo combing) |
| groove / feel | ratio | −0.25…+0.25 | rhythmic swing / micro-timing of taps (best with sync — unmeasured musically) |
| saturation_db | dB | 0…24 | in-loop drive; THD 0→~3 % (odd-harmonic) |
| lowcut | norm | 0…1 | wet HP, ~6 dB/oct, up to −29 dB @50 Hz |
| highcut | norm | 0…1 | wet LP, gentle, up to −23 dB @12 kHz |
| rhythmmode | enum | Time, Note, Dotted, Triplet, Pattern, CustomTime, CustomBeats | Rhythm-engine sync (tempo-sync: unmeasured) |
| rhythmnote | enum | 1/2…1/64 + trip/dot | Rhythm engine note |
| rhythmtime_msec | ms | 0…30000 | Rhythm tap base time |
| rhythmrepeats | count | 1…16 | number of pattern taps |
| rhythmdecay_db | dB | 0…40 | per-tap level falloff across the pattern |
| style | enum | 28 models | colour model (only Studio Tape measured) |
| tempo_bpm | BPM | 30…240 | internal tempo for sync (no host transport in pedalboard) |

## CLEAN measurements (summary tables above)
- Delay-time map: linear, actual≈displayed for ≥50 ms; PDC 32 samp.
- Feedback decay law: table above (g vs fb); self-osc ≳110 %.
- Saturation THD vs drive: 0/6/12/18/24 dB → 0/0.12/0.46/1.36/2.95 % (odd-harmonic).
- Highcut/lowcut transfer tables above (gentle 1-pole).
- Wow/flutter: fb 0.94 → ±16 cents spread; dry stable.

## To implement (CLEAN-only path for ES-L / ES-X)
- **Fractional-delay line** with linear true-ms time control (clamp tiny times to a min-buffer floor); 32-sample PDC.
- **In-loop colour stage**: symmetric soft-saturator (drive→odd harmonics; e.g. `tanh`-class or polynomial, tuned to ~3 % THD at full drive) + 1-pole LP (HF roll, default tape loss ~−6 dB @8 k) + 1-pole HP, **placed inside the feedback path** so repeats evolve.
- **Feedback law**: map a 0–125 % control to loop gain with in-loop compression so g stays ≤1 up to ~100 % and tips to self-oscillation only past ~110 % (compressor/limiter in the loop, or a soft-sat that bleeds energy).
- **Wow/flutter**: slow random/periodic delay-time modulation (sub-Hz wow + few-Hz flutter), small depth (~±a few cents/pass), that visibly accumulates over many repeats.
- Multiple style presets = different (saturation curve, HF/LF cut, mod depth) tuples on the same engine.
- tempo-sync (Note/Dotted/Triplet/Beats/Rhythm) = derive ms from host BPM × note value; **unmeasured here (needs REAPER transport)**.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). Style-list *names* = public/marketing. **REF** = none (no disasm performed).
