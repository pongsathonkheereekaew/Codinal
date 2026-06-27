---
name: workflow-stack
description: "Locked Claude Code workflow stack — winner per job, what's disabled, what was rejected"
metadata: 
  node_type: memory
  type: project
  originSessionId: facadea4-6150-49fc-b019-43bee62266f9
---

Consolidated 2026-06-27 from an overlapping pile (karpathy, matt, rtk, ECC, superpowers, claude-mem, harness, caveman, claudeclaw).

**Winners per job:** memory → claude-mem · coding spine → superpowers · deep review → /review-pr (standalone, fans out to code-reviewer + silent-failure-hunter + pr-test/type/comment/simplify) · spec/issues/handoff → matt pocock (to-prd/to-issues/handoff/zoom-out) · web design → ui-ux-pro-max · native mac → macos-design · design-system → Figma MCP · a11y → a11y-architect agent · code-trim → ponytail (on-demand only) · token → rtk+lowfat+caveman · docs → WebFetch · quality overlay → karpathy-guidelines.

**Disabled/removed:** claude-code-harness (edit-blocking deny-hooks + 7.3GB harness-mem) · **ECC REMOVED 2026-06-27** — scrutinize found it was the dominant token tax (574 skills + 253 agents loaded every session for 3 used features); extracted its crown jewels first (/review-pr command + code-reviewer/comment-analyzer/pr-test-analyzer/silent-failure-hunter/type-design-analyzer/code-simplifier + a11y-architect agents → ~/.claude/{commands,agents}), then disabled the plugin · claudeclaw · Cloudflare skill pack. Standalone agents now 64 (57 kept + 7 ECC jewels); the earlier "210→57" claim was misleading while 253 ECC agents still loaded — removal made it real.

**Rejected:** 9arm (redundant), openwolf (2nd memory SSOT + hook collisions; "fewer tokens" = advisory hint not compression).

**Why:** one spine + one memory beats five overlapping stacks — the original setup triple-captured memory and had harness deny-hooks fighting superpowers, costing tokens and fragmenting recall. Superpowers is lightest + full-lifecycle; ECC kept only for its crown jewels (/review-pr, context7, a11y).

**How to apply:** route per the table in ~/.claude/CLAUDE.md; never re-add a competing spine/memory (see [[memory-ssot]]); when tempted to install a new repo, default to subtract. Long tasks use [[goal-loop]].
