Status: resolved
Type: task
Blocked by: 03

## Question

How will approval, evidence, Git checkpoint/apply, worker, and audit surfaces
remain explicit, durable, and reviewable in the GPUI shell?

## Answer

The prototype remains read-only. `SAFETY.md` pins the required reducer sequence:
render sidecar-derived approval/evidence/diff first, require explicit native
confirmation, submit only the exact authenticated mutation, then reload the
sidecar's durable audit/evidence/Git/worker state. No UI state may claim a
mutation succeeded before a sidecar response.
