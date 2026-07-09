# SoundToys FilterFreak — SoundToys (resonant filter / modulated filter)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 (Mac & Windows) |
| Type | Creative resonant filter — LPF/BPF/HPF/notch with deep modulation (LFO, tempo-rhythm, envelope-follower, random/sample-hold, step, ADSR) + analog-style saturation. Ships as two plug-ins: **FilterFreak** (1 filter) and **FilterFreak 2** (two filters, serial/parallel) |
| Format | VST3 / AU / AAX (not stated explicitly in manual; standard SoundToys delivery) |
| Source | manual: `SoundToys FilterFreak/SoundToys FilterFreak.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
FilterFreak is a recreation of classic analog resonant filters (Minimoog 24 dB LPF, Mu-Tron III envelope follower, Morley/wah, Sherman FilterBank-style LFO sweeps) with far more control than the hardware. At its core is a multi-mode resonant filter — Lowpass, Bandpass, Highpass, or Band-Reject/Notch — with continuously variable Frequency, Resonance (up to self-oscillation), and selectable steepness (2/4/6/8 poles = 12/24/36/48 dB per octave). The filter cutoff can be driven by one of six modulation engines selected from a menu: a wide-range **LFO** (0–100 Hz, editable custom waveshapes), tempo-locked **Rhythm** mode with a drum-machine-style pattern editor and swing/shuffle groove, an **Envelope** follower, **Random** (sample-and-hold), **Step** (triggered sample-and-hold), and a synth-style **ADSR**. A Tweak menu under every mode exposes modulation depth per parameter (Freq/Res/Level), stereo L/R offset and flip, smoothing, the Shape/Rhythm editors, and seven **Analog Style** saturation algorithms (Clean → Pump) that add genuine analog drive when pushed. FilterFreak 2 doubles the filter so you can chain or blend two filter types (e.g. LPF→HPF for a bandpass, or two filters moving in opposite directions for vocal "wah" sounds).

## Controls (every param → musical effect)

### Common controls (all modes)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Mix** | Dry ↔ Wet (0–100%) | Blend between filtered and dry signal. | Insert: dial blend (recommended — avoids send-path phase issues). Aux send/return: 100% wet, ride the return fader. |
| **Frequency** | 20 Hz – 20 kHz | Cutoff/center frequency of the filter; the spectral region the filter acts on. With LPF, sets where highs start rolling off. The single most important tone control. | Park it for static filtering; sweep manually/MIDI/automation for the "cool" moves; or let a mod engine drive it automatically. |
| **Resonance** | Min ↔ Max | Boosts harmonics near the cutoff — the squeak/wheeze/squelch. At max, drives the filter into self-oscillation (generates a tone). | Add bite and that "picked-out" resonant peak; crank for screech/oscillation. ⚠ Extreme settings make VERY high levels — turn Output down first. |
| **Mod** | Min ↔ Max | Depth/amount of modulation applied to the filter frequency (how far the cutoff sweeps). Character of the sweep depends on the selected mod engine. | Set sweep intensity — subtle wobble (low) to full sweeping auto-wah (high). At 0, no front-panel mod sweep. |
| **Shape** (filter type) | LPF / BPF / HPF / BRF | Selects filter character. **LPF** removes highs above cutoff; **HPF** removes lows below; **BPF** passes a band around cutoff (Resonance sets band width — higher Res = narrower); **BRF** notch rejects a narrow band, passes the rest. Drawn live in the Filter Response Display. | LPF: dark/synth sweeps. HPF: thin out / remove bass. BPF: telephone/wah/radio. BRF: surgically notch a frequency, dynamic phasing. |
| **Poles** | 2 / 4 / 6 / 8 | Filter slope/steepness. 2 = 12 dB/oct (gentle, smooth, subtle), 4 = 24 dB/oct (classic Moog), 6 = 36 dB/oct, 8 = 48 dB/oct (steep, extreme, effect-laden). | Low poles = musical/subtle. High poles = aggressive, pronounced filtering. 4 for the classic synth sweep. |
| **Input** | −24 to +24 dB | Level into FilterFreak. LED: yellow = 6 dB below clip, red = max/clipping. | Drive the Analog Style saturation harder, or tame the input. Default ≈ unity. |
| **Output** | −24 to +24 dB | Level out of FilterFreak. LED metering as above. | Compensate gain after heavy resonance/saturation; tame self-oscillation peaks. Default ≈ unity. |
| **Tweak** | button | Slides out the hidden Tweak Menu (mod-depth knobs, stereo, smoothing, editors, Analog Style) — layout varies per mode. | Access deep per-parameter modulation, stereo width, saturation styles. |
| **Modulation mode** | menu (under Rate/center button): LFO · Rhythm · Envelope · Random · Step · ADSR | Chooses the engine that drives the filter cutoff. Front-panel center controls change to match. | Pick the movement type — see mode rows below. |

### Tweak Menu — shared first row (present in every mode)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Freq Mod** | −10.00 → +10.00 oct (center 12 o'clock = 0 = off) | Modulation depth on filter **frequency**, in octaves. +1 oct = sweep up to one octave above the Frequency knob; negative = sweep downward. At 0, frequency is NOT modulated regardless of front-panel Mod knob. Editable LCD value. | Precisely set sweep range; negative for inverted/downward sweeps. |
| **Res Mod** | bipolar dB (default 0) | Modulates the **resonance** peak strength over the mod cycle. Positive increases, negative decreases. Big effect at high base Resonance. Editable LCD value. | Make the resonant peak pulse/breathe with the modulation; add liveliness to sweeps. |
| **Level Mod** | bipolar dB (default 0) | Works with Res Mod to set overall **applied modulation level** (output level movement). Editable LCD value. | Add tremolo-like level movement synced to the filter mod. |
| **L/R Offset** | 0 → ±2 oct (center = 0) | Static frequency offset between L and R channels. + raises right channel relative to left; − lowers it. **Mono-to-stereo inserts only.** | Create stereo width/separation from a mono source. |
| **L/R Mode** | Normal / Flipped | Normal = same modulation both channels. Flipped = L and R modulation inverted → swirling auto-pan. **Mono-to-stereo inserts only.** | Wide swirling stereo modulation. |
| **Analog Style** | Clean · Fat · Squash · Dirt · Crunch · Shred · Pump (7) | Saturation/distortion character applied to the signal. **Clean** = max undistorted range, hard clip. **Fat** = smooth low-freq distortion. **Squash** = Fat but more compressed. **Dirt** = smooth broadband saturation. **Crunch** = exaggerated high-end clipping. **Shred** = lots of asymmetrical clipping. **Pump** = extreme pumping compression. Drive harder via Input to hear more. | Choose how the filter "breaks up" when pushed — from clean to aggressive analog grit. |
| **Shape Editor** + **Smoothing** + **Smoothing Mode** + **Shape Preset** | see below | Custom LFO/modulation waveshape editing (present in LFO/Rhythm/Envelope/Random/Step modes). | Design bespoke sweep contours. |

### Shape editing (LFO/Rhythm and most mod modes)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Shape (preset menu)** | Sine, Triangle, Square, … + Custom + saved shapes | Selects the modulation waveshape that drives the filter. | Sine = smooth wobble; Square = on/off gating; Triangle = even sweep; custom for anything. |
| **Shape Editor** | draw-able curve | Click to add points, drag to move, Option-click to remove. Build arbitrary LFO contours; save as a named preset (floppy icon) into the Shape menu. | Hand-draw a unique filter sweep contour. |
| **Smoothing** | None ↔ Max | Rounds the edges between editor points. 0 = stair-step/abrupt jumps; max = fully smooth. | Soften abrupt waveshape transitions; or keep stepped for rhythmic chops. |
| **Smoothing Mode** | Lin / Sin / Exp / Sym / Rev | Curve type used to connect points. **Lin** = straight lines. **Sin** = sinusoidal/very smooth. **Exp** = scooped, rises quickly (ADSR-like). **Sym** = even symmetrical curve. **Rev** = reverse-scooped (rises slowly, falls quickly). | Shape the feel of each transition (snappy vs. gliding). |

### LFO mode
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Rate** | 0 (≈0.1) Hz – 100 Hz | Speed of the LFO sweep. 1 Hz = one cycle/sec. Wider than typical (goes to 100 Hz for ring-mod/clangy sidebands; classic auto-wah lives at low Hz). | Auto-wah and tremolo-filter sweeps; push high for warped ring-mod textures. |
| **Shape** | preset/custom (see Shape editing) | LFO waveform. | Choose/design the sweep contour. |

### Rhythm mode (tempo-synced LFO + pattern editor)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Tap Tempo / BPM** | tap button + BPM field + MIDI-sync toggle | Sets the tempo for sync. Toggle locks to host/project MIDI tempo. | Lock filter movement to the song; or tap a feel for un-clicked tracks. |
| **Rhythm** | menu: 1/1 … 1/16 note (etc.) + Custom | Rhythmic transition rate — how often the pattern advances (e.g. 1/2 note = step every half note). Custom = uses the Rhythm Editor pattern instead. | Set the grid of the auto-wah/filter rhythm. |
| **Shape** | preset/custom | LFO waveshape triggered per rhythm event (one full cycle per event). | Same shape control as LFO mode. |
| **Groove** | Shuffle ↔ 0 (12 o'clock) ↔ Swing | Imparts feel. CW = increasing **Swing**; CCW = increasing **Shuffle**; center = straight. Shifts even beats toward a triplet feel; relative to current Rhythm. **Applies in all modes**, any rate/rhythm. | Humanize/groove the filter pattern; lock to the track's swing. |
| **Rhythm Editor** | pattern grid | Drum-machine-style editor: add/remove pattern sections (one LFO Shape cycle per event). **Num Bars / Beats per Bar / Bar / Grid** set length and resolution (Grid sets the length of each added shape, e.g. 1/8, 1/16, 1/4). Save/recall via **Rhythm Preset** (interchangeable with other SoundToys plug-ins). | Program complex moving filter patterns that follow the song. |

### Envelope mode (envelope follower)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Threshold** | comp-style threshold | Level the input must exceed before the follower starts tracking and modulating the cutoff. Louder/farther above = more sweep; below = no modulation. | Set against program dynamics — high = only loud peaks move the filter; too low = overmodulation. |
| **Gain** | sensitivity (low ↔ high) | Like a comp ratio/sensitivity; boosts signal exceeding threshold. High = follower acts gate-like (on above / off below); low = touch-sensitive and dynamic. | Useful with high threshold or slow attack; dial responsiveness. |
| **Attack** | fast ↔ slow | How fast the follower reacts to rising level. Fast = snappy, staccato filtering; slow = hazy/lazy onset. | Snappy funk auto-wah (fast) vs. smooth swells (slow). |
| **Release** | fast ↔ slow | How fast it reacts as level falls. Fast = dynamic; slow = smooth decay. | Match to the source's decay; smoother trails with slow. |
| *(plus shared first-row Tweak controls)* | — | Freq/Res/Level Mod, L/R, Analog Style as above. | — |

### Random mode (tempo-synced sample-and-hold)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Rhythm** | note-value menu | Rate at which a new random filter value is jumped to (sample-and-hold synced to tempo). No pattern editor (values assigned randomly per rhythm). | Sci-fi bleeping/chirping, random stepped filter movement on tempo. |
| **Smoothing** | None ↔ Max | Glide between random values (stepped vs. gliding). | Glitchy steps vs. smooth random sweeps. |
| *(plus shared first-row Tweak controls)* | — | as above | — |

### Step mode (triggered sample-and-hold)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Trigger** | threshold knob (LED ring) + Manual Trigger button + MIDI | New random filter value created on each **trigger** (audio crossing threshold, manual button, or MIDI note). Set threshold to the input level you want to fire on. Threshold all the way up = audio triggering off (manual/MIDI only). Note: audio must be below threshold for a Manual Trigger to fire. | Per-hit random filter jumps on drums/percussion; rhythmic creative randomization tied to performance. |
| **Smoothing** | None ↔ Max | Glide between triggered values. | Snap (stepped) vs. glide between hits. |
| *(plus shared first-row Tweak controls)* | — | as above | — |

### ADSR mode (synth envelope generator)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Trigger** | button + Threshold + MIDI | Fires the ADSR envelope: Manual Trigger button, MIDI note, or input exceeding Threshold. | Triggered filter envelopes on hits/notes. |
| **A — Attack** | fast ↔ slow | Time for the envelope to rise to max after trigger. Low = fast; high = longer/slower rise. | Pluck/sweep onset speed. |
| **D — Decay** | fast ↔ slow | Time to fall from max down to the Sustain level. | Length of the initial drop after attack. |
| **S — Sustain** | 0 – 100% | Level the envelope holds at while the trigger is held / input stays above threshold. | Set the steady-state filter position during the note. |
| **R — Release** | fast ↔ slow | Time to fall from Sustain back to 0 after the trigger releases / input drops below threshold. | Tail length of the filter envelope. |
| *(plus shared first-row Tweak controls)* | — | as above (no Shape editor — envelope is the shape) | — |

### FilterFreak 2 only (dual filter)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Two full filter sections (1 & 2)** | each has Freq/Res/Gain/Shape/Poles | Two independent filters, each identical to FilterFreak 1's. Combine types: LPF+HPF = bandpass, LPF+notch, etc. Mono-to-stereo splits Filter 1 → left, Filter 2 → right. | Complex multi-filter tones; stereo split filtering; vocal-formant "wah." |
| **Parallel / Serial** | toggle | **Parallel** = input hits both filters separately, outputs mixed (no interaction). **Serial** = input → Filter 1 → Filter 2 (Filter 1's output reprocessed; can null the signal entirely with the right types/poles). | Parallel for blended dual filtering; Serial for cascaded/extreme sculpting. ⚠ Serial + high Resonance = very loud peaks. |
| **Link** | switch | Links Frequency, Resonance, and Gain of both filters — moving one moves the other equally/same direction. (Note: a control already at max won't move until the linked one has headroom.) | Sweep both filters together while keeping their offset/type difference. |
| **Per-filter Tweak (Mod 1 / Mod 2)** | Freq/Res/Level Mod ×2 | Same Tweak controls but doubled — independent modulation depth (and direction) per filter from the single shared mod source. Set Filter 1 to sweep up while Filter 2 sweeps down. | Opposing-direction sweeps for vocal-like "wah"; richer dual movement. |

## Use by lens
- **Producer (create):** The headline creative-FX filter. Rhythm mode + custom Shape/Rhythm editor = tempo-locked auto-wah and rhythmic filter gates that lock to the groove (use Groove for swing). LFO mode for classic synth/Sherman sweeps; push Rate to 100 Hz for ring-mod clang. Envelope mode for funky touch-sensitive guitar/clav/synth wah (Mu-Tron III vibe). Step/Random on drums for per-hit sci-fi filter randomization. Crank Resonance + Analog Style (Shred/Crunch) to turn a flat synth or loop into a screaming acid line; FilterFreak 2 serial LPF→HPF for vocal-formant movement.
- **Mixing (balance):** Use as a tone/movement tool — static LPF/HPF to carve a sound's range, or BRF/notch to dynamically dodge a problem frequency. Envelope mode adds subtle program-dependent motion (filter opens on transients) to liven static parts. Mono-to-stereo L/R Offset + Flipped widens a mono synth/guitar. Keep Resonance modest and Analog Style on Clean/Fat for musical, non-destructive filtering. Run as an insert (manual warns send use can cause phase cancellation) and use Mix to parallel-blend.
- **Mastering (finalize):** Not a mastering tool — it's a creative resonant filter with audible saturation and (at high Res) self-oscillation; no linear-phase/transparent mode. Avoid on the 2-bus except as a deliberate effect on a stem/parallel return.

## Notes / gotchas
- **Six modulation engines, one at a time** — selected from the menu under the center button; the front-panel center section and Tweak layout change per mode.
- **Self-oscillation & loud peaks:** max Resonance generates a tone; Serial mode (FF2) + high Res can produce speaker-damaging peaks. Pull Output down before experimenting. The Input/Output LEDs (yellow = −6 dB, red = clip) are your guide.
- **Analog Style is real saturation**, not cosmetic — drive Input to hear it; Clean stays hard-clip-clean, Pump pumps hard.
- **Stereo controls (L/R Offset, L/R Mode) only do anything on mono-to-stereo instances.**
- **Custom Shapes and Rhythm patterns are savable** and Rhythm patterns are interchangeable with other SoundToys plug-ins (EchoBoy, Tremolator, PanMan, etc.).
- **Two plug-ins installed:** "FilterFreak" (single filter) and "FilterFreak 2" (dual filter, serial/parallel + Link). Same engine.
- **MIDI:** tempo sync (Rhythm/Random), and note-triggering (Step/ADSR) supported.
- Filter modeled on Minimoog-style 24 dB LPF; 4-pole is the classic-Moog setting.

## Deep spec (Programmer only)
Not reverse-engineered — capability only.
