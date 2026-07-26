# LittlePlate — Soundtoys (Reverb · EMT-140-style plate)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Reverb — single EMT-140-style metal-plate (mono-in stereo-out tank) |
| Tech | C++ VST3, shared "Soundtoys" framework (statically linked across the 23-plugin suite → one plugin per process). AAX = PACE; VST3 = pedalboard-hostable, no DRM wall. |
| Binary | universal2 (arm64+x86_64); VST3 not PACE-encrypted; static framework dup-ObjC means co-loading two Soundtoys VST3s crashes — isolate per process. |
| Provenance | **CLEAN** (all facts = black-box measurement of the licensed VST3 + public plate-reverb literature). No disasm. |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys/` (harness `Tools/st_sysid.py`, `Tools/st_rev_run.py`; data `out/LittlePlate_*.json`) |

## Signal chain
```
x(mono) → input → [Decay-set plate tank: dense allpass/comb network, mono→2ch,
                   intrinsic HF damping] → (optional chorus modulation of tank delays)
                 → low-cut HP on the wet → mix(wet/dry) → stereo out (decorrelated L/R)
```
Single fixed plate voicing (the "little" sibling of SuperPlate's Classic-140 model). Five params only.

## Per-stage formula  (all CLEAN — measured)
- **Plate tank** (CLEAN): a high-density reverberator (plate = a driven steel sheet → extremely dense early modal field, no discrete echoes). Measured early-tap density at −30 dB is "wall-to-wall" (probe saturates its 40-tap cap inside ~60 ms) ⇒ very high echo density from the first millisecond, the plate signature (vs a room's sparse early reflections). Mono input → two **decorrelated** output channels (tail L/R correlation ≈ **−0.02**, i.e. independent left/right pickups — fixed-wide, no width control).
- **Decay → RT60** (CLEAN): the displayed **Decay** value *is* the target reverberation time in seconds. Measured RT60 (Schroeder EDC, T20/T30) tracks the label across the range; HF damping makes the *broadband* T30 read a touch longer than the mid-band label at the short end. The control is a **continuous** normalized parameter (the GUI shows ~24 detents, but the VST3 param interpolates smoothly — a finer raw sweep yields >24 distinct values). Top of range = **Infinite** (non-decaying freeze; render-limited measurement ≈45–55 s, effectively sustains).
- **Low-cut (`low_cut_hz` 20–1000)** (CLEAN): 1-pole-ish **high-pass on the wet** path (pre/in-tank). At lc=1000 the 60 Hz tail band drops ~−40 dB vs lc=20, while ≥500 Hz is untouched → clears low-end mud from the reverb without thinning the body.
- **Intrinsic HF damping** (CLEAN): even with low-cut at minimum the tail rolls off steeply above ~1 kHz (1k≈−33, 2k≈−43, 4k≈−60, 8k≈−93 dB rel. its own peak) → high frequencies decay much faster than mids/lows. This frequency-dependent decay is *built into the plate model* (no user HF-damp knob) and is the EMT-140 "darkening-with-time" character.
- **Modulation (`mod_enable` bool)** (CLEAN): a low-rate chorus on the tank delay lines. Enabling roughly **doubles** the tail's pitch wobble (instantaneous-frequency std 5.0→9.2 Hz, peak-to-peak 33→63 Hz on a held 1 kHz carrier) → breaks up metallic ringing/flutter, smooths the tail.
- **Mix (`mix` 0–100 %)** (CLEAN): linear wet/dry. mix=0 → bit-exact dry passthrough (null −400 dB). Increasing mix raises the wet proportion; at 100 % the output is fully wet.

## Why / design rationale (music ↔ code)
- **Plate, not room/hall** → instant ultra-dense diffusion with *no* discernible early reflections → the classic 1970s vocal/snare "sheen". A plate has no geometry, so there is no pre-delay-by-distance and no slap-back; you get smooth wash from sample one. Purpose: a fast, always-flattering ambience.
- **Decay label = RT60 seconds** → the one knob a user actually thinks in ("how long does it ring?") is exposed directly, no abstract "size". The continuous taper with named detents gives recallable musical times.
- **Built-in HF damping (no knob)** → real plates lose highs faster than lows; baking this in keeps the reverb from ever sounding brittle/digital and means the single control set can't be misused into harshness. Trades flexibility for foolproof warmth — the "Little" ethos.
- **Decorrelated L/R, fixed wide** → a mono source blooms into a wide stereo image with near-zero interchannel correlation → maximum width/envelopment with no comb-filtering when summed. No width knob because "always wide" is the desired plate behavior.
- **Mod = anti-flutter** → dense fixed delay networks ring on sustained tones; slow chorus detunes the modes so the tail shimmers instead of buzzing. Off by default for purists, on for lushness.
- **Low-cut only (no high-cut)** → the plate already self-damps highs, so the one tone control users need is a low-cut to keep big decays out of the bass. Minimal, opinionated control set.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| mix | % | 0–100 (def 100) | linear wet/dry; 0 = bit-exact dry |
| decay | s (RT60) | ~0.50 … 51.83, + **Infinite** | continuous normalized param; label ≈ target RT60 s; GUI ~24 detents but VST3 interpolates |
| low_cut_hz | Hz | 20–1000 (def 20) | HP on wet; log taper (20/53/141/376/1000 at norm 0/.25/.5/.75/1) |
| mod_enable | bool | Off/On (def Off) | chorus on tank delays; ~2× tail wobble when on |

## CLEAN measurements
**Decay → RT60** (low-cut at 20 Hz; Schroeder EDC):
| decay raw | displayed label | T20 (s) | T30 (s) |
|---|---|---|---|
| 0.00 | 0.50 | 0.93 | 0.89 |
| 0.10 | 0.81 | 1.03 | 1.00 |
| 0.20 | 1.32 | 1.34 | 1.33 |
| 0.30 | 2.14 | 2.06 | 2.06 |
| 0.45 | 4.44 | 4.52 | 5.08 |
| 0.60 | 9.19 | 9.97 | 11.5 |
| 0.75 | 19.03 | 25.6 | 29.8 |
| 0.90 | 39.40 | 71.6* | 65.1* |
| 1.00 | Infinite | (sustains) | (sustains) |
*very long settings exceed practical render windows → values are lower-bounds; treat the label as the spec.

**Modulation** (held 1 kHz, decay≈9s): off → inst-freq std 5.0 Hz / ptp 33 Hz; on → std 9.2 Hz / ptp 63 Hz.
**Low-cut tail bands** (rel. peak, decay≈4.4s): lc=20 → 60Hz −15.0 dB; lc=1000 → 60Hz −56.5 dB (≥500 Hz unchanged ≈−28 dB).
**Mix**: 0→null −400 dB; 25→null −14.2; 50→−7.9; 100→−1.2 dB (linear wet blend).
**Width**: tail L/R correlation −0.019 (fully decorrelated, fixed). **Latency**: reported 32 samples.

## To implement (CLEAN-only path for ES-L family)
- **Plate tank** = a dense **FDN** (8–16 delay lines, lossless mixing matrix e.g. Hadamard) or a Dattorro-style **figure-of-8 allpass+modulated-delay plate** (Dattorro 1997, *Effect Design Part 1: Reverberator*). Either reaches the measured wall-to-wall density.
- **Decay** = set per-line feedback gain g so that RT60 = −3·L_total / log10(g·…); expose the knob directly as RT60 seconds (label = value). Add an **Infinite** detent = g→1 (no loss).
- **HF damping** = one-pole low-pass in each feedback path (frequency-dependent decay) tuned so the tail's 8 kHz energy sits ~60–90 dB below mid by ~2 s — reproduces the measured −33/−43/−60/−93 dB tilt without a user knob.
- **Modulation** = slow (~0.5–1.5 Hz) LFO on a few delay lengths, depth ≈ the off→on doubling of wobble; bool enable.
- **Low-cut** = 1-pole HP on the wet bus, 20–1000 Hz log. **Mix** = linear dry/wet. **Decorrelation** = different delay-line tap sets / mixing-matrix rows feeding L vs R (→ corr ≈ 0).

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). **REF** = disasm-derived (none used here).
