# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
"""PEM distance thresholds, labels and colors."""

# Quality thresholds applied to the distance (0 = perfect, 1 = at poor threshold).
QUALITY_EXCELLENT = 0.1
QUALITY_GOOD = 0.20
QUALITY_ACCEPTABLE = 0.50
QUALITY_POOR = 1.00

# Quality labels (ordered best → worst)
QUALITY_LABELS = ("excellent", "good", "acceptable", "poor")

# Terminal colors per quality label
QUALITY_COLORS = {
  "excellent": "green",
  "good": "yellow",
  "acceptable": "magenta",
  "poor": "red",
  "N/A": "dim white",
}


def quality_label (distance):
  """Judge quality from a distance."""
  if distance < QUALITY_EXCELLENT: return QUALITY_LABELS[0]
  if distance < QUALITY_GOOD: return QUALITY_LABELS[1]
  if distance < QUALITY_ACCEPTABLE: return QUALITY_LABELS[2]
  return QUALITY_LABELS[3]


def quality_thresholds_text ():
  """Human-readable thresholds string for headers/footers."""
  return (f"<{QUALITY_EXCELLENT} {QUALITY_LABELS[0]} "
          f"· <{QUALITY_GOOD} {QUALITY_LABELS[1]} "
          f"· <{QUALITY_ACCEPTABLE} {QUALITY_LABELS[2]} "
          f"· ≥{QUALITY_ACCEPTABLE} {QUALITY_LABELS[3]}")
