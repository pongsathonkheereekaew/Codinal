# LittleMicroShift — Soundtoys (fixed stereo widener — MicroShift subset)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | One-knob stereo widener — fixed micro-detune + delay recipes (reduced-control sibling of MicroShift) |
| Tech | C++ VST3, shared Soundtoys framework. AAX = PACE; VST3 = pedalboard-hostable, no DRM wall. |
| Binary | universal VST3; not PACE-encrypted in the VST3 slice. |
| Provenance | **CLEAN** — black-box measurement of the licensed VST3 + public widener literature. No disassembly. |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (`Tools/micro_probe.py`, `Tools/micro_delay.py`, `Tools/cleanup_probe.py` → `out/LittleMicroShift_*.json`) |

## Signal chain
```
mono/stereo x → [ +Δcents / delay τL → L ] + [ −Δcents / delay τR → R ] → dry/wet mix → y
   style ∈ {I,II,III} = three FIXED detune+delay presets (no detune/delay knobs)
```
Same engine as MicroShift but with the **detune and delay amounts baked into the 3 styles** — only `style`,
`inputgain_db`, and `mix` are exposed (4 params total incl. bypass). Decode the parent (MicroShift); this is the
param-subset sibling.

## Per-stage formula  (all CLEAN — black-box)
- **Fixed symmetric micro-detune per style** (CLEAN):
  - **Style I, II:** L **+9.0 c** / R **−9.0 c** (same ±9 c as MicroShift's detune=100 default).
  - **Style III:** narrower — L **−5.0 c** / R **+5.0 c** (swapped polarity *and* reduced depth — differs from
    MicroShift's style III which keeps ±9 c).
- **Fixed inter-channel delays per style** (CLEAN, cross-correlation dry→channel) — the "Little" presets use
  **longer stereoizing delays** than MicroShift's tunable ~1–11 ms:
  - **Style I:** L ≈ 17 ms, R ≈ 40 ms (L−R ≈ −23 ms).
  - **Style II:** L ≈ 11 ms, R ≈ 34 ms (L−R ≈ −22 ms).
  - **Style III:** strongly asymmetric (L early, R ≈ 26 ms).
  (Burst-onset cross-check: I L34/R22, II L5/R35, III ≈29/29 ms — values are in the tens-of-ms doubler range.)
- **Width = dry/wet `mix`** (CLEAN): linear decorrelation morph, same as MicroShift. L/R correlation vs mix:
  0→1.00, 25→0.77, 50→0.37, 75→0.10, 100→0.00 (side=mid at 100 % = max width, mono-sum preserved).
- **inputgain_db** (CLEAN): −3..+6 dB pre-trim.
- **Latency:** reported 32 samples (~0.67 ms); the long internal delays + pitch smear dominate the impulse
  response (measured IR energy out to ~40 ms = the style delay taps, not latency).

## Why / design rationale (music ↔ code)
- **Fixed "right" recipes, one knob** → the Soundtoys "Little" philosophy: the parent's best-sounding detune+delay
  combos pre-dialed so the user only chooses a flavour (I/II/III) and amount (mix) → instant wide vocals/synths
  with zero tweaking.
- **Opposite-sign detune → mono-compatible width** (same rationale as MicroShift): centred, in-tune sum.
- **Longer baked delays than the tunable parent** → these presets lean more on Haas decorrelation (tens of ms)
  than fine detune → a fuller, more obvious "instant double" suited to the simplified target user.
- **Style III narrower detune** → a subtler option for sources where ±9 c is too much shimmer (e.g. lead vocal).

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| inputgain_db | dB | −3..+6 | pre-trim |
| mix | % | 0..100 | dry/wet = width amount (linear decorrelation) |
| style | enum | I, II, III | fixed detune+delay preset; III = ±5 c (narrower, swapped) vs ±9 c (I/II) |

## CLEAN measurements
- **Detune (cents):** I = L+9/R−9 · II = L+9/R−9 · III = L−5/R+5.
- **Fixed delays (xcorr dry→ch, ms):** I L17/R40 · II L11/R34 · III asymmetric (R≈26).
- **Width vs mix (L/R corr):** 0→1.00, 25→0.77, 50→0.37, 75→0.10, 100→0.00.
- **Latency:** 32 samp (~0.67 ms). All styles fully decorrelated at mix=100 (corr ≈ 0).

## To implement (CLEAN-only path)
- **Reuse the MicroShift widener block**; replace the detune/delay knobs with **3 hard-coded presets**:
  I = (±9 c, L17/R40 ms), II = (±9 c, L11/R34 ms), III = (∓5 c, asymmetric). Pan A→L, B→R; width = dry/wet.
- Drop-in "instant widener" for ES-X where only a flavour + amount is wanted.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). **REF** = none used.
