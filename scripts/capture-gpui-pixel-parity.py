#!/usr/bin/env python3
"""Launch the native GPUI shell, capture one display, and run the diff gate.

This helper is intentionally fixture-driven: it never creates sessions, edits
the checked-in golden, or falls back to the user's production data directory.
The caller supplies an isolated data directory containing the desired state.
"""

from __future__ import annotations

import argparse
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts" / "verify-gpui-pixel-parity.py"
DEFAULT_GPUI = ROOT / "desktop" / "gpui" / "target" / "debug" / "codinal-gpui"
DEFAULT_RUNTIME = (
    ROOT / "crates" / "codinal-runtime" / "target" / "debug" / "codinal-runtime"
)
PROFILE_DIMENSIONS = {
    "window-1710x1112@2x": (3420, 2224),
    "window-1280x720@2x": (2560, 1440),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture one isolated native GPUI fixture and compare it with a golden."
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        type=Path,
        help="isolated data directory containing codinal.db; never the production directory",
    )
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--actual", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--gpui", type=Path, default=DEFAULT_GPUI)
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--profile", default="window-1710x1112@2x")
    parser.add_argument("--state", default="ready-chat")
    parser.add_argument("--expected-width", type=int)
    parser.add_argument("--expected-height", type=int)
    parser.add_argument("--startup-timeout", type=float, default=20.0)
    parser.add_argument("--settle-seconds", type=float, default=2.0)
    parser.add_argument(
        "--allow-keychain",
        action="store_true",
        help="allow the native shell to query macOS Keychain during capture",
    )
    parser.add_argument(
        "--no-activate",
        action="store_true",
        help="do not ask System Events to bring the GPUI window to the front",
    )
    parser.add_argument(
        "--no-window-check",
        action="store_true",
        help="skip the macOS window readiness check (less safe; display capture may be wrong)",
    )
    parser.add_argument("--channel-threshold", type=int, default=16)
    parser.add_argument("--mae-threshold", type=float, default=0.02)
    parser.add_argument("--changed-fraction-threshold", type=float, default=0.02)
    return parser.parse_args()


def fail(message: str) -> int:
    print(f"native capture: ERROR: {message}", file=sys.stderr)
    return 2


def validate_path(path: Path, label: str, *, executable: bool = False) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"{label} does not exist: {resolved}")
    if executable and not os.access(resolved, os.X_OK):
        raise ValueError(f"{label} is not executable: {resolved}")
    return resolved


def window_is_ready(pid: int) -> bool:
    script = (
        'tell application "System Events" to tell (first process whose unix id is '
        f"{pid}) to return (count of windows) > 0"
    )
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def activate_window(pid: int) -> None:
    script = (
        'tell application "System Events" to set frontmost of '
        f"(first process whose unix id is {pid}) to true"
    )
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "unknown System Events error"
        print(f"native capture: warning: could not activate GPUI window: {detail}")


def wait_for_window(process: subprocess.Popen[bytes], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("GPUI exited before its window became ready")
        if window_is_ready(process.pid):
            return
        time.sleep(0.25)
    raise RuntimeError(
        "GPUI window did not become ready; grant System Events access or pass "
        "--no-window-check only when the correct window is already foreground"
    )


def terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass


def main() -> int:
    args = parse_args()
    if platform.system() != "Darwin":
        return fail("native display capture requires macOS")
    if not VERIFY.is_file():
        return fail(f"comparison runner is missing: {VERIFY}")

    try:
        data_dir = args.data_dir.expanduser().resolve()
        if not data_dir.is_dir():
            raise ValueError(f"isolated --data-dir does not exist: {data_dir}")
        if not (data_dir / "codinal.db").is_file():
            raise ValueError(f"isolated --data-dir is missing codinal.db: {data_dir}")
        golden = validate_path(args.golden, "golden")
        gpui = validate_path(args.gpui, "GPUI binary", executable=True)
        runtime = validate_path(args.runtime, "runtime binary", executable=True)
        actual = args.actual.expanduser().resolve()
        output_dir = (args.output_dir or actual.parent).expanduser().resolve()
        if actual == golden:
            raise ValueError("--actual must not be the golden path")
        if args.startup_timeout <= 0 or args.settle_seconds < 0:
            raise ValueError("startup timeout must be positive and settle seconds non-negative")
    except ValueError as error:
        return fail(str(error))

    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "gpui.log"
    profile_dimensions = PROFILE_DIMENSIONS.get(args.profile)
    expected_width = args.expected_width or (
        profile_dimensions[0] if profile_dimensions else None
    )
    expected_height = args.expected_height or (
        profile_dimensions[1] if profile_dimensions else None
    )
    environment = os.environ.copy()
    environment["CODINAL_DATA_DIR"] = str(data_dir)
    environment["CODINAL_NATIVE_RUNTIME"] = str(runtime)
    environment["CODINAL_CAPTURE_PROFILE"] = args.profile
    if not args.allow_keychain:
        environment["CODINAL_CAPTURE_NO_KEYCHAIN"] = "1"

    process: subprocess.Popen[bytes] | None = None
    try:
        with log_path.open("wb") as log:
            process = subprocess.Popen(
                [str(gpui)],
                cwd=ROOT,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            if args.no_window_check:
                deadline = time.monotonic() + args.startup_timeout
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("GPUI exited before capture")
                    time.sleep(0.25)
            else:
                wait_for_window(process, args.startup_timeout)
            if not args.no_activate:
                activate_window(process.pid)
            time.sleep(args.settle_seconds)

            compare_command = [
                sys.executable,
                str(VERIFY),
                "--capture",
                "--profile",
                args.profile,
                "--state",
                args.state,
                "--golden",
                str(golden),
                "--actual",
                str(actual),
                "--output-dir",
                str(output_dir),
                "--channel-threshold",
                str(args.channel_threshold),
                "--mae-threshold",
                str(args.mae_threshold),
                "--changed-fraction-threshold",
                str(args.changed_fraction_threshold),
            ]
            if expected_width is not None:
                compare_command.extend(["--expected-width", str(expected_width)])
            if expected_height is not None:
                compare_command.extend(["--expected-height", str(expected_height)])
            result = subprocess.run(compare_command, cwd=ROOT, env=environment, check=False)
            print(f"native capture: log={log_path}")
            return result.returncode
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"native capture: ERROR: {error}", file=sys.stderr)
        print(f"native capture: log={log_path}", file=sys.stderr)
        return 2
    finally:
        if process is not None:
            terminate_process_group(process)


if __name__ == "__main__":
    raise SystemExit(main())
