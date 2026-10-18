# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
"""Generic piecewise-linear calibration.

Provides a single interpolation function.  All metric-specific anchor
definitions live in their respective compute_*() functions in metrics.py."""

import math
from dataclasses import dataclass


@dataclass (frozen=True)
class MetricResult:
  """Structured result from a single metric computation."""
  raw: float
  unit: str
  direction: int  # +1 (higher=better) or -1 (lower=better)
  calibrated: float  # distance [0..1], 0 = identical (JSON field name kept)


def calibrate (raw: float, anchors: list[tuple[float, float]]) -> float:
  """Piecewise-linear interpolation between anchor points.

  Anchors are (raw_value, distance) pairs, in any order, so tables for
  lower=better and higher=better metrics both work.

  Values outside the anchor range clamp to the nearest endpoint's
  distance."""
  if math.isnan (raw):
    return anchors[-1][1]  # the poor anchor
  (x0, y0), *rest = sorted (anchors)
  if raw <= x0:
    return y0
  for x1, y1 in rest:
    if raw <= x1:
      return y0 + (raw - x0) / (x1 - x0) * (y1 - y0)
    x0, y0 = x1, y1
  return y0
