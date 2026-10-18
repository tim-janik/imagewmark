// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#include <cstdio>
#include "../butteraugli-build/wrapper.cc"

int
main ()
{
  for (size_t size : {32, 2048})
    {
      butteraugli::ImageF diffmap (size, size);
      const float value = 0.1f;
      for (size_t y = 0; y < size; ++y)
        for (size_t x = 0; x < size; ++x)
          diffmap.Row (y)[x] = value;
      const double l3 = butteraugli::score_from_diffmap_l3 (diffmap);
      const double l2 = butteraugli::score_from_diffmap_l2 (diffmap);
      if (std::abs (l3 - value) > 1e-9 || std::abs (l2 - value) > 1e-9)
        {
          std::fprintf (stderr, "%zu px map: L3 %.12g, L2 %.12g, expected %.12g\n", size, l3, l2, static_cast<double> (value));
          return 1;
        }
    }
  return 0;
}
