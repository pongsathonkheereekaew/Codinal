# 11 — Stem Mastering Workflow

Stems = grouped submixes (drums, bass, instruments, vocals, FX) delivered as separate stereo files. More control than full-mix mastering without remixing.

## When to Use

- Problem mixes — one element (kick, vocal, bass) needs surgical work that broadband mastering can't reach
- Different platforms need different treatment (streaming + vinyl simultaneously)
- Mix balance was close but one bus needs ±1–2 dB across the song

## Stem Count — 3–8 Typical

| Stems | Layout |
|---|---|
| 4 | drums, bass, instruments, vocals |
| 6 | kick, drums-percussion, bass, instruments, lead-vox, BVs |
| 8 | kick, drums-percussion, bass, synths-keys, guitars, lead-vox, BVs, FX |

## Mandatory Delivery Rules

- All stems same length, sample-accurate start/stop from bar 1 of session — sum must reconstruct the original mix exactly
- Identical sample rate + bit depth across all stems (typically 24-bit/48 kHz or 24-bit/96 kHz)
- Interleaved stereo WAV per stem (not split-mono pairs)
- Peak per stem: -6 to -3 dBFS — no stem clips even with its own bus FX printed
- **NO dither on stems** — dither is applied once at the final master step
- Filename convention: `<song>_stem_<group>.wav` (e.g. `track01_stem_drums.wav`)

## Processing Order Options

- `individual_then_sum` — process each stem separately, sum to stereo, then final master chain. Maximum control, more setup time.
- `sum_then_process` — recombine stems first (verify match to mix), then traditional stereo master chain with light per-stem corrective EQ pre-sum. Faster.

## Verification

Import printed stems back into DAW, sum at unity — must sound identical to source mix. Any deviation = re-print.
