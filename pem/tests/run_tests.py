#!/usr/bin/env python3
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
"""PEM tests: distance calibration, known anchor points, text fidelity,
identical images and the JSON output that tests/strength-report.py reads."""

import json
import os
import subprocess
import sys
import tempfile
from unittest import mock

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PEM_DIR = os.path.dirname (os.path.dirname (os.path.abspath (__file__)))
sys.path.insert (0, PEM_DIR)

from calibrate import calibrate  # noqa: E402
from constants import quality_label  # noqa: E402
from display import compute_combined  # noqa: E402
from metrics import compute_butteraugli  # noqa: E402
from metrics import _get_ocr, compute_mse_psnr, compute_ssim, compute_text_fidelity, compute_tiling_artifact_loss  # noqa: E402

METRIC_KEYS = {"mse", "psnr", "ms_ssim", "ssimulacra2", "butteraugli_l3", "butteraugli_l2",
               "cvvdp", "text_fidelity_l1", "tiling_artifact"}
failed = 0


def check (condition, msg):
  global failed
  failed += not condition
  print (f"  [{'PASS' if condition else 'FAIL'}] {msg}")


def photo (h=192, w=256):
  """Smooth colour image with values in 0..128, so small offsets never clip."""
  y, x = np.mgrid[0:h, 0:w]
  img = np.stack ([64 + 64 * np.sin (x / 17), 64 + 64 * np.cos (y / 13), (x + y) % 128], axis=2)
  return img.astype (np.uint8)


def text_image ():
  img = Image.new ("RGB", (480, 160), (128, 128, 128))
  draw = ImageDraw.Draw (img)
  draw.text ((20, 30), "Watermark test", fill=(0, 0, 0), font=ImageFont.load_default (size=40))
  draw.text ((20, 90), "Perceptual metrics", fill=(0, 0, 0), font=ImageFont.load_default (size=40))
  return np.array (img)


def compare_json (orig_path, wm_path):
  """Run compare.py --json, return (exit code, parsed JSON or None)."""
  p = subprocess.run ([sys.executable, os.path.join (PEM_DIR, "compare.py"), orig_path, wm_path, "--json"],
                      capture_output=True, text=True)
  if p.returncode:
    return p.returncode, None
  def no_constants (name):
    raise ValueError (f"invalid JSON constant {name}")
  return 0, json.loads (p.stdout, parse_constant=no_constants)


def test_calibrate ():
  print ("calibrate() and quality labels")
  desc = [(60.0, 0.0), (40.0, 0.1), (30.0, 0.2), (20.0, 0.5), (0.0, 1.0)]
  asc = [(0.0, 0.0), (2.0, 0.1), (5.0, 0.2), (10.0, 0.5), (30.0, 1.0)]
  for raw, want in [(40.0, 0.1), (30.0, 0.2), (25.0, 0.35), (70.0, 0.0), (-5.0, 1.0)]:
    check (abs (calibrate (raw, desc) - want) < 1e-9, f"descending anchors: {raw} -> {want}")
  for raw, want in [(2.0, 0.1), (5.0, 0.2), (20.0, 0.75), (-1.0, 0.0), (40.0, 1.0)]:
    check (abs (calibrate (raw, asc) - want) < 1e-9, f"ascending anchors: {raw} -> {want}")
  for distance, want in [(0.0, "excellent"), (0.1, "good"), (0.2, "acceptable"), (0.5, "poor")]:
    check (quality_label (distance) == want, f"quality_label({distance}) == {want}")


def test_anchor_points ():
  print ("Known anchor points")
  orig = photo (100, 100)
  wm = orig.copy()
  wm.reshape (-1)[:21675] += 3      # 72.25% of the values off by 3: MSE 6.5025, PSNR 40 dB
  mse, psnr = compute_mse_psnr (orig, wm)
  check (mse.raw == 6.5025 and mse.calibrated == 0.1, f"MSE 6.5025 -> distance 0.1 (got {mse})")
  check (psnr.raw == 40.0 and psnr.calibrated == 0.1, f"PSNR 40 dB -> distance 0.1 (got {psnr})")
  for offset, want in [(2, 0.1), (5, 0.2), (10, 0.5)]:
    r = compute_tiling_artifact_loss (photo(), photo() + offset, tile_size=64)
    check (r.raw == offset and r.calibrated == want, f"tiling offset {offset} -> distance {want} (got {r})")


