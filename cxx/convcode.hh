// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
/*
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
#include <vector>

#ifndef IMAGEWMARK_RANDOM_HH
#define IMAGEWMARK_RANDOM_HH

void               convcode_test   ();
void               convcode_check  ();
std::vector<int>   convcode_encode (const std::vector<float> &bits);
std::vector<int>   convcode_decode (const std::vector<float> &bits, double *normalized_error);
std::vector<float> read_stdin_bits ();

#endif /* IMAGEWMARK_RANDOM_HH */
