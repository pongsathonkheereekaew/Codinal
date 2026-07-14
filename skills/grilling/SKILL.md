---
name: grilling
description: >-
  Grill the user relentlessly about a plan or design. Use when the user wants to
  stress-test a plan before building, says "grill me", uses any grill trigger, or
  wants a grilling session that also updates domain docs.
---

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time, waiting for feedback on each question before continuing. Asking multiple questions at once is bewildering.

If a *fact* can be found by exploring the codebase, look it up rather than asking me. The *decisions*, though, are mine — put each one to me and wait for my answer.

Do not enact the plan until I confirm we have reached a shared understanding.

## Optional: leave a paper trail

When the user is in a real codebase (or asks to create ADRs / glossary / CONTEXT as you go), also follow the `domain-modeling` skill so resolved terms and decisions land in the project's domain docs. Skip this when there is no repo / no docs to update.

## After a written plan

If this session produces a written plan intended as final to ship, run `scrutinize` next before presenting it as done.
