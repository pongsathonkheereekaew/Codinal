# PhaseMistress — Soundtoys 5.5 (phaser)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Multi-stage analog-style phaser (cascaded allpass comb + feedback resonance, modulated) |
| Tech | C++ VST3 over the shared **Soundtoys** framework (statically-linked; co-loading two Soundtoys VST3s duplicates ObjC classes → load one-per-process). AAX=PACE; VST3=clean, pedalboard-hostable. |
| Binary | Universal VST3, not stripped of shared framework; AAX=PACE (not used). |
| Provenance | **CLEAN** — black-box pedalboard measurement of the licensed VST3 + public DSP literature + own description. No disassembly. |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (`Tools/st_sysid.py`, `Tools/mod_probe.py`; `out/PhaseMistress_{params,null,probe,mod}.json`) |

## Signal chain
```
x → input gain → [Analog/Digital coloration] → N cascaded allpass stages (N set by `style`)
     allpass center swept by LFO (lfo_rate_hz · modulationdepth) about `frequency_hz`
     → feedback path (resonance_db) summed back to input → mix(notched=wet) with dry → output gain → y
```
A phaser = a chain of first-order allpass filters; summing the all-pass output with the dry signal creates **notches** wherever the allpass phase = 180°. **N allpass stages → ~N/2 notches.** Feedback around the chain (`resonance_db`) turns the notches into resonant peaks.

## Per-stage formula (all CLEAN — black-box)
- **Allpass comb / style (CLEAN):** `style` (24 presets) sets the **number and spacing of allpass stages** → number of notches. Static-LFO white-noise Welch notch count: `Classic 2`→0–1, `Classic 5`→1, `Super 2`→2, `PM 4`/`Breath 4`→2, `PM 6 Peak`→3, `Super 4`→7, `Super 6`→9, `Super 12`→8 (deep overlapping pairs undercounted), `Primes`→5 (prime-ratio notches), `Super 7x5`→5+ (paired-notch "x" styles). The "Super/PM/Classic" families = different allpass topologies; the number/"NxM" in the name encodes stage count (e.g. Super 12 = most stages; the "7x5"/"23x12" = two interleaved combs giving **paired notches**, measured as close doublets e.g. 234/246, 750/785, 1430/1494 Hz).
- **Notch frequencies (CLEAN):** harmonically spread, not octave-uniform — e.g. Super 12 notches at 234, 750, 1430, 2572, 5326 Hz (ratios ≈ 1 : 3.2 : 6.1 : 11 : 23) ⇒ stages tuned to a stretched/prime series, the classic "musical phaser" voicing rather than a plain uniform comb.
- **Frequency / sweep center (CLEAN):** `frequency_hz` 5–20000 shifts the **whole comb**. Super 2 lowest notch tracks linearly at ≈**2× the setting**: freq 50→100, 100→199, 200→398, 500→938, 1000→1822, 2000→3445, 5000→7670 Hz. So `frequency_hz` = the phaser sweep center; all notches scale proportionally with it.
- **Modulation (CLEAN):** `lfo_rate_hz` 0.01–256 (FREE Hz) × `modulationdepth` 0–1 sweeps `frequency_hz`. With a steady carrier the swept notches AM-modulate it at **≈3× the set LFO rate** (lfo 1.0→2.96 Hz, lfo 2.0→6.09 Hz measured) because in one LFO period several notches sweep across the carrier (multi-notch comb → multiple amplitude dips per cycle). The fundamental sweep = `lfo_rate_hz` itself (set directly in FreeRun). `modulationdepth=0` freezes the comb (used for the static notch maps above).
- **Resonance / feedback (CLEAN):** `resonance_db` 0–180 = feedback emphasis. Peak gain rises monotonically: 0→+0.2 dB, 6→+3, 20→+12, 60→**+30.3 dB**, then 180→+26 dB (saturates/folds). Notch troughs stay deep (−80…−95 dB) throughout (true allpass nulls). So the label ≈ the resonant-peak height in dB up to ~60; high values self-resonate (whistling phaser).
- **Gain (CLEAN):** `gain_db` ±60 = wet/feedback-path level (drives the resonance harder / makeup).
- **Trigger (CLEAN, present):** `trigger` bool = envelope/transient retrigger of the LFO phase (sync the sweep to input attacks); behaviorally a reset, not measurable on a sustained tone.
- **In-stage coloration (CLEAN):** Analog vs Digital — Analog adds even-harmonic saturation (consistent with the sibling Tremolator/PanMan inoutmode: Analog ≈ 2–3 % THD, Digital = 0 %).

