# ValhallaSupermassive — Valhalla DSP (Delay / Reverb hybrid — FDN)

| | |
|---|---|
| Vendor / ver | Valhalla DSP, LLC · **v5.0.0** (free plugin) |
| Type | **Feedback-Delay-Network (FDN) delay↔reverb hybrid** — selectable topologies ("modes") spanning discrete echoes → dense ambient reverb. Off-axis from ES-L's dynamics core; pure KB coverage. |
| Tech | C++ / **JUCE**; UI = **WebKit** (web-rendered). Internal DSP statically linked. Links **Accelerate/vDSP**. |
| Binary | Mach-O **universal** (x86_64 + arm64) **bundle**. **STRIPPED** (only the 3 VST3 entry exports: `_GetPluginFactory`/`_bundleEntry`/`_bundleExit`; 0 DSP syms). **No DRM** (no PACE / `LC_ENCRYPTION_INFO`). **Not a shared engine** (self-contained; sibling FreqEcho/SpaceModulator/VintageVerb are separate binaries). |
| Provenance | **100% CLEAN** — all behavior by black-box measurement. **Stripped ⇒ no REF DSP roster** (static is a wall; documented in `_quarantine_disasm/Valhalla/Supermassive/REF_WALL_NOTE.md`). The plugin's embedded **help-tooltip strings** (user-facing docs, not disasm) independently corroborate every measurement and are cited as CLEAN. |
| Measured on | `ValhallaSupermassive (Nov 2025 build) · 48kHz · pedalboard 0.9.17 · 2026-06-27` |
| Source | `private-research/Valhalla/Supermassive/` (harness `Valhalla/Tools/valhalla_sysid.py` + `sm_probe*.py`) |

## Signal chain
```
x ─┬─────────────────────────────────────────────────────────────────────► (1-mix)·x  ── dry
   │
   └─► [MODE: select FDN topology] ─► FDN core:
            delay lines (base time = DELAY × WARP-spread per line)
            ├─ FEEDBACK (recirculation gain → decay time)
            ├─ DENSITY (diffusion / reflection-density build-up, mode-dependent)
            └─ MOD (modrate/moddepth modulate delay-line lengths → chorus/pitch wobble)
       ─► WIDTH (M/S stereo width) ─► LOW CUT + HIGH CUT (filters on the OUTPUT, not in-loop)
       ─► mix·wet ──────────────────────────────────────────────────────────► + dry  ─► out
```
- Latency: **PDC = 0** (no lookahead/oversampling reported). Real DSP confirmed (`ident` max|out−in| = 0.249, not passthrough).

