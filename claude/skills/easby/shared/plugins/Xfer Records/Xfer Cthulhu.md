# Xfer Cthulhu — Xfer Records (MIDI effect: chord generator + arpeggiator)

| | |
|---|---|
| Vendor / ver | Xfer Records · v1.1 (Oct 2015), manual rev 22 Sep 2015 · coder Steve Duda |
| Type | MIDI FX (note generator) — chord memorizer/player + pattern arpeggiator. Outputs MIDI only (internal sawtooth is reference tone, not a real instrument) |
| Format | VST (Win/Mac), AudioUnit (`Cthulhu.component` audio inst + `Cthulhu_MFX.component` Logic X MIDI-FX). No AAX. |
| Source | manual: `Xfer Cthulhu/Xfer Cthulhu.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Cthulhu is two MIDI tools in one plug-in, used to generate notes for a downstream instrument. The **Chords module** is a chord memorizer: each incoming MIDI note triggers a stored chord (up to 8 notes), so one-finger presses play full progressions. 128 chord slots per preset, 150+ factory presets, plus Learn/record, MIDI-file import, and a deep chord-analysis/sort engine (Circle of 5ths, Hindemith, by low/high note, etc.) for reorganizing your chord set. The **Arpeggiator module** is a graph-based step sequencer with 8 independent data lanes (note-selection, octave, pitch, velocity, gate, timing, harmony, randomize) and 12 patterns — each lane can have its own length for polymetric/evolving arps. Signal flow when both are on: **Chord → Arp** (chord built first, then arpeggiated). It only emits MIDI; route that MIDI to a synth to hear it. Distinct for its chord-theory analysis/transform tools and its per-lane-length graph arp with chord-arpeggio mode, ties, and intelligent (scale-degree-only) transposition.

## Controls (every param → musical effect)

### Top bar / global
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Speaker (mute) | on/off | Mutes the internal sawtooth reference tone; MIDI still transmits. Default ON (1) in 1.1 | turn OFF once routed to a real synth, so you only hear the destination |
| Chords on/off | on/off | Enable/bypass the Chords module | play single notes raw vs. expanded to chords |
| Arp on/off | on/off | Enable/bypass the Arpeggiator | sustained chords vs. rhythmic arp |
| Transpose | semitones (global) | Global note-out transpose; exposed as a VST parameter (automatable) | shift whole output up/down, automate key changes |
| Gear (GUI size) | 100% / 200% | Resizes the GUI (top-right). Default size set in CthulhuConfig.txt | hi-DPI / readability |

### Chords module
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Chord slots | 128 slots | One chord memory per incoming MIDI pitch; last-triggered slot shows in the display + orange "blip" on keyboard | build a progression mapped across the keys |
| Chord "thought bubble" | read-out | Auto-analyzes & names the current chord (e.g. "D min") | confirm what a slot actually spells |
| Voice slots 1–8 (note row) | note name or OFF | The up-to-8 notes of the selected chord. Edit by dragging the text value, clicking/double-clicking piano keys (green = in chord) | hand-craft or tweak a voicing |
| Velocity row (per voice) | 0–200% | Scales each chord note's velocity vs. the incoming velocity | accent/duck specific voices (e.g. quieter top) |
| Lock switches (per voice, ×8) | on/off (global) | "Pedal tone" — locks a pitch/voice across ALL chords at its current value | keep a drone/common tone under every chord |
| LEARN | toggle | Chord-learn mode: play notes → assigned to current slot, auto-advances to next slot. Cmd/Ctrl-click = learn a single slot only. Alt-click = Advanced Learn (note-on only, learns simultaneous-onset chords from a MIDI roll). Shift-click = learn-with-timer (chord only committed after held 1 s) | record your own chord set quickly |
| COPY | button | Copies the current chord slot to clipboard | duplicate a voicing elsewhere |
| PASTA (paste) | button | Pastes the copied chord into the current slot | place a copied voicing |
| WTF? | button | Generates a random chord on the current slot (respects locks) | inspiration / happy accidents |
| Chord Presets browser | menu + arrows | Loads chord presets (top-right). Arrows step through last subfolder | recall factory/your progressions |
| Eye (Watch) switch | toggle | Marks "watched" slots; pairs with Menu→Remove→Unwatched Chords to keep only played slots | prune a big imported set to what you used |

#### Chord MENU
| item | what it does |
|---|---|
| Mute Output (MIDI only) | same as speaker mute |
| **Sort** ▶ | Re-orders all slots by: Low (Absolute) / Low (Pitch Class) / High Note / Number of Notes / Hindemith (Chromatic) / Hindemith (Circle of Fifths) — new playing layouts |
| **Remove** ▶ | Erase slots by rule: Duplicates / One-Note / Two-Note / Three-Note / Unwatched Chords |
| Make Major chords Minor | Hindemith-analyze; lower the 3rd of every major chord (+3 instead of +4) |
| Make Minor chords Major | raise the 3rd of every minor chord (+4 instead of +3) |
| Make All Chords Suspended | turn maj/min 3rds into sus4 (+5) |
| Populate Empty Slots with Variations | (Transform) fills empty slots with transposed "inversions" of loaded chords |
| Move Chord slots to begin here | shift the slot block to start at the selected slot |
| Save Preset (Chords+Arp) / Save Chords Preset / Save Arp Preset | save full state / chords-only / arp-only |
| Import MIDI File | imports chords from a **Type 0** (single-track) MIDI file starting at the current slot; held overlaps = one chord, gaps advance the slot |

### Arpeggiator module
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Pattern selector A–L | 12 patterns | Choose/active pattern (green = has data). Alt-drag a letter to copy a whole pattern (all lanes) to another | A/B variations, song sections |
| Rate knob | 16 bars … 1/512 (per pattern) | Step length; common range 1/8–1/64, default 1/16 | overall arp speed |
| Swing | knob (Arp) | Global swing feel on the arp | groove |
| Gate (knob) | knob (Arp) | Global note-length scaling for arp output | staccato vs. legato overall |
| RETRIG | on/off | Restart playback at step 1 whenever a new MIDI note arrives | tight, re-locking arps on each chord |
| LINK LENGTHS | on/off | Force every graph lane to share one length (the Graph Pattern Length bar) | simple equal-length arps |
| CHORD (mode) | on/off | Chord-arpeggio: output all incoming notes transposed up by the lane value (inversions stacking), not one note at a time | piano-style rolled chords |
| Pattern Name | text | Name per pattern | organization |
| Clock Div | denominator (per graph) | Slows the visible graph's rate (2 = ½ speed, 4 = ¼) | polymetric lane vs. lane |
| COPY / PASTA / RAND (graph) | buttons | Copy / paste / randomize the **currently-selected graph lane** only (alt-drag pattern letter copies all lanes) | reuse or shuffle one lane |
| Graph Pattern Length | drag (per lane) | Length of the selected lane (e.g. 4-step note vs. 5-step pitch) → polymeter | evolving, non-repeating patterns |
| Arp Presets browser | menu + arrows | Load arp presets (lower-left) | recall rhythmic patterns |
| Arp Free Rate (Hz) | menu option | Switch arp clock from tempo-synced to free Hz time | un-synced / drifting arps |
| Note-prevent keyboard (1 octave) | 4 states per key | Block notes from output: black/white = pass · solid red = silence · red >  = play +1 semitone instead · red < = play −1 semitone instead | keep transposed steps in key |

#### Arp graph lanes (tabs)
| tab | range / unit | what it does |
|---|---|---|
| **Note** (note-selection) | per step: pattern shape, or chord-degree 1–8, or muted | Picks which note of the held chord plays per step. Top half = pattern shapes (up, down, up/down, down/up, up&down, down&up, fingered top, fingered bottom — extremes play once or twice as labeled); bottom = explicit "1"=lowest … "8"=8th-highest note. Drag below "1" or use the under-row buttons to mute a step. Alt-click a step = Position Reset (green ↓): arp restarts its pattern from that step |
| **Rand Sel** | per step (center = none) | Amount of random note-selection per step; bar above center = randomly select a higher chord note than assigned |
| **Octave** | ±8 octaves (center = 0) | Per-step octave transpose of the output note |
| **Pitch** | semitones (center = 0) + Pitch Enable buttons 1–7 / A–G | Per-step semitone transpose, but applied **only to enabled scale degrees** (number buttons = which chord degrees are eligible; only enabled ones turn green/transpose). Uses Cthulhu's root analysis so you can change chord flavor (e.g. maj→min) without moving the root |
| **Vel scale** | per step | Scales output velocity per step (great when the synth maps velocity→filter/amp) |
| **Gate** | ≤100% (default 100 = full) | Shortens step duration per step for rhythmic motion |
| **Late** | early/late per step | Nudges a step's trigger earlier/later — custom per-step swing |
| **Harmony** | −1 oct … +1 oct per step | Adds a 2nd note per step relative to the step's output pitch (needs a polyphonic destination) |

## Use by lens
- **Producer (create):** This is a songwriting/idea engine. Load a chord preset (or build/learn your own), play single notes to sketch progressions, then enable the Arp and try patterns A–L for instant riffs — even one held note becomes a sequence in Chord mode. Use WTF? and Populate Variations for inspiration; per-lane lengths + Clock Div for evolving, non-looping arps. Drag-and-drop the Cthulhu monster icon to export the current chord as a MIDI file, or alt-drag a pattern letter to export a 1-bar arp render.
- **Mixing (balance):** Not a mix tool, but useful for fixing/printing parts: commit Cthulhu's MIDI to the instrument track, use Gate/Late/Vel-scale lanes to add groove and dynamics, and Harmony/Octave lanes to thicken or widen a part without overdubbing. Velocity-row scaling tames an over-loud chord voice at the source.
- **Mastering (finalize):** Not applicable — MIDI generator, no audio processing.

## Notes / gotchas
- **MIDI only, no audio of substance:** the speaker is a reference sawtooth — route MIDI to a synth. Mute it once routed.
- **Routing is host-specific:** Logic 9 / legacy AU needs an IAC loopback (Cthulhu→OS X IAC→Logic In); top-bar shows "MIDI: IAC Driver …" or "IAC BUS NOT FOUND!!". Logic X: use the **MIDI-FX slot** (`Cthulhu_MFX`) — routing to the same-track instrument is automatic. Don't record-enable Cthulhu's own track in feedback-prone setups (can hang the host).
- **Order:** Chord processes before Arp.
- **MIDI import must be Type 0** (single-track). Convert Type 1 first (e.g. MIDI Squeezer).
- **MIDI CC pass-through / control:** MIDI CCs on Ch1 pass through to the destination (since 1.1). Realtime graph control via CC on **Ch2/Ch3** (Ch2 = current step of each lane CC1–7; Ch3 = every step) and chord-slot note CCs 101–108 are **disabled by default** — enable in `CthulhuConfig.txt` (located atop the Cthulhu Presets folder). Aftertouch/pitch-bend/program-change pass through (since b11b).
- **MIDI latching** (top upper-left): when on, note-offs are ignored — a chord holds until the next note/chord arrives.
- **Default chord behavior:** empty slots default to minor triads on all 128 slots (not silence). Choose "-init-" from the Chord Presets menu if you want true silence.
- **Presets:** three types/locations — Chord Presets → `/Cthulhu Presets/Chord/`, Arp Presets → `/…/Arp/`, Chord+Arp → `/…/Presets/`. All are `.fxp`. Full state auto-saves inside the host song.
- **CPU/latency:** lightweight MIDI processor; no oversampling. Arp is tempo-synced — host transport must be playing to hear it (unless Arp Free Rate Hz).

## Deep spec (Programmer only)
not reverse-engineered — capability only.
