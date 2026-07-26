# ValhallaFreqEcho — Valhalla DSP (Frequency-Shifter + Echo FX)

| | |
|---|---|
| Vendor / ver | Valhalla DSP · v1.2.8 (Dec 2022 build) |
| Type | Single-sideband (Bode) **frequency shifter** + feedback **echo** with in-loop filters ("barberpole echo"). OFF-AXIS from ES-L dynamics — KB coverage only. |
| Tech | C++ / JUCE (VST3 via Steinberg SDK), Accelerate/vDSP. Hilbert analytic-signal SSB shifter (REF: `VPlug_FreqEcho::SetHilbertCoefs()`). |
| Binary | universal `x86_64+arm64` Mach-O bundle, **NOT stripped** (7968 syms; 185 Valhalla/VPlug DSP-class syms = REF roster), **NO DRM/PACE** (no `LC_ENCRYPTION_INFO`, no iLok). Not a shared engine (0 symbol overlap w/ sibling Valhallas). |
| Provenance | All behaviour **CLEAN** (pedalboard black-box). Architecture name (`SetHilbertCoefs`, `processBlock`) = **REF** (symbol roster, never shipped). |
| Measured on | ValhallaFreqEcho (Dec 2022 build) · 48kHz · pedalboard 0.9.17 · 2026-06-27 |
| Source | `private-research/Valhalla/{Tools,FreqEcho}/` · REF `private-research/_quarantine_disasm/Valhalla/FreqEcho/` |

## Signal chain
```
                 ┌──────────────── feedback loop (fb%) ─────────────────┐
                 ▼                                                       │
x ──► [+]──► SSB FREQ-SHIFT (+Δ Hz) ──► DELAY (ms or tempo-sync) ──► [lowcut HPF]──►[highcut LPF]──┤
      ▲                                                                                            │
      └────────────────────────────────── (sum) ──────────────────────────────────────────────────
                                                                          │
   wet path (above) ──┐                                                   ▼ (tap)
   dry path  x ───────┴──► LINEAR mix (1-w · dry + w · wet) ──► out   (stereo: R uses −Δ)
```
The shifter sits **inside** the feedback loop → every repeat is shifted again (+Δ cumulative) ⇒ the signature endless "barberpole" glide. The two filters are **in the loop** ⇒ each repeat is progressively band-limited (analog-echo darkening).

