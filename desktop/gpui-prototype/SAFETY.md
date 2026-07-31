# G3 safety-surface contract

The prototype is read-only. Its first Rust-native slice renders session metadata
and ordered messages from an isolated snapshot through `ControlPlaneClient`.
Safety resources remain unavailable until their Rust routes pass parity.

Before a production GPUI shell gains any mutation route, it must implement this
sequence in one native reducer:

1. Load the current approval/evidence and candidate Git diff.
2. Render the risk, command/evidence, and affected paths before enabling the
   action.
3. Require an explicit native confirmation with a visible cancel path.
4. POST only the exact approval/apply payload to the authenticated Rust runtime.
5. Reload audit, evidence, Git, and worker state from the runtime result.

No client-side state can treat an approval as resolved, an apply as successful,
or evidence as durable until the runtime replies successfully. During shadow
mode the Python runtime remains the production persistence authority.
