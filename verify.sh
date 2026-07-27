#!/usr/bin/env bash
# Codinal product acceptance — harness, Python runtime, and macOS desktop shell
# Codinal layout: harness content under harness/, product at root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
HARNESS="$ROOT/harness"
PYTHON_BIN=python3
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
fi
cd "$ROOT"

echo "=== Codinal verify ==="

echo "== layout =="
test -f "$HARNESS/AGENTS.md"
test -d "$HARNESS/skills"
test -d "$HARNESS/memory"
test -f "$HARNESS/memory/MEMORY.md"
test -d "$HARNESS/standards"
test -d "$HARNESS/scripts"
test -x install.sh
test -f docs/AGENT_HARNESS.md
echo "layout: OK"

echo "== shell syntax =="
for f in install.sh backup.sh verify.sh bootstrap.sh "$HARNESS"/scripts/*; do
  [ -f "$f" ] || continue
  case "$f" in
    *.py) continue ;;
  esac
  bash -n "$f"
done
echo "syntax: OK"

echo "== skills =="
count=$(find "$HARNESS/skills" -mindepth 1 -maxdepth 1 ! -name '.*' | wc -l | tr -d ' ')
test "$count" -gt 0
echo "skills: $count"

echo "== memory =="
mcount=$(find "$HARNESS/memory" -mindepth 1 -maxdepth 1 -name '*.md' ! -name '.*' | wc -l | tr -d ' ')
test "$mcount" -gt 0
echo "memory: $mcount md"

echo "== project wiki template (optional) =="
if [ -f "$HARNESS/templates/project-wiki/init-wiki.sh" ]; then
  bash -n "$HARNESS/templates/project-wiki/init-wiki.sh"
  echo "project-wiki template: OK"
fi

echo "== bootstrap / install-and-go =="
test -x bootstrap.sh
test -f "$HARNESS/adapters/CLAUDE.md"
test -f "$HARNESS/adapters/claude-settings.defaults.json"
test -f "$HARNESS/scripts/merge-claude-settings.py"
"$PYTHON_BIN" -c "import ast, pathlib; ast.parse(pathlib.Path('$HARNESS/scripts/merge-claude-settings.py').read_text())"
grep -q 'harness update' "$HARNESS/scripts/harness"
echo "bootstrap assets: OK"

echo "== capability manifest =="
test -f "$HARNESS/config/hosts.yaml"
test -f "$HARNESS/schemas/host-capability.schema.json"
test -f "$HARNESS/config/skills.yaml"
test -d "$HARNESS/scripts/lib"
test -d "$HARNESS/scripts/adapters"
test -f "$HARNESS/scripts/harness_host.py"
test -f "$HARNESS/scripts/harness_skill.py"
# manifest validates against its schema (pyyaml + jsonschema required)
if "$PYTHON_BIN" -c "import yaml, jsonschema" 2>/dev/null; then
  HARNESS_PATH="$HARNESS" "$PYTHON_BIN" - <<'PY'
import json, pathlib, os, yaml, jsonschema
root = pathlib.Path(os.environ["HARNESS_PATH"])
m = yaml.safe_load((root/"config/hosts.yaml").read_text())
s = json.loads((root/"schemas/host-capability.schema.json").read_text())
jsonschema.validate(m, s)
assert m["hosts"]["opencode"]["tier"] == 1
assert "core" in yaml.safe_load((root/"config/skills.yaml").read_text())
PY
  echo "manifest: OK"
else
  echo "manifest: SKIP (pyyaml/jsonschema not installed; pip install -r requirements-dev.txt)"
fi

echo "== product tests =="
if ! "$PYTHON_BIN" -c "import fastapi, httpx, pytest, uvicorn, yaml, jsonschema" 2>/dev/null; then
  echo "FAIL: test dependencies missing; install requirements-dev.txt" >&2
  exit 1
fi
"$PYTHON_BIN" -X faulthandler -m pytest -q \
  --timeout=90 --timeout-method=thread \
  -p no:cacheprovider
echo "product tests: OK"

echo "== desktop shell (macOS) =="
if [ "$(uname -s)" = "Darwin" ] && command -v cargo >/dev/null 2>&1; then
  cargo fmt --manifest-path desktop/src-tauri/Cargo.toml -- --check
  cargo clippy --manifest-path desktop/src-tauri/Cargo.toml --all-targets -- -D warnings
  cargo test --manifest-path desktop/src-tauri/Cargo.toml
  echo "desktop shell: OK"
else
  echo "desktop shell: SKIP (macOS Rust gate runs in CI)"
fi

echo "== policy invariants =="
# F1 regression guard: no fictional Mode enum in guardrails (hosts have no Mode type)
if grep -q 'discuss.*plan.*interactive.*auto' "$HARNESS/standards/agent-guardrails.md"; then
  echo "FAIL: agent-guardrails.md still ships a Mode enum" >&2; exit 1
fi
# F2 regression guard: always-on risk spine present in AGENTS.md
grep -q '## Risk spine' "$HARNESS/AGENTS.md"
# F4 regression guard: no false 'fail loudly' claim (no parser exists)
if grep -q 'fail loudly' "$HARNESS/standards/persona-manifest.md"; then
  echo "FAIL: persona-manifest.md claims 'fail loudly' with no parser" >&2; exit 1
fi
# F5 regression guard: worker ceiling framed as RiskClass, not Mode
grep -q 'Worker ceiling' "$HARNESS/skills/orchestrating-workers/SKILL.md"
# standards/*.md start with H1 (no broken frontmatter drift)
for f in "$HARNESS"/standards/*.md; do
  head -1 "$f" | grep -q '^# ' || { echo "FAIL: $f does not start with H1" >&2; exit 1; }
done
echo "policy invariants: OK"

echo "== host install (skip on CI) =="
if [ -d ~/.agents ]; then
  # SSOT integrity: at least one symlink adapter under ~/.agents/skills is a live symlink
  found_link=0
  for d in ~/.agents/skills/*/; do
    [ -L "${d%/}" ] && { found_link=1; break; }
  done
  [ "$found_link" -eq 1 ] && echo "symlink adapter: OK" || echo "symlink adapter: none (ok if direct install)"
else
  echo "host install: skip (no ~/.agents — CI environment)"
fi

echo ""
echo "Codinal verify: PASS"
echo "On a machine after install, also run: harness doctor"
