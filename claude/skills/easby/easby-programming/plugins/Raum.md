# Raum — Native Instruments (Algorithmic reverb)

| | |
|---|---|
| Vendor / ver | Native Instruments · Raum **v1.3.7** (build NI_6_8_4_R2) |
| Type | Algorithmic reverb — **Galois-sequence FDN** + modulated allpass diffuser, 3 modes (Grounded/Airy/Cosmic), freeze |
| Tech | C++ "**Effekt Rig**" engine (`ni::effektrig::dsp::raum::Raum` on `ModulatableDSPCore<2u,2u,19u>`), Qt6.8.4 QML. **Shared engine** (Bite/Dirt/Freak/Raum). No FFI. |
| Binary | Mach-O universal, ~119 MB, not stripped, no PACE, Accelerate-linked |
| Provenance | CLEAN = pedalboard impulse measurement (RT60/onset/modes). REF = symbol roster (quarantined). |
| Measured on | Raum v1.3.7 · 48 kHz · pedalboard 0.9.17 · `NI_ModFX/Tools/{ni_sysid.py,raum2.py,raum3.py}` · 2026-06-26 |
| Source | `private-research/NI_ModFX/Tools/ni_sysid.py` · REF `_quarantine_disasm/NI_ModFX/Raum.dsp_symbols.ref.txt` |

## Shared engine
Same family as Bite/Dirt/Freak (see `Bite.md` + NOTICE). Internal reverb classes (REF, names only):
`raum::galoisreverbextended::GaloisReverbExtended` (Galois-sequence feedback-delay-network tank,
`setDiffuserLength`/`updateDiffusion`), `raum::diffuser::Diffuser` (modulated nested allpass,
`setDenseMode`/`setModulationFreq`/`calculateModFrequency`), `raum::util::{AllPassNested,
MultiWriteDelayLine, StereoDelay}`, `MultiMode2ndOrderButterworth<float>` (cuts).

## Signal chain
```
x → pre-delay (predelay / sync) → input diffuser (diffusion, modulated allpass)
  → Galois-FDN tank (size, decay, feedback, modulation, density) with in-loop damping (damp)
  → low_cut / high_cut (Butterworth) → freeze hold → output section (mix dry/wet, reverb level)
```
(REF: `setPreDelay`, `Diffuser`, `GaloisReverbExtended`, `setLowpassCoeffs(MultiMode2ndOrderButterworth)`,
`setMode`, `triggerDensityModeChange`, `setFreeze`, `processOutputSectionSmoothedParameters`. Behaviour CLEAN.)

## Per-stage formula (CLEAN/REF)
- **Decay → RT60** (CLEAN): `decay` is enumerated **0.25 s … 200 s** and **directly = RT60**.
  Measured (mode Airy, Schroeder backward-integration): `decay=0.5 s`→RT60 0.44 s; `4.8 s`→4.85 s;
  ~linear 1:1 (slight under-read from window). So `decay` *is* the reverb time, not a feedback %.
- **Modes** (CLEAN): `Grounded / Airy / Cosmic` = three FDN algorithms (REF `Raum::Modes`,
  `setMode`):
  - **Grounded** — short room/ambience: RT60 ≈ 0.06 s even with `decay=2 s` ⇒ **caps the tail**
    (tight, damped, "grounded" space).
  - **Airy** — hall: tail tracks `decay` fully (RT60 ≈ decay), bright/open.
  - **Cosmic** — like Airy for RT60 but with heavier modulation/feedback character (huge/infinite-leaning).
- **size** (CLEAN 0–100%): scales delay-line lengths → mild RT60 + modal-density change
  (decay=4.8 s: size10→RT60 4.62 s, size50→4.87, size90→5.14) — size stretches the tank, decay sets damping.
- **feedback** (CLEAN 0–100%): tank regeneration on top of `decay` (push toward self-oscillation / freeze-like).
- **freeze** (CLEAN bool, REF `setFreeze`): infinite-hold the tank (sustains the current tail; input
  damped). Measured tail still present multi-seconds with input gone.
