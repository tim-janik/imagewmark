// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

// Based on src/embed.py
#include <array>
#include <cstddef>
#include <cmath>
#include <cstring>
#include <exception>
#include <filesystem>
#include <functional>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#include <opencv2/opencv.hpp>

#include "CLI/CLI.hpp"

#include "imagewmark.hh"
#include "utils.hh"
#include "random.hh"
#include "convcode.hh"

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
  std::vector<float> floats (payload.size());
  std::copy (payload.begin(), payload.end(), floats.begin());
  std::vector<int> ints = convcode_encode (floats);
  std::vector<bool> out (ints.size()); // == payload.size() * 2
  std::copy (ints.begin(), ints.end(), out.begin());
  return out;
}

/// Random matrix `bp_r` (the "r" pattern) - size Lr × Lr
static std::pair<int, cv::Mat>
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
  cv::Mat bp_r (Lr, Lr, CV_32F);
  int idx = 0;
  for (int y = 0; y < Lr; y++)
    for (int x = 0; x < Lr; x++)
      // 0→+1, 1→-1     - bipolar float matrix: [[1 -1 -1 1 1 -1 1 -1]...]
      bp_r.at<float> (y, x) = Rbits[idx++] * -2.0 + 1;
  return {Lr, bp_r};
}

/// Random mask `Ksmall` - size Lks × Lks
static cv::Mat
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
  cv::Mat Ksmall (Lks, Lks, CV_32F);
  int idx = 0;
  for (int y = 0; y < Lks; ++y)
    for (int x = 0; x < Lks; ++x)
      Ksmall.at<float> (y, x) = Kbits[idx++] * -2.0 + 1;
  return Ksmall;
}

/// Local mean (box filter) - mirrors `common.local_mean`
static cv::Mat
local_mean (const cv::Mat &img, const cv::Size &win)
{
  cv::Mat mean;
  cv::boxFilter (img, mean, CV_32F, win,
                 cv::Point (-1, -1), true, cv::BORDER_REFLECT);
  return mean;
}

/// Local variance - mirrors `common.local_variance`
static cv::Mat
local_variance (const cv::Mat &img)
{
  const cv::Size win (Config::var_win_w, Config::var_win_h);
  cv::Mat mean1 = local_mean (img, win);
  cv::Mat img2  = img.mul (img);
  cv::Mat mean2 = local_mean (img2, win);
  return mean2 - mean1.mul (mean1);
}

/// Non-linear strength function `F` (identical to `common.F`)
static cv::Mat
compute_F (const cv::Mat &img_variance, float strength)
{
  cv::Mat var_clamped;
  cv::max (img_variance, 1e-5, var_clamped);    // enforce ≥ 1e-5
  cv::Mat sqrt_var;                             // img_std
  cv::sqrt (var_clamped, sqrt_var);
  cv::Mat log2_var;                             // np.log2 (img_std)
  cv::log (sqrt_var, log2_var);                 // natural log
  log2_var /= std::log (2.0);                   // → log₂
  cv::Mat result;
  cv::max (log2_var, strength, result);         // max(strength, log₂(√var))
  return result;
}

/// Choose an integer r such that 99.5% of the watermark pixels is in [-r:r] for areas of constant color
/// Determine the integer range r so that 99.5 % of |W·s| < r
static int
wm_range (const cv::Mat &W, float strength)
{
  // TODO: optimize F (0, strength) == strength
  // compute_F(cv::Mat::zeros(1, 1, CV_32F), strength) is actually: max(log2(sqrt(1e-5)), strength)
  const float s = compute_F (cv::Mat::zeros (1, 1, CV_32F), strength).at<float> (0, 0);
  // TODO: const float s = strength;
  cv::Mat abs_scaled = cv::abs (W * s);
  const double total = abs_scaled.total();
  for (int r = 0; r < 32; r++) {
    cv::Mat mask = abs_scaled < r;
    int inside = cv::countNonZero (mask);
    if (inside / total > 0.995f) // calculates mean
      return r;
  }
  dprintf (2, "imagewmark: error detecting watermark range\n");
  return 16;
}

/** Clip the host image to leave head-room for the watermark.
 * we need some headroom to add the watermark, so in this function we ensure that
 * ll channels of the image are in range [r, 255 - r], where r is the is the
 * pixel offset the watermark will add for areas of constant color
 */
static cv::Mat
wm_pre_clip (const cv::Mat &img, const cv::Mat &W, float strength)
{
  /* - for grayscale, simple range clipping is enough
   * - for color images we watermark in the YIQ colorspace - however, since
   *   changing the Y channel in YIQ and converting back to RGB has the same
   *   effect on each of the RGB channels, we can simply use the range r for the
   *   individual color channels
   */
  const double r = wm_range (W, strength);
  cv::Mat clipped = img.clone();
  cv::Mat low  = clipped < r;
  clipped.setTo (r, low);
  cv::Mat high = clipped > 255 - r;
  clipped.setTo (255 - r, high);
  // TODO: manual single pass could be faster
  return clipped;
}

