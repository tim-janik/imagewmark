// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
/** @file peaks2grid.cc

    The peaks2grid executable takes a list of peak coordinates extracted from
    an image as input and attempts to match the spikes to a grid like
    structure.
    For each peak the relative and normalized height is passed as input to
    peaks2grid, which selects a subset of all peaks based on their height
    before performing grid detection.

    Potential grids are sorted by regularity. For each regularity level, a list
    of grids is printed on stdout, before the search continues at decreasing
    regularities.
    This allows parallel processing of grids at higher regularities, which may
    help to produce early detection results, because searching grids at smaller
    regularities involves more computation time.

    Regularity is guaranteed to decrease with each new grid list produced by
    peaks2grid, however quality scores may increase.
    The grids within a list are sorted by score, with highest scores at the
    start of the list.
    The score is based on the height of the grid peaks and the size of the grid.
    A larger grid indicates higher confidence in correct detection.

    Each grid contains a number of scores and a list of rectangles. The pixel
    rectangle coordinates of each unit within a grid use the same relative
    order of rectangle corners.
    The scores for each grid are as follows:
    - 'qscore': indicator for how close the rectangle angles are to 90°
    - 'min_edge': indicator for the size of detected units
    - 'mmax_score': this indicator increases if the units more similar to a
      square than a rectangle
    - 'axis_score': indicator for units being parallel to an axis and distance
      from 45° rotation
    - 'regularity': sum of the 'axis_score', 'qscore', 'mmax_score' if a score
      exceeds 98%

    Each unit within a grid contains 5 coordinate pairs. The first pair
    corresponds to the unit position within a grid.
    The next 4 coordinates represent the 4 corners of a rectangle.
 */

#include <vector>
#include <string>
#include <algorithm>
#include <random>

#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <cassert>

#include <poll.h>

#include "minsearch.hh"

#ifdef HAVE_OPENCV
#include <opencv2/imgproc.hpp>
#endif

using std::string;
using std::vector;
using std::sort;
using std::min;
using std::max;

struct Peak {
  int       x = 0;
  int       y = 0;
  double    height = 0;
  double    raw_height = 0;
  uint64_t  random_id = 0;
};

vector<Peak> peaks;

class PeakIndex
{
  vector<int> index_;
  int width_;
  int height_;

  void
  set (int x, int y, int value)
  {
    if (x < 0 || y < 0 || x >= width_ || y >= height_)
      return;

    index_[y * width_ + x] = value;
  }
public:
  int
  get (int x, int y) const
  {
    if (x < 0 || y < 0 || x >= width_ || y >= height_)
      return -1;

    return index_[y * width_ + x];
  }

  PeakIndex (int width, int height, const vector<Peak>& peaks) :
    index_ (width * height, -1),
    width_ (width),
    height_ (height)
  {
    for (size_t i = 0; i < peaks.size(); i++)
      {
        for (int dx = -10; dx <= 10; dx++)
          {
            for (int dy = -10; dy <= 10; dy++)
              {
                int dist = std::abs (dx) + std::abs (dy);
                if (dist < 10)
                  {
                    int x = peaks[i].x + dx;
                    int y = peaks[i].y + dy;

                    int idx = get (x, y);
                    if (idx >= 0)
                      {
                        /* replace peak if we're closer */
                        const Peak& q = peaks[idx];

                        int qdist = std::abs (q.x - x) + std::abs (q.y - y);
                        if (dist < qdist)
                          set (x, y, i);
                      }
                    else
                      {
                        /* enter new peak into index */
                        set (x, y, i);
                      }
                  }
              }
          }
      }
  }
};

// Calculate angle between (a,b) and (a,c)
double
p3angle (Peak b, Peak a, Peak c)
{
  double t_angle = atan2 (c.y - a.y, c.x - a.x) - atan2 (b.y - a.y, b.x - a.x);

  // normalized degrees from radians
  double d = t_angle * 180 / M_PI;

  while (d < -180)
    d += 360;

  while (d > +180)
    d -= 360;
  return d;
}

struct GridUnit
{
  int gx = 0;
  int gy = 0;
  int ai = 0;
  int bi = 0;
  int ci = 0;
  int vi = 0;
};

