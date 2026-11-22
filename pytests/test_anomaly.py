import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from finops.anomaly import day_over_day, fixed_threshold, rolling_forecast  # noqa: E402


def noisy(base, seed=0, sd=0.03):
    rng = np.random.default_rng(seed)
    return np.asarray(base) * np.exp(rng.normal(0, sd, len(base)))


def test_steady_series_has_no_anomalies():
    y = noisy(np.full(30, 100.0))
    out = rolling_forecast(y)
    assert not out["is_anomaly"].any()


def test_planned_growth_is_not_flagged_but_fixed_threshold_is():
    # Cost growing 8% a day on purpose: a ramp, not an incident.
    y = noisy(100 * 1.08 ** np.arange(30), seed=1)
    out = rolling_forecast(y)
    assert out["is_anomaly"].sum() == 0
    # A static limit set from week one fires on most of the month.
    assert fixed_threshold(y, limit=1.5 * y[:7].mean()).sum() >= 15


def test_spike_is_flagged_high_with_positive_excess():
    y = noisy(np.full(30, 100.0), seed=2)
    y[20] = 400.0
    out = rolling_forecast(y)
    assert bool(out.loc[20, "is_anomaly"])
    assert out.loc[20, "direction"] == "high"
    assert out.loc[20, "excess"] > 0
    assert out.loc[20, "expected"] == pytest.approx(100, rel=0.15)


def test_day_after_a_spike_is_not_flagged_as_a_drop():
    y = noisy(np.full(30, 100.0), seed=5)
    y[20] = 400.0
    out = rolling_forecast(y)
    assert bool(out.loc[20, "is_anomaly"])
    assert not bool(out.loc[21, "is_anomaly"])


def test_drop_is_flagged_low():
    y = noisy(np.full(30, 100.0), seed=3)
    y[25] = 5.0
    out = rolling_forecast(y)
    assert bool(out.loc[25, "is_anomaly"])
    assert out.loc[25, "direction"] == "low"
    assert out.loc[25, "excess"] < 0


def test_break_in_trend_is_flagged():
    y = noisy(100 * 1.05 ** np.arange(30), seed=4)
    y[22:] *= 3  # the ramp suddenly triples
    out = rolling_forecast(y)
    assert bool(out.loc[22, "is_anomaly"])


def test_step_change_is_accepted_after_a_few_days():
    y = noisy(np.full(30, 100.0), seed=6)
    y[15:] *= 3  # a new workload goes live and stays
    out = rolling_forecast(y)
    assert bool(out.loc[15, "is_anomaly"])
    assert out["is_anomaly"].iloc[20:].sum() == 0
    # The forecast must stay near the real level, never run away.
    assert out["expected"].iloc[20:].max() < 2 * y.max()


def test_first_window_days_have_no_forecast():
    out = rolling_forecast(np.full(10, 50.0), window=7)
    assert out["expected"].iloc[:7].isna().all()
    assert not out["is_anomaly"].iloc[:7].any()


def test_negative_cost_is_rejected():
    with pytest.raises(ValueError):
        rolling_forecast([10, 12, -5, 11, 10, 9, 10, 11])


def test_day_over_day_rule():
    flags = day_over_day([10, 12, 20, 19, 0, 5], pct=0.5)
    assert flags.tolist() == [False, False, True, False, False, True]
