"""Daily cost anomaly detection.

The check compares each day against a forecast built only from the days before
it, instead of a fixed dollar threshold. Cost that is growing steadily (a
ramp-up) moves the forecast with it, so it is not flagged every day; a break
from the recent pattern is.

Method, per day t (t >= window):
  1. Work in log space, because cost changes are multiplicative:
         r_i = log1p(y_i) - log1p(y_{i-1})      (daily log change)
  2. From the previous `window` daily changes, take the median (the typical
     change, i.e. the trend) and the MAD scaled by 1.4826 (a robust standard
     deviation that one past spike cannot inflate).
  3. Forecast day t from the last day that was not flagged (usually yesterday):
     log1p(anchor) + median * steps, with an interval of
     +/- k * robust SD * sqrt(steps) (k = 3.5 by default). Anchoring on the last
     normal day means one spike does not make the next normal day look like a drop.
  4. Flag day t if it falls outside the interval. If more than MAX_RUN days in a
     row are flagged, the new level is accepted (a step change, such as a new
     workload going live) and the forecast re-anchors on it.

The two baselines it is compared against are the rules most teams start with:
a fixed daily threshold and a day-over-day percentage jump.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MAD_TO_SD = 1.4826
MIN_SPREAD = 0.05  # log units; stops a perfectly flat history from flagging every cent
MAX_RUN = 3        # flagged days in a row before the new level is accepted as normal


def rolling_forecast(values, window: int = 7, k: float = 3.5) -> pd.DataFrame:
    """Flag days outside a trend-aware robust interval.

    Returns one row per input day with columns: actual, expected, lower, upper,
    is_anomaly, direction ('high'/'low'/None), excess (cost beyond the interval
    edge; 0 when not flagged). The first `window` days have no forecast.
    """
    y = np.asarray(values, dtype=float)
    if window < 3:
        raise ValueError("window must be at least 3")
    if np.any(y < 0):
        raise ValueError("rolling_forecast expects non-negative cost; pass usage cost, not net of credits")

    ly = np.log1p(y)
    rows = []
    last_good = window - 1  # last day not flagged; the forecast is anchored on it
    for t in range(len(y)):
        if t < window:
            rows.append((y[t], np.nan, np.nan, np.nan, False, None, 0.0))
            continue
        # A run of more than MAX_RUN flagged days is a new level, not an incident: re-anchor.
        if t - 1 - last_good >= MAX_RUN:
            last_good = t - 1
        changes = np.diff(ly[max(0, t - window - 1):t])
        med = float(np.median(changes))
        spread = max(MAD_TO_SD * float(np.median(np.abs(changes - med))), MIN_SPREAD)
        steps = t - last_good
        pred = ly[last_good] + med * steps
        half = k * spread * np.sqrt(steps)
        lo, hi = pred - half, pred + half
        expected, lower, upper = np.expm1(pred), max(np.expm1(lo), 0.0), np.expm1(hi)
        if ly[t] > hi:
            rows.append((y[t], expected, lower, upper, True, "high", y[t] - upper))
        elif ly[t] < lo:
            rows.append((y[t], expected, lower, upper, True, "low", y[t] - lower))
        else:
            rows.append((y[t], expected, lower, upper, False, None, 0.0))
            last_good = t

    return pd.DataFrame(rows, columns=["actual", "expected", "lower", "upper", "is_anomaly", "direction", "excess"])


def fixed_threshold(values, limit: float) -> np.ndarray:
    """Baseline rule: flag any day whose cost is above a fixed limit."""
    return np.asarray(values, dtype=float) > limit


def day_over_day(values, pct: float) -> np.ndarray:
    """Baseline rule: flag a day whose cost rose more than `pct` (0.5 = 50%) over the day before."""
    y = np.asarray(values, dtype=float)
    out = np.zeros(len(y), dtype=bool)
    prev = y[:-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        jump = np.where(prev > 0, (y[1:] - prev) / prev, np.inf)
    out[1:] = jump > pct
    return out
