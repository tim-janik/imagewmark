#!/usr/bin/env python3
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

"""Black-box regression test for extraction from constant images.

Run `make -j3 tests/check-flat-images` to schedule the three cases in parallel
(also included in `make check`). Each case has its own temporary directory.
Run `python3 tests/check-flat-images.py` for all cases sequentially, or append
`FlatImageTest.test_black` (also test_gray, test_white) to select one case.
Set IMAGEWMARK to test an installed executable.

The cases are black 4x4, gray 512x512 and white 1x1. Using cornersync=auto
exercises both synchronization paths on these no-match images with only three
CLI starts. Check exit status, empty matches, finite JSON numbers and absence
of candidate grids, numerical warnings and non-finite values in verbose
diagnostics. Black input must also have no marked peaks; gray/white inputs
can produce tiny rounding residuals that the peak normalization amplifies.
Only the public CLI is invoked; no imagewmark modules or helpers are imported
or called directly. Fixtures and JSON validation use the Python standard library.
"""

import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


IMAGEWMARK = os.environ.get(
    "IMAGEWMARK", str(Path(__file__).resolve().parent.parent / "imagewmark")
)


def finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite JSON number: {value}")
    return result


def reject_constant(value):
    # json.loads accepts NaN and Infinity by default, although JSON forbids them.
    raise ValueError(f"Invalid JSON constant: {value}")


class FlatImageTest(unittest.TestCase):
    def test_black(self):
        self.check_no_match(4, 4, "black", 0)

    def test_gray(self):
        self.check_no_match(512, 512, "gray", 128)

    def test_white(self):
        self.check_no_match(1, 1, "white", 255)

    def check_no_match(self, width, height, color, value):
        with tempfile.TemporaryDirectory(prefix="imagewmark-flat-") as directory:
            filename = Path(directory) / f"{color}-{width}x{height}.pgm"
            filename.write_bytes(
                f"P5\n{width} {height}\n255\n".encode("ascii")
                + bytes([value]) * (width * height)
            )
            command = [
                IMAGEWMARK, "get", "-vv", "--test-key", "0",
                "--cornersync=auto", str(filename), "--json",
            ]
            # Bound regressions that create excessive numbers of
            # peaks or spend too long trying to synchronize them.
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=120
            )
            diagnostics = (
                f"Command: {command!r}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
            self.assertEqual(result.returncode, 0, diagnostics)
            self.assertNotRegex(
                result.stderr, r"RuntimeWarning|Traceback", diagnostics
            )
            # Invalid helper scores can be discarded before JSON
            # serialization, leaving matches=[] even on failure.
            # The public verbose CLI exposes these intermediate
            # values (e.g. cornersync: best_zoom=inf).
            self.assertNotRegex(
                result.stderr,
                r"(?i)(?<![\w./-])[+-]?(?:inf(?:inity)?|nan)(?![\w./-])",
                diagnostics,
            )
            # Black stays exactly zero through preprocessing. A variance floor
            # hides division by zero but still marks every pixel as a peak.
            # Any nonempty peak_list is therefore spurious.
            # Gray/white can have nonzero maps from floating-point roundoff.
            if value == 0:
                self.assertRegex(result.stderr, r"(?m)^peak_list: len=0$", diagnostics)
                self.assertNotRegex(
                    result.stderr, r"(?m)^peak_list: len=[1-9][0-9]*$", diagnostics
                )
            # Flat images have no synchronization signal. A broken no-match
            # exit can emit zero-size grids with finite scores that are later
            # rejected, so empty final matches alone are not sufficient.
            self.assertNotRegex(result.stderr, r"(?m)^grid_list:", diagnostics)
            try:
                report = json.loads(
                    result.stdout, parse_float=finite_float,
                    parse_constant=reject_constant,
                )
            except ValueError as error:
                self.fail(f"Invalid or non-finite JSON: {error}\n{diagnostics}")
            self.assertIsInstance(report, dict, diagnostics)
            self.assertEqual(report.get("matches"), [], diagnostics)
            self.assertEqual(report.get("width"), width, diagnostics)
            self.assertEqual(report.get("height"), height, diagnostics)
            self.assertEqual(report.get("filename"), str(filename), diagnostics)


if __name__ == "__main__":
    unittest.main()
