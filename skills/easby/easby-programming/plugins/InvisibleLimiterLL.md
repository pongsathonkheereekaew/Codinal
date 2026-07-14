# Invisible Limiter LL — A.O.M. (AOM Factory) (Limiter — transparent brickwall, **low-latency**)

| | |
|---|---|
| Vendor / ver | A.O.M. Factory · v1.18.9 (sibling of Invisible Limiter; bundle `Invisible_Limiter_LL.vst3`) |
| Type | Dynamics — **low-latency** mastering brickwall limiter. Same engine as Invisible Limiter, short lookahead. |
| Tech | C++/JUCE (AppKit + CoreText). No FFI. |
| Binary | universal (x86_64 + arm64), MH_BUNDLE. **Stripped** (3 exported syms, 434 total), **no DRM/PACE**. Same triage as the original → static is a wall, no usable REF. |
| Provenance | **100% CLEAN** (black-box measurement). |
| Measured on | v1.18.9 · SR 48000 · pedalboard 0.9.17 · 2026-06-26 |
| Source | `private-research/AOM_InvisibleLimiter/Tools/il_sysid.py --ll`, `…/data/measured_tables.txt` |

## Relationship to Invisible Limiter
**Same DSP engine, only the lookahead window differs.** Full spec, formulas, parameters, and rationale: **[InvisibleLimiter.md](InvisibleLimiter.md)**. Everything there applies byte-for-byte to LL except the latency, which is the LL build's entire reason to exist.

Measured to be **identical** between IL and LL (CLEAN, side-by-side):
- 9-param host surface, ranges, defaults — identical.
- Enum maps (overshoot / shape / channel_mode / oversampling_factor) — identical norm bands.
- Static brickwall curve — identical (ceiling accuracy 0.00 dB, knee 0 dB).
- True-peak behavior — identical (OS x1 +0.64 dB, OS x8 +0.04 dB over ceiling).
- Overshoot policy divergence (1 kHz square +6-over, OS x8) — **identical**: Thru +0.22 / Clip +0.00 / Suppress −0.84 dB sample-peak.
- OS aliasing rejection — identical (−25 / −38.8 / −50.8 / −63.6 / −74.1 dBc for x1…x16).
- Release behavior — identical: no release tail, no program ducking, GR time-localized, ~2–4 ms recovery.
- THD on hot steady tone — 0.000% (transparent). Sample-peak ceiling held exactly on single-sample +20 dB spikes.

## THE delta (CLEAN)
- **Lookahead / latency**: **LL = 336 samples = 7.000 ms @ 48 kHz** vs **IL = 2496 samples = 52.000 ms**. (Help-doc: LL "approx. 7 ms", IL "approx. 53 ms.") That is the entire difference — a **7.4× shorter** lookahead window. OS-independent in both (336 at x1…x16). Lookahead is a round number of ms → scales with SR.
- **Behavioral consequence** (interpretation): the shorter window gives less time to pre-shape the gain curve, so on very dense/sharp material LL has marginally less room to stay "invisible" (slightly more potential transient coloration / harder curve). At the SR and signals measured, both held the sample-peak ceiling exactly with 0% tone THD — the audible trade is the classic transparency-vs-latency one, not a curve/ceiling change. LL is for tracking, live monitoring, and low-latency mix-bus use; the 52 ms original is for offline/mastering where latency is free.

## Parameters
Identical to [InvisibleLimiter.md](InvisibleLimiter.md) (9 params, same units/ranges/enums/defaults).
**Harness note (same as IL):** pedalboard `raw_value` is the VST3 **normalized [0,1]** value — convert real dB writes `raw=(real−lo)/(hi−lo)` or the DSP ignores them.

## To implement (ES-L)
Build the IL architecture (see InvisibleLimiter.md "To implement") and expose the **lookahead window as a mode/param**: e.g. a "Latency: Normal (≈52 ms) / Low (≈7 ms)" switch. The kernel is otherwise unchanged — same minimal-area lookahead brickwall, same oversampled true-peak, same Overshoot policy. IL and LL are literally one engine with two lookahead presets; ES-L should mirror that (one limiter, a latency-mode control) rather than two code paths.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). **REF** = disasm-derived (none — stripped, no DRM).
