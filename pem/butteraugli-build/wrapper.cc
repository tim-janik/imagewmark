// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
// Butteraugli 3-norm and 2-norm from uint8 RGB HWC arrays.
#include <cmath>
#include <cstdint>
#include <vector>
#include "butteraugli/butteraugli.h"

namespace butteraugli {
namespace {

// sRGB -> linear LUT
const double*
new_srgb_to_linear_table ()
{
  static double table[256];
  static bool inited = false;
  if (!inited)
    {
      for (int i = 0; i < 256; ++i)
        {
          double srgb = i / 255.0;
          table[i] = 255.0 * (srgb <= 0.04045 ? srgb / 12.92 : std::pow ((srgb + 0.055) / 1.055, 2.4));
        }
      inited = true;
    }
  return table;
}

// Build ImageF planes from contiguous uint8 RGB HWC array
void
build_image_from_rgb (const uint8_t* data, int h, int w, std::vector<ImageF>& linear)
{
  static const double* lut = new_srgb_to_linear_table();
  for (int c = 0; c < 3; c++)
    {
      linear.push_back (ImageF (w, h));
      for (int y = 0; y < h; ++y)
        {
          float* row = linear[c].Row (y);
          for (int x = 0; x < w; ++x)
            row[x] = lut[data[(y * w + x) * 3 + c]];
        }
    }
}

// 3-norm: (mean(diff³))^(1/3), upstream ButteraugliScoreFromDiffmap() returns the max
double
score_from_diffmap_l3 (const ImageF& diffmap)
{
  double sum = 0.0;
  size_t count = 0;
  for (size_t y = 0; y < diffmap.ysize(); ++y)
    {
      const float * const BUTTERAUGLI_RESTRICT row = diffmap.Row (y);
      for (size_t x = 0; x < diffmap.xsize(); ++x)
        {
          double v = row[x];
          sum += v * v * v;
          count++;
        }
    }
  if (count == 0)
    return 0.0;
  return std::cbrt (sum / count);
}

// 2-norm (RMS): sqrt(mean(diff²))
double
score_from_diffmap_l2 (const ImageF& diffmap)
{
  double sum = 0.0;
  size_t count = 0;
  for (size_t y = 0; y < diffmap.ysize(); ++y)
    {
      const float * const BUTTERAUGLI_RESTRICT row = diffmap.Row (y);
      for (size_t x = 0; x < diffmap.xsize(); ++x)
        {
          double v = row[x];
          sum += v * v;
          count++;
        }
    }
  if (count == 0)
    return 0.0;
  return std::sqrt (sum / count);
}

} // anonymous namespace
} // namespace butteraugli

extern "C" {

int
butteraugli_compare_arrays_norms (const void* data1, int h1, int w1,
                                const void* data2, int h2, int w2, double* l3, double* l2)
{
  using namespace butteraugli;
  if (h1 != h2 || w1 != w2 || h1 <= 0 || w1 <= 0)
    return 0;
  std::vector<ImageF> linear1, linear2;
  build_image_from_rgb (static_cast<const uint8_t*> (data1), h1, w1, linear1);
  build_image_from_rgb (static_cast<const uint8_t*> (data2), h2, w2, linear2);
  ImageF diff_map;
  double score = 0.0;
  if (!ButteraugliInterface (linear1, linear2, 1.0, diff_map, score))
    return 0;
  *l3 = score_from_diffmap_l3 (diff_map);
  *l2 = score_from_diffmap_l2 (diff_map);
  return 1;
}

} // extern "C"
