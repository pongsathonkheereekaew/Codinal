#!/usr/bin/env bash
# Sync ~/.agents/skills into tool adapter dirs via relative symlinks.
# Install skills ONLY into ~/.agents/skills, then run this script.
#
# Native readers of ~/.agents/skills (no per-skill sync required, but safe):
#   Gemini CLI, Codex (user scope), OpenCode
# Hermes: skills.external_dirs in ~/.hermes/config.yaml (do not symlink tree here)
# Symlink adapters (this script):
#   Claude, Cursor, Openclaw, Gemini ~/.gemini/skills, ZCode ~/.zcode/skills
# Policy files:
#   AGENTS.md / GEMINI.md wired for Codex, ZCode, OpenCode, Gemini
set -euo pipefail

AGENTS_HOME="${AGENTS_HOME:-$HOME/.agents}"
SKILLS_SRC="$AGENTS_HOME/skills"
POLICY="$AGENTS_HOME/AGENTS.md"
COMMANDS_SRC="$AGENTS_HOME/commands"

TARGETS=(
  "$HOME/.claude/skills"
  "$HOME/.openclaw/skills"
  "$HOME/.cursor/skills"
  "$HOME/.gemini/skills"
  "$HOME/.zcode/skills"
)

# Codex: modern builds read ~/.agents/skills natively and may skip symlinks
# under ~/.codex/skills — we only wire AGENTS.md there (see wire_policy_files).

log() { printf '%s\n' "$*"; }

rel_link() {
  local target="$1" linkpath="$2"
  local linkdir
  linkdir="$(dirname "$linkpath")"
  python3 - "$target" "$linkdir" <<'PY'
import os, sys
target, linkdir = sys.argv[1], sys.argv[2]
print(os.path.relpath(target, start=linkdir))
PY
}

ensure_dir() {
  mkdir -p "$1"
}

link_skill() {
  local name="$1"
  local src="$SKILLS_SRC/$name"
  local dest_root="$2"
  local dest="$dest_root/$name"

  if [[ ! -e "$src" ]]; then
    log "skip missing source: $name"
    return 0
  fi

  if [[ -L "$dest" ]]; then
    local current expected
    current="$(readlink "$dest")"
    expected="$(rel_link "$src" "$dest")"
    if [[ "$current" == "$expected" ]]; then
      return 0
    fi
    rm -f "$dest"
  elif [[ -e "$dest" ]]; then
    log "WARN: refusing to replace non-symlink $dest (move it into $SKILLS_SRC first)"
    return 1
  fi

  local rel
  rel="$(rel_link "$src" "$dest")"
  ln -s "$rel" "$dest"
  log "linked $dest -> $rel"
}

NESTED_ALIASES=(
  "nuiny=insurance/nuiny"
  "insurance-commission=insurance/insurance-commission"
  "insurance-premium-finding=insurance/insurance-premium-finding"
  "easby-mastering=easby/easby-mastering"
  "easby-mixing=easby/easby-mixing"
  "easby-producer=easby/easby-producer"
  "easby-programming=easby/easby-programming"
  "easby-decomp=easby/easby-decomp"
)

link_nested() {
  local dest_root="$1"
  local entry alias relsrc src dest expected current rel
  for entry in "${NESTED_ALIASES[@]}"; do
    alias="${entry%%=*}"
    relsrc="${entry#*=}"
    src="$SKILLS_SRC/$relsrc"
    dest="$dest_root/$alias"
    [[ -e "$src" ]] || continue
    if [[ -L "$dest" ]]; then
      current="$(readlink "$dest")"
      expected="$(rel_link "$src" "$dest")"
      if [[ "$current" == "$expected" ]]; then
        continue
      fi
      rm -f "$dest"
    elif [[ -e "$dest" ]]; then
      log "WARN: refusing nested alias non-symlink $dest"
      continue
    fi
    rel="$(rel_link "$src" "$dest")"
    ln -s "$rel" "$dest"
    log "linked nested $dest -> $rel"
  done
}

