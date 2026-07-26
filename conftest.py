"""Repo-root pytest conftest.

Presence at repo root makes pytest put the repo root on sys.path, so the
``runtime`` package (Codinal Python sidecar) and ``harness`` content are
importable from tests. Per-package fixtures live under tests/<area>/.
"""

import faulthandler

# Dump ALL thread tracebacks to stderr every 80s. pytest-timeout (thread
# method) only reports the main thread; on a hung worker thread that is not
# enough to diagnose. This periodic dump surfaces the actually-blocked thread
# (e.g. a subprocess.communicate / selector.poll in a turn worker) so CI
# failures name the real culprit. No-op on fast runs (timer cancelled below).
_dump = faulthandler.dump_traceback_later(80, exit=False)


def pytest_unconfigure(config):
    try:
        _dump.cancel()
    except Exception:
        pass
