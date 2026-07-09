# Newfangled Punctuate — Newfangled Audio (multi-band transient shaper)

| | |
|---|---|
| Vendor / ver | Newfangled Audio (distributed by Eventide) · v1.12.0 (manual P/N 141313 Rev 3, ©2018) |
| Type | Intelligent multi-band transient shaper / designer (per-band attack-sustain modulator) |
| Format | VST / VST3 / AU (Audio Units) / AAX |
| Source | manual: `Newfangled Punctuate/Newfangled Punctuate.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Punctuate is a transient shaper that splits the signal into up to **26 critical bands** (Mel-scale, linear-phase triangular FIR filters modeling the inner ear) and runs an **independent transient shaper on every band**, so you can emphasize or suppress attack/punch only in the frequency regions that need it — instead of slamming the whole signal up and down at each transient. Built on the Transient Emphasis section of Elevate, it uses intelligent adaptive algorithms to drive up to 26 shapers from just **4 macro controls**, with per-band override sliders for surgical work. Because the filters are critical-band-shaped and linear-phase (minimal pre-echo), even drastic moves sound natural. Distinct from ordinary single-band transient designers: you can boost transients in one band while cutting them in another (e.g. pull hats out of a snare mic, boost kick without touching bass, add drum punch to a whole mix). At 1 band it collapses into a standard look-ahead limiter with transient emphasis. Processing is linear floating-point — it will not saturate at any internal stage.

## Controls (every param → musical effect)

### Global / header
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Master Input Level | gain (dB) | Knob above the INPUT meter; sets level just before the input meter (pre-process) | Drive the meters / make up for throughput gain change |
| Master Output Level | gain (dB) | Knob above the OUTPUT meter; sets level just before the output meter (post-process) | Match in/out level after shaping |
| ACTIVE | on / off | Master engage/bypass of all processing (header, by NEWFANGLED AUDIO logo) | True bypass A/B against the source |
| Δ (Delta Listen) | toggle | Subtracts output from input — auditions only what the processor is changing (what it's adding/removing) | Hear exactly what each band is doing; dial in surgically |
| MIX | 0–100% wet/dry | Blends transient-modulated (wet) signal with dry input (active only when ACTIVE) | Parallel transient shaping; dial back aggressive moves |
| Input / Output bar meters | Peak (ticks) + RMS (bar+number) + Peak Hold (number) | Matching L/R vertical meters, always on; click Peak Hold or bypass to clear held peak | Gain staging, spotting throughput change |
| Scrolling Transient Meter | display (Stack / Spread waveforms) | Top-center scrolling view of transient modulation applied per band; Stack overlays waveforms on one axis, Spread separates them | See what the algorithm is doing per band in real time |

### Transient page (4 macro controls + per-band)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| TRANSIENT EMPHASIS | -? to +? %  (Suppressed ↔ Emphasized; "Emphasized" = +) | Main macro. Above 0% emphasizes transients, below 0% suppresses. Scales the per-band amounts (per-band sliders define the total reached at 100%) | One-knob "more punch / less punch" across the whole spectrum |
| ADAPTIVE TRANSIENT | 0–100% (Single Band ↔ Multi Band) | How independently bands react. 0% = intelligent algo off, all bands respond at the same level to incoming transients; 100% = each band ignores neighbors and reacts only to its own range; in-between = bands cooperate to find transients naturally | Low = smooth/coupled/glued; High = surgical per-band; mid = natural |
| TRANSIENT LENGTH | time (ms; Short ↔ Long), default ~200 ms | How long a "transient" is considered. Short = only the very onset is modulated; Long = more of the attack body is captured (slower recovery, less sensitive to rapid transients) | Short for tight clicky onsets; long to grab more attack body |
| ADAPTIVE LENGTH | 0–100% (Same Length ↔ Different Lengths) | Lets each band adapt its own LENGTH to its signal — generally lower bands get longer lengths/slower reaction, higher bands shorter/faster | Strong character control; raise for per-band-appropriate timing |
| TRANSIENT EMPHASIS PER BAND | -12 dB … +12 dB per band (default +12 dB) | Up to 26 sliders setting each band's total emphasis when EMPHASIS is at 100%. **Positive = emphasize, negative = suppress** — invert behavior per band (boost transients in one region, cut in another) | Surgical: hats out of snare mic, boost kick / cut snare in room mic |
| Per-band meters | -12 … +12 dB | Behind each per-band slider, shows transient emphasis actually being applied in that band | Visual confirmation of per-band action |
| SOLO (per band) | toggle | Solos that band's output; shift/ctrl-click to solo several (same solos as on Filter Bank page) | Isolate a band to hear/aim its shaping |
| RESET TRANS | button | Resets all per-band sliders to 0.0 dB | Start the per-band curve from flat |
| DRAW CURVE | on / off (on by default) | On: click-and-swipe across the slider field to draw a curve over the per-band sliders. Off: edit one band at a time (fine-tune with command-click) | On for fast macro shaping; off for single-band precision |

### Filter Bank page (sub-module)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| AUDITORY FILTER BANK (band count) | 1–26 bands (default 26) | Number of bands the signal is split into; auto-spaced on the Mel scale between min/max. More bands = finer control + more gain before artifacts, but higher CPU. **Selecting 1 BAND deactivates the ADAPTIVE controls and turns it into a standard look-ahead limiter w/ transient emphasis** | Fewer bands = smoother/lighter; 26 = max resolution; 1 = global limiter mode |
| MEL / CUSTOM | radio | MEL distributes filter center freqs perceptually (Mel) across the range; CUSTOM (auto-set when you move any center freq) lets you place them freely | CUSTOM to focus bands on program-specific frequency ranges |
| SOLO (per band) | toggle | Solo one band's output; shift/ctrl-click for several (shared with Transient page) | Audition a band while tuning filters |
| INSERT FILTER (+) | button (per selected band) | Inserts a new filter between the selected band and the one to its right; greyed when at max (26) | Add resolution in a region that needs fine tuning |
| REMOVE FILTER (−) | button (per selected band) | Removes the current band without moving neighbors' center freqs | Drop a redundant band while tuning |
| FILTER CENTER FREQUENCIES | Hz (text/slider per band) | Set each band's center frequency; default = critical bands of the ear. Editing switches the bank to CUSTOM | Align bands to important freqs in your material, then shape per band |
| Filter Bank Display | display | Shows relative distance + triangular shape of each filter on the Mel scale (adjacent triangles overlap → smoother result) | Visualize band layout / overlap |

### Navigation bar (preset + global UI)
| control | what it does |
|---|---|
| UNDO / REDO | Multi-level undo/redo of any parameter change |
| A/B, A>B | Toggle two full states (A/B); A>B (or B>A) copies one state to the other for comparison |
| LIBRARY | Opens preset librarian — browse/search by category, author, tags, favorites; banks (Factory/User); live miniature plugin UI preview |
| Preset selector (dropdown) | All / Favorite / Filtered / by-Category views; ◀ ▶ step through subgroup; heart icon = favorite (asterisk + italics = modified) |
| SAVE | Save screen: Preset Name, Set As Default, Heart (favorite), Save, Export (save preset as a file outside the browse folder), Category, Author (+url), Tags, Description |
| SETTINGS | Installed version (+ Update if available), User Guide (Show), Show Meters (on/off — hides extra meter glow/graphs), Brightness, OpenGL Graphics Rendering (on/off, needs UI reopen), Color Scheme (e.g. Modern), Presets Folder (Reveal), Default Settings (Save current as default) |
| Resize | Drag bottom-right corner to resize; save over default preset to set default size |

**Slider/knob conventions:** double-click to type a value; option/alt-click resets to default; command/ctrl-click for vernier (fine) mode; some controls have shift-click extras (noted in tool-tips). Section on/off buttons disable that section to save CPU.

## Use by lens
- **Producer (create):** Reshape drums and busses to taste — turn the kick up without touching the bass, pull hats out of a snare mic, add snap to acoustic guitar/piano or push them back. Use a few bands (or 1-band limiter mode) for quick character; draw a per-band curve to sculpt punch where the track needs it. MIX for parallel "punch in" without losing body.
- **Mixing (balance):** Surgical transient balance per instrument — boost transients in one region while suppressing them in another (e.g. crack up on the snare, thump down). ADAPTIVE TRANSIENT low = glued/smooth, high = independent/precise. Δ Listen to confirm you're only touching the intended bands. Solo bands to aim filters; custom center freqs to target problem regions.
- **Mastering (finalize):** "Turn the drums up/down" in a finished mix, or breathe transients back into dull/over-compressed masters — gently, with linear-phase critical-band filters so it stays natural. Keep EMPHASIS modest, use 26 bands + adaptive controls for the most natural result, and watch in/out meters since it's linear (no internal saturation). MIX to taste-blend.

## Notes / gotchas
- **Per-band sign matters:** EMPHASIS macro >0% emphasizes; per-band sliders can be set negative to **suppress** in that band, inverting the macro for that region. This is the key to "boost here / cut there."
- **1 BAND mode** turns Punctuate into a standard **look-ahead limiter with transient emphasis** and disables both ADAPTIVE controls (they work across bands).
- **Linear-phase FIR filters** → minimal pre-echo/artifacts and "what you see is what you hear," but linear-phase filtering + look-ahead implies **latency** (uses the PFFFT FFT library; manual doesn't state exact sample count).
- More bands = more CPU and more clean gain before artifacts, but beyond a point may not improve audible quality. Turn unused sections off to save CPU.
- ADAPTIVE TRANSIENT and ADAPTIVE LENGTH are the big "character" controls — small changes greatly affect the sound.
- Linear floating-point process: will not saturate at any internal step; use Input/Output knobs to manage throughput gain.
- Authorization: PACE/iLok (with or without a hardware dongle); 2 activations per license.
- Worth-knowing presets/categories: Bass, Drum Bus, Effect, Generic, Guitar, Kick, Mastering, Mix Bus, Piano, Snare, Utility (e.g. "Bring Out the Kick," "Hat Out Of Snare Mic," "Snare Crack Fader," "Adaptive Transient," "Detail").

## Deep spec (Programmer only)
not reverse-engineered — capability only.
