# SoundToys PanMan — SoundToys (auto-panner / modulation)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 (manual; modern build ships in SoundToys 5.x) |
| Type | Rhythmic auto-panner / stereo modulation (with analog saturation) |
| Format | VST3 / AU / AAX (not stated in manual; standard SoundToys formats) |
| Source | manual: `SoundToys PanMan/SoundToys PanMan.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
PanMan is an auto-panner that moves a (mono or stereo) source around the stereo field, far beyond what hand-drawn automation can do. It models classic hardware panners (PanScan, Cyclosonic FS-1, Electrospace Spanner) and adds modern rhythmic tools: six modulation modes (LFO, Rhythm Step, Rhythm Shape, PingPong, Random, Step) plus tempo-sync, a custom step/shape editor, an audio/MIDI/manual trigger system with a vintage "trigger divider," a trigger-input filter, dynamics-driven modulation (threshold/attack/release moving rate/width/offset), and 7 analog saturation styles. It can pan "beyond the speakers" — up to ±105° offset and up to 210° of width modulation. Distinct vs ordinary panners: it can be *triggered by the music itself* (every snare hit, every Nth transient) and its panning rate/width/offset can be *modulated by track dynamics*.

## Controls (every param → musical effect)

### Global (header + always visible)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Preset name / ◀ ▶ / Save / Reset | — | Browse, save, reset presets (top bar) | Recall starting points; PanMan presets are a great tour of what it does |
| Modulation Mode menu | LFO · Rhythm Step · Rhythm Shape · PingPong · Random · Step | The white button (center) picks the whole engine; control layout changes per mode | The single biggest decision — sets everything below |
| Input level | −24…+24 dB | Boosts/attenuates signal into PanMan; default ≈ unity | Drive harder into the Analog Style for more saturation |
| Output level | −24…+24 dB | Boosts/attenuates output; default ≈ unity | Compensate level after driving input / saturation |
| Input/Output LED meters | yellow = −6 dB / red = clip | Visual level; red may = audible clipping (may be desired) | Gain-staging the saturation |
| Tweak button | toggle | Reveals the slide-out Tweak Menu (per-mode extra controls) | Always — the real depth lives here |
| Pan Position meter | L–C–R LEDs | Shows live pan; red = normal range (−90..+90°), yellow = "beyond speakers" | Keep panning "in the red" if you don't want the extreme look |

### Common pan controls (shared by most modes)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Offset | −105°…+105° (default 0 = center) | Base/center pan position. ±90° = fully one channel; ±105° = "beyond the speaker" | Re-center the whole effect; park a sound off to one side |
| Width | 0…210° of modulation (±105°) (default 180°) | How far around the offset the pan swings | Subtle drift vs full hard-pan ping; widen for drama |
| Smoothing | Hard ↔ Soft | How abruptly pan jumps between positions; on L→R/R→L it controls snap-back hardness | Hard = clicky/steppy rhythmic; Soft = gliding sweeps |
| Feel (Rhythm Step only) | Rush ↔ Drag | Shifts the whole pattern early/late in time (pattern phase); wraps around | Push panning ahead of / behind the beat for groove |
| Groove (Rhythm Shape only) | Shuf ↔ Swing | Adds shuffle/swing feel to the shape pattern | Make synced shapes feel human / swung |

### Tempo / rhythm engine (rhythmic modes)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Direction buttons | L→R · Back-and-Forth · R→L (amber = active) | Basic pan shape/direction for LFO, Rhythm Step. In **Rhythm Shape** these are Ramp-Down · Triangle · Ramp-Up | Pick the underlying motion shape |
| Rate (LFO mode) | 0.1 Hz…10 Hz | LFO speed in Hz (1 Hz = one pan cycle/sec) | Free-running (non-synced) panning speed |
| Rhythm (Step / Shape / Random) | beat-length menu (e.g. 1/2, 1/4, 1/8, 1/16, dotted/trip) + "custom" | Rhythmic transition rate — how often it moves to the next position | Tempo-locked panning; pick the note value |
| Steps (Rhythm Step) | count menu | Number of steps in the pattern before it repeats | Build longer / odder step sequences |
| Tap Tempo | tap pad + BPM display | Tap to set BPM (for non-click material or to find "feel") | Live tracks, or to dial slightly-off-grid organic motion |
| MIDI toggle | down = use Rate knob · up/on = MIDI clock master | Lets host MIDI clock drive the rate | Lock panning to project tempo |

### Trigger engine (PingPong, Random Step)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Trigger (threshold) | dB threshold; white notches light red w/ audio | Audio level that fires a pan transition (acts like a threshold knob) | Make the track's own transients drive the panning |
| Manual Trigger button | momentary (automatable / MIDI-mappable) | Fires a trigger by hand; audio must be *below* threshold to take | Automate jumps at song points; manual/MIDI triggering |
| Trigger Divider | 1…12 (LCD count + LED ring) | # of triggers needed before it actually moves position (vintage PanScan feature) | "Move L→R every 3rd snare"; thin out busy triggers |
| (turn off audio trigger) | Trigger knob fully up | Disables audio-based triggering (use MIDI/manual only) | When you only want manual/MIDI fires |

### Dynamics / Tweak Menu — shared by LFO · Rhythm Step · Rhythm Shape
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Threshold | dB (e.g. −40…0); notches turn red w/ level | Level the input must exceed before dynamic mod (of rate/width/offset) engages; *how far above* sets mod depth (in Env mode). Below threshold = mod fully off | The master gate for all dynamics-driven panning |
| Attack | 0…5000 ms | How long the Rate/Width Mod take to reach full modulation once over threshold | Fast = instant grab; slow = smooth swells in motion |
| Release | 0…5000 ms | How long mod returns to normal after signal drops below threshold | Match the source's decay for natural-feeling tracking |
| Mode (Env / Gate) | toggle | **Env**: mod scales with how loud the signal is. **Gate**: mod "pings" to full while signal is over threshold (on/off feel) | Env = expressive/dynamic; Gate = consistent hits |
| Offset Mod | bi-polar (Left ↔ Right, center = 0) | Dynamics move the *base offset* — a dynamically-controlled pan | Make louder hits shove the sound to one side |
| Width Mod | bi-polar (Slim ↔ Wide, ±45° typ., center = 0) | Dynamics widen/narrow the pan; ±105° total always enforced | Snare hits open up the width; quiet = narrow/centered |
| Rate Mod | bi-polar in octaves (Slow ↔ Fast, center = 0) | Dynamics speed up/slow the LFO/Rhythm (1.00 = x2, 2.00 = x4, 3.00 = x9); works even under MIDI sync (drifts out, re-locks) | Louder = faster spin; momentary speed bursts |

### Trigger filter — Tweak Menu for PingPong · Random Step
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Type | OFF · HPF · LPF | Filter feeding the trigger detector (not the audio path) | Stop bass energy from firing triggers; isolate hats |
| Cutoff | 100 Hz…15 kHz | Where the trigger filter acts | Tune which frequency band drives the trigger |
| Gain | −20…+20 dB | Trims level into the trigger detector (compensate for the filter) | Re-balance trigger sensitivity without touching threshold |
| Monitor | On / Off | Hear the *filtered* source (no panning) to set the filter | Audition exactly what the trigger "hears" |

### Step editors (Tweak Menu)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Rhythm Step Editor | draggable point grid (L/C/R × time) | Draw custom pan sequences; click adds, Option/right-click removes, drag moves (snaps to grid; Cmd/Alt-drag = off-grid) | Hand-design exact stereo step patterns |
| Rhythm (Shape) Editor | drum-machine-style event grid | Each event triggers one full cycle of the LFO shape; click add/remove, Opt/Shift-drag = width/duration | Place when the shape sweep happens, per beat |
| Num Bars | count | Pattern length in bars | Multi-bar evolving patterns |
| Beats/Bar | count | Beats per bar (match the song meter) | Odd meters / matching the groove |
| Bar | selector | Which bar you're editing (for >1-bar patterns) | Edit long patterns one bar at a time |
| Grid | note-value menu (e.g. 1/8) | Snap/spacing of the editor grid | Tighter/looser quantize of edits |
| Smoothing Mode (Rhythm Step) | Linear · Sine · Exp · Sym · Rev | Curve between points: straight / sinusoidal / scooped / even-curved / reverse-scooped | Shape the *feel* of each transition |
| Shape Preset / Rhythm Preset | menu + floppy "Save" | Load factory/user pattern files; save your own | Reuse custom patterns across sessions |

### Analog Style (all modes; saturation character)
| option | character |
|---|---|
| Clean | Max non-distorted range, fairly hard clipping |
| Fat | Smooth low-frequency distortion |
| Squash | Like Fat but more compressed |
| Dirt | Smooth broadband saturation |
| Crunch | Exaggerated high-end clipping |
| Shred | Lots of asymmetrical clipping |
| Pump | Extreme pumping compression |

## Use by lens
- **Producer (create):** This is a sound-design playground. Use **Rhythm Step / Rhythm Shape** synced to host tempo to make signature tempo-locked pan patterns (draw your own in the editor). **Random** for ear-candy movement on pads/synths/FX returns. **PingPong** on drums/percussion so the kit ping-pongs on transients — set the **Trigger Divider** (e.g. 3) for "move every Nth hit." Use **Offset/Width up to ±105°/210°** for dramatic "beyond the speakers" effects, and pick an **Analog Style** (Crunch/Shred/Dirt) to add grit while you pan. Dynamics mods (Width/Rate/Offset Mod + Threshold) let the *track itself* drive the motion — "sweep when the snare hits," "spin faster on a loud vocal."
- **Mixing (balance):** Use gently for width and interest without wrecking mono. **LFO** at a slow Rate with modest Width + **Soft** Smoothing = subtle, musical drift on backing vox, guitars, synths. Keep an eye on the **Pan meter** (stay "in the red," ±90°) and use the **trigger filter (HPF)** so bass doesn't trigger or get thrown off-center. Watch mono compatibility — heavy width can thin the center. Use **Input/Output** to gain-stage and keep Analog Style on **Clean/Fat** if you only want subtle color.
- **Mastering (finalize):** Generally **not** a mastering tool — it intentionally moves and saturates the stereo image, which is destructive on a full mix. Avoid on the 2-bus. If ever used on a stem/parallel for a creative master, keep Width small, Smoothing Soft, Analog Style Clean, and check mono — but treat as an effect, not a finalizer.

## Notes / gotchas
- **Six modes, different layouts:** the front panel + Tweak Menu reconfigure per mode. Trigger modes (PingPong, Random Step) expose Trigger + Divider + trigger filter; rhythmic modes (Rhythm Step/Shape, Random) expose Rhythm/Tempo/MIDI; LFO exposes Rate.
- **Trigger filter ≠ audio filter:** Type/Cutoff/Gain shape only what the *trigger* listens to; use **Monitor** to hear it. The audio you pan is unfiltered.
- **"Beyond the speakers":** ±105° offset and 210° width are real and can sound wide/weird; the **yellow** meter LEDs warn you you've left the normal ±90° range. Width Mod cannot push past ±105° total (it's clamped).
- **Env vs Gate** (dynamics Mode) drastically changes feel: Env = proportional to loudness; Gate = full-depth ping while over threshold.
- **Rate Mod survives MIDI sync:** it temporarily drives the rate out of sync, then re-locks to host clock when mod returns to base.
- **Manual Trigger** only fires when audio is below the Trigger threshold; it's automatable / MIDI-mappable for song-section jumps.
- **Saturation is always-on per Analog Style** at all levels; drive it with Input, recover with Output. Clean still hard-clips at the top.
- **Custom rhythm:** selecting/creating a custom pattern shows "Custom" and disables the Direction/Step buttons (the pattern controls them).
- No oversampling / latency / CPU figures stated in the manual. iLok-authorized (per vendor note).

## Deep spec (Programmer only)
not reverse-engineered — capability only.
