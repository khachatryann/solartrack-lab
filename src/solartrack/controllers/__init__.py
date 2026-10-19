"""Controllers see only sensor V and I; no environment, panel or oracle."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Decision:
    target_v: float
    reason: str


class Controller:
    def __init__(self, step_v=0.6, initial_v=24.0, vmin=0.0, vmax=50.0):
        if not (0 < step_v <= 5 and 0 <= vmin < vmax <= 50 and vmin <= initial_v <= vmax):
            raise ValueError("Invalid controller settings")
        self.step = step_v
        self.target = initial_v
        self.vmin, self.vmax = vmin, vmax
        self.previous = None
        self.direction = 1

    def move(self, direction, reason):
        proposed = self.target + direction * self.step
        self.target = max(self.vmin, min(self.vmax, proposed))
        if proposed != self.target:
            reason += "; command clipped at voltage limit"
        return Decision(self.target, reason)

    def prepare(self, v, i):
        if not isfinite(v) or not isfinite(i):
            self.previous = None
            return Decision(self.target, "Invalid sensor input: hold voltage")
        if i < 0.05 or v < 0.1:
            self.previous = None
            return Decision(self.target, "Low measured current/voltage: hold and reset history")
        if self.previous is None:
            self.previous = (v, i)
            self.direction = 1
            return self.move(1, "Startup: probe with one positive voltage step")
        return None


class FixedVoltage(Controller):
    def update(self, measured_v, measured_i):
        self.target = max(self.vmin, min(self.vmax, 32.0))
        return Decision(self.target, "Baseline: hold the preselected 32.0 V reference")


class PerturbObserve(Controller):
    def update(self, measured_v, measured_i):
        early = self.prepare(measured_v, measured_i)
        if early:
            return early
        pv, pi = self.previous
        dp = measured_v * measured_i - pv * pi
        self.previous = (measured_v, measured_i)
        if dp < -0.02:  # W deadband
            self.direction *= -1
            reason = "Measured power fell: reverse perturbation direction"
        else:
            reason = "Measured power rose or stayed within 0.02 W: continue perturbation"
        # Reflect at a hard stop to avoid a permanently saturated probe.
        if (self.target >= self.vmax and self.direction > 0) or (self.target <= self.vmin and self.direction < 0):
            self.direction *= -1
            reason = "Voltage limit: reverse perturbation direction"
        return self.move(self.direction, reason)


class IncrementalConductance(Controller):
    def update(self, measured_v, measured_i):
        early = self.prepare(measured_v, measured_i)
        if early:
            return early
        pv, pi = self.previous
        dv, di = measured_v - pv, measured_i - pi
        self.previous = (measured_v, measured_i)
        if abs(dv) < 1e-4:
            if abs(di) < 1e-5:
                return self.move(0, "Unchanged measurements: hold voltage")
            direction = 1 if di > 0 else -1
            return self.move(direction, "Nearly zero ΔV: follow the sign of ΔI without dividing")
        slope = measured_i + measured_v * di / dv  # dP/dV, A
        if abs(slope) <= 0.05:
            return self.move(0, "Estimated dP/dV within ±0.05 A: hold voltage")
        return self.move(1 if slope > 0 else -1,
                         "Estimated dP/dV positive: increase voltage" if slope > 0
                         else "Estimated dP/dV negative: decrease voltage")


CONTROLLERS = {"fixed": FixedVoltage, "po": PerturbObserve, "inc": IncrementalConductance}
