# 14 — Apple Digital Masters (formerly MFiT)

Apple's certification for high-quality streaming masters. Naming: "Mastered for iTunes" (2012) → "Apple Digital Masters" (2019).

## Delivery Spec

| Parameter | Target |
|---|---|
| Source format | 24-bit minimum |
| Sample rate | 44.1 kHz minimum; **96 kHz preferred** |
| No upsampling / bit-padding | Native resolution only |
| True peak ceiling | **-1.0 dBTP** (inter-sample) |
| Inter-sample peak verification | Required (afclip) |

## Apple's Encode Chain

source → 32-bit float `.caf` → sample-rate conversion → AAC 256 kbps. Higher-resolution source = better AAC output (cleaner SRC + encode headroom).

## afclip Tool

- Apple's free CLI checker; reports clipped samples with location, channel, count
- Generates a stereo audio file (L = original, R = graphic representation of clipping) for visual inspection
- Run before submission; any clipping = re-master

## Codec Pre-Check (recommended)

- Apple's "Mastered for iTunes" droplets / Apple's `afconvert` simulate the AAC encode
- Audition the simulated AAC against the master — verify no codec-induced distortion or sibilance lift
- AudioUnit `auval` validates plugins used in the chain

## Avoid Steep Linear-Phase Pre-Ringing

- Steep linear-phase low-cuts and brick-wall limiters produce symmetric pre-ringing audible as a "tick" or "whoosh" before transients
- AAC encode preserves this artifact; on quiet content (acoustic, classical) it becomes audible
- Use minimum-phase or gentler-slope linear-phase on the master bus when possible

## Benefit

Apple Digital Masters AAC sounds better than CD-rate AAC because the encoder works from cleaner 24/96 source — fewer artifacts in SRC and encoding stages.
