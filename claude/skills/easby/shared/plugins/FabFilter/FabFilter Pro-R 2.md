# FabFilter Pro-R 2 — FabFilter (algorithmic reverb)

| | |
|---|---|
| Vendor / ver | FabFilter · Pro-R 2 (v2) |
| Type | Algorithmic reverb (musical-control reverb with Decay Rate EQ, Post EQ, ducking, IR import) |
| Format | VST, VST3, CLAP, AU (macOS), AAX Native, AudioSuite, Pro Tools; AUv3 (iPad) |
| Source | manual: `FabFilter Pro-R 2/FabFilter Pro-R 2.pdf` · deep spec: `easby-programming/plugins/Pro-R2.md` (RE'd — black-box measured) |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
A high-quality algorithmic reverb that trades technical reverb parameters for musical, intuitive ones. The central stepless **Space** knob fades smoothly between dozens of tuned room models (200 ms ambience → ~10 s cathedral), auto-picking a matching decay time, while **Decay Rate** scales it 25–400%. Three styles (Modern/Vintage/Plate) cover natural rooms, vintage-digital shimmer, and metallic plates. Its standout feature is the industry-first **Decay Rate EQ** — up to 6 parametric bands that freely shape decay time across the spectrum (instead of a simple low/high crossover) — paired with a 6-band **Post EQ** that tones the final output (with auto-compensated mix). Built to sit in a mix without coloration/phase problems; supports surround/Dolby Atmos up to 9.1.6, ducking, freeze, thickness/saturation, and can import IR files and convert them to its own settings.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Space** | ~200 ms → ~10 s (stepless, dozens of room models) | Master control: smoothly blends room model + decay time. Yellow time label shows current decay time. Click room icons around the knob to jump models | First thing you set — picks the room and its natural decay |
| **Decay Rate** | 25–400% of current Space decay | Scales decay time relative to the chosen model without changing the model. Yellow Space label always shows the final time | Fine-tune a model's tail to fit the mix (shorter/longer) without losing its character |
| **Style** | Modern / Vintage / Plate | Modern = Pro-R v1, most natural/realistic. Vintage = early-digital character, shimmer, great on large/long spaces. Plate = metallic plate vibe, fast build-up | Modern for realism; Vintage for lush '80s/'90s tails; Plate for vocals/snare sheen |
| **Predelay** | 0–500 ms (optional host sync) | Initial gap before the reverb starts. More predelay = more separation from dry, clarity, larger perceived room | Open up vocals/leads; preserve transient clarity; fake bigger rooms without longer decay |
| **Predelay Sync** | Off / Quarter / 8th / 16th / 32nd Note | Locks predelay to host tempo instead of ms | Rhythmic predelay tied to the song |
| **Predelay Offset** | 50–200% of synced predelay | Scales the synced predelay — e.g. 150% (dotted), 67% (triplet) | Dotted/triplet predelay feels |
| **Character** | 0–100% | 0% = transparent/predictable. ~50% = modulation + pronounced early reflections/echoes. 50–100% = increasing chorus-like movement | Add life/lushness; high values shine on vocals & synths |
| **Thickness** | 0–100% (approx) | Density + saturation combo. Up = denser, subtle non-linearities/dynamics. Down = airier, sparser. Effect varies with program material | Glue/weight on the tail; keep it lighter for delicate sources |
| **Distance** | 0–100% | Proximity to the source in the modelled space. 0% = close, brighter, pronounced early reflections. Higher = walking away, longer build-up, more diffuse tail | Push reverb back for depth; pull forward for an up-front, reflective sound |
| **Brightness** | (tilt-style HF balance) | Clarity / high-vs-low balance of the tail; also affects HF decay rate. Lower = more HF absorption (darker, more natural). | Darken for realism; brighten for sheen/air |
| **Stereo Width** | 0% → 100%+ (mono → true stereo → multi-mono) | 0% = mono. Increasing = true stereo via channel cross-feeding (max cross-feed at 50%). 50–100% = re-introduces stereo placement. >100% amplifies side signal (better mono compat) | Mono for narrow/centered FX; 100% for full width; >100% for mono-safe width control |
| **Ducking** | range knob (0 = off) | Intelligent ducking keyed off the plug-in's input — pulls reverb gain down while the dry source plays | Keep vocals/dialogue clear; reverb blooms in the gaps |
| **Auto Gate** | enable + hold time (drag) / sync | Automatic gating of the reverb tail; intelligent auto threshold + attack/release tuned for drums. `sync` button locks hold time to host tempo | Gated-reverb snare; truncated, rhythmic tails; creative on any source |
| **Auto Gate Sync** | host-tempo hold time | Syncs gate hold time to tempo (like Predelay Sync) | Tempo-locked gated reverb |
| **Freeze** | button (hold or toggle) | Infinite/eternal decay reusing current tank contents. Input-side controls (Distance, Thickness, Ducking, Auto Gate) stop affecting sound; output-side (Character, Brightness) still adjust | Drones, ambient pads, sound-design holds; click-and-hold for momentary freeze |
| **Mix** | 0–100% dry/wet | Final dry/wet balance | 100% when used on a send/aux; lower for insert use |
| **Lock Mix** | button | Locks Mix to its current value while loading presets (so presets don't override your send level). Mix is still saved with the session | Send-effect workflow: browse presets without the mix jumping |
| **Decay Rate EQ** (×6 bands) | per-band; decay-rate scale 12.5–200% (display); shapes Bell / Low Shelf / High Shelf / Notch | Per-frequency decay-time multipliers — extend bass tails, shorten harsh HF, etc. Far more flexible than a low/high crossover. Drag blue curve to add; double/Ctrl-click lower display for a notch | Make low end ring longer / tame boxy or sibilant tails / sculpt a room's decay signature |
| **Post EQ** (×6 bands) | gain via display range ±30 / 18 / 9 dB; shapes Bell / Low Shelf / High Shelf / Low Cut / High Cut (cuts to 96 dB/oct, slope adjustable); freq, Q | Full parametric EQ on the final reverb output. Reverb gain auto-compensates so Mix stays right while you EQ | Carve mud, de-ess the tail, shape tone of the wet signal without retouching the dry |
| **Post EQ — Stereo Placement** | Stereo / Left / Right / Mid / Side (stereo); Speakers menu (surround) | Per-band channel targeting on Post EQ bands | EQ only the sides of the reverb, or specific speakers in surround |
| **EQ band Speakers** (multichannel) | All / All excl. LFE / All Tops / L-C-R / LFE / Center / L/R / Lss-Rss / Lsr-Rsr / Lts-Rts | Which speaker sets a Decay Rate / Post EQ band affects (surround/Atmos only) | Make rear speakers decay longer, top speakers less bright, etc. |
| **Input Level / Pan** | dB + L/R | Trim and pan the signal *before* processing (bottom-bar output panel) | Gain-stage into the reverb |
| **Output Level / Pan** | dB + L/R | Trim and pan the final output. Output level metering shows per-channel level | Match wet return level; useful per-channel in surround |
| **Global Bypass** | on/off | Soft-bypass the whole plug-in (click-free); freezes analyzer, shows red line | A/B against dry |
| **Analyzer** | Off / Pre+Post / Reverb+Post | Real-time spectrum + decay-over-frequency visualization behind the EQ curves | Judge tonal balance and how the tail decays per band |
| **Piano display** | toggle | 88-key piano scale under the analyzer; quantize/snap band frequencies to musical notes | Tune reverb resonances/cuts to the song's key |

### Surround Settings (multichannel only)
| control | range / unit | what it does |
|---|---|---|
| **Tilt Controller** | per main control, up/down | Tilts each main knob's behavior front↔back (up = more at front/less at back) |
| **LFE / Center / Top** | wet-mix level per speaker group | Attenuate/boost reverb to LFE (default dry), Center, Top. Higher Top = more immersive vs classic-surround feel |
| **Cross Feed** | 0–100% | Cross-feed between speaker pairs. 0% = each speaker independent; 100% = natural immersive blend |

## Use by lens
- **Producer (create):** Reach for the factory presets, then ride **Space** to taste. Use **Vintage** style + high **Character** for lush '80s synth/vocal tails; **Plate** for snare/vocal sheen. **Freeze** + **Brightness** = instant ambient pads/drones. **Auto Gate** for gated-reverb snares. IR import to drop a real space in as a starting point.
- **Mixing (balance):** Run as a send at **Mix 100%** with **Lock Mix** on. Add **Predelay** (or **Ducking**) to keep vocals/leads clear and forward. Use **Decay Rate EQ** to shorten harsh HF and **Post EQ** low-cut to keep the wet out of the low-mids. **Distance** sets depth; **Stereo Width** sets how wide/mono-safe the return is.
- **Mastering (finalize):** Rarely on a master bus — but light **Modern** room at low **Mix** can add cohesion/air. If used, keep **Brightness** modest, **Decay Rate** short, and use **Post EQ** (Mid/Side placement) surgically. Output metering helps gain-stage.

## Notes / gotchas
- **Styles**: Modern (= Pro-R v1, most natural), Vintage (digital shimmer), Plate (metallic). IR import always forces **Modern**.
- **Decay Rate EQ vs Post EQ**: blue curve/left scale = decay-time shaping; yellow curve/right scale = output tone. Easy to confuse — the active scale lights up. Up to 6 bands each.
- **Post EQ auto-compensates reverb gain**, so EQ moves don't drift your wet level — no need to re-touch Mix.
- **Ducking & Auto Gate are keyed off the plug-in's own input** (no external sidechain input); they stop affecting sound under **Freeze**.
- **IR import** accepts WAV/AIFF transient/impulse files only (drag-drop or preset menu → Import IR). Sine-sweep files are rejected with a warning. Results are a customizable "ballpark," not a true convolution match.
- **Surround/Atmos** up to 9.1.6; unlocks Surround Settings (tilt/cross-feed/per-group levels) and per-band Speakers targeting.
- **Latency**: deep spec reports **zero-latency** (latency identical at 44.1/48/96 kHz). No PACE/iLok in the binary.
- **Mix automation**: parameter changes via MIDI/automation don't create undo states. Lock Mix value is saved per-session; new instances pick up the global Lock Mix setting.
- **MIDI Learn** on every parameter; effect must actually receive MIDI (routing differs per host — Pro Tools/Logic/Ableton/Cubase instructions in manual). Interface resize: Medium/Large/XL + Scaling 100–300%, plus Full Screen.

## Deep spec (Programmer only)
`/Users/pongsathonkheeereekaew/.claude/skills/easby/easby-programming/plugins/Pro-R2.md` — black-box measured (impulse/tone in → measure out): signal chain, decay-rate map, per-band brightness, ducking envelope, long-tail/freeze behavior, zero-latency confirmation. CLEAN (no r2/Ghidra).
