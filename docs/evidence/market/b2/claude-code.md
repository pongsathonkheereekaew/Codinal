# Claude Code adapter verification

Date: 2026-08-08.

```bash
bash harness/scripts/adapters/claude_verify.sh
```

Result: PASS. The smoke creates an isolated `$HOME/.claude` layout and asserts:

- `~/.claude/CLAUDE.md` exists (policy_file)
- `~/.claude/skills` exists (skill_discovery)
- `~/.claude/commands` exists (command_dir)

Statuses in `harness/config/hosts.yaml`:

- `policy_file`, `skill_discovery`, `command_dir`: supported
- `native_permissions`, `config_merge`, `project_override`,
  `uninstall_ownership`: partial (layout proven, permission contract not yet
  exercised)
