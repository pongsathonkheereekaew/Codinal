---
description: Audit whole repo for over-engineering — what can be deleted (on-demand)
allowed-tools: Bash(git ls-files:*)
argument-hint: "[optional subdir to scope]"
---

Files in scope:

!`git ls-files $ARGUMENTS`

Audit the repository above for over-engineering only, not correctness. Read the files yourself; scan the whole tree, not a diff. One line per finding, ranked biggest cut first: <tag> <what to cut>. <replacement>. [path]. Tags: delete (dead code/speculative feature), stdlib (reinvented standard library), native (dependency doing what the platform does), yagni (abstraction with one implementation), shrink (same logic, fewer lines). End with the net lines and dependencies removable. If nothing to cut: 'Lean already. Ship.'
