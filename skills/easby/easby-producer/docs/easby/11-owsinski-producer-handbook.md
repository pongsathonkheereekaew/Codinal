# 11 — Owsinski Producer Handbook (Distilled)

Distilled operating principles from Bobby Owsinski, *The Music Producer's Handbook* (5th ed.,
Hal Leonard, 2010). Filtered to what Easby-Producer can act on: arrangement, music mechanics,
variation philosophy, vocal success criteria, producer conduct. Recording-engineering material
(mic choice, preamp routing, studio acoustics) is out of scope and intentionally dropped.

Citation shorthand: `O-Ch5`, `O-Ch6`, `O-Ch7`, `O-Ch10`, `O-Ch11`.

---

## 1. Arrangement Elements (O-Ch5, O-Ch14)

Every modern arrangement decomposes into **5 element slots**. A group of instruments playing
the *same rhythm* counts as one element (doubled guitar = one; doubled vocal + 2 harmonies = one).

| Element | Role | Typical instruments |
|---|---|---|
| **Foundation** | Rhythm-section pulse | Bass + drums (sometimes rhythm guitar / keys when locked to bass) |
| **Pad** | Long sustained chord/note glue | Hammond, Rhodes, synth pad, string section, guitar power chord |
| **Rhythm** | Counter to foundation; adds motion | Shaker, tambourine, congas, backbeat rhythm guitar |
| **Lead** | Focal melodic voice | Lead vocal, lead instrument, solo |
| **Fills** | Answers in the spaces between leads | Counter-line, signature riff, bg-vocal answer, piano fill |

### Arrangement Rules (hard)

- **Limit to 4 elements simultaneously.** 3 elements often works. 5 rarely does.
- **Every element in its own frequency range.** If two share a band+octave they clash —
  change sound, change octave, or stagger their entries.
- **Multi-guitar disambiguation:** different line, different register/voicing, different
  rhythm, OR different sound (instrument/amp). Pick at least two.

### Reconciliation with sibling docs

`03-composition-methods.md` § Story Curve states "Verse — medium density (4–6 elements)",
which appears to exceed this cap. Resolve as follows:

- **Default cap = 4.** Owsinski + `00-producer-mind.md` Taste Rule §2 ("Space over density.
  Prefer 4 elements with room to breathe over 12 fighting") agree.
- **5 elements acceptable** if (a) the ornament is brief (≤2 bars), (b) the added element
  occupies an otherwise-empty frequency band, and (c) `expected_audible_change` cites the
  improvement direction. This matches Owsinski's "very rarely 5 works".
- **6+ elements** = refuse. The 03-comp "4–6 verse" upper bound is for dense modern pop
  where two slots are effectively transparent (e.g. brushed perc + pad ambience). When in
  doubt, count layers like Owsinski would: same-rhythm group = one element.

### Operational consequence for Easby

When recommending a variation that *adds* an element to a loop slot, verify the slot does
not push the section over 4 active elements. If it would, refuse or recommend a swap:
emit `elements_remove` alongside `elements_add` in `ArrangementDecision`.

For `03-comp` Heuristic 3 ("Final chorus must contain ONE new element"): if the prior
chorus already had 4 elements, the new ornament must be brief OR an element must be
removed in compensation. Use `elements_add` AND `elements_remove` in the same
`ArrangementDecision`.

---

## 2. Common Song Problems Taxonomy (O-Ch5)

When the user asks "why doesn't this loop work?", check against this list before generating
a variation. The variation should *fix* one of these, not paper over it.

1. **Too long.** Sections drag. (2-min intro, 3-min solo.) Variation: tighten by deleting bars.
2. **No focus.** Chords meander; sections indistinguishable. Variation cannot fix this — needs rewrite.
3. **Weak chorus.** Verse and chorus identical. Variation: lift chorus via element add, harmony,
   anticipation, or different chord changes (see `06-music-theory.md` § cadence + secondary
   dominant for the theory operations).
4. **No bridge.** Tension/release missing at song midpoint. Variation: introduce a bridge-feel
   slot (key change, dynamic dip, rhythm change).
5. **Poor arrangement.** Same lick/chord/rhythm whole song. Variation: introduce counter-line
   or fill in a later section.
6. **No intro/outro hook.** No memorable instrumental signature. Variation: lift a strong
   melodic fragment from the loop and place it as bookend.
7. **No song dynamics.** Volume/intensity stays flat. Variation: drop a slot in verse 2,
   re-introduce in chorus 2. See dynamic scale below.

---

## 3. Section Dynamic Scale 1–10 (O-Ch5, O-Ch6)

Reference target levels for energy. `ArrangementDecision.energy_level` should track this.

| Section | Target | Notes |
|---|---|---|
| Intro | 7–8 (pop/rock) · 1–3 (EDM/DJ) | Genre-dependent — see note below |
| Verse 1 | 4–5 | Make room for vocal/lead |
| Prechorus | 7 | Lifts toward chorus |
| Chorus | 9 | Hook peak; lift via add/anticipation |
| Verse 2 | 5–6 | Slightly louder than verse 1 |
| Prechorus 2 | 7 | Same as P1 |
| Chorus 2 | 9 | Match chorus 1 |
| Bridge | 10 *(peak)* or 1–2 *(breakdown)* | Either extreme; never middle |
| Out chorus | 9 | Match earlier choruses |
| Outro | 7–8 | Fade or tag |
| Breakdown | 1–2 | Optional; whisper region |

**Intro genre split.** Owsinski's 7–8 reflects rock/pop intros (full instrumental hook
before verse). `03-composition-methods.md` § Energy Arc states "Sparse intro — 1–3
elements, hint at hook," which is the EDM/DJ-tool convention (16–32-bar DJ intro). Both
are correct for their genre. Easby selects target by `ArrangementDecision.section_context`:

