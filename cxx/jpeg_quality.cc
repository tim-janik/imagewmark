// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#include "jpeg_quality.hh"
#include <array>
#include <cstdint>
#include <fstream>
#include <limits>
#include <vector>

static constexpr int MIN_QUALITY = 50;  // must be >= 50: IJG scale formula changes below that
static constexpr int QUALITY_LEVELS  = 100 - MIN_QUALITY + 1;

// JPEG Annex K (ITU-T T.81) luminance quantization table, reordered the
// way libjpeg-turbo API v62 emit_dqt via jpeg_natural_order arranges them.
static constexpr uint8_t IJG_L[64] = {
   16,  11,  12,  14,  12,  10,  16,  14,
   13,  14,  18,  17,  16,  19,  24,  40,
   26,  24,  22,  22,  24,  49,  35,  37,
   29,  40,  58,  51,  61,  60,  57,  51,
   56,  55,  64,  72,  92,  78,  64,  68,
   87,  69,  55,  56,  80, 109,  81,  87,
   95,  98, 103, 104, 103,  62,  77, 113,
  121, 112, 100, 120,  92, 101, 103,  99,
};

// Precomputed luma reference tables for Q=MIN_QUALITY..100
static constexpr std::array<std::array<int16_t, 64>, QUALITY_LEVELS>
build_R()
{
  std::array<std::array<int16_t, 64>, QUALITY_LEVELS> r{};
  for (int q = 0; q < QUALITY_LEVELS; ++q) {
    const int sc = 200 - 2 * (q + MIN_QUALITY);
    // IJG quality-to-scale formula (Q >= 50): scale = (200 - 2*Q) / 100
    for (int k = 0; k < 64; k++)
      r[q][k] = (IJG_L[k] * sc + 50.0) / 100;
  }
  return r;
}

inline constexpr auto R_IJG = build_R();

int
estimate_jpeg_quality (const char *path, int fallback)
{
  std::ifstream f (path, std::ios::binary | std::ios::ate);
  if (!f)
    return fallback;
  const std::streamoff length = f.tellg();
  if (length < 2 || static_cast<uintmax_t> (length) > std::numeric_limits<size_t>::max() ||
      static_cast<uintmax_t> (length) > static_cast<uintmax_t> (std::numeric_limits<std::streamsize>::max()))
    return fallback;
  const size_t n = static_cast<size_t> (length);
  f.seekg (0);
  if (!f)
    return fallback;
  std::vector<uint8_t> b (n);
  f.read (reinterpret_cast<char*> (b.data()), static_cast<std::streamsize> (n));
  if (!f)
    return fallback;

  // Must be a JPEG file: SOI marker 0xFFD8 at offset 0.
  // Avoids false positives on J2K, PNG, etc. where random bytes match DQT.
  if (b[0] != 0xFF || b[1] != 0xD8)
    return fallback;
  const uint8_t *const d = b.data();

  // Extract the *last* (quality-scaled) luma DQT table (id=0).
  // DQT segment layout per ISO/IEC 10918-1 §B.2.4.1 (ITU-T T.81):
  //   marker 0xFFDB, big-endian length (including the 2 length bytes),
  //   then one or more tables: precision nibble (Pt=0 → 8-bit, Pt=1 → 16-bit),
  //   table ID nibble, followed by 64 coefficients in zigzag order.
  std::array<uint16_t, 64> qt;
  bool found = false;
  bool in_scan = false;
  bool complete = false;
  size_t pos = 2;
  while (pos < n) {
    if (in_scan)
      while (pos < n && d[pos] != 0xFF)
        pos++;
    if (pos >= n || d[pos++] != 0xFF)
      return fallback;
    while (pos < n && d[pos] == 0xFF)
      pos++;
    if (pos >= n)
      return fallback;
    const uint8_t marker = d[pos++];
    if (marker == 0x00) {
      if (!in_scan)
        return fallback;
      continue;
    }
    if (marker >= 0xD0 && marker <= 0xD7) {
      if (!in_scan)
        return fallback;
      continue;
    }
    in_scan = false;
    if (marker == 0xD9) {
      complete = true;
      break;
    }
    if (marker == 0xD8)
      return fallback;
    if (marker == 0x01)
      continue;
    if (n - pos < 2)
      return fallback;
    const size_t len = (d[pos] << 8) | d[pos + 1];
    if (len < 2 || len > n - pos)
      return fallback;
    const size_t segment_end = pos + len;
    pos += 2;
    if (marker == 0xDB) {
      while (pos < segment_end) {
        const uint8_t pt_id = d[pos++];
        const uint8_t precision = pt_id >> 4;
        const uint8_t table_id = pt_id & 0x0F;
        if (precision > 1 || table_id > 3)
          return fallback;
        const size_t width = precision + 1;
        const size_t need = 64 * width;
        if (need > segment_end - pos)
          return fallback;
        if (table_id == 0) {
          for (int k = 0; k < 64; ++k) {
            qt[k] = precision ? ((d[pos] << 8) | d[pos + 1]) : d[pos];
            pos += width;
          }
          found = true;
        } else
          pos += need;
      }
    }
    pos = segment_end;
    if (marker == 0xDA)
      in_scan = true;
  }
  if (!complete || !found)
    return fallback;                                                    // no luma DQT found
  // Find best Q: minimize sum-of-squared-errors (SSE) against luma reference
  int best = MIN_QUALITY;
  double best_e = 1e38;
  for (int q = 0; q < QUALITY_LEVELS; ++q) {
    // SSE against IJG reference
    double e = 0;
    for (int k = 0; k < 64; ++k) {
      double x = qt[k] - R_IJG[q][k];
      e += x * x;
    }
    if (e < best_e) {
      best_e = e;
      best = q + MIN_QUALITY;
    }
  }
  return best;
}
