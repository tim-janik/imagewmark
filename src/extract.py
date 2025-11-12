# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
import sys, os
import argparse
import config, common
from pathlib import Path
from time import time
from config import vprint, dprint, eprint
import math
from plotting import *
from ddist import distribution_divergence
import scipy.misc, scipy.signal, cv2
import skimage.color
import imageio
import subprocess
import convcode

def pre_scale (img):
  csize = min (img.shape[0], img.shape[1])
  ZOOM = config.pre_scale / csize
  if (ZOOM < 1):
    scaled_img = common.zoom_image (img, ZOOM)
    dprint ("pre_scale: %.1f%% %s -> %s" % (ZOOM * 100, img.shape, scaled_img.shape))
    return scaled_img
  else:
    return img

def corner_sync_scale (img):
  # upscale lower resolution images to pre_scale size to improve the accuracy
  # of the corner sync detection; use the smaller dimension to determine ZOOM
  # limit ZOOM to at most 4 to handle pathological cases (like an 10x1000 pixel image)
  csize = min (img.shape[0], img.shape[1])
  ZOOM = min (config.pre_scale / csize, 4)
  if (ZOOM < 1.05):
    # don't upscale images which are already at or really close to our desired resolution
    return img
  else:
    return common.zoom_image (img, ZOOM)

# Generatre watermark estimation for ACNF
def estimate_watermark (face_J, orig_J, strength, window):
  # Calculate for J: local variance, local mean, residue J´
  # TODO: use mean from local_variance
  J_mean = common.local_mean (face_J, window)             # µ = local mean of J
  dprint ("J_mean:", J_mean.shape, J_mean.min(), '...', J_mean.max())
  J_var = common.local_variance (face_J, window)          # σ²_J
  dprint ("J_var:", J_var.shape, J_var.min(), '...', J_var.max())
  if orig_J is None:
    J_delta = face_J - J_mean                             # J´ = J - µ
  else:
    J_delta = face_J - orig_J
  dprint ("J_delta:", J_delta.shape, J_delta.min(), '...', J_delta.max())
  if config.will_plot ('MSCN'): # MSCN = Mean Substracted Contrast Normalization
    show (J=face_J, J_mean=J_mean, J_var=J_var, J_delta=J_delta)

  # Calc σ²_J´, σ²_W and W_est
  J_dvar = common.local_variance (J_delta, window)        # σ²_J´
  # as we divide through J_dvar below, we limit the value to be not too close to
  # zero in order to avoid high peaks in the estimated watermark
  J_dvar = np.maximum (J_dvar, 0.01)
  dprint ("J_dvar:", J_dvar.shape, J_dvar.min(), '...', J_dvar.max())
  # assuming σ²_J ≈ σ²_I ; σ²_W == σ²(s * σ²_Wimg) ; s == F(σ²_I)
  # Note: np.var ([ -1,+1, -1,+1, -1,+1, ... ]) == 1.0 for σ²_Wimg
  strengthj = strength          # TODO: estimate strenth? try/search strength?
  J_Wvar = common.F (J_var, strengthj)   # σ²_W for W^ ≈ s(i,j) * (W = 1.0)
  dprint ("J_Wvar:", J_Wvar.shape, J_Wvar.min(), '...', J_Wvar.max())
  W_est = J_delta * J_Wvar / J_dvar                       # W^ = J´ * σ²_W / σ²_J´
  dprint ("W_est:", W_est.shape, W_est.min(), '...', W_est.max())
  if config.will_plot ('Estimation'):
    show (J=face_J, J_dvar=J_dvar, J_Wvar=J_Wvar, W_est=W_est)
  return W_est, J_Wvar

# Compute auto convolution, returns image twice the original size
def auto_convolution (img, pad_value = 0):
  # 32 bit fft is faster than 64 bit fft
  assert (img.dtype == np.float32)
  # pad bottom right
  img_p_margins = ((0, img.shape[0]), (0, img.shape[1]))
  img_p = np.pad (img, img_p_margins, constant_values = (pad_value, pad_value))
  # precondition to get identical results from rfft2/irfft2 (compared to fft2/ifft2)
  # always true due to padding
  assert (img_p.shape[1] % 2 == 0)
  # https://docs.scipy.org/doc/scipy/reference/generated/scipy.fft.rfft2.html
  img_a = scipy.fft.rfft2 (img_p)                             # FFT(img_p)
  del img_p
  return scipy.fft.irfft2 (img_a * img_a)                     # IFFT(FFT(img_p)*FFT(img_p))

# Generate auto convolution of all-white reference for brightness normalisation
def auto_conv_ones (shape):
  Ones_range = (1, 255)   # Start with 1 to avoid div-by-0
  Ones = np.ones (shape, dtype=np.float32) * Ones_range[1]
  return auto_convolution (Ones, pad_value = Ones_range[0])

# Normalize peaks to counter vanishing heights at the edges
def rescale_peaks (S2j, W_est, args):
  # Rescale outer/inner peaks
  O_denom = auto_conv_ones (W_est.shape)
  dprint ("O_denom:", O_denom.shape, O_denom.min(), '...', O_denom.max())
  S2j_uni = S2j / O_denom     # uniform upsampled s
  dprint ("S2j_uni:", S2j_uni.shape, S2j_uni.min(), '...', S2j_uni.max())
  S2_uni = common.normalize (S2j_uni, dtype = np.float32)
  del S2j_uni
  dprint ("S2_uni:", S2_uni.shape, S2_uni.min(), '...', S2_uni.max())
  if 'peaks' in args.dump:
    imageio.imwrite ('S2_uni.png', S2_uni)
    imageio.imwrite ('S2_uniζ.png', maxi (S2_uni, 20))
  if config.will_plot ('Peaks'):
    show (W_est=W_est, S2jζ=maxi(S2j), O_denom=O_denom, S2_uniζ=maxi(S2_uni))
  return S2_uni

