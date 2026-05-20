#!/usr/bin/env python3
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

import os, json, sys, re
import matplotlib.pyplot as plt
import math

# == GLOBALS & OPTIONS ==
EXPECTED_WM = None
ATTACKS = None
def parse_args():
  # Parse args
  EXPECTED_WM = None
  i = 1
  while i < len (sys.argv):
    EXPECTED_WM = (sys.argv[i] * 32)[0:32].lower()
    # print ("expected_wm:", expected_wm, file = sys.stderr)
    i += 1
  if not EXPECTED_WM:
    print ("usage: report.py <payload>", file = sys.stderr)
    sys.exit (1)
  return EXPECTED_WM


def eprint (*args, **kwargs):
  print (*args, file = sys.stderr, **kwargs)

# collect file paths recursively into a list
def files_recursively (rootdir, extension = ''):
  all_files = []
  for root, dirs, files in os.walk (rootdir):
    for name in files:
      if name.endswith (extension):
        filepath = os.path.join (root, name)
        all_files.append (filepath)
  return all_files
def list_subdirs (rootdir):
  root, dirs, files = next (os.walk (rootdir)) # , topdown = False))
  return dirs

# Categorize JSON file into matching, matching-with-alignment, failed
def categorize_detections (jsonfiles):
  cs_matching, acnf_matching, aligned, failed = [], [], [], []
  for jf in jsonfiles:
    jo = json.loads (open (jf, 'r').read())
    is_valid = False
    is_aligned = jo.get ('aligned', False)
    is_cornersync = -1
    window = 0
    for m in jo['matches']:
      if m['bits'] == EXPECTED_WM:
        is_valid = True
        window = m['window']
        if m.get ('sync') == 'acnf':
          is_cornersync = False
        elif m.get ('sync') == 'cornersync':
          is_cornersync = True
    if is_valid and is_cornersync == -1:
      # imagewmark 0.5 has no  matches[].sync field
      is_cornersync = window == 9 and jo.get ('cornersync_detect_cpu', 0) > 0.0
    if is_valid and is_aligned:
      aligned.append (jo)
    elif is_valid and is_cornersync:
      cs_matching.append (jo)
    elif is_valid:
      acnf_matching.append (jo)
    else:
      failed.append (jo)
  n_results = len (cs_matching) + len (acnf_matching) + len (aligned) + len (failed)
  assert len (jsonfiles) == n_results
  return acnf_matching, cs_matching, aligned, failed

# Attack Statistics
def generate_attack_statistics (n_input_files, acnf_matching, cs_matching, aligned, failed):
  n_input = {}
  n_cs_valid = {}
  n_acnf_valid = {}
  n_aligned = {}
  total_fail_perc = 0.0
  total_match_perc = 0.0
  # strip ATTACKNAMEseed123 to just ATTACKNAME
  strip_seed = lambda attack: re.sub(r'seed[0-9]+$', '', attack)
  # setup counters
  for attackdir in ATTACKS:
    attack = strip_seed (attackdir)
    n_input[attack] = 0
    n_acnf_valid[attack] = 0
    n_cs_valid[attack] = 0
    n_aligned[attack] = 0
  num_attacks = len (n_input)
  # merge counts from different seeds of the same attack
  for attackdir in ATTACKS:
    attack = strip_seed (attackdir)
    n_input[attack] += n_input_files
    n_cs_valid[attack] += len (cs_matching[attackdir])
    n_acnf_valid[attack] += len (acnf_matching[attackdir])
    n_aligned[attack] += len (aligned[attackdir])
    assert n_input_files == len (acnf_matching[attackdir]) + len (cs_matching[attackdir]) + len (aligned[attackdir]) + len (failed[attackdir])
  # generate output table
  s = ''
  s += '## Attack Statistics\n\n'
  s += 'Results for correct watermark detection (blind, "Match"), plus fallback detection via original image (non-blind, "Total").\n'
  s += 'Some attacks are re-run with different random seeds, which multiplies the number of inputs.\n\n'
  s += 'Total input files: %d\n\n' % n_input_files
  s += '| **Attack** | **ACNF** | **CS** | **AO** | **Fail** | **Match** |\n'
  s += '|----------------------------|-----:|:----:|:----:|-----:|----:|\n'
  # Attack stats
  for attack in sorted (n_input.keys()):
    is_geometric_attack = bool (re.search (r'(?<![A-Za-z])g$', attack))
    cs_weight = 1 if is_geometric_attack else 0.5       # assume CS only catches 50% of leaks
    valid_count = n_acnf_valid[attack] + n_cs_valid[attack] * cs_weight
    mismatch_perc = (n_input[attack] - valid_count) * 100.0 / n_input[attack]
    match_perc = 100 - mismatch_perc
    total_fail_perc += mismatch_perc
    total_match_perc += match_perc
    H,E = ('**','') if mismatch_perc < 1e-9 else ('','**')      # highlight matches <= 90%
    s += '| %s | %d/%d | %d | %d | %s%.1f%%%s | %s%.1f%%%s\n' % \
      (attack,
       n_acnf_valid[attack], n_input[attack],
       n_cs_valid[attack],
       n_aligned[attack],
       E, mismatch_perc, E,
       H, match_perc, H)
  # Add average row to the table
  if num_attacks > 0:
    avg_fail_perc = total_fail_perc / num_attacks
    avg_match_perc = total_match_perc / num_attacks
    s += '| **Average:** | | | | **%.1f%%** | **%.1f%%** |\n' % (avg_fail_perc, avg_match_perc)

  print (s)

