# FabFilter Pro-L 2 — FabFilter (true-peak brickwall limiter)

| | |
|---|---|
| Vendor / ver | FabFilter · Pro-L 2 (v2.x) |
| Type | Limiter — true-peak brickwall maximizer, 8 algorithms, loudness metering |
| Format | VST, VST3, CLAP, AU, AAX Native, AudioSuite (macOS 10.13+, Intel/Apple Silicon) |
| Source | manual: `FabFilter Pro-L 2/FabFilter Pro-L 2.pdf` · deep spec: `easby-programming/plugins/Pro-L2.md` (RE'd) |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
A professional true-peak limiter / loudness maximizer for the master bus, stems, or individual tracks. You drive the signal in with the **Gain** slider; Pro-L 2 raises perceived loudness while holding the output under a set ceiling. Its distinguishing traits: **eight program-dependent limiting algorithms** spanning transparent → aggressive → "glue/squash" characters, **true-peak (inter-sample) limiting** so the analog/MP3 reconstruction never overshoots, up to **32× linear-phase oversampling**, full **EBU R128 / ITU-R BS.1770-4 / ATSC A/85 loudness metering** (Momentary/Short-Term/Integrated + LRA + true-peak), surround/immersive up to **Dolby Atmos 9.1.6** with per-stage channel linking, dithering with three noise-shaping curves, and a large real-time level display with peak gain-reduction labels.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Gain** (slider) | 0 .. +30 dB | Input/threshold drive into the limiter — the main loudness control; raises level, then limiting holds the ceiling. Reverse-linked to Output Level (Alt/Cmd-drag drops ceiling by same amount). | Always — push until you reach target loudness / desired limiting amount. |
| **Style** | Transparent · Punchy · Dynamic · Allround · Aggressive · Modern · Bus · Safe | The 8 limiting algorithms, each a different character (see Notes for per-style behavior). Sets the *flavour* of limiting, not just intensity. | Pick by material: rock/pop → Transparent; EDM → Aggressive; drum bus glue → Bus; clean all-purpose loud → Modern (default). |
| **Lookahead** | 0 .. 5 ms | Time the limiter looks ahead to predict needed gain reduction for the transient stage. Short = louder but harder/more distortion + inter-sample peaks; long = safer/cleaner but transients can dull. | Lower for max loudness; raise (≥0.1 ms) to tame ISPs & distortion. <0.1 ms ≈ hard clipping. |
| **Attack** | 0 ms .. 10 s | Speed of the slower "release-envelope" stage onset (beyond the fast transient stage). Short attack lets the release stage engage sooner. | Short = safer/cleaner; long = more loudness/presence but risks pumping/distortion. |
| **Release** | 0 ms .. 10 s | How fast the gain recovers after limiting (program-dependent per style). | Short = louder/more aggressive, risks distortion; long = cleaner, less pumping. |
| **Channel Linking — Transients** | 0–100 % (stereo); extends to "100% All" in surround | Stereo-link amount for the fast transient stage. Less than 100% removes a short peak only in the channel where it occurs (often inaudible) → tighter stereo. | Often <100% on transients to preserve stereo image / stop one-side peaks pulling both. |
| **Channel Linking — Release** | 0–100 % (stereo); extends in surround | Stereo-link amount for the release stage. | Best near 100% to keep the stereo image stable during sustained limiting. |
| **Channel Link — C (Center)** | on/off (surround only) | Include center channels in their L/R pair's linking (else C stays independent). | Surround/Atmos when you want C glued to its stereo pair. |
| **Channel Link — LFE** | on/off (surround only) | Include LFE in all-channel linking (else LFE independent). | Surround/Atmos; usually leave off so LFE limits independently. |
| **Output Level** | −30 .. 0 dB (shows **dBTP** when True Peak Limiting on) | The output ceiling — max peak the limiter won't exceed. Reverse-linked to Gain. | Set to platform spec: −1.0 dBTP (EBU/streaming), −2.0 (ATSC), −0.1 safe; never exceed 0.0 dBTP. |
| **True Peak Limiting** | on/off | Ensures inter-sample (true) peaks in the output don't exceed Output Level — detects existing true peaks and attenuates overshoot the fast limiter creates. Adds ~5 ms latency. | Turn ON for any real release/master to prevent D/A & MP3 clipping. |
| **Oversampling** | Off · 2× · 4× · 8× · 16× · 32× | Runs the limiter at a multiple of host SR to reduce aliasing & inter-sample peaks (higher = better/cleaner, more CPU). 16×/32× CPU-intensive. | 4× (or 8×) recommended for normal use; combine with True Peak Limiting. 16×/32× for offline render. |
| **Dither** | Off · 16 · 18 · 20 · 22 · 24 Bits | Target output bit depth; adds TPDF noise before truncation to remove quantization distortion. | Only as the *final* stage when reducing bit depth (e.g. 16-bit CD master). Off for further processing / lossy. |
| **Noise Shaping** | None · Basic · Optimized · Weighted | Shapes the dither noise spectrum away from ear-sensitive bands. Basic = mild; Optimized = lower overall noise, HF boosted more; Weighted = lowest audible noise (tuned for 44.1 kHz). | Use with Dither; Optimized is a good default, Weighted at 44.1 kHz. |
| **Filter DC Offset** | on/off | Gentle high-pass that removes DC bias (from asymmetric saturation upstream) so limiting isn't triggered unnecessarily. | If input has DC offset / asymmetric waveform. |
| **Side Chain Triggering** | on/off | Routes the external side chain to feed the limiter's *detection* path instead of the main input. | **Stem mastering**: feed the full master to the side chain so each stem gets the exact same limiting as the master. |
| **Unity Gain** | on/off | Auto-sets Output Level to the inverse of current Gain so you hear limiting's effect *without* the loudness increase (level-matched A/B). | Temporarily, while auditioning settings — judge tone, not loudness. |
| **Audition Limiting** | on/off | Outputs only the *delta* (the gain reduction being applied) so you can hear exactly what/where limiting acts. | Diagnose how much/where the limiter is working. |
| **Global Bypass** | on/off | Latency-compensated, soft (click-free) bypass of the whole plug-in. | A/B against unprocessed. |
| **Lock Output** | on/off | Preserves Gain, Output Level, DC Offset, Unity Gain, True Peak Limiting, Oversampling, Dither, Noise Shaping when loading presets. | Audition presets without changing your loudness/output setup. |
| **Meter Scale** | −16 / −32 / −48 dB · K-12 / K-14 / K-20 · Loudness | Output/GR meter range; K-System for calibrated monitoring; Loudness switches the panel to LUFS metering. | −16 dB for fine limiting detail; K-14 for commercial monitoring; Loudness for LUFS targets. |
| **True Peak Metering (TP)** | on/off | Shows inter-sample peaks in the output meter (green light; reading turns orange near, red over 0 dBTP). | Keep ON whenever using True Peak Limiting / chasing a dBTP target. |
| **Display Mode** | Slow Down · Fast · Slow · Infinite · Off | Behavior of the real-time level display (scroll/refresh speed). | Slow Down to read GR peak labels; Infinite pairs with Integrated loudness; Off if distracting. |
| **Loudness Meter Target** | −9 / −14 / −23 / −24 LUFS · Custom | Desired Integrated loudness target. | −14 streaming (Spotify/YT), −9 CD, −23 EBU R128 broadcast, −24 ATSC. |
| **Loudness Time Scale** | Momentary · Short Term · Integrated | Which loudness window the big meter shows. | Integrated for final program loudness; Momentary/Short-Term while mixing. |
| **Loudness Meter Scale** | +9 / +18 LU · Absolute/Relative | Meter range above target (EBU +9 / +18 modes) and absolute vs relative readout. | Match your standard's mode; relative when working to a target. |
| **Loudness Auto-Reset** | on/off | Resets loudness/peak/GR readings when host playback starts. | On for repeated playback measurement passes. |
| **Resize / Scaling** | Compact · Small · Medium · Large · scaling % | Interface size (Compact hides real-time display for bigger meters) + DPI scaling; Full Screen button maximizes. | Compact for big meters; Full Screen for precise display work. |
| **MIDI Learn** | — | Associate any MIDI controller with any parameter. | Hardware control of Gain etc. |

## Use by lens
- **Producer (create):** Drop on a track/bus and push **Gain** for instant loudness while writing. Use the colorful styles as effects — **Bus** for drum-bus glue/squash, **Punchy** on single tracks (bass, vocal, guitar) for beat-edge, **Aggressive** for in-your-face EDM. Use **Unity Gain** to make sure it's actually sounding better, not just louder.
- **Mixing (balance):** Use as a transparent safety/level ceiling on the mix bus — **Transparent** or **Modern** with modest Gain, **True Peak Limiting** on, **Oversampling 4×**, Output ≈ −1 dBTP. Keep **Channel Link Transients** below 100% to protect the stereo image; watch the real-time display + GR labels to catch over-limiting.
- **Mastering (finalize):** The core job. Pick a style to taste, dial **Lookahead/Attack/Release** for character, set **Loudness Meter → Integrated** to a platform target (−14 streaming / −23 EBU / −9 CD), enable **True Peak Limiting + True Peak Metering**, set Output to the standard's dBTP, and add **Dither + Noise Shaping** only as the very last stage when going to 16-bit. For **stem mastering**, enable **Side Chain Triggering** and feed the full master to the side chain so every stem gets identical limiting.

## Notes / gotchas
- **Per-style character (manual):** *Transparent* — minimal pumping/coloring, rock/pop. *Punchy* — most apparent, adds flavor/pump, "safe", single tracks. *Dynamic* — enhances transients before limiting, preserves punch, great on rock. *Allround* — balanced loudness/transparency, any material. *Aggressive* — near-clipping, EDM/trance, also rock/metal/pop. *Modern* (default) — transparent, very high loudness, near-zero lookahead. *Bus* — NOT transparent; glue/pump/squash for drum bus & tracks. *Safe* — no distortion ever; delicate acoustic/classical/instruments.
- **Latency:** the four new styles (Aggressive, Modern, Bus, Safe), True Peak Limiting (~5 ms), and oversampling each add latency. For minimal latency use a Pro-L 1 style (e.g. Transparent) and disable TP + oversampling.
- **True-peak vs sample:** with TP off and OS off, output can leak inter-sample peaks above the ceiling; TP on + OS ≥ 8× clamps real true-peaks well under ceiling. Always quote dBTP with the oversampling factor near Nyquist (any finite-rate TP meter over-reads close to fs/2).
- **Dither once, last:** never dither more than once or before further gain/processing; pointless for AAC/MP3.
- **Channel linking defaults:** Release link starts at 100% (keep), Transients often <100%. In surround, knobs gain a second "All" range and C/LFE include buttons; mono version disables linking.
- **Presets** organized by genre (Acoustic, Clipping, Dance & Electronica, Pop, Rock, Single Channel) + Default Setting; use **Lock Output** to A/B them without changing loudness. Opens all Pro-L 1 presets; co-installs alongside Pro-L 1.
- Reads as a single instance: GPU-accelerated graphics, Smart Parameter Interpolation, MIDI Learn, undo/redo + A/B, double-click text entry (accepts `2x`, `50%`, `-1.0`), Pro Tools control-surface support, AudioSuite "Analyze".

## Deep spec (Programmer only)
`/Users/pongsathonkheeereekaew/.claude/skills/easby/easby-programming/plugins/Pro-L2.md` — measured per-style fingerprints (pre-duck/recover/harmonics, attack-release step shapes, program-dependence), full self-reported parameter table, true-peak verification.
