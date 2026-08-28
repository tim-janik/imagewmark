#!/bin/bash
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

# Check pixel-format and colorspace handling of "imagewmark add":
# - bit depth (8/16 bit) and float pixels must survive the watermark round trip
# - alpha channels must be preserved bit-exact (except for JPEG output)
# - CMYK images must stay CMYK where the output format supports it and must
#   convert to RGB otherwise
# - EXIF and other metadata must be preserved
# - the embedded watermark must still be decodable
#
# Usage: tests/formats/check-formats.sh
# Dependencies: ImageMagick (convert, identify, compare) and imagewmark are
# required, vips and exiftool are optional (their checks are skipped).
set -Eeuo pipefail

test "${1-}" == -x && { shift ; set -x ; }

SELFDIR=$(dirname "$(readlink -f "$0")")
SRCDIR=$(dirname "$SELFDIR")/..
IMAGEWMARK=${IMAGEWMARK:-$SRCDIR/imagewmark}
WATERMARK=${WATERMARK:-fedcba98765432100123456789abcdef}

# ImageMagick tool selection: IMv7 deprecates convert/compare/identify in
# favor of magick(1) and prints a warning for each legacy invocation
if command -v magick >/dev/null 2>&1; then
  IMCONVERT="magick"
  IMIDENTIFY="magick identify"
  IMCOMPARE="magick compare"
elif command -v convert >/dev/null 2>&1; then
  IMCONVERT="convert"
  IMIDENTIFY="identify"
  IMCOMPARE="compare"
else
  echo "check-formats: skipping, missing dependency: ImageMagick"
  exit 0
fi
[ -x "$IMAGEWMARK" ] || { echo "check-formats: skipping, missing executable: $IMAGEWMARK" ; exit 0 ; }

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
cd "$tmpdir"

failures=0
checks=0
check()
{
  local name="$1"; shift
  checks=$((checks + 1))
  if "$@"; then
    echo "  OK      $name"
  else
    echo "  FAIL    $name"
    failures=$((failures + 1))
  fi
}

# check_opt <command> <name> <args...> - like check(), but skipped when <command> is unavailable
check_opt()
{
  local dep="$1" name="$2"; shift 2
  if command -v "$dep" >/dev/null 2>&1; then
    check "$name" "$@"
  else
    checks=$((checks + 1))
    echo "  SKIP    $name (no $dep)"
  fi
}

# normalized RMSE of two images, see: compare -metric RMSE
rmse()
{
  local r=$($IMCOMPARE -metric RMSE "$1" "$2" null: 2>&1 || true)
  r=$(printf '%s\n' "$r" | sed -e 's/.*(//' -e 's/).*//')
  printf '%s' "$r"
}

# colorspace_grep <file> <colorspace> - ImageMagick colorspace must match
colorspace_grep()
{
  $IMIDENTIFY -quiet -format "%[colorspace]" "$1" 2>/dev/null | grep -qi "^$2$"
}

# channels_grep <file> <channels> - ImageMagick channel set must match, e.g. rgba;
# IMv7 appends " <channels>.<meta channels>" to %[channels], e.g. "srgba 4.0"
channels_grep()
{
  $IMIDENTIFY -quiet -format "%[channels]" "$1" 2>/dev/null | grep -qiE "^$2( |$)"
}

# depth_is <file> <bits> - ImageMagick pixel depth must match
depth_is()
{
  [ "$($IMIDENTIFY -quiet -format "%z" "$1" 2>/dev/null)" == "$2" ]
}

# alpha_cmp <input> <output> - alpha channels must be bit-exact; both alpha
# extractions are normalized to 16-bit so cross depth comparisons work
alpha_cmp()
{
  $IMCONVERT "$1" -alpha extract -depth 16 "$tmpdir/alpha_in.png"
  $IMCONVERT "$2" -alpha extract -depth 16 "$tmpdir/alpha_out.png"
  local ae=$($IMCOMPARE -metric AE "$tmpdir/alpha_in.png" "$tmpdir/alpha_out.png" null: 2>&1 || true)
  ae=${ae%% *} # IMv7 appends the normalized value: "0 (0)"
  awk "BEGIN { exit !($ae == 0) }"
}

