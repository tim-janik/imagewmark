// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#pragma once

#include <cstdio>
#include <cstring>

extern const char imagewmark_version[];

static inline bool
print_version (int argc, char *argv[], const char *program)
{
  for (int i = 1; i < argc && std::strcmp (argv[i], "--") != 0; i++)
    if (std::strcmp (argv[i], "--version") == 0 || std::strcmp (argv[i], "-V") == 0)
      {
        std::printf ("%s %s\n", program, imagewmark_version);
        return true;
      }
  return false;
}
