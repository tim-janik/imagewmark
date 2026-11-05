# PEM - Perceptual Evaluation Metrics

PEM measures how visible a watermark is. It compares the original image with its
watermarked version using several perceptual metrics, maps each metric onto one
distance scale and reports the weighted mean.

PEM is a developer and tester tool. Setup downloads Python 3.12 and about 2.3 GB of
packages (torch, PaddleOCR, ColorVideoVDP). So PEM is optional, it is not built by
default and not part of the top-level build. Python, packages, models and caches
live under `pem/`.

## Setup

Prerequisites: AMD64 Linux, `uv`, `curl` and `g++`.

```sh
make -C pem setup	# Python 3.12, packages, builds libbutteraugli.so
make -C pem check	# runs pem/tests/run_tests.py
make -C pem clean	# removes Python, caches, downloaded sources and build outputs
```

## Usage

```sh
pem/compare.sh original.png watermarked.png          # table
pem/compare.sh original.png watermarked.png --json   # JSON on stdout
pem/compare.sh --batch-dir DIR --json                # every image pair in DIR
pem/display.sh result.json                           # table from saved JSON
```

| Option | Description |
|---|------|
| `--json` | JSON output instead of a table |
| `-v, --verbose` | Per-metric progress on stderr |
| `--tile-size N` | Tile grid of the tiling artifact metric (default 504) |
| `--no-text` | Skip text fidelity |
| `--no-tiling` | Skip the tiling artifact metric |
| `--no-ssimulacra2` | Skip SSIMULACRA2 |
| `--no-butteraugli` | Skip Butteraugli |
| `--no-cvvdp` | Skip CVVDP, the slowest metric on CPU |
| `--batch-dir DIR` | Compare `NAME_orig` or `NAME_original` with `NAME_wm` or `NAME_watermarked` images in DIR |

Batch mode warns about unpaired images and exits with 1 if a pair fails.
With `--json`, it outputs one array of successful results. `display.sh` accepts
both a single result and a batch array, from files or stdin.

JSON output, one entry per metric:

```json
{
  "metrics": {
    "psnr": { "raw": 41.1712, "unit": "dB", "direction": 1, "calibrated": 0.094144 },
    ...
  },
  "input": { "original": "xs1.png", "watermarked": "xs1+wm.png", "dimensions": [400, 400] }
}
```

`raw` is the metric's own value, `direction` is 1 if higher is better and -1 if
lower is better, `calibrated` is the distance (the field keeps its old name so older
results stay readable). `raw` is null if OCR finds no text, if Butteraugli fails,
and for the infinite PSNR of identical images; the distance is 0 then.
Metrics skipped with a `--no-*` option are null, the combined distance leaves
them out.
The metric keys are `mse`, `psnr`, `ms_ssim` (SSIM, the old key is kept),
`ssimulacra2`, `butteraugli_l3`, `butteraugli_l2`, `cvvdp`, `text_fidelity_l1`
and `tiling_artifact`.

## Distance scale

The metrics use different units, and for some higher values are better. PEM maps
each raw value to a distance by piecewise-linear interpolation between anchors
(`calibrate()` in `calibrate.py`, anchors in `metrics.py`). Distance 0 means
identical images. The anchors put the limits of excellent, good and acceptable
quality at 0.1, 0.2 and 0.5, and 1.0 is poor (`constants.py`). Raw values beyond
the outer anchors clamp to 0 or 1. Excellent reaches up to 0.1, which leaves room
on the scale to tell differences below the just noticeable threshold apart.

| Metric | Better | 0 | 0.1 excellent | 0.2 good | 0.5 acceptable | 1.0 poor | Weight |
|---|---|---|---|---|---|---|---|
| PSNR [dB] | ↑ | 60 | 40 | 30 | 20 | 0 | 10% |
| MSE | ↓ | 0 | 6.5 | 65 | 650 | 65025 | 0 |
| SSIM | ↑ | 1.00 | 0.99 | 0.95 | 0.90 | 0.70 | 10% |
| SSIMULACRA2 | ↑ | 100 | 80 | 50 | 10 | -100 | 10% |
| Butteraugli 3-norm | ↓ | 0 | 1.0 | 3.0 | 6.0 | 10 | 10% |
| Butteraugli 2-norm | ↓ | 0 | 1.0 | 3.0 | 6.0 | 10 | 10% |
| CVVDP [JOD] | ↑ | 10 | 9 | 7 | 4 | 0 | 20% |
| Text fidelity L1 | ↓ | 0 | 3 | 8 | 15 | 40 | 20% |
| Tiling artifact | ↓ | 0 | 2 | 5 | 10 | 30 | 10% |

Where the anchors come from:

- PSNR: the common codec thresholds, above 40 dB excellent, 30 to 40 good, 20 to 30 acceptable.
- MSE: computed from the PSNR anchors, MSE = 255² · 10^(-PSNR/10). It has weight 0
  and is only shown for reference.