prune_orphans() {
  local dest_root="$1"
  local allowed=" "
  local name entry alias dest
  for name in "$SKILLS_SRC"/*; do
    [[ -e "$name" ]] || continue
    allowed+="$(basename "$name") "
  done
  for entry in "${NESTED_ALIASES[@]}"; do
    alias="${entry%%=*}"
    allowed+="$alias "
  done
  for dest in "$dest_root"/*; do
    [[ -e "$dest" || -L "$dest" ]] || continue
    name="$(basename "$dest")"
    [[ "$name" == .* ]] && continue
    if [[ "$allowed" != *" $name "* ]]; then
      if [[ -L "$dest" ]]; then
        rm -f "$dest"
        log "pruned orphan link $dest"
      else
        log "WARN: orphan non-symlink left untouched: $dest"
      fi
    fi
  done
}

wire_policy_link() {
  local dest="$1"
  ensure_dir "$(dirname "$dest")"
  if [[ -L "$dest" ]]; then
    local current expected
    current="$(readlink "$dest")"
    expected="$(rel_link "$POLICY" "$dest")"
    if [[ "$current" == "$expected" ]]; then
      return 0
    fi
    rm -f "$dest"
  elif [[ -e "$dest" ]]; then
    log "WARN: refusing to replace non-symlink policy $dest"
    return 0
  fi
  local rel
  rel="$(rel_link "$POLICY" "$dest")"
  ln -s "$rel" "$dest"
  log "policy $dest -> $rel"
}

wire_commands_dir() {
  local dest="$1"
  [[ -d "$COMMANDS_SRC" ]] || return 0
  ensure_dir "$(dirname "$dest")"
  if [[ -L "$dest" ]]; then
    local current expected
    current="$(readlink "$dest")"
    expected="$(rel_link "$COMMANDS_SRC" "$dest")"
    if [[ "$current" == "$expected" ]]; then
      return 0
    fi
    rm -f "$dest"
  elif [[ -e "$dest" ]]; then
    log "WARN: refusing to replace non-symlink commands dir $dest"
    return 0
  fi
  local rel
  rel="$(rel_link "$COMMANDS_SRC" "$dest")"
  ln -s "$rel" "$dest"
  log "commands $dest -> $rel"
}

wire_policy_files() {
  log "== wire policy / commands =="
  [[ -f "$POLICY" ]] || { log "error: missing $POLICY"; return 1; }

  # Tools that read AGENTS.md (or GEMINI.md) at these paths
  wire_policy_link "$HOME/.codex/AGENTS.md"
  wire_policy_link "$HOME/.zcode/AGENTS.md"
  wire_policy_link "$HOME/.config/opencode/AGENTS.md"
  wire_policy_link "$HOME/.gemini/GEMINI.md"

  # Claude already has CLAUDE.md adapter (@AGENTS.md); keep commands wired
  wire_commands_dir "$HOME/.claude/commands"
  wire_commands_dir "$HOME/.cursor/commands"
  wire_commands_dir "$HOME/.zcode/commands"
}

main() {
  if [[ ! -d "$SKILLS_SRC" ]]; then
    log "error: skills source missing: $SKILLS_SRC"
    exit 1
  fi

  local target name failures=0
  for target in "${TARGETS[@]}"; do
    ensure_dir "$target"
    log "== sync -> $target =="
    for name in "$SKILLS_SRC"/*; do
      [[ -e "$name" ]] || continue
      base="$(basename "$name")"
      [[ "$base" == .* ]] && continue
      if ! link_skill "$base" "$target"; then
        failures=$((failures + 1))
      fi
    done
    link_nested "$target"
    prune_orphans "$target"
  done

  wire_policy_files

  if [[ "$failures" -gt 0 ]]; then
    log "done with $failures warning(s)"
    exit 1
  fi
  log "done"
  log "note: Codex + Gemini + OpenCode also read ~/.agents/skills natively"
}

main "$@"
