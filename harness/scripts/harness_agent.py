#!/usr/bin/env python3
"""Validate and resolve the minimal agent configuration (config/agent.yaml)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "agent.yaml"
SCHEMA_PATH = ROOT / "schemas" / "agent-config.schema.json"


def load(root: Path = ROOT) -> dict[str, Any]:
    data = yaml.safe_load((root / "config" / "agent.yaml").read_text())
    schema = json.loads((root / "schemas" / "agent-config.schema.json").read_text())
    jsonschema.validate(data, schema)
    return data


def resolve_active(data: dict[str, Any]) -> dict[str, Any]:
    active = data["active_model"]
    for model in data["models"]:
        if model["id"] == active:
            return model
    raise SystemExit(f"FAIL: active_model {active!r} is not in models")


def check(root: Path = ROOT) -> None:
    data = load(root)
    model = resolve_active(data)
    enabled_mcp = sum(1 for server in data["mcp"] if server["enabled"])
    print("agent config: OK")
    print(f"active model: {data['active_model']} ({model['provider']} / {model['model']})")
    print(f"models: {len(data['models'])}")
    print(f"plugins: {len(data['plugins'])}")
    print(f"mcp servers: {len(data['mcp'])} (enabled: {enabled_mcp})")


def resolve_model(root: Path = ROOT) -> None:
    data = load(root)
    json.dump(resolve_active(data), sys.stdout, indent=2)
    sys.stdout.write("\n")


def list_mcp(root: Path = ROOT) -> None:
    data = load(root)
    json.dump(data["mcp"], sys.stdout, indent=2)
    sys.stdout.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="validate config and print the active model")
    sub.add_parser("resolve-model", help="print the active model profile as JSON")
    sub.add_parser("list-mcp", help="print configured MCP servers as JSON")
    args = parser.parse_args()
    if args.command == "check":
        check()
    elif args.command == "resolve-model":
        resolve_model()
    else:
        list_mcp()


if __name__ == "__main__":
    main()
