# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
import numpy as np
import scipy, math
import config
import matplotlib.pyplot as plt
import matplotlib.patches as Patches

# Maximum filter, helps with visualization (denoted by ζ)
def maxi (img, size = 8):
  return scipy.ndimage.maximum_filter (img, size = size)

# Display a list of grey images
show_fullscreen = { 'fullscreen': True }
def show (title = '', cfg = show_fullscreen, **images):
  n = len (images)
  sq = int (math.sqrt (n))
  if sq * sq == n:
    r = sq
  else:
    r = 2 if n > 2 else 1
  fig, axs = plt.subplots (r, round (n / r))
  if config.will_plot_name:
    fig.canvas.manager.set_window_title (config.will_plot_name)
  if title:
    fig.suptitle (title, fontsize=16)
  if cfg.get ('fullscreen', 0):
    mng = plt.get_current_fig_manager()
    mng.resize (*mng.window.maxsize())
  if n == 1:
    axl = [ axs ]
  else:
    axl = list (ax for ax in axs.flat)
  i = 0
  for name,img in images.items():
    axl[i].set_title (name)
    axl[i].imshow (img, cmap = plt.cm.gray)
    i += 1
  plt.show()

# Display a number of polygons
def polyanimation (title, img, polygons, color = '#f0f', clear = False, keypress = False, animate = True):
  mkcolor = (lambda : color) if color != 'random' else lambda : np.random.choice (range (70, 256), size = 3) / 255
  plt.ion()                       # interactive mode ON
  fig = plt.figure()
  if config.will_plot_name:
    fig.canvas.manager.set_window_title (config.will_plot_name)
  if 1:
    mng = plt.get_current_fig_manager()
    mng.resize (*mng.window.maxsize())
  ax = fig.add_subplot(111)
  ax.set_title (title)
  ax.imshow (img, cmap = plt.cm.gray)
  dims = 1 # len (polygons[0])
  patches = [None] * dims
  for poly in polygons:
    if patches[0] and clear:
      for pat in patches:
        pat.remove()
    if dims > 1:
      for i in range (dims):
        point = poly[i]
        patches[i] = Patches.Circle ((point[0], point[1]), radius=11, fill=False, color = mkcolor())
        ax.add_patch (patches[i])
    else:
      patches[0] = Patches.Polygon (poly, fill=False, color = mkcolor())
      ax.add_patch (patches[0])

    if animate:
      fig.canvas.flush_events()
    if keypress:
      while not plt.waitforbuttonpress():
        pass
  plt.ioff()
  plt.show()
