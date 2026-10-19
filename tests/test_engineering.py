import ast
import inspect
import json
from pathlib import Path
import numpy as np
import pytest
from solartrack.model import parameters, current, terminal_current, voc
from solartrack.controllers import PerturbObserve, IncrementalConductance, FixedVoltage
from solartrack.experiments.profiles import SCENARIOS, Scenario
from solartrack.experiments.runner import Config, simulate, actuator_step
from solartrack.evaluation.metrics import cumulative_wh, settling, summarize
from solartrack.evaluation.verification import compare_pvlib

ROOT = Path(__file__).resolve().parents[1]


def test_independent_solver_against_pvlib():
    r = compare_pvlib()
    assert r["comparison_points"] == 5050
    assert r["passed"], r


@pytest.mark.parametrize("g,tc", [(0,25), (.001,75), (1,-20), (1400,85), (1000,25)])
def test_iv_curve_and_equation(g, tc):
    p = parameters(g, tc)
    v = np.linspace(0,50,101)
    i = np.array([current(float(x),p) for x in v])
    assert np.isfinite(i).all()
    assert np.all(np.diff(i) <= 1e-10)
    vd = v + i * p.rs
    residual = i - p.il + p.io * np.expm1(vd / p.a) + vd / p.rsh
    assert np.max(np.abs(residual)) < 2e-10
    assert abs(current(voc(p),p)) < 2e-10


@pytest.mark.parametrize("g,tc", [(-1,25),(1401,25),(1000,86),(1000,-21),(float("nan"),25)])
def test_model_rejects_out_of_domain(g, tc):
    with pytest.raises(ValueError):
        parameters(g,tc)


def test_po_decisions_follow_own_perturbation():
    c = PerturbObserve(step_v=.6)
    assert c.update(24,8).target_v == pytest.approx(24.6)
    assert c.update(24.6,8).target_v == pytest.approx(25.2)
    assert c.update(25.2,7).target_v == pytest.approx(24.6)
    assert c.update(24.6,8).target_v == pytest.approx(24.0)


@pytest.mark.parametrize("voltage,current_a,expected", [(25,8,25.2), (25,7,24.0), (24,8,24.6), (24,9,25.2), (24,7,24.0)])
def test_incremental_conductance_branches(voltage, current_a, expected):
    c = IncrementalConductance(step_v=.6)
    c.update(24,8)
    assert c.update(voltage,current_a).target_v == pytest.approx(expected)


def test_incremental_conductance_at_zero_slope():
    c = IncrementalConductance()
    c.update(24,8)
    # di/dv = −I/V with current I=200/26 A and V=25 V.
    assert c.update(25,7.6923076923076925).target_v == pytest.approx(24.6)


@pytest.mark.parametrize("cls", [PerturbObserve, IncrementalConductance])
def test_sensor_edges_and_controller_voltage_limits(cls):
    c = cls(initial_v=50)
    for v,i in [(50,9),(50,9),(float("nan"),9),(0,0),(50,-1),(50,9)]:
        d = c.update(v,i)
        assert 0 <= d.target_v <= 50
    assert c.previous is not None


def test_actuator_rate_limit_and_clamp():
    assert actuator_step(24,50,8,.05) == pytest.approx(24.4)
    assert actuator_step(24,-99,8,.05) == pytest.approx(23.6)
    assert actuator_step(49.9,100,8,.05) == 50
    assert actuator_step(.1,-100,8,.05) == 0


def test_fixed_voltage_is_preselected():
    assert FixedVoltage().update(10,2).target_v == 32


def test_zero_light_full_experiment():
    class Dark:
        id = "dark"
        seed = 4
        noise_v = noise_i = 0
        events = ()
        steady_start = None
        def environment(self,t):
            return 0.0,25.0
    # dataclass for serialization, retain a constant-zero environment function.
    from dataclasses import dataclass
    @dataclass(frozen=True)
    class DarkScenario(Scenario):
        def environment(self,t):
            return 0.0,25.0
    r = simulate(DarkScenario("dark","Dark","Zero irradiance",4), Config(duration_s=2))
    for c in r["controllers"].values():
        assert c["metrics"]["harvested_wh"] == 0
        assert c["metrics"]["tracking_pct"] is None
        assert max(c["series"]["p"]) == 0
    assert terminal_current(50,parameters(0,25)) == 0


def test_seed_reproducibility_and_noise_pairing():
    c = Config(duration_s=2)
    a = simulate(SCENARIOS["noise"],c)
    assert a == simulate(SCENARIOS["noise"],c)
    residuals = []
    for r in a["controllers"].values():
        s = r["series"]
        sampled = np.asarray(s["sampled"],bool)
        residuals.append((np.array(s["sensor_v"])-np.array(s["v"]))[sampled])
    np.testing.assert_allclose(residuals[0],residuals[1],atol=1e-14)
    np.testing.assert_allclose(residuals[1],residuals[2],atol=1e-14)


