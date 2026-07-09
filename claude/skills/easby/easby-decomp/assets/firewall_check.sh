#!/usr/bin/env bash
# Clean-room firewall gate. FAILS (exit 1) if product source references TAINTED (disasm/REF) material.
# Run in CI and as a git pre-commit hook in any product repo (e.g. ES-L).
#
#   ./firewall_check.sh <product_src_dir> [<product_src_dir> ...]
#   default dir = ./Source
#
# Rationale: the CLEAN/REF firewall (easby-programming) is only real if mechanically enforced.
# Product code must be built from black-box measurement + public DSP literature ONLY — never from
# disassembly/decompilation. This catches the silent paste.
set -u
DIRS=("${@:-Source}")

# forbidden: references to quarantine/disasm artifacts + explicit REF provenance tags
PATTERNS=(
  '_quarantine_disasm'
  'decompiled\.c'
  '\bdsp\.c\b'
  'stage2\.c'
  'all_dsp\.asm'
  'process_entries\.asm'
  'ghidra_addr'
  'provenance:[[:space:]]*REF'
  '\[REF\b'
  'disasm-derived'
  'Ghidra @0x'                       # pasted decompiled address tags
)

fail=0
for d in "${DIRS[@]}"; do
  [ -d "$d" ] || { echo "firewall: dir not found: $d (skipping)"; continue; }
  for pat in "${PATTERNS[@]}"; do
    # scan source-ish files only
    hits=$(grep -rInE --include='*.cpp' --include='*.h' --include='*.hpp' --include='*.rs' \
                 --include='*.c' --include='*.cc' --include='*.mm' "$pat" "$d" 2>/dev/null)
    if [ -n "$hits" ]; then
      echo "✗ FIREWALL BREACH — product code references TAINTED material (pattern: $pat):"
      echo "$hits" | sed 's/^/    /'
      fail=1
    fi
  done
done

if [ "$fail" -ne 0 ]; then
  echo
  echo "Clean-room firewall: product code must use CLEAN only (black-box measurement + public DSP)."
  echo "Remove the reference. If you need that behaviour, emit a black-box behavior_target and measure it."
  exit 1
fi
echo "✓ firewall clean — no TAINTED references in: ${DIRS[*]}"
