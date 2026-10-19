import numpy as np


def cumulative_wh(time_s, power_w):
    """Composite trapezoids; timestamps in s, input W, output Wh."""
    t, p = np.asarray(time_s), np.asarray(power_w)
    if len(t) != len(p) or len(t) < 2 or np.any(np.diff(t) <= 0):
        raise ValueError("Need equal-length arrays and strictly increasing time")
    return np.r_[0.0, np.cumsum((p[1:] + p[:-1]) * np.diff(t) / 7200.0)]


def settling(time_s, power_w, available_w, event_s, end_s, dwell_s=2.0):
    """First ≥98%-of-oracle interval lasting 2 s, before next event/end.

    Returns null when the dwell cannot be established; not a claim that the
    controller stays settled forever. Dark periods cannot satisfy the test.
    """
    t, p, a = map(np.asarray, (time_s, power_w, available_w))
    good = (a > 1e-6) & (p >= 0.98 * a)
    start = None
    for k in np.flatnonzero((t >= event_s) & (t < end_s)):
        if not good[k]:
            start = None
        elif start is None:
            start = k
        if start is not None and t[k] - t[start] >= dwell_s - 1e-9:
            return float(t[start] - event_s)
    return None


def summarize(t, power, available, scenario):
    e, a = cumulative_wh(t, power)[-1], cumulative_wh(t, available)[-1]
    mask = np.asarray(t) >= (scenario.steady_start or float("inf"))
    ps = np.asarray(power)[mask]
    changes = (0.0,) + scenario.events
    ends = scenario.events + (float(t[-1]),)
    # Moving profiles have no stationary post-change reference.
    recoveries = [] if scenario.id in ("ramp", "clouds", "temperature") else [
        {"event_s": event, "settling_s": settling(t, power, available, event, end)}
        for event, end in zip(changes, ends)
    ]
    return {
        "harvested_wh": float(e), "available_wh": float(a),
        "tracking_pct": float(100 * e / a) if a > 1e-12 else None,
        "steady_ripple_pp_w": float(np.ptp(ps)) if len(ps) else None,
        "steady_std_w": float(np.std(ps, ddof=0)) if len(ps) else None,
        "steady_window_s": [scenario.steady_start, float(t[-1])] if len(ps) else None,
        "settling": recoveries,
    }
