#!/usr/bin/env bash
# Deprecated path — delegates to repo-root install.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "NOTE: templates/agents-harness/install.sh delegates to $ROOT/install.sh"
exec bash "$ROOT/install.sh"
