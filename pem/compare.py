#!/usr/bin/env python3
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
"""Compare image pairs and print PEM tables or JSON."""

import argparse
import json
import os
import re
import sys
from contextlib import nullcontext, redirect_stdout
from pathlib import Path

# Ensure this directory is on sys.path so module imports work
sys.path.insert (0, str (Path (__file__).resolve().parent))


# ---------------------------------------------------------------------------
# Batch mode helpers
# ---------------------------------------------------------------------------

def _find_image_pairs (directory):
  """Pair NAME_orig or NAME_original with NAME_wm or NAME_watermarked images in a directory."""
  img_exts = (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp")
  paired = {}
  for fpath in sorted (Path (directory).iterdir()):
    m = re.fullmatch (r"(.+)_(orig|original|wm|watermarked)", fpath.stem.lower())
    if m and fpath.suffix.lower() in img_exts:
      role = "orig" if m[2].startswith ("orig") else "wm"
      paired.setdefault (m[1], {})[role] = str (fpath)

  pairs = []
  for v in paired.values():
    if "orig" in v and "wm" in v:
      pairs.append ((v["orig"], v["wm"]))
    else:
      print (f"Warning: unpaired image: {next(iter(v.values()))}", file=sys.stderr)
  return pairs


def _compute (args, orig_path, wm_path):
  """Compute the metrics of an image pair, return the result dict."""
  # Import metrics here (after arg parsing) so missing deps give clean errors
  from metrics import compute_all_metrics
  # With --json, library noise on stdout goes to stderr
  with redirect_stdout (sys.stderr) if args.as_json else nullcontext():
    return compute_all_metrics (
      orig_path, wm_path,
      tile_size=args.tile_size,
      skip_text=args.no_text,
      skip_tiling=args.no_tiling,
      skip_ssimulacra2=args.no_ssimulacra2,
      skip_butteraugli=args.no_butteraugli,
      skip_cvvdp=args.no_cvvdp,
      verbose=args.verbose,
    )


def _output (args, result):
  """Print a result dict as JSON or as a table."""
  if args.as_json:
    print (json.dumps (result, indent=2))
  else:
    from display import display_result
    display_result (result, verbose=args.verbose)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main ():
  parser = argparse.ArgumentParser (description="Perceptual Evaluation Metrics — measure how visible a watermark is, see pem/PEM.md.")
  parser.add_argument ("original_image", nargs="?", help="Path to original image")
  parser.add_argument ("watermarked_image", nargs="?", help="Path to watermarked/altered image")
  parser.add_argument ("--json", action="store_true", dest="as_json",
                       help="Output structured JSON instead of pretty table")
  parser.add_argument ("--verbose", "-v", action="store_true", help="Extra diagnostics")
  parser.add_argument ("--tile-size", type=int, default=504,
                       help="Tile size for tiling artifact analysis (default: 504)")
  parser.add_argument ("--no-text", action="store_true", help="Skip text fidelity computation")
  parser.add_argument ("--no-tiling", action="store_true", help="Skip tiling artifact computation")
  parser.add_argument ("--no-ssimulacra2", action="store_true", help="Skip SSIMULACRA2 computation")
  parser.add_argument ("--no-butteraugli", action="store_true",
                       help="Skip Butteraugli computation")
  parser.add_argument ("--no-cvvdp", action="store_true", help="Skip CVVDP computation")
  parser.add_argument ("--batch-dir", type=str, default=None,
                       help="Batch mode: compare all matching pairs in a directory")

  args = parser.parse_args()
  if args.tile_size <= 0:
    parser.error ("--tile-size must be positive")

  # ---- Batch mode ----
  if args.batch_dir:
    if not os.path.isdir (args.batch_dir):
      print (f"Error: batch directory not found: {args.batch_dir}", file=sys.stderr)
      sys.exit (1)

    pairs = _find_image_pairs (args.batch_dir)
    if not pairs:
      print ("No image pairs found in batch directory.", file=sys.stderr)
      sys.exit (1)

    from tqdm import tqdm

    failed = 0
    results = []
    for orig_p, wm_p in tqdm (pairs, desc="Comparing pairs"):
      try:
        result = _compute (args, orig_p, wm_p)
        if args.as_json:
          results.append (result)
        else:
          _output (args, result)
      except SystemExit:
        failed += 1
      except Exception as exc:
        print (f"Error comparing pair ({orig_p}, {wm_p}): {exc}", file=sys.stderr)
        failed += 1
    if args.as_json:
      print (json.dumps (results, indent=2))
    return 1 if failed else 0

  # ---- Single pair mode ----
  if not args.original_image or not args.watermarked_image:
    parser.print_help()
    sys.exit (1)

  try:
    result = _compute (args, args.original_image, args.watermarked_image)
  except Exception as exc:
    print (f"Metric computation failed: {exc}", file=sys.stderr)
    sys.exit (2)

  _output (args, result)
  return 0


if __name__ == "__main__":
  sys.exit (main())