## Per-stage formula  (tag each CLEAN or REF)
- **Topology select / MODE** (CLEAN): **22 distinct FDN topologies** (the 23rd normalized band wraps back to Gemini — quantization artifact). VST3 normalized→mode = 22 equal bands ~0.0425 wide; band-center raws measured (see Parameters). Each mode = a different delay-network size / feedback structure / diffusion preset → different decay, echo density, stereo behavior at *identical* user settings (verified: at fb50%/dens30%/delay≈150ms, RT60 ranges **2.5 s (Pleiades) → 10.9 s (Orion)**). Celestial names = presets, not parameters.
- **DELAY → tap times** (CLEAN): scales the FDN delay-line lengths, **0–2000 ms**. Impulse first-echo tracks the param at the top (300 ms→297 ms, 2000 ms→1998 ms); at small settings a **modal floor** dominates (0 ms setting still yields a ~167 ms first arrival in Gemini — the network's intrinsic minimum modal time). So DELAY is a global delay-time scaler over the whole network, not a single-tap time.
- **WARP → non-uniform tap spread** (CLEAN; help-string: *"adjusts the delay lengths relative to the DELAY setting. 0% = all delays are the same length"*): at 0% the impulse is a **uniform comb** (echoes at 218/406/577/739 ms, ~170 ms apart = single effective period). As warp rises each echo **splits into a detuned cluster** (at 50%: first echo → 174/184/196/210 ms); the comb becomes a dense, slightly inharmonic tap field → lusher, less metallic tails.
- **FEEDBACK → decay (RT60)** (CLEAN): recirculation gain. Monotone, strongly super-linear: **10%→1.0 s, 30%→1.9 s, 50%→3.1 s, 70%→6.1 s, 85%→12.7 s, 95%→30.8 s**, and **100% = freeze / near-infinite sustain** (tail floor only −32 dB at end of a 20 s impulse; effectively self-oscillating hold). (RT60 also strongly mode-dependent — see MODE.)
- **DENSITY → diffusion build-up** (CLEAN; help-string: *"0% = discrete echoes, 100% = echoes quickly turn to reverb"*): controls reflection density / diffusion when feedback is up. **Mode-dependent**: on Orion, 0%→1 discrete echo vs 100%→8+ echoes (dense smear) in the first 1.5 s; on already-dense modes (Great Annihilator) it's saturated. In several modes (Aquarius/Pisces) density doubles as a delay-vs-reverb blend control.
- **MOD (modrate × moddepth) → delay-line modulation** (CLEAN; help-string: *"controls the depth/rate of the delay modulation"*): modulates delay-line lengths → tail **chorusing / pitch wobble**. Spectral spread of a 1 kHz carrier in the tail: depth 0/50/100% → **3 / 26 / 64.5 Hz** (@ ~2 Hz rate); rate scales spread (0.06 Hz→42 Hz, 7.8 Hz→110 Hz @ depth 100%). modrate **0.01–10 Hz (exp taper)**, moddepth 0–100% linear.
- **WIDTH → M/S stereo width** (CLEAN; help-string: *"controls the width of the stereo image"*): **linear ±100%**. At 0% the tail collapses to mono (side energy −152 dB rel. mid); at ±100% side/mid = −3.5 dB (full width). Sign of width inverts side polarity (±100% measure identically in magnitude). Modes also have intrinsic stereo decorrelation (LR cross-corr 0.405 Gemini … −0.12 Hydra).
- **LOW CUT / HIGH CUT → OUTPUT filters** (CLEAN — *definitively output, not in-loop damping*): help-string confirms *"low/high cut filter on the **outputs**."* Decisive black-box test: with highcut fixed at 4160 Hz, the late-tail HF tilt is **identical at feedback 0.3 vs 0.9** (Δ < 0.1 dB). If the LPF were inside the feedback loop, the heavily-recirculated 0.9 tail would be far darker — it isn't ⇒ **single output-stage filters, no cumulative in-loop roll-off.** LOW CUT 10–2000 Hz (log), HIGH CUT 200–20000 Hz (log). (This is the notable design departure from classic reverb "damping," which is in-loop.)
- **MIX → equal-power dry/wet** (CLEAN): dry coefficient at 0/25/50/75/100% mix = **1.00 / 0.924 / 0.707 / 0.383 / 0.00** ⇒ **dry = cos(θ), wet = sin(θ)** constant-power crossfade (0.707 at center = −3 dB). UI exposes a mix-lock toggle.
- **CLEAR** (CLEAN): momentary button that flushes the delay/feedback buffers (kills a frozen/long tail). Help: *"clears the delay buffers."*
- **reserved1–4 = INERT (dead params)** (CLEAN): NULL-tested per param, impulse render at raw 0.0 vs 1.0 → **bit-exact identical output, max|Δ| = 0.0, residual = −∞ dB** for all four. Exposed to the host but **not wired to any DSP** (placeholder/automation slots). Stronger result than a modeled-but-disabled param (those leak a tiny residual) — these are truly unconnected.

## Why / design rationale (music ↔ code)
- **FDN with selectable topologies (22 "modes")** → one engine spans *tight slapback* → *infinite ambient wash* by swapping the recirculation network's size/structure → musical purpose: a single "supermassive" ambient-spaces box for sound-designers/producers chasing huge pads, risers, and dub delays. Choosing **topology presets** (vs exposing raw matrix coefficients) keeps a vast space navigable with one knob — and celestial naming sells the "deep space" identity.
- **WARP = non-uniform/detuned tap lengths** → breaks the periodic comb that a single delay time produces (which sounds metallic/flutter-y) into a dense inharmonic cluster → **lusher, smoother, more reverb-like tails** without raising feedback. Cheaper and more controllable than adding more delay lines.
- **DENSITY = diffusion build-up, mode-dependent** → lets the *same* mode morph from clean rhythmic echoes (0%) to a smeared reverb (100%) → producer can dial "delay vs reverb" continuously instead of switching plugins. Mode-gating it means each topology gets a tailored diffusion law.
- **MOD on the delay lines** → time-varying delay = chorus/detune in the tail → **de-correlates repeats and masks the metallic resonances of long FDN feedback** → the lush, "breathing," shimmer-adjacent character. A free plugin leans hard on mod (0–100% depth, up to 10 Hz) because it's a cheap way to sound expensive.
- **Filters on the OUTPUT (not in-loop)** → a deliberate simplification: tone-shape the wet result once, decoupling timbre from decay (changing brightness doesn't change RT60). Trades the "natural air absorption" feel of in-loop damping for predictable, decay-independent EQ — fits a creative delay box more than a physical-space emulator.
- **Equal-power mix + mix-lock** → −3 dB-center crossfade holds perceived loudness constant while sweeping wetness; lock keeps mix steady while auditioning presets (each mode/preset would otherwise carry its own mix).
- **Freeze at 100% feedback** → instant infinite-sustain pad/drone from any input → a signature ambient move; CLEAR gives a one-click escape.

## Parameters
| param | unit | range | taper / notes |
|---|---|---|---|
| mix | % | 0–100 | linear knob; **equal-power** dry/wet law (dry=cos, wet=sin). Lockable in UI. |
| delaysync | enum | Msec / Note / Dotted / Triplet | host-tempo sync source. **Needs host transport → DEFERRED to REAPER.** |
| delaynote | enum | 1/64T … 4/4T (tempo divisions) | only active when delaysync≠Msec. **DEFERRED to REAPER.** |
| delay_ms | ms | 0–2000 | piecewise ~exp taper (raw 0.5≈306 ms, 0.7≈531 ms, 0.9≈1300 ms). Global FDN tap-time scaler. |
| delaywarp | % | 0–100 | linear. 0%=uniform taps; >0 detunes/spreads tap lengths into clusters. |
| clear | button | Cleared / ClearedAgain | momentary; flushes delay buffers. |
| feedback | % | 0–100 | linear param; **super-linear → RT60** (50%≈3 s, 95%≈31 s, 100%=freeze). |
| density | % | 0–100 | linear; diffusion build-up (mode-dependent). |
| width | % | −100…+100 | linear M/S width; 0%=mono, ±100%=full (sign = side polarity). |
| lowcut | Hz | 10–2000 | **log** taper; output high-pass. |
| highcut | Hz | 200–20000 | **log** taper; output low-pass. |
| modrate | Hz | 0.01–10 | **exp** taper; delay-modulation LFO rate. |
| moddepth | % | 0–100 | linear; delay-modulation depth. |
| mode | enum (22) | see list ↓ | 22 equal normalized bands (~0.0425 each); FDN topology preset. |
| reserved1–4 | — | — | **INERT** (bit-exact null at raw 0 vs 1; not wired to DSP). |
| bypass | bool | — | host bypass. |

**Complete mode list (22, in order) + normalized band-center raw** (set `mode.raw_value` to the center to select):
| idx | mode | center raw | character (plugin help text, CLEAN) |
|---|---|---|---|
| 0 | **Gemini** | 0.0425 | single echoes, high density |
| 1 | **Hydra** | 0.1050 | double echoes / long decay |
| 2 | **Centaurus** | 0.1462 | repeating echoes → longer reverb |
| 3 | **Sagittarius** | 0.1888 | long reverb / repeating echoes / slow attack |
| 4 | **Great Annihilator** | 0.2300 | repeating echoes, with HUGE reverb |
| 5 | **Andromeda** | 0.2712 | long reverb / repeating echoes / long decay / slow attack |
| 6 | **Lyra** | 0.3137 | single echoes, low density |
| 7 | **Capricorn** | 0.3550 | single echoes, medium density |
| 8 | **Triangulum** | 0.3962 | long reverb / VERY LONG repeating echoes / long decay / slow attack |
| 9 | **Large Magellanic Cloud** | 0.4387 | (dense ambient cloud) |
| 10 | **Cirrus Major** | 0.4800 | longer predelay, strange long echo pattern, medium density |
| 11 | **Cirrus Minor** | 0.5212 | longer predelay, strange shorter echo pattern, low density |
| 12 | **Cassiopeia** | 0.5637 | sparse initial echoes, fast attack, high echo density over time |
| 13 | **Orion** | 0.6050 | fast attack, sparse initial echoes that build up quickly, long decays w/ higher Density |
| 14 | **Aquarius** | 0.6462 | delay/reverb combo; Density sets the reverb level |
| 15 | **Pisces** | 0.6887 | delay + high-density reverb combo; Density sets the reverb level |
| 16 | **Scorpio** | 0.7300 | single echoes, sparse initial density, fast attack, filtered decay |
| 17 | **Libra** | 0.7712 | long reverb / long repeating echoes / filtered decay / medium attack |
| 18 | **Leo** | 0.8137 | very long reverb / very long repeating echoes / filtered decay / slow attack |
| 19 | **Virgo** | 0.8550 | sparse filtered echoes, very low density |
| 20 | **Pleiades** | 0.8962 | dense reverb / short echoes / filtered decay / fast attack |
| 21 | **Sirius** | 0.9387 | very dense reverb / short echoes / filtered decay / fast attack / balanced mod / open |

*(mode descriptions are the plugin's own UI help text = user-facing docs, CLEAN; they independently confirm the measured RT60/density/predelay spread.)*

## FFI contract (if clean C ABI)
- **None.** Stripped JUCE bundle, no exported DSP / Rust-FFI. Black-box host (pedalboard) only.

## CLEAN measurements
- **ident**: max|out−in| = 0.249 (real DSP, not passthrough); PDC = 0.
- **reserved1–4 NULL**: max|Δ(raw0,raw1)| = **0.0** (bit-exact), residual = **−∞ dB** → INERT.
- **feedback→RT60 (s)**: 10%→1.01, 30%→1.93, 50%→3.07, 70%→6.08, 85%→12.68, 95%→30.78, 100%→freeze (−32 dB floor @20 s).
- **mode RT60 @fb50/dens30/delay≈150 ms (s)**: Pleiades 2.52, Cirrus Minor 2.87, Gemini 3.72, Hydra 9.35, Great Annihilator 10.58, Orion 10.90. Predelay ≈ 218–219 ms across modes. LR cross-corr: Gemini +0.41 (narrowest) → Hydra/Great Annihilator −0.11 (widest).
- **delay_ms first-echo**: 0 ms→167 ms (modal floor), 120 ms→206 ms, 300 ms→297 ms, 2000 ms→1998 ms.
- **delaywarp echo taps (ms)**: 0% = 218/406/577/739 (uniform); 50% = first echo splits to 174/184/196/210 cluster (detuned spread).
- **density (Orion)**: echoes in first 1.5 s = 1 (0%) → 8 (100%); mode-gated diffusion.
- **mod spread (1 kHz tail, −20 dB width)**: depth 0/50/100% = 3/26/64.5 Hz; rate 0.06/7.8 Hz = 42/110 Hz @ depth 100%.
- **filter loop-position**: late-tail HF tilt @highcut 4160 Hz = 7.91 dB (fb 0.3) vs 7.99 dB (fb 0.9), Δ 0.08 dB ⇒ **output filter, not in-loop**.
- **width**: side/mid −152 dB @0% (mono), −3.5 dB @±100%. **mix**: dry coeff 1.0/0.924/0.707/0.383/0.0 @0/25/50/75/100% (equal-power).

## To implement
Building blocks to reuse if cloning an ambient delay/reverb for the suite (all CLEAN — no product-firewall concern since this is OFF-AXIS from ES-L's dynamics):
- **FDN core** (N delay lines + orthogonal feedback matrix — Hadamard/Householder) with **per-line lengths = base DELAY × per-line ratio**, and **WARP = controlled non-uniform spread/detune** of those ratios (uniform → clustered). Build from **public DSP literature** (Jot & Chaigne FDN, Stautner–Puckette feedback matrices, Schroeder/Moorer diffusers — all textbook) + the `building-blocks/` delay-line primitive; **no vendor code needed** (clean-room, behavior matched to the measurements below).
- **Feedback→RT60 mapping**: map a 0–100% knob to a super-linear gain → RT60 (≈1 s at 10% to ≈31 s at 95%, freeze at 100%); near-unity loop gain = freeze.
- **Diffusion stage** (allpass-chain or mixing-matrix density), **mode-gated** so each topology has its own 0→reverb law.
- **Delay-line modulation** (per-line LFOs, modrate/moddepth) for chorused/de-correlated tails.
- **Output filters** (HP 10–2000 Hz, LP 200–20000 Hz) on the wet bus (NOT in the loop) + **equal-power dry/wet** mix.
- **M/S width** post-stage; **CLEAR** = buffer flush.
- Tempo-sync (delaysync/delaynote) deferred — implement against host transport.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (reproduce black-box before shipping). *This plugin: 100% CLEAN — binary is stripped (no REF roster); the only static artifacts are user-facing help strings, used as CLEAN corroboration.*
