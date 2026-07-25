# Easby-Producer Knowledge Base Index

Machine-readable index. `SKILL.md` consults this index to decide which file to load for a given query. **Routers** are slim files listing pointers to sub-files; load the router first, then the matching sub-file. Never load a megafile unless explicitly required.

## Loading policy (TL;DR)

1. **Hot-path** = `05-quick-decisions.md` always loaded.
2. **Router-first** for theory / drum-beats / composition (`06`, `07`, `03`) — load only the matching sub-file.
3. **Section-anchor** for any file >15K: `grep -n "^## " <file>` then `Read offset/limit` for the matching section. Files >15K: `01-synthesis-engine.md`, `03b-drum-patterns.md`, `06e-modernist.md`, `08-rhythm-techniques.md`, `11-owsinski-producer-handbook.md`.
4. **Schemas** (in `schemas/`) load only when emitting/validating.
5. **Never load megafiles in full** — they are routers.

## Always-load (hot-path)

| File | Triggers | Est. tokens | Precedence |
|---|---|---|---|
| `05-quick-decisions.md` | always | ~2,500 | hot-path; may trigger lazy load of `06*` for theory follow-up |

## Routers (load first when query matches the topic)

| Router | Topic | Sub-files | Router-est. tokens |
|---|---|---|---|
| `06-music-theory.md` | theory: cadences, NCT, modulation, secondary dom, borrowed, voice leading, modernist | 06a–f | ~1,000 |
| `07-famous-drum-beats.md` | famous beat lookup by song/drummer/genre | 07a, 07b | ~1,500 |
| `03-composition-methods.md` | composition + arrangement + vocal tuning | 03a–e | ~1,700 |

## Sub-files (load only after router routes here)

### Theory (06*) — split of original 06-music-theory.md

| File | Triggers | Est. tokens | Precedence |
|---|---|---|---|
| `06a-core-progressions.md` | cadence, PAC, IAC, deceptive, plagal, half-cadence, 7th chord, maj7, m7, dim7, circle of fifths, I-V-vi-IV, NCT, passing tone, neighbor tone, suspension, sequence, inversion, augmentation, diminution, retrograde, fragmentation, ≤M3 gap | ~2,000 | diatonic basics |
| `06b-secondary-borrowed.md` | V/X, V/V, V/vi, secondary dominant, secondary diminished, borrowed chord, mode mixture, iv, bVI, bVII, Picardy, Neapolitan, bII, augmented sixth, It+6, Fr+6, Ger+6 | ~1,100 | chromatic palette |
| `06c-modulation.md` | modulation, pivot chord, direct modulation, common-tone, sequential modulation, chromatic pivot, key change | ~400 | modulation |
| `06d-dsp-wiring.md` | amt, ladder, semitone, pitch-shift, time-stretch, audio operation, DSP proxy, pitch confidence gate, real_helper, CreateVariationController, melodic loop, chord loop | ~1,800 | **Easby-critical** — semitone-op math + amt ladder |
| `06e-modernist.md` | omnibus, chain of dominants, double chromatic mediant, mystic chord, mode (Lydian/Dorian/etc.), pentatonic, whole-tone, octatonic, quartal, quintal, secundal, tone cluster, tall chord, 9th/11th/13th, polychord, bitonality, pandiatonicism, pitch class, prime form, set theory, twelve-tone, tone row, matrix, combinatoriality, total serialization, asymmetric meter, polyrhythm, polymeter, additive rhythm, metric modulation, hemiola, planing, sprechstimme, prepared piano, multiphonics, musique concrète, phase music, minimalism, graphic notation | ~4,800 | post-tonal / modernist |
| `06f-voice-leading-analysis.md` | voice leading, SATB, spacing, doubling, parallel 5ths, parallel octaves, hidden 5ths, contrary motion, oblique motion, 6/4 chord, tendency tone, leading tone resolution, root relationship, part writing case 1/2/3/4, deceptive progression voice leading, analysis labels, concentric, expanded tonality, late Romantic, Impressionism, Bartók, Stravinsky, minimalism style | ~3,300 | voice-leading legality |

### Drum beats (07*) — split of original 07-famous-drum-beats.md

| File | Triggers | Est. tokens | Precedence |
|---|---|---|---|
| `07a-beats-c-l.md` | song names C–L · Funky Drummer · Get Up Sex Machine · Give It Away · Englishman In New York · Green Onions · Hot Fun · Hot For Teacher · Immigrant Song · Kashmir · etc. | ~3,400 | alphabetical C–L |
| `07b-beats-m-z-advanced.md` | song names M–Z · Manic Depression · Funky Drummer follow-ups · Rosanna · Sing Sing Sing · Stratus · Take Five · Tom Sawyer · YYZ · Walking On The Moon · 6:00 · Constant Motion · Oakland Stroke · Stream Of Consciousness | ~7,400 | alphabetical M–Z + Part 2 advanced |

