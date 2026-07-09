# SpaceBlender — Soundtoys (Reverb · ambient diffusion / texture)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Reverb — ambient/diffusion "soundscape" generator (very long, gapless, modulated wash; tone via tilt, texture via diffusion) |
| Tech | C++ VST3, shared "Soundtoys" framework (statically linked → one plugin per process). AAX = PACE; VST3 = pedalboard-hostable, no DRM wall. |
| Binary | universal2 (arm64+x86_64); VST3 not PACE-encrypted. |
| Provenance | **CLEAN** (all facts = black-box measurement of the licensed VST3 + public diffusion-reverb literature). No disasm. Tempo-sync (Beats) path measured only structurally — see below. |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 (Time mode) |
| Source | `private-research/Soundtoys/` (harness `Tools/{st_sysid.py,st_rev_run.py}`; data `out/SpaceBlender_*.json`) |

## Signal chain
```
x → [diffusion/reverb engine: decay time = time_msec (or beats), no distinct onset —
     gapless diffuse bloom; warp/freeze hold the tail] → texture (diffusion density / HF detail)
   → color (spectral tilt: dark ↔ bright) → modulation chorus → shape (X/Y morph of the space)
   → mix(wet/dry) → stereo out (correlated, mono-ish)
```
Not a plate and not a room: an **ambient texture machine** — extremely long, smooth, gap-free decays meant to sit *under* a mix as a pad/soundscape, with morphable "shape" coordinates.

## Per-stage formula  (all CLEAN — measured, Time mode)
- **Decay time (`time_msec` 100–60000, log taper)** (CLEAN): the master decay/size control. Measured T30 grows monotonically with the setting: 200 ms→1.0 s, 1 s→4.1 s, 4.5 s (default)→14.3 s, 10 s→30.5 s, 60 s→117.6 s. So the *displayed* time is **not** RT60 — it is a decay-scaling parameter (RT60 ≈ 2–6× the setting; super-long at the top → effectively infinite pad). **No predelay** and **no distinct onset** (tail-to-−40 dB measured 0.0 s at every setting) → the wet blooms immediately and diffusely, the ambient signature.
- **`color` (−100…+100)** = **spectral tilt / tone tilt** pivoting around ~250–500 Hz (CLEAN). color=−100 → dark tail (1 kHz −41, 4 kHz −66 dB rel.); color=0 → flat (all bands ≈ −15 dB); color=+100 → bright (1–2 kHz boosted to ≈ −9 dB, lows pulled down). A continuous dark↔bright voicing tilt.
- **`texture` (0–100)** = **diffusion density / HF detail** (CLEAN): spectrally near-neutral (only ~3 dB LF shift 0→100) — it changes the *grain/smoothness* of the diffusion rather than the gross spectrum (low texture = sparser/grainier, high = denser/smoother wash).
- **`mod` (0–100)** = chorus on the diffusion delays (CLEAN): tail pitch wobble rises with depth (held-1 kHz inst-freq std 3.2→5.3 Hz, ptp 18→27 Hz from 0→100) → keeps the long wash from forming static metallic resonances; gentler than the plates.
- **`shapex` / `shapey` (0–1, def 0.28 / 0.88)** (CLEAN, from param surface): an **X/Y morph** of the space (the GUI "blend pad" — interpolates between diffusion/space presets). Continuous coordinates; affects density/character of the bloom.
- **`warp` (bool)** / **`freeze` (bool)** (CLEAN, from param surface): performance holds — freeze = infinite-sustain capture of the current tail; warp = a pitch/texture transform of the held wash.
- **`syncmode` (Time / Beats)** + **`time_msec` / `beats_beats` (1–32)** (CLEAN structure): two ways to set the decay time — absolute ms (Time, measured) or tempo-synced beat count (Beats). **Beats path = tempo-synced, unmeasured** here (host tempo not driven in the offline harness); structurally it selects `beats_beats` × host-beat as the time.
- **`mix` (0–100)** (CLEAN): linear wet/dry; mix=0 → bit-exact dry (null −400 dB). Because the wet is a wide diffuse wash, peak level *drops* as mix rises (energy spread across the tail), unlike a discrete-echo effect.
- **Stereo image** (CLEAN): tail L/R correlation ≈ **0.93** → fairly mono/correlated (a centered ambient bed), in deliberate contrast to the fully-decorrelated plates. No width param.

