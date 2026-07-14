# Tape Fiasco — Phase Fiasco (varispeed / stretch / stutter glitch FX, not a tape saturator)

| | |
|---|---|
| Vendor / ver | Phase Fiasco (`com.phasefiasco.tapefiasco`) · 1.2.2 |
| Type | **Buffer-glitch multi-FX**: 3 serial engines — Stretch (granular), **Varispeed** (tape transport: wow/flutter, tape-stop, scratch, saturation, compress), Stutter (beat-repeat). NOT a continuous tape-sat plugin. |
| Tech | JUCE C++ + WebKit UI; 9.3k syms, NOT stripped, no PACE |
| Binary | universal (x86_64+arm64) |
| Provenance | **CLEAN** (pedalboard). No disasm. |
| Measured on | Tape Fiasco 1.2.2 · 48 kHz · pedalboard 0.9.17 · 2026-06-26 |
| Source | `private-research/CleanMisc/Tools/cleanmisc_sysid.py` |

## Signal chain
```
x → [Stretch granular] → [Varispeed transport] → [Stutter beat-repeat] → out   (effect_order configurable)
```
Mostly tempo-synced / buffer-state effects (host transport dependent) — only the Varispeed continuous DSP (saturation, wow/flutter) is cleanly black-boxable static.

## Per-stage formula (CLEAN — Varispeed continuous DSP)
- **vari_saturation** (CLEAN): **odd-harmonic (H3-dominant) waveshaper** — tanh/cubic class. 1 kHz @ −6 dB: THD 0 % @ sat0, **9.7 % @ sat50** (H3 −20.3, H2 −107 dBc), **17.9 % @ sat100** (H3 −15.2, H2 −110 dBc). Symmetric (H2 negligible).
- **vari_wow_flutter** (CLEAN): buffer-speed pitch modulation; not a subtle period wow — at full it sweeps to a near-stop glide (±100 %, ~0.25 Hz). This is a transport-wobble, exaggerated by design.
- **vari_tape_stop / vari_scratch**: pitch-glide-to-zero / scrub (transport, transient — buffer-driven).
- Stretch (granular, grain 5–100 ms) + Stutter (beat-repeat, rate 10–500%, division 4–256) = tempo-synced buffer effects, not static-characterizable.

## Why / design rationale
- "Tape Fiasco" = creative *transport chaos*, not gentle warmth: varispeed/tape-stop/stutter for glitch/IDM. Saturation is the only "tape" tone stage (odd-harmonic, like tape's symmetric compression). Buffer engines need host tempo → live performance / clip FX, not mix-bus glue.

## Parameters (selected; ~80 total)
| param | unit | range | notes |
|---|---|---|---|
| vari_saturation | % | 0..100 | odd-harmonic shaper (9.7%/50, 17.9%/100 THD) |
| vari_wow_flutter | % | 0..100 | transport pitch wobble (extreme) |
| vari_speed | % | 0..100 | playback speed |
| vari_tape_stop / vari_scratch | bool / −100..100 | | transport glide / scrub |
| vari_compress / vari_distort_type | % / 0..1 | | |
| stretch_* (granular) | | grain 5..100ms, pitch ±12 | tempo-synced |
| stutter_* (beat-repeat) | | rate 10..500%, div 4..256, pitch ±12 | tempo-synced |
| effect_order | enum | Stretch>Vari>Stutter | chain order |
| ducking | % | 0..100 | |

## Open questions
- Stretch/Stutter need host transport+tempo → not statically measurable in pedalboard; would need REAPER with a playing timeline. Characterized only the continuous Varispeed saturation+wow here.

## To implement
Varispeed saturation = odd waveshaper (tanh), drive-mapped (≈18% THD @ max). Wow/flutter = fractional-delay pitch-mod (here exaggerated to transport-stall). Buffer engines out of scope for static clone. CLEAN.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing.