/// Convert from float to int; see: dither.py:round_pixels()
static void
round_pixels (cv::Mat &img)
{
  // dprintf (2, "round_pixels: img.type()=%d (CV_32FC1=%d CV_32FC3=%d)\n", img.type(), CV_32FC1, CV_32FC3);
  assert (img.type() == CV_32FC1 || img.type() == CV_32FC3);
  img += 0.5f;                  // Add 0.5 for proper rounding to nearest integer
  img.convertTo (img, CV_8U);   // Convert the float image to 8-bit unsigned integer
}


// "ITU-R BT.1700 Characteristics of composite video signals for conventional analogue television systems"
// https://www.itu.int/rec/R-REC-BT.1700-0-200502-I/en
// Transformation matrix for BGR to YIQ (adjusted from RGB to YIQ)
static const cv::Matx33f
BGR2YIQ_MATRIX ( +0.1140, +0.5870, +0.2990,   // Y row
                 -0.3213, -0.2746, +0.5959,   // I row
                 +0.3112, -0.5227, +0.2115 ); // Q row
static const cv::Matx33f
YIQ2BGR_MATRIX ( +1.0000, -1.1067, +1.7044,   // B row
                 +1.0000, -0.2720, -0.6472,   // G row
                 +1.0000, +0.9560, +0.6207 ); // R row

/// Embed the watermark
static cv::Mat
add_watermark (const cv::Mat &src, const cv::Mat &W, double strength, const AddOptions &options)
{
  // TODO: check element type of Mat src
  // Convert to float and apply head-room clipping
  cv::Mat src_f; // TODO: use single pass for float + clip
  src.convertTo (src_f, CV_32F);
  cv::Mat img = wm_pre_clip (src_f, W, strength);
  // Extract the Y (luminance) channel
  cv::Mat yiq, Y;
  std::vector<cv::Mat> ch;
  if (src.channels() == 1)
    Y = img;
  else if (src.channels() == 3) {
    // cv::cvtColor (img, yiq, cv::COLOR_BGR2YIQ);
    cv::transform (img, yiq, BGR2YIQ_MATRIX);
    cv::split (yiq, ch);
    Y = ch[0];
  } else
    die (1, "Input image with %d channels not supported", src.channels());
  // Compute local variance
  cv::Mat I_var = local_variance (Y);
  // Strength map I_s
  cv::Mat I_s = compute_F (I_var, strength);
  // Add the scaled watermark
  cv::Mat Y_wm = Y + W.mul (I_s);

  // TODO: Clip back to [0,255] : cv::Mat Y_clipped; cv::min (Y_wm, 255.0, Y_clipped); cv::max (Y_clipped, 0.0, Y_clipped);
  // cv::min (Y_wm, 255.0, Y_wm); cv::max (Y_wm, 0.0, Y_wm);

  // Reconstruct image from luminance channel
  if (src.channels() == 3) {
    ch[0] = Y_wm;
    cv::merge (ch, yiq);
    cv::Mat dst;
    // cv::cvtColor (yiq, dst, cv::COLOR_YIQ2BGR);
    cv::transform (yiq, dst, YIQ2BGR_MATRIX);
    return dst;
  } else
    return Y_wm;
}

/// PSNR (peak-signal-to-noise ratio), see: common.py:psnr()
static double
compute_psnr (const cv::Mat &orig, const cv::Mat &wm)
{
  cv::Mat diff;
  cv::absdiff (orig, wm, diff);
  diff.convertTo (diff, CV_32F);
  diff = diff.mul (diff);
  cv::Scalar s = cv::sum (diff);
  // Note, for grey images: s[1]==0 && s[2]==0
  double mse = (s[0] + s[1] + s[2]) /
               (static_cast<double> (orig.total()) * orig.channels());
  // No difference at all?
  if (mse == 0)
    return 100;
  const double max_pixel = 255.0;
  double psnr = 10.0 * std::log10 ((max_pixel * max_pixel) / mse);
  return psnr;
}

