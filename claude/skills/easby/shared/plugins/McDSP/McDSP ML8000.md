# McDSP ML8000 — McDSP (limiter — 8-band multiband + master brickwall)

| | |
|---|---|
| Vendor / ver | McDSP · v7.x ("ML8000 Advanced Limiter", manual © 2022) |
| Type | Two-stage limiter: 8-band multiband limiter → master brickwall (look-ahead) limiter |
| Format | AAX Native/DSP (HD), AU, VST3; mono + stereo; VENUE S6L (HD). RTA only on AAX Native/AU/VST3 |
| Source | manual: `McDSP ML8000/McDSP ML8000.pdf` · deep spec: `easby-programming/plugins/ML8000.md` (MEASURED CLEAN via REAPER; no REF) |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
The ML8000 is a mastering-grade limiter built from two completely separate processing stages. Stage 1 is an 8-band **multiband limiter** that uses *active processing* (not a traditional crossover filter network) to split the spectrum with minimal phase distortion — each band has its own gain, threshold (output ceiling), limiter Knee/Mode/Focus, and can be soloed, key-listened, or linked to other bands. Stage 2 is a **master brickwall limiter**: a precise recreation of the patented ML4000 limiter algorithm with ~1 ms look-ahead, six Character Modes, soft-knee control, and a hard output ceiling that program peaks will not exceed. The distinctive bit is the combination — sculpt loudness band-by-band first, then guarantee a true output ceiling on the sum — plus McDSP's Knee + Mode + Focus controls that change *how* limiting "feels" (from transparent to crushed) rather than just how much. Excellent for transparent mastering ceilings, buss loudness, gentle dialog/vocal control, and aggressive drum-buss limiting.

## Controls (every param → musical effect)

### Master Limiter (final output stage)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Master Enable | on/off | Toggles the master brickwall limiter stage in/out | Bypass to compare, or to use only the multiband stage |
| Threshold | 0 to −36 dB | Level where the limiter starts catching peaks. **Ceiling − Threshold = max makeup gain** — lower it to drive more level/loudness into the ceiling | Push down for louder, denser output; the main "loudness" knob |
| Ceiling | 0 to −36 dB | Maximum output level — output will not exceed this | Set the final true-peak ceiling (e.g. −0.3 / −1.0 dB for masters) |
| Knee | 0–100 (0 = normal/hard, 100 = soft) | Transition softness into limiting. ~0%→0 dB, 25%→3 dB, 50%→6 dB, 75%→9 dB, 100%→12 dB knee. Softer = more gradual, less distortion | Raise for transparent/vocal work; keep low (<10%) for loud drum busses |
| Release | 1 ms to 5 s | Recovery speed after a peak. Faster = louder + more distortion; slower = cleaner but less loud. Can go as fast as 1 ms | Fast (<25 ms) to chase loudness; slower (>300 ms) to tame an over-loud signal cleanly |
| Mode | CLEAN / SOFT / SMART / DYNAMIC / LOUD / CRUSH | Secondary peak-detection character. CLEAN = most transparent → CRUSH = loudest + most distortion (see Mode table) | Pick the limiting "style"; most audible at Release <200 ms (very audible <20 ms) |

### Multi-band Limiter (first stage — global section)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Multi-band Enable | on/off | Toggles the entire 8-band stage in/out | Turn off for a pure single-stage limiter |
| Knee | 0–100 (0 = hard, 100 = soft) | Global limiting-transition softness for all bands (same calibration as master Knee) | Soften all bands at once for transparency |
| Release | 1 ms to 5 s ("RANGE" in spec table) | Global per-band recovery rate; faster = louder/more level | Set the overall multiband release feel |
| Mode | CLEAN / SOFT / SMART / DYNAMIC / LOUD / CRUSH | Character of secondary detection applied to all bands | Match band-limiting character to the source |
| Focus | FIXED / VARI-1 / VARI-2 | How each band *tracks/responds* to its own input. FIXED = standard; VARI-1 = slightly narrower "bell" per band; VARI-2 = most narrow bell, and preserves part of the bell peak | Tighten band articulation; VARI-2 for the most surgical per-band response |
| Snap | on/off (momentary) | Sets all 8 band Thresholds to the approximate current input-meter levels; auto-toggles off after | One-click starting point for all band ceilings, then fine-tune |

### Per-band controls (×8 bands)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Gain Fader | −24 to +24 dB | Boosts/cuts input signal into that band (post-gain feeds the input meter & limiter) | Shape band balance / drive a band harder into its threshold |
| Threshold Marker (THR) | 0 to −48 dB | Output ceiling of that band's limiter — prevents that band's signal from exceeding it. Aligned to the band input meter for visual setting | Set how hard each band is limited |
| IN (Band Enable) | on/off | Toggles that single band's limiter in/out | Disable bands you don't want limited |
| S (Solo) | on/off | Disables other (non-soloed) bands so this band can be auditioned (metering/monitoring) | Listen to one crossover band in isolation |
| M (Master Link) | on/off | Designates this band the **master** — its Gain/Threshold moves drag all linked bands (retaining offsets). Only one master at a time | Move several bands together while keeping their relative shape |
| L (Link) | on/off | Links this band to follow the master band's Gain/Threshold. Option/Alt-click "L" links *all* bands | Gang two-plus bands for quick simultaneous control |
| Key (Listen) | on/off | Monitors that band's input (key) signal before processing | Verify what frequencies each band is acting on |