struct Grid
{
  vector<GridUnit> units;
  uint64_t hash = 0;
  double   score = 0;
  double   axis_score = 0;
  double   qscore = 0;
  double   mmax_score = 0;
  double   min_edge = 0;
  uint     regular_grid = 0;
};

static constexpr int GRID_MAX_DIST = 30;
static constexpr int GRID_RANGE = GRID_MAX_DIST / 2;

double
grid_score (const Grid& grid)
{
  double score = 0;
  for (const auto& unit : grid.units)
    {
      score += peaks[unit.ai].height;
      score += peaks[unit.bi].height;
      score += peaks[unit.ci].height;
      score += peaks[unit.vi].height;
    }
  return score;
}

uint64_t
grid_hash (const Grid& grid)
{
  uint64_t hash = 0;
  for (const auto& unit : grid.units)
    {
      hash += peaks[unit.ai].random_id;
      hash += peaks[unit.bi].random_id;
      hash += peaks[unit.ci].random_id;
      hash += peaks[unit.vi].random_id;
    }
  return hash;
}

// [0,1] normalized score: 1.0 if peaks a and b are parallel to x or y axis
double
axis_score_peaks (const Peak& a, const Peak& b)
{
  Peak c = b;
  c.x += 100;
  double angle = p3angle (a, b, c);

  double min_angle_diff = 90;
  for (auto axis_angle : { -180, -90, 0, 90, 180 })
    min_angle_diff = min (min_angle_diff, std::abs (axis_angle - angle));

  return 1 - min_angle_diff / 45.;
}

// [0,1] normalized score: 1.0 if both grid unit sides are parallel to x or y axis
double
axis_score_peaks (const Peak& a, const Peak& b, const Peak& c)
{
  return min (axis_score_peaks (a, b), axis_score_peaks (a, c));
}

Grid
build_grid (const PeakIndex& peak_index, Peak a, Peak b, Peak c, Peak v)
{
  auto closest = [&] (Peak &p) { return peak_index.get (p.x, p.y); };

  Grid grid;

  grid.units.push_back ({ 0, 0, closest (a), closest (b), closest (c), closest (v) });
  assert (grid.units[0].ai >= 0 && grid.units[0].bi >= 0 && grid.units[0].ci >= 0 && grid.units[0].vi >= 0);

  struct GridPos
  {
    int gx;
    int gy;
  };
  static vector<GridPos> grid_positions; // build this once and then keep it
  if (grid_positions.empty())
    {
      /* grid search order: increasing distance from the center */
      for (int distance = 1; distance <= GRID_MAX_DIST; distance++)
        {
          for (int gx = -GRID_RANGE; gx <= GRID_RANGE; gx++)
            {
              for (int gy = -GRID_RANGE; gy <= GRID_RANGE; gy++)
                {
                  if (distance == std::abs (gx) + std::abs (gy))
                    {
                      GridPos gp;
                      gp.gx = gx;
                      gp.gy = gy;
                      grid_positions.push_back (gp);
                    }
                }
            }
        }
    }
  for (auto grid_pos : grid_positions)
    {
      int gx = grid_pos.gx;
      int gy = grid_pos.gy;

      /* we need to find a unit that is as close to this one as possible */
      auto unit_distance = [gx, gy] (const GridUnit& u) {
        return std::abs (u.gx - gx) + std::abs (u.gy - gy);
      };
      auto it = std::min_element (grid.units.begin(), grid.units.end(),
                                  [&] (const auto& u1, const auto& u2) { return unit_distance (u1) < unit_distance (u2); });

      const auto& nearby_unit = *it;

      /* compute new unit points from nearby unit */
      int dx = (b.x - a.x) * (gx - nearby_unit.gx) + (c.x - a.x) * (gy - nearby_unit.gy);
      int dy = (b.y - a.y) * (gx - nearby_unit.gx) + (c.y - a.y) * (gy - nearby_unit.gy);

      auto closest_unit_point = [&] (int idx)
        {
          Peak p = peaks[idx];
          p.x += dx;
          p.y += dy;
          return closest (p);
        };

      int ai = closest_unit_point (nearby_unit.ai);
      if (ai >= 0)
        {
          int bi = closest_unit_point (nearby_unit.bi);
          if (bi >= 0)
            {
              int ci = closest_unit_point (nearby_unit.ci);
              if (ci >= 0)
                {
                  int vi = closest_unit_point (nearby_unit.vi);
                  if (vi >= 0)
                    {
                      /* insert if all points correspond to valid peaks */
                      grid.units.push_back ({ gx, gy, ai, bi, ci, vi });
                    }
                }
            }
        }
    }
  grid.hash = grid_hash (grid);
  grid.score = grid_score (grid);
  return grid;
}

