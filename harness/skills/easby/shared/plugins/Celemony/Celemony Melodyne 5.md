# Celemony Melodyne 5 — Celemony (note-based audio editor / pitch & time correction)

| | |
|---|---|
| Vendor / ver | Celemony · Melodyne 5 studio (manual rev 09/21/2023, covers 5.0–5.3.1) |
| Type | Note-based audio editor — pitch/timing/formant/dynamics correction, polyphonic note editing, spectral sound design, tempo/quantize. Editions: essential < assistant < editor < studio (this card = studio, the fullest) |
| Format | VST3, AU, AAX + stand-alone. Also runs as ARA inside supporting DAWs. Auth: iLok (USB dongle) or computer-based activation |
| Source | manual: `Celemony/Celemony Melodyne 5.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Melodyne analyses audio and shows each note as a **blob** you can grab and edit — pitch, timing, length, vibrato, drift, volume, formants, sibilants, attack and even the harmonic spectrum, note by note. Unlike a pitch-corrector that works blindly on a stream, Melodyne first *understands* the music (notes, scales, chords, tempo), which is why its edits stay musical and usually inaudible. It handles monophonic (vocals, lead lines), percussive (drums) and — uniquely — **polyphonic** material (piano, guitar, full mixes). Work is non-destructive and resolution-independent. The thing that distinguishes it from every "transparent" pitch tool: DNA Direct Note Access to individual notes inside chords, plus a **Sound Editor** that re-synthesises the overtone structure for additive-synth-style timbre design.

## Controls (every param → musical effect)

### Algorithm (set BEFORE editing — switching it discards edits on that track)
| control | range / options | what it does | when to reach for it |
|---|---|---|---|
| Algorithm | Melodic · Percussive · Percussive Pitched · Polyphonic · Universal | Detection engine. Melodic = monophonic pitched (vocals/lead); Percussive = unpitched drums (one horizontal line); Percussive Pitched = pitched drums/perc; Polyphonic = chords/piano/guitar/mixes; Universal = anything, all-rounder | Let auto-detect choose, then verify. Wrong algo = wrong note display |
| Sibilant Detection / Handling | on / off (checkbox) | Treats sibilants & breath noise ("s","sh","z","t","k", inhales) separately from pitched body so pitch/time edits stay natural | Melodic: default ON (ideal for vocals). Turn off on bass/instruments if attack is mis-flagged |
| Robust Pitch Curve | on / off | Forces a simpler, more stable pitch curve per note (Melodic & Percussive Pitched only) | Mono sources with "technical polyphony" / room resonance / FM synths / throaty male rock vox causing artifacts |
| Separate Audio | Auto / Now button | Whether Melodyne recalcs cache immediately (Auto, smooth preview, occasional pauses) or only on Now/exit (uninterrupted workflow) | Auto for previewing detection edits; off if pauses break your flow |
| Save/Load/Remove Assignment Data | menu (cog) | Writes note+tempo detection into the audio file so it reloads in any project/ARA DAW | Reuse a perfected detection across sessions |

### Algorithm Inspector — Preview & algorithm parameters
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Transient (slider) | left↔right (Universal default = middle; Percussive default = full right) | Sharper/crisper transients (right) vs softer (left) | Tune attack clarity per material |
| Formant Correction Up | 0–100% | Degree of automatic formant compensation for *upward* transpositions | 100% = no "Mickey Mouse" on vocals; lower for parallel formants (e.g. guitar charm) |
| Formant Correction Down | 0–100% | Same, for *downward* transpositions | Independent control of down-shifts |
| F (Formant) Character | slider | Re-weights shifted formants across the frequency range | Dial timbre of shifted formants |
| Formant Center | slider (Universal & Percussive only; greyed for Melodic/Poly/Perc-Pitched) | Sets the formant reference when blobs aren't pitch-sorted | Rarely; sound-design on Universal/Percussive |

### Macros (operate on selected notes, or all notes if none selected)
| macro | params (range) | what it does | when to reach for it |
|---|---|---|---|
| **Correct Pitch** | Pitch Center 0–100% · Pitch Drift 0–100% · "Snap to chord scale" (chk) · "Include notes edited manually" (chk) | Moves notes toward nearest semitone (Center) and reins in slow drift within notes (Drift). 100% = fully in tune | One-shot intonation fix on a take/track |
| **Quantize Time** | Groove Reference: 1/4,1/4T,1/8,1/8T,1/16,1/16T,1/32,1/32T,Auto · Intensity 0–100% · "Include notes fine-tuned manually" (chk) | Moves notes toward the intended beat / chosen grid. Auto = Melodyne's musical detection rather than rigid grid | Tighten timing globally; Auto is more musical than DAW quantize |
| **Note Leveling** | "Make quiet notes louder" 0–100% · "Make loud notes quieter" 0–100% | Smooths note-to-note volume disparities for consistency | Even out a performance; great pre-compressor stage |

### Edit-menu commands (selection-based, independent of Undo)
| command | what it does |
|---|---|
| Restore Original / Reset Individual Edits → Pitch · Formants · Amplitude · Time | Nullify a specific edit type on selected notes (e.g. reset pitch but keep timing). "Undo All Changes" = all types on selection; "...to Entire File" = whole file |
| Add Random Deviations → Pitch / Timing: Subtle · Moderate · Drastic | Randomly varies pitch or timing of selection — humanise/de-double for choir/unison thickening (repeatable) |
| Quantization Macros · Tempo · Chords and Keys · Select Special | Macro/tempo/harmony access + advanced selection |

### Editing tools (toolbar; F-key shortcuts; press F-key repeatedly to cycle sub-tools)
| tool (shortcut) | edits | unit / detail | notes |
|---|---|---|---|
| **Main Tool** (F1) | pitch (drag ↕), timing (drag ↔), length (drag blob edge), note separation (drag/dbl-click upper edge) | semitone steps (Alt = cents/free); time snaps to grid (Alt = free) | Context-sensitive all-in-one; dbl-click middle = snap pitch to grid (Alt = snap to chord, keep offset). Dbl-click above blob = split |
| **Pitch Tool** (F2) | pitch center | drag ↕; Note/toolbar field: absolute (C3) or relative (+2,-1); cents box | Snap modes: No/Chromatic/Key/Chord (Alt = free). Dbl-click = snap in tune. Rear of note = drag pitch **transition** steeper/shallower. Cmd-drag = hear whole chord |
| ↳ Pitch Modulation (F2×2) | vibrato / intentional pitch movement | % (100=original, 0=flat, −100=inverted) | Dbl-click = restore original/none toggle |
| ↳ Pitch Drift (F2×3) | slow unintentional pitch drift | % (100/0/−100) | Eliminate both mod+drift = flat monotone (effect) |
| **Formant Tool** (F3) | formant shift (timbre) | cents (100 ct = 1 semitone); a few ct → several thousand | Beam shows shift. Dbl-click = restore. End of note = **Formant Transitions** tool (drag = transition speed) |
| **Amplitude Tool** (F4) | per-note volume | dB (Alt = finer); gearing follows vertical zoom | End of note = **Amplitude Transitions** (speed). Dbl-click = **mute** (toggle); Note Inspector "Note Off" button |
| **Fade Tool** (F4×2) | fade-in (note start) / fade-out (note end) | length tied to position-in-note (not ms); drag length ↔, curve ↕ | Dbl-click 1st half = fade-in, 2nd half = fade-out. Auto-inserts hard separation. Enables musical crossfades w/ Time Tool overlap |
| **Sibilant Balance Tool** (F4×3) | balance of sibilant/noise vs pitched body | % (+ = quieter pitched / sibilants up; − = sibilants down). Dbl-click = −100% (mute sibilant) | Melodic & Perc-Pitched only. Precision de-essing: −10 to −40% lead, ~−80% backing/doubles |
| **Timing Tool** (F5) | horizontal position & length | drag center=move, edge=stretch/compress (Alt = ignore grid) | Adjacent connected notes flex too (soft sep). Dbl-click = quantize to "intended" note (Show Intended Notes) |
| ↳ Time Handle Tool (F5×2) | internal time path | dbl-click in note adds a handle; drag ↕ = advance/retard that phase | Multiple handles per note; reshape phrasing without changing overall length |
| ↳ Attack Speed Tool (F5×3) | attack hardness | % (0 = neutral; up = harder/faster attack, down = softer) | No function on Universal algo (greyed). Dbl-click = neutral |
| **Note Separation Tool** | insert/move/remove separations | dbl-click = split / reunite | Show Note Separations to edit |
| ↳ Separation Type Tool | soft ↔ hard separation | line (soft, notes connected/flex) vs bracket (hard, independent) | Hard sep kills pitch/amp/formant transitions between notes |

### Sound Editor (Options → Show Sound Editor; spectral / additive-synth timbre design)
Works on the **mean spectrum** (averaged overtone fingerprint of the track). Tabs: **Lo · Harmonics · Hi · EQ · Synth** (Cmd-click tab = open several side by side).

| control / area | range / detail | what it does |
|---|---|---|
| **Emphasis** (slider) | ±200% (Alt = 1%/step) | Exaggerates (right) or smooths toward mean (left) each note's spectral peculiarities — helps a source cut through or blend, *without* changing volume |
| **Dynamics** (slider) | left↔right | Right = quiet parts quieter (staccato feel/faster decay); left = louder/longer decay (legato). Internal note dynamics |
| **Bypass** | on/off | A/B the Sound Editor against the unedited track |
| **Gain** | knob | Manual output trim (Melodyne auto-compensates level; use if clipping or too quiet) |
| menu: Reset All / Copy Settings / Paste Settings | — | Reset all areas; copy/paste relative spectral edits between tracks (not the mean spectrum itself) |
| **Harmonics / Lo / Hi** bars | per-harmonic level; bar "<" = sub-fundamental, "1"=fundamental, "2,3,4…"=overtones | Additive-style overtone shaping (Lo/Hi = lower/upper register halves, morph in crossover). Drag bar (Alt finer); range-drag; dbl-click bar = all octaves; Cmd-click = restore |
| Harmonics/Lo/Hi macros | **Brilliance** (high-harmonics up/down) · **Contour** (peak/trough exaggeration↔flatten/invert) · **Odd/Even** (right fades odd→reinforce octaves; left fades even→hollow clarinet) · **Comb** (thins spectrum; side buttons slide comb) | Quick timbre macros over the harmonic bars; Cmd-click macro = neutral |
| Harmonics menu | Reset/Copy/Paste/Clear/Shuffle Spectrum · Show All Harmonics | Clear = silence (build timbre from scratch); Shuffle = random |
| **EQ** working area | graphic EQ, fixed bands **one semitone wide**, labelled by note name | Conventional fixed-frequency EQ (vs harmonic-following bars). Same drag/select gestures; "<" band = energy below detected fundamentals |
| EQ macros | **Brilliance** · **Contour** · **Tonality** (right fades out-of-scale notes; left fades in-scale) · **Comb** (removes notes by circle-of-fifths distance from tonic; side buttons pick tonic) | Macro shaping for the EQ |
| **Formants** (in EQ/Harmonics/Lo/Hi, dark zone at base) | drag horizontally | Shift formants of all (or selected) bands/bars; Cmd-click = restore. Works with Formant Tool (note-based offset) + Track Inspector Formants knob (track-wide) |
| **Synth: Spectrum / Formant / Amplitude envelopes** | each: starting level · attack time · sustain level · sustain time · decay time · final level; ruler = length in sec; checkbox per env; Cmd-click = neutral | Per-note envelopes (triggered by note starts, not MIDI) over spectral-edit intensity, formant glide, and amplitude — e.g. lengthen piano attack, glide formants |
| **Resynthesize: Magnitudes** | slider | Right = reduces per-note amplitude changes; at full right no timbral movement + narrows harmonic bands so non-harmonic content disappears → synthetic |
| **Resynthesize: Phases** | slider | Right = aligns partial phases → affects transients, more synthetic. Both at max = static-synth waveform |

## Use by lens
- **Producer (create):** Comp & re-pitch to build vocal harmonies from one take (Cmd-drag to audition chords); change melody/chords by dragging blobs; quantize/transpose loops & sampled instruments (even polyphonic); thicken doubles with Add Random Deviations + Sibilant Balance ~−80%; radical sound design in the Sound Editor (Clear/Shuffle Spectrum, Resynthesis to synth-ify, formant gender-bends). Audio-to-MIDI export for re-instrumenting.
- **Mixing (balance):** Surgical, precision **de-essing** with the Sibilant Balance Tool (−10 to −40%) — beats a de-esser because it touches only the noise, not the whole signal; tame double-track sibilant flutter at ~−80%; even note levels with Note Leveling (and as a pre-compressor optimiser); fix intonation/timing transparently; per-note volume rides (Amplitude Tool); spectral problem-solving with the note-following Harmonics bars (e.g. brighten dull low piano notes via Lo without touching Hi).
- **Mastering (finalize):** Not a master-bus tool, but on stems/mixes it can correct an off note in a bounced mix (Polyphonic), tame a harsh resonance (EQ semitone bands), nudge timing, or even out dynamics before the chain. Use sparingly; place Gain/Bypass to verify null.

## Notes / gotchas
- **Pick the algorithm first.** Changing algorithm after editing **discards all edits** on that track. Verify the auto-choice in **Note Assignment Mode** before working (especially polyphonic, where overtones can be mis-detected as separate notes).
- **Soft vs hard separations** govern transitions: pitch, amplitude, and formant *transitions* exist only across **soft** separations. Switch to hard (Separation Type Tool / bracket) to fully isolate two notes.
- **Reset commands operate independently of Undo** — `Edit > Reset Individual Edits > {Pitch|Formants|Amplitude|Time}` un-does a category without rewinding history.
- **Cents:** 100 cents = 1 semitone (formant shifts can run to thousands of cents for drastic timbre change).
- **Sibilant Handling defaults:** ON for Melodic, OFF for Percussive Pitched, greyed for others. Old (pre-5) projects load with it OFF to preserve prior sound — enable to gain v5 vocal tools.
- **Sound Editor distinctions:** Harmonics/Lo/Hi bars follow each note's fundamental (additive-synth-like) → harmonic #N of *every* note; the EQ acts on *fixed* frequency bands. Both can run simultaneously. Mis-detected notes route energy to the wrong band/the "<" band — fix detection first.
- **Robust Pitch Curve** & **Separate Audio (Auto)** are greyed where not applicable (Poly/Universal/Percussive already have robust curves by default).
- **Multitrack (studio):** see/edit notes from many tracks in one window; Cmd-click Edit buttons to add tracks; "Spread Unison Tracks"; copy notes between tracks/documents with track-mapping rules; **Auto Stretch** switch decides whether pasted notes adopt destination tempo.
- **Tempo/Assign Tempo Mode**, **Chord Track / Key Track / Scale Detective**, and **Stretch Tuning / custom scales** exist (studio) for harmonic & rhythmic analysis and editing — beyond the core blob tools.
- **Editions differ by feature set, not engine** — projects open across editions at the same version; fewer tools available in smaller editions but sound is preserved.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
