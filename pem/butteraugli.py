# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
"""Butteraugli 3-norm and 2-norm for uint8 RGB arrays. See PEM.md."""

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
  _lib.butteraugli_compare_arrays_norms.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int,  # data1, h1, w1
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int,  # data2, h2, w2
    ctypes.POINTER (ctypes.c_double), ctypes.POINTER (ctypes.c_double),
  ]
  _lib.butteraugli_compare_arrays_norms.restype = ctypes.c_int
  return _lib


def compute_butteraugli_arrays_norms (orig: np.ndarray, wm: np.ndarray) -> tuple[float, float]:
  """Return both norms of (H, W, 3) uint8 sRGB arrays, or (-1, -1) on error."""
  lib = _load_library()

  o = np.ascontiguousarray (orig, dtype=np.uint8)
  w = np.ascontiguousarray (wm, dtype=np.uint8)

  h, wd = o.shape[:2]
  if o.shape != w.shape:
    return -1.0, -1.0

  l3, l2 = ctypes.c_double(), ctypes.c_double()
  if not lib.butteraugli_compare_arrays_norms (o.ctypes.data, h, wd, w.ctypes.data, h, wd,
                                              ctypes.byref (l3), ctypes.byref (l2)):
    return -1.0, -1.0
  return l3.value, l2.value


def compute_butteraugli_arrays (orig: np.ndarray, wm: np.ndarray) -> float:
  """Return the 3-norm, or -1 on error."""
  return compute_butteraugli_arrays_norms (orig, wm)[0]


def compute_butteraugli_arrays_l2 (orig: np.ndarray, wm: np.ndarray) -> float:
  """Return the 2-norm, or -1 on error."""
  return compute_butteraugli_arrays_norms (orig, wm)[1]
