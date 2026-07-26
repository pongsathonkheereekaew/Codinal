# Twin 3 — FabFilter (Subtractive synthesizer — instrument)

| | |
|---|---|
| Vendor / ver | FabFilter · Twin 3 · VST3 **instrument** (`is_instrument=True`) · no DRM |
| Type | **Subtractive synthesizer** — 4 oscillators (default GUI shows 3), 4 multimode filters (default 2), ring mod, deep mod matrix (XLFO step-LFOs + multi-segment EGs + env-followers + XY macros), built-in FX chain (drive / delay / reverb / chorus / phaser / compressor) + arpeggiator |
| Tech | VST3 instrument (FabFilter), C++. Universal Mach-O bundle (x86_64+arm64), **STRIPPED** (6 external syms — only CF/CoreServices help symbols), **NO PACE/iLok**. Only system frameworks (Cocoa/Metal/AudioToolbox/libz). Static is a wall → **BLACK-BOX ONLY** |
| Provenance | **100% CLEAN** — black-box measurement via pedalboard (MIDI render). No r2/Ghidra used or needed. Every fact below is CLEAN unless marked "open" |
| Measured on | Twin 3 · SR 48 kHz · pedalboard 0.9.17 · `Tools/twin3_sysid.py` (host MIDI render) · 2026-06-22 (osc/filter/env + mod-matrix/FX/XLFO pass) |
| Source | `private-research/Twin3/` — `Tools/twin3_sysid.py`, `docs/harness-notes.md` |

## MIDI-render method (load-bearing — pedalboard 0.9.17, no mido)
```python
y = p(midi_messages, duration, sample_rate, num_channels=2)   # -> float32 (2, N)
```
`midi_messages` = list of mido-DUCK objects: each exposes `.bytes()` (a **METHOD** returning
`[status,d1,d2]`) and `.time` (float **seconds**). Shim in the harness; `note_on=0x90`, `note_off=0x80`.
Example: `p([note_on(57,100,0.0), note_off(57,1.0)], duration=2.0, sample_rate=48000, num_channels=2)`.

## Signal chain (CLEAN — confirmed by isolation + routing tests)
```
 per voice (poly up to 64, mono, or per-oscillator):
   OSC 1..4  (waveform, detune, scale-octave, PW, hard-sync, level, pan, phase-sync)
        │  (+ ring mod on osc pairs 1·2 and 3·4)
        ▼
   MIX  ──► FILTER 1..4  (routing: Serial = cascade │ Parallel = sum │ Per-Oscillator)
                 each: shape(7) × style(11) × slope(6/12/24/48) × freq × peak(reso) × pan
        ▼
   AMP  (eg_main = DAHDSR amplitude envelope; level)
        ▼
 ── voices summed ──►
   DRIVE (waveshaper; routing Pre/Post FX) → DELAY (4-band EQ'd, ping-pong, sync)
        → REVERB → CHORUS → PHASER/FLANGER → COMPRESSOR → output_volume / output_pan / stereo
 MOD: 100-slot matrix routes {XLFO ×6 step-seq LFOs, EG ×6, Env-Followers ×4, XY ×6,
      MIDI sources ×10} → any of 299 targets (osc/filter/FX/mod-source/slot-level).
      Slot amount = unipolar 0..1 + inverted flag. Arpeggiator feeds notes.
```
**Serial vs Parallel proven**: LP@300 ∩ HP@2000 → Serial rms 0.00001 (gap), Parallel rms 0.037 (both bands).

