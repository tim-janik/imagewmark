// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#include "imagewmark.hh"
#include "random.hh"
#include "convcode.hh"
#include <sys/stat.h>
#include <stdio.h>

static void     image_info (const String &input);

const char *argv0 = nullptr;

int
main (int argc, char *argv[])
{
  argv0 = argv[0]; // used for error handling

  CLI::App app { "wmops - Watermark operation helper" };
  app.ignore_case(); // Allow case-insensitive subcommands (e.g., GEN-KEY vs gen-key)
  app.require_subcommand (1); // Require at least one command to be present
  app.fallthrough(); // Allow global options as part of subcommands

  // --- Global Options ---
  std::string key_file;
  app.add_option ("--key", key_file, "Load watermarking key from file");

  std::string test_key;
  app.add_option ("--test-key", test_key, "Specify test key (for debugging only, insecure)");

  // --- Subcommands ---

  // convcode-test
  auto *cmd_test = app.add_subcommand ("convcode-test", "Run convcode tests");

  // convcode-check
  auto *cmd_check = app.add_subcommand ("convcode-check", "Run convcode checks");

  // convcode-encode
  auto *cmd_encode = app.add_subcommand ("convcode-encode", "Encode bits from stdin");

  // convcode-decode
  auto *cmd_decode = app.add_subcommand ("convcode-decode", "Decode bits from stdin");

  // GEN-KEY <keyfile>
  std::string gen_key_outfile;
  auto *cmd_gen_key = app.add_subcommand ("gen-key", "Generate 128-bit watermarking key");
  cmd_gen_key->add_option ("keyfile", gen_key_outfile, "Output key file")->required();

  // GET <inputimage>
  std::string get_input;
  auto *cmd_get = app.add_subcommand ("get", "Extract watermarks from image");
  cmd_get->add_option ("inputimage", get_input, "Input image")->required();

  // RAND
  auto *cmd_rand = app.add_subcommand ("rand", "Internal key based PRNG");

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
  if (cmd_test->parsed()) {
    convcode_test();
    return 0;
  } else if (cmd_check->parsed()) {
    convcode_check();
    return 0;
  } else if (cmd_encode->parsed()) {
    for (;;) {
      const std::vector<float> bits = read_stdin_bits();
      if (bits.empty())
        return 0;

      for (auto b : convcode_encode (bits))
        printf ("bit %d\n", b);
      printf ("end\n");
      fflush (stdout);
    }
  } else if (cmd_decode->parsed()) {
    for (;;) {
      const std::vector<float> bits = read_stdin_bits();
      if (bits.empty())
        return 0;

      double normalized_error = 0;
      for (auto b : convcode_decode (bits, &normalized_error))
        printf ("bit %d\n", b);
      printf ("error %f\n", normalized_error);
      printf ("end\n");
      fflush (stdout);
    }
  } else if (cmd_gen_key->parsed()) {
    FILE *f = fopen (gen_key_outfile.c_str(), "w");
    if (!f || fchmod (fileno (f), 0600) < 0 || // secret key file must only user-readable
        fprintf (f, "# watermarking key for imagewmark\n\nkey %s\n", Random::gen_key().c_str()) < 0 ||
        fclose (f) < 0)
      die (5, "failed to create `%s`: %s\n", gen_key_outfile.c_str(), strerror (errno));
  } else if (cmd_get->parsed()) {
    image_info (get_input);
  } else if (cmd_rand->parsed()) {
    const std::pair<Random::Stream, const char *> streams[] = { { Random::Stream::wm_pattern, "wm_pattern" },
                                                                { Random::Stream::wm_mask, "wm_mask" },
                                                                { Random::Stream::wm_convcode, "wm_convcode" }
    };
    const size_t n_streams = sizeof (streams) / sizeof (streams[0]);
    const size_t L = 4096;
    std::string s;
    s += "{\n";
    for (size_t i = 0; i < n_streams; i++) {
      Random r (0, streams[i].first);
      s += "  \"" + std::string (streams[i].second) + "\": [";
      for (size_t j = 0; j < L; j += sizeof (uint64_t)) {
        char buffer[100] = { 0, };
        const uint64_t b = htobe64 (r()); // big endian
        snprintf (buffer, sizeof (buffer) - 1, "%u,%u,%u,%u,%u,%u,%u,%u,", uint8_t (b >> 56), uint8_t (b >> 48), uint8_t (b >> 40), uint8_t (b >> 32), uint8_t (b >> 24), uint8_t (b >> 16), uint8_t (b >> 8), uint8_t (b));
        s += buffer;
      }
      s.pop_back(); // remove trailing comma
      s += "],\n";
    }
    s.pop_back();
    s.pop_back();
    s += '\n'; // remove trailing comma
    s += "}";
    printf ("%s\n", s.c_str());
  }

  return 0;
}

static void
image_info (const String &input)
{
  Image img;
  using namespace OIIO;
  auto inp = ImageInput::open (input);
  if (!inp)
    die (1, "%s: failed to load image `%s`: %s", argv0, input.c_str(), strerror (errno));
  const ImageSpec &spec = inp->spec();
  img.width = spec.width;
  img.height = spec.height;
  img.channels = spec.nchannels;
  img.pixels.resize (img.width * img.height * img.channels);
  inp->read_image (inp->current_subimage(), inp->current_miplevel(), 0, -1, TypeDesc::UINT8, &img.pixels[0]);
  img.comment = spec.get_string_attribute ("ImageDescription", ""); // JPEG, TIFF
  if (img.comment.empty())
    img.comment = spec.get_string_attribute ("Comment", ""); // PNG
  inp->close();

  printf ("%s:\n", input.c_str());
  printf ("size: %dx%d\n", img.width, img.height);
  printf ("comment: %s\n", img.comment.c_str());

  std::vector<int> bitvec = bit_str_to_vec (img.comment);
  Random crng (0, Random::Stream::img_comment);
  for (size_t i = 0; i < bitvec.size(); i++)
    bitvec[i] ^= crng() & 1;
  const String cmessage = bit_vec_to_str (bitvec);
  printf ("bitvec:  %s\n", bit_vec_to_str (bitvec).c_str());

  std::vector<int> pbits = bits_validate_hash (bitvec);
  if (pbits.size())
    printf ("message: %s\n", bit_vec_to_str (pbits).c_str());
}
