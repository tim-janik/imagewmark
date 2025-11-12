#!/usr/bin/env python3
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

# For benchmarking, start tracking execution time as first thing
from time import time
startup_time = time()

# Load submodules relative to script location
from pathlib import Path
BASE_DIR = Path (__file__).resolve().parent
import sys
sys.path.insert (0, str (BASE_DIR / '../src'))

__version__ = open (str (BASE_DIR / "../.version")).read().strip()

import argparse
import embed, extract
import numpy as np
import scipy.misc, scipy.signal, cv2
import hashlib
from plotting import *
import config, common
import imageio

blurb = """
Script implementing watermark message bit embedding and extraction.
"""

class VerboseAction (argparse.Action):
  def __call__ (self, parser, args, values, option_string=None):
    dir = -1 if option_string.find ("q") >= 0 else +1
    setattr (args, self.dest, dir + getattr (args, self.dest))

# Setup CLI parsr for embedding
def cli_parser():
  p = argparse.ArgumentParser (description = blurb, formatter_class = argparse.ArgumentDefaultsHelpFormatter)
  a = p.add_argument
  def add_common_args (parser, addget):
    parser.add_argument ('-v', '--verbose', nargs = 0, action = VerboseAction, dest = 'verbose', default = config.verbose,
                         help = "Increase output messages or debugging info for multiple `-vv`")
    parser.add_argument ('-q', '--quiet', nargs = 0, action = VerboseAction, dest = 'verbose',
                         help = "Reduce output verbosity")
    if not addget:
      return
    parser.add_argument ('--strength', type = float, default = 2, help = "Strength for embedded watermark")
    parser.add_argument ('-P', dest = 'plots', type = str, help = "Configure plots with colon separated keywords, 'most' or 'all'")
    parser.add_argument ('--key', type = str, help = "Load watermarking key from file")
    parser.add_argument ('--test-key', type = str, help = "Watermarking key")

  # COMMANDS
  p.add_argument ('-V', '--version', action = 'version', version = 'ImageWMark %s' % __version__)
  cmdp = p.add_subparsers (title = 'command', dest = 'command', required = True,
                           help = 'Use `<command> -h` for detailed help')
  # ADD
  addp = cmdp.add_parser ('add', help = "Embed a watermark message in an image", formatter_class = argparse.ArgumentDefaultsHelpFormatter)
  addp.add_argument ('input_img', type = str, help = "Image into which the message is to be embedded")
  addp.add_argument ('output_img', type = str, help = "Image with embedded watermark message")
  addp.add_argument ('message_hex', type = str, help = "Message bits to embed (max 128)")
  addp.add_argument ('--dynamic-zoom', type = float, default = -1, help = "Zoom watermark depending on image size")
  addp.add_argument ('--zoom', type = float, default = -1, help = "Set zoom factor for watermark")
  addp.add_argument ('--trace-psnr', action='store_true', help='Compute PSNR')
  addp.add_argument ('--trace-quality', action='store_true', help='Compute quality metrics')
  add_common_args (addp, True)
  # GET
  getp = cmdp.add_parser ('get', help = "Extract a watermark message from an image", formatter_class = argparse.ArgumentDefaultsHelpFormatter)
  getp.add_argument ('input_img', type = str, help = "Image containing embedded watermark message")
  getp.add_argument ('--expect', type = str, help = "Expected bit pattern for early exit")
  getp.add_argument ('--json', dest = 'jsonfile', nargs = '?', default = None, const = '/dev/stdout', help = "Write JSON results into file")
  getp.add_argument ('--dump', type = str, default = '', help = "Debug flags to dump intermediate stages")
  getp.add_argument ('--norm-peak-count', type = int, default = config.norm_peak_count, help = "Number of normalized peaks to use for grid")
  getp.add_argument ('--raw-peak-count', type = int, default = config.raw_peak_count, help = "Number of raw peaks to use for grid")
  getp.add_argument ('--jsd-threshold', type = str, default = config.jsd_threshold, help = "Jensen-Shannon divergence threshold that is sufficient to stop searching for more watermarks")
  getp.add_argument ("--cornersync", choices = ['on', 'off', 'auto'], default = 'auto', help = "Set cornersync aided detection mode: 'on' forces it, 'off' disables it, 'auto' is the default.")
  getp.add_argument ('--perspective', action="store_true", help = "Search for optimal perspective grids")
  getp.add_argument ('--original', type = str, default = '', help = "Use original image for detection")
  add_common_args (getp, True)
  # GEN-KEY
  genp = cmdp.add_parser ('gen-key', help = "Generate 128-bit watermarking key, to be used with the --key option", formatter_class = argparse.ArgumentDefaultsHelpFormatter)
  genp.add_argument ('output_key_file', type = str, help = "File to store watermarking key")
  add_common_args (genp, False)
  return p

# gen-key command
def gen_key (keyfile, args):
  import subprocess, os
  cxx_imagewmark = Path (__file__).resolve().parent.parent / "cxx" / "imagewmark-cxx"
  proc = subprocess.run ([ cxx_imagewmark, 'gen-key', keyfile ])
  if proc.returncode:
    raise RuntimeError ("Failed to generate key (%d): %s" % (cirand.returncode, ' '.join (cmdline)))

# parse args
args = cli_parser().parse_args()
config.verbose = args.verbose
config.with_debug = args.verbose >= 2
config.enable_plots (args.plots if 'plots' in args else '')
args.startup_time = startup_time
if hasattr (args, 'cornersync'):
  args.cornersync = -1 if args.cornersync.lower() == 'auto' else args.cornersync.lower() == 'on'

# Load Key and prepare Key based PRNGs
if hasattr (args, 'key') or hasattr (args, 'test_key'):
  if not args.test_key and not args.key:
    args.test_key = config.DEFAULT_KEY
  common.load_key (args.key, args.test_key)

# command handling
if args.command == 'add':
  exit_code = 0
  embed.command_add (args.input_img, args.output_img, args.message_hex, args.strength, args)
elif args.command == 'get':
  exit_code = extract.command_get (args.input_img, args.strength, args)
elif args.command == 'gen-key':
  exit_code = gen_key (args.output_key_file, args)
sys.exit (exit_code)
