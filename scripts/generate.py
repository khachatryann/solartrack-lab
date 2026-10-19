"""Run every published experiment, export files, verification and real charts."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import zipfile
from dataclasses import asdict

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))
sys.path.insert(0, str(ROOT / "src"))
from solartrack.experiments.runner import Config, simulate
from solartrack.experiments.profiles import SCENARIOS
from solartrack.model import parameters, terminal_current, Panel
from solartrack.evaluation.verification import compare_pvlib, convergence

OUT = ROOT / "results"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")


def csv_text(run):
    f = io.StringIO(newline="")
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["controller", "time_s", "irradiance_w_m2", "cell_temperature_c", "oracle_v", "oracle_w", "oracle_energy_wh",
                "voltage_v", "current_a", "power_w", "energy_wh", "target_v", "sensor_v", "sensor_i", "sampled", "decision"])
    for ctrl, data in run["controllers"].items():
        s = data["series"]
        for k, t in enumerate(run["time_s"]):
            w.writerow([ctrl, t, run["irradiance_w_m2"][k], run["cell_temperature_c"][k], run["oracle_v"][k],
                run["oracle_w"][k], run["oracle_energy_wh"][k], s["v"][k], s["i"][k], s["p"][k], s["energy_wh"][k],
                s["target_v"][k], s["sensor_v"][k], s["sensor_i"][k], s["sampled"][k], data["decisions"][s["decision_index"][k]]["reason"]])
    return f.getvalue()


def curves(scenario):
    voltages = [k * 0.5 for k in range(101)]
    frames = []
    for k in range(241):
        t = k * 0.25
        g, tc = scenario.environment(t)
        p = parameters(g, tc)
        frames.append({"time_s": t, "i_a": [terminal_current(v, p) for v in voltages]})
    return {"voltage_v": voltages, "frames": frames}


def make_charts(allruns, summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    colors = {"fixed": "#687084", "po": "#b46c00", "inc": "#087d78"}
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), constrained_layout=True)
    r = allruns[("drop", "step0.6-sample0.25")]
    axes[0].plot(r["time_s"], r["oracle_w"], "--", color="#b4bcc4", label="Oracle (evaluation only)")
    for name, data in r["controllers"].items():
        axes[0].plot(r["time_s"], data["series"]["p"], color=colors[name], label=name.upper(), linewidth=1)
        axes[1].plot(r["time_s"], data["series"]["energy_wh"], color=colors[name], label=name.upper())
    axes[0].set(ylabel="True panel power (W)", title="Drop & recovery · step 0.6 V · sample 0.25 s · simulated")
    axes[1].set(xlabel="Time (s)", ylabel="Harvested energy (Wh)")
    axes[0].legend(ncol=4, fontsize=8)
    for ax in axes:
        ax.grid(alpha=.18)
    fig.savefig(OUT / "charts/drop-recovery.png", dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5), constrained_layout=True)
    for ax, ctrl in zip(axes, ("po", "inc")):
        import numpy as np
        matrix = np.array([[next(x["tracking_pct"] for x in summary if x["scenario"] == "noise" and x["controller"] == ctrl and x["step_v"] == step and x["sample_s"] == sample)
                             for sample in (0.1, 0.25, 0.5)] for step in (0.2, 0.6, 1.2)])
        im = ax.imshow(matrix, cmap="YlGnBu", vmin=85, vmax=100)
        for i in range(3):
            for j in range(3):
                ax.text(j, i, f"{matrix[i,j]:.2f}%", ha="center", va="center", color="white" if matrix[i,j] > 95 else "black")
        ax.set(xticks=range(3), xticklabels=["0.10", "0.25", "0.50"], yticks=range(3), yticklabels=["0.2", "0.6", "1.2"],
               xlabel="Sampling interval (s)", ylabel="Step size (V)", title=f"{ctrl.upper()} · noisy sensors · tracking efficiency")
    fig.colorbar(im, ax=axes, label="Energy tracking efficiency (%)", shrink=.8)
    fig.savefig(OUT / "charts/noise-sweep.png", dpi=170)
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    (OUT / "charts").mkdir(exist_ok=True)
    allruns, summary, configurations = {}, [], []
    configs = [Config(step_v=a, sample_s=b) for a in (0.2, 0.6, 1.2) for b in (0.1, 0.25, 0.5)]
    for c in configs:
        configurations.append({"id": c.id, **asdict(c)})
    with zipfile.ZipFile(OUT / "all-traces-csv.zip", "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, scenario in SCENARIOS.items():
            print(f"Simulating {name} (9 configurations × 3 controllers)", flush=True)
            write_json(OUT / "curves" / f"{name}.json", curves(scenario))
            for c in configs:
                r = simulate(scenario, c)
                allruns[(name, c.id)] = r
                write_json(OUT / "runs" / f"{name}-{c.id}.json", r)
                info = zipfile.ZipInfo(f"{name}-{c.id}.csv", date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, csv_text(r))
                for ctrl, data in r["controllers"].items():
                    summary.append({"scenario": name, "config_id": c.id, "controller": ctrl,
                                    "step_v": c.step_v, "sample_s": c.sample_s, **data["metrics"]})
    print("Comparing independent solver with pvlib", flush=True)
    verification = compare_pvlib()
    print("Running timestep refinement", flush=True)
    refinement = convergence()
    write_json(OUT / "verification.json", verification)
    write_json(OUT / "convergence.json", refinement)
    write_json(OUT / "summary.json", summary)
    with (OUT / "summary.csv").open("w", newline="") as f:
        fields = ["scenario", "config_id", "controller", "step_v", "sample_s", "harvested_wh", "available_wh", "tracking_pct", "steady_ripple_pp_w", "steady_std_w"]
        w = csv.DictWriter(f, fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(summary)
    make_charts(allruns, summary)
    write_json(OUT / "manifest.json", {"schema_version": 1, "experiment_version": "1.0.0", "simulation_only": True,
        "panel": asdict(Panel()), "scenarios": [asdict(s) for s in SCENARIOS.values()],
        "configurations": configurations, "controllers": {"fixed": "Fixed voltage", "po": "Perturb & Observe", "inc": "Incremental Conductance"},
        "runs": len(allruns), "controller_runs": len(summary), "seed_policy": "Paired sensor normal sequences per scenario and sampling schedule", "playback_frame_s": 0.25,
        "verification": {k: v for k, v in verification.items() if k not in ("conditions", "voltage_grid_v")},
        "convergence": {k: v for k, v in refinement.items() if k != "rows"}})
    digests = {str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(OUT.rglob("*")) if p.is_file() and p.name != "checksums.json"}
    write_json(OUT / "checksums.json", digests)
    print(json.dumps({"runs": len(summary), "pvlib": verification["passed"], "max_current_error_a": verification["max_current_abs_error_a"],
        "convergence": refinement["passed"], "max_energy_change_pct": refinement["max_successive_energy_change_pct"]}, indent=2))
    if not verification["passed"]:
        raise SystemExit("Numerical comparison failed; inspect results/verification.json")
    # Record refinement failures as findings, then CI/tests enforce the stated bound.


if __name__ == "__main__":
    main()
