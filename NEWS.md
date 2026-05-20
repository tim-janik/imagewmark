## Imagewmark NEXT:

### Added:
* Added `results.txt` generation to test suite, listing best JSD scores per extraction

### Changed:
* Replaced OpenCV with libvips for the C++ watermark embedding pipeline
* Moved to affine transform with bicubic interpolation for image resizing
* Optimized PNG compression options when saving embedded images
* Updated build dependencies to require libvips-dev instead of libopencv-dev

### Removed:
* Removed `--flat` option and flat report generation from test suite, use `results.txt`
* Removed `flat.txt` and `fails.txt` report generation from test Makefile


## Imagewmark 0.6.0:

### Added:
* Documentation and example updates
* Added `imagewmark.py add --py` option to force embedding via Python code
* Reimplemented watermark embedding in C++
* C++ based watermark embedding is significantly faster and uses less memory
* Extended test suite results to include an averaged failure-rate
* Added gamma and brightness-contrast to the default attacks
* Implemented range-scaleto and aspect-crop attacks
* Added support to customize attacks for test suite runs
* Added cornersync / ACNF distinction to test suite results
* Extended test suite construction to shuffle, filter and select image sets
* Added support for --cornersync={on,off,auto} to reduce test cases
* Added CLI11.hpp version 2.6.2 to 3rdparty sources
* Added --without-original flag to test runner
* Added peak normalization

### Changed:
* Made C++ based watermark embedding the default
* Split imagewmark into a C++ based executable and a Python program
* Made C++ based imagewmark the default executable to reduce startup time
* Improved performance by moving more operations to OpenCV
* Made all test suite decisions depend on a single seed
* Strip metadata from converted images so test results are reproducible
* Updated dependencies

### Fixed:
* Fixed issues where `.ppm` and `.tif` images were not recognized
* Fixed sign preservation in the auto-convolution calculation
* Fixed potential build issues from stale files
* Fixed Make --test-key option work with integers again
	https://github.com/tim-janik/imagewmark/issues/11
* Fixed wmtool.py: Add "aspect‑resize:WxH" attack to improve j90randomsizej80
	https://github.com/tim-janik/imagewmark/issues/10
* Fixed tests/Makefile: properly use cornersync mode from Makefile variable
	https://github.com/tim-janik/imagewmark/issues/9
* Fixed tests/gen-tests-mk: fix random size aspect ratio generation
	https://github.com/tim-janik/imagewmark/issues/8
* Fixed Enforce random aspect ratio in test suite
	https://github.com/tim-janik/imagewmark/issues/6
* Fixed gen-tests-mk: Makefile triggers /bin/bash: Argument list too long
	https://github.com/tim-janik/imagewmark/issues/4
* Fixed gen-tests-mk: support only running some attacks
	https://github.com/tim-janik/imagewmark/issues/2

### Removed:
* Removed image comment watermarking (test) code
* Removed outdated (debugging) comments

### Contributors
Thanks to everyone who gave feedback and to the
contributors who made this release happen!

* Tim Janik (@tim-janik)
* Stefan Westerfeld (@swesterfeld)

For full details, see the commit history:
	https://github.com/tim-janik/imagewmark/compare/v0.5.0...v0.6.0


## Imagewmark 0.5.0:

### Added:
* Added the --cornersync=<on|off|auto> option to control the corner sync algorithm during extraction
* Added developer documentation, including a description of the architecture
* Added a manual page to the documentation (`imagewmark.1`)
* Added a new tests/README.md to provide an overview and usage instructions for test runs
* Added information about test image datasets to the test documentation
* Added an Alpine CI workflow for automated builds and checks using GitHub Actions
* Added an IRC bot for CI build status notifications
* Added unit tests to verify basic functionality before/after installation
* Added new script (gen-tests-mk) that creates out-of-tree test suites of custom sizes
* Added support to utilize all CPU cores when running test batteries
* Added specific tests for high-resolution images and downscaling attacks

### Breaking:
* We now read all images with OpenCV instead of PIL, this potentially changes the set of supported images
* We assume OpenImageIO/imageio.h and gcrypt.h header files are present
* Dependencies: libgcrypt20-dev libopenimageio-dev libopencv-dev
* Watermark encoding has changed in the 0.5.0 version due to PRNG enum modifications
* We now build PDF versions of the docs only if pdflatex is installed

