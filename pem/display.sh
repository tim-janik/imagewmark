#!/bin/bash
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
# Display PEM metrics JSON as a human-readable table.
# Usage:
#   bash display.sh < result.json
#   bash display.sh result1.json [result2.json ...]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$SCRIPT_DIR/.venv/bin/python3"

if [ ! -f "$PYTHON" ]; then
    echo "Error: bundled Python not found — run 'make -C $SCRIPT_DIR -f Makefile.mk setup' first" >&2
    exit 1
fi

unset PYTHONHOME PYTHONPATH

exec "$PYTHON" "$SCRIPT_DIR/display.py" "$@"