### Response Plot (interactive display)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Crossover "Marker" (X1–X7) | 20 Hz–20 kHz (bands can't overlap; min ~1 octave apart) | Drag to set the 7 crossover frequencies splitting the 8 bands (defaults ~33/95/190/578/1600/3451/6901 Hz region per UI) | Re-place band edges by ear/eye on the plot |
| Gain "Dot" | −24 to +24 dB | Drag the per-band node to set that band's input gain (mirrors the Gain Fader) | Visual band-balance editing |
| HPF Enable | on/off | High-pass pre-filter that tracks crossover 1's frequency | Roll off subsonic rumble before limiting |
| LPF Enable | on/off | Low-pass pre-filter that tracks crossover 7's frequency | Tame the extreme top before limiting |

### Utility / display
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| RTA | on/off | Real-Time Analyzer overlay on the response plot (AAX Native/AU/VST3 only) | Watch the spectrum being affected |
| Master Meters | IN / GR / OUT | Input (post-multiband), gain-reduction, and final output (won't exceed Ceiling) | Monitor overall limiting + verify ceiling |
| Multi-band Meters | per band | Per-band input meter + threshold marker, calibrated identically so you can see peaks crossing threshold | Dial each band threshold visually |

## Use by lens
- **Producer (create):** Use it as a creative loudness/effect box. Crank Mode toward LOUD/CRUSH with a low Knee and fast Release for an aggressive, in-your-face drum or synth buss. Or set up the multiband stage as a quick tone-shaper (Gain dots) + safety limiter on a rough mix so nothing clips while you write.
- **Mixing (balance):** Buss level control — set a threshold + ceiling and treat the master stage as a compressor-with-brickwall so a group's level never exceeds the ceiling; tame dynamics of busses that aren't volume-automated. On vocals/dialog, run the 8-band stage as a frequency-selective compressor/limiter (e.g. catch plosives in the lows, "esses" in the highs) and let the master stage guarantee the ceiling. Use Knee >50% for gentle, transparent limiting on delicate sources.
- **Mastering (finalize):** The primary design target. Set the Ceiling to your delivery true-peak (e.g. −1.0 dBTP), lower Threshold for loudness, start with CLEAN/SMART Mode and a soft-ish Knee for transparency. Use the multiband stage to even out spectral peaks before the master brickwall so you reach target loudness with less audible pumping/distortion. Snap for a fast band-threshold starting point, then refine.

## Notes / gotchas
- **Two independent stages**: multiband and master limiter each have their own Enable; either can run alone. Signal path is multiband → master.
- **Active processing, not crossovers**: the 8-band split uses active processing to minimize inter-band phase distortion vs. a traditional filter network. Bands can't overlap and must stay ≥ ~1 octave apart.
- **Multiband Threshold = output ceiling per band** (not a downward-comp threshold); Master Threshold lowers to add makeup gain (loudness), Ceiling caps the output.
- **Snap auto-disables** after setting band thresholds — it's a one-shot, not a mode.
- **Solo is metering-oriented**: it lets you audition/monitor a band; per the deep-spec measurement it is metering/monitoring-style isolation (impulse through a soloed band still returns full-range), so don't rely on Solo to hard-isolate audio bands.
- **Pre-filters track crossovers**: HPF follows X1, LPF follows X7.
- **Latency / look-ahead**: ~1 ms look-ahead; manual states ~68 samples @44.1 kHz total DSP delay (deep-spec measured 51 samples @48 kHz in REAPER). Manual feature list also markets "Zero Latency"/"Brick wall look-ahead" — the look-ahead path adds the ~1 ms delay above. Double-precision processing.
- **Control editing**: Cmd-drag = fine; click text box to type a value (out-of-range snaps to nearest legal); Option-click = default; arrow keys nudge typed fields.
- **Linking & automation**: only one master band at a time; when automating linked bands, automate the master band — linked bands follow, and automating both can "fight."
- **RTA** is unavailable on AAX DSP/VENUE HD paths (Native/AU/VST3 only).
- **Six Character Modes** (apply to both stages): CLEAN (most transparent, least distortion) · SOFT (slightly louder, still transparent) · SMART (intelligent, more distortion than SOFT) · DYNAMIC (louder than SMART, hint of pumping) · LOUD (as loud as possible, minimal distortion) · CRUSH (louder than LOUD, some distortion).

## Deep spec (Programmer only)
`easby-programming/plugins/ML8000.md` — MEASURED CLEAN via REAPER offline render (parameter surface = 69 params, master + per-band limiter static curves, modes, crossover defaults, 51-sample latency). **No REF** (PACE-encrypted binary, no disassembly).
