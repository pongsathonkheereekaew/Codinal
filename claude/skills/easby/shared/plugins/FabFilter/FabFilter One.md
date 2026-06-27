# FabFilter One — FabFilter (synth)

| | |
|---|---|
| Vendor / ver | FabFilter · (unversioned in manual) |
| Type | Synth — monophonic/10-voice subtractive synthesizer (1 osc → 12 dB/oct LP filter) |
| Format | VST, VST3, CLAP, AU (macOS), AAX Native |
| Source | manual: `FebFilter One/FabFilter One.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
A deliberately minimal one-oscillator subtractive synth modeled on analog classics like the Korg MS-10/MS-20. Its whole identity is two hand-tuned DSP blocks: an aliasing-free oscillator (saw/triangle/square+PWM/noise) and a fat, smooth, self-oscillating 12 dB/oct low-pass filter that stays musical even at full resonance. One LFO ("modulation generator") and one ADSR envelope can each modulate oscillator pitch, filter cutoff, and pulse width; velocity tracks volume and cutoff. No second osc, no FM operator, no mod matrix — you reach for it when you want a thick, characterful single-voice bass/lead/drum/FX sound fast, not for complex sound design (use Twin 3 for that). Famous extras: polyphonic portamento (slides chords) and click-free smart parameter interpolation.

## Controls (every param → musical effect)

### Bit Controlled Oscillator
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Wave Form | triangle / sawtooth / square / white noise | Source tone: triangle = soft warm (sine-like), saw = bright sharp (best for filtering), square = metallic (shaped by PW), noise = percussion/FX | Triangle for sub/soul bass; saw for leads & defined bass; square for electro; noise for drums/FX |
| PW / PWM | even square → infinitely thin pulse | Sets square's pulse width; with PW MOD switch it instead sets the *amount* of pulse-width modulation | Thin the square for nasal/reedy tone; modulate for movement (keep ≤8–9 or pulse mutes) |
| Scale | 32′ / 16′ / 8′ / 4′ (octaves) | Transposes osc in full octaves — 32′ rich bass, 4′ high whistles | 32′ for sub-bass; 16′/8′ for leads; 4′ for bells/raindrop FX |
| Pitch | −5 … +5 (fine detune) | Slight detune of the oscillator | Tune to a record/live instrument; Ctrl/Cmd-click to reset to 0 |
| Portamento | 0 … 10 | Glide time between notes; works in *polyphonic* mode too (sliding chords) | Smooth solos, analog "lively" feel; a little goes a long way |
| Noise | 0 … 10 | Mixes white/pink noise into the osc signal (type set by Noise Type switch) | A touch = natural realism; high = thunder/storm FX, snare snap |
| Frequency Modulation — MG | 0 … 10 | Amount the LFO modulates oscillator pitch | Vibrato (moderate MG); car-siren / ocean-wave sweeps (slow MG) |
| Frequency Modulation — EG | 0 … 10 | Amount the envelope modulates oscillator pitch | Pitch-attack blips, raindrop "ping" (high EG + Frequency Mod EG=inverted) |
| Frequency Mod EG switch | normal / inverted | Inverts the EG signal feeding osc pitch | Inverted = falling pitch attack |
| Noise Type switch | white / pink | White = bright hiss, pink = darker rumble | Pink for storm/wind & warm body; white for snare/hat |

### Cutoff Filter (12 dB/oct low-pass)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Frequency | 0 … 10 | Cutoff: 0 ≈ a few Hz (near silence), 10 ≈ >20 kHz (fully open). Lowering removes upper harmonics → warmer/darker | Core tone shaping; ~5 for warm bass; sweep for filter movement |
| Peak | 0 … 10 | Resonance; ~8+ the filter self-oscillates at cutoff (deep ringing bass tones with Freq ~3–4). Tuned to never go "over the top" | A little = warm character; high = acid/raw 70s leads & self-osc kicks |
| Filter Modulation — MG | 0 … 10 | Amount the LFO modulates cutoff | Tremolo/wobble, swelling storm pads, livelier timbre |
| Filter Modulation — EG | 0 … 10 | Amount the envelope modulates cutoff | Essential for percussive "pluck"/attack; fat self-osc kicks |
| Filter Mod EG switch | normal / inverted | Inverts EG signal feeding cutoff | Inverted sweeps for snares/special FX |

### Envelope Generator (ADSR + Hold)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Hold | 0 … 10 | Extra time the note is treated as held after key release (lets you overlap new notes) | Avoid premature release with short decay/low sustain; legato feel |
| Attack | 0 … 10 | Time for volume to rise 0→max on key-down | 0 for staccato/drums; larger for pads/flutes |
| Decay | 0 … 10 | Time to fall from max to sustain level (no effect if Sustain=max) | Plucks/percussive ticks; shapes the front of the sound |
| Sustain | 0 … 10 | Held level while key down. Low = sharp attack (esp. when EG modulates filter); 0 = silent after decay | Low for drums/plucks; high for sustained bass/leads |
| Release | 0 … 10 | Fade-to-zero time after key-up + hold | Longer for live playability/overlap; short for tight drums |

*Stages: attack → decay → (sustain while held) → release. In sustain the EG has no modulation effect; in attack/decay it raises osc/cutoff, in release it lowers them.*

### Modulation Generator (LFO)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Wave Form | square ↔ triangle, with adjustable balance | Shape + rising/falling ramp balance (anything saw→tri→square). Square = repeated 2-tone switching; triangle = smooth sweeps | Triangle for vibrato/siren/swell; square for trill/octave-jump |
| Frequency / Sync type | 0 … 10 (free) or note values (synced) | LFO speed; free run, or sync to host tempo/position (e.g. 16 bars … 1/64). 0 = very slow ramps (ocean waves) | Tempo-locked wobble; very slow for evolving FX |
| Sync mode switch | free / sync | Toggles arbitrary-Hz vs host-tempo sync | Sync for rhythmic modulation in-project |
| Wave Form balance reset | — | Ctrl/Cmd-click the wave-form knob → perfect centered triangle | Neutral starting LFO shape |

### Additional / global
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Polyphony | Mono / Poly (10 voices) | Mono = classic single-voice (legato/portamento leads & bass); Poly = up to 10 notes | Poly for chords/pads; Mono for tight bass & glide leads |
| PW MOD source | Off / MG / EG / EG Inv | What modulates pulse width (requires square wave): Off=static PW; MG=PWM by LFO; EG=thins on attack; EG Inv=thicker attack/thinner release (most natural) | EG Inv = FabFilter's favorite for living analog tone |
| Filter KBD Tracking | 0 … 10 | How much cutoff follows note pitch up the keyboard | Keep brightness even across range; consistent self-osc tuning |
| Keyboard Velocity — Volume | 0 … 10 | How much MIDI velocity drives loudness (Volume=0 → always max volume) | Dynamic, touch-responsive playing |
| Keyboard Velocity — Filter | 0 … 10 | How much velocity drives cutoff | Velocity-opened brightness (harder hit = brighter) |
| Volume | 0 … 10 | Master output level | Output gain staging |

### UI / utility
- **Knob control:** vertical drag, rotate (drag the arrow — move cursor away for fine control), mouse-wheel, double-click for text entry. Ctrl(Win)/Cmd(mac)-click = reset to default (Alt-click in Pro Tools). Shift-drag = fine-tune. Linked knobs adjust together.
- **Text entry tricks:** type `1k`=1000 Hz, note names like `A4`/`C#3+13`, `2x`=+6 dB, `50%`=center.
- **Presets / Undo-Redo / MIDI Learn:** preset browser + prev/next arrows at top; full undo/redo; MIDI Learn button (bottom) maps any CC to any knob — menu has Clear, Revert, Save, Load Factory Settings.

