#!/usr/bin/env bash
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#
# Summarize .mdiff files: global field stats + per-file change counts.
#
# Usage: mdiff-summary.sh file.mdiff [file2.mdiff ...]
#        find . -name '*.mdiff' | xargs mdiff-summary.sh

set -euo pipefail

tmpfile=$(mktemp)
trap 'rm -f "$tmpfile"' EXIT

total=0
files_with_changes=0
declare -A counts

for mdiff in "$@"; do
  [ -f "$mdiff" ] || continue

  # Extract removed lines (not diff headers), count them, collect field names
  removed=$(sed -n '/^-[^-]/{ s/^.//; p; }' "$mdiff")
  count=$(echo "$removed" | grep -c . || true)

  if [ "$count" -gt 0 ]; then
    total=$((total + count))
    files_with_changes=$((files_with_changes + 1))
    counts["$mdiff"]=$count

    # Extract field names (first word-like token on each line)
    echo "$removed" | sed -E 's/^ +//; s/ *[: ] .*//; s/ *=.*//;' >> "$tmpfile" || true
  fi
done

echo "Files with metadata changes:"
for mdiff in "${!counts[@]}"; do
  printf "%6d  %s\n" "${counts[$mdiff]}" "$mdiff"
done | sort -n
echo ""

if [ -s "$tmpfile" ]; then
  echo "Changes by field name:"
  sort "$tmpfile" | uniq -c | sort -n
  echo ""
fi

echo "=== Metadata Diff Summary ==="
echo "Files with changes: $files_with_changes"
echo "Total metadata changes: $total"
echo ""

