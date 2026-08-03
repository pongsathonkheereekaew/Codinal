#!/usr/bin/env python3
"""Capture and compare one deterministic GPUI screenshot against a golden.

The script deliberately never writes to the golden path. It emits the actual
capture, an amplified diff, a 50/50 overlay, and machine-readable metrics so a
native macOS capture can be reviewed without claiming parity from geometry
tests alone.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare a GPUI actual capture with a checked-in golden."
    )
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--actual", required=True, type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Artifact directory; defaults to the actual capture directory.",
    )
    parser.add_argument(
        "--capture",
        action="store_true",
        help="Capture the main macOS display to --actual before comparing.",
    )
    parser.add_argument("--profile", default="unspecified")
    parser.add_argument("--state", default="unspecified")
    parser.add_argument("--expected-width", type=int)
    parser.add_argument("--expected-height", type=int)
    parser.add_argument("--channel-threshold", type=int, default=16)
    parser.add_argument("--mae-threshold", type=float, default=0.02)
    parser.add_argument("--changed-fraction-threshold", type=float, default=0.02)
    return parser.parse_args()


def capture_main_display(path: Path) -> None:
    if platform.system() != "Darwin":
        raise SystemExit("--capture is only supported on macOS")
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["/usr/sbin/screencapture", "-x", "-m", str(path)],
        check=True,
    )


def write_error(output_dir: Path, message: str) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(
        json.dumps({"pass": False, "error": message}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"pixel parity: ERROR: {message}", file=sys.stderr)
    return 2


def main() -> int:
    args = parse_args()
    golden = args.golden.expanduser().resolve()
    actual = args.actual.expanduser().resolve()
    output_dir = (args.output_dir or actual.parent).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if golden == actual:
        return write_error(output_dir, "--golden and --actual must be different files")
    if args.channel_threshold < 0 or args.channel_threshold > 255:
        return write_error(output_dir, "--channel-threshold must be between 0 and 255")
    if args.mae_threshold < 0 or args.changed_fraction_threshold < 0:
        return write_error(output_dir, "diff thresholds must be non-negative")

    if args.capture:
        try:
            capture_main_display(actual)
        except (OSError, subprocess.CalledProcessError) as error:
            return write_error(output_dir, f"capture failed: {error}")

    if not golden.is_file():
        return write_error(output_dir, f"golden does not exist: {golden}")
    if not actual.is_file():
        return write_error(output_dir, f"actual does not exist: {actual}")

    try:
        from PIL import Image, ImageChops, ImageEnhance
    except ImportError as error:
        return write_error(output_dir, f"Pillow is required: {error}")

    with Image.open(golden) as golden_image, Image.open(actual) as actual_image:
        golden_rgb = golden_image.convert("RGB")
        actual_rgb = actual_image.convert("RGB")

    if golden_rgb.size != actual_rgb.size:
        return write_error(
            output_dir,
            f"dimension mismatch: golden={golden_rgb.size}, actual={actual_rgb.size}",
        )

    width, height = actual_rgb.size
    if args.expected_width is not None and width != args.expected_width:
        return write_error(output_dir, f"actual width {width} != {args.expected_width}")
    if args.expected_height is not None and height != args.expected_height:
        return write_error(output_dir, f"actual height {height} != {args.expected_height}")

    difference = ImageChops.difference(actual_rgb, golden_rgb)
    amplified = ImageEnhance.Brightness(difference).enhance(8.0)
    amplified.save(output_dir / "diff.png")
    Image.blend(golden_rgb, actual_rgb, 0.5).save(output_dir / "overlay.png")

    total_delta = 0
    max_delta = 0
    changed_pixels = 0
    over_threshold_pixels = 0
    for actual_pixel, golden_pixel in zip(actual_rgb.getdata(), golden_rgb.getdata()):
        pixel_deltas = [
            abs(actual_channel - golden_channel)
            for actual_channel, golden_channel in zip(actual_pixel, golden_pixel)
        ]
        total_delta += sum(pixel_deltas)
        max_delta = max(max_delta, max(pixel_deltas, default=0))
        if any(pixel_deltas):
            changed_pixels += 1
        if any(delta > args.channel_threshold for delta in pixel_deltas):
            over_threshold_pixels += 1
    pixel_count = width * height
    mae = total_delta / (pixel_count * 3 * 255) if pixel_count else 0.0
    changed_fraction = changed_pixels / pixel_count if pixel_count else 0.0
    over_threshold_fraction = over_threshold_pixels / pixel_count if pixel_count else 0.0
    bounds = difference.getbbox()
    metrics = {
        "pass": mae <= args.mae_threshold and over_threshold_fraction <= args.changed_fraction_threshold,
        "profile": args.profile,
        "state": args.state,
        "golden": str(golden),
        "actual": str(actual),
        "dimensions": {"width": width, "height": height},
        "mae_normalized": mae,
        "max_channel_delta": max_delta,
        "changed_pixels": changed_pixels,
        "changed_fraction": changed_fraction,
        "over_threshold_pixels": over_threshold_pixels,
        "over_threshold_fraction": over_threshold_fraction,
        "channel_threshold": args.channel_threshold,
        "mae_threshold": args.mae_threshold,
        "changed_fraction_threshold": args.changed_fraction_threshold,
        "difference_bounds": list(bounds) if bounds else None,
        "artifacts": {
            "diff": str(output_dir / "diff.png"),
            "overlay": str(output_dir / "overlay.png"),
        },
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "pixel parity: "
        f"{'PASS' if metrics['pass'] else 'FAIL'} "
        f"{width}x{height}, mae={mae:.6f}, "
        f">{args.channel_threshold}={over_threshold_fraction:.4%}"
    )
    return 0 if metrics["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
