# XLN RC-20 Retro Color — XLN Audio (multi-effect / lo-fi character)

| | |
|---|---|
| Vendor / ver | XLN Audio · 1.0.0 (build 161104) |
| Type | Multi-effect character/lo-fi processor — noise, wow/flutter, saturation, bitcrush, reverb, tape volume artifacts |
| Format | VST / AU / AAX (JUCE-based) |
| Source | manual: `XLN RC-20 Retro Color/XLN RC-20 Retro Color.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
RC-20 recreates the warmth, grit and instability of vintage recording gear and early digital samplers. Six independent FX modules — **Noise, Wobble, Distort, Digital, Space, Magnetic** — chain left-to-right (Noise first, Magnetic last) to add anything from subtle vinyl crackle and tape hiss to wobbly VHS pitch drift, fuzz, bitcrush, lo-fi reverb and dropping/fluctuating tape volume. Each module has a **FLUX** control that injects custom organic, non-linear randomness ("Flux Engine") so the effect breathes and never repeats exactly — the source of its alive, analog feel. A single global **Magnitude** slider scales the entire plugin (all six Big Knobs + master In/Out/EQ) from dry to "wobbly distorted mayhem," making it ideal for automated intros, outros, drops and transitions. Distinct: not a single-purpose box but a one-stop "color/character" suite, with focus filters that let distortion/crushing target only chosen frequency bands.

## Controls (every param → musical effect)

### Top Section
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| RC-20 logo | click | opens Credits & Help page (manual, version, Computer ID, graphics mode) | troubleshooting / open manual |
| Preset Name / LOAD | click | opens Preset Browser (load XLN or User presets, rename/delete User) | recall sounds |
| SAVE | click | save current state as User preset (Save As / Overwrite) | store your own |
| **Magnitude** | global slider | master "amount" for the whole plugin — scales all six Big Knobs + master In/Out/EQ at once; automatable | go dry→full instantly; automate intros/outros/drops/transitions |

### NOISE module (Big Knob = Noise Volume)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Type** | selector (vinyl crackle, cassette, VHS, studio noise, circuit hum, stompbox static, etc.) | chooses the noise character added on top of the signal | pick the era/medium flavor |
| **Tone** | knob (tilt) | tilt EQ on the noise — CW = brighter (more highs, less lows), CCW = darker | sit noise in the mix |
| **Follow** | 0–100 % | makes noise level track the input signal level (0 % = static noise) | gate noise to drums/program; CW for dynamic hiss |
| **Routing (Post)** | toggle (Pre/Post) | Pre = noise enters chain first (gets distorted/crushed/filtered with source); Post = inserted at end, after master EQ (clean noise) | Post for pristine vinyl over the whole mix |
| **Duck** | knob | noise is pushed down by incoming peaks — "pumping" compressor feel with slow attack | rhythmic ducking against drums/vocal |
| FLUX | slider + on/off | organic random fluctuation of the noise | add life; high = wild |
| Big Knob | 0–100 % | Noise Volume (0 % = bypassed) | overall noise amount |

> Note: Noise module only *adds* noise; it does not otherwise alter the source audio.

### WOBBLE module (Big Knob = Wow & Flutter depth)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Wow ⟷ Flutter Balance** | slider | sets mix of Wow (slow pitch drift) vs Flutter (fast pitch wobble) | tape = some of both; vinyl warp = more Wow |
| **Rate** (Wow) | knob | speed of the slow Wow modulation | slower = seasick warp |
| **Rate** (Flutter) | knob | speed of the fast Flutter modulation | faster = shimmery instability |
| **Stereo** | toggle | turns Wow into a stereo chorus-like effect | width / lush detune |
| **Mix** | 0–100 % | dry/wet for the (stereo) wobble — ~50 % gives lush chorus | tame depth; chorus sweet spot |
| FLUX | slider + on/off | organic randomness on the modulation | natural, drifting wow |
| Big Knob | 0–100 % | Wow & Flutter amount (depth) | how warped overall |

### DISTORT module (Big Knob = Distortion amount)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Type** | selector (mild saturation → raging fuzz, several types) | distortion flavor | warmth vs aggression |
| **Focus Filter** | band selector | restricts distortion to a frequency range (e.g. mid/high only, leaving lows clean) | distort top without mud |
| **Mix** | 0–100 % | balance distorted vs unprocessed | parallel grit |
| FLUX | slider + on/off | non-linear fluctuation of the distortion | living, unstable drive |
| Big Knob | 0–100 % | Distortion amount (0 % = bypass) | overall drive |

### DIGITAL module (Big Knob = Rate & Bits reduction amount)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Rate ⟷ Bits Balance** | slider | sets ratio of sample-rate reduction vs bit-depth reduction | rate=aliasing grit, bits=quantize crunch |
| **Smooth** | knob | polishes rough digital edges for a less harsh sound | tame harshness |
| **Focus Filter** | band selector | restricts crushing to a frequency range | crunch top of a kick, keep lows |
| **Cut** | toggle (within Focus) | removes frequencies *outside* the focus range entirely | telephone/band-limited lo-fi |
| **Mix** | 0–100 % | balance crushed vs unprocessed | parallel crush |
| FLUX | slider + on/off | random fluctuation of the degrade | retro sampler instability |
| Big Knob | 0–100 % | Rate & Bits reduction amount | overall crush |

### SPACE module (Big Knob = Dry/Wet)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Decay** | knob | reverb tail length | short room → long wash |
| **PreDelay** | knob | gap before reverb starts | reduce muddiness, keep transients clear |
| **Focus Filter** | band selector | controls resonance/damping of the reverb (can be drastic per source) | tune the reverb color |
| **Stereo** | toggle | turns mono into stereo / widens the space | width on mono sources |
| FLUX | slider + on/off | organic fluctuation in the space | lo-fi, unstable ambience |
| Big Knob | 0–100 % | Dry/Wet balance | overall reverb amount |

### MAGNETIC module (Big Knob = Wear/Flutter/Dropouts amount)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Wear** | (via balance) | worn-tape volume fluctuation (magnetic particles thinning) | gentle vintage volume waver |
| **Flutter** | (via balance) | faster volume artifact (capstan-pin caused) | rapid volume tremble |
| **Wear ⟷ Flutter Balance** | slider | mixes Wear vs Flutter | dial the artifact blend |
| **Dropouts** | knob | random sudden drops in volume (more intense than wear) | broken/old-tape damage |
| **Stereo** | toggle | wear & dropouts act same in both channels, or independently | mono vs per-channel chaos |
| FLUX | slider + on/off | organic randomness of the volume artifacts | natural, unpredictable wear |
| Big Knob | 0–100 % | Wear/Flutter/Dropouts amount | overall tape-volume damage |

### Big Knob Section (per module)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Enable button | on/off | turns a module entirely on/off; off = bypassed + covered by a "hatch" (click hatch to re-enable) | A/B a module |
| Big Knob | 0–100 % | per-module amount; 0 % = fully bypassed; moving a hatched knob re-enables it | quick per-module dose |

### Master Section
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **In · Gain** | knob | input level into the chain | drive DISTORT/DIGITAL harder |
| **EQ · Enable** | on/off | turns whole EQ section on/off | bypass tone shaping |
| **Cut Filter** | low + high cut, each Soft/Hard slope | cuts unwanted lows/highs; steepness selectable per end | clean rumble/fizz, band-limit |
| **Tone** | knob, Tilt or Mid mode | Tilt: CW = more highs/less lows (CCW opposite). Mid: knob boosts/cuts mids (smiley/frowney) | broad final tone shape |
| **Out · Gain** | knob | output level | match levels for A/B; gain-stage Magnitude automation |
| **Out · Width** | 0 % (mono) → 100 % (orig) → 200 % (exaggerated) | stereo width of output | mono-check, narrow, or widen |

## Use by lens
- **Producer (create):** the headline tool — slap it on drums, keys, guitars, bass or a loop and pick a vintage preset, then push **Magnitude** for instant lo-fi/character. Automate Magnitude to build intros, outros, filter-drops and transitions. Wobble + Magnetic for tape/VHS dreaminess; Digital for old-sampler/boom-bap crunch; Noise (with **Follow**) for hiss/vinyl that breathes with the part. Crank **FLUX** for chaotic, evolving textures.
- **Mixing (balance):** use as a gentle "glue/character" insert — small Big-Knob amounts of Distort/Magnetic for analog warmth and subtle movement; Noise on **Routing |Post** to lay clean vinyl/tape hiss over a bus without it being crushed; **Duck** the noise to pump with the groove. Use **Focus Filters** to add grit only to mids/highs and keep low end tight. Master **Cut Filter** + **Tone** to re-shape, **Out Gain** to level-match for honest A/B, **Width** to place it.
- **Mastering (finalize):** not a clean mastering processor — it intentionally adds noise, distortion and pitch/volume instability. Use only as a deliberate aesthetic (lo-fi/cassette release, retro stem) at very low Big-Knob/Magnitude settings; check mono via **Width**, and prefer subtle FLUX. For transparent finalizing reach for a dedicated EQ/limiter instead.

## Notes / gotchas
- **Signal order is fixed** left→right: Noise → Wobble → Distort → Digital → Space → Magnetic (Noise can be moved to the very end via **Routing |Post**, after master EQ).
- **Magnitude is the macro**: it multiplies every Big Knob *and* master In/Out/EQ — automate this one parameter rather than six. Great for risers/drops.
- **Disabled modules** show a "hatch" overlay; clicking the hatch or moving the Big Knob re-enables. 0 % Big Knob = fully bypassed (no CPU character).
- **FLUX** is the secret sauce (custom per module) — a little = life/texture, a lot = "cosmically wild." It's what makes RC-20 sound non-static.
- **Focus Filter + Cut** (Digital) and Focus Filter (Distort) let damage hit only chosen bands — key to keeping lows clean. Space's Focus Filter sets reverb resonance/damping and can be drastic.
- **Tone** has two modes: **Tilt** (broadband) and **Mid**. **Cut Filter** slopes are **Soft/Hard** per end.
- **Presets** are tailored by category (drums, keys, guitars, bass, full mix, post-production); you can set a **Startup** preset and **tweak high-level controls while browsing**. **CloudSync** syncs User presets across machines and **Share** gives a sharable link.
- No stated sidechain input, oversampling control, or reported latency (Space reverb / lookahead-free; treat as low-latency). CPU scales with active modules + FLUX.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
