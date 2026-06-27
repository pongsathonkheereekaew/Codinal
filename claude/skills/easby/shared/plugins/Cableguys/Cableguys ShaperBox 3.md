# Cableguys ShaperBox 3 — Cableguys (modulation multi-effect rack)

| | |
|---|---|
| Vendor / ver | Cableguys · v3.6.2 |
| Type | Modulation multi-effect rack — 9 LFO/envelope-driven Shapers (time, pitch, drive, noise, reverb, filter, flanger/phaser, bitcrush, volume, pan, width) + Compressor + Oscilloscope tools, all 3-band multiband |
| Format | VST2, VST3, AU, AAX (Win 7/8/10/11 64-bit; macOS 10.15+, Intel/Apple Silicon) |
| Source | manual: `Cableguys ShaperBox/Cableguys ShaperBox 3.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
ShaperBox 3 is a serial effects rack holding any combination of nine "Shapers" plus a Compressor and Oscilloscope tool, chained left-to-right (output of each feeds the next). Each Shaper's core parameter (volume, pitch, cutoff, drive, etc.) is driven by an **editable LFO** drawn in a large Wave Editor — freehand points with Soft/Medium/Hard weights, plus Line/Arc/S-Curve pens — and/or a per-band **Envelope Follower** that reacts to the audio's amplitude. Every Shaper is **3-band multiband** (independent LFO/envelope/settings per band) and every LFO can be **Sync'd to host tempo, restarted by MIDI notes, or triggered by audio transients** (internal or external sidechain). The distinctive value: precision drawable rhythmic modulation (sidechain ducking, gating, stutter, filter sweeps, autopan, pitch FX, dynamic distortion) that's fast to dial and reacts to the music, scaling from everyday mix tools to extreme sound design.

## Controls (every param → musical effect)

### Global / rack
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Shaper Bar | — | Holds loaded Shapers; click to edit, drag to reorder, hover for Remove / On-Off (On-Off is automatable) | Reorder = different sound (filtered stutter vs stuttered filter) |
| Add Shaper (+) | — | Opens Shaper Selection Screen; add any of 9 Shapers + 2 Tools (one of each max) | Building the chain; demo unowned Shapers |
| Master Mix | 0–100% | Global dry/wet — internally offsets every band's Mix of every Shaper; always click-free, automatable, no multiband phasing | Quick dry/wet of whole rack; morph complex chains |
| Master Bypass | on/off | Switch between full processed and true dry signal | A/B the whole rack |
| Per-Shaper Mix | 0–100% | Dry/wet of that Shaper (per band in multiband). On Volume/Pan/Width = "amount" (flattens curve); on others = blend dry/wet | Dial back any single effect |
| Preset Library | — | Full preset browser (Categories + Packs + Search + filter-by-Shaper dot, Favorites ♥); loads complete setup incl. Wave Palette | Recall / inspiration; SB1 & SB2 legacy presets via Show Legacy |
| Preset step `<` `>` | — | Step through presets matching current filter | Audition presets fast |
| Scaling | 75–200% | Resize GUI | Match monitor |
| Anti-Click Trigger Smoothing | on/off | Adds 6ms lookahead to smooth MIDI/audio retrigger clicks (Volume); off = lower latency | Disable to cut latency if no clicks heard |
| Reserve DriveShaper Latency | on/off | Always imposes DriveShaper's 16-sample latency so it can be bypassed click-free | Helps DAWs with flaky PDC (Live, Logic) |
| High Contrast | on/off | Boosts GUI contrast | Bright rooms |

### LFO Wave Editor & LFO Settings (shared by all Shapers)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Wave points | Soft / Medium / Hard | Drawable breakpoints: Hard = tight angle (precise, may click), Medium = rounded (instant jump, no click), Soft = smooth curve | Build any LFO shape; right-click point to change weight |
| Pens (Line / Arc / S-Curve) | — | Click to stamp shapes, click again to repeat, click-drag to size; always snap to grid | Fast stepped/rhythmic patterns |
| Pointer tool | — | Click=line, drag=curve, click breakpoint=toggle line/curve, drag=move, dbl-click=delete, Shift-click=soften, Ctrl-click=add soft point | Detailed freehand editing |
| Snap to grid | on/off | Snaps points to grid (global except PitchShaper) | On for rhythmic, off for freeform |
| Triplet grid | on/off | Triplet snap | Shuffle/swing |
| Randomize | — | Random positions/weights to all or selected points | Happy accidents |
| 2x / Move L-R | — | Double-time (Shift = triple) selection; shift wave/selection left-right (Shift = 1/16 grid fine) | Tighten sidechain timing; tempo-double a pattern |
| Delete points / Undo-Redo | — | Remove all/selected; per-Shaper/band undo | — |
| LFO Mode | Bars/Beats · Hertz/ms · Pitch | Loop synced to note value/bars; or free-run in Hz (Speed); or LFO pitch tracks MIDI note (ring-mod-style) | Pitch mode → audio-rate FM/ring effects |
| Loop Length | 1/128–32 Bars (Triplet/Straight/Dotted) | Length of synced LFO loop (1/4, 1/2, 1 = quick buttons) | Set rhythmic period |
| Speed | 0.02–5.24kHz | Free-run rate in Hz mode | Non-synced sweeps, audio-rate mod |
| Transpose | -3 to +3 octaves | Transpose incoming MIDI in Pitch mode | AM/FM-type effects |
| Smooth | 0–100% | Progressively rounds hard angles of final modulation (Modulation Trace shows it); high values at fast rates flatten the curve | Reduce click/pop; or creative softening |
| Trigger Mode | Sync / MIDI / Audio | Sync to project transport; restart on MIDI note; restart on audio transient | Choose how LFO is driven |
| Looping | On / Off (1-Shot) | Loop continuously (resets on trigger) vs play once then hold at End | 1-Shot for one-off envelopes/risers |
| End Marker | — | Where 1-Shot LFO "stops" and freezes | Shape one-shot tail |
| LFO Link | on/off | Links Mode/Length/Trigger across all bands (control via Mid band) | Keep bands in sync; unlink for cross-rhythm |
| Wave Presets | per-Shaper categories | One-click LFO shapes (Basic/Hit/Pump/Sweep/Rhythm 1&2/Favorites etc.); Shift = scale to existing wave height | Instant starting shapes |
| Wave Palette (MIDI Switch) | up to 9 slots | Store 9 LFO waves switchable live via MIDI notes C#–A (or automation) — turns SB into a performance/wobble instrument | Live wave-switching, dubstep wobble, glitch |
| Modulation Trace | display | Animated curve behind LFO = actual combined LFO+Envelope+Smooth output | See real modulation vs drawn LFO |

### Audio Trigger Setup (global, when any Shaper in Audio mode)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Threshold | dB | Transient level needed to fire LFO | Ignore quiet hits |
| Sidechain Input | on/off | Use external track (inputs 3&4) as trigger | Kick-triggers-bassline ducking |
| Monitor Input | on/off | Listen to the filtered/routed signal the detector hears | Tune the High/Low filter surgically |
| High/Low Filters | freq range | Restrict trigger detection band (e.g. 200–300Hz for snare) | Avoid mistriggers from bass/hats |
| Algorithm | Drums / General / Complex | Transient detection: Drums (percussive), General (all-round), Complex (most sensitive, full mixes) | Match source material |
| Detail | sensitivity | Finer detection (fast rolls, ghost notes) | Busy material |
| Trigger Shift | ±4ms | Nudge LFO restart ahead/behind detected transient | Fix timing on awkward sources |
| MIDI Out | note | Output MIDI note on each detected transient | Trigger other plugins / print to MIDI |

### Multiband Editor (every Shaper + Compressor)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Split sliders | freq | Add low/high band by dragging Split point; sets crossover | Bass-only sidechain, treble-only crush |
| Slope | 6 / 12 / 24 dB/oct | Crossover steepness (hover spectrum to set) | Tighter vs gentler band separation |
| Solo (per band) | on/off | Solo a band (mutes others) | Tune one band in isolation |

### Envelope Follower (DriveShaper, PitchShaper, FilterShaper Core, CrushShaper, NoiseShaper, PanShaper, WidthShaper — per band)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Envelope On | on/off | Enable dynamic amplitude-driven modulation | Make filter open on each snare, etc. |
| Attack | 0.010–200ms | How fast envelope rises to peaks (fast=vertical, slow=lags) | Let transients through (slow) vs grab them (fast) |
| Hold | 0–500ms | Holds peak before release | Off-beat bounce, avoid short-time distortion |
| Release | 50ms–2.00s | How fast envelope falls back | Fast=rides cycles, slow=smooth |
| Adaptive Release (A) | on/off | Dual-stage release; faster on transients | Reduce pumping |
| Threshold | -inf to high dB | Gate — ignores signal below level | Follow only loud hits (kick/snare not hats) |
| Amount | ±200% | Strength + direction of modulation (negative inverts) | Filter open (+) vs close (−) per hit |
| Depth | x2 / x4 / x8 | Extends Amount range to ±200/400/800% | When more depth needed (high attack, filtered SC) |
| Shift | offset | Moves whole modulation curve up/down without changing Amount | Reposition resting point (e.g. keep synth audible) |
| Add / Multiply | mode | LFO+Env combine: Add (offset) or Multiply (LFO scales Env depth) | Multiply: rising LFO ramps up an env-following filter over bars |
| Band / Free | mode | Env reacts to band freqs (Band) or independent High/Low Env Filter (Free) | Free: isolate snare freqs to trigger |
| High/Low Env Filters | freq range | Frequencies the envelope listens to (Free mode) | Surgical envelope triggering |
| Sidechain | on/off | Envelope listens to external track (inputs 3&4) | Duck bassline from kick on another track |
| Solo Sidechain | on/off | Monitor exactly what envelope hears (routed to output) | Set up filtering/sidechain |
| Follow / Duck | mode | (NoiseShaper, ReverbShaper only) noise/reverb present when signal present (Follow) or in the gaps (Duck) | Duck = reverb swells in vocal gaps |

### TimeShaper 3 (multiband stutter / scratch / tape-stop / reverse — LFO-only, no slider/envelope)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Time (LFO) | — | LFO scrubs a buffer back/forward; Y = time offset | All time manipulation drawn as LFO shape |
| Time Range | Linked (As LFO Length) / Beat (1/2/4/8 Bars) / Fine (2.5/10/20ms) | Max Y-axis time offset: Linked=loop length, Beat=larger jumps, Fine=tiny fluctuations | Fine = tape wow/vibrato/chorus (+dry/wet) |
| Step Mode | Smooth / Instant | Smooth = small fade-in before hard steps (no clicks, default); Instant = jumps instantly (may click) | Smooth for stutters; Instant for source-dependent edits |

### PitchShaper (4-octave pitch + formant shift)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Pitch (LFO/slider) | ±24 semitones (Shift=cents) | Transpose; dbl-click retains cents offset (unlike others) | Melody/bassline change, risers, drops |
| Mode | Complex / Vocals / Drums / Vintage | Algorithm (global all bands): Complex (any/polyphonic, preserves transients, NO processing at 0st), Vocals (mono voice + Formant), Drums (percussive, preserves punch + Formant), Vintage (gritty cyclic) | Complex=default safe; Vocals/Drums add Formant; Vintage=lo-fi |
| Grain Size | Short/Medium/Long (Complex) or continuous (Vintage) | Granular grain size; longer reduces low-end artifacts | Increase if deep bass sounds rough; Vintage long=flanger-y |
| Formant | ±semitones | Shifts resonance/timbre independently (Vocals/Drums, when Formant Link off) | Transmogrify vocals, gender-bend |
| Formant Link | on/off | Formant follows Pitch (tape-style) or independent | Off = independent pitch/formant |
| Density | amount | Fills micro-gaps when Formant exceeds Pitch (Drums); preserves punch | Reduce for gritty textures |

### DriveShaper 2 (modulated distortion)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Drive (LFO/slider) | — | Main saturation amount into distortion circuit (auto gain comp) | Rhythmic/dynamic distortion |
| Input Gain | -12 to +36dB | Level into distortion (aim red meter mostly-full) | Balance drive |
| Output Gain | +12 to -36dB | Compensate output level | Gain-stage |
| Style | 12 types | Soft/Smooth/Hard Clip, Soft/Hard Square, Soft/Hard Rectify, Skew/Sine/Triangle/Saw/Extreme Fold | Pick distortion character |
| Grip | amount | Makes quiet parts quieter as raised | Stop ambience/noise being boosted |
| Push | amount | DC offset → asymmetric distortion (Rectify/Wavefold) | Octave-up / characterful asymmetry |
| Accent | scale | Emphasize/de-emphasize LFO/Env peaks (scales gain comp) | Add punch or tame jumpy mod patterns |
| Tone | bipolar LP/HP | Filter mixed in as Drive rises | Tame low-end boost / harsh harmonics |

### NoiseShaper 2 (adds its own noise layer — only Shaper that creates sound)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Type | 60+ noises | Noise / Organic / Analogue / Cymbal / Percussion categories (downloaded on first launch); + user import | Vinyl crackle, tape hiss, drum body, ambience |
| Noise (LFO/slider) | -inf to 0dB | Noise volume (designed for use w/ Envelope, which is on by default) | Dynamic noise layering |
| Trim | +12/-48dB | Gain at output of noise (headroom at LFO top / boost for Env) | Gain-stage noise |
| Pitch (LFO/slider) | ±24 semitones | Tune the noise (esp. Cymbal/Percussion bodies) | Tune crashes/perc to track |
| HP/LP Filter | freq range | Shape noise frequency range (HP defaults 120Hz; drag to 20Hz for sub) | Filter the noise itself (use this, not Bands) |
| Mono Noise | on/off | Mutes R, pans L to center | Avoid phase issues / mono-compat |
| Noise Only | on/off | Mute input, hear only noise | Sound design / split noise to its own track |

### ReverbShaper (convolution reverb + modulated send/return)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Reverb | IR library | Hall / Epic / Special / Mechanical / Room / Non-Linear categories; + user IR import | Pick space; per-band independent IR |
| Send (LFO/slider) | amount | Dry signal sent to reverb | Rhythmic/ducked send modulation |
| Pre-Delay | ms (sync at max) | Offset reverb start (separation/clarity; syncs to musical values near max) | Transient clarity; rhythmic pre-delay |
| Decay | time | Reverb tail length | Set space size feel |
| Gated | on/off | Decay then abrupt cut (Decay sets gate time) | Gated-verb drum effect |
| Width | 0–200% | Stereo width of wet (side level) | Mono to super-wide reverb |
| Size | resample | Resample IR — length/timbre/scale | Re-scale the space |
| Volume (LFO/slider) | level | Reverb output level | Modulate reverb level |
| Clear Tails | on/off | Clears reverb tail at Volume-LFO 0% hard points (green dot marks) | Stop overlapping tails clashing between chords |
| Dry/Wet | dry + wet levels | Send/return style — dry & wet set independently (left=dry, right=wet) | Raise reverb without dropping dry |

### FilterShaper Core 3 (3-band multimode filter, cutoff + resonance modulation)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Filter Type | LP / HP / BP / Notch / Peak | Filter shape | Sculpt frequencies |
| Flavor | Clean / Warm | Clean=transparent, Warm=analogue Sallen-Key (enables Dist/Safe Res/Hard Dist) | Warm for character/self-osc |
| Slope | 6 / 12 / 24 dB/oct | Roll-off steepness | Gentle vs steep/powerful |
| Cutoff (LFO/slider) | 20.6Hz–21.1kHz | Filter cutoff freq | Main filter sweep |
| Resonance (LFO/slider) | amount | Emphasis around cutoff / widen Notch cut | Wah, whistle, self-osc |
| Stereo | ±60 semitones | Offsets cutoff opposite directions per channel | Wide stereo (esp. Notch/Peak/BP) |
| Dist | amount | Saturation in resonance feedback (Warm types) | Whistle (low) vs smoothed/saturated (high) |
| Safe Res | on/off | Caps resonance to "safe"; disable to allow self-oscillation (Warm) | Self-osc tones (WARNING: loud) |
| Hard Dist | on/off | Resonance distortion → hard clip | More aggressive resonance |

### LiquidShaper (flanger / phaser, center + feedback modulation)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Type | Off / Flanger / Phaser | Off=bypass band; Flanger=short delay comb (harmonic peaks/notches); Phaser=all-pass (unrelated peaks) | Jet-flange vs rich phasing |
| Mode | + / − | Feedback polarity: rich peaks (+) vs hollow notches (−) | Tonal character |
| Stages | 2 / 4 / 6 / 8 | Number of all-pass filters (Phaser) — pairs = peaks/notches | More stages = more notches |
| Center (LFO/slider) | freq | Center freq where peaks/notches generated (Flanger above / Phaser around) | Main sweep |
| Stereo | ±60 semitones | Center offset opposite per channel | Wide stereo movement |
| Feedback (LFO/slider) | amount | Feeds delay/all-pass back into itself | Intensify peaks/notches; robotic |

### CrushShaper 2 (bitcrush + sample-rate reduction)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Bits (LFO/slider) | 16-bit (top) to 1-bit; "Max"=bypass | Bit-depth reduction | Crunchy lo-fi; "Max"+unmodulated passes full res |
| Push | DC offset | DC offset before bit reduction (removed after) — preserves low-level/tails | Restore sustains/tails |
| Dither | amount | Reduces quantisation distortion (adds noise) | Greater dynamic range/preservation |
| Resample (LFO/slider) | 44.1kHz (top) to 8.82Hz | Sample-rate reduction | Vintage sampler grit; sizzle |
| Jitter | amount | Random SR fluctuation around Resample | Emulate vintage sampler instability |
| Pre-Filter | amount | LP at ~half Resample (virtual Nyquist) | Reduce aliasing |
| Treble | 0–100% | Fixed HF shelf at output as Resample/Bits drop (100%=unfiltered) | Control lo-fi harshness |

### VolumeShaper 7 (volume modulation — sidechain / gating / tremolo)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Volume (LFO/slider) | -inf to 0dB (graph %: -6dB center, 0dB top) | Gain modulation | Sidechain ducking, gating, tremolo, transient edit |
| Trim | ±24dB | Output gain of Volume module | Headroom at LFO top / boost transients |
| Show External Sidechain | on/off | Overlay external SC waveform on input waveform | See SC positioning vs signal |
| *(no Envelope)* | — | Envelope-driven volume = a compressor → see Compressor tool | — |

### PanShaper 4 (stereo pan — level + Haas)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Pan (LFO/slider) | L–R; Y = pan pos / Haas ms | Pan signal (level- and/or delay-based) | Autopan, rhythmic panning |
| Pan Law | 3/4.5/6/0dB (Stereo Balance) or Combined | Balance (reduces one channel, compensate by 3/4.5/6dB; 0=none) vs Combined (pans both, stops hard-pan disappearing) | Balance for most sources; Combined to keep hard-panned audible |
| Pan/Haas | 100%/0% to 0%/100% | Blend level-pan vs psychoacoustic Haas delay panning | Mix for wide imaging |
| Haas Range | 0.00–40.0ms | Max Haas delay (≈2ms=realistic, higher=larger-than-life) | Width amount (check mono!) |

### WidthShaper 3 (stereo width — side-signal only, mono-safe)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Width (LFO/slider) | 0% (mono) – 200% | Stereo width (modulates only side of M/S → never harms mono-compat) | Stereo risers, mono bass, dynamic width |
| Gain | boost/attenuate | Compensate level change from width change | Match perceived loudness |

### Compressor (Tool)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Threshold | dB | Level above which compression starts | Catch loud peaks vs squash everything |
| Ratio | 1:1–100:1 | Amount of reduction (2:1 default; 100:1=brutal limiting) | Gentle glue vs hard limiting |
| Attack | 0.010–200ms | Speed to full reduction | Snap (short) vs let pluck through (long) |
| Hold | 0–500ms | Holds full compression before release | Emphasize transients; specific shapes |
| Release | 50.0ms–2.00s | Speed to let go | Pumping vs smooth |
| Adaptive Release (A) | on/off | Faster release on transients | Reduce pumping |
| Makeup | dB (Auto via A) | Output gain to compensate; Auto matches loudness | Accurate A/B; manual offset |
| Band/Free + High/Low Filters + Sidechain + Solo SC | — | Same detection-circuit filter/sidechain options as Envelope Follower | De-essing, ignore bass, external SC, multiband comp |
| Mix | 0–100% | Parallel (NY-style) compression | Blend compressed + dry |

### Oscilloscope (Tool)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Length / Trigger | Sync / MIDI / Audio | Display time range + trigger (Pitch mode tracks MIDI note) | Analyse waveforms in sync |
| Zoom | dB | Scale vertically | See quiet / tame loud waveforms |
| Mode | Left / Right / Both / Split | Channel display | Inspect channels |
| Show SC | on/off | Overlay external sidechain waveform | Compare SC vs signal |
| Freeze | on/off | Pause display | Inspect a moment |
| Clipping indicators | display | Red pixels when input >0dB (visual only, no clipping done) | Spot clipping risk |

## Use by lens
- **Producer (create):** This is the creative engine. TimeShaper for stutters/half-time/reverse/tape-stop/scratch; CrushShaper + DriveShaper for lo-fi grit and rhythmic distortion; PitchShaper for risers/drops/transmogrified vocals; NoiseShaper to layer vinyl/tape/ambience or build drum-hit tails; FilterShaper Core + Wave Palette MIDI Switch for dubstep wobble and live wave-switching; LiquidShaper for jet-flange/phaser movement; PanShaper/WidthShaper for stereo motion and risers. Draw LFOs freehand or stamp with Pens, set 1-Shot for one-off FX, trigger off transients to make any sound react to the groove.
- **Mixing (balance):** VolumeShaper is the precision sidechain-ducking / gating / trance-gate staple — multiband to duck only the bass under the kick while keeping top-end groove. Compressor tool for transparent multiband dynamics, de-essing (Free filter on sibilance), and parallel glue. FilterShaper Core to carve or rhythmically open elements; WidthShaper to widen highs while keeping bass mono (mono-safe by design); NoiseShaper multiband to enhance only a snare in a loop. Envelope Follower everywhere for dynamic, music-reactive moves; external sidechain (inputs 3&4) to duck/trigger from another track.
- **Mastering (finalize):** Use sparingly and surgically. Multiband Compressor tool to tame a jumpy resonance or add gentle glue on a specific band (low ratio, Auto Makeup). FilterShaper Core (Clean, gentle slope) for subtle tonal correction. WidthShaper for safe stereo adjustment (never compromises mono-compat). Master Mix for overall parallel blend. Most modulation/Shaper effects are too overt for a master bus — reach for static, low-amount, single-band corrective settings only.

## Notes / gotchas
- **Serial chain, order matters:** Shapers process left→right; reorder by dragging in the Shaper Bar. One instance of each Shaper/Tool max.
- **Trigger modes (per Shaper, per band when unlinked):** Sync (tempo), MIDI (note restarts LFO; note C is reserved for MIDI Trigger so Wave Palette MIDI Switch uses C#–A), Audio (transient-triggered; set up in Global Audio Trigger panel).
- **Multiband everywhere:** every Shaper + the Compressor is 3-band with fully independent LFO/envelope/settings/IR/noise per band. NoiseShaper exception: to filter the noise use its own HP/LP, not Bands (Bands only affects which input freqs trigger it).
- **Envelope-volume = Compressor:** VolumeShaper has no Envelope Follower by design — that's literally a compressor, hence the separate Compressor tool.
- **PitchShaper Complex @ 0st = zero processing** (totally transparent passthrough). Mode is global across bands. Dbl-click Pitch keeps cents offset (unlike other Shapers which return to center).
- **External sidechain** uses plugin inputs 3 & 4 (route in your DAW); available to every Envelope Follower, the Compressor, and Audio Trigger.
- **Latency / lookahead:** Audio Trigger +14ms (24ms with Complex algo); VolumeShaper +6ms (Anti-Click Smoothing in Audio/MIDI); PitchShaper +25ms Complex / +50ms Vocals / +60ms Drums (Vintage = 0); DriveShaper +0.36ms oversampling. All PDC-compensated by the DAW. Disable Anti-Click Smoothing / Reserve DriveShaper Latency to minimize where needed (some DAWs like Live/Logic have flaky PDC).
- **User content:** NoiseShaper noises download on first launch (internet required) and support WAV/AIF/AIFF/FLAC user import (≤100MB, ≤192kHz, one subfolder tier, 10k max); ReverbShaper supports user IRs (WAV/AIF/AIFF, ≤30MB). User noises/IRs save only the file path in presets — relocating breaks them (Type/Reverb menu turns red).
- **Wave Palette** stores up to 9 LFO waves in the preset, switchable live via MIDI (C#–A) or automation (any wave into any LFO) — turns SB into a performance instrument.
- **Presets:** load complete setups (all Shapers + Wave Palette). Cloud-synced library (Sync button); SB1/SB2 legacy presets via Show Legacy Presets. Favorite Waves are NOT cloud-synced — export/import via Main Menu when moving machines.
- **Automation target indicators:** hold Cmd-Ctrl-Opt (Mac) / Start-Ctrl-Alt (Win) to highlight every automatable control in the visible Shaper. Shaper On/Off and most params are automatable; settings in the top-bar section are not modulatable but are automatable.
- **FilterShaper Core** uses zero-delay-feedback DSP — clean even at audio-rate LFO (up to 5.24kHz) and self-oscillation; built to be pushed to extremes.
- **Demo mode:** unowned Shapers run in demo to audition.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
