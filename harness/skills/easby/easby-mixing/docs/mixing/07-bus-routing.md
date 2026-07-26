# 07 — Bus Routing and Sub-Groups

Bus = a routing destination where multiple tracks sum. Process the sum once instead of each track.

## Three Flavors

| Type | Audio flows through? | Use for | Recall behavior |
|------|---------------------|---------|-----------------|
| **Audio bus / sub-group** | Yes — sums then processes | Group EQ/comp on drum kit, vocal stack, guitar wall | Processing baked into bus |
| **VCA / DCA** | No — controls fader levels only | Level control across many tracks, preserve sends-pre-fader behavior | Only relative levels stored |
| **Aux send** | Parallel copy — original still plays direct | Reverb, delay, parallel comp | Send level + return processing both recall |

## Standard Bus Architecture

| Bus | Routes to | Typical processing |
|-----|-----------|---------------------|
| Drum bus | All drum tracks | Glue comp 2–4dB GR, gentle EQ, saturation |
| Vocal bus | Lead + BGV + adlibs | Comp 1–2dB GR, EQ for stack cohesion, sometimes reverb send pre |
| Guitar bus | All gtrs (rhythm + lead) | Tone-shaping EQ, light comp |
| FX/dimension bus | Reverb + delay returns | EQ, sidechain ducking by lead vocal |
| Parallel drum bus | Drum sends | Heavy comp (10dB+ GR), bright EQ — NY trick |
| Parallel vocal bus | Vocal send | Heavy comp + distortion for grit blended underneath |
| Mix bus | Everything | Glue comp 1–3dB GR, mix-bus EQ, optional saturation |

## VCA vs Sub-Group — Which to Use

- Need to **process** the summed sound (compress, EQ) → sub-group (audio bus)
- Need to **control level** only without changing tone or send relationships → VCA
- VCA preserves pre-fader sends (verb sends stay at original ratios when VCA fader moves); sub-group disrupts that flow

## Insert vs Send

- **Insert** — processor on the channel/bus signal path; 100% wet through it; used for EQ, comp, gates
- **Send** — parallel split to aux bus with return; used for time-based FX (reverb, delay) and parallel processing
- Rule: serial coloration → insert. Parallel ambience → send.

## Benefits

1. **Mix recall** — one fader/process change updates whole group; fewer plugins; cleaner session
2. **Automation simplification** — automate VCA once instead of 12 individual drum faders
3. **CPU** — single compressor on bus vs. one per track
4. **Glue** — common comp/saturation across grouped tracks "fuses" them into a single sonic object

## Rules

1. Drum bus before mix bus — always. Glue drums first, then mix bus glues the glued groups
2. Parallel comp is a *send*, never an insert (preserves dynamics on dry path)
3. VCA for live-style fader rides; sub-group for tone work
4. Don't double-process — if drum bus has comp, mix bus comp must work lighter
