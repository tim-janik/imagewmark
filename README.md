# IMAGEWMARK

Invisible watermarking for digital images.


## SYNOPSIS

`imagewmark {add|get} [OPTIONS] <input.image> [output.image] [watermark]`


## DESCRIPTION

Imagewmark is a Free Software program to add an encrypted invisible digital watermark to an
image. Using the same encryption key, the watermark can be reconstructed from cropped, scaled
or compressed variants of the watermarked image, without knowledge of the original source
(blind decoding).

The methods used for watermark embedding and extraction are based on:

*"Local Geometric Distortions Resilient Watermarking Scheme Based on Symmetry"* by
Zehua Ma, Weiming Zhang, Han Fang, Xiaoyi Dong, Linfeng Geng, Nenghai Yu.
https://arxiv.org/abs/2007.10240


## INSTALLATION

To build and run imagewmark, the following package dependencies need to be provided:

	# Packages needed for the C++ helpers and Python routines
	apt install build-essential libgcrypt20-dev libopenimageio-dev \
	  python3-numpy python3-scipy python3-matplotlib python3-imageio \
	  python3-opencv python3-skimage
	# Build C++ helpers
	make
	# Test invocation
	src/imagewmark --help

### DOCKER

A dockerized runtime can be created and used as described below.
To pass image files in and out of the eocker environment, a `/data` volume needs
to be provided for `docker run`.

	# Create docker image from source repositors
	docker build -f Dockerfile -t imagewmark-0 .
	# Run the dockerized executable, using the current dir for image io
	docker run -ti --rm -v $PWD:/data imagewmark-0 add in.png out.png 1234
	docker run -ti --rm -v $PWD:/data imagewmark-0 get out.png


## EXAMPLES

Add a watermark to an existing image, note that watermarks shorter than 128 bits
are repeated to fill up to 128 bits:

	src/imagewmark add input.png output.png babe

Extract a previously embedded watermark:

	src/imagewmark get output.png
	babebabebabebabebabebabebabebabe JSD=99.94%

Using an encryption key to conceal the watermark payload:

	# Create a private key to encrypt and decrypt the payload
	src/imagewmark gen-key mysecret.key
	# Utilize the key during embedding and extraction
	src/imagewmark add --key mysecret.key in.png out.png 12341234123412341234123412341234
	src/imagewmark get --key mysecret.key out.png
	12341234123412341234123412341234 JSD=99.96% pixels_mscn= -6.9952832164817345 … 6.9973355487490725

For automation, the watermark extraction supports result generation in JSON format:

	# Write watermark detection results into watermarks.json
	src/imagewmark get --key mysecret.key --json watermarks.json out.png
	cat watermarks.json      # shortened output
	{
	  "width": 1024, "height": 1024,
	  "filename": "out.png",
	  "matches": [ {
	      "bits": "12341234123412341234123412341234",
	      "jsd": 0.9996185779935369,
	      "error": 0.114406
          } ]
	}


## LICENSE

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
