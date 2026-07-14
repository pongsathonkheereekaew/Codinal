---
description: RE / decompile audio plugin binary (easby-decomp process)
---
Follow ~/.claude/skills/easby/easby-decomp/SKILL.md as the active process for this task.

Target binary: $ARGUMENTS

Rules:
- Enforce the CLEAN/TAINTED clean-room firewall (read it first, non-negotiable).
- Triage cheapest track first (file/lipo/otool/nm), then Track 1 black-box (CLEAN), Track 2 static only to navigate.
- Emit a distilled per-plugin spec into easby-programming/plugins/ (use _TEMPLATE.md) + add catalog row.
