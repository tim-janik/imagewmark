// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#ifndef __UTILS_HH__
#define __UTILS_HH__

#include <stdint.h>
#include <stdlib.h>
#include <vector>
#include <algorithm>
#include <cctype>
#include <string>

#include <OpenImageIO/imageio.h>
#include <gcrypt.h>

// == Type Decls ==
using Byte = unsigned char;
using ByteS = std::vector<Byte>;
using String = std::string;

// == Utility Functions ==

/// Convert `str` to lower case.
extern inline String
string_tolower (String str)
{
  for (auto &c : str)
    c = std::tolower (c);
  return str;
}

/// Returns whether @a string ends with @a fragment.
bool string_endswith (const String &string, const String &fragment);

/// Construct std::string in printf()-manner using the "C" locale.
String  string_printf (const char *format, ...) __attribute__ ((__format__ (__printf__, 1, 2)));

/// Indent continuation lines of a multiline string.
String string_reindent (const std::string &s);

/// Exit the program with a message.
void die (int code, const char *format, ...) __attribute__ ((noreturn, __format__ (__printf__, 2, 3)));

/// Parse string of bits into a vector.
std::vector<int> bit_str_to_vec (const String &bits);
/// Format a vector of bits as string.
String           bit_vec_to_str (const std::vector<int> &bit_vec);

/// Parse hex string of bits into a vector.
std::vector<uint8_t> hex_str_to_vec (const String &str);
/// Format a vector of bits as hax string.
String               vec_to_hex_str (const std::vector<uint8_t> &vec);

/// Extend vector by appending a shortened SHA3 hash sum.
std::vector<int> bits_add_hash      (const std::vector<int> &bits);

/// Extract payload vector if hash matches, else returns empty vector.
std::vector<int> bits_validate_hash (const std::vector<int> &bits);

#endif // __UTILS_HH__