## Why / design rationale (music ↔ code)
- **Allpass cascade (not a notch-filter bank)** → allpass-sum is *phase-coherent*: full-amplitude except at the notches, so the dry energy is preserved and only the notch frequencies cancel — the signature swooshy, "underwater" phaser motion. Chosen over static EQ notches because the notches *move* with one shared phase, which a bank of biquad notches can't do cheaply.
- **Style = stage count / topology** → more stages = more notches = thicker, more vocal sweep (Super 12) vs a single gentle dip (Classic 2). Exposing 24 voicings (Super/PM/Classic/Prime/paired) covers the whole history of hardware phasers (MXR 2-stage → 12-stage studio units) in one box.
- **Stretched / prime notch spacing** → uniformly-spaced notches sound metallic (flanger-like); a stretched/prime series sounds *musical and organic* — the designer tuned the allpass coefficients to a non-harmonic series on purpose (the "Primes" style makes this explicit).
- **Paired-notch "x" styles (7x5, 23x12)** → two interleaved combs beat against each other → a richer, shimmering double-sweep that a single chain can't produce.
- **Feedback resonance up to self-oscillation (+30 dB)** → from subtle motion to screaming resonant whistle; the resonance emphasizes the notch edges, the classic "juicy" phaser sound, and at the top it becomes a tonal effect.
- **Free Hz LFO 0.01–256** → covers glacial mix-wide movement (0.01 Hz) up to audio-rate FM-like timbral phasing (256 Hz) — far beyond a typical phaser, enabling sound-design textures.
- **Analog mode** → harmonic glue so the swept notches sit on a warm bed rather than sounding like a clinical digital sweep.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| inputgain_db | dB | −24…+24 | |
| outputgain_db | dB | −24…+24 | |
| mix | % | 0…100 (def 100) | dry/wet (100 = full notched signal) |
| inoutmode | enum | Digital / Analog (def Analog) | Analog = even-harmonic saturation |
| frequency_hz | Hz | 5…20000 (def 35) | sweep center; lowest notch ≈2× this; all notches scale with it |
| resonance_db | dB | 0…180 (def 6) | feedback emphasis; ≈peak height in dB to ~60 (+30 dB peaks), folds above |
| gain_db | dB | −60…+60 (def 0) | wet/feedback level |
| modulationdepth | 0–1 | 0…1 (def 1.0) | LFO depth (0 = frozen comb) |
| style | enum | 24 presets (def Super 7x5) | sets # allpass stages → # notches + spacing |
| trigger | bool | Off/On | envelope-retrigger LFO phase (reset on attack) |
| tempo_bpm | BPM | 30…240 (def 120) | host tempo proxy; sync rates need transport |
| lfo_rate_hz | Hz | 0.01…256 (def 0.25) | **FREE Hz LFO rate** (directly measurable) |

**style enum (24):** Super 12, Super 7x5, Super 6, Super 4, Super 2, Rezo 7 Low, PM 23x12, PM 12, PM 8x6, PM 7x5, PM 6 Peak, PM 5 High, PM 4, PM 2x4, Classic 9, Classic 5, Classic 2, ThinMan, Squeezer, Primes, OuterIn, FatFace, Breath 4, Custom.

## CLEAN measurements
- **Notch count vs style** (static, white-noise Welch): Super 12≈8 (deep pairs), Super 6≈9, Super 4≈7, Primes≈5, Super 2≈2, Classic 2≈0–1.
- **Frequency tracking** (Super 2): lowest notch ≈ 2× `frequency_hz`, linear 50→100 … 5000→7670 Hz.
- **Resonance** (Super 7x5, freq 500): peak 0→+0.2, 6→+3, 20→+12, 60→+30.3, 180→+26 dB; troughs −80…−95 dB.
- **LFO rate** (carrier AM): lfo 1.0→2.96 Hz, 2.0→6.09 Hz AM (≈3× — multiple notches/cycle); fundamental sweep = set rate.

## Tempo-sync deferrals
The LFO **FREE Hz** mode (`lfo_rate_hz`) was measured directly. **Rhythm/tempo-sync rate modes are unmeasured — needs REAPER transport** (pedalboard has no host clock; `tempo_bpm` doesn't drive a free-running sweep here). `trigger` (envelope retrigger) confirmed present but not characterized on sustained input.

## To implement (CLEAN-only)
- N cascaded first-order allpass filters (`H(z)=(a+z⁻¹)/(1+a z⁻¹)`), a = f(center freq); `style` picks N and per-stage tuning offsets (stretched/prime series, optionally two interleaved combs for "x" styles → ~N/2 notches).
- Sum allpass output with dry (mix) → notches; feedback the chain output to its input scaled by `resonance_db` (map dB→feedback coeff so peak rises ~linearly to +30 dB near res=60, soft-limit above).
- LFO (free Hz) sweeps the allpass center about `frequency_hz` × `modulationdepth`; notches scale ~proportionally (lowest ≈2× center). `trigger` resets LFO phase on input transients.
- Optional Analog stage = even-harmonic input saturation.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). No REF (no disassembly performed).
