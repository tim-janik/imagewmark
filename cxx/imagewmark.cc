// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#include "imagewmark.hh"
#include "random.hh"
#include "convcode.hh"
#include <stdio.h>

static void     image_info (const String &input);
static void     convert_image (const String &input, const String &output, const String &bits);

static void
usage (int code)
{
  printf ("Usage: %s [options] <command> <args...>\n", argv0);
  printf ("Options:\n");
  printf ("  --key <file>          load watermarking key from file\n");
  printf ("  --test-key <int>      specify test key directly\n");
  printf ("Commands:\n");
  printf ("  GET <inputimage>      extract watermarks from image\n");
  printf ("  ADD <inimage> <outimage> <wmark>\n");
  printf ("                        add watermark to image\n");
  printf ("  GEN-KEY <keyfile>     generate 128-bit watermarking key\n");
  printf ("  RAND                  internal key based PRNG\n");
  exit (code);
}

static bool
getarg (const char *argname, String &s, const char **argv, int &i)
{
  if (!argname || i < 0 || !argv || !argv[i])
    return false;
  String a = argname;
  if (a == argv[i])
    {
      if (argv[i + 1])
        {
          s = argv[++i];
          return true;
        }
      return false;
    }
  const unsigned l = strlen (argv[i]);
  if (l > a.size() && argv[i][a.size()] == '=')
    {
      s = argv[i] + a.size() + 1;
      return true;
    }
  return false;
}

static bool
getarg (const char *argname, long long &ll, const char **argv, int &i)
{
  String s;
  if (getarg (argname, s, argv, i))
    {
      char *e = nullptr;
      ll = strtoll (s.c_str(), &e, 0);
      if (e && e[0]) {
        dprintf (2, "invalid decimal: %s\n", s.c_str());
        exit (1);
      }
      return true;
    }
  return false;
}

const char *argv0 = nullptr;

int
main (int argc, const char *argv[])
{
  argv0 = argv[0]; // used for error handling
  // parse args
  std::vector<String> args;
  String s;
  long long ll;
  for (int i = 1; argv[i]; i++)
    {
      if (getarg ("--key", s, argv, i))
        Random::load_global_key (s);
      else if (getarg ("--test-key", ll, argv, i))
        Random::set_global_test_key (ll);
      else
        args.push_back (argv[i]);
    }
  // handle commands
  if (args.size() == 1 && args[0] == "convcode-test")
    {
      convcode_test ();
      return 0;
    }
  else if (args.size() == 1 && args[0] == "convcode-check")
    {
      convcode_check ();
      return 0;
    }
  else if (args.size() == 1 && args[0] == "convcode-encode")
    {
      for (;;)
        {
          const std::vector<float> bits = read_stdin_bits ();
          if (bits.empty())
            return 0;

          for (auto b : convcode_encode (bits))
            printf ("bit %d\n", b);
          printf ("end\n");
          fflush (stdout);
        }
    }
  else if (args.size() == 1 && args[0] == "convcode-decode")
    {
      for (;;)
        {
          const std::vector<float> bits = read_stdin_bits ();
          if (bits.empty())
            return 0;

          double normalized_error = 0;
          for (auto b : convcode_decode (bits, &normalized_error))
            printf ("bit %d\n", b);
          printf ("error %f\n", normalized_error);
          printf ("end\n");
          fflush (stdout);
        }
    }
  else if (args.size() == 2 && string_tolower (args[0]) == "gen-key")
    {
      const String outfile = args[1];
      FILE *f = fopen (outfile.c_str(), "w");
      if (!f ||
          fprintf (f, "# watermarking key for imagewmark\n\nkey %s\n", Random::gen_key().c_str()) < 0 ||
          fclose (f) < 0)
        die (5, "failed to create `%s`: %s\n", outfile.c_str(), strerror (errno));
    }
  else if (args.size() == 2 && string_tolower (args[0]) == "get")
    {
      const String input = args[1];
      image_info (input);
    }
  else if (args.size() == 4 && string_tolower (args[0]) == "add")
    {
      const String input = args[1], output = args[2], bits = args[3];
      convert_image (input, output, bits);
    }
  else if (args.size() == 1 && string_tolower (args[0]) == "rand")
    {
      const std::pair<Random::Stream,const char*> streams[] = { { Random::Stream::wm_pattern, "wm_pattern" },
                                                                { Random::Stream::wm_mask, "wm_mask" },
                                                                { Random::Stream::wm_convcode, "wm_convcode" } };
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
      s.pop_back(); s.pop_back(); s += '\n'; // remove trailing comma
      s += "}";
      printf ("%s\n", s.c_str());
    }
  else
    usage (0);
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
  inp->close ();

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

static void
convert_image (const String &input, const String &output, const String &bits)
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

  printf ("%s:\n", input.c_str());
  printf ("size: %dx%d\n", img.width, img.height);
  printf ("oldcomm: %s\n", img.comment.c_str());

  const size_t payload_size = 128;
  std::vector<int> bitvec = bit_str_to_vec (bits);
  if (bitvec.empty())
    die (5, "failed to parse bits: %s", bits.c_str());
  if (bitvec.size() < payload_size)
    {
      std::vector<int> expanded_bitvec;
      for (size_t i = 0; i < payload_size; i++)
        expanded_bitvec.push_back (bitvec[i % bitvec.size()]);
      bitvec = expanded_bitvec;
    }
  printf ("message: %s\n", bit_vec_to_str (bitvec).c_str());
  std::vector<int> hbits = bits_add_hash (bitvec);
  printf ("hashed:  %s (validates=%d)\n", bit_vec_to_str (hbits).c_str(), bits_validate_hash (hbits) == bitvec);

  Random crng (0, Random::Stream::img_comment);
  for (size_t i = 0; i < hbits.size(); i++)
    hbits[i] ^= crng() & 1;
  const String cmessage = bit_vec_to_str (hbits);
  printf ("shuffle: %s\n", cmessage.c_str());

  ImageSpec out_spec = inp->spec();
  if (string_endswith (string_tolower (output), ".png"))
    out_spec.attribute ("Comment", cmessage.c_str());
  else
    out_spec.attribute ("ImageDescription", cmessage.c_str());
  std::unique_ptr<ImageOutput> out = ImageOutput::create (output);
  if (out &&
      out->open (output, out_spec) &&
      out->copy_image (inp.get()) &&
      out->close ())
    ; // success
  else
    die (1, "%s: failed to save image `%s`: %s", argv0, output.c_str(), strerror (errno));

  inp->close ();
}
