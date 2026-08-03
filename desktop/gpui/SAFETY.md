# C2a/C3 Safety UI contract

The GPUI shell renders session metadata, ordered messages, provider profile,
runtime readiness, approvals, and receipts through `ControlPlaneClient`. The
Rust runtime remains the only authority for execution, approval, mutation, and
durability; the UI cannot promote a disabled capability locally.

The covered execution path implements this sequence in one native reducer:

1. Load the current approval/evidence and candidate Git diff.
2. Render the risk, command/evidence, and affected paths before enabling the
   action.
3. Require an explicit native confirmation with a visible cancel path.
4. POST only the exact approval/apply payload to the authenticated Rust runtime.
5. Reload approval, receipt, and session state from the runtime result.

No client-side state can treat an approval as resolved, an apply as successful,
or evidence as durable until the Rust runtime replies successfully. The
production path stays read-only unless Experimental execution is explicitly
enabled and the runtime readiness gate is true.

Live macOS keyboard/VoiceOver and provider smoke remain release evidence gates;
the Rust unit and fixture suites do not substitute for those observations.
