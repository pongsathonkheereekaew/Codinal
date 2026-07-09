# u-he Repro-1 — u-he (monophonic synthesizer)

| | |
|---|---|
| Vendor / ver | u-he · Model 100B, Rev 1.1.3 (manual 2025) |
| Type | Monophonic subtractive synth (component-level model of an early-80s Curtis-chip mono) + onboard FX, dual sequencer, arpeggiator |
| Format | VST/VST3, AU (.aupreset), AAX (NKS supported) |
| Source | manual: `u-he Repro/u-he Repro-1.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Repro-1 is a circuit-faithful emulation of an iconic early-1980s monophonic keyboard synth (Curtis 3340 oscillators, 3320 filter, 3310 envelopes) — fat drones, cutting leads, funky basses and quirky sci-fi FX. Architecture is deliberately simple: two oscillators (saw / triangle / pulse, with sync), noise, a 24 dB/oct (4-pole) lowpass filter, two ADSR envelopes, one LFO, and a compact "3 sources via 2 paths to 5 destinations" modulation matrix. u-he extends the original with a much more capable two-pattern step sequencer (up to 32 steps each), an arpeggiator, a 4/8-slot mod matrix (PERFORM), five built-in effects (JAWS wavefolder, Lyrebird delay, ResQ EQ/resonator, Drench reverb, Sonic Conditioner), and a TWEAKS page that swaps the modeled character of each oscillator / filter / envelope. Distinctive trait: it nails the "lovable quirks" of the hardware (inverted PW modulation, envelope curvature tied to volume, arp won't trigger on a single held note) while remaining a pristine modern instrument.

## Controls (every param → musical effect)

### Control bar (global)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Master Tune | ±12 semitones | Tunes whole preset; SHIFT for fine | match other instruments / detune |
| Output | 0–200 (12 o'clock nominal) | Final volume after amp + all FX | gain-stage, compensate for resonance/FX loss |
| HQ | on/off (global, not saved) | High-Quality mode; only needed for extreme FM | enable for harsh FM artefacts |
| zZz (Sleepy) | on/off (global) | Cuts CPU when no notes play | leave on to save CPU |
| Key Ctrl | toggle | Experimental numpad-driven param entry | precise value typing (WIP) |

### Oscillator A
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Frequency | ±12 semitones | Coarse pitch (two-octave) | tune osc A |
| Fine Tune (trimmer) | ±20 cents | Fine pitch; sets beating vs OSC B | gentle detune / chorus-thickening |
| Octave | 4-octave rotary switch | Transpose by octave | range placement |
| Sawtooth shape | on/off | Full-harmonic brassy saw | leads, brass, anything bright |
| Pulse shape | on/off | Pulse wave (timbre set by Pulse Width) | hollow / reedy tones; OSC silent if neither shape on |
| Pulse Width | 0–100% (double-click = 50%) | Duty cycle of pulse (no effect on saw; thins to silence at extremes) | PWM, square (50%), nasal tones |
| Sync | on/off | Hard-syncs OSC A waveform to OSC B zero crossings | aggressive sync leads (OSC A freq must be > OSC B) |

### Oscillator B (same as A minus Sync, plus extras)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Frequency / Fine / Octave / Pulse Width | as OSC A | coarse/fine pitch, octave, pulse duty | tune / detune second osc |
| Saw / Triangle / Pulse shapes | on/off each (mixable) | Triangle is bipolar (no DC) — little bite as audio, ideal LFO / wavefolder driver | sub layers, modulation source, mellow tone |
| Norm / Lo Freq | switch | Lo Freq drops OSC B to sub-audio (range ×4 wider) for use as an LFO | use OSC B as a second LFO |
| Kybd / Off | switch | Off = disable keyboard tracking (constant pitch) | drones, fixed-pitch FX, FM index source |

### Glide & Mode
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Glide Rate | 0–100 (slow above 50) | Portamento time; 0 = instant | 303-style slides, expressive leads |
| Auto / Norm | switch | Auto = glide only on legato overlap; Norm = always | natural slides only when desired |
| Retrig / Norm | switch | Retrig = envelopes restart on each legato note; Norm = no retrigger | accent vs smooth legato |
| Repeat | on/off | Retriggers envelopes at LFO or Clock rate (per LFO\|KEY\|CLOCK); notes repeat without holding | rhythmic pulsing, tremolo gating |
| Drone | on/off | Holds amp envelope sustaining indefinitely | drones, hands-free pads |

### Mixer
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Osc A | 0–100 | Level of OSC A into filter | balance oscillators |
| Osc B | 0–100 | Level of OSC B | balance oscillators |
| Feedb \| Noise (knob) | 0–100 | Level of either noise OR post-amp feedback (see switch) | wind/percussion (noise) or bass boost (feedback) |
| Feedb \| Noise (switch) | switch | Selects whether the knob feeds white noise or feeds signal from behind the amp back into the mixer | NOISE for texture, FEEDB for grit/low-end |

### Filter (24 dB/oct 4-pole LP)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Cutoff | 0–100 | LP cutoff frequency (tone control) | brighten / darken |
| Resonance | 0–100 | Filter feedback / emphasis; self-oscillates above ~60 (sine at cutoff pitch) | squelch, acid, sine-tone source (lowers volume — raise Output) |
| Envelope Amount | 0–100 | Depth of filter-envelope cutoff modulation | classic filter sweeps |
| Keyboard Amount | 0–100 (75.00 ≈ 1:1 tracking) | Cutoff tracks note pitch | keep timbre even across keys; set 75 for near-perfect tracking |

### Filter Envelope (ADSR)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Attack | 2 ms – >6 s | Rise time to peak | pluck (fast) vs swell (slow) |
| Decay | 2 ms – >6 s | Fall from peak to sustain | shape attack transient |
| Sustain | 0–100 | Hold level while key down (decays to new value while adjusting) | static vs evolving brightness |
| Release | 2 ms – >6 s | Fall after key off | tails |
| Velocity (trimmer, between Sustain & Release) | min–max | Multiplies Envelope Amount by velocity (max = min-velocity gives zero mod) | velocity-sensitive filter sweep |

### Amp Envelope (ADSR)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Attack / Decay / Sustain / Release | as filter env | Volume contour (pre-effects) | overall articulation |
| Volume Curve (trimmer, between Decay & Sustain) | 0–100 | Replaces the hardware VOLUME knob's side-effect on envelope curvature — min = punchy s-curve + shorter decay, max = softer | punchier transients (low) vs smoother (high) |
| Velocity (trimmer, between Sustain & Release) | min–max | Velocity → amp-envelope depth (max = min velocity is silent) | dynamic playing |

### LFO
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Clock \| Rate (switch) | switch | Clock = sync LFO to host Clock; Rate = free | tempo-locked vs free vibrato |
| Rate | ~0.1–30 Hz | Free LFO speed | vibrato, tremolo, PWM |
| Shape | Saw / Triangle / Square (mixable, PW fixed 50%) | LFO waveform(s); add them e.g. saw+square | shape modulation contour |

### Clock
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Clock (rotary) | 8/1 → 1/64, incl. dotted + triplet | Master sync division (4/4 bar based) for LFO, arp, sequencer, Repeat | set rhythmic resolution; type "19" = 1/16 |

### Arpeggiator
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| LFO \| Key \| Clock | switch | Drives arp/seq/Repeat from LFO, one-note-per-keypress (Key), or host Clock | tempo-sync vs manual stepping |
| Up \| Off \| Up/Down | switch | Arp direction (off / up / up-down) | classic arps (needs ≥2 held notes to start) |
| Latch | on/off (global) | Hold arpeggiated notes after release | hands-free arps |

### Sequencer (basic strip; full editor on SEQUENCER page)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| LFO \| Key \| Clock | switch | Step advance source (as arp) | sync sequence |
| On Key \| Always (global) | switch | Always = keeps playing on release (hold-pedal sim); On Key = restart per keypress | looping vs gated playback |
| Rec \| Off \| Play | switch | Step-record / stop / playback; auto-stops at step 32 | record patterns |
| 1+2 \| 2 \| 1 | switch | Choose pattern(s) to record/play | A/B pattern handling |
| Rest | button | Inserts a pause at current step while recording | rhythmic gaps |

### Sequencer page — Pattern data & Edit (per pattern, ×2; up to 32 steps)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Steps | 1–32 | Pattern length before looping | odd-length / polyrhythmic patterns |
| Type cells | note / tied (arc) / pause (X) | Per-step gate; tied extends gate into next step | legato runs, gaps |
| Note cells | -36 … +36 semitones | Pitch offset per step | melodic sequences |
| Vel cells | 1–127 (default 90) | Per-step MIDI velocity (overrides keyboard while running) | accents, dynamics |
| Root | NOTE selector (auto = first recorded note) | Defines "note 0"; a *lower* root transposes the sequence *up* | set transposition reference |
| Edit: Preset | menu | Load/copy/save patterns from `…/u-he/Repro-1/Modules/Pattern` | recall stored sequences |
| Edit: Rotate ◄ ► | buttons | Shift active portion left/right | fix "first note", make variations |
| Edit: Copy / Paste | buttons | Clipboard per pattern (across presets) | reuse sequences |
| Edit: Clear (X) | button | Wipe pattern, reset to step 1 | start fresh |

### Keys / Perform (left-hand controls + mod matrix)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| PB Range (up/down separately) | 0–24, plus 36 / 48 | Pitch-bend range per direction | dive-bombs, subtle bends |
| Bypass FX | on/off (global) | Bypass all effects | A/B treated vs dry |
| Pitch / ModW wheels | mirror MIDI | On-screen pitch + mod wheels (also mouse-adjustable) | manual expression |
| MW Upper / Lower limit | drag | Set range scaled by mod wheel (these are mod targets) | constrain wheel-driven mod |
| Keyboard | 3-octave | Click/double-click (sustain) note entry | quick auditioning |

### PERFORM — Modulation Matrix (MM A: 2 slots shown / 4 total; MM B: 4 more)
| element | options | what it does |
|---|---|---|
| Source (per slot) | Mod Wheel, Pitch Wheel, Control A (def Breath CC#02), Control B (def Expression CC#11), LFO, Clock Phase (ramp), Trigger, Gate, Key Follow 1, Key Follow 2 (no PB), Velocity, Aftertouch, Wavefolder AR, Filter Envelope, Amp Envelope | Modulation input |
| Target (per slot) | LFO Freq; MIDI Glide/Master Tune/MW limits; Filter Env A·D·S·R; Amp Env A·D·S·R; OSC A Freq·Fine·PW; OSC B Freq·Fine·PW; Mod amounts (LFO/OscB/FilEnv); Mixer A/B/Noise-Feedback; Filter Cutoff/Res/KbdAmt/EnvAmt; Jaws Folds/Bias/FoldModDepth; Lyrebird Time/Regen/Mix; ResQ all bands+Q; Drench PreDelay/Decay/Tone/Mix; Sonic Cond Gain/Width/Transient | Destination (FX targets only show when FX active) |
| Slot modifiers | Curve, Rectify, Quantise, Sample&Hold (S+H), Slew Limiter (SL) | Pre-process the mod signal |
| → Curve | very compressed … linear … very expanded (s-curve) | Map source onto an s-curve |
| → Rectify | none, half-wave +/−, full-wave +/−, unipolarize | Rectify the bipolar source |
| → Quantise | integer, steps of 12, overtone series, minor/major scale·chord·series, fifths & octaves | Step the signal (post-depth) — pitch scales |
| → S+H | trigger source: Mod/Pitch Wheel, Control A/B, LFO, Gate, Aftertouch, Wavefolder AR | Sample-and-hold on positive zero crossing (stepped) |
| → SL | none, fast, smooth, slow | Slew/smooth transitions |

### Modulation section (the "3 sources via 2 paths to 5 destinations" panel)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Mod Fil Env / Mod Osc B / Mod LFO (Amount knobs) | 0–100 each | Amount of each source mixed into the Wheel or Direct path | set per-source mod depth |
| Wheel \| Direct (per source) | switch | Route source to the Wheel bus (depth scaled by mod wheel CC#01) or always-on Direct bus | performance vibrato (Wheel) vs constant (Direct) |
| Dest switches: OSC A Freq, OSC A PW, OSC B Freq, OSC B PW, Filter | Wheel/Off/Dir each | Pick which bus drives each of the 5 destinations | wire vibrato, PWM, filter-FM, etc. (note: PW modulation is inverted by design) |

## Effects (5-slot reorderable chain; drag to reorder, click to enable)

### JAWS wavefolder
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Folds | 0–100 | How much of the fold curve is used (input drive; 0 + F-Mod 0 = silence) | West-Coast / FM-like timbres |
| Teeth | 0 / 2 / 4 / 6 (rotary) | Number of folds; 0 = soft saturation (distortion mode) | gentle drive (0) vs rich folding (6) |
| Bias | 0–100 | Shifts fold region; if B-Mod active, depth of own LFO bias mod (opposite per channel = stereo) | move sweet spot / stereo width |
| B-Mod | Off / Min / Med / Max | Bias-modulation LFO rate (Off disables) | animated stereo folding |
| F-Mod | 0–100 | Depth of fold modulation from JAWS' own AR/ASR envelope | dynamic, decaying folds |
| A / R | times | Attack / Release of the wavefolder envelope | shape fold movement |
| Trigger | ASR / AR / LFO | Envelope behaviour (sustaining / one-shot / LFO-triggered) | sustained vs percussive |

### Lyrebird delay (BBD-style)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Sync (upper selector) | Chorus/Short, Unsync/Long, Sync 1/16, Sync 1/4 | Time base (free flanging→2 s, or tempo 1/16–8/1) | chorus/flange vs rhythmic vs ambient |
| Flavour (lower selector) | Clean / Bright / Dark | Tonal character of repeats | match brightness |
| Mode | Echo / Pingpong / Swing / Groove | L/R ratio: mono, alternating, triplet, dotted | stereo movement / rhythmic feel |
| Modulation | Off / Min / Med / Max | Time-modulation LFO rate | analog/tape warble |
| Time | 1–8× (sync) / wide (unsync) | Scales the delay time (modulate for pitch glides) | dial in delay length |
| Mix | 0–100 | Dry/processed ratio | blend |
| Regen | 0–100 | Feedback (max = very long) | number of repeats |

### ResQ resonator / equalizer
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Mode | EQ / RES | Semi-parametric 3-band EQ (Low+High shelves, Mid bell) or triple bandpass resonator | tone-shape vs add resonant tones |
| Frequency: Low / Mid / High | Low 45 Hz–3 k, Mid 55 Hz–9 k, High 130 Hz–10 k | Per-band cutoff (bands overlap/swap freely) | place each band |
| Gain (EQ mode) | ±18 dB (centre-zero) | Cut/boost each band | corrective/creative EQ |
| Volume (RES mode) | positive only | Amplitude of each resonant bandpass | tuned resonances |
| Q / Res | knob | Band width vs cutoff (EQ: applies to Mid only) | narrow ring vs broad shelf |

### Drench reverb (plate w/ pre-delay)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Pre Delay | 0–max | Delay before reverb (0 = further away) | retain dry presence / size |
| Decay | 0–100 (100 = minutes-long) | Reverb tail length | room size |
| Tone | -100 (dark) … +100 (bright), tilt | Surface softness/hardness (wet nearly vanishes at extremes) | match space brightness |
| Dry/Wet | 0–100% | Reverb amount | blend |

### Sonic Conditioner (final glue / fix-it)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Gain | bipolar (centre 0) | Output level; above centre saturates (compensate with Output) | loudness + drive |
| Transient | bipolar | Percussive content: − reduces clicks, + adds punch | de-click or add attack |
| Width | knob | Stereo spread | re-focus bias/delay stereo or widen |

## Use by lens
- **Producer (create):** This is a sound-design / bass-and-lead workhorse. Start from `default`/init or the 1981 Historic bank. Fat unison: detune OSC A/B with Fine Tune for slow beating; thick basses on saw+pulse with Sub from OSC B (Octave −1/−2). Use the onboard sequencer (two 32-step patterns) for instant acid lines and motorik sequences — record with REC, set Clock division, transpose live by playing off the Root. JAWS wavefolder on a triangle or self-resonating filter gives FM-ish metallic timbres; Lyrebird above JAWS in the chain for "interesting" textures. Arp needs ≥2 held notes.
- **Mixing (balance):** Largely a generator, but the FX chain doubles as a channel toolkit — ResQ in EQ mode is a semi-parametric 3-band for carving the patch in the mix, Sonic Conditioner's Transient tames clicky bass-sequences or adds punch, Width re-centres overly wide bias/delay stereo. Watch resonance dropping level (raise Output). Bypass FX to A/B against the raw synth. Per-step velocity in the sequencer shapes groove dynamics.
- **Mastering (finalize):** Not a mastering tool. The only finalize-adjacent control is the global Output (post-FX) for level matching, and Sonic Conditioner GAIN for gentle saturation/glue on the instrument bus — but this is an instrument, keep it on tracks, not the master.

## Notes / gotchas
- **Quirks kept on purpose:** PW modulation signal is *inverted* (mod up → pulse width down) — compensate "the wrong direction". Amp envelope curvature is tied to the Volume Curve trimmer (hardware side-effect). Arp won't repeat a single held note (need ≥2). Repeat/Drone modes interact with envelopes (Retrig turns ties into notes, Repeat removes rests by repeating prior pitch).
- **Global per-instance switches (NOT saved with preset):** HQ, zZz, Bypass FX, arp Latch, sequencer On Key \| Always. They keep their state across preset loads.
- **TWEAKS page = real DSP swaps, not eye-candy-only:** Oscillator models (Ideal / P1 / P5 warmer; P5 inverts pulse → louder saw+pulse but breaks OSC B self-PWM; Bottom emphasizes OSC B triangle). Filter models: Crispy (clear/bright), Rounded (darker, ~semitones lower, different resonance), Driven (novel 3320), Poly (cutoff won't max without upward mod). Envelope models: Normal, High Sustain (attack won't reach sustain >~85), One Shot (gate ignored — percussion), Piano 1/2 (extra true release). Jumpers: LFO invert / DC offset, OSC2 saw inversion, Note Priority (low/high/last), Key-tracking source (key vs key+PB), Microtuning on/off.
- **Microtuning:** Supports .TUN tables (in `…/u-he/Tunefiles/`) and Oddsound MTS-ESP (v1.1.2+).
- **Latency / buffers:** Block-processes in n×16 samples. Base Latency defaults to 16 samples; set it *off* for latency-free operation if your host uses buffers that are multiples of 16 (64/128/256/512). Sequencer wants host buffer ≥128 samples.
- **CPU:** Leave HQ off (only needed for extreme FM) and Sleepy (zZz) on to save CPU.
- **MIDI:** Control A/B default to Breath (CC#02) / Expression (CC#11) but are user-definable. MIDI Learn + MIDI Program Change (MIDI Programs folder = bank 0, sub-folders are banks via CC#0 Bank Select).
- **Presets:** Ships with Repro-5 (poly sibling) via same installer. NKS-ready. 1981 Historic = 20 presets copied from the original hardware manual. `.uhe-soundset` install = drag onto GUI.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
