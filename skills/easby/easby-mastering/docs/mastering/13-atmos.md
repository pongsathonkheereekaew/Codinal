# 13 — Dolby Atmos / Immersive Mastering

Object-based immersive format. Apple Music Spatial Audio = Dolby Atmos under the hood.

## Loudness Spec

| Parameter | Target |
|---|---|
| Integrated loudness | **-18 LUFS** (dialogue-gated, verified in Dolby Renderer) |
| True peak | **-1.0 dBTP** |
| Sample format | 24-bit LPCM @ 48 kHz |

The -18 LUFS target is 4 LU quieter than Spotify (-14) — sounds quiet in raw A/B but equal after streaming loudness normalization. Do not "fix" by limiting harder.

## Speaker Format — 7.1.4

- 7 floor channels (L, R, C, LFE, Ls, Rs, Lrs, Rrs) — that's 7.1 + 2 surround rear
- 4 height channels (overhead L/R front + L/R rear)

## Beds vs Objects

| Type | What it is | Use for |
|---|---|---|
| **Beds** | Fixed channel layout, max 7.1.2 (only 2 height channels) | Background music, ambience, reverb tails, stable wide content |
| **Objects** | Mono / stereo source with 3D position metadata; renderer places them per playback system | Lead vocal, prominent instruments, anything needing precise localization or movement |

Up to **128 objects** per mix. Use beds for the foundation, objects for elements that need spatial precision.

## Height Channel Content Guidance

- Reverb tails and room ambience → up
- Overhead percussion (hats, shakers, claps) → tasteful overhead placement
- Atmospheric pads, FX risers → height channels for envelopment
- **Never put lead vocal or kick exclusively in heights** — playback fallback (stereo, headphones) loses them

## Delivery — ADM BWF

- Single `.wav` file (Broadcast Wave Format) carrying up to 128 channels + spatial metadata via Audio Definition Model
- Length must match the accompanying stereo master exactly
- Verified in Dolby Atmos Renderer before delivery

## Approach

Dedicated Atmos mix from multitrack is strongly preferred over upmixing a stereo master. Tools: Dolby Atmos Production Suite, Nuendo, Pro Tools (Ultimate), Logic Pro 10.7.3+ (built-in Atmos plugin), Avid Pro Tools with Dolby Atmos Renderer.

**Binaural render check:** Atmos delivers a binaural render for headphones — audition this before sign-off; lead-vocal localization or low-end weight can shift versus speaker playback.
