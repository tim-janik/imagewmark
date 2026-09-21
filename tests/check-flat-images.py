#!/usr/bin/env python3
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

"""Black-box regression test for extraction from constant images.

Run `make -j3 tests/check-flat-images` to schedule the three cases in parallel
(also included in `make check`). Each case has its own temporary directory.
Run `python3 tests/check-flat-images.py` for all cases sequentially, or append
`FlatImageTest.test_black` (also test_gray, test_white) to select one case.
Set IMAGEWMARK to test an installed executable.
Successful runs are silent; Make prints the OK line. Failures print diagnostics.

The cases are black 4x4, gray 512x512 and white 1x1. Using cornersync=auto
exercises both synchronization paths on these no-match images with only three
CLI starts. All cases check exit status, empty matches, finite JSON numbers
and absence of numerical warnings and non-finite values in verbose diagnostics.
Only black input must also have no peaks or candidate grids: it stays exactly
zero through preprocessing. Gray/white inputs can produce rounding residuals
that normalization amplifies, depending on numerical library versions and
platform, without changing the correct final no-match result.
Only the public CLI is invoked; no imagewmark modules or helpers are imported
or called directly. Fixtures and JSON validation use the Python standard library.
"""

import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
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
            self.assertEqual(
                result.returncode, 0, f"Extraction must exit successfully.\n{diagnostics}"
            )
            self.assertNotRegex(
                result.stderr, r"RuntimeWarning|Traceback",
                f"Extraction must not emit numerical warnings or tracebacks.\n{diagnostics}",
            )
            # Invalid helper scores can be discarded before JSON output,
            # leaving matches=[] even with cornersync: best_zoom=inf.
            self.assertNotRegex(
                result.stderr,
                r"(?i)(?<![\w./-])[+-]?(?:inf(?:inity)?|nan)(?![\w./-])",
                f"Extraction must not produce non-finite diagnostic values.\n{diagnostics}",
            )
            # Black stays exactly zero through preprocessing. A variance floor
            # hides division by zero but still marks every pixel as a peak.
            # Any nonempty peak_list is therefore spurious.
            # Gray/white can have nonzero maps from floating-point roundoff.
            if value == 0:
                self.assertRegex(
                    result.stderr, r"(?m)^peak_list: len=0$",
                    f"Black input must report an empty peak list.\n{diagnostics}",
                )
                self.assertNotRegex(
                    result.stderr, r"(?m)^peak_list: len=[1-9][0-9]*$",
                    f"Black input must not produce spurious peaks.\n{diagnostics}",
                )
                # A broken no-match exit can emit zero-size grids with finite
                # scores that are later rejected. Empty matches do not catch it.
                self.assertNotRegex(
                    result.stderr, r"(?m)^grid_list:",
                    f"Black input must not produce candidate grids.\n{diagnostics}",
                )
            try:
                report = json.loads(
                    result.stdout, parse_float=finite_float,
                    parse_constant=reject_constant,
                )
            except ValueError as error:
                self.fail(f"Invalid or non-finite JSON: {error}\n{diagnostics}")
            self.assertIsInstance(report, dict, f"Expected a JSON object.\n{diagnostics}")
            self.assertEqual(
                report.get("matches"), [],
                f"Flat input must produce an empty match list.\n{diagnostics}",
            )
            self.assertEqual(report.get("width"), width, f"Incorrect image width.\n{diagnostics}")
            self.assertEqual(report.get("height"), height, f"Incorrect image height.\n{diagnostics}")
            self.assertEqual(
                report.get("filename"), str(filename), f"Incorrect input filename.\n{diagnostics}"
            )


if __name__ == "__main__":
    output = io.StringIO()
    runner = unittest.TextTestRunner(stream=output)
    program = unittest.main(testRunner=runner, exit=False)
    if not program.result.wasSuccessful():
        sys.stderr.write(output.getvalue())
        sys.exit(1)
