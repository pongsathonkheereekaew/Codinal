# 10 — Pre-Master Checks and Mix Prep

## Pre-Master Checks (Katz + Owsinski)

Run before touching any processing:

### Polarity check

- Flip polarity on one channel; listen: if mix sounds fuller after flip → polarity problem in mix
- Check mono: fold to mono; listen for disappearing elements → phase cancellation → redirect to Mixing

### DC Offset

- Scope check: waveform asymmetric around zero = DC offset present
- Fix: high-pass filter at 2–5Hz (removes DC, inaudible); or dedicated DC offset removal (iZotope RX)
- DC offset = wastes headroom and causes click on track start/end

### Stereo Balance

- Measure L vs. R average levels; must be within 0.1dB
- Imbalance >0.1dB = panning error or monitor asymmetry; fix by trimming one channel or M/S panning adjustment

### Headroom audit

- Mix peaks should be −3 to −6 dBFS; if slammed to 0dBFS → request new mix
- Run true peak meter; inter-sample peak above 0dBTP before mastering = request new mix

## Mix Prep — What the Mastering Engineer Needs (Owsinski)

**Tell the mixer:**
- Don't over-EQ before sending — better slightly dull than over-bright
- Don't over-compress — hypercompression cannot be undone in mastering
- Print at native resolution (24-bit/48kHz or higher); **NO dither** on the mix export
- Leave headroom: -3 to -6 dBFS on peaks (not slammed to 0 dBFS)
- Reference the mix in mono before sending — phase problems visible immediately
- Provide alternate mixes if possible: instrumental, TV mix (no lead vox), acappella

## Digital Audio Basics (Owsinski)

| Sample rate | Use case |
|---|---|
| 44.1 kHz | CD standard |
| 48 kHz | Film/TV minimum |
| 96 kHz | Pro music standard |

| Bit depth | Dynamic range |
|---|---|
| 16-bit | 96 dB |
| 24-bit | 144 dB |

6 dB per additional bit. Never export at higher resolution than source.

## Headroom Contract (Mix → Master handoff)

| Measurement | Target | What it measures |
|---|---|---|
| Mix peak (dBFS) | -3 to -6 dBFS | Instantaneous sample peak |
| Mix integrated LUFS | -18 to -16 LUFS | K-weighted average over full track |
| Per stem peak (dBFS) | -6 to -3 dBFS each | Sample peak on each stem file |
| Mix / stem dither | none | Mastering applies final dither |

A mix peaking at -3 dBFS typically integrates around -16 to -18 LUFS — about 12 LUFS of dynamic range. Hot prints (peaks ≥ -1 dBFS) force the mastering limiter to start gain-staging from a deficit; request a new mix.
