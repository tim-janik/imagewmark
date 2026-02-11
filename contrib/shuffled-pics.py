#!/usr/bin/env python3
# This Source Code Form is licensed MPL-2.0: http://mozilla.org/MPL/2.0
"""
Script: shuffled-pics.py

Usage: ./shuffled-pics.py [options] <image-directory>...

Filters images based on dimensions:
- Shuffle input images
- Ignore images with max dimension >= MAX_DIM (default: 4000)
- Pick no more than MAX_3K images with max dimension >= 3000 (default: 10)
- Pick no more than MAX_2K images with max dimension >= 2000 (default: 20)
- Ignore images with min dimension < MIN_DIM (default: 512)
- Total selected images <= LIMIT (default 100)
- Optionally, create relative symlinks in output directory

Prints selected image paths to stdout, logs info to stderr.
"""

import sys, os
import subprocess
import random
import argparse
from pathlib import Path

parser = argparse.ArgumentParser (description="Select images based on dimensions.")
parser.add_argument ("input_dirs", nargs='+', type=Path, help="Input image directories")
parser.add_argument ("--output", "-o", type=Path, help="Output directory for symlinks")
parser.add_argument ("--limit", type=int, default=100, help="Total limit of selected images")
parser.add_argument ("--max-3k", type=int, default=10, help="Max number of images to select with max dimension >= 3000")
parser.add_argument ("--max-2k", type=int, default=20, help="Max number of images to select with max dimension >= 2000")
parser.add_argument ("--min-dim", type=int, default=512, help="Ignore images with a minimum dimension smaller than this value")
parser.add_argument ("--max-dim", type=int, default=4000, help="Ignore images with a maximum dimension greater than or equal to this value")

args = parser.parse_args ()

input_dirs = args.input_dirs
OUT_DIR = args.output
TOTAL_LIMIT = args.limit

for img_dir in input_dirs:
  if not img_dir.is_dir ():
    print (f"Error: {img_dir} is not a directory", file=sys.stderr)
    sys.exit (1)

if OUT_DIR:
  OUT_DIR.mkdir (parents=True, exist_ok=True)

# --- Configurable limits ---
MAX_3K = args.max_3k
MAX_2K = args.max_2k
MIN_DIM = args.min_dim
MAX_DIM = args.max_dim

# --- Gather all image files ---
exts = (".jpg", ".jpeg", ".png", ".tif", ".tiff")
all_images = []
for img_dir in input_dirs:
  all_images.extend ([p for p in img_dir.iterdir () if p.suffix.lower () in exts])

if not all_images:
  print ("No images found.", file=sys.stderr)
  sys.exit (0)

# --- Shuffle the images ---
random.shuffle (all_images)

selected = []
count_3k = 0
count_2k = 0

for img in all_images:
  if len (selected) >= TOTAL_LIMIT:
    print (f"Reached total limit of {TOTAL_LIMIT} images", file=sys.stderr)
    break

  try:
    # Use exiftool to get width and height
    out = subprocess.check_output (
        ["exiftool", "-s", "-s", "-s", "-ImageWidth", "-ImageHeight", str (img)],
        text=True
    )
    parts = out.strip ().split ()
    if len (parts) != 2:
      print (f"Warning: Could not parse dimensions for {img}", file=sys.stderr)
      continue
    w, h = map (int, parts)
  except Exception as e:
    print (f"Warning: exiftool failed for {img}: {e}", file=sys.stderr)
    continue

  min_dim = min (w, h)
  max_dim_img = max (w, h)

  # Apply filters
  if max_dim_img >= MAX_DIM:
    continue
  if min_dim < MIN_DIM:
    continue
  if max_dim_img >= 3000 and count_3k >= MAX_3K:
    continue
  if 2000 <= max_dim_img < 3000 and count_2k >= MAX_2K:
    continue

  # Keep the image
  selected.append (img)

  # Update counters
  if max_dim_img >= 3000:
    count_3k += 1
  elif 2000 <= max_dim_img < 3000:
    count_2k += 1

# --- Create symlinks in output directory ---
if OUT_DIR:
  for img in selected:
    link_path = OUT_DIR / img.name
    try:
      # Remove existing link if present
      if link_path.exists ():
        link_path.unlink ()
      # Create relative symlink
      rel_target = Path (os.path.relpath (img, OUT_DIR))
      link_path.symlink_to (rel_target)
    except Exception as e:
      print (f"Warning: could not link {img} -> {link_path}: {e}", file=sys.stderr)

# --- Output selected images ---
for img in selected:
  print (img)

# --- Summary ---
print (f"\nTotal selected: {len (selected)}", file=sys.stderr)
print (f"3K+ images: {count_3k}, 2K+ images: {count_2k}", file=sys.stderr)
