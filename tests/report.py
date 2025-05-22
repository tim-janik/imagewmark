#!/usr/bin/env python3
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

import os, json, sys, re
import matplotlib.pyplot as plt
import math

# == GLOBALS & OPTIONS ==
EXPECTED_WM = None
ATTACKS = None
FLAT = None
def parse_args():
  global EXPECTED_WM, ATTACKS, FLAT
  assert not EXPECTED_WM and not ATTACKS
  # Parse args
  FLAT = False
  i = 1
  while i < len (sys.argv):
    if sys.argv[i] == "--flat" or sys.argv[i] == "--flat2":
      FLAT = True
    else:
      EXPECTED_WM = (sys.argv[i] * 32)[0:32].lower()
      # print ("expected_wm:", expected_wm, file = sys.stderr)
    i += 1
  if not EXPECTED_WM:
    print ("usage: report.py [--flat] <payload>", file = sys.stderr)
    sys.exit (1)
  ATTACKS = sorted (list_subdirs ('attack/'))


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
  matching, aligned, failed = [], [], []
  for jf in jsonfiles:
    jo = json.loads (open (jf, 'r').read())
    is_valid = False
    is_aligned = jo.get ('aligned', False)
    for m in jo['matches']:
      if (m['bits'] == EXPECTED_WM):
        is_valid = True
    if is_valid and is_aligned:
      aligned.append (jo)
    elif is_valid:
      matching.append (jo)
    else:
      failed.append (jo)
  n_results = len (matching) + len (aligned) + len (failed)
  assert len (jsonfiles) == n_results
  return matching, aligned, failed

# List OK/FAIL with JSD, suitable as input for diff and awk
def generate_flat_report (n_input_files, matching, aligned, failed):
  for attackdir in ATTACKS:
    assert n_input_files == len (matching[attackdir]) + len (aligned[attackdir]) + len (failed[attackdir])
    for jo in failed[attackdir]:
      print (jo['filename'])
  return

# Attack Statistics
def generate_attack_statistics (n_input_files, matching, aligned, failed):
  n_input = {}
  n_valid = {}
  n_aligned = {}
  # strip ATTACKNAMEseed123 to just ATTACKNAME
  strip_seed = lambda attack: re.sub(r'seed[0-9]+$', '', attack)
  # setup counters
  for attackdir in ATTACKS:
    attack = strip_seed (attackdir)
    n_input[attack] = 0
    n_valid[attack] = 0
    n_aligned[attack] = 0
  # merge counts from different seeds of the same attack
  for attackdir in ATTACKS:
    attack = strip_seed (attackdir)
    n_input[attack] += n_input_files
    n_valid[attack] += len (matching[attackdir])
    n_aligned[attack] += len (aligned[attackdir])
    assert n_input_files == len (matching[attackdir]) + len (aligned[attackdir]) + len (failed[attackdir])
  # generate output table
  s = ''
  s += '## Attack Statistics\n\n'
  s += 'Results for correct watermark detection (blind, "Match"), plus fallback detection via original image (non-blind, "Total").\n'
  s += 'Some attacks are re-run with different random seeds, which multiplies the number of inputs.\n\n'
  s += 'Total input files: %d\n\n' % n_input_files
  s += '| **Attack** | **Found** | **Fail** | **Match** | **Orig** | **Total** |\n'
  s += '|----------------------------|:-----:|-----:|-----:|:----:|-----:|\n'
  for attack in sorted (n_input.keys()):
    mismatch_perc = (n_input[attack] - n_valid[attack]) * 100.0 / n_input[attack]
    aligned_perc = mismatch_perc
    if (n_input[attack] - n_valid[attack]):
      aligned_perc = (n_input[attack] - n_valid[attack] - n_aligned[attack]) * 100.0 / n_input[attack]
    R = '**' if aligned_perc < 1e-9 else ''
    H,E = ('**','') if mismatch_perc < 1e-9 else ('','**')      # highlight matches <= 90%
    s += '| %s | %d/%d | %s%.1f%%%s | %s%.1f%%%s | %s | %s%.1f%%%s\n' % \
      (attack, n_valid[attack], n_input[attack],
       E, mismatch_perc, E,
       H, 100 - mismatch_perc, H,
       n_aligned[attack] or '', R, 100 - aligned_perc, R)
  print (s)

# Timings
def generate_timings (matching, aligned, failed):
  import numpy as np
  import matplotlib.pyplot as plt
  svt = {} # size vs time
  for attackdir in ATTACKS:
    for jo in matching[attackdir] + aligned[attackdir] + failed[attackdir]:
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
  assert EXPECTED_WM and ATTACKS
  # Read inputs and attacks
  input_files = files_recursively ('inputs/')
  n_input_files = len (input_files)
  extracted = {}
  aligned = {}
  matching = {}   # WM found
  aligned = {}    # WM found via aligned original
  failed = {}     # WM detection failed

  # Categorize WM detection results per attack
  for attackdir in ATTACKS:
    # attack_files = files_recursively ('attack/' + attackdir)
    extracted[attackdir] = files_recursively ('extract/' + attackdir, extension = '.json')
    assert n_input_files == len (extracted[attackdir])
    matching[attackdir], aligned[attackdir], failed[attackdir] = categorize_detections (extracted[attackdir])
    assert len (matching[attackdir]) + len (aligned[attackdir]) + len (failed[attackdir]) == n_input_files

  # Report generation
  if FLAT:
    generate_flat_report (n_input_files, matching, aligned, failed)
  else:
    generate_attack_statistics (n_input_files, matching, aligned, failed)
    generate_timings (matching, aligned, failed)

parse_args()
main()
