# 08 — Rhythm Techniques & Production Workflow

Sources: Mike Adamo "Breakbeat Bible" (Hudson Music) · Ethan Hein "Classic Breakbeats" pattern reference · LMD Lesson Book · Pegada Drum Method.

Companion to `07-famous-drum-beats.md` (80 named beats catalogued). This file is technique-level and production-workflow: how to chop, stretch, layer, and program breakbeats — not per-song documentation.

---

## 1. Breakbeat Fundamentals

**Definition:** funk drumming played with loop precision. Feel = funk; timing = machine-tight. Live-drumkit phrase recorded once, then sampled, chopped, looped.

⚡ **Quantization rule:** keep ON for all breakbeat work EXCEPT J Dilla-style. Dilla programmed with quantize disabled — humanised swing comes from offset placement, not swing %. Mixing the two destroys both.

**The pocket — "in between the cracks":**
- Straight 16ths = mechanical
- Swung 16ths = jazz / shuffle
- Breakbeat pocket = halfway between. Hi-hat and snare sit slightly behind straight; kick lands on the grid. Listener feels swing without the triplet.

**Tempo targets:**

| Genre | BPM | Source break behaviour |
|---|---|---|
| Boom-bap hip-hop | 85–95 | Original tempo or slowed |
| West Coast hip-hop | 90–105 | Original tempo |
| Trap (half-time feel) | 130–150 (counted half) | Half-time snare on 3 |
| Drum'n'Bass | 160–180 | Amen stretched +30% |
| Jungle | 190–210 | Amen stretched +40–50% |
| Footwork | 155–165 | Triplet-shifted hi-hat |

**Three practice / programming concepts:**
1. **Transcribe & play along** — load a reference loop, count 16ths aloud, mimic on pads 10×, then record and compare.
2. **Metronome cracks** — set click to quarter notes; place hi-hat between the straight and swung subdivision until it feels neither.
3. **Half-note breathing pulse** — feel the loop as 2 big beats (not 4 or 8) — keeps programming open instead of cluttered.

---

## 2. Ghost Note System — Five Subtypes

Ghost notes are the texture / colour / depth of a break. They must NOT disturb the main pulse.

⚡ **Cardinal ghost rule:** when snare accents, hi-hat stays smooth. Never accent both simultaneously — kills the pocket.

⚡ **Ghost velocity:** 20–30% of accent velocity. Wrist-only motion, ~1 inch off head. In a DAW: ghost = 20–35 / accent = 100–115 / rimshot = 127.

**The 5 two-16th-in-a-row subtypes (one hand, both notes consecutive):**

| Subtype | Pattern | Velocity shape | Musical function | Where it lives |
|---|---|---|---|---|
| **Both mezzo-forte** | accent + accent | equal medium | Drive, sustained motion | Straight rock 8ths |
| **Both ghosted** | ghost + ghost | both 20–30% | Texture under groove | Funk hi-hat under snare |
| **Control stroke** | accent → ghost | 100 → 25 | Forward motion. Most common: downbeat + "e" | Funk snare ghosts |
| **Pull out** | ghost → accent | 25 → 100 | Anticipation. Most common: "ah" → next downbeat | Lead-in to backbeat |
| **Pull out into control stroke** | ghost → accent → ghost | 25 → 100 → 25 | Three notes one motion. Clyde Stubblefield signature. | Funky Drummer ghost cluster |

⚡ **Practice tempo for pull-out-into-control-stroke:** start at 40 BPM. Below this the motion is one fluid arm gesture; above it becomes three discrete strokes and loses the feel.

**Dynamic vocabulary = structural vocabulary.** Each of the 5 subtypes has a distinct musical job — choose by function, not by hand.

---

## 3. Classic Break Production Notes

Pattern anatomy for each break → `07-famous-drum-beats.md`. This section covers production-specific traps and manipulation rules only.

| Break | Production rule |
|---|---|
| **Funky Drummer** | Kick NOT on beat 3 — never quantise that away. Ghost cluster between backbeats is the groove; gating kills it. ~12 chop points/bar. |
| **Amen Brother** | 4-bar phrase; ride NOT hi-hat — open shimmer is the identity. Bar 4 snare roll = main chop point. signalsmith-stretch OK to +20%; above +35% layer fresh transients under stretched cymbals. |
| **Apache** | Keep conga interlock intact — removing one conga destroys the polyrhythm and the loop sounds empty. |
| **Synthetic Substitution** | Kick doubles on beat 1 AND "+"-of-1. Snare crack is the sample trigger. Safe to stretch to 160–175 BPM for jungle/DnB. |
| **Impeach The President** | Snare on 2, **3**, and "+" of 4 — snare on 3 (not 4) is the identifier. Open HH on "a" of 1 and "a" of 4. |
| **When The Levee Breaks** | Stairwell reverb IS the sound. Do NOT gate the reverb tail. Sampling clean = wrong sample. |

