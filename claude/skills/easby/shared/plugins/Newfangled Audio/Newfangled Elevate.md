# Newfangled Elevate — Newfangled Audio (adaptive multiband mastering limiter / maximizer)

| | |
|---|---|
| Vendor / ver | Newfangled Audio (distributed by Eventide) · v1.12.0 |
| Type | Mastering limiter + maximizer with adaptive multiband processing, human-ear (Mel-scale) filter bank, per-band EQ + transient shaping, and spectral clipper |
| Format | VST / VST3 / AU (Components) / AAX |
| Source | manual: `Newfangled Elevate/Newfangled Elevate.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Elevate is a "mastering limiter with a brain": it raises loudness while preserving (or improving) dynamic perception and tonal balance. Audio is split by a **triangular auditory filter bank** of up to **26 bands spaced on the Mel scale** (modeled on the critical bands of human hearing), and **machine-learning / adaptive algorithms** set the gain, speed (attack/release), look-ahead, and transient emphasis **per band in real time** to minimize pumping, breathing, distortion, and stereo/tonal shifts. On top of the adaptive engine, the four sub-modules expose manual per-band EQ gain and per-band transient emphasis, plus a final **spectral clipper** that overdrives the signal without making it "tubby." What's distinct: the adaptivity (it reacts to the program), the perceptual band layout, and the ability to keep tuning tonal balance and transients *after* the limiting stage.

## Controls (every param → musical effect)

### Navigation / global (always visible)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| ACTIVE | on/off | Master bypass for all processing. With **Match Level** on, bypassed state applies the equivalent clean gain so you A/B at the same theoretical level | True bypass A/B; pair with Match Level for fair loudness-matched comparisons |
| Δ (Delta Listen) | toggle | Subtracts output from input — you hear only what the processor is *changing* | Audit exactly what Elevate is doing to the audio |
| Match Level | toggle | When ACTIVE is off, boosts the dry signal to match the requested gain so limited vs. unlimited compare at equal loudness (output may exceed 0 dBFS — leave headroom) | Honest "is the processing helping?" checks |
| MASTER INPUT LEVEL | dB (trim, knob above INPUT meter) | Trims level into the processor | Hit limiter harder/softer; fix too-low / too-hot input; target a non-0 dBFS input standard |
| OUTPUT — AUTO | on/off | Auto-reduces master output by the total GAIN+DRIVE added, so you compare processed vs. source at equal level. **Turn OFF before bouncing** or you'll reduce gain instead of adding it | Loudness-matched auditioning while dialing settings |
| MASTER OUTPUT LEVEL | dB (manual mode via down-arrow next to AUTO) | Manual output trim (post-limiter, pre-meter) | Target output standard other than 0 dBFS; manual final-level set |
| GAIN LOCK | toggle | Locks gain-related params (GAIN, DRIVE, CEILING, INPUT, OUTPUT) so loading presets won't jump your loudness — only the GAIN:DRIVE *ratio* updates from the preset, not total GAIN+DRIVE | Browse presets for *tone/character* without level jumps |
| UNDO / REDO | — | Multi-level undo/redo of parameter changes | Step back through edits |
| A/B · A>B | — | Two compare slots; A>B/B>A copies one state to the other | Compare two full settings |

### LIMITER section (Main Parameters page)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| NUMBER OF BANDS | dropdown (1 … 26 Band), next to LIMITER label | Resolution of the adaptive engine — how many filter bands the LIMITER + TRANSIENT algorithms use. 26 = max detail/CPU. **1 Band turns it into a standard single-band look-ahead limiter and disables all ADAPTIVE params** | Lower to save CPU; pick fewer bands if quality holds; 1 Band for plain limiting |
| TRUE PEAK | on/off | Inter-sample peak limiting (limits on reconstructed peaks, not samples). Output meter switches to true-peak readout. Slightly higher CPU | Broadcast/streaming compliance; lossy codec (mp3/mp4) delivery; prevent ISP overshoot distortion |
| GAIN | 0 … 12 dB | Amount of limiting gain (a.k.a. "threshold" on other limiters) — drives signal into the soft-knee limiter. Has own on/off button | The primary loudness control |
| ADAPTIVE GAIN | 0 … ~9 dB (knob) | Lets the algorithm vary gain reduction **per band** (more reduction on the loudest bands near the limit) — value = dB each band may stray from the others. Behaves like multiband limiting; too much can shift tonal balance. Own on/off | Transparent loudness without obvious pumping; back off if tone shifts |
| SPEED | Slow … Fast (≈ ms; combined attack+release) | Overall limiter dynamics speed. Faster = louder but more distortion risk; program-dependent | Trade loudness vs. distortion for the material |
| ADAPTIVE SPEED (a.k.a. ADAPTIVE DYNAMICS) | 0 … 100 % | Adapts attack/release/look-ahead **per band**; the core anti-"pumping & breathing" / anti-distortion control. Own on/off | Keep loud masters clean and natural |
| CEILING | -12 … 0 dB (slider) | Maximum output level — affects **both** LIMITER and SPECTRAL CLIPPER | Set the true output ceiling (e.g. -1 dBTP) |

### TRANSIENT EMPHASIS section (Main Parameters page)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| TRANSIENT EMPHASIS | Clean … Emphasized (slider, global) | Compensates for limiter squashing of fast transients, or over-emphasizes them for a more explosive sound (then driven into the clipper). Own on/off | Restore punch lost to limiting; add attack/impact |
| ADAPTIVE TRANSIENT | 0 … 100 % (Single Band … Multi Band) | Adapts transient emphasis **per band** — at higher %, adjacent bands track together but distant bands don't, so kick/snare/cymbal attacks pop without affecting the whole mix or each other. Powerful — use with care. Own on/off | Bring out specific percussive transients selectively |

### SPECTRAL CLIPPER section (Main Parameters + Clipper page)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| DRIVE | 0 … 12 dB | Drives LIMITER output into the spectral clipper for extra loudness + (soft) distortion, following the SHAPE curve. Frequency-domain design avoids the low-passed "tubby" sound and preserves tonal balance. Own on/off | Aggressive loudness on transients; "extra oomph" for hard genres |
| (CLIPPER) SHAPE | Soft … Hard (0 … 100 %) | Shape of the clipping gain curve; optimal set for max boost with minimal harmonics. At DRIVE 0 dB no gain is added and soft = hard | Soft for transparency, hard for grit |

### FILTER BANK sub-module page (defines the bands all other sections use)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| AUDITORY FILTER BANK (band count) | dropdown (1 … 26) | Sets how many bands the signal is split into; auto-spaces them on the Mel scale between current min/max. Changing it re-defines the bands shown on the EQ + Transient pages | Same as NUMBER OF BANDS — resolution vs. CPU |
| MEL / CUSTOM | radio toggle | MEL = perceptual auto-spacing of center frequencies; CUSTOM = you've moved a band's center freq manually (auto-selected when you drag one) | Switch to CUSTOM to target program-specific resonances |
| BAND SOLO | per-band toggle (shift/ctrl-click for multiple) | Solos the output of one or several bands. Shared across Filter Bank / EQ / Transient pages | Find problem frequencies; isolate a band to tune it |
| INSERT FILTER (+) | per-band button | Inserts a new band between the selected band and the next (more resolution where needed); greyed out at max bands | Need finer control in one frequency region |
| REMOVE FILTER (−) | per-band button | Removes the selected band without moving neighbors' center freqs | Cull redundant bands while tuning |
| FILTER CENTER FREQUENCIES | per-band text/slider (Hz) | Sets each band's center frequency (default = critical bands of hearing); retune to match key elements of your material | Align a band to a kick/bass resonance, etc. |

### LIMITER/EQ sub-module page
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| LIMITER GAIN | 0 … 12 dB | Same GAIN as Main page, with per-band breakout below | Detailed limiting view |
| ADAPTIVE GAIN | 0 … 12 dB | Same ADAPTIVE GAIN as Main page, per-band breakout | — |
| GAIN PER BAND | per-band ± dB sliders | Manual additive EQ — boost/cut each band (graphic-EQ style; click-drag a band, or shift-drag to draw a curve). Own on/off | Post-limiter tonal sculpting; corrective/creative EQ |
| DRAW CURVE | toggle | Switch between drawing one curve across all sliders vs. editing sliders individually (Shift inverts current mode) | Fast broad EQ moves vs. surgical tweaks |
| RESET GAINS | button | Resets all per-band gains to 0 dB | Start the EQ over |
| BAND SOLO | per-band | Solo band(s) — full algorithm still runs; only what you hear/see changes | Audit a band's processing |
| METERING (behind sliders) | input / output / gain-reduction per band (slowed) | Visualizes per-band level + GR; good for seeing ADAPTIVE GAIN at work | — |

### TRANSIENT sub-module page
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| TRANSIENT EMPHASIS | Clean … Emphasized | Same as Main page, with per-band breakout | — |
| ADAPTIVE TRANSIENT | 0 … 100 % | Same as Main page, per-band breakout | — |
| TRANSIENT EMPHASIS PER BAND | per-band 0 … 200 % sliders | Reduce (<100%) or increase (>100%) transient emphasis on each band individually; 100% = neutral. Click-drag or shift-draw a curve. Own on/off | Bring out transients in specific ranges (kick/snare) only |
| DRAW CURVE | toggle | Draw one curve across all transient sliders vs. edit individually (Shift inverts) | Broad vs. surgical transient shaping |
| RESET TRANS | button | Resets all transient sliders to 100% | Start over |
| BAND SOLO | per-band | Shared solo state across pages | Isolate to tune |
| METERING (behind sliders) | per-band transient-emphasis applied (slowed) | Shows effect of ADAPTIVE TRANSIENT across the spectrum | — |

### Settings panel
| control | range / unit | what it does |
|---|---|---|
| Apply Dither | Off / 24 / 20 / 16 / 12 / 8 bits | Output dither to target bit depth |
| Show Meters | on/off | Show/hide extra meter glow (RADAR glow, level-detector envelope graph, curve graphic) |
| Brightness | % | Brightness of those meter glows/graphics |
| OpenGL Graphics Rendering | on/off | GPU rendering (reopen UI to apply); also enables the center-section scrolling meters |
| Color Scheme | dropdown (e.g. Modern, Newfangled) | UI color theme; affects meter colors (e.g. red input-over-output cue) |
| Presets Folder — Reveal | button | Opens presets folder (for sharing) |
| Default Settings — Save | button | Saves current state as plug-in default startup state |

### Metering (read-only)
- **Input / Output bar meters** — Peak (ticks), RMS (solid + numeric), Peak Hold (numeric); output side adds a global **gain-reduction** meter. Output becomes **true-peak** when TRUE PEAK is on. Click Peak Hold (or bypass) to clear holds.
- **Center scrolling meters** (OpenGL on): **Input/Output** (input peak vs. output peak over time; red input poking above = consider lowering MASTER INPUT + adding GAIN); **Gain Reduction** (per-band GR + transient over time, Stack or Spread waveform views — best view of what Elevate does over time *and* frequency); **Filter Bank** (per-band input/output/GR bar graph, slowed/averaged — best view of frequency distribution).

## Use by lens
- **Producer (create):** Throw it on a bus or master for instant loudness + glue. Use TRANSIENT EMPHASIS (and per-band on the Transient page) to make drums slap; push DRIVE with hard SHAPE for aggressive EDM/hip-hop energy. Browse the included presets (APS Mastering, Matt Lange, Jeremy Lubsey, Eric Beam, ROCAsound, Chris Tabron, John McCaig) with GAIN LOCK on to audition character without level jumps.
- **Mixing (balance):** Use the per-band GAIN PER BAND as a smart, post-limiter EQ to tame or lift ranges; SOLO bands to hunt problem frequencies. Keep ADAPTIVE GAIN/SPEED engaged for transparency; use ADAPTIVE TRANSIENT to protect snare/kick attack on a drum bus without squashing the rest. MATCH LEVEL / OUTPUT AUTO + Δ to verify you're improving, not just louder.
- **Mastering (finalize):** Set CEILING (e.g. -1 dB), enable TRUE PEAK for streaming/broadcast and lossy delivery, then raise GAIN to taste with ADAPTIVE GAIN + ADAPTIVE SPEED keeping it clean. Use TRANSIENT EMPHASIS to recover punch a brickwall would lose; DRIVE/CLIPPER (soft SHAPE) for the last dB without pumping. **Turn OUTPUT AUTO off before bouncing.** Watch the scrolling Gain Reduction (Spread) and Filter Bank meters to confirm even, musical processing. Mind the "too loud" warning — chase quality, not just LUFS.

## Notes / gotchas
- **OUTPUT AUTO and Match Level are auditioning aids** — they reduce/boost level for fair comparison. AUTO **must be off** before printing the final track or you'll *lose* gain instead of adding it; with Match Level on while bypassed, output can far exceed 0 dBFS (leave headroom).
- **ACTIVE bypass with Match Level** can clip your DAW master if you lack headroom (applies the clean gain you're asking for).
- **Band count drives CPU.** 26 bands = max quality + max load; reducing bands often sounds nearly identical. **1 Band disables all ADAPTIVE params** (plain look-ahead limiter + transient/clipper).
- **TRUE PEAK** adds CPU and slightly alters processing; it also repurposes the output meter to true-peak.
- **CEILING governs both limiter and spectral clipper.** GAIN ≈ threshold; DRIVE feeds the clipper; ADAPTIVE controls are the secret sauce — pull them back if you hear tonal shift/over-emphasis (they're "powerful, use with care").
- **CUSTOM filter centers + per-band gain/transient** let you target specific instruments (e.g. focus a band on a kick's resonance) — band edits on the Filter Bank page propagate to the EQ and Transient pages.
- Linear-phase auditory (Mel-scale) filters; uses Eigen and PFFFT libraries. Distributed by Eventide; **iLok / PACE** licensing (2 activations, computer or dongle). UI is resizable (drag bottom-right corner; save over default to persist).

## Deep spec (Programmer only)
Not reverse-engineered — capability only.
