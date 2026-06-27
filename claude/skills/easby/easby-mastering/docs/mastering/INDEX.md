# Mastering Knowledge Index (machine-readable)

Trigger → file → topic. Load on demand; never load all up-front.

| Trigger keywords | File | Topic |
|---|---|---|
| compromise / first principle / taste / monitoring philosophy | `00-mastering-mind.md` | Compromise rule, tonal balance reference, monitor philosophy |
| eq / shelf / baxandall / yin-yang / feather / linear-phase / minimum-phase | `01-eq.md` | Corrective EQ, Q selection, feathering, shelf choice |
| macrodynamics / microdynamics / album leveling / domino effect | `02-dynamics.md` | Manual riding vs compression, 4 varieties of DR, album leveling |
| compressor / multiband / dynamic eq / hypercompression / saturation | `03-compression.md` | Mastering comp settings, multiband, hypercompression refusal, saturation |
| limiter / ceiling / true peak / brick-wall / manual peak ride | `04-limiting.md` | Limiter rules, transparent technique, manual gain drops |
| quick / LUFS target / chain order / headroom contract / first-pass | `05-quick-decisions.md` | Always-loaded hot path |
| monitoring / K-system / calibration / meter / Lissajous / phase correlation | `06-monitoring-metering.md` | K-System SPL, all meter types |
| dither / TPDF / POW-R / wordlength / truncation | `07-dither.md` | Dither types, anti-patterns, PT placement |
| mid-side / M/S / sides / center / stereo width | `08-mid-side.md` | M/S math, EQ, compression |
| noise reduction / hiss / hum / click / RX | `09-noise-reduction.md` | Tiered NR approach |
| pre-master / polarity / DC offset / stereo balance / mix prep / headroom | `10-pre-master-checks.md` | Checks before processing, mixer brief |
| stem / stems / sub-mix / individual_then_sum | `11-stem-mastering.md` | Stem mastering workflow |
| vinyl / RIAA / lacquer / lathe / mono below | `12-vinyl.md` | Vinyl cutting constraints |
| atmos / immersive / 7.1.4 / objects / beds / ADM BWF | `13-atmos.md` | Dolby Atmos delivery |
| apple digital masters / MFiT / afclip / AAC 256 | `14-apple-digital-masters.md` | Apple Digital Masters spec |
| Pro Tools / dither placement / SRC / bounce | `~/.claude/skills/easby/easby-producer/docs/easby/09-pro-tools-daw-reference.md` | Shared PT reference |

## Always-loaded

- `05-quick-decisions.md`

## Conflict precedence

1. `01-eq.md` wins on EQ moves and shelf choice
2. `02-dynamics.md` wins on macro vs micro problem diagnosis
3. `03-compression.md` wins on compressor/multiband/dynamic-EQ math
4. `04-limiting.md` wins on ceiling and limiter behavior
5. `07-dither.md` wins on wordlength reduction and dither placement
6. `08-mid-side.md` wins on stereo-domain processing
7. `10-pre-master-checks.md` wins on mix-quality gates before processing
8. `12-vinyl.md` / `13-atmos.md` / `14-apple-digital-masters.md` win on platform-specific delivery
9. `05-quick-decisions.md` wins for the hot-path first-pass answer
10. `00-mastering-mind.md` is taste tiebreaker only
