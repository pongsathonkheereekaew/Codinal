# MegaMod — Sync Audio (modulation matrix / generator — not an audio processor on its own)

| | |
|---|---|
| Vendor / ver | Sync Audio (`com.syncaudio.megamod`) · 0.8.0 |
| Type | **Modulation source bank**: 16 LFOs + 16 XY-pads + 16 macros. Generates modulation; routes to *other* plugins' params (host modulation), **no audio-path DSP of its own**. |
| Tech | JUCE C++ + WebKit UI; 27.6k syms, NOT stripped, no PACE |
| Binary | universal (x86_64+arm64) |
| Provenance | **CLEAN** (pedalboard). No disasm. |
| Measured on | MegaMod 0.8.0 · 48 kHz · pedalboard 0.9.17 · 2026-06-26 |
| Source | `private-research/CleanMisc/Tools/cleanmisc_sysid.py` |

## Behavior
- **Audio = unity pass-through** (CLEAN): 1 kHz @ −13.5 dB in → out −13.5 dB, Δ 0.00 dB. The plugin does not touch the audio signal; it emits modulation values for the host to route to destination plugin parameters.
- 16 **LFOs**: rate **0.001–20 Hz**, phase 0–360°, per-LFO enable.
- 16 **XY-pads**: x/y ∈ −1..+1, enable.
- 16 **macros**: −100..+100, enable.

## Why / design rationale
- A central "mega" modulation brain — one instance feeds many targets (LFO/macro/XY) across a session. Lives in the FX chain only to be host-visible for routing; the audio just passes through. v0.8.0 (beta).

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| lfo_N_rate (×16) | Hz | 0.001..20 | |
| lfo_N_phase (×16) | deg | 0..360 | |
| lfo_N_enable / macro_N_enable / xypad_N_enable | bool | | |
| macro_N (×16) | — | −100..+100 | |
| xypad_N_x / _y (×16) | — | −1..+1 | |
| bypass | bool | | |

## Open questions
- Modulation routing (LFO→destination) is host-side / internal UI, not observable via audio. Nothing to clone in the audio path.

## To implement
N/A for audio DSP — it's a modulator. If ever needed: standard multi-LFO generator (rate 0.001–20 Hz, phase offset). CLEAN.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing.
