# Composition Methods — Router

> Originally 1142 lines / 45K. Split for load efficiency.
> Load only the sub-file matching your query — do NOT load all five.

> Composition decides notes. Arrangement decides when those notes appear and what
> surrounds them. A finished track is a sequence of sections that ride one energy
> curve from first sample to last.

## Router Table

| Sub-file | Owns | Load when query mentions… |
|---|---|---|
| **`03a-development-methods.md`** | Melodic development (6 moves) · Rhythmic development · Harmony / chord variation · Texture & arrangement (4 contrast levers, subtractive arrangement, story curve) · DeSantis/Ableton 74 strategies · Iterative layering · Constraint recipe (Huang) · Linking composition → synthesis · Linking composition → recording | melody development, rhythmic development, harmony, chord variation, 4 contrast levers, contrast lever, subtractive arrangement, story curve, DeSantis, Ableton 74, iterative layering, constraint recipe, Huang, "how do I start a track", linking composition |
| **`03b-drum-patterns.md`** | Drum machine pattern reference for 20+ genres (Afro-Cuban, Blues, Boogie, Bossa Nova, Cha Cha, Disco, Funk, Jazz, March, Tango, Paso Doble, Charleston, Pop, Reggae, Rock, R&B, Samba, Shuffle, Ska, Slow, Swing, Twist, Waltz) + Universal Endings + Grid Reading Rules | drum pattern, drum machine pattern, grid, "Afro-Cuban pattern", "Bossa Nova pattern", "Cha Cha pattern", "Samba pattern", "Tango pattern", "Waltz pattern", "Swing pattern", clave, tumbao, ending pattern |
| **`03c-arrangement-arc.md`** | Song forms (Verse-Chorus, AABA, 12-bar blues, Head-Solos-Head, EDM 8/32, Through-composed) · Energy arc · Section contrast (frequency clearing) · Typical section lengths · Intro/outro rules · Transition tools (riser, reverse cymbal, noise sweep, snare roll, drop-out, etc.) · Arrangement heuristics | song form, ABABCB, AABA, 12-bar, EDM 8/32, head-solos-head, through-composed, energy arc, section contrast, section length, intro rules, outro rules, riser, reverse cymbal, noise sweep, snare roll, drop-out, filter sweep, transition tools, arrangement heuristic |
| **`03d-genre-templates.md`** | Concrete genre arrangement blueprints (Pop, House/Techno, Trap, Hip-Hop, Indie/Rock, Jazz, Country) with BPM range, section bar counts, structural conventions | genre template, pop arrangement, EDM arrangement, house arrangement, techno arrangement, trap arrangement, hip-hop arrangement, indie arrangement, rock arrangement, jazz arrangement, country arrangement, BPM range, section bar count |
| **`03e-vocal-tuning.md`** | Vocal tuning approaches · Auto-Tune workflow · Melodyne workflow · Formant slider · Retune speed bands · Pitch correction philosophy · Vibrato handling | vocal tuning, pitch correction, Auto-Tune, Autotune, Melodyne, formant, retune speed, key + scale tuning, vibrato preservation, T-Pain effect |

## Conflict precedence within `03*`

- `03c` wins on **section structure** (form, transition, energy arc) — generic principles.
- `03d` wins on **genre-specific arrangement** decisions (Pop = ABABCB, EDM = 8/32, etc.).
- `03b` wins on **drum pattern grids** — genre-specific drum-machine blueprints.
- `03a` wins on **note-level composition** (melodic/rhythmic/harmonic moves before arrangement).
- `03e` wins on **vocal tuning execution**.

## Cross-doc references

- For *theory operations* behind chord changes → `06-music-theory.md` (router)
- For *how* to execute a specific sound → `01-synthesis-engine.md`, `02-sound-design-recipes.md`
- For *fast* answers → `05-quick-decisions.md`
- For *taste tiebreaker* → `00-producer-mind.md`
- For *4-element cap + dynamic scale + variation gate* → `11-owsinski-producer-handbook.md`
- For *drum beat name lookup* → `07-famous-drum-beats.md` (router) + `08-rhythm-techniques.md`