## Per-stage formula  (tag each CLEAN or REF)
- **SSB frequency shifter** (CLEAN; REF name `VPlug_FreqEcho::SetHilbertCoefs()`): output = **f + Δ Hz, additive constant-Hz** (NOT a pitch ratio). Verified F∈{200,500,1000,2000,3000}, all → F+Δ exactly (e.g. F+168 → 368/668/1168/2168/3168; a pitch shifter would give F·1.168). Single-sideband, Bode style via Hilbert/analytic signal: y = Re{ x_analytic · e^{j2πΔt} } (upper SSB) — measured **mirror sideband (f−Δ) = −61.8 dB**, **carrier feedthrough (f) = −125 dB**. Δ<0 ⇒ downshift (verified raw0.15 F=1000→832). vDSP usage = only `vDSP_vclr` (buffer clear) external ⇒ the Hilbert is a hand-rolled allpass/FIR quadrature network, **not** an FFT.
- **Shift taper** (CLEAN): `shift` raw[0,1] → ±1000 Hz, **symmetric bipolar exponential around raw0.5 (=0 Hz)**. Measured: raw 0.0→−1000, 0.2→−78, 0.4→−0.5, **0.5→0**, 0.6→+0.5, 0.8→+78, 1.0→+1000 Hz. Fine control near 0 Hz, expanding to the rails. raw≈0.5007 default = 0.00 Hz.
- **Echo / delay** (CLEAN): free delay `delay` exp taper 0.01–1000 ms (raw0.3=18.33, 0.4=47.65, 0.5=100, 0.65=239 ms). Echo period == the delay value. Tempo-sync via `sync` (see deferred).
- **Feedback loop gain** (CLEAN): `feedback%` → per-repeat loop gain g, monotonic, **g→1.0 (endless self-oscillation) at 100%**. Measured steady-state per-repeat ratio (delay 100 ms): fb30%≈−7.7 dB (g≈0.41), fb50%≈−2.8 dB (g≈0.72), fb70%≈−0.5 dB (g≈0.94), fb90%≈−0.04 dB (g≈0.99), **fb100% = 0 dB (g≈1.0, infinite)**. First repeat always steeper (one-time SSB-path insertion loss) then settles to the loop gain.
- **Barberpole spiral** (CLEAN — the signature): with shift≠0 AND feedback>0, each successive echo is shifted by another +Δ. Measured (delay 239 ms): shift +77.76 Hz → per-repeat step **+76.5 Hz** (settles to +76/+76/+76 across reps 3–6); shift +10.24 Hz → +8 Hz/repeat. n·Δ cumulative progression monotonic ⇒ confirmed endless-glide spiral.
- **In-loop filters** (CLEAN): `lowcut` HPF (20–3000 Hz, exp) and `highcut` LPF (50–15000 Hz, exp) live **inside** the feedback loop → cumulative per-repeat band-limiting. Measured (impulse, fb70%, delay47.65ms): highcut=3040Hz → centroid 363→95 Hz over repeats, 3kHz band −67dB rep1; lowcut=1510Hz → lows collapse 100Hz −74→−91dB, 300Hz −27→−60dB rep1→rep4. Even "wide" darkens (centroid 757→147 Hz) — HF rolls each pass.
- **Wet/dry mix** (CLEAN): **LINEAR** crossfade, NOT equal-power. Measured dry_lin = {1.0, 0.75, 0.5, 0.25, 0.0} and wet_lin = {0.0, 0.25, 0.5, 0.75, 1.0} for w = {0,25,50,75,100}%. At 50% both = 0.5 (−6.02 dB). dry = (1−w)·x, wet = w·shifted.
- **Stereo** (CLEAN): `stereo` enum {mono, stereo} (threshold raw≈0.55). **mono** = same shift both channels (L==R, corr 1.0). **stereo** = **opposite shift SIGN per channel** on the wet output: input 1000 @ +168 → L=1168 (+Δ), R=832 (−Δ), corr → 0.0 (full decorrelation / max width). Per-channel in-loop spiral step magnitude reads the same (+76 Hz both) ⇒ decorrelation comes from the opposite starting sideband, not opposite spiral direction (minor open Q).
- **Latency** (CLEAN): PDC = 0 samples (no oversampling FIR reported; Hilbert is allpass/IIR-style, zero reported latency).

