# Xfer LFO Tool — Xfer Records (modulation / LFO FX utility)

| | |
|---|---|
| Vendor / ver | Xfer Records · v1.5.0 (April 2015) · coding Steve Duda |
| Type | Tempo-syncable LFO shaper → modulates filter cutoff/reso, volume, pan, + built-in multimode filter. Also a MIDI CC generator. |
| Format | VST (2/64-bit), AudioUnit, AAX · Win + macOS · separate "LFOToolMFX" MIDI-FX build for Logic X |
| Source | manual: `Xfer LFO Tool/Xfer LFO Tool.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
LFOTool draws a custom, tempo-locked LFO and routes it to up to four destinations at once — **filter Cutoff, filter Resonance, Volume, Pan** — plus a fifth filter-dependent **Var** parameter. Its signature jobs are sidechain-style **volume "pumping"** (the classic ducked-kick effect without a sidechain), **auto-pan**, **tremolo/gate**, and **rhythmic filter sweeps**. The LFO is a point-and-tension curve editor (like a step sequencer or envelope) with **12 selectable graphs per preset** that can be switched live via MIDI notes or automation, each with its own warp/speed multiplier. A full **multimode filter** (ladder/SVF/comb/flanger/phaser/formant/EQ/reverb) sits in the signal path as the Cutoff/Reso/Var destination. It can additionally **emit the LFO as MIDI CC** to drive external synths/hardware. Distinct from a generic LFO: hand-drawn arbitrary shapes, per-graph warp, swing, PWM, sample-accurate host sync, and MIDI-note graph-switching turn it into a rhythmic performance tool, not just a wobble source.

## Controls (every param → musical effect)

### Graph editor (the LFO shape — heart of the plug-in)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Graph Selector | 1–12 | Picks which of 12 graphs to view/edit. Switching the *view* does NOT change the sound — playback is set by LFO Routing source numbers. | Build variations (e.g. graph 1 = pump, graph 2 = stutter) to switch between live. |
| Graph Area | drawable curve | Double-click = add point; double/ctrl-click a point = remove; alt-click/drag = snap point to Grid (Snap); shift-click = add points as a horizontal step at Grid size (step-sequencer style). | Sculpt any LFO shape — ramps, gates, stutters, custom envelopes. |
| Tension curves | hollow point per segment | Each non-vertical/horizontal segment shows a hollow midpoint; drag it to curve the segment. Alt-click a hollow point curves ALL segments at once. | Smooth or sharpen transitions (exponential pumps vs. linear). |
| Warp (speed multiplier) | default 1x | Plays the *selected* graph faster/slower than the global Rate. LFO restarts at end of the global Rate period. | Pack fast detail into one graph without redrawing; or slow a busy shape. |
| Copy / Paste | per-graph | Duplicate the current graph to another of the 12 slots. | Quick variations from a base shape. |
| Save (disk icon) | — | Store the current graph to the Shape Menu (saved into "Shapes" subfolder). | Reuse your own LFO shapes across projects. |
| Shape Menu | dropdown | Load a preset *graph shape* as a starting point — replaces only the visible graph, keeps the rest of your settings. | Fast "starting point" without loading a full preset. |
| LFO Output Meter | readout | Shows live LFO output value. | Confirm the LFO is moving / monitor depth. |

### LFO Controls (global — affect how ALL graphs play back)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Rate | host beat divisions (e.g. 1/4) **or** Hz | Time to play one cycle of the graph. | Set the rhythmic speed (1/4 pump, 1/8 tremolo, etc.). |
| Musical Note icon | on = BPM-sync / off = Hz | Toggles tempo-sync vs. free-running Hz. | On for in-tempo FX; off for un-synced wobble/LFO. |
| Anchor icon | on / off | Locks LFO phase to the song position (each cycle stays in-phase). With Anchor on, changing Rate makes playback "jump" to stay phase-locked. | On = tight to the grid; turn **off** if you want to sweep Rate smoothly without jumping. |
| Dot (.) / Triplet (3) icons | on / off | Include dotted / triplet divisions in the Rate list (only when Note icon = on). | Dotted pumps, triplet gating. |
| Swing | bipolar, 0 = none | Alternates each playback faster/slower (shuffle). **Requires Anchor AND Note/BPM both on.** Typical with Rate at 1/8 or 1/16. | Add groove/shuffle to gates and pumps. |
| Phase | bipolar, 0 center | Shifts the phase of the graphs left/right. Blue background shading shows actual LFO output. | Nudge the modulation earlier/later vs. the beat. |
| PWM | bipolar, 0 center | "Pulse-width" — squeezes line segments together left/right (compress/expand the shape over time). | Reshape duty cycle of gates; tighten/loosen pumps. |
| Smooth | 0 → up | Makes LFO output more gradual (slew). | Kill clicks/zipper noise from steep vertical jumps in the graph. |
| Snap | grid divisions (e.g. 8) | Sets Grid Size in the graph area for alt-/shift-click snapping. | Lock drawn points to musical divisions for clean step shapes. |

### Additional controls
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Offset | −4096 to +4096 samples (shift-click = fine) | "Sync offset": runs LFOTool early (negative) or late (positive) vs. host timing — manual latency compensation when the host doesn't compensate. | Re-align the effect when it drifts; prefer using MIDI Note-Retrig for exact timing. |
| Oscilloscope (scope) switch | on / off | Draws a tempo-synced scope over the graph: grey = input/unprocessed, red = processed/output (colors editable in config). | Visually verify gating/pumping depth and shape. |

### LFO Routing (5 destinations)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Source # (per dest) | 1–12 | Which of the 12 graphs feeds **Cut / Res / Vol / Pan / Var**. | Assign different shapes to different destinations. |
| Cut depth | 0–100 (bipolar amount) | How much LFO modulates **filter cutoff**. (SVF must be enabled to hear it.) | Rhythmic filter sweeps / wah. |
| Res depth | amount | LFO → **filter resonance**. (SVF must be enabled.) | Animated resonance peaks. |
| Vol depth | amount (e.g. default 100) | LFO → **volume** — the classic "pumping"/sidechain-duck and tremolo/gate. | Sidechain-pump without a sidechain; trance gate. |
| Pan depth | amount | LFO → **stereo pan**. | Auto-pan / stereo movement. |
| Var depth | amount | LFO → the filter's **Var** parameter (function depends on filter type — see table). | Modulate 2nd-filter cutoff, formant shift, EQ gain, etc. |
| depth (master) | 0–100 | Global scaler over ALL the above depths. | Automate momentary depth (bypass/partial) without losing your per-dest amounts. |
| Blue dots (per slider) | meter | Show the *final* value (post-LFO + depth) for each destination. | Watch combined modulation result. |

### Filter module (the Cut/Res/Var destination engine)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Power switch | on / off | Enables/bypasses the filter. **Must be ON to hear Cut/Res modulation.** | Turn off if only using Vol/Pan (pump/auto-pan). |
| Filter Type | dropdown (see table) | Selects ladder / SVF LP/HP / band-peak-notch / dual / morphing / comb / flanger / phaser / EQ / reverb / formant. | Pick the character of the filtered sweep. |
| Cutoff slider | base freq | Base cutoff the LFO modulates around. | Set the sweep's center frequency. |
| Reso slider | base amount | Base resonance the LFO modulates around. | Set sweep emphasis/sharpness. |
| Mix slider | 0–100% (wet) | Wet/dry of the filter. Keep at 100% normally; lower for flanger/phaser/comb/downsampling balance (Flanges menu items: ~50%). | Parallel/blended filter effects. |
| Var slider | base value (function = filter-type-dependent) | "Fat" amount, 2nd cutoff, morph, formant shift, EQ gain, reverb damping, etc. — see table below. | Dial the secondary character of the chosen filter. |
| Drive slider | 0 → up | Input drive/saturation into the filter. | Add grit/harmonics to sweeps. |

#### Filter Types → Var parameter function
| Filter Type | Description | Var function |
|---|---|---|
| Mg 6/12/18/24 | Moog-style ladder lowpass | "Fat" amount |
| Low 6/12/18/24 | State-variable lowpass (SVF) | "Fat" amount |
| High 6/12/18/24 | State-variable hipass (SVF) | "Fat" amount |
| Band / Peak / Notch | SVF band/peak/notch | "Fat" amount |
| LH/LB/LP/LN/HB/HP/HN/BP/BN/PP/PN/NN | Dual SVF (1st letter primary, 2nd secondary; Reso links to 2nd cutoff via Var) | Cutoff freq of the 2nd filter |
| LBH/LPH/LNH/BPN | Morphing SVF (e.g. Low↔Band↔Hipass) | Morph between the three filter states |
| CombL / FlangeL / PhaseL | Comb/flanger/phaser w/ lowpass in feedback | LP cutoff (Flanges: set Mix ~50%) |
| CombH / FlangeH / PhaseH | Comb/flanger/phaser w/ hipass in feedback | HP cutoff (Flanges: set Mix ~50%) |
| CombHL / FlangeHL / PhaseHL | Comb/flanger/phaser w/ HP+LP in feedback | HL width (band separation) (Flanges: Mix ~50%) |
| EQ | Shelf (L/H) / Peak EQ | dB gain |
| Combs / Allpasses / Reverb | (varied) | Damping |
| Formant 1–3 | Formant "vowel" filters (Cutoff morphs between formants) | Formant shift |

### MIDI options
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Note Retrig | on / off | LFO restarts each note received (envelope-like). Click twice → "Env": LFO stops at end of cycle instead of looping. | Trigger pumps/envelopes per note; one-shot envelopes. |
| Note Gate | on / off | LFO stops on Note-Off (note release). | Momentary gating/tremolo lasting only while a note is held. |
| Vel→PWM | on / off | Incoming note velocity drives the PWM slider. | Velocity-sensitive duty-cycle. |
| Note→Rate | on / off | Note number (0–127) sets the Rate slider. | "Play" different LFO speeds from the keyboard. |
| Note→Cutoff | on / off | Note number (0–127) sets the Cutoff slider. | Keyboard-controlled base cutoff. |
| OFF / CC out depth ('midi') | OFF → 0–127 | Sends the LFO out as a **MIDI CC** stream (VST only; use the MFX build in Logic X). CC resolution 0–127, updates whenever value changes >1/128. | Drive external synths/hardware/other plug-ins with the same LFO. |
| CC Lock icon | on / off | Locks the MIDI CC number assignment so it doesn't change when switching presets. | Preserve your CC mapping while browsing presets. |
| MIDI Drag-export icon | drag | Drag the blue MIDI icon to a MIDI track to export the graph as MIDI CC data (raise CC depth first; ~89 reaches 0–127 with cutoff centered). | Bake the LFO into editable MIDI clips. |
| Graph-switch via notes | MIDI notes (lowest 5 octaves) | Notes select the *routing source graph* per destination: 0–11 Cutoff · 12–23 Reso · 24–35 Volume · 36–47 Pan · 48–59 Var. **Overridden** if Vel→PWM / Note→Rate / Note→Cutoff are enabled. | Live-switch LFO shapes per destination from a controller/clip. |

## Use by lens
- **Producer (create):** The go-to for sidechain "pump" without routing a sidechain — Vol destination, draw a kick-shaped duck on graph 1, Rate 1/4. Build trance gates / stutters (shift-click step shapes, Snap to 16), auto-pan (Pan dest), and rhythmic filter wahs (enable filter, Cut dest). Switch between 12 hand-drawn grooves live via MIDI notes for performance/variation. Use it as a MIDI CC LFO to wobble any external synth.
- **Mixing (balance):** Tame or create rhythmic dynamics on a bus (ducked pads under a kick), add subtle stereo movement via Pan, or carve repetitive filter motion on a synth. Use **Smooth** to remove clicks from steep gates, and the **master depth** to automate the effect in/out for builds. Scope on to confirm depth visually.
- **Mastering (finalize):** Generally out of scope on a master bus (it's a creative modulator, not a corrective tool). At most, very subtle tempo-synced auto-pan or a gentle gate on a stem — keep depth low, Smooth up, watch the scope.

## Notes / gotchas
- **Filter Power must be ON** to hear Cut/Res/Var modulation; Vol and Pan work regardless.
- **Swing** needs both **Anchor** and **BPM/Note** on. Anchor-on makes Rate changes "jump" (phase-lock); turn Anchor **off** to sweep Rate smoothly.
- For Flanger ("Flanges") filter menu items, set the **Mix knob to ~50%** for best results.
- **Logic:** no native way to route MIDI notes into an audio-insert plug-in → it appears as an **AU MIDI Effect** ("AU MIDI-controlled Effects → Xfer Records → LFOTool → Stereo"); set its Side-Chain (top-right "Side Chain: None") to the source track and mute the dry track's fader. The separate **LFOToolMFX** is for sending MIDI CC out atop an Instrument track (filter/vol/pan/split params hidden in that build).
- **Ableton routing for MIDI control:** put LFOTool on the audio track, create a MIDI track, set its "MIDI To" → the audio track → "1-LFOTool", and arm/Monitor "IN".
- **MIDI CC out is VST only** (or the Logic MFX build); resolution limited to 0–127.
- **No copy protection / no latency reported** beyond the optional manual Offset; offset is a manual sync nudge, not auto-PDC. Prefer **Note Retrig** for exact timing.
- Coded entirely in C++ for low CPU. Ships with dozens of presets; preset folder = `/Library/Audio/Presets/Xfer Records/` (macOS) or `Documents/Xfer/` (Win). Custom **shapes** save to a "Shapes" subfolder inside LFOTool Presets.
- Power-user config: hand-editable `LFOToolConfig.txt` in the presets folder (global, not per-project) — sets scope colors, default plug-in size, update rate, MIDI thinning, default sidechain preset, etc.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
