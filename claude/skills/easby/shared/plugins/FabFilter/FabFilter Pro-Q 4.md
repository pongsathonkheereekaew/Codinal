# FabFilter Pro-Q 4 — FabFilter (Parametric EQ)

| | |
|---|---|
| Vendor / ver | FabFilter · Pro-Q 4 (v4.x) |
| Type | Parametric EQ — dynamic + spectral, multi-phase, per-band M/S, surround |
| Format | VST, VST3, CLAP, AU (macOS), AAX Native, AudioSuite (+ AUv3 on iPad). macOS 10.13+, Intel or Apple Silicon |
| Source | manual: `FabFilter Pro-Q 4/FabFilter Pro-Q 4.pdf` · deep spec: `easby-programming/plugins/Pro-Q4.md` (RE'd — Programmer-only) |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Pro-Q 4 is FabFilter's flagship parametric equalizer and the de-facto workhorse EQ for mixing and mastering. Up to 24 bands, each with 10 filter shapes and a continuous slope (0–96 dB/oct or Brickwall), edited directly on a large interactive curve display. Beyond static EQ, every Bell/Shelf/Flat-Tilt band can become **dynamic** (level-dependent gain, like a per-band multiband comp/expander) or **spectral** (triggers only on offending frequencies *within* the band, leaving the rest untouched). Three processing engines — Zero Latency, Natural Phase (analog-matched min-phase), and Linear Phase (variable resolution) — plus per-band L/R/M/S placement, full surround up to 9.1.6 Dolby Atmos, EQ Match, an Instance List that controls every Pro-Q 4 in the session, EQ Sketch (draw a whole curve in one gesture), Spectrum Grab, and optional Subtle/Warm analog "character" saturation. Distinct for combining surgical precision, the smoothest workflow in the category, and dynamic/spectral processing folded naturally into normal EQ work.

## Controls (every param → musical effect)

### Per-band (×24, edited via interactive display or floating band controls)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Bypass (band) | on/off | Mutes this band only (dimmed + red light); also Alt-click the band dot | A/B a single move without losing it |
| Shape | Bell, Low Shelf, Low Cut, High Shelf, High Cut, Notch, Band Pass, Tilt Shelf, Flat Tilt, All Pass | Filter type. Bell = versatile boost/cut; Cuts = remove below/above fc; Notch = surgical kill; Band Pass = isolate; Tilt/Flat Tilt = tilt spectrum about fc; All Pass = phase-only | Match the tool to the job; All Pass for phase alignment instead of polarity flip |
| Frequency | 5 Hz – 30 kHz | Center/corner freq of the band (display extends to 30 kHz so HF filter skirts still shape audible range) | Place the move; multi-select adjusts in parallel |
| Gain | −30 … +30 dB | Boost/cut amount. Only used by Bell, Shelf, Flat Tilt | Tone shaping; multi-select scales gains relative to each other |
| Slope | 0 – 96 dB/oct (+ Brickwall on Low/High Cut), fractional | Steepness for any shape (e.g. 3.5 dB/oct HP). Bell/Notch min 0; Low Cut/High Cut/Band Pass min 12 (others 6) | Gentle vs surgical filtering; Brickwall = near-vertical cliff |
| Q | 0.025 – 40 (1 = default BW) | Bandwidth — narrow/wide. Not adjustable at 6 dB/oct. Shelf Q internally tuned for musical shapes | Tighten for surgical notches, widen for broad tone |
| Gain-Q interaction | on/off (button between Gain & Q) | Analog-console behavior: Q auto-narrows as gain rises, slight gain added as Q narrows. Bell only | Want musical, console-like bells |
| Dynamic range | −30 … +30 dB (ring around Gain) | Makes band dynamic. Negative = compress (gain reduces over threshold), positive = expand/boost. Bell/Shelf/Flat-Tilt only. Live gain shown as yellow bar in the ring | De-ess, tame resonances, brighten transient-dependent, dynamic mastering |
| Stereo placement | Stereo / Left / Right / Mid / Side (+ surround speaker sets) | Which channel(s) the band processes | M/S mastering, fix one-sided artefacts, widen/narrow by band |
| Split | button (scissors) | Duplicates band into L+R (or M+S) copies for independent tweaking | Quickly diverge the two channels |
| Prev / Next band | buttons | Step through bands; shows band number (for host automation ID) | Identify a band when automating |
| Delete | button | Removes selected band(s) (recoverable via Undo). Bands don't renumber on delete | Clean up |

### Dynamic band sub-controls (appear when Dynamic range ≠ 0, after clicking Expand >>)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Expand >> | toggle | Switches from Auto (program-dependent atk/rel/threshold/knee) to manual mode, revealing the panel below. Hide it to revert to Auto | Auto is great default; expand only when you need control |
| Threshold | slider (top = Auto) | Trigger level; trigger level shown in slider for easy dialing. Soft knee internally | Set where dynamics kick in |
| Attack / Release | center 50% = Auto | <50% faster, >50% slower than auto | Snap onto transients vs smooth riding |
| Triggering | Band / Free | Band = detect on the band's freq range; Free = exposes low/high-cut sidechain filters to shape the trigger | Trigger on a different freq than you're moving |
| External side chain | on/off | Trigger from plug-in's external SC input instead of the input signal | Duck/expand from another source |
| Audition | hold button | Listen to the current trigger signal | Verify what's driving the dynamics |
| Spectral | toggle (top of ring) | Switches band from whole-band dynamic to per-frequency (spectral) processing. Forces linear phase on that band | Treat varying problem freqs surgically |
| Spectral Density | slider (spectral only) | Selectivity: low = wide ranges triggered, high = very narrow/specific | Broad vs pinpoint spectral treatment |
| Spectral Tilt | toggle, +3 dB/oct (spectral only, on by default) | Tilts input spectrum before triggering so HF triggers a bit more — pink-noise-like balance | Natural results on full-range/complex audio |
| Bypass dynamics | button (left of ring) | Bypass just the dynamic behavior of selected bands | Compare static vs dynamic |
| Clear dynamics | button | Resets dynamic range to 0 → back to normal band | Undo dynamic behavior |

### Global / bottom-bar
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Processing mode | Zero Latency / Natural Phase / Linear Phase | EQ engine. Zero Latency = analog-magnitude match, 0 latency. Natural Phase = analog magnitude+phase match, low fixed latency, no cramping. Linear Phase = phase-preserving FIR with latency | ZL/Natural for nearly everything; Linear Phase to avoid phase-cancellation on parallel/crossfaded material |
| Processing Resolution | Low / Medium / High / Very High / Maximum (Linear/Spectral) | FIR resolution vs latency. ~70 ms (Low) → ~1509 ms (Maximum) @44.1k. Higher = better LF resolution, more pre-ring | Match to material; Low/Medium for HF, High+ for LF |
| Character | Clean / Subtle / Warm | Adds vintage saturation. Clean = transparent; Subtle = gentle program-dependent color; Warm = more apparent tube-like saturation | "Mix into" coloration across the session, or per-track warmth |
| Instance List | button (center) | Opens overview of all Pro-Q 4 instances in session — view/edit curves, spectrums, collisions; starting point for EQ Match. Zoom levels, filter, Quick Jump, pin tracks, minimap | Set up whole-mix EQ fast, spot collisions |
| Spectrum analyzer | Pre / Post / SC-Ext toggles + panel | Real-time analyzer. Panel: **Range** (60/90/120 dB), **Resolution** (Low 1024 → Maximum 8192 pts), **Speed** (release), **Tilt** (default 4.5 dB/oct), Freeze, Spectrum Grab toggle, Show Collisions | Judge moves visually; pick external spectrum from any instance |
| EQ Match | via Instance List menu | Auto-creates bands to match a reference spectrum (input/sidechain/another instance/audio file). Step 1 analyze, Step 2 set number of bands, Finish | Match a vocal take or a reference master |
| Spectrum Grab | hover spectrum / hold | Freezes spectrum; drag a labeled peak to create a Bell band there. Permanent mode for multiple grabs | Grab and correct an obvious peak instantly |
| EQ Sketch | button (bottom-left) | Draw the entire EQ curve in one left-to-right gesture; auto-creates LP/HP/shelves/bells from your stroke | Lightning-fast starting curve |
| Piano display | button (bottom-left) | Toggles freq scale to 88-key piano (A0–C8); click dot to quantize band to nearest note, drag stays quantized. C4 = middle C (Roland) | Tonal/musical EQ, notch a specific note |
| Global Bypass | button (far right) | Bypasses whole plug-in with click-free, latency-compensated soft bypass | True bypass A/B |
| Phase Invert | toggle | Flips output polarity (blue when on) | Polarity fix |
| Auto Gain | toggle | Estimates make-up gain from EQ settings (not level-measured) to compensate boosts/cuts | Level-matched A/B while EQing |
| Output Level Metering | toggle | Show/hide output meter (unlimited internal headroom — never clips internally; meter warns of downstream clipping) | Watch output level |
| Gain Scale | slider, 0–200% (deep spec) | Scales all bands' gain at once (Bell/Shelf/Flat-Tilt only) | Automate "amount of EQ"; dial back a whole curve |
| Output Gain | −∞ … +36 dB | Overall output level | Compensate level change |
| Output Pan | ring (stereo only) | L/R or M/S balance of output | Rebalance; not available in surround |
| Output Pan Mode | L/R or M/S (stereo only) | Panning law for the output pan ring | M/S balance |

### Top bar / global UI
| control | what it does |
|---|---|
| Undo / Redo | Step through full edit history |
| A/B | Switch between two full states; Before switching the current state is saved |
| Copy (A/B) | Copy active state to the inactive slot |
| Presets | Browse/load/save; Copy/Paste all params incl. output + processing mode |
| MIDI Learn | Map any MIDI controller to any param; specific-band or active-band modes; Enable/Clear/Revert/Save submenu |
| Full Screen | Fill the whole screen for precise edits (Esc to exit) |
| Resize / Scaling | Mini/Small/Medium/Large/Very Large sizes; 100–300% scaling; VST3 freely resizable by window edge |

## Use by lens
- **Producer (create):** EQ Sketch a quick tone shape, then refine. Drag the yellow curve or double-click to spawn bands (low/high area → cut, far edges → LP/HP, drag the curve edge → shelf). Use Warm/Subtle Character to glue or add vintage color to a track. Piano display to notch/boost specific notes. Spectrum Grab to kill an obvious resonance fast.
- **Mixing (balance):** The everyday channel EQ — static moves plus a dynamic band whenever you need it (de-ess a vocal, tame a boomy resonance only when it rings, brighten a kick on transients). Per-band M/S to fix one-sided artefacts or clear low-end mud from the sides. Open the Instance List to set initial EQ across the whole session and spot frequency collisions between tracks. External side chain for frequency-conscious ducking.
- **Mastering (finalize):** Natural Phase for transparent tonal moves; Linear Phase when applying EQ to part of a song with crossfades or on parallel material to avoid phase cancellation. Mid/Side bands to widen (boost HF side) or tighten (cut/LP the mid low end). EQ Match to a reference master. Spectral dynamics to tame varying harshness without static dips. Auto Gain off and trust unlimited internal headroom; set 3 dB / 6 dB display range for fine moves.

## Notes / gotchas
- **Display range:** ±3 / 6 / 12 / 30 dB (yellow EQ scale); analyzer has its own gray scale. Use 3/6 dB for mastering precision.
- **Dynamic + Linear Phase:** works only up to **High** resolution; Very High/Maximum show a warning — lower resolution to use dynamic/spectral. Spectral bands *force* linear phase on that band regardless of global mode.
- **Latency:** Zero Latency = 0; Natural Phase = small fixed (≈320 smp per deep spec); Linear Phase ∝ resolution & SR (70 ms–1.5 s @44.1k). Using L/R-specific **and** M/S-specific bands together in Linear Phase **doubles** latency (two FIR stages).
- **Cramping:** Zero Latency cramps near Nyquist (mainly audible at 44.1k on HF boosts); Natural Phase does not. Bell BW is wider than RBJ and proportional-Q (narrows as gain rises) — see deep spec.
- **Surround:** up to 9.1.6 Atmos (DAW/format-dependent). Output pan unavailable in surround. Stereo Placement button opens a speaker-selection panel; presets with unavailable speaker sets show disabled bands → use curve menu "Reset Placement/Speakers".
- **Q convention:** Pro-Q's Q=1 = default bandwidth; shelf Q tuned for musical shapes — Q values are NOT directly comparable to other EQs.
- **Auto Gain** is an estimate from settings, not a measured/dynamic process.
- **AU/AAX limitation:** Instance List can't read track order/color in AU & AAX (Logic, Pro Tools) yet — instances ordered by name; VST3 hosts (Studio One, Cubase, Live) show track color/order.
- **CPU:** very low even at 24 bands; barely changes with linear-phase modes.
- **Knob control:** vertical drag, mouse-wheel, double-click for text entry. Text entry accepts notes ("A4", "C#3+13"), "2k", "2x" (+6 dB), "50%". Ctrl/Cmd-click resets; Shift fine-tunes. Alt-drag links paired knobs.
- **Upgrade-safe:** installs alongside Pro-Q 1/2/3; reads all older presets.

## Deep spec (Programmer only)
`/Users/pongsathonkheeereekaew/.claude/skills/easby/easby-programming/plugins/Pro-Q4.md` — black-box host measurement (CLEAN) with a quarantined REF corroboration; 605 params (24 bands × 24 + 29 global), measured Bell BW≈2.04/Q, proportional-Q tables, cut roll-off, Warm = asymmetric even-order soft-sat, phase-engine latencies.
