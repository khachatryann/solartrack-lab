"""Independent pvlib comparison and time-refinement experiment."""
import numpy as np
import pvlib
from solartrack.model import Panel, parameters, current
from solartrack.evaluation.oracle import maximum_power


def compare_pvlib():
    panel = Panel()
    irradiances = [0, 0.001, 0.1, 1, 10, 50, 200, 600, 1000, 1200]
    temperatures = [-10, 0, 25, 50, 75]
    voltages = np.linspace(0, 50, 101)
    errors, normalized, rows = [], [], []
    param_error = 0.0
    for g in irradiances:
        for tc in temperatures:
            p = parameters(g, tc)
            # pvlib's zero-light Rsh=∞ limit needs NumPy scalar division,
            # rather than Python scalar 1/0. Keep zero in the comparison grid.
            with np.errstate(divide="ignore", invalid="ignore"):
                refp = pvlib.pvsystem.calcparams_desoto(np.float64(g), np.float64(tc), panel.alpha_sc, panel.a_ref,
                    panel.il_ref, panel.io_ref, panel.rsh_ref, panel.rs,
                    EgRef=panel.eg_ref, dEgdT=panel.deg_dt)
            ownp = np.array([p.il, p.io, p.rs, p.rsh, p.a])
            rp = np.array(refp)
            finite = np.isfinite(rp)
            param_error = max(param_error, float(np.max(np.abs((ownp[finite] - rp[finite]) / np.maximum(1e-30, np.abs(rp[finite]))))))
            reference = pvlib.pvsystem.i_from_v(voltages, *refp, method="lambertw")
            actual = np.array([current(float(v), p) for v in voltages])
            error = np.abs(actual - reference)
            tolerance = 1e-8 + 1e-8 * np.abs(reference)
            errors.extend(error.tolist())
            normalized.extend((error / tolerance).tolist())
            ov, op = maximum_power(g, tc)
            sd = pvlib.pvsystem.singlediode(*refp, method="lambertw")
            rows.append({"g_w_m2": g, "cell_c": tc, "max_current_abs_error_a": float(np.max(error)),
                         "mpp_power_error_w": abs(op - float(sd["p_mp"])),
                         "mpp_voltage_error_v": abs(ov - float(sd["v_mp"]))})
    mpp_p = max(r["mpp_power_error_w"] for r in rows)
    mpp_v = max(r["mpp_voltage_error_v"] for r in rows)
    passed = max(normalized) <= 1 and mpp_p <= 1e-5 and mpp_v <= 1e-4
    return {"pvlib_version": pvlib.__version__, "irradiance_grid_w_m2": irradiances,
        "temperature_grid_c": temperatures, "voltage_grid_v": voltages.tolist(),
        "comparison_points": len(errors), "signed_current_above_voc": True,
        "current_atol_a": 1e-8, "current_rtol": 1e-8,
        "max_current_abs_error_a": max(errors), "rms_current_error_a": float(np.sqrt(np.mean(np.square(errors)))),
        "max_fraction_of_current_tolerance": max(normalized), "max_parameter_relative_error": param_error,
        "mpp_power_atol_w": 1e-5, "mpp_voltage_atol_v": 1e-4,
        "max_mpp_power_error_w": mpp_p, "max_mpp_voltage_error_v": mpp_v,
        "passed": bool(passed), "conditions": rows,
        "interpretation": "Numerical cross-check of the same model, not physical validation."}


def convergence():
    from solartrack.experiments.runner import Config, simulate
    from solartrack.experiments.profiles import SCENARIOS
    rows = []
    for name in ("constant", "drop", "clouds", "temperature", "noise"):
        runs = [simulate(SCENARIOS[name], Config(dt_s=dt)) for dt in (0.05, 0.025, 0.0125)]
        for ctrl in ("fixed", "po", "inc"):
            energies = [r["controllers"][ctrl]["metrics"]["harvested_wh"] for r in runs]
            changes = [100 * abs(energies[j] - energies[j+1]) / max(energies[j+1], 1e-12) for j in (0, 1)]
            rows.append({"scenario": name, "controller": ctrl, "dt_s": [0.05, 0.025, 0.0125],
                         "energy_wh": energies, "successive_energy_change_pct": changes,
                         "within_0_5_pct": max(changes) <= 0.5})
    return {"energy_change_tolerance_pct": 0.5, "rows": rows,
        "max_successive_energy_change_pct": max(max(r["successive_energy_change_pct"]) for r in rows),
        "passed": all(r["within_0_5_pct"] for r in rows),
        "interpretation": "Finite refinement sensitivity of harvested energy; no general stability or waveform convergence proof."}
