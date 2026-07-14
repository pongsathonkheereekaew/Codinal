# Music Theory — Modernist: Late 19th-c Chromatic + 20th-c Scales / Chords / Texture

> Originally part of `06-music-theory.md`. Split for load efficiency. Owns §13–§20 of
> the original numbering: late-Romantic chromatic techniques (Kostka/Payne Ch. 27) +
> 20th-century scales, chord structures, set theory, twelve-tone, total serialization,
> rhythm/meter innovations, texture/extended techniques (Kostka/Payne Ch. 28).

---

## 13. Late 19th-Century Chromatic Techniques [Kostka/Payne Ch. 27]

These are post-Romantic moves that dissolve traditional harmonic function. Useful for cinematic, ambient, and chromatic variation.

### Omnibus Progression
A chromatic series of chords harmonizing a chromatic bass line by treating chords between two root-position V7 chords as Ger+6 or cadential 6/4 passing chords. Creates intense harmonic motion with zero functional root movement. Bass moves chromatically while inner voices sustain or move minimally.
- In practice: `Bb: V7 → [V6/4, ii°+6, I6/4-passing] → V7` with bass C→B→Bb→A→Ab descending.
- DSP proxy: chromatic pitch-shift sequence across bass slice: −1 st steps.

### Chain of Dominant 7ths in Parallel
V7 chords moving in strict parallelism (all four voices move together by same interval). No resolution — pure coloristic motion. Fauré's move — parallel V7 sonorities leading eventually to a brief tonicization.
- Rule: strict parallelism requires consistent chord quality (all Mm7), makes tonal center unclear.
- DSP proxy: repeat V7 stamp slice pitch-shifted by consistent interval (e.g., every +2 st or +3 st).

### Sequential Modulation as Legitimizer
Sequences "legitimize" nontraditional chord relationships by imposing a pattern. Ears accept a foreign chord if it's the next step in an audible sequence, even with no diatonic logic (Rimsky-Korsakov example: whole-step sequential tonicizations C# → A → F# → E half-cadence).
- Rule: minimum 2 sequential units needed for listener to perceive the pattern before the "surprising" unit.

### Double Chromatic Mediant [extends `06b-secondary-borrowed.md` §8 content]
Two chords whose roots are a M3 or m3 apart **and** are of contrasting quality (major ↔ minor). Zero common tones, two chromatic inflections required.
- Examples (from A): a minor → C# major, a minor → F# major; A major → c minor, A major → f minor.
- Vs. chromatic mediant (Ch. 26): same quality, one common tone, one chromatic inflection.
- Vs. diatonic mediant: same quality, two common tones, no chromatic inflections.
- Effect: startling tonal shift, incompatibility of both sonorities in any single diatonic key.
- DSP proxy: pitch-shift by +4 st (M3) or +3 st (m3) AND flip quality (if major chunk → treat as minor source material).

### Shifting Keys / Expanded Tonality
Post-Romantic composers avoid confirming the tonic through:
1. Avoiding V→I cadences (use plagal, deceptive, or half-cadence instead).
2. Rapid modulation via sequence — no single key "wins."
3. Double chromatic mediant jumps between tonics.
4. Linear (contrapuntal) voice leading that blurs vertical harmony.
Result: "expanded tonality" — a tonal center exists but is never confirmed. The listener is always expecting resolution that never fully arrives.

### Mystic Chord (Scriabin)
A chord stacked in 4ths (rather than 3rds): C–F#–Bb–E–A–D. Whole-tone collection with one deviation. Related to Lydian-Mixolydian scale (see § 14). No perfect 5th → no dominant function → no resolution pull. Creates hovering, restless ambiguity.
- Structural property: 3 consecutive whole tones create a tritone as the framing interval → tonal restlessness is built in.

### Nonconcentricity (Non-concentric Tonality)
A composition that opens and closes in **different** keys. Contrasts with concentric/centric (opening = closing key). Mahler's *Kindertotenlieder* No. 2 is the textbook example.
- Analytical flag: if a piece's final bars imply a different tonal center than the opening, label it non-concentric.

---

## 14. 20th-Century Scales [Kostka/Payne Ch. 28]

### Church Modes — Brightness Ordering
All use the same white-key pitch classes (C–B), only the final/tonic differs. Ordered from brightest (most major intervals above final) to darkest:

| Mode | = Major scale starting on | Signature alteration vs. major |
|---|---|---|
| **Lydian** | F | #4 (raised 4th) |
| **Ionian** | C | = major |
| **Mixolydian** | G | b7 |
| **Dorian** | D | b3, b7 (natural minor + raised 6) |
| **Aeolian** | A | = natural minor |
| **Phrygian** | E | b2, b3, b6, b7 (natural minor + lowered 2) |
| **Locrian** | B | b2, b3, b5, b6, b7 — no true dominant; rare in composition, common in jazz improv |

