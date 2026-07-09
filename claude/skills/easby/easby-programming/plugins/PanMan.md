# PanMan — Soundtoys 5.5 (auto-pan)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Auto-panner (rhythmic/LFO stereo position modulation; rhythm/LFO/trigger/random modes) |
| Tech | C++ VST3 over the shared **Soundtoys** framework (statically-linked; co-loading two Soundtoys VST3s duplicates ObjC classes → load one-per-process). AAX=PACE; VST3=clean, pedalboard-hostable. |
| Binary | Universal VST3, not stripped of shared framework; AAX=PACE (not used). |
| Provenance | **CLEAN** — black-box pedalboard measurement of the licensed VST3 + public DSP literature + own description. No disassembly. |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (`Tools/st_sysid.py`, `Tools/mod_probe.py`; `out/PanMan_{params,null,probe,mod}.json`) |

## Signal chain
```
x → input gain → [Analog/Digital coloration] → stereo pan law driven by LFO
     pan position = offset_deg + width_deg·LFO(rate_hz);  smoothing morphs shape (triangle→sine)
     rhythm/feel/groove = pattern + swing;  modulators: ratemod_oct, offsetmod_deg, widthmod_deg
  → dry/wet (mix) → output gain → y(L,R)
```
Auto-pan = an LFO driving the stereo pan position; here position is expressed in **degrees** (pan angle, ±105° offset, up to 210° width).

## Per-stage formula (all CLEAN — black-box)
- **Rate (CLEAN, FREE Hz):** `rate_hz` 0.01–10 directly sets the pan LFO. Measured pan-signal (L−R envelope) rate vs set: 0.5→0.52, 1.0→1.04, 2.0→2.09, 4.0→4.0 Hz — **accurate, free-running** (no transport needed; the only one of the 4 with a clean free-Hz rate).
- **Width / pan depth (CLEAN):** `width_deg` 0–210 = pan-swing magnitude. L/R amplitude swing vs width: 0→L=R (no pan), 52.5→±~5 dB swing, 105→±~10 dB, **180→full hard pan** (one channel drops to −55…−97 dB at the extremes = signal fully on the other side), 210→over-pan (both channels drop at the extremes ⇒ past hard-L/R, the constant-power law wraps). So 0–180° = mono→hard-L/R; >180° = over-rotation.
- **Pan shape (CLEAN):** at `width=180, smoothing=0` the pan signal `(L−R)/(L+R)` traces a **near-linear ramp** −0.57→+0.80 (monotonic) ⇒ **triangle LFO** (constant-velocity sweep across the field). With `smoothing=1.0` the ramp rounds into a **sine** (the corners soften: cycle becomes −0.34→−0.75 plateau→+0.75). So `smoothing` morphs the pan LFO **triangle → sine** (linear sweep → eased sweep).
- **Offset / static pan (CLEAN):** `offset_deg` ±105 = pan-position bias (center of the sweep, or static pan when width=0). Static L−R vs offset: −105°→+17.45 dB, −52.5°→+9.29, 0→0, +52.5→−9.29, +105°→−17.45 dB — **linear ≈ 0.166 dB/deg**; ±105° ≈ ±17.5 dB L/R difference (strong but not infinite ⇒ a constant-power pan pot, not a hard mute).
- **Constant-power pan law (CLEAN):** the offset law (≈sin/cos taper, ~17 dB at the rail rather than −∞) and the width behavior (180° = full hard pan) are consistent with a **constant-power (equal-power) pan** mapping angle→(gainL, gainR), the standard for click-free panning that holds perceived loudness across the sweep.
- **Rhythm / feel / groove (CLEAN params, tempo-domain):** `feel` ±0.25 and `groove` ±0.25 = swing/timing of the rhythmic pan pattern; `manualtrigger` bool = manually fire one pan step. PanMan's rhythm/step modes (and "trigger"/"random" pattern modes) ride the host clock — pattern timing is tempo-sync (deferred); the **free-Hz LFO rate** path was measured directly.
- **Modulators (CLEAN params):** `ratemod_oct` ±3 = rate modulation (±3 oct = ÷8…×8 on the pan rate); `offsetmod_deg` ±180 and `widthmod_deg` ±180 = dynamic modulation of pan center/width.
- **In-stage coloration (CLEAN):** Analog mode adds saturation — measured **3.17 % THD, H2 −30 dB dominant (even-harmonic / asymmetric)** at static width=0; Digital = 0 % THD. Matches the suite inoutmode gotcha (Analog ≠ transparent).

