# Easby — our skill suite

Five sibling skills sharing one producer-engineer mindset. **[INDEX.md](INDEX.md) is the router** — read it
first to pick a skill; it owns trigger routing, the dir↔skill↔command↔agent name-map, and the handoff contracts.

## Install & repos
This repo (`easby-agent`, private) holds the **skills + commands + agents + KB specs**. It lives at
`~/.claude/skills/easby/` (where Claude Code loads skills). Run **`./setup.sh`** to symlink the suite's commands
(`/produce /mix /master /decomp /easby-programming`) + agent (`easby-programmer`) into `~/.claude/{commands,agents}`
(single source of truth = this repo; originals backed up to `*.pre-easby.bak`).

The **raw RE research** (black-box/FFI/REAPER harnesses, measured data, REF/disasm quarantine) lives in a
**separate private repo `easby-research`** — kept apart by the clean-room firewall (TAINTED material never sits
in a distributable/product repo). The plugin specs here cite it via `Source:` rows.

## Fresh machine — bootstrap
Both repos are **private** → auth GitHub first (`gh auth login`, or add an SSH key).

```bash
# 1. Skills MUST clone to this exact path (Claude Code loads skills from ~/.claude/skills/)
git clone git@github.com:pongsathonkheereekaew/easby-agent.git ~/.claude/skills/easby

# 2. Install the suite's commands + agent (symlinks into ~/.claude)
~/.claude/skills/easby/setup.sh
```
**Done — the music KB + all 5 skills + slash commands work immediately** (pure markdown, no deps).

Optional — only if you'll do plugin reverse-engineering:
```bash
# 3. research workspace (raw harnesses + REF). Path is yours; specs reference it as "private-research/".
git clone git@github.com:pongsathonkheereekaew/easby-research.git ~/easby-research
cd ~/easby-research && python3 -m venv .venv && .venv/bin/pip install pedalboard numpy scipy
# 4. RE tooling: brew install radare2 ghidra ; brew install --cask reaper ; (iLok if DRM plugins)
```
Verify: open Claude Code, type `/mix` (skill loads) and `easby` (router responds).

## Two families
**Music craft** — a 3-stage pipeline (Producer → Mixing → Mastering), each owns one stage and refuses the others:
| Skill (`name:`) | Dir | Command | Owns | Emits |
|---|---|---|---|---|
| `easby-producer` | `easby-producer/` | `/produce` | sound design, loop variation (amt 1–5), music theory, arrangement | `VariationDecision` / `SoundDesignTarget` / `ArrangementDecision` |
| `easby-mixing` | `easby-mixing/` | `/mix` | balance, track/bus EQ, panning, dimension, per-track dynamics, sidechain, automation, bus routing | `MixDecision` / `MixBusDecision` |
| `easby-mastering` | `easby-mastering/` | `/master` | LUFS, stereo-bus glue, final/true-peak limiting, dither, M/S, format prep | `MasterDecision` / `StemMasterDecision` |

**Plugin DSP** — reverse-engineer a binary, then store/implement its DSP:
| Skill (`name:`) | Dir | Command | Agent | Owns |
|---|---|---|---|---|
| `easby-decomp` | `easby-decomp/` | `/decomp` | `easby-programmer` | RE process: black-box system-ID, r2/Ghidra static, FFI harness, **REAPER** host-route (DRM/sidechain), clean-room firewall |
| `easby-programming` | `easby-programming/` | `/easby-programming` | — | KB of researched plugin DSP (formulas, params, FFI); emits `PluginSpec` (internal) / `BuildSpec` (CLEAN-only, product) |

## Usage
- Slash command (explicit stage): `/produce`, `/mix`, `/master`, `/decomp`, `/easby-programming`.
- Or phrase a stage-qualified trigger (see [INDEX.md](INDEX.md)). A bare process word ("EQ this", "compress this")
  spans Mixing+Mastering → the router asks **per-track/bus (Mixing) or stereo master (Mastering)?** before routing.
- Bare "easby" → read INDEX and route.

## Firewall (DSP family)
`easby-programming` is the **only** place that holds disasm-derived **REF**. Product builds (e.g. ES-L) use **CLEAN only**
(black-box measurement + public DSP literature). Gate: `easby-decomp/assets/firewall_check.sh`.

## Per-skill internals
Each skill dir holds `SKILL.md` + `docs/<topic>/` knowledge base + `schemas/*.schema.json` (emitted JSON contracts).
`easby-programming/` also holds `plugins/` (per-plugin specs), `building-blocks/`, `implementation-doctrine.md`.

## Sources (music craft)
Synthesised from 14 books incl. Welsh (synthesis), Curtis Roads (computer music), Martin Russ (synthesis & sampling),
Hutchinson (theory), Kostka/Payne (tonal harmony), Mike Adamo (breakbeat), LMD, Pegada Drum Method.
