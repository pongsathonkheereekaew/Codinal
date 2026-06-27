---
name: workflow-stack
description: "Locked Claude Code workflow stack — winner per job, what's disabled, what was rejected"
metadata: 
  node_type: memory
  type: project
  originSessionId: facadea4-6150-49fc-b019-43bee62266f9
---

Consolidated 2026-06-27 from an overlapping pile (karpathy, matt, rtk, ECC, superpowers, claude-mem, harness, caveman, claudeclaw).

**Winners per job:** memory → claude-mem · coding spine → superpowers · deep review → /ecc:review-pr · spec/issues/handoff → matt pocock (to-prd/to-issues/handoff/zoom-out) · web design → ui-ux-pro-max · native mac → macos-design · design-system → Figma MCP · a11y → ecc a11y-architect · code-trim → ponytail (on-demand only) · token → rtk+lowfat+caveman+ecc strategic-compact · docs → ecc context7 MCP · quality overlay → karpathy-guidelines.

**Disabled:** claude-code-harness (removed — edit-blocking deny-hooks + 7.3GB harness-mem) · ECC minimal (ECC_HOOK_PROFILE=minimal, SESSION_START_MAX_CHARS=0, disabled MCPs exa/github/memory/playwright/sequential-thinking) · claudeclaw · ECC design-* swarm + redundant planners. Pruned 210→57 agents (rest in ~/.claude/agents-archive/).

**Rejected:** 9arm (redundant), openwolf (2nd memory SSOT + hook collisions; "fewer tokens" = advisory hint not compression).

**Why:** one spine + one memory beats five overlapping stacks — the original setup triple-captured memory and had harness deny-hooks fighting superpowers, costing tokens and fragmenting recall. Superpowers is lightest + full-lifecycle; ECC kept only for its crown jewels (/review-pr, context7, a11y).

**How to apply:** route per the table in ~/.claude/CLAUDE.md; never re-add a competing spine/memory (see [[memory-ssot]]); when tempted to install a new repo, default to subtract. Long tasks use [[goal-loop]].