**Comparison shorthand:**
- Modes with #4 or raised tones → brighter/major-flavored: Lydian, Ionian, Mixolydian
- Modes with b2 or lowered tones → darker/minor-flavored: Dorian, Aeolian, Phrygian, Locrian

**Lydian-Mixolydian hybrid** (Debussy's favorite scale): #4 AND b7 simultaneously. Equivalent to stacking two major-minor (Mm7) chords whose roots are a whole step apart. Contains both Bb and F# → impossible on white keys alone.

### Pentatonic Scales
- **Anhemitonic (diatonic) pentatonic**: C–D–E–G–A (5 pitches, no half steps, no tritones). Harmonically static — no leading tone, no tritone → avoids resolution pressure. Any of the 5 pitches can serve as tonic.
- **Hirajoshi (Japanese)**: different step pattern, includes half steps, more exotic color.
- From stacked 5ths: G–D–A–E–B = C–D–E–G–A (pentatonic emerges from the circle of 5ths).

### Whole-Tone Scale
6 notes, all whole steps. Intervals: only M2, M3, tritone (and their inversions).
- No perfect 5th, no perfect 4th → no dominant/tonic function.
- Only 2 distinct whole-tone scales exist (all others are transpositions of one of the two).
- Sonorities built from it are "whole-tone chords." The Fr+6 chord is structurally derivable from the whole-tone scale.
- DSP proxy: pitch material derived from +2 st steps only (no +1 or +3).

### Octatonic Scale (Diminished Scale)
8 notes from superimposing two diminished 7th chords at interval of half step or whole step:
- **Half-step version**: alternating H–W (semitone then whole tone)
- **Whole-step version**: alternating W–H
Contains all 3 minor triads + alternating major 2nd inversions, plus 4-note chords with exotic quality.
- Only 3 distinct octatonic scales exist.
- Used by Russian Five (Rimsky-Korsakov), Messiaen, Bartók.
- Designation: 4+1 (four whole steps, one half step separating them).

### Half-Step Minor-3rd Scale
From juxtaposing two augmented triads at a half-step interval. 6 notes. Distinct from whole-tone by containing minor 3rds and half steps.

---

## 15. 20th-Century Chord Structures [Kostka/Payne Ch. 28]

### Quartal / Quintal Harmony
Chords built from stacked 4ths (P4) or 5ths (P5) rather than 3rds.
- Avoids major/minor quality implications → tonally ambiguous but not atonal.
- Debussy's "La Cathédrale engloutie": chords built in 5ths and 4ths over pentatonic pitch material.
- Hindemith's quartal writing maintains B as tonal center via bass line (Dorian scale on B).
- Notation: no standard Roman numeral — label by root + "quartal" or just describe intervallic structure.
- DSP proxy: layer slices at +5 st (P4) or +7 st (P5) intervals on top of source.

### Secundal Harmony (Tone Clusters)
Chords built from stacked 2nds (M2 or m2).
- **Secundal chords**: stacked major or minor 2nds, forward/angular melodic character.
- **Tone cluster**: 3+ pitches in 2nd relationship played simultaneously. Henry Cowell (pianist uses fists/palms/forearm).
- Effect: dense dissonance, percussive texture, no harmonic function.
- Soft cluster (M2 spacing) vs. hard cluster (m2 / chromatic spacing).

### Tall Chords: 9ths, 11ths, 13ths (Extended Tertian)
Stacking 3rds beyond the 7th:
- **9th chord**: root–3–5–7–9. Most common extended chord. 9th typically resolves down by step. Present in functional tonal music (Schumann, Chopin, Beethoven) — 11ths and 13ths are rarer pre-20th century.
- **11th chord**: adds the 11th (= 4th) — often omitted or raised (#11 = Lydian sound).
- **13th chord**: root + all 7 diatonic pitches of a scale simultaneously. Omitting 5th and 11th common.
- In 20th century: tall chords used coloristically (not functionally) — traditional resolution rules may not apply.
- **Lead-sheet symbols**: Cmaj9, Cm9, C9(#11), C13, Cm11, etc.

### Split-Third Chord
A chord that simultaneously implies both major and minor quality — the major and minor 3rd sounded together (a m9 apart, or presented in separation). Effect: bitonal color on a single root. Used in Ravel and impressionism.

### Polychord
Two (or more) triads/seventh chords sounded simultaneously from **different keys**. Notated as fraction: `F/C` = F major triad over C major triad.
- Sharp dissonance when roots are a half-step or tritone apart.
- Less dissonance when roots share a common key signature.
- Distinct from "slash chord" (inversion notation) — polychord implies two independent triads.

### Bitonality / Polytonality
Two or more key centers heard simultaneously. For bitonality to register, each key must have uncomplicated harmonic motion. Bartók "Playsong" (Mikrokosmos No. 105): one hand in C, other in F#.
- Polytonal ≠ polyrhythmic (rhythm separate parameter).

### Pandiatonicism
Technique of equalizing all 7 pitches of a diatonic scale so no single pitch is heard as tonic. Contrapuntal texture; angular individual lines. Stravinsky's Petrouchka "Danse russe." No clear tonal center despite using only diatonic pitches.
- Designation "4+1 scale" sometimes useful.
- Distinct from modal writing (which does have a final/tonic).

---

## 16. Set Theory — Atonal Analysis Vocabulary [Kostka/Payne Ch. 28]

Pitch-class numbers (C=0 through B=11):

| C | C#/Db | D | D#/Eb | E | F | F#/Gb | G | G#/Ab | A | A#/Bb | B |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |

**Normal order**: arrange pitch classes in ascending order with smallest interval framing the set (smallest interval between first and last, octave = modulus 12).

**Prime form**: read intervals smallest-to-largest from left to right (and compare with retrograde to pick the most compressed form). Written as [0,1,6] etc.

**Interval class**: reduce any interval to its smallest form (inversion doesn't matter):
| Class | Intervals |
|---|---|
| 1 | m2 (1), M7 (11) |
| 2 | M2 (2), m7 (10) |
| 3 | m3 (3), M6 (9) |
| 4 | M3 (4), m6 (8) |
| 5 | P4 (5), P5 (7) |
| 6 | TT (6) |

**Interval vector**: 6-digit series showing how many times each interval class appears in the set. Format: `<ic1, ic2, ic3, ic4, ic5, ic6>`.

**Cardinality**: number of pitch classes in the set (trichord = 3, tetrachord = 4, hexachord = 6, etc.).

**Practical use for Easby**: set theory provides pitch-content fingerprint of a loop's harmonic material. If the source material reduces to prime form [0,1,6] (tritone-heavy), variation operations that avoid tritone resolution (no V→I) are appropriate.

---

## 17. Twelve-Tone Technique [Kostka/Payne Ch. 28]

Developed by Arnold Schoenberg. Systematic avoidance of any pitch as tonal center.

### Pre-12-tone atonal procedures (Schoenberg Op. 11):
1. Avoid P8 as melodic or harmonic interval.
2. Avoid traditional pitch collections (major/minor triads).
3. Avoid 3+ successive pitches from same diatonic scale.
4. Use wide-ranging, extremely disjunct melodies.

### Tone row rules:
1. Composition based on a specific **ordering** of all 12 pitch classes — the **tone row** (also called series or set).
2. No pitch repeated until all 12 have sounded (exception: immediate repetition, trills, tremolos).
3. Row may be used in 4 forms:
   - **P** (prime/original): as composed
   - **R** (retrograde): reversed order
   - **I** (inversion): each interval mirrored
   - **RI** (retrograde inversion): reversed mirror
4. Any of the 4 forms may be transposed to any of 12 pitch levels → up to **48 versions** of the row.

### Matrix
12×12 grid. P0 across the top row; I0 down the first column. Row labels on left (P), column labels on top (I), right-to-left = R, bottom-to-top = RI. Sum of any P index + its I index = 12 (or 0).

### Combinatoriality
Property of a row where its first hexachord (6 pitches) contains no pitch-class duplicates with the first hexachord of one of its transpositions or transformations. Reduces available forms from 48 to 24 but creates maximum structural cohesion (Webern Symphony Op. 21).

### Row design considerations:
- Berg Violin Concerto row: triadic structure (open strings G–D–A–E bracketed in row), last 4 pitches = whole-tone scale.
- Dallapiccola all-interval set: 11 different intervals in a single 12-note row.

### Pointillism
Atomization of the melodic line — extremely short fragments distributed across registers and timbres (Webern). Melody exists only as a series of isolated sound-color points.

### Klangfarbenmelodie ("sound-color melody")
Rapid shifting of tone color (instrument/timbre) while sustaining a single pitch or small melodic gesture. Melody created by timbral change rather than pitch change.

---

## 18. Total Serialization [Kostka/Payne Ch. 28]

Extension of 12-tone: serialize **all** musical parameters simultaneously.
- **Pitch**: 12-tone row.
- **Duration**: 12-step series of note values.
- **Dynamics**: 12 dynamic levels (ppp to fff).
- **Mode of attack/articulation**: series of articulation signs.

Messiaen (*Mode de valeurs et d'intensités*, 1949) → influenced Boulez (*Structures Ia*). Also called **integral serialism** or **multiparametric serialization**.

**Stochastic music**: the ultimate extension — composition by computer-generated choices based on laws of probability (Xenakis, Hiller). Parallel extreme to total control: both attempt to escape conscious aural choice.

---

## 19. Rhythm and Meter Innovations [Kostka/Payne Ch. 28]

### Asymmetric Meter
Time signatures like 5/8, 7/8, 7/4. Not equally divisible — groupings within the bar are unequal.
- Bartók: 5/8 tends to group as 2+3 or 3+2 consistently (not alternating) → "regular irregularity."
- DSP relevance: loop lengths that are not powers of 2 or multiples of 4 (5, 7, 11 beats).

### Mixed Meter (Changing Meter)
Rapid changes of time signature measure by measure. Achieves desired irregularity via cross-accentuation. Elliott Carter's *Fantasy for Woodwind Quintet* uses this over a 5-bar segment.

### Polyrhythm vs. Polymeter
- **Polyrhythm**: listener aware of 2+ independent rhythmic streams simultaneously, each responding to its own recurring metric pulse.
- **Polymeter**: notation of 2+ meters simultaneously. A passage can be both polyrhythmic and polymetric.
- Copland *Appalachian Spring* mm. 86–98: strings in one meter, flute obbligato in another.

### Additive Rhythm (Messiaen)
Rhythmic irregularity by **adding a small value** (dot, tie, rest, extra note) to an otherwise regular pattern. From Messiaen's *Technique of My Musical Language*, influenced by Indian talas.
- Example: `♩♩♩` → `♩. ♩♩♪` (dot added to first note, creating irregular grouping).
- Effect: metric accent shifts without changing notated meter.

### Metric Modulation (Elliott Carter)
Changing tempo by equating one note value to a proportional value of another note value at the bar line.
- Example: `♩ = 60` → passage in 16th notes → meter changes to `14/16, ♩. = ♩. (= 72)` → return to `2/4, ♩.. = ♩ (= 70)`.
- Perceptual effect: smooth tempo change that feels sudden.

### Hemiola
Cross-rhythm where 3 beats in duple time are grouped as 2, or vice versa. 3 quarter notes against 2 dotted quarters. Common in Brahms, Baroque dance music.

---

## 20. Texture and Extended Techniques [Kostka/Payne Ch. 28]

### Parallelism / Planing
Parallel movement of chord structures (not just octaves or 3rds, but entire chords).
- **Strict planing**: all voices move the same interval (requires consistent chord quality → many accidentals, unclear tonal center).
- **Diatonic planing**: voices move in parallel but quality is determined by the prevailing diatonic scale (quality varies, tonal center clearer).
- Debussy's signature move: parallel dominant 7ths (strict) or parallel triads (diatonic, "La Cathédrale engloutie").
- Term **planing** = 20th-century synonym for parallelism, avoids pejorative classical connotation.

### Sprechstimme
Technique between singing and dramatic speech-declamation. Schoenberg *Pierrot Lunaire* (1912). Voice part notated with pitches as starting points but no sustained pitch — immediately drops or rises after attack.
- Techniques include: whistling, clucking, cooing, laughing (Penderecki, Stockhausen, Berio).

### Prepared Piano (Cage)
Objects placed on/between strings to alter pitch, timbre, and harmonic content. Effect suggests a percussion ensemble. Creates "found" timbres from a single instrument.

### Multiphonics
Wind instrument technique: producing more than one pitch simultaneously using various means (overblowing, altered embouchure, humming while playing).

### Musique Concrète
Natural sounds (voice, instruments, objects) recorded then subjected to: altered playback speed, reversed direction, fragmentation, splicing, tape loops, echo, timbral manipulation. Pierre Schaeffer, 1948.

### Electronic Music Waveform Types
- **Sine wave**: pure tone, no overtones (like open flute).
- **Sawtooth wave**: all overtones (nasal, buzzy).
- **Square/rectangular wave**: odd-numbered overtones only (hollow).
- **White noise**: all audible frequencies at random amplitudes (hissing).
Basic signals → modified by filters, modulators, equalizers, sequencers, reverberation units.

### Phase Music (Minimalism)
Constant repetition of a pattern over extended time; second performer gradually moves slightly ahead or behind in tempo → patterns move in and out of phase. Steve Reich *Piano Phase* (1967). Effect: the process itself becomes the form.
- Related: minimalism (Philip Glass, Terry Riley) — extreme economy of materials, gradual evolution.

### Graphic Notation
Non-standard notation used when aleatory, extended technique, or new timbral resources require it. Score as visual/artistic object. Crumb's *Makrokosmos* (circular score layout) is canonical example.

---

## Cross-references

- Core triadic harmony / diatonic basics → `06a-core-progressions.md`
- Borrowed chords / Neapolitan / Aug6 (these techniques extend) → `06b-secondary-borrowed.md`
- Modulation taxonomy (these techniques extend) → `06c-modulation.md`
- DSP proxy table — how each modernist technique maps to semitone ops → `06d-dsp-wiring.md`
- Voice-leading rules + analysis methods + style fingerprints → `06f-voice-leading-analysis.md`
