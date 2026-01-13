# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
import sys
import numpy as np

# Default encryption key for unique encoding/decoding
DEFAULT_KEY = b'00000000000000000000000000000000'

# message bits is the number of watermark bits without error correction
message_size = 128

# payload dimensions (including error correction bits)
payload_shape = (16, 16)
payload_size = payload_shape[0] * payload_shape[1]

# length of matrix `r`
Lr = 4

# window size for local mean
mean_win = (9,9)
# window size for local variance
var_win = mean_win

# Useful window sizes during extraction, 9 matches the window used during
# embedding, and at some zoom sizes it can help to double the window size.
extract_window_size = [ 9, 18, 27 ]

# the "dynamic_zoom" and "minimum_zoom" variables determine the zoom level used during
# watermark embedding
#
# - higher zoom means better resistance to downscaling and jpeg attacks
# - lower zoom means better resistance to crop attacks
#
# the zoom level is choosen so that "dynamic_zoom" watermark units fit into the
# image, for instance for an 2000x1600 image with a "dynamic_zoom" of 8, each
# watermark unit would have 200 pixels
#
# the "minimum_zoom" level determines a lower bound for the computed zoom level,
# which is used for low resolutions
dynamic_zoom = 8
minimum_zoom = 1.5

# we downscale very large images before performing watermark detection, this
# shouldn't affect reliability
pre_scale = 1536

# number of peaks to pick for peaks2grid
norm_peak_count = 250
raw_peak_count = 250

# Jensen-Shannon divergence threshold to stop watermark searching, range 0..1.
# Watermark patterns are detected by their dissimilarity to the normal
# 𝓝 (0,1) Gauss distribution. An adequate threshold highly depends on
# the number of elements in a distribution being compared against 𝓝 (0,1).
# For instance, a 64 element 𝓝 (0,1) distribution may well reach a divergence
# score of 53.8% when ddist.distribution_divergence() compares it against
# an ideal Gauss histogram (e.g. run 10e6 test and take the maximum).
# For a 256 elements distribution, the score probably stays below 29%.
jsd_threshold = '55%'   # conservative default

# JSD threshold to determine if a match with one of the multiple local mean /
# local variance window sizes used during extraction is "good enough" to be
# able to quit searching other window sizes
#
# This has to be fairly high to ensure that the error correction can correct
# all errors (otherwise trying another windows size could produce a better
# result)
jsd_window_threshold = '70%'

# If the JSD is really low, then it is impossible that we can decode the
# data bits at all, so we set a minimum JSD, and skip decoding if this is
# not reached
jsd_min_threshold = '38%'

# Helper to interpret percentage arguments
def parse_percentage (string):
  scale = 100 if string.find ('%') >= 0 else 1
  return float (string.strip ('%')) / scale

# Verbosity & debugging, configured via CLI
verbose = 0
def eprint (*args):
  print (*args, file = sys.stderr)
def vprint (*args):
  if verbose >= 1:
    print (*args, file = sys.stderr)
def dprint (*args):
  if verbose >= 2:
    print (*args, file = sys.stderr)

# Find `option` in colon separated option list, return `true_value`, `false_value` or `type_conv` converted assigned value
def find_option (option_list, option, type_conv = bool, false_value = False, true_value = True):
  options = option_list.lower().split (':')
  if option in options:
    return true_value
  option = option + '='
  ovalue = [s for s in options if s.startswith (option)]
  if len (ovalue):
    return type_conv (ovalue[-1].split ('=', 1)[1])
  if 'all' in options:
    return true_value
  return false_value

# Test and announce plots as configured via enable_plots
def will_plot (plotname, inmost = True):
  global will_plot_name
  willplot = False
  if ':all:' in plots:
    willplot = True
  elif inmost and ':most:' in plots:
    willplot = True
  elif (':' + plotname + ':').lower() in plots:
    willplot = True
  if willplot:
    print ('PLOT:', plotname, file = sys.stderr)
    will_plot_name = plotname
  else:
    if plots:
      print ('SKIP:', plotname, file = sys.stderr)
    will_plot_name = ''
  return willplot
will_plot_name = ''
def enable_plots (string):
  global plots
  if string:
    plots = (':' + string + ':').lower()
  else:
    plots = ''
plots = ''
