// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#include "jpeg_quality.hh"
#include <array>
#include <cstdint>
#include <fstream>
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
  const size_t n = f.tellg();
  f.seekg (0);
  std::vector<uint8_t> b (n);
  f.read (reinterpret_cast<char*> (b.data()), n);

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
  std::array<int16_t, 64> qt;
  bool found = false;
  for (size_t i = 0; i + 4 < n;) {                                      // OOB guard for marker scan
    if (d[i] != 0xFF || d[i + 1] != 0xDB) {
      i += 1;
      continue;
    }
    // big-endian segment length, as per spec §B.1.1.2
    size_t len = (d[i + 2] << 8) | d[i + 3], off = i + 4;
    while (off < i + 2 + len) {                                         // stay within DQT segment
      int pt_id = d[off++];
      int prec = pt_id >> 4;
      int table_id = pt_id & 0x0f;
      const size_t need = 64 * (1 + prec);
      if (off + need > i + 2 + len)
        break;                                                          // truncated table, skip
      if (table_id == 0) {                                              // luma, last one wins
        for (int k = 0; k < 64; ++k) {
          qt[k] = prec ? ((d[off] << 8) | d[off + 1]) : d[off];
          off += 1 + prec;
        }
        found = true;
      } else
        off += need;                                                    // skip non-luma tables
    }
    i = i + 2 + len;
  }
  if (!found)
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
