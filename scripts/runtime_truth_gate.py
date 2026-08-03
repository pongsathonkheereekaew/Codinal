#!/usr/bin/env python3
"""Check and generate Codinal's Rust runtime capability inventory.

The catalogue is deliberately declarative: official capability names and
release decisions are reviewed data, while every Rust/GPUI evidence marker is
resolved against the current source tree. CI uses --check so route or wiring
drift cannot leave a stale capability table behind.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "docs/evidence/runtime-truth/capability-catalog.json"
INVENTORY_PATH = ROOT / "docs/evidence/runtime-truth/capability-inventory.json"
TABLE_PATH = ROOT / "docs/evidence/runtime-truth/capability-table.md"
ALLOWED_STATUSES = {"complete", "partial", "missing", "external-gated"}
NOT_IMPLEMENTED_PHRASE = "not implemented in rust runtime"


class GateError(Exception):
    """A capability inventory assertion failed."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise GateError(f"cannot read {path.relative_to(ROOT)}: {error}") from error
    if not isinstance(value, dict):
        raise GateError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def read_source(path_value: str, cache: dict[Path, list[str]]) -> list[str]:
    path = ROOT / path_value
    if path not in cache:
        if not path.is_file():
            raise GateError(f"evidence source does not exist: {path_value}")
        try:
            cache[path] = path.read_text().splitlines()
        except OSError as error:
            raise GateError(f"cannot read evidence source {path_value}: {error}") from error
    return cache[path]


def find_marker(lines: list[str], marker: str, regex: bool = False) -> int | None:
    if regex:
        pattern = re.compile(marker)
        for index, line in enumerate(lines):
            if pattern.search(line):
                return index
        return None
    for index, line in enumerate(lines):
        if marker in line:
            return index
    return None


def source_fingerprint(lines: list[str]) -> str:
    return hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest()


def resolve_evidence(
    entry: dict[str, Any],
    source_cache: dict[Path, list[str]],
) -> dict[str, Any]:
    path_value = entry.get("path")
    marker = entry.get("marker")
    if not isinstance(path_value, str) or not path_value:
        raise GateError("every evidence entry needs a source path")
    if not isinstance(marker, str) or not marker:
        raise GateError(f"every evidence entry needs a marker: {path_value}")
    lines = read_source(path_value, source_cache)
    line = find_marker(lines, marker, bool(entry.get("regex", False)))
    if line is None:
        raise GateError(
            f"source marker missing: {path_value}::{marker}"
        )

    behavior = entry.get("behavior")
    if behavior == "not_implemented":
        context = "\n".join(lines[max(0, line - 24) : line + 41]).lower()
        if "501 not implemented" not in context or NOT_IMPLEMENTED_PHRASE not in context:
            raise GateError(
                f"not-implemented marker is not backed by a 501 response: "
                f"{path_value}:{line + 1}"
            )

    resolved = {
        "path": path_value,
        "line": line + 1,
        "marker": marker,
    }
    if entry.get("kind"):
        resolved["kind"] = entry["kind"]
    if behavior:
        resolved["behavior"] = behavior
    return resolved


