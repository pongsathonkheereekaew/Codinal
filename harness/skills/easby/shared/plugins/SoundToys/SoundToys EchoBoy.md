# SoundToys EchoBoy — SoundToys (delay/echo)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 (manual; first release 2006) |
| Type | Delay / echo (analog/tape-modeled), with chorus & reverb-style styles |
| Format | VST3/AU/AAX (Mac & Windows) |
| Source | manual: `SoundToys EchoBoy/SoundToys EchoBoy.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
EchoBoy is a character delay built to emulate "virtually any classic or contemporary delay device" — tape echoes (Echoplex, Space Echo, Ampex ATR-102), bucket-brigade pedals (DM-2, Memory Man), oil-can (TelRay), digital racks, plus chorus (CE-1), vibrato and reverb-flavored styles. Its signature is *musical* echo: tempo-locked note values with unique **Groove / Feel / Accent** rhythm-shaping (shuffle, swing, rush/drag, beat accenting), plus deep analog-modeling tools (saturation, tape **Wobble**, reverb-like **Diffusion**) in a slide-out Style Editor. Four modes — Single, Dual, Ping-Pong, and a 16-tap **Rhythm** sequencer — span everything from a clean slap to wild self-oscillating dub textures.

## Controls (every param → musical effect)

### Common controls (all modes)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Mix | Dry…Wet (12 o'clock = 50/50) | Dry vs delayed balance; past noon dry drops out | in-line on a track; set 100% wet on a send/bus |
| Feedback | Min…Max | Number/decay of repeats; near max → self-oscillation ("runaway") | tape decays, dub, drones — watch output level |
| Saturation (main knob) | Min…Max | Tube/tape-style compression, emphasis & subtle distortion on the echo; behavior depends on Style (e.g. acts as limiter threshold on "Limited") | warm up repeats, auto de-ess vocal echoes, pumping limiter |
| Input level | -24…+24 dB | Drives the echo circuit pre-saturation (affects echo only, not dry); LEDs: yellow = -6 dB, red = clip | push for grit/dirt or pull for clean |
| Output level | -24…+24 dB | Trims echo level post-circuit (echo only) | tame loud feedback, gain-stage the wet path |
| Style | menu (30 styles) | Picks the modeled echo character (tone, saturation curve, response) — see Styles list | the fastest way to set vibe |
| Low Cut | Min…Max | High-pass on the echoes (style-dependent) | thin bass out of repeats so they sit under the source |
| High Cut | Min…Max | Low-pass / "darkening" of echoes | analog hi-roll-off; push repeats back in depth |
| Prime Numbers | switch (up = on) | Slightly offsets repeat times to minimize resonance build-up | short delays + feedback, chorus/flange/reverb-like patches (esp. Dual/Rhythm) |
| Tap Tempo | tap button + BPM readout | Tap to set the BPM that note-value times lock to | un-clicked live tracks; deliberately off-grid feel |
| MIDI toggle | switch (below tempo) | Down = manual/tapped tempo; up = host MIDI clock drives note values | lock repeats to session tempo |
| Groove | Shuffle ↔ 0 ↔ Swing | Shifts "even" repeats toward triplet feel — CCW adds shuffle, CW adds swing; relative to current rhythm | give synced delays human bounce |
| Feel | Rushin' ↔ Draggin' | Shifts the *whole* delay output vs the beat (laid-back vs pushed); like global pre-delay / negative pre-delay | sit echoes in or ahead of the pocket |
| Mode | Single / Dual / Ping-Pong / Rhythm | Selects echo engine; panel layout changes | see per-mode rows below |
| Tweak (button) | slide-out | Opens the per-mode advanced menu | width, offset, accent, FB routing, etc. |
| Style Edit (button) | slide-out | Opens the Style Editor (custom styles) | deep tone/modulation/saturation design |

### Single Echo mode
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Echo Time | knob + LCD | Time to first echo & between repeats; turning it pitch-bends like analog hardware | the core delay time |
| Time / Note / Dot / Trip | 4 buttons | Time = ms (free); Note/Dot/Trip = tempo-synced 1/2…1/64 (straight/dotted/triplet); menu arrows browse divisions | type ms, or dial musical note values |
| Width (Tweak) | Min…Max | Stereo spread; past 3 o'clock uses out-of-phase info for super-wide "beyond speakers" | fatten/widen the wet image |
| L/R Offset (Tweak) | 0…25 ms (default 8) | Small L/R time difference that creates the stereo image (Width must be up) | tighter = phasey, larger = looser/wider |
| Accent (Tweak) | bipolar (12 o'clock = off) | Alternates repeat loudness; CW accents on-beat (1st/3rd/5th), CCW accents off-beat (syncopation) | animate synced repeats; pair w/ Groove |

### Dual Echo mode (two independent echoes — Echo 1 = L, Echo 2 = R)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Echo 1 / Echo 2 Time | knob + LCD + Time/Note/Dot/Trip each | Independent L & R delay times (one can free-run, the other synced) | huge stereo soundscapes, polyrhythmic L/R |
| Balance (Tweak) | L ↔ R | Relative loudness of left vs right echo | center the stereo delay |
| Width / L/R Offset (Tweak) | as Single | Stereo spread & L/R time difference | same as Single mode |
| Accent 1 / Accent 2 (Tweak) | bipolar each | Per-channel beat accenting (as Single) | independent L/R animation |
| FB Mix (Tweak) | Min…Cross (12 = off) | Cross-feeds Echo1→Echo2 and vice-versa; at max = full cross feedback | dense reverb-like or cross-pollinated syncopation (Feedback must be up) |
| FB Bal (Tweak) | L ↔ R | Sends more feedback to one channel | balance perceived feedback when L/R times differ (Feedback must be up) |

### Ping-Pong mode (bounces L↔R; input summed to mono, always stereo out)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Ping / Pong Time | knob + LCD + Time/Note/Dot/Trip each | Ping = first repeat (always L); Pong = next (R), heard after Ping+Pong time | classic bouncing delay; set both to note values + MIDI sync for rhythmic ping-pong |
| Width (Tweak) | Min…Max | Stereo spread (as Single) | widen the bounce |
| Balance (Tweak) | L ↔ R | L vs R loudness | center/skew the ping-pong |

### Rhythm Echo mode (up to 16 programmable taps = "16 read heads")
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Rhythm Editor grid | click to place taps | Graphical multi-tap: X = time, bar height = volume; left→right = first→last; only visible taps sound. Click add, Option-click delete, drag to move/level, Cmd/Ctrl-click for off-grid | drum-machine-style custom echo patterns |
| Rhythm (Time/Note/Dot/Trip/Patt) | buttons + LCD | Base grid unit; Patt recalls/saves shared SoundToys rhythm patterns | set pattern resolution |
| Shape | knob + LCD menu | Applies an amplitude envelope across all taps; knob = amount. Shapes: Decay, Reverse, Swell, Fade, NonLin (AMS RMX16-style cluster) | quick natural decay, '80s reverse, reverb-like clusters |
| Repeats | knob + LCD | Sets number of audible echoes directly (instead of Feedback) for exact tap count + timing | "exactly 4 repeats at 1/16" — precise control |
| Pan Shape (Tweak) | LCD menu | Per-tap pan pattern: Double, Center, Alt 1/2/3, Sweep L, Sweep R, Pan. "Double" halves taps to 8, each a modulated stereo pair | thick stereo chorus / panning taps |
| Accent (Tweak) | bipolar | Beat accenting across the pattern (as other modes) | groove emphasis |
| Rhythm Grid (Tweak) | LCD menu | Changes editor grid resolution without moving existing taps | finer tap placement |
| Length (Tweak) | 1…8 beats | Overall pattern length (= beats per "measure", e.g. 3 = 3/4) | set the loop length / meter |
| L/R Offset / Width (Tweak) | as Single | Stereo image controls | widen the multi-tap |
| "The One" | (yellow tap at beat 0) | First tap = the source note; only heard when Feedback repeats the pattern; move off-zero → turns green/discrete | understand why tap 1 may be silent |

### Style Editor (custom styles — Style Edit button)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Low / High EQ — Freq, Gain, Decay | shelving | Gentle shelves; Gain = initial echo, Decay = tone change per repeat (CCW cuts/"EQ out", CW boosts each repeat) | progressive darkening/brightening of repeats |
| Mid EQ — Freq, Res, Gain, Decay | semi-parametric | One-band peaking EQ with resonance; Gain/Decay as above | shape midrange of echoes dynamically |
| Diffusion — Amount | Off…Max | Reverb-style smear/density per repeat; high + long time → plate/hall-like; can add metallic resonance | turn echoes into ambient wash |
| Diffusion — Size | 0…50 | Character of the diffusion (small = phasing, large = reverb-like) | match diffusion to source |
| Diffusion — Loop/Post switch | Post / Loop | Post = each repeat equally diffused; Loop = diffusion in the feedback path → cumulatively smeared | choose static vs building diffusion |
| Wobble — Depth | Off…Max (CCW = off) | Tape "vari-speed" pitch wobble depth; high = extreme warp | analog instability, chorus, mangling |
| Wobble — Rate | .01…50 | Speed of the wobble | slow drift vs fast chorus |
| Wobble — Shape | LCD menu | LFO shape: Triangle, Sine, Square, Random Walk, Random S/H | random walk/S&H for vintage tape sauntering |
| Wobble — Sync | bipolar (12 = locked) | Aligns/de-aligns wobble across echo paths: CCW = different rates (out of rate-sync), CW = locked but out-of-phase L/R | rich choruses, opposing L/R pitch motion |
| Wobble — FB / Out toggles | switches | FB = wobble on initial + feedback echoes; Out = wobble on entire wet+dry signal | resonant, pronounced modulation (Out) |
| Saturation (Tweak) — Decay Sat / Out Sat | -24…+24 each | Saturation applied to delay vs overall signal independently (works with main Sat knob) | dial echo grit separately from output |
| Saturation type | LCD menu | Clean, Tape, Warm, Pump, Dirt, Hard Limit, Soft Limit, Warm Limit, Bright Limit | pick the distortion/limiter flavor for a custom style |

### Echo Styles (30 — the `Style` menu)
Tape/analog: **Master Tape** (ATR-102 @30ips, hi-fi smooth), **Studio Tape** (ATR-102 @15ips, HF compression/de-ess), **EchoPlex**, **Space Echo** (RE-201, gritty, self-oscillates via Feedback), **Tube Tape** (hi-mids + distortion), **Cheap Tape** (bright, compressed), **Memory Man** (warm lo-bw chorus-echo), **DM-2** (bucket-brigade, warm/punchy/clean), **TelRay** (oil-can, dark/warbly), **Binsonette** (Binson Echo-Rec, warbly compressed — guitar/keys), **Analog Delay** (warm, lightly distorted), **Digital Delay** (clean/accurate). Radio/lo-fi: **Telephone**, **AM Radio**, **FM Radio** (ultra-compressed/loud), **Shortwave** (narrow/staccato), **Transmitter** (CB, distorted/resonant). Chorus/mod: **Digital Chorus** ('80s), **Analog Chorus**, **CE-1 Chorus** (holy-grail guitar chorus), **Vibrato** (true-pitch). Distortion/character: **Saturated**, **Fat** (super-warm), **Distorted**, **Distressed** (compressed+distorted), **Queeked** (multi-band comp echo). Reverb-like: **Ambient** (distortion+diffusion), **Diffused**, **Splattered** (reflective), **Verb** (echo + cheap verb chaser). Plus **Limited** (built-in limiter — pair with high feedback).

## Use by lens
- **Producer (create):** Reach for a Style first (Space Echo for dub, CE-1 for guitar chorus, DM-2/Memory Man for warm pedal slaps, Telephone for vocal FX). Use note-value sync + Tap Tempo to lock to the song; carve grooves with **Groove** (shuffle/swing), **Feel** (push/drag) and **Accent**. Push **Feedback** + **Space Echo** for self-oscillating risers. Rhythm Mode = a 16-tap echo sequencer for signature stutters and reverse ('80s Reverse shape). Wobble + low Saturation = instant tape vibe.
- **Mixing (balance):** Run 100% wet on a send/bus and blend via send level (manual's recommended workflow). Use **Low Cut / High Cut** to tuck repeats under the dry source; **Prime Numbers** to stop short-delay resonance; **L/R Offset + Width** for width without smearing the center; **Accent**/Groove to keep delays from clouding the beat. The classic vocal slap (100–200 ms) on Studio/Master Tape adds size with auto HF-compression de-essing.
- **Mastering (finalize):** Not a mastering tool — it's a colored, often pitch-modulated effect that alters the wet path only. If ever used on a bus/stem, keep it 100% wet on a parallel send, watch the output LEDs (Feedback can boost level hard), and avoid Wobble/Diffusion on full mixes. No metering, M/S, or transparent-EQ functions.

## Notes / gotchas
- **Four modes restructure the panel**: Single/Dual share controls (Dual = two independent L/R echoes); Ping-Pong sums input to **mono** and is always stereo out (Ping always L first); Rhythm replaces the time knob with a 16-tap grid + Shape/Repeats.
- **Feedback runaway**: near-max feedback self-oscillates and can spike output significantly — ride Output and turn up carefully at high monitor levels.
- **Echo Time is pitch-sensitive**: turning/automating it bends pitch like real analog hardware (great for slides, beware of clicks if not intended).
- **Saturation behavior is Style-dependent** — same knob acts as warm tape comp on tape styles but as a limiter threshold on "Limited"; in the Style Editor pick the saturation *type* (Clean…Hard Limit). When building a custom style, leave the main Sat knob at 12 o'clock and set levels in the Tweak menu.
- **Input/Output and Decay/Out Sat affect the echo path only** — the dry signal is untouched.
- **"The One"** (yellow tap at beat 0 in Rhythm mode) is silent unless Feedback repeats the pattern — by design, since it represents the source note.
- **Patterns are portable**: Rhythm "Patt" + saved patterns are shared across any SoundToys plug-in with a Rhythm mode.
- Part of the SoundToys 5 bundle; iLok authorized. Latency/oversampling not specified in the manual.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
