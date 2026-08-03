#!/usr/bin/env python3
"""Measure macOS desktop launch through the bundled Rust runtime listener.

The metric starts at the packaged Codinal executable and stops when its
freshly spawned native Rust runtime binds a loopback TCP port.  It deliberately
does *not* call an authenticated endpoint or claim that GPUI first paint or
first-model-token latency has completed; those need separate probes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.perf.measurement import summarize_samples

DEFAULT_APP = Path("/Applications/Codinal.app/Contents/MacOS/codinal")
_LISTENER = re.compile(r"127\.0\.0\.1:(\d+) \(LISTEN\)")


def _listener_port(output: str) -> int | None:
    """Return the loopback listener port reported by lsof, if any."""
    match = _LISTENER.search(output)
    return int(match.group(1)) if match else None


def _child_pid(parent_pid: int) -> int | None:
    result = subprocess.run(
        ["/usr/bin/pgrep", "-P", str(parent_pid)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    pids = [line for line in result.stdout.splitlines() if line.isdigit()]
    return int(pids[0]) if pids else None


def _runtime_listener(pid: int) -> int | None:
    result = subprocess.run(
        ["/usr/sbin/lsof", "-nP", "-a", "-p", str(pid), "-iTCP", "-sTCP:LISTEN"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    return _listener_port(result.stdout)


def _matching_app_pids(app: Path) -> list[int]:
    result = subprocess.run(
        ["/bin/ps", "-axo", "pid=,command="],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    wanted = str(app)
    matches: list[int] = []
    for line in result.stdout.splitlines():
        fields = line.strip().split(maxsplit=1)
        if len(fields) == 2 and fields[0].isdigit() and fields[1] == wanted:
            matches.append(int(fields[0]))
    return matches


def _owned_runtime_is_running(pid: int) -> bool:
    result = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", "command="],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    return "codinal-runtime" in result.stdout


def _stop(process: subprocess.Popen[bytes], child_pid: int | None) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    if process.poll() is None:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    if child_pid is None:
        return
    deadline = time.monotonic() + 5
    while _owned_runtime_is_running(child_pid) and time.monotonic() < deadline:
        time.sleep(0.025)
    if _owned_runtime_is_running(child_pid):
        try:
            os.kill(child_pid, signal.SIGKILL)
        except ProcessLookupError:
            return


def _run_sample(app: Path, timeout_seconds: float) -> float:
    started = time.perf_counter()
    process = subprocess.Popen(
        [str(app)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    child_pid: int | None = None
    try:
        deadline = started + timeout_seconds
        while time.perf_counter() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Codinal exited before its native runtime was ready")
            child_pid = child_pid or _child_pid(process.pid)
            if child_pid is not None and _runtime_listener(child_pid) is not None:
                return (time.perf_counter() - started) * 1000
            time.sleep(0.025)
        raise TimeoutError(f"native runtime did not bind within {timeout_seconds:.1f}s")
    finally:
        _stop(process, child_pid)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, default=DEFAULT_APP)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("desktop launch measurement currently requires macOS")
    app = args.app.resolve()
    if not app.is_file():
        parser.error(f"Codinal executable not found: {app}")
    if not 1 <= args.samples <= 20:
        parser.error("--samples must be between 1 and 20")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    running = _matching_app_pids(app)
    if running:
        parser.error(f"close Codinal before measuring a cold launch (running: {running})")
    result = summarize_samples([_run_sample(app, args.timeout) for _ in range(args.samples)])
    print(json.dumps({"metric": "desktop_to_native_runtime_listener", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