vector<vector<int>>
grid_norm (const Grid& grid)
{
  vector<vector<int>> sorted_grid_points;

  for (const auto& gu : grid.units)
    {
      vector<int> points { gu.ai, gu.bi, gu.ci, gu.vi };

      sort (points.begin(), points.end());
      sorted_grid_points.push_back (points);
    }

  sort (sorted_grid_points.begin(), sorted_grid_points.end());
  return sorted_grid_points;
}

bool
grid_equal (const Grid& grid1, const Grid& grid2)
{
  return grid1.hash == grid2.hash && grid_norm (grid1) == grid_norm (grid2);
}

void
insert_grid (vector<Grid>& best_grids, const Grid& grid)
{
  /* already have this? */
  for (const auto& bg : best_grids)
    if (grid_equal (grid, bg))
      return;

  best_grids.push_back (grid);
  sort (best_grids.begin(), best_grids.end(),
        [] (auto &g1, auto &g2) { return g1.score > g2.score; });

  if (best_grids.size() > 5)
    best_grids.resize (5);
}

/*
 * 1. Optimize grid to best fit all grid unit peaks with subpixel resolution
 * 2. Extend grid all over the image so that when extracting the watermark
 *    all pixels are used
 */
class GridModel
{
public:
  struct GridPeak
  {
    int gx;
    int gy;
    int px;
    int py;
  };
  struct Vec2d
  {
    double x;
    double y;
  };
};

class AffineGridModel : public GridModel
{
  Vec2d
  grid_pos_for_vec (const vector<double>& vec, int gx, int gy)
  {
    double ax = vec[0];
    double ay = vec[1];
    double abx = vec[2];
    double aby = vec[3];
    double acx = vec[4];
    double acy = vec[5];
    return Vec2d ({ax + gx * abx + gy * acx, ay + gx * aby + gy * acy});
  }

  vector<double> vec; // actual model : A, AB, AC
public:
  AffineGridModel (const GridUnit& root_unit, int width, int height)
  {
    // A
    vec.push_back (peaks[root_unit.ai].x);
    vec.push_back (peaks[root_unit.ai].y);
    // AB
    vec.push_back (peaks[root_unit.bi].x - peaks[root_unit.ai].x);
    vec.push_back (peaks[root_unit.bi].y - peaks[root_unit.ai].y);
    // AC
    vec.push_back (peaks[root_unit.ci].x - peaks[root_unit.ai].x);
    vec.push_back (peaks[root_unit.ci].y - peaks[root_unit.ai].y);
  }

  void
  minimize_error (const vector<GridPeak>& grid_peaks)
  {
    auto score_func = [&] (const vector<double>& new_vec) {
      double s = 0;
      for (const auto &peak : grid_peaks)
        {
          auto v2 = grid_pos_for_vec (new_vec, peak.gx, peak.gy);

          double dx = v2.x - peak.px;
          double dy = v2.y - peak.py;

          s += dx * dx + dy * dy;
        }
      return s;
    };
    MinSearch::minimize (vec, score_func);
  }

  Vec2d
  grid_pos (int gx, int gy)
  {
    return grid_pos_for_vec (vec, gx, gy);
  }
};

