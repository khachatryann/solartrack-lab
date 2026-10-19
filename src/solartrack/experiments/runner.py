"""Causal discrete simulation with a rate-limited voltage reference actuator."""
from dataclasses import dataclass, asdict
import numpy as np
from solartrack.controllers import CONTROLLERS
from solartrack.model import parameters, terminal_current
from solartrack.evaluation.oracle import maximum_power
from solartrack.evaluation.metrics import cumulative_wh, summarize


@dataclass(frozen=True)
class Config:
    step_v: float = 0.6
    sample_s: float = 0.25
    dt_s: float = 0.05
    duration_s: float = 60.0
    initial_v: float = 24.0
    slew_v_per_s: float = 8.0

    def __post_init__(self):
        if not all(np.isfinite(x) and x > 0 for x in (self.step_v, self.sample_s, self.dt_s, self.duration_s, self.slew_v_per_s)):
            raise ValueError("Time/step/slew must be finite and positive")
        for a, b in ((self.sample_s, self.dt_s), (self.duration_s, self.dt_s)):
            if abs(a / b - round(a / b)) > 1e-7:
                raise ValueError("Sampling and duration must be integer multiples of dt")
        if not 0 <= self.initial_v <= 50:
            raise ValueError("Initial voltage outside actuator bounds")

    @property
    def id(self):
        return f"step{self.step_v:g}-sample{self.sample_s:g}"


def actuator_step(v, target, slew, dt):
    target = np.clip(target, 0.0, 50.0)
    return float(np.clip(v + np.clip(target - v, -slew * dt, slew * dt), 0.0, 50.0))


def simulate(scenario, config=Config()):
    n = round(config.duration_s / config.dt_s) + 1
    t = np.arange(n, dtype=float) * config.dt_s
    sample_ticks = round(config.sample_s / config.dt_s)
    g, tc = np.array([scenario.environment(float(x)) for x in t]).T
    # Evaluation runs separately; no oracle object enters update(Vsensor, Isensor).
    oracle = np.array([maximum_power(float(a), float(b)) for a, b in zip(g, tc)])
    conditions = [parameters(float(a), float(b)) for a, b in zip(g, tc)]
    # One paired standard-normal sequence per sampling schedule, shared by all
    # controllers and step sizes. Same sample sequence under dt refinement.
    rng = np.random.default_rng(scenario.seed)
    z = rng.standard_normal((1 + (n - 1) // sample_ticks, 2))
    runs = {}
    for name, cls in CONTROLLERS.items():
        controller = cls(config.step_v, config.initial_v)
        v = config.initial_v
        series = {key: [] for key in ("v", "i", "p", "target_v", "sensor_v", "sensor_i", "sampled", "decision_index")}
        events, last_sv, last_si, decision_index = [], v, 0.0, 0
        for k in range(n):
            i = terminal_current(v, conditions[k])
            sampled = k % sample_ticks == 0
            if sampled:
                last_sv = v + z[k // sample_ticks, 0] * scenario.noise_v
                last_si = i + z[k // sample_ticks, 1] * scenario.noise_i
                d = controller.update(float(last_sv), float(last_si))
                events.append({"time_s": float(t[k]), "reason": d.reason, "target_v": d.target_v})
                decision_index = len(events) - 1
            for key, value in zip(series, (v, i, v * i, controller.target, last_sv, last_si, int(sampled), decision_index)):
                series[key].append(value)
            v = actuator_step(v, controller.target, config.slew_v_per_s, config.dt_s)
        series["energy_wh"] = cumulative_wh(t, series["p"]).tolist()
        runs[name] = {"series": series, "decisions": events,
                      "metrics": summarize(t, series["p"], oracle[:, 1], scenario)}
    return {"schema_version": 1, "scenario": asdict(scenario), "config": asdict(config),
            "time_s": t.tolist(), "irradiance_w_m2": g.tolist(), "cell_temperature_c": tc.tolist(),
            "oracle_v": oracle[:, 0].tolist(), "oracle_w": oracle[:, 1].tolist(),
            "oracle_energy_wh": cumulative_wh(t, oracle[:, 1]).tolist(), "controllers": runs}