def find_peaks (S2_uni, S2j, window):
  # WM Unit Map M
  S2M_uni = 255 * S2_uni                          # S´ adjusted for M
  dprint ("S2M_uni:", S2M_uni.shape, S2M_uni.min(), '...', S2M_uni.max())
  S2M_mean = common.local_mean (S2M_uni, window)  # µ_S´ = local mean of S´
  dprint ("S2M_mean:", S2M_mean.shape, S2M_mean.min(), '...', S2M_mean.max())
  S2M_std = np.std (S2M_uni)                      # standard deviation of S´ - "σ²_S´"
  dprint ("S2M_std:", S2M_std.shape, S2M_std.min(), '...', S2M_std.max())
  S2M_var = S2M_std ** 2                          # global variance of S´ - "σ²_S´"
  # S2M_var = common.local_variance (S2M_uni, S2M_uni.shape) # global variance of S´ - "σ²_S´"
  # dprint ("S2M_var:", S2M_var.shape, S2M_var.min(), '...', S2M_var.max())
  β = 4.3                                         # 3.0 … 4.3
  M2_simple = S2M_uni > S2M_mean + β * S2M_var    # booleans
  dprint ("M2_simple:", M2_simple.shape, M2_simple.min(), '...', M2_simple.max())

  # Peak detection
  peak_win = 37 # peak window size
  S2_maxi = scipy.ndimage.maximum_filter (S2_uni, size = peak_win)
  dprint ("S2_maxi:", S2_maxi.shape, S2_maxi.min(), '...', S2_maxi.max())
  bg_threshold = 0.15 # amplitude threshold against background
  S2_bgmax = (S2_maxi > bg_threshold) & (S2_maxi == S2_uni) # booleans
  dprint ("S2_bgmax:", S2_bgmax.shape, S2_bgmax.min(), '...', S2_bgmax.max())

  # Show M2_simple vs S2_bgmax
  if config.will_plot ('ThresholdedPeaks'):
    show (S2_uniζ=maxi(S2_uni), M2_simpleζ=maxi(M2_simple), S2_maxi37=S2_maxi, S2_bgmaxζ=maxi(S2_bgmax))

  # only use simple maximum peak detector
  M2 = (S2_maxi == S2_uni)
  dprint ("M2:", M2.shape, M2.min(), '...', M2.max())
  S2_peaks = M2
  if config.will_plot ('Peaks@1024'):
    iz = 32
    show (M2_simpleζ=maxi(M2_simple),
          M2_simple_at1024x768=M2_simple[768-iz:768+iz,1024-iz:1024+iz],
          M2_peak_at1024x768=M2[768-iz:768+iz,1024-iz:1024+iz],
          # M2ζ=maxi(M2),
          S2_peaksζ=maxi(S2_peaks))

  peak_positions = []
  rows, cols = np.nonzero (S2_peaks)
  for r, c in zip (rows, cols):
    assert S2_peaks[r][c] > 0 # boolean map
    peak_positions.append ((c,r, (S2M_uni[r][c] - S2M_mean[r][c]) / S2M_var, S2j[r][c]))     # (x,y) ordering
  return peak_positions, S2_peaks

def start_peaks_to_grid (args, img, peaks):
  clocksecs = common.clocksecs_start()
  peaks2grid = Path (os.path.dirname (__file__), "..", "cxx", "peaks2grid").resolve()
  p2g = subprocess.Popen ([ peaks2grid ],
                          stdin = subprocess.PIPE,
                          stdout = subprocess.PIPE,
                          universal_newlines = True,
                          bufsize = 0)
  p2g.clocksecs = clocksecs

  # Pass peaks to C++ helper
  p2g.stdin.write ("size %d %d\n" % (img.shape[1], img.shape[0])) # size <width> <height>
  p2g.stdin.write ("perspective %d\n" % args.perspective)
  min_edge_bound = config.payload_shape[0] * config.Lr * 0.9
  dprint ("min_edge_bound: %.4f" % min_edge_bound)
  p2g.stdin.write ("min_edge_bound %.4f\n" % min_edge_bound)
  p2g.stdin.write ("peak_count %d %d\n" % (args.norm_peak_count, args.raw_peak_count))
  for peak in peaks:
    p2g.stdin.write ("peak %d %d %.17g %.17g\n" % (peak[0], peak[1], peak[2], peak[3]))
  p2g.stdin.write ("start\n")
  p2g.stdin.flush()
  return p2g

def stop_peaks_to_grid (p2g):
  clocksecs = p2g.clocksecs
  t = time()
  try:
    p2g.stdin.write ("stop\n")
    p2g.stdin.flush()
  except BrokenPipeError:
    # this happens if the peaks2grid process is done already
    pass
  p2g.communicate()
  dprint ("peaks2grid: stopped after %.1f ms" % ((time() - t) * 1000))
  common.clocksecs_add ('peaks2grid', clocksecs)

def peaks_to_grid_parse_peaks (p2g, S2_xpeaks):
  # Fetch detected peaks
  for line in p2g.stdout:
    ps = line.strip().split()
    if (ps[0] == "peak"):
      x = int (ps[1])
      y = int (ps[2])
      height = float (ps[3])
      S2_xpeaks[y][x] = 1 # height
    if (ps[0] == "end_peaks"):
      return

class Grid:
  def __init__ (self, index):
    self.index = index
    self.units = []
    self.features = {}
  def __repr__ (self):
    s = '<extract.Grid'
    s += ' index=%d' % self.index
    s += ' n_units=%d' % len (self.units)
    s += ' features=' + str (self.features)
    s += '>'
    return s

