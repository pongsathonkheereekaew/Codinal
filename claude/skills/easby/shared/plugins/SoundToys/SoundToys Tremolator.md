# SoundToys Tremolator — SoundToys (tremolo / rhythmic amplitude modulation / auto-gate)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 (manual: "Version 5, For Mac and Windows"; modern build ships in SoundToys 5.x) |
| Type | Tremolo / rhythmic amplitude modulation + programmable auto-gate (with envelope-follower dynamics + analog saturation) |
| Format | VST3 / AU / AAX (not stated in manual; standard SoundToys formats) |
| Source | manual: `SoundToys Tremolator/SoundToys Tremolator.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Tremolator is rhythmic amplitude modulation — it oscillates a signal's *volume* with an LFO. It re-creates the tremolo of classic hardware (Fender vibrato amps, Wurlitzer electric piano) by analyzing those units' actual waveshapes and pairing them with 7 "Analog Style" saturation/distortion models. Beyond vintage emulation it adds modern tools: tempo-sync via MIDI clock, a programmable **Shape (LFO waveshape) Editor**, a drum-machine-style **Rhythm Editor** for custom patterns, Groove/Feel/Accent controls for shuffle-swing-and-pocket, and a **Tweak Menu** built around an envelope follower so your *playing dynamics* can drive the tremolo's rate and depth. Switch the smooth LFO to a square wave (or push Depth/Accent hard) and it becomes an aggressive rhythmic **auto-gate** / remix chopper. Distinct vs an ordinary tremolo: it's tempo-locked, pattern-programmable, groove-aware, and dynamically responsive to the input.

## Controls (every param → musical effect)

### Header / preset bar
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Preset name / ◀ ▶ / Save / Reset | — | Browse, save, reset presets (top strip) | Recall starting points; presets range "tame to out-of-this-world" |

### Main Control Panel — modulation shape & feel
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Depth | Min…Max | How much of the signal's amplitude is modulated — subtle volume shimmer up to full gating (especially with square/saw shapes) | Set the intensity; push to Max + square wave for auto-gate. Can be dynamically modulated via Tweak's Depth Mod |
| Groove | Shuffle ↔ 0 (12 o'clock) ↔ Swing | Adds a triplet-type rhythmic feel by shifting the "even" beats; CCW = shuffle, CW = swing. Amount is relative to current Rhythm; applies regardless of rate/shape/rhythm | Make synced tremolo/gate feel swung or shuffled instead of robotic |
| Feel | Draggin' ↔ 0 ↔ Rushin' | Shifts the *whole* tremolo relative to the beat (pocket), not just the groove. CCW (Draggin') adds pre-delay so it falls behind the downbeat; CW (Rushin') = negative pre-delay, ahead of the beat | Lay the effect back in the pocket or push it ahead for urgency |
| Accent | Sync ↔ 0 ↔ Max | Emphasizes/de-emphasizes the downbeat ("One") vs beats 2-3-4. CW (Max) silences 2-3-4 so only "One" pulses; CCW (Sync) drops out the "One" downbeat while 2-3-4 keep modulating | Build rhythmic accents/gating; with square wave + Groove + Depth = highly custom MIDI-synced rhythm gate |
| Shape | menu: Sine, Triangle, Square, … + Custom | Selects the LFO waveshape. Smooth shapes = classic tremolo; square/sharp = gating. Custom shapes built in the Tweak Shape Editor | Pick the modulation character; square = auto-gate, sine = vintage amp throb |
| Mod (indicator light) | blue pulsing LED | Visual reference of current modulation speed; pulses in sync with the pattern | Eyeball the rate / confirm sync |
| Rhythm | menu: 1/32 note … up to 4 bars (bar & note values, incl. dotted/trip) + Custom | Subdivision of the Rate — how often the LFO cycle is applied. Custom patterns built in the Rhythm Editor | Set the note value of the tremolo/gate (e.g. 1/8, 1/16); lock to a groove |
| Rate | 30 BPM … 240 BPM | Basic modulation rate in BPM; sets the downbeat on the "one" of a 4-beat measure (then subdivided by Rhythm). Fixed to the value you set | Free-running (non-MIDI) tremolo speed. Note: actual heard speed depends on the Rhythm subdivision |
| MIDI toggle (next to Rate) | down/off = Rate knob · up/on = host MIDI clock | Switches the master rate source. With MIDI on, Rhythm note-divisions still work but all stay locked to host clock | Lock tremolo/gate to project tempo |
| Tap Tempo | tap pad + BPM readout | Tap to set BPM | Tracks not on a click; or deliberately tap slightly off-grid for organic "feel" |
| Input level | −24…+24 dB (default ≈ unity) | Boosts/attenuates signal *into* Tremolator; drives the Analog Style harder | Gain-stage; push for more saturation/distortion |
| Output level | −24…+24 dB (default ≈ unity) | Boosts/attenuates *output*; default unity = "what goes in comes out same level" | Recover level after driving Input / heavy saturation |
| Input/Output LED meters | yellow = −6 dB below clip · red = max / possible clipping | Visual input & output levels | Gain-staging; red may = audible clip (may be desired) |
| Tweak button | toggle | Reveals the slide-out **Tweak Menu** (envelope-follower dynamics + Width + Analog Style + Shape/Rhythm editors) | Always — the dynamic depth and editors live here |

### Tweak Menu — envelope follower / dynamics
> Underlying all Tweak controls is an envelope follower watching the input level; all of these are referenced to that follower signal.
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Threshold | −80 dB … 0 dB (white ring turns red w/ level) | Level the input must exceed before Rate/Depth Mod engage. Above threshold = mod active; below = mod fully off. *How far above* sets how deep the mod goes (max set by the Mod knobs) | The master gate for all dynamics-driven modulation; central to every Tweak knob |
| Attack | 0 … 5000 ms | How long Rate/Depth Mod take to reach full once over threshold. Fully CCW = instant; higher = slower, smoother swells | Fast = grab transients; slow = gradual rate/depth swells. Signal must stay above threshold for ~the Attack time to fully respond |
| Release | 0 … 5000 ms | How long Rate/Depth Mod take to return to base after signal drops below threshold | Match source decay; short = track fast changes, long = smooth |
| Mode | Env / Gate | **Env**: mod scales with input loudness (louder = more, quieter = less). **Gate**: mod ignores how-far-above and "pings" to full while signal is over threshold (on/off feel), at the Attack rate | Env = expressive/proportional; Gate = consistent full-depth hits |
| Rate Mod | bi-polar, octaves (Slower ↔ 0 ↔ Faster); LCD value | Dynamically speeds up / slows down the LFO/Rhythm rate, added/subtracted from base Rate. Scale in octaves: 1.00 = x2, 2.00 = x4, 4.00 = x16; can push into audio-rate for ring-mod effects. Works even under MIDI sync (drives out of sync, then re-locks) | Louder = faster throb; momentary speed bursts; "ring-mod" extremes |
| Depth Mod | bi-polar (Less ↔ 0 @ 12 o'clock ↔ More); LCD value | Dynamically increases/decreases tremolo depth based on input level above threshold. CW = add depth (base Depth gets biased/scaled back to make room); CCW = remove depth | Swell depth on loud hits / fade depth as chords decay. Tip: set front-panel Depth near Max and work Depth Mod backwards |
| Width | 0 … 100 | Stereo spread of the output. 0 = centered/mono; turning up widens; past ~3 o'clock uses out-of-phase info for a pseudo-super-stereo "outside the speakers" spread | Add stereo motion to the tremolo. Always check mono — wide settings may not translate |
| Analog Style | Clean · Fat · Squash · Dirt · Crunch · Shred · Pump (radio buttons) | 7 saturation/distortion algorithms applied at all signal levels (see table below) | Dial the analog character / amount of grit |

### Analog Style options
| option | character |
|---|---|
| Clean | Maximum non-distorted range, fairly hard clipping |
| Fat | Smooth low-frequency distortion |
| Squash | Like Fat but more compressed |
| Dirt | Smooth broadband saturation |
| Crunch | Exaggerated high-end clipping |
| Shred | Lots of asymmetrical clipping |
| Pump | Extreme pumping compression |

### Tweak Menu — Shape Editor (custom LFO waveshapes)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Shape Editor grid | draggable point graph | Draw custom LFO waveshapes. Default Sine has 3 points (each end + apex). Click = add point; Option/Alt-click = remove; drag = move. Unlimited points / very complex shapes | Recreate vintage shapes or invent new modulation curves; tighten/loosen gate timing |
| Smoothing | None … Max | Rounds the edges between points. 0 = stair-step / abrupt jumps; Max = fully smooth | Soften steppy custom shapes; sharpen for gating |
| Smoothing Mode | Lin · Sin · Exp · Sym · Rev (radio) | Curve used between points: **Lin** straight lines · **Sin** sinusoidal (very smooth) · **Exp** scooped, rises quickly (exp ADSR-like) · **Sym** even/symmetrical curve · **Rev** reverse scoop (rises slowly, falls quickly) | Shape the *feel* of each transition in a custom waveshape |
| Shape Preset | menu + floppy "Save" (Save / Save As… / Organize…) | Load factory/user shapes; editing flips readout to "Custom"; save your own to the Shape pop-up | Reuse custom shapes across sessions |

### Tweak Menu — Rhythm Editor (custom patterns)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Rhythm Editor grid | drum-machine-style event grid (green) | Build custom rhythm patterns. Each placed event triggers one full cycle of the LFO Shape. Click a division to add/remove; must have available "blank" length to add (a 1/4 event needs the space two 1/8 events would occupy) | Hand-design exact rhythmic tremolo/gate patterns that evolve with the song |
| Num Bars | count | Pattern length in bars | Multi-bar evolving patterns |
| Beats/Bar | count | Beats per bar (match the song meter) | Odd meters / matching the groove |
| Bar | selector | Which bar you're editing (for >1-bar patterns) | Edit long patterns one bar at a time |
| Grid | note-value menu (e.g. 1/8, 1/16, 1/4) | Spacing/length of each LFO shape added when you click — set by Grid, NOT by available editor space | Tighter/looser resolution of placed events |
| Rhythm Preset | menu + floppy "Save" (Save / Save As… / Organize…) | Load factory/user patterns; save your own (incl. groove library patterns) | Reuse / browse custom rhythm patterns |

## Use by lens
- **Producer (create):** Tremolator's playground. Classic vibe: **Sine/Triangle** shape, modest **Depth**, **Rate** to taste (or MIDI-sync) + an **Analog Style** (Fat/Dirt) for amp-style throb on Rhodes, guitars, vox. Auto-gate / remix: **Square** shape, high **Depth**, MIDI on, pick a **Rhythm** (1/8, 1/16), then carve a pattern in the **Rhythm Editor** (or pull a groove preset) and add **Groove** (shuffle/swing) + **Accent** for a stuttering chopper. Use the **Shape Editor** to recreate a specific vintage waveshape or invent gate envelopes (tighten/loosen gate time with Smoothing). The **Tweak dynamics** make it expressive — set a **Threshold**, then **Rate Mod/Depth Mod** so the track's own loudness drives the throb (e.g. "speed up + deepen as the chord swells, fade as it decays"); push Rate Mod into audio rate for ring-mod ear candy. Add **Width** for stereo motion.
- **Mixing (balance):** Use subtly. Slow gentle **Sine** tremolo + low **Depth** adds movement/interest to pads, gtrs, backing vox. **Feel (Draggin'/Rushin')** and **Groove** to sit the motion in the pocket. Keep **Analog Style** on **Clean/Fat** if you only want color; gain-stage with **Input/Output** (watch the red LEDs). Mind mono compatibility — **Width** past 3 o'clock uses out-of-phase content; always check mono. As a rhythmic gate it's a strong creative-FX-bus / parallel tool, less a corrective one.
- **Mastering (finalize):** Not a mastering tool — it intentionally modulates level (and can gate/saturate), which is destructive on a finished mix. Avoid on the 2-bus. If ever used creatively on a stem/parallel master, keep Depth tiny, shape Sine, Width small/centered, Analog Style Clean, and check mono — but treat it as an effect, not a finalizer.

## Notes / gotchas
- **Heard speed = Rate × Rhythm subdivision.** The Rate knob sets the downbeat on "one"; what you actually hear depends on the Rhythm note value — set Rhythm to the division you want (1/4, 1/8, etc.).
- **MIDI toggle** swaps the master clock to the host; Rhythm divisions still apply but stay locked. **Rate Mod survives MIDI sync** — it drives temporarily out of sync, then re-locks.
- **Custom Shape vs Custom Rhythm** are separate editors: Shape = the LFO waveshape (one cycle); Rhythm = where/when full LFO cycles fire across bars. Selecting/editing either shows "Custom".
- **Depth Mod biases the base Depth** — adding mod scales the front-panel Depth back to leave headroom; set Depth near Max and work backwards (standard synth practice).
- **Env vs Gate** (dynamics Mode) changes feel dramatically: Env = proportional to loudness; Gate = full-depth ping while over threshold.
- **Threshold must be exceeded** for any Rate/Depth Mod; staccato sources may need fast Attack or they won't stay above threshold long enough to respond.
- **Analog Style is always-on** at all signal levels per the selected algorithm; drive with Input, recover with Output. Even Clean hard-clips at the top.
- **Width** past 3 o'clock = out-of-phase pseudo-super-stereo — test in mono.
- **Rhythm Editor add rule:** you must have enough "blank" length to place an event (e.g. can't drop a 1/4 unless the equivalent 1/8 space is free).
- No oversampling / latency / CPU figures stated in the manual. Vendor note lists authorization as **iLok**. Manual © 2015, Version 5.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
