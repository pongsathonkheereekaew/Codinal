# Pro Tools DAW Reference (for our parity)

Source: Avid Pro Tools Reference Guide 2023.3 — https://resources.avid.com/SupportFiles/PT/Pro_Tools_Reference_Guide_2023.3.pdf

our models its single-sample edit + bar-grid behavior on Pro Tools. This doc encodes the PT semantics easby should assume when emitting `ArrangementDecision` or grid-aware `VariationDecision` payloads. Reference only — easby never executes timeline ops; codebase owns that (`TimebaseRulerComponent`, `WaveformPanel`, `TransportPanel`).

---

## 1. Edit Modes (four)

| Mode | Behavior | our relevance |
|---|---|---|
| **Shuffle** | Clips snap end-to-end. Moving/deleting ripples adjacent clips. No gaps allowed. | **Irrelevant** — single-sample, no multi-region timeline. |
| **Slip** | Free movement. No snap. Finest control. Default for sound-design. | **Core**. Default for waveform interaction. |
| **Spot** | Dialog-driven precise placement (timecode / bars\|beats / samples / feet+frames). | **Irrelevant** — no spot dialog in AH v1. |
| **Grid** | Selections + edits snap to grid resolution. | **Core**. Default for bar-grid mode. |

Exclusive — exactly one active at a time. PT shortcut row: `F1=Shuffle F2=Slip F3=Spot F4=Grid`. our v1 = **Slip + Grid only** (Q8 lock 2026-06-05).

### Grid sub-modes

- **Absolute Grid** — clip snaps to nearest grid line. Origin = grid line itself.
- **Relative Grid** — clip preserves its offset from nearest grid line during edits. Origin = current position.

Toggle independently of edit mode. our v1 = Absolute only.

---

## 2. Grid Resolution

PT exposes Grid resolution as **independent dropdown** — not tied to zoom level. Values:

**Bars\|Beats timebase**: `Bars | 1/2 | 1/4 | 1/8 | 1/16 | 1/32 | 1/64 note` — each with `straight | triplet | dotted` modifier.

**Min:Sec**: `1 min | 10 sec | 1 sec | 100 ms | 10 ms | 1 ms`.

**Timecode**: `1 frame | 10 frames | 1 sec | 10 sec | 1 min` (frame rate per session).

**Samples**: `1 sample | 10 | 100 | 1000 | 10000`.

our deviation (Q7 lock): **zoom-linked auto-resolution**. No dropdown.

| Zoom | Subdivision |
|---|---|
| Wide (full sample) | Bars only |
| Medium | Bars + beats |
| Tight | Bars + beats + 1/8 |
| Tightest | Bars + beats + 1/16 |

**Q7 lock relaxed 2026-06-08.** `BarGridComponent` now exposes a right-click
context menu: `Auto | 1/2 | 1/4 | 1/8 | 1/16 | 1/32 | 1/64 | ── | Straight |
Triplet | Dotted | ── | Off (Hide Grid)`. Auto remains the default and keeps
the zoom-linked ladder; manual entries pin a subdivision; Off hides the grid
and disables snap. Color hierarchy shipped same day: 1/16 `#A3A3A3`, 1/32
`#C0C0C0`, 1/64 `#D8D8D8`. Straight/Triplet/Dotted multiplier (`1.0 | 2/3 |
1.5`) applies to subdivision lines, drag/click/trim/nudge snap, and the Auto
adaptive ladder.

---

## 3. Snap Behavior

Snap **applies** to:

- Drag selection start/end
- Trim clip boundaries
- Click-scrub to set edit cursor
- Nudge (`←/→`; nudge value separate from grid value)
- Spot dialog entry
- Tab key (Tab-to-Transients off → next grid; on → next transient)

Snap **does NOT** apply to:

- Playback start position (PT plays from wherever cursor lands)
- "Edit Insertion Follows Playback" lets playback leave the edit cursor where it stopped — snap re-engages on subsequent edits

our parity: snap drives drag/click/nudge. Playback start = cursor position. Matches PT exactly.

---

## 4. Modifier Keys

- **Cmd** — temporary slip while in Grid mode (one-shot, releases on key-up)
- **Cmd+Shift** — temporary grid while in Slip mode
- **Ctrl** — fine-nudge (1 sample at any zoom)
- **Shift** — extend selection to clicked point

our v1: Cmd (temp slip in grid) + Cmd+Shift (temp grid in slip). Drop Ctrl/Shift for now.

---

## 5. Timeline / Main Time Scale

PT exposes five timebases switchable per-session:

