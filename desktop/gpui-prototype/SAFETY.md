# G3 safety-surface contract

The prototype is read-only. It may render the following sidecar resources only
through `ControlPlaneClient` descriptors: pending approvals, preview evidence,
Git status/diff, workers, checkpoints, and audit records.

Before a production GPUI shell gains any mutation route, it must implement this
sequence in one native reducer:

1. Load the current approval/evidence and candidate Git diff.
2. Render the risk, command/evidence, and affected paths before enabling the
   action.
3. Require an explicit native confirmation with a visible cancel path.
4. POST only the exact approval/apply payload to the authenticated sidecar.
5. Reload audit, evidence, Git, and worker state from the sidecar result.

No client-side state can treat an approval as resolved, an apply as successful,
or evidence as durable until the sidecar replies successfully. The sidecar
remains the persistence and authorization authority.
