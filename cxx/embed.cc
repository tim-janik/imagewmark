// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

// Based on src/embed.py
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <filesystem>
#include <functional>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
#include <vips/vips8>
#include "3rdparty/CLI11/CLI11.hpp"
#include "imagewmark.hh"
#include "utils.hh"
#include "random.hh"
#include "convcode.hh"

using FloatS = std::vector<float>;
using DoubleS = std::vector<double>;
using vips::VError;
using vips::VImage;

// src/config.py
struct Config {
  static constexpr int message_size    = 128;   // number of watermark bits without error correction
  static constexpr int payload_rows    = 16;    // payload_shape[0]
  static constexpr int payload_cols    = 16;    // payload_shape[1]
  static constexpr int Lr              = 4;     // length of matrix `r`
  static constexpr int mean_win_w      = 9;     // local mean window width
  static constexpr int mean_win_h      = 9;     // local mean window height
  static constexpr int var_win_w       = 9;     // local variance window width
  static constexpr int var_win_h       = 9;     // local variance window height
  static constexpr double minimum_zoom = 1.5;   // minimum zoom, see config.py
  static constexpr double dynamic_zoom = 8.0;   // number of watermark units to fit
  Random *prng_wm_pattern = nullptr;
  Random *prng_wm_mask = nullptr;
};
static Config add_config;

CLI::App*
imagewmark_add_options (CLI::App &app, AddOptions &opt)
{
  CLI::App *add_cmd = app.add_subcommand ("add", "Embed a 128-bit watermark into an image");
  add_cmd->add_option ("input_img", opt.input_img, "Image into which the message is to be embedded")->required();
  add_cmd->add_option ("output_img", opt.output_img, "Image with embedded watermark message")->required();
  add_cmd->add_option ("message_hex", opt.message_hex, "Message bits to embed (max 128)")->required();
  add_cmd->add_option ("-s,--strength", opt.strength, "Strength for embedded watermark")->default_val (opt.strength);
  add_cmd->add_option ("-d,--dynamic-zoom", opt.dynamic_zoom, "Zoom watermark depending on image size")->default_val (opt.dynamic_zoom);
  add_cmd->add_option ("-z,--zoom", opt.zoom, "Set zoom factor for watermark")->default_val (opt.zoom);
  add_cmd->add_flag ("--trace-psnr", opt.trace_psnr, "Compute PSNR");
  add_cmd->add_flag ("--trace-quality", opt.trace_quality, "Compute quality metrics");
  add_cmd->add_flag ("--py", "Delegate to Python implementation");
  return add_cmd;
}

[[maybe_unused]] static std::string
bits_to_hex (const std::vector<bool> &bits)
{
  std::vector<uint8_t> packed_bits; // np.packbits
  packed_bits.reserve (bits.size() / 8);
  for (size_t i = 0; i < bits.size(); i += 8) {
    uint8_t byte = 0;
    for (int j = 0; j < 8 && i + j < bits.size(); j++)
      if (bits[i + j])
        byte |= 1 << (7 - j);
    packed_bits.push_back (byte);
  }
  return vec_to_hex_str (packed_bits);
}

// Return exactly n bytes (0-255) - the order matches numpy.unpackbits()
static std::vector<uint8_t>
get_bytes (Random &prng, std::size_t n)
{
  std::vector<uint8_t> out;
  out.reserve (n);
  while (out.size() < n) {
    uint64_t v = prng();
    for (int i = 0; i < 8 && out.size() < n; ++i) {
      out.push_back (static_cast<uint8_t> ((v >> (i * 8)) & 0xFF));
    }
  }
  return out;
}

// Parse string into message bits with payload_shape - src/common.py
static std::vector<bool>
parse_payload (const std::string &hex)
{
  std::vector<bool> bits;
  for (char c : hex) {
    const uint8_t nibble = std::stoi (std::string (1, c), nullptr, 16);
    bits.push_back ((nibble & 8) > 0);
    bits.push_back ((nibble & 4) > 0);
    bits.push_back ((nibble & 2) > 0);
    bits.push_back ((nibble & 1) > 0);
  }
  // Repeat bits[] to construct out[] with size message_size
  std::vector<bool> out (Config::message_size);
  for (size_t i = 0; i < out.size(); i++)
    out[i] = bits[i % bits.size()];
  return out;
}

