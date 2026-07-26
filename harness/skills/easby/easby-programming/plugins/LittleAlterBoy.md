# LittleAlterBoy — Soundtoys (vocal pitch + formant shifter + drive)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Vocal pitch + formant shifter with drive — independent pitch/formant resample, tube-style saturation, Transpose/Quantize/Robot modes |
| Tech | C++ VST3, shared Soundtoys framework. AAX = PACE; VST3 = pedalboard-hostable, no DRM wall. |
| Binary | universal VST3; not PACE-encrypted in the VST3 slice. |
| Provenance | **CLEAN** — black-box measurement of the licensed VST3 + public pitch/formant-shift literature. No disassembly. |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (`Tools/st_sysid.py`, `Tools/alterboy_probe.py`, `Tools/cleanup_probe.py` → `out/LittleAlterBoy_*.json`) |

## Signal chain
```
x → pitch shifter (±12 st, formant-preserving) → formant shifter (±12 st, independent spectral-envelope resample)
  → drive (asymmetric→symmetric saturation) → dry/wet mix → y
   shiftmode ∈ {Transpose | Quantize (snap-to-note) | Robot (fixed/MIDI note)}
   formantlink: when ON, formant tracks pitch (1:1); OFF = formant fixed while pitch moves
```
A phase-vocoder-class pitch shifter that **separates pitch from spectral envelope (formant)**, so you can shift
pitch while keeping (or independently moving) the vocal "size" — plus a saturation stage for grit.

## Per-stage formula  (all CLEAN — black-box)
- **Pitch shift (`pitch_semitones`)** (CLEAN, exact): output fundamental = input × 2^(semi/12). Measured 1:1
  across the **full ±12 range**: −12→−12.01, −5→−4.99, −3→−3.0, +3→2.98, +5→4.98, +7→6.99, +12→12.00 semitones
  (FFT fundamental ratio). Formant-preserving by default (the spectral envelope stays put when only pitch moves).
- **Formant shift (`formant_semitones`)** (CLEAN, independent): rescales the **spectral envelope** by 2^(semi/12)
  while the **fundamental stays fixed**. Measured on a fixed-f0 (220 Hz) saw: f0 unchanged for all formant
  settings; spectral centroid ratio tracks 2^(semi/12) — formant −3→0.851 (exp 0.841), +3→1.206 (1.189),
  +5→1.330 (1.335), +7→1.494 (1.498). ⇒ independent formant resampling, exact semitone ratio.
- **formantlink** (CLEAN): ON → formant follows pitch 1:1 (pitch +12 with link ON pushed centroid up ×2.0 →
  "chipmunk"/naïve-resample sound); OFF → formant stays while pitch shifts (centroid barely moves → natural
  pitch-only shift). This is the formant-preservation switch.
- **Drive (`drive`)** (CLEAN): saturation stage, 0..10.
  - THD vs drive (1 kHz, −12 dBFS in): 0→3.0 %, 2.5→5.4 %, 5→14.6 %, 7.5→35.6 %, 10→35.0 %.
  - **Harmonic profile:** H2-dominant at low/mid drive (H2 −31→−21 dB, H3 far below), then **H3 climbs hard**
    (−85 dB → −11 dB by drive 7.5) → asymmetric (tube/even-harmonic) at low drive turning to symmetric
    clipping at high drive. Output level rises then **compresses/clips** (drive 10 out −16.8 dB = hard limiting).
- **Mode (`shiftmode`)** (CLEAN):
  - **Transpose** = continuous pitch by the knob (the measurements above).
  - **Quantize** = snaps output pitch to nearest semitone/scale: in 150 Hz→146.8 Hz (D3), in 300→293.7 (D4)
    → auto-tune-style note snapping.
  - **Robot** = forces a **single fixed pitch** regardless of input: in 150 and in 300 both → ≈261 Hz (C4),
    monotone "robot voice." The fixed note is **MIDI-controllable → UNMEASURED without MIDI** (default ≈ C4).
- **Mix (`mix`)** (CLEAN): dry/wet 0..100 % (parallel blend of shifted+dry).
- **Latency (`reported_latency_samples`)** (CLEAN): **2417 samples = 50.35 ms @ 48k** — the phase-vocoder /
  formant-preserving analysis window. Default state (pitch 0/formant 0/drive 0) nulls to dry (−75 dB) = clean
  bypass-equivalent.

