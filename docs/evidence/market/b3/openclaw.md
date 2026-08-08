# OpenClaw adapter verification

```bash
bash harness/scripts/adapters/openclaw-verify.sh
```

Result: PASS. Asserts `~/.openclaw/skills` discovery in an isolated HOME.

Statuses: `skill_discovery` and `nested_skill_aliases` supported; hosts without
a declared instruction/command/permission surface stay `unsupported` honestly.
