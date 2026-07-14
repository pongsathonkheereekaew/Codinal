# DSP Programming Standards (Easby Plugins)

## 1. Safety & Audio Quality (Clamping Curves)
- Ensure all gain coefficient calculations, feedback loops, and wave-shaping lookup tables are properly bounded.
- Apply clamping curves where necessary to avoid rendering artifacts or sudden digital overflows/explosions.

## 2. Headless Verification Gates
- Never weaken, bypass, or comment out any assertions/tests inside `Tools/verify.py` or `./verify.sh` to make a failing run pass.
- A task is considered "complete" only when `./verify.sh` returns `exit 0` showing a clean green pass on the acceptance suite.

## 3. Scope of Modifications
- Treat user-reported bug locations as hypotheses. Run a sweep/trace to confirm the exact code paths before editing.
- Do not introduce unrequested abstractions or structural modifications (keep code changes surgical).

## 4. Dual-Axis Verification & Self-Review (Concept from mattpocock/code-review)
- **Verification Routine**: When testing any change via `./verify.sh`, enforce two review axes internally:
  1. **Compliance Axis**: Ensure the code satisfies constraints (e.g., gain clamping, DSP boundary checks, font constraints).
  2. **Specification Axis**: Double-check that the code fully covers the task description without skipping edge-case paths.
