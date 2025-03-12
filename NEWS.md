## Imagewmark 0.4.0:

* Improved documentation in various places.
* Enhanced test reporting with additional columns, titles, and sorting.
* Extended and separated attack vector generations in the test suite.
* Extended visualizations when following along the detection algorithms.
* Extended performance monitoring by adding CPU time and wall clock measurements to various phases.
* Extended JSON support for reporting detected watermarks.
* Introduced --trace-quality option, to provides scoresduring embedding.
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
  - clip luminance to leave some headroom before embedding the watermark
* Fixed cropping of images with odd numbered dimensions.
* Improve automated testing.
* Use peak angles and regularities to detect a grid of embedded watermarks.
* Allow dumping of intermediate 'peaks' stage.


## Imagewmark 0.1.0:

* Milestone 1 reached.
* Proof of concept embedding and extration works, based on:
  Local Geometric Distortions Resilient Watermarking Scheme Based on Symmetry
  Zehua Ma, Weiming Zhang, Han Fang, Xiaoyi Dong, Linfeng Geng, and Nenghai Yu
  https://arxiv.org/abs/2007.10240