# cmyk_fidelity <input> <output> - CMYK output must keep the colors of the
# input CMYK image, only the watermark luminance delta may shift pixels
cmyk_fidelity()
{
  awk "BEGIN { exit !($(rmse "$1" "$2") < 0.1) }"
}

# float_fidelity <input> <output> - float pixels are stored in [0,1], so the
# watermark delta (~4/255) needs a tighter bound than for 8-bit images
float_fidelity()
{
  awk "BEGIN { exit !($(rmse "$1" "$2") < 0.05) }"
}

# vips_fidelity <input> <output> <threshold> - watermarked output must keep the
# colors of a libvips reference conversion of the input (converts both via
# vips colourspace so mixed colorspace outputs compare consistently)
vips_fidelity()
{
  vips colourspace "$1" "$tmpdir/v_ref.png" srgb
  vips colourspace "$2" "$tmpdir/v_out.png" srgb
  awk "BEGIN { exit !($(rmse "$tmpdir/v_ref.png" "$tmpdir/v_out.png") < $3) }"
}

# decodes <file> - watermark must still be decodable
decodes()
{
  "$IMAGEWMARK" get --json "$tmpdir/decodes.json" "$1" >/dev/null 2>&1 || return 1
  grep -qE "\b$WATERMARK\b" "$tmpdir/decodes.json"
}

# exiftool_grep <file> <tag> <pattern> - grep an EXIF tag value written by exiftool
exiftool_grep()
{
  exiftool -s "$2" "$1" 2>/dev/null | grep -q "$3"
}

# == 1. create fixtures ==
# base test image: color gradient, includes saturated regions;
# generate 16-bit first and derive 8-bit from it to avoid double quantization
$IMCONVERT -size 512x512 gradient:red-blue -depth 16 -define png:bit-depth=16 base16.png
$IMCONVERT base16.png -depth 8 base8.png
# png:color-type=6 keeps the fully opaque alpha band in the fixture, IMv7's
# PNG writer would otherwise strip it (fully opaque alpha => writes RGB)
$IMCONVERT base8.png -alpha set -define png:color-type=6 rgba8.png
$IMCONVERT base8.png -alpha set -channel A -evaluate set 60% +channel rgba8a.png
$IMCONVERT -size 512x512 gradient: -colorspace gray -depth 16 -define png:bit-depth=16 gray16.png
$IMCONVERT gray16.png -depth 8 gray8.png
$IMCONVERT gray8.png -alpha set -channel A -evaluate set 60% +channel gray8a.png
$IMCONVERT base16.png -alpha set -define png:color-type=6 -define png:bit-depth=16 rgba16.png
# 60% alpha as an absolute value: 39321/65535 == 153/255, exactly on the 8-bit
# grid, so float->8-bit alpha conversions stay bit-exact at 16-bit precision
$IMCONVERT base16.png -alpha set -channel A -evaluate set 39321 +channel -define png:bit-depth=16 rgba16a.png
$IMCONVERT gray16.png -alpha set -channel A -evaluate set 60% +channel -define png:bit-depth=16 gray16a.png
$IMCONVERT base8.png -colorspace CMYK cmyk.jpg                    # 4-band CMYK JPEG
$IMCONVERT base16.png -colorspace CMYK -depth 16 cmyk16.tif       # 4-band 16-bit CMYK TIFF
$IMCONVERT rgba8a.png -colorspace CMYK -alpha on -depth 8 cmyka.tif    # 5-band CMYK+alpha TIFF
$IMCONVERT rgba16a.png -colorspace CMYK -alpha on -depth 16 cmyka16.tif
# EXIF metadata fixture
$IMCONVERT base8.png -quality 92 exif.jpg
exiftool -overwrite_original -Artist='imagewmark-artist' -ImageDescription='imagewmark-desc' exif.jpg >/dev/null 2>&1 || :
# float fixtures: floating point TIFF pixels in [0,1]; ImageMagick cannot write
# float TIFFs (-depth 32 yields integer), so generate them via vips
if command -v vips >/dev/null 2>&1; then
  $IMCONVERT base16.png -depth 16 base16.tif
  $IMCONVERT rgba16a.png -depth 16 rgba16a.tif
  vips cast base16.tif f32.v float && vips linear f32.v f32.tif 0.00001525902189669642 0
  vips cast rgba16a.tif f32a.v float && vips linear f32a.v f32a.tif 0.00001525902189669642 0
