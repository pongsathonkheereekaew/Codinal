#!/bin/bash
# install.sh: One-Command Installer for harness-flow workspace

set -e

echo "=== Starting harness-flow installation ==="

# 1. คัดลอกกฎของ Cursor ไปยังพิกัด Global
echo "1. Installing Global Cursor Rules..."
mkdir -p ~/.cursor/rules
cp -f .cursor/rules/*.mdc ~/.cursor/rules/ 2>/dev/null || echo "No custom rules to copy yet, skipping. (Rules will be managed directly in ~/.cursor/rules/)"

# 2. คัดลอกและตั้งค่าของ Hermes
echo "2. Setting up Hermes Agent configuration..."
mkdir -p ~/.hermes
if [ -d "hermes" ]; then
    cp -rf hermes/* ~/.hermes/
    echo "Hermes configurations copied to ~/.hermes"
else
    echo "No hermes directory found in repository."
fi

# 3. ให้คำแนะนำผู้ใช้
echo "=== Installation Completed Successfully! ==="
echo "Next Steps:"
echo "1. If you are on a new machine, make sure to install Cursor IDE and Hermes Agent."
echo "2. Your global rules are now active at ~/.cursor/rules/"
echo "3. Run your local project test suites with ./verify.sh"
