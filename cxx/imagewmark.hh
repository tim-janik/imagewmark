// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#ifndef __IMAGEWMARK_HH__
#define __IMAGEWMARK_HH__

#include "utils.hh"
#include "3rdparty/CLI11/CLI11.hpp"

struct Image {
  String comment;
  int    width = 0, height = 0, channels = 0;
  ByteS  pixels;
};

// CLI options for "add"
struct AddOptions {
  std::string cmd;
  std::string input_img;
  std::string output_img;
  std::string message_hex;
  float       strength       =  2.0;    // --strength
  float       zoom           = -1.0;    // --zoom
  float       dynamic_zoom   = -1.0;    // --dynamic-zoom
  bool        trace_psnr     = false;   // --trace-psnr
  bool        trace_quality  = false;   // --trace-quality
};
int       imagewmark_add         (const AddOptions &options);
CLI::App* imagewmark_add_options (CLI::App &app, AddOptions &options);

extern const char *argv0;

#endif // __IMAGEWMARK_HH__