class PerspectiveGridModel : public GridModel
{
  vector<double>
  matrix_for_vec (const vector<double>& vec)
  {
#if HAVE_OPENCV
    vector<cv::Point2f> grid_coords {
      { 0, 0 },
      { 1, 0 },
      { 0, 1 },
      { 1, 1 }
    };

    vector<cv::Point2f> root_unit_pixels;
    for (int i = 0; i < 4; i++)
      root_unit_pixels.push_back (cv::Point2f (vec[i * 2], vec[i * 2 + 1]));

    auto mat = cv::getPerspectiveTransform (grid_coords, root_unit_pixels);

    vector<double> matrix {
      mat.at<double> (0, 0), mat.at<double> (0, 1), mat.at<double> (0,2),
      mat.at<double> (1, 0), mat.at<double> (1, 1), mat.at<double> (1,2),
      mat.at<double> (2, 0), mat.at<double> (2, 1)
    };
    return matrix;
#else
    fprintf (stderr, "peaks2grid: need opencv support to build perspective grids\n");
    exit (1);
#endif
  }

  Vec2d
  grid_pos_for_matrix (const vector<double>& matrix, int gx, int gy)
  {
    double tx = matrix[0] * gx + matrix[1] * gy + matrix[2];
    double ty = matrix[3] * gx + matrix[4] * gy + matrix[5];
    double t  = matrix[6] * gx + matrix[7] * gy + 1;

    return { tx / t, ty / t };
  };

  vector<double> vec; // actual model : coordinates of A, B, C, V
  int            max_dimension;
public:
  PerspectiveGridModel (const GridUnit& root_unit, int width, int height)
  {
    vec.push_back (peaks[root_unit.ai].x);
    vec.push_back (peaks[root_unit.ai].y);
    vec.push_back (peaks[root_unit.bi].x);
    vec.push_back (peaks[root_unit.bi].y);
    vec.push_back (peaks[root_unit.ci].x);
    vec.push_back (peaks[root_unit.ci].y);
    vec.push_back (peaks[root_unit.vi].x);
    vec.push_back (peaks[root_unit.vi].y);

    max_dimension = max (width, height);
  }

  void
  minimize_error (const vector<GridPeak>& grid_peaks)
  {
    auto score_func = [&] (const vector<double>& new_vec) {
      double s = 0;
      vector<double> new_matrix = matrix_for_vec (new_vec);

      for (const auto &peak : grid_peaks)
        {
          auto v2 = grid_pos_for_matrix (new_matrix, peak.gx, peak.gy);

          double dx = v2.x - peak.px;
          double dy = v2.y - peak.py;

          s += dx * dx + dy * dy;
        }
      return s;
    };

    /* minimize needs to numerically compute the derivative, but opencv
     * perspective transform uses float (not double) for its computation, so we
     * need to adjust the h for the numerical derivative to a higher value
     */
    double h = max_dimension / 1e6;

    MinSearch::minimize (vec, score_func, "", h);
  }

  Vec2d
  grid_pos (int gx, int gy)
  {
    return grid_pos_for_matrix (matrix_for_vec (vec), gx, gy);
  }
};

template<class Model> void
build_optimal_global_grid (const Grid& grid, int width, int height)
{
  Model model (grid.units[0], width, height);

  vector<GridModel::GridPeak> grid_peaks;
  for (const auto &unit : grid.units)
    {
      grid_peaks.push_back ({ unit.gx, unit.gy,         peaks[unit.ai].x, peaks[unit.ai].y });
      grid_peaks.push_back ({ unit.gx + 1, unit.gy,     peaks[unit.bi].x, peaks[unit.bi].y });
      grid_peaks.push_back ({ unit.gx, unit.gy + 1,     peaks[unit.ci].x, peaks[unit.ci].y });
      grid_peaks.push_back ({ unit.gx + 1, unit.gy + 1, peaks[unit.vi].x, peaks[unit.vi].y });
    }

  model.minimize_error (grid_peaks);

  for (int gx = -GRID_RANGE; gx <= GRID_RANGE; gx++)
    {
      for (int gy = -GRID_RANGE; gy <= GRID_RANGE; gy++)
        {
          auto va = model.grid_pos (gx, gy);
          auto vb = model.grid_pos (gx + 1, gy);
          auto vc = model.grid_pos (gx, gy + 1);
          auto vv = model.grid_pos (gx + 1, gy + 1);

          auto in_range = [&] (GridModel::Vec2d v) {
            return v.x >= 0 && v.y >= 0 && v.x < width && v.y < height;
          };

          if (in_range (va) || in_range (vb) || in_range (vv) || in_range (vc))
            {
              printf ("unit %d %d %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f\n", gx, gy,
                    va.x, va.y, vb.x, vb.y, vv.x, vv.y, vc.x, vc.y);
            }
        }
    }
}

