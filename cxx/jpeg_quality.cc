// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#include "jpeg_quality.hh"
#include <array>
#include <cstdint>
#include <fstream>
#include <vector>

static constexpr int MIN_QUALITY = 50;  // must be >= 50: IJG scale formula changes below that
static constexpr int QUALITY_LEVELS  = 100 - MIN_QUALITY + 1;

// JPEG Annex K (ITU-T T.81) luminance quantization table, zigzag order
static constexpr int L[64] = {
  16, 11, 10, 16,  24,  40,  51,  61,
  12, 12, 14, 19,  26,  58,  60,  55,
  14, 13, 16, 24,  40,  57,  69,  56,
  14, 17, 22, 29,  51,  87,  80,  62,
  18, 22, 37, 56,  68, 109, 103,  77,
  24, 35, 55, 64,  81, 104, 113,  92,
  49, 64, 78, 87, 103, 121, 120, 101,
  72, 92, 95, 98, 112, 100, 103,  99,
};

// Precomputed luma reference tables for Q=MIN_QUALITY..100
static constexpr std::array<std::array<int16_t, 64>, QUALITY_LEVELS>
build_R()
{
  std::array<std::array<int16_t, 64>, QUALITY_LEVELS> r{};
  for (int q = 0; q < QUALITY_LEVELS; ++q) {
    int sc = 200 - 2 * (q + MIN_QUALITY);
    for (int k = 0; k < 64; k++)
      r[q][k] = (L[k] * sc + 50) / 100;
  }
  return r;
}
inline constexpr auto R = build_R();

int
estimate_jpeg_quality (const char *path, int fallback)
{
  std::ifstream f (path, std::ios::binary | std::ios::ate);
  if (!f)
    return fallback;
  size_t n = f.tellg();
  f.seekg (0);
  std::vector<uint8_t> b (n);
  f.read (reinterpret_cast<char*> (b.data()), n);

  // Extract first DQT table only, luma is typically id=0, first in file.
  // DQT segment layout per ISO/IEC 10918-1 §B.2.4.1 (ITU-T T.81):
  //   marker 0xFFDB, big-endian length (including the 2 length bytes),
  //   then one or more tables: precision nibble (Pt=0 → 8-bit, Pt=1 → 16-bit),
  //   table ID nibble, followed by 64 coefficients in zigzag order.
  std::vector<int16_t> qt (64);
  const uint8_t *d = b.data();
  for (size_t i = 0; i + 4 < n;) {                                      // OOB guard for marker scan
    if (d[i] != 0xFF || d[i + 1] != 0xDB) {
      i += 1;
      continue;
    }
    // big-endian segment length, as per spec §B.1.1.2
    size_t len = (d[i + 2] << 8) | d[i + 3], off = i + 4;
    while (off < i + 2 + len) {                                         // stay within DQT segment
      int prec = d[off++] >> 4;
      size_t need = 64 * (1 + prec);
      if (off + need > i + 2 + len)
        break;                                                          // truncated table, skip
      for (int k = 0; k < 64; ++k) {
        qt[k] = prec ? ((d[off] << 8) | d[off + 1]) : d[off];
        off += 1 + prec;
      }
      goto found;                                                       // got first table, done
    }
    i = i + 2 + len;
  }
  return fallback;

 found:
  // Find best Q: minimize sum-of-squared-errors (SSE) against luma reference
  int best = MIN_QUALITY;
  double best_e = 1e30;
  for (int q = 0; q < QUALITY_LEVELS; ++q) {
    double e = 0;
    for (int k = 0; k < 64; ++k) {
      double x = qt[k] - R[q][k];
      e += x * x;
    }
    if (e < best_e) {
      best_e = e;
      best = q + MIN_QUALITY;
    }
  }
  return best;
}
