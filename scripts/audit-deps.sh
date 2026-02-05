#!/bin/sh
# Run dependency CVE audit for Vigil backend (see docs/SYSTEM_RATING.md, docs/OPTIMIZATION_AUDIT.md).
set -e
cd "$(dirname "$0")/.."

echo "=== Vigil dependency audit ==="
PIP="${PIP:-pip}"
if ! command -v "$PIP" >/dev/null 2>&1; then
  PIP="python3 -m pip"
fi
if $PIP audit 2>/dev/null; then
  echo "Done (pip audit)."
elif command -v pip-audit >/dev/null 2>&1; then
  pip-audit
  echo "Done (pip-audit)."
else
  echo "Installing pip-audit..."
  $PIP install pip-audit
  pip-audit
  echo "Done."
fi
