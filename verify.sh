#!/usr/bin/env bash
# harness-flow acceptance — Agent Harness only (no AgentMonitor suite)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== harness-flow verify ==="

echo "== layout =="
test -f AGENTS.md
test -d skills
test -d memory
test -f memory/MEMORY.md
test -d standards
test -d scripts
test -x install.sh
test -f docs/AGENT_HARNESS.md
echo "layout: OK"

echo "== shell syntax =="
for f in install.sh backup.sh verify.sh bootstrap.sh scripts/*; do
  [ -f "$f" ] || continue
  case "$f" in
    *.py) continue ;;
  esac
  bash -n "$f"
done
echo "syntax: OK"

echo "== skills =="
count=$(find skills -mindepth 1 -maxdepth 1 ! -name '.*' | wc -l | tr -d ' ')
test "$count" -gt 0
echo "skills: $count"

echo "== memory =="
mcount=$(find memory -mindepth 1 -maxdepth 1 -name '*.md' ! -name '.*' | wc -l | tr -d ' ')
test "$mcount" -gt 0
echo "memory: $mcount md"

echo "== project wiki template (optional) =="
if [ -f templates/project-wiki/init-wiki.sh ]; then
  bash -n templates/project-wiki/init-wiki.sh
  echo "project-wiki template: OK"
fi

echo "== bootstrap / install-and-go =="
test -x bootstrap.sh
test -f adapters/CLAUDE.md
test -f adapters/claude-settings.defaults.json
test -f scripts/merge-claude-settings.py
python3 -c "import ast, pathlib; ast.parse(pathlib.Path('scripts/merge-claude-settings.py').read_text())"
grep -q 'harness update' scripts/harness
echo "bootstrap assets: OK"

echo "== capability manifest =="
test -f config/hosts.yaml
test -f schemas/host-capability.schema.json
test -f config/skills.yaml
test -d scripts/lib
test -d scripts/adapters
test -f scripts/harness_host.py
test -f scripts/harness_skill.py
# manifest validates against its schema (pyyaml + jsonschema required)
if python3 -c "import yaml, jsonschema" 2>/dev/null; then
  python3 - <<'PY'
import json, pathlib, yaml, jsonschema
root = pathlib.Path(".")
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

echo "== contract tests =="
if python3 -c "import pytest, yaml, jsonschema" 2>/dev/null; then
  python3 -m pytest tests/contracts/ -q
  echo "contracts: OK"
else
  echo "contracts: SKIP (pip install -r requirements-dev.txt)"
fi

echo "== policy invariants =="
# F1 regression guard: no fictional Mode enum in guardrails (hosts have no Mode type)
if grep -q 'discuss.*plan.*interactive.*auto' standards/agent-guardrails.md; then
  echo "FAIL: agent-guardrails.md still ships a Mode enum" >&2; exit 1
fi
# F2 regression guard: always-on risk spine present in AGENTS.md
grep -q '## Risk spine' AGENTS.md
# F4 regression guard: no false 'fail loudly' claim (no parser exists)
if grep -q 'fail loudly' standards/persona-manifest.md; then
  echo "FAIL: persona-manifest.md claims 'fail loudly' with no parser" >&2; exit 1
fi
# F5 regression guard: worker ceiling framed as RiskClass, not Mode
grep -q 'Worker ceiling' skills/orchestrating-workers/SKILL.md
# standards/*.md start with H1 (no broken frontmatter drift)
for f in standards/*.md; do
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
echo "harness-flow verify: PASS"
echo "On a machine after install, also run: harness doctor"