- Rock / pop / country / soul → Owsinski intro = 7–8.
- House / techno / trap / DnB → 03-comp intro = 1–3.
- Hip-hop → 4–6 (verse-density intro is common).

**Element-density ↔ intensity mapping.** `03-composition-methods.md` § Story Curve uses
qualitative density labels; this scale quantifies them:

| 03-comp label | This scale | Typical element count |
|---|---|---|
| Sparse | 1–3 | 1–2 elements |
| Medium | 4–6 | 3–4 elements |
| Full | 7–9 | 4 elements + ornament |
| Peak | 10 | 4 + chorus ornament + ad-libs |

**The Secret to Playing Dynamically (verbatim):**
> When you play loudly, play as loudly as you can.
> When you play softly, play as softly as you can.

**Don't confuse volume with intensity.** When dropping a section to lower dB the player
must keep: (a) same attacks/releases, (b) same tempo, (c) same internal dynamics per beat.
Drop volume, NOT intensity. Sloppy soft = wimp; tight soft = power at any level.

---

## 4. Music Mechanics — Tightness Checklist (O-Ch6)

When evaluating whether a loop/variation "feels tight," check in order:

1. **Song starts/stops together** — including pickups and mid-song stops. No "fix in the mix."
2. **Accents played the same way** by every element — same timing, same intensity, same phrasing.
3. **Groove established** — `groove = pulse + how instruments dynamically breathe with it`.
4. **Attacks AND releases match** — releases are the silent killer; everyone ends a phrase
   the same way.
5. **Turnarounds defined** — the 1–2 bars between sections must have an *exact* part, not
   improvised. Drum fills must have precise notes other elements lock to.
6. **Tempo right** — 1 bpm matters. Test ±2 bpm before committing. Faster ≠ more exciting.
7. **In tune** — non-negotiable.

### Pocket types (drummer-style → variation BPM placement)

| Pocket | Where beat sits | Effect | Examples |
|---|---|---|---|
| **Straight / on-top** | Right on grid | Driving, machine-like | Disco, quantized programming, Stewart Copeland |
| **Laid-back** | Behind beat | Heavy, relaxed | Phil Rudd (AC/DC), Bonham, Clyde Stubblefield |
| **Urgent / in-front** | Ahead of beat | Pushing, anxious | Stewart Copeland (Police) |

Pocket type is a property of the *loop's source* — variations should preserve it. Don't
quantize a laid-back loop to grid; you kill the pocket.

### Groove tension principle

> A groove is created by tension against even time. Perfect quantization removes tension
> and the song loses its groove.

Easby should NOT recommend hard-quantize variations on swing/funk loops. Default to micro-timing
preservation unless the source itself is already grid-locked.

### Builds (O-Ch6)

Builds (transitions between sections) must go from **same low volume → same high volume**
each time. Inconsistent build endpoints break section identity. When emitting
`ArrangementDecision.transition_in` with `type: riser`, the riser must terminate at the
target section's `energy_level`.

---

## 5. "Make It Better, Not Just Different" — Variation Gate (O-Ch10)

**The central producer principle for variation.** Easby must apply this gate to every
emitted `VariationDecision`:

> Sometimes an artist will come up with good idea after good idea for new lines and parts,
> and while most of them might work, they just make the song *different* and not *better*.
> It's up to you to focus the energy back to where it needs to be.

### Implementation rule

Every `VariationDecision` must populate `expected_audible_change` with **a stated improvement
direction** — not just "what changed." Bad: `"bar 3 has a pitch shift up 9 semitones"`. Good:
`"bar 3 brightens with V/V approach, lifting energy into chorus"`.

If the change is purely cosmetic (timbre swap, random pitch jitter) with no improvement
direction, **drop amt by one rung** and re-evaluate. If still no improvement direction,
refuse:

```json
{"type": "Refusal", "reason": "different_not_better",
 "redirect": "operator must specify improvement target (energy lift / contrast / hook lift)"}
```

### First inspiration usually wins

> The artist's first inspiration is usually the best, and it's probably the one that
> attracted you to him in the first place.

For Easby: when amt=1 (subtle) sounds right on first pass, **do not propose amt=3+** to
appear more useful. Stop at the smallest delta that creates audible improvement.

### Two-session experiment rule

> The first day you take that brilliant seed of an idea and work it out, and the second day
> is when the idea flowers and you can properly execute it.

For Easby: variations exploring genuinely new territory (e.g. cross-genre transplant,
modal modulation) should be flagged `confidence < 0.7` on first emission. Operator should
hear it, sleep on it, re-grill the next day. Don't claim high confidence on day-1 experiments.

---

## 6. The 3 Ps — Vocal/Lead Quality Criteria (O-Ch11)

The producer's vocal quality framework, extended by Easby to any **lead element** (sung
or instrumental) in a loop/variation:

| P | Definition | Easby check |
|---|---|---|
| **Pitch** | In tune AND reliably follows the melody (no scatting around the line) | `pitchConfidence >= 0.7` AND target note hit, not approximated |
| **Pocket** | In time and in the groove | preserves micro-timing of source loop; locks to downbeat for entries, snare on 2/4 for pocket-feel |
| **Passion** | Sells the lyric/melody through performance — emotion the listener believes | velocity/accent shape varies meaningfully across the loop; no flat-velocity robot output |

**Passion can trump pitch and pocket.** A mediocre singer with conviction beats a perfect
singer with no emotion. For Easby: when faced with a choice between (a) a tighter-quantized
variation that loses velocity dynamics and (b) a slightly looser variation with strong
accent contour, prefer (b). Encode this as the per-cell velocity/accent modulation introduced
at ADR-0021 / lm96.

### Pitch failure modes (variations on these)

- **Singing sharp** = can't hear self → headphones too low. Easby analog: source pitch is
  drifting upward over the loop; gate aggressive upward pitch_delta. Cite this if proposing
  a downward correction.
- **Singing flat** = closed embouchure / no relaxation. Easby analog: source is dragging
  pitch downward; cautious about further down-shifts.

---

## 7. Doubling / Stacking — "Change Something" Rule (O-Ch10)

> Using the exact same performance twice (doubling) can sound pretty good, but you soon
> reach the point of diminishing returns unless you **change something** to make it sound
> different.

For Easby's stacked-layer outputs (Stacks/Shuffler mode, multi-slot variations):

- **Identical slots are wasted.** If two slots in the same section play identical pitch
  AND timbre AND timing, the second adds inaudible mass. Diversify ONE of pitch, timbre,
  micro-timing, octave, or formant.
- **Layered take attenuation.** When stacking the same source twice, second copy should
  be `-6 to -10 dB` relative to first to avoid comb-filter buildup. This is the production
  default that's been right since 4-track Beatles.
- **Vocal-stack ambience trick.** Each pass, step back from mic, increase gain to compensate.
  Result: progressively more room ambience without artificial reverb. Easby analog: each
  successive variation slot can use progressively wider stereo image or slightly more wet
  signal in the timbre recipe, simulating "stepping back."
- **Stacking re-voicing trick.** Three-part harmony stack: on pass 2, vocalists swap parts
  (high → low, mid → high, low → mid). Easby analog: when generating 3 harmony variations,
  rotate the voice that owns each interval across slots — don't always put the third on top.

---

## 8. Producer Conduct (O-Ch11)

How Easby presents output to the operator:

- **Open to ideas.** "I haven't tried that before, but I'm really interested to hear what
  it sounds like." NOT "that won't work." When the operator proposes a variation Easby
  hasn't seen before, default response is *try it at amt=1*, not refuse.
- **Specific not vague.** "You're falling behind the beat every time we come out of the
  chorus" beats "do it again." Easby's refusal/critique messages must be specific:
  cite the bar, the slice, the failing gate.
