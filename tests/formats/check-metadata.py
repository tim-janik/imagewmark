#!/usr/bin/env python3
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

IMAGEWMARK = os.environ.get ("IMAGEWMARK", str (Path (__file__).resolve ().parents[2] / "imagewmark"))
WATERMARK = os.environ.get ("WATERMARK", "fedcba98765432100123456789abcdef")
TAGS = (
    "Artist", "ImageDescription", "UserComment", "Copyright", "Orientation",
    "XResolution", "YResolution", "ResolutionUnit", "GPSLatitude", "GPSLatitudeRef",
    "GPSLongitude", "GPSLongitudeRef", "GPSAltitude", "Description", "Creator", "Rights",
    "CopyrightNotice", "Keywords", "CopyrightFlag", "URL",
)
BLOBS = ("ICC_Profile", "XMP", "IPTC", "ThumbnailImage")

def run (*args):
  result = subprocess.run ([str (arg) for arg in args], capture_output=True, timeout=60)
  if result.returncode:
    raise RuntimeError (f"{args!r}: {result.stderr.decode (errors='replace')}")
  return result

def metadata (path):
  values = json.loads (run ("exiftool", "-j", "-G1", "-a", "-n", * ("-" + tag for tag in TAGS), path).stdout)[0]
  values.pop ("SourceFile")
  return values

def blob (path, tag):
  return run ("exiftool", "-b", "-" + tag, path).stdout

def save_options (source, suffix):
  options = "keep=all"
  if suffix == "jpg":
    quality = 92 if source.suffix == ".jpg" else 90
    options += f",Q={quality},optimize-coding=true,interlace=true,subsample-mode=auto"
  elif suffix == "png":
    options += ",compression=1,filter=all,effort=1,interlace=false,palette=false"
  return "[" + options + "]"

