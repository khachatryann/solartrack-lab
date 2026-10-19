from functools import lru_cache
from scipy.optimize import minimize_scalar
from solartrack.model import parameters, terminal_current, voc


@lru_cache(maxsize=32768)
def maximum_power(g, tc):
    """Unconstrained quasistatic panel MPP; evaluation only, no slew limit."""
    p = parameters(g, tc)
    if p.il == 0:
        return 0.0, 0.0
    upper = voc(p)
    optimum = minimize_scalar(lambda v: -v * terminal_current(v, p),
                              bounds=(0, upper), method="bounded",
                              options={"xatol": 1e-9})
    if not optimum.success:
        raise ArithmeticError("Oracle optimization failed")
    return float(optimum.x), float(-optimum.fun)
