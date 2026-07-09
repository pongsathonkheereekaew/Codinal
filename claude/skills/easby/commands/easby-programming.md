---
description: Plugin DSP knowledge base — algorithms, formulas, params, FFI contracts; emit CLEAN-only BuildSpec for product (easby-programming)
---
Follow ~/.claude/skills/easby/easby-programming/SKILL.md as the active process for this task.

Query / task: $ARGUMENTS

Rules:
- This skill is the sole holder of REF (reference-only / disasm-derived) facts. Never hand REF to product code.
- For any product/build output emit a BuildSpec filtered to CLEAN only (black-box measurement + public DSP literature + own voicing), with provenance_gate:"CLEAN_ONLY".
- Doing the RE itself (taking a binary apart) is NOT this skill → route to easby-decomp (/decomp).
- Reference implementation craft in implementation-doctrine.md + building-blocks/.
