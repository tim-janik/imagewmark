# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
import os
import subprocess
import numpy as np
import common

def cmdline (mode, args):
  cxx_imagewmark = os.path.join (os.path.dirname (__file__), "..", "cxx", "imagewmark-cxx")
  cmdline = [ cxx_imagewmark, mode ]
  if args.test_key:
    cmdline += [ '--test-key', args.test_key ]
  if args.key:
    cmdline += [ '--key', args.key ]
  return cmdline

def encode (bits, args):
  input_str = "".join (("bit %.17f\n" % bit) for bit in bits)
  input_str += "end\nstop\n"

  proc = subprocess.run (cmdline ("convcode-encode", args),
                         input = input_str,
                         stdout = subprocess.PIPE,
                         universal_newlines = True)

  bits = []
  error = -1
  for line in proc.stdout.splitlines():
    l = line.strip().split()
    if (l[0] == "bit"):
      bits.append (l[1] == "1")
    elif (l[0] == "end"):
      break
    else:
      raise RuntimeError ("convcode: unexpected output line '%s'" % line)

  return np.array (bits)

def start_decoder (args):
  decoder = subprocess.Popen (cmdline ("convcode-decode", args),
                              stdin = subprocess.PIPE,
                              stdout = subprocess.PIPE,
                              universal_newlines = True,
                              bufsize = 0)
  return decoder

def stop_decoder (decoder):
  decoder.communicate ("stop\n")

def decode (decoder, bits):
  clocksecs = common.clocksecs_start()
  input_str = "".join (("bit %.17f\n" % bit) for bit in bits)
  input_str += "end\n"
  decoder.stdin.write (input_str)
  decoder.stdin.flush()
  bits = []
  error = -1
  for line in decoder.stdout:
    l = line.strip().split()
    if (l[0] == "bit"):
      bits.append (l[1] == "1")
    elif (l[0] == "error"):
      error = float (l[1])
    elif (l[0] == "end"):
      break
    else:
      common.clocksecs_add ('convcode', clocksecs)
      raise RuntimeError ("convcode: unexpected output line '%s'" % line)
  result = np.array (bits), error
  common.clocksecs_add ('convcode', clocksecs)
  return result
