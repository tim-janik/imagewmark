// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#ifndef __IMAGEWMARK_HH__
#define __IMAGEWMARK_HH__

#include "utils.hh"

struct Image {
  String comment;
  int    width = 0, height = 0, channels = 0;
  ByteS  pixels;
};

extern const char *argv0;

#endif // __IMAGEWMARK_HH__
