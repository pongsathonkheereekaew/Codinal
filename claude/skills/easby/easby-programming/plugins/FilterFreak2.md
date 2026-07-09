# FilterFreak2 — Soundtoys (dual analog multimode filter)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Two-filter analog-modeled multimode filter (series/parallel routing, per-filter shape/freq/res/gain/order, link) |
| Tech | C++ VST3, shared Soundtoys framework. AAX = PACE; VST3 = pedalboard-hostable, no DRM wall. |
| Binary | universal VST3; not PACE-encrypted in the VST3 slice. |
| Provenance | **CLEAN** — black-box measurement of the licensed VST3 + public filter-DSP literature. No disassembly. |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (`Tools/st_sysid.py`, `Tools/ff_refine.py` → `out/FilterFreak2_routing.json`) |

## Signal chain
```
                         ┌─ Filter1 (shape1, fc1, res1, order1) → gain1 ─┐
x → inputgain → [Analog sat] →                                            (Series | Parallel) → [Analog sat] → outputgain → mix → y
                         └─ Filter2 (shape2, fc2, res2, order2) → gain2 ─┘
  Series   : x → F1 → F2 (cascade)
  Parallel : x → (F1 + F2) summed
  filterlink: couples the two filters' frequency controls (move fc1 → fc2 tracks)
```
Each filter = the **same engine as FilterFreak1** (4 shapes, order 2–8, log cutoff, dB-peak resonance, Analog
saturation/self-osc) plus a **per-filter output gain** (±24 dB).

## Per-stage formula  (all CLEAN — black-box)
- **Two independent multimode filters** (CLEAN): identical per-filter behavior to FilterFreak1 — slope
  6 dB/oct·order, log cutoff 20 Hz–20 kHz, resonance peak ≈ ½·resonance_db (≤40), Analog mode adds level-dependent
  saturation/self-oscillation. Verified Analog passband THD on the dual engine = **20.5 % @ 0 dBFS** (H2 −28,
  H3 −14) — same nonlinear character.
- **Routing (`filterrouting`)** (CLEAN, definitive):
  - **Series** (F1 LP500 → F2 HP2000): full cascade — no passband overlap ⇒ everything attenuated
    (100 Hz −52, 500 −27, 1k −25, 2k −27, 8k −48 dB). Signal passes through F1 *then* F2.
  - **Parallel** (F1 LP500 + F2 HP2000 summed): LF passes via LP (100 Hz −0.0, 500 −3.3), HF passes via HP
    (8k +0.2), **mid dips** (1k −9.0) ⇒ classic parallel LP+HP = band-reject / "spread" response.
  - **Dual bandpass:** Parallel → **two independent resonant peaks** (300 Hz +6, 3k +6, mid 1k −28 dB) =
    two-formant/dual-resonant character. Series → the two BPs multiply → much deeper (300/3k ≈ −20, 1k −30).
- **Per-filter gain (`gain1_db`/`gain2_db`)** (CLEAN): output trim on each filter path. gain1 = −12 dB dropped the
  300 Hz peak exactly −12 dB (from +6 to −6) while leaving F2's 3 kHz peak untouched → independent per-band level.
- **filterlink** (CLEAN): ON couples the frequency controls — setting fc1 → 1000 Hz dragged fc2 → 1000 Hz
  (locked tracking, useful for moving both filters together while keeping their offset).
- **Latency** (CLEAN): 45 samples (0.94 ms @ 48k), same as FilterFreak1.
- **Modulation:** one LFO/envelope/rhythm modulator (shared `modulationdepth`, `lfo_rate_hz` 0.01–256 free Hz,
  `tempo_bpm` sync). Free LFO measurable; **rhythm-sync + envelope = UNMEASURED** (no transport in pedalboard).

