#!/usr/bin/env python3
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
import argparse
import cv2
import numpy as np
import tempfile
import sys
import random

quiet = False
def print_attack (s):
  if not quiet:
    print (s)

blurb = """
Helper Script to perform different attacks on images.
"""

epilog = """
------------------------------------------------------------------------------
ATTACK argument can contain one or multiple attacks:
"""

epilog += """
* jpeg:<quality>

  perform lossy jpeg compression on the image with jpeg quality <quality>
"""

def attack_jpeg (img, q):
  print_attack ("ATTACK jpeg %d" % q)
  tf = tempfile.NamedTemporaryFile (suffix=".jpeg")
  cv2.imwrite (tf.name, img, [ int (cv2.IMWRITE_JPEG_QUALITY), q ])
  return cv2.imread (tf.name)

epilog += """
* scale:<smin>:<smax>

  scale image with a randomized percentage between <smin> and <smax>
"""

def attack_scale (img, smin, smax):
  z = random.randint (smin, smax)
  print_attack ("ATTACK scale %d" % z)

  img_scale = z / 100

  width = round (img.shape[1] * img_scale)
  height = round (img.shape[0] * img_scale)

  return cv2.resize (img, (width, height))

epilog += """
* scaleto:<pixels>

  scale image to fixed size where smaller dimension has exactly <pixels> pixels
"""

def attack_scaleto (img, pixels):
  print_attack ("ATTACK scaleto %d" % pixels)

  img_scale = pixels / min (img.shape[0], img.shape[1])

  width = round (img.shape[1] * img_scale)
  height = round (img.shape[0] * img_scale)

  return cv2.resize (img, (width, height))

epilog += """
* crop:<cmin>:<cmax>

  crop image preserving a randomized percentage of pixels between <cmin> and <cmax>
"""

def attack_crop (img, cmin, cmax):
  width = int (img.shape[1])
  height = int (img.shape[0])

  percent = random.randint (cmin, cmax)
  crop_ok = False
  while not crop_ok:
    new_width = random.randint (int (width * percent / 100), width)
    new_height = round ((width * height) / new_width * percent / 100)
    crop_ok = (new_width <= width) and (new_height <= height)

  x = random.randint (0, width - new_width)
  y = random.randint (0, height - new_height)
  cropped_image = img[y:y + new_height, x:x + new_width]

  ratio = (new_width * new_height) / (width * height) * 100
  print_attack ("ATTACK crop %d" % round (ratio))
  return cropped_image

epilog += """
* rotate:<rmin>:<rmax>

  rotate image between [+/-] <rmin> and [+/-] <rmax> degrees
"""

def attack_rotate (img, rmin, rmax):
  width = int (img.shape[1])
  height = int (img.shape[0])

  angle = random.randint (rmin, rmax) * random.choice([-1, 1])

  print_attack ("ATTACK rotate %d" % angle)

  height, width = img.shape[:2]
  center = (width/2, height/2)
  rotate_matrix = cv2.getRotationMatrix2D (center=center, angle=angle, scale=1)

  return cv2.warpAffine(src=img, M=rotate_matrix, dsize=(width, height))

epilog += """
* aspect:<amin>:<amax>

  change aspect ratio to a value between amin..amax percent
    an aspect ratio > 100% will increase the image width
    an aspect ratio < 100% will increase the image height
"""

def attack_aspect (img, amin, amax):
  width = int (img.shape[1])
  height = int (img.shape[0])

  aspect = random.randint (amin, amax)

  print_attack ("ATTACK aspect %d" % aspect)

  if (aspect > 100):
    width = round (width * aspect / 100)
  if (aspect < 100):
    height = round (height * 100 / aspect)

  return cv2.resize (img, (width, height))

epilog += """
------------------------------------------------------------------------------
Example:
 - crop image to 75%..95% of its pixels
 - scale cropped image to 75%..125% of its original size
 - jpeg compress scaled & cropped image at quality 90

wmtool.py --attack 'crop:75:95|scale:75:125|jpeg:90' in.png out.png
"""

# Setup CLI parsr for embedding
def cli_parser():
  p = argparse.ArgumentParser (description = blurb, epilog = epilog, formatter_class=argparse.RawDescriptionHelpFormatter)
  a = p.add_argument
  a ('inputimage', type = str,
     help = "Source image")
  a ('outputimage', type = str,
     help = "Destination image")
  a ('--scale', default = False, action = 'store_true',
     help = "Print information about progress")
  a ('--verbose', default = False, action = 'store_true',
     help = "Be verbose")
  a ('--seed',
     help = "seed random number generator (for reproducable random numbers)")
  a ('--attack',
     help = "a list of attacks, seperated by '|'")
  a ('-q', '--quiet',
     default = False, action = 'store_true',
     help = "Reduce output verbosity")
  return p

# load image, return either greyscale or rgb array
def load_bgr_image (filename):
  face = cv2.imread (filename)
  if face is None:
    err = 'unsupported format' if os.access (filename, os.R_OK) else 'failed to read from file'
    print ("imagewmark: failed to load image '%s':" % filename, err, file = sys.stderr)
    sys.exit (1)
  return face

# parse args
args = cli_parser().parse_args()
quiet = args.quiet

face = load_bgr_image (args.inputimage)
if (args.verbose):
  print ("Input Image:", face.shape, face.min(), '...', face.max());

if (args.seed):
  random.seed (args.seed)

if (args.scale):
  face_scale = 1024 / max (face.shape[0], face.shape[1])

  width = int (face.shape[1] * face_scale)
  height = int (face.shape[0] * face_scale)

  face = cv2.resize (face, (width, height))

if (args.attack):
  for attack in args.attack.split ("|"):
    aargs = attack.split (":")
    if aargs[0] == "jpeg" and len (aargs) == 2:
      face = attack_jpeg (face, int (aargs[1]))
    elif aargs[0] == "scale" and len (aargs) == 3:
      face = attack_scale (face, int (aargs[1]), int (aargs[2]))
    elif aargs[0] == "scaleto" and len (aargs) == 2:
      face = attack_scaleto (face, int (aargs[1]))
    elif aargs[0] == "crop" and len (aargs) == 3:
      face = attack_crop (face, int (aargs[1]), int (aargs[2]))
    elif aargs[0] == "rotate" and len (aargs) == 3:
      face = attack_rotate (face, int (aargs[1]), int (aargs[2]))
    elif aargs[0] == "aspect" and len (aargs) == 3:
      face = attack_aspect (face, int (aargs[1]), int (aargs[2]))
    elif aargs[0] == "none" and len (aargs) == 1:
      pass
    else:
      sys.exit ("Unsupported attack: %s" % attack)

if (args.verbose):
  print ("Output Image:", face.shape, face.min(), '...', face.max());
cv2_imwrite_success = cv2.imwrite (args.outputimage, face)
assert (cv2_imwrite_success)
