# u-he Satin — u-he (tape machine / saturation)

| | |
|---|---|
| Vendor / ver | u-he · v1.3.3 (User Guide 7 Aug 2025) |
| Type | Tape machine emulation — saturation + harmonic colour + transient smoothing + HF compression, plus tape delay & through-zero flange modes |
| Format | VST / VST3 / AU / AAX (nksfx export VST-only) |
| Source | manual: `u-he Satin/u-he Satin.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Satin is a modular tape-machine *construction kit*, not an emulation of a single deck. It models each part of a real tape path separately — record/repro EQ circuits, the tape itself (saturation, hiss, asperity, wow & flutter, crosstalk, bias), the repro head (gap width, head bump, azimuth) and noise-reduction companders — and lets them interact like real hardware. Use it for everything from subtle mastering "sheen" and multitrack "glue", through warm coloured saturation, all the way to abused lo-fi degradation, NR-encoded cassette decoding, and EQ-standard format conversion. Two bonus modes turn the same tape engine into a multi-tap **tape delay** and a classic **through-zero flange**. Runs at 8× oversampling internally (352–384 kHz), with a Group system to gang up to 8 instances for coherent multitrack processing.

## Controls (every param → musical effect)

### Control bar (always visible)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Bypass | on/off | Disables all processing. **Grouped instances bypass together.** | A/B the tape sound vs dry — match perceived loudness when judging |
| Key Ctrl | on/off | Experimental numeric-keypad value entry: click control, type value, Enter (minus first for negatives; +/- to step, shift=fine, opt/ctrl=±10) | Precise value entry from numpad |
| Data Display | preset name / value | Click = preset list; arrows = step presets; drag a preset file onto it to load (not saved). Right-click = **Initialize** (`init`) + **1.3.3 Mode (Native)** vs **Legacy Mode** | Quick preset stepping; reset patch; choose DSP era |
| Presets / Save | — | Opens preset browser / save dialog (right-click Save picks native/h2p/h2p-extended/nksfx export format) | Manage presets |
| Undo / Redo | — | Step through edit history | Recover from a tweak |

### Upper Panel (applies in ALL modes)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Input** | gain | Drives signal into the tape stage — *the* primary saturation control. More input = more tape colour/distortion. | Set the amount of tape character; the most important knob |
| **Output** | gain | Output trim. Does **not** auto-follow Input even with Makeup on, so always usable for fine level matching. | Gain-match wet vs bypass |
| Makeup | on/off | Links output down as Input rises (auto gain compensation). **Caution:** turning Input way down with Makeup on can seriously boost hiss & asperity; in Delay mode a fast input drop can briefly spike the delay level. | Keep level constant while dialling saturation by ear |
| Tape | Vintage / Modern | Tape formula. **Vintage** = distorts sooner, loses treble, stronger low-mids (THD ~2.4%). **Modern** = flatter, less distortion, keeps treble (THD ~1.2%). | Vintage for character/grit; Modern for clean glue |
| Metering | In / Out | Selects whether VU needles show input or output level. | Monitor the stage you care about |
| RMS | on/off | VU ballistics. Off = traditional ~300 ms VU response; On = steadier reaction to signal energy. | RMS for average-level mastering reference |
| 0VU Ref | -24 to 0 dBFS | Sets the dBFS that reads as 0 VU (AES-17). E.g. -18 project → set -18 so -20 dB shows as -2. | Calibrate metering to project reference |
| Soft Clip | on/off | Gentle Class-AB/FET-style limiter on peaks approaching 0 dBFS (smooth clean→clipped transfer). Off = peaks only visualized ("Over"), not treated. | Catch occasional overs musically |
| VU meter | — | Stereo VU (slow, AES-17: 0 dBFS sine = 0 VU). Central bar = fast **stereo peak meter** for transients. | Watch average (needles) + peaks (bar) |

### Lower Panel — **Studio Mode** (default tape processor)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Speed ips | 1.875–30 ips (continuous; common 7.5/15/30) | Tape speed. Faster = better HF fidelity, less noise, LF limit rises slightly; slower = darker, more character. | Pick fidelity vs vintage flavour |
| Pre-Emphasis | 0 to ~27–56 dB (depends on speed, @18 kHz) | HF pre-filtering that addresses repro-head *gap loss* (not EQ). Gap-loss freq ~8 kHz @15 ips (16 k @30, 4 k @7.5). | Restore/boost highs; push HF into saturation |
| No Group | momentary | Resets this instance to ungrouped (default). | Detach from a group |
| Bypass Tape | on/off | Removes the tape section from the path; **compander + rec/repro circuits stay active**. (Ignored in Delay/Flange.) | Format conversion / NR decode without tape colour |
| Group 1–8 | radio (mutually exclusive) | Assign instance to one of 8 groups; all members behave as one entity while editing. Double-click a field to rename. | Coherent multitrack ("glue") + central control |
| **Compander – Encoder** | None / A-Type / A-Type Mod / B-Type / uhx Type I / uhx Type II | NR encode model. A-Type = 4-band, ~12 dB NR. **A-Type Mod** = Cat-22 "airy" top-end enhancer (great on vox/ac.gtr). B-Type = single-band HF, ~9 dB. uhx I = 2:1 pro. uhx II = consumer, rolls off ctrl-path HF/LF. | Coloration, "Dolby trick" enhancement, or encode |
| **Compander – Decoder** | same list + **Same as Enc** | NR decode model. Set to match a known encoding to decode old tapes. | Decode NR-encoded media; or mismatch for FX |
| Mix (Compander) | 0–100% | Wet/dry of the compander circuit (normally max; lower to soften an enhancer). Note: only reduces on-tape noise, not pre-plugin or system noise. | Dial enhancer intensity (Dolby trick) |
| Legacy Mode | on/off | Appears when a uhx type is selected (improved in v1.3.1); switch off to keep old behaviour before resaving. | Preserve legacy patch sound |

### Lower Panel — **Delay Mode** (multi-tap tape echo)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Repro Heads | 2 / 4 | Number of delay taps. 2 saves CPU/memory. | More taps = denser/reverb-like echoes |
| Speed ips | 1.875–30 ips | Sets delay times (faster tape = shorter delays) *unless* Tempo Sync is on, where it only colours the sound. Max delay: 4.267 s @1.875 → 267 ms @30 ips. | Set echo length + tone |
| Tempo Sync | on/off | Delay distances become musical note-lengths relative to 15 ips. | Sync echoes to song tempo |
| Routing | Multi-Mono / Cross / Ping-Pong | Feedback path. Multi-Mono = each channel feeds itself; Cross = swaps L/R; Ping-Pong = sums to mono then bounces L↔R. | Stereo behaviour of repeats |
| Distance (per tap) | inches (Tempo Sync: 16th-note snap; centre = 4/16 = ¼ note) | Distance between each repro head & its record head = that tap's delay time. Shift before dragging slider = fine/arbitrary. | Set each tap's time / rhythm |
| Mod Rate (per tap) | LFO rate | Sine-LFO speed modulating that tap's length. | Add movement / chorus / dispersion |
| Mod Amt (per tap) | depth | Depth of the per-tap length modulation. | Organic wobble; reverb-like smear |
| Balance (per tap) | L↔R | Pans each delayed tap in the stereo field. | Spread taps across the image |
| Level (per tap) | gain | Output volume of each tap. | Set decay shape (e.g. 1.0/0.5/0.25/0.125) |
| Mix | 0–100% (dry↔wet) | Global wet/dry (insert use). Keep 100% on a send; Lock helps when browsing insert presets. | Blend echo into source |
| Feedback | amount | **Global** feedback (sum of all taps → input); each pass re-coloured by EQ/tape. | Number/length of regenerations |
| Limit | on/off | Dynamic limiter on the feedback output — stops fast tape-delay build-ups from running away; can "breathe" when pushed. | Tame complex 4-tap feedback |
| Low Cut | 20 Hz–2 kHz | HPF inside the feedback loop. | Thin repeats / clear mud |
| High Cut | 200 Hz–20 kHz | LPF inside the feedback loop (darkens repeats over iterations). | Natural tape-echo HF decay |

### Lower Panel — **Flange Mode** (true through-zero tape flange)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Speed ips | 1.875–30 ips | Tape speed = tonal colour of the flange. | Flavour the sweep |
| Trigger | button (momentary / MIDI-note / midi-learn) | Fires one automatic flange sweep (one-shot "whoosh"). Re-trigger mid-sweep reverses direction. | Drop a flange hit on cue |
| Fade In / Fade Out | 0.1 s / 1 s / 10 s, or note-lengths 1/64–8/1 | Separate fade-in and fade-out durations of the auto sweep (tape2 faded in near alignment, out as it departs). | Shape sweep entry/exit length |
| Multiply (×2) | 0.1–2.0× | Scales each Fade value (in & out) as a multiplier. | Fine-tune fade timing |
| Shape (×2) | Lin ↔ Exp ↔ Log | Curvature of fade-in / fade-out. Exp = slower rise & decay; Log = faster rise & decay. | Tune the contour of the whoosh |
| Range | ms | Max delay between the two tapes; sets tape1's static delay to exactly half (= the process latency, reported to host but **not automatable**). | Depth/length of through-zero sweep |
| Phase Invert | on/off | Flips tape2 phase so signals cancel (instead of +6 dB) at alignment. Tip: turn **Wow & Flutter to min** for smoothest result. | Hollow cancellation flange |
| (Manual) slider | drag / midi-learn | Move the flange position by hand instead of auto-trigger. | Manual/automated flange control |

### Service Panel — Tape section
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Hiss | -100 to -40 dB | Stereo tape hiss level (adds retro authenticity + dither). | "Tape was here" vibe; smooth comp edits |
| Auto Mute | on/off | Soft-gates hiss **and** asperity when no input detected. | Stop noise in silent passages |
| Asperity | -100 to -50 dB | Surface-imperfection noise — mid-range enharmonic distortion that tracks the signal (stereo; can pseudo-stereo-ize mono). | Roughness/randomness; subtle width |
| Crosstalk | -80 to -20 dB @1 kHz | Bleed between L/R (2-track only per instance). | "Glue" stereo tracks together |
| Wow & Flutter | unnoticeable → "horribly wobbly" (DIN/IEC, follows speed) | Pitch instability of tape transport. | Lo-fi warble; keep min for Flange |
| Bias | ±, double-click 0 = flattest response | Pre-magnetization; flattens the tape curve. Lower bias = better HF where magnetization is low (more distortion); higher = lower distortion, less treble. Works with Gap Width to balance response. | Trade distortion vs HF; creative tone |

### Service Panel — Repro Head(s)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Gap Width | 1–5 µm | Head gap size — sets HF gap-loss *and* LF thresholds; complex resonances across spectrum (acts roughly like a tilt). 2–3 µm ≈ classic studio decks. | Shape overall response w/ Bias |
| Bump | 0–8 dB (typ. 4 dB) | "Head bump" — amount of LF resonance allowed. Low = corrected/shallow roll-off; high = more LF fluctuation & build-up. Bump freq follows tape speed. | Add low-end "oomph"/resonance |
| Azimuth | ±2 arc-minutes | Head skew → Haas-style stereo shift + comb-filter when mono'd; washier treble. More effect at slow speeds. In **Delay** mode the angle alternates L/R across taps (smear FX). | Spatial width / vintage smear |
| Analyzer | display (right-click: glow / fast / eco) | Live frequency-response plot from a hidden DSP copy (no test tones to output). | Visually verify your tape EQ shaping |

### Service Panel — Circuit
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Rec EQ** | Flat / IEC 7.5 ips / IEC 15 ips / NAB / AES 30 ips | Recording (emphasis) EQ standard. **Flat**=no EQ, max HF saturation (risk treble distortion/slew limit). **IEC 7.5**=cuts >2275 Hz, most distortion but best transients/least slew limit. **IEC 15**=corner 4550 Hz, mastering de-facto. **NAB**=higher noise floor, big LF boost (+3 dB@50 Hz…+8 dB@20 Hz), "sexy oomph". **AES 30**=treble cut @9100 Hz, mastering/high-output tape @30 ips. | Choose colour vs transient retention; format-convert |
| **Repro EQ** | same list + **Same as Rec** | Playback EQ standard. Matched pairs (Same as Rec) for correct response; mismatch to correct EQ errors or for FX. | Decode/correct EQ standard; creative mismatch |
| Headroom | default 9 dB above 0 dB tape level | Headroom of rec/repro circuit before circuit distortion (blue LED shows amount). High = max saturation + transparency; low = gritty brickwall-type distortion (loses "liveliness"). | Set circuit-distortion onset |

## Use by lens
- **Producer (create):** Reach for Input to glue and fatten any source — drums, bass, synths, vox. Vintage tape + low Speed (7.5) + some Wow & Flutter + Bias creatively low for grit and lo-fi character; A-Type Mod compander as an "airy" enhancer on vocals/acoustic guitar (Dolby trick). Switch to **Delay** mode for instant tape echo (Tempo Sync on, Cross routing, High Cut down) or even a "tape reverb" (4 taps, prime-number distances, exponential level decay, modulation). **Flange** mode = one-shot through-zero whooshes triggerable from a MIDI note.
- **Mixing (balance):** Subtle Modern tape across many tracks for cohesion; use **Groups** to gang related tracks (e.g. all drums) so they behave as one and to drive coherence. Crosstalk + asperity for stereo "3D"/glue; Soft Clip to tame stray peaks; pre-emphasis + Flat/IEC 7.5 Rec EQ to keep transient slam ("maximum slam"). A small gain reduction on the peak meter confirms tape transient-taming is working.
- **Mastering (finalize):** Final "sheen" with Modern tape, 15 or 30 ips, high Headroom for transparency, IEC 15 / AES 30 EQ pairs, RMS metering + 0VU Ref set to your project reference. Keep saturation gentle near 0 dB; gain-match Output vs Bypass and judge transients/width/front-back image. Also a **format converter / EQ corrector**: Bypass Tape, set Rec EQ + Repro EQ independently to remap an old tape's EQ standard, or decode known NR with the Compander Decoder.

## Notes / gotchas
- **Three modes** via the Mode selector (Studio / Delay / Flange) reconfigure the whole lower panel; Bypass Tape only matters in Studio.
- **Groups are global per host project** — opening multiple projects simultaneously can overwrite group assignments; grouping fails if the plugin is **sandboxed** by the DAW. Central-control trick: assign every instance to its own group, add a hidden "dummy" instance to drive them, lock + Bypass it to save CPU.
- **Latency:** Flange mode reports latency (= tape1's static delay = half of Range) to the host; Range is not automatable. General tape processing latency comes from 8× oversampling.
- **Internal sample rate 352–384 kHz** (8× @44.1k). u-he flagged a **Sample Rate Issue** (2023): some parts respond differently by project SR — use **1.3.3 Mode (Native)** for current behaviour or **Legacy Mode** for older-version compatibility (Legacy toggle also appears when a uhx compander type is selected, improved since v1.1.0 / v1.3.1).
- **Parameter Lock** (right-click any knob/switch): value survives preset changes and won't react to/affect grouped instances.
- **Compander Mix** only reduces *on-tape* noise — not noise present before the plugin, nor the modeled system noise (~-120 dB).
- 120+ factory presets; NKS FX compatible; resizable UI 70–200%; skinnable. Specs: bias osc 118–128 kHz, azimuth ±2 arc-min, gap 1–5 µm, head bump 0–8 dB, crosstalk -80..-20 dB, system noise -120 dB.

## Deep spec (Programmer only)
Not reverse-engineered — capability only. (FLVTTER is u-he's separate flutter/wow plugin and has its own deep spec at `easby-programming/plugins/FLVTTER.md`; it is a different product, not Satin.)
