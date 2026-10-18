# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
"""Perceptual Evaluation Metrics — core computation functions.

Each metric function returns a structured result:
  - MetricResult(raw, unit, direction, calibrated) for single-value metrics
  - a (mse, psnr) and a (3-norm, 2-norm) tuple of MetricResult for MSE/PSNR and Butteraugli
  - raw=None with distance 0.0 if the metric has no valid output (no text, Butteraugli error)

Anchor points are defined inline per-metric.  The generic calibrate() function
(calibrate.py) does piecewise-linear interpolation.  Quality thresholds come
from constants.py — anchors map to:
  QUALITY_EXCELLENT=excellent, QUALITY_GOOD=good,
  QUALITY_ACCEPTABLE=acceptable, QUALITY_POOR=poor."""

import logging
import os
import sys
from dataclasses import asdict
from functools import cache
from pathlib import Path
import numpy as np
from PIL import Image

# Keep all caches local to pem/ — nothing in ~/
_PEM_ROOT = Path (__file__).resolve().parent
_CACHE_DIR = _PEM_ROOT / ".cache"
_CACHE_DIR.mkdir (exist_ok=True)

devnull = open (os.devnull, "w")

os.environ["TORCH_HOME"] = str (_CACHE_DIR / "torch")
os.environ["HF_HOME"] = str (_CACHE_DIR / "huggingface")
os.environ["HUGGINGFACE_HUB_CACHE"] = str (_CACHE_DIR / "huggingface")
os.environ["PADDLE_OCR_BASE_DIR"] = str (_CACHE_DIR / "paddleocr")
os.environ["IMAGEIO_USERDIR"] = str (_CACHE_DIR)  # imageio, used by pycvvdp

# Suppress PaddleOCR library noise (DEBUG/WARNING on every call)
logging.getLogger ("ppocr").setLevel (logging.ERROR)

import torch  # noqa: E402
torch.hub.set_dir (str (_CACHE_DIR / "torch" / "hub"))

from calibrate import MetricResult, calibrate
from constants import (
  QUALITY_EXCELLENT,
  QUALITY_GOOD,
  QUALITY_ACCEPTABLE,
  QUALITY_POOR,
)


def load_images (original_path: str, watermarked_path: str) -> tuple[np.ndarray, np.ndarray]:
  """Load two images as uint8 RGB arrays (H, W, 3). Always 3-channel.

  Single source of truth for image IO — metric functions must NOT do their own loading.
  Grayscale → RGB triplet (R=G=B). RGBA → RGB (alpha stripped).
  Exits on error."""
  for p in (original_path, watermarked_path):
    if not Path (p).is_file():
      print (f"Error: file not found: {p}", file=sys.stderr)
      sys.exit (1)
  orig_pil = Image.open (original_path).convert ("RGB")
  wm_pil = Image.open (watermarked_path).convert ("RGB")
  if orig_pil.size != wm_pil.size:
    print (
      f"Error: dimension mismatch — "
      f"{original_path} is {orig_pil.size}, "
      f"{watermarked_path} is {wm_pil.size}.",
      file=sys.stderr,
    )
    sys.exit (1)
  return np.array (orig_pil, dtype=np.uint8), np.array (wm_pil, dtype=np.uint8)


# ---------------------------------------------------------------------------
# MSE / PSNR (paired — computed together for efficiency)
# ---------------------------------------------------------------------------

