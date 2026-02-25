// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#include "imagewmark.hh"
#include "random.hh"
#include <stdio.h>
#include <unistd.h>
#include <limits.h>
#include <libgen.h>

const char *argv0 = nullptr;

// Become imagewmark.py
[[noreturn]] static void
exec_python (int argc, char *argv[])
{
  // find the directory of this executable
  char exe_path[PATH_MAX + 1] = { 0, };
  const ssize_t len = readlink ("/proc/self/exe", exe_path, sizeof (exe_path) - 1);
  if (len < 0)
    die (1, "failed to read /proc/self/exe: %s", strerror (errno));
  exe_path[len] = 0;
  const char *dir = dirname (exe_path);

  // build path to Python script
  char python_script[PATH_MAX + 1] = { 0, };
  snprintf (python_script, sizeof (python_script), "%s/../src/imagewmark.py", dir);

  // prepare new argv with python script as first argument
  const char **new_argv = (const char**) malloc ((argc + 2) * sizeof (char*));
  new_argv[0] = "python3";
  new_argv[1] = python_script;
  for (int i = 1; i < argc; i++)
    new_argv[i + 1] = argv[i];
  new_argv[argc + 1] = nullptr;

  // exec Python script
  execvp ("python3", (char*const*) new_argv);
  die (1, "failed to exec python3: %s", strerror (errno));
}

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

  // For any other command, delegate to imagewmark.py
  exec_python (argc, argv);

  return 1; // Should not be reached
}