- **Take responsibility.** When a previous Easby suggestion turned out wrong, own it in
  the next session — don't blame the operator or the executor.
- **Stay positive.** Never "this loop sucks." Use: "the loop has the energy; the
  variation can lift its contour." Constructive framing only.

---

## 9. Oblique Strategies — Artistic Block Fallback (O-Ch10)

When the operator says "I'm stuck" and the deeper docs (`06-music-theory.md`, etc.) have
no obvious next step, Easby may emit an Oblique-Strategies-style suggestion. Reference
prompts (Brian Eno / Peter Schmidt, 1975):

- "State the problem in words as clearly as possible."
- "Only one element of each kind." *(direct match to Arrangement Rule §1)*
- "What to increase? What to reduce?" *(direct match to Dynamic Scale §3)*
- "Are there sections? Consider transitions." *(direct match to Build §4)*
- "Honour the error as a hidden intention." *(direct match to "first inspiration wins" §5)*
- "Try faking it!"

These map onto the existing rules above — when emitting an Oblique-Strategies hint, also
cite the underlying rule it implements. `00-producer-mind.md` remains the tiebreaker;
this section is its operational complement.

---

## 10. Preproduction Quality Bar — "The Little Things" (O-Ch7)

The producer's checklist for "is this song ready?" — Easby applies the loop-variation
analog before considering a variation complete:

- [ ] Each slot knows its part inside-out (no random-token output).
- [ ] Starts/stops aligned across slots (no slot starts a beat late).
- [ ] Each slot plays the same part the same way every loop iteration (deterministic seed).
- [ ] Dynamics defined across the loop (velocity contour, not flat).
- [ ] All rhythm slots in the pocket; loop grooves.
- [ ] Turnarounds between sections defined (last bar of section A leads cleanly to bar 1
      of section B).
- [ ] Attacks AND releases aligned across slots.
- [ ] No two slots clash frequency-wise (Arrangement Rule §1).
- [ ] Tempo locked.
- [ ] All pitched slots in tune (key-locked).
- [ ] Lead slot in best range (no overcompression of pitch range).
- [ ] Background/harmony slots defined and tight.

If a variation fails ≥3 of these, refuse the output and ask the operator to clarify which
gate they want relaxed.

---

## 11. Music Troubleshooting Checklist (O-Ch14)

When the operator says "this loop doesn't sound right" but can't name what's wrong, run
this 10-Q diagnostic in order. First failing Q identifies the variation target.

1. **Parts inside-out.** Does every slot in the loop know its part? Random-token output =
   no. → if fail: refuse variation, ask for slot intent first.
2. **Same way every time.** Does each slot play the same part the same way every iteration?
   Jazz/blues exempt (intentional variation). → if fail: increase determinism (lower seed
   variance), not amt.
3. **Plays dynamically.** Does the loop *breathe* volume-wise? Verse less intense than chorus?
   → if fail: emit per-cell velocity/accent modulation (ADR-0021 / lm96).
4. **Holds drive at lower intensity.** When a slot drops volume, does it keep its attacks
   and releases? See §3 "Don't confuse volume with intensity." → if fail: tighten transient
   shaping at quiet sections.
5. **Starts and stops together.** Every slot enters and exits at the same grid point?
   → if fail: snap entries to nearest grid division; refuse if loop has hard pickup.
6. **Tight as a unit.** Builds, turnarounds, accents all played the same way by all slots?
   → if fail: emit unison-accent variation; cite §4 turnarounds rule.
7. **In tune.** All pitched slots key-locked? → if fail: refuse pitch ops; defer to
   `aubio` key detection.
8. **Has groove.** Does the rhythm section play in the pocket? Drummer/bass wavering tempo?
   → if fail: cite §4 pocket types; if source is laid-back, do NOT hard-quantize.
9. **Tempo right.** Try ±1–2 BPM mental check. Too slow → drags; too fast → sloppy.
   → if fail: defer BPM to `AnalysisCoordinator` (out-of-scope for Easby).
10. **Lead in best range.** Is the lead instrument/voice in a comfortable register?
    Out-of-range = strained. → if fail: emit register-shift variation (octave down for
    over-stretched lead).

### Operational use

Easby reports the diagnostic as `{"type": "TroubleshootDiagnostic", "failed_at": <Q#>,
"target": "<one-line fix direction>"}`. The failed-Q index maps to which variation operation
to propose next — i.e. Q3 fail → velocity/accent var; Q6 fail → unison-accent var; Q10
fail → register-shift var.