## Use by lens
- **Producer (create):** This is a *sound source*, not a processor — put it on an instrument track. Bass: triangle/saw, 32′/16′, snappy ADSR (low A/D/R, high sustain), Peak ~5, a touch of EG→cutoff and portamento. Leads: saw/square, short A + short D + high sustain + noticeable release, push Peak high + EG/MG cutoff mod for raw 70s rawness, add portamento. Drums: Freq~3 / Peak~10, Attack 0, max EG→cutoff for self-osc kicks; noise wave + inverted EG for snares/hats. FX: exploit modulation freely — e.g. raindrop (triangle 4′, inverted EG→pitch ~9, Freq~4, EG→cutoff 10) or storm (noise+pink, slow triangle MG→cutoff, high attack/release swell).
- **Mixing (balance):** Treat as a synth track to fit in the mix — lean on **Filter Frequency** to carve space (dark bass under vocals, bright lead on top), **KBD Tracking** to keep timbre even across the part, and **velocity→volume/filter** for dynamics that sit naturally. Poly mode + light portamento for pad/chord glue. Use moderate Peak rather than extreme self-osc to avoid a narrow resonant peak fighting other elements.
- **Mastering (finalize):** Not a mastering tool — it's a generative instrument with no audio input. Skip on the master bus.

## Notes / gotchas
- **Single oscillator only** — no osc 2, no sync, no FM-operator; depth comes from filter self-oscillation + LFO/EG modulation, not stacked oscs.
- **PWM needs the square wave** set first — PW MOD switch only does anything on square; don't push PW/PWM fully right or the pulse mutes (stay ≤8–9).
- **EG-as-modulator quirk:** the envelope only modulates during attack/decay/release; in sustain it contributes nothing — for sustained filter movement use the MG (LFO) instead.
- **Short decay + low sustain + long release** can make a note ring far longer than expected if released mid-envelope (it jumps straight to release); add Hold time to tame.
- **Polyphonic portamento** is unusual — sliding *chords* are possible; great trick, can sound chaotic if overused.
- **Self-oscillation is musical by design** — high Peak won't produce harsh digital whistles/zipper artifacts; safe to crank.
- Sample-accurate automation, arbitrary sample rates, click-free parameter interpolation (smooth even with MIDI CC). Presets are cross-platform (macOS/Windows identical files); `Basic` category (Sawtooth, Pink Noise) = good blank starting points.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
