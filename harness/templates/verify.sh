#!/bin/bash
# verify.sh: Smart Verification and DSP Safety Gate

set -e

echo "=== Running project verification ==="

# 1. Compile check (YAGNI - standard compile checking)
echo "Checking build status..."
if [ -d "build" ]; then
    cmake --build build --config Debug
else
    echo "No build directory found. Please run cmake setup first."
    exit 1
fi

# 2. Run DSP & Acceptance Tests
# ponytail: Simple script check, upgrade to pedalboard/scipy test runner when adding complex audio verification
if [ -f "Tools/verify.py" ]; then
    echo "Executing python verification suite..."
    python3 Tools/verify.py
else
    echo "No custom python verification suite (verify.py) found, skipping."
fi

echo "=== All checks passed! exit 0 ==="
