# SoundToys MicroShift — SoundToys (stereo-widening micro pitch-shifter)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 (Mac & Windows) |
| Type | Stereo widener / micro pitch-shift + time-varying delay (harmonizer / chorus-family) |
| Format | VST / VST3 / AU / AAX (SoundToys 5 standard set) |
| Source | manual: `SoundToys MicroShift/SoundToys MicroShift.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
The classic "micro-shift" stereo-widening trick in a refined plug-in: pitch the left channel up a few cents, the right channel down a few cents, add a dash of time-varying delay, and a mono/narrow source instantly spreads into a big, thick stereo image. It recreates the vibe — and the quirks (analog saturation, de-glitching behavior) — of the vintage hardware harmonizers the SoundToys founders (Ken Bogdanowicz & Bob Belcher) worked on at Eventide: the H3000 Multi-Effects Processor (and H910), plus the AMS/Neve DMX 15-80. Three "Style" buttons select the modeled flavor; MicroShift then goes *beyond* the original hardware with three extra knobs — variable **Detune** amount, variable **Delay** amount, and a **Focus** crossover that restricts widening to high frequencies so the low end stays tight. It is the full-featured big brother of **Little MicroShift** (which exposes only Mix + Style, with detune/delay/focus baked in). The go-to "make it WIDE" tool for vocals, backing vocals, guitars, synths, and anything that needs to sound larger than life.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Mix** | Dry ↔ Wet (0–100%) | Balance between dry (unprocessed) and wet (pitch-shifted + delayed) signal. 100% wet = clearest, widest result. Blending dry back in gives a thicker, more chorused tone. | 100% wet for max width on a 100%-wet insert/aux/bus; pull toward Dry on a mono/lead source to keep center punch and add subtle chorus thickness. |
| **Detune** | % (≈ around 100% default; e.g. 50% = halved, 200% = doubled) | Scales the amount of micro pitch-shifting applied by the active Style. Pitch shift is continually time-varying, so this is a *relative* percent multiplier on the Style's built-in detune, not a fixed cents value. More = wider/thicker but more "chorused"/detuned character. | Dial up for more obvious width/movement; dial down for a subtler, tighter widening that detunes the source less. |
| **Delay** | % (≈ around 100% default; 50% = halved, 200% = doubled) | Scales the amount of time-varying delay in the active Style. Like Detune, expressed as a percent because the delay continually varies over time. More delay = bigger, looser, more spacious spread; less = tighter, more immediate. | More for size/space (walls of sound, lush BGVs); less when you want width without smearing transients (tight rhythm guitars). |
| **Focus** | 20 Hz → 10 kHz (crossover freq) | Crossover point of a 2-band crossover filter; the widening effect is applied **only to the high band** above this point. Lows below the Focus point pass through unprocessed/centered. Defaults to 20 Hz (whole signal widened). | Raise it to widen only mids/highs — adds "shimmer"/"air" to vocals or guitars while keeping bass and low-mids mono and tight (avoids loose, muddy, phasey low end). Very source-dependent. |
| **Style I** | mode button (1 of 3) | Modeled on **H3000 preset #231**. Delay + pitch variation closely matched to the hardware (which oddly doesn't match its own front-panel numbers), with the original analog saturation emulated. The "classic" widening flavor. | Default go-to. Smooth, musical widening for vocals, BGVs, synths. |
| **Style II** | mode button (1 of 3) | Modeled on **H3000 preset #519**, a different pitch-shifting algorithm. Slightly different feel vs Style I — different amount of delay variation and a different frequency response. | A/B against Style I when I feels too much/too little; subtly different color and movement. |
| **Style III** | mode button (1 of 3) | Modeled on the **AMS/Neve DMX 15-80**. Much **wider delay variation**, different saturation, and a different, **harder "de-glitching"** circuit. The biggest, most obvious widener of the three. | When you want maximum width / the most dramatic spread — especially guitars and walls of sound. |

*(Styles I/II/III are mutually exclusive — exactly one is active at a time. Detune, Delay, and Focus then sculpt that Style. Standard SoundToys header bar adds preset prev/next, save/A-B, and undo.)*

## Use by lens
- **Producer (create):** Instant "bigger" button. Drop it on a synth, double-tracked guitar, or lead vocal during arrangement; pick a Style (III for the most dramatic spread, I for polished default), then push Detune/Delay to taste. Use Focus to widen only the top so the part keeps its low-end weight. Pair with doubling/layering to build walls of sound.
- **Mixing (balance):** The classic BGV thickener and width tool. Run 100% wet on a backing-vocal bus to spread and blend them around the lead; on a mono guitar use lower Mix (or higher Focus) to widen without losing punch or muddying the lows. Because width comes from L/R detune + delay, **always mono-check** — collapse to mono and confirm the widened source doesn't thin, hollow, or phase-cancel against the dry. Focus ≈ 200–500 Hz+ is a great trick to keep bass mono-safe while still widening.
- **Mastering (finalize):** Not a master-bus tool — it widens via pitch/delay manipulation that introduces detuning and mono-compatibility risk across the whole mix. Avoid on the master; prefer a dedicated stereo-imaging/MS tool for finalization. Mastering-adjacent only: parallel widening of an individual stem with Focus set high and the result mono-checked.

## Notes / gotchas
- **Beyond Little MicroShift:** the extra surface vs Little is exactly Detune, Delay, and Focus — the per-Style detune/delay are *scalable* here (Detune/Delay as %), and Focus lets you band-limit the widening. Same three Style models in both.
- **Percent, not cents/ms:** Detune and Delay are percentages because both the pitch shift and the delay are *continually time-varying* inside each Style. 100% ≈ the modeled hardware amount; 50% halves, 200% doubles.
- **Focus = highpass on the *effect*, not the signal:** below the Focus frequency the audio stays dry/centered; only content above it gets widened. Set it up to stop loose/muddy/phasey low end. Defaults to 20 Hz (everything widened).
- **Mono compatibility:** widening uses opposite-direction pitch shifts + time-varying delay between L and R — heavier Detune/Delay (especially Style III) can phase-cancel or thin out when summed to mono. Always mono-check for broadcast/club; use Focus to protect the lows.
- **Mono→stereo:** designed to turn a mono/narrow source into a wide stereo image; most dramatic on mono material (it still works on already-stereo sources).
- **Saturation is part of the sound:** each Style emulates the analog saturation (and de-glitching) of its source hardware, so the wet path adds subtle harmonic color, not just width.
- **Three Styles ≈ three classic units:** I = H3000 #231, II = H3000 #519, III = AMS DMX 15-80 (widest/hardest). Audition all three before committing.
- **Trademark note:** Eventide/Harmonizer/H3000 and AMS are referenced for historical/tonal purposes only; not endorsed by or affiliated with SoundToys.
- **Presets / housekeeping:** ships within SoundToys 5 / SoundToys 5 Rack; iLok-authorized. Negligible latency, light CPU.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
