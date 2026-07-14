# 03e — Vocal Tuning and Pitch Correction

> Originally part of `03-composition-methods.md`. Split for load efficiency. Owns Auto-Tune, Melodyne, formant settings, retune speed, and pitch correction philosophy.

## Vocal Tuning and Pitch Correction

> Pitch correction is a craft. There are two legitimate modes; the failure mode is using the wrong one for the song.

### Two Modes — choose deliberately

| Mode | Sound | Tool setting | When to use |
|---|---|---|---|
| **Transparent** | Inaudible — preserves natural pitch wobble within ±50 cents | Auto-Tune retune speed **20–50**; Melodyne note-by-note ±30 cents max | Almost all pop, rock, country, jazz vocals; correcting the 1–2 wobbly notes of an otherwise great take |
| **Effect** | Audibly tuned — the "Auto-Tune sound" | Auto-Tune retune speed **0–10** with key locked; Melodyne hard-quantize | Hip-hop, modern R&B, EDM hooks, deliberate stylistic colour (Cher "Believe", T-Pain) |

⚡ **The single biggest mistake** is "I want it transparent" with retune speed at 5. Slow the retune. Transparent = 20+.

### Key and Scale Lock — non-negotiable

Auto-Tune is **useless without the correct key and scale set**. Without it, every nearby chromatic note is a valid target; the correction snaps to wrong notes and the result sounds drunker than the original. Set:

- Song's key (e.g. A minor)
- Scale (major, natural minor, harmonic minor, blues, chromatic for instrument-by-instrument work)
- Optional: bypass notes that should slide / bend (e.g. exclude 3rd and 7th in a blues vocal to keep the blue-note feel)

### Formant Preservation — the chipmunk gate

Pitch and formant (vocal-tract resonance, ~the "size" of the voice) are independent. Naive pitch shifting moves both — pitch up = formants up = chipmunk; pitch down = formants down = monster.

- **Always pitch-shift with formant preservation ON** when correction exceeds ~±100 cents.
- **Melodyne Formants slider at 100%** = original formants preserved during transpose.
- **Auto-Tune "Throat Modeling" / "Formant"** parameter must match the voice type (male / female / instrument). Wrong setting = formants shift weirdly even at correct pitch.
- **Exception**: when the chipmunk / monster effect IS the artistic point (kids' choir, demon voice), turn formant correction OFF deliberately.

### Vibrato Handling

Natural vibrato is part of the singer's identity. Over-correction destroys it.

- **Transparent mode**: leave vibrato alone. Auto-Tune retune speed slower than the vibrato period (typically ~150ms = retune 20+) lets vibrato pass through.
- **Effect mode**: vibrato gets flattened — that's the sound.
- **Melodyne**: the vibrato amount slider lets you reduce a wobbly vibrato to taste without removing it.
- **Never** add vibrato that wasn't there. Synthetic vibrato sounds synthetic.

### Auto-Tune vs Melodyne Paradigm

| Auto-Tune | Melodyne |
|---|---|
| Real-time, processes every note as it passes | Offline, displays the whole performance as editable notes |
| Fast workflow, key + speed and go | Slow workflow, note-by-note graphical edits |
| The choice for live performance and the iconic effect sound | The choice for transparent surgical correction |
| Best for hip-hop hooks, EDM vocal chops, lead vocal "vibe" passes | Best for studio comping, harmony stacks, restoring great-but-imperfect takes |

### When to Stop — re-record the take

Pitch correction is not a re-singer. If any of these are true, stop tuning and book another vocal session:

- **More than 3 semitones** of correction required on a single note.
- The note is **on the wrong chord tone** (e.g. singing the 4 over a I chord) — tuning to the right note loses the singer's phrasing.
- Timing is more off than pitch — quantize the vocal first, then pitch-correct.
- The performance is flat in energy, not pitch. No plugin fixes commitment.

⚡ **Record the best performance first. Tune second.** A great take with 2 minor pitch corrections always beats an okay take with 50.

---

### Production Tips from the Book

1. **Always program breaks in pairs** — two complementary patterns plus one break minimum for a usable phrase.
2. **Flams add humanity** — any hit prefixed with F sounds less mechanical. Use on SD, MT, LT for fills.
3. **CB (cowbell) locks African/Caribbean genres** — if Afro-Cuban, Cha Cha, or Samba sounds wrong, check if CB is missing.
4. **RS substitutes for SD** in Bossa Nova, Reggae — RS is not an accent, it IS the backbeat voice.
5. **OH timing defines genre feel** — OH on offbeat 8ths = Disco; OH on "and of 4" = Funk; OH sparse = Reggae/Rock.
6. **TAM (tambourine) adds shimmer** — used in Disco patterns 4,6,12 for high-frequency density without changing groove.
7. **4-on-floor BD is genre-defining** — Disco requires it; Funk forbids it; Rock uses it as a variant (not default).
8. **Half-time SD** (SD on beat 3 only, pos 9) = instant "bigger" feel. Available in Pop:9, Rock:8, R&B:3, Slow:6–9.
9. **Triplet-feel genres use 12-step grid** — Blues, Boogie, Jazz, Shuffle, Swing all use 12 steps (each = 1 triplet 8th). Never program these on 16-step grids at the same BPM or the feel collapses.
10. **Song structure recommendation** — `Pattern1 + Pattern2 + Pattern1 + Pattern2 + Pattern1 + Pattern2 + Pattern1 + Break` per 8-bar phrase. Chain 2–4 phrases before a section change.

---


---

## Cross-references

- Owsinski 3 Ps (Pitch / Pocket / Passion) as the vocal quality framework → `11-owsinski-producer-handbook.md` §6
- Pitch confidence gate used for pitch-shift safety → `06d-dsp-wiring.md`
- Composition development methods feeding the vocal melody → `03a-development-methods.md`
