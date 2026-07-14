# FabFilter Twin 3 — FabFilter (virtual-analog subtractive synthesizer)

| | |
|---|---|
| Vendor / ver | FabFilter · Twin 3 |
| Type | Synth — virtual-analog / subtractive synthesizer (instrument) |
| Format | VST, VST3, CLAP, AU (macOS only), AAX Native |
| Source | manual: `FabFilter Twin 3/FabFilter Twin 3.pdf` · deep spec: `easby-programming/plugins/Twin3.md` (RE'd — Programmer only) |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Twin 3 is FabFilter's virtual-analog subtractive synthesizer: up to four vintage-voiced, analog-drift oscillators (saw / square / triangle, "Pure" or warm variants, plus sine and white/pink noise) feeding up to four high-quality self-oscillating filters (LP/HP/BP/bell/shelf/notch, 11 character styles with internal drive, 6–48 dB/oct), a central ADSR amp envelope, and a built-in six-unit FX section (reverb, delay, chorus, phaser/flanger, drive, compressor). Its signature is a fast **drag-and-drop modulation system**: any of the XLFOs (16-step sequencer LFOs), envelope generators, envelope followers, MIDI sources and XY controllers can be dropped onto almost any parameter — including the FX. A full preset browser, arpeggiator and microtuning round it out. The distinct part is the "Twin" character (warm, slightly imperfect oscillators + characterful saturating filters) combined with a deep-yet-effortless modulation matrix.

## Controls (every param → musical effect)

### Oscillators (up to 4 — add with `+`, delete with `x`)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Waveform | Saw / Square / Square Pure / Triangle / Triangle Pure / Sine / White noise / Pink noise | Selects the wave. Saw = bright/full, ideal for filtering; Square = metallic round (PWM-able); Square Pure = clean digital square (PWM-able); Triangle = soft warm; Triangle Pure = pure triangle (more harmonics); Sine = pure no-harmonics; White/Pink noise = full/​darkened noise | Pick the raw harmonic palette per layer; "Pure" for cleaner/digital, non-Pure for warmer vintage |
| Enable | on/off | Mutes/unmutes that oscillator | A/B an oscillator's contribution |
| Pulse Width | even square → infinitely thin (inaudible) | Duty cycle of Square / Square Pure only; modulation target | Classic PWM movement (modulate with an XLFO) |
| Detune | ±1 octave (±12 st), extra-sensitive near 0 | Per-oscillator fine/coarse pitch; type "0.5 octaves", "1 semitone", "50 cents"; mod target | Fatten with slight detune; tune intervals for stacks |
| Scale | −1 to +3 octaves | Transposes that oscillator in whole octaves relative to master tune | Build octave stacks / sub layers |
| Sync | 1 (off) .. 4 (hard sync) | Hard-sync: squeezes phases into one audible phase → metallic, formant-rich; mod target | Aggressive sync sweeps (modulate Sync for the classic effect) |
| Phase Sync | on/off (MIDI icon) | Resets phase to half-waveform on each note-on → sharp consistent attack; can introduce clicks on sustained sounds | On for tight percussive/bass attacks; off normally |
| Level / Pan | inner = level (−inf..0 dB), outer ring = pan (−1..+1) | Per-oscillator volume and stereo position; both mod targets | Balance the oscillators; spread them in stereo |
| Ring modulation 1·2 / 3·4 | on/off (`*` button between osc pairs) | Ring-modulates the pair (sum & difference frequencies) → bell-like / metallic overtones | Inharmonic / bell / FM-ish textures |

### Master / global
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Master Tune | global frequency offset; mod target | Tunes all oscillators together | Detune the whole patch; vibrato (modulate it) |
| Scale | 32' / 16' / 8' / 4' | Transposes all oscillators by full octaves | Set the patch's octave register |
| Portamento | 0 → long glide | Glide between notes; works in poly too; mod target | Smooth solos, bass slides, sliding chords |
| Portamento Legato | on/off | Glide only applies to notes after the first held note | Legato-only glide for expressive playing |

### Filters (up to 4 — interactive display; create by dragging the yellow curve, double-click background)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Shape | Low Pass / High Pass / Band Pass / Bell / Low Shelf / High Shelf / Notch | Filter type; shape of a new curve is auto-guessed from where you click | Sculpt the spectrum; bell/shelf for EQ-style tone shaping |
| Slope | 6 / 12 / 24 / 48 dB/oct | Steepness (1/2/4/8-pole); mouse-wheel over curve adjusts | Gentle (6/12) for musical sweeps, steep (24/48) for surgical/resonant |
| Frequency (cutoff) | full audio range | Corner/center frequency; drag dot, type "100", "2k", "A4", "C#2+13"; mod target | The main tone control / filter sweeps |
| Peak (resonance) | bipolar (damped ↔ resonant, up to self-oscillation) | Emphasis at cutoff; negative damps, positive resonates → self-oscillating whistle near max; mod target | Squelchy/acid sweeps, self-osc tones, or tame with negative peak |
| Pan (frequency panning) | per-filter L/R offset | Filters L and R channels at different center freqs (stereo balance of the filter); mod target | Stereo filter movement, width tricks |
| Style | FabFilter One / Smooth / Raw / Hard / Hollow / Extreme / Gentle / Tube / Metal / Easy Going / Clean | Character/nonlinearity of the filter (internal drive & saturation). Clean = linear no distortion; Tube/Metal/Raw/Extreme/Hard add drive, low-end self-osc, whistle, grit | Dial the filter's "vibe" — clean EQ vs gritty analog drive |
| Filter Routing | Serial / Parallel / Per Oscillator | Serial = osc → filter1 → filter2 (cascade); Parallel = filters in parallel then summed; Per Oscillator = osc1→filter1, osc2→filter2, etc. | Cascade for steep/combined tone, parallel for blended bands, per-osc for split processing |
| Frequency Offset (large knob) | ±, mod target | Shifts cutoff of ALL filters at once | Global filter sweep across any preset; modulate for whole-patch movement |
| Peak Offset (large knob) | ±, mod target | Shifts resonance of ALL filters at once | Global resonance push |

### Main EG (central ADSR amplitude envelope) — also see Envelope generator (mod EGs)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Delay | time | Wait before attack starts after note-on | Staggered/swelling onsets |
| Attack | very short → long (lowered minimum in v3) | Time to reach peak level | Short = percussive, long = pads |
| Hold | time | Holds peak before decay | Plucky sustain shaping |
| Decay | time | Fall from peak to sustain level | Pluck/key decay |
| Sustain | volume level (−inf..0 dB) | Level held while key is down | Body of held notes |
| Release | time | Fade after key release | Tails; short = tight, long = lush |
| Attack / Decay / Release Slope | curve −/+ (drag the slope dot) | Curve shape per segment (linear ↔ log/exp) | Snappy vs smooth feel per stage |

### FX section (six units, top-right; each has Amount knob + Enable; click center for per-effect panel & presets — Drive has no panel)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Reverb** Amount | mix | Wet level of the vintage reverb; mod target | Add space |
| Reverb Time | 200 ms (small room) → 20 s (cathedral) | Decay length; mod target | Tiny ambience to huge wash |
| Reverb Brightness | 0..100 % (dark → bright) | Tone of the tail; mod target | Dark vintage vs shimmering |
| Reverb Predelay | initial delay before reverb | Sense of space; modulate it → analog tape-style pitch modulation (chorus-like reverb); mod target | Push reverb back; modulate for chorused verb |
| **Delay** Amount | mix | Wet level of the stereo delay; mod target | Echo level |
| Delay Time | tempo-syncable (free or host sync) | Echo spacing; two time fields (L/R), can be synced; mod target | Rhythmic echoes / slap |
| Delay Feedback | up to runaway (>unity) | Number of repeats (self-oscillates high); mod target | Dub-style regenerating trails |
| Delay Offset / Time Pan | per-tap | Stereo offset & time panning of the delay; mod targets | Ping-pong / stereo spread |
| Ping Pong | Off / L-R / R-L | Bounces echoes across the stereo field | Classic ping-pong delay |
| Delay Filters (×4) | full filter display (same specs as main filters: shape/style/slope/freq/peak/pan, routing) | EQ/shape the delay repeats; freq/peak/pan are mod targets | Filtered/dub delays, tone-shaped echoes |
| **Chorus** Amount | mix | Wet level; mod target | Stereo widening |
| Chorus Mode | Single / Double | Single = one tap/channel, Double = two taps (richer) | Subtle vs lush widening |
| Chorus Rate | ~0..10 Hz | Modulation speed; mod target | Slow shimmer vs fast warble |
| Chorus Depth | 0..100 % | Modulation depth → stereo decorrelation; mod target | Width amount |
| Chorus Delay | ~0.5..30 ms | Base delay time of the chorus; mod target | Thicken / detune character |
| **Phaser/Flanger** Mode | Phaser / Flanger | Phaser = allpass notches; Flanger = short modulated delay w/ feedback | Swirl (phaser) vs jet/metallic (flanger) |
| Phaser Amount | mix | Wet level; mod target | Effect strength |
| Phaser Rate | speed | Sweep rate (1:1 with display); mod target | Slow sweep vs fast wobble |
| Phaser Depth | depth | Sweep range / obviousness; mod target | Subtle to pronounced |
| Phaser Feedback | ± | Resonance/intensity of notches; mod target | More pronounced, ringing |
| Phaser Shift | L/R phase offset | Offsets modulation phase between channels → wider | Stereo-widen the swirl |
| **Drive** Amount | 0..100 % (1-knob; routing button) | Lower half = subtle saturation, upper half = obvious drive / amp distortion (folds at extremes); mod target | Warmth → screaming distortion |
| Drive Routing | Pre FX / Post FX | Drive before all other FX, or after (just before final compressor) | Distort the raw synth vs the whole FX'd signal |
| **Compressor** Amount | mix | Wet/intensity of compression; mod target | Glue, control, pumping |
| Compressor Threshold | level (input meter shown) | Level above which it compresses; mod target | Set how much it grabs |
| Compressor Attack | very fast → slow; mod target | How fast it clamps | Punchy (slow) vs tame transients (fast) |
| Compressor Release | very fast → subtly slow; mod target | Recovery time | Pumping (fast) vs smooth |
| Compressor Auto Gain | on/off | Automatic make-up gain from threshold/attack | Keep level constant while dialing |

### Modulation sources (add via `+` in the modulation section; drag the source's drag-button onto any target)
| source | key controls | what it does |
|---|---|---|
| **XLFO** ×up to 6 | Frequency (0.02–500 Hz free, or sync 16..1/64 → becomes **Offset** = tempo multiplier ½..2×), Balance (duty of first/last halves), Glide (global inter-step smoothing −1..+1), Phase Offset, MIDI sync (Retrigger / Legato), Snap (turns it into a 2-octave arpeggiator), Source Level (−200..200 %). Per step: Value, Glide, Curve (Linear/Sqr/Sqrt/Sine), Random | 16-step sequencer LFO — the "waveform" is the steps. Steps freely added/removed. From classic LFO to step sequences to random S&H |
| **Envelope Generator (EG)** ×many | Delay, Attack, Decay, Sustain, Hold, Release + per-segment Slope; Trigger input (MIDI or side-chain), Threshold (mod target; meter shown), Range (0..1 or centered around 0), Source Level | ADSR mod envelope triggered by MIDI or external side-chain audio level |
| **Envelope Follower (EF)** ×many | Attack, Release, Mode (Envelope / Transient), audition button, Source Level | Tracks the side-chain input's loudness (Envelope) or hits (Transient detector) into a mod signal |
| **MIDI Source** ×up to (many) | Input (Mod Wheel / Pitch Bend / Velocity / Aftertouch / KB Track / Controller), Controller number, Range (Negative −1..0 / Centered −1..1 / Positive 0..1), Response curve (Linear/Exp/Log/Sqr/Sqrt/Sine), Source Level | Turns MIDI data into modulation; sustain pedal (CC64) auto-applied. (VST3: no per-note aftertouch) |
| **XY Controller / Slider** ×up to 6 | Mode (XY 2-D / Slider 1-D), Range (bipolar −1..1 / unipolar 0..1); XY has two outputs (X & Y drag buttons), Slider has one (Y) | Hands-on macro pad; great to assign to many targets and control by hand or MIDI Learn |

### Modulation slot mechanics
| control | what it does |
|---|---|
| Drag-and-drop connection | Drag a source's drag-button onto any highlighted target; a slot is created |
| Level slider (per slot) | Amount of modulation; Shift = fine, Alt/Cmd-click = reset |
| Invert (+/− button) | Flips the modulation polarity for that slot |
| On/off (per slot) | Temporarily disable a slot |
| Source/target dropdown | Re-route a slot's source or target without re-dragging |
| Slot → slot | A slot's Level is itself a target → modulate one slot's depth with another source (meta-modulation; shown indented) |
| Source Level | Per-source output scaler (−200..200 %) — scales everything that source drives |

### Arpeggiator (bottom-bar panel)
| control | range | what it does |
|---|---|---|
| Enable | on/off (center of Rate) | Auto-plays held notes on tempo |
| Rate | 0.25–20 Hz | Arp speed (free) |
| Sync | host-tempo divisions | Tempo-locked rates; Rate becomes ×0.5..2 multiplier |
| Retrigger | on/off (MIDI icon) | On = restart pattern on first key; Off = follow DAW timeline |
| Groove | offsets every 2nd note | Swing / dotted-triplet feel |
| Legato | short → full | Note length |
| Transpose | Off / 1 / 2 octaves | Adds octave-shifted repeats |
| Note Order | Up / Down / Up÷Down / As Played / Random | Sequence order of held notes |
| Latch | Off / Held / Full | Off=only while held; Held=remember+add; Full=remember & keep after release |
| Lock | on/off | Keep arp settings when loading presets |

### Polyphony / unison / output (bottom bar)
| control | range | what it does |
|---|---|---|
| Polyphony mode | Mono / Poly / Per Oscillator | Mono (last-note priority, slides back on release); Poly; Per Oscillator (each new note uses the next oscillator → every chord differs) |
| Voices | up to 64 | Max simultaneous voices (CPU cost) |
| Unison Voices | n per note | Stacked detuned voices per key for thickness; mod-relevant |
| Unison Spread | 0..200 % (mod target) | Detune/pan spread of unison voices |
| Tuning / Microtuning | 12-TET default · MTS · MTS-ESP · AnaMark .tun | Custom note→frequency maps (reacts to host MTS, MTS-ESP master, or loaded .tun); Reset Tuning to revert |
| High Quality | on/off | 4× oversampling — reduces aliasing from nonlinearities/sync/audio-rate mod (CPU cost) |
| Output Width | 0 (mono) ..100% (normal) ..200% (wider) | Stereo width; mod target (can cause phase cancellation) |
| Output Volume | −inf .. ~+10 dB | Master level; mod target (often by velocity) |
| Output Pan | L/R | Master pan; mod target |

## Use by lens
- **Producer (create):** This is the core instrument — start from the preset browser (type-to-search, tags, favorites), then sculpt. Stack 2–4 oscillators (saw + detuned saw + sub) for fat leads/basses; ring-mod or Per-Oscillator polyphony for inharmonic/bell textures; drag an XLFO onto Filter Frequency for movement and an EG onto Pulse Width or Sync for evolving timbre. Use the arpeggiator + XLFO-Snap for sequenced patterns. The built-in FX mean a patch is gig-ready without extra plugins.
- **Mixing (balance):** As an instrument it sits in the arrange, but treat its character filters/styles and FX as part of the sound design rather than corrective tools. Use the Compressor + Auto Gain to tame dynamics at the source, Width/Stereo for placement, and the EF (side-chain) to make the synth duck/react to other tracks. Modulate Output Volume by velocity for natural dynamics.
- **Mastering (finalize):** Not a mastering tool — it is a synth instrument. Use Pro-Q/Pro-L/Pro-MB on the bus instead.

## Notes / gotchas
- **Drag-and-drop is the whole workflow** — there is no traditional matrix grid; drop a source's drag-button onto a target, then tune the slot's Level/Invert. Slots that modulate other slots appear indented.
- **Source Level (−200..200 %)** scales a source's whole output before any slots — a fast way to globally deepen/invert/disable everything a source drives.
- **High Quality = 4× oversampling**; turn on when sync / drive / audio-rate modulation cause audible aliasing (costs CPU). Drive folds back / saturates past ~75 %.
- **Delay/Reverb/Compressor time fields display-wrap ms→s** in the UI; long settings are seconds.
- **Filter styles carry internal nonlinearity** (Tube/Metal/Raw/Extreme/Hard/Hollow drive and can self-oscillate at the low end) — "Clean" is the only fully linear style. Resonance (Peak) is bipolar: negative damps, positive → self-oscillation.
- **Side-chain**: EGs and EFs can trigger/track an external side-chain input (see manual "Using the side chain"); set it up in the host. Threshold has a metering ring and is a mod target.
- **VST3 limitation:** no per-note (polyphonic) aftertouch modulation. Sustain pedal (CC64) is applied automatically without routing.
- **CPU:** fewer oscillators / lower Voices / Sync=1 are cheaper; unison and high voice counts are costly.
- **Per-effect presets** via the menu button next to each FX label; **section presets** (Save As Default) per modulation source; full **preset browser** with tags/favorites for whole patches.

## Deep spec (Programmer only)
`/Users/pongsathonkheeereekaew/.claude/skills/easby/easby-programming/plugins/Twin3.md` — black-box-measured DSP (oscillator harmonic ladders, filter transfer/slope/resonance tables, DAHDSR time calibration, mod-matrix depth laws, FX confirmations, XLFO cycle-rate). Note: that file additionally contains a quarantined REF (static-disasm) section that is TAINTED / not product-safe — this CLEAN card carries none of it.
