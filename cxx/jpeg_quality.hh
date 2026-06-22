// Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
#pragma once

/** Estimate JPEG quality from DQT quantization tables.
 * Returns a quality estimate in [min_quality..100], or @p fallback on failure.
 * Only works for images encoded with IJG-style tables at Q >= 50.
 *
 * @param path  Path to the JPEG file.
 * @param fallback  Value returned when no DQT is found (e.g. -1 or 90).
 */
int estimate_jpeg_quality (const char *path, int fallback);