def peaks_to_grid_parse_grids (p2g):
  grids = []
  # Fetch detected grid
  for line in p2g.stdout:
    ps = line.strip().split()
    if (ps[0] == "start_grid"):
      ps = ps[1:]
      grid_index = int (ps[0])
      grid = Grid (grid_index)
    elif (ps[0] == "end_grid"):
      grids.append (grid)
    elif (ps[0] == "unit"):
      ps = ps[1:]
      assert (len (ps) == 10)
      gx = int (ps[0])
      gy = int (ps[1])
      ps = ps[2:]
      pg = ((float (ps[0]), float (ps[1])), (float (ps[2]), float (ps[3])), (float (ps[4]), float (ps[5])), (float (ps[6]), float (ps[7])))
      grid.units += [ ((gx, gy), pg) ]
      # (gx,gy) - relative position of unit within grid
      # pg - pixel rectangle of the unit
    elif (ps[0] == "feature"):
      ps = ps[1:]
      assert (len (ps) == 2)
      fname = ps[0]
      fvalue = float (ps[1])
      grid.features[fname] = fvalue
    elif (ps[0] == "end_grids"):
      yield grids
      grids = []
    else:
      assert False, "error parsing peaks2grid process output"

def send_array (process, array):
  process.stdin.write (np.array (array.shape).tobytes())
  process.stdin.write (array.tobytes())
  process.stdin.flush()

def corner_sync (W_est, wmasked, conv_decoder):
  clocksecs = common.clocksecs_start()
  ZOOM = 2
  W_est_width = W_est.shape[1]
  W_est_height = W_est.shape[0]
  wmasked_up = common.zoom_image (wmasked, ZOOM)
  cornersync = Path (os.path.dirname (__file__), "..", "cxx", "cornersync").resolve()
  cornersync_args = [ cornersync ]
  if (config.verbose >= 2):
    cornersync_args.append ("verbose")
  proc = subprocess.Popen (cornersync_args, stdin = subprocess.PIPE, stdout = subprocess.PIPE)
  send_array (proc, W_est.astype (np.float32))
  send_array (proc, wmasked_up.astype (np.float32))
  lines = proc.communicate()[0].decode('utf-8')
  for line in lines.splitlines():
    l = line.strip().split()
    if (l[0] == "corner_sync"):
      zoom = float (l[1])
      center_x = float (l[2]) * 2
      center_y = float (l[3]) * 2
      grid_inside = Grid (0)
      grid_full = Grid (1)
      for ux in range (-20, 21):
        for uy in range (-20, 21):
          sz = zoom * 128 / 2
          cx = center_x + ux * sz * 2
          cy = center_y + uy * sz * 2
          corners = ((cx - sz, cy - sz), (cx + sz, cy - sz), (cx + sz, cy + sz), (cx - sz, cy + sz))
          corners_visible = 0
          for i in range (4):
            if 0 <= corners[i][0] < W_est_width * 2:
              if 0 <= corners[i][1] < W_est_height * 2:
                corners_visible += 1
          if corners_visible == 4:
            grid_inside.units += [ ((ux, uy), corners) ]
          if corners_visible > 0:
            grid_full.units += [ ((ux, uy), corners) ]
      grid_inside.features['regularity'] = 4
      grid_full.features['regularity'] = 4

  result = [[ grid_inside, grid_full ]]
  common.clocksecs_add ('cornersync', clocksecs)
  return result

def get_grid_polygons (grid):
  polygons = []
  for grid_unit in grid.units:
    polygons.append (grid_unit[1])
  return polygons

def affine_transform_image (rcimg, xyaffine, size = None, zoom = 1):
  size = size or rcimg.shape
  T = xyaffine * zoom                           # support zooming into
  dst = np.empty (size)
  for y in range (dst.shape[0]):
    for x in range (dst.shape[1]):
      psrc = affine ((x,y), T)                  # src pixel coord from dst
      x2, y2 = np.round (psrc).astype (int)     # nearest
      if y2 >= 0 and y2 < W_est.shape[0] and \
         x2 >= 0 and x2 < W_est.shape[1]:
        dst[y][x] = W_est[y2][x2]
      else:
        dst[y][x] = 0
  return dst

def affine_transform_image_scipy (rcimg, xyaffine, size = None, zoom = 1):
  size = size or rcimg.shape
  # scipy uses (y,x) as index vector into rcimg
  (a11,a12,a13), (b11,b12,b13) = xyaffine       # decompose
  T = [ (b12, b11, b13), (a12, a11, a13) ]      # swap x/y coordinates of the affine
  T = np.array (T) * zoom                       # support zooming into
  dst = scipy.ndimage.affine_transform (rcimg, T, None, size, order = 3, prefilter = False)
  return dst

def affine_transform_image_cv2 (rcimg, xyaffine, size = None, zoom = 1):
  size = size or rcimg.shape
  T = xyaffine * zoom                           # support zooming into
  # CV2 calls `dst = src * T` the "inverse"
  dst = cv2.warpAffine (rcimg, T, size, flags = cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP)
  return dst

# Generate image variants by applying flip and rotate
def rotateflip8 (img):
  s8 = []
  s8 += [img, np.flip (img, 1), np.flip (img, (0, 1)), np.flip (img, 0)]
  img = np.rot90 (img)
  s8 += [img, np.flip (img, 1), np.flip (img, (0, 1)), np.flip (img, 0)]
  return s8

# Point to point distance (or edge length)
def point_dist (p1, p2):
  # √( (x2-x1)^2 + (y2-y1)^2 )
  dist = math.sqrt ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
  return dist