void
dump_grid_features (const Grid& grid, int virtual_grid)
{
  printf ("feature score %.8f\n", grid.score);
  printf ("feature axis_score %.8f\n", grid.axis_score);
  printf ("feature qscore %.8f\n", grid.qscore);
  printf ("feature mmax_score %.8f\n", grid.mmax_score);
  printf ("feature min_edge %.8f\n", grid.min_edge);
  printf ("feature regularity %d\n", grid.regular_grid);
  printf ("feature virtual %d\n", virtual_grid);
}

void
pick_peaks (vector<Peak>& peaks, int normalized_peak_count, int raw_peak_count)
{
  vector<Peak> selected_peaks;

  /* helper: picks one peak from peaks and inserts it into selected peaks by score function */
  auto pick_peak = [&] (const auto& score_func)
    {
      auto it = std::max_element (peaks.begin(), peaks.end(), [&] (const Peak& p1, const Peak& p2) { return score_func (p1) < score_func (p2); });
      if (it != peaks.end())
        {
          selected_peaks.push_back (*it);
          peaks.erase (it);
        }
    };
  while (normalized_peak_count || raw_peak_count)
    {
      if (normalized_peak_count)
        {
          /* pick peak which has the best height */
          pick_peak ([] (const Peak& p) { return p.height; });
          normalized_peak_count--;
        }
      if (raw_peak_count)
        {
          /* pick peak which has the best raw height */
          pick_peak ([] (const Peak& p) { return p.raw_height; });
          raw_peak_count--;
        }
    }
  peaks = selected_peaks;
}

bool
read_stop()
{
  pollfd pfd;
  pfd.fd = 0;
  pfd.events = POLLIN;
  int ready = poll (&pfd, 1, 0);
  if (ready == 1)
    {
      if (pfd.revents & POLLIN)
        {
          char buffer[1024];
          while (fgets (buffer, 1024, stdin))
            {
              string c = strtok (buffer, " \n");
              assert (c == "stop");
              return true;
            }
        }
    }
  return false;
}