### BPM Reference Table

| Pattern | Original | Hip-Hop range | Jungle/DnB range |
|---|---|---|---|
| Funky Drummer | 98 | 85–100 | — |
| Amen Brother | 136 | 85–95 | 160–180+ |
| Apache | 103 | 85–100 | — |
| Synthetic Substitution | 100 | 88–105 | 160–175 |
| Impeach The President | 100 | 88–105 | — |
| When The Levee Breaks | 70 | 70–85 | 140–160 |
| Mardi Gras | 92 | 85–98 | — |
| Billie Jean | 117 | 90–110 | — |

---

## 4. Pattern Manipulation Techniques

### 4.1 Chopping

⚡ **Slice at the transient zero-crossing, not the visual peak.** Cutting on the peak introduces a click on retrigger.

| Method | Use for | Tool |
|---|---|---|
| **Single-hit slice** | Replay break note-by-note on pads | MPC-style chop |
| **2-beat slice** | Rearrange halves of the bar | Half-bar reshuffle |
| **Stutter chop** | Repeat one slice on 16ths/32nds | Effect / fill |
| **Snare-targeted chop** | Replace only the snare layer | Layered re-imagining |

**Chop rule of thumb:** Amen Brother has ~20 useable slice points per 4-bar phrase. Funky Drummer has ~12 per bar. Apache has ~8 per bar (kick + snare + conga clusters as units).

### 4.2 Time-Stretch

| Stretch range | Preferred algorithm | Notes |
|---|---|---|
| ±5% | Resampling (varispeed) | Pitch shifts with tempo. Old-school sound. |
| ±5–20% | signalsmith-stretch | Transparent, transient-preserving. our default. |
| ±20–40% | RubberBand formant-preserved | Phasey on cymbals — accept it or layer dry transients on top. |
| >+40% | Granular or texture replacement | Stretched cymbals become pads. Use as a texture, not as drums. |

⚡ **Jungle Amen rule:** above +35% stretch, layer a fresh dry kick + snare under the stretched break so transients survive. Stretched cymbals become atmosphere.

### 4.3 Pitch-Shift

- **Pitch up 2–4 semitones:** classic "sped-up break" sound (golden-era hip-hop, jungle).
- **Pitch down 2–5 semitones:** Houston / DJ Screw, lo-fi heaviness.
- ⚡ **Independent pitch ≠ varispeed.** Varispeed pitches AND tempos together (analog tape feel); independent pitch preserves tempo (modern). Pick deliberately.

### 4.4 Ghost Note Preservation

⚡ **Do not noise-gate breakbeats.** The ghost notes ARE the groove. Gating raises threshold above ghosts → groove dies.

- Transient designer: reduce sustain to tighten kicks/snares without touching ghost velocity.
- Parallel compression: bus-compress 4:1 ratio, blend 30% under dry — pulls ghosts forward.
- Mid/Side EQ: cut 200–400 Hz on Mid to clean kick, leave Side cymbals/ghosts intact.

---

## 5. Genre Groove Signatures

| Genre | Hi-Hat | Snare | Bass Drum | Signature characteristic |
|---|---|---|---|---|
| Rock | Straight 8ths (shank) | Rimshot 2 & 4 | Beat 1 + syncopation | Driving |
| Jazz | Ride: Chang-Chang-Choo-Chang | Charleston accents | Feathered quarters | Triplet feel |
| Shuffle / Blues | Triplet shuffle (middle note removed) | Ghost + 2 & 4 | Shuffle subdivision | 12/8 feel in 4/4 |
| Second Line (NOLA) | Heel-toe alternating | Accented "big four" | Complex syncopation | "And" of 4 accent |
| R&B / Funk | Open/close accent | Ghost + backbeat | Syncopated upbeats | Pocket |
| Latin (Son) | Cascara | Cross-stick / backbeat | Tumbao (rest on 1) | Son clave anchor |
| Samba | Upbeats | Cross-stick cruzado | Samba pattern | Accent "a" of beat |
| Reggae (One Drop) | Triplet upbeats only | Cross-stick beat 3 | Absent (drops beat 1) | Back-heavy, spacious |
| Hip-Hop | Open HH upbeats | Half-time (beat 3) | Heavy syncopation | Space + weight |
| Motown | Shuffle or quarters | Ghost + 2 & 4 | Syncopated quarters | Ghost density |
| Drum'n'Bass | 16ths or stuttered breaks | 2 & 4 on half-time count | Sub-heavy syncopation | Stretched Amen |

