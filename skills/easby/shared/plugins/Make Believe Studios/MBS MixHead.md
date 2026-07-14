# MBS MixHead — Make Believe Studios (saturation / tape)

| | |
|---|---|
| Vendor / ver | Make Believe Studios (DSP by Metric Halo) · v4.0.2 manual (build v4.0.3.161) |
| Type | Digital tape-saturation processor (warmth + perceived-loudness, modeled on a late-'90s/early-'00s digital-I/O hardware tape box) |
| Format | AAX (Pro Tools 11+ Mac / 10+ Win, Native AAX), AU, VST2, VST3 · 64-bit Mac (Intel/Apple Silicon) & Win |
| Source | manual: `MB MixHead/MBS MixHead.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
MixHead resurrects a specific hardware "plugin-in-a-box": a 1U digital-in/digital-out unit that added analog-tape-style warmth and perceived loudness to early digital recordings *without* the harshness of digital clipping or the hassle of real tape (no wow/flutter/noise, no extra A/D-D/A pass). It is a saturation/loudness "glue" tool, not a transparent tape sim — the manual stresses its controls are highly interactive and "counter-intuitive" by design (e.g. 30ips can sound *more* distorted than 15ips; Input and Drive interact strongly; HF-Adjust runs HF energy contrary to what real tape would do). Five primary controls (Input, Drive, HF-Adjust, Output, Tape Speed), three tape-speed algorithms incl. a new 3.75ips lo-fi mode, and efficient code for many instances. Usable at any stage of the recording chain.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Input Gain** | −12.0 to +12.0 dB, 0.1 dB steps | Pre-process input level (like a tape deck's line-in calibration). Sets how hard the signal hits the Drive stage — interacts greatly with Drive and Output. | Drive the saturation harder/softer without touching the Drive knob; set the operating point of the effect. |
| **Drive** | −7 to +14 (dB-ish) | Amount of harmonic distortion / saturation; **non-linear with gain**. Default 0.0 ≈ a record level of +7 dB to tape, so the effect is already fairly engaged at 0.0. Below 0 = more headroom, less dynamic saturation, Input/Output have more relative effect; high values = serious breakup. Usually needs Output compensation. | Dial in warmth → crunch. Low for subtle glue, high for aggressive color (esp. great high-passed in parallel on bass-heavy masters). |
| **HF-Adjust** | −6 (max cut) to +6 (max boost), 0.1 dB resolution | High-frequency cut/boost **independent of Drive**. Deliberately breaks tape's "more saturation = more HF damping" rule; simulates different tape formulations / playback electronics / bias-EQ. **Automatable** (unlike real tape). | Tame or open the top end; push instruments back or pull them forward over a song. At low saturation, HF boost acts like a vintage exciter. |
| **Output Gain** | −12.0 to +12.0 dB, 0.1 dB steps | Post-process output level. Compensates perceived-loudness changes from the Drive stage; ensures MixHead doesn't clip the next process. | Final make-up / gain-match A/B; keep level legal downstream. |
| **Tape Speed** | 15 ips / 30 ips / 3.75 ips (3-way toggle) | Selects the saturation algorithm. **15ips** (default, light dark): general 15ips distortion + a subtle unexpected stereo-widening effect. **30ips** (amber light): lower distortion, higher saturation headroom curve (note: the 40–70 Hz bass dip of real 30ips tape is *not* reproduced). **3.75ips** (green light): new lo-fi mode modeled on a 1950s Webcor machine — its headbump curve + heavy distortion, plus MixHead's own compression/limiting/HF behavior. | 15ips for default warmth+width; 30ips for cleaner/loud headroom; 3.75ips for gritty vintage lo-fi character. |
| **Active** | on/off (lit = processing) | Engages/bypasses MixHead processing. Mirrors (and is mirrored by) the header-bar Soft-Bypass button. | A/B the effect vs. dry. |
| *Power* | inactive placeholder | Far-right "power" button — **non-functional**, reserved for a future release. | — |
| *Presets (LCD segment)* | inactive placeholder | The Presets area of the LCD panel is **currently inactive**, reserved for a future release. (Header-bar preset menu still works.) | — |

**Meters (3 stereo sets):** *Input PPM* — peak after Input Gain, −30 dBFS→0 dBFS, 1 s peak hold; topmost segment = digital signal too hot (does not change color), 2nd-from-top = 0 dBFS, bottom "SIG" segment is a legacy AES-clock-lock indicator. *Drive Level* — how hard the Drive/saturation stage is working ("virtual tape record level"), −10 dB→+21 dB. *Output PPM* — peak after Output Gain, −30 dBFS→0 dBFS, 1 s hold; for safety keep the top two segments dark.

## Use by lens
- **Producer (create):** Print character early. Push **Input** so **Drive** bites, pick **Tape Speed** for vibe (3.75ips for lo-fi grit, 15ips for warm+wide), then ride **HF-Adjust** (automatable) to move parts forward/back in the arrangement. Trim **Output** to match.
- **Mixing (balance):** Glue/loudness on buses, color on tracks. Watch the **Drive Level** meter to judge how hard it's working; compensate with **Output**. The classic move on a bass-heavy mix bus is **high Drive in a high-passed parallel chain** — crunch in the mids/highs without smearing the lows. Use HF-Adjust like a gentle exciter at low Drive.
- **Mastering (finalize):** Subtle warmth + perceived loudness. Keep **Drive** modest (consider sub-0 for more headroom), nudge **HF-Adjust** to open or tame the top, and gain-match via **Input/Output** so the **Output PPM** top two segments stay dark (no clipping into the next stage). Note 30ips does *not* reproduce real tape's 40–70 Hz bass dip — don't expect that low-end scoop.

## Notes / gotchas
- **Controls are intentionally interactive / counter-intuitive.** Input↔Drive↔Output all push on each other; Drive 0.0 is already ~+7 dB-to-tape, not "off." Expect phase interplay in the highs and 30ips sounding *more* distorted than 15ips — per the designers, that's correct behavior.
- **Gain-link gestures:** Ctrl-Shift-drag **Input** to apply the inverse change to **Output** (and vice-versa) — keeps gain structure constant while shifting the Drive operating point. Knob/LCD gestures: click-drag = change, **Alt-click = reset**, **Ctrl-Alt-click = minimum**, **Ctrl-click / Right-click = text entry**. Tape Speed: click to step through models.
- **Three UI sizes:** Full / Mini / Micro (toggle/right-click the disclosure icon in the header). Standard Metric Halo header: A/B snapshot registers, Snapshot Blend, Undo/Redo, Compare, Soft-Bypass (= Active), `?` tooltips on every element.
- **Meters never recolor on overs** — the top segment just lights; learn to read it. Bottom "SIG" segment is a cosmetic legacy AES-lock light, not a level.
- No oversampling / latency / sidechain controls exposed in the manual. Emphasis on **low CPU / many instances**. Power button and LCD Presets segment are **dead placeholders** for now.
- Licensing: PACE iLok (account / iLok Cloud / 2nd-or-3rd-gen USB key); one license, any platform; v2/v3 licenses remain separate & valid.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