## Oscillator waveforms (CLEAN — osc1 solo, note 57 = 440.0 Hz, FFT harmonic ladder, dBc)
`osc_N_wave_form` enum (8): Sawtooth / Square / Square Pure / Triangle / Triangle Pure / Sine / White Noise / Pink Noise.
| waveform | H2 | H3 | H4 | H5 | H6 | H7 | ladder identity |
|---|---|---|---|---|---|---|---|
| **Sine** | −130 | −152 | −146 | −160 | −154 | −164 | pure (numerical floor) |
| **Sawtooth** | −6.0 | −9.5 | −12.0 | −14.0 | −15.6 | −16.9 | **ideal 1/n** (−20·log10 n); band-limited, anti-aliased |
| **Square** | −15.6 | −9.5 | −21.6 | −14.0 | −25.1 | −16.9 | odds = 1/n; evens present −16..−31 (slightly asymmetric/analog) |
| **Square Pure** | −104 | −9.5 | −103 | −14.0 | −95 | −16.9 | **odd-only ideal** square (evens at floor) |
| **Triangle** | −43.0 | −45.8 | −49.1 | −51.0 | −52.6 | −54.0 | rounded/soft variant (steep rolloff) |
| **Triangle Pure** | −49.0 | −19.0 | −55.0 | −27.7 | −58.6 | −33.5 | **ideal 1/n²** odd triangle |
| **White Noise** | flat spectrum (tilt +0.6 dB across 100 Hz–15 kHz) |
| **Pink Noise** | −3 dB/oct tilt (+20.4 dB low-vs-high over the test bands) |

