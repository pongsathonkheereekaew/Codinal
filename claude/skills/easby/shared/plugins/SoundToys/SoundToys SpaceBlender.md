# SoundToys SpaceBlender — SoundToys (experimental reverb / spatial sound-design)

| | |
|---|---|
| Vendor / ver | SoundToys · v5.5 (manual: User's Guide v5.5, Mac & Windows) |
| Type | Experimental algorithmic reverb / "imaginary space machine" — gated/reverse/bloom/decay spatial processor with embedded modulation, spectral evolution, and freeze |
| Format | VST / VST3 / AU / AAX (SoundToys standard; not explicitly listed in manual) · iLok authorized |
| Source | manual: `SoundToys SpaceBlender/SoundToys SpaceBlender.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
SpaceBlender is an experimental reverb for building *unreal, imaginary* spaces rather than modeling real rooms. Inspired by swarm synthesis (not the usual delay-network-with-feedback reverb topology) and by ambient-music tape-loop pioneers, it sends sound through a defined "time tunnel" — a time window from 100 ms up to 60 seconds — where the signal can stay at a constant or decaying level and then simply **stop/disappear** (like a gated reverb that can stretch from a fraction of a second to a full minute), or be shaped to decay like a conventional reverb. The whole effect is sculpted on an interactive **Visualizer** with a drag-able X/Y cursor that morphs the envelope between gate, reverse, decay, and bloom shapes in real time. Distinct from normal reverb: tails can grow *brighter* over time (Color), density morphs from lush to sparse/grainy (Texture), embedded modulation adds watery motion (Mod), and Freeze loops the output back through itself for evolving, organically degrading ambient washes. Pedigree: founder Ken Bogdanowicz + sound designer Andrew Schlesinger (the original Eventide DSP4000 Black Hole team), with nods to the Ursa Major Space Station, Lexicon 224, and the Swarmatron.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Visualizer (X/Y Cursor)** | drag anywhere in display | Grab-and-drag sonar-style cursor that reshapes the space envelope/direction. Combination of X + Y gives extensive control over how the effect evolves. Time/length stay constant regardless of cursor position — only amplitude & envelope change. | Primary creative control — morph between gate / reverse / decay / bloom shapes live while playing. |
| ↳ **X-Axis** (cursor horizontal) | left ↔ right | Shapes the amplitude envelope. Moving right = fade-in/fade-out; far-right *inverts* the envelope for reverse-sounding effects with a long build time. | Dial reverse swells, slow blooms, gated bursts. |
| ↳ **Y-Axis** (cursor vertical) | top ↕ bottom | Amount of envelope shaping. Top = no envelope (constant level for the whole timeframe, then disappears). Moving down thins the effect at the edges → more drastic amplitude change. | Top for flat gated tails; lower for tapered, dynamic shapes. |
| **Time** | 100 ms – 60,000 ms (1 min); in **Sync** = 1–32 beats | Sets the total length of the space (the time-tunnel window). Shown in the Time display as ms or bars/beats. | Short non-linear bursts (~100 ms) up to minute-long ambient/meditation tails or frozen drones. |
| **Sync** (button) | On / Off | On = Time locks to host tempo, length set in beats (1–32), display shows bars. Off = free, no tempo-sync / no quantization. | On for ambient loops, tempo'd gated/frozen tails; Off for free-running sound design. |
| **Warp** (button) | On / Off | Changes how Time *changes* respond. **On**: pitch + speed of sound within the space shift and Time changes are smoothed — sound glides to the new length like a tape echo retuning (with a very short momentary volume duck until it reaches the new value). **Off**: Time changes happen without pitch adjustment. | On for tape-style pitch warps when automating/modulating Time; Off for clean time changes. |
| **Color** | 0–100% (12 o'clock = neutral / 50%) | Tone control that evolves *over time* as sound passes through the delay matrix (not instant EQ). CW = high-frequency shelf boost → reverb grows **brighter** over time; CCW → darkens over time. 12 o'clock = no tonal change. | Lo-fi/dark tails (down) or unnatural "gets brighter as it decays" tails (up). |
| **Texture** | 0–100% (50% default) | Density / diffusion. Low = discrete delay taps (individual lines visible in display), sparse/grainy "swarming repeats." High = smooth, lush, diffused reverb. | Low for grainy/swarm/granular character; high for smooth lush wash. |
| **Mod** | 0–100% (50% default; can be off) | Depth of a complex, evolving chorus-like modulation deep in the processing layers (shape & rate are preset; knob = depth). Off = static; up = rich, watery motion. | Subtle for natural movement; cranked for lush watery synth/guitar; small doses on vocals/acoustic. |
| **Mix** | 0–100% dry/wet (12 o'clock = 50/50) | Dry/wet blend. | Parallel depth vs. fully-wet sound design. (Long/variable shapes can seem imperceptible at first — "wait for it.") |
| **Freeze** (button) | On / Off | Captures and loops the current sound, feeding output back into itself. Each repeat is re-modified in amplitude & tone → individual notes merge/diffuse into an evolving, organically degrading ambient wash. Manipulate the frozen sound with the cursor/other controls. | Infinite-ish evolving pads, drones, ambient beds; "frozen tail" performance. |
| **Bypass** | On / Off | Standard plugin bypass (control-bar). | A/B the effect. |

## Use by lens
- **Producer (create):** This is a sound-design playground first. Drag the cursor to flip envelopes into reverse swells and slow blooms; set long Time (10–60 s) + Freeze for evolving cinematic drones and ambient beds; pull Texture down for grainy/swarm granular textures; ride Color up for "impossible" brighten-over-time tails; automate Time with Warp ON for tape-style pitch warps. Turn the simplest source into a dramatic cinematic swell.
- **Mixing (balance):** Despite the avant-garde framing it works as an everyday depth/dimension reverb on vocals, guitars, synths. Sync ON + short-to-medium Time for tempo'd gated/ambient tails; keep Mod small on vocals & acoustic instruments; use Mix for parallel depth. Watch Color when feeding bright sources — it can get very bright.
- **Mastering (finalize):** Not a mastering tool — it's a creative, heavily-colored spatial effect (gated/reverse/bloom shapes, embedded modulation), unsuitable for transparent bus reverb on a mix bus. Use only as a deliberate creative send on a stem, not across a master.

## Notes / gotchas
- **Not a normal reverb topology** — swarm-synthesis-inspired; tails can *disappear* (gated time-tunnel) rather than decay, and can brighten over time. Set expectations accordingly.
- **Time/length is fixed by the Time knob** — the cursor never changes total length, only amplitude/envelope shape.
- **Warp OFF** has a brief momentary volume duck while Time settles to a new value; **Warp ON** adds pitch/speed shift + smoothing on Time changes.
- **Color warning:** bright input + high Color can get extremely bright — ease in.
- Long/variable shapes can sound imperceptible at first; "wait for it" — something is always evolving.
- **Hidden interactions:** right-click a knob *name* to show its numeric value; Shift-drag to fine-tune; **Ctrl+Option (Mac) / Ctrl+Alt (PC)** to lock a knob so it doesn't change when switching presets.
- All controls are DAW-automatable for real-time morphing.
- **Resizable UI:** drag lower-right corner, or pick 75/100/125/150/175/200% from the Menu icon.
- Presets via standard SoundToys preset manager (factory "Ambient" etc. + user saves).
- Manual states no oversampling/latency/CPU figures; iLok authorization.

## Deep spec (Programmer only)
Not reverse-engineered — capability only.
