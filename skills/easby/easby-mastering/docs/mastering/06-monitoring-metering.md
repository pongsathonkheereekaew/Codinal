# 06 — Monitoring and Metering

## K-System Monitor Calibration (Katz)

| K-System | dBFS reference | dB SPL (at ref) | Typical use |
|---|---|---|---|
| K-20 | -20 dBFS | 83 dB SPL | Classical, film, wide dynamic range |
| K-14 | -14 dBFS | 79 dB SPL | Jazz, acoustic, high-fidelity pop |
| K-12 | -12 dBFS | 77 dB SPL | Pop, rock, contemporary |
| K-0 | 0 dBFS | — | Don't care / loudness-normalized streaming |

**How to calibrate:** set monitor output so that pink noise at the reference dBFS level reads target dB SPL on a calibrated meter at the listening position.

**Consistent fixed listening level** — not volume-normalized perception:
- TV broadcast calibration: 82 dB SPL
- Film mastering calibration: 85 dB SPL
- Music: typically 79–83 dB SPL for K-14 calibration

## Metering Tools (Owsinski) — Use All Simultaneously

### Peak Meter + Inter-Sample Distortion

- Peak meter = sample peak values (dBFS); does NOT show what the DAC reconstructs.
- **Inter-sample distortion (Owsinski Ch.6).** Between samples, the DAC reconstructs a smooth analog waveform via interpolation. The reconstructed waveform can peak *above* 0 dBFS even when all individual samples sit at or below 0 dBFS. This is most extreme at phase-aligned stereo transients (kick + snare landing together, mastered "loud" tracks).
- **Consequence:** a track that "doesn't clip" on a sample peak meter can still clip on consumer hardware (especially lossy decoders, which add their own peaks). Streaming platforms penalize this.
- True Peak meter (Nugen Mastercheck, Intersample Pro, iZotope) required for streaming compliance — these meters oversample 4×/8× to estimate the reconstructed peak.
- **True peak ceiling:** -1.0 dBTP standard; -2.0 dBTP for broadcast; -1.5 dBTP recommended for tracks targeting lossy distribution (MP3 320 / AAC 256).

### RMS Meter

- 300ms integration; shows average power — more correlated to perceived loudness than peak
- Rule: RMS should sit 10–14 dB below peak (healthy dynamic range)
- If RMS ≈ peak → hypercompressed; stop mastering, redirect to Mixing

### Phase Scope (Lissajous Figure)

- X-Y oscilloscope: X = L−R (sides), Y = L+R (mid)
- Shapes → meaning:
  - Thin vertical line: mono / too narrow
  - Wide ellipse tilted ~45°: healthy stereo
  - Mostly horizontal: danger — heavy out-of-phase content; mono cancel
  - Rotating/spinning: phase movement — OK if biased toward vertical

### Phase Correlation Meter

- Scale: +1 (perfect in-phase) → −1 (perfect out-of-phase)
- Target: stay in +0.5 to +1.0 for music
- Below 0: mono-incompatible — bass disappears in mono
- At −1: full null in mono; do not release

### Spectrum Analyzer

- Use 1/3 or 1/6 octave resolution (1/6 catches narrow resonances better)
- Integration: 300–600ms for mastering decisions (not real-time FFT flash)
- Reference tonal curve: symphonic orchestra = gold standard; compare your mix against it
- Spot-check with pink noise (flat 1/3-octave reference) to confirm monitor accuracy

### Dorrough / VU / LUFS (Katz)

- **Dorrough meter**: dual-scale (peak + average simultaneously) — preferred for seeing both at once
- **VU meter**: 300ms integration, 13dB usable range; not correlated to perceived loudness
- **LUFS/LUF**: ITU-R BS.1770 — use integrated LUFS for platform loudness targeting
