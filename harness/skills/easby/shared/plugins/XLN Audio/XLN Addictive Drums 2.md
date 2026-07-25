# XLN Addictive Drums 2 — XLN Audio (drum sampler / virtual instrument)

| | |
|---|---|
| Vendor / ver | XLN Audio · AD2 (manual dated Oct 28, 2024) |
| Type | Virtual drum instrument — multi-mic acoustic drum sampler + built-in mixing/FX + MIDI beat library |
| Format | VST/VST3/AU/AAX plugin + standalone app. Plugin is multi-out (18 outs); standalone is stereo only (no multi-out) |
| Source | manual: `XLN Audio/XLN Addictive Drums 2/XLN Addictive Drums 2.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Addictive Drums 2 is a sample-based acoustic-drum instrument: world-class kits recorded in legendary studios with a full close/overhead/room multi-mic setup, multi-velocity layered with round-robin alternates. You build a custom kit from 18 Kit Piece slots (drawing from any owned ADpaks/KitpiecePaks), shape each raw sound (pitch, envelopes, tone, velocity response), then mix and finish it with a studio-grade channel strip on every channel (EQ, comp+distortion, tape+transient+limiter, noise, trig-gate) plus two combined delay→reverb "Delerb" sends. A large MIDI groove library (Beats page) with a Beat Transformer lets you find, tweak, and drag grooves straight into the DAW. The distinct value: it turns a multi-application "get acoustic drums to sound produced" chore into one fast click-through workflow — swap the kit (samples), the production (FX), and the drummer (MIDI) independently.

## Controls (every param → musical effect)

### Top section (global)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Play / Stop | — | Starts/stops the currently selected MIDI file (internal player) | Audition beats without the DAW |
| Play Sync | on/off | Makes AD2 follow host/DAW transport | Lock groove playback to the song |
| Tempo display | BPM (click+drag up/down) | Sets tempo of the internal player | Match preview/beat tempo |
| Lock Tempo (padlock) | on/off | Standalone: locks to a fixed tempo while browsing beats/presets. Plugin: tempo always locked to DAW | Keep one tempo while auditioning many grooves |
| Preset display / scroll | — | Shows current preset; click opens Preset Browser; scroll-wheel steps presets | Fast preset hopping |
| Preset prev/next | — | Step through presets | Sequential A/B of presets |
| Save Preset | Name, Type (Acoustic/Electronic/Percussion), Sound Ideal (Natural↔Extreme), MIDI Preview (Record/Play) | Saves a user preset with a tag for processing amount + an embedded preview beat | Store your kit; tag clean vs mangled for later sorting |

### Preset / Explore browsing
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Preset Browser filters | All/User/per-ADpak; Type; Name search | Narrow the preset list | Find a starting point by genre/source |
| Sound Ideal sort | Natural → Extreme | Sorts presets by amount of processing applied | Want dry/natural vs radio-ready/distorted fast |
| Set As Startup | — | Make a preset the default on launch | Pin your go-to kit |
| Explore page quick knobs | Kick / Snare / Hihat / Overhead / Room level | Fast balance of the most important elements | Quick rough mix while auditioning |

### Kit Piece slot (per slot, 18 slots: Kick, Snare, Hihat, Tom 1-4, Ride 1-2, Cym 1-6, Flexi 1-3)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Audition pad | click (vertical = velocity) | Plays the loaded Kit Piece; click higher = harder hit | Check the raw sound at a chosen dynamic |
| Mute / Solo | on/off | Isolate or silence a Kit Piece | Dial one piece, browse a single drum |
| Kit Piece prev/next | — | Step through Kit Pieces for the slot | Quick swap drums |
| Kit Piece Browser | — | Pick any owned Kit Piece into the slot (Flexi adds Kicks/Snares filters) | Build a custom kit; load percussion into Flexi |
| Link (kick/snare drag) | — | Drag link icon to another pad → they always play together | Layer kick+sub or snare+clap on one MIDI note |
| Kit Piece Volume | level | Overall level of that Kit Piece | Quick per-piece balance |
| Load Tom Set | menu (toms only) | Loads a matched tom group (also sets tom Pitch) | Get a coherent tom set in one click |

### Kit Piece basic settings (Edit page top)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Volume | level | Overall Kit Piece level (in the slot) | Balance piece in the kit |
| OH Level / Room Level | level | Amount of this piece in the Overhead and Room channels | Add ambience/air to an individual drum |
| OH/Room Pan | L↔R | Pan of this piece within OH/Room | Place a drum in the stereo room image |
| OH/Room Width | narrow↔wide | Stereo width of this piece in OH/Room | Widen or focus a drum's ambience |

### Kit Piece Controls (Edit page top — raw sound design)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Response · Volume | 0–200% | 0% = velocity-independent volume; 100% = "as recorded" dynamics; 100-200% extends dynamic range downward (softer soft hits) | Flatten dynamics (0%) or exaggerate them (>100%) |
| Response · Filter | amount | Exaggerates HF roll-off on softer hits | More natural soft hits; help triggers lacking soft samples |
| Response · Sample (Layer Selection) | exclude soft / hard / single layer | Restricts which velocity sample layers are used | Force one consistent sample, or drop the softest/hardest |
| No Alts | on/off | Turns off round-robin alternate samples → static, machine-like | Want intentionally rigid/electronic feel |
| Pitch · Main | ±12 semitones | Tunes the whole Kit Piece | Tune drum to track / change size feel |
| Pitch · Offset | ±12 semitones | Detunes OH/Room relative to Main | Phasey/wide tuning tricks on the ambience |
| Tone Designer · Start / End | levels (can boost above center) | (Kick & Snare only) shortens the decay of the tonal part without touching noise/room; End shows the affected frequency bands | Dampen ring/boom without losing length or ambience |
| Pitch Envelope · Start / Hold / Release | semitones / ms | Pitch sweep on the hit (classic "boing"/punch) | Add attack thump, 808-style drop, snare snap |
| Pitch Env · Vel | amount | Velocity controls amount of pitch envelope | Harder hits bend pitch more |
| Volume Envelope · Attack / Decay / Sustain Level / Sustain Time / Release | ms / dB | Full amplitude envelope of the Kit Piece | Tighten, gate, or sustain a drum |
| Vol Env · Vel | amount | Velocity controls Attack time (softer attack at low vel) | Natural softer hits |
| Cut · Range | Hi/Lo cut | High/low cut affecting ALL channels (Close/OH/Room) for that Kit Piece | Quick global tone shaping of the whole piece |

### Per-Kit-Piece special mic controls
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Snare Buzz | level | Volume of sympathetic snare buzz triggered when kick/toms play | Add realism; remove for a clean/electronic feel |
| Kick & Snare Close Mics Balance | slider (two close mics) | Snare: Top↔Bottom (more bottom = more buzz/wires); Kick: Beater↔Front (Beater = click, Front = deep bass) | Dial click vs body on kick; snap vs wires on snare |
| Room Distance | 0–50 ms (≈ up to 56 ft / 17 m) | Delays the room mics to simulate mic distance | Bigger/farther room sound |

### Channel strip — Insert Effects (every mixer channel; chain order as laid out)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Channel Inserts Enable | on/off (yellow, top-left) | Bypass ALL inserts on the channel (hatched when off) | A/B processed vs raw |
| **Noise** · Type | model select (arrows) | Chooses recorded noise source (mics/studios/machines), triggered by signal | Lo-fi, vinyl, tape-hiss color |
| Noise · Decay | time | Length of the noise burst per hit | Constant hiss → short stab per hit |
| Noise · Level | level | Amount of noise added | Subtle texture vs in-your-face grit |
| **MultiFX (mode A) Comp & Dist** | — | Combined compressor + distortion; each half has its own Enable | One-stop punch + crunch |
| Comp · Thr | dB | Compressor threshold (AutoGain keeps level in check) | Tame dynamics, add sustain |
| Comp · Ratio / Attack / Release | ratio / ms | Standard compressor controls; GR meter shows reduction | Shape transient/punch |
| Comp · Boost Mode | on/off (button above GR) | Multiband processing variant, same controls, very different sound | Aggressive parallel-style crush |
| Dist · Type | model select | Several distortion flavors | Add character to a flat drum |
| Dist · Range | freq slider | Restricts distortion to a frequency band (rest passes clean) | Crunch only the mids of a kick |
| Dist · Amount | amount | Drive into the distortion | More edge/saturation |
| Dist · Mix | dry↔wet | Blend clean vs distorted | Parallel distortion |
| **MultiFX (mode B) Tape & Shape** | — | Combined tape sim + transient shaper + saturating limiter (toggle from Comp&Dist via top-right arrows; only one mode active) | Analog glue + transient control |
| Tape · Drive | amount | How hard you push the tape | Warmth/compression of tape |
| Tape · Bottom | amount | Natural low-range boost from tape | Add weight |
| Shape · Attack | ±amount | Transient shaper attack — boosts/cuts the "snap" regardless of level | Add click or soften the hit |
| Shape · Sustain | ±amount | Level after the transient (up = gated-room feel, down = shorter) | Lengthen or tighten the tail |
| Sat · Gain / Threshold | dB | Saturating limiter — cuts spiky transients above Thr (adds slight crunch) | Tame spikes before the master comp |
| **EQ** · per band: Freq / Gain / Q | Hz / dB / Q | Parametric EQ — mono/close-mic channels 5 bands, stereo channels 4 bands; drag dots (X=freq, Y=gain, wheel=Q); live post-EQ analyzer behind graph | Carve/boost tone per channel |
| EQ · Hi/Lo Cut filters | Freq / Q | Extra cut filters dragged from graph sides | Clean rumble/fizz |
| **Trig Gate** (OH/Room/Bus/Master + each Delerb send) · Enable | Kick / Snare (Open1/Open2/Rimshot only) / Toms | Picks which Kit Pieces trigger the gate (MIDI-triggered, no audio threshold fiddling) | Mangle ambience yet keep tight gating |
| Trig Gate · Threshold | level | Excludes low-velocity hits (ghost notes) from triggering | Gate only the main hits |
| Trig Gate · Hold time | ms or note value (Tempo Sync) | Gate open duration; sync to musical value | Tempo-locked gated reverb |
| Trig Gate · Release | time | Fall time to Floor after hold | Smooth vs abrupt gate close |
| Trig Gate · Floor | -∞ to 0 dB | Level between hits (-∞ = fully gated, -10 dB = subtle ducking) | Punch-through ambience |
| **Cut** (Bus & Master only) · Range | Hi/Lo cut | High/low cut at end of chain; grab the middle to move both at once | Master tone shaping |
| **Output** · Trim | level | Level of the processed signal (match to unprocessed for even gain staging) | Keep gain structure / fair A/B |

### Mixer (14 channels: 10 mono close-mic [Kick, Snare, Hihat, Tom 1-4, Flexi 1-3], 2 stereo [OH, Room], Bus, Send FX, Master)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Pan | L↔R (up/down on stereo = width; reversible image) | Channel pan / stereo width | Place pieces in the field |
| Volume fader | level | Channel level | Core balance |
| Solo / Mute | on/off | Isolate/silence channel (Master has none) | Focus / drop a channel |
| Phase/Polarity | on/off | Flip polarity (Master has none) | Fix phase between mics |
| Separate Out | Master / Sep Out (Pre-Fader)[+Master] / Sep Out (Post-Fader)[+Master] | Route channel to a discrete host output (plugin only) | Mix kit in the DAW; kick→sidechain bass |
| Bus Send (when Bus selected) | level per channel | Sends a submix to the Bus channel | Parallel-crush/distort a kick+snare+hihat submix |
| FX Sends (per channel ×2) | level + enable | Sends to the two Delerb (delay→reverb) units | Add space/echo per piece |

### FX page — two identical Delerb units (delay→reverb)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Delay · Time | ms or Tempo Sync | Delay time (drag graph L/R for time+reverb) | Slap/echo, tempo-synced delays |
| Delay · Feedback | 0–100% | Repeats (0% = one repeat, 100% = infinite); drag graph up/down | Build echo trails |
| Delay · Swing | amount | Shuffle/swing on the echoes | Groovy delay feel |
| Delay · Ping Pong | on/off | Bounces echoes L↔R | Wide stereo delay |
| Delay · Range | freq | Limits delay frequency range | Keep delays out of the low end |
| Delerb Crossfader | delay↔reverb | Balance between delay and reverb in the unit (graph updates) | Set how much echo vs space |
| Reverb · Type | model select | Reverb algorithm/flavor | Plate vs ambience vs hall feel |
| Reverb · Pre-delay | time | Delays reverb after the transients | Clearer, punchier mix |
| Reverb · Decay | time | Reverb length (drag graph up/down) | Short room → long tail |
| Reverb · Damping | amount | Tames HF reflections/ringing | Darker/smoother tail |
| Reverb · Swirl | amount | Adds chorus thickness to the tail | Lush, wide reverb |
| FX EQ | 2 bands (Freq/Gain/Q) | EQ on the Delerb (same behavior as channel EQ) | Shape the wet signal |
| FX Trig Gate | see channel Trig Gate | Gates the Delerb output via MIDI triggers | Gated reverb on the sends |
| Delerb Output · Level / Pan | level / L-R | Wet return level+pan (also in mixer Send FX); can solo the wet | Blend/solo the effects return |
| Delerb Output Routing | Pre Master Inserts / Post Master Inserts | Whether the wet hits the Master inserts or bypasses them | Compress whole mix incl. reverb, or keep reverb natural |

### Beats page (MIDI groove library + Beat Transformer)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Library / Filters | All MIDI / MIDIpak / Favorites; Style, Tempo (±10/20%), Time Sig; Beats/Fills; Name | Browse/search the groove library (+ external MIDI folder) | Find a groove fast |
| Grid Search | paint 1-bar 16th grid; Snare→Sidestick, Hihat→Open/Ride; Search/Replace/Search&Replace per lane | Find beats by kick/snare pattern, or force a pattern (Replace) | Match or impose a specific rhythm |
| Main Beat / Variant lists | select + heart (Favorite) | Choose a beat and its variants | A/B variants, mark favorites |
| Beat Transformer · Range | compress/expand/shift | Reshapes velocity range of the beat | Even out or exaggerate dynamics |
| Beat Transformer · Accents (8th/16th) | ±amount | Adds positive/negative accents on the grid | Add groove/swing emphasis |
| Beat Transformer · Random (Timing/Velocity) | amount | Humanizes timing/velocity separately | Loosen stiff programmed beats |
| Kit Piece Mix & Reassign | per-piece level, Mute/Solo, Reassign dropdown | Velocity per piece; isolate; swap articulation (e.g. snare→sidestick) | Rebalance/re-voice the groove |
| Speed / Length | half/double/etc · bars | Change playback speed and loop length | Halftime feel, longer phrases |
| Reset All | — | Revert all transforms | Start over |
| Record MIDI / Mark First Beat | — | Record from e-drum or AD2 track (DAW cycle auto-loops); realign where the beat starts | Capture grooves; align to chorus |

### Utility
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Audio Recorder | up to 15 s, records Master out; drag to DAW/desktop | Continuously records Master; file created only on drag, overwritten each time | Bounce a hit/loop as audio to chop/reverse |
| MIDI Mapping window | per-piece notes, stroke types, hihat CC, positional snare/ride, cymbal chokes, PowerMap | Maps e-drums and external MIDI (GM etc.) to AD2 | E-kit setup; use 3rd-party MIDI grooves |

## Use by lens
- **Producer (create):** Start on Explore/Preset Browser by genre, then build a custom kit in the Kit Piece slots from any owned ADpak. Sound-design raw drums with Pitch/Pitch-Env (punch, 808 drop), Tone Designer (dampen ring on kick/snare), Volume Env (tighten/gate), and Response/No Alts/Sample (force consistency or exaggerate dynamics). Use the Beats page + Beat Transformer to find and humanize a groove, then drag MIDI (or audio via the Recorder) into the DAW. Layer with Link (kick+sub, snare+clap) and the Flexi slots for percussion.
- **Mixing (balance):** Treat it like a real kit. Balance with the mixer faders/pans; add air via per-piece OH/Room Level + Room Distance; carve tone with per-channel EQ (5-band on close mics). Punch and character come from MultiFX Comp&Dist (incl. Boost multiband) and Tape&Shape (transient Attack/Sustain, Sat limiter). Build a parallel "crunch" submix on the Bus (send kick+snare+hihat, distort/compress, blend back). Add space with the two Delerb sends. Use MIDI-triggered Trig Gate for tight gated reverb/ambience without threshold fuss. Use multi-out (plugin) to mix individual pieces in the DAW.
- **Mastering (finalize):** Not a master-bus tool. The closest internal "glue" stage is the Master channel (its own EQ, MultiFX comp/limiter, Cut filter, Output Trim). Tame spiky transients per-channel with the Sat limiter so the Master comp behaves. For finalizing a full song, print AD2 and use a dedicated bus/master processor.

## Notes / gotchas
- **No 1:1 Kit Piece ↔ mixer channel.** Cymbals/rides have no close mics — they live only in OH/Room, but you can still adjust them in Kit Piece Controls. 10 mono + 2 stereo (OH, Room) + Bus + Send FX + Master = 14 channels.
- **MultiFX is one slot, two modes:** Comp&Dist OR Tape&Shape — only one active at a time per channel (toggle via the unit's top-right arrows).
- **Trig Gate is MIDI-triggered** (not audio-threshold) → perfect gating even on heavily mangled signals; available on OH/Room/Bus/Master and each Delerb send. Snare triggers only on Open 1/Open 2/Rimshot stroke types.
- **Two Delerb sends** = each is a delay feeding a reverb (not separate delay+reverb units). Output routing can sit Pre- or Post-Master-Inserts.
- **Multi-out is plugin-only** (standalone = stereo). Fixed out map: 1+2 Master, 3 Kick, 4 Snare, 5 Hihat, 6-9 Tom 1-4, 10-12 Flexi 1-3, 13+14 OH, 15+16 Room, 17+18 Bus. Some hosts (Logic) offer a "stereo version" — load the multi-out version if you want separate outs.
- **Control editing:** Shift = fine resolution; Cmd/Ctrl+click = reset to default; scroll-wheel edits most controls; right-click = copy/paste channel or insert settings (even between AD2 instances); darkened ("off") sections activate when you touch a control.
- **Cloud Sync** auto-uploads user presets/keymaps/favorites to the XLN account; first launch on a new machine downloads them.
- **Sound Ideal** tag (Natural↔Extreme) on presets is purely a sort/label aid for how processed a preset is.
- **Audio Recorder** overwrites the same file each drag — import/rename in the DAW pool before recording again.
- **Loading indicator:** playing while still loading may produce silence/glitches until it finishes.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
