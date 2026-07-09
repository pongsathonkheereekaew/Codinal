# Avid Pro Tools — Avid (DAW / host)

| | |
|---|---|
| Vendor / ver | Avid · Pro Tools 2025.10 (Reference Guide, REV A) |
| Type | Digital Audio Workstation (recording / editing / MIDI / mixing / immersive host) |
| Format | macOS + Windows app (AAX-native plugin host; also AU/VST3 via third-party wrappers). Tiers: Intro (free), Artist, Studio, Ultimate |
| Source | manual: `Avid/Avid Pro Tools/Avid Pro Tools.pdf` (~2134 pp) + `Avid Pro Tools_Plugins.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Pro Tools is the industry-standard DAW for recording, editing, MIDI/instruments, mixing, and immersive (Dolby Atmos / Ambisonics / 360RA) delivery — the universal session format used on most pro music, film, and TV releases. It is built around two main windows: the **Edit** window (timeline: clips, waveforms, MIDI, automation, fades) and the **Mix** window (console: channel strips with inserts, sends, pan, faders). It is distinct for its sample-accurate non-linear editing, deep automation engine, Playlist-based comping, Elastic Audio time/pitch warping, integrated Melodyne/ARA pitch editing, Beat Detective, AI speech-to-text Transcription, and a tightly integrated Dolby Atmos renderer. Pro Tools is the *host* the rest of the easby plugins load into — this card describes the environment and its built-in tools, not a single processor.

## Controls (every capability area → musical effect)
Pro Tools has thousands of individual controls; this lists its real capability surface — the features an engineer reaches for. Stock-processor parameter rows (Sketch FX, Clip Effects) are itemised where they have musical knobs.

### Tracks & session structure
| control / feature | what it is | what it does | when to reach for it |
|---|---|---|---|
| Track types | Audio, Aux Input, Master Fader, VCA Master, MIDI, Instrument, Basic Folder, Routing Folder, Video | Each is a channel/lane with its own role in signal flow | building any session |
| Voices | up to 2048 voices / audio tracks (Ultimate), 64 video tracks | playback/record concurrency limit per track | large sessions, film |
| Folder Tracks | Basic (organize) vs Routing (sub-bus + collapse) | group/collapse many tracks; Routing folders sum to a bus | taming hundreds of tracks; stems |
| VCA Master | controls grouped member faders/mutes without audio path | trim a whole group's level/automation from one fader | mix bus control, dialogue/music/FX stems |
| Track Presets | save/recall a track's inserts, sends, I/O, routing, color | instant recall of a processed channel | template channels, vocal chains |
| Groups (Mix / Edit / Mix+Edit) | link tracks for level, mute, solo, edit, attributes | move/edit/balance many tracks as one | drum kits, multi-mic, stems |
| Clip List | session-wide pool of audio/MIDI/video clips | browse, rename, batch-rename (regex), audition, drag to timeline | asset management |

### Recording
| control / feature | what it is | what it does | when to reach for it |
|---|---|---|---|
| Record modes | Normal (nondestructive), Destructive, Loop, QuickPunch, TrackPunch, DestructivePunch | how takes are captured / punched | tracking, ADR, dubbing |
| Loop Record + Playlists | cycles record region, each pass → new take/playlist | capture many takes for comping | vocals, solos |
| Punch (Quick/Track/Destructive) | punch in/out on the fly over a range | fix sections without re-tracking | overdubs, film re-record |
| Click / metronome | built-in click track + Click options | tempo reference for tracking | any tempo-based recording |
| Input monitoring | Auto Input vs Input Only; Low-Latency / Zero / DSP Mode | controls what you hear while armed | tracking with effects |
| Retrospective Record (MIDI) | recovers played notes even when not recording | rescue a performance you didn't arm | MIDI improv |
| Alternate Takes / Matching | swap takes by region; Matching Criteria window | quickly audition/select among takes | comping |

### Editing (Edit window)
| control / feature | what it is | what it does | when to reach for it |
|---|---|---|---|
| Edit modes | Shuffle, Slip, Spot, Grid (abs/rel) | governs how clips move/snap | every edit task |
| Edit tools | Zoomer, Trim, Selector, Grabber, Smart Tool, Scrubber, Pencil | the core mouse tools (Smart = context-sensitive) | all editing |
| Trim tools | Standard, TCE (time-compress/expand), Scrub, Loop | adjust clip boundaries; TCE warps length | tightening edits, fitting to picture |
| Tab to Transients | jump edit cursor to next audio transient | fast rhythmic editing without zooming | drum/dialogue editing |
| Fades & Crossfades | fade-in/out + crossfade with shape/slope/link curves | smooth clip boundaries, avoid clicks | every cut, comp seam |
| Playlists / Track Compositing | alternate edit lanes per track; rate + promote | comp best bits across takes | vocal/solo comping |
| Clip Gain | per-clip volume (pre-fader), with breakpoint line | level rides before the channel | dialogue/level balancing |
| Clip Effects | per-clip EQ + Filters + Dynamics (see params below) | inline processing on a single clip | dialogue cleanup, quick fix |
| Beat Detective | transient detection → beat triggers, conform, quantize | tighten/realign performances; extract tempo | drum editing, groove |
| Strip Silence | removes silence between regions by threshold | auto-chop gaps | dialogue, drum cleanup |
| Memory Locations / Markers | recallable timeline/edit positions + track markers | navigate, recall selections/zoom/window states | arrangement, post |
| Quantize clips (audio) | snap audio clips/Elastic events to grid/groove | tighten timing of recorded audio | rhythm correction |

### MIDI & instruments
| control / feature | what it is | what it does | when to reach for it |
|---|---|---|---|
| MIDI / Score / MIDI Editor windows | piano-roll + notation editing | compose, edit notes/CC/velocity | MIDI production, scoring |
| MIDI Operations | Quantize, Groove Quantize, Transpose, Change Velocity/Duration, Select/Split, Step Input, Flatten/Restore Performance | non-destructive MIDI transforms | programming, humanizing |
| Groove Templates | apply timing/velocity feel of a groove to MIDI/audio | impose a groove (incl. extracted) | feel, swing |
| Input Quantize / Wait for Note / MIDI Thru | record-time MIDI handling | tighten as you play, step in | tracking MIDI |
| Score Editor + Chord Symbols | notation view, chord ruler, extract chords | lead sheets, charts | composition |

### Mixing & routing (Mix window)
| control / feature | what it is | what it does | when to reach for it |
|---|---|---|---|
| Channel strip | fader, pan, solo, mute, inserts (10: A–J), sends (10: A–J), I/O | the mix console per track | all mixing |
| Inserts | plugin or hardware insert slots, pre-fader | EQ/comp/FX in series on a track | shaping every channel |
| Sends | aux sends (pre/post), with own level/pan/mute | parallel FX, cue mixes, submix feeds | reverb/delay buses, headphones |
| Buses / submixes | internal mix buses; Aux Inputs as returns | group/route signals, parallel processing | stems, bus comp, FX returns |
| Pan / Stereo Pan Depth | mono→stereo→surround panners; pan depth law | place in the field | every mix |
| HEAT | analog-emulation (Drive + Tone) across the mixer (Ultimate) | adds harmonic saturation/glue to all tracks | "analog" warmth on a session |
| Delay Compensation (ADC) | auto time-aligns track latencies | keeps phase-coherent mix despite plugin delay | mixing with latency plugins |
| Dither | output dither + noise shaping | clean bit-depth reduction at the master | bounce/master to lower bit depth |
| Output windows | floating fader/pan/meter per output or send | mix outputs/sends in a focused window | surround, multi-out |
| Control surface support | EUCON (S4/S6/Artist), MIDI surfaces, D-Command/C24 | hands-on fader/knob control | large mixes, re-recording |

### Stock Sketch / Global FX (parameters)
*(Pro Tools Sketch = non-linear loop/clip launcher with its own lightweight FX; Global FX = Delay + Reverb sends.)*
| effect | key params | what it does |
|---|---|---|
| Sketch EQ | bands / freq / gain | tone-shape a clip in Sketch |
| Sketch Compressor | threshold / ratio / attack / release | dynamics in Sketch |
| Sketch Delay | time / feedback / mix (+ Global Delay) | echo |
| Sketch Reverb | size / decay / mix (+ Global Reverb) | space |
| Sketch Chorus / Multimode Filter / Saturation / LoFi / Crunch Crusher | mod / cutoff-res / drive / bit-rate / distortion | creative coloring per clip |
| SynthCell | OSC1/OSC2, Filter, Env, Mod, Effects, Matrix, Arp, Global | built-in subtractive synth instrument |
| PlayCell | macros + global controls | sample/loop player instrument |

### Clip Effects (per-clip inline processor, parameters)
| section | params | what it does |
|---|---|---|
| Input | Input Trim, Polarity Invert | gain-stage / phase flip a clip |
| EQ + Filters | multi-band EQ, HPF/LPF filters | tonal correction on one clip |
| Dynamics | compressor/dynamics controls (threshold/ratio/attack/release) | level control on one clip |

### Processing & rendering
| control / feature | what it is | what it does | when to reach for it |
|---|---|---|---|
| AudioSuite | offline (file-based) rendering of plugins | print processing to new audio, batch process | destructive cleanup, mass FX |
| Elastic Audio | real-time/rendered time + pitch warp (algorithms: Polyphonic, Rhythmic, Monophonic, Varispeed, X-Form, élastique Pro) | conform tempo, warp timing, transpose | tempo-matching loops, comping timing |
| Melodyne / ARA | integrated Celemony Melodyne + ARA plugins (RX, SpectraLayers, etc.) | pitch/time editing inside Pro Tools; audio→MIDI | tuning vocals, extract MIDI |
| Transcription | AI speech-to-text on tracks/clips (Ultimate/Studio) | searchable text, edit audio via words | dialogue/podcast editing |
| Commit | print a track's inserts to new audio, keep source | free CPU, lock in a sound | mixdown prep, sharing |
| Freeze | temporarily render inserts in place | free DSP without losing the chain | CPU-heavy sessions |
| Bounce Track / Bounce Mix | render track or whole mix to file | stems, mixdowns, deliverables | export/master |
| DSP Mode | HDX-DSP ultra-low-latency path for monitoring | near-zero-latency tracking with plugins | overdubs through reverb |

### Automation
| control / feature | what it is | what it does | when to reach for it |
|---|---|---|---|
| Automation modes | Off, Read, Touch, Latch, Touch/Latch, Write, Trim | how moves are recorded/played | every dynamic mix |
| Automatable | volume, pan, mute, sends, plugin params, surround position | breakpoint curves over time | rides, fades, FX moves |
| Write To / AutoMatch / Glide | write to start/end/all/punch; glide between values | shape and join automation | polishing automation |
| Snapshot / Preview / Capture | audition then commit automation values | try moves before printing | precise mixes |
| Trim automation | offset existing automation by a delta | bump a whole pass up/down | overall level tweaks |

### Immersive / surround
| control / feature | what it is | what it does | when to reach for it |
|---|---|---|---|
| Surround formats | LCRS → 5.1 → 7.1 → 7.1.2 → up to 9.1.6, SDDS, Ambisonics | multichannel beds and panning | film/TV/immersive music |
| Surround / 3D panners | X/Y + 3-Knob + immersive panner, divergence, LFE, AutoGlide | position sources in 2D/3D field | surround mixing |
| Dolby Atmos Renderer | internal (or external) Atmos renderer, bed/object groups, object panner, re-renders, ADM BWF I/O | author + monitor + deliver Atmos masters | Atmos mixing/delivery |
| 360 Reality Audio (360RA WalkMix) | spherical object panner + renderer | author Sony 360RA immersive | 360RA delivery |

### Session management, sync & video
| control / feature | what it is | what it does | when to reach for it |
|---|---|---|---|
| Sessions / Projects / Sketches | local session file vs cloud Project vs non-linear Sketch | save/version/collaborate | all work |
| Track Collaboration | cloud-shared tracks, ownership, chat, Revision History | multi-user projects | remote collaboration |
| Import/Export | audio, MIDI, AAF/OMF/MXF, session data, text, Sibelius | interchange with other DAWs/NLEs | post pipelines |
| Sync | timecode (MTC/LTC), Sync X/SYNC HD, pull up/down, MachineControl, Ableton Link, MIDI Beat Clock | lock to picture/external gear | film/broadcast |
| Video | up to 64 video tracks, AVE engine, bounce to QuickTime/MOV | edit/score to picture | post-production |
| Satellite Link / Video Satellite | link multiple Pro Tools / Media Composer rigs | distributed playback/record | large facilities |

## Use by lens
- **Producer (create):** Start in **Sketch** to jam loops/MIDI non-linearly, then move to the timeline. Use **Instrument tracks** + stock **SynthCell/PlayCell** (or any third-party instrument), **Loop Record** + **Playlists** for takes, **Elastic Audio** to fit loops to tempo, **Beat Detective**/**Groove Quantize** for feel, **HEAT** for instant analog glue. Track Presets give instant vocal/drum chains.
- **Mixing (balance):** Live in the **Mix window** — inserts for EQ/comp, **sends → Aux returns** for reverb/delay, **buses/submixes** for stems, **VCA Masters** + **Groups** for control, full **automation** (Touch/Latch/Trim) for rides. Turn on **Delay Compensation**. Use **Clip Gain** and **Clip Effects** to pre-balance before the channel. **Commit/Freeze** to manage CPU.
- **Mastering (finalize):** Put a chain on a **Master Fader** (the only insert point that processes the summed mix post-fader for the bus), apply **Dither + noise shaping** when reducing bit depth, then **Bounce Mix** to the delivery format/sample rate (offline or real-time). For immersive, author and **export ADM BWF** / re-renders via the **Dolby Atmos Renderer**. Pro Tools is a capable mastering host but has no dedicated mastering suite — use stock/3rd-party limiters (e.g. the easby limiters) on the Master Fader.

## Notes / gotchas
- **Tiers matter:** Intro/Artist/Studio/Ultimate differ in track/voice counts, surround/Atmos, Transcription, HEAT, HD hardware, advanced metering. Some features above are **Ultimate/Studio only** (Transcription, full immersive, HEAT, high voice counts).
- **AAX is native;** to load AU/VST3 you need a wrapper. Most easby targets ship AAX, so they load directly.
- **Inserts are pre-fader; Master Fader processing is post-fader** — put limiters/dither on a Master Fader for true bus processing.
- **Delay Compensation (ADC)** must be ON for phase-coherent mixing with latency plugins; **side-chain delay comp** is configurable. **DSP Mode** (HDX only) bypasses it for ultra-low-latency tracking.
- **Sends can be pre or post-fader**; pre-fader sends are how you build independent cue/headphone mixes.
- **Bounce can be offline** (faster than real-time) or real-time (needed when external hardware inserts are in the path).
- **Elastic Audio** is real-time by default but renders to disk; choose the algorithm by source (Polyphonic for chords, Rhythmic for drums, Monophonic for single notes/vocals, X-Form for highest quality offline).
- **Clip Gain vs Volume automation** are separate stages (clip gain is pre-insert); they can be converted/coalesced into each other.
- **élastique Pro V3 by zplane** is the time-stretch engine for Elastic Audio (vendor-licensed, per legal page).
- **Session format = industry interchange**; opening newer sessions in older Pro Tools has documented compatibility limits (see "Sharing Sessions Between versions").

## Deep spec (Programmer only)
Not reverse-engineered — capability only. Pro Tools is the *host*; the easby DSP targets (limiters/EQ/dynamics/reverb) are the cloned plugins, each with its own `easby-programming/plugins/<NAME>.md`.
