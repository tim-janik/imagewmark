#!/bin/bash
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

# set -Eeuo pipefail # -x
set -Eeo pipefail

if [ "x$IWM_SEEDS" == "x" ]; then
  IWM_SEEDS=0
fi
if [ "x$IWM_FILE" == "x" ]; then
  IWM_FILE=t
fi

imagewmark_get()
{
  imagewmark get "$@" || {
    if [ "x$IWM_FAIL_DIR" != "x" ]; then
      mkdir -p $IWM_FAIL_DIR
      SUM=$(sha1sum $1 | awk '{print $1;}')
      cp $1 $IWM_FAIL_DIR/t${SUM}.tif
      echo "CP $IWM_FAIL_DIR/t${SUM}.tif"
    fi
  }
}

if [ "x$IWM_SET" != "x" ] && [ -d "$IWM_SET" ]; then
  ls $IWM_SET/*
else
  ls test/T*
fi | while read i
do
  for SEED in $IWM_SEEDS
  do
    # file specific seed
    FSEED=$SEED:$(basename $i | sed 's:^[a-zA-Z0-]*::g;s:[_.].*::g')
    echo "FILE $i"
    echo "FSEED $FSEED"
    [ "x$IWM_PARAMS_ADD" != "x" ] && echo "PARAMS_ADD $IWM_PARAMS_ADD"
    PATTERN=$(echo $FSEED | sha256sum | awk '{print substr ($1, 1, 32)}')
    imagewmark add $i ${IWM_FILE}.tif $PATTERN ${IWM_PARAMS_ADD} --psnr -q | grep PSNR
    echo "BITS_IN  $PATTERN"
    if [ "x$IWM_ATTACK" != x ]; then
      wmtool.py ${IWM_FILE}.tif --seed "$FSEED" --attack "$IWM_ATTACK" ${IWM_FILE}_attack.tif
      mv ${IWM_FILE}_attack.tif ${IWM_FILE}.tif
    fi
    [ "x$IWM_PARAMS_GET" != "x" ] && echo "PARAMS_GET $IWM_PARAMS_GET"
    {
      imagewmark_get ${IWM_FILE}.tif --cmp "$PATTERN" ${IWM_PARAMS_GET} -q --json ${IWM_FILE}.json
      jq '.matches[] | "MATCH " + .bits + " " + (.jsd|tostring) + " " + (.error|tostring) + " " + (.cmperrors|tostring)' -r ${IWM_FILE}.json
    } | awk '
      BEGIN {
        best_jsd = 0
        best_error = 1
        best_cmperrors = 64
        best_bits = ""
      }
      $1 == "MATCH" {
        match_bits = $2
        match_jsd = $3
        match_error = $4
        match_cmperrors = $5

        # find best jsd of all matches
        if (match_jsd > best_jsd)
          best_jsd = match_jsd

        # find item with lowest cmperrors
        if (match_cmperrors < best_cmperrors || (match_cmperrors == best_cmperrors && match_error < error))
          {
            best_bits = match_bits
            best_cmperrors = match_cmperrors
            best_error = match_error
          }
      }
      $1 == "CP" {
        print "CP", $2
      }
      END {
        if (best_bits != "")
          print "BITS", best_bits

        print "JSD", best_jsd
        print "CMPERRORS", best_cmperrors
        print "ERROR", best_error
      }'
    echo
    rm -f ${IWM_FILE}.tif ${IWM_FILE}.json
  done
done | stdbuf -oL awk '
  $1 == "JSD" { jsd_count++; if ($2 > 0.5) jsd_ok++ }
  $1 == "CMPERRORS" { cmp_count++; if ($2 == 0) cmp_ok++ }
  { print "###", $0; }
  END {
    jsd_fail = jsd_count - jsd_ok
    cmp_fail = cmp_count - cmp_ok
    printf ("JSD_FAIL %d / %d %.2f %%\n", jsd_fail, jsd_count, jsd_fail / jsd_count * 100);
    printf ("CMP_FAIL %d / %d %.2f %%\n", cmp_fail, cmp_count, cmp_fail / cmp_count * 100);
  }'