# Timings
def generate_timings (acnf_matching, cs_matching, aligned, failed):
  import numpy as np
  import matplotlib.pyplot as plt
  svt = {} # size vs time
  for attackdir in ATTACKS:
    for jo in acnf_matching[attackdir] + cs_matching[attackdir] + aligned[attackdir] + failed[attackdir]:
      size = jo['width'] * jo['height']
      svt[size] = svt.get (size, []) + [ jo['time'] ]
  for k in svt:
    svt[k] = sum (svt[k]) / len (svt[k])

  fig, ax = plt.subplots()
  xs = [round (math.sqrt (k)) for k in sorted (svt)]
  ys = [svt[k] for k in sorted (svt)]
  ax.plot (xs, ys)
  ax.set_ylabel ('Average Seconds for Extraction')
  ax.set_xlabel ('Pixels per Dimension')
  ax.set_title ('Time for Watermark Extraction vs Pixel Dimension')
  # ax.legend (title = 'Seconds/PixelDim')
  plt.savefig ('timevspix.svg')        # plt.show()
  s = '## Timing Statistics\n'
  s += 'Timings for watermark extraction in seconds vs pixels per image dimension.\n'
  s += '![Seconds / √ImagePixel](./timevspix.svg)\n'
  print (s)

def main():
  # Parse args and attack types
  global EXPECTED_WM, ATTACKS
  EXPECTED_WM = parse_args()
  ATTACKS = sorted (list_subdirs ('attack/'))
  assert EXPECTED_WM and ATTACKS
  # Read inputs and attacks
  input_files = files_recursively ('inputs/')
  n_input_files = len (input_files)
  extracted = {}        # JSON files from 'get'
  aligned = {}          # JSON aligned==true
  acnf_matching = {}    # WM found
  cs_matching = {}      # WM found
  failed = {}           # WM detection failed

  # Categorize WM detection results per attack
  for attackdir in ATTACKS:
    # attack_files = files_recursively ('attack/' + attackdir)
    extracted[attackdir] = files_recursively ('extract/' + attackdir, extension = '.json')
    assert n_input_files == len (extracted[attackdir])
    acnf_matching[attackdir], cs_matching[attackdir], aligned[attackdir], failed[attackdir] = categorize_detections (extracted[attackdir])
    assert len (acnf_matching[attackdir]) + len (cs_matching[attackdir]) + len (aligned[attackdir]) + len (failed[attackdir]) == n_input_files

  # Report generation
  generate_attack_statistics (n_input_files, acnf_matching, cs_matching, aligned, failed)
  print ("\n---\n")
  generate_timings (acnf_matching, cs_matching, aligned, failed)

main()
