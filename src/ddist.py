#!/usr/bin/env python3
# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
import numpy as np
import scipy
import scipy.special, scipy.spatial
import matplotlib.pyplot as plt
from config import vprint, dprint

# calculate histogram bin heights for a 𝓝 (0,1) gauss distribution
def gauss_bins (mean, var, bins):
  # from https://numpy.org/doc/stable/reference/random/generated/numpy.random.normal.html
  # return 1 / (var * np.sqrt (2 * np.pi)) * np.exp (-(bins - mean)**2 / (2 * var**2))
  return np.exp (-(bins - mean)**2 / (2 * var**2)) / (var * np.sqrt (2 * np.pi))

# show distribution histogram
def plot_std_histogram (dist):
  mean = np.mean (dist)
  var  = np.std (dist, ddof = 0)
  count, bins, ignored = plt.hist (dist, 30, density = True)
  plt.plot (bins, gauss_bins (mean, var, bins), linewidth = 2, color = 'r')
  # from https://numpy.org/doc/stable/reference/random/generated/numpy.random.normal.html
  plt.show()

# calculate similarity measure between distributions
def distribution_divergence (d1, d2 = None):
  buckets, limit = 207, 14    # total buckets covering ±limit, e.g. [-4 -2.4 -0.8 +0.8 +2.4 +4]
  edges = limit / (buckets / 2) * (np.array (list (range (-buckets//2, (buckets + 1)//2))) + 0.5)
  bins1, edges1 = np.histogram (d1, edges, density = False)
  if d2 is not None:
    bins2, edges2 = np.histogram (d2, edges, density = False)
  else: # use d2 = 𝓝 (0,1)
    bincenter = 0.5 * (edges[1] - edges[0])
    bins2 = gauss_bins (0, 1, bincenter + np.array (edges1[:-1]))
  d = {
    "JensenShannon": scipy.spatial.distance.jensenshannon (bins1, bins2, base = 2) # jensenshannon normalizes
  }
  sbi = round (buckets / 2 - buckets * 1 / limit / 2)       # bucket index for σ=1
  sperc = np.sum (bins1[sbi:-sbi]) * 100 / np.sum (bins1)
  d["σ%"] = sperc
  d["σ-most?"] = sperc > 52 # >= 68.27%
  bins1 = np.array (bins1) / sum (bins1) # normalize
  bins2 = np.array (bins2) / sum (bins2) # normalize
  kld_values = scipy.special.rel_entr (bins1, bins2)
  d["KullbackLeibler"] = sum (kld_values)
  if 0:
    vprint ("edges", edges1)
    vprint ("bins1", bins1, sum (bins1))
    vprint ("bins2", bins2, sum (bins2))
    gdist = np.random.normal (0, 1, 9999999)
    gbins, gedges = np.histogram (gdist, edges, density = True)
    vprint ("gauss", gbins)
    vprint ("kld_values", kld_values)
  return d

# render example
if __name__ == '__main__':
  # Test distribution size
  l = 16 * 16
  ddof = 0

  # Generate test distribution with 2 peaks left and right from 0.0
  s1 = np.random.normal (0, 0.5, l//2)
  s2 = np.concatenate ((s1-1, s1+1))
  vprint ("s2:", "len=%d" % len (s2), "%f…%f" % (s2.min(), s2.max()), "µ=%f" % np.mean (s2), "σ=%f" % np.std (s2, ddof = ddof))

  # Show random 𝓝 (0,1) distributions against each other
  n01 = np.random.normal (0, 1, l)
  vprint ("𝓝 (0,1) ↔ 𝓝 (0,1)    divergence:", distribution_divergence (n01, np.random.normal (0, 1, l)))

  # Show random 𝓝 (0,1) distribution against ideal Gauss distribution
  vprint ("𝓝 (0,1) ↔ gauss_bins divergence:", distribution_divergence (n01)) # more exact, due to gauss_bins() precision

  # Show random 2-peak distribution against ideal Gauss distribution
  s_kld = distribution_divergence (s2)
  vprint ("dist ↔ gauss_bins divergence:", s_kld)

  # Test max of 𝓝 (0,1) ↔ gauss_bins divergence
  jsvals = np.zeros ((10000,))
  klvals = np.zeros (jsvals.shape)
  vprint ("Making %d measurements of 𝓝 (0,1) ↔ gauss_bins divergence:" % jsvals.shape[0])
  for i in range (jsvals.shape[0]):
    nd = distribution_divergence (np.random.normal (0, 1, l))
    jsvals[i] = nd['JensenShannon']
    klvals[i] = nd['KullbackLeibler']
  vprint ('JensenShannon:  ', jsvals.min(), '…', np.average (jsvals), '…', jsvals.max())
  vprint ('KullbackLeibler:', klvals.min(), '…', np.average (klvals), '…', klvals.max())

  # Plot random 2-peak distribution against ideal Gauss distribution
  plot_std_histogram (s2)
