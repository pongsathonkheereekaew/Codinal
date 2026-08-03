from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.perf

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "measure_runtime_startup.py"


def test_native_runtime_benchmark_uses_read_only_isolated_processes() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")

    assert '"CODINAL_SESSION_TOKEN"' in source
    assert '"CODINAL_DATA_DIR"' in source
    assert '"CODINAL_EXPERIMENTAL_EXECUTION"' in source
    assert '"CODINAL_PARENT_PID"' in source
    assert '"CODINAL_SECRET_BOOTSTRAP"' in source
    assert "start_new_session=True" in source
    assert "os.killpg(process.pid, signal.SIGTERM)" in source