1. **Bars\|Beats** (BBT) — tempo-relative. `bar|beat|tick` (960 ticks/beat).
2. **Min:Sec** — absolute clock.
3. **Timecode** — SMPTE (23.976, 24, 25, 29.97, 30 fps drop/non-drop).
4. **Feet+Frames** — film (35mm = 16 frames/foot).
5. **Samples** — absolute sample count.

Sub Counter shows secondary timebase. Tempo + meter rulers above timeline.

our v1 originally: **Bars\|Beats only**, hardcoded 4/4 (Q5 lock), t=0 anchor (Q6 lock). No SMPTE/feet+frames. Min:Sec optional later as sub-counter.

**Q5 / §5 lock relaxed 2026-06-08.** `TimeCodeEditComponent` (transport row, centered) exposes a right-click timebase menu with all four PT-relevant modes:

| Timebase | Display | Source |
|---|---|---|
| **Time** (default) | `M:SS.mmm` | clock seconds |
| **Bars\|Beats\|Ticks** | `bar.beat.tick` | 4/4 + t=0 (Q5/Q6 still apply inside this mode), 960 ticks/beat |
| **Samples** | `N` | file sample rate from `AudioEngine::getFileSampleRate()` |
| **Timecode (SMPTE)** | `HH:MM:SS:FF` | 30 fps non-drop default (no per-session fps selector yet) |

Each timebase supports the same PT segment-edit interaction (click → digits → ←/→/Tab → Enter / Esc). Bars mode falls back to `— bpm` when BPM is unknown; Samples mode falls back to `— sr` when no file is loaded. Feet+Frames remains out of scope.

---

## 6. Tempo & Conform

PT semantics for tempo changes:

- **Tick-based** (BBT-locked) clips → position is bar\|beat\|tick. Tempo change moves sample position; BBT stays.
- **Sample-based** (absolute-locked) clips → position is samples. Tempo change leaves sample position; BBT slides.

Per-clip flag: timebase selector per track.

our deviation (Q4 lock):

- Bar grid gated on `loops + analyzedBPM`.
- Fallback to transport tempo (120 BPM) when sample lacks analyzed BPM.
- No tempo automation — fixed tempo per session.

---

## 7. Tab to Transients

PT feature: `Tab` advances cursor to next detected transient instead of next grid line. Toggle in toolbar.

**High our relevance** — aligns with slice-based variation (`_spectral_flux_onsets` in `real_helper.py`).

**Promoted to v1 2026-06-08.** `Tab` advances cursor to the next entry in
`SampleRecord::getTransients()`; `Shift+Tab` moves backward; selection-start
is the cursor anchor. Wired through `KeyboardShortcutController::onTabToTransientShortcut`
→ `WaveformPanel::tabToTransient(int dir)`.

---

## 8. Nudge Value

Independent of grid resolution. Separate dropdown. Lets you grid-snap to bars while nudging by 1 ms with arrow keys.

our v1: defer.

---

## 9. Selection vs Insertion

PT distinguishes:

- **Edit Insertion** — single-point cursor. `Return` clears selection back to insertion point.
- **Edit Selection** — start/end range.

Both snap when grid mode active. Selection drag respects snap.

our: waveform `selectionStart`/`selectionEnd` — same model.

---

## 10. PT feature → our owner

