// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
/** @file cornersync.cc

    The cornersync executable attempts to find the watermark under the assumption
    that the corners of the original and watermarked image match (no cropping
    was performed) and the aspect ratio was not changed.

    This means that cornersync can find the watermark if the original has
    been compressed with a lossy compression like jpeg, or if the image has
    been scaled while preserving the aspect ratio, or a combination of these
    and similar attacks.

    To find the watermark, the cornersync algorithm assumes that a watermark
    unit has been embedded exactly in the center of the image and the other
    units form a regular grid around this one central unit. It then performs
    two steps:

    First, different zoom levels are used for watermark detection and each
    of these zoom levels is rated with a score. By looking at a local maximum
    in the score function, the most likely zoom level can be computed.

    Then, different sub-pixel positions for the "true" center of the watermark
    are tested and rated with a score. By estimating the position of the
    local maximum of the position scores, we get a sub-pixel position that
    is close to the center and maximizes the score.

    Finally, the zoom level and the sub pixel position of the center of the
    watermark are returned to the python extract algorithm. It can build a
    grid from this information and decode the watermark.

    To compute the score function, cornersync uses the wmasked_up matrix
    (which depends on the key) and accumulates the 256 data bits over all
    units in the image. The bit mean is used to rate the quality of the match.

 */

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/highgui.hpp>
#include <opencv2/imgproc.hpp>
#include <iostream>
#include <sys/time.h>

using namespace cv;
using std::vector;
using std::string;
using std::array;

static constexpr int payload_dim = 16; /* 16 * 16 bits = 256 data bits */
static constexpr int Lr = 4;           /* dimension of the R matrix */
static constexpr int wmasked_zoom = 2;

/* get minimum and maximum value from matrix */
std::pair<float, float>
get_range (const Mat& mat)
{
  float mn = 0, mx = 0;
  if (mat.rows && mat.cols)
    mn = mx = mat.at<float> (0, 0);

  for (int i = 0; i < mat.rows; i++)
    for (int j = 0; j < mat.cols; j++)
      {
        float pixel = mat.at<float>(i,j);
        mx = max (mx, pixel);
        mn = min (mn, pixel);
      }
  return { mn, mx };
}

/* load matrix from stdin (usually from numpy array written by python) */
Mat
load (const char *name)
{
  std::vector<uint64_t> shape (2);
  if (fread (shape.data(), sizeof (uint64_t), 2, stdin) != 2)
    {
      fprintf (stderr, "cornersync: failed to read dimensions of %s matrix\n", name);
      exit (1);
    }

  Mat mat (shape[0], shape[1], CV_32F);
  for (int y = 0; y < mat.rows; y++)
    {
      float *row_ptr = mat.ptr<float> (y);
      if (fread (row_ptr, sizeof (float), mat.cols, stdin) != size_t (mat.cols))
        {
          fprintf (stderr, "cornersync: failed to read data of %s matrix\n", name);
          exit (1);
        }
    }
  return mat;
}

/* flip and/or rotate input matrix, return flipped/rotated matrix; orientation is 0..7 */
Mat
change_orientation (const Mat& in_mat, int orientation)
{
  Mat out_mat;
  out_mat.create (in_mat.size(), in_mat.type());

  for (int i = 0; i < in_mat.rows; i++)
    for (int j = 0; j < in_mat.cols; j++)
      {
        int ii = (orientation & 1) ? in_mat.rows - 1 - i : i; // flip x
        int jj = (orientation & 2) ? in_mat.cols - 1 - j : j; // flip y
        if (orientation & 4) // rotation 90 degree
          std::swap (ii, jj);

        out_mat.at<float> (ii, jj) = in_mat.at<float> (i, j);
      }
  return out_mat;
}

/* return timestamp in seconds as double */
double
get_time()
{
  timeval tv;
  gettimeofday (&tv, 0);

  return tv.tv_sec + tv.tv_usec / 1000000.0;
}

/* display normalized matrix, useful for debugging */
void
display (Mat& in_mat)
{
  Mat mat = in_mat.clone();

  float mn = 0, mx = 0;
  for(int i=0; i<mat.rows; i++)
    for(int j=0; j<mat.cols; j++)
      {
        float pixel = mat.at<float>(i,j);
        mx = max (mx, pixel);
        mn = min (mn, pixel);
      }

  for (int y = 0; y < mat.rows; y++)
    {
      float *f = mat.ptr<float> (y);
      for (int x = 0; x < mat.cols; x++)
        f[x] = std::clamp ((f[x] - mn) / (mx - mn), 0.f, 1.f);
    }
  imshow ("Display window", mat);
  waitKey(0); // Wait for a keystroke in the window
}

