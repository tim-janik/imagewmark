#!/bin/bash
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
set -Eeuo pipefail

VERBOSE=false
test ".${1-}" == .-x && { shift ; set -x ; }
test ".${1-}" == .-v && { shift ; VERBOSE=true ; }

wmops=${1:-cxx/wmops}
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
ERRORS=false

get_quality()
{
  local rc=0
  "$wmops" jpeg-quality "$1" || { rc=$?; printf '%s: WARNING: %s jpeg-quality failed (exit %s)\n' "${1##*/}" "$wmops" "$rc" >&2; ERRORS=true; }
}

expect_exact()
{
  local path=$1 expected=$2 quality
  quality=$(get_quality "$path")
  if test "$quality" = "$expected"; then
    test "$VERBOSE" != true || printf '%s: expected jpeg-quality %s, got %s\n' "${path##*/}" "$expected" "$quality"
  else
    printf '%s: expected jpeg-quality %s, got %s\n' "${path##*/}" "$expected" "${quality:-<empty>}" >&2
    ERRORS=true
  fi
}

expect_fallback()
{
  local name=$1 bytes=$2
  printf '%b' "$bytes" > "$tmpdir/$name.jpg"
  expect_exact "$tmpdir/$name.jpg" -1
}

expect_quality()
{
  local path=$1 expected=$2 quality
  quality=$(get_quality "$path")
  if [[ ! $quality =~ ^[0-9]+$ ]] || (( quality < expected - 2 || quality > expected + 2 )); then
    printf '%s: expected jpeg-quality %s +/- 2, got %s\n' "${path##*/}" "$expected" "${quality:-<empty>}" >&2
    ERRORS=true
  else
    test "$VERBOSE" != true || printf '%s: expected jpeg-quality %s +/- 2, got %s\n' "${path##*/}" "$expected" "$quality"
  fi
}

expect_fallback empty ''
expect_fallback one-byte '\377'
expect_fallback truncated-dqt '\377\330\377\333\000\103\000'

convert -size 200x200 plasma:fractal "$tmpdir/source.png"
expect_exact "$tmpdir/source.png" -1
for q in 51 76 97 ; do
  convert "$tmpdir/source.png" -quality "$q" "$tmpdir/im_q$q.jpg"
  expect_quality "$tmpdir/im_q$q.jpg" "$q"
done

convert "$tmpdir/source.png" -quality 73 -interlace Plane "$tmpdir/im_prog_q76.jpg"
expect_quality "$tmpdir/im_prog_q76.jpg" 73
convert "$tmpdir/source.png" -colorspace Gray -quality 84 "$tmpdir/im_gray_q80.jpg"
expect_quality "$tmpdir/im_gray_q80.jpg" 84
convert "$tmpdir/source.png" -colorspace CMYK -quality 87 "$tmpdir/im_cmyk_q80.jpg"
expect_quality "$tmpdir/im_cmyk_q80.jpg" 87

printf '%b' '\377\330\377\341\372\002' > "$tmpdir/large-app1.jpg"
printf '%b' '\377\333\000\103\000' >> "$tmpdir/large-app1.jpg"
for _ in $(seq 1 64); do printf '\001' >> "$tmpdir/large-app1.jpg"; done
head -c 63931 /dev/zero | tr '\000' A >> "$tmpdir/large-app1.jpg"
tail -c +3 "$tmpdir/im_q97.jpg" >> "$tmpdir/large-app1.jpg"
expect_quality "$tmpdir/large-app1.jpg" 97

printf '%b' '\377\330\377\333\000\103\000' > "$tmpdir/short-header.jpg"
for _ in $(seq 1 64); do printf '\001' >> "$tmpdir/short-header.jpg"; done
printf '%b' '\377\341\377\377' >> "$tmpdir/short-header.jpg"
expect_exact "$tmpdir/short-header.jpg" -1

printf '%b' '\377\330\377\340\000\107\377\333\000\103\000' > "$tmpdir/app-dqt.jpg"
for _ in $(seq 1 64); do printf '\001' >> "$tmpdir/app-dqt.jpg"; done
printf '%b' '\377\331' >> "$tmpdir/app-dqt.jpg"
expect_exact "$tmpdir/app-dqt.jpg" -1

printf '%b' '\377\330\377\333\000\303\040' > "$tmpdir/invalid-precision.jpg"
for _ in $(seq 1 192); do printf '\001' >> "$tmpdir/invalid-precision.jpg"; done
printf '%b' '\377\331' >> "$tmpdir/invalid-precision.jpg"
expect_exact "$tmpdir/invalid-precision.jpg" -1

# hand-built JPEG: fake markers inside COM, 0xff fill resync, junk DQT after EOI;
# all-1 quant table => top-range estimate
printf '%b' '\377\330\377\340\000\004\001\002\377\376\000\006\377\340\377\377\377\333\000\103\000' > "$tmpdir/valid.jpg"
for _ in $(seq 1 64); do printf '\377' >> "$tmpdir/valid.jpg"; done
printf '%b' '\377\333\000\103\000' >> "$tmpdir/valid.jpg"
for _ in $(seq 1 64); do printf '\001' >> "$tmpdir/valid.jpg"; done
printf '%b' '\377\331\377\333\000\103\000' >> "$tmpdir/valid.jpg"
for _ in $(seq 1 64); do printf '\377' >> "$tmpdir/valid.jpg"; done
quality=$(get_quality "$tmpdir/valid.jpg")
if [[ ! $quality =~ ^[0-9]+$ ]] || (( quality <= 90 || quality > 100 )); then
  printf '%s: expected jpeg-quality 91..100, got %s\n' valid.jpg "${quality:-<empty>}" >&2
  ERRORS=true
else
  test "$VERBOSE" != true || printf 'valid.jpg: expected jpeg-quality 91..100, got %s\n' "$quality"
fi

# 16-bit luma DQT (Pq=1, len 131 = 2+1+64*2) with saturated 65535 values:
# an 8-bit misread hits invalid precision => -1; correct parse bottoms out at the 50 floor
printf '%b' '\377\330\377\333\000\203\020' > "$tmpdir/valid-16bit.jpg"
for _ in $(seq 1 64); do printf '%b' '\377\377' >> "$tmpdir/valid-16bit.jpg"; done
printf '%b' '\377\331' >> "$tmpdir/valid-16bit.jpg"
expect_exact "$tmpdir/valid-16bit.jpg" 50

test "$ERRORS" = false || { printf '%-8s%s\n' FAIL 'jpeg-quality checks' >&2; exit 1; }
printf '%-8s%s\n' OK 'jpeg-quality checks'