/// Main embedding routine (command_add() in Python)
static void
command_add (const AddOptions &opt)
{
  // Load the host image in BGR order
  cv::Mat host = cv::imread (opt.input_img, cv::IMREAD_COLOR); // == IMREAD_COLOR_BGR
  if (host.empty())
    die (1, "failed to load image: %s", opt.input_img.c_str());

  // Message → payload → ECC → reshape to 16 × 16 matrix
  const std::vector<bool> payload = parse_payload (opt.message_hex.empty() ? "0" : opt.message_hex);
  // dprintf (2, "Message: %s\n", bits_to_hex (payload).c_str());
  const std::vector<bool> encoded = convcode_encode (payload);
  const int Ldim = Config::payload_rows;                 // 16
  assert (Config::payload_rows == Config::payload_cols); // need square payload
  cv::Mat m_enc (Ldim, Ldim, CV_8U);
  for (int y = 0; y < Ldim; y++)
    for (int x = 0; x < Ldim; x++)
      m_enc.at<uint8_t> (y, x) = encoded[y * Ldim + x] ? 1 : 0;

  // Generate the basic watermark unit (r-pattern)
  const auto [Lr, bp_r] = make_wm_pattern();
  const int Lwsmall = Ldim * Lr;                       // 64

  // Spread-spectrum encoding of `m_enc` with `bp_r`
  cv::Mat wmunit (Lwsmall, Lwsmall, CV_32F);
  for (int j = 0; j < Ldim; j++)
     for (int i = 0; i < Ldim; i++) {
      const int lj = j * Lr, li = i * Lr;
      const float neg = m_enc.at<uint8_t> (j, i) > 0 ? 1.0 : -1.0;
      for (int dy = 0; dy < Lr; dy++)
        for (int dx = 0; dx < Lr; dx++)
          wmunit.at<float> (lj + dy, li + dx) = neg * bp_r.at<float> (dy, dx);
    }

  // Generate key-dependent mask `Ksmall`
  cv::Mat Ksmall = make_wm_mask (Lwsmall);
  // Mask wmunit with Ksmall
  cv::Mat wmasked = wmunit.mul (Ksmall);

  // Determine zoom factor (dynamic or user-provided)
  double ZOOM = opt.zoom;       // Zoom level set by --zoom
  // Use dynamic_zoom from config (allow override with --dynamic-zoom)
  if (ZOOM <= 0) {
    const double dynamic_zoom = opt.dynamic_zoom > 0 ? opt.dynamic_zoom : Config::dynamic_zoom;
    ZOOM = std::min (host.cols, host.rows) / double (Lwsmall) / dynamic_zoom;
    ZOOM = std::max (Config::minimum_zoom, ZOOM);
  }

  // Determine watermark tiles to cover the image
  int hreps = host.cols / Lwsmall / ZOOM + 2;
  int vreps = host.rows / Lwsmall / ZOOM + 2;
  // Ensure watermark is centered around one unit in the middle
  if (hreps % 2 == 0)
    hreps += 1;
  if (vreps % 2 == 0)
    vreps += 1;
  // Tile the masked unit with alternating x/y-flips to cover the image
  cv::Mat tiled_img (Lwsmall * vreps, Lwsmall * hreps, CV_32F);
  for (int v = 0; v < vreps; ++v)
    for (int h = 0; h < hreps; ++h) {
      cv::Mat tile = wmasked.clone();
      if (h % 2) cv::flip (tile, tile, 1); // horizontal flip
      if (v % 2) cv::flip (tile, tile, 0); // vertical flip
      cv::Rect roi (h * Lwsmall, v * Lwsmall, Lwsmall, Lwsmall);
      tile.copyTo (tiled_img (roi));
    }
  // Resize to the host size, see: common.py:zoom_image()
  cv::Mat W;
  cv::resize (tiled_img, W, cv::Size(), ZOOM, ZOOM, cv::INTER_CUBIC);
  // TODO: c++ cannot optimize/reuse multiple cv::Mat variables, so we are wasting quite a bit of memory here

  // Crop to exactly the host dimensions (centered)
  const int dy = (W.rows - host.rows + 1) / 2;
  const int dx = (W.cols - host.cols + 1) / 2;
  if (dy || dx) {
    cv::Rect roi (dx, dy, host.cols, host.rows);
    W = W (roi).clone();
  }

  // Embed the watermark
  cv::Mat watermarked = add_watermark (host, W, opt.strength, opt);

  // Conversion to 8-bit
  round_pixels (watermarked);

  // Write the result
  if (!cv::imwrite (opt.output_img, watermarked))
    die (1, "Failed to write output image: %s", opt.output_img.c_str());

  // Optional quality reporting
  if (opt.trace_psnr || opt.trace_quality) {
    double psnr = compute_psnr (host, watermarked);
    dprintf (2, "PSNR: %f\n", psnr);
  }

  // TODO: fix debug printouts
}

/// Entry point - run after CLI parsing, implements `command_add`
int
imagewmark_add (const AddOptions &options)
{
  add_config.prng_wm_pattern = new Random (0, Random::Stream::wm_pattern);
  add_config.prng_wm_mask = new Random (0, Random::Stream::wm_mask);

  command_add (options);
  return 0;
}
