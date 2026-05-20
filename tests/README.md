# IMAGEWMARK - TESTS

The scripts in the tests/ subdirectory allow to run Imagewmark on a collection
of images with a variety of attacks and generate a report (`report.pdf`) and
a plain-text results file (`results.txt`) at the end.

Introduction to the scripts and commands:
- ber-test.sh: Developer tool for error rate testing
- example01.svg: Simple test image for `make check`
- gen-tests-mk: Script to generate test directory Makefile,
  populate input images and configure attacks.
- Makefile: Template for gen-tests-mk.
- policy.xml: Config file for ImageMagick to allow large images.
- report.py: Script for test statistics and report generation.
- wmtool.py: Script implementing various image modification attacks.

Simple usage example:

```sh
# Create a clean test directory `/tmp/iwmtest/` and populate it with a collection
# of test input images. See also `gen-tests-mk --help` for more options.
tests/gen-tests-mk -c -O /tmp/iwmtest/ ~/Downloads/test-images/

# Run watermarking and attacks in the test directory
time nice make -C /tmp/iwmtest/ -j`nproc`

# Inspect the resulting report
xdg-open /tmp/iwmtest/report.pdf
```

## Inspecting results.txt

The `results.txt` file lists every extraction result with the filename, highest
JSD score, and matched bits. Lines with a numeric JSD value indicate a (possibly
weak) watermark detection, verify the `bits` member for correctness.
Lines without a numeric JSD indicate synchronization failures.

Filter or count successes and failures:
```sh
grep -cP 'jsd=\d' results.txt		# successful
grep -cP -v 'jsd=\d' results.txt	# failed
```