// src/convcode.py:encode()
static std::vector<bool>
convcode_encode (const std::vector<bool> &payload)
{
  // TODO: implement convcode_encode() for vector<bool> -> vector<bool>
  FloatS floats (payload.size());
  std::copy (payload.begin(), payload.end(), floats.begin());
  std::vector<int> ints = convcode_encode (floats);
  std::vector<bool> out (ints.size()); // == payload.size() * 2
  std::copy (ints.begin(), ints.end(), out.begin());
  return out;
}

/// Random matrix `bp_r` (the "r" pattern) - size Lr × Lr
static std::pair<int, FloatS>
make_wm_pattern()
{
  const int Lr = Config::Lr;
  const size_t nbits = Lr * Lr;
  const std::size_t nbytes = (nbits + 7) / 8;
  const auto Rshake = get_bytes (*add_config.prng_wm_pattern, nbytes);
  // unpack bits (big-endian, like np.unpackbits)
  std::vector<uint8_t> Rbits;
  Rbits.reserve (nbits);
  for (uint8_t b : Rshake)
    for (int i = 7; i >= 0 && Rbits.size() < nbits; i--)
      Rbits.push_back ((b >> i) & 1);
  FloatS bp_r (nbits);
  for (size_t i = 0; i < nbits; ++i)
    // 0→+1, 1→-1     - bipolar float matrix: [[1 -1 -1 1 1 -1 1 -1]...]
    bp_r[i] = Rbits[i] * -2.0 + 1;
  return {Lr, bp_r};
}

/// Random mask `Ksmall` - size Lks × Lks
static FloatS
make_wm_mask (int Lks)
{
  const size_t nbits = Lks * Lks;
  const std::size_t nbytes = (nbits + 7) / 8;
  const auto Kshake = get_bytes (*add_config.prng_wm_mask, nbytes);
  std::vector<uint8_t> Kbits;
  Kbits.reserve (nbits);
  for (uint8_t b : Kshake)
    for (int i = 7; i >= 0 && Kbits.size() < nbits; i--)
      Kbits.push_back ((b >> i) & 1);   // np.unpackbits (Kbits, axis = 1) # Key based random matrix
  FloatS Ksmall (nbits);
  for (size_t i = 0; i < nbits; ++i)
    Ksmall[i] = Kbits[i] * -2.0 + 1;
  return Ksmall;
}

/// Box kernel with uniform weights, blurs local window for local mean calculation
static VImage
box_kernel (int width, int height)
{
  DoubleS coeffs (width * height, 1.0 / (width * height));
  return VImage::new_matrix (width, height, coeffs.data(), coeffs.size());
}

/// Local mean (box filter) - mirrors `common.local_mean`
static VImage
local_mean (const VImage &img, int win_width, int win_height)
{
  const int pad_x = win_width / 2;
  const int pad_y = win_height / 2;
  VImage padded = img.embed (pad_x, pad_y, img.width() + 2 * pad_x, img.height() + 2 * pad_y,
                             VImage::option()->set ("extend", VIPS_EXTEND_MIRROR));
  const VImage convol = padded.convf (box_kernel (win_width, win_height));
  const VImage cropped = convol.crop (pad_x, pad_y, img.width(), img.height());
  return cropped;
}

/// Local variance - mirrors `common.local_variance`
static VImage
local_variance (const VImage &img)
{
  const VImage mean1 = local_mean (img, Config::var_win_w, Config::var_win_h);
  const VImage mean2 = local_mean (img * img, Config::var_win_w, Config::var_win_h);
  return mean2 - mean1 * mean1;
}

static constexpr float MINPXV = 1e-5f; // minimum pixel variance to avoid log(0) and very small values

