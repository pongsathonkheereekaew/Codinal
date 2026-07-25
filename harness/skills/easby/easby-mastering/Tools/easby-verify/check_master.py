#!/usr/bin/env python3
"""Validate a MasterDecision or StemMasterDecision JSON against the easby-mastering schema.

Usage:
    check_master.py path/to/decision.json
    cat decision.json | check_master.py
Exit 0 on PASS, 1 on FAIL.
"""
from __future__ import annotations

import json
import sys
from typing import Any

EQ_BANDS = {
    "high_pass", "low_pass", "low_shelf", "high_shelf",
    "high_shelf_baxandall", "peak_cut", "peak_boost",
}
COMP_TYPE = {"broadband", "multiband", "parallel", "dynamic_eq", "none"}
COMP_PURPOSE = {"glue", "control", "effect"}
WIDTH = {"none", "narrow", "widen"}
DITHER_TYPE = {"TPDF", "POW-R-1", "POW-R-3", "UV22HR", "none"}
K_SYS = {"K-20", "K-14", "K-12", "K-0"}
FORMAT = {
    "16bit/44100", "24bit/48000", "24bit/96000",
    "mp3/320", "atmos_adm_bwf", "vinyl_lacquer",
}
PROC_ORDER = {"individual_then_sum", "sum_then_process"}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check_range(name: str, val: Any, lo: float, hi: float) -> None:
    if not isinstance(val, (int, float)):
        fail(f"{name} not numeric: {val!r}")
    if val < lo or val > hi:
        fail(f"{name}={val} out of range [{lo}, {hi}]")


def check_master_decision(d: dict) -> None:
    check_range("target_lufs", d.get("target_lufs", -14), -30, 0)
    check_range("true_peak_ceiling", d.get("true_peak_ceiling", -1.0), -3.0, 0)

    for i, m in enumerate(d.get("eq_moves", []) or []):
        band = m.get("band")
        if band not in EQ_BANDS:
            fail(f"eq_moves[{i}].band={band!r} not in {EQ_BANDS}")
        freq = m.get("freq_hz")
        if freq is not None:
            check_range(f"eq_moves[{i}].freq_hz", freq, 20, 20000)
        if "gain_db" in m:
            check_range(f"eq_moves[{i}].gain_db", m["gain_db"], -12, 12)

    comp = d.get("compression")
    if comp:
        if comp.get("type") not in COMP_TYPE:
            fail(f"compression.type={comp.get('type')!r} not in {COMP_TYPE}")
        if comp.get("purpose") not in COMP_PURPOSE:
            fail(f"compression.purpose={comp.get('purpose')!r} not in {COMP_PURPOSE}")
        if comp.get("ratio", 1.0) < 1.0:
            fail(f"compression.ratio={comp['ratio']} must be >= 1.0")
        if comp.get("gain_reduction_db", 0) < 0:
            fail("compression.gain_reduction_db must be >= 0")

    lim = d.get("limiter")
    if lim:
        check_range("limiter.ceiling_dbtp", lim.get("ceiling_dbtp", -1.0), -3.0, 0)
        if lim.get("release_ms", 0) < 0:
            fail("limiter.release_ms must be >= 0")

    stereo = d.get("stereo")
    if stereo and stereo.get("width_adjustment") not in WIDTH:
        fail(f"stereo.width_adjustment={stereo.get('width_adjustment')!r} not in {WIDTH}")

    dither = d.get("dither")
    if dither:
        if dither.get("type") not in DITHER_TYPE:
            fail(f"dither.type={dither.get('type')!r} not in {DITHER_TYPE}")

    if d.get("k_system_reference") and d["k_system_reference"] not in K_SYS:
        fail(f"k_system_reference={d['k_system_reference']!r} not in {K_SYS}")
    if d.get("format") and d["format"] not in FORMAT:
        fail(f"format={d['format']!r} not in {FORMAT}")

    check_range("confidence", d.get("confidence", 0), 0, 1)
    notes = d.get("notes", "")
    if not isinstance(notes, str) or not notes.strip():
        fail("notes must be non-empty string")


def check_stem_master_decision(d: dict) -> None:
    stems = d.get("stems") or []
    if not stems:
        fail("stems[] must be non-empty")
    for i, s in enumerate(stems):
        for k in ("name", "file"):
            if not isinstance(s.get(k), str) or not s[k].strip():
                fail(f"stems[{i}].{k} must be non-empty string")
        check_range(f"stems[{i}].peak_dbfs", s.get("peak_dbfs", 0), -60, 0)

    if d.get("processing_order") not in PROC_ORDER:
        fail(f"processing_order={d.get('processing_order')!r} not in {PROC_ORDER}")
    if d.get("latency_aligned") is not True:
        fail("latency_aligned must be true (sample-accurate stem alignment is mandatory)")

    check_range("target_lufs", d.get("target_lufs", -14), -30, 0)
    check_range("true_peak_ceiling", d.get("true_peak_ceiling", -1.0), -3.0, 0)


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
    if t == "MasterDecision":
        check_master_decision(d)
    elif t == "StemMasterDecision":
        check_stem_master_decision(d)
    else:
        fail(f"unknown type: {t!r}")

    print("PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
