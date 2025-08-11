# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
import numpy as np
import scipy.misc, scipy.signal, cv2
import os, sys
import math, config
from config import eprint, vprint, dprint, verbose
from time import process_time_ns, perf_counter_ns

# Dict to collect global statistics
def stats_set (key, value):
  global global_stats
  global_stats[key] = value
global_stats = {}

# Fetch dict with current global statistics
def get_stats():
  result = {}
  result.update (global_stats)
  return result

# Start to measure CPU+Sys time
def cpusecs_start ():
  return process_time_ns()

nsecs2seconds = 10**-9

# Stop to measure CPU+Sys time (from `start`), add to stats
def cpusecs_add (key, start):
  key = key + '_cpu'
  stop = cpusecs_start()
  accu = global_stats.get (key, 0)
  accu += (stop - start) * nsecs2seconds
  stats_set (key, accu)

# Start to measure wall clock time
def clocksecs_start ():
  return perf_counter_ns()

nsecs2seconds = 10**-9

# Stop to measure wall clock time (from `start`), add to stats
def clocksecs_add (key, start):
  key = key + '_clock'
  stop = clocksecs_start()
  accu = global_stats.get (key, 0)
  accu += (stop - start) * nsecs2seconds
  stats_set (key, accu)

# Load file, yield BGR for color images (CV2 order)
def load_bgr_image (filename):
  face = cv2.imread (filename)
  if face is None:
    err = 'unsupported format' if os.access (filename, os.R_OK) else 'failed to read from file'
    eprint ("imagewmark: failed to load image '%s':" % filename, err)
    sys.exit (1)
  dprint ("image:", face.shape, face.min(), '...', face.max())
  return face

# Convert back and forth between BGR <-> RGB
def swap_bgr_rgb (image):
  nchannels = image.shape[2] if len (image.shape) > 2 else 1
  if nchannels == 3:
    image = image[:, :, ::-1]           # BGR -> RGB
  return image

# Load image via CV2, leave greyscale or convert to RGB
def load_rgb_image (filename):
  image = load_bgr_image (filename)
  return swap_bgr_rgb (image)

# Save image via CV2, expects image format as filename extension
def save_rgb_image (filename, image):
  cv2.imwrite (filename, swap_bgr_rgb (image))

# Convert a np.array image from BGR to YIQ-Y if not already greyscale
def bgr_to_gray (image):
  return rgb_to_gray (swap_bgr_rgb (image))

# Convert a np.array image from RGB to YIQ-Y if not already greyscale
def rgb_to_gray (image):
  import skimage.color
  nchannels = image.shape[2] if len (image.shape) > 2 else 1
  if nchannels == 1:
    # Enforce float grayscale format
    gray = image.astype (float)
  elif nchannels == 3:
    yiq_face = skimage.color.rgb2yiq (image)
    gray = yiq_face[:,:,0] * 255 # extract Y channel
  else:
    raise RuntimeError ("Input image with %d channels not supported" % nchannels)
  dprint ("J:", gray.shape, gray.min(), '...', gray.max())
  return gray

# Compute PSNR for two images (with pixel range [0:255])
def psnr (orig_img, wm_img):
  mse = np.mean ((orig_img - wm_img) ** 2)
  # no difference at all?
  if (mse == 0):
    return 100
  max_pixel = 255.0
  psnr = 20 * math.log10 (max_pixel / math.sqrt (mse))
  return psnr

# Normalize pixel range of an image
def normalize (src, base = 0.0, full = 1.0, dtype = float):
  img = np.array (src, dtype = dtype)
  if img.min() != base:
    img += base - img.min()
  if img.max() != full:
    img *= full / img.max()
  return img

# zoom via OpenCV2
# - this is a lot faster than scipy.ndimage.zoom
# - interpolation is different than scipy.ndimage.zoom, but INTER_CUBIC works for our purpose
def zoom_image (img, zoom):
  return cv2.resize (img, dsize = None, fx = zoom, fy = zoom, interpolation = cv2.INTER_CUBIC)

# local mean via OpenCV2
def local_mean (img, win = config.mean_win):
  # https://docs.opencv.org/2.4-beta/modules/imgproc/doc/filtering.html?highlight=boxfilter#cv2.boxFilter
  # https://docs.opencv.org/4.x/d4/d86/group__imgproc__filter.html#gad533230ebf2d42509547d514f7d3fbc3
  mean = cv2.boxFilter (img, -1, win, borderType = cv2.BORDER_REFLECT)
  return mean

# 2D local variance via OpenCV2
def local_variance (img, win = config.var_win):
  # variance = mean ( (img - mean (img))**2 )           # https://en.wikipedia.org/wiki/Variance
  # variance = mean (img^2) - mean (img)^2              # https://en.wikipedia.org/wiki/Variance
  # https://docs.opencv.org/2.4-beta/modules/imgproc/doc/filtering.html?highlight=boxfilter#cv2.boxFilter
  # https://docs.opencv.org/4.x/d4/d86/group__imgproc__filter.html#gad533230ebf2d42509547d514f7d3fbc3
  mean1 = cv2.boxFilter (img, -1, win, borderType = cv2.BORDER_REFLECT)
  mean2 = cv2.boxFilter (img**2, -1, win, borderType = cv2.BORDER_REFLECT)
  return mean2 - mean1**2

