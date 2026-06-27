#!/usr/bin/env python3
"""Validate a MixDecision or MixBusDecision JSON against the easby-mixing schema.

Usage:
    check_mix.py path/to/decision.json
    cat decision.json | check_mix.py
Exit 0 on PASS, 1 on FAIL.
"""
from __future__ import annotations

import json
import sys
from typing import Any

EQ_BANDS = {
    "high_pass", "low_pass", "low_shelf", "high_shelf",
    "peak_cut", "peak_boost",
}
COMP_PURPOSE = {"control", "effect", "glue"}
REVERB_TYPE = {"plate", "hall", "room", "spring", "chamber", "nonlinear"}
Y_DEPTH = {"front", "mid", "back"}
Z_PLACEMENT = {"low", "mid", "mid-high", "high"}
SC_SOURCE = {"kick", "snare", "vocal", "ghost_midi", "trigger_click", None}
GROUP_ASSIGN = {
    "drum_bus", "vocal_bus", "guitar_bus", "fx_bus",
    "parallel_drum_bus", "parallel_vocal_bus", "mix_bus", None,
}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check_range(name: str, val: Any, lo: float, hi: float) -> None:
    if not isinstance(val, (int, float)):
        fail(f"{name} not numeric: {val!r}")
    if val < lo or val > hi:
        fail(f"{name}={val} out of range [{lo}, {hi}]")


def check_mix_decision(d: dict) -> None:
    check_range("fader_db", d.get("fader_db", 0), -60, 12)
    check_range("pan", d.get("pan", 0), -100, 100)

    for i, m in enumerate(d.get("eq_moves", []) or []):
        band = m.get("band")
        if band not in EQ_BANDS:
            fail(f"eq_moves[{i}].band={band!r} not in {EQ_BANDS}")
        freq = m.get("freq_hz")
        if freq is not None:
            check_range(f"eq_moves[{i}].freq_hz", freq, 20, 20000)
        if "gain_db" in m:
            check_range(f"eq_moves[{i}].gain_db", m["gain_db"], -24, 24)

    comp = d.get("compression")
    if comp:
        if comp.get("ratio", 1.0) < 1.0:
            fail(f"compression.ratio={comp['ratio']} must be >= 1.0")
        if comp.get("gain_reduction_db", 0) < 0:
            fail("compression.gain_reduction_db must be >= 0")
        if comp.get("purpose") not in COMP_PURPOSE:
            fail(f"compression.purpose={comp.get('purpose')!r} not in {COMP_PURPOSE}")

    sc = d.get("sidechain")
    if sc:
        if sc.get("source") not in SC_SOURCE:
            fail(f"sidechain.source={sc.get('source')!r} not in {SC_SOURCE}")
        if sc.get("depth_db", 0) < 0:
            fail("sidechain.depth_db must be >= 0")

    rv = d.get("reverb")
    if rv and rv.get("type") not in REVERB_TYPE:
        fail(f"reverb.type={rv.get('type')!r} not in {REVERB_TYPE}")

    img = d.get("imaging")
    if img:
        if img.get("y_depth") not in Y_DEPTH:
            fail(f"imaging.y_depth={img.get('y_depth')!r} not in {Y_DEPTH}")
        if img.get("z_freq_placement") not in Z_PLACEMENT:
            fail(f"imaging.z_freq_placement={img.get('z_freq_placement')!r} not in {Z_PLACEMENT}")

    if d.get("group_assignment") not in GROUP_ASSIGN:
        fail(f"group_assignment={d.get('group_assignment')!r} not in {GROUP_ASSIGN}")

    check_range("confidence", d.get("confidence", 0), 0, 1)
    notes = d.get("notes", "")
    if not isinstance(notes, str) or not notes.strip():
        fail("notes must be non-empty string")


def check_mix_bus_decision(d: dict) -> None:
    if d.get("compression_ratio", 1.0) < 1.0:
        fail(f"compression_ratio={d['compression_ratio']} must be >= 1.0")
    if d.get("compression_gr_db", 0) < 0:
        fail("compression_gr_db must be >= 0")
    check_range("limiter_ceiling_dbfs", d.get("limiter_ceiling_dbfs", -1.0), -6.0, 0.0)
    check_range("target_peak_lufs", d.get("target_peak_lufs", -6), -30, 0)
    check_range("confidence", d.get("confidence", 0), 0, 1)
    notes = d.get("notes", "")
    if not isinstance(notes, str) or not notes.strip():
        fail("notes must be non-empty string")


def main() -> None:
    if len(sys.argv) >= 2:
        with open(sys.argv[1], "r", encoding="utf-8") as fh:
            payload = fh.read()
    else:
        payload = sys.stdin.read()

    try:
        d = json.loads(payload)
    except json.JSONDecodeError as e:
        fail(f"invalid JSON: {e}")

    t = d.get("type")
    if t == "MixDecision":
        check_mix_decision(d)
    elif t == "MixBusDecision":
        check_mix_bus_decision(d)
    else:
        fail(f"unknown type: {t!r}")

    print("PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
