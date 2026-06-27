# Shared DSP-block shapes (suite-level canonical source)

The music-craft schemas (`easby-mixing/schemas/MixDecision`, `easby-mastering/schemas/MasterDecision`) share a
**common core** for a few DSP blocks. They are NOT merged via `$ref` — the stdlib validators
(`*/Tools/easby-verify/check_*.py`) don't resolve cross-file refs, and each stage legitimately *extends* the core
with stage-specific fields. This file is the **single source of truth for the shared ranges/shapes**; keep the
inline copies in each schema in sync with it. Each schema carries a top-level `$comment` pointing here.

## `compression_core` (shared by Mixing + Mastering)
```
ratio            number  1.0 … 100
attack_ms        number  0 … 5000
release_ms       number  1 … 5000
threshold_db     number  -60 … 0
gain_reduction_db number  0 … 30
```
**Stage extensions (do NOT share):**
| Stage | Adds | Why |
|---|---|---|
| Mixing | `purpose: control \| effect \| glue` | per-track intent |
| Mastering | `type: broadband \| multiband \| parallel \| dynamic_eq \| none` | stereo-bus topology |

## `eq_move` (base; each stage tunes ranges)
```
freq_hz   number  20 … 20000
gain_db   number  (Mixing ±15 surgical/tonal · Mastering ±6 broad)
q         number  0.1 … 10   (Mastering skews wide/low-Q)
type      enum    bell | shelf_low | shelf_high | hpf | lpf | notch
```
Mixing = surgical/tonal per-track; Mastering = broad, gentle, often M/S. Ranges differ by stage **on purpose** —
that difference is the Mixing↔Mastering boundary, not duplication.

## Rule
Change a shared range here first, then mirror into both schemas (search the property name). A reviewer diffing
the two inline blocks against this file should find only the documented stage extensions differing.