### Changed:
* Improved test realism by randomizing attack resolutions and shuffled input image selection
* Enhanced test reproducibility with improved and deterministic seeding mechanisms
* Moved all C++ source code into a dedicated cxx/ directory
* Better error handling in build scripts, with improved logging for debugging
* Major overhaul of the build system with unified Makefiles and improved dependency handling
* Fixed various bugs in the build system and C++ code
* Introduced installation check and uninstallation rules (make install, installcheck, uninstall, distcheck)
* Migrated version handling to a shell script with git integration
* Fixed image reading to properly handle subimages and miplevels
* Added check that secret key files are only readable by the user
* We support parallel installations of different major.minor versions

### Removed:
* Removed unused OpenCV configure script
* Removed auto config, compile sources in subdir

### Contributors

Thanks to everyone who made this release happen!

* Tim Janik (@tim-janik)
* Stefan Westerfeld (@swesterfeld)

For full details, see the [commit history](https://github.com/tim-janik/imagewmark/commits/v0.5.0)


## Imagewmark 0.4.0:

* Improved documentation in various places.
* Enhanced test reporting with additional columns, titles, and sorting.
* Extended and separated attack vector generations in the test suite.
* Extended visualizations when following along the detection algorithms.
* Extended performance monitoring by adding CPU time and wall clock measurements to various phases.
* Extended JSON support for reporting detected watermarks.
* Introduced --trace-quality option, to provide scores during embedding.
* Improved test reports, added list generation for failing test cases.
* Fixed test suite crashes, improved test rules and optimized parallel processing.
* Fixed various image processing bugs, removed PIL dependency in favor of CV2 for image IO.
* Use float-to-int rounding conversion for watermark embedder.
* Improve reliability for areas which contain a constant color for some colors.
  - Clip each channel to leave some headroom before embedding the watermark.
* Introduced the imagewmark --ssim option to compute SSIM for images after embedding.
* Improved non-blind decoding via feature based image alignment.
* Improved non-blind decoding via ECC based sub-pixel alignment.
* Improved image extraction performance by relying on corner sync for non-blind decoding.
* Added support for auto-converting CMYK and RGBA images.
* Added support for improved detection via use of the original image (non-blind).
* Add "cornersync" algorithm, to make watermark detection more robust for some attacks:
  - Works if original/wm corners are identical (i.e. jpg, scale, jpg+scale,...).
* Improved peaks2grid for better handling of images with extreme aspect ratios.


## Imagewmark 0.3.0:

* Change strength computation for less visible (less robust) watermarks.
* Improved handling of greyscale images and images in CMYK (tiff format).
* Added experimental perspective virtual grid search using --perspective.
* Improve speed and reduce memory consumption for watermark detection.
  - Pre-scale high resolution images before detection
  - Use 32-bit floats instead of 64-bit complex values for symmetry matrix
  - Compute auto convolution using real FFT
* Robustness improvements:
  - Dynamically adjust zoom for high resolution images
  - Use forward error correction with convolutional codes
  - Try different window sizes for local mean / local variance
* Support fractional zoom for the watermark.
* Improved grid search performance.
* Researched, documented and adjusted statistical threshold for watermark detection.
* Properly documented peaks2grid interface.
* Added JSON output, which provides extracted watermark bits and statistical measures.
* Reworked and added new graphical plot generations, plots can be selected via labels.
* Added a new test suite with maximized parallelism and lots of new attack tests.
* Added new test reports with timing statistics, error percentages, HTML and PDF generation.
* Improved search performance without reducing robustness using JSD match threshold.
* Improved corner case handling and stability.
* Added watermark pattern encryption and decryption via AES key.
* Improved memory usage by releasing auxiliary structures earlier.
* Properly documented new dependencies and improved Python version compatibility.
* Adjusted the Dockerfile to enable fully self contained builds and test runs.


## Imagewmark 0.2.0:

* Significantly improved robustness and detection speed.
* Reduced memory consumptions for extraction by an order of magnitude.
* Added Dockerfile for reproducible builds and runs.
* Reduce size of the randomized pixel pattern for more watermarks in small images.
* Use smooth upsampling for embedding to reduce artifacts.
* Improve reliability for areas of white or black pixels
  - Clip luminance to leave some headroom before embedding the watermark
* Fixed cropping of images with odd numbered dimensions.
* Improve automated testing.
* Use peak angles and regularities to detect a grid of embedded watermarks.
* Allow dumping of intermediate 'peaks' stage.


## Imagewmark 0.1.0:

* Milestone 1 reached.
* Proof of concept embedding and extraction works, based on:
  Local Geometric Distortions Resilient Watermarking Scheme Based on Symmetry
  Zehua Ma, Weiming Zhang, Han Fang, Xiaoyi Dong, Linfeng Geng, and Nenghai Yu
  https://arxiv.org/abs/2007.10240
