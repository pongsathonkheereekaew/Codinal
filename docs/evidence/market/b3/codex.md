# Codex adapter verification

```bash
bash harness/scripts/adapters/codex-verify.sh
```

Result: PASS. Asserts `~/.codex/AGENTS.md` and `~/.agents/skills/core/SKILL.md`
resolve in an isolated HOME.

Statuses: `policy_file`, `skill_discovery`, `nested_skill_aliases` supported;
permissions/config/project/uninstall remain `partial` until contract tests
exist.
