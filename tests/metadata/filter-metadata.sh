#!/usr/bin/env bash
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#
# Filter raw metadata output (.mdata) to keep only interesting lines.
# All patterns are ^-anchored to avoid false positives from mid-line matches.
# Strips noise: filenames, sizes, timestamps, permissions, inodes,
# processing timing, histograms, hex dumps, ICC LUT arrays, bare numbers.
#
# Usage: filter-metadata.sh < file.mdata    # stdin
#        filter-metadata.sh file.mdata ...   # file args
#        cat file.mdata | filter-metadata.sh

set -euo pipefail

# Patterns to IGNORE (noise to filter out).
# Shared with mdiff-summary.sh — keep in sync or refactor further.
IGNORE_PATTERNS=(
  # Filename / path references
  '^File:'
  '^[[:space:]]*FILE:'
  '^[[:space:]]*File Name[[:space:]]'
  '^[[:space:]]*File name[[:space:]]'
  '^[[:space:]]*Filename:'
  '^[[:space:]]*filename:'
  '^[[:space:]]*filename='
  '^[[:space:]]*Complete name'
  '^[[:space:]]*Directory'

  # Tool version / format info (redundant with file command)
  '^[[:space:]]*ExifTool Version Number'
  '^[[:space:]]*File Type[[:space:]]'
  '^[[:space:]]*MIME Type'
  '^[[:space:]]*STRUCTURE OF JPEG FILE:'
  '^[[:space:]]*render:'
  '^[[:space:]]*"@ref":'
  '^[[:space:]]*"media":'

  # File size (exiftool, mediainfo, ffprobe)
  '^[[:space:]]*File Size[[:space:]]'
  '^[[:space:]]*File size[[:space:]]'
  '^[[:space:]]*File[sS]ize'
  '^[[:space:]]*Stream size'
  '^[[:space:]]*StreamSize'
  '^[[:space:]]*"FileSize":'
  '^[[:space:]]*"StreamSize":'

  # Timestamps (exiftool, mediainfo, imagemagick)
  '^[[:space:]]*File Modification Date'
  '^[[:space:]]*File Access Date'
  '^[[:space:]]*File Inode Change Date'
  '^"File_Modified_Date'
  '^"File_Modified_Date_Local'
  '^    date:create:'
  '^    date:modify:'
  '^    date:timestamp:'
  '^[0-9]{4}:[0-9]{2}:[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}'

  # Permissions (exiftool, imagemagick)
  '^[[:space:]]*File Permissions'
  '^[[:space:]]*Permissions:'
  '^-[rwx-]+$'

  # Processing timing
  '^[[:space:]]*Pixels per second'
  '^[[:space:]]*User time'
  '^[[:space:]]*Elapsed time'

  # Histogram/statistics (ImageMagick identify -verbose)
  '^[[:space:]]+(mean|median|standard deviation|kurtosis|skewness|entropy|min|max):'

  # Signature/hash
  '^[[:space:]]*signature:'

  # Internal offsets
  '^[[:space:]]*Thumbnail Offset'
  '^[[:space:]]*Exif\.Thumbnail\.JPEGInterchangeFormat'
  '^[[:space:]]*Exif\.Photo\.InteroperabilityTag'
  '^[[:space:]]*Exif\.Image\.GPSTag'
  '^[[:space:]]*Exif\.MakerNote\.Offset'
  '^[[:space:]]*chunk \w+ at offset \w+, length'

  # DONE marker
  '^  DONE:'

  # Diff hunk headers (if filtering mdiff output)
  '^@@'

  # Bare numbers / sizes
  '^[0-9]+$'
  '^[0-9.]+[[:space:]]*(kB|KB|KiB|MB|Bytes|B)$'
  '^[0-9]+(\.[0-9]+)*$'
  '^[[:space:]]*[0-9]+,[0-9]+$'

  # JPEG segment structure lines
  '^[[:space:]]*[0-9]+[[:space:]]*\|'

  # Magick/vips summary line (filename + dimensions, only filename differs)
  '^:[[:space:]]*[0-9]+x[0-9]+[[:space:]]'
  '^[^:]+:[[:space:]]*[0-9]+x[0-9]+[[:space:]]+(uchar|srgb|char)[, ]'

  # Profile lines from identify
  '^[[:space:]]*Profile-'

  # Bare filename lines
  '^[A-Za-z0-9_][A-Za-z0-9_. -]*\.(jpg|jpeg|tiff|tif|png|heic|HEIC)$'

  # quality: from identify
  '^[[:space:]]*quality:'

  # Binary data (exiv2 -pa awk filter + exiftool grep handle most; these catch remaining edge cases)
  '^[0-9 ]{20,}'
  '^0x[0-9a-fA-F]+$'
  '^[0-9]+( [0-9]+){5,}'

  # ICC profile LUT entries (TIFF palette/colormap)
  '^[[:space:]]*[0-9]+:[[:space:]]*[()]'

  # Empty/whitespace lines
  '^[[:space:]]*$'
)

# Build combined regex
IGNORE_RE=$(printf "%s|" "${IGNORE_PATTERNS[@]}")
IGNORE_RE="${IGNORE_RE%|}"

# If no args, read from stdin. Otherwise process each file.
if [ $# -eq 0 ]; then
  grep -vE "$IGNORE_RE"
else
  for f in "$@"; do
    grep -vE "$IGNORE_RE" "$f"
  done
fi