---

## 6. Rhythmic Feel Rules

| Feel | Definition | Subdivision count |
|---|---|---|
| Straight | Even subdivision | 1-e-+-a |
| Triplet / swing | Three per beat | 1-trip-let |
| Shuffle | Triplets with middle note removed | 1—let (gap) |
| Compound (6/8, 12/8) | Inherently triplet — group in 3s, NOT 2s | 1-2-3, 4-5-6 |
| Half-time | Snare on 3 only (not 2 & 4) | Doubles perceived BPM |
| Double-time | Snare on every beat | Halves perceived BPM |

⚡ **Half-time / double-time = perception trick, not tempo change.** BPM stays constant; backbeat position shifts. Use for trap (half-time feel at 140 BPM = 70 BPM groove) and DnB (double-time feel at 87 BPM = 174 BPM groove).

⚡ **Compound meter rule:** count 6/8 as "1-2-3, 4-5-6" (two big beats), not "1-2-3-4-5-6" (six small beats). The former phrases musically, the latter sounds like a math exercise.

---

## 7. Clave (Latin) Rules

⚡ **All Latin instruments relate to the clave. It is the rhythmic anchor — non-negotiable.** If the clave flips, the whole arrangement must flip with it.

**Son Clave (3-2):**
```
1 e + a  2 e + a  3 e + a  4 e + a
X . . X  . . X .  . . X .  X . . .
```

**Rumba Clave (3-2):** identical except the 3rd note delays from "+ of 2" to "a of 2" — gives Rumba its hotter forward drive.

**Direction — 2-3 vs 3-2:** which "side" of the clave plays first.
- **3-2:** 3-note bar first, then 2-note. Classic son montuno.
- **2-3:** 2-note bar first. Common in salsa, mambo.
- ⚡ Direction follows the melody's rhythmic accents — pick the side that aligns the melody's strongest accent with the clave's strong note.

**Tumbao bass:** rests on beat 1, plays "+" of 2 and beat 4. Characteristic back-heavy Latin bass feel. Beat 1 is felt by absence, not played.

**Cascara:** the ride pattern of Latin drumming — played on timbale shell. Equivalent role to the hi-hat in funk: drives the time without occupying the backbeat.

---

## 8. Groove Construction Formula

```
GROOVE = Ostinato                  steady repeating pattern, 1–2 limbs
       + Backbeat                  accent on 2 & 4 (or beat 3 for half-time)
       + Bass drum variation       syncopation against the ostinato
       + Ghost notes               snare micro-dynamics below backbeat
       + Hi-hat nuance             open/close, accent placement
```

Build groove by layer. Skipping a layer creates a recognisable sub-style:

| Skip | Result |
|---|---|
| Ghost notes | Rock / pop programmed feel |
| Hi-hat nuance | Trap / 808 minimalism |
| Backbeat displacement | Reggae / one-drop |
| Bass drum syncopation | Marching / military |
| Ostinato | Free jazz / drum solo |

---

## 9. Fill Philosophy

⚡ **Silence > unnecessary fill.** A fill must serve the music, not the ego.

**Six fill rules:**
1. Silence > unnecessary fill.
2. Fill serves the music, never the ego.
3. Breathe through fills — stay in tempo, don't rush.
4. Know what you'll play BEFORE starting. No improvising mid-fill.
5. Volume direction: complex (floor toms) → simple (snare) for loud→soft; reverse for soft→loud.
6. Use a double hit (RR or LL) to change lead-hand direction around the kit.

⚡ **Crash rule:** never crash on beat 1 before a singer's first lyric. The crash steps on the vocal entrance.

**Fill construction — tom routes:**

| Drums used | Route options |
|---|---|
| 2-drum | Sn–T1 · Sn–T2 · Sn–FT · T1–T2 · T2–FT |
| 3-drum | Sn–T1–T2 · T1–T2–FT · Sn–T1–FT · T1–Sn–T2 |
| 4-drum | Sn–T1–T2–FT · Sn–T1–T2–Sn · T1–Sn–T2–FT |

Fills resolve on beat 1 of the next bar, typically with crash + bass drum landing simultaneously.

**Ensemble figure rule:**
- Whole-band figure → reinforce with BD + cymbal.
- Section-only figure → reinforce subtly (rimshot, splash).

**Solo construction (5 rules):**
1. Start simple → build complexity.
2. Use motifs; develop them.
3. Repetition = listener comprehension.
4. Silence is a musical statement.
5. Dynamics = the arc.