/*
 * accumulate pixel data from all units for a given zoom level and center_x, center_y
 *  - returns matrix the same size than wmasked_up, to be xored with wmasked_up to get real bit values
 *  - output matrix is not normalized (with the number of pixels used to produce each score),
 *    so normalization is necessary
 *
 * this function is the performance critical part of the code, so it needs to be as fast as possible
 */
void
accumulate_units (Mat& acc_units, const Mat& W_est, float zoom, float center_x, float center_y)
{
  const int acc_size = payload_dim * Lr * wmasked_zoom;
  acc_units = Mat::zeros (acc_size, acc_size, CV_32F);

  const int height = W_est.rows;
  const int width = W_est.cols;

  float dx = 1 / zoom;
  float dy = 1 / zoom;

  float source_y = 64 - center_y * dy;
  float source_x = 64 - center_x * dx;

  // translate input pixel coordinate to wmasked_up position including flipping
  auto to_dest_pixel = [] (float f) {
    f = fmod (f, 256);
    if (f < -0.5)
      f += 256;
    int px = std::clamp<int> (lrint (f), 0, 255);
    if (px <= 127)
      return px;
    else
      return 255 - px;
  };

  int xindex[width];
  for (int x = 0; x < width; x++)
    xindex[x] = to_dest_pixel (source_x + dx * x);

  for (int y = 0; y < height; y++)
    {
      const float *W_est_ptr = W_est.ptr<float> (y);
      float *acc_ptr = acc_units.ptr<float> (to_dest_pixel (source_y + dy * y));

      for (int x = 0; x < width; x++)
        acc_ptr[xindex[x]] += W_est_ptr[x];
    }
}

/* normal distribution with mean/std */
double
normal_distribution (double mean, double std, double x)
{
  auto square = [](double value) { return value * value; };

  return std::exp (-square (x - mean) / (2 * square (std))) / (std * sqrt (2 * M_PI));
}

/* compute kullback leibler divergence for two probability distributions P and Q */
double
distribution_divergence_kld (const vector<double>& P, const vector<double>& Q)
{
  assert (P.size() == Q.size());

  double kld = 0;
  for (size_t x = 0; x < P.size(); x++)
    {
      if (P[x] > 0)
        kld += P[x] * log2 (P[x] / Q[x]);
    }
  return kld;
}

/* compute jenson shannon distance between two probability distributions P and Q */
double
jensen_shannon_distance (const vector<double>& P, const vector<double>& Q)
{
  assert (P.size() == Q.size());

  vector<double> M;
  for (size_t x = 0; x < P.size(); x++)
    M.push_back (0.5 * (P[x] + Q[x]));

  return sqrt (0.5 * (distribution_divergence_kld (P, M) + distribution_divergence_kld (Q, M)));
}

/* mean subtracted contrast normalization on data bit blocks in matrix */
Mat
normalize_blocks_mscn (const Mat& mat)
{
  Mat norm_mat = mat.clone();

  const int block_size = wmasked_zoom * Lr;
  for (int by = 0; by < payload_dim; by++)
    {
      for (int bx = 0; bx < payload_dim; bx++)
        {
          /* compute block mean */
          float sum = 0;
          for (int y = 0; y < block_size; y++)
            for (int x = 0; x < block_size; x++)
              {
                sum += norm_mat.at<float> (by * block_size + y, bx * block_size + x);
              }
          float mean = sum / block_size / block_size;
          /* subtract block mean */
          for (int y = 0; y < block_size; y++)
            for (int x = 0; x < block_size; x++)
              {
                norm_mat.at<float> (by * block_size + y, bx * block_size + x) -= mean;
              }
          /* compute block sum of squares */
          float sum_squares = 0;
          for (int y = 0; y < block_size; y++)
            for (int x = 0; x < block_size; x++)
              {
                float value = norm_mat.at<float> (by * block_size + y, bx * block_size + x);
                sum_squares += value * value;
              }
          /* normalize block variance/std to 1 */
          float var = sum_squares / block_size / block_size;
          float std = sqrt (var);
          for (int y = 0; y < block_size; y++)
            for (int x = 0; x < block_size; x++)
              norm_mat.at<float> (by * block_size + y, bx * block_size + x) /= std;
        }
    }
  return norm_mat;
}

/* write matrix as image to filename (for debugging) */
void
dump_matrix (const Mat& mat, const string& filename)
{
  auto [ mn, mx ] = get_range (mat);

  Mat norm_mat = mat.clone();
  for (int y = 0; y < mat.rows; y++)
    {
      for (int x = 0; x < mat.cols; x++)
        {
          norm_mat.at<float> (y, x) = (mat.at<float> (y, x) - mn) / (mx - mn);
        }
    }
  imwrite (filename, norm_mat);
}

enum class SyncScore {
  JSD,      // jensen shannon distance
  BIT_MEAN  // mean value of the decoded bits
};

/*
 * compute sync score from accumulated units (either JSD or BIT_MEAN), higher values are better
 */