def rhombus_area (corners):
  # calculate rhombus area via diagonals, corners is assumed to
  # contain the 4 adjacent corner points of a rhombus
  e = point_dist (corners[0], corners[2])
  f = point_dist (corners[1], corners[3])
  area = e * 0.5 * f
  return area

# create Y array for the case that unmasking results in normal distributed noise
def gen_normal_dist_sum (Lwu, LR, wmasked_up):
  # setup deterministic PRNG
  prng = np.random.Generator (np.random.PCG64 (seed = 42))
  normal_dist_image = prng.choice ([-1.0, 1.0], size = (Lwu,Lwu))
  normal_dist_image *= wmasked_up
  return sum_image_blocks (normal_dist_image, LR) / LR

# Extract Watermark from pixel square (correctly oriented)
def pixels_to_watermark (Y, score, conv_decoder, args):
  cpusecs = common.cpusecs_start()
  #dprint ("Y:", Y.shape, Y.min(), '...', Y.max())
  # Use the 256 bits to decode 128 bits
  Yflat = Y.flatten()
  # normalize soft bits using mean:
  #   - before normalization -mean..mean
  #   - after normalization   0..1
  abs_mean = np.mean (abs (Yflat))
  if (abs_mean < 1e-5): # avoid division by zero
    abs_mean = 1
  Ynorm = (Yflat / abs_mean + 1) * 0.5
  B, error = convcode.decode (conv_decoder, Ynorm)

  bits = ''.join (['%02x' % xx for xx in np.packbits (B.flatten())])
  vprint (bits, "JSD=%.2f%%" % (100 * score), "pixels_mscn=" , Y.min(), '…', Y.max())

  if config.will_plot ('BitPixels', False):
    show (title = "JSD=%.2f%%" % (100 * score),
          Y=Y, # Ynorm = Ynorm.reshape (16, 16),
          B128 = B.reshape (8, 16))

  # Watermark info
  wmi = { "bits": bits,
          "jsd": score,
          "bitmean": np.mean (abs (Yflat)),
          "bitstd": np.std (abs (Yflat)),
          "error": error,
         }
  if args.expect:
    X = convcode.encode (common.parse_payload (args.expect), args).astype (int)
    soft_error = 0
    for i in range (len (X)):
      soft_error += (X[i] - Ynorm[i]) * (X[i] - Ynorm[i])
    wmi["xerror"] = math.sqrt (soft_error / 128 * 2)
  common.cpusecs_add ('pixels2wm', cpusecs)
  return wmi