## Why / design rationale (music ↔ code)
- **Independent pitch and formant** → the core feature: shift a vocal up an octave *without* the chipmunk effect
  (keep formants), or deepen/feminize a voice by moving formants alone, or do classic "monster"/"chipmunk" by
  linking them → one tool for natural transposition *and* extreme character.
- **Formant = separate spectral-envelope resample** (vs naïve resampling that drags formants with pitch) → keeps
  vocals sounding human after big shifts → why a phase-vocoder/PSOLA-class engine is used (and why the 50 ms
  latency is acceptable: vocal-shaping, not tracking).
- **Drive with even→odd harmonic progression** → musical "warmth" at low settings (tube-like H2) escalating to
  aggressive grit/clip at high settings → lets a clean pitch shifter also be a vocal-mangling effect (Soundtoys
  house "character"), and the built-in soft-limit keeps level under control.
- **Three modes** map to three idioms: Transpose (creative/harmony), Quantize (auto-tune correction/effect),
  Robot (vocoder/monotone) → covers correction, harmony, and sound-design from one box.
- **formantlink switch** → one click between "natural" (preserve) and "cartoon" (link) → exposes the engine's
  key DSP choice as a musical decision.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| pitch_semitones | semitones | −12..+12 | exact 2^(n/12) transpose (formant-preserving) |
| formant_semitones | semitones | −12..+12 | independent spectral-envelope resample 2^(n/12), f0 fixed |
| drive | 0..10 | 0..10 | saturation; THD 3 %→36 %; H2-dominant→H3 climbs; soft-limits at top |
| mix | % | 0..100 | dry/wet parallel blend |
| shiftmode | enum | Transpose, Quantize, Robot | continuous · snap-to-note · fixed/MIDI note |
| formantlink | bool | Off/On | ON = formant tracks pitch (chipmunk); OFF = formant fixed (natural) |

## CLEAN measurements
- **Pitch (param→measured semitones):** −12→−12.01, −5→−4.99, −3→−3.0, 0→0, +3→2.98, +5→4.98, +7→6.99,
  +12→12.00 (exact 1:1, full range; FFT fundamental ratio).
- **Formant (centroid ratio vs 2^(n/12)):** −3 0.851/0.841 · 0 1.00 · +3 1.206/1.189 · +5 1.330/1.335 ·
  +7 1.494/1.498 (f0 held at 220 Hz throughout — independent of pitch).
- **Drive THD (1 kHz):** 0→3.0 %, 2.5→5.4 %, 5→14.6 %, 7.5→35.6 %, 10→35.0 %; H2 −31→−19 dB, H3 −85→−11 dB.
- **Modes:** Transpose continuous · Quantize snaps (150→146.8, 300→293.7 Hz) · Robot fixes pitch (150&300→≈261 Hz).
- **Latency:** 2417 samp (50.35 ms). Default (0/0/0) nulls to dry −75 dB.
- **MIDI-driven note for Robot/Quantize-key = UNMEASURED** (no MIDI in pedalboard).

## To implement (CLEAN-only path)
- **Phase-vocoder (or PSOLA) pitch shifter with separate formant control:** analyze STFT → shift bin pitch by
  2^(pitch/12); independently warp the spectral-envelope (cepstral/LPC envelope) by 2^(formant/12); resynthesize.
  Default = formant-preserving (decouple envelope from pitch); formantlink ON = apply pitch ratio to the envelope too.
- **Window ≈ 2417 samp @ 48k (~50 ms)** if matching latency; smaller windows trade quality for latency.
- **Drive:** asymmetric soft-clip (bias for H2 at low drive) escalating to symmetric/hard clip, with output
  soft-limit — a waveshaper whose asymmetry decreases as drive rises (or a fixed asymmetric tanh + post-clip).
- **Modes:** Transpose = continuous knob; Quantize = snap output f0 to nearest scale note (pitch tracker → nearest
  semitone); Robot = ignore input pitch, output a fixed (or MIDI) note. mix = parallel dry/wet.
- For ES-X vocal chains: this is the **independent pitch+formant** primitive (natural octave shifts, gender/size
  morphing) plus a character drive — reusable as a vocal-doubler/harmonizer building block.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). **REF** = none used.
