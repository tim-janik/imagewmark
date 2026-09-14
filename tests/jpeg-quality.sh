set -Eeuo pipefail

wmops=${1:-cxx/wmops}
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT

expect_fallback()
{
  local name=$1 bytes=$2
  printf '%b' "$bytes" > "$tmpdir/$name.jpg"
  test "$("$wmops" jpeg-quality "$tmpdir/$name.jpg")" = -1
}

expect_fallback empty ''
expect_fallback one-byte '\377'
expect_fallback truncated-dqt '\377\330\377\333\000\103\000'
expect_fallback app-marker '\377\330\377\340\000\010\377\333\000\103\000\000\377\331'

printf '%b' '\377\330\377\333\000\103\040' > "$tmpdir/invalid-precision.jpg"
for _ in $(seq 1 64); do printf '\000' >> "$tmpdir/invalid-precision.jpg"; done
printf '%b' '\377\331' >> "$tmpdir/invalid-precision.jpg"
test "$("$wmops" jpeg-quality "$tmpdir/invalid-precision.jpg")" = -1

printf '%b' '\377\330\377\333\000\103\000' > "$tmpdir/valid.jpg"
for _ in $(seq 1 64); do printf '\001' >> "$tmpdir/valid.jpg"; done
printf '%b' '\377\331' >> "$tmpdir/valid.jpg"
quality=$("$wmops" jpeg-quality "$tmpdir/valid.jpg")
test "$quality" -ge 50
test "$quality" -le 100

printf '%b' '\377\330\377\333\000\203\020' > "$tmpdir/valid-16bit.jpg"
for _ in $(seq 1 64); do printf '%b' '\377\377' >> "$tmpdir/valid-16bit.jpg"; done
printf '%b' '\377\331' >> "$tmpdir/valid-16bit.jpg"
test "$("$wmops" jpeg-quality "$tmpdir/valid-16bit.jpg")" = 50

printf '%b' '\377\330\377\333\000\103\000' > "$tmpdir/dnl.jpg"
for _ in $(seq 1 64); do printf '\001' >> "$tmpdir/dnl.jpg"; done
printf '%b' \
  '\377\300\000\013\010\000\000\000\001\001\001\021\000' \
  '\377\332\000\010\001\001\000\000\077\000\001' \
  '\377\334\000\004\000\100\002\377\331' >> "$tmpdir/dnl.jpg"
quality=$("$wmops" jpeg-quality "$tmpdir/dnl.jpg")
test "$quality" -ge 50
test "$quality" -le 100
