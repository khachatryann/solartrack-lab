from dataclasses import dataclass
from math import sin, pi


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str
    seed: int
    noise_v: float = 0.0
    noise_i: float = 0.0
    events: tuple = ()
    steady_start: float | None = None

    def environment(self, t):
        if self.id in ("constant", "noise"):
            return 1000.0, 25.0
        if self.id == "drop":
            return (1000.0 if t < 20 or t >= 40 else 250.0), 25.0
        if self.id == "ramp":
            return (300 + 700 * min(t, 30) / 30 if t <= 30
                    else 1000 - 600 * (t - 30) / 30), 25.0
        if self.id == "clouds":
            # Uniform whole-panel cloud pulses, not partial shading.
            g = 1000.0
            for center, width, depth in ((14, 5, 650), (30, 7, 800), (47, 4, 550)):
                d = abs(t - center) / width
                if d < 1:
                    g -= depth * 0.5 * (1 + sin(pi / 2 + pi * d))
            return g, 25.0
        if self.id == "temperature":
            return 1000.0, 25.0 + 35.0 * max(0, min(1, (t - 15) / 30))
        raise KeyError(self.id)


SCENARIOS = {
    s.id: s for s in [
        Scenario("constant", "Constant sunlight", "1000 W/m² and 25 °C for 60 s. Isolate startup and steady operation.", 7310, steady_start=45),
        Scenario("drop", "Drop & recovery", "Uniform irradiance drops from 1000 to 250 W/m² at 20 s, then returns at 40 s. Cell temperature stays at 25 °C.", 7311, events=(20.0, 40.0), steady_start=50),
        Scenario("ramp", "Changing sunlight", "Irradiance ramps from 300 to 1000 W/m² by 30 s, then falls to 400 W/m² by 60 s.", 7312),
        Scenario("clouds", "Passing clouds", "Three smooth, uniform cloud pulses with different depth and duration. No partial shading.", 7313),
        Scenario("temperature", "Warming cells", "At 1000 W/m², cell temperature rises from 25 to 60 °C between 15 and 45 s.", 7314, steady_start=50),
        Scenario("noise", "Noisy sensors", "Constant 1000 W/m² and 25 °C; independent Gaussian sensor noise σV = 0.12 V, σI = 0.04 A.", 7315, 0.12, 0.04, steady_start=45),
    ]
}
