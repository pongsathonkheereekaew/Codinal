# XLN Addictive Keys — XLN Audio (sampled keyboard instrument)

| | |
|---|---|
| Vendor / ver | XLN Audio · (Addictive Keys, ver. unstated in manual) |
| Type | Virtual keyboard instrument (multi-mic sampled piano/EP) + built-in studio FX |
| Format | Standalone app + plug-in for all major DAW hosts (Cubase, Pro Tools, Logic; VST/AU/AAX-class — exact formats not enumerated in manual) |
| Source | manual: `XLN Audio/XLN Addictive Keys/XLN Addictive Keys.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Addictive Keys is a sample-based virtual keyboard instrument with a built-in studio effects rack, aimed at songwriters/producers who want a great keyboard sound fast. Each instrument (e.g. Studio Grand = Steinway D, Modern Upright = Yamaha U3, Electric Grand = CP-80, Mark One = Rhodes Mk.1) is sampled from multiple microphone perspectives (typically 6–7) plus DI/amped sources on the electrics. Its defining feature is **mic blending**: you load up to three Instrument Channels, each with a different mic/DI perspective, and mix/pan them to sculpt the space and tone. On top sits a per-channel + master channel strip (noise, compressor+distortion, EQ, and modulation FX) and two shared Delerb (delay→reverb) sends. Workflow is preset-first via **ExploreMaps** (curated preset banks with audio previews and 4 Macro knobs), with a deep Edit page for full sound design (pitch/filter/volume envelopes, X-mod, tuning/temperament). The "Memo" feature records MIDI sketches instantly with the preset baked in.

## Controls (every param → musical effect)

### Navigation / pages
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Gallery page | — | Browse installed/available instruments; arrows = prev/next instrument; thumbnails = that instrument's ExploreMaps; [View] shows all maps for all instruments | Pick the instrument |
| Explore page | — | Loads an ExploreMap: a bank of presets w/ audio previews + (on some maps) 4 Macro knobs | Fast preset auditioning, light tweaking |
| Macro Controls (Explore) | 4 knobs (e.g. Tone, Soft/Hard, Timbre, FX) | Each mapped to one or more Edit params for quick tonal shaping without opening Edit | Dial a preset to taste in seconds |
| Preset Preview / Memo Preview | play button | Audition a preset/memo via its stored MIDI without playing | Hear before committing |
| Edit page | — | Full sound-design surface (see below) | Deep editing |

### Edit-page interaction conventions
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| X-mod knob | small knob beside a param | Sets the **range** that param is modulated by your live MIDI source (mod wheel / aftertouch / chosen CC). Params marked "X-modable" | Expressive real-time control |
| Shift+drag | — | Fine/high-resolution control adjustment | Precise values |
| Scroll wheel | — | Adjust most controls by hovering + scrolling | Fast edits |
| Instant On | — | Touching any control in a darkened (off) section re-activates that section | — |
| Ctrl/Cmd+click | — | Reset a control to default | Undo a tweak |

### Instrument Settings (per instrument; some params instrument-dependent)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Instrument selector | dropdown | Switch the loaded instrument | — |
| Pedals — Softness | (amount) | How much softer the tone gets when soft pedal (Una Corda) is pressed | Una corda realism |
| Pedals — Pedal Noise | −inf … +10 dB | Volume of mechanical pedal noise (0 = as recorded) | Add/remove mechanical realism |
| Pedals — Sustain Body | Off / 0 … +10 dB | Amount of sympathetic resonance while sustain pedal held (0 = natural; more = "richer") | Lush, resonant sustains |
| Pedals — Sustain Noise | Off / 0 … +10 dB | Amount of string resonance/noise on all strings under sustain (0 = natural) | Natural string noise |
| Vel > Sample | slider (range) | Filters out the lowest and/or highest velocity sample layers while keeping dynamic range (volume still tracks velocity) | Tame harsh top layers or remove pp samples |

### Sample Playback — Pitch tab
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Octave | +1 / 0 / −1 | Transpose whole instrument via MIDI by an octave | Range shifting |
| Tune FX — Dissonance | amount | Random per-key detuning (Session Settings graph shows the key-by-key result) | Vintage/out-of-tune character |
| Tune FX — Sample Shift | semitones | Shifts sample pitch while compensating MIDI transpose oppositely → raises/lowers overtone content | Brighter/darker timbre w/o changing pitch |
| Vibrato — Rate | 0 – 24 Hz | Vibrato speed | Pitch wobble |
| Vibrato — Depth | 0 – 100 % (X-modable) | Vibrato amount | Expressive vibrato on mod wheel |
| Pitch Envelope — Enable | on/off | Turns on pitch envelope | — |
| Pitch Env — Pitch Start | ±24 semitones | Starting pitch offset | Pitch scoops/dives |
| Pitch Env — Hold Time | 0 – 500 ms | Hold before release | — |
| Pitch Env — Release Time | 0 – 10 s | Glide back to pitch | — |
| Pitch Env — Vel | slider | Velocity influence over the pitch envelope | Dynamic pitch FX |

### Sample Playback — Filter tab
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Enable | on/off | Turns the whole filter section on/off | — |
| Type | LP 12 / LP 24 / HP 12 / BP 12 dB | Filter shape/slope | Tone shaping |
| Cutoff | 16 Hz – 16744 Hz (X-modable) | Filter cutoff frequency | Darken/brighten, wah-style on mod |
| Resonance | 0 – 100 % | Emphasis at cutoff | Squelch/character |
| Kbd | ± (keytrack) | Cutoff tracks MIDI note (high note→high cutoff); negative = inverse | Consistent brightness across range |
| Filter Env — Enable | on/off | Turns on filter envelope | — |
| Filter Env — Envelope Point (Cutoff) | 0 – 100 % | Envelope target depth | — |
| Filter Env — Attack | 0 – 7 s | Filter env attack | — |
| Filter Env — Sustain 1 Time | 0 – 7 s | Stage time | — |
| Filter Env — Sustain 2 Time | 0 – 7 s | Stage time | — |
| Filter Env — Release | 0 – 15 s | Filter env release | — |
| Filter Env — Vel | slider | Velocity influence over filter envelope | Dynamic filter motion |

### Sample Playback — Volume tab
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Vel > Vol | knob | How much velocity affects volume | Compress/expand dynamic response |
| Kbd | ± (keytrack) | Volume tracks MIDI note (high note→louder); decrease for inverse | Balance bass vs treble |
| Volume Env — Enable | on/off | When off, plays "as recorded" using release samples if available | Toggle natural vs shaped decay |
| Volume Env — Vel | slider | Velocity influence over volume envelope | — |
| Volume Env — Envelope Point Amplitude | −inf … 0 dB | Sustain level | — |
| Volume Env — Attack | 0 – 7 s | Volume attack (soften the strike) | Pads/swells |
| Volume Env — Decay | 0 – 7 s | Volume decay | — |
| Volume Env — Sustain 2 | 0 – 7 s | Stage time | — |
| Volume Env — Release | 0 – 15 s | Release (only when Release Samples off) | Shorten/lengthen tails |
| Volume Env — Release Samples | on/off | Use recorded release samples | Realistic key-off |

### Channel Strip (each of 3 Instrument Channels + Master; each module has Enable toggle)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Input | dropdown | Selected mic/DI perspective for this channel | Choose the "sound" of the channel |
| **Noise** — Type | Neumann U67 / Jupiter 8 / "Burr" rack distortion / Big Muff / Vinyl / Tape 7.5 ips / Tape 15 ips (7 types) | Adds modeled analog noise (pre-FX on instrument channels, post on master) | Lo-fi, analog grit, glue |
| Noise — Decay | 0 – 24 s | How long the noise rings | — |
| Noise — Level | −78 … −30 dB | Noise amount | Subtle vs heavy |
| **Compressor** — Enable | on/off | — | — |
| Comp — Threshold | 0 … −48 dB | Level where compression starts (has AutoGain to keep levels in check) | Even out dynamics |
| Comp — Ratio | 1:1 – 8:1 | Compression amount | Gentle→firm |
| Comp — Attack | 1 – 500 ms | How fast it clamps | Preserve/soften transients |
| Comp — Release | 10 – 2000 ms | How fast it recovers | Pumping vs transparent |
| **Distortion** — Enable | on/off | — | — |
| Dist — Algorithm | Crunch / Tube Pair / Iron Transformer / Zap / Air Pressure | Distortion flavor | Warmth→aggression |
| Dist — Amount | knob | Drive into distortion | Color/saturation |
| Dist — Mix | 0–100 % | Blend clean vs distorted | Parallel grit |
| Dist — Range | 20 – 20000 Hz | Frequency band exposed to distortion | Distort only highs/mids |
| **EQ** (3-band) — Centre Freq | 20 Hz – 20 kHz (per band) | Band frequency | Tone sculpting |
| EQ — Gain | ±24 dB per band | Boost/cut | — |
| EQ — Q | 0.1 – 10 | Bandwidth (scroll on graph sets Q) | Surgical vs broad |
| **Chorus** — Rate | 0 – 32 Hz | 5-voice chorus speed | Width/movement |
| Chorus — Depth | amount | Chorus depth | — |
| Chorus — Stereo | amount | Spreads chorus voices for width | Wide stereo |
| Chorus — Mix | 0–100 % (X-modable) | Wet/dry | — |
| Chorus — Filter | 20 Hz – 20 kHz | Frequency range passed through effect | Keep bass dry |
| Chorus — Octave Mode | on/off | Voices get octave-related rates (e.g. 16/8/4/2/1 Hz); off = same rate w/ LFO phase offset | Rich shimmering vs classic |
| **Phaser** — Waveform | Triangle/Sine/Square/Saw/3-step/4-step/6-step/Random | LFO shape | Smooth vs stepped sweeps |
| Phaser — Invert | on/off | Inverts the waveform | — |
| Phaser — Rate | (Hz; SYNC to host) | Phaser speed | Tempo-locked sweeps |
| Phaser — Stereo | on/off | Stereo mode | — |
| Phaser — Stages | 6 / 12 / 24 | Number of allpass stages (depth/character) | Subtle→intense |
| Phaser — Depth | amount | Sweep depth | — |
| Phaser — Feedback | amount (X-modable) | Resonant intensity | Vocal/jet character |
| Phaser — Phase | 0 – 1 | Gradually flips phase | — |
| Phaser — Mix | 0–100 % (X-modable) | Wet/dry | — |
| **Tremolo** — Waveform | Triangle/Sine/Square/Saw | Modulation shape | — |
| Tremolo — Rate | (Hz; SYNC to host) | Tremolo speed | Tempo-locked tremolo (EP staple) |
| Tremolo — Invert | on/off | Inverts the waveform | — |
| Tremolo — Vol Amt | amount (X-modable) | Volume modulation depth | Classic amp tremolo |
| Tremolo — Pan Amt | amount (X-modable) | Pan/auto-pan depth | Stereo movement |
| Tremolo — Filter on/off | toggle | Enable filter modulation | — |
| Tremolo — Cutoff | 20 Hz – 20 kHz (X-modable) | Tremolo LP filter cutoff | — |
| Tremolo — Fil Amt | amount (X-modable) | Filter mod depth; right = with resonance, left = without | Filter-tremolo motion |

> Note: each AK channel has **two Multi-Effect Slots** (one pre-EQ, one post-EQ); each slot can load Noise/Comp+Dist/Chorus/Phaser/Tremolo via dropdown.

### Mixer (6 stereo channels: 3 Instrument + 2 FX returns + Master)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Volume Fader | per channel | Level | Balance mic blend |
| Pan | drag L/R = pan; drag up/down = stereo width; drag up past center = reversed image (handle turns blue) | Stereo placement + width + reverse | Spread/narrow the blend |
| Mute / Solo | per channel (Master has Mute only) | — | Audition mics |
| Send FX1 / FX2 | Instrument channels only | Amount sent to each Delerb | Add space |
| Delerb balance | FX return channels | Balance within the return | — |

### FX — Delerb (×2 identical: FX1, FX2 — a delay feeding a reverb)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Delay — Time | 0 – 1000 ms (SYNC to host) | Delay time (drag graph L/R) | Rhythmic echoes |
| Delay — Feedback | amount (drag graph up/down) | Number of repeats | — |
| Delay — Swing | amount | Swing/shuffle on the repeats | Grooved delays |
| Delay — Ping Pong | amount | Bounces L↔R | Wide stereo echo |
| Delay — Range | 20 Hz – 20 kHz | Frequency range of the delay | Dub-style filtered delays |
| Delerb Crossfader | delay ↔ reverb | Balance between the delay and reverb | — |
| Reverb — Algorithm | Ambience 0–1 s / Room 0–3 s / Hall 0–10 s / Plate 0–10 s | Reverb space/type | Tight room → big hall/plate |
| Reverb — Pre-delay | 0 – 500 ms | Gap before reverb onset | Keep attack clear |
| Reverb — Decay | (reverb time) | Tail length (drag graph up/down) | Short vs cavernous |
| Reverb — Damping | amount | Tames high-frequency reflections | Darker tail |
| Delerb EQ | 3-band (= insert EQ) | Shape the FX return | Carve mud out of reverb |

### Session Settings (performance/tuning; saved with song, NOT with preset)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Pitch Bend Up / Down | separate ranges | Pitch-bend wheel range (independent up/down) | Bend setup |
| X-mod Source | Mod wheel / Aftertouch / MIDI CC (Learn) | Which MIDI parameter drives all X-mod knobs | Map expression hardware |
| Velocity Response | curve (rotate knob / drag graph; sides limit range) | Maps incoming velocity to response | Adapt to your controller |
| Master Tune | Hz or cents (A=440 default) | Global tuning | Match ensemble/tuning |
| Temperament | 30 temperaments dropdown | Tuning system | Historical/microtonal tuning |
| Temperament — Scale Key | root key | Root for key-specific temperaments | — |
| Temperament — Stretch | knob | Stretch tuning (sharpen highs, flatten lows) | Piano-realistic stretch |
| Set Defaults / Load Startup / Save as Startup | buttons | Reset, recall, or store these settings as the per-instance default | Consistent session defaults |

## Use by lens
- **Producer (create):** Start in Gallery → pick instrument → Explore for an ExploreMap, audition presets via play buttons, dial the 4 Macro knobs. Use Memo (top-left record) to capture ideas instantly with the sound baked in. For a fast custom tone, blend 2–3 mic perspectives in the Mixer (e.g. a close mic + a room mic) and pan/widen them. Tremolo (SYNC) + Phaser are the go-to vintage-EP motion FX on Mark One / Electric Grand.
- **Mixing (balance):** Treat the mic blend like a mini console — narrow/reverse-image the room mics to fit a dense mix, lean on the close/DI mic for presence. Use the per-channel Comp (AutoGain on) + 3-band EQ to seat the keys; the Distortion module (Tube Pair / Iron Transformer, low Amount, Mix to taste) adds harmonic glue to cut through. Keep reverb on the FX returns (sends) rather than baking it in, so you can pull it later. Vel>Sample + Velocity Response tame harsh top layers.
- **Mastering (finalize):** Not a master-bus tool — it's an instrument. The only "finalize"-adjacent knobs are the **Master channel strip** (post-noise placement, master EQ/comp) for the instrument's own bus, **Master Tune/Temperament** to lock tuning to the project, and Save-as-Startup to standardize defaults. Render the chosen mic blend printed to audio for mix/master stages downstream.

## Notes / gotchas
- **Library is per-instrument:** Studio Grand, Modern Upright, Electric Grand, Mark One are separate sample libraries; some Edit params (Pedals, available mics, DI/amp inputs) only exist on instruments that have them.
- **Session Settings ≠ presets:** tuning, pitch-bend, X-mod source, velocity curve save with the song/arrangement but are NOT stored in presets and don't change when you switch presets/instruments.
- **X-mod** is a single global source driving every X-modable knob's range — set it once in Session Settings (Mod wheel/Aftertouch/CC-Learn).
- **Two FX slots per channel** (pre- and post-EQ) means you can stack e.g. distortion before EQ and chorus after.
- **Delerb** = delay→reverb in series, with a crossfader; the graph is draggable (L/R = delay time, up/down = feedback & reverb decay).
- **Automatable params (host):** Channel Volume (Inst 1/2/3, FX1, FX2, Master), FX Sends 1 & 2 per instrument channel, Master Channel Filter (Hi/Lo), X-Mod. Deeper Edit params are tweaked via X-mod/Macro, not direct host automation.
- **My Cloud:** presets/memos auto-sync to your XLN account when online; shareable via Share links; deleted/older versions are recoverable.
- **DSP credits:** core engine by XLN Audio; additional DSP effects by PSPaudioware and Michael Ljunggren — relevant if matching the comp/EQ/FX character.
- **Preview** (bottom-right) plays the current Memo from any page, so you can tweak Edit controls live while it loops.
- Standalone version exists for jamming/live; plug-in supports all major DAW hosts.

## Deep spec (Programmer only)
Not reverse-engineered — capability only.
