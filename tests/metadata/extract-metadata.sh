#!/usr/bin/env bash
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#
# Extract every available metadata field from image files using various metadata extractors.
#
# Usage: extract-metadata.sh <image> [image2...]
#        find images/ -type f | xargs extract-metadata.sh
set -euo pipefail

# -- helpers --
die() { echo "ERROR: $*" >&2; exit 1; }
section() { echo; echo "================================================================"; echo "  $1"; echo "================================================================"; }
subsection() { echo; echo "--- $1 ---"; }
run() { "$@" 2>&1 || true; }
run_if() { local fmt="$1"; shift; [[ "${file_fmt,,}" == *"${fmt,,}"* ]] && "$@" 2>&1 || true; }

[ $# -eq 0 ] && die "usage: $0 <image> [image2 ...]"

for filepath in "$@"; do
  [ -f "$filepath" ] || die "not a file: $filepath"

  section "FILE: $filepath"

  # -- file type detection --
  subsection "File type"
  file -bL "$filepath"
  file -bL --mime "$filepath"

  # -- detect format for conditional tools --
  file_fmt=$(file -bLi "$filepath" | sed 's/.*mime=//; s/;.*//')

  # -- exiftool (comprehensive EXIF/IPTC/XMP/metadata) --
  subsection "ExifTool (full)"
  run exiftool "$filepath"

  # -- exiv2 (EXIF/IPTC/XMP) --
  subsection "Exiv2 (summary)"
  run exiv2 -pa "$filepath"

  # -- ImageMagick identify --
  subsection "ImageMagick identify (verbose)"
  run identify -verbose "$filepath"

  # -- vipsheader --
  subsection "vipsheader (with metadata)"
  run vipsheader --vips "$filepath"

  # -- jhead (JPEG EXIF) --
  subsection "jhead (JPEG EXIF/IPTC)"
  run_if jpeg jhead "$filepath"

  # -- jpeginfo (JPEG structure) --
  subsection "jpeginfo (JPEG markers + comments)"
  run_if jpeg jpeginfo -c "$filepath" | sed 's/^/jpeginfo: /'

  # -- rdjpgcom (JPEG comments) --
  subsection "rdjpgcom (JPEG text comments)"
  run_if jpeg rdjpgcom "$filepath"

  # -- jpegexiforient (JPEG EXIF orientation) --
  subsection "jpegexiforient (JPEG EXIF orientation tag)"
  run_if jpeg jpegexiforient "$filepath"

  # -- pngcheck (PNG structure) --
  subsection "pngcheck (PNG chunk analysis)"
  run_if png pngcheck -v "$filepath"

  # -- tiffinfo / tiffdump (TIFF structure) --
  subsection "tiffinfo (TIFF IFD dump)"
  run_if tiff tiffinfo "$filepath"

  subsection "tiffdump (TIFF raw dump)"
  run_if tiff tiffdump "$filepath"

  # -- webpinfo (WebP structure) --
  subsection "webpinfo (WebP chunk structure)"
  run_if webp webpinfo "$filepath"

  # -- heif-info (HEIF/HEIC info) --
  subsection "heif-info (HEIF/HEIC structure)"
  run_if heif heif-info "$filepath"
  run_if heic heif-info "$filepath"

  # -- ffprobe (container + codec metadata) --
  subsection "ffprobe (streams)"
  run ffprobe -v quiet -show_streams "$filepath"

  subsection "ffprobe (format)"
  run ffprobe -v quiet -show_format "$filepath"

  # -- mediainfo --
  subsection "MediaInfo"
  run mediainfo "$filepath"

  # -- netpbm (cross-format info) --
  subsection "pamfile (NetPBM file info)"
  run pamfile "$filepath"

  # -- GIF animation dump --
  subsection "anim_dump (GIF animation frames)"
  run_if gif anim_dump "$filepath" 2>&1 || true

  section "DONE: $filepath"
done