def compute_mse_psnr (orig: np.ndarray, wm: np.ndarray) -> tuple[MetricResult, MetricResult]:
  """Mean Squared Error and Peak Signal-to-Noise Ratio on pixel values in [0, 255].

  MSE included for reference but weighted 0.0 (1-to-1 related to PSNR).
  Both calibrated independently via own anchor tables.

  Distance anchors: excellent >40 dB, good >30 dB, acceptable >20 dB, poor <20 dB
  """
  from skimage.metrics import mean_squared_error as _sk_mse
  from skimage.metrics import peak_signal_noise_ratio as _sk_psnr

  # Ascending (lower=better) — MSE anchors derived from PSNR via exact formula:
  #   MSE = MAX² · 10^(-PSNR/10)
  # Anchors match PSNR quality thresholds exactly.
  _mse_anchors = [
    (0.0, 0.00),
    (255**2 * 10**(-40/10), QUALITY_EXCELLENT),   # PSNR=40 → MSE=6.5025
    (255**2 * 10**(-30/10), QUALITY_GOOD),   # PSNR=30 → MSE=65.025
    (255**2 * 10**(-20/10), QUALITY_ACCEPTABLE),  # PSNR=20 → MSE=650.25
    (255**2 * 10**(0/10), QUALITY_POOR),   # PSNR=0 → MSE=65025
  ]

  # Descending (higher=better → distance decreases with raw)
  # POI source: codec literature & ITU-T P.910:
  #   karam-nus.github.io/metrics, scienceinsights.org, metricgate.com
  #   >40 dB excellent, 30-40 good, 20-30 acceptable, <20 poor
  _psnr_anchors = [
    (60.0, 0.00),   # ceiling → 0 distance
    (40.0, QUALITY_EXCELLENT),   # excellent: differences nearly imperceptible
    (30.0, QUALITY_GOOD),   # good: minor artifacts, usually tolerable
    (20.0, QUALITY_ACCEPTABLE),  # acceptable: noticeable distortion, visible artifacts
    (0.0, QUALITY_POOR),   # poor: <20 dB per codec literature; 0 = natural floor
  ]

  mse_raw = round (float (_sk_mse (orig, wm)), 6)  # already in [0..255] pixel space
  psnr_raw = round (float (_sk_psnr (orig, wm, data_range=255)), 4)
  return (
    MetricResult (raw=mse_raw, unit="", direction=-1, calibrated=round (calibrate (mse_raw, _mse_anchors), 6)),
    # identical images have infinite PSNR, JSON has no Infinity: write null
    MetricResult (raw=psnr_raw if np.isfinite (psnr_raw) else None, unit="dB", direction=+1,
                  calibrated=round (calibrate (psnr_raw, _psnr_anchors), 6)),
  )


# ---------------------------------------------------------------------------
# SSIM
# ---------------------------------------------------------------------------

def compute_ssim (orig: np.ndarray, wm: np.ndarray) -> MetricResult:
  """Structural Similarity Index (single scale, Wang et al. 2004).

  Distance anchors: excellent >0.99, good >0.95, acceptable >0.90, poor >0.70
  """
  from skimage.metrics import structural_similarity as _sk_ssim

  # Descending (higher=better)
  # POI source: Wang et al. 2004 "Image Quality Assessment: From Error Visibility to Structural Similarity";
  # scikit-image docs (>0.99 excellent, >0.95 good, >0.90 acceptable)
  _anchors = [
    (1.00, 0.00),   # perfect → 0 distance
    (0.99, QUALITY_EXCELLENT),   # excellent: near-perfect structural fidelity
    (0.95, QUALITY_GOOD),   # good: scikit-image threshold
    (0.90, QUALITY_ACCEPTABLE),   # acceptable: structurally similar
    (0.70, QUALITY_POOR),   # poor: significant degradation
  ]

  win_size = min (11, min (orig.shape[:2]))
  if win_size % 2 == 0:
    win_size -= 1
  raw = round (float (_sk_ssim (
    orig, wm, data_range=255, channel_axis=2,
    gaussian_weights=True, sigma=1.5, use_sample_covariance=False, win_size=win_size,
  )), 6)

  return MetricResult (raw=raw, unit="", direction=+1, calibrated=round (calibrate (raw, _anchors), 6))


# ---------------------------------------------------------------------------
# Text Fidelity Loss (L1 on text regions)
# ---------------------------------------------------------------------------

@cache
def _get_ocr ():
  from paddleocr import PaddleOCR
  return PaddleOCR (use_angle_cls=False, lang="en", show_log=False)


