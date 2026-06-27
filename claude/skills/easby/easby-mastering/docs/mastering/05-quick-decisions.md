# 05 — Quick Decisions (hot-path lookup)

Always load. First-pass answers; deeper files refine.

## Platform Loudness Targets

| Platform | Integrated LUFS | True Peak |
|---|---|---|
| Spotify | -14 LUFS | -1.0 dBTP |
| Apple Music | -16 LUFS | -1.0 dBTP |
| YouTube | -14 LUFS | -1.0 dBTP |
| Tidal | -14 LUFS | -1.0 dBTP |
| Broadcast (EBU R128) | -23 LUFS | -1.0 dBTP |
| Club / DJ | -9 to -6 LUFS | -0.3 dBTP |
| Dolby Atmos (Apple Music Spatial) | -18 LUFS | -1.0 dBTP |
| Vinyl | -12 to -9 LUFS | N/A (groove limit) |

## Mastering Chain Order (canonical)

1. Broad EQ — corrective tonal shaping (cut-first; max 2–4 moves)
2. Compression — glue / dynamic control (ratio 1.5:1–3:1; 2–4 dB GR typical)
3. Saturation — optional harmonic warmth pre-limiter (digital sources only)
4. EQ — subtle high-shelf air or post-compression correction
5. Stereo / M-S processing — width, mono compatibility check
6. Limiting — brick-wall true peak compliance
7. Metering — LUFS integrated, true peak, DR score

**Never reorder steps 1–7.** Compression before saturation before limiting — always.

## Headroom Contract (Mix → Master handoff)

dBFS peaks and LUFS integrated are **different measurements** — both targets coexist on the same healthy mix.

| Measurement | Target | What it measures |
|---|---|---|
| Mix peak (dBFS) | -3 to -6 dBFS | Instantaneous sample peak |
| Mix integrated LUFS | -18 to -16 LUFS | K-weighted average over full track |
| Per stem peak (dBFS) | -6 to -3 dBFS each | Sample peak on each stem file |
| Mix / stem dither | none | Mastering applies final dither |

A mix peaking at -3 dBFS typically integrates around -16 to -18 LUFS — about 12 LUFS of dynamic range. Hot prints (peaks ≥ -1 dBFS) force the mastering limiter to start gain-staging from a deficit; request a new mix.

## K-System Quick Reference

| K-System | dBFS reference | dB SPL (at ref) | Typical use |
|---|---|---|---|
| K-20 | -20 dBFS | 83 dB SPL | Classical, film, wide DR |
| K-14 | -14 dBFS | 79 dB SPL | Jazz, acoustic, high-fidelity pop |
| K-12 | -12 dBFS | 77 dB SPL | Pop, rock, contemporary |
| K-0 | 0 dBFS | — | Don't care / loudness-normalized streaming |

### K-System ↔ Compression Trade-off (Katz)

Lower K-meter = more compression required to hit a given LUFS target. Plan ratio + GR per K-bucket:

| K-System | Typical extra GR to hit -14 LUFS streaming | Sound character |
|---|---|---|
| K-20 (classical/wide DR) | +5–7 dB GR — heavy compression — kills the dynamic range that K-20 exists to preserve. Don't push to -14 LUFS from K-20; ship at quieter LUFS. |
| K-14 (jazz/HD pop) | +2–4 dB GR — moderate compression — preserves DR, balanced. |
| K-12 (pop/rock) | +1–2 dB GR — light compression — already loud-mastered, comp adds glue not loudness. |

⚡ **Rule:** match the K-bucket to the genre, then accept the LUFS the K-bucket can naturally reach. Forcing a wide-DR K-20 master to -14 LUFS is mastering malpractice — choose -16 or -18 LUFS instead.

## Default Limiter Ceiling

`-1.0 dBTP` streaming; `-0.3 dBTP` club/DJ; `-2.0 dBTP` broadcast.

## Default Dither

TPDF for general; POW-R Type 1 for pop/electronic; POW-R Type 3 for classical/acoustic.