fi

# == 2. watermark every fixture ==
for f in rgba8.png rgba8a.png gray8.png gray8a.png \
         rgba16.png rgba16a.png gray16.png gray16a.png \
         cmyk.jpg cmyk16.tif cmyka.tif cmyka16.tif exif.jpg ; do
  "$IMAGEWMARK" add "$f" "out_$f" "$WATERMARK"
done
# cross-format outputs
"$IMAGEWMARK" add rgba8a.png out_rgba8a.jpg "$WATERMARK"   # JPEG output drops alpha
"$IMAGEWMARK" add gray16.png out_gray16.jpg "$WATERMARK"   # 16-bit to 8-bit JPEG
"$IMAGEWMARK" add rgba16a.png out_rgba16.jpg "$WATERMARK"  # 16-bit+alpha to JPEG
"$IMAGEWMARK" add cmyk.jpg out_cmyk.png "$WATERMARK"       # PNG has no native CMYK, output RGB
"$IMAGEWMARK" add cmyka.tif out_cmyka.png "$WATERMARK"     # CMYKA to RGBA PNG
"$IMAGEWMARK" add cmyk16.tif out_cmyk16.jpg "$WATERMARK"   # 16-bit CMYK to 8-bit CMYK JPEG
"$IMAGEWMARK" add exif.jpg out_exif.png "$WATERMARK"       # JPEG to PNG keeps EXIF
if command -v vips >/dev/null 2>&1; then
  "$IMAGEWMARK" add f32.tif out_f32.tif "$WATERMARK"       # float round trip
  "$IMAGEWMARK" add f32a.tif out_f32a.tif "$WATERMARK"     # float+alpha round trip
  "$IMAGEWMARK" add f32.tif out_f32.png "$WATERMARK"       # float to 8-bit PNG
  "$IMAGEWMARK" add f32a.tif out_f32a.png "$WATERMARK"     # float+alpha to 8-bit PNG
fi