| PT feature | our owner | Status |
|---|---|---|
| Slip mode | `WaveformPanel` mouse handler | Q8 (b) locked — ✅ shipped |
| Grid mode + snap (drag/click/trim) | `WaveformPanel` + `BarGridComponent` | Q8 (b) locked — ✅ shipped |
| Snap on nudge | `WaveformPanel::nudgeSelection` | ✅ shipped 2026-06-08 |
| Grid resolution menu | right-click on `BarGridComponent` | Q7 relaxed 2026-06-08 — ✅ shipped (Auto + 1/2..1/64 + Off) |
| Straight \| Triplet \| Dotted | `BarGridComponent::Modifier` | ✅ shipped 2026-06-08 |
| Hide Grid (PT "Snap Off") | `Subdivision::Off` | ✅ shipped 2026-06-08 |
| Subdivision color hierarchy | `BarGridComponent::paint` | ✅ shipped 2026-06-08 (1/16 #A3A3A3, 1/32 #C0C0C0, 1/64 #D8D8D8) |
| Bar number auto-decimation | `BarGridComponent::paint` | ✅ shipped 2026-06-08 (pow2 stride by pxPerBar) |
| Bar\|Beat ruler | `BarGridComponent` | ✅ shipped |
| Tempo conform | none (fixed tempo per sample) | Q4 by-design deviation — won't ship |
| Tab to Transients | `WaveformPanel::tabToTransient` | ✅ promoted v1 2026-06-08 (was Q7 v2-deferred) |
| Cmd / Cmd+Shift modifiers | `WaveformPanel` key handler | v1 — ✅ shipped |
| Edit Insertion Follows Playback | always-on (PT default) | v1 — ✅ shipped |
| Spot mode / dialog | not implemented | irrelevant for single-sample |
| Shuffle mode | not implemented | irrelevant for single-sample |

---

## 11. Easby usage

When user asks "what should grid do at amt N" or "should this slice land on bar":

1. Grid resolution = **zoom-derived** — never propose absolute grid values directly.
2. `VariationDecision.slice_ops.slice_idx` indexes onsets from `_spectral_flux_onsets`. PT's Tab-to-Transients is conceptual parallel — slices = transients.
3. `ArrangementDecision.bar_count` → default PT-style power-of-two bars (4/8/16/32). Off-grid only if user explicitly asks.
4. Refuse SMPTE / feet+frames / timecode questions → out of scope (our is BBT-only).

---

---

## 12. Mixing — Sends / Busses / Aux / VCA

PT mixer topology:

- **Audio track** — plays a clip; output bus-routable.
- **Aux Input track** — sums one or more busses; hosts insert FX; no clip recording.
- **Master Fader** — post-fader on its assigned bus/output; meters peak/RMS/LUFS; hosts dither + final-stage FX.
- **VCA Master** — no audio; controls fader/mute of grouped tracks (DCA-style); automation lanes write to the VCA, not the slaves.

### Sends

- 10 sends per track (A–J). Each routable to internal bus, output, or external HW.
- Pre-fader vs post-fader toggle per send.
- Send level + pan + mute independent of channel.
- Follow Main Pan option.

### Busses

- Up to 256 internal busses (stereo/mono/multichannel).
- Configured in I/O Setup. Path mapping persists per-session.
- Sub-paths allow nested routing (e.g. Drums bus → Mix bus).

### Insert slots

- 10 inserts per track (A–J). Pre-fader.
- Hardware Insert routes out a physical I/O pair and back (zero-latency mix).
- AudioSuite vs AAX Native vs AAX DSP — RT or render.

### our relevance

- **None for v1**. AH = single sample preview, no mixer topology.
- **Future**: Stacks shuffler (`StackMixerSource`) is conceptual parallel — 16 slots = lightweight aux structure. PT's send model could inform Stacks per-slot send→FX bus in v2.

---

## 13. Automation

PT automation modes per track:

| Mode | Read | Write |
|---|---|---|
| **Off** | no | no |
| **Read** | yes | no |
| **Touch** | yes | only while touching |
| **Latch** | yes | from first touch until stop |
| **Write** | yes | always overwrite |
| **Trim** | yes | additive offset |
| **Touch/Latch** | yes | touch in playback, latch on stop |

Automatable parameters:

- Volume, pan, mute, send level, send pan, send mute
- All plugin parameters
- Track input (with restrictions)

Automation lanes shown as breakpoint envelopes on track. Edit ops: Cut/Copy/Paste/Trim/Glue/Thin/Snap to current value.

### our relevance

- **None for v1**. AH has no automation.
- **Future v2 — Variation amt automation**: easby's `amt` parameter could be automatable in arrangement view. Maps cleanly to PT Touch/Latch model.

---

## 14. Clip Gain / Clip Effects

PT 2018+ feature:

- **Clip Gain** — per-clip dB offset envelope, drawn directly on waveform. Pre-insert. Renders into pool on Bounce-in-Place.
- **Clip Effects** — per-clip EQ + Dyn (compressor/limiter/gate) chain. Pre-insert. Lightweight, no plugin slot consumed.
- **Clip FX rendering** — Bounce-in-Place commits Clip Gain + Clip Effects to a new audio file.

### our relevance

- **Clip Gain** ↔ `WaveformPanel` future per-region gain envelope. **Medium relevance** for v2 mixing workflow.
- **Clip Effects** — out of scope. easby-mixing focuses on full-mix bus, not per-clip.

---

## 15. Beat Detective + Elastic Audio

### Beat Detective

PT clip-analysis tool for groove extraction + quantize:

1. **Bar | Beat Marker Generation** — auto-detect downbeats, write tempo map.
2. **Groove Template Extraction** — capture timing/velocity from reference, save as DigiGroove template.
3. **Clip Separation** — split selection at detected transients.
4. **Conform** — quantize separated clips to grid (strength + exclude-within slider).
5. **Edit Smoothing** — fill gaps with crossfades after conform.

Sensitivity slider gates transient detection threshold. Operates on single-track or multi-track selection.

### Elastic Audio

Real-time time-stretch on tracks. Algorithms:

- **Polyphonic** — chords, full mix. Best for music.
- **Rhythmic** — drums, percussion. Preserves transients.
- **Monophonic** — vocals, single instrument.
- **Varispeed** — tape-like (pitch follows speed).
- **X-Form** — offline render, highest quality.

Per-track. Warp Markers user-draggable on waveform. Quantize-to-grid via Event Operations.

### our relevance

- **High**. Slice-based variation pipeline (`_spectral_flux_onsets` + `_pitch_shift_chunk` + `_time_stretch` in `real_helper.py`) implements PT-style Beat Detective + Elastic Audio Polyphonic+Rhythmic.
- easby should treat slice ops as conceptual equivalent to Beat Detective Clip Separation + Conform.
- `signalsmith-stretch` ≈ Elastic Audio Polyphonic.
- RubberBand ≈ Elastic Audio Polyphonic w/ formant preservation.

---

## 16. Tempo Operations + Conductor

PT Conductor track holds tempo + meter map. Tempo Operations dialog:

- **Constant** — set tempo over range.
- **Linear** — ramp between two tempi.
- **Parabolic** — accelerate/decelerate non-linear (concavity param).
- **S-Curve** — ease-in/ease-out between two tempi.
- **Scale** — multiply existing tempi by factor.
- **Stretch** — fit existing tempo map to new bar count.

Meter changes inserted on bar boundaries. Click-track derived from Conductor.

### our relevance

- **Low for v1** (fixed tempo, 4/4 hardcoded, Q4+Q5 locks).
- **Future v2** — multi-sample sessions w/ tempo automation. Defer.

---

## 17. Bounce / Export

### Bounce Mix dialog

- **File Type**: WAV / AIFF / MP3 / MXF / etc.
- **Format**: Interleaved / Multiple Mono / Multichannel.
- **Bit Depth**: 16 / 24 / 32-float.
- **Sample Rate**: session SR or convert (44.1/48/88.2/96/176.4/192 kHz).
- **Source**: any output or bus path.
- **Offline Bounce** — render faster than realtime.
- **Online Bounce** — realtime, captures live hardware inserts.
- **Add MP3** — secondary MP3 alongside WAV.
- **Import After Bounce** — auto-import to Workspace.

### Quick Export

One-click bounce w/ saved preset.

### Sample Rate Conversion

- **Quality**: Tweak Head / Better / Best (TPDF dither at last stage).
- Linear-phase SRC.

### Dither

Master Fader insert slot — last in chain. Algorithms (Katz mapping; see Mastering SKILL §8 — canonical):

- **POW-r 1** — noise shaped away from 3–5 kHz. **Pop / rock / electronic.**
- **POW-r 2** — noise-shaped, intermediate. Less-critical material.
- **POW-r 3** — most aggressive shaping; ~19–20-bit performance on 16-bit. **Classical / acoustic / high dynamic range.**
- **TPDF** — flat triangular, 1 LSB, neutral. **General purpose, safest default.**

Apply dither **only at final bit-depth reduction** (e.g. 24→16). Never stack.

### our relevance

- **High for mastering persona**. `easby-mastering` should emit `MasterDecision` w/ dither algorithm + bit-depth + SRC choice modeled on PT's Bounce Mix options.
- **Medium for mixing persona**. Bounce-in-Place workflow (commit) maps to AH future "render variation" action.

---

## 18. Persona usage matrix

| PT topic | Producer | Mixing | Mastering |
|---|---|---|---|
| Edit modes (Slip/Grid) | core | low | low |
| Grid resolution + snap | core | low | none |
| Modifier keys | core | core | none |
| Bars\|Beats timeline | core | low | none |
| Tab to Transients | core | medium | none |
| Sends / Busses / Aux | none | core | none |
| VCA Masters | none | core | none |
| Automation modes | none | core | low |
| Clip Gain / Clip Effects | low | core | none |
| Beat Detective | core | medium | none |
| Elastic Audio | core | medium | none |
| Tempo Operations | low | low | none |
| Bounce / Export | low | core | core |
| Dither + SRC | none | low | core |
| Bit-depth + format | none | low | core |

---

## 19. Sources

- Pro Tools Reference Guide 2023.3 (Avid) — primary
- Q1–Q8 decision lock log: our memory, 2026-06-05
- Q-lock delta log 2026-06-08 (this doc): Q7 relaxed → manual override + Off; Tab-to-Transients promoted v1
- ADR-0013 Stacks Sync (precedent for sample-clock master / bar-locked playback)
- `Source/UI/TimebaseRulerComponent.h` (existing ruler scaffold)
- `Source/UI/BarGridComponent.h` (right-click subdivision menu, color hierarchy, modifier)
- `Source/UI/WaveformPanel.{h,cpp}` (snap helper + nudgeSelection + tabToTransient + seekTo)
- `Source/Controllers/KeyboardShortcutController.{h,cpp}` (NudgeLeft/Right/Fine, TabToTransientForward/Backward bindings)
