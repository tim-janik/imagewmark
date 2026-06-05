// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#include "utils.hh"
#include "imagewmark.hh"
#include <stdarg.h>

// == Utility Functions ==
static uint8_t
from_hex_nibble (char c)
{
  int uc = (uint8_t)c;

  if (uc >= '0' && uc <= '9') return uc - (uint8_t)'0';
  if (uc >= 'a' && uc <= 'f') return uc + 10 - (uint8_t)'a';
  if (uc >= 'A' && uc <= 'F') return uc + 10 - (uint8_t)'A';

  return 16;	// error
}

std::vector<int>
bit_str_to_vec (const String &bits)
{
  std::vector<int> bitvec;
  for (auto nibble : bits)
    {
      uint8_t c = from_hex_nibble (nibble);
      if (c >= 16)
        return std::vector<int>(); // error

      bitvec.push_back ((c & 8) > 0);
      bitvec.push_back ((c & 4) > 0);
      bitvec.push_back ((c & 2) > 0);
      bitvec.push_back ((c & 1) > 0);
    }
  return bitvec;
}

String
bit_vec_to_str (const std::vector<int>& bit_vec)
{
  String bit_str;

  for (size_t pos = 0; pos + 3 < bit_vec.size(); pos += 4) // convert only groups of 4 bits
    {
      int nibble = 0;
      for (int j = 0; j < 4; j++)
        {
          if (bit_vec[pos + j])
            {
              // j == 0 has the highest value, then 1, 2, 3 (lowest)
              nibble |= 1 << (3 - j);
            }
        }
      const char *to_hex = "0123456789abcdef";
      bit_str += to_hex[nibble];
    }
  return bit_str;
}

std::vector<uint8_t>
hex_str_to_vec (const String &str)
{
  std::vector<uint8_t> result;

  if ((str.size() % 2) != 0) // even length
    return std::vector<uint8_t>();

  for (size_t i = 0; i < str.size() / 2; i++)
    {
      uint8_t h = from_hex_nibble (str[i * 2]);
      uint8_t l = from_hex_nibble (str[i * 2 + 1]);
      if (h >= 16 || l >= 16)
        return std::vector<uint8_t>();

      result.push_back ((h << 4) + l);
    }

  return result;
}

String
vec_to_hex_str (const std::vector<uint8_t>& vec)
{
  String s;
  for (auto byte : vec)
    {
      char buffer[256];

      sprintf (buffer, "%02x", byte);
      s += buffer;
    }
  return s;
}

bool
string_endswith (const String &string, const String &fragment)
{
  return (fragment.size() <= string.size() &&
          0 == string.compare (string.size() - fragment.size(), fragment.size(), fragment));
}

static String
string_vprintf (const char *format, va_list args)
{
  static locale_t posix_c_locale = newlocale (LC_ALL_MASK, "C", NULL);
  locale_t saved_locale = uselocale (posix_c_locale);
  char *cstr = nullptr;
  ssize_t l = vasprintf (&cstr, format, args);
  String result;
  if (l >= 0)
    {
      result = String (cstr, l);
      free (cstr);
    }
  else
    result = "*** Error during vasprintf(" + String (format) + ") ***\n";
  uselocale (saved_locale);
  return result;
}

String
string_printf (const char *format, ...)
{
  va_list args;
  va_start (args, format);
  String result = string_vprintf (format, args);
  va_end (args);
  return result;
}

String
string_reindent (const std::string &s)
{
  String result;
  for (const char c : s) {
    result += c;
    if (c == '\n')
      result += "  ";
  }
  return result;
}

void
die (int code, const char *format, ...)
{
  va_list args;
  va_start (args, format);
  String result = argv0;
  result += ": ";
  result += string_vprintf (format, args);
  va_end (args);
  if (result.size() && result.back() != '\n')
    result += "\n";
  dprintf (2, "%s", result.c_str());
  exit (code);
}

static constexpr int hash_bytes = 8;

std::vector<int>
bits_add_hash (const std::vector<int> &bits)
{
  std::vector<uint8_t> bytes = hex_str_to_vec (bit_vec_to_str (bits));
  gcry_md_hd_t hd = {};
  constexpr int HASHALGO = GCRY_MD_SHAKE128; // openssl dgst -shake128 <inputfile>
  gcry_error_t err = gcry_md_open (&hd, HASHALGO, 0);
  if (!err)
    {
      gcry_md_write (hd, bytes.data(), bytes.size());
      err = gcry_md_final (hd);
    }
  std::vector<uint8_t> digest (hash_bytes);
  if (!err)
    err = gcry_md_extract (hd, HASHALGO, &digest[0], digest.size());
  if (err)
    die (5, "%s: failed: %s", gcry_strsource (err), gcry_strerror (err));
  gcry_md_close (hd);
  std::vector<int> dbits = bit_str_to_vec (vec_to_hex_str (digest));
  std::vector<int> hbits = bits;
  hbits.insert (hbits.end(), dbits.begin(), dbits.end());
  return hbits;
}

std::vector<int>
bits_validate_hash (const std::vector<int> &bits)
{
  if (bits.size() < 8 * hash_bytes)
    return {};
  std::vector<int> pbits = bits;
  pbits.resize (pbits.size() - 8 * hash_bytes);
  std::vector<int> hbits = bits_add_hash (pbits);
  if (hbits != bits)
    return {};
  return pbits; // validated payload
}