/// Non-linear strength function `F` (identical to `common.F`)
static VImage
compute_F (const VImage &img_variance, float strength)
{
  const VImage var_clamped = (img_variance < MINPXV).ifthenelse (MINPXV, img_variance); // enforce ≥ 1e-5
  const VImage sqrt_var = var_clamped.pow (0.5);                                        // img_std = √var
  const VImage log2_var = sqrt_var.math (VIPS_OPERATION_MATH_LOG) / std::log (2.0);     // log₂(√var)
  const VImage result = (log2_var < strength).ifthenelse (strength, log2_var);          // max(strength, log₂(√var))
  return result;
}

/// Choose an integer r such that 99.5% of the watermark pixels is in [-r:r] for areas of constant color
/// Determine the integer range r so that 99.5 % of |W·s| < r
static int
wm_range (const VImage &W, float strength)
{
  // TODO: optimize F (0, strength) == strength
  // s = compute_F( [ [ 0.0 ] ] , strength); is actually: max(log2(sqrt(1e-5)), strength)
  const float s = std::max (std::log2 (std::sqrt (MINPXV)), strength);
  // TODO: const float s = strength;
  const VImage abs_scaled = (W * s).abs();
  for (int r = 0; r < 32; r++)
    if ((abs_scaled < r).ifthenelse (1.0, 0.0).avg() > 0.995f)
      return r;
  dprintf (2, "imagewmark: error detecting watermark range\n");
  return 16;
}

/** Clip the host image to leave head-room for the watermark.
 * we need some headroom to add the watermark, so in this function we ensure that
 * ll channels of the image are in range [r, 255 - r], where r is the is the
 * pixel offset the watermark will add for areas of constant color
 */
static VImage
wm_pre_clip (const VImage &img, const VImage &W, float strength)
{
  /* - for grayscale, simple range clipping is enough
   * - for color images we watermark in the YIQ colorspace - however, since
   *   changing the Y channel in YIQ and converting back to RGB has the same
   *   effect on each of the RGB channels, we can simply use the range r for the
   *   individual color channels
   */
  const double r = wm_range (W, strength);
  const VImage clipped = (img < r).ifthenelse (r, img);
  return (clipped > 255 - r).ifthenelse (255 - r, clipped);
}

#if 0
/// Print the first N pixel values of a VImage (all bands, row-major)
[[maybe_unused]] static void
print_first_pixels (const VImage &img, int n = 16)
{
  dprintf (2, "  pixels[%d..%d] = {", 0, std::min (n, img.width()));
  int count = 0;
  for (int y = 0; y < img.height() && count < n; y++)
    for (int x = 0; x < img.width() && count < n; x++, count++) {
      std::vector<double> vals = img.getpoint (x, y);
      if (count > 0) dprintf (2, ", ");
      if (vals.size() == 1)
        dprintf (2, "(%d,%d)=[%.4f]", x, y, vals[0]);
      else
        dprintf (2, "(%d,%d)=[%.4f", x, y, vals[0]);
      for (size_t b = 1; b < vals.size(); b++)
        dprintf (2, ", %.4f", vals[b]);
      dprintf (2, "]");
    }
  dprintf (2, "}\n");
}
#endif

/// Convert from float to int; see: dither.py:round_pixels()
static VImage
round_pixels (const VImage &img)
{
  // Add 0.5 to round to nearest integer when converting to 8-bit unsigned integer
  //dprintf (2, "round_pixels: image type (before) = %s %s\n", vips_enum_nick (VIPS_TYPE_INTERPRETATION, img.interpretation()), vips_enum_nick (VIPS_TYPE_BAND_FORMAT, img.format()));
  VImage result = (img + 0.5).cast (VIPS_FORMAT_UCHAR);
  //dprintf (2, "round_pixels: image type (after)  = %s %s\n", vips_enum_nick (VIPS_TYPE_INTERPRETATION, img.interpretation()), vips_enum_nick (VIPS_TYPE_BAND_FORMAT, img.format()));
  return result;
}

