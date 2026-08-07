#!/usr/bin/env python3
"""harness skill — core/catalog skill management.

  harness skill list [--all] [--json]    show skills with class + state
  harness skill enable NAME              enable a catalog skill
  harness skill disable NAME             disable a catalog skill (core refused)
  harness skill reset                    re-enable every disabled skill
  harness skill audit [--json]           classification coverage + journal health

Disabling never deletes source skills. For OpenCode it adds a native
`permission.skill.<name>: deny` rule; for hosts without a native mechanism it
reports `unsupported` (decision #6) and records the intent in the journal.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_hf = os.environ.get("CEDIA_HOME")
if _hf:
    ROOT = Path(_hf).resolve()
for sub in ("scripts",):
    p = ROOT / sub
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from adapters import registry  # noqa: E402
from lib import skills as skills_lib  # noqa: E402


def _apply_to_adapters(home: Path, disabled: set[str]) -> list[str]:
    """Push the disabled set to every implemented host adapter. Returns
    human-readable results."""
    notes: list[str] = []
    # opencode is the only host with a native mechanism today
    for name in registry.implemented():
        from lib import manifest as manifest_lib
        data = manifest_lib.load(ROOT / "config" / "hosts.yaml",
                                 ROOT / "schemas" / "host-capability.schema.json")
        entry = data["hosts"].get(name)
        if not entry:
            continue
        adapter = registry.get(name)(
            entry=entry, baseline=data["permission_baseline"],
            agents_home=ROOT, policy_source=ROOT / "AGENTS.md",
            commands_source=ROOT / "commands")
        res = adapter.apply_skill_state(home, disabled)
        for w in res.written:
            notes.append(f"{name}: {w}")
        for s in res.skipped:
            notes.append(f"{name}: skip ({s})")
        for c in res.conflicts:
            notes.append(f"{name}: CONFLICT ({c})")
    return notes


def cmd_list(args, agents_home: Path) -> int:
    classes = skills_lib.classify(agents_home)
    disabled = skills_lib.SkillJournal(agents_home).disabled()
    rows = []
    for name in sorted(classes):
        state = "disabled" if (classes[name] == "catalog" and name in disabled) else "enabled"
        rows.append({"name": name, "class": classes[name], "state": state})
    if not args.all:
        rows = [r for r in rows if r["state"] == "enabled"] if False else rows  # default: show all
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    print(f"{'name':<40} {'class':<8} state")
    for r in rows:
        print(f"{r['name']:<40} {r['class']:<8} {r['state']}")
    print(f"\n{len(rows)} skills  ({sum(1 for r in rows if r['state']=='disabled')} disabled)")
    return 0


def cmd_disable(args, agents_home: Path, home: Path) -> int:
    classes = skills_lib.classify(agents_home)
    if args.name not in classes:
        print(f"unknown skill: {args.name}", file=sys.stderr)
        return 2
    if classes[args.name] == "core":
        print(f"refusing to disable core skill: {args.name}", file=sys.stderr)
        return 1
    journal = skills_lib.SkillJournal(agents_home)
    changed = journal.disable(args.name)
    disabled = journal.disabled()
    print(f"{'disabled' if changed else 'already disabled'}: {args.name}")
    for note in _apply_to_adapters(home, disabled):
        print(f"  {note}")
    return 0


def cmd_enable(args, agents_home: Path, home: Path) -> int:
    classes = skills_lib.classify(agents_home)
    if args.name not in classes:
        print(f"unknown skill: {args.name}", file=sys.stderr)
        return 2
    journal = skills_lib.SkillJournal(agents_home)
    changed = journal.enable(args.name)
    disabled = journal.disabled()
    print(f"{'enabled' if changed else 'already enabled'}: {args.name}")
    for note in _apply_to_adapters(home, disabled):
        print(f"  {note}")
    return 0


def cmd_reset(args, agents_home: Path, home: Path) -> int:
    journal = skills_lib.SkillJournal(agents_home)
    prev = journal.reset()
    print(f"cleared {len(prev)} disabled entr{'y' if len(prev)==1 else 'ies'}")
    for note in _apply_to_adapters(home, set()):
        print(f"  {note}")
    return 0


def cmd_audit(args, agents_home: Path) -> int:
    report = skills_lib.audit(agents_home)
    if args.json:
        print(json.dumps(report, indent=2))
        return 1 if report["issues"] else 0
    print(f"skills: {report['total']}  core={report['core']}  catalog={report['catalog']}")
    if report["disabled"]:
        print(f"disabled: {', '.join(report['disabled'])}")
    if report["issues"]:
        print("issues:")
        for i in report["issues"]:
            print(f"  - {i}")
        return 1
    print("audit: OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="harness skill")
    p.add_argument("--agents-home", default=str(ROOT))
    p.add_argument("--home", default=str(Path.home()))
    sub = p.add_subparsers(dest="cmd", required=True)

    s_list = sub.add_parser("list")
    s_list.add_argument("--all", action="store_true")
    s_list.add_argument("--json", action="store_true")
    s_list.set_defaults(fn=cmd_list)

    s_dis = sub.add_parser("disable")
    s_dis.add_argument("name")
    s_dis.set_defaults(fn=cmd_disable)

    s_en = sub.add_parser("enable")
    s_en.add_argument("name")
    s_en.set_defaults(fn=cmd_enable)

    s_reset = sub.add_parser("reset")
    s_reset.set_defaults(fn=cmd_reset)

    s_audit = sub.add_parser("audit")
    s_audit.add_argument("--json", action="store_true")
    s_audit.set_defaults(fn=cmd_audit)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    agents_home = Path(args.agents_home)
    if getattr(args, "name", None) and args.cmd in ("disable", "enable"):
        return args.fn(args, agents_home, Path(args.home))
    if args.cmd in ("reset",):
        return args.fn(args, agents_home, Path(args.home))
    return args.fn(args, agents_home)


if __name__ == "__main__":
    sys.exit(main())
