# Generic fallback evidence

```bash
bash harness/scripts/adapters/generic-verify.sh
python3 harness/scripts/harness_host.py --agents-home harness host verify --host generic
```

Result: PASS. The generic host keeps `policy_file` and `skill_discovery` at
`partial` (behavioral `AGENTS.md` + `~/.agents/skills` only) and every other
capability `unsupported` with a reason, exactly as declared in `hosts.yaml`.