int
main()
{
  int width = 0;
  int height = 0;
  int perspective = 0;
  int norm_peak_count = 0;
  int raw_peak_count = 0;
  float min_edge_bound = 0;
  std::mt19937_64 random_gen;

  char buffer[1024];
  while (fgets (buffer, 1024, stdin))
    {
      string c = strtok (buffer, " \n");
      if (c == "size")
        {
          width = atoi (strtok (nullptr, " \n"));
          height = atoi (strtok (nullptr, " \n"));
        }
      else if (c == "peak")
        {
          Peak p;
          p.x = atoi (strtok (nullptr, " \n"));
          p.y = atoi (strtok (nullptr, " \n"));
          p.height = atof (strtok (nullptr, " \n"));
          p.raw_height = atof (strtok (nullptr, " \n"));
          p.random_id = random_gen();
          peaks.push_back (p);
        }
      else if (c == "peak_count")
        {
          norm_peak_count = atoi (strtok (nullptr, " \n"));
          raw_peak_count = atoi (strtok (nullptr, " \n"));
        }
      else if (c == "min_edge_bound")
        {
          min_edge_bound = atof (strtok (nullptr, " \n"));
        }
      else if (c == "perspective")
        {
          perspective = atoi (strtok (nullptr, " \n"));
        }
      else if (c == "start")
        {
          /* start processing now */
          break;
        }
      else
        {
          fprintf (stderr, "peaks2grid: unsupported input key %s\n", c.c_str());
          exit (1);
        }
    }
  pick_peaks (peaks, norm_peak_count, raw_peak_count);
  for (auto p : peaks)
    printf ("peak %d %d %f\n", p.x, p.y, p.height);
  printf ("end_peaks\n");
  fflush (stdout);

  vector<Peak> center_peaks;
  for (const auto &p : peaks)
    {
      auto center_dist = [&] (Peak p) {
        double xx = p.x / double (width) - 0.5;
        double yy = p.y / double (height) - 0.5;

        return max (std::abs (xx), std::abs (yy));
      };

      if (center_dist (p) < 0.4)
        center_peaks.push_back (p);
    }

  PeakIndex peak_index (width, height, peaks);
  PeakIndex center_peak_index (width, height, center_peaks);

  int grid_count = 0;
  for (int search_regular_grid = 3; search_regular_grid >= 0; search_regular_grid--)
    {
      vector<Grid> grids;

      for (size_t i = 0; i < center_peaks.size(); i++)
        {
          /* check if parent process wants us to generate more grids */
          if (read_stop())
            return 0;

          for (size_t j = i + 1; j < center_peaks.size(); j++)
            for (size_t k = j + 1; k < center_peaks.size(); k++)
              {
                const auto &pa = center_peaks[i];
                const auto &pb = center_peaks[j];
                const auto &pc = center_peaks[k];

                int lx = pb.x + (pc.x - pa.x);
                int ly = pb.y + (pc.y - pa.y);
                int l = center_peak_index.get (lx, ly);
                if (l >= 0)
                  {
                    /*
                     *   a --- b
                     *   |     |
                     *   |     |
                     *   c --- v
                     */
                    const auto &pv = center_peaks[l];

                    if (size_t (l) != i && size_t (l) != j && size_t (l) != k)
                      {
                        double a1 = std::abs (p3angle (pa, pb, pv));
                        double a2 = std::abs (p3angle (pb, pv, pc));

                        // how quadratic is the unit? [0..1]
                        double qscore = 1 - max (a1 - 90, a2 - 90) / 90;

                        // length of the smallest edge
                        auto dist = [] (auto p, auto q) {
                          int dx = p.x - q.x;
                          int dy = p.y - q.y;
                          return sqrt (dx * dx + dy * dy);
                        };
                        double min_edge = min ({ dist (pa, pb), dist (pb, pv), dist (pv, pc), dist (pc, pa) });
                        double max_edge = max ({ dist (pa, pb), dist (pb, pv), dist (pv, pc), dist (pc, pa) });

                        double mmax_score = min_edge / max_edge;
                        double axis_score = axis_score_peaks (pa, pb, pc);

                        if (qscore > 0.1 && min_edge >= min_edge_bound)
                          {
                            int regular_grid = 0;
                            if (qscore > 0.98)
                              regular_grid++;
                            if (mmax_score > 0.98)
                              regular_grid++;
                            if (axis_score > 0.98)
                              regular_grid++;

                            if (search_regular_grid == regular_grid)  // search regular grids first to improve search performance
                              {
                                auto grid = build_grid (peak_index, pa, pb, pc, pv);

                                grid.axis_score = axis_score;
                                grid.qscore = qscore;
                                grid.mmax_score = mmax_score;
                                grid.min_edge = min_edge;
                                grid.regular_grid = regular_grid;

                                insert_grid (grids, grid);
                              }
                          }
                      }
                  }
              }
        }

      for (const auto& grid : grids)
        {
          /* check if parent process wants us to generate more grids */
          if (read_stop())
            return 0;

          printf ("start_grid %d\n", ++grid_count);
          for (const auto& unit : grid.units)
            {
              auto ga = peaks[unit.ai];
              auto gb = peaks[unit.bi];
              auto gc = peaks[unit.ci];
              auto gv = peaks[unit.vi];

              printf ("unit %d %d %d %d %d %d %d %d %d %d\n", unit.gx, unit.gy, ga.x, ga.y, gb.x, gb.y, gv.x, gv.y, gc.x, gc.y);
            }
          dump_grid_features (grid, /* virtual */ 0);
          printf ("end_grid\n");

          printf ("start_grid %d\n", ++grid_count);
          build_optimal_global_grid<AffineGridModel> (grid, width, height);
          dump_grid_features (grid, /* virtual */ 1);
          printf ("end_grid\n");

          if (perspective)
            {
              printf ("start_grid %d\n", ++grid_count);
              build_optimal_global_grid<PerspectiveGridModel> (grid, width, height);
              dump_grid_features (grid, /* virtual, perspective */ 2);
              printf ("end_grid\n");
            }
        }
      printf ("end_grids\n");
      fflush (stdout);
    }
}
