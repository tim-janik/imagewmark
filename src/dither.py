#!/usr/bin/env python3
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
import cv2
import numpy as np
import sys
import random
from plotting import *
import common

# Floyd Steinberg dithering for one color channel
#
# edc is a factor (which should be close to 1) to ensure that each color
# channel has a slightly different error diffusion strategy, which should
# make each channel dither with a different pattern (note: it could be
# interesting to dither the delta-Y before adding it to the watermark
# to make all channels have the same error diffusion pattern)
def fs_dither_channel (wm, edc):
  wm = wm.copy().astype (float)
  for y in range (wm.shape[1]):
    for x in range (wm.shape[0]):
      old_pixel = wm[x,y]
      new_pixel = np.rint (wm[x,y])
      wm[x,y] = new_pixel
      error = old_pixel - new_pixel
      if x > 0 and x + 1 < wm.shape[0] and y + 1 < wm.shape[1]:
        wm[x + 1, y    ] += error * 7 / 16 * edc
        wm[x - 1, y + 1] += error * 3 / 16 / edc
        wm[x    , y + 1] += error * 5 / 16 / edc
        wm[x + 1, y + 1] += error * 1 / 16 * edc
  return wm

# Floyd Steinberg dithering
#
# Experimental results: there is not much difference between this and the other
# methods, unless the strength is really small. Floyd Steinberg dithering is
# also really slow, because it loops over the pixels in python.
def fs_dither (wm):
  n_channels = wm.shape[2] if len (wm.shape) > 2 else 1
  if (n_channels > 1):
    dither_wm = wm.copy()
    for ch in range (3):
      d = fs_dither_channel (dither_wm[:,:,ch], [0.97, 1.0, 1.05][ch])
      dither_wm[:,:,ch] = d
  else:
    dither_wm = fs_dither_channel (wm, 1)
  return np.clip (dither_wm, 0, 255).astype (np.uint8)

# Randomized dithering
#
# Experimental results: like Floyd Steinberg dithering, this is mainly interesting
# for really small strength.
def rand_dither (wm):
  r = np.random.random (wm.shape) - 0.5
  return np.clip (np.rint (wm + r), 0, 255).astype (np.uint8)

# Round to nearest
def round_pixels (wm):
  return np.clip (np.rint (wm), 0, 255).astype (np.uint8)

# Truncation
#
# The advantage (or disadvantage) over rounding here is that for really small
# strength, rounding always discards the watermark.
#
# Example: two pixels with a small strength, 99.9 and 100.1, with rounding
# they will be rounded to 100, and no watermark can be detected later on.
# With truncation, they will be truncated to 99 and 100, which makes
# watermark detection possible. However, this also means that below a certain
# strength, truncation will no longer improve in PSNR for areas of constant
# color, whereas all other strategies will.
def trunc_pixels (wm):
  return np.clip (wm, 0, 255).astype (np.uint8)

# render example
if __name__ == '__main__':
  np.random.seed (seed=42)
  if len (sys.argv) != 3:
    print ("usage: dither.py <strength> <zoom>")
    sys.exit (1)
  strength = float (sys.argv[1])
  zoom = float (sys.argv[2])
  x = (np.random.random ((64,64)) - 0.5) * 2 * strength + 127
  wm = common.zoom_image (x, zoom)
  round_wm = round_pixels (wm)
  trunc_wm = trunc_pixels (wm)
  fs_dither_wm = fs_dither (wm)
  rand_dither_wm = rand_dither (wm)
  show (wm=wm, fs_dither_wm=fs_dither_wm)
  show (wm=wm, rand_dither_wm=rand_dither_wm)
  show (fs_dither_wm=fs_dither_wm, rand_dither_wm=rand_dither_wm, round_wm=round_wm, trunc_wm=trunc_wm)

  def check (name, dithered):
    dithered = dithered.astype (float)
    dot = np.mean ((dithered - 127.) * (wm - 127.))
    smooth_dithered = cv2.boxFilter (dithered, -1, (5,5), borderType = cv2.BORDER_REFLECT)
    smooth_wm = cv2.boxFilter (wm, -1, (5,5), borderType = cv2.BORDER_REFLECT)
    orig = np.ones (dithered.shape) * 127
    print ("--- %s ---" % name)
    print ("dot product  : %f" % dot)
    print ("psnr orig/wm : %f" % common.psnr (dithered, orig))
    print ("qpsnr        : %f" % common.psnr (dithered, wm))
    print ("qpsnr q(5x5) : %f" % common.psnr (smooth_dithered, smooth_wm))
    print ()
  check ("fs_dither", fs_dither_wm)
  check ("rand_dither", rand_dither_wm)
  check ("trunc", trunc_wm)
  check ("round", round_wm)
