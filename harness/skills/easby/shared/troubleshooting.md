# troubleshooting — shared symptom → cause → fix

CLEAN (public). One heuristic table; the **router sends each symptom to the owning stage** (no single skill
hoards troubleshooting). Producer = sound identity, Mixing = balance/space, Mastering = loudness/translation.

| Symptom | Likely cause | Fix | Owning stage |
|---|---|---|---|
| Muddy / boxy | LF buildup 200–500 Hz, masking | cut 250–400, HPF non-bass, check arrangement density | Mixing (→ Producer if too many low elements) |
| Harsh / fatiguing | 2–5 kHz buildup, over-saturation | dynamic EQ / de-ess, ease drive | Mixing · Mastering |
| Thin / small | no LF weight, too narrow, over-HPF | add body, check mono, saturation for harmonics | Producer (timbre) · Mixing |
| No punch | transient squashed, slow attack comp | slower attack / less GR, parallel comp | Mixing |
| Won't get loud | dynamic peaks, no limiting headroom | clip/limit peaks, glue, then master limiter | Mastering |
| Pumping | release too fast, over-compression, sidechain | lengthen release, less GR | Mixing · Mastering |
| Narrow / mono | no width, side too low | M/S side boost, pan, stereo FX (mind mono-compat) | Mixing · Mastering |
| Translates bad on phone | sub-only bass, mono issues, too dark | check mono+small speakers, mid focus | Mastering |
| Distorted unintentionally | clipping, gain staging | back off input gain, find the hot stage | any (find the stage) |
| Boring / static | no variation/movement, arrangement flat | automation, variation (amt), arrangement | Producer (variation) · Mixing (automation) |
| Lifeless sound | wrong synth/timbre, no harmonics | sound design, saturation, layering | Producer |

## Use
Match the symptom → apply the fix **at the owning stage** (route via INDEX). A "why does this sound bad" with no
stage context → ask which stage the user is at (mix in progress? final master?), then route.