## Why / design rationale (music ↔ code)
- **Gapless, onset-less bloom** → ambient/cinematic use wants the reverb to *be* the sound, not to follow a transient; removing early reflections and any pre-delay makes the wet feel like an ever-present atmosphere rather than "an effect on a source".
- **time = decay-scale, not RT60** → for soundscapes the musically useful control is "how long does the pad sustain", scaled into the tens-of-seconds region (up to 60 s → ~2 min RT60); exposing it as a time the user sweeps (and can tempo-sync) is more intuitive than an RT60 number nobody needs at that length.
- **color as a tilt, not separate hi/lo cuts** → one bipolar knob that darkens or brightens the whole wash is the fastest way to fit a pad into a track's spectrum (sit it under vocals = dark; make it shimmer on top = bright) — fewer controls, more "blend".
- **texture + shapeXY = morphable diffusion** → instead of fixed algorithm choices, the space is a continuous morph field, so users *design* an evolving ambience by ear (the "Blender" concept) rather than picking a preset reverb type.
- **freeze / warp** → turn the reverb into an instrument: freeze grabs an infinite pad from any moment; warp mangles it → sound-design territory, not just mixing.
- **Mono-ish correlated tail** → an ambient bed usually wants to sit *centered and behind* the stereo image (so it doesn't fight panned elements); high L/R correlation keeps it phase-coherent and mono-compatible — opposite design goal to the plates' max-width.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| mix | % | 0–100 (def 50) | linear wet/dry; 0 = bit-exact dry |
| syncmode | enum | Time / Beats (def Time) | selects time source |
| time_msec | ms | 100–60000 (def 4500) | decay/size; **not** RT60 (RT60 ≈ 2–6×); log taper |
| beats_beats | beats | 1–32 (def 9) | tempo-synced time (**unmeasured** — needs host tempo) |
| color | bipolar | −100…+100 (def 0) | spectral tilt: − dark / + bright, pivot ~250–500 Hz |
| mod | % | 0–100 (def 50) | chorus depth on diffusion |
| texture | % | 0–100 (def 50) | diffusion density / HF detail (near spectrally-neutral) |
| warp | bool | Off/On (def Off) | tail transform (sound-design) |
| freeze | bool | Off/On (def Off) | infinite sustain / hold |
| shapex | norm | 0–1 (def 0.28) | X/Y morph of the space (GUI blend pad) |
| shapey | norm | 0–1 (def 0.88) | " |

## CLEAN measurements
**Decay vs time (Time mode, Schroeder EDC):**
| time_msec | T20 (s) | T30 (s) |
|---|---|---|
| 200 | 1.7 | 1.0 |
| 500 | 3.0 | 2.3 |
| 1000 | 5.0 | 4.1 |
| 2000 | 8.4 | 7.1 |
| 4500 (def) | 16.5 | 14.3 |
| 10000 | 34.9 | 30.5 |
| 30000 | 99.6 | 89.9 |
| 60000 | 130.4 | 117.6 |

**color tilt** (tail bands, rel.): −100 → 1k −40.6 / 4k −65.7 dB (dark); 0 → all ≈ −15 dB (flat); +100 → 1k −10.0 / 2k −8.9 dB (bright).
**texture**: 0→100 ≈ spectrally flat (±3 dB LF), changes diffusion grain.
**mod**: held-1 kHz wobble ptp 17.6 (mod 0) → 27.1 Hz (100).
**mix**: 0 → null −400 dB; wider/diffuse so peak falls with mix.
**Stereo**: tail L/R corr 0.93 (mono-ish). **No predelay / no onset gap** (tail-to-−40 dB = 0.0 s at all times). **Latency**: reported 32 samples.

## To implement (CLEAN-only path for ES-L family)
- **Engine** = a deep **diffusion network** (long cascaded allpasses) or **FDN with very high feedback** sized for tens-of-seconds RT60; drive density up so there is *no* discernible early structure (onset-less bloom). `time_msec` → feedback-gain / line-length scale with RT60 ≈ 2–6× the dial; **freeze** = feedback→1.
- **color** = a single **bipolar tilt EQ** (shelf pair pivoting ~300 Hz, ±~12 dB at the extremes) on the wet bus.
- **texture** = modulate diffusion **density / allpass count or coefficient** (grain) with ~neutral magnitude.
- **mod** = slow chorus on the network delays (gentle; ptp ~20–30 Hz). **shapeX/Y** = a 2-D morph interpolating preset diffusion configs (own-voicing the map). **mix** = linear dry/wet. Keep the tail **correlated** (centered bed) — share more delay structure between L/R (corr ≈ 0.9), the opposite of the plate decorrelation. Tempo-sync (Beats) = `beats × (60/BPM)` → time.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). **REF** = disasm-derived (none used here).
