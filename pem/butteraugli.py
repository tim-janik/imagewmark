# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
"""Butteraugli — psychovisual image similarity metric (Google).

Wraps a bundled shared library (libbutteraugli.so) built from Google's
reference C++ implementation.  The library handles gamma correction,
opsin mixing, XYB color space, HF/LF masking, and diffmap scoring.

Two norms are available:
  - 3-norm (default): (mean(diff³))^(1/3) — preferred for watermarking
  - 2-norm (RMS):     sqrt(mean(diff²)) — best overall CID22 correlation

Two APIs are provided:
  - compute_butteraugli_arrays(orig_arr, wm_arr) — pre-loaded arrays (3-norm)
  - compute_butteraugli_arrays_l2(orig_arr, wm_arr) — pre-loaded arrays (2-norm)

Score interpretation: see the anchors in metrics.compute_butteraugli().

Note: 3-norm is preferred for watermarking because it is more sensitive
to localized compression-like artifacts than 2-norm while being less
prone to single-pixel outlier spikes than L∞.  2-norm has slightly better
overall correlation with human judgments (CID22 MCOS: KRCC -0.6575 vs -0.6547).

Returns -1.0 on error (dimension mismatch, etc.).
"""

import ctypes
from pathlib import Path
from typing import Optional

import numpy as np

# ---------------------------------------------------------------------------
# Locate the bundled shared library
# ---------------------------------------------------------------------------

_BUNDLE_DIR = Path (__file__).resolve().parent
_LIB_PATH = _BUNDLE_DIR / "libbutteraugli.so"

_lib: Optional[ctypes.CDLL] = None


def _load_library () -> ctypes.CDLL:
  """Load libbutteraugli.so once (singleton)."""
  global _lib
  if _lib is not None:
    return _lib

  if not _LIB_PATH.is_file():
    raise RuntimeError (f"Butteraugli shared library not found at {_LIB_PATH}. "
                        f"Build it with: make -C {_BUNDLE_DIR} -f Makefile.mk libbutteraugli.so")

  _lib = ctypes.CDLL (str (_LIB_PATH))
  # Array-based API (3-norm)
  _lib.butteraugli_compare_arrays.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int,  # data1, h1, w1
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int,  # data2, h2, w2
  ]
  _lib.butteraugli_compare_arrays.restype = ctypes.c_double
  # Array-based API (2-norm)
  _lib.butteraugli_compare_arrays_l2.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int,  # data1, h1, w1
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int,  # data2, h2, w2
  ]
  _lib.butteraugli_compare_arrays_l2.restype = ctypes.c_double
  return _lib


def compute_butteraugli_arrays (orig: np.ndarray, wm: np.ndarray) -> float:
  """Butteraugli 3-norm of two (H, W, 3) uint8 sRGB arrays, as loaded by
  PIL.Image.convert('RGB'). Score >= 0, lower is better, -1.0 on error."""
  lib = _load_library()

  # Ensure contiguous uint8 arrays
  o = np.ascontiguousarray (orig, dtype=np.uint8)
  w = np.ascontiguousarray (wm, dtype=np.uint8)

  h, wd = o.shape[:2]
  if o.shape != w.shape:
    return -1.0

  return lib.butteraugli_compare_arrays (o.ctypes.data, h, wd, w.ctypes.data, h, wd)


def compute_butteraugli_arrays_l2 (orig: np.ndarray, wm: np.ndarray) -> float:
  """Like compute_butteraugli_arrays(), with the 2-norm (RMS)."""
  lib = _load_library()

  o = np.ascontiguousarray (orig, dtype=np.uint8)
  w = np.ascontiguousarray (wm, dtype=np.uint8)

  h, wd = o.shape[:2]
  if o.shape != w.shape:
    return -1.0

  return lib.butteraugli_compare_arrays_l2 (o.ctypes.data, h, wd, w.ctypes.data, h, wd)