# normalize image block std / mean efficiently (without loops)
def normalize_image_blocks (image, block_size, mean = False, std = False):
  assert (mean or std)
  height, width = image.shape
  normalized_image = image.reshape ((height // block_size, block_size, width // block_size, block_size))

  if (mean):
    means = np.mean (normalized_image, axis=(1,3), keepdims = True)
    normalized_image = normalized_image - means
  if (std):
    std_devs = np.std (normalized_image, axis=(1,3), keepdims = True)
    std_devs_mask = std_devs > 1e-5
    normalized_image = normalized_image / np.where (std_devs_mask, std_devs, 1.0)
    normalized_image *= np.where (std_devs_mask, 1.0, 0.0)

  return normalized_image.reshape (image.shape)

# sum up image block efficiently (without loops)
def sum_image_blocks (image, block_size):
  height, width = image.shape
  reshaped_image = image.reshape ((height // block_size, block_size, width // block_size, block_size))
  return np.sum (reshaped_image, axis=(1,3))

def watermark_from_grid (grid, uz, LR, Ldim, Lwu, face_J, orig_J, wmasked_up, W_est, normal_dist_sum, ZOOM, min_ws_score, S2_xpeaks, conv_decoder, args):
  cpusecs = common.cpusecs_start()
  upsample_factor = 2  # peaks are detected on FFT image, upsampled by a factor of 2
  # visualize and debug grid with rectangle list
  grid_regularity = grid.features['regularity']
  grid_rectangles = [np.array (u[1]) / upsample_factor for u in grid.units]
  grid_area_size = sum (rhombus_area (r) for r in grid_rectangles)
  coverage = grid_area_size * 100 / (face_J.shape[0] * face_J.shape[1])
  if config.will_plot ('Grid', False):
    grid_title = ("Grid: " +
                  "len=%d " % len (grid_rectangles) +
                  "regularity=%.1f " % grid_regularity +
                  "coverage=%.1f%%" % coverage)
    vprint (grid_title) # "rects:", grid_rectangles
    polyanimation (grid_title, face_J, grid_rectangles, 'red', clear = False, animate = False) # keypress = True

  if config.will_plot ('Polygons', False):
    polygons = get_grid_polygons (grid)
    # note, animation the polygons was only useful back when we generated overlapping or duplicate polygons
    polyanimation ("Grid [%d]" % grid.index, maxi (S2_xpeaks), polygons, 'random', clear = False, animate = False)
  # dprint ("polygons", get_grid_polygons (grid))

  # Construct 𝔀_s (geometrically restored watermark unit, still masked and orientation unknown) by summating grid rectangles
  torigin = np.float32 ([(0,uz), (0,0), (uz,0)])
  w_s = np.zeros ((Lwu, Lwu))
  w_s_count = 0
  if orig_J is None:
    face_J_diff = face_J
  else:
    face_J_diff = face_J - orig_J
  # sum up all rectangles into a single watermark pattern w_s
  for grid_unit in grid.units:
    wm_rect = grid_unit[1]
    # transform wm_rect into origin
    at = cv2.getAffineTransform (torigin, np.float32 ([wm_rect[0], wm_rect[1], wm_rect[2]]))
    t_size = Lwu # 8 * R_size
    current_w_s = affine_transform_image_cv2 (face_J_diff, at, (t_size,t_size), 1 / ZOOM) # geometric restauration
    # flip rectangle according to their relative position within the grid
    if (grid_unit[0][1] % 2 == 1):  # flip vartically adjacent untis according to relative position
      current_w_s = np.flip (current_w_s, 1)
    if (grid_unit[0][0] % 2 == 1):  # flip horizontally adjacent untis according to relative position
      current_w_s = np.flip (current_w_s, 0)
    w_s += normalize_image_blocks (current_w_s, LR, std=True) # normalize block std
    w_s_count += 1

  # DEBUG 21: affine back transformations
  if config.will_plot ('AffineWM', False):
    W_trans = affine_transform_image_cv2 (W_est, at, W_est.shape, 1 / ZOOM)
    show (W_est=W_est, w_s=w_s, W_trans = W_trans, W_transζ = maxi (W_trans))
    del W_trans

  if w_s_count > 1:
    # normalize w_s pixel heights
    w_s /= w_s_count

  # rotate and unmask 𝔀_s (geometrically restored watermark unit) with K to get 𝔀_r (spread-spectrum encoded watermark unit)
  # unmask 𝔀_s (geometrically restored watermark unit) with K to get 𝔀_r (spread-spectrum encoded watermark unit)
  # rotate the watermark pattern, retain the state with maximum 𝓝 (0,1) divergence
  ws_score, ws_Y = -1, None
  w_s = normalize_image_blocks (w_s, LR, mean=True, std=True) # Mean Substracted Contrast Normalization (MSCN) for all blocks
  for w_r in rotateflip8 (w_s):
    wr_y = w_r * wmasked_up # unmask with key
    Y = sum_image_blocks (wr_y, LR) / LR
    # to get a realistic JSD for a Y matrix that contains zero, replace zeros with Y from normal dist image
    Y_no_zeros = np.where (abs (Y) < 1e-5, normal_dist_sum, Y)
    ddiv = distribution_divergence (Y_no_zeros)
    state_score = ddiv["JensenShannon"] # ddiv["KullbackLeibler"]
    if state_score >= ws_score:
      ws_score, ws_Y = state_score, Y
    # DEBUG 22: unmasked state variants
    #  show (title = "𝔀 → Y (%f)" % state_score, K=K, w_s=w_s, w_r=w_r, wr_y=wr_y, Y=Y)

  dprint ("w_s [%d | %6.2f %%]:" % (grid.index, ws_score * 100), w_s.shape, w_s.min(), '...', w_s.max())
  feature_str = "grid %d  ws_score = %.4f" % (grid.index, ws_score)
  for gf_entry in grid.features.items():
    feature_str += "  %s = %.4f" % (gf_entry[0], gf_entry[1])
  dprint (feature_str)

  # skip decoding step if minimum ws_score is not reached
  wmi = None
  if ws_score >= min_ws_score:
    wmi = pixels_to_watermark (ws_Y, ws_score, conv_decoder, args)
    # add statistics
    wmi['regularity'] = grid.features['regularity']
    wmi['coverage'] = coverage
  common.cpusecs_add ('grid2wm', cpusecs)
  return wmi

# Sort `kyp` by decreasing .response, return `kyp` list and `des` array sorted and shortened
def take_best_responses (kyp, des, nmax = 262144):
  indices = range (len (kyp))
  indices = sorted (indices, key = lambda i: -kyp[i].response)  # sort indices into list (argsort)
  indices = indices[:nmax]                                      # shorten index list
  kyp = tuple (kyp[i] for i in indices)
  des = des[ indices , :]
  return (kyp, des)

# Align source image `colimg1` to match template image `colimg2`, return transformed result.
def align_image (colimg1, colimg2):
  cpusecs = common.cpusecs_start()
  # perform matching on grayscale images
  img1 = cv2.cvtColor (colimg1, cv2.COLOR_BGR2GRAY)
  img2 = cv2.cvtColor (colimg2, cv2.COLOR_BGR2GRAY)
  # height, width = simg.shape
  vprint ("ALIGN: source=%s, template=%s" % (colimg1.shape, colimg2.shape))
  # == SIFT extraction ==
  sift = cv2.SIFT_create()
  MAX_VECTORS = 8192    # OpenCV2 asserts 1<<18 as MAX: https://github.com/opencv/opencv/issues/5700
  kp1, des1 = sift.detectAndCompute (img1, None)
  if kp1 is None or len (kp1) < 1 or des1 is None or len (des1) < 1:
    return None     # too few features
  kp1, des1 = take_best_responses (kp1, des1, MAX_VECTORS)
  kp2, des2 = sift.detectAndCompute (img2, None)
  if kp2 is None or len (kp2) < 1 or des2 is None or len (des2) < 1:
    return None     # too few features
  kp2, des2 = take_best_responses (kp2, des2, MAX_VECTORS)
  ppd1 = img1.shape[0] * img1.shape[1] / len (des1) # pixels per descriptor
  ppd2 = img2.shape[0] * img2.shape[1] / len (des2)
  vprint ("ALIGN: SIFT descriptors1=%u(%.1fpx) descriptors2=%u(%.1fpx)" % (len (des1), ppd1, len (des2), ppd2))
  common.cpusecs_add ('align1_sift', cpusecs)
  if config.will_plot ('ALIGN'):
    img3 = cv2.drawKeypoints (img1, kp1, None, flags = cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
    plt.imshow (img3); plt.show()
  # == kNN matching & outlier rejection ==
  bf = cv2.BFMatcher() # max: 262144
  matches = bf.knnMatch (des1, des2, k = 2) # brute force knn matching
  common.cpusecs_add ('align2_knnmatch', cpusecs)
  # The probability for a bad match skyrockets once the first/second best match ratio exceeds 0.75
  # https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf - Distinctive Image Features from Scale-Invariant Keypoint, David G. Lowe, 2004
  good = []
  for m,n in matches: # select by ratio to second best <= 0.75
    if m.distance < 0.75 * n.distance:
      good.append (m)
  # assuming half the matches are possibly outliers, apply 50% quantil thresholding
  good = sorted (good, key = lambda x: x.distance)
  good_ratios = len (good)
  len_thresholded = int (good_ratios * 0.5) if good_ratios > 30 else good_ratios
  good = good[:len_thresholded]
  vprint ("ALIGN: SIFT kNN matches=%u good=%u thresholded=%u" % (len (matches), good_ratios, len (good)))
  if config.will_plot ('ALIGN'):
    llgood = [[m] for m in good]                # cv2.drawMatchesKnn expects list of lists as matches
    img3 = cv2.drawMatchesKnn (img1, kp1, img2, kp2, llgood, None, flags = cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
    plt.imshow (img3); plt.show()
  if len (good) <= 11:                          # too few matches
    return None
  # == RANSAC & Homography search ==
  pts1 = np.float32 ([ kp1[m.queryIdx].pt for m in good ]).reshape (-1, 1, 2)
  pts2 = np.float32 ([ kp2[m.trainIdx].pt for m in good ]).reshape (-1, 1, 2)
  M, mask = cv2.findHomography (pts1, pts2, cv2.RANSAC, 3) # 1..10
  matchesMask = mask.ravel().tolist()
  common.cpusecs_add ('align3_homography', cpusecs)
  vprint ("ALIGN: Homography mask n=%u ones=%u" % (len (mask), np.count_nonzero (mask))); vprint (M)
  if config.will_plot ('ALIGN'):
    h,w = img1.shape
    pts = np.float32 ([ [0,0], [0,h-1], [w-1,h-1], [w-1,0] ]).reshape (-1, 1, 2)
    dst = cv2.perspectiveTransform (pts, M)
    img3 = cv2.polylines (img2.copy(), [np.int32 (dst)], True, 255, 3, cv2.LINE_AA)
    draw_params = dict (matchesMask = matchesMask, # draw only inliers
                        singlePointColor = None, flags = 2)
    img3 = cv2.drawMatches (img1, kp1, img3, kp2, good, None, **draw_params)
    plt.imshow (img3, 'gray'); plt.show()
  # == ECC - Enhanced Correlation Coefficient Maximization ==
  # Matrix format for cv2.MOTION_HOMOGRAPHY
  warp_matrix = np.array (M, dtype = np.float32) # float64 -> float32, needed for findTransformECC
  # Termination criteria (iteration count and epsilon)
  criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 400, 0.0002)
  # Refine M until criteria is reached, throws if the algorithm cannot terminate
  try:
    (ecc, M) = cv2.findTransformECC (img1, img2, warp_matrix, cv2.MOTION_HOMOGRAPHY, criteria)
  except cv2.error as e:
    if e.code == -215:  # Assertion failed "map.cols == 3"
      return None
    if e.code == -7:    # Iterations do not converge
      return None
    raise e
  common.cpusecs_add ('align4_ecc', cpusecs)
  vprint ("ALIGN: ECC:", ecc, 'M:\n', M)
  if config.will_plot ('ALIGN'):
    h,w = img1.shape
    pts = np.float32 ([ [0,0], [0,h-1], [w-1,h-1], [w-1,0] ]).reshape (-1, 1, 2)
    dst = cv2.perspectiveTransform (pts, warp_matrix)
    img3 = cv2.polylines (img2.copy(), [np.int32 (dst)], True, 255, 3, cv2.LINE_AA)
    plt.imshow (img3); plt.show()
  # == Backwards Transformation of Source ==
  reconstruction = cv2.warpPerspective (colimg1, M, (colimg2.shape[1], colimg2.shape[0]), flags = cv2.INTER_LINEAR)
  if config.will_plot ('ALIGN'):
    h,w = img1.shape
    pts = np.float32 ([ [0,0], [0,h-1], [w-1,h-1], [w-1,0] ]).reshape (-1, 1, 2)
    dst = cv2.perspectiveTransform (pts, M)
    img3 = cv2.polylines (img2.copy(), [np.int32 (dst)], True, 255, 3, cv2.LINE_AA)
    draw_params = dict (matchesMask = matchesMask, # draw only inliers
                        singlePointColor = None, flags = 2)
    img3 = cv2.drawMatches (img1, kp1, img3, kp2, good, None, **draw_params)
    show (Source=colimg1[:,:,::-1], Template=img2, Homography=img3, Reconstructed=reconstruction[:,:,::-1])
  common.cpusecs_add ('align5_warp', cpusecs)
  return reconstruction

# GET
def command_get (input_img, strength, args):
  clocksecs = common.clocksecs_start()
  cpusecs = common.cpusecs_start()
  # Load WM image and its original
  if args.original:
    face_IMG = common.load_bgr_image (input_img)
    common.cpusecs_add ('origi1_loadface', cpusecs)
    orig_IMG = common.load_bgr_image (args.original)
    common.cpusecs_add ('origi2_loadorig', cpusecs)
    reco_IMG = align_image (face_IMG, orig_IMG)
    common.cpusecs_add ('origi3_align', cpusecs)
    orig_J = common.bgr_to_gray (orig_IMG)
    del orig_IMG
    is_aligned = reco_IMG is not None    # managed to reconstruct aligned image
    face_J = common.bgr_to_gray (reco_IMG if is_aligned else face_IMG)
    del face_IMG, reco_IMG
    if is_aligned:
      assert (orig_J.shape == face_J.shape)
    else:
      pass # image might be clipped
    wmi_list = []
    if is_aligned:
      common.cpusecs_add ('origi4_aligned', cpusecs)
      dprint ("orig_J:", orig_J.shape, orig_J.min(), '...', orig_J.max())
      wmi_list = extract_from_grey (face_J, orig_J, strength, args)
      common.cpusecs_add ('origi5_extract', cpusecs)
  else:
    is_aligned = False
    # Load WM image
    face_J = common.bgr_to_gray (common.load_bgr_image (input_img))
    common.clocksecs_add ('cmdget1_loadface', clocksecs)
    # pre scale high resolution images
    face_J = pre_scale (face_J)
    common.clocksecs_add ('cmdget2_prescale', clocksecs)
    wmi_list = extract_from_grey (face_J, None, strength, args)
    common.clocksecs_add ('cmdget3_extractfromgrey', clocksecs)
  # ADD: print WM with score
  if args.jsonfile:
    common.clocksecs_add ('command_get', clocksecs)
    import json
    result = {
      "width": face_J.shape[1],
      "height": face_J.shape[0],
      "filename": input_img,
      "aligned": is_aligned,
      "matches": wmi_list,
      "time": time() - args.startup_time,
    }
    stats = common.get_stats()
    stats.update (result)
    jout = open (args.jsonfile, 'w')
    jout.write (json.dumps (stats, sort_keys = False, indent = 2) + '\n')
    jout.close()
  else: # non JSON output
    for wmi in wmi_list:
      # {'bits': 'abc', 'jsd': 0.997, 'bitmean': 5.31, 'bitstd': 0.732, 'error': 0.123, 'regularity': 3.0, 'coverage': 75.1, 'time': 1.2, 'window': 9}
      marker = '●' if wmi["jsd"] >= 0.90 else '◎' if wmi["jsd"] >= 0.55 else '◌'
      print (marker, wmi["bits"], "JSD=%.1f%%" % (100.0 * wmi["jsd"]), "mean=%.2f±%.3f" % (wmi["bitmean"], wmi["bitstd"]), "err=%.2f" % wmi["error"], "cov=%.1f%%" % wmi["coverage"])

# GET
def extract_from_grey (face_J, orig_J, strength, args):
  cpusecs = common.cpusecs_start()
  if None is not orig_J:
    assert (orig_J.shape == face_J.shape)
  dprint ("face_J:", face_J.shape, face_J.min(), '...', face_J.max())
  face_height, face_width = face_J.shape

  Ldim = config.payload_shape[0]

  # generate random matrix `r` (bp_r)
  Lr, bp_r = common.make_wm_pattern()

  # generate expected watermark unit
  Lwsmall = Ldim * Lr
  wmunit = np.empty ((Lwsmall, Lwsmall), dtype = float)
  for j in range (Ldim):
    for i in range (Ldim):
      lj = j * Lr; li = i * Lr
      wmunit[lj:lj+Lr, li:li+Lr] = bp_r

  # Generate key-dependent randomized matrix Ksmall used for watermark masking
  Ksmall = common.make_wm_mask (Lwsmall)

  # mask wmunit with Ksmall
  wmasked = wmunit * Ksmall

  dprint ("wmasked:", wmasked.shape, wmasked.min(), '...', wmasked.max())

  conv_decoder = convcode.start_decoder (args)

  # Watermark detection sync strategies (steps somewhat sorted to minimize run-time cost):
  #  - first step:  try to find watermark with smallest window size, using auto convolution for synchronization
  #  - second step: try to find watermark with smallest window size, using corner sync for synchronization
  #  - finally:     try all other window sizes, using auto convolution for synchronization
  #
  # Usually the first step will succeed, if the watermark can be detected at
  # all, and auto convolution is much faster than corner sync, so we start with
  # that. If the first step fails, and the image is suitable for corner sync, there
  # is a good chance that corner sync will find the watermark. Finally try the remaining
  # window sizes with auto convolution; in some cases different window sizes can still
  # succeed with auto convolution even if the first window size did not work.
  #
  # In case face_J could be aligned to the unwatermarked original image, there is little
  # use for synchronization via auto convolution, so we only use corner sync by default.
  if args.cornersync >= 1:      # cornersync=on
    sync_list = [ (config.extract_window_size[0], True) ]
  elif args.cornersync == 0:    # cornersync=off: ACNF
    sync_list = [ (window_size, False) for window_size in config.extract_window_size ]
  elif orig_J is not None:      # cornersync=auto, orig_J: decode with aligned original
    sync_list = [ (config.extract_window_size[0], True) ]
  else:                         # cornersync=auto, !orig_J (blind decoding)
    sync_list = [ (window_size, False) for window_size in config.extract_window_size ]
    sync_list.insert (1, (config.extract_window_size[0], True)) # insert cornersync after first window size
  wmi_list = []
  for (window_size, use_corner_sync) in sync_list:
    win_wmi_list, done = detect_watermark_with_window (face_J, orig_J, strength, args, (window_size, window_size), wmasked, use_corner_sync, conv_decoder)
    if done:
      # if done is true, we had a very good match, so we omit the rest of the results
      wmi_list = win_wmi_list
      break
    else:
      wmi_list += win_wmi_list

  wmi_list = sorted (wmi_list, key = lambda wmi: -wmi['jsd'])

  convcode.stop_decoder (conv_decoder)
  common.cpusecs_add ('extract_from_grey', cpusecs)
  return wmi_list

def auto_convolution_sync (W_est, args, window, face_J, J_Wvar):
  cpusecs = common.cpusecs_start()
  # ACNF of W^ (W_est)
  S2j = auto_convolution (W_est.astype (np.float32))
  # TODO: np.abs discards the sign of the auto convolution - we may want to
  # preserve it (also in the steps after computing the symmetry matrix)
  # this change needs testing
  S2j = np.abs (S2j)
  dprint ("S2j:", S2j.shape, S2j.min(), '...', S2j.max())
  if config.will_plot ('ACNF'):
    show (J=face_J, J_Wvar=J_Wvar, S2j=S2j, S2jζ=maxi (S2j))
  S2_uni = rescale_peaks (S2j, W_est, args)

  ppos, S2_peaks = find_peaks (S2_uni, S2j, window)
  del S2_uni
  vprint ("peak_list:", "len=%d" % len (ppos))
  S2_xpeaks = np.zeros (S2_peaks.shape)

  p2g = start_peaks_to_grid (args, S2_peaks, ppos)
  peaks_to_grid_parse_peaks (p2g, S2_xpeaks)
  grid_lists = peaks_to_grid_parse_grids (p2g)
  result = S2_xpeaks, p2g, grid_lists
  common.cpusecs_add ('auto_convolution_sync', cpusecs)
  return result

def detect_watermark_with_window (face_J, orig_J, strength, args, window, wmasked, use_corner_sync, conv_decoder):
  cpusecs = common.cpusecs_start()
  sync_label = "CORNER" if use_corner_sync else "ACNF"
  dprint ("==== using (%dx%d) window for local_mean/local_variance; %s sync ====" % (window[0], window[1], sync_label))
  if use_corner_sync:
    face_J = corner_sync_scale (face_J)
    if orig_J is not None:
      orig_J = corner_sync_scale (orig_J)
    W_est, J_Wvar = estimate_watermark (face_J, orig_J, strength, window)
    S2_xpeaks = np.zeros (W_est.shape)
    grid_lists = corner_sync (W_est, wmasked, conv_decoder)
    result = watermark_from_grid_lists (grid_lists, face_J, orig_J, W_est, wmasked, S2_xpeaks, args, window, conv_decoder)
    common.cpusecs_add ('cornersync_detect', cpusecs)
    return result
  else:
    W_est, J_Wvar = estimate_watermark (face_J, orig_J, strength, window)
    S2_xpeaks, p2g, grid_lists = auto_convolution_sync (W_est, args, window, face_J, J_Wvar)
    result = watermark_from_grid_lists (grid_lists, face_J, orig_J, W_est, wmasked, S2_xpeaks, args, window, conv_decoder)
    stop_peaks_to_grid (p2g)
    common.cpusecs_add ('peaks2grid_detect', cpusecs)
    return result

def watermark_from_grid_lists (grid_lists, face_J, orig_J, W_est, wmasked, S2_xpeaks, args, window, conv_decoder):
  ZOOM = 2
  Lr   = config.Lr
  Ldim = config.payload_shape[0]
  LR   = ZOOM * Lr

  wmasked_up = common.zoom_image (wmasked, ZOOM)

  uz = Ldim * Lr * ZOOM                          # watermark unit egde size
  Lwu = uz
  dprint ("Lwu", Lwu)

  # flip and rotate wmasked_up
  if config.will_plot ('Orientations'):
    W8 = rotateflip8 (wmasked_up)
    show (title = "Flip and Rotate wmasked_up", W0=W8[0], W1=W8[1], W2=W8[2], W3=W8[3], W4=W8[4], W5=W8[5], W6=W8[6], W7=W8[7])


  normal_dist_sum = gen_normal_dist_sum (Lwu, LR, wmasked_up)

  # match --expect <bits> to finish early
  expected_bits = None
  if args.expect:
    expected_bits = common.parse_payload (args.expect)
    expected_bits = ''.join (['%02x' % xx for xx in np.packbits (expected_bits.flatten())])[0:32]
  done_expecting = False

  # Collect possible watermarks
  best_jsd, wmi_list = -1, []
  jsd_threshold = config.parse_percentage (args.jsd_threshold)
  jsd_window_threshold = max (config.parse_percentage (config.jsd_window_threshold), jsd_threshold)
  jsd_min_threshold = config.parse_percentage (config.jsd_min_threshold)
  wmi_time = args.startup_time

  # Detect lists of grids with decreasing regularity
  for grid_list in grid_lists:
    # peaks2grid can send us empty grid lists?
    if len (grid_list) < 1:
      continue

    # show the current grid list
    grid_list_regularity = grid_list[0].features['regularity'] if len (grid_list) > 0 else '-/-'
    vprint ("grid_list:", "regularity=%g" % grid_list_regularity, "len=%d" % len (grid_list))

    # Try to extract a watermark from each grid
    for grid in grid_list:
      # if we already have a "good" match, only consider other "good" matches to improve search performance
      if best_jsd > jsd_threshold:
        min_ws_score = jsd_threshold
      else:
        min_ws_score = jsd_min_threshold
      wmi = watermark_from_grid (grid, uz, LR, Ldim, Lwu, face_J, orig_J, wmasked_up, W_est, normal_dist_sum, ZOOM, min_ws_score, S2_xpeaks, conv_decoder, args)
      if wmi:
        time_now = time()
        wmi['time'] = time_now - wmi_time
        wmi['window'] = window[0]
        wmi_list.append (wmi)
        wmi_time = time_now
        if wmi['jsd'] >= best_jsd:
          best_jsd = wmi['jsd']
        if expected_bits == wmi['bits']:
          done_expecting = True
          break
    # matched --expect <bits>
    if done_expecting:
      vprint ("early termination, found expected bits:", expected_bits)
      break
    # if we had a sufficiently good match, we don't process all grids that peaks2grid generates
    if best_jsd > jsd_threshold:
      vprint ("early termination, JSD-threshold reached: %f >= %f" % (best_jsd, jsd_threshold))
      break

  done = best_jsd > jsd_window_threshold or done_expecting
  return wmi_list, done
