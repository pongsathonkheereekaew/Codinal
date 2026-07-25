---
description: Review current git diff for over-engineering — what can be deleted (on-demand, never auto)
allowed-tools: Bash(git diff:*)
argument-hint: "[optional path or ref to diff]"
---

Current changes to review:

!`git diff $ARGUMENTS`

Review the diff above for over-engineering only, not correctness. One line per finding: L<line>: <tag> <what to cut>. <replacement>. Tags: delete (dead code/speculative feature), stdlib (reinvented standard library), native (dependency doing what the platform does), yagni (abstraction with one implementation), shrink (same logic, fewer lines). End with the net lines removable. If nothing to cut: 'Lean already. Ship.'
