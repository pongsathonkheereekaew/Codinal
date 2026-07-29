from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


pytestmark = pytest.mark.perf

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "measure_desktop_startup.py"
_SPEC = importlib.util.spec_from_file_location("measure_desktop_startup", _SCRIPT)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_listener_port_requires_loopback_listener() -> None:
    assert _MODULE._listener_port("python3 42 user TCP 127.0.0.1:61234 (LISTEN)") == 61234
    assert _MODULE._listener_port("python3 42 user TCP *:61234 (LISTEN)") is None


def test_samples_own_their_process_group() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")

    assert "started = time.perf_counter()\n    process = subprocess.Popen(" in source
    assert "start_new_session=True" in source
    assert "os.killpg(process.pid, signal.SIGTERM)" in source
    assert "def _owned_sidecar_is_running" in source
    assert "os.kill(child_pid, signal.SIGKILL)" in source