float
compute_sync_score (const Mat& acc_units, const Mat& wmasked_up, int orientation, SyncScore sync_score)
{
  vector<float> bit_sum (16 * 16);
  Mat wmasked_up_flipped = change_orientation (wmasked_up, orientation);
  Mat norm_units = normalize_blocks_mscn (acc_units);

  // extract 256 data bits
  for (int y = 0; y < 128; y++)
    {
      for (int x = 0; x < 128; x++)
        {
          bit_sum[y / 8 * 16 + x / 8] += wmasked_up_flipped.at<float> (y, x) * norm_units.at<float> (y, x) / Lr / wmasked_zoom;
        }
    }
  if (sync_score == SyncScore::BIT_MEAN)
    {
      // just use the average bit level
      float total = 0;
      for (auto x : bit_sum)
        total += std::abs (x);
      return total / bit_sum.size();
    }
  else
    {
      // use jsd as sync score
      vector<double> histogram (207);
      vector<double> normal_histogram (207);
      vector<double> hist_center (histogram.size());
      for (size_t i = 0; i < hist_center.size(); i++)
        {
          hist_center[i] = (double (i) - hist_center.size() / 2) / double (hist_center.size() / 2) * 14;
          normal_histogram[i] = normal_distribution (0, 1, hist_center[i]);
        }
      for (auto x : bit_sum)
        {
          size_t best_i = 0;
          float  best_diff = 1e9;
          for (size_t i = 0; i < histogram.size(); i++)
            {
              float diff = std::abs (hist_center[i] - x);
              if (diff < best_diff)
                {
                  best_diff = diff;
                  best_i = i;
                }
            }
          histogram[best_i]++;
        }
      auto normalize_histogram = [](auto& histogram) {
        double value_sum = 0;
        for (auto value : histogram)
          value_sum += value;
        for (auto& value : histogram)
          value /= value_sum;
      };
      normalize_histogram (histogram);
      normalize_histogram (normal_histogram);
      return jensen_shannon_distance (histogram, normal_histogram);
    }
}

/* von Hann window */
inline double
window_cos (double x)
{
  if (fabs (x) > 1)
    return 0;
  return 0.5 * cos (x * M_PI) + 0.5;
}

struct ZoomScore
{
  float units = 0;
  float score = 0;
};

/*
 * The scores from zoom search are usually a bit noisy, so the local maximum
 * from the zoom score vector is not necessarily the best choice.
 *
 * To get rid of the noise to some degree, this function smoothes the scores
 * using a cosine window and then finds the local maximum of this smooth
 * function.
 */
static ZoomScore
zoom_score_smooth_find_best (const vector<ZoomScore>& scores, double distance)
{
  ZoomScore best_score;

  for (double units = scores.front().units; units < scores.back().units; units += 0.0001)
    {
      double score_sum = 0;
      double score_div = 0;

      for (auto s : scores)
        {
          double w = window_cos ((s.units - units) / distance);

          score_sum += s.score * w;
          score_div += w;
        }
      score_sum /= score_div;
      if (score_sum > best_score.score)
        {
          best_score.units = units;
          best_score.score = score_sum;
        }
    }

  return best_score;
}

/*
 * find best zoom level, assuming that the watermark has been embedded so that one unit is
 * exactly centered around center_x and center_y
 */
std::tuple<float, int>
find_best_zoom (const Mat& W_est, const Mat& wmasked_up, float center_x, float center_y, bool verbose)
{
  /* usually we use a dynamiczoom of 8, so that the image contains 8 units in the smaller dimension
   * for small images, the dynamczoom is effectively less, so for this implementation we assume that
   * the image was large enough to contain at least 2 units in the smaller dimension
   *
   * 2 units with min_zoom=1.5 and unit size=64 == 192 pixels in the smaller dimension
   */
  double min_units = 2, max_units = 8;
  double unit_stepping = 0.01;

  float best_sync_score = 0;
  int best_orientation = 0;
  float avg_sync_score = 0;
  float avg_sync_score_n = 0;

  // try different zoom levels and orientations
  Mat acc_units;
  array<vector<ZoomScore>, 8> zoom_scores;
  for (double units = min_units - unit_stepping * 15; units < max_units + unit_stepping * 15; units += unit_stepping)
    {
      float zoom = std::min (W_est.rows, W_est.cols) / 128. / units;

      accumulate_units (acc_units, W_est, zoom, center_x, center_y);
      for (int orientation = 0; orientation < 8; orientation++)
        {
          ZoomScore zscore;
          zscore.score = compute_sync_score (acc_units, wmasked_up, orientation, SyncScore::BIT_MEAN);
          zscore.units = units;
          zoom_scores[orientation].push_back (zscore);
          avg_sync_score += zscore.score;
          avg_sync_score_n++;
        }
    }

  // use zoom smoothing to improve robustness and find best zoom
  double best_units = 0;
  const float smoothing_distance = 0.06;
  for (size_t orientation = 0; orientation < zoom_scores.size(); orientation++)
    {
      ZoomScore zscore = zoom_score_smooth_find_best (zoom_scores[orientation], smoothing_distance);
      if (zscore.score > best_sync_score)
        {
          best_sync_score  = zscore.score;
          best_units       = zscore.units;
          best_orientation = orientation;
        }
    }

  float best_zoom = std::min (W_est.rows, W_est.cols) / 128. / best_units;
  avg_sync_score /= avg_sync_score_n;
  if (verbose)
    fprintf (stderr, "cornersync: best_zoom=%f, best_orientation=%d, best_sync_score=%f, avg_sync_score=%f\n",
             best_zoom * 2, best_orientation, best_sync_score, avg_sync_score);
  return std::make_tuple (best_zoom, best_orientation);
}