- SSIM: common thresholds, the code cites the scikit-image docs.
- SSIMULACRA2: the quality bands of the Cloudinary README, 80 very high quality,
  50 medium (MOS about 3), 10 very low (MOS about 1).
- Butteraugli: 1.0 and 3.0 from `butteraugli_main.cc`, 6 and 10 calibrated on
  example images.
- CVVDP: 9 JOD is just noticeable. 1 JOD is a 75% pairwise preference
  (CVVDP paper, arXiv:2401.11485 §3.8), so at 9 JOD 75% of observers prefer the
  original. 7 and 4 were calibrated on example images. All Kodak test image strength
  sweep scores are above 9.
- Text fidelity and tiling: custom anchors, set to penalize visible watermark
  artefacts around crisp text.

The quality label of a metric or of the combined distance is excellent below 0.1,
good below 0.2, acceptable below 0.5 and poor above.

## Combined distance

The combined distance is the weighted mean of the metric distances
(`compute_combined()` in `display.py`, weights in the table above). CVVDP and
text fidelity weigh twice as much as the other metrics, which gives the
psychophysical visibility model and text preservation more influence than the
pixel and structural metrics.

Images without text count text fidelity as distance 0 at its full weight, which
lowers their combined distance by that weight. This is on purpose. Renormalizing
the weights was tried and dropped, because it shifted the assigned weights of the
other metrics.

## Metrics

**PSNR and MSE.** Pixel differences from scikit-image, the baseline every image
codec reports.

**SSIM.** `skimage.metrics.structural_similarity`, single-scale SSIM (Wang et al.,
IEEE TIP 2004) with Gaussian weights (sigma 1.5) over the RGB channels.
Images below 11 pixels in either dimension use a smaller odd window.

**SSIMULACRA2.** The `ssimulacra2` Python package. Detects compression-like
artefacts. It reads the image files itself.

**Butteraugli.** `make setup` downloads Google's upstream Butteraugli source at a
fixed commit, checks its SHA-256 (`Makefile.mk`) and builds `libbutteraugli.so`
with `butteraugli-build/wrapper.cc`. Upstream pools the difference map with the
max; the wrapper pools it with the 3-norm, (mean(d³))^(1/3), and the 2-norm (RMS).
The 3-norm reacts more to local artefacts than the 2-norm and less to single-pixel
spikes than the max. The 2-norm correlates best with the CID22 ratings. Butteraugli
is Apache 2.0 licensed.

**CVVDP.** ColorVideoVDP (`pycvvdp`), a model of human visibility, scored in JOD
(10 = identical). PEM uses the `standard_fhd` display model, a 24" Full HD
monitor at 0.6 m, 200 cd/m², about 38 pixels per degree. The JPEG XL paper used
CVVDP as the primary metric of its codec comparison charts with `standard_4k`,
a 30" 4K monitor at 0.75 m, about 75 pixels per degree (arXiv:2506.05987 §10.2.2,
Fig. 55). PEM differs because watermarks matter more for smaller images, and
because at 75 pixels per degree the Kodak strength sweep scores cluster at 9.6
to 9.9 JOD. Means over the 18 Kodak images:

| Case | standard_4k | standard_fhd |
|---|---|---|
| JPEG q98 | 9.986 | 9.963 |
| JPEG q95 | 9.979 | 9.940 |
| JPEG q90 | 9.963 | 9.887 |
| JPEG q70 | 9.892 | 9.648 |
| JPEG q30 | 9.605 | 9.035 |
| Watermark strength 0.1 | 9.854 | 9.586 |
| Watermark strength 3.0 | 9.779 | 9.280 |

**Text fidelity L1.** PaddleOCR finds text boxes in the original image, the metric
is the mean absolute pixel difference inside these boxes.

**Tiling artifact.** Mean absolute pixel difference in 8 px wide bands along a
grid of 504 px tiles (`--tile-size`), starting at the image origin. Results are
averaged over the scales 1, 0.5 and 0.25. This is a fixed-grid heuristic.
Imagewmark centers its watermark tiles and changes their size with zoom, so
this grid does not generally follow the actual watermark tile boundaries.

## Dropped metrics

PEM started from the distortion loss of the PICO codec paper (arXiv:2605.05148),
which combines MSE, LPIPS, MS-SSIM, a tiling artifact loss and a text fidelity
loss. The paper publishes no weights, the PEM weights are its own.

LPIPS was tested and dropped. On watermark artefacts it disagreed with CVVDP and
SSIMULACRA2, for example LPIPS rated an image excellent where SSIMULACRA2 gave
-3.3 and the artefacts were visible. It also needs a 528 MB VGG16 model and takes
about 8 s per image pair.

VIF (Sheikh and Bovik, 2006) was tested and dropped. It is slow and its wavelet
model correlates poorly with what people see in watermark and compression
artefacts. CVVDP and Butteraugli model human vision better.
