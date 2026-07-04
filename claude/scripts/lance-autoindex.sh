#!/usr/bin/env bash
# lance-search: auto-index repo on session start (first time only, then skip).
# Safe: never fails the session. Runs async from settings.json.
set -u
root="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$root" ] || exit 0
VENV="$HOME/.claude/lance-search/.venv/bin/python"
[ -x "$VENV" ] || exit 0

"$VENV" - "$root" <<'PY' 2>/dev/null
import sys, pathlib
home = pathlib.Path.home()
sys.path.insert(0, str(home / ".claude" / "lance-search"))
root = pathlib.Path(sys.argv[1])
name = root.name
store = home / ".claude" / "lance-search" / "lance"
try:
    import lancedb
    db = lancedb.connect(str(store))
    if name in db.table_names():
        sys.exit(0)  # already indexed — skip
except Exception:
    pass
try:
    import server
    server.lance_index(str(root))
except Exception:
    pass
PY
exit 0