# == 3. pixel format, colorspace and alpha checks ==
check '8-bit RGB output keeps alpha'        channels_grep out_rgba8.png 'srgba'
check '8-bit RGBA output keeps 4 channels'  channels_grep out_rgba8a.png 'srgba'
check '8-bit output stays 8-bit'            depth_is out_rgba8a.png 8
check 'alpha preserved (8-bit RGBA)'        alpha_cmp rgba8a.png out_rgba8a.png
check 'alpha preserved (8-bit grey)'        alpha_cmp gray8a.png out_gray8a.png
check '16-bit output stays 16-bit'          depth_is out_rgba16.png 16
check '16-bit RGBA output keeps 4 channels' channels_grep out_rgba16a.png 'srgba'
check 'alpha preserved (16-bit RGBA)'       alpha_cmp rgba16a.png out_rgba16a.png
check '16-bit grey output stays 16-bit'     depth_is out_gray16.png 16
check '16-bit grey keeps 1 channel'         channels_grep out_gray16.png 'gray'
check 'alpha preserved (16-bit grey+alpha)' alpha_cmp gray16a.png out_gray16a.png
check 'JPEG output drops alpha'             channels_grep out_rgba8a.jpg 'srgb'
check '16-bit input to JPEG is 8-bit'       depth_is out_rgba16.jpg 8
check 'CMYK output stays CMYK'              colorspace_grep out_cmyk.jpg 'cmyk'
check 'CMYK colors preserved'               cmyk_fidelity cmyk.jpg out_cmyk.jpg
check 'CMYK to PNG output is RGB'           colorspace_grep out_cmyk.png 'srgb'
# the CMYK to RGB output conversion is a device level naive conversion, so it
# differs from vips' profile based reference conversion, hence the loose bound
check_opt vips 'CMYK to PNG colors preserved' vips_fidelity cmyk.jpg out_cmyk.png 0.3
check '16-bit CMYK output stays 16-bit'     depth_is out_cmyk16.tif 16
check 'CMYK stays CMYK (16-bit)'            colorspace_grep out_cmyk16.tif 'cmyk'
check 'CMYK colors preserved (16-bit)'      cmyk_fidelity cmyk16.tif out_cmyk16.tif
check '16-bit CMYK to JPEG is 8-bit CMYK'   colorspace_grep out_cmyk16.jpg 'cmyk'
check 'CMYKA TIFF keeps 5 channels'         channels_grep out_cmyka.tif 'cmyka'
check 'alpha preserved (CMYKA TIFF)'        alpha_cmp cmyka.tif out_cmyka.tif
# input and output are both converted with the same vips reference conversion,
# so only the watermark delta and conversion noise show up here
check_opt vips 'CMYKA colors preserved'     vips_fidelity cmyka.tif out_cmyka.tif 0.05
check 'CMYKA to PNG output is RGBA'         channels_grep out_cmyka.png 'srgba'
check_opt vips 'CMYKA to PNG colors preserved' vips_fidelity cmyka.tif out_cmyka.png 0.3
check 'CMYKA 16-bit TIFF keeps 5 channels'  channels_grep out_cmyka16.tif 'cmyka'
check 'alpha preserved (CMYKA 16-bit)'      alpha_cmp cmyka16.tif out_cmyka16.tif
check_opt vips 'float output stays float'           depth_is out_f32.tif 32
check_opt vips 'float output keeps 3 channels'      channels_grep out_f32.tif 'srgb'
check_opt vips 'float round trip preserves values'  float_fidelity f32.tif out_f32.tif
check_opt vips 'float+alpha output keeps 4 channels' channels_grep out_f32a.tif 'srgba'
check_opt vips 'alpha preserved (float+alpha)'      alpha_cmp f32a.tif out_f32a.tif
check_opt vips 'float to PNG output is 8-bit'       depth_is out_f32.png 8
check_opt vips 'float+alpha to PNG output is 8-bit' depth_is out_f32a.png 8
check_opt vips 'alpha preserved (float+alpha to PNG)' alpha_cmp f32a.tif out_f32a.png
check_opt exiftool 'EXIF metadata preserved (JPEG)' exiftool_grep out_exif.jpg -Artist 'imagewmark-artist'
check_opt exiftool 'EXIF metadata preserved (PNG)'  exiftool_grep out_exif.png -Artist 'imagewmark-artist'

# == 4. watermark decodability ==
# get/OpenCV cannot read 5-channel CMYK TIFFs nor 32-bit float TIFFs, so CMYKA
# and float decodability is verified via the PNG outputs
check 'watermark decodes (8-bit RGB)'          decodes out_rgba8.png
check 'watermark decodes (8-bit RGBA)'         decodes out_rgba8a.png
check 'watermark decodes (8-bit grey+alpha)'   decodes out_gray8a.png
check 'watermark decodes (16-bit RGBA)'        decodes out_rgba16a.png
check 'watermark decodes (16-bit grey)'        decodes out_gray16.png
check 'watermark decodes (16-bit grey+alpha)'  decodes out_gray16a.png
check 'watermark decodes (CMYK JPEG)'          decodes out_cmyk.jpg
check 'watermark decodes (CMYK PNG)'           decodes out_cmyk.png
check 'watermark decodes (CMYKA PNG)'          decodes out_cmyka.png
check 'watermark decodes (16-bit RGB JPEG)'    decodes out_rgba16.jpg
check 'watermark decodes (EXIF JPEG)'          decodes out_exif.jpg
check_opt vips 'watermark decodes (float to PNG)' decodes out_f32.png

if [ "$failures" -ne 0 ]; then
  echo "check-formats: $failures of $checks checks FAILED"
  exit 1
fi
echo "check-formats: all $checks checks passed"