- **predelay** (CLEAN 0–2000 ms, REF `setPreDelay` + sync/numerator/denominator/mode): delays the
  **reverb tank**, not the very first sample — the diffuse onset still begins ~immediately; predelay
  offsets the recirculating reverb relative to the direct/early energy. Tempo-syncable (`sync`,
  `setPreDelayNumerator/Denominator/Mode`).
- **diffusion** (CLEAN 0–100%): input allpass diffuser amount (smears transients into smooth wash).
- **density** (CLEAN enum **Dense / Sparse**, REF `setDensityMode`/`triggerDensityModeChange`): echo
  texture — Sparse = fewer/more-discrete reflections (more grain/modulation), Dense = smooth.
- **modulation** (CLEAN 0–100%, REF `Diffuser::setModulation`/`calculateModFrequency`): chorused tank
  (de-metallizes long tails, adds movement).
- **damp** (CLEAN 0–100%): HF decay damping inside the loop (darker tail over time).
- **low_cut / high_cut** (CLEAN, REF `MultiMode2ndOrderButterworth`): pre/post Butterworth shel, low_cut
  enumerated as dB-labeled, high_cut 1 kHz…(off) — tone-shape the wet.
- **mix** dry/wet, **reverb** wet level, **mixlock** (lock mix when changing preset).
- **Latency** (CLEAN): impulse onset ~0 (no reported lookahead/PDC in measured path).

## Why / design rationale
- **Galois-sequence FDN** (vs plain Hadamard FDN) → maximal-length-sequence delay tap pattern gives a
  very even, colorless modal density quickly → smooth, "expensive" tail with few delay lines.
- **Modulated nested allpass diffuser** → kills metallic comb-flutter on transients and long tails =
  the lush, chorused Raum signature; `density` toggles smooth-wash vs grainy-discrete character.
- **3 modes = 3 spaces** → Grounded (tight room, decay-capped) / Airy (true hall) / Cosmic (ambient
  pad/infinite) cover ambience→hall→sound-design in one engine.
- **freeze + feedback + huge decay (200 s)** → drone/pad sound-design, not just naturalistic reverb.
- **predelay on the tank not the direct** → keeps transient clarity (direct + early stay punchy) while the
  diffuse tail arrives late = classic "separate the dry from the wash" mixing move; tempo-syncable.

## Parameters (CLEAN)
| param | unit | range | notes |
|---|---|---|---|
| mode | enum | Grounded / Airy / Cosmic | FDN algorithm (Grounded caps RT60) |
| decay | s | 0.25 – 200 (enum) | = RT60 (≈1:1) |
| size | % | 0 – 100 | tank length scale (mild RT + density) |
| feedback | % | 0 – 100 | extra tank regen |
| diffusion | % | 0 – 100 | input allpass smear |
| density | enum | Dense / Sparse | echo texture |
| modulation | % | 0 – 100 | tank chorus/movement |
| damp | % | 0 – 100 | in-loop HF damping |
| predelay | ms | 0 – 2000 | pre-tank delay (tempo-syncable via `sync`) |
| sync | bool | | tempo-sync predelay |
| low_cut | enum (dB-labeled) | Off … | Butterworth low shelf/cut |
| high_cut | Hz | 1 kHz … Off | Butterworth high cut |
| mix | % | 0 – 100 | dry/wet |
| reverb | % | 0 – 100 | wet level |
| freeze | bool | | infinite hold |
| mixlock | bool | | lock mix on preset change |
| bypass | bool | | |

## CLEAN measurements
decay→RT60 (0.44/4.85 s), size→RT60 (4.62/4.87/5.14 s), mode RT60 (Grounded 0.06 / Airy = decay /
Cosmic = decay), freeze sustains, predelay offsets tank not direct, density Dense vs Sparse texture.

## To implement (ES-L CLEAN path)
FDN reverb (public literature: Jot/Schroeder FDN, maximal-length/Galois tap lengths, unitary feedback
matrix) + modulated nested-allpass input diffuser + per-loop one-pole damping + Butterworth low/high
cuts + pre-delay line (tempo-sync) + freeze (feedback→1, input mute). Map `decay`→RT60 1:1, `size`→delay
scale, mode→3 matrices/damping presets. Null-match RT60 + tail spectrum per mode.

---
Provenance: **CLEAN** = measurement / public DSP / own voicing. **REF** = symbol roster (reference only).