/*
 * find best subpixel offset around the center according to score function
 */
std::tuple<float, float>
find_subpixel_center_offset (const Mat& W_est, const Mat& wmasked_up, float best_zoom, int best_orientation, float center_x, float center_y)
{
  Mat acc_units;
  /* evaluate score function using a regular grid to find maximum using (dx, dy) */
  int range = 5;
  int samples = 21;
  Mat ss = Mat::zeros (samples, samples, CV_32F);
  for (int idy = 0; idy < samples; idy++)
    for (int idx = 0; idx < samples; idx++)
      {
        auto scale_to_range = [&](int i) {return (i - (samples - 1) * 0.5) / ((samples - 1) * 0.5) * range; };
        float dx = scale_to_range (idx);
        float dy = scale_to_range (idy);
        accumulate_units (acc_units, W_est, best_zoom, center_x + dx, center_y + dy);

        ss.at<float> (idy, idx) = compute_sync_score (acc_units, wmasked_up, best_orientation, SyncScore::BIT_MEAN);
      }

  /* upsample score function values */
  int scaled_samples = 201;
  Mat ss_up;
  resize (ss, ss_up, Size (scaled_samples, scaled_samples), INTER_CUBIC);

  /* blur: this removes noise and low pass filters the upsampled score function */
  int blur = 41;
  GaussianBlur (ss_up, ss_up, Size (scaled_samples, scaled_samples), blur, blur, BORDER_REPLICATE);
  float best_sync_score = 0;

  float best_dx = 0, best_dy = 0;
  for (int idy = 0; idy < scaled_samples; idy++)
    for (int idx = 0; idx < scaled_samples; idx++)
      {
        auto scale_to_range = [&](int i) {return (i - (scaled_samples - 1) * 0.5) / ((scaled_samples - 1) * 0.5) * range; };
        float dx = scale_to_range (idx);
        float dy = scale_to_range (idy);
        float score = ss_up.at<float> (idy, idx);
        if (score > best_sync_score)
          {
            best_sync_score = score;
            best_dx = dx;
            best_dy = dy;
          }
      }
  return std::make_tuple (best_dx, best_dy);
}

int
main (int argc, char **argv)
{
  double start_time = get_time();

  bool verbose = (argc == 2) && (strcmp (argv[1], "verbose") == 0);

  // load input from stdin
  const Mat W_est      = load ("W_est");
  const Mat wmasked_up = load ("wmasked_up");

  const int height = W_est.rows;
  const int width = W_est.cols;
  if (verbose)
    fprintf (stderr, "cornersync: width = %d, height = %d\n", width, height);

  float center_x = width * 0.5;
  float center_y = height * 0.5;

  // find best zoom level
  auto [ best_zoom, best_orientation ] = find_best_zoom (W_est, wmasked_up, center_x, center_y, verbose);

  // find best subpixel offset
  auto [ best_dx, best_dy ] = find_subpixel_center_offset (W_est, wmasked_up, best_zoom, best_orientation, center_x, center_y);

  /* there is a difference between our coordinate system we use to compute
   * synchronization and the python extraction algorithm, so we need to
   * compensate for this here
   */
  center_x -= 0.5 * best_zoom;
  center_y -= 0.5 * best_zoom;

  if (verbose)
    {
      // print verbose information for user
      Mat acc_units;
      accumulate_units (acc_units, W_est, best_zoom, center_x + best_dx, center_y + best_dy);
      double jsd = compute_sync_score (acc_units, wmasked_up, best_orientation, SyncScore::JSD);
      fprintf (stderr, "cornersync: time %f, best_dx=%f best_dy=%f jsd=%f\n", get_time() - start_time, best_dx, best_dy, jsd);
    }

  // pass results to python
  printf ("corner_sync %f %f %f\n", best_zoom * 2, center_x + best_dx, center_y + best_dy);
  return 0;
}