class MetadataTest (unittest.TestCase):
  @classmethod
  def setUpClass (cls):
    for tool in ("vips", "exiftool"):
      if not shutil.which (tool):
        raise RuntimeError (f"check-metadata: missing dependency: {tool}")
    cls.directory = tempfile.TemporaryDirectory (prefix="imagewmark-metadata-")
    cls.addClassCleanup (cls.directory.cleanup)
    cls.path = Path (cls.directory.name)
    # Create small RGB and CMYK images, with and without alpha channels.
    pixels = bytes (value for y in range (128) for x in range (128) for value in (32 + x, 32 + y, 128))
    (cls.path / "base.ppm").write_bytes (b"P6\n128 128\n255\n" + pixels)
    run ("vips", "icc_transform", cls.path / "base.ppm", cls.path / "rgb.png", "srgb", "--input-profile", "srgb")
    run ("vips", "bandjoin_const", cls.path / "rgb.png", cls.path / "rgba.png", "153")
    run ("vips", "copy", cls.path / "rgb.png", str (cls.path / "rgb.jpg") + "[Q=92,keep=all]")
    run ("vips", "copy", cls.path / "rgb.png", cls.path / "rgb.tif")
    run ("vips", "colourspace", cls.path / "rgba.png", cls.path / "raw-cmyka.tif", "cmyk")
    run ("vips", "icc_transform", cls.path / "raw-cmyka.tif", cls.path / "cmyka.tif", "cmyk", "--input-profile", "cmyk")
    run ("vips", "copy", cls.path / "cmyka.tif", str (cls.path / "cmyk.jpg") + "[Q=92,keep=all]")
    run ("vips", "resize", cls.path / "rgb.png", cls.path / "thumbnail.jpg", "0.25")
    cls.sources = [cls.path / name for name in ("rgb.jpg", "rgb.png", "rgb.tif", "rgba.png", "cmyk.jpg", "cmyka.tif")]
    for source in cls.sources:
      tags = [
          "-EXIF:Artist=imagewmark-artist", "-EXIF:ImageDescription=imagewmark-description",
          "-EXIF:UserComment=imagewmark-comment", "-EXIF:Orientation#=6",
          "-EXIF:XResolution=300", "-EXIF:YResolution=150", "-EXIF:ResolutionUnit#=2",
          "-EXIF:GPSLatitude=48.1", "-EXIF:GPSLatitudeRef=N",
          "-EXIF:GPSLongitude=11.5", "-EXIF:GPSLongitudeRef=E", "-EXIF:GPSAltitude=456",
          "-XMP-dc:Description=imagewmark-xmp", "-XMP-dc:Creator=imagewmark-creator",
          "-XMP-dc:Rights=imagewmark-rights", "-IPTC:CopyrightNotice=imagewmark-copyright",
          "-IPTC:Keywords=imagewmark-keyword", "-Photoshop:CopyrightFlag=True",
          "-Photoshop:URL=https://example.invalid/imagewmark",
      ]
      if source.suffix in (".jpg", ".png"):
        tags.append ("-ThumbnailImage<=" + str (cls.path / "thumbnail.jpg"))
      run ("exiftool", "-overwrite_original", *tags, source)

  def round_trip (self, source, suffix):
    baseline = self.path / f"{source.name}-baseline.{suffix}"
    output = self.path / f"{source.name}-watermarked.{suffix}"
    # Use libvips as the reference. Accept its format and metadata limits.
    run ("vips", "copy", source, str (baseline) + save_options (source, suffix))
    run (IMAGEWMARK, "add", source, output, WATERMARK)
    # Compare selected fields and the full ICC profile, XMP, IPTC, and thumbnail data.
    expected = metadata (baseline)
    self.assertTrue (expected)
    self.assertEqual (metadata (output), expected)
    for tag in BLOBS:
      with self.subTest (blob=tag):
        self.assertEqual (blob (output, tag), blob (baseline, tag))
    return baseline, output

  def test_supported_metadata (self):
    for source in self.sources:
      for suffix in ("jpg", "png", "tif"):
        with self.subTest (source=source.name, output=suffix):
          baseline, output = self.round_trip (source, suffix)
          self.assertEqual (metadata (baseline)["XMP-dc:Description"], "imagewmark-xmp")
          self.assertEqual (metadata (baseline)["IFD0:Orientation"], 6)
          if source.name.startswith ("cmyk") and suffix == "png":
            self.assertEqual (blob (output, "ICC_Profile"), b"")
          else:
            self.assertEqual (blob (output, "ICC_Profile"), blob (source, "ICC_Profile"))

  # PNG must keep the complete XMP packet, including large packets.
  def test_large_xmp (self):
    source = self.path / "large-xmp.png"
    textfile = self.path / "large-xmp.txt"
    description = "imagewmark-large-xmp-" + "x" * 70000
    textfile.write_text (description)
    run ("vips", "copy", self.sources[1], source)
    run ("exiftool", "-overwrite_original", "-XMP-dc:Description<=" + str (textfile), source)
    _, output = self.round_trip (source, "png")
    self.assertEqual (metadata (output)["XMP-dc:Description"], description)
    self.assertEqual (blob (output, "XMP"), blob (source, "XMP"))

  # A save error must not change an existing output file or leave temporary files.
  def test_save_error_preserves_output (self):
    output = self.path / "output.unsupported"
    output.write_bytes (b"existing output\n")
    result = subprocess.run (
        [IMAGEWMARK, "add", str (self.sources[0]), str (output), WATERMARK], capture_output=True, timeout=60,
    )
    self.assertNotEqual (result.returncode, 0)
    self.assertIn (b"error processing", result.stderr)
    self.assertEqual (output.read_bytes (), b"existing output\n")
    self.assertFalse (list (self.path.glob (".imagewmark-*")))

if __name__ == "__main__":
  # Show the test report only if a test fails.
  stream = io.StringIO ()
  result = unittest.TextTestRunner (stream).run (unittest.defaultTestLoader.loadTestsFromTestCase (MetadataTest))
  if not result.wasSuccessful ():
    sys.exit (stream.getvalue ())
