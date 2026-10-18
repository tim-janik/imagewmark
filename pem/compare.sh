#!/bin/bash
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
# Self-contained runner — bundles its own Python, works on any AMD64 Linux.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Use bundled standalone Python (no system Python needed)
PYTHON="$SCRIPT_DIR/.venv/bin/python3"

if [ ! -f "$PYTHON" ]; then
    echo "Error: bundled Python not found — run 'make -C $SCRIPT_DIR -f Makefile.mk setup' first" >&2
    exit 1
fi

unset PYTHONHOME PYTHONPATH

# metrics.py keeps the caches in pem/.cache
exec "$PYTHON" "$SCRIPT_DIR/compare.py" "$@"