def validate_catalog(
    catalog: dict[str, Any],
    source_cache: dict[Path, list[str]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    capabilities = catalog.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        raise GateError("capability catalogue must contain a non-empty capabilities list")

    rows: list[dict[str, Any]] = []
    fingerprints: dict[str, str] = {}
    seen_ids: set[str] = set()
    for capability in capabilities:
        if not isinstance(capability, dict):
            raise GateError("capability entries must be JSON objects")
        capability_id = capability.get("id")
        name = capability.get("official_name")
        status = capability.get("status")
        if not isinstance(capability_id, str) or not capability_id:
            raise GateError("every capability needs a non-empty id")
        if capability_id in seen_ids:
            raise GateError(f"duplicate capability id: {capability_id}")
        seen_ids.add(capability_id)
        if not isinstance(name, str) or not name:
            raise GateError(f"{capability_id}: missing official_name")
        if status not in ALLOWED_STATUSES:
            raise GateError(f"{capability_id}: unsupported status {status!r}")
        if not isinstance(capability.get("notes"), str) or not capability["notes"].strip():
            raise GateError(f"{capability_id}: missing truth note")
        sources = capability.get("official_sources")
        if not isinstance(sources, list) or not sources:
            raise GateError(f"{capability_id}: missing official source")
        if any(
            not isinstance(source, str)
            or not source.startswith("https://learn.chatgpt.com/docs/")
            for source in sources
        ):
            raise GateError(f"{capability_id}: official source must be a ChatGPT Learn URL")

        visible = capability.get("visible_action")
        enabled = capability.get("enabled_action")
        local_fallback = capability.get("local_fallback")
        if not isinstance(visible, bool) or not isinstance(enabled, bool):
            raise GateError(f"{capability_id}: visible_action and enabled_action must be booleans")
        if not isinstance(local_fallback, bool):
            raise GateError(f"{capability_id}: local_fallback must be a boolean")
        if enabled and not visible:
            raise GateError(f"{capability_id}: an enabled action must be visible")

        rust_evidence = capability.get("rust_evidence")
        gpui_evidence = capability.get("gpui_evidence")
        test_evidence = capability.get("tests_or_evidence")
        if not isinstance(rust_evidence, list) or not isinstance(gpui_evidence, list):
            raise GateError(f"{capability_id}: Rust and GPUI evidence lists are required")
        if not isinstance(test_evidence, list) or not test_evidence:
            raise GateError(f"{capability_id}: tests_or_evidence must not be empty")
        if visible and not gpui_evidence:
            raise GateError(f"{capability_id}: visible actions need a GPUI entry point")
        if status == "missing" and enabled:
            raise GateError(f"{capability_id}: missing capability cannot expose an enabled action")
        if status == "external-gated" and enabled and not local_fallback:
            raise GateError(
                f"{capability_id}: external-gated capability needs a local fallback or a disabled action"
            )

        resolved_rust = []
        for evidence in rust_evidence:
            if not isinstance(evidence, dict):
                raise GateError(f"{capability_id}: invalid Rust evidence entry")
            resolved = resolve_evidence(evidence, source_cache)
            resolved_rust.append(resolved)
            path = ROOT / resolved["path"]
            fingerprints[resolved["path"]] = source_fingerprint(read_source(resolved["path"], source_cache))
        resolved_gpui = []
        for evidence in gpui_evidence:
            if not isinstance(evidence, dict):
                raise GateError(f"{capability_id}: invalid GPUI evidence entry")
            resolved = resolve_evidence(evidence, source_cache)
            resolved_gpui.append(resolved)
            fingerprints[resolved["path"]] = source_fingerprint(read_source(resolved["path"], source_cache))
        resolved_tests = []
        for evidence_path in test_evidence:
            if not isinstance(evidence_path, str) or not evidence_path:
                raise GateError(f"{capability_id}: invalid test/evidence path")
            path = ROOT / evidence_path
            if not path.is_file():
                raise GateError(f"{capability_id}: test/evidence path does not exist: {evidence_path}")
            resolved_tests.append(evidence_path)

        not_implemented = [
            item for item in resolved_rust if item.get("behavior") == "not_implemented"
        ]
        if status == "complete" and not_implemented:
            raise GateError(f"{capability_id}: complete claim includes a 501 route")
        if visible and enabled and not_implemented and not local_fallback:
            raise GateError(
                f"{capability_id}: visible enabled action maps to a 501 route without a local fallback"
            )

        rows.append(
            {
                "id": capability_id,
                "official_name": name,
                "official_sources": sources,
                "status": status,
                "release_blocking": bool(capability.get("release_blocking", False)),
                "visible_action": visible,
                "enabled_action": enabled,
                "local_fallback": local_fallback,
                "notes": capability["notes"],
                "rust_entry_points": resolved_rust,
                "gpui_entry_points": resolved_gpui,
                "tests_or_evidence": resolved_tests,
            }
        )

    return rows, dict(sorted(fingerprints.items()))


def format_entry_points(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "—"
    return "<br>".join(f"`{entry['path']}:{entry['line']}`" for entry in entries)


def render_table(inventory: dict[str, Any]) -> str:
    lines = [
        "# Codinal runtime truth capability table",
        "",
        "Generated by `scripts/runtime_truth_gate.py`; do not edit this file directly.",
        "The official pages are the comparison catalogue. Rust and GPUI source markers,"
        " tests, and evidence determine the local status.",
        "",
        f"Baseline date: `{inventory['baseline_date']}`",
        "",
        "| Official capability | Status | Release blocker | Rust/runtime entry point | GPUI entry point | Test/evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in inventory["capabilities"]:
        status = row["status"]
        blocker = "yes" if row["release_blocking"] else "no"
        sources = ", ".join(f"[{index + 1}]({url})" for index, url in enumerate(row["official_sources"]))
        evidence = "<br>".join(f"`{path}`" for path in row["tests_or_evidence"])
        action = "enabled" if row["enabled_action"] else "not enabled"
        lines.append(
            "| "
            f"{row['official_name']} ({sources})<br>{row['notes']}<br>UI: {action}"
            f" | `{status}` | {blocker} | {format_entry_points(row['rust_entry_points'])}"
            f" | {format_entry_points(row['gpui_entry_points'])} | {evidence} |"
        )
    lines.extend(
        [
            "",
            "`complete` requires a reachable Rust path, GPUI wiring, and evidence; a lower-level helper or a `501` route cannot satisfy it.",
            "",
        ]
    )
    return "\n".join(lines)


def build_inventory() -> dict[str, Any]:
    catalog = load_json(CATALOG_PATH)
    source_cache: dict[Path, list[str]] = {}
    capabilities, fingerprints = validate_catalog(catalog, source_cache)
    return {
        "schema_version": catalog.get("schema_version"),
        "generated_by": "scripts/runtime_truth_gate.py",
        "baseline_date": catalog.get("baseline_date"),
        "source_policy": catalog.get("source_policy"),
        "source_fingerprints": fingerprints,
        "capabilities": capabilities,
    }


def serialized_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when generated inventory or table differs from the source catalogue",
    )
    args = parser.parse_args()

    try:
        inventory = build_inventory()
        expected_json = serialized_json(inventory)
        expected_table = render_table(inventory)
        if args.check:
            actual_json = INVENTORY_PATH.read_text() if INVENTORY_PATH.is_file() else None
            actual_table = TABLE_PATH.read_text() if TABLE_PATH.is_file() else None
            errors = []
            if actual_json != expected_json:
                errors.append(INVENTORY_PATH.relative_to(ROOT))
            if actual_table != expected_table:
                errors.append(TABLE_PATH.relative_to(ROOT))
            if errors:
                raise GateError(
                    "generated runtime truth artifacts are stale: "
                    + ", ".join(str(path) for path in errors)
                    + "; run scripts/runtime_truth_gate.py"
                )
        else:
            INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            INVENTORY_PATH.write_text(expected_json)
            TABLE_PATH.write_text(expected_table)
        print(
            f"runtime truth gate: PASS ({len(inventory['capabilities'])} capabilities, "
            f"{len(inventory['source_fingerprints'])} source files)"
        )
        return 0
    except (GateError, OSError) as error:
        print(f"runtime truth gate: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
