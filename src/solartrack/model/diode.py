"""Independent scalar single-diode solver; no pvlib calls.

Illustrative silicon module parameters, not fitted to a manufacturer's panel.
Environmental scaling follows the De Soto equations (see docs/methodology.md).
"""
from dataclasses import dataclass
from functools import lru_cache
from math import exp, expm1, inf, isfinite, log1p


@dataclass(frozen=True)
class Panel:
    il_ref: float = 9.2       # A at 1000 W/m², 25 °C
    io_ref: float = 1e-9     # A
    rs: float = 0.3         # ohm
    rsh_ref: float = 400.0  # ohm
    a_ref: float = 1.8      # n Ns k Tref / q, V
    alpha_sc: float = 0.0046  # A/K
    eg_ref: float = 1.121     # eV, crystalline silicon assumption
    deg_dt: float = -0.0002677  # 1/K (relative bandgap coefficient)


@dataclass(frozen=True)
class Parameters:
    il: float
    io: float
    rs: float
    rsh: float
    a: float


@lru_cache(maxsize=32768)
def parameters(g: float, tc: float, panel: Panel = Panel()) -> Parameters:
    """G is effective plane-of-array irradiance W/m²; Tc is cell °C."""
    if not isfinite(g) or not isfinite(tc) or not (0 <= g <= 1400 and -20 <= tc <= 85):
        raise ValueError("Model domain: 0–1400 W/m² and −20–85 °C")
    tk, tr = tc + 273.15, 298.15
    eg = panel.eg_ref * (1 + panel.deg_dt * (tk - tr))
    kb_ev = 8.617333262145179e-5
    return Parameters(
        g / 1000 * (panel.il_ref + panel.alpha_sc * (tk - tr)),
        panel.io_ref * (tk / tr) ** 3 * exp(panel.eg_ref / (kb_ev * tr) - eg / (kb_ev * tk)),
        panel.rs, panel.rsh_ref * 1000 / g if g > 0 else inf,
        panel.a_ref * tk / tr,
    )


def current(v: float, p: Parameters) -> float:
    """Solve signed I(V) with bracketed Newton, absolute residual ≤ 1e-11 A.

    For V≥0 the bracket [-V/Rs, IL] encloses the unique root. The
    positive derivative prevents multiple roots. Signed current above Voc
    is retained here for comparison; terminal_current blocks absorption.
    """
    if not isfinite(v) or not 0 <= v <= 60:
        raise ValueError("Solver voltage must be finite and in [0, 60] V")
    if p.rs <= 0 or p.io <= 0 or p.a <= 0 or p.rsh <= 0 or p.il < 0:
        raise ValueError("Invalid diode parameters")
    lo, hi = -v / p.rs, p.il
    x = 0.0 if v == 0 else min(p.il, max(lo, (voc(p) - v) / p.rs))
    for _ in range(100):
        vd = v + x * p.rs
        e = exp(vd / p.a)
        f = x - p.il + p.io * expm1(vd / p.a) + vd / p.rsh
        if abs(f) <= 1e-11:
            return x
        if f > 0:
            hi = x
        else:
            lo = x
        derivative = 1 + p.io * e * p.rs / p.a + p.rs / p.rsh
        candidate = x - f / derivative
        x = candidate if lo < candidate < hi else (lo + hi) / 2
    raise ArithmeticError("Single-diode solver did not converge")


@lru_cache(maxsize=32768)
def voc(p: Parameters) -> float:
    """Open-circuit root in V. Shunt-free expression is an upper bound."""
    if p.il == 0:
        return 0.0
    lo, hi = 0.0, p.a * log1p(p.il / p.io)
    for _ in range(48):
        mid = (lo + hi) / 2
        if p.io * expm1(mid / p.a) + mid / p.rsh > p.il:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def terminal_current(v: float, p: Parameters) -> float:
    """Ideal reverse-current blocking abstraction, not a diode circuit model."""
    return max(0.0, current(v, p))
