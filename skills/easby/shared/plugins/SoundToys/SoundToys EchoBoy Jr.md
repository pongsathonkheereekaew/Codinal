# SoundToys EchoBoy Jr — SoundToys (delay / echo)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 |
| Type | Delay / echo (analog/tape-modeled) |
| Format | VST / VST3 / AU / AAX (Mac & Windows; not enumerated in manual) |
| Source | manual: `SoundToys EchoBoy Jr./SoundToys EchoBoy Jr.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
A streamlined single-panel delay derived from the full EchoBoy, built to emulate a wide range of classic and contemporary echo devices (tube/transistor Echoplex, Roland RE-201 Space Echo, EH Memory Man, ATR-102 studio tape, plus Soundtoys originals) without the deep tweak menus. The musical job: add slap, doubling, rhythmic, dub, or ambient echoes that sound *better than the source* — repeats that are colored, band-limited, and saturated like real analog hardware rather than clinical digital copies. What's distinct is the **Style** knob (7 voiced echo characters that re-tune how Saturation, Low/High Cut and Feedback behave) combined with tape-style **Glide** (pitch bends on echo-time changes / self-oscillation) — Soundtoys' signature analog grit in a fast, few-knob layout.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Mix** | Dry → Wet (12 o'clock = 50/50) | Dry/delay balance; past noon dry level drops toward delay-only | In-line: dial the blend. On a send/aux bus: set 100% wet and balance with send return. Also used to even out preset level anomalies |
| **Echo Time** (knob) | ms (Time mode) or note division (Note/Dot/Trip) | Time between source and first echo, and between repeats. Knob, LCD type-in, or up/down menu arrows | Set the delay length / rhythm. 0–10 ms = flange, 10–50 ms = chorus/doubling, 100–200 ms = slapback |
| **Echo Time mode: Time** | fixed ms | Free milliseconds, shown in LCD readout | Non-tempo slap, doubling, flange/chorus; precise ms values |
| **Echo Time mode: Note** | 1/2 → 1/64 | Tempo-synced straight note divisions; auto-locks to DAW tempo | Musical, in-the-groove rhythmic echoes |
| **Echo Time mode: Dot** | dotted 1/2 → 1/64 | Dotted versions of synced notes | Dotted-1/8 "U2/The Edge" style rhythmic delays |
| **Echo Time mode: Trip** | triplet 1/2 → 1/64 | Triplet versions of synced notes | Triplet/shuffle-feel echoes |
| **Feedback** | Min → Max | Amount of delay fed back to input = number of repeats; near-max → self-oscillation / "runaway" | Few repeats vs. long decaying tails; push to max for dub/Space-Echo self-oscillation. Caution: high settings can sharply boost output level |
| **Stereo Mode: Normal** | radio button (default) | Centered, narrow mono-ish repeat | Default; tight, focused echo |
| **Stereo Mode: Wide** | radio button | Small L/R offset → much wider stereo image | Widen the echo, stereo interest on mono sources |
| **Stereo Mode: Ping Pong** | radio button | Each successive repeat bounces L↔R | Bouncing stereo delays, rhythmic width |
| **Glide** | Off / On | On = tape-style pitch shift when echo time changes (and pitched self-oscillation); Off = real-time time changes with no pitch artifact | On for tape pitch-bend / automation FX. Off to retune delay while Feedback is up without feeding pitch glitches back |
| **Style** | 7-position knob (click name or turn) | Selects the modeled echo voice; re-tunes Saturation + Low/High Cut response | Pick the tonal character of the echo (see styles below) |
| **Low Cut** | Min → Max | High-pass on the echoes (attenuate bass) | Stop delays muddying the low end; shape tone/distance; behavior varies by Style |
| **High Cut** | Min → Max | Low-pass / "darkening" of the echoes | Roll off top for analog/tape-style darker, more distant repeats; behavior varies by Style |
| **Input** | Min → Max | Boosts/attenuates signal into the echo circuit (models analog input-stage drive). Affects echo only, not dry | Keep clean or drive dirty; interacts with Style. Watch LED meter |
| **Output** | Min → Max | Boosts/attenuates echo output. Affects echo only, not dry | Gain-stage the wet path; tame self-oscillation level |
| **Input/Output LEDs** | green / yellow (−6 dB) / red (clip) | Visual level of echo in/out; red = possible audible clipping | Monitor drive; intentional clip = grit, or back off to stay clean |
| **Saturation** | Min → Max | Tube/tape-style compression, emphasis and subtle distortion on the delay; response depends on Style | Add analog warmth/grunge to repeats; on Studio Tape it adds low/mid odd-harmonic distortion + HF compression (auto de-ess on loud vocal echoes) |

### Echo Styles (7)
| style | modeled after | character |
|---|---|---|
| **Studio Tape** | ATR-102 @ 15 ips | Subtle distortion + HF compression; clean-ish pro tape |
| **Plex** | EchoPlex EP-3 | Classic solid-state tape echo |
| **Space** | Roland RE-201 Space Echo | Warm, gritty; dub/reggae staple; self-oscillates via Feedback |
| **Cheap Tape** | Soundtoys original (consumer tape stock) | Bright, very compressed |
| **Memory** | EH Memory Man | Warm, low-bandwidth chorus echo |
| **Ambient** | EchoBoy Distortion + Diffusion combo | Smooth long tails; good for long feedback loops & solo instruments |
| **Transmitter** | CB-radio-type response | Heavily distorted, mid-resonant; echo grit for synths |

## Use by lens
- **Producer (create):** Pick a Style for instant vibe — Space for dub/reggae throws, Memory for warm chorused guitar/vocal, Transmitter to mangle synths. Use synced Note/Dot/Trip for grooving rhythmic delays (dotted-1/8 on guitars). Automate Echo Time with **Glide On** for tape pitch-dives; ride **Feedback** to max for self-oscillating risers/dub sirens. Short ms (0–50) for flange/chorus/doubling, ~120–200 ms for slapback on vocals.
- **Mixing (balance):** Run on an aux/send at **Mix = 100% wet**; control level via send. Use **High Cut** + **Low Cut** to tuck repeats behind the dry signal (darker, narrower, more "distant") so the delay supports rather than clutters. **Wide**/**Ping Pong** add stereo space; **Normal** keeps it focused. Modest **Saturation** glues repeats; Studio Tape's HF compression auto-de-esses sibilant vocal echoes.
- **Mastering (finalize):** Not a mastering tool (effect/delay). At most a parallel/aux ambience or stylistic throw in a mix — keep off the master bus for finalizing.

## Notes / gotchas
- **Tempo sync:** Note/Dot/Trip auto-sync to host tempo; Time mode is free ms. LCD readout doubles as a type-in for exact ms; up/down arrows browse divisions.
- **Self-oscillation / level:** High Feedback (esp. Space style) self-oscillates and can dramatically raise output — turn down before pushing Feedback at loud monitoring levels.
- **Glide trade-off:** Glide On = musical tape pitch glides on time changes but feeds pitch artifacts into the repeats; Glide Off = clean retune-while-running.
- **Style is global tone:** Low/High Cut, Saturation, and Input drive all respond *differently per Style* — re-audition them when you change Style.
- **Wet/dry routing:** Input/Output/Saturation touch only the echo path; the dry signal is unaffected, so the plug-in is safe in-line as well as on a send.
- **Junior vs. full:** This is the stripped EchoBoy — no Rhythm Echo / multi-tap / dual-echo / deep tweak panel; reach for full EchoBoy when you need those.
- Manual is v5, © 2016. No latency/oversampling/CPU figures stated.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