// "ITU-R BT.1700 Characteristics of composite video signals for conventional analogue television systems"
// https://www.itu.int/rec/R-REC-BT.1700-0-200502-I/en
static VImage
rgb2yiq_matrix()
{
  static const double matrix[] = {
    +0.2990, +0.5870, +0.1140,   // Y row
    +0.5959, -0.2746, -0.3213,   // I row
    +0.2115, -0.5227, +0.3112,   // Q row
  };
  return VImage::new_matrix (3, 3, const_cast<double*> (matrix), 9);
}

static VImage
yiq2rgb_matrix()
{
  static const double matrix[] = {
    +1.0000, +0.9560, +0.6207,   // R row
    +1.0000, -0.2720, -0.6472,   // G row
    +1.0000, -1.1067, +1.7044,   // B row
  };
  return VImage::new_matrix (3, 3, const_cast<double*> (matrix), 9);
}

/// Embed the watermark
static VImage
add_watermark (const VImage &src, const VImage &W, double strength, const AddOptions &options)
{
  // Convert to float and apply head-room clipping
  // TODO: check element type of Mat src, do we need .cast ?
  // TODO: check, can we use single pass for cast(float) + clip ?
  VImage img = wm_pre_clip (src.cast (VIPS_FORMAT_FLOAT), W, strength);
  // Extract the Y (luminance) channel
  VImage yiq, Y;
  std::vector<VImage> ch;
  if (src.bands() == 1)
    Y = img;
  else if (src.bands() == 3) {
    yiq = img.recomb (rgb2yiq_matrix());
    ch = yiq.bandsplit();
    Y = ch[0];
  } else
    die (1, "Input image with %d channels not supported", src.bands());
  // Compute local variance
  VImage I_var = local_variance (Y);
  // Strength map I_s
  VImage I_s = compute_F (I_var, strength);
  // Add the scaled watermark
  VImage Y_wm = Y + W * I_s;
  // TODO: Check if we need to clip Y_wm back to [0,255] range, or do we always have enough headroom, or do we auto-clip later ?
  // Reconstruct image from luminance channel
  if (src.bands() == 3) {
    ch[0] = Y_wm;
    return VImage::bandjoin (ch).recomb (yiq2rgb_matrix());
  } else
    return Y_wm;
}

/// PSNR (peak-signal-to-noise ratio), see: common.py:psnr()
static double
compute_psnr (const VImage &orig, const VImage &wm)
{
  // TODO: is .cast(FLOAT) needed ?
  // Mean Squared Error: Σ |orig - wm|² / (H × W × bands)
  const double mse = (orig.cast (VIPS_FORMAT_FLOAT) - wm.cast (VIPS_FORMAT_FLOAT)).pow (2.0).avg();
  // No difference at all?
  if (mse == 0)
    return 100;
  const double max_pixel = 255.0;
  double psnr = 10.0 * std::log10 ((max_pixel * max_pixel) / mse);
  return psnr;
}

/// Save the watermarked image to disk, preserving format-specific options.
static void
save_host_image (const VImage &img, const std::string &path)
{
  // Write the result including ALL metadata
  auto save_opts = VImage::option()->set ("keep", VIPS_FOREIGN_KEEP_ALL); // drop meta-data: VIPS_FOREIGN_KEEP_NONE

  // TODO: preserve number of input image channels
  // TODO: preserve bit depth (8bpp, 16bpp) when writing

  // Check if the output is a PNG (case-insensitive)
  std::string out_lower = path;
  std::transform (out_lower.begin(), out_lower.end(), out_lower.begin(), ::tolower);
  if (out_lower.length() >= 4 && out_lower.substr (out_lower.length() - 4) == ".png") {
    // 0 = no compression (fastest, huge file)
    // 1 = minimum compression, better than OpenCV which forces Z_RLE level=0
    // 3 = fast, reasonable size
    // 6 = libvips default (slow, small size)
    // 9 = maximum, slowest
    save_opts->set ("compression", 1);
    // Allow adaptive encoding to improve compression
    save_opts->set ("filter", VIPS_FOREIGN_PNG_FILTER_ALL);
    save_opts->set ("effort", 1);
    // Interlaced saving is very slow
    save_opts->set ("interlace", 0);
    // Avoid palette dithering and quantization
    save_opts->set ("palette", 0);
  }
  img.write_to_file (path.c_str(), save_opts);
}

