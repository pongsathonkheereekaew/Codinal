# SoundToys Sie-Q — SoundToys (EQ + saturation)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 |
| Type | Vintage-modeled 3-band EQ with output-stage saturation (Drive) |
| Format | VST3 / AU / AAX (Mac & Windows; iLok auth) |
| Source | manual: `SoundToys Sie-Q/SoundToys Sie-Q.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Sie-Q is Soundtoys' model of the Siemens **w295b**, a discrete silicon-transistor EQ "cassette" from the 1960s Siemens Sitral broadcast console. It is a deliberately simple, hard-to-make-sound-bad EQ: a low shelf/bell, a famously silky high band, and a switched mid bell on six broadcast-tuned center frequencies. The voicing is gentle and broad — curves and frequencies were chosen for "always musical" results rather than surgical control. Beyond the EQ, Soundtoys modeled the output amplifier's saturation; the **Drive** control (not on the original hardware) pushes the active circuit for analog grit. Unlike the stepped 2/3 dB gain switches of the hardware, every band has smooth continuous gain in the plug-in.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Low** (gain) | −15 to +15 dB | Low band. **Boost** = gentle bell with a very low center freq (adds bass "oomph"); **cut** = low-shelf shape (carves space, thins lows). Asymmetric boost-vs-cut shape. | Add weight/body, or clean up low-end mud and rumble. |
| **High** (gain) | −15 to +15 dB | High band — the star. **Boost** = gentle bell with a very high center (airy, silky top, extends ~10–20 kHz); **cut** = gentle low-pass slope. Stays smooth no matter how hard you boost. | Add air/sheen to vocals, acoustics, cymbals, mix/master bus; or tame brightness/digital edge. |
| **Mid Frequency** | switched: 700 Hz · 1000 Hz · 1500 Hz · 2300 Hz · 3500 Hz · 5600 Hz | Selects the center frequency of the mid bell (original "präsenz"/presence control). Six fixed broadcast-chosen points across the presence range. | Choose where to add/scoop presence on vocals & instruments. |
| **Mid Gain** | −8 to +8 dB | Cut or boost at the selected mid frequency. **Proportional-Q**: small gains = wide/gentle curve, large gains = narrower/more focused curve. | Accentuate presence and intelligibility, or soften harsh/honky mids. |
| **Drive** | −15 to +15 dB | Sets gain into the modeled output amplifier, controlling saturation amount from the active circuit. Positive settings (0→+15) also apply a static "auto-gain" trim **after** the saturation stage (proportional to Drive, not dynamic) to hold output level roughly in check. | Add analog color/grit/edge; push hard for obvious saturation, or back off (negative) for the cleanest path. |

## Use by lens
- **Producer (create):** A fast tone-shaper while tracking — dial in air on a vocal or guitar, add low-end body, pick a presence frequency, then crank Drive for instant attitude. Pairs famously with Decapitator in the Soundtoys Effect Rack to de-digitize sterile sources.
- **Mixing (balance):** Broad, forgiving moves — silky High band to lift vocals/acoustics above the mix, switched Mid to fix presence/harshness, Low shelf to clear mud or add weight. Light Drive glues and thickens. Not for surgical/notch work (use a parametric EQ for that).
- **Mastering (finalize):** A touch of the High band adds openness and life to a full mix; the gentle Low band nudges overall balance. Keep Drive subtle on the bus for analog character without overt distortion. Use sparingly — moves are wide-Q and broadband.

## Notes / gotchas
- **No bypass/output trim controls** — only the five knobs above (Low, High, Mid Freq, Mid Gain, Drive). Very simple panel.
- **Mid frequency is switched, not continuous** — you get the six fixed points only.
- **Mid range is ±8 dB**; Low/High/Drive are ±15 dB.
- **Proportional-Q on the Mid band**: Q tightens automatically as you push gain — you can't set Q independently.
- **Drive auto-gain is static, not dynamic** (not a compressor/limiter); it just trims post-saturation level on positive Drive so output doesn't run away. Driving still colors/saturates regardless of the gain comp.
- **Boost and cut are not mirror-images** on Low and High (boost = bell, cut = shelf/low-pass). Expect asymmetric curves.
- No oversampling/latency or sidechain options documented; lightweight CPU. Manual lists no factory preset content (it's a few-knob utility).

## Deep spec (Programmer only)
not reverse-engineered — capability only.
