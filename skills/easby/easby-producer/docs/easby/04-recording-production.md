# Recording & Production

> Recording is decision-making with a microphone. Mic position is EQ. Room choice is reverb. Distance is dynamics. I make those decisions at the source, because what I capture is what I'm stuck with — fixing it in the mix is a tax I refuse to pay.

<!-- LOAD POLICY: lazy — load only when query contains: mic, record, stereo capture, Blumlein, overhead, acoustic treatment, SM7, signal chain -->

> Rule-of-thumb voice: rows in tables describe what Easby reaches for, not first-person narration.

---

## Core Recording Beliefs (Swedien / Acusonic)

1. ⚡ **Record in stereo at the source whenever possible.** Mono-then-widen-later never sounds like genuine stereo. The phase relationships you capture are the magic.
2. ⚡ **Minimal compression.** Preserve transients. Compression is the last resort, not the default.
3. ⚡ **Mono collapses magic.** Every element should occupy a deliberate place in the stereo field.
4. **SMPTE-sync everything.** Capture everything that's happening — you decide what to use later.
5. **Synaesthesia mixing.** Assign colours to sounds (bright yellow = hi-hat, deep blue = bass). Helps with spatial placement decisions.
6. ⚡ **Blumlein pair** (two figure-8 mics at 90°) for stereo room capture — most natural stereo field on the planet.
7. **SM7 dynamic on MJ lead vocals.** Handles extreme SPL, smooth top-end. Reference for any loud, controlled vocal source.

---

## Mic Choice — the three families

| Family | Strengths | Use for |
|---|---|---|
| **Dynamic** (SM7, SM57, SM58) | Handles SPL, rejects bleed, controlled top | Loud vocals, snare top, guitar amp, kick out |
| **Condenser** | Detail, air, fast transient response | Vocals (intimate), acoustic guitar, overheads, room |
| **Ribbon** (figure-8) | Warm, smooth top, natural | Brass, guitar amp, room, Blumlein |

⚡ **Distance = brightness + room.** Close mic = more direct, more low-end (proximity effect on cardioids). Far mic = more room, less proximity.

⚡ **On-axis = bright. Off-axis = warmer.** Use position as EQ before reaching for a plugin. SM7B at 3 inches, 15° off-axis on a vocalist is a different sound than 6 inches dead-on.

---

## Stereo Mic Techniques — Decision Table

| Technique | Mics | Angle | Spacing | Character |
|---|---|---|---|---|
| **X-Y** (coincident) | 2× cardioid | 90° | 0 | Focused centre, mono-compatible |
| **A-B** (spaced pair) | 2× omni | 0° | 20–100 cm | Wide, phase issues in mono |
| **M-S** | 1× cardioid + 1× fig-8 | 90° | 0 | Variable width post, mono-compatible |
| **Blumlein** | 2× fig-8 | 90° | 0 | Natural, full-frequency stereo |
| **ORTF** | 2× cardioid | 110° | 17 cm | Approximates human ears |
| **NOS** | 2× cardioid | 90° | 30 cm | Wider than ORTF |
| **Decca Tree** | 3× omni | — | LCR arrangement | Orchestral, wide + centre fill |
| **INA-3 / INA-5** | 3–5× cardioid | Splayed | Centre + flanks | Surround capture |
| **OCT** | 1× super-cardioid + 2× cardioid | — | Spaced flanks | Surround, tight centre |

### Quick Mic-Choice Matrix

| Priority | Technique |
|---|---|
| Mono compatibility (broadcast) | X-Y or M-S |
| Widest stereo image | A-B spaced pair |
| Natural, immersive | Blumlein |
| Orchestral / classical | Decca Tree |
| Surround film | OCT or INA-5 |
| Variable width in post | M-S |

⚡ **M-S is the only technique where width can change after the fact without artefacts.** Default to M-S when the final mix width is undetermined.

---

## Instrument-Specific Mic Decisions

### Vocals

| Source | Mic | Distance | Notes |
|---|---|---|---|
| Loud lead, controlled | SM7B dynamic | 3–4" | Off-axis ~15° to tame sibilance |
| Intimate lead | LDC condenser | 6–8" | Pop filter mandatory |
| Air / harmonies | SDC pair | 12"+ | Capture detail and room |
| Rap / hip-hop | SM7B or U87 | 4–6" | Cardioid for rejection |

⚡ **Pop filter always.** Plosives are unfixable.

### Acoustic Guitar
- **XY at 12th fret** → balanced body + attack
- **A-B pair** (one at 12th fret, one at soundhole/body) → width
- Distance: 8–12" close, 24"+ for room blend

### Drums

