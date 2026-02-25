// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#include "imagewmark.hh"
#include "random.hh"
#include <stdio.h>

const char *argv0 = nullptr;

int
main (int argc, char *argv[])
{
  argv0 = argv[0]; // used for error handling

  CLI::App app { "imagewmark - Add watermark to image" };
  app.ignore_case(); // Allow case-insensitive subcommands (e.g., GEN-KEY vs gen-key)
  app.require_subcommand (1); // Require at least one command to be present
  app.fallthrough(); // Allow global options as part of subcommands

  // --- Global Options ---
  std::string key_file;
  app.add_option ("--key", key_file, "Load watermarking key from file");

  std::string test_key;
  app.add_option ("--test-key", test_key, "Specify test key (for debugging only, insecure)");

  // ADD <inimage> <outimage> <wmark>
  AddOptions add_options;
  CLI::App *cmd_add = imagewmark_add_options (app, add_options);

  // --- Parse Arguments ---
  CLI11_PARSE (app, argc, argv);

  // --- Handle Global Options ---
  if (!key_file.empty()) {
    Random::load_global_key (key_file);
  } else if (!test_key.empty()) {
    std::string s = test_key;
    while (s.size() < 32)
      s = "0" + s; // expand to 128bit
    Random::set_global_test_key (s);
  } else {
    static constexpr const char *DEFAULT_KEY = "00000000000000000000000000000000";
    Random::set_global_test_key (DEFAULT_KEY);
  }

  // --- Handle Commands ---
  if (cmd_add->parsed())        // only add is supported
    return imagewmark_add (add_options);

  return 0;
}