Interpretation: **"Pure" = mathematically ideal/symmetric** (odd-only square / 1/n² tri, BLEP-style anti-alias);
non-Pure = a "warmer" rounded analog-flavoured variant. Saw/square/tri are anti-aliased (no images measured at 440 Hz).
- **PWM** (`osc_N_pulse_width` 0..1): on Square, H2 rises −15.6→−3.3 dBc as PW 0→0.49 — real duty-cycle PWM (even harmonics emerge).
- **Hard sync** (`osc_N_sync` 1.0..4.0): spectral centroid 3629→5206 Hz over ratio 1→4 — adds upper harmonics/formants.
- **Tuning**: with mod matrix cleared, note 57 → exactly **440 Hz** at `master_scale=8'`. `master_scale` (32'/16'/8'/4') shifts the whole keyboard by octaves (16' = one octave down). `osc_N_scale` = ±octave per osc; `osc_N_detune` ±12 semitones.

## Filter (CLEAN — saw transfer-function measurement, filter_1, LP, "Classic" style)
`filter_N_shape` (7): Low Pass / High Pass / Band Pass / Bell / Low Shelf / High Shelf / Notch.
`filter_N_slope` (4): 6 / 12 / 24 / 48 dB/oct (= 1/2/4/8-pole nameplate).
`filter_N_style` (11): Classic / Gentle / Raw / Tube / Metal / Easy Going / Smooth / Hard / Hollow / Extreme / Clean.
`filter_N_freq`: 4.8 Hz .. 75.6 kHz. `filter_N_peak` (resonance): −1 .. +1 (bipolar).

Authority confirmed: HP@15kHz → rms 0; BP@100 → rms 0.001; LP sweeps cleanly **once mod matrix is bypassed**.
Measured LP attenuation (transfer vs fc=22 kHz reference; fc=500 Hz):
| slope (nameplate) | T@2fc | T@4fc | T@8fc | measured asymptote |
|---|---|---|---|---|
| 6 dB/oct  | −4.6 | −9.6 | −14.8 | ~−5 dB/oct (1-pole) ✓ |
| 12 dB/oct | −13.1 | −31.5 | −49.0 | ~−17 dB/oct near cutoff (2-pole) |
| 24 dB/oct | −23.3 | −39.7 | −61.7 | ~−22 dB/oct |
| 48 dB/oct | −32.0 | −51.7 | −72.7 | steepest (≈ floor by 8fc) |

Higher-order settings dip more at the labelled corner (T@fc: 6→0, 12→−5, 24→−10, 48→−17 dB); the
"Classic" −3 dB point sits slightly **below** the labelled fc (Q/topology dependent). The 11 styles are
measurably distinct in passband gain/rolloff (Classic flattest passband −0.5 dB; others ≈+2 dB) — the
"Tube/Metal/Raw/Extreme" styles add nonlinearity at high drive/resonance (**character/THD per style = open**).

**Resonance** (`filter_1_peak`, LP 24 dB/oct, magnitude of the band at fc rel. passband):
| peak | −1.0 | 0.0 | +0.25 | +0.5 | +0.75 | +0.9 | +1.0 |
|---|---|---|---|---|---|---|---|
| reso bump | −35 (damped) | −35 (neutral) | −26 | −22 | −16 | **+12** | **+15 dB** |
Bipolar: **−1..0 = damping/no resonance, 0 = neutral, 0..+1 = resonance up to ~+15 dB** (near self-oscillation at max).

## Amplitude envelope `eg_main` (CLEAN — DAHDSR; drive raw_value 0..1, MEASURE the time)
Stages: delay · attack · hold · decay · sustain · release, each ADR segment also has a **slope** (curve −1..+1).
NB the displayed time **wraps ms→s** (`500.10`=500 ms, `1.75`=1.75 s) — set `raw_value` and measure.
| raw | ATTACK t(10→90%) | RELEASE t(90→10%) | DECAY t(→sustain) |
|---|---|---|---|
| 0.0 | 1.6 ms | 2.0 ms | (min) |
| 0.2 | 8.9 ms | 172 ms | 190 ms |
| 0.3 | 32 ms | 301 ms | — |
| 0.5 | 259 ms | 644 ms | 718 ms |
| 0.6 | 400 ms | 859 ms | 957 ms |
| 0.7 | 1399 ms | 1712 ms | 1907 ms |
| 0.8 | 2406 ms | 2580 ms | — |
Full range ≈ **0.1 ms .. ~25 s**, roughly exponential in the normalized control.
**Sustain** (`eg_main_sustain`, dB): measured = set, **dB-linear** (set −3/−6/−12/−24/−48 → measured −3.7/−6.6/−12.6/−24.6/−48.6, const ~−0.6 dB offset = window/smoothing). `eg_main_level` −2..+2; `eg_main_range` Normal/Neutral-Sustain; `eg_main_triggering` MIDI/Side-Chain; `eg_main_threshold` −90..0 dB (side-chain trigger).

## Modulation matrix (CLEAN — `Tools/twin3_sysid.py matrix`)
**100 slots** (`slot_1..100_*`), each = {source, target, level(amount), bypassed, inverted}. Mechanics
proven on a clean slot with a HELD constant source (EG with instant-attack / 0 dB-sustain, or XLFO with all
16 steps=+1) so the target receives a steady offset = `source_value × amount`.

**Slot amount** (`slot_N_level`): **unipolar 0..1** in display, NOT bipolar. Concave taper from the underlying
raw control (raw 0.5 → amount 0.16; raw 0.7 → 0.36; raw 1.0 → 1.0) — fine control at low depths.
**Bipolarity** comes from `slot_N_inverted` (Normal/Inverted) and/or a bipolar source, **not** from a signed amount.

**Depth law — TARGET = Filter Freq** (white-noise carrier, LP −6 dB corner = cutoff pointer, base fc=1000 Hz,
source = EG held +1):
| amount (disp) | 0.00 | 0.16 | 0.36 | 1.00 | inverted @1.0 |
|---|---|---|---|---|---|
| Δ cutoff (octaves) | 0.00 | **+1.09** | **+3.05** | **+4.88** (rails ~19 kHz) | **−2.15** |

Full-scale (amount 1.0 × source +1) ≈ **+5 octaves** of cutoff; roughly proportional to displayed amount,
compressive only as it rails at fmax. `inverted` cleanly mirrors the offset below the base. Cutoff mod target
is **exponential (octaves/V)** — equal amounts = equal octaves.

**Depth law — TARGET = Osc Level** (sine, base osc level −48 dB, source = EG held +1):
| amount (disp) | 0.00 | 0.07 | 0.16 | 0.36 | 1.00 |
|---|---|---|---|---|---|
| Δ level (dB) | 0.0 | +25.4 | +32.1 | +39.0 | **+47.8** (rails at 0 dB) |

Level mod is in the **dB domain**, wide range (full-scale ≈ +48 dB from this base, rails at the 0 dB ceiling).
Cross-source check: EG-held and XLFO-all-+1 both drive the same target identically (mechanics source-agnostic;
absolute depth differs with the source's own `level` scaling). Targets carry the target param's native unit/law
(Freq=octaves, Level=dB, Pan/Time/etc. = that control's range).

**Source enum (39 = 38 routable + `< Source >`)**: `XY 1..6 Hor`, `XY 1..6 Ver` (12), `XLFO 1..6` (6),
`EG 1..6` (6), `EF 1..4` (4), `MIDI 1..10` (10).
**Target enum (300 = 299 routable + `< Target >`)** — every modulatable destination:
- Global: Master Tune, Portamento, Output Volume, Output Pan, Stereo, Unison Spread.
- Osc 1..4 × {Detune, Pulse Width, Sync, Level, Pan} (20).
- Filter 1..4 × {Freq, Pan, Peak} (12) + Filter Freq Offset, Filter Peak Offset.
- FX: Reverb {Amount,Time,Brightness,Pre Delay}; Delay {Amount,Time,Offset,Time Pan,Feedback} + Delay Filter 1..4
  × {Freq,Pan,Peak}; Chorus {Amount,Rate,Depth,Delay}; Phaser {Amount,Rate,Depth,Feedback,Shift}; Drive {Amount};
  Compress {Amount,Threshold,Attack,Release}.
- Mod sources as targets (meta-mod): XLFO 1..6 × {Level,Freq,Freq Offset,Balance,Glide,Phase Offset} (36);
  EG 1..6 × 11 fields (66); EF 1..4 × {Level,Attack,Release} (12); MS 1..10 Level (10);
  **Slot 1..100 Level** (100 — a slot can modulate another slot's amount).

## FX chain (CLEAN — `Tools/twin3_sysid.py fx`; surfaces dumped in §Parameters)
Block order as declared by the target enum: **Reverb → Delay → Chorus → Phaser → Drive → Compress**, with
`drive_routing` (Pre FX / Post FX) the one explicit reorder (drive before vs after the rest). NB `delay_time`,
`reverb_time`, `compress_release` **display-wrap ms→s** (set `raw_value`, read display); `delay_feedback` 0..200 %
exceeds unity (regenerating/runaway). Each FX confirmed by a measured probe:
| FX | key params | measured confirmation |
|---|---|---|
| **Drive** | amount 0..100 %, routing Pre/Post-FX | waveshaper: THD on 440 Hz sine **1.7→7.2→16.4→20.9→18.1 %** at amt 0/25/50/75/100 (folds back >75 % = saturation) |
| **Delay** | amount(mix), time **10 ms..5 s**, sync (Free/½/¼/⅛/1÷16), feedback 0..200 %, ping_pong (Off/L-R/R-L), offset, time_pan, **+4-filter EQ** (shape7/style11/slope4 each, routing Serial/Parallel/Per Delay) | echo spacing = displayed time **exactly** (147.7/259.5/435.1 ms); feedback regenerates train |
| **Reverb** | amount, time **200 ms..20 s**, brightness 0..100 %, predelay | −40 dB tail grows **0.33→1.14→1.83 s** as time 0.2→3→6.9 s |
| **Chorus** | amount, mode Single/Double, rate **0..10 Hz**, depth 0..100 %, delay 0.5..30 ms | pitch-mod **stereo widener**: L/R corr collapses **0.999→0.096→0.025** as depth 0→100 % (Double) |
| **Phaser** | mode Phaser/Flanger, rate **0..25 Hz**, depth, feedback ±100 %, shift, amount | sweep rate = displayed Hz **1:1** (1.0→1.00, 2.0→2.01, 5.0→5.01 Hz) |
| **Compressor** | amount, auto_gain, threshold −30..0 dB, attack 0..250 ms, release **0..2.5 s** | downward comp: out RMS **−18.1→−22.1→−29.7→−34.6 dBFS** as threshold 0→−30 dB (auto_gain off) |
| **Arpeggiator** | enabled, sync (5), rate 0.25..20 Hz, rate_offset 0.5..2, groove 20..180 %, legato 10..100 %, note_order (Up/Down/Up÷Down/As Played/Random), transpose (Off/1/2 oct), latch (Off/Held/Full), lock, follow_host_position | feeds notes to the voice (structural; not signal-measured) |

## XLFO (step-sequencer LFO — CLEAN — `Tools/twin3_sysid.py lfo`)
Each XLFO is a **16-step sequencer**, NOT a classic shape-LFO — there is **no waveform/shape enum**; the waveform
IS the 16 `step_value`s (0..1 each). `xlfo_N_frequency` (display Hz, **0..500 Hz**) = the **cycle rate of the whole
16-step sequence** — confirmed **1:1** by routing XLFO→Osc Level and counting amplitude pulses (set 1.0/2/4/8/16 Hz
→ measured 1.00/2.00/4.00/8.00/16.00 Hz). `xlfo_N_glide` (−1..+1) sets inter-step smoothing (−1/0 = steps merge;
+1 = transitions/sub-steps emerge); per-step `glide` + `glide_function` (Linear/Sqr/Sqrt/Sine) shape each ramp;
`random` (Fixed/Random) per step. `sync_mode` (Free + 11 musical divisions) tempo-locks; `midi_trigger`
(Off/Retrigger/Legato); `balance` (step duty), `phase_offset`, `frequency_offset` (0.5..2 ratio).

## Parameters (CLEAN — 1293 total; grouped. enum sizes in parens)
**Master/voice**: master_tune (±12 st), master_scale (32'/16'/8'/4'), portamento (0..~25 s) + portamento_legato,
total_voices (1..64), unison_voices (1..64), unison_spread (0..100 %), polyphony (Mono/Poly/Per-Oscillator),
stereo (0..200 %), output_volume (−inf..+10.8 dB), output_pan, high_quality_mode, tuning_enabled, host_bypass.

**Oscillator ×4** (`osc_1..4_*`, 10 each): detune (±12 st), scale (−1..+3 oct, 5), wave_form (8, table above),
sync (1..4 hard-sync), pulse_width (0..1 PWM), level (−inf..0 dB), pan (−1..+1), phase_sync (bool), enabled, used.
`ring_modulation_1_2_enabled`, `ring_modulation_3_4_enabled` (ring mod on osc pairs).

**Filter ×4** (`filter_1..4_*`, 9 each): freq (4.8 Hz..75.6 kHz), pan, peak (−1..+1 reso), style (11), shape (7),
slope (4), enabled, used. Global: filter_routing (Serial/Parallel/Per-Oscillator), filter_freq_offset (±oct),
filter_peak_offset (±100 %).

**Envelope generators** (`eg_main` = amp; `eg_2..` = mod EGs, 13 fields each): level (−2..+2), delay (0..1000),
range, threshold (−90..0 dB), triggering (MIDI/Side-Chain), attack (0.1 ms..25 s), attack_slope (−1..+1),
decay, decay_slope, sustain (−inf..0 dB), hold (0..1000), release, release_slope.

**Mod sources** (38 routable + a `< Source >` placeholder = 39 enum entries):
- **XLFO ×6** (`xlfo_1..6_*`, 73 params each = 438): 16-step sequencer LFOs. Top level: level (−2..+2),
  frequency (0..500 Hz = **cycle rate**), frequency_offset (0.5..2), balance (0..1), phase_offset (0..1),
  glide (−1..+1), sync_mode (12: Free/16/8/4/2/1/1÷2…1÷64), midi_trigger (Off/Retrigger/Legato), snap.
  Each of **16 steps**: value (0..1 disp), glide (0..1), glide_function (Linear/Sqr/Sqrt/Sine), random (Fixed/Random).
- **EG ×6** (`eg_main`=amp + mod EGs): DAHDSR, 13 fields each (see envelope section).
- **Env followers ×4** (`ef_1..4`): level (−2..+2), mode (Envelope/Transient), attack, release (audio-driven).
- **XY controllers ×6** (`xy_controller_1..6`): hor, ver (−1..+1), mode (Slider/XY), range (Positive/Centered). Macro XY pads.
- **MIDI sources ×10** (`midi_source_1..10`): input (Mod Wheel/Pitch Bend/Velocity/Aftertouch/KB Track/Controller),
  level (−2..+2), controller_number (0..127), response_curve (Linear/Exp/Log/Sqr/Sqrt/Sine), range (Neg/Centered/Pos).

**Mod matrix** (`slot_1..100_*`, 5 fields = 500 params): source (39 enum), target (300 enum = 299 routable +
`< Target >`), **level = unipolar amount 0..1** (display; concave taper from raw), bypassed (Normal/Bypassed),
inverted (Normal/Inverted). See **Modulation matrix** section below for the measured depth law + full enums.

**FX chain** (surface + measured confirmations — see **FX chain** table below). Default factory patch ships with
drive/delay/reverb/chorus enabled; `Tools/twin3_sysid.py` clears all 100 slots + all FX before probing.

**Arpeggiator**: enabled, sync (5), rate (0.25..20 Hz), groove (20..180 %), legato, transpose (3),
note_order (Up/…5), latch, lock, follow_host_position.

## CLEAN measurements summary
Oscillator harmonic ladders (table), PWM H2 ramp, sync centroid shift, tuning (440 Hz @8'), filter
authority + LP transfer/slope table, resonance bipolar curve, amp DADSR raw→time calibration, dB-linear
sustain, Serial/Parallel routing nulls; **mod-matrix depth law** (Filter-Freq ≈+5 oct full-scale, Osc-Level
≈+48 dB, unipolar amount 0..1 + invert, 39 src/300 tgt enumerated); **FX confirmations** (drive THD, delay
echo=disp-time, reverb tail, chorus L/R-decorrelation, phaser rate 1:1, compressor gain-reduction, order);
**XLFO** cycle rate=frequency 1:1 + glide polarity. All re-runnable via
`Tools/twin3_sysid.py {params|osc|filter|env|matrix|fx|lfo|all}`.

## To implement (CLEAN path for product — own voicing + public DSP literature)
A subtractive-synth voice = **anti-aliased oscillators → multimode filter → DADSR amp**, plus a mod matrix.
- **Oscillators**: BLEP / PolyBLEP band-limited saw/square/triangle to match the measured 1/n (saw), odd-1/n
  (square), 1/n² (triangle) ladders with no aliasing (Välimäki & Huovilainen; "Antialiasing Oscillators in
  Subtractive Synthesis", IEEE SPM 2007). Offer "Pure" (ideal/symmetric) vs warm (rounded) variants; PWM via
  two-BLEP duty offset; hard-sync via BLEP at the reset. Sine = pure; white = uniform, pink = −3 dB/oct (Voss-McCartney).
  General reference: Pirkle, *Designing Software Synthesizer Plugins in C++* (oscillators, modulation, voice arch).
- **Filter**: virtual-analog state-variable / ladder with selectable LP/HP/BP/notch/shelf/bell and bipolar
  resonance (damped→self-osc), zero-delay-feedback topology. Literature: Zavalishin, *The Art of VA Filter
  Design* (TPT SVF & ladder, resonance, nonlinear "drive" in the feedback path); Moog-ladder & SVF models.
  Slope = cascade 1/2/4/8 poles. Style/character (Tube/Metal/Raw) = saturation in the filter path (model the
  per-style passband-gain + nonlinearity from CLEAN black-box re-measurement before shipping).
- **Amp + mod**: DADSR with per-segment curve (slope); exponential time mapping 0.1 ms..25 s; dB-linear sustain.
  **Mod matrix** = 100 slots, source(38)×target(299)×**unipolar amount 0..1**(+invert flag for bipolarity). Apply
  the modulation in the **target's native domain/law**: Freq targets = exponential (≈ amount×source×5 octaves
  full-scale, equal-octaves-per-step), Level targets = dB-domain, others = that control's range. Sources sum into
  the target (each slot adds source_value×amount). **XLFO** = 16-step sequencer (step values = the waveform;
  `frequency` Hz = whole-sequence cycle rate, 1:1; per-step glide+glide_function Linear/Sqr/Sqrt/Sine; sync to
  tempo). Plus multi-trigger EGs (6), env-followers (4), XY macro pads (6), MIDI sources (10).
- **FX**: standard drive (antiderivative-AA waveshaper), delay (with EQ + ping-pong + sync), algorithmic reverb,
  chorus/phaser/flanger, compressor — all from public literature (Zölzer, *DAFX*) + own voicing.
- Build from CLEAN tables + public DSP only. Re-measure each curve black-box and null against `twin3_sysid.py`.

### Open questions (measured-only; not invented)
- Exact filter **style** nonlinearity / THD curves (Tube/Metal/Raw/Extreme) — needs a per-style drive/THD sweep.
- Per-style precise −3 dB corner vs labelled fc, and exact Q at each `peak` value (only the resonant-bump
  magnitude was measured, not the full complex transfer).
- Oscillator anti-aliasing algorithm (BLEP vs minBLEP vs other) — inferred from clean ladders, not identified.
- FX block order declared by the target enum (Reverb→Delay→Chorus→Phaser→Drive→Compress) + drive Pre/Post; the
  *fine* inter-FX ordering was not forensically isolated (single-note Pre/Post echo-THD test was ~equal — 18.7 vs
  17.9 %). Oversampling/`high_quality_mode` behaviour and per-osc filter routing in "Per Oscillator" mode (structural).
- XLFO step **glide-function** ramp SHAPES (Linear/Sqr/Sqrt/Sine) and `balance`/step-duty exact law (enum captured;
  per-shape ramp curve not curve-fit). Arpeggiator note timing/groove (structural; not signal-measured).
- Mod-matrix **mechanics + depth law RESOLVED** (Filter-Freq octaves, Osc-Level dB, unipolar amount + invert,
  39 sources / 300 targets enumerated). Per-target depth law beyond Freq/Level spot-checked, not exhaustively mapped.
- Absolute MIDI-note→pitch reference offset (note 57 = 440 Hz at 8' suggests a non-A440-at-69 internal map;
  not chased — irrelevant to DSP fingerprinting since f0 is measured per render).

---
Provenance tags: **CLEAN** = black-box measurement (`twin3_sysid.py`) / public DSP / own voicing (product-safe).
Items marked "open" are simply un-measured.

## REF — static-disasm pass (TAINTED / reference-only — NOT product-safe)
> Quarantine: `private-research/_quarantine_disasm/Twin3/` (`architecture-findings.md` + `decomp/ghidra/`).
> Correction to the header "static is a wall": the binary is stripped of *symbols* but **RTTI type strings
> are intact** → full DSP class graph + kernel decompile were recovered (Ghidra 12.1.2 + r2). This is REF —
> it says *what to measure*; do NOT cite from product. Each fact below must be re-derived black-box before use.
- **Osc anti-aliasing (open Q resolved → REF):** band-limited **additive wavetable mip-maps** (NOT BLEP/minBLEP)
  — builder sums Fourier harmonics to a per-table Nyquist limit into 128×4096 tables (odd `1/(2k-1)` + `cos²`
  sigma window); alias-free by construction. Explains the CLEAN saw-1/n / square-evens-−100 dB measurement.
- **Filter type (open Q resolved → REF):** **TPT / Zavalishin State-Variable Filter** (class `StateVariableFilter`
  with `FreqFunction` g=tan(π·fc/fs), `Damp/PeakLimitFunction` = resonance, `ClipTable::ClipFunction` =
  feedback-path saturation → self-osc; `FilterOversampling` = the HQ toggle). NOT a Moog ladder.
- **Filter styles (open Q resolved → REF):** vectorized `WaveShaperVec<vectorClip*Fast>` family — ArcTan, Sine,
  DivAbs, Polynome2/3, Tube, Triode, Rectify, TanH, each ±Bias/PolyBias (asym → even harmonics); "Clean"=linear.
  ArcTan + logf coeffs are **byte-identical to Pro-L 2** (shared FabFilter transcendental library).
- **Envelope (REF):** exponential one-pole DADSR, segment coeff `a = 10^(−1/(T·fs))` (`−ln10`), `y+=(1−a)(target−y)`.
- Confidence HIGH (RTTI naming + decoded math agree). REF coeff tables: `_quarantine_disasm/Twin3/decomp/ghidra/coeff_table.md`.