## Why / design rationale (music ↔ code)
- **Pan expressed in degrees with constant-power law** → maps to how a sound source moves in a real stereo field; constant-power keeps loudness steady as the source crosses center (a linear pan would dip −3…−6 dB in the middle, audible on every sweep). Standard, but correct.
- **Triangle default, smoothing→sine** → triangle = constant-velocity sweep (even, rhythmic motion, classic auto-pan); sine = eased motion that lingers at the sides (gentler, more natural "swing" between speakers). One knob spans both feels.
- **Width up to 210° (over-pan)** → beyond hard-L/R lets the designer push into "wider-than-the-speakers" / phasey extremes for special FX, not just safe panning.
- **Offset = sweep center** → place the motion off-center (e.g. pan mostly on the right) so the auto-pan supports a sound's position in the arrangement instead of always swinging symmetrically.
- **Rhythm engine (feel/groove/trigger/random) + free LFO** → the Soundtoys philosophy: panning should *groove* (sync'd rhythmic jumps, swing, random per-step) or *flow* (free LFO). Random/trigger modes turn auto-pan into a rhythmic placement tool, not just a stereo wobble.
- **`ratemod`/`offsetmod`/`widthmod`** → dynamic, performance-reactive panning (e.g. wider/faster on louder passages) — the modulation matrix that makes it feel alive.
- **Analog mode** → harmonic coloration glues the moving image and adds vintage character (real pan circuits/tape colored the signal); a clean gain-pair would sound sterile.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| inputgain_db | dB | −24…+24 | |
| outputgain_db | dB | −24…+24 | |
| mix | % | 0…100 (def 100) | dry/wet |
| inoutmode | enum | Digital / Analog (def Analog) | Analog = even-harmonic saturation (H2 −30 dB); Digital clean |
| rate_hz | Hz | 0.01…10 (def 0.25) | **FREE Hz pan LFO rate** (accurate, directly measured) |
| offset_deg | deg | −105…+105 (def 0) | pan-position bias / static pan; ≈0.166 dB/deg L−R |
| width_deg | deg | 0…210 (def 180) | pan swing; 180 = hard L/R, >180 over-pan |
| smoothing | 0–1 | 0…1 (def 0) | morphs pan LFO **triangle (0) → sine (1)** |
| ratemod_oct | oct | −3…+3 (def 0) | rate modulation (×⅛…×8) |
| offsetmod_deg | deg | −180…+180 (def 0) | dynamic pan-center modulation |
| widthmod_deg | deg | −180…+180 (def 0) | dynamic width modulation |
| feel | ±0.25 | −0.25…0.25 (def 0) | timing feel/swing (tempo-domain) |
| groove | ±0.25 | −0.25…0.25 (def 0) | swing of rhythm pattern (tempo-domain) |
| manualtrigger | bool | Off/On | fire one pan step manually |
| tempo_bpm | BPM | 30…240 (def 120) | host tempo proxy; rhythm/step modes need transport |

## CLEAN measurements
- **Rate accuracy:** rate_hz 0.5/1/2/4 → 0.52/1.04/2.09/4.0 Hz (free-running, accurate).
- **Width → L/R swing:** 0→L=R; 52.5→±5 dB; 105→±10 dB; 180→hard (other ch −55…−97 dB); 210→over-pan (both drop).
- **Pan shape:** smoothing 0 = triangle (linear ramp −0.57→+0.80); smoothing 1 = sine (rounded).
- **Offset static pan:** −105→+17.45, −52.5→+9.29, 0→0, +52.5→−9.29, +105→−17.45 dB (≈0.166 dB/deg, constant-power).
- **inoutmode THD (static):** Analog 3.17 % (H2 −30, H3 −42), Digital 0 %.

## Tempo-sync deferrals
The **free-Hz LFO rate** (`rate_hz`) was measured directly and is accurate. **Rhythm/step/trigger/random pattern modes, `feel`/`groove` swing, and `ratemod_oct` scaling are tempo-sync: unmeasured — needs REAPER transport** (pedalboard has no host clock). All LFO/width/offset/shape/coloration behavior measured CLEAN.

## To implement (CLEAN-only)
- Pan LFO (free Hz) → position = `offset_deg + width_deg·LFO`; `smoothing` crossfades the LFO waveform triangle→sine.
- Constant-power pan law: angle→(gainL, gainR) via sin/cos taper (≈17 dB at ±105°, full hard at ±180°, over-pan beyond).
- Rhythm engine: tempo-locked step patterns + `feel`/`groove` swing + random/trigger modes (needs host clock); `manualtrigger` fires one step.
- `ratemod`/`offsetmod`/`widthmod` modulate the base rate/center/width.
- Optional Analog stage = even-harmonic (H2-dominant) input saturation, always on in Analog mode.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). No REF (no disassembly performed).