def test_energy_has_correct_units_and_nonuniform_time():
    assert cumulative_wh([0,1800,3600],[10,10,10])[-1] == 10
    assert cumulative_wh([0,1,3],[0,2,6])[-1] == pytest.approx(9/3600)
    with pytest.raises(ValueError):
        cumulative_wh([0,0],[1,1])


def test_settling_requires_continuous_dwell():
    t = np.arange(0,6.1,.1)
    a = np.ones(len(t))*100
    assert settling(t,a,a,0,6) == 0
    assert settling(t,a*.97,a,0,6) is None
    assert settling(t,a,a,5,6) is None
    assert settling(t,a*0,a*0,0,6) is None


def test_controllers_have_no_oracle_import_or_input():
    import solartrack.controllers as controllers
    tree = ast.parse(inspect.getsource(controllers))
    imports = [n for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
    assert all("oracle" not in ast.unparse(n) and "model" not in ast.unparse(n) and "evaluation" not in ast.unparse(n) for n in imports)
    for cls in (FixedVoltage,PerturbObserve,IncrementalConductance):
        assert list(inspect.signature(cls.update).parameters) == ["self","measured_v","measured_i"]


def test_poisoning_oracle_changes_evaluation_only(monkeypatch):
    import solartrack.experiments.runner as runner
    a = simulate(SCENARIOS["constant"],Config(duration_s=2))
    monkeypatch.setattr(runner,"maximum_power",lambda g,tc: (1.0,1.0))
    b = simulate(SCENARIOS["constant"],Config(duration_s=2))
    for ctrl in a["controllers"]:
        assert a["controllers"][ctrl]["series"] == b["controllers"][ctrl]["series"]
        assert a["controllers"][ctrl]["decisions"] == b["controllers"][ctrl]["decisions"]


@pytest.mark.parametrize("kwargs", [{"dt_s":0},{"sample_s":.12},{"initial_v":51},{"slew_v_per_s":-1}])
def test_bad_config_rejected(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)


def test_all_published_metrics_and_files():
    import hashlib
    import zipfile
    import csv
    import io
    out = ROOT / "results"
    checksums = json.loads((out/"checksums.json").read_text())
    for path, digest in checksums.items():
        assert hashlib.sha256((out/path).read_bytes()).hexdigest() == digest, path
    summary = json.loads((out/"summary.json").read_text())
    assert len(summary) == 162
    csv_archive = zipfile.ZipFile(out/"all-traces-csv.zip")
    assert len(csv_archive.namelist()) == 54
    for path in sorted((out/"runs").glob("*.json")):
        r = json.loads(path.read_text())
        cfg = r["config"]
        config_id = f'step{cfg["step_v"]:g}-sample{cfg["sample_s"]:g}'
        scenario = SCENARIOS[r["scenario"]["id"]]
        csvrows = list(csv.DictReader(io.StringIO(csv_archive.read(path.stem+".csv").decode())))
        assert len(csvrows) == len(r["time_s"])*3
        for ci,(ctrl,data) in enumerate(r["controllers"].items()):
            m = summarize(r["time_s"],data["series"]["p"],r["oracle_w"],scenario)
            assert m == data["metrics"]
            row = next(x for x in summary if x["scenario"]==scenario.id and x["config_id"]==config_id and x["controller"]==ctrl)
            for key,value in m.items():
                assert row[key] == value
            assert float(csvrows[(ci+1)*len(r["time_s"])-1]["energy_wh"]) == m["harvested_wh"]
            np.testing.assert_allclose(data["series"]["energy_wh"],cumulative_wh(r["time_s"],data["series"]["p"]),atol=1e-12)
            assert max(np.asarray(data["series"]["p"])-np.asarray(r["oracle_w"])) <= 1e-7
            assert all(0 <= v <= 50 for v in data["series"]["v"])
    assert json.loads((out/"convergence.json").read_text())["passed"]


def test_published_default_run_reproduces():
    recorded = json.loads((ROOT/"results/runs/drop-step0.6-sample0.25.json").read_text())
    actual = simulate(SCENARIOS["drop"])
    for c in actual["controllers"]:
        np.testing.assert_allclose(recorded["controllers"][c]["series"]["p"], actual["controllers"][c]["series"]["p"], atol=1e-8)


def test_curve_frames_match_full_resolution_trace():
    for name,s in SCENARIOS.items():
        curves = json.loads((ROOT/f"results/curves/{name}.json").read_text())
        for frame in curves["frames"][::20]:
            g,tc = s.environment(frame["time_s"])
            p = parameters(g,tc)
            np.testing.assert_allclose(frame["i_a"],[terminal_current(v,p) for v in curves["voltage_v"]],atol=1e-10)
