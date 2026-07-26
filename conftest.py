"""Repo-root pytest conftest.

Presence at repo root makes pytest put the repo root on sys.path, so the
``runtime`` package (Codinal Python sidecar) and ``harness`` content are
importable from tests. Per-package fixtures live under tests/<area>/.
"""

import os

import faulthandler
import pytest

# Sandbox/integration tests that spawn real subprocesses (sandbox-exec
# seatbelt, isolated pdf_worker over the embedded-Python bundle, git worktree
# lifecycle, crash-recovery workers) pass on a developer macOS host but hang
# or fail on CI runners: Linux lacks sandbox-exec entirely; macOS CI runners
# restrict the seatbelt/entitlement environment and the embedded bundle is
# absent. Skip them in the CI unit lane; they run in full locally and in the
# release smoke lane.
skip_on_ci = pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason=(
        "sandbox/integration test spawns OS subprocesses that need a real "
        "macOS host; skipped on CI runners (run locally or in the release "
        "smoke lane)"
    ),
)

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
