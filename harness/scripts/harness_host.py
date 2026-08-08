#!/usr/bin/env python3
"""harness host / verify / skill CLI.

Subcommands:
  harness host list                       list hosts + tier
  harness host inspect [name|--all]       show capabilities + smoke probes
  harness host provision <name>           render the host adapter into $HOME
                                          (--dry-run, --enable SKILL repeatable)
  harness verify [--host N] [--tier N]    effective-state verification
              [--project DIR] [--json]
  harness skill ...                       (Phase 2) catalog management

Reads the central manifest (config/hosts.yaml). Never weakens verify.sh.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Resolve repo / agents-home root from this file's location (works both in the
# dev tree and under ~/.agents/scripts/ after install). CEDIA_HOME
# overrides for isolated smoke/contract runs.
ROOT = Path(__file__).resolve().parent.parent
_hf = os.environ.get("CEDIA_HOME")
if _hf:
    ROOT = Path(_hf).resolve()
for sub in ("scripts",):
    p = ROOT / sub
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from adapters import registry  # noqa: E402
from lib import manifest as manifest_lib  # noqa: E402


def _load_manifest(agents_home: Path):
    agents_home = Path(agents_home)
    mpath = agents_home / "config" / "hosts.yaml"
    spath = agents_home / "schemas" / "host-capability.schema.json"
    return manifest_lib.load(mpath, spath), mpath


def _adapter_for(host_name: str, entry: dict, baseline: dict, agents_home: Path):
    agents_home = Path(agents_home)
    cls = registry.get(host_name)
    if cls is None:
        return None
    adapter = cls(
        entry=entry,
        baseline=baseline,
        agents_home=agents_home,
        policy_source=agents_home / "AGENTS.md",
        commands_source=agents_home / "commands",
    )
    adapter.name = host_name
    return adapter


def cmd_host_list(args, data) -> int:
    print(f"{'host':<14} {'tier':<5} {'adapter':<10} capabilities")
    for name, entry in sorted(data["hosts"].items()):
        impl = "yes" if registry.get(name) else "—"
        caps = entry.get("capabilities", {})
        supported = sum(1 for c in caps.values() if c.get("status") == "supported")
        print(f"{name:<14} {entry.get('tier','?'):<5} {impl:<10} "
              f"{supported}/{len(caps)} supported")
    return 0


def cmd_host_inspect(args, data) -> int:
    hosts = data["hosts"]
    names = sorted(hosts) if args.all or not args.name else [args.name]
    for n in names:
        if n not in hosts:
            print(f"unknown host: {n}", file=sys.stderr)
            return 2
        entry = hosts[n]
        print(f"== {n} (tier {entry.get('tier')}) ==")
        if entry.get("min_version"):
            print(f"  min_version: {entry['min_version']}")
        if entry.get("config_file"):
            print(f"  config: {entry['config_file']} ({entry.get('config_format','?')})")
        print("  capabilities:")
        for cname, c in entry.get("capabilities", {}).items():
            print(f"    {cname:<24} {c.get('status'):<12} {c.get('mechanism','')}")
        if entry.get("smoke"):
            print("  smoke:")
            for s in entry["smoke"]:
                print(f"    - {s}")
    return 0


def cmd_host_provision(args, data) -> int:
    entry = data["hosts"].get(args.name)
    if entry is None:
        print(f"unknown host: {args.name}", file=sys.stderr)
        return 2
    adapter = _adapter_for(args.name, entry, data["permission_baseline"], args.agents_home)
    if adapter is None:
        print(f"no implemented adapter for {args.name} "
              f"(tier {entry.get('tier')}); nothing provisioned", file=sys.stderr)
        return 1
    home = Path(args.home).resolve()
    enabled = set(args.enable) if args.enable else None
    if args.dry_run:
        print(f"== dry-run: provision {args.name} into {home} ==")
    result = adapter.provision(home, dry_run=args.dry_run, enabled_skills=enabled)
    if result.diff:
        print(result.diff)
    for w in result.written:
        print(f"wrote: {w}")
    for s in result.skipped:
        print(f"skipped: {s}")
    for b in result.backups:
        print(f"backup: {b}")
    for c in result.conflicts:
        print(f"CONFLICT: {c}", file=sys.stderr)
    return 0 if not result.conflicts else 1


def cmd_verify(args, data) -> int:
    import json as _json
    hosts = data["hosts"]
    if args.host:
        names = [args.host]
    elif args.tier:
        names = [n for n, e in hosts.items() if e.get("tier") == args.tier]
    else:
        names = sorted(hosts)
    project = Path(args.project).resolve() if args.project else None
    rows = []
    exit_code = 0
    for n in names:
        entry = hosts.get(n)
        if entry is None:
            print(f"unknown host: {n}", file=sys.stderr)
            return 2
        adapter = _adapter_for(n, entry, data["permission_baseline"], args.agents_home)
        if adapter is None:
            for cname, c in entry.get("capabilities", {}).items():
                rows.append({"host": n, "capability": cname,
                             "status": c.get("status", "unverified"),
                             "evidence": "no adapter implemented",
                             "declared": c.get("status", "unverified")})
            continue
        for r in adapter.verify(Path(args.home).resolve(), project=project):
            rows.append({"host": n, "capability": r.name, "status": r.status,
                         "evidence": r.evidence, "declared": r.declared})
    # Tier-1 gate: a declared native mechanism that is still unverified
    # (unproven) blocks a READY verdict. Explicit unsupported rows are honest
    # negatives and do not block.
    for row in rows:
        host_tier = hosts[row["host"]].get("tier", 3)
        if host_tier == 1:
            mechanism = hosts[row["host"]].get("capabilities", {}).get(row["capability"], {}).get("mechanism")
            if mechanism and row["status"] == "unverified":
                exit_code = 1
    if args.json:
        print(_json.dumps(rows, indent=2))
        return exit_code
    print(f"{'host':<12} {'capability':<24} {'status':<12} evidence")
    for row in rows:
        print(f"{row['host']:<12} {row['capability']:<24} {row['status']:<12} {row['evidence']}")
    print()
    if exit_code == 0:
        print("READY (Tier-1 capabilities verified)")
    else:
        print("NOT READY — Tier-1 host has unsupported/unverified capability")
    return exit_code


def cmd_host_uninstall(args, data) -> int:
    entry = data["hosts"].get(args.name)
    if entry is None:
        print(f"unknown host: {args.name}", file=sys.stderr)
        return 2
    adapter = _adapter_for(args.name, entry, data["permission_baseline"], args.agents_home)
    if adapter is None:
        print(f"no adapter for {args.name}", file=sys.stderr)
        return 1
    removed = adapter.uninstall(Path(args.home).resolve())
    for r in removed:
        print(f"removed: {r}")
    if not removed:
        print(f"nothing owned by harness for {args.name} (journal empty)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="harness", description="cross-agent harness CLI")
    p.add_argument("--agents-home", default=str(ROOT),
                   help=f"SSOT root (default {ROOT})")
    sub = p.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("host", help="host capability management")
    hs = h.add_subparsers(dest="host_cmd", required=True)
    hs_list = hs.add_parser("list")
    hs_list.set_defaults(fn=cmd_host_list)
    hs_inspect = hs.add_parser("inspect")
    hs_inspect.add_argument("name", nargs="?")
    hs_inspect.add_argument("--all", action="store_true")
    hs_inspect.set_defaults(fn=cmd_host_inspect)
    hs_prov = hs.add_parser("provision")
    hs_prov.add_argument("name")
    hs_prov.add_argument("--home", default=str(Path.home()),
                         help="target HOME (default $HOME)")
    hs_prov.add_argument("--dry-run", action="store_true")
    hs_prov.add_argument("--enable", action="append", default=[],
                         metavar="SKILL", help="enable a skill (repeatable)")
    hs_prov.set_defaults(fn=cmd_host_provision)
    hs_un = hs.add_parser("uninstall")
    hs_un.add_argument("name")
    hs_un.add_argument("--home", default=str(Path.home()))
    hs_un.set_defaults(fn=cmd_host_uninstall)
    hs_verify = hs.add_parser("verify", help="verify every declared host")
    hs_verify.add_argument("--all", action="store_true")
    hs_verify.add_argument("--home", default=str(Path.home()))
    hs_verify.add_argument("--project")
    hs_verify.add_argument("--json", action="store_true")
    hs_verify.set_defaults(fn=cmd_verify, host=None, tier=None)

    v = sub.add_parser("verify", help="effective-state verification")
    v.add_argument("--home", default=str(Path.home()),
                   help="target HOME (default $HOME)")
    v.add_argument("--host")
    v.add_argument("--tier", type=int, choices=[1, 2, 3])
    v.add_argument("--project", help="project dir to check for overrides")
    v.add_argument("--json", action="store_true")
    v.set_defaults(fn=cmd_verify)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data, _ = _load_manifest(Path(args.agents_home))
    return args.fn(args, data)


if __name__ == "__main__":
    sys.exit(main())
