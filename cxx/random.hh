// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
/*
 * Copyright (C) 2018-2020 Stefan Westerfeld
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#pragma once

#include <gcrypt.h>
#include <stdint.h>

#include <vector>
#include <string>

class Random
{
public:
  enum class Stream : uint8_t {
    wm_pattern  = 1,
    wm_mask     = 2,
    wm_convcode = 3,
    img_comment = 4,
  };
private:
  gcry_cipher_hd_t           aes_ctr_cipher = nullptr;
  gcry_cipher_hd_t           seed_cipher = nullptr;
  std::vector<uint64_t>      buffer;
  size_t                     buffer_pos = 0;

  void die_on_error (const char *func, gcry_error_t error);
public:
  Random (uint64_t seed, Stream stream);
  ~Random();

  uint64_t
  operator()()
  {
    if (buffer_pos == buffer.size())
      refill_buffer();

    return buffer[buffer_pos++];
  }
  void refill_buffer();
  void seed (uint64_t seed, Stream stream);

  template<class T> void
  shuffle (std::vector<T>& result)
  {
    // Fisher–Yates shuffle
    for (size_t i = 0; i < result.size(); i++)
      {
        const uint64_t random_number = (*this)();

        size_t j = i + random_number % (result.size() - i);
        std::swap (result[i], result[j]);
      }
  }

  static void        set_global_test_key (std::string testkey);
  static void        load_global_key (const std::string& key_file);
  static std::string gen_key();
};


template<class T> std::vector<T>
randomize_bit_order (const std::vector<T>& bit_vec, bool encode)
{
  std::vector<unsigned int> order;

  for (size_t i = 0; i < bit_vec.size(); i++)
    order.push_back (i);

  Random random (/* seed */ 0, Random::Stream::wm_convcode);
  random.shuffle (order);

  std::vector<T> out_bits (bit_vec.size());
  for (size_t i = 0; i < bit_vec.size(); i++)
    {
      if (encode)
        out_bits[i] = bit_vec[order[i]];
      else
        out_bits[order[i]] = bit_vec[i];
    }
  return out_bits;
}
