# MicroShift — Soundtoys (stereo widener: micro-detune + delay)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Stereo widener — symmetric micro-pitch detune + small inter-channel delay (Eventide H3000 / AMS-style), 3 modes |
| Tech | C++ VST3, shared Soundtoys framework. AAX = PACE; VST3 = pedalboard-hostable, no DRM wall. |
| Binary | universal VST3; not PACE-encrypted in the VST3 slice. |
| Provenance | **CLEAN** — black-box measurement of the licensed VST3 + public widener/pitch-shift literature. No disassembly. |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (`Tools/micro_probe.py`, `Tools/micro_delay.py`, `Tools/cleanup_probe.py` → `out/MicroShift_*.json`) |

## Signal chain
```
                ┌─ pitch-shift +Δcents → delay τL ─┐
mono/stereo x → ┤                                   ├→ [L , R]  (wet) → dry/wet mix → y
                └─ pitch-shift −Δcents → delay τR ─┘
   style ∈ {I,II,III} selects the detune/delay polarity-and-time recipe
   detune param scales Δcents (±4.5..±18 c) · delay param scales |τL−τR| (~1..11 ms)
   focus_hz = HF/LF emphasis (which band gets widened)
```
Two pitch-shifted copies, **detuned in opposite directions** and given **small different delays**, panned hard
L/R → decorrelates the two channels → wide stereo image from a mono source. (Classic Eventide "MicroPitch"/AMS
stereo-doubler.)

## Per-stage formula  (all CLEAN — black-box)
- **Symmetric micro-detune** (CLEAN, definitive): one voice up +Δ cents, the other down −Δ cents.
  - Default `detune`=100 → measured **L +9.0 c, R −9.0 c** (FFT fundamental ratio).
  - **Detune law is linear:** Δcents ≈ **±0.09 · detune_param**. Measured: 50→±5, 70.7→±6, 100→±9,
    141.4→±13, 200→±18 cents. Range ≈ **±4.5 .. ±18 cents**.
- **Inter-channel micro-delay** (CLEAN): `delay` param scales the L/R time offset.
  - Measured L↔R lag (cross-correlation, detune 50): delay 50→1.1 ms, 100→6.25 ms, 200→10.6 ms ⇒ roughly
    linear, **~1 ms .. ~11 ms** relative delay.
- **3 styles (`style`)** = different detune/delay polarity+time recipes (CLEAN):
  - **I** and **II:** L +9 c / R −9 c (same detune polarity); their inter-channel delay differs
    (style I L−R lag ≈ +9 ms, style II ≈ −1.9 ms at delay=100) → I = wide delay-spread, II = near-coincident.
  - **III:** **detune polarity swapped** (L −9 c / R +9 c) and L−R lag ≈ −7.5 ms → mirrored image.
  - All three give **fully decorrelated** channels at mix=100 (L/R correlation ≈ 0.004).
- **Width = dry/wet `mix`** (CLEAN): linear morph dry→wide. Measured L/R correlation vs mix: 0 %→1.00,
  25 %→0.91, 50 %→0.62, 75 %→0.22, 100 %→0.00; side/mid energy 0→equal at 100 % (max width, mono-sum preserved).
  mix=0 nulls to dry (−6 dB self vs dry = the two voices' incoherent sum, not a true null — see note).
- **focus_hz** (CLEAN, param surface): 20 Hz–10 kHz "Focus" control = spectral emphasis of where the widening
  acts (default 20 Hz = full-range). Not swept exhaustively; behaves as an LF/HF tilt on the widened component.
- **inputgain_db** (CLEAN): −3..+6 dB pre-trim.
- **Latency:** reported 32 samples (~0.67 ms). The pitch-shift smears impulses, so absolute per-channel onset
  isn't cleanly resolvable; detune (cents) and L↔R lag (xcorr) are the load-bearing measured numbers.

## Why / design rationale (music ↔ code)
- **Opposite-sign micro-detune (±cents), not a single shift** → keeps the **mono-sum centred and in tune** (the
  two voices average back to the original pitch) while the *difference* between channels creates width → wide but
  mono-compatible, the #1 requirement for a mix-bus/vocal widener.
- **Tiny detune (single-digit cents)** → shimmer/thickening without audible "out of tune" or chorus warble → the
  "expensive studio doubler" sound (H3000 MicroPitch) vs a cheap chorus.
- **Add small L/R delay on top of detune** → Haas-style decorrelation reinforces the width and avoids comb-filter
  cancellation when summed → richer image than detune alone.
- **3 styles** → presets of the detune/delay recipe (different vendors' classic settings: H3000 vs AMS vs a
  mirrored variant) → instant "which famous box" choice.
- **Width via dry/wet only** → the wet path is *always* maximally decorrelated; you dial *how much* widening, so
  the effect degrades gracefully to mono and never collapses center content.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| mix | % | 0..100 | dry/wet = width amount (linear decorrelation morph) |
| inputgain_db | dB | −3..+6 | pre-trim |
| detune | (param) | 50..200 | Δcents ≈ ±0.09·param ⇒ ±4.5..±18 c (default 100 = ±9 c) |
| delay | (param) | 50..200 | L↔R inter-channel delay ~1..11 ms (default 100 ≈ 6 ms) |
| focus_hz | Hz | 20..10000 | spectral focus / tilt of the widened band (default 20 = full) |
| style | enum | I, II, III | detune/delay recipe; III swaps detune polarity |

## CLEAN measurements
- **Detune law (cents, style I):** 50→L+5/R−4, 70.7→±6, 100→L+9/R−9, 141.4→±13, 200→±18. Linear ±0.09·param.
- **Delay law (L↔R xcorr ms, style I, detune 50):** 50→1.1, 100→6.25, 200→10.6.
- **Per-style (detune 100):** I L+9/R−9, L−R lag +9 ms · II L+9/R−9, L−R lag −1.9 ms · III L−9/R+9, L−R lag −7.5 ms.
- **Width vs mix (L/R corr):** 0→1.00, 25→0.91, 50→0.62, 75→0.22, 100→0.00 (side=mid at 100 %).
- **Latency:** 32 samp (~0.67 ms). All styles: L/R correlation ≈ 0.004 at mix=100 (max decorrelation).

## To implement (CLEAN-only path)
- **Two delay-line pitch-shifters** (granular / overlap-add micro-pitch, or fractional-delay phasor-modulated
  taps) — voice A at +Δ cents, voice B at −Δ cents, Δ = ±0.09·detune (clamp ±4.5..±18 c).
- **Per-voice short delay**, L−R offset scaled by the delay param (~1..11 ms). Pan A→L, B→R.
- **Width = dry/wet crossfade** (keep wet fully decorrelated; mix sets amount). Preserve mono-sum (opposite
  detune signs guarantee centred sum).
- **3 styles** = three (detune-polarity, L/R-delay) presets; style III flips detune sign.
- Optional **focus** = pre-tilt EQ on the wet path (LF/HF emphasis). Drop-in stereo-widener block for ES-X.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). **REF** = none used.