static VImage
load_host_image (const std::string &path)
{
  VImage host = VImage::new_from_file (path.c_str());
  if (host.has_alpha())
    // TODO: we need load -> save handling that preserves alpha channel
    host = host.extract_band (0, VImage::option()->set ("n", host.bands() - 1));
  if (host.bands() == 1) {
    // TODO: greyscale should be handled everywhere
    std::vector<VImage> rgb = { host, host, host };
    host = VImage::bandjoin (rgb);
  } else if (host.bands() > 3) {
    host = host.extract_band (0, VImage::option()->set ("n", 3));
    // TODO: this must properly handle CMYK -> RGB, we need something like VIPS_INTERPRETATION_sRGB conversion like cv2.IMREAD_COLOR
  }
  if (host.bands() != 3)
    die (1, "failed to load RGB image: %s", path.c_str());
  // TODO: normalize pixel range, so we dont deal with 0-255 for 8bit and 0-65535 for 16bit images
  if (host.format() != VIPS_FORMAT_UCHAR)
    // TODO: investigate if using FLOAT everywhere is better, esp for 16bit images
    host = host.cast (VIPS_FORMAT_UCHAR);
  return host.copy (VImage::option()->set ("interpretation", VIPS_INTERPRETATION_sRGB));
}

/// Copy flotas into a VImage with the given dimensions and band count
static VImage
image_from_floats (const FloatS &floats, int width, int height, int bands = 1)
{
  auto vimage = VImage::new_from_memory_copy ((void*) floats.data(), floats.size() * sizeof (float),
                                              width, height, bands, VIPS_FORMAT_FLOAT);
  vimage = vimage.copy (VImage::option()->set ("interpretation", bands == 1 ? VIPS_INTERPRETATION_B_W : VIPS_INTERPRETATION_sRGB));
  return vimage;
}

