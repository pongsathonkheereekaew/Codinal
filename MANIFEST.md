# MANIFEST — external dependencies

`install.sh` copies all files into `~/.claude`. These extras must be installed by hand (one-time).

## 1. CLIs + apps (Homebrew)

```bash
brew install jq node            # jq = hooks; node = claude-mem runtime
brew install rtk lowfat         # token compressors (rtk-ai). If tap needed: brew tap rtk-ai/tap
brew install --cask obsidian    # optional — graph view over ~/.claude/projects/-/memory
```

- **rtk** `0.38.0` + **lowfat** `0.6.8` power the `PreToolUse` Bash hook (`scripts/lowfat-rtk-router.sh`).
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

Deliberately NOT installed (disabled in the consolidation): `claude-code-harness`, `claudeclaw`.

## 3. Skills (bundled — no action)

`claude/skills/` is copied to `~/.claude/skills/` by the installer. Includes the design skills the router uses (**ui-ux-pro-max**, **macos-design**), the Cloudflare pack, and personal skills (insurance, nuiny, graphify, easby, prompt-master, visual-plan).

> Some are third-party (Cloudflare pack, ui-ux-pro-max). Personal skills are your IP → **keep this repo PRIVATE.**

## 4. matt pocock skills (optional)

`to-prd`, `to-issues`, `handoff`, `zoom-out`, `triage`, `prototype` live in `~/.agents/skills/` (symlinked into `~/.claude/skills/`). Reinstall via their setup skill if you want them:

```text
# in claude: run the setup-matt-pocock-skills skill, or:
npx @mattpocock/skills install
```

## Verify after install

```bash
rtk --version && lowfat --version && jq --version
ls ~/.claude/{CLAUDE.md,settings.json,scripts,commands,templates}
ls ~/.claude/projects/-/memory
# launch claude → claude-mem should auto-recall; routing in CLAUDE.md active
```