---

## 12. Mixing Echo (O-Ch14 partial)

The MIXING checklist (O-Ch14) is owned by `easby-mixing`, BUT three items echo principles
Easby-producer enforces upstream — flag these during variation so the mix isn't fighting
the arrangement:

- **Mix focal point.** Every loop should have one clear lead element. If a variation
  creates ambiguous focal point (two equal-loudness leads in same band), refuse.
- **Mix groove preserved.** If the loop's groove relies on a specific slot (e.g. bass
  pocket), variation must not weaken that slot.
- **Dull/uninteresting sounds.** Generic synth patches / predictable presets = mix problem
  rooted in `SoundDesignTarget`. If a `SoundDesignTarget` reads as "default sawtooth, LPF
  half, ADSR med", upgrade to a specific recipe from `02-sound-design-recipes.md` before
  emitting.

---

## Citation Index

| Topic | Owsinski location |
|---|---|
| 5 arrangement elements + 4-element rule | O-Ch5 § Arrangements Are the Key |
| Common song problems (7) | O-Ch5 § Let's Discuss Your Songs |
| Dynamic scale 1–10 by section | O-Ch5 Table 5.1 + O-Ch6 § Dynamics |
| Groove = tension against even time | O-Ch6 § The Groove and the Pocket |
| Pocket types (straight / laid-back / urgent) | O-Ch6 § How to Find the Pocket |
| Attacks and releases as the secret to tight music | O-Ch6 § Attacks and Releases + O-Ch11 § Phrasing |
| Make it better, not just different | O-Ch10 § Make It Better, Not Just Different |
| Two-session experiment rule | O-Ch10 § Time to Experiment |
| Oblique Strategies | O-Ch10 § When Artistic Block Hits |
| 3 Ps — Pitch / Pocket / Passion | O-Ch11 § The Three Ps |
| Doubling diminishing returns / change something | O-Ch10 § Instrument Doubling and Stacking |
| Producer conduct (specific not vague, positive, responsibility) | O-Ch11 § Be a Professional + § Getting the Best out of Musicians |
| "Little things" preproduction checklist | O-Ch7 § It's the Little Things That Count |
| Music troubleshooting 10-Q diagnostic | O-Ch14 § Music Troubleshooting |
| Mixing focal-point / groove / dullness echoes | O-Ch14 § Mixing |

---

## Cross-references — overlap with sibling docs

- **§1 4-element cap** ↔ `00-producer-mind.md` Taste Rule §2 ("Space over density") ·
  `03-composition-methods.md` § Story Curve density column · § Heuristic 3 (final-chorus +1
  ornament — requires `elements_remove` compensation when at cap).
- **§2 Common Song Problems** ↔ `03-composition-methods.md` § Story Curve (Promise / Setup
  / Lift / Payoff functions map to the 7 problems).
- **§3 Dynamic scale 1–10** ↔ `03-composition-methods.md` § Energy Arc (qualitative ↔
  quantitative mapping in this doc) · `00-producer-mind.md` Taste Rule §3 ("Tension/release
  over constant energy").
- **§4 Pocket types** ↔ `08-rhythm-techniques.md` § 6 Rhythmic Feel Rules (Owsinski =
  *where* the beat sits; 08-rhythm = *how* the beat subdivides — orthogonal axes) ·
  `00-producer-mind.md` Taste Rule §1 ("Groove over grid").
- **§4 Groove = tension against even time** ↔ `08-rhythm-techniques.md` § 8 Groove
  Construction Formula (Owsinski = principle; 08 = composition recipe).
- **§5 Make-It-Better gate** ↔ `00-producer-mind.md` § "Should I add this element?"
  (mute-test = post-hoc check; Owsinski's improvement direction = pre-emission gate) ·
  Core Belief "Specific beats generic".
- **§5 First-inspiration-wins** ↔ `00-producer-mind.md` § "Stuck" step 1 ("return to the
  inspiration source").
- **§7 Doubling "change something"** ↔ no sibling overlap; net-new rule.
- **§8 Producer Conduct** ↔ `00-producer-mind.md` § "Should I trust this feedback?"
  (Owsinski = how to *give* feedback; 00-mind = how to *take* feedback).
- **§9 Oblique Strategies** ↔ `00-producer-mind.md` § "Stuck" steps 2–4 (alternative
  framings of the same nudges).
- **§10 Little Things checklist + §11 Troubleshooting** ↔ `00-producer-mind.md` § Quality
  Signals (body-listen complement to checklist).
