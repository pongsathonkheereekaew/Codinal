# Gemini CLI adapter verification

```bash
bash harness/scripts/adapters/gemini-cli-verify.sh
```

Result: PASS. Asserts `~/.gemini/GEMINI.md`, `~/.gemini/skills`,
`~/.agents/skills`, and `~/.gemini/policies` in an isolated HOME.

Statuses: `policy_file`, `skill_discovery`, `nested_skill_aliases` supported;
`native_permissions` partial (user-policy TOML mechanism declared, no contract
test yet).