---

## 10. Rudiments Reference

| Rudiment | Sticking | Category | Production use |
|---|---|---|---|
| Single Stroke Roll | RLRLRLRL | Roll | Tom fills, blast beats |
| Double Stroke Roll | RRLLRRLL | Roll | Fast fills, foundation |
| 5-Stroke Roll | RRLL R | Roll | Short fill cap |
| 7-Stroke Roll | RRLL RRL | Roll | 3-beat fill |
| 9-Stroke Roll | RRLL RRLL R | Roll | 4-beat fill |
| Single Paradiddle | RLRR LRLL | Paradiddle | Linear-funk lead-hand switch |
| Double Paradiddle | RLRLRR LRLRLL | Paradiddle | 6/8 grooves |
| Paradiddle-diddle | RLRRLL LRLLRR | Paradiddle | Fusion / linear ostinato |
| Flam | lR or rL (grace + main) | Flam | Thick backbeat |
| Drag | rrL or llR (2 grace + main) | Drag | Lead-in snare ornament |

**Sticking-combination system (apply to any exercise):**

| Code | Pattern | Use |
|---|---|---|
| S/S | RLRL RLRL | Default — even hand wear |
| D/D | RRLL RRLL | Power, fewer accents |
| S/D | RLRL RRLL | Linear funk lead-hand switch |
| D/S | RRLL RLRL | Reverse linear, weak-hand emphasis |

⚡ **Programming use:** S/D and D/S generate asymmetric velocity profiles that humanise programmed drums — the natural slight velocity drop on each hand's 2nd consecutive hit reads as "real player".

**Rock groove HH progression (build complexity by subdivision):**
1. Quarter notes: `x . x . x . x .`
2. Eighth notes: `x x x x x x x x`
3. Dotted eighth + 16th
4. Sixteenth notes: `xxxx xxxx xxxx xxxx`

**Bass-drum pattern library (against 8th HH, snare 2 & 4):**

| Code | BD positions |
|---|---|
| A | 1, 3 |
| B | 1, 2, 3 |
| C | 1, 3, 4 |
| D | 1, 2, 3, 4 |
| E | 1-and, 3 |
| F | 1, 2-and, 3, 4 |
| G | 1, "+"-of-2, 3 |
| H | 1, 3, 3-and |

---

## 11. Essential Listening (by genre)

| Genre | Drummers to study | Why |
|---|---|---|
| Jazz | Elvin Jones, Tony Williams, Steve Gadd, Vinnie Colaiuta | Triplet vocabulary, ride independence |
| Rock | John Bonham, Neil Peart, Keith Moon, Jeff Porcaro | Bonham = pocket; Porcaro = ghost-note master |
| R&B / Funk | Bernard Purdie (Purdie shuffle), Clyde Stubblefield, Jabo Starks, Al Jackson Jr. | Defines funk pocket + ghost vocabulary |
| Latin | Mongo Santamaria, David Garibaldi (Latin-funk) | Clave + tumbao authority |
| Hip-Hop foundational | Clyde Stubblefield, Gregory C. Coleman, James Gadson | The breaks every sampler relies on |
| Drum'n'Bass / Jungle | Photek, Goldie, DJ Krush (programming) | Amen chopping vocabulary |

---

## 12. Production Notation Legend

| Symbol | Meaning |
|---|---|
| `X` above staff | Hi-hat or ride cymbal |
| `X` with ° | Open hi-hat |
| Filled notehead | Drum hit |
| `>` above note | Accent |
| `( )` around note | Ghost note (very soft) |
| `R` / `L` | Right hand / left hand |
| `3` above beam | Triplet |
| Wavy line | Roll / tremolo |
| Small notes before main | Grace notes (flam / drag) |

**Equipment notes (for sample-library taxonomy):**
- Coated heads → warmer, less attack.
- Clear heads → brighter, more attack.
- Stick size: 5A = standard, 5B = rock, 7A = jazz / brushes.

---

## Cross-References

- `07-famous-drum-beats.md` — 80 named beats catalogued by song. Use for "what does X sound like?". This file = how to BUILD / MANIPULATE; that file = REFERENCE.
- `03-composition-methods.md` — song structure, arrangement, where to place the breakbeat in the arrangement.
- `05-quick-decisions.md` — fast lookup for kick/snare/hi-hat synthesis start points.
- `06-music-theory.md` — meter, polymeter, polyrhythm theory.
- `02-sound-design-recipes.md` — kick/snare/hi-hat synthesis recipes.
- ADR `0014-chord-aware-loop-variation-lm19.md` — loop-variation engine that consumes pattern metadata.