| Source | Mic | Position |
|---|---|---|
| Kick (in) | Dynamic (D6, β52) | Inside, near beater |
| Kick (out) | Dynamic or condenser | 12–18" off front head |
| Snare top | SM57 | 1–2" above rim, 30° angle |
| Snare bottom | SM57 (phase flipped) | 1" below snare wires |
| Hi-hat | SDC | 4–6" above edge |
| Toms | Dynamic (e604, MD421) | 1–2" off head |
| Overheads | SDC pair, X-Y or spaced | 3–4 ft above kit |
| Room | Condenser pair | 6–12 ft, Blumlein or A-B |

⚡ **Blend close + overheads + room for live/close ratio.** Three positions = three tones to mix. More mics ≠ better drums.

### Guitar Amp
- **SM57 on the grille**, edge of dust cap = balanced; centre = bright; off-axis = warm.
- **Add ribbon (R-121) at 6"** for warmth and body. Blend.
- **Room mic** at 3–6 ft for natural ambience.

### Brass
- **Ribbon mic 12"+ off-axis.** Brass is bright; ribbon tames it naturally.
- For section: Blumlein pair at 6–8 ft.

---

## Room as Sound Source

⚡ **Recording in a dead room then adding reverb ≠ recording in a live room.** The early reflections, the way the mic picks up the room, the way the air moves — none of that comes from a plugin.

| Need | Room |
|---|---|
| Tight, controlled | Dead room, close-mic only |
| Natural ambience | Medium room, blend close + room mic |
| Cinematic / huge | Live room or hall, room mic dominant |
| Lo-fi / bedroom | Embrace the small room — close mic + slight room bleed |

---

## Signal Chain Order (recording → mix)

Capture chain (keep minimal):
```
Mic → preamp → (optional) light compression (3:1, 1–2 dB GR max) → A/D
```

✗ **Don't EQ on the way in unless you're sure.** EQ choices baked into the recording can't be reversed.

Mix chain (typical):
```
Track → HPF → corrective EQ (subtractive) → compressor → saturation → 
  tonal EQ (additive) → delay/reverb sends → bus
```

⚡ **Subtractive EQ before additive EQ.** Remove what doesn't belong before boosting what should be louder.

---

## Compression Philosophy

- ⚡ **Compression preserves transients only if you use it sparingly.** Heavy GR kills dynamics — which is usually what makes the track feel alive.
- Default starting points:
  - Vocal: 3:1, 3 dB GR, slow attack (10 ms), medium release (100 ms)
  - Drum bus: 4:1, 2 dB GR, fast attack, fast release
  - Mix bus: 2:1, 1 dB GR, slow attack/release, glue not crush
- ✗ Don't compress to make something louder. Fader for level. Compressor for shape.

---

## Spatial Perception — Mix Decisions

| Combination | Perceived position |
|---|---|
| Dry + loud | Close, in-your-face |
| Dry + soft | Whispered, intimate-close |
| Wet + loud | Large space, but present |
| Wet + soft | Far away, large space |

- **Echo (>100 ms distinct repeats)** ≠ reverb (blurred reflections) ≠ chorus (slight detune recombined). Use the right tool.
- ⚡ Reverb controls apparent **room size** AND **listener distance** simultaneously. Treat it as both an EQ and a placement tool.

---

## Synaesthesia Mixing Map

Borrowed from Swedien — assign colour/position before EQ/pan decisions:

| Sound | Colour | Stereo position | Vertical |
|---|---|---|---|
| Kick | Deep red | Centre | Floor |
| Snare | White | Centre | Chest |
| Hi-hat | Bright yellow | Slightly off-centre | Eye-level |
| Bass | Deep blue | Centre | Floor |
| Vocal lead | Warm gold | Centre | Eye-level |
| Pad | Soft purple | Wide L/R | Behind |
| Lead synth | Bright orange | Slightly off-centre | Front |

⚡ When two elements share colour + position, they fight. Move one.

---

## Recording → Composition Feedback Loop

| Recording reveals | Composition response |
|---|---|
| Singer can't hold long note | Shorten phrase, breath in melody |
| Drummer rushes the chorus | Pull tempo down 2 BPM, or commit to the push |
| Guitar amp too bright | Voice the chord lower, leave high-end for vocals |
| Room sounds too live | Move arrangement sparser; let room be reverb |

✗ Don't fix performance issues with editing if you can fix them with arrangement first.

---

## Cross-references

- For what to record → `02-sound-design-recipes.md`, `03-composition-methods.md`
- For taste during mixdown → `00-producer-mind.md`
- For fast mic + signal-chain answers → `05-quick-decisions.md`