### Composition (03*) — split of original 03-composition-methods.md

| File | Triggers | Est. tokens | Precedence |
|---|---|---|---|
| `03a-development-methods.md` | melody development, rhythmic development, harmony, chord variation, 4 contrast levers, subtractive arrangement, story curve, DeSantis, Ableton 74, iterative layering, constraint recipe, Huang, "how do I start a track" | ~1,900 | note-level composition moves |
| `03b-drum-patterns.md` | drum pattern, drum machine pattern, grid, Afro-Cuban, Bossa Nova, Cha Cha, Samba, Tango, Waltz, Swing, clave, tumbao, ending pattern | ~5,600 | genre-by-genre drum-machine grids |
| `03c-arrangement-arc.md` | song form, ABABCB, AABA, 12-bar, EDM 8/32, energy arc, section contrast, section length, intro/outro rules, riser, reverse cymbal, noise sweep, snare roll, drop-out, filter sweep, transition tools, arrangement heuristic | ~1,800 | section structure |
| `03d-genre-templates.md` | genre template, pop arrangement, EDM arrangement, house arrangement, techno arrangement, trap arrangement, hip-hop arrangement, indie arrangement, rock arrangement, jazz arrangement, country arrangement, BPM range, section bar count | ~800 | concrete blueprints |
| `03e-vocal-tuning.md` | vocal tuning, pitch correction, Auto-Tune, Autotune, Melodyne, formant, retune speed, key + scale tuning, vibrato preservation, T-Pain effect | ~1,500 | vocal tuning execution |

## Single-file modules (no router)

| File | Triggers | Est. tokens | Precedence |
|---|---|---|---|
| `01-synthesis-engine.md` | FM, AM, ring mod, granular, wavetable, wavetable position, morph, Serum, Vital, additive, Fourier, partials, formant, Harmor, K5000, modulation matrix, mod routing, LFO, envelope, velocity, aftertouch, mod wheel, MPE, per-note expression, macro knob, Bessel, C:M | ~7,500 | synthesis math |
| `02-sound-design-recipes.md` | recipe, patch, instrument, waveform, ADSR | ~6,000 | canonical for synthesis recipes |
| `04-recording-production.md` | mic, record, stereo capture, Blumlein, SM7 | ~4,000 | lazy |
| `08-rhythm-techniques.md` | breakbeat, break, chop, Amen, Funky Drummer, Apache, ghost note, clave, tumbao, fill, rudiment, paradiddle, time-stretch, half-time feel, jungle, DnB, swing, pocket | ~5,500 | canonical for rhythm techniques + production workflow |
| `09-pro-tools-daw-reference.md` | pro tools, PT, DAW, edit mode, slip, grid, shuffle, spot, snap, grid resolution, BBT, bars beats, tab to transients, timeline, nudge, modifier, Cmd, ruler, timebase | ~3,500 | DAW timeline + grid semantics |
| `11-owsinski-producer-handbook.md` | arrangement element, foundation pad rhythm lead fills, 4-element rule, common song problem, dynamic level, tension release, make it better not different, 3 Ps, pitch pocket passion, doubling, stacking, oblique strategies, producer conduct, little things checklist, music troubleshooting, loop doesn't sound right, Owsinski | ~9,500 | arrangement rules + variation gate + 3 Ps + 10-Q troubleshoot; cite as `O-Ch{n}` |
| `00-producer-mind.md` | taste, stuck, creative direction | ~2,500 | tiebreaker only |

## Schemas

Authoritative JSON Schemas in `~/.claude/skills/easby/easby-producer/schemas/`:
- `VariationDecision.schema.json`
- `SoundDesignTarget.schema.json`
- `ArrangementDecision.schema.json`
- `TroubleshootDiagnostic.schema.json`

`SKILL.md` carries a one-line summary per schema. Load the `.schema.json` file only when emitting or validating.

## Verifier

`Tools/easby-verify/check_variation.py` — validates `VariationDecision` + `SoundDesignTarget` JSON. Exit `0` PASS, `1` FAIL.

## Worked Examples

`docs/easby/examples/01-variation-trace.md` — end-to-end trace for `amt=3` secondary-dominant on a C-major loop.

## ADR

`docs/adr/0015-easby-producer-agent-contract.md`
