# Music Theory — Router

> This file was 800+ lines / 49K (covering 25 sections). Split for load efficiency.
> Load only the sub-file matching your query — do NOT load all six.

> Theory isn't a rulebook. It's the names I give to the moves I already hear. Every theory concept must survive being applied to a slice of waveform with pitch-shift and time-stretch. If it can't, it doesn't ship.

## Router Table

| Sub-file | Owns (original §) | Load when query mentions… |
|---|---|---|
| **`06a-core-progressions.md`** | §1 Cadences · §2 Seventh chords · §3 Progressions · §4 NCT · §5 Melodic alteration | cadence, PAC, IAC, deceptive, plagal, half-cadence, seventh chord, maj7/m7/dim7, circle of fifths, I-V-vi-IV, NCT, passing tone, neighbor tone, suspension, sequence, inversion, augmentation, diminution, retrograde, fragmentation, ≤M3 gap |
| **`06b-secondary-borrowed.md`** | §6 Secondary dominants · §7 Secondary diminished · §8 Borrowed (mode mixture) · §9 Neapolitan + Aug6 | V/X, V/V, V/vi, V/IV, secondary dominant, secondary diminished, borrowed chord, mode mixture, iv, bVI, bVII, bIII, Picardy, Neapolitan, bII, augmented sixth, It+6, Fr+6, Ger+6 |
| **`06c-modulation.md`** | §10 Modulation | modulation, pivot chord, direct modulation, common-tone, sequential modulation, chromatic pivot, key change |
| **`06d-dsp-wiring.md`** | Wiring · §11 DSP Proxy · §12 Variation amount ladder | amt, ladder, semitone, pitch-shift, time-stretch, audio operation, DSP proxy, pitch confidence gate, real_helper, CreateVariationController, melodic loop, chord loop |
| **`06e-modernist.md`** | §13 Late-Romantic chromatic · §14 20th-c scales · §15 20th-c chord structures · §16 Set theory · §17 Twelve-tone · §18 Total serialization · §19 Rhythm/meter innovations · §20 Texture/extended techniques | omnibus, chain of dominants, double chromatic mediant, mystic chord, nonconcentric, mode, Lydian, Mixolydian, Dorian, Phrygian, Locrian, pentatonic, whole-tone, octatonic, quartal, quintal, secundal, tone cluster, tall chord, 9th, 11th, 13th, polychord, bitonality, pandiatonicism, pitch class, prime form, interval class, set theory, twelve-tone, tone row, matrix, combinatoriality, pointillism, klangfarbenmelodie, total serialization, integral serialism, stochastic, asymmetric meter, mixed meter, polyrhythm, polymeter, additive rhythm, metric modulation, hemiola, planing, sprechstimme, prepared piano, multiphonics, musique concrète, phase music, minimalism, graphic notation |
| **`06f-voice-leading-analysis.md`** | §21 Voice leading (Ch. 5–9) · §22 Extended analysis · §23 Style fingerprints · §24 Voice leading (Ch. 4–5) · §25 Part-writing by root relationship | voice leading, SATB, spacing, doubling, parallel 5ths, parallel octaves, hidden 5ths, contrary motion, oblique motion, 6/4 chord, cadential six-four, passing six-four, pedal six-four, tendency tone, leading tone resolution, root relationship, part writing case 1/2/3/4, deceptive progression voice leading, analysis labels, concentric, expanded tonality, late Romantic, Impressionism, Bartók, Stravinsky, minimalism style |

## Conflict precedence within `06*`

- `06d` wins on **execution math** (semitone deltas, time-stretch factors, audio-side gates).
- `06f` wins on **voice-leading legality** (which semitone shifts are forbidden in 4-voice contexts).
- `06e` wins on **modernist / post-tonal** territory (overrides 06a–c when the source is atonal/modal/serial).
- `06a–c` win on **diatonic tonal** territory (default).

## Cross-doc references

- For *what* arrangement use these chord-moves support → `03-composition-methods.md`
- For *how* DSP slice-level primitives implement them → `01-synthesis-engine.md`
- For *fast* amt selection → `05-quick-decisions.md`
- For *which* operation to default to when stuck → `00-producer-mind.md` § "Stuck."
