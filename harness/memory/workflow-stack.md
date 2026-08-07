---
name: workflow-stack
description: "Locked Claude Code workflow stack — winner per job, what's disabled, what was rejected"
metadata: 
  node_type: memory
  type: project
  originSessionId: facadea4-6150-49fc-b019-43bee62266f9
---

Consolidated 2026-06-27 from an overlapping pile (karpathy, matt, rtk, ECC, superpowers, claude-mem, harness, caveman, claudeclaw).

**Winners per job:** memory → claude-mem (episodic) + `~/.agents/memory/` (durable) · coding spine → Matt skills in `~/.agents` (`grilling` / `implement` / `tdd` / `wayfinder` / `handoff` / `code-review`) · Superpowers (selective SSOT: `verification-before-completion`, `using-git-worktrees`, `finishing-a-development-branch` + Claude plugin for fan-out only) · deep review → `/review-pr` + `code-review` · write/optimize skills → `skill-creator` (Anthropic) + `writing-great-skills` · web design → ui-ux-pro-max · native mac → macos-design · design-system → Figma MCP · a11y → a11y-architect agent · code-trim → ponytail (on-demand only) · token → rtk+lowfat+caveman · docs → WebFetch · quality overlay → karpathy-guidelines.

**Disabled/removed:** claude-code-harness (edit-blocking deny-hooks + 7.3GB harness-mem) · **ECC REMOVED 2026-06-27** — scrutinize found it was the dominant token tax (574 skills + 253 agents loaded every session for 3 used features); extracted its crown jewels first (/review-pr command + code-reviewer/comment-analyzer/pr-test-analyzer/silent-failure-hunter/type-design-analyzer/code-simplifier + a11y-architect agents → ~/.claude/{commands,agents}), then disabled the plugin · claudeclaw · Cloudflare skill pack. Standalone agents now 64 (57 kept + 7 ECC jewels); the earlier "210→57" claim was misleading while 253 ECC agents still loaded — removal made it real.

**Rejected / do not centralize:** 9arm · openwolf · full GSD pack (overlaps Matt spine) · full Superpowers dump (use selective + Claude plugin) · ultra-review duplicates · context-mode in `~/.agents` (Claude-private runtime) · claude-mem in `~/.agents` (episodic stays under `~/.claude`) · **OpenWorker / aisuite / Tauri coworker runtime** (2026-07-24) — adopt risk/inbox/standing/scheduler/persona/orchestration as **harness policy + skills only** (`agent-guardrails`, `persona-manifest`, `orchestrating-workers`); do not port the desktop product into `~/.agents`.

**Why:** one spine + one memory beats five overlapping stacks — the original setup triple-captured memory and had harness deny-hooks fighting superpowers, costing tokens and fragmenting recall. Matt spine + selective Superpowers + claude-mem is the locked shape (2026-07-18). Universal fan-out SSOT is `orchestrating-workers` (multi-AI); Claude Superpowers remains adapter mapping only.

**How to apply:** route per `~/.agents/AGENTS.md` + tool adapter; never re-add a competing spine/memory (see [[memory-ssot]]); when tempted to install a new repo, default to subtract. Long tasks use [[goal-loop]]. Install new portable skills into `~/.agents/skills` (via CEDIA repo) then `harness sync` — never `skills add -a '*'` into adapter dirs as real copies.