---

## Sources — Song Form, Arrangement, Pitch Correction sections

- Wikipedia, *Song structure* — pop/rock section labels and ABABCB template (`en.wikipedia.org/wiki/Song_structure`).
- Wikipedia, *Thirty-two-bar form* — AABA history and section counts (`en.wikipedia.org/wiki/Thirty-two-bar_form`).
- Songstuff, *AABA Song Form* (`songstuff.com/songwriting/article/aaba-song-form/`).
- MasterClass, *Songwriting 101: Learn Common Song Structures* (`masterclass.com/articles/songwriting-101-learn-common-song-structures`).
- The Jazz Piano Site, *Common Jazz Forms — AABA / ABAC / Head-Solos-Head* (`pianogroove.com/jazz-piano-lessons/common-jazz-forms/`).
- Jazz Newbie, *The Structure Of A Jazz Standard* (`jazznewbie.com/the-structure-of-a-jazz-standard/`).
- EDMtips, *EDM Song Structure: Arrange Your Loop into a Full Song* (`edmtips.com/edm-song-structure/`) — 8 / 16 / 32-bar section rule, build / drop / breakdown lengths.
- Cymatics.fm, *EDM Song Structure: Turn Your Loop Into A Song!* (`cymatics.fm/blogs/production/edm-song-structure`).
- Mixed In Key, *How to arrange a Dance Music track* (`mixedinkey.com/captain-plugins/wiki/how-to-arrange-a-dance-music-track/`).
- EDMProd, *The Advanced Guide to Tension and Energy in Electronic Music* (`edmprod.com/tension/`) — density-as-energy, element removal before drop.
- Point Blank Music School, *Creating Tension and Release in Electronic Dance Music* (`pointblankmusicschool.com/blog/creating-tension-and-release-in-electronic-dance-music/`).
- Point Blank Music School, *Designing Unique Risers and FX for Transitions* (`pointblankmusicschool.com/blog/designing-unique-risers-and-fx-for-transitions-to-level-up-your-tracks/`) — frequency layering of transition FX.
- Mantasonica Audio, *Production Technique: Reverse Cymbal as Transitional Effect* (`smabellakoppenaudio.wordpress.com/2015/08/12/production-technique-2-reverse-cymbal-as-transitional-effect/`).
- ColeMize Studios, *How To Rap: Song Structure* (`colemizestudios.com/how-to-rap-song-structure/`) — 8-bar verse / 4-bar hook arrangement.
- Rap Authority, *Rap Song Structure Blueprint* (`rapauthority.com/rap-song-structure/`).
- Unison Audio, *Pop Song Structure 101* (`unison.audio/pop-song-structure/`).
- Producer Spot, *Auto-Tune Vs. Melodyne* (`producerspot.com/auto-tune-vs-melodyne-which-is-the-best-tuning-software/`) — per-note vs realtime paradigm.
- The Vocal Market, *How to Tune Vocals: Autotune, Melodyne & Pitch Correction (2026)* (`thevocalmarket.com/blogs/how-to/how-to-tune-vocals-autotune-melodyne-pitch-correction-2026`) — formant slider, vibrato.
- Antares Tech, *Getting Started with Auto-Tune 2026* (`antarestech.com/community/tutorial-getting-started-with-autotune-2026`) — key / scale / retune-speed parameters.
- LukeMountHillBeats, *How To Use Auto-Tune: A Guide To Sounding Natural (2026)* (`lukemounthillbeats.com/music-production/how-to-use-auto-tune/`) — retune speed bands 0–10 / 20–35 / 45–80.
- Mastering.com, *How to Use Melodyne: Pitch Correction 101* (`mastering.com/melodyne/`).
