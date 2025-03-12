// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#include "convcode.hh"
#include "random.hh"
#include <array>
#include <algorithm>
#include <assert.h>
#include <stdio.h>
#include <cstring>
#include <string>
#include <random>

using std::vector;
using std::min;
using std::string;

int
parity (unsigned int v)
{
  int p = 0;

  while (v)
    {
      p ^= (v & 1);
      v >>= 1;
    }
  return p;
}

constexpr  auto         ab_generators = std::array<unsigned,2>
  {
    076761, 054533
  };

constexpr  unsigned int ab_rate       = ab_generators.size();
constexpr  unsigned int order         = 15;

constexpr  unsigned int state_count = (1 << order);
constexpr  unsigned int state_mask  = (1 << order) - 1;

constexpr  unsigned int n_payload_bits = 128;

size_t
conv_code_size (size_t msg_size)
{
  return (msg_size + order) * ab_rate;
}

vector<int>
conv_encode (const vector<int>& in_bits)
{
  auto generators = ab_generators;

  vector<int> out_vec;
  vector<int> vec = in_bits;

  /* termination: bring encoder into all-zero state */
  for (unsigned int i = 0; i < order; i++)
    vec.push_back (0);

  unsigned int reg = 0;
  for (auto b : vec)
    {
      reg = (reg << 1) | b;

      for (auto poly : generators)
        {
          int out_bit = parity (reg & poly);

          out_vec.push_back (out_bit);
        }
    }
  return out_vec;
}

/* decode using viterbi algorithm */
vector<int>
conv_decode_soft (const vector<float>& coded_bits, const vector<int>& puncture_pattern, float *error_out = nullptr)
{
  auto generators = ab_generators;
  unsigned int rate = generators.size();
  vector<int> decoded_bits;
  vector<float> puncture_pattern_float;
  for (auto b : puncture_pattern)
    {
      /* move int->float conversions out of the inner loop */
      puncture_pattern_float.push_back (b);
    }

  assert (coded_bits.size() % rate == 0);

  struct StateEntry
  {
    int   last_state;
    float delta;
    int   bit;
  };
  vector<vector<StateEntry>> error_count;
  for (size_t i = 0; i < coded_bits.size() + rate; i += rate) /* 1 extra element */
    error_count.emplace_back (state_count, StateEntry {0, -1, 0});

  error_count[0][0].delta = 0; /* start state */

  /* precompute state -> output bits table */
  vector<float> state2bits;
  for (unsigned int state = 0; state < state_count; state++)
    {
      for (size_t p = 0; p < generators.size(); p++)
        {
          int out_bit = parity (state & generators[p]);
          state2bits.push_back (out_bit);
        }
    }

  for (size_t i = 0; i < coded_bits.size(); i += rate)
    {
      vector<StateEntry>& old_table = error_count[i / rate];
      vector<StateEntry>& new_table = error_count[i / rate + 1];

      for (unsigned int state = 0; state < state_count; state++)
        {
          /* this check enforces that we only consider states reachable from state=0 at time=0*/
          if (old_table[state].delta >= 0)
            {
              for (int bit = 0; bit < 2; bit++)
                {
                  int   new_state = ((state << 1) | bit) & state_mask;

                  float delta = old_table[state].delta;
                  int   sbit_pos = new_state * rate;

                  for (size_t p = 0; p < rate; p++)
                    {
                      const float cbit = coded_bits[i + p];
                      const float sbit = state2bits[sbit_pos + p];

                      /* decoding error weight for this bit; if input is only 0.0 and 1.0, this is the hamming distance */
                      delta += (cbit - sbit) * (cbit - sbit) * puncture_pattern_float[i + p];
                    }

                  if (delta < new_table[new_state].delta || new_table[new_state].delta < 0) /* better match with this link? replace entry */
                    {
                      new_table[new_state].delta      = delta;
                      new_table[new_state].last_state = state;
                      new_table[new_state].bit        = bit;
                    }
                }
            }
        }
    }

  unsigned int state = 0;
  if (error_out)
    {
      int n_transmitted_bits = 0;
      for (auto b : puncture_pattern)
        if (b)
          n_transmitted_bits++;
      *error_out = error_count.back()[state].delta / n_transmitted_bits;
    }
  for (size_t idx = error_count.size() - 1; idx > 0; idx--)
    {
      decoded_bits.push_back (error_count[idx][state].bit);

      state = error_count[idx][state].last_state;
    }
  std::reverse (decoded_bits.begin(), decoded_bits.end());

  /* remove termination */
  assert (decoded_bits.size() >= order);
  decoded_bits.resize (decoded_bits.size() - order);

  return decoded_bits;
}

vector<int>
puncture (const vector<int>& bits, const vector<int>& puncture_pattern)
{
  vector<int> out_bits;

  for (size_t i = 0; i < bits.size(); i++)
    if (puncture_pattern[i])
      out_bits.push_back (bits[i]);

  // fprintf (stderr, "puncture: %zd => %zd\n", bits.size(), out_bits.size());
  return out_bits;
}

vector<float>
un_puncture (const vector<float>& bits, const vector<int>& puncture_pattern)
{
  vector<float> out_bits;
  size_t b = 0;
  for (size_t i = 0; i < puncture_pattern.size(); i++)
    {
      if (puncture_pattern[i])
        out_bits.push_back (bits[b++]);
      else
        out_bits.push_back (0.5);
    }
  return out_bits;
}

