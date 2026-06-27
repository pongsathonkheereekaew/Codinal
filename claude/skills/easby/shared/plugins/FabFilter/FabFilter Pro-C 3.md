# FabFilter Pro-C 3 — FabFilter (compressor)

| | |
|---|---|
| Vendor / ver | FabFilter · Pro-C 3 |
| Type | Compressor (multi-style feed-forward + upward, with analog character saturation, 6-band sidechain EQ, M/S, surround) |
| Format | VST, VST3, CLAP, AU, AAX Native, AudioSuite; AUv3 on iPad. macOS 10.13+ (Intel/Apple Silicon), Windows 7–11 |
| Source | manual: `FabFilter Pro-C 3/FabFilter Pro-C 3.pdf` · deep spec: `easby-programming/plugins/Pro-C3.md` (RE'd, black-box measured) |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
A high-end single-band compressor built around 14 program-dependent compression **styles** (downward + upward) spanning modern feed-forward, classic feedback/opto/vari-mu, and task-specific (Vocal/Mastering/Bus/Pumping) flavors — so it behaves like dozens of different compressors in one. On top of the core it adds a **character** panel for analog saturation/coloration/drift, a freely-editable **6-band sidechain EQ** (Pro-Q shapes incl. all-pass/brickwall), variable **stereo-link with M/S** routing, auto-threshold / auto-release / auto-gain intelligence, lookahead, hold, up to 32× oversampling, and full immersive/Dolby Atmos (up to 9.1.6). Distinctive for combining transparent precision and aggressive pumping/EDM glue in one clean, animated, resizable UI.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Threshold** | dB (level) | Level above which gain reduction starts; circular meter around the knob shows the filtered/stereo-linked detector level | the primary "how much compression" control; lower = more GR |
| **Auto Threshold** | on/off | Makes threshold work input-level-independent — same amount of compression regardless of input gain | dialog, varying-level vocals, consistent GR across a track |
| **Lock Auto Threshold** | on/off (appears when Auto on) | Preserves the current auto-threshold value while skipping/loading presets | when A/B-ing presets without re-triggering |
| **Audition Triggering** | momentary/toggle (above Threshold btn) | Solos exactly what the compressor is triggering on & how much GR | choosing a threshold that catches the right peaks |
| **Ratio** | 1:1 → ∞:1 | Amount of compression above threshold (∞ = brickwall limiter) | gentle 2–4:1 glue vs hard limiting at ∞ |
| **Knee** | 0–72 dB (width) | "Roundness" around threshold: 0 = hard, high = soft/gradual; >60 dB + fast attack ≈ saturation-like | soft for transparent mastering/vocals; hard for punch/control |
| **Range** | dB | Hard limit on the *maximum* applied gain change (clamps total GR); scales differently than Ratio | cap how deep compression can go; tame extreme pumping |
| **Attack** | 0.005–250 ms | How fast GR engages; program-dependent per style | fast for drum transient control, slow to let transients through |
| **Release** | ms (style-dependent) | Recovery time from GR; very program-dependent per style. With Auto Release on, this scales the auto effect | short for pump/energy, long for smooth glue |
| **Auto Release** | on/off | Smart program-dependent release: adapts release to current GR amount | "set & forget" musical release on busses/mix |
| **Lookahead** | slider, up to Max Lookahead | Advance time to anticipate peaks → more transparent GR, preserves transients (adds latency) | transparent limiting/mastering, protecting transients |
| **Maximum Lookahead** | Off / 1–20 ms | Caps lookahead latency to trade plug-in delay vs needed lookahead | low-latency tracking; Off = zero-latency path |
| **Hold** | ms | Prolongs each GR event before release begins | smoother GR; longer = deliberate pumping effects |
| **Style** | 14 options (see below) | Selects the entire detection/topology/curve model | the single biggest tonal decision — pick the compressor "type" |
| **Character mode** | Off / Tube / Diode / Bright | Type of analog saturation, coloring & drift added | add warmth/harmonics/vibe; Off = clean |
| **Drive** (Character) | level | Drives the saturation circuit harder → more saturation/harmonics. Reverse-linked to Threshold (Alt/Shift-drag) | trade compression for saturation in one move |
| **Routing** (Character) | Pre / Post | Saturation before or after compression (default Post). Pre saturates input peaks → very different character | Pre to distort transients pre-comp; Post to color the result |
| **Wet / Make-up Gain** | dB (+ pan ring) | Output gain after compression (make-up); pan ring balances mid vs side of the wet path. Reverse-linked to Dry Gain | restore level lost to GR; rebalance M/S after M/S comp |
| **Auto Gain** | on/off | Auto make-up based on Threshold/Ratio/Knee/Attack; aware of mid-only/side-only so it only lifts the processed signal | quick level-matched A/B (educated guess — still verify by ear) |
| **Dry Gain** | dB | Blends uncompressed input back in → parallel compression | NY/parallel: keep transients while adding body/density |
| **Mix** (output panel) | 0–200% | Wet/dry blend scaling overall dynamic + static gain change; >100% increases overall gain | global parallel blend; can push *more* compression instead of less |
| **Sidechain Input** | Internal / External / Host Sync / MIDI | What the detector triggers on | Internal=normal; External=ducking; Host Sync=tempo pulse; MIDI=note-gated |
| **Sidechain Level** | dB slider | Level of the incoming trigger signal (use circular SC meter to set) | boost a soft trigger; on Vari-Mu it changes flavor markedly |
| **SC Audition** | momentary/toggle | Listen to the filtered + stereo-linked trigger signal | verify what the EQ'd sidechain is actually keying on |
| **Host Sync — Sync** | note value (e.g. 1/4) | Pulse speed relative to song tempo (when input=Host Sync) | tempo-locked rhythmic pumping |
| **Host Sync — Offset** | 50–200% | Shifts sync speed → dotted/triplet feel | groove variations on the pump |
| **Host Sync — Length** | % of sync | Length of each pulse | shape pump depth/duty cycle |
| **Stereo Link** | 0–100%, then →Mid/All | 0=channels independent, 100=identical GR; beyond 100% transitions to mid-only / side-only processing | tighten stereo image; M/S compression at the far end |
| **Stereo Link Mode** | Mid / Side / M>S / S>M | At max link: which signal triggers and which gets compressed | Mid=center comp; Side=width comp; cross-trigger M>S / S>M |
| **C button** (surround) | on/off | Links center channels (C, Cs) to their L/R pair | immersive mixes where center should track fronts |
| **All button** (surround) | menu: Sides/Tops/LFE | Toggle speaker groups in/out of all-channel linking (2nd half of Stereo Link) | Atmos bus glue with selective channel linking |
| **Sidechain EQ** | up to 6 bands | Filter the trigger signal: all Pro-Q shapes incl. all-pass + brickwall, low/high cut to 96 dB/oct; per-band Freq/Gain/Q, dynamic range, M/S targeting, bypass | de-ess/de-boom the trigger, frequency-conscious ducking, tilt-free keying |
| **Input Level / Pan** | dB / L–R | Pre-processing input trim & pan (alt to changing threshold) | gain-stage into the detector; not available in surround |
| **Output Level / Pan** | dB / L–R | Final output trim & pan; compensate global gain change | level-match bypass vs processed; not available in surround |
| **Oversampling** | Off / 2× / 4× / 8× / 16× / 32× | Internal upsampling to reduce aliasing from fast/aggressive GR (more CPU + latency) | aggressive comp, character on, fast attack; Off for zero-latency |
| **Meter scale** | 9–90 dB | Scale for level/knee displays + meters | 9 dB precise mastering, 90 dB general mixing |
| **Knee display** | show/hide | Visualizes input→output transfer (Threshold/Ratio/Knee/Range); curve turns green at live input level | dialing the static curve visually |
| **Level display** | show/hide (Compact layout) | Animated in/out + GR (GR = red line); hiding it = traditional compressor look | quick metering vs distraction-free workflow |
| **Show Input Level** | on/off (Help menu) | Adds an input peak/loudness meter | gain-staging checks (hidden in surround) |
| **Global Bypass** | on/off | Bypasses whole plug-in with correct latency compensation + soft (click-free) bypassing | reliable A/B vs host bypass when using lookahead/oversampling |
| MIDI Learn | — | Map any MIDI CC to any parameter; menu: Enable, Clear, Revert, Save | hardware/automation control, MIDI-note triggering |
| Undo/Redo · A/B · Copy | — | History, two-state compare, copy A↔B | iterate and compare settings |

### The 14 styles
**Modern** — *Clean* (allround low-distortion feed-forward, program-dependent) · *Versatile* (works on anything; punchy at long attack, tight/smooth at short) · *Smooth* (stays smooth always — low-ratio gluing, long times) · *Punch* (traditional analog-like, good on anything) · *Upward* (pumping upward compression à la Saturn's Dynamics, with more control) · *TTM* "To The Max" (multiband combined up+down; threshold becomes a target level, knee blends the two stages).
**Classic** — *Op-El* (effortless opto-like tube, smooth & warm) · *Vari-Mu* (variable-mu feedback, smooth & colorful — SC level changes flavor) · *Classic* (vintage feedback, very program-dependent) · *Opto* (slow, very soft knee, more linear opto).
**Utility** — *Vocal* (auto knee+ratio, bring vocals forward — just set threshold) · *Mastering* (max transparency, minimal harmonic distortion) · *Bus* (bus glue / drums-mix-tracks) · *Pumping* (deep over-the-top pump for drums/EDM).

## Use by lens
- **Producer (create):** Pump and color. *Pumping*/*Upward* + Host-Sync sidechain for EDM sidechain ducking without a separate trigger track; *TTM* for loud, in-your-face busses; Character (Tube/Diode, Routing=Pre) to distort transients for attitude; Dry Gain for parallel thickness on drums. *Vocal* style nails an upfront lead in one knob.
- **Mixing (balance):** Glue and control. *Bus*/*Smooth* low-ratio + Auto Release on group busses; *Clean*/*Punch* on individual tracks; sidechain EQ to stop low-end pumping the detector (high-pass the trigger) or to de-ess by keying highs; External sidechain for ducking (e.g. bass under kick); Stereo Link / M/S to compress center vs sides independently.
- **Mastering (finalize):** Transparency first. *Mastering* style, soft knee, gentle Ratio, Lookahead on with Range to cap GR; M/S (Mid) to tame center energy while leaving width; oversampling 2–4× to control aliasing; 9 dB meter scale + knee display for precise moves; Auto Gain to level-match, then verify by ear.

## Notes / gotchas
- **Reverse-linking:** Threshold ↔ Character Drive (trade compression for saturation in one drag); Wet Gain ↔ Dry Gain — hold Alt (Shift in Pro Tools) while dragging.
- **Latency:** Lookahead + oversampling add latency; set both Off (and Max Lookahead Off) for a zero-latency path. Global Bypass compensates correctly.
- **Detector is RMS-following feed-forward** (per deep spec) — equal-peak square ducks ~+2 dB more than sine; threshold reads the *filtered + stereo-linked* signal.
- **Surround/immersive:** up to 9.1.6 Atmos; input meters and input/output/dry-wet panning are unavailable in surround layouts (use a dedicated surround panner).
- **TTM quirk:** threshold acts as a *target level* (up+down toward it); knee blends the two stages — not a normal threshold.
- **Vari-Mu quirk:** driving the sidechain Level (not threshold) opens up distinctly different flavors.
- **Auto Gain is an estimate** (doesn't measure loudness) — tweak output gain to taste.
- **Meters above 0 dBFS ≠ distortion** in Pro-C; it handles >0 dBFS internally (clip may be elsewhere in the chain).
- **Instance List:** controllable from Pro-Q 4 (≥4.10) alongside Pro-G/Pro-DS as a modular channel strip (not on iOS yet).
- **Presets:** `.ffp` files in `Documents/FabFilter/Presets/Pro-C 3`; MIDI program-change loading available; Restore Factory Presets in Options. Opens Pro-C 2 presets; installs alongside Pro-C 2 (no overwrite).
- **SC EQ spectrum** uses a 4.5 dB/oct tilt for a natural-looking display.

## Deep spec (Programmer only)
`~/.claude/skills/easby/easby-programming/plugins/Pro-C3.md` — reverse-engineered, black-box measured (signal chain, RMS detector law, release shapes, SC-EQ, stereo matrix, auto-gain ≈0.358·|thr|·(1−1/R) dB). **REF — Programmer agents only; do not mix into CLEAN usage.**
