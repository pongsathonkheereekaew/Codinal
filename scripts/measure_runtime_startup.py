#!/usr/bin/env python3
"""Measure cold bootstrap of the bundled Rust runtime.

Each sample starts a fresh read-only runtime process with an isolated
temporary data directory and stops when its loopback listener accepts a
connection. This does not claim GPUI first paint or first-model-token
latency; those require separate macOS UI/provider probes.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME = Path("/Applications/Codinal.app/Contents/Resources/codinal-runtime")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.perf.measurement import summarize_samples


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def _run_sample(runtime: Path, timeout_seconds: float) -> float:
    port = _free_loopback_port()
    token = "benchmark-token-with-at-least-32-characters"
    with tempfile.TemporaryDirectory(prefix="codinal-native-runtime-bench-") as directory:
        environment = os.environ.copy()
        environment.update(
            {
                "CODINAL_SESSION_TOKEN": token,
                "CODINAL_PORT": str(port),
                "CODINAL_DATA_DIR": directory,
            }
        )
        for name in (
            "CODINAL_EXPERIMENTAL_EXECUTION",
            "CODINAL_PARENT_PID",
            "CODINAL_SECRET_BOOTSTRAP",
        ):
            environment.pop(name, None)
        started = time.perf_counter()
        process = subprocess.Popen(
            [str(runtime)],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            deadline = started + timeout_seconds
            while time.perf_counter() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("native runtime exited before it was ready")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.05):
                        return (time.perf_counter() - started) * 1000
                except OSError:
                    time.sleep(0.025)
            raise TimeoutError(f"native runtime did not bind within {timeout_seconds:.1f}s")
        finally:
            _stop(process)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    if not runtime.is_file() or not os.access(runtime, os.X_OK):
        parser.error(f"native runtime executable not found: {runtime}")
    if not 1 <= args.samples <= 50:
        parser.error("--samples must be between 1 and 50")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    result = summarize_samples([_run_sample(runtime, args.timeout) for _ in range(args.samples)])
    print(json.dumps({"metric": "native_runtime_to_listener", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
