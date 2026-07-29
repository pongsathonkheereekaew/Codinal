#!/usr/bin/env python3
"""Measure cold Python-sidecar bootstrap in a fresh process per sample.

This covers interpreter startup, runtime imports, and ``build_services``. It
does not claim end-to-end Tauri/WebView launch latency or first-model-token
latency.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# Direct ``python scripts/…`` execution puts scripts/ on sys.path, not the
# repository root where the runtime package lives.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.perf.measurement import summarize_samples


def _bootstrap_once() -> None:
    """Compose the real service graph, then let process shutdown close stores."""
    from runtime.control_plane.server import ServerConfig, build_services

    with tempfile.TemporaryDirectory(prefix="codinal-startup-bench-") as directory:
        build_services(
            ServerConfig(
                token="benchmark-token-with-at-least-32-characters",
                port=43123,
                data_dir=Path(directory),
                default_model="openai:gpt-5.6-sol",
            )
        )


def _run_sample() -> float:
    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--once"],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("sidecar bootstrap sample failed")
    return (time.perf_counter() - started) * 1000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--once", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.once:
        _bootstrap_once()
        return 0
    if not 1 <= args.samples <= 50:
        parser.error("--samples must be between 1 and 50")
    result = summarize_samples([_run_sample() for _ in range(args.samples)])
    print(json.dumps({"metric": "python_sidecar_bootstrap", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