# F - non-linear strength function
def F (img_variance, strength):
  img_variance = np.maximum (1e-5, img_variance)  # enforce positive values for sqrt / log2
  img_std = np.sqrt (img_variance)
  # TODO: right now we have only one parameter for strength:
  # - the minimum strength (to be used on areas with low texture complexity)
  #
  # However, it would be better if we could control two parameters:
  # - the minimum strength (for regions with low texture complexity)
  # - how much the strength should grow in regions with high texture complexity
  #
  # This could be implemented as factor, for instance f * np.log2 (img_std) or np.log2 (f * img_std).
  return np.maximum (strength, np.log2 (img_std))

# generate random matrix `r` (bp_r)
def make_wm_pattern (ENCRYPTION_KEY):
  Lr = config.Lr
  Rshake = prng_gen ("wm_pattern", (Lr * Lr + 7) // 8)  # hashlib.shake_256 (b'Rshake' + ENCRYPTION_KEY).digest ((Lr * Lr + 7) // 8)
  Rbits = np.unpackbits (np.array ([b for b in Rshake], dtype = np.uint8))
  dprint ("Rbits:", Rbits.shape, Rbits.min(), '...', Rbits.max(), Rbits);
  bp_r = np.empty ((Lr, Lr), dtype = float)
  for j in range (Lr):
    for i in range (Lr):
      bp_r[j,i] = Rbits[j * Lr + i]
  bp_r = bp_r * -2.0 + 1  # bipolar float matrix: [[1 -1 -1 1 1 -1 1 -1]...]
  dprint ("bp_r:", bp_r.shape, bp_r.min(), '...', bp_r.max());
  return (Lr, bp_r)

# Generate key-dependent randomized matrix Ksmall
def make_wm_mask (ENCRYPTION_KEY, Lks):
  Kshake = prng_gen ("wm_mask", Lks * Lks // 8)         # hashlib.shake_256 (b'Kshake' + ENCRYPTION_KEY).digest (Lks * Lks // 8)
  Kbits = np.array ([b for b in Kshake], dtype = np.uint8).reshape (Lks, Lks // 8)
  Kbits = np.unpackbits (Kbits, axis = 1) # Key based random matrix
  Ksmall = Kbits * -2.0 + 1   # bipolar float matrix: [[1 -1 -1 1 1 -1 1 -1]...]
  dprint ("Ksmall mask:", Ksmall.shape, Ksmall.min(), '...', Ksmall.max());
  return Ksmall

# Parse string into message bits with payload_shape
def parse_payload (message):
  v = []
  for c in message:
    nibble = int (c, 16)
    v.append ((nibble & 8) > 0)
    v.append ((nibble & 4) > 0)
    v.append ((nibble & 2) > 0)
    v.append ((nibble & 1) > 0)
  b = []
  for i in range (config.message_size):
    b.append (v[i % len (v)])
  bits = np.array (b)
  # dprint ("BITS:", ''.join (['%02x' % xx for xx in np.packbits (bits.flatten())]))
  return bits

# Load Key and prepare Key based PRNGs
def load_key (keyfile, test_key):
  clocksecs = clocksecs_start()
  global key_based_prng
  dprint ("load_key:", keyfile, test_key)
  import os, subprocess, json
  cxx_imagewmark = os.path.join (os.path.dirname (__file__), "..", "cxx", "imagewmark-cxx")
  cmdline = [ cxx_imagewmark, 'rand' ]
  if test_key:
    cmdline += [ '--test-key', test_key ]
  if keyfile:
    cmdline += [ '--key', keyfile ]
  clocksecs_add ('loadkey1_prep', clocksecs)
  cirand = subprocess.Popen (cmdline, stdout = subprocess.PIPE, universal_newlines = True, bufsize = 0)
  clocksecs_add ('loadkey2_popen', clocksecs)
  out, err = cirand.communicate()
  clocksecs_add ('loadkey3_communicate', clocksecs)
  if cirand.returncode:
    raise RuntimeError ("Failed to process encryption key (%d): %s" % (cirand.returncode, ' '.join (cmdline)))
  import json
  key_based_prng = json.loads (out)
  clocksecs_add ('loadkey4_jsonload', clocksecs)
  for k in key_based_prng.keys():
    ints = key_based_prng[k]
    bb = b''.join (b'%c' % i for i in ints) # struct.pack ('%dB' % len (ints), *ints)
    key_based_prng[k] = bb
  # prng_gen ("wm_convcode", 16)
  clocksecs_add ('loadkey5_byteassign', clocksecs)
key_based_prng = None

# Generate random numbers from Key based PRNGs
def prng_gen (prng, n):
  global key_based_prng
  rnd = key_based_prng[prng]
  sub, rest = rnd[:n], rnd[n:]
  key_based_prng[prng] = rest
  return sub
