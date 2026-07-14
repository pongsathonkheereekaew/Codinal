# Xfer Serum 2 — Xfer Records (synth)

| | |
|---|---|
| Vendor / ver | Xfer Records · Serum 2.0.18 (manual v1.0.3, Apr 2025) |
| Type | Hybrid software synthesizer (wavetable + multisample + sample + granular + spectral) with built-in FX rack, modulation, clip sequencer, arpeggiator |
| Format | VST3, Audio Unit (AU), AAX · macOS + Windows |
| Source | manual: `Xfer Serum 2/Xfer Serum 2.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Serum 2 is a deep, visual, workflow-oriented synthesizer built around high-quality wavetable synthesis, now expanded with four additional oscillator engines (multisample/SFZ instruments, sample playback, granular, spectral resynthesis) plus a sub and a noise oscillator. Each main oscillator offers unison (up to 16 voices), dual independent warp processors (sync, distortion, FM/PD/AM/RM/wavefolding, etc.), and full per-frame wavetable editing/import. Sound is shaped by two flexible multimode filters (Moog ladders, SVF, comb/flanger/phaser, formant/vowel, drawable, and more), a per-source mixer with two aux busses, and a modular FX rack of 18 modules (incl. band/MS splitters that host their own sub-racks). Modulation is enormous: 4 envelopes, 10 LFOs (drawable + chaos), 8 macros, and a 64-slot mod matrix with 49 sources and aux-source multiplication. A built-in CLIP module (MIDI piano-roll sequencer, 12 clips), full-featured arpeggiator (12 arps/bank, custom pattern editor), on-screen keyboard with key/scale/swing, and global tuning (concert pitch, .tun files, MTS-ESP microtuning) round it out. It's distinct for combining "go-deep" editability with a fun, immediate interface, plus lifetime-free updates and Serum 1 preset compatibility.

## Controls (every param → musical effect)

### Oscillator — common (OSC A / B / C, all engines)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Power / label | on/off | Enables the oscillator (green = on); click to mute/solo or free CPU | turning layers on/off, soloing |
| Engine menu | Wavetable / Multisample / Sample / Granular / Spectral | Selects the synthesis type for that oscillator slot | choosing the sound source per slot |
| OCT | octaves | Octave transpose | coarse tuning, octave layering |
| SEM | semitones | Semitone transpose | intervals, chords across oscs |
| FIN | cents | Fine tuning | detuning, beating, analog drift |
| CRS | continuous semitones (no snap) | Smooth pitch transpose — best as a modulation/automation target for wide sweeps (sirens) | LFO/automated pitch glides |
| Pitch mode (RC on OCT/SEM) | Semitones / Harmonics / Ratio / Step | How pitch math works: even-temperament, harmonic multiples, FM-style ratios, or MTS-ESP steps | organ/overtone tunings, FM ratios |
| Enable Pitch Tracking (RC) | on/off | Whether osc follows MIDI note pitch; off = fixed pitch (drones, percussion, noise, use WT osc as LFO at C-2) | drones, perc, static layers |
| Enable Pitch Bend Tracking (RC) | on/off | (Sample/Granular/Spectral only) whether pitch-bend affects fixed-pitch oscs | static sounds that ignore bend |
| Routing button (top-right) | Filter / Main / Direct / None | Sends osc to Filter (knob blends F1↔F2), Main (thru FX), Direct (bypass filter+FX), or None (mod source only) | filter routing, clean blends, mod-only |
| BUS 1 / BUS 2 | send amount | Sends osc signal to the two aux effect busses | shared reverb/delay sends |
| UNISON | 1–16 voices | Stacks detuned copies; field color warns of CPU cost; level kept in check | thickness, supersaws |
| UNISON ⚙ MODE | Linear / Super / Exp / Inv / Random | Detune spread shape (even / lush-supersaw / dramatic / inverted / chaotic) | character of the unison spread |
| UNISON STACK | Off / 12 (1-3x) / 12+7 (1-3x) / Center-12 / Center-24 | Transposes/harmonizes unison voices by octaves/fifths | octave/fifth-stacked stacks |
| UNISON WIDTH | 0–100% | Stereo spread of unison voices | width vs. mono focus |
| UNISON RANGE | depth | How far apart in pitch unison voices spread | subtle chorus → dissonant |
| DETUNE | ± amount | Unison detune amount (active only with >1 voice) | tuning the unison spread |
| BLEND | 0–100% (def 75%) | Level of outer unison voices vs. centre (wet/dry of unison); only with >2 voices | center-weighted vs. even |
| WARP 1 / WARP 2 (knobs) | depth per mode | Two independent warp processors; depth of the selected warp mode | shaping/animating the waveform |
| WARP 1/2 mode menu | see Warp Modes below | Selects each warp's algorithm (< > arrows to cycle) | FM, sync, distortion, folding etc. |
| WARP 1/2 (unison settings) | spread | Spreads warp amount across unison voices | per-voice warp variation |
| PAN | L↔R | Stereo placement of the oscillator | stereo image |
| LEVEL | volume | Oscillator output level | mix balance |
| Module menu (RC label) | Reset / MIDI Learn / Lock Module / Init Module / Copy / Copy (w/mods) / Paste | Per-module ops; Lock keeps settings across preset changes; Copy w/ or w/o modulations | preset building, A/B copying |

### Oscillator — Warp modes (apply to WARP 1 & WARP 2)
| category | modes | effect |
|---|---|---|
| Off | — | warp disabled |
| Sync | (one mode) | Hard→soft sync to an internal osc; WARP knob = internal pitch (harmonic shift); WARP Var fader sets sync softness |
| Alt Warp | Bend +/−/±, PWM, Asym +/−/±, Flip, Mirror, Remap 1–4, Quantize, Odd/Even | Waveshape bends, pulse-width, polarity flips, mirroring, custom/sinusoidal remaps, sample-rate-redux that tracks pitch, odd/even harmonic scaling |
| Filter | LPF, HPF | Per-oscillator low/high pass |
| Distortion | Tube, Soft Clip, Hard Clip, Diode 1/2, Linear Fold, Sine Fold, Zero-Square, Asym, Rectify, Sine Shaper, Stomp Box, Tape Sat., Soft Sat. | Wide palette from gentle warmth/saturation to harsh wavefolding/rectify |
| FM | from other osc (B/C), Noise, Sub, Filter 1/2, + Thru-Zero, Exp, Linear | Frequency modulation; source must be enabled (turn its level down to use as mod only); Thru-Zero/Linear keep pitch stable, Exp brighter/harsher |
| PD | from other osc/Noise/Sub/Filter/Self | Phase distortion (like FM but modulates phase) |
| AM | from other osc/Noise/Sub/Filter | Amplitude modulation |
| RM | from other osc/Noise/Sub/Filter | Ring modulation |
| Swap A/B | — | Swaps WARP 1 and WARP 2 modes |

### Wavetable oscillator (extra)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Wavetable menu | Analog / Digital / S2 Tables / Spectral / Vowel + Load/Import | Chooses the wavetable | source timbre |
| WT POS | frame index | Selects the audible frame/subtable; RC → Smooth Interpolation for near-infinite morph positions | morphing, evolving timbres |
| Phase / RAND | degrees / 0–100 | Start phase and phase randomization per note | transient consistency vs. variation |
| Wavetable Editor | full editor | Draw/FFT-edit frames, manage subtables, import audio/PNG, formula parser | custom wavetable design |

### Multisample oscillator (extra)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Instrument menu | Bass/Choir/Drums/Keys/Mallet/Plucked/Strings/Synth/Winds + Load SFZ | Loads a multisample instrument (open-standard .sfz; no native SF2) | realistic instruments, choirs, orchestras |
| TIMBRE | amount | Adjusts mapped-sample-to-pitch relationship (inverse zone mapping for experimental timbres) | unusual key-zone timbre effects |
| Envelope OVERRIDE + DELAY/A/H/D/S/R | ms / dB | Override the SFZ envelope with DAHDSR (DELAY can BPM-sync) | reshaping sampled instrument dynamics |
| VEL TRACK | 0–100 | Velocity sensitivity of sample selection | dynamic playing response |
| RAND | 0–100 | Randomizes initial sample phase | per-note variation |
| Switch to Single Sample / Wavetable | menu | Convert last-played note into a Sample, then optionally into a Wavetable | sound-design conversions |

### Sample oscillator (extra)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Sample menu | Factory / Factory Non-Tonal / Wavetables / Load Sample | Loads a sample (or a wavetable as a sample) | sample-based sounds |
| Start/End markers + LS/LE | sample % | Sample start/end and loop start/end (drag or type) | trimming, looping |
| SCAN | speed/direction | Playback speed & direction; RC → Range (±200/400/800%), Reverse, Lock to Tempo, Sample Length to BPM (knob → RATE in beats) | tape-stop, time-stretch, tempo-sync |
| Sample ops (RC) | Snap Off/Zero/Beats/Loop, Fade Edges (1–128ms/None), Normalize, Reverse, Trim, Slice Off/Auto/Manual | Non-destructive edits + slicing (Auto = threshold line, Manual = drag handles); slices assignable to notes/clip | break chopping, click-free loops |
| Loop menu | One-shot / Fwd / Rev / Fwd-Rev / Tailed / Relative Loop / Link Loop Length / Exit Loop on Release | Loop behaviour | sustained vs one-shot vs ping-pong |
| Loop X-Fade | 0–100% | Crossfade at loop point for click-free loops | seamless looping |
| UNISON START / SPAN | offset | Random / fixed start-position offset per unison voice | livelier unison textures |

### Granular oscillator (extra)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| WARP / SCAN / DENS / LENGTH / PAN / LEVEL | — | Top row: warp mode, scan rate, grain density, grain length, pan, level | core granular shaping (CPU-heavy) |
| SCAN | speed | Playhead speed through sample (high = rhythmic/glitch, low/0 = stretched/frozen, negative = reverse); RC → Range, Reverse, Key Track, Lock to Tempo, Length to BPM | time-stretching, freezing, glitch |
| DENS (Density) | Hz / BPM / Grains | Grain spawn rate; RC → Free/BPM-Sync(Trip/Dot)/Grains, Jump Start, Max Grains (CPU limit) | grain cloud density |
| LENGTH | sec/ms/BPM/% | Duration of each grain (short=rhythmic, long=smooth); RC → Free/BPM/Percent | grain character |
| Window AMOUNT / SKEW / SHAPE | + per-grain RAND | Grain amplitude envelope: influence, skew, and shape (Hann/Welch/Gaussian/Blackman-Harris/Sinc/Tukey/Triangle/Trapezoid/ExpDec/ExpDecRev) | grain attack/decay articulation |
| OFFSET / DIR / PITCH / RAND×3 (lower row) | per-grain randomization | Randomize grain offset, direction (DIR RC → Reverse Grains), pitch, length, pan, level | organic/chaotic grain clouds |
| SPAWN PATTERN | Together / Even / Exp / Random | Timing offset of unison grain spawns | unison grain texture |
| Loop Grains / Manual mode | menu | Loop respects markers, or Manual: SCAN→X/Y dot you modulate freely (no auto-scan) | controlled scrubbing |
| X|Y Control + Y axis | red dot | 2D pad: SCAN on X, assignable Y target (Level/Warp/Density/Grain Length/Window/skew/rand…) | expressive 2-axis control |

### Spectral oscillator (extra)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Sample menu | Factory / Non-Tonal / Wavetables / Load Sample / Import PNG | Loads sample for FFT resynthesis | spectral/resynth sounds |
| Hi/Lo frequency markers | drag right of spectrogram | Limit spectral high/low; RC → Smooth (Butterworth edges), Post Warp; modulatable | spectral band shaping |
| SCAN | speed/direction | Playhead through spectral frames; RC adds Phase Lock (less smearing, tonal) & Transients (preserve transients, perc) | spectral time control |
| CUT | cutoff | Spectral filter cutoff | refining spectral tone |
| FILTER (display) | drawable curve / preset / wavetable | Custom spectral filter mask (draw points, GRID), filter preset, or wavetable-as-filter | precise spectral filtering |
| MIX | wet/dry | Balance of spectral-processed vs dry | blend amount |
| X|Y + Y axis | Level/Warp/Spec Flt Cutoff/Spec Flt Wet-Dry/Freq Lo/Freq Hi | 2D control for spectral params | expressive spectral morphing |

### Sub oscillator
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Power | on/off | Enables sub osc | adding low-end weight |
| OCT / CRS | octaves / cont. semis | Pitch transpose | tuning the sub |
| Waveform | Sine / Rounded Rect / Triangle / Saw / Square / Pulse | Sub waveform (sine=pure sub, saw/square=aggressive/harmonic) | clean vs gritty bass |
| PHASE | degrees | Start phase; RC → Contiguous (continue prev note's phase) | transient consistency |
| PAN / LEVEL | L↔R / volume | Stereo placement and output | sub mix |

### Noise oscillator
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Power | on/off | Enables noise osc (stereo sample player) | texture, attack, realism |
| Sample menu | Analog / Attacks_Kick / Attacks_Misc / FP_Inharms / Organics / S2 Noises / SOR / Color / Load Sample | Loads noise sample; also a WARP source for the three main oscs | layered noise, drum attacks |
| Color (White/Pink/Brown/Geiger) | — | Color-noise modes; enables STEREO control + FILTER knob | tonal noise shaping |
| STEREO | 0–100 | (color modes) 0=mono, 100=decorrelated L/R | noise width |
| FILTER | LP↔HP | (color modes) high/low-pass the noise | brightening/darkening noise |
| One-Shot / Loop | toggle | Loop the noise sample, or one-shot (attack sounds) | sustained vs percussive |
| START | phase % | Sample/phase start (automate for lo-fi scratching) | start-point variation |
| RAND | 0–100 | Randomizes start phase per note | chord variation |
| PITCH / FINE | base pitch / fine | Base pitch (50%=nominal) and fine tune | tuned noise |
| PAN / LEVEL | L↔R / volume | Placement and output | noise mix |

### Filter modules (Filter 1 & Filter 2)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Power / M | on/off | Enable filter module | engaging filtering |
| Source routing S/A/B/C/N | per-source | Routes Sub/OSC A/B/C/Noise into the filter | choosing what gets filtered |
| TYPE menu | Normal / Multi / Flanges / Misc / New (see below) | Selects filter algorithm (< > to cycle, mouse-wheel) | filter character |
| CUTOFF | frequency | Primary cutoff (except vowel/formant); keytrack switch offsets by MIDI note (tracks first pitch-tracked osc) | brightness, sweeps |
| RES | resonance | Filter resonance/feedback | emphasis, self-oscillation |
| DRIVE | gain | Input gain into filter; mild coloration; RC → Clean Mode (−24dB pre / +24dB post) | warmth/grit, or clean |
| FAT / VAR (variable knob) | per-type | Type-dependent: FAT (resonance saturation), FREQ/MORPH (dual/morph filters), LP/HP FRQ, HL WID, DB+/−, SPREAD, DAMP, BOEUF, THRU, FORMNT, WIDTH, COMBFRQ, SCREAM, STAGES, SMOOTH, PAIN | the second control of dual/special filters |
| PAN | L↔R offset | Cutoff offset between L/R channels (def 50% = no effect) | stereo filter motion |
| MIX | wet/dry (def 100%) | Filter wet/dry (no effect on comb-type) | parallel filtering |
| LEVEL | dB | Filter output level | filter mix |
| Display mode (RC) | Frequency Response / + FFT / Phase + FFT | Visualization (Option/Alt-click to cycle) | visual filtering |

**Filter type catalog:** Normal: MG Low 6/12/18/24 (Moog ladder LP), Low/High/Band/Peak/Notch 6/12/18/24 (SVF). Multi: LH/LB/LP/LN/HB/HP/HN/BP/BN/PP/PN/NN (dual SVF, VAR=2nd cutoff) and LBH/LPH/LNH/BPN (morphing SVF, MORPH). Flanges: Comb/Flanger/Phaser L/H/HL variants (feedback-circuit filter, MIX≈50%). Misc: Low/Band/High EQ 6/12, Ring Mod/Modx2, SampHold/SampHold−, Combs/Allpasses/Reverb, French LP (BOEUF), German LP (zero-delay), Add Bass (THRU), Formant-I/II/III (vowel, FORMNT), Bandreject (WIDTH), Dist.Comb 1/2 LP/BP (COMBFRQ), Scream LP/BP (SCREAM). New: Wsp, DJ Mixer, Diffusor (STAGES), MG Ladder, Acid Ladder, EMS Ladder, MG Dirty (PAIN), PZ SVF (drawable), Comb 2, Exp MM/BPF (SMOOTH/MIX).

### Mixer (MIX tab)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Per-source channel (SUB/OSC A-C/NOISE/FILTER 1-2) | header on/off | Enable + show each source channel | per-source balance |
| Channel routing menu | Filter / Main / Direct / None | Signal destination per source (Main/Direct show ENV 1 amp button) | routing per source |
| Filter blend knob (1↔2) | F1↔F2 | When routed to filters, blends between Filter 1 and 2 | serial/parallel filtering |
| BUS 1 / BUS 2 sends | amount | Send to the two aux effect busses | shared sends, parallel comp |
| PAN | L↔R | Per-channel stereo placement | stereo image |
| Level fader | dB | Per-channel level | mix balance |
| BUS 1 / BUS 2 channels | Main/Direct/Bus + bypass + level | Bus routing, FX bypass, and bus output level | aux bus mixing |
| MAIN / DIRECT channels | bypass per FX + level | Main (thru FX) and Direct (clean) output levels; per-FX bypass | final output balance |

### FX rack (FX tab — drag to reorder, modular)
General per-module: power/bypass, drag-reorder, copy, MIX (0=dry→100=wet) and LEVEL (dB) on most. Add modules per slot; FX params are modulatable.

| module | key controls | musical job |
|---|---|---|
| **Bode** | MONO INPUT, SHIFT (RC Retrig), RANGE, DIR, WIDTH, DELAY, BPM, FEED, BALANCE, BLUR, MIX, LEVEL | Bode frequency shifter — dissonance, phasing, movement, chorus/wow-flutter (BLUR) |
| **Chorus** | RATE (BPM-sync or 0-20Hz), BPM, DELAY 1, DELAY 2, DEPTH, FEEDBACK, LPF/HPF, MIX, LEVEL | 4-voice chorus (2L/2R taps) — width, warble |
| **Compressor** | MODE (Single/Multiband), THRESH, RATIO (max=Limit, true peak limiter), ATTACK, RELEASE, GAIN; multiband: X-LOW/X-HIGH crossovers, BELOW, H/M/L band gains; MIX, LEVEL | Dynamics control; multiband for freq-selective comp / sidechain ducking |
| **Convolve** | IMPULSE menu (Load IR/Embed), SIZE, TONE, φ MIN, PRE-DLY, BPM, ATTACK, DECAY, DAMP, IR GAIN, MIX, LEVEL | Convolution reverb / IR coloration |
| **Delay** | MODE (Normal/Ping-Pong/Tap→ + High Quality), L/R delay times + scalar (Trip/Dot), BPM/MS, LINK, FEEDBACK, FREQ, Q, MIX, LEVEL | Echo/delay with filtered feedback |
| **Distortion** | MODE (13 types incl. X-Shaper dual-waveshaper w/ Edit A/B), OFF/PRE/POST filter, TYPE (LP↔BP↔HP), FREQ (RC Key Track), Q, DRIVE (downsample amt / X-Shaper morph), MIX, LEVEL | Distortion/saturation; custom dual waveshaper, asym for even harmonics |
| **Equalizer** | Low band: FREQ/Q/GAIN (Shelf/Peak/High Pass); High band: FILTER TYPE (Shelf/Peak/Low Pass), FREQ/Q/GAIN; LEVEL | 2-band parametric EQ |
| **Filter** | TYPE (full filter catalog), CUTOFF (RC Key Track), RES, DRIVE (RC Clean Mode), VAR knob, PAN, MIX, LEVEL | Master-effect version of the synth filter |
| **Flanger** | RATE (BPM/0-20Hz), BPM, DEPTH, FEEDBACK, PHASE (stereo offset), MIX, LEVEL | Flanging sweeps |
| **Hyper/Dimension** | Hyper: RATE, UNISON (1-7), DETUNE, RETRIG, MIX; Dimension: SIZE, MIX; LEVEL | Micro-delay chorus (unison alternative, low CPU) + pseudo-stereo widener |
| **Phaser** | RATE (BPM/Hz), BPM, POLES, DEPTH, DEPTH 2, FREQ, FEEDBACK, PHASE, MIX, LEVEL | Phaser — peaks/troughs sweep |
| **Reverb** | TYPE (Plate/Hall/Vintage/Nitrous/Basin), LO CUT, HI CUT, SIZE, PRE-DLY, DAMP/DECAY, WIDTH/SPIN/DIFF/CHORUS/FEEDBACK (per type), Nitrous MODE (Space/Marble/Rectangle/Hexagon/Box), MIX, LEVEL | Plate & hall reverb (Tal-based), multiple algorithms |
| **Splitter L/H** | LOWS rack, SPLIT FREQ, HIGHS rack, LEVEL | Split into low/high bands, each with its own FX sub-rack |
| **Splitter L/M/H** | LOWS/MIDS/HIGHS racks, 2× SPLIT FREQ, LEVEL | 3-band split with per-band FX sub-racks |
| **Splitter M/S** | MID rack, SIDE rack, LEVEL | Mid/Side split with per-band FX sub-racks |
| **Utility** | POLARITY INV (L/R), LPF, HPF, MONO BASS + FREQ, WIDTH, PAN (balance), MIX, LEVEL | Polarity, filtering, mono-bass, width/balance utility |

### Modulation — Envelopes (ENV 1–4)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| ATK / HOLD / DEC / SUS / REL | ms or BPM-sync; SUS in dB | Attack / Hold / Decay / Sustain / Release of the envelope (ENV 1 = always-on amp env) | shaping amplitude & mod over time |
| Attack/Decay/Release curves | drag on graph | Per-segment curvature | tone of the envelope shape |
| BPM/MS toggle | units | Envelope times in ms or note subdivisions | tempo-locked envelopes |
| Lock (zoom) | on/off | Auto-fit zoom vs manual zoom | display convenience |
| Legato Inverted (RC) | on/off | Forces this env to retrigger even when global LEGATO on | per-env retrigger control |
| Grid Time/Beats (RC) | display | Background grid in ms or beats | visual alignment |
| Assign (drag tab → control) | — | Drag ENV tab onto any knob to modulate it; depth via blue halo; RC tab → bypass/remove destinations | routing modulation |

### Modulation — LFOs (LFO 1–10; 7–10 appear after using LFO 6)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Graph + tools | Point / Flat / Ramp Up / Ramp Down | Draw the LFO shape (snap to GRID, step sequences via Shift-click) | custom modulation shapes |
| TYPE | Normal / Path / Chaos: Lorenz / Chaos: Rossler / S&H | LFO engine type | smooth, chaotic, or random mod |
| MODE (Retrig) | Free / Retrig / Envelope | Free-running, note-retriggered, or one-shot envelope (with loopback point) | timing behaviour |
| MONO | on/off | Single LFO for all voices vs per-voice | unified vs per-voice motion |
| SHAPE menu | load/save preset | Load/save LFO graph presets | reusing shapes |
| DIRECTION | Forward / Reverse / Ping Pong | Playback direction | shape direction |
| GRID (H/V) | divisions | Grid for snapping/step drawing | rhythmic LFOs, step seq |
| HOST | on/off | Anchor LFO phase to host transport (works even when BPM off in S2) | song-synced LFOs |
| BPM/HZ | toggle | Tempo-synced (1/4, 1/8…) or free Hz | sync vs free rate |
| RATE | time/Hz | LFO speed (RC → Swing in BPM mode, 10× in Hz mode) | modulation speed |
| TRIP / DOT | toggle | Triplet / dotted timing | groove timing |
| RISE | time | Fade-in time for LFO influence | slow-onset modulation |
| DELAY | time | Delay before RISE begins | delayed modulation |
| SMOOTH | amount | Smooths LFO output (avoid abrupt jumps) | de-stepping |
| PHASE | start position | LFO start phase (RC → Snap to Grid) | phase alignment |
| LFO Editor | larger canvas | Full-screen graph editing | precise drawing |

### Modulation — Macros (8), Matrix, sources
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| MACRO 1–8 | knob, multi-destination | Assign one knob to many params (drag macro → control); also usable as mod destination | performance, complex moves |
| Matrix SOURCE | 49 sources | LFOs, envelopes, macros, oscillators/filters as mod, velocity, note, Active Voices, Note-On Alt/Rand 1/2, Voice Index, Voice Mod 1/2, Expression/MPE X/Y/Z, ModWheel, Aftertouch, Poly Aftertouch, Pitch Bend, Fixed | choosing the modulator |
| Matrix CRV | curve (50%=linear, gray=bypass) | Non-linear remap of source (editable curve + RISE/FALL slew) | shaping the modulation response |
| Matrix AMOUNT | bi-directional | Modulation depth (left = inverted) | depth & polarity |
| Matrix POL | uni / bi-directional | Whether modulation is uni- or bipolar | knob-at-start vs centre |
| Matrix DESTINATION | param menu | Target parameter | the modulated control |
| Matrix AUX SOURCE + INV + CRV | secondary source | Scales the main modulation (multiplied); INV inverts aux | gated/scaled modulation (e.g. LFO via ModWheel) |
| Matrix OUTPUT | scale | Final output scaling | fine-tuning |
| Matrix ops (menu) | Sort, Lock Matrix, Create Vibrato, Create Velo→Amp, Apply and Delete Macros | Housekeeping + quick-mod creation; "bake" macros into preset | matrix management |
| Matrix capacity | 64 slots | Up to 64 destinations | large patches |

### Voicing & Portamento
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| MONO | on/off | Monophonic mode (one note, re-pitched) | leads, basses |
| LEGATO | on/off | (Mono) envelopes/LFOs don't retrigger on legato; off when paraphonic gives effect-retrigger control | smooth legato lines |
| POLY | 1–16 voices | Polyphony limit (CPU); disabled in Mono | voice management |
| Limit Same Note Poly to 1 (RC) | on/off | Prevents stacking the same note | clean basses/drums |
| Voice Steal Priority (RC) | Newest/Oldest/Highest/Lowest/Velocity | Which voice is stolen when over limit | predictable voice stealing |
| PORTA | rate | Portamento glide time (mainly with MONO) | pitch glides |
| CURVE | convex/concave | Glide contour (convex=fast-then-slow) | glide feel |
| ALWAYS | on/off | Glide on every note vs only when a note is held | always-glide vs held-glide |
| SCALED | on/off | Glide time scaled by interval distance (octave = full PORTA time) | even glide on short intervals |

### CLIP module (MIDI sequencer)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| GLOBAL BANK | load/save/Init | Load/save clip banks (12 clips), Init to start fresh | clip preset management |
| TRIGGER MODE | Mono / Poly | One clip at a time vs multiple simultaneously | clip layering |
| EDIT ALL | on/off | Parameter edits apply to all clips (or Opt/Alt-drag) | batch editing |
| Clip slots (1–12) | select | Choose active clip | clip selection |
| LENGTH | bars.beats.16ths | Clip length | clip duration |
| KB SPAN / TRANS / MODE / TIME / RATE / BPM | per-clip | Keyboard span, transpose, mode, time, playback rate, BPM-sync | clip behaviour |
| LAUNCH QUANT | 1/16… | Quantize clip launch to clock | tight triggering |
| RETRIG / VELO TRIG / NOTE RATE | toggles | Retrigger and velocity-trigger behaviour | live triggering |
| Piano roll | draw/record | Click-in or record MIDI notes + velocity | sequencing |
| MIDI OUT | Off / route | Output generated MIDI internally or to another instrument | MIDI routing |
| RECORD / OVERDUB / EXTEND | transport | Record live performance into clip | capturing performances |
| Macros (Show Macros) | assign | Assign macros to clip settings | live clip control |

### Arpeggiator (ARP module)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| GLOBAL BANK / LAUNCH QUANT / EDIT ALL | load/save/Init; 1/16…; on/off | Bank management (12 arps), launch quantize, batch-edit all arps | arp preset mgmt |
| PATTERN SHAPE | Up/Down/Converge/Diverge/random/etc. | Arp pattern shape (< > to cycle) | rhythmic pattern |
| RATE + BPM/HZ + TRIP/DOT | time/Hz; toggles | Arp speed and timing | arp tempo |
| Custom Pattern editor | pencil button | Advanced graph editor: LENGTH, MODE (Normal/Reverse/Pendulum/Random/Rand Start/Rand End/One Shot/Static), TIME, STEP MODE (Normal/New Only/Chord/Chord new), WRAP, PITCH (0-24), RANGE; Accent & Strum lanes, automation lanes | bespoke arp patterns |
| TRANSPOSE SHIFT / RANGE / Shape | ± / count / shape menu | Per-repetition transpose amount, number of repeats, and range shape (Up/Down/Thumb/Pinky/Converge/Diverge/Chord/Random…) | evolving arp pitch |
| PLAYBACK: LATCH / OFFSET / REPEATS / GATE / CHANCE / THRU | toggles / values | Latch (hold without keys), step offset, repeats, gate length, note-play probability, MIDI thru | playback feel |
| RETRIGGER: LAUNCH / NOTE / FIRST / RATE | toggles | How/when arp shape retriggers (on launch or incoming note) | retrigger behaviour |
| VELOCITY: RETRIG / DECAY / TARGET | toggles/knobs | Arp velocity evolution over time | dynamic arps |
| MIDI OUT | Off / route | Output arp MIDI | MIDI routing |

### Keyboard
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| TRANSPOSE | −24…+24 semitones | Transpose keyboard (2-octave range) | quick transpose |
| KEY / SCALE | root + scale list | Sets key & scale (huge list: Major/Minor/modes/world scales/Chromatic…); quantizes CLIP & ARP and highlights piano-roll | scale-locking sequences |
| SWING | Off / % + division | Swing applied to notes (matches host convention) | groove |
| OSC MAPPING | dialog | Edit note ranges each oscillator/arp responds to | key-splits, layering |

### Global settings (GLOBAL tab)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Preferences** — Help/Param tooltips, Double-click params (Reset/Type Value), Mouse-wheel param, Keyboard shortcuts, Default waveform view (2D/3D) | toggles | UI behaviour | personalizing workflow |
| MPE — enabled by default, Pitch Bend→Expr X, Expr Y bi-directional | toggles | MPE configuration | MPE controllers |
| General — Limit Mod depth on drop, Mod Wheel→WT Pos (editor open), Silence note+FX tails on stop, Load MIDI Map from Presets, Use Ultra quality when rendering, Auto-check updates | toggles | Misc global behaviours | render quality, MIDI maps |
| **Voice Control** — OSC select (S/A/B/C/N), RANDOM (Pan/Detune/Cutoff/Envs, per-voice), SEQ (per-voice Pan/Detune/Cutoff/Envs/Mod1/Mod2, seq length 1-8), SCALING (Envs %, LFOs % or Rate) | per-voice settings | Per-voice variation/humanization (analog drift, round-robin) + global env/LFO scaling | organic/analog character |
| **Quality** — oversampling (Draft 1× / High 2× / Ultra 4×), lock, S1 Compatibility Mode, Disable Smoothing | menu/toggles | Render quality, Serum-1 sound match, sample-accurate automation | CPU vs quality, S1 presets |
| **Tuning** — Concert pitch (A=Hz), TUN FILE (.tun), MTS-ESP (Enable / Note-On Only), lock | values/menu | Global tuning: concert pitch, Scala .tun, MTS-ESP microtuning across instances | microtuning, alt tunings |
| Build/Date | display | Serum version & build (e.g. 2.0.18) | support reference |

### Global controls (top bar / always visible)
| control | range / unit | what it does |
|---|---|---|
| MAIN | volume | Master output volume |
| Resize (logo menu) | 50–400% | Scale the UI |
| Undo / Redo | — | Undo/redo edits |
| Preset browser | nav / search | Load/save presets, search by name/category/rating |

## Use by lens
- **Producer (create):** Serum 2 is a primary sound-design instrument. Start from a wavetable for classic EDM leads/basses/pads, switch a slot to Multisample/SFZ for realistic instruments, Granular/Spectral for evolving textures and risers. Layer OSC A/B/C + Sub + Noise, fatten with UNISON (magic number 7) and the dual WARPs (Sync, FM, wavefolding). Drive movement with the 10 LFOs (draw your own, or step-sequence on the grid) and 4 envelopes, then commit complex moves to the 8 macros for live tweaking. Use the CLIP sequencer to ship preset+pattern combos and the arpeggiator to turn chords into evolving lines. Build whole sounds in the box including its 18-module FX rack.
- **Mixing (balance):** Use the per-source MIXER for internal balance, PAN, and aux-bus sends (shared reverb/delay, parallel compression). The FX rack doubles as a channel-strip: EQ (2-band), Compressor (single/multiband), Filter, and Utility (mono-bass, width, polarity) tidy the sound before it leaves the synth. The MS/L-M-H splitters let you process bands or mid/side independently. Set quality to High and watch POLY/unison for CPU. The keyboard KEY/SCALE keeps sequenced material in key.
- **Mastering (finalize):** Not a mastering tool — it's a synth — but as a sound source for a master context, set Quality to Ultra (and enable "Use Ultra quality when rendering") for the cleanest bounce, lock Tuning to your project's concert pitch / MTS-ESP, and use the Utility/EQ/Compressor on the Main bus only for finishing a standalone patch (e.g. a one-shot or texture) before export. Disable Smoothing only if you need sample-accurate automation precision.

## Notes / gotchas
- **CPU:** UNISON voices, Granular (Max Grains/density), Spectral, and Ultra oversampling (4×) are the big CPU costs; UNISON field color warns you. Hyper/Dimension is a low-CPU alternative to high unison.
- **Serum 1 compatibility:** Loading a Serum 1 preset auto-enables **S1 Compatibility Mode** (Quality pane) to preserve the original sound; disable it to get Serum 2's rebuilt DSP. Serum 2 is a free upgrade for Serum 1 owners.
- **Modulation routing is drag-and-drop:** drag any ENV/LFO/macro/osc/filter tab onto a knob; depth via the blue halo; everything also appears in the 64-slot matrix (and vice-versa). Aux Source multiplies two modulators (classic LFO-via-ModWheel vibrato).
- **Pitch-tracking quirk:** with pitch tracking off, Multisample/Sample/Granular/Spectral play C3, but the Wavetable osc plays C-2 — letting you repurpose a wavetable osc as an audio-rate LFO/mod source.
- **LFOs 7–10** are hidden until you use LFO 6. **POLY** is disabled in MONO. **MIX** has no effect on comb-type filters.
- **Latency:** Compressor RATIO=Limit (true peak limiter) can add latency — RC → Limiter Latency Comp to report it to the host. Convolve and oversampling can add latency.
- **Microtuning:** supports Scala .tun files and MTS-ESP (Note-On Only option freezes a note's tuning for its duration); .tun always overrides MTS-ESP. Lock tuning to ignore preset tuning.
- **Embedding:** wavetables, noise samples, and convolution IRs can be embedded into a saved preset for portability.
- **Multisample format:** open-standard human-readable .sfz (key-zones, velocity layers, round-robins, key-switches); SF2 not native (convert to SFZ).
- **Sample editing is non-destructive:** Fade Edges/Normalize/Reverse/Trim are undoable; Reload Sample restores the original.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
