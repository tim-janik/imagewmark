# Image Watermarking

The **imagewmark** program can add watermarks to image files and extract
previously embedded watermarks from modified images.
The usage is as follows:


```
@:sed:usage_imagewmark-h:@
```


# Imagewmark Architecture
<style>	body { max-width: 50em; margin: auto; }	</style>

The **imagewmark** program is used to integrate (`add` command) and extract (`get` command) watermarks (messages of up to 128 bits) into/from image files.


## Adding Watermarks

The `imagewmark add [--key…] input_img output_img message_hex` command allows adding watermarks to image files.
This command takes an image file, a 128-bit hexadecimal watermark and an optional key as input, and
it combines these into a newly generated image file. Using the same key, the watermark bits can later
be re-retrieved with the `imagewmark get` command without requiring access to the original
image input (so called blind decoding).

Using the encoding key as input, several AES based random number streams are generated to
synthesize, shuffle, mask and repeat bit patterns in the image, reflecting the watermark information.

For robust extraction and forward error correction, the watermark is encoded via convolutional codes
with puncturing, an order of `15` and a rate of `1/2` (similar to codes found in
[satellite communication](https://en.wikipedia.org/wiki/Convolutional_code#Punctured_convolutional_codes)).

The watermark bits are expanded (multiplied) with a random bit pattern, scaled up and masked with
another random bit pattern. The resulting rectangular shaped pattern is repeatedly tiled over the
source image with alternatingly flipped orientation. The actual bit values are added to the source
image, depending on the local variance of the source image. This avoids altering homogeneous source
image areas too much.
Values that exceed the original pixel range due to the addition of the bit patterns are simply
constrained to a valid pixel range via clipping.

\pagebreak

## Extracting Watermarks

The `imagewmark get <watermarked_image> [--key…]` command extracts a watermark from an image file.
This command takes an image file and an optional key as input.
With the same key used during watermark embedding, the watermark bits can be extracted from the
image file without requiring access to the original image input (so called blind decoding).

The process of extracting a watermark involves four steps:
First, the embedded watermark information is estimated via mean-subtracted contrast-normalization
of the input image.
Second, potential watermark positions are approximated by identifying peaks, symmetries and resulting
grid positions from the auto-convolution of the previous step.
Third, watermark positions and their orientation are identified based on statistical properties of
the pixel patterns used during embedding.
Finally, the cumulative signal from the detected pixel patterns and locations are decoded using
a Viterbi algorithm, yielding the originally embedded payload bits with good robustness against
geometric distortions and common image encoding artifacts.

The extracted message is then printed to the console in hexadecimal format.

Except for the encryption, Viterbi algorithm and grid detection implemented in imagewmark, the exact details of the embedding and
synchronization are provided in the paper
"Local Geometric Distortions Resilient Watermarking Scheme Based on Symmetry" by
Zehua Ma, Weiming Zhang, Han Fang, Xiaoyi Dong, Linfeng Geng, and Nenghai Yu, 2021.


The user provided 128-Bit AES key is essential to determine watermark bit patterns, the masking pattern and convolutional code bit locations.
During decoding, the same Pseudo Random Number Generator sequences are used that facilitated watermark embedding.
By using the same AES key and a cryptographically secure PRNG, the sequences are uniformly distributed and deterministically reproducible but cannot be extrapolated.
This prevents watermark extraction or modification by anyone without possession of the exact encoding key.

<!--
BUILD:
pandoc imagewmark-arch.md -o imagewmark-arch.html
pandoc imagewmark-arch.md -V papersize:a4 -V geometry:margin=2cm -o imagewmark-arch.pdf
-->