def compute_text_fidelity (orig: np.ndarray, wm: np.ndarray) -> MetricResult:
  """Text-region L1 error using PaddleOCR. Returns distance 0.0 if no text.

  Distance anchors: excellent <3, good <8, acceptable <15, poor <40
  """
  _na = MetricResult (raw=None, unit="", direction=-1, calibrated=0.0)
  import cv2

  # Ascending (lower=better)
  # POI source: custom metric — heuristic on [0,255] pixel L1 difference in text regions
  _anchors = [
    (0.0, 0.00),
    (3.0, QUALITY_EXCELLENT),   # excellent: imperceptible on text
    (8.0, QUALITY_GOOD),   # good: subtle anti-aliasing shift
    (15.0, QUALITY_ACCEPTABLE),  # acceptable: text still legible
    (40.0, QUALITY_POOR),  # poor: text clearly degraded
  ]

  # Suppress PaddleOCR C-level output (not caught by Python redirect_stdout)
  sys.stdout.flush()
  sys.stderr.flush()
  old_stdout = os.dup (1)
  old_stderr = os.dup (2)
  os.dup2 (devnull.fileno(), 1)
  os.dup2 (devnull.fileno(), 2)
  try:
    results = _get_ocr().ocr (orig[..., ::-1], cls=False)  # PaddleOCR models expect BGR
  finally:
    os.dup2 (old_stdout, 1)
    os.dup2 (old_stderr, 2)
    os.close (old_stdout)
    os.close (old_stderr)
  h, w = orig.shape[:2]
  mask = np.zeros ((h, w), dtype=np.uint8)
  if not results or not results[0]:
    return _na
  for line in results[0]:
    bbox = np.array (line[0], dtype=np.int32)
    cv2.fillPoly (mask, [bbox], 255)
  text_pixels = mask > 0
  if not np.any (text_pixels):
    return _na
  raw = round (float (np.mean (np.abs (
    orig[text_pixels].astype (np.float64) - wm[text_pixels].astype (np.float64)
  ))), 6)
  return MetricResult (raw=raw, unit="", direction=-1, calibrated=round (calibrate (raw, _anchors), 6))


# ---------------------------------------------------------------------------
# Tiling Artifact Loss (multi-resolution L1 on tile boundaries)
# ---------------------------------------------------------------------------

