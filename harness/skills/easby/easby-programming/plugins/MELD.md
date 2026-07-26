# MELD — Metric Halo (Dynamics / Multi-FX channel strip)

| | |
|---|---|
| Vendor / ver | Metric Halo · v4.1.12.276 · AU `aufx`/`MELD`, also VST3/AAX |
| Type | Channel strip: EQ → MixHead (saturation) → Compressor → Limiter → Loudness maximizer |
| Tech | Mach-O universal, `MHShellAUFactory` (shared MHShell host, mono-repo `MHNativePlugins`); **PACE/Eden iLok DRM** → effectively stripped |
| Provenance | **CLEAN only** — black-box render-based (DRM blocks static); no DRM touched. **+ REAPER ReaScript: full 107-param dump + comp curve** (2026-06-22) |
| Source | `private-research/MELD/` — `MELD-RE-ANALYSIS.md`, `MELD-dsp-measured.md`, `MELD-parameters.md`, `freq_map.txt`, `limiter_loudness.txt`; REAPER probe via `../ML4000/Tools/ml_reaper_probe.lua` |

## Measured modules (CLEAN)
- **EQ** — params: Gain ±24 dB, Bandwidth 0.1–2.5 oct, Frequency **normalized 0..1** (GUI-mapped; measured
  map in `freq_map.txt`, +24 dB narrow peak saturates ~14.6 kHz). Bands 2–11 ship disabled (cosmetic defaults).
- **MixHead** — **odd-order symmetric saturation (tanh / cubic-like)**: soft-clip whose 3rd-order term scales
  with input³; slight asymmetry when driven dirtier. Recipe: `y = x − k·x³` or `tanh(g·x)/g`, drive-dependent g.
- **Compressor** (REAPER-measured, 107-param dump): **Character = `MIO`**; **ratio 2 → 1000:1** (1000:1 = brickwall); threshold norm 0.3 = **−42 dB**; **attack 16 ms, release 160 ms** (defaults); + knee, auto-gain, out-gain. Curve (thr −42, ratio 2, RMS): −24→−13.5, −12→−6.1, plateau ~−3 (0 dBFS peak). At ratio 1000:1 → −24→−20.7 (steep brickwall).
- **Limiter** — **true brickwall**.
- **Loudness** — **soft-clip density maximizer** (NOT brickwall): near-square, maximally dense
  (crest vs limiter −2.65 dB).

## Param-unit gotcha (CLEAN)
Gain/bandwidth/time = direct real units; **Frequency and Ratio are normalized 0..1** → need the GUI map
(`MELD-parameters.md`, `mappings_raw.txt`). Classic normalized-param trap.

## To implement
Saturation stage = symmetric soft-clip (`x−k·x³` / `tanh`) + LF/HF voicing tilt; optional 2nd asymmetric
stage when driven. Loudness = soft-clip density maximizer distinct from the brickwall limiter. All CLEAN.