/// Main embedding routine (command_add() in Python)
static void
command_add (const AddOptions &opt)
{
  // Load the host image in RGB order
  VImage host = load_host_image (opt.input_img);

  // Message → payload → ECC → reshape to 16 × 16 matrix
  const std::vector<bool> payload = parse_payload (opt.message_hex.empty() ? "0" : opt.message_hex);
  // dprintf (2, "Message: %s\n", bits_to_hex (payload).c_str());
  const std::vector<bool> encoded = convcode_encode (payload);
  const int Ldim = Config::payload_rows;                 // 16
  assert (Config::payload_rows == Config::payload_cols); // need square payload

  // Generate the basic watermark unit (r-pattern)
  const auto [Lr, bp_r] = make_wm_pattern();
  const int Lwsmall = Ldim * Lr;                       // 64

  // Spread-spectrum encoding of `encoded` with `bp_r`
  FloatS wmunit (Lwsmall * Lwsmall);
  for (int j = 0; j < Ldim; j++)
     for (int i = 0; i < Ldim; i++) {
      const int lj = j * Lr, li = i * Lr;
      const float neg = encoded[j * Ldim + i] ? 1.0 : -1.0;
      for (int dy = 0; dy < Lr; dy++)
        for (int dx = 0; dx < Lr; dx++)
          wmunit[(lj + dy) * Lwsmall + li + dx] = neg * bp_r[dy * Lr + dx];
     }
  // Generate key-dependent mask `Ksmall`
  const FloatS Ksmall = make_wm_mask (Lwsmall);
  // Mask wmunit with Ksmall
  FloatS wmasked (wmunit.size());
  for (size_t i = 0; i < wmasked.size(); ++i)
    wmasked[i] = wmunit[i] * Ksmall[i]; // element-wise multiply

  // Determine zoom factor (dynamic or user-provided)
  double ZOOM = opt.zoom;       // Zoom level set by --zoom
  // Use dynamic_zoom from config (allow override with --dynamic-zoom)
  if (ZOOM <= 0) {
    const double dynamic_zoom = opt.dynamic_zoom > 0 ? opt.dynamic_zoom : Config::dynamic_zoom;
    ZOOM = std::min (host.width(), host.height()) / double (Lwsmall) / dynamic_zoom;
    ZOOM = std::max (Config::minimum_zoom, ZOOM);
  }

  // Determine watermark tiles to cover the image
  VImage W;
  {
    int hreps = host.width() / Lwsmall / ZOOM + 2;
    int vreps = host.height() / Lwsmall / ZOOM + 2;
    // Ensure watermark is centered around one unit in the middle
    if (hreps % 2 == 0)
      hreps += 1;
    if (vreps % 2 == 0)
      vreps += 1;
    // Tile the masked unit with alternating x/y-flips to cover the image
    VImage wm = image_from_floats (wmasked, Lwsmall, Lwsmall);
    VImage wm_h  = wm.fliphor ();
    VImage wm_v  = wm.flipver ();
    VImage wm_hv = wm_h.flipver ();
    // Build a 2×2 checkerboard block, replicate, then crop to exact tile count
    VImage block = wm.join (wm_h, VIPS_DIRECTION_HORIZONTAL)
                   .join (wm_v.join (wm_hv, VIPS_DIRECTION_HORIZONTAL), VIPS_DIRECTION_VERTICAL);
    VImage tiled = block.replicate ((hreps + 1) / 2, (vreps + 1) / 2)
                   .crop (0, 0, Lwsmall * hreps, Lwsmall * vreps)
                   ;
    // Resize to the host size, see: common.py:zoom_image()
    // Use vips_affine with bicubic interpolator to match OpenCV's coordinate system.
    const vips::VInterpolate interp = vips::VInterpolate::new_from_name ("bicubic");
    W = tiled.affine ({ ZOOM, 0, 0, ZOOM },
                      VImage::option()
                      ->set ("interpolate", interp)
                      ->set ("oarea", std::vector<int> {
                          0, 0,
                          int (tiled.width() * ZOOM),
                          int (tiled.height() * ZOOM) }));
    // The alternative tiled.resize() has a hardcoded centre-sampling offset that shifts peaks by ~1px.
    // W = tiled.resize (ZOOM, VImage::option()->set ("vscale", ZOOM)->set ("kernel", VIPS_KERNEL_CUBIC));

    // Crop to exactly the host dimensions (centered)
    const int dy = (W.height() - host.height() + 1) / 2;
    const int dx = (W.width() - host.width() + 1) / 2;
    if (dy || dx)
      W = W.crop (dx, dy, host.width(), host.height());
  }

  // Embed the watermark
  VImage watermarked = add_watermark (host, W, opt.strength, opt);

  // Conversion to 8-bit
  watermarked = round_pixels (watermarked);

  // Write the result
  save_host_image (watermarked, opt.output_img);

  // Optional quality reporting
  if (opt.trace_psnr || opt.trace_quality) {
    double psnr = compute_psnr (host, watermarked);
    dprintf (2, "PSNR: %f\n", psnr);
  }
}

/// Entry point - run after CLI parsing, implements `command_add`
int
imagewmark_add (const AddOptions &options)
{
  if (VIPS_INIT (argv0 ? argv0 : "imagewmark") != 0)
    die (1, "failed to initialize libvips: %s", vips_error_buffer());
  std::atexit (vips_shutdown);
  add_config.prng_wm_pattern = new Random (0, Random::Stream::wm_pattern);
  add_config.prng_wm_mask = new Random (0, Random::Stream::wm_mask);
  try {
    command_add (options);
  } catch (const VError &e) {
    std::filesystem::remove (options.output_img);
    die (1, "%s: error processing %s:\n  %s", options.output_img.c_str(), options.input_img.c_str(), string_reindent (e.what()).c_str());
  }
  return 0;
}
