#!/usr/bin/env bash
# Generate ~/.cursor/rules/*.mdc from ~/.agents/standards body + cursor.meta.yaml
set -euo pipefail

AGENTS_HOME="${AGENTS_HOME:-$HOME/.agents}"
STANDARDS="$AGENTS_HOME/standards"
META="$STANDARDS/cursor.meta.yaml"
OUT_DIR="${CURSOR_RULES_DIR:-$HOME/.cursor/rules}"

python3 - "$STANDARDS" "$META" "$OUT_DIR" <<'PY'
import sys, os, re
from pathlib import Path

standards, meta_path, out_dir = map(Path, sys.argv[1:])
out_dir.mkdir(parents=True, exist_ok=True)

# Minimal YAML subset parser for our meta format (no PyYAML dependency).
text = meta_path.read_text(encoding="utf-8")
entries = {}
current = None
for raw in text.splitlines():
    line = raw.rstrip()
    if not line or line.lstrip().startswith("#"):
        continue
    if re.match(r"^[A-Za-z0-9_-]+:\s*$", line):
        current = line[:-1].strip()
        entries[current] = {}
        continue
    if current is None:
        continue
    m = re.match(r"^\s+([A-Za-z0-9_]+):\s*(.*)$", line)
    if not m:
        continue
    key, val = m.group(1), m.group(2).strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1]
    elif val.lower() in ("true", "false"):
        val = val.lower() == "true"
    entries[current][key] = val

for key, cfg in entries.items():
    body_name = cfg.get("body", f"{key}.md")
    body_path = standards / body_name
    if not body_path.is_file():
        raise SystemExit(f"missing body: {body_path}")
    out_name = cfg.get("out", f"{key}.mdc")
    description = cfg.get("description", key)
    always_apply = cfg.get("alwaysApply", False)
    globs = cfg.get("globs")

    fm = ["---", f"description: {description}"]
    if globs is not None and globs != "":
        # Preserve quoting if globs contain spaces/special chars
        if not (str(globs).startswith('"') or " " in str(globs) or "*" in str(globs)):
            fm.append(f"globs: {globs}")
        else:
            g = str(globs).strip('"')
            fm.append(f'globs: "{g}"')
    fm.append(f"alwaysApply: {'true' if always_apply else 'false'}")
    fm.append("---")
    fm.append("")

    body = body_path.read_text(encoding="utf-8").lstrip("\n")
    if not body.endswith("\n"):
        body += "\n"

    header = (
        "<!-- GENERATED from ~/.agents/standards — do not edit by hand.\n"
        f"     Source body: {body_name} | meta key: {key}\n"
        "     Regenerate: ~/.agents/scripts/gen-cursor-rules.sh -->\n"
    )
    out_path = out_dir / out_name
    out_path.write_text(header + "\n".join(fm) + "\n" + body, encoding="utf-8")
    print(f"wrote {out_path}")
PY