def test_text_fidelity ():
  print ("Text fidelity")
  from paddleocr import PaddleOCR
  _get_ocr.cache_clear()
  with mock.patch ("paddleocr.PaddleOCR", wraps=PaddleOCR) as constructor:
    orig = text_image()
    r = compute_text_fidelity (orig, orig + 3)
    check (r.raw == 3.0 and r.calibrated == 0.1, f"text offset 3 -> distance 0.1 (got {r})")
    r = compute_text_fidelity (photo(), photo() + 3)
    check (r.raw is None and r.calibrated == 0.0, f"no text -> raw None, distance 0 (got {r})")
    check (constructor.call_count == 1, "OCR models loaded once for multiple pairs")


def test_small_ssim ():
  print ("SSIM on small images")
  for h, w in ((1, 1), (1, 10), (2, 2), (4, 4), (10, 10), (11, 11)):
    orig = photo (h, w)
    r = compute_ssim (orig, orig)
    check (r.raw == 1.0 and r.calibrated == 0.0, f"identical {w}x{h} image: SSIM 1")
    r = compute_ssim (orig, orig + 5)
    check (r.raw < 1.0 and r.calibrated > 0.0, f"changed {w}x{h} image: positive SSIM distance")


def test_invalid_tile_size ():
  print ("Tiling input validation")
  for size in (0, -1):
    try:
      compute_tiling_artifact_loss (photo(), photo(), tile_size=size)
    except ValueError:
      check (True, f"tile size {size} rejected")
    else:
      check (False, f"tile size {size} rejected")


def test_butteraugli ():
  print ("Butteraugli paired norms")
  from butteraugli import _load_library, compute_butteraugli_arrays_norms
  lib = _load_library()
  orig = photo()
  with mock.patch.object (lib, "butteraugli_compare_arrays_norms", wraps=lib.butteraugli_compare_arrays_norms) as compare:
    l3, l2 = compute_butteraugli (orig, orig + 3)
    check (compare.call_count == 1, "both Butteraugli norms use one native comparison")
    check (l3.raw >= l2.raw > 0.0, f"valid norms with L3 >= L2 (got {l3.raw}, {l2.raw})")
  check (compute_butteraugli_arrays_norms (orig, orig[:-1]) == (-1.0, -1.0), "Butteraugli dimension mismatch rejected")


def test_compare_json (tmpdir):
  print ("compare.py --json")
  a, b, small = (os.path.join (tmpdir, n) for n in ("a.png", "b.png", "small.png"))
  Image.fromarray (photo()).save (a)
  Image.fromarray (photo() + 2).save (b)
  Image.fromarray (photo (96, 128)).save (small)

  code, jo = compare_json (a, a)
  check (code == 0 and jo is not None, "identical images give valid JSON")
  if jo:
    m = jo["metrics"]
    check (set (m) == METRIC_KEYS, f"metric keys (got {sorted(m)})")
    check (all (v["calibrated"] == 0.0 for v in m.values()), "identical images: every distance is 0")
    check (m["psnr"]["raw"] is None and m["mse"]["raw"] == 0.0, "identical images: PSNR null, MSE 0")
    check (m["ssimulacra2"]["raw"] == 100.0 and m["cvvdp"]["raw"] == 10.0, "identical images: SSIMULACRA2 100, CVVDP 10 JOD")
    check (compute_combined (m)["total_perceptual_distance"] == 0.0, "identical images: combined distance 0")

  code, jo = compare_json (a, b)
  check (code == 0 and jo is not None, "different images give valid JSON")
  if jo:
    m = jo["metrics"]
    check (set (m) == METRIC_KEYS, "metric keys")
    check (all (set (v) == {"raw", "unit", "direction", "calibrated"} for v in m.values()),
           "every metric has raw, unit, direction, calibrated")
    check (jo["input"]["dimensions"] == [256, 192], f"input dimensions [w, h] (got {jo['input']['dimensions']})")
    combined = compute_combined (m)
    weights = {k: v["weight"] for k, v in combined["breakdown"].items()}
    check (set (weights) == METRIC_KEYS and abs (sum (weights.values()) - 1) < 1e-6, "weights cover every metric and sum to 1")
    check (0 < combined["total_perceptual_distance"] < 0.1, f"offset 2: combined distance excellent (got {combined['total_perceptual_distance']})")

  code, _ = compare_json (a, small)
  check (code == 1, "dimension mismatch exits with 1")


def main ():
  test_calibrate()
  test_anchor_points()
  test_small_ssim()
  test_invalid_tile_size()
  test_butteraugli()
  test_text_fidelity()
  with tempfile.TemporaryDirectory() as tmpdir:
    test_compare_json (tmpdir)
  print ("FAILED" if failed else "All tests passed")
  return 1 if failed else 0


if __name__ == "__main__":
  sys.exit (main())
