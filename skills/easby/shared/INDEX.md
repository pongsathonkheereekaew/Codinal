# shared/INDEX — the ONE music knowledge base (every easby agent loads this)

> **→ Read [principles.md](principles.md) FIRST** — the concentrated core (mindset, universal laws,
> ways-of-thinking; every branch in ~3 pages). It's the north-star cheat-sheet; this INDEX is the deep-retrieval
> router behind it. Principles first, then load the matching deep doc on demand.

> 🧭 **ALWAYS load [principles.md](principles.md) first** — the concentrated core (mindset + principles + ways
> of thinking, every branch). This INDEX is the deep router; principles is the north star. Load deep docs on demand.

**Architecture (2026-06-22):** there is a **single shared music knowledge base — all angles**. Every easby
agent has the **same full access**: Producer, Mixing, Mastering, *and* the Programmer side. The skills do **not**
differ in *what they know* — only in **purpose / lens**:

| Agent | Purpose lens | Also knows |
|---|---|---|
| easby-producer | **create** — sound identity, variation, arrangement | music KB (full) |
| easby-mixing | **balance** — track relationships, space | music KB (full) |
| easby-mastering | **finalize** — loudness, translation, format | music KB (full) |
| easby-decomp + easby-programming | **engineer** — RE + clone plugin DSP | music KB (full) **+ code/DSP** (the ONLY side with both) |

Same knowledge, tiny diff in purpose. A music question is answered from this one KB; the lens only changes
*which decision/JSON* the agent emits. **Programmer is the superset** (music + code/DSP); music skills are music-only.

## Each lens — purpose, intent, and when to cross
Same KB; the lens sets **default intent + altitude**, not a wall. Read the situation and **borrow another
lens's method when it serves** — your **output contract** (your JSON schema) and altitude stay yours; the
**method** can flex.

- **Producer (create)** — notice/protect the idea, delete the rest; specific brief over generic; groove>grid,
  space>density, tension/release; "finished is a decision, not a state." Altitude = the *sound's identity*.
- **Mixing (balance)** — serve the song: set direction, develop the groove, **emphasize the most-important
  element**, build *bigger-than-life* with tension/release; mono-check; fix at source. Altitude = *track relationships*.
- **Mastering (finalize)** — art of compromise: **fewest moves, every move trades off**; tonal-balance reference
  (symphonic), translation across systems, "do less," "the most transparent limiter is none." Altitude = the *finished stereo file*.
- **Programmer (engineer)** — recover/clone DSP; reads the music KB to understand a plugin's *musical* intent.

### Crossing — same method, borrowed intent (allowed + expected when the situation calls)
- **Creative mixing** — a mix that *transforms*, not just balances: production methods inside the mix
  (resampling, saturation as tone-design, FX-as-instrument, arrangement edits, bus reverb as a creative space).
  → **Mixing lens + Producer methods**; still emits a Mix decision.
- **Mix-bus / pre-master moves** — gentle master-style glue/tone on the bus to audition the destination →
  **Mixing borrows Mastering methods** (≤3 dB, safety only; full loudness still → Mastering).
- **Sound-design via mix tools** — EQ/comp/reverb/sidechain used as *instruments* to invent timbre, not balance →
  **Producer borrows Mixing methods**.
- **Mastering that can't fix without collateral** → kick back to Mixing (don't force it; Katz's rule).

**Rule:** default to your lens; borrow a method when the goal needs it; **never change your output contract or
altitude.** "Be creative with the mix" → creative-mixing mode (Mixing lens, Producer methods).

## The KB by angle (canonical source — load on demand; all SHARED)
Technique = shared cores (here). Deep craft areas keep their tuned sub-routers (load the sub-INDEX first).

| Angle | Canonical source | Kind |
|---|---|---|
| **Saturation / distortion** | [saturation.md](saturation.md) | shared core |
| **EQ / filtering** | [eq-filtering.md](eq-filtering.md) (+ app: ../easby-mixing/docs/mixing/02-eq.md, ../easby-mastering/docs/mastering/01-eq.md) | shared core + stage app |
| **Dynamics** (comp/limit/gate/exp) | [dynamics.md](dynamics.md) (+ app: ../easby-mixing/docs/mixing/04-dynamics.md, ../easby-mastering/docs/mastering/{02-dynamics,03-compression,04-limiting}.md) | shared core + stage app |
| **Troubleshooting** | [troubleshooting.md](troubleshooting.md) | shared core |
| **Synthesis / sound design** | ../easby-producer/docs/easby/{01-synthesis-engine,02-sound-design-recipes}.md | shared |
| **Music theory / harmony** | ../easby-producer/docs/easby/06-music-theory.md → sub-router 06a–06f | shared (sub-router) |
| **Composition / arrangement / development** | ../easby-producer/docs/easby/{03-composition-methods,03a-development-methods,03c-arrangement-arc,03d-genre-templates}.md | shared |
| **Rhythm / drums / beats** | ../easby-producer/docs/easby/{08-rhythm-techniques,07-famous-drum-beats,03b-drum-patterns}.md → 07a/07b | shared (sub-router) |
| **Recording / production craft / vocal** | ../easby-producer/docs/easby/{04-recording-production,03e-vocal-tuning,11-owsinski-producer-handbook,09-pro-tools-daw-reference}.md | shared |
| **Imaging / stereo / dimension** | ../easby-mixing/docs/mixing/{01-imaging-balance,03-dimension}.md, ../easby-mastering/docs/mastering/08-mid-side.md | shared |
| **Sidechain / bus routing / automation** | ../easby-mixing/docs/mixing/{06-sidechain,07-bus-routing,08-automation}.md | shared |
| **Loudness / metering / dither / format** | ../easby-mastering/docs/mastering/{06-monitoring-metering,07-dither,09-noise-reduction,10-pre-master-checks,11-stem-mastering,12-vinyl,13-atmos,14-apple-digital-masters}.md | shared |
| **Workflow / genre** | ../easby-mixing/docs/mixing/{09-workflow,10-genre-mixing}.md, ../easby-producer/docs/easby/03d-genre-templates.md | shared |
| **DSP primitives (impl)** | ../easby-programming/building-blocks/README.md | shared (impl) |
| **Plugin capabilities** (what each plugin does + every control + musical use) | [plugins/](plugins/README.md) (capability cards distilled from manuals) | **shared — every agent** |
| **Plugin deep DSP** (gain law / FFI / internals / REF) | ../easby-programming/plugins/ | **Programmer only** |

Full deep routers (read first for theory/drums/synthesis depth): `../easby-producer/docs/easby/INDEX.md`,
`../easby-mixing/docs/mixing/INDEX.md`, `../easby-mastering/docs/mastering/INDEX.md`.

## Per-lens files (the ONLY non-shared bit — the purpose itself)
Each music skill keeps just its **lens**: `00-<stage>-mind.md` (taste/priorities) + `05-quick-decisions.md`
(hot-path for that purpose). These encode *how that purpose weighs the same knowledge* — not new knowledge.
- create → `../easby-producer/docs/easby/{00-producer-mind,05-quick-decisions}.md`
- balance → `../easby-mixing/docs/mixing/{00-mixing-mind,05-quick-decisions}.md`
- finalize → `../easby-mastering/docs/mastering/{00-mastering-mind,05-quick-decisions}.md`

## Firewall (unchanged)
Music KB is CLEAN/public. Disasm-derived **REF** stays only in easby-programming and never enters a product.
Programmer may pull plugin **CLEAN** specs as emulation targets (cross-family handoff).
