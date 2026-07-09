# SoundToys Little MicroShift — SoundToys (stereo-widening micro pitch-shifter)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 (Mac & Windows) |
| Type | Stereo widener / micro pitch-shift + delay (chorus-family) |
| Format | VST / VST3 / AU / AAX (SoundToys 5 standard set) |
| Source | manual: `SoundToys Little MicroShift/SoundToys Little MicroShift.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
A one-knob, one-trick stereo widener that recreates the classic studio "micro-shift" effect: pitch the left channel up a few cents, the right channel down a few cents, add a touch of time-varying delay, and the source instantly spreads into a wide, thick stereo image. It captures the vibe (and the saturation + de-glitching quirks) of sought-after hardware harmonizers — the Eventide H3000 and the AMS/Neve DMX 15-80s — distilled into three preset "Style" buttons plus a Mix knob. The pitch/detune amount and delay times are fixed inside each Style; the user only chooses a Style and how much to blend. Made for fattening backing vocals, lead vocals, guitars, synths, and any track that needs to sound "larger than life." It is the stripped-down sibling of the full **MicroShift** (which adds delay-time, variable detune, and a multiband Focus control); Little MicroShift exposes none of those. Mono-in→stereo-out widener.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Mix** | Dry ↔ Wet (0–100%) | Balance between dry (unprocessed) and wet (pitch-shifted + delayed) signal. 100% wet = clearest, widest result. Blending dry back in gives a thicker, more chorused tone. | 100% wet for max width on a 100%-wet insert/aux; pull back toward Dry on a full-band/lead source to keep center focus and add subtle chorus thickness. |
| **Style I** | mode button (1 of 3) | Modeled on **H3000 preset #231**. Delay + pitch variation closely matched to the hardware (which, oddly, doesn't match its own front-panel numbers), with the original analog saturation emulated. The "classic" widening flavor. | Default go-to. Smooth, musical widening for vocals, BGVs, synths. |
| **Style II** | mode button (1 of 3) | Modeled on **H3000 preset #519**, a different pitch-shifting algorithm. Slightly different feel vs Style I — different amount of delay variation and a different frequency response. | A/B against Style I when I sounds too much/too little; subtly different color and movement. |
| **Style III** | mode button (1 of 3) | Modeled on the **AMS/Neve DMX 15-80**. Much **wider delay variation**, different saturation, and a different, **harder "de-glitching"** circuit. The biggest, most obvious widener of the three. | When you want maximum width / the most aggressive spread, especially on guitars and walls of sound. |

*(Styles I/II/III are mutually exclusive — exactly one is active at a time. There are no other knobs, no per-channel detune, no delay-time, no input/output trim on the panel.)*

## Use by lens
- **Producer (create):** Instant "bigger" button. Slap it on a synth, double-tracked guitar, or lead vocal during arrangement to hear it sit wider in the field. Cycle the three Styles to taste — III for the most dramatic spread, I for polished default. Pair with doubling/layering to build walls of sound.
- **Mixing (balance):** The classic BGV thickener and width tool. Run it 100% wet on a stereo backing-vocal bus to spread and blend them around the lead; use lower Mix on a mono guitar to widen without losing punch. Because width comes from L/R detune + delay, **always mono-check** — collapse the mix to mono and confirm the widened source doesn't thin out, hollow, or phase-cancel against the dry. Great for opening space around a busy center.
- **Mastering (finalize):** Not a mastering-bus tool — it widens by pitch/delay manipulation that introduces detuning and mono-compatibility risk across the whole mix. Avoid on the master. If width is needed at this stage, prefer a dedicated stereo-imaging/MS tool. (Mastering-adjacent only: parallel widening of a stem, mono-checked.)

## Notes / gotchas
- **Fixed effect, almost no params:** the entire sound is Mix + which Style. All detune amounts, delay times, saturation and de-glitch behavior are baked into each Style preset — for fine control over delay time / detune / multiband focus you need the full **MicroShift**, not Little.
- **Mono compatibility:** widening is achieved with opposite-direction pitch shifts and time-varying delay between L and R — heavier settings (especially Style III) can phase-cancel or thin out when summed to mono. Mono-check anything destined for broadcast/club.
- **Mono→stereo:** designed to turn a mono or narrow source into a wide stereo image; on an already-wide stereo source it still works but the effect is most dramatic on mono material.
- **Saturation is part of the sound:** each Style emulates the analog saturation of its source hardware, so the wet path adds subtle harmonic color, not just width.
- **Three Styles ≈ three classic units:** I = H3000 #231, II = H3000 #519, III = AMS DMX 15-80 (the widest/hardest). Audition all three before committing.
- **Presets:** ships within the SoundToys 5 / SoundToys 5 Rack environment; minimal surface means presets mostly just store Style + Mix. iLok-authorized. Negligible latency, light CPU.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