def compute_tiling_artifact_loss (orig: np.ndarray, wm: np.ndarray, tile_size: int = 504) -> MetricResult:
  """Multi-resolution L1 loss on tile boundary regions. Returns aggregate as MetricResult.

  Distance anchors: excellent <2, good <5, acceptable <10, poor <30
  """
  if tile_size <= 0:
    raise ValueError ("tile_size must be positive")
  import cv2

  # Ascending (lower=better)
  # POI source: custom metric — heuristic on [0,255] pixel L1 difference at tile boundaries
  _anchors = [
    (0.0, 0.00),
    (2.0, QUALITY_EXCELLENT),   # excellent: imperceptible boundaries
    (5.0, QUALITY_GOOD),   # good: subtle boundary shift
    (10.0, QUALITY_ACCEPTABLE),  # acceptable: not objectionable
    (30.0, QUALITY_POOR),  # poor: obvious tiling artifacts
  ]

  scales = [1.0, 0.5, 0.25]
  band_width = 8
  scale_results = {}

  for scale in scales:
    new_h = max (int (orig.shape[0] * scale), 1)
    new_w = max (int (orig.shape[1] * scale), 1)
    o_s = cv2.resize (orig, (new_w, new_h), interpolation=cv2.INTER_LINEAR).astype (np.float64)
    w_s = cv2.resize (wm, (new_w, new_h), interpolation=cv2.INTER_LINEAR).astype (np.float64)
    ts = max (int (tile_size * scale), 1)
    diff = np.abs (o_s - w_s)
    boundary_errors = []

    x = ts
    while x < new_w:
      lo = max (0, x - band_width // 2)
      hi = min (new_w, x + (band_width + 1) // 2)
      boundary_errors.append (diff[:, lo:hi].mean())
      x += ts

    y = ts
    while y < new_h:
      lo = max (0, y - band_width // 2)
      hi = min (new_h, y + (band_width + 1) // 2)
      boundary_errors.append (diff[lo:hi, :].mean())
      y += ts

    scale_results[f"scale_{scale}"] = round (
      float (np.mean (boundary_errors)) if boundary_errors else float (diff.mean()), 6
    )

  raw = round (float (np.mean ([scale_results[f"scale_{s}"] for s in scales])), 6)
  return MetricResult (raw=raw, unit="", direction=-1, calibrated=round (calibrate (raw, _anchors), 6))


# ---------------------------------------------------------------------------
# SSIMULACRA2
# ---------------------------------------------------------------------------

def compute_ssimulacra2 (original_path: str, watermarked_path: str) -> MetricResult:
  """SSIMULACRA2 perceptual quality metric.

  POI source: cloudinary/ssimulacra2 README (Jon Sneyers 2022):
  https://github.com/cloudinary/ssimulacra2
    80 = very high (side-by-side 1:1), 50 = medium/MOS~3 'fair',
    10 = very low/MOS~1 'bad'
  """
  import ssimulacra2 as _ss

  # Descending (higher=better)
  # Range is -inf..100; use -100 as floor (scores below 10 are already MOS~1 'bad')
  _anchors = [
    (100.0, 0.00),   # perfect → 0 distance
    (80.0, QUALITY_EXCELLENT),   # excellent: side-by-side 1:1 (per README)
    (50.0, QUALITY_GOOD),   # good: medium/MOS~3 'fair' (per README)
    (10.0, QUALITY_ACCEPTABLE),  # acceptable: very low/MOS~1 'bad' (per README)
    (-100.0, QUALITY_POOR),   # poor: extremely low/negative (per README)
  ]

  raw = round (float (_ss.compute_ssimulacra2 (original_path, watermarked_path)), 4)
  return MetricResult (raw=raw, unit="", direction=+1, calibrated=round (calibrate (raw, _anchors), 6))


# ---------------------------------------------------------------------------
# Butteraugli (3-norm + 2-norm)
# ---------------------------------------------------------------------------

def compute_butteraugli (orig: np.ndarray, wm: np.ndarray) -> tuple[MetricResult, MetricResult]:
  """Butteraugli psychovisual similarity metric (3-norm and 2-norm).

  Distance anchors (both norms): excellent <1.0 (JND), good <3.0,
  acceptable <6.0, poor <10.0
  """
  from butteraugli import compute_butteraugli_arrays_norms

  # Ascending (lower=better, distance metric)
  # POI source: google/butteraugli README + butteraugli_main.cc:430-431:
  # https://github.com/google/butteraugli/blob/master/butteraugli/butteraugli_main.cc
  #   ButteraugliFuzzyInverse(1.5) ≈ 1.0 → "great" (JND)
  #   ButteraugliFuzzyInverse(0.5) ≈ 3.0 → "acceptable" boundary
  _anchors = [
    (0.0, 0.00),   # perfect match → 0 distance
    (1.0, QUALITY_EXCELLENT),   # excellent: JND threshold (ButteraugliFuzzyInverse(1.5))
    (3.0, QUALITY_GOOD),   # good: acceptable boundary (ButteraugliFuzzyInverse(0.5))
    (6.0, QUALITY_ACCEPTABLE),   # acceptable: clearly visible
    (10.0, QUALITY_POOR),  # poor: very bad (~JPEG q=10)
  ]

  score_l3, score_l2 = compute_butteraugli_arrays_norms (orig, wm)
  if score_l3 < 0:
    _na = MetricResult (raw=None, unit="", direction=-1, calibrated=0.0)
    return _na, _na
  return (
    MetricResult (
      raw=round (float (score_l3), 4), unit="", direction=-1,
      calibrated=round (calibrate (round (float (score_l3), 4), _anchors), 6),
    ),
    MetricResult (
      raw=round (float (score_l2), 4), unit="", direction=-1,
      calibrated=round (calibrate (round (float (score_l2), 4), _anchors), 6),
    ),
  )


# ---------------------------------------------------------------------------
# CVVDP
# ---------------------------------------------------------------------------

def compute_cvvdp (orig: np.ndarray, wm: np.ndarray) -> MetricResult:
  """ColorVideoVDP perceptual quality metric.

  Distance anchors: excellent >9.0 (lossless), good >7.0,
  acceptable >4.0, poor >0.0
  Receives pre-loaded uint8 RGB arrays from load_images() — never does own IO."""
  import pycvvdp

  # Descending (higher=better)
  # POI source: CVVDP paper arXiv:2401.11485 §3.8 (SIGGRAPH 2024):
  # https://arxiv.org/html/2401.11485
  #   Q_JOD = 10 - α·D^β; 10 JOD = perfect; 1 JOD drop = 75% of observers notice
  _anchors = [
    (10.0, 0.00),   # ceiling → 0 distance (identical images)
    (9.0, QUALITY_EXCELLENT),   # excellent: lossless threshold (1 JOD = 75% detect)
    (7.0, QUALITY_GOOD),   # good: good quality band
    (4.0, QUALITY_ACCEPTABLE),   # acceptable: poor quality band
    (0.0, QUALITY_POOR),   # poor: catastrophic
  ]

  # 24" Full HD at 0.6 m (38 ppd), separates watermark strengths better than standard_4k (75 ppd)
  cvvdp_instance = pycvvdp.cvvdp (display_name="standard_fhd", quiet=True)
  t_orig = torch.from_numpy (orig.astype (np.float32) / 255.0).permute (2, 0, 1).unsqueeze (0).unsqueeze (2)
  t_wm = torch.from_numpy (wm.astype (np.float32) / 255.0).permute (2, 0, 1).unsqueeze (0).unsqueeze (2)
  result = cvvdp_instance.predict (t_wm, t_orig, dim_order="BCFHW", frames_per_second=30)
  raw = round (float (result[0]), 4)
  return MetricResult (raw=raw, unit="JOD", direction=+1, calibrated=round (calibrate (raw, _anchors), 6))


# ---------------------------------------------------------------------------
# Convenience: compute all metrics at once
# ---------------------------------------------------------------------------

def compute_all_metrics (original_path: str, watermarked_path: str, tile_size: int = 504, skip_text: bool = False, skip_tiling: bool = False,
                         skip_ssimulacra2: bool = False, skip_butteraugli: bool = False, skip_cvvdp: bool = False, verbose: bool = False) -> dict:
  """Load images and compute every metric.

  Returns the JSON result {"metrics": {key: MetricResult as dict}, "input": {...}},
  skipped metrics are None."""
  orig, wm = load_images (original_path, watermarked_path)

  def run (name, func, *args):
    if verbose:
      print (f"Computing {name}...", file=sys.stderr)
    return func (*args)

  metrics = {}
  metrics["mse"], metrics["psnr"] = run ("MSE/PSNR", compute_mse_psnr, orig, wm)
  metrics["ms_ssim"] = run ("SSIM", compute_ssim, orig, wm)  # key kept for existing results
  metrics["ssimulacra2"] = None if skip_ssimulacra2 else run ("SSIMULACRA2", compute_ssimulacra2, original_path, watermarked_path)
  metrics["butteraugli_l3"], metrics["butteraugli_l2"] = (None, None) if skip_butteraugli else run ("Butteraugli", compute_butteraugli, orig, wm)
  metrics["text_fidelity_l1"] = None if skip_text else run ("text fidelity", compute_text_fidelity, orig, wm)
  metrics["tiling_artifact"] = None if skip_tiling else run ("tiling artifact", compute_tiling_artifact_loss, orig, wm, tile_size)
  metrics["cvvdp"] = None if skip_cvvdp else run ("CVVDP", compute_cvvdp, orig, wm)
  return {
    "metrics": {k: asdict (v) if v else None for k, v in metrics.items()},
    "input": {
      "original": original_path,
      "watermarked": watermarked_path,
      "dimensions": list (orig.shape[:2][::-1]),
    },
  }
