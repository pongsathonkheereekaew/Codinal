# 01 — Imaging, Balance, Panorama

## 1. The 3D Imaging Model (Gibson)

Mix = crowd control in a 3D space between speakers.

| Axis | What controls it | Range |
|------|-----------------|-------|
| X (left/right) | Pan pot | Speaker L → Speaker R |
| Y (front/back) | Volume, compression, presence-boost, short delays | A few inches in front → a few inches behind speakers |
| Z (up/down) | Frequency content | Bass/kick at floor, hi-hat/cymbals at top |

**Sound image types:**
- **Sphere** — a single mono sound (volume+pan+EQ places it)
- **Line / oblong sphere** — fattened via short delay (<30ms), fills left-right
- **Room / cube** — reverb (hundreds of simultaneous delays → massive masking)

**Key imaging rules:**
- Bass instruments occupy the most space; 3 bass guitars = muddy mix
- Loud sounds appear larger → mask more
- Reverb takes enormous space in stereo; EQ dark to reduce masking
- Delays <30ms widen/fatten without audible echo; ≥30ms = heard as distinct repeat
- Reducing 5kHz presence makes sounds more distant; boosting brings forward

## 2. The 6 Elements of a Mix (Owsinski)

1. **Balance** — relative fader levels; foundation first
2. **Frequency Range** — EQ so each instrument has its own band
3. **Panorama** — stereo placement; Big Three stay center
4. **Dimension** — reverb/delay ambient field
5. **Dynamics** — compression/gating shaping envelopes
6. **Interest** — the groove, the direction, the most important element emphasized

All 6 must be addressed. Interest is what separates a great mix from a technically correct one.

## 3. Regional Mixing Styles (Owsinski Ch.1)

Three canonical aesthetics. Pick first; everything downstream (EQ, comp, reverb depth) follows.

| Style | Character | Compression | EQ | Reverb / depth |
|---|---|---|---|---|
| **LA (West Coast)** | Natural, warm, conservative | Light, transparent | Conservative — small boosts only | Subtle, depth via volume + light reverb |
| **NY (East Coast)** | Aggressive, in-your-face, compressed | Heavy, parallel comp, NY trick | Bigger boosts, brighter top end | Short, tight; dryer than LA |
| **London** | Layered, perspectival, "separate environment per instrument" | Per-instrument character (varies) | Sculpted per element | **Distinct reverb env per instrument** — 3D depth via reverb-type separation, not just level |

⚡ **Default selection:**
- Pop/R&B/classic rock → LA
- Hip-hop / modern rock / aggressive pop → NY
- Alt / shoegaze / cinematic / Britpop → London

Cite the chosen style in any `MixDecision` output — operator can override.

## 4. Mix Starting Place by Material Type (Owsinski Ch.3)

Where to first push a fader. The starting element anchors balance order.

| Material | Start with | Order after |
|---|---|---|
| Dance / electronic | Kick | Bass → groove perc → lead → pads |
| Rock / pop with vocals | Lead vocal | Drums → bass → guitars → keys → BGV |
| Hip-hop | Kick + 808/bass simultaneously | Vocal → hi-hat → snare/percussion → samples |
| Jazz / live band | Drum overheads | Bass → piano → horns → soloist |
| Orchestral / cinematic | Highest string (1st violin) | Down through strings → brass → woodwinds → perc |
| R&B / soul ballad | Lead vocal + acoustic piano/Rhodes | Drums → bass → BGV → pads |

⚡ **Rule:** never start with whichever instrument is "most interesting" — start with the structural anchor. Interest comes later in the process.

## 5. Arrangement / Balance Rules (Owsinski)

**Track hierarchy (Foundation → Lead):**
- **Foundation**: kick + bass (these anchor everything)
- **Pad**: long sustaining chords (keys, strings, pads)
- **Rhythm**: guitar chops, arpeggiated synths, percussion
- **Lead**: main vocal or lead melody
- **Fills**: background vocals, countermelodies, FX hits

**Rule:** Never more than 4 layers simultaneously. Thin the arrangement to make room.

**Instrument fighting — fix order (Owsinski Fig.1).** When two instruments clash in the same frequency range, try in this order, stopping at the first that resolves:

1. **Change the arrangement** — re-voice one instrument higher/lower, mute one during the other's lead phrase, or move one to a different register at the composition level.
2. **Mute** — does the mix sound *better* without one of them? Cut it.
3. **Lower the level** of one until the conflict resolves.
4. **EQ to a different range** — cut one and boost the other at that frequency rather than boosting both.
5. **Pan differently** — if the conflict is still spectral but separable spatially.

⚡ **Producer's privilege rule:** fix at arrangement first (1). Only descend to EQ tricks if the arrangement can't change (mix-only contract).

**Rule of thumb:** fewer instruments → each can be bigger; more instruments → each must be smaller to fit.

## 4. Panorama (Owsinski)

**The Big Three** — always center: kick, bass, lead vocal.

**Big Mono problem:** panning everything to center produces a wall of indistinguishable sound. Spread to create definition.

**Dance music panning:** most elements dead-center or very slight; hi-hats and percussion wide.

**Mono check:** always fold to mono before finalizing — if elements disappear, a phase problem exists. Fix at source, not with width.

**Rule:** avoid panning bass below 250Hz hard left or right — it unbalances the low end.
