% IMAGEWMARK(1)	imagewmark-0 | Imagewmark Manual Pages

# NAME
imagewmark - An image program for watermark message bit embedding and extraction


# SYNOPSIS

**imagewmark** {`add`,`get`,`gen-key`} [*OPTIONS*] <*INPUTIMAGE*> [*OUTPUTIMAGE*] [*WATERMARK*]


# DESCRIPTION

**Imagewmark** is a Free Software utility to add an encrypted invisible digital watermark to an image.
Using the same encryption key, the watermark can be reconstructed from cropped, scaled, or compressed
variants of the watermarked image, without knowledge of the original source (blind decoding).
It also includes a command to generate a 128-bit watermarking key that can be used with the `--key` option.

# OPTIONS

Imagewmark supports short and long options which start with two dashes (`--`).

## Global Options

`-h`, `--help`
  : Show a help message about command line usage.

`-v`, `--version`
: Print information about the program version.

# COMMANDS

## Add Watermark
**add** [**OPTIONS**] *INPUT_IMG* *OUTPUT_IMG* *MESSAGE_HEX*

Embed the watermark *MESSAGE_HEX* (up to 128 message bits)
in *INPUT_IMG* and write the result into *OUTPUT_IMG*.

**Command Options:**

`-h`, `--help`
: Show this help message and exit.

`-d`, `--dynamic-zoom` *DYNAMIC_ZOOM*
: Zoom watermark depending on image size (default: -1).

`-z`, `--zoom` *ZOOM*
: Set zoom factor for watermark (default: -1).

`--trace-psnr`
: Compute PSNR (default: False).

`--trace-quality`
: Compute quality metrics (default: False).

`-v`, `--verbose`
: Increase output messages or debugging info for multiple `-vv` (default: 0).

`-q`, `--quiet`
: Reduce output verbosity (default: None).

`-s`, `--strength` *STRENGTH*
: Strength for embedded watermark (default: 2).

`-P` *PLOTS*
: Configure plots with colon separated keywords, 'most' or 'all' (default: None).

`--key` *KEY*
: Load watermarking key from file (default: None).

`--test-key` *TEST_KEY*
: Watermarking key (default: None).

## Get Watermark
**get** [**OPTIONS**] *INPUT_IMG*

Extract a watermark message from the image given as *INPUT_IMG*.

**Command Options:**

`-h`, `--help`
: Show this help message and exit.

`--expect` *EXPECT*
: Expected bit pattern for early exit (default: None).

`--json` [*JSONFILE*]
: Write JSON results into file (default: None).

`--dump` *DUMP*
: Debug flags to dump intermediate stages (default: ).

`--norm-peak-count` *NORM_PEAK_COUNT*
: Number of normalized peaks to use for grid (default: 250).

`--raw-peak-count` *RAW_PEAK_COUNT*
: Number of raw peaks to use for grid (default: 250).

`--jsd-threshold` *JSD_THRESHOLD*
: Jensen-Shannon divergence threshold that is sufficient to stop searching for more watermarks (default: 55%).

`--cornersync` {`on`,`off`,`auto`}
: Set cornersync aided detection mode: 'on' forces it, 'off' disables it, 'auto' is the default.

`--perspective`
: Search for optimal perspective grids (default: False).

`--original` *ORIGINAL*
: Use original image for detection (default: ).

`-v`, `--verbose`
: Increase output messages or debugging info for multiple `-vv` (default: 0).

`-q`, `--quiet`
: Reduce output verbosity (default: None).

`--strength` *STRENGTH*
: Strength for embedded watermark (default: 2).

`-P` *PLOTS*
: Configure plots with colon separated keywords, 'most' or 'all' (default: None).

`--key` *KEY*
: Load watermarking key from file (default: None).

`--test-key` *TEST_KEY*
: Watermarking key (default: None).

## Generate Key Files
**gen-key** [`-h`] [`-v`] [`-q`] *OUTPUT_KEY_FILE*

Generate a 128-bit watermarking key and write the result in hexadecimals into *OUTPUT_KEY_FILE*.

**Command Options:**

`-h`, `--help`
: Show this help message and exit.

`-v`, `--verbose`
: Increase output messages or debugging info for multiple `-vv` (default: 0).

`-q`, `--quiet`
: Reduce output verbosity (default: None).


# EXAMPLES

1. **Generate a 128-bit watermarking key:** \
   Create a private key to encrypt and decrypt the payload.
   ```sh
   imagewmark gen-key mysecret.key
   ```

2. **Embed a watermark message in an image:** \
   Note that watermarks shorter than 128 bits are repeated to fill up to 128 bits:
   ```sh
   imagewmark add [--key mysecret.key] input.png output.png babe
   ```

3. **Extract a watermark message from an image:** \
   Note that the output may contain more than one watermark.

   ```sh
   imagewmark get [--key mysecret.key] output.png
   babebabebabebabebabebabebabebabe JSD=99.94%
   ```


# AUTHORS
This manual page and Imagewmark are written by Tim Janik and Stefan Westerfeld.


# COPYRIGHT
Copyright © 2023-Present The Imagewmark Development Team.
License GPL-3.0+: GNU GPL version 3 or later <https://gnu.org/licenses/gpl.html>.
This is free software: you are free to change and redistribute it.
There is NO WARRANTY; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.


# SEE ALSO

[**Imagewmark Website**](https://github.com/tim-janik/imagewmark) \
[**"Local Geometric Distortions Resilient Watermarking Scheme Based on Symmetry"**](https://arxiv.org/abs/2007.10240)
by Zehua Ma, Weiming Zhang, Han Fang, Xiaoyi Dong, Linfeng Geng, Nenghai Yu.
