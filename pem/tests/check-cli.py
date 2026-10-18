#!/usr/bin/env python3
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

PEM_DIR = Path (__file__).resolve().parents[1]
SKIP_MODELS = ["--no-text", "--no-cvvdp", "--no-ssimulacra2", "--no-butteraugli"]


class CliTest (unittest.TestCase):
  def setUp (self):
    self.tmp = tempfile.TemporaryDirectory()
    self.addCleanup (self.tmp.cleanup)
    self.root = Path (self.tmp.name)
    for name in ("one", "two"):
      Image.fromarray (np.full ((32, 32, 3), 100, dtype=np.uint8)).save (self.root / f"{name}_orig.png")
      Image.fromarray (np.full ((32, 32, 3), 102, dtype=np.uint8)).save (self.root / f"{name}_wm.png")

  def run_cli (self, script, args, text=None):
    return subprocess.run ([sys.executable, str (PEM_DIR / script), *map (str, args)], input=text,
                           capture_output=True, text=True, env={**os.environ, "COLUMNS": "180", "NO_COLOR": "1"})

  def batch (self):
    return self.run_cli ("compare.py", ["--batch-dir", self.root, "--json", *SKIP_MODELS])

  def test_batch_json_and_display (self):
    result = self.batch()
    self.assertEqual (result.returncode, 0, result.stderr)
    results = json.loads (result.stdout)
    self.assertEqual (len (results), 2)
    for entry in results:
      self.assertIsNone (entry["metrics"]["ssimulacra2"])
    for use_file in (False, True):
      with self.subTest (use_file=use_file):
        path = self.root / "results.json"
        path.write_text (result.stdout)
        displayed = self.run_cli ("display.py", [path] if use_file else [], None if use_file else result.stdout)
        self.assertEqual (displayed.returncode, 0, displayed.stderr)
        self.assertEqual (displayed.stdout.count ("Original:"), 2)
        rows = [line for line in displayed.stdout.splitlines() if "SSIMULACRA2" in line]
        self.assertEqual (len (rows), 2)
        self.assertTrue (all ("skipped" in line and "N/A" in line and "excellent" not in line for line in rows))

  def test_partial_and_total_batch_failure (self):
    for name, expected in (("one", 1), ("two", 0)):
      Image.new ("RGB", (16, 16)).save (self.root / f"{name}_wm.png")
      result = self.batch()
      self.assertEqual (result.returncode, 1, result.stderr)
      self.assertEqual (len (json.loads (result.stdout)), expected)

  def test_single_json_and_mixed_display_files (self):
    result = self.run_cli ("compare.py", [self.root / "one_orig.png", self.root / "one_wm.png", "--json", *SKIP_MODELS])
    self.assertEqual (result.returncode, 0, result.stderr)
    self.assertIsInstance (json.loads (result.stdout), dict)
    path = self.root / "single.json"
    path.write_text ("Saved result\n" + result.stdout)
    batch_path = self.root / "batch.json"
    batch_path.write_text ("[" + result.stdout + "]")
    displayed = self.run_cli ("display.py", [path, batch_path])
    self.assertEqual (displayed.returncode, 0, displayed.stderr)
    self.assertEqual (displayed.stdout.count ("Original:"), 2)

  def test_invalid_tile_sizes (self):
    for size in ("0", "-1"):
      with self.subTest (size=size):
        result = self.run_cli ("compare.py", ["--tile-size", size])
        self.assertEqual (result.returncode, 2)
        self.assertIn ("--tile-size must be positive", result.stderr)


if __name__ == "__main__":
  unittest.main()
