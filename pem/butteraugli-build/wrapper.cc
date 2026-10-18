// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
// C wrapper exposing butteraugli_compare_arrays / butteraugli_compare_arrays_l2
// (uint8 RGB HWC arrays) with 3-norm and 2-norm scoring respectively.
#include <cmath>
#include <cstdint>
#include <vector>
#include "butteraugli/butteraugli.h"

namespace butteraugli {
namespace {

// sRGB -> linear LUT
const double* NewSrgbToLinearTable() {
  static double table[256];
  static bool inited = false;
  if (!inited) {
    for (int i = 0; i < 256; ++i) {
      double srgb = i / 255.0;
      table[i] = 255.0 * (srgb <= 0.04045 ? srgb / 12.92 : std::pow((srgb + 0.055) / 1.055, 2.4));
    }
    inited = true;
  }
  return table;
}

// Build ImageF planes from contiguous uint8 RGB HWC array
void BuildImageFromRgb(const uint8_t* data, int h, int w, std::vector<ImageF>& linear) {
  static const double* lut = NewSrgbToLinearTable();
  for (int c = 0; c < 3; c++) {
    linear.push_back(ImageF(w, h));
    for (int y = 0; y < h; ++y) {
      float* row = linear[c].Row(y);
      for (int x = 0; x < w; ++x) {
        row[x] = lut[data[(y * w + x) * 3 + c]];
      }
    }
  }
}

// 3-norm: (mean(diff³))^(1/3), upstream ButteraugliScoreFromDiffmap() returns the max
double ScoreFromDiffmapL3(const ImageF& diffmap) {
  float sum = 0.0f;
  size_t count = 0;
  for (size_t y = 0; y < diffmap.ysize(); ++y) {
    const float * const BUTTERAUGLI_RESTRICT row = diffmap.Row(y);
    for (size_t x = 0; x < diffmap.xsize(); ++x) {
      float v = row[x];
      sum += v * v * v;
      count++;
    }
  }
  if (count == 0) return 0.0;
  return std::pow(sum / count, 1.0f / 3.0f);
}

// 2-norm (RMS): sqrt(mean(diff²))
double ScoreFromDiffmapL2(const ImageF& diffmap) {
  float sum = 0.0f;
  size_t count = 0;
  for (size_t y = 0; y < diffmap.ysize(); ++y) {
    const float * const BUTTERAUGLI_RESTRICT row = diffmap.Row(y);
    for (size_t x = 0; x < diffmap.xsize(); ++x) {
      float v = row[x];
      sum += v * v;
      count++;
    }
  }
  if (count == 0) return 0.0;
  return std::sqrt(sum / count);
}

// Run comparison on two sets of ImageF planes (3-norm)
double CompareLinear(const std::vector<ImageF>& l1, const std::vector<ImageF>& l2) {
  ImageF diff_map;
  double score = 0.0;
  if (!ButteraugliInterface(l1, l2, 1.0, diff_map, score)) return -1.0;
  return ScoreFromDiffmapL3(diff_map);
}

// Run comparison on two sets of ImageF planes (2-norm)
double CompareLinearL2(const std::vector<ImageF>& l1, const std::vector<ImageF>& l2) {
  ImageF diff_map;
  double score = 0.0;
  if (!ButteraugliInterface(l1, l2, 1.0, diff_map, score)) return -1.0;
  return ScoreFromDiffmapL2(diff_map);
}

} // anonymous namespace
} // namespace butteraugli

// ---- C API (same signatures as existing libbutteraugli.so) ----

extern "C" {

double butteraugli_compare_arrays(
    const void* data1, int h1, int w1,
    const void* data2, int h2, int w2) {
  using namespace butteraugli;
  if (h1 != h2 || w1 != w2 || h1 <= 0 || w1 <= 0) return -1.0;
  std::vector<ImageF> linear1, linear2;
  BuildImageFromRgb((const uint8_t*)data1, h1, w1, linear1);
  BuildImageFromRgb((const uint8_t*)data2, h2, w2, linear2);
  return CompareLinear(linear1, linear2);
}

// ---- 2-norm variants ----

double butteraugli_compare_arrays_l2(
    const void* data1, int h1, int w1,
    const void* data2, int h2, int w2) {
  using namespace butteraugli;
  if (h1 != h2 || w1 != w2 || h1 <= 0 || w1 <= 0) return -1.0;
  std::vector<ImageF> linear1, linear2;
  BuildImageFromRgb((const uint8_t*)data1, h1, w1, linear1);
  BuildImageFromRgb((const uint8_t*)data2, h2, w2, linear2);
  return CompareLinearL2(linear1, linear2);
}

} // extern "C"
