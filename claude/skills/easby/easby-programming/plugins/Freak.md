# Freak — Native Instruments (Frequency shifter / ring-mod / FM)

| | |
|---|---|
| Vendor / ver | Native Instruments · Freak **v1.3.7** (build NI_6_8_4_R2) |
| Type | Bode frequency-shifter / ring-mod (SSB↔DSB morph) with feedback + harmonics; 3 carrier modes (Radio/Oscillator/Sidechain) |
| Tech | C++ "**Effekt Rig**" engine (`ni::effektrig::dsp::freak::Freak` on `ModulatableDSPCore<4u,2u,19u>` — **4-in** = stereo+sidechain), **xsimd neon64** SIMD feedback path, Qt6.8.4 QML. **Shared engine** (Bite/Dirt/Freak/Raum). No FFI. |
| Binary | Mach-O universal, ~119 MB, not stripped, no PACE, Accelerate-linked |
| Provenance | CLEAN = pedalboard measurement (FFT of tone). REF = symbol roster (quarantined). |
| Measured on | Freak v1.3.7 · 48 kHz · pedalboard 0.9.17 · `NI_ModFX/Tools/{ni_sysid.py,freak2.py,freak3.py}` · 2026-06-26 |
| Source | `private-research/NI_ModFX/Tools/ni_sysid.py` · REF `_quarantine_disasm/NI_ModFX/Freak.dsp_symbols.ref.txt` |

## Shared engine
Same family as Bite/Dirt/Raum (see `Bite.md` + NOTICE). Unique: `<4u,2u,19u>` core (sidechain carrier),
`DomeFilter` (anti-image band filter), `computeFeedbackNode` (SIMD feedback), `s_audibleBandHz`.

## Signal chain
```
x → (BP pre-filter) → ×carrier(fx_mode) [quadrature mult: Hilbert/analytic → complex shift]
  → SSB/DSB select(type) → harmonics(higher-order sideband stack) → feedback loop(feedback)
  → stereo offset(stereo) → antifold(anti-image) → mix(dry/wet)
```
(REF: `setFxMode`,`setBPFilterOn`,`setSidechainSignal`,`computeFeedbackNode`,`DomeFilter`. Behaviour CLEAN.)

## Per-stage formula (CLEAN/REF)
- **Frequency-shifter core** (CLEAN, the key measurement): 1 kHz tone + `freq`=+200 Hz (Coarse) →
  output sidebands at **800 & 1200 Hz** (= f∓Δ and f+Δ), plus 2nd-order 400/1600 Hz. Carrier
  (1000 Hz) suppression and **lower-vs-upper sideband balance are set by `type`** ⇒ this is a true
  **Bode single-sideband frequency shifter** (Hilbert/analytic-signal quadrature), with `type`
  morphing SSB↔DSB:
  - **type = 0**  → carrier 1000 present (−68), both sidebands ~−62 → toward dry/ring blend.
  - **type = 50** → both sidebands EQUAL (500 & 1500 @ −68), carrier suppressed → **balanced ring-mod (DSB-SC)**.
  - **type = 100** → **upper sideband 1500 Hz dominant (−73), lower 499 suppressed (−43, ≈30 dB down)** →
    **single-sideband up-shift** (true freq shift, not ring-mod).
  So `type` = the SSB quadrature mix (lower↔suppressed↔upper). Confirmed: at type=50, `freq=+1000`
  and `freq=−1000` give **identical** output (DSB-SC is sign-symmetric); at type=100 the sign sets shift direction.
- **freq** (CLEAN): shift amount. **Range=Fine** ≈ ±a few Hz (vibrato/comb territory); **Range=Coarse**
  ±5000 Hz (param shows ±5000). Negative = down-shift.
- **harmonics** (CLEAN, 0–100%): stacks **higher-order sidebands** (multi-stage / nonlinear shift):
  shift=+500, harm 0 → sidebands 500/1500 only; harm 100 → adds 2498/3497/5497 Hz (rising series) at
  −35…−45 dBc. = harmonic-shifter "metallic" richness.
- **fx_mode** (CLEAN enum): **Radio** = AM-radio demodulation/heterodyne character (1 kHz in → strong
  even-harmonic comb 2k/4k/6k/8k/10k, independent of `freq` — a fixed demod stage, REF
  `setRadioProductDemodulation`/`handleParameterRadioTuning`); **Oscillator** = internal carrier
  (the SSB shifter measured above); **Sidechain** = external 3rd/4th-channel signal as carrier
  (`setSidechainSignal`; needs 4-ch host route — main-bus pedalboard can't feed it).
- **feedback** (CLEAN 0–100%, REF `computeFeedbackNode` SIMD): recirculate shifted output → cascading
  shift series / resonant comb (Freak's signature runaway sweep).
- **stereo** (CLEAN −50…+50%): L/R shift offset → stereo widening / barber-pole motion.
- **antifold** (CLEAN 0–100%): anti-aliasing for the shift when sidebands exceed Nyquist (`DomeFilter`).

## Why / design rationale
- **SSB shifter ≠ pitch shift**: adds a constant Hz offset → **inharmonic** partials (1000→1500 keeps
  spacing, breaks the harmonic series) = clangorous/metallic/robotic — the defining freq-shifter sound.
- **type morph SSB↔DSB** in one knob → one engine spans clean shift, ring-mod, and detuned-carrier
  textures; producer dials "how ring-moddy vs how shifty."
- **feedback** → barber-pole / infinite-glissando illusions and resonant drones (the Freak hero move).
- **Radio mode** → broken-transistor-radio / AM demod grit; **Sidechain** → vocoder-ish carrier from another track.
- **antifold/DomeFilter** → keeps large shifts from aliasing into garbage = usable across the full ±5 kHz.

## Parameters (CLEAN)
| param | unit | range | notes |
|---|---|---|---|
| range | enum | Fine / Coarse | scales `freq` (Fine ≈ ±few Hz, Coarse ±5 kHz) |
| freq | Hz | −5000 – +5000 | shift amount (sign = direction) |
| type | % | 0 – 100 | SSB↔DSB morph (0 carrier-leaning, 50 ring-mod, 100 single-sideband) |
| harmonics | % | 0 – 100 | higher-order sideband stack |
| feedback | % | 0 – 100 | recirculate shifted output |
| stereo | % | −50 – +50 | L/R shift offset (width) |
| antifold | % | 0 – 100 | anti-alias the shift (DomeFilter) |
| fx_mode | enum | Radio / Oscillator / Sidechain | carrier source |
| mix | % | 0 – 100 | dry/wet |
| bypass | bool | | |

## CLEAN measurements
Sideband tables (type sweep, harmonics sweep, Radio comb) above. type=±sign identity at 50% confirms DSB-SC.

## To implement (ES-L CLEAN path)
Analytic signal via Hilbert (FIR or allpass-pair) → complex multiply by carrier e^{jΔt} → take real
(cos·I − sin·Q) for upper, (cos·I + sin·Q) for lower; `type` = crossfade lower/carrier/upper. Harmonics =
cascade/nonlinear extra shift stages. Feedback path with delay+gain. Anti-image LP (DomeFilter) before
mix. Match measured sideband levels per `type` + harmonic series to null. Sidechain/Radio modes are extra carriers.

---
Provenance: **CLEAN** = measurement / public DSP / own voicing. **REF** = symbol roster (reference only).
