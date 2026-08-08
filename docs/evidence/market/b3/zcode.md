# ZCode adapter verification

```bash
bash harness/scripts/adapters/zcode-verify.sh
```

Result: PASS. Asserts `~/.zcode/AGENTS.md`, `~/.zcode/skills`, and
`~/.zcode/commands`.

Statuses: `policy_file`, `skill_discovery`, `nested_skill_aliases`,
`command_dir` supported; other capabilities remain `partial`.
