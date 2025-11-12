# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
import argparse
import numpy as np
import scipy.misc, scipy.signal, cv2
import sys
from plotting import *
import config, common
from config import vprint, dprint, eprint
import convcode
import dither

def trace_quality (img, wm_img, W, args):
  if args.trace_quality or args.trace_psnr:
    print ("PSNR:", common.psnr (img, wm_img))
  if args.trace_quality:
    img_y = common.rgb_to_gray (img)
    wm_img_y = common.rgb_to_gray (wm_img)
    # signal strength
    print ("SIG:", np.mean (common.local_mean (W) * wm_img_y))
    # ssim
    from skimage.metrics import structural_similarity
    ssim_index = structural_similarity (img_y, wm_img_y, data_range = 255)
    print ("SSIM:", ssim_index)
    import tempfile, subprocess
    with tempfile.NamedTemporaryFile (suffix = ".png") as src_tmp_file:
      with tempfile.NamedTemporaryFile (suffix = ".png") as dst_tmp_file:
        common.save_rgb_image (src_tmp_file.name, img)
        common.save_rgb_image (dst_tmp_file.name, wm_img)
        # dssim
        command = ["dssim", src_tmp_file.name, dst_tmp_file.name]
        result = subprocess.run (command, capture_output=True, text=True)
        assert (result.returncode == 0)
        print ("DSSIM:", float (result.stdout.split()[0]))
        # ssimulacra2
        command = ["ssimulacra2", src_tmp_file.name, dst_tmp_file.name]
        result = subprocess.run (command, capture_output=True, text=True)
        assert (result.returncode == 0)
        print ("SA2:", float (result.stdout))
        # butteraugli
        command = ["butteraugli", src_tmp_file.name, dst_tmp_file.name]
        result = subprocess.run (command, capture_output=True, text=True)
        assert (result.returncode == 0)
        print ("BTA:", float (result.stdout))

# choose an integer r such that 99.5% of the watermark pixels is in [-r:r]
# for areas of constant color
def wm_range (W, strength):
  s = common.F (0, strength)
  for r in range (32):
    if np.mean (np.where (np.abs (W * s) < r, 1, 0)) > 0.995:
      return r
  eprint ("imagewmark: error detecting watermark range")
  return 16

# we need some headroom to add the watermark, so in this function we ensure that
# all channels of the image are in range [r, 255 - r], where r is the is the
# pixel offset the watermark will add for areas of constant color
def wm_pre_clip (img, W, strength):
  r = wm_range (W, strength)
  # - for grayscale, simple range clipping is enough
  # - for color images we watermark in the YIQ colorspace - however, since
  #   changing the Y channel in YIQ and converting back to RGB has the same
  #   effect on each of the RGB channels, we can simply use the range r for the
  #   individual color channels
  return np.clip (img, r, 255 - r)

# embedd watermark
def add_wm (img, W, strength, args):
  import skimage.color
  # extract luminance channel into `ay`
  ai, aq = None, None
  nchannels = img.shape[2] if len (img.shape) > 2 else 1
  img = wm_pre_clip (img, W, strength)
  if nchannels == 1:
    # RGB images automatically are float arrays due to colorspace conversion but for greyscale
    # we need to enforce it here to make the steps after loading the image work properly
    ay = img.astype (float)
  elif nchannels == 3:
    yiq_img = skimage.color.rgb2yiq (img)
    ay = yiq_img[:,:,0] * 255 # extract Y channel
  else:
    raise RuntimeError ("Input image with %d channels not supported" % nchannels)
  # variance: np.var (array) = ((array - array.mean())**2).mean()
  # https://numpy.org/doc/stable/reference/generated/numpy.var.html
  # local variance (needs window size):
  # scipy.ndimage.generic_filter (b, np.var, size = (3,3), mode = 'constant')
  I_var = common.local_variance (ay)
  dprint ("I_var:", I_var.shape, I_var.min(), '...', I_var.max());
  I_s = common.F (I_var, strength)
  dprint ("I_s:", I_s.shape, I_s.min(), '...', I_s.max());
  dst = ay + W * I_s
  # reconstruct image from luminance channel
  if nchannels == 3:
    yiq_img[:,:,0] = dst / 255 # reassign Y channel
    dst = skimage.color.yiq2rgb (yiq_img) * 255
  if args.trace_quality or args.trace_psnr:
    trace_quality (dither.round_pixels (img), dither.round_pixels (dst), W, args)
  return dst

