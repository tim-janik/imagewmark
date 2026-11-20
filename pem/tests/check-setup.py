#!/usr/bin/env python3
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

MAKEFILE = Path (__file__).resolve().parents[1] / "Makefile.mk"


class SetupTest (unittest.TestCase):
  def setUp (self):
    self.tmp = tempfile.TemporaryDirectory()
    self.addCleanup (self.tmp.cleanup)
    self.root = Path (self.tmp.name)
    self.archive = self.root / "python.tar.gz"
    with tarfile.open (self.archive, "w:gz") as archive:
      python = b"#!/bin/sh\nexit 0\n"
      entry = tarfile.TarInfo ("python/bin/python3")
      entry.mode = 0o755
      entry.size = len (python)
      archive.addfile (entry, io.BytesIO (python))
    self.digest = hashlib.sha256 (self.archive.read_bytes()).hexdigest()
    self.bin_dir = self.root / "bin"
    self.bin_dir.mkdir()
    uv = self.bin_dir / "uv"
    uv.write_text ("#!/bin/sh\ntouch uv-ran\n")
    uv.chmod (0o755)

  def setup (self, digest):
    return subprocess.run (["make", "-f", str (MAKEFILE), "-o", "libbutteraugli.so", "setup",
                            f"PEM_STANDALONE_URL={self.archive.as_uri()}", f"PEM_STANDALONE_SHA256={digest}"],
                           cwd=self.root, env={**os.environ, "PATH": f"{self.bin_dir}:{os.environ['PATH']}"},
                           capture_output=True, text=True)

  def test_verified_archive_and_empty_ocr_cache (self):
    result = self.setup (self.digest)
    self.assertEqual (result.returncode, 0, result.stdout + result.stderr)
    self.assertTrue ((self.root / ".venv/bin/python3").is_file())
    self.assertTrue ((self.root / ".venv/bin/python").is_symlink())
    self.assertTrue ((self.root / ".cache/paddleocr/.downloaded").is_file())
    self.assertFalse ((self.root / ".venv.tar.gz.tmp").exists())
    self.archive.unlink()
    result = self.setup (self.digest)
    self.assertEqual (result.returncode, 0, result.stdout + result.stderr)

  def test_bad_checksum_stops_before_install (self):
    result = self.setup ("0" * 64)
    self.assertNotEqual (result.returncode, 0)
    self.assertIn ("checksum", result.stderr)
    self.assertFalse ((self.root / ".venv/bin/python3").exists())
    self.assertFalse ((self.root / "uv-ran").exists())

  def test_clean_removes_downloads (self):
    for name in ("butteraugli-build/butteraugli/butteraugli.cc", ".venv.tar.gz.tmp"):
      path = self.root / name
      path.parent.mkdir (parents=True, exist_ok=True)
      path.touch()
    result = subprocess.run (["make", "-f", str (MAKEFILE), "clean"], cwd=self.root, capture_output=True, text=True)
    self.assertEqual (result.returncode, 0, result.stdout + result.stderr)
    self.assertFalse ((self.root / "butteraugli-build/butteraugli").exists())
    self.assertFalse ((self.root / ".venv.tar.gz.tmp").exists())


if __name__ == "__main__":
  unittest.main()