## Why / design rationale (music ↔ code)
- **SSB frequency shift (additive Hz, not pitch ratio)** → **inharmonic / clangorous detune**. Because a constant-Hz add breaks the harmonic ratio (200→368 is not a musical interval; partials of a complex tone all move by the same Hz, NOT the same ratio), the result is metallic/bell-like/dissonant — a *special-FX* color, not a musical transpose. This is exactly why it's a FreqEcho FX and not a pitch shifter: the designer wants the weird, not the in-tune.
- **Shifter INSIDE the feedback loop** → **endless "barberpole" glide** (Shepard-tone-like illusion of perpetual rising/falling pitch). Each echo is re-shifted by +Δ, so repeats sweep continuously up (or down) the spectrum forever at fb→100%. Tiny shifts (±a few Hz) inside the loop also give slow **chorus/flange-like detuned smearing** of the echo tail.
- **Symmetric exponential shift taper around 0 Hz** → musically usable control: most expressive action (subtle ±Hz chorus/beating) is packed around the center where you spend most time; the ±1000 Hz extremes (full alien) are at the rails.
- **Filters IN the loop (not just on output)** → **analog tape/BBD-echo darkening**: each repeat gets darker (highcut) or thinner (lowcut), mimicking the cumulative bandwidth loss of analog delay lines — repeats decay in *timbre*, not just level, for a natural, non-fatiguing tail.
- **Linear (not equal-power) dry/wet** → predictable parallel-FX blend on a fully-wet special-effect; the dry stays present at unity until fully dialed out (the shifted content is so different from dry that equal-power's center boost would over-hot the mix).
- **Opposite shift sign per stereo channel** → **wide, swirling stereo** for free: L rises while R falls (or starts a mirror sideband), instantly decorrelating a mono source into a lush stereo field (corr 0) — a hallmark Valhalla "spaciousness from cheap DSP" move.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| wetdry | % | 0–100 (lin) | **LINEAR** mix: dry=(1−w), wet=w. raw=%/100. |
| shift | Hz | −1000…+1000 | **bipolar exp**, symmetric about raw0.5=0Hz. raw0.5007 default=0. SSB additive Hz. |
| delay | ms | 0.01–1000 | exp taper. raw0.3=18.33, 0.5=100, 0.65=239ms. Free (un-synced) delay. |
| sync | division idx | 0–23 (24 vals) | raw×23 = integer division index (raw0.0435≈1, 0.087≈2). Tempo-locked delay; **needs host transport/BPM** → division→ms map **deferred to REAPER** (string labels are bare numbers, no note names exposed). |
| feedback | % | 0–100 (lin) | → loop gain g; **g→1.0 endless at 100%**. fb50≈g0.72, fb70≈g0.94, fb90≈g0.99. |
| lowcut | Hz | 20–3000 | exp taper. HPF **in the feedback loop**. raw0.5=1510Hz. |
| highcut | Hz | 50–15000 | exp taper. LPF **in the feedback loop**. raw0.2=3040, 0.5=7520Hz. |
| stereo | enum | mono / stereo | threshold raw≈0.55. stereo = opposite shift sign per channel (corr→0). |
| bypass | bool | Off/On | host bypass. |

## FFI contract (if clean C ABI)
None — JUCE VST3, hosted via pedalboard. No exported C DSP API. (REF symbols: `ValhallaFreqEcho::processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&)`, `prepareToPlay(double,int)`, `setParameter(int,float)`, `VPlug_FreqEcho::SetHilbertCoefs()` — reference only.)

## CLEAN measurements
- Freq-shift law: out = f + Δ (constant Hz), F∈{200…3000} all confirmed. Pitch-ratio ruled out.
- SSB: mirror −61.8 dB, carrier feedthrough −125 dB (true single-sideband).
- Shift taper: ±1000 Hz symmetric exp around raw0.5=0 Hz (raw0.2→−78, 0.8→+78 Hz).
- Echo period = delay value (18.33/47.65/100/239 ms verified).
- Feedback→loop gain: g(fb) ≈ {30%:0.41, 50%:0.72, 70%:0.94, 90%:0.99, 100%:1.00 endless}.
- Barberpole: per-repeat shift = +Δ cumulative (+76.5 Hz/repeat measured for +77.76 Hz shift).
- In-loop filters: cumulative darkening (highcut) / thinning (lowcut) across repeats.
- Mix: linear (dry=1−w, wet=w; 50%=−6 dB both).
- Stereo: opposite shift sign per channel, corr 0.0; mono corr 1.0.
- Latency: PDC 0.

## To implement
CLEAN-only clone path (KB / generic FX engine — NOT for ES-L dynamics core):
1. **Analytic signal** via Hilbert transform (FIR quadrature pair or IIR allpass network — public DSP literature, e.g. two-path polyphase allpass Hilbert). Build x_a = x + j·H{x}.
2. **SSB shift**: y = Re{ x_a · e^{j2πΔt} } = x·cos(2πΔt) − H{x}·sin(2πΔt) (upper sideband). Δ from bipolar-exp taper. Lower sideband flips the sign for the opposite mirror; stereo R uses −Δ.
3. **Feedback delay line** (fractional, ms or tempo-sync), shifter + HPF (lowcut) + LPF (highcut) **inside** the loop, loop gain g(fb%) with g→1 at 100% (guard against >1 if matching exactly).
4. **Linear dry/wet**: out = (1−w)·dry + w·wet_loop.
5. Stereo widener = run the SSB with +Δ on L, −Δ on R.
- Reuse: generic biquad HPF/LPF (building-blocks), fractional delay line, quadrature-allpass Hilbert. No vendor coefficients needed (SSB math is textbook).

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (reproduce black-box before shipping). Here REF = symbol roster only (`SetHilbertCoefs`/`processBlock` names), used to *confirm* the measured SSB architecture; no code shipped.
