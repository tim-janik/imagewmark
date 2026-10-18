# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
"""Combine PEM distances and display results as tables."""

import json
import sys

from constants import (
  quality_label,
  quality_thresholds_text,
  QUALITY_COLORS,
)


def _severity_color (quality):
  return QUALITY_COLORS.get (quality, "white")


# ---------------------------------------------------------------------------
# Weights — single source of truth, change in one place
# ---------------------------------------------------------------------------

# Weights keyed by metric (heuristic tuning for watermarking benchmarking).
# Divided by sum() at module load → fractions summing to 1.0.
_WEIGHTS = {
  "mse":               0.0,  # included for reference (1-to-1 with PSNR)
  "psnr":              0.1,  # pixel reference
  "ms_ssim":           0.1,  # structural fidelity safety net
  "ssimulacra2":       0.1,  # compression-like artifact detector
  "butteraugli_l3":    0.1,  # 3-norm JND check; catches graininess / colour shifts
  "butteraugli_l2":    0.1,  # 2-norm/RMS; best CID22 correlation
  "cvvdp":             0.2,  # psychophysical JND model; primary metric of the JPEG XL paper's codec comparison
  "text_fidelity_l1":  0.2,  # text preservation
  "tiling_artifact":   0.1,  # tile-boundary consistency
}
_WEIGHTS_SUM = sum (_WEIGHTS.values())
METRIC_WEIGHTS = {k: v / _WEIGHTS_SUM for k, v in _WEIGHTS.items()}


def compute_combined (metrics: dict) -> dict:
  """Combine distances, excluding skipped metrics and retaining weights for raw=None."""
  entries = [(key, metrics[key]) for key in METRIC_WEIGHTS if metrics.get (key) is not None]
  raw_weight_sum = sum (METRIC_WEIGHTS[key] for key, _ in entries)
  if raw_weight_sum <= 0:
    return {"total_perceptual_distance": 0.0, "breakdown": {}}

  breakdown = {}
  total_weighted = 0.0

  for key, entry in entries:
    distance = entry.get ("calibrated", 0.0)
    weight = METRIC_WEIGHTS[key] / raw_weight_sum
    contribution = weight * distance

    breakdown[key] = {
      "raw": entry.get ("raw"),
      "unit": entry.get ("unit", ""),
      "direction": entry.get ("direction", -1),
      "distance": round (distance, 6),
      "weight": round (weight, 6),
      "contribution": round (contribution, 6),
    }
    total_weighted += contribution

  return {
    "total_perceptual_distance": round (total_weighted, 6),
    "breakdown": breakdown,
  }


# ---------------------------------------------------------------------------
# Pretty output (rich tables)
# ---------------------------------------------------------------------------

def display_result (result: dict, verbose: bool = False):
  """Render a single PEM result dict as a rich table."""
  try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
  except ImportError:
    print (json.dumps (result, indent=2))
    return

  console = Console()
  metrics = result.get ("metrics", {})

  combined = compute_combined (metrics)
  inp = result.get ("input", {})

  # Header
  console.print (Panel (
    f"[bold]Perceptual Evaluation Metrics[/bold]\n"
    f"Original:    {inp.get('original', 'N/A')}\n"
    f"Watermarked: {inp.get('watermarked', 'N/A')}\n"
    f"Dimensions:  {inp.get('dimensions', ['N/A'])}\n"
    f"[dim]Thresholds: {quality_thresholds_text()}[/dim]",
    title="PEM Analysis",
    border_style="blue",
  ))

  # Unified metrics + breakdown table
  table = Table (title="PEM Metrics", show_header=True)
  table.add_column ("Metric", style="bold cyan")
  table.add_column ("Value", justify="right")
  table.add_column ("Distance", justify="right")
  table.add_column ("Quality", justify="center")
  table.add_column ("Weight", justify="right")
  table.add_column ("Contribution", justify="right")

  breakdown = combined.get ("breakdown", {})

  def _add (name, brk_key):
    bd = breakdown.get (brk_key)
    raw = bd.get ("raw") if bd else None
    unit = bd.get ("unit", "") if bd else ""
    direction = bd.get ("direction", -1) if bd else -1
    arrow = {+1: "↑", -1: "↓"}.get (direction, "↓")
    distance = bd.get ("distance", 0.0) if bd else 0.0
    wt = f"{bd.get('weight', 0):.3f}" if bd else "0.000"
    contrib = f"{bd.get('contribution', 0):.6f}" if bd else "0.000000"

    display = f"{raw}{unit} {arrow}" if raw is not None else f"N/A {arrow}"
    q = quality_label (distance) if bd else "N/A"
    color = _severity_color (q)
    dist_text = f"{distance:.6f}" if bd else "skipped"
    table.add_row (name, display, dist_text, Text (q, style=color), wt, contrib)

  # Metrics in display order (keyed by breakdown key)
  _add ("MSE", "mse")
  _add ("PSNR", "psnr")
  _add ("SSIM", "ms_ssim")
  _add ("SSIMULACRA2", "ssimulacra2")
  _add ("Butteraugli L3", "butteraugli_l3")
  _add ("Butteraugli L2", "butteraugli_l2")
  _add ("CVVDP", "cvvdp")
  _add ("Text Fidelity L1", "text_fidelity_l1")
  _add ("Tiling Artifact (agg)", "tiling_artifact")

  console.print()
  console.print (table)

  # Combined score (at the end)
  total = combined.get ("total_perceptual_distance", "N/A")
  tq = quality_label (total) if isinstance (total, (int, float)) else "N/A"
  color = _severity_color (tq)
  console.print()
  console.print (Panel (
    f"[bold cyan]Total Perceptual Distance:[/bold cyan] {total}\n"
    f"[bold cyan]Quality:[/bold cyan] [{color}]{tq}[/{color}]",
    title="Combined Score",
    border_style="cyan",
  ))


# ---------------------------------------------------------------------------
# Standalone usage: python display.py [file.json ...]  or  cat json | python display.py
# ---------------------------------------------------------------------------

def _load_json_result (text):
  """Parse a result or batch array, allowing a preamble."""
  lines = text.splitlines()
  start = 0
  for i, line in enumerate (lines):
    if line.strip().startswith (('{', '[')):
      start = i
      break
  return json.loads ('\n'.join (lines[start:]))


def main ():
  """Standalone entry point: read JSON from files or stdin, display results."""
  files = sys.argv[1:] if len (sys.argv) > 1 else None
  results = []
  if files:
    for fpath in files:
      with open (fpath) as f:
        result = _load_json_result (f.read())
      results.extend (result if isinstance (result, list) else [result])
  else:
    text = sys.stdin.read()
    result = _load_json_result (text)
    results.extend (result if isinstance (result, list) else [result])

  for result in results:
    display_result (result)
    if len (results) > 1:
      print()


if __name__ == "__main__":
  main()
