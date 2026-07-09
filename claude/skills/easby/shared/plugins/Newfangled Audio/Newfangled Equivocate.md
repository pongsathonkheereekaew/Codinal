# Newfangled Equivocate — Newfangled Audio (linear-phase auditory graphic/match EQ)

| | |
|---|---|
| Vendor / ver | Newfangled Audio (distributed by Eventide) · v1.12.0 (manual P/N 141300 Rev 5, ©2016) |
| Type | EQ — linear-phase FIR graphic/paragraphic EQ + Match EQ, built on a human-ear (Mel/critical-band) auditory filter bank |
| Format | VST2, VST3, AU (Audio Units), AAX (Native) · iLok (PACE) licensing, with or without dongle |
| Source | manual: `Newfangled Equivocate/Newfangled Equivocate.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
EQuivocate is a graphic/paragraphic EQ whose bands are modeled on the human ear. Up to 26 linear-phase FIR filters are triangular (not "ideal" rectangular) — the same shape used in auditory models to approximate the critical bands of the inner ear. By default the bands are spread along the **Mel Scale** (0 Hz–20 kHz) so each fader "tickles" a different, perceptually-equal section of hearing. Because the filters are triangular and complementary they sum to unity (flat at 0 dB) and stay independent of their neighbours — what you see is what you hear, with minimal pre-echo/time-domain artifacts versus typical linear-phase EQs. The standout feature is **Match EQ**: feed a reference into the sidechain and EQuivocate morphs your tone to match it (or, at negative amounts, to *complement* it for separation). Because matching happens in critical bands it gives a transparent, natural match instead of overfitting imperceptible detail. Best for tonal balancing of full mixes/masters and any source meant for human ears.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **ACTIVE** | on/off (header, by NEWFANGLED AUDIO logo) | Master engage/bypass of all processing | A/B the whole effect against dry |
| **Δ (Delta Listen)** | on/off | Subtracts output from input → you hear *only* what the EQ is changing/removing | Audition exactly what you're adding or cutting; surgical checks |
| **Auditory Filter Bank — band count** | 1–26 bands (dropdown) | Sets how many filters exist; picking a count auto-spaces them MEL between current low/high | Fewer bands = broader strokes; 26 = full critical-band resolution |
| **MEL** (spacing button) | toggle | Re-spaces all bands to standard perceptual Mel distribution | Snap back to default ear-spaced layout |
| **CUSTOM** (spacing button) | toggle | Indicates/keeps non-Mel band positions (auto-highlights once you move a band) | After hand-tuning band frequencies |
| **Master Input Level** | gain knob (above INPUT meter) | Trims level into the EQ; EQ is linear/floating so no saturation at any stage | Optimize metering / gain-stage the input |
| **Output AUTO** | on/off | Auto-compensates output for the level change the EQ introduced | Level-matched A/B; keep perceived loudness constant while EQ'ing |
| **Master Output Level** | gain knob (via down-arrow next to AUTO) | Manual makeup/output trim (alternative to AUTO) | Set final output by hand instead of auto comp |
| **MATCH EQ button** | on/off | Engages match mode: analyzes avg level diff between main input and **sidechain** per band, then drives band gains; locks sliders out of UI (sliders tint to button colour) while on. Toggling off bakes the result in for further tweaking | Match tone to a reference; fit a sound into a mix |
| **MATCH EQ knob** | −100% … +100% | +100% = make main input match the sidechain's spectrum; −100% = complement (push main *away* from sidechain for separation); in-between = partial morph | Dial how strongly you match (or anti-match) the reference |
| **RANGE** | −24 dB … +24 dB | Sets min/max scaling of all gain faders. Positive = up-pushes-boost (normal); negative = up-pushes-*cut* (inverts); also scales/limits a baked Match EQ result | Rein in an aggressive curve/match; invert a programmed shape; gentle mastering match |
| **RESET GAINS** | button | Resets all gain faders to 0.0 dB (keeps band layout) | Start the curve over without losing band setup |
| **DRAW CURVE** | on/off (default on) | On = click-and-swipe across the fader field to draw a curve over many bands; Off = move one band at a time (command/Ctrl-click to fine-tune). Shift inverts the active mode | On for fast shaping; off for surgical single-band moves |
| **INPUT METERS** (toggle) | on/off | Shows/hides per-band input meters in the fader field | De-clutter, or use bands as a perceptual spectrogram |
| **OUTPUT METERS** (toggle) | on/off | Shows/hides per-band output (post-gain) meters | See post-EQ band energy |
| **INPUT meter / OUTPUT meter** (master) | Peak (ticks) · RMS (bar + number) · Peak Hold (number) | L = input, R = output level metering; click Peak-Hold area or bypass to clear held peak | Gain-stage and level-match in/out |
| **Per-band GAIN FADER** | ±12 dB | Main control per band; double-click to type a value; draw across (DRAW CURVE on) or command/Ctrl-drag to fine-tune (off); option/alt-click resets to default | The core EQ move for each critical band |
| **Per-band PEAK FREQUENCY** | per-band center freq (below each fader) | Drag up/right ↑ freq, down/left ↓ freq; pushes neighbours out of the way (can collapse a band to zero width); command/Ctrl-drag fine-tunes, option/alt-click resets; also set by band-count/MEL/CUSTOM | Reposition a band onto a problem frequency (→ paragraphic EQ) |
| **Per-band SOLO** | toggle | Solos that band's output; shift/ctrl-click to solo several at once | Hunt problem frequencies; confirm what a band contains |
| **INSERT FILTER (+)** | button (visible only when band highlighted) | Inserts a new filter to the right of the clicked band, re-dividing local bandwidths; greyed out at 26 bands | Add resolution where a filter feels too broad, without moving other centers |
| **REMOVE FILTER (−)** | button (visible only when band highlighted) | Removes a filter; neighbours' bandwidths expand to cover it, other centers untouched | Clean up collapsed/zero-width bands in CUSTOM mode |
| **BAND ENABLE** | circular toggle (below +/−) | Enables/disables that band's gain fader (disabled = greyed, no gain change) | Park a band's setting without resetting it |
| **Filter Display** | view (below freq row) | Live Mel-scale view of all triangular filters; highlights the band being edited; soloed bands fill in | Visualize the bank in perceptual space |

### Settings panel (SETTINGS button)
| control | range / unit | what it does |
|---|---|---|
| Installed version | read-out / UPDATE button | Shows version; UPDATE appears if outdated → downloads page |
| User Guide — SHOW | button | Opens this manual |
| Show meters | on/off | Shows/hides extra meter graphics (glow + envelope/curve graphics behind sections) — turn off to lighten the UI |
| Brightness | % | Brightness of glow/graph/curve graphics |
| OpenGL graphics rendering | on/off | Toggles OpenGL UI rendering (requires UI close/reopen); save as default if it renders better on your machine |
| Color scheme | dropdown (e.g. MODERN) | Pick UI colour theme |
| Presets folder — REVEAL | button | Opens the presets folder (for sharing/manual access) |
| Default settings — SAVE | button | Saves current state as the plug-in default |

### Navigation bar / preset system
UNDO / REDO (multi-level) · **A/B** + **A>B** (copy/compare two states) · **LIBRARY** (preset librarian: BANKS Factory/User, SEARCH, FILTERS by Category/Author/Tags/Favorites, live mini-UI preview) · preset-selector dropdown (All / Favorite / Filtered / by Category / by Author) with ◀▶ step · **heart** = favorite · **SAVE** screen (name, Set As Default, category, author+URL, tags, description, EXPORT to file). Resize via bottom-right corner (save over default to persist size). Includes artist presets (Richard Devine, Jeremy Lubsey, Alex Saltz, Sebastian Arocha Morton, Richard X, John McCaig).

## Use by lens
- **Producer (create):** Treat the 26 faders as a perceptual spectrogram — turn on INPUT/OUTPUT band meters and watch which critical bands a sound occupies. DRAW CURVE on for fast, broad tone sculpting; SOLO bands to find a harsh or honky region, then notch it. Reposition PEAK FREQUENCY to turn it into a paragraphic EQ on a single problem tone. Use fewer bands for gentle, musical broad strokes.
- **Mixing (balance):** The killer move is complementary Match EQ — sidechain one element into another, set the MATCH knob toward **−100%** to carve pockets so two sources stop competing (separation without manual notching). Or match a track toward a reference at **+100%** to make a layered/comped part sound like one source. Use RANGE to keep the match subtle. Linear phase keeps transients/phase intact across busses; Δ to verify you're only touching what you intend. AUTO output for level-matched decisions.
- **Mastering (finalize):** Feed a **reference master** into the sidechain, MATCH EQ at a *modest* amount with a small RANGE (e.g. a few dB) so you nudge tonal balance toward the reference without slamming the curve — the manual explicitly recommends RANGE for "Match EQ to a master without applying the EQ effect too heavily." Critical-band matching avoids the unnatural overfit of conventional match EQ. Use 26 bands for fine balance; AUTO/Output trim for gain. Note: linear-phase FIR → latency (offline/bounce-safe; watch monitoring latency).

## Notes / gotchas
- **Linear-phase FIR** = inherent latency and zero saturation (floating/linear path) — great for transparency, but expect look-ahead delay; fine for mixing/mastering, mind it for tracking.
- **Triangular complementary filters** sum to unity → truly flat at 0 dB, bands independent of neighbours (unlike IIR/analog graphic EQs). Minimal pre-echo vs typical linear-phase designs.
- **Match EQ requires an active sidechain feed** routed in your DAW *and* transport playing to analyze; while MATCH is ON the band faders are locked (tinted). Toggle MATCH OFF to bake the result and then hand-edit / scale with RANGE.
- **RANGE inverts** when negative (fader-up becomes a cut) — easy to confuse; it also scales any baked Match EQ result.
- **CPU:** turning off unused sections/meters (per the Controls note and Show-meters setting) reduces processing load.
- **Band editing:** INSERT/REMOVE FILTER and per-band controls only appear when that band is **highlighted**; pushing PEAK FREQUENCY can collapse neighbour bands to zero width (remove them with −).
- **Universal control gestures:** double-click = type value; option/alt-click = default; command/Ctrl-drag = vernier fine-tune; shift = use the *other* draw/single mode temporarily; tool-tips on hover.
- Uses the PFFFT FFT library (jpommier/pffft).

## Deep spec (Programmer only)
not reverse-engineered — capability only.