vector<int>
make_puncture_pattern()
{
  size_t coded_bits = conv_code_size (n_payload_bits);
  size_t bits_to_erase = coded_bits - 256;

  /* approximately equal distance between punctured bits */
  vector<int> puncture_pattern (coded_bits, 1);

  for (size_t i = 0; i < bits_to_erase; i++)
    puncture_pattern[int (coded_bits / double (bits_to_erase + 1) * (i + 1))] = 0;

  int keep_bits = 0;
  for (auto b : puncture_pattern)
    if (b)
     keep_bits++;

  assert (keep_bits == 256);

  return puncture_pattern;
}

void
convcode_test()
{
  vector<int> puncture_pattern = make_puncture_pattern();

  std::default_random_engine generator;

  for (double stddev = 0; stddev < 1; stddev += 0.01)
    {
      std::normal_distribution<double> dist (0, stddev);
      int good = 0;
      double stddev_est = 0;
      static constexpr int REPS = 100;

      for (int reps = 0; reps < REPS; reps++)
        {
          vector<int> in_bits;
          for (unsigned int i = 0; i < n_payload_bits; i++)
            in_bits.push_back (rand() & 1);

          vector<int> coded_bits = puncture (conv_encode (in_bits), puncture_pattern);

          vector<float> recv_bits;
          for (auto b : coded_bits)
            recv_bits.push_back (b + dist (generator));

          float error = 0;
          vector<int> decoded_bits1 = conv_decode_soft (un_puncture (recv_bits, puncture_pattern), puncture_pattern, &error);
          if (decoded_bits1 == in_bits)
            good++;
          stddev_est += error;
        }
      stddev_est = sqrt (stddev_est / REPS);
      printf ("%f %f %f\n", stddev, stddev_est, double (good) / REPS);
    }
}

void
convcode_check()
{
  // we do not randomly seed the PRNG here because there is no guarantee that
  // for truely random noise the decoder will always succeed
  std::mt19937 mt (42);
  const double stddev = 0.4;
  double stddev_est = 0;
  const int REPS = 10;
  for (int i = 0; i < REPS; i++)
    {
      vector<int> puncture_pattern = make_puncture_pattern();

      vector<int> in_bits;
      for (unsigned int i = 0; i < n_payload_bits; i++)
        in_bits.push_back (mt() & 1);

      vector<int> coded_bits = puncture (conv_encode (in_bits), puncture_pattern);

      vector<float> recv_bits;
      for (auto b : coded_bits)
        {
          // unfortunately std::normal_distribution will not generate the same values
          // on all platforms / c++ libraries, so we add up a few random [-1,1] values
          int x = 0, k = 8;
          for (int noise = 0; noise < k * k; noise++)
            {
              if (mt() & 1)
                x += 1;
              else
                x -= 1;
            }

          recv_bits.push_back (b + x * stddev / k);
        }

      float error = 0;
      vector<int> decoded_bits1 = conv_decode_soft (un_puncture (recv_bits, puncture_pattern), puncture_pattern, &error);
      assert (decoded_bits1 == in_bits);
      stddev_est += sqrt (error);

      // expected decoder error is the distance between the coded bits and the received bits
      double in_error = 0;
      for (size_t i = 0; i < coded_bits.size(); i++)
        in_error += pow ((coded_bits[i] - recv_bits[i]), 2);
      in_error /= coded_bits.size();
      assert (std::abs (in_error - error) < 1e-5);
    }
  stddev_est /= REPS;
  assert (std::abs (stddev - stddev_est) < 0.002);
}

std::vector<float>
read_stdin_bits ()
{
  vector<float> bits;
  char buffer[1024];
  while (fgets (buffer, 1024, stdin))
    {
      string c = strtok (buffer, " \n");
      if (c == "bit")
        {
          bits.push_back (atof (strtok (nullptr, " \n")));
        }
      else if (c == "end")
        {
          assert (!bits.empty());
          return bits;
        }
      else if (c == "stop")
        {
          assert (bits.empty());
          return bits;
        }
      else
        {
          fprintf (stderr, "convcode: unsupported input key %s\n", c.c_str());
          exit (1);
        }
    }
  fprintf (stderr, "convcode: unexpected end of input\n");
  exit (1);
}

std::vector<int>
convcode_encode (const std::vector<float> &bits)
{
  vector<int> puncture_pattern = make_puncture_pattern();
  assert (bits.size() == n_payload_bits);

  vector<int> ibits;
  for (auto b: bits)
    ibits.push_back (b > 0.5);

  return randomize_bit_order (puncture (conv_encode (ibits), puncture_pattern), true);
}

std::vector<int>
convcode_decode (const std::vector<float> &bits, double *normalized_error)
{
  vector<int> puncture_pattern = make_puncture_pattern();
  assert (bits.size() == 256);
  float error = 0;
  const std::vector<float> rbits = randomize_bit_order (bits, false);
  const std::vector<float> pbits = un_puncture (rbits, puncture_pattern);
  const std::vector<int> ibits = conv_decode_soft (pbits, puncture_pattern, &error);

  /* this is trial-and-error normalized:
   *  - sqrt (error) is the estimated stddev of the noise added to the signal
   *  - if stddev > 0.5, it is unlikely that we can error-correct the bits
   *    (although not impossible)
   */
  if (normalized_error)
    *normalized_error = sqrt (error) * 2;
  return ibits;
}
