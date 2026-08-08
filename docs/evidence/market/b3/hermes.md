# Hermes adapter verification

```bash
bash harness/scripts/adapters/hermes-verify.sh
```

Result: PASS. Asserts `~/.hermes/config.yaml` declares
`skills.external_dirs` pointing at `~/.agents/skills` and that the skill
directory resolves.

Statuses: `skill_discovery` supported; `nested_skill_aliases` partial;
`policy_file` remains behavioral fallback (`partial`).
