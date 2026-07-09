# SoundToys Crystallizer — SoundToys (granular pitch/echo)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 (Mac & Windows) |
| Type | Granular echo synthesizer — pitch-shifting splice/delay with feedback (reverse-shift "Crystal Echoes" effect) |
| Format | VST3 / AU / AAX (not stated explicitly in manual; standard SoundToys delivery) |
| Source | manual: `SoundToys Crystalizer/SoundToys Crystallizer.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Crystallizer grabs short "slices" of the incoming mono/stereo audio and replays them — forward or reversed — pitch-shifted up to ±4 octaves, with adjustable delay and a feedback ("Recycle") path that re-injects the output. Feeding pitch-shifted slices back on themselves builds the signature shimmering, spiraling, ascending/descending echo clouds — a recreation of the Eventide H-3000 "Crystal Echoes" reverse-shift preset that originated the sound. It ranges from subtle detuned thickening through rhythmic pitched delays to wild metallic granular textures. A dynamics-aware Gate/Duck section (driven by a Threshold) lets the effect move out of the way while you play and bloom when you stop, and a hidden Tweak menu adds stereo offsets, filtering, smoothing, and feedback-routing modes.

## Controls (every param → musical effect)

### Main panel
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Mix** | Dry ↔ Wet (0–100%) | Balance between dry signal and the shifted wet effect. | Insert use: dial blend. Aux send/return: set 100% and ride the return fader. |
| **Pitch** | ±3600 cents (±3 oct shown; ±4 oct / 6-oct total range capability), 1-cent steps | Pitch of the effect slice. ±100 = semitone; ±1200 = octave. Small ±10 = subtle detune; e.g. +750 sits between a 5th & 6th. | Octave shimmers (+1200), spirals (with Recycle), gentle chorusing (±5–10), pitched melodic echoes. |
| **Splice** | 0–2050 ms (~2 s) | Length of the captured audio slice that gets replayed; also sets the approximate spacing/delay between grabs. | <30 ms = pitchless metallic/granular percussive textures; >30 ms keeps pitch; ~300 ms+ = distinct grabbed-and-shifted slices; 500 ms+ + Pitch 1200 + Recycle = classic Crystal Echoes. |
| **Delay** | 0–2050 ms | Fixed (un-modulated) delay inserted between dry and effect; adds on top of the Splice-inherent delay. | Push echoes later in time; widen spacing between repeats; combine with Recycle for sparser spirals. |
| **Recycle** | Min ↔ Max (feedback amount) | Feedback — sends effect output back to input. With Pitch set, each pass shifts again → rising/falling spirals. | Sustained shimmer trails, infinite-ish spirals, thickening. More Splice/Delay = longer gaps between repeats. |
| **Threshold** | −40 dB → 0 dB (LED ring shows input level) | Level the **input** must exceed to engage the Gate/Duck action. | Set against program dynamics so Gate/Duck triggers on the notes you want. No "right" value — program-dependent. |
| **Gate / Duck** | bipolar knob; **12 o'clock = OFF** | Dynamic effect-level control vs. Threshold. CW = **Duck** (lower effect while input is above Threshold; full CW = effect disappears until you stop). CCW = **Gate** (effect rises when input exceeds Threshold; full CCW = effect silent until input crosses up). | Duck: keep echoes out of the way while playing, bloom on stops. Gate: swirly washes that only appear on loud hits. |
| **Forward / Reverse** | switch | Plays each slice normally (Forward) or backwards (Reverse). Pitch shift applies either way. | Reverse + long Splice + Recycle = thick swirling reverse echo / backwards-tape feel. |
| **MIDI Sync** | on / off | Locks Splice & Delay to host/MIDI clock; their readouts switch from ms to note values. Splice restarts on each downbeat (osc-sync style) so it can't exceed the downbeat length. | Tempo-locked rhythmic pitched delays; grooved granular patterns. |
| **Input** | −24 to +24 dB | Boost/cut level **into** the effect (affects shifted signal only, not dry). LED: yellow = 6 dB below clip, red = max/clipping. | Drive the crystallization harder, or tame it — independent of dry level. |
| **Output** | −24 to +24 dB | Boost/cut level **of** the effect (shifted signal only). LED metering as above. | Match wet level to mix; default ≈ unity. |
| **Tweak** | button | Slides out the hidden Tweak menu (below). | Access stereo offsets, filters, smoothing, gate timing, routing modes. |

### Tweak menu
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Pitch Ofs** (Pitch Offset) | ±4800 cents (±4 oct), regardless of main Pitch | Detunes **left down / right up** by the set amount (subtract from L, add to R). Independent of main Pitch position. | Thick stereo detune (e.g. Pitch 0, Offset 11 → L flat / R sharp); extreme L−4oct / R+4oct stereo spreads. |
| **Splice Ofs** (Splice Offset) | 0–100 (% shorter) | Shortens **right-channel** Splice by the shown %. 25 = R 25% shorter; 50 = R half; 100 = R 1/100th of L. | Asymmetric L/R slice lengths → interesting stereo motion, especially with longer Splice. |
| **Delay Ofs** (Delay Offset) | 0–100 (% shorter) | Shortens **right-channel** Delay by the shown % (same scheme as Splice Offset). | Different L/R delay times → wider, enhanced stereo echo image. |
| **Smoothing** | 20 ms → longer crossfades | Crossfade time between splices in the delay; longer = smoother, more ethereal/washy transitions, less abrupt. | Min 20 ms for tight/defined; raise for ambient, glassy, washed echoes. |
| **Low Cut** | 1.00 Hz – 5000 Hz, 12 dB/oct highpass | Removes lows from the **effect** signal below the set freq. | Clean mud out of trails; thin the wet for contrast. |
| **High Cut** | 500 Hz – 20 kHz, 12 dB/oct lowpass | Removes highs from the **effect** signal above the set freq (CCW lowers freq → darker). | Dark/vintage echoes; with Low Cut forms a bandpass on the wet. (Filters never touch dry signal.) |
| **Attack** | fast (low) → slow (high) | With Gate/Duck: how quickly the effect ducks/gates once input crosses **above** Threshold. | Fast = snappy duck on transients; slow = gradual fade-down. Speed up if input crosses Threshold rapidly. |
| **Release** | fast → slow | With Gate/Duck: how quickly the effect returns to normal once input drops **below** Threshold (Duck = comes back up; Gate = drops back to Gate level). | Tune with Attack to the source dynamics; longer = slower wet recovery. |
| **Feedback Mode** | Mixed · Dual · Ping-Pong | How feedback repeats sit in the stereo field. **Mixed**: L/R blended into both channels (diffused with Recycle + Delay Offset). **Dual**: independent L/R feedback paths, each in its own channel. **Ping-Pong**: repeats alternate L↔R. | Reshape the echo's stereo pattern without changing any other control. |
| **Ducking Mode** | Output · Feedback · Both | Where Gate/Duck acts. **Output**: ducks/gates the initial effect before it hits feedback. **Feedback**: ducks/gates only the feedback path. **Both**: acts on both. | Sculpt exactly which part of the spiral responds to dynamics. |

## Use by lens
- **Producer (create):** The signature toy — Pitch +1200, Splice 500 ms+, Delay ~500, decent Recycle = lush Crystal Echoes shimmer (gorgeous on guitar, vocals, synth, FX). Reverse + long Splice + Recycle for backwards swirls; sub-30 ms Splice for metallic granular/percussive sound design; MIDI Sync for tempo-locked pitched delay grooves; Pitch Offset for instant huge stereo detune pads.
- **Mixing (balance):** Run as an aux (Mix 100%, ride the return) and use Duck mode (Threshold + Gate/Duck CW, set Attack/Release) so shimmer ducks under the dry part and blooms in gaps — keeps trails from cluttering. Tame the wet with Low/High Cut (filters hit only the effect) and Input/Output to seat it. Subtle ±5–10 cent detune for width without obvious pitch.
- **Mastering (finalize):** Not a mastering tool — it's a creative pitched-echo/granular effect with no clean/transparent mode. Avoid on the 2-bus; if used at all, only as a deliberate parallel texture on a stem, dialed far back.

## Notes / gotchas
- **Gate/Duck knob center = OFF.** CW adds Ducking, CCW adds Gating — it's one bipolar control, not two.
- **Threshold reads the INPUT (dry) level** (LED ring), and gates/ducks the **wet**; the dry passes unaffected. Lowest Threshold = always on; highest = never engages.
- **Input/Output and Low/High Cut affect ONLY the wet (shifted) signal**, never the dry — intentional, lets you balance the effect independently.
- **Splice sets both slice length AND repeat spacing**; delay timing inside the slice is modulated, so onset isn't exactly the readout value — character is best found by ear.
- **MIDI Sync constrains Splice ≤ one downbeat** (splice restarts each downbeat, synth osc-sync style).
- **Pitch Offset range is ±4800 cents independent of main Pitch**; Splice/Delay Offsets only shorten the **right** channel (stereo asymmetry tool).
- Manual states no oversampling/latency/CPU figures; pitch shifting/granular processing implies some latency — verify in host if PDC-critical.
- Lineage: H-3000 Harmonizer "Reverse Shift" → "Crystal Echoes" preset (Andrew Schlesinger / Wave Mechanics, now SoundToys).

## Deep spec (Programmer only)
Not reverse-engineered — capability only.