# ADD
def command_add (input_img, output_img, message_hex, strength, args):
  # load host image
  try:
    face = common.load_rgb_image (input_img)
  except Exception as err:
    eprint ("imagewmark: error loading image '%s': %s" % (input_img, err))
    sys.exit (1)
  vprint (input_img + ':', "loaded:", face.shape, face.min(), '...', face.max());

  # parse message
  assert (len (message_hex) <= config.message_size / 8 * 2)

  message_bits = common.parse_payload (message_hex or '0')
  vprint ("Message:", ''.join (['%02x' % xx for xx in np.packbits (message_bits.flatten())])[0:32])
  dprint (str (message_bits * 1).replace ('0', '.'))

  # marker message, ECC encoded
  m_enc = convcode.encode (message_bits, args)
  m_enc = np.reshape (m_enc, config.payload_shape)
  dprint ("m_enc:", m_enc.shape, m_enc.min(), '...', m_enc.max())
  Lm = m_enc.shape[0] * m_enc.shape[1] # 256
  Ldim = m_enc.shape[0]
  assert Ldim * Ldim == Lm
  dprint ("m (needs encoding):", "size=%d" % Lm, m_enc.shape, m_enc.min(), '...', m_enc.max());

  # generate random matrix `r` (bp_r)
  Lr, bp_r = common.make_wm_pattern()

  # generate watermark unit by spread-spectrum encoding m_enc with bp_r
  Lwsmall = Ldim * Lr
  wmunit = np.empty ((Lwsmall, Lwsmall), dtype = float)
  for j in range (Ldim):
    for i in range (Ldim):
      lj = j * Lr; li = i * Lr
      wmunit[lj:lj+Lr, li:li+Lr] = bp_r if m_enc[j,i] else -bp_r
  # Generate key-dependent randomized matrix Ksmall
  Ksmall = common.make_wm_mask (Lwsmall)

  dprint ("wmunit:", wmunit.shape, wmunit.min(), '...', wmunit.max());
  if config.will_plot ('WMunit'):
    show (bp_r=bp_r, m=m_enc, wmunit=wmunit, Ksmall=Ksmall)


  # mask wmunit with Ksmall
  wmasked = wmunit * Ksmall
  dprint ("wmasked:", wmasked.shape, wmasked.min(), '...', wmasked.max());

  # set zoom level
  if (args.zoom > 0):
    # allow --zoom to directly set zoom level
    ZOOM = args.zoom
  else:
    # use dynamic_zoom from config (allow override with --dynamic-zoom)
    dynamic_zoom = args.dynamic_zoom if args.dynamic_zoom > 0 else config.dynamic_zoom
    ZOOM = min (face.shape[1], face.shape[0]) / Lwsmall / dynamic_zoom

    if ZOOM < config.minimum_zoom:
      ZOOM = config.minimum_zoom

  # repeat/flip watermark unit to have sufficient repetitions for the whole image
  hreps = int (face.shape[1] / Lwsmall / ZOOM) + 2
  vreps = int (face.shape[0] / Lwsmall / ZOOM) + 2

  if hreps % 2 == 0: # ensure watermark is centered around one unit in the middle
    hreps += 1
  if vreps % 2 == 0:
    vreps += 1

  # https://www.pythoninformer.com/python-libraries/numpy/index-and-slice/
  wmasked_rep = np.empty ((Lwsmall * vreps, Lwsmall * hreps), dtype = float)
  for hrep in range (hreps):
    for vrep in range (vreps):
      flipped = wmasked
      if hrep % 2:
        flipped = np.flip (flipped, 1)
      if vrep % 2:
        flipped = np.flip (flipped, 0)
      wmasked_rep[Lwsmall*vrep:Lwsmall*(vrep + 1), Lwsmall*hrep:Lwsmall*(hrep + 1)] = flipped
  W = common.zoom_image (wmasked_rep, ZOOM)
  dprint ("ZOOM = %.5g, W.shape=%s, face.shape=%s" % (ZOOM, W.shape, face.shape))
  if config.will_plot ('Wmasked'):
    show (Ksmall=Ksmall,wmasked=wmasked, wmasked_rep=wmasked_rep, W=W)

  dprint ("Watermark Image:", W.shape, W.min(), '...', W.max());

  # Crop W to host image size
  wcrop_y = (W.shape[0] - face.shape[0] + 1) // 2
  wcrop_x = (W.shape[1] - face.shape[1] + 1) // 2
  if wcrop_y or wcrop_x:
    W = W[wcrop_y:wcrop_y + face.shape[0], wcrop_x:wcrop_x + face.shape[1]]
    dprint ("Cropped W:", W.shape, W.min(), '...', W.max());

  wm_face = add_wm (face, W, strength, args)
  if config.with_debug:
    dprint ("Wmarked Image:", "strength=%.2f" % strength, wm_face.shape, wm_face.min(), '...', wm_face.max())
    if len (wm_face.shape) > 2 and wm_face.shape[2] == 3:
      dprint ("Wmarked: R", wm_face[:,:,0].min(), "...", wm_face[:,:,0].max())
      dprint ("Wmarked: G", wm_face[:,:,1].min(), "...", wm_face[:,:,1].max())
      dprint ("Wmarked: B", wm_face[:,:,2].min(), "...", wm_face[:,:,2].max())

  # float -> int conversion (see dither.py for comments), possible strategies are:
  #  - fs_dither (Floyd Steinberg)
  #  - rand_dither (Random)
  #  - trunc_pixels (Truncation)
  #  - round_pixels (Rounding)
  wm_face = dither.round_pixels (wm_face)

  if config.will_plot ('output'):
    in_out_diff = common.normalize (face.astype (float) - wm_face.astype (float))
    show (face=face, W=W, wm_face=wm_face, in_out_diff=in_out_diff)
  common.save_rgb_image (output_img, wm_face)
  vprint (output_img + ':', "written:", wm_face.shape, wm_face.min(), '...', wm_face.max());

  if args.trace_quality or args.trace_psnr:
    # re-read image to get PSNR for watermarking plus lossy image compression (jpg)
    reread_img = common.load_rgb_image (output_img)
    print ("XPSNR:", common.psnr (face, reread_img))