## Why / design rationale (music ↔ code)
- **Two filters, series OR parallel** → covers both **steeper / compound shaping** (series = stacked slopes, deep
  notches, formant-multiplying) and **dual-resonance / spread** sounds (parallel = two peaks, vocal-formant or
  wide band-reject) from one device → the creative "filter playground" use-case.
- **Per-filter gain trim** → balance the two resonant peaks (e.g. tame a screaming 3 kHz peak under a warm
  low-mid peak) → musical control of a dual-formant timbre without re-EQing downstream.
- **filterlink** → "move both, keep the interval" → sweep a two-peak vowel-like color across the spectrum while
  preserving its shape → the hands-on performance gesture Soundtoys filters are built around.
- **Same Analog nonlinearity as FF1** → consistent house "analog" warmth + the self-osc-enabling soft-clip; the
  dual structure just doubles the resonant voices.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| inputgain_db | dB | −24..+24 | global pre-gain (drives Analog sat) |
| outputgain_db | dB | −24..+24 | global makeup |
| mix | % | 0..100 | dry/wet |
| inoutmode | enum | Digital, Analog | Analog = saturation + self-osc (per-filter) |
| frequency1_hz / frequency2_hz | Hz | 20..20000 | per-filter cutoff, log taper |
| resonance1_db / resonance2_db | dB(peak)/2 | 0..180 | peak ≈ ½ value (≤40), → self-osc above |
| gain1_db / gain2_db | dB | −24..+24 | **per-filter output trim** (independent band level) |
| filter1shape / filter2shape | enum | Lowpass, Bandpass, Highpass, Notch | (defaults LP / BP) |
| filter1order / filter2order | poles | 2..8 | 6 dB/oct·order |
| filterlink | bool | Off/On | **couples fc1↔fc2** (linked tracking) |
| filterrouting | enum | Series, Parallel | cascade vs sum |
| modulationdepth | 0..1 | 0..1 | shared modulator depth |
| trigger | bool | Off/On | env-follower trigger — **UNMEASURED** |
| tempo_bpm | BPM | 30..240 | rhythm-sync — **UNMEASURED** (no transport) |
| lfo_rate_hz | Hz | 0.01..256 | free LFO, measurable |

## CLEAN measurements
- **Series LP500→HP2000:** 100 Hz −52, 315 −33, 500 −27, 800 −25, 1.25k −25, 2k −27, 5k −40, 8k −48, 20k −68 dB
  (deep two-sided rejection — no overlap).
- **Parallel LP500+HP2000:** 100 Hz 0.0, 500 −3.3, 1k −9.0, 2k −3.2, 8k +0.2 dB (band-reject / spread).
- **Dual BP, res 12:** Parallel 300 +6.0 / 1k −28 / 3k +6.2 dB; Series 300 −20 / 1k −30 / 3k −20 dB.
- **gain1 = −12 dB:** 300 Hz peak −6 (was +6), 3k peak +6.2 (unchanged) → independent ±24 dB per filter.
- **filterlink ON:** fc1→1000 ⇒ fc2 reads 1000 (tracks).
- **Analog dual-engine passband THD @ 0 dBFS:** 20.5 % (H2 −28, H3 −14). **Latency:** 45 samp (0.94 ms).
- All single-filter laws inherited from FilterFreak1 (slope/cutoff/resonance/Analog identical engine).

## To implement (CLEAN-only path)
- **Reuse the FilterFreak1 SVF core** (TPT/ZDF, 4 shapes, order cascade, dB-peak resonance, Analog soft-clip
  wrapper) and instantiate **two**; add a **per-filter output gain** and a **routing switch**:
  - Series: `y = F2(F1(x))`. Parallel: `y = F1(x) + F2(x)`.
  - filterlink: when ON, derive fc2 from fc1 (lock or preserve offset).
- For ES-X/ES-L this gives a dual-resonant tone-shaper / band-reject building block; the parallel dual-BP mode is
  a cheap formant/vowel effect. Tempo-sync + envelope modulators are deferred (not core to the filter color).

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). **REF** = none used.
