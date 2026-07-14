# MANIFEST — external dependencies

**Live SSOT for portable skills & policy:** `~/.agents/` (Agent Harness).  
**This repo:** bootstrap + personal Claude/Hermes packs + shareable templates.

| Layer | Location |
|-------|----------|
| Lingua franca + shared skills | `~/.agents/AGENTS.md`, `~/.agents/skills/` |
| Portable starter for others | `templates/agents-harness/` |
| Personal Claude packs (IP) | `claude/` in this repo → install via `./install.sh` |
| Hermes identity / mission | `hermes/` + live `~/.hermes/SOUL.md` |

> Old standalone repo `claude-skills` is **deprecated**. Prefer `~/.agents` + `templates/agents-harness/`, and `./install.sh` for personal Claude glue.

`install.sh` → `scripts/install-claude.sh` copies `claude/` into `~/.claude` and installs external packs. After that, keep new skills in `~/.agents/skills` and run `harness sync`.

## 1. CLIs + apps (Homebrew)

```bash
brew install jq node            # jq = hooks; node = claude-mem runtime
brew install rtk lowfat         # token compressors (rtk-ai). If tap needed: brew tap rtk-ai/tap
brew install --cask obsidian    # optional — graph view over ~/.claude/projects/-/memory
npm i -g skills                 # skills.sh CLI for third-party packs
```

- **rtk** + **lowfat** power the `PreToolUse` Bash hook (`scripts/lowfat-rtk-router.sh`).
  ⚠ If they are NOT on `PATH`, that hook errors on every Bash call — install them first, or delete the `PreToolUse` block from `~/.claude/settings.json`.

## 2. Plugins

`settings.json` already lists the marketplaces + enabled plugins. Launch `claude` and run:

```text
/plugin marketplace add forrestchang/andrej-karpathy-skills
/plugin marketplace add JuliusBrussee/caveman
/plugin marketplace add thedotmack/claude-mem
/plugin marketplace add affaan-m/everything-claude-code

/plugin install superpowers@claude-plugins-official
/plugin install clangd-lsp@claude-plugins-official
/plugin install caveman@caveman
/plugin install claude-mem@thedotmack
/plugin install andrej-karpathy-skills@karpathy-skills
/plugin install ecc@ecc
```

## 3. Skills layout

| Location | What |
|---|---|
| `claude/skills/` (this repo) | **Personal / bundled** — easby, graphify, insurance/nuiny, prompt-master, visual-plan, macos-design, ui-ux-pro-max, agents-sdk, scrutinize, … |
| `~/.agents/skills/` | **Third-party** — mattpocock, google, caveman (via `skills add`) |
| `~/.claude/skills/` | Runtime merge: personal copy + symlinks to `~/.agents/skills/` |

Personal skills are your IP → **keep this repo PRIVATE.**

## 4. External packs (auto via install.sh)

```bash
skills add mattpocock/skills -g -y --all -a claude-code
skills add google/skills -g -y --all -a claude-code
skills add JuliusBrussee/caveman -g -y -s caveman -a claude-code
```

Then run `/setup-matt-pocock-skills` once in Claude/Cursor.

## Verify after install

```bash
bash install.sh
bash ./verify.sh
rtk --version && lowfat --version && jq --version
ls ~/.claude/{CLAUDE.md,settings.json,scripts,commands,templates}
ls ~/.claude/skills/{easby,graphify,nuiny,handoff}
ls ~/.claude/projects/-/memory
```

## Agents index

`agents-keep.txt` ที่ repo root = รายชื่อ agents ที่ใช้งานจริง (ที่เหลือใน `claude/agents/` เป็น optional packs)
