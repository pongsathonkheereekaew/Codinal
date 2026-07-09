# 08 — Automation

Static mix snapshots a single moment. Songs are not static — energy rises into choruses, drops into bridges, vocals breathe louder on key words. Automation makes the mix follow the song.

## What to Automate, When

| Parameter | Typical move | When |
|-----------|-------------|------|
| Vocal fader | +1 to +2dB on chorus, ride per-word in verse | Every chorus; weak syllables in verse |
| Vocal reverb/delay send | -3 to -6dB in verse, +3dB into chorus | Section transitions |
| Drum bus | +1dB on chorus | Every chorus |
| Filter sweep on synth/pad | sweep open into drop | Pre-chorus / build |
| Mute automation | mute hi-hat in breakdown, mute snare reverb on quiet passages | Section change |
| FX send (delay throw) | +6dB momentary spike on last word of phrase | Per phrase |
| Bass fader | +0.5–1dB on chorus to match drum lift | Every chorus |
| Pan automation | slow LFO-style pan on solos | Solo sections |
| Plugin bypass | bypass distortion in soft bridge | Section change |

## Clip Gain vs Track Automation

- **Clip gain** — pre-fader, pre-insert; rides waveform level *before* compression. Use to even out raw performance variance (loud breath, weak word, plosive) so compressor reacts evenly. "Fix the source so the chain works less."
- **Track automation (fader)** — post-insert; rides final delivered level. Use for musical/section moves (chorus lift, verse intimacy).
- **Workflow rule:** clip-gain first → compress consistent signal → automate fader for musical shape. Don't automate fader to fix what clip gain should handle.

## Automation Modes

| Mode | Behavior | Use case |
|------|----------|----------|
| Off | No read, no write | Hidden / disabled |
| Read | Plays back recorded automation, no overwrite | Default playback |
| Touch | Writes while touched; returns to previous value on release | Surgical edits inside existing automation |
| Latch | Writes while touched; **stays at last value** on release until stop | Long sustained rides (e.g. fader through chorus) |
| Write | Overwrites continuously from playback start | First pass / initial print; dangerous — wipes prior moves |
| Trim | Adds/subtracts relative to existing curve | Global rebalance without rewriting |

## Practical Rules

1. Write mode on first pass only; Touch/Latch for all subsequent revisions
2. Vocal fader rides typically every 2–4 bars in dense arrangements; every word in sparse ones
3. Automate reverb/delay sends, not return levels — preserves return EQ/character
4. Section moves (verse→chorus) first, then per-word rides
5. If you're cranking compression ratio to control dynamics, automate clip gain first — compressor only finishes what gain riding starts
