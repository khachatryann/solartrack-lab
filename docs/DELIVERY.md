# Delivery record — 2026-10-19 (Asia/Yerevan)

## Published and verified

* Public repository: [khachatryann/solartrack-lab](https://github.com/khachatryann/solartrack-lab), a new repository separate from OpenCore Lab.
* Working public demonstration: [SolarTrack Lab](https://khachatryann.github.io/solartrack-lab/).
* First complete numerical/browser/deployment workflow: [successful run 39288599578](https://github.com/khachatryann/solartrack-lab/actions/runs/39288599578), model/dashboard source commit `602793f`.
* Public-browser execution evidence: [public-qa.json](public-qa.json), recorded after the deployment completed. It verifies HTTP 200, numerical verification data, changed scenario/configuration against generated metrics, a 3603-row CSV download, mobile playback and the methodology deep link. No public script errors were observed.

The subsequent delivery commit adds the reusable public-deployment check and this evidence record; it does not change the model, controller, data, or dashboard implementation tested above. No publication step remains outstanding.

## Delivered contents

* Independent single-diode model, three sensor-only controllers, causal voltage actuator, reproducible experiment runner and separate oracle/metrics.
* 54 environment/tuning configurations, 162 controller traces, six scenarios, all recorded seeds, full-resolution CSV and JSON, IV-curve frames, charts, checksums and numerical comparisons.
* Static dashboard with configuration selection, recorded play/pause/reset, exact frame inspection, five time-series signals, P–V/I–V curves, decision explanations, sensor table, parameter sweep and downloads.
* Complete technical report, equation/metric definitions, beginner learning guide, system/control-loop diagrams, source/license attribution and AI-assistance statement.
* Dependency locks, build/generation scripts, automated tests, browser/public QA scripts and GitHub Actions/Pages deployment.
* [Desktop screenshot](screenshots/desktop.png), [desktop viewport](screenshots/desktop-viewport.png), [mobile screenshot](screenshots/mobile.png).

The local delivery archive also includes `dist/`, a prepared static demo. It can be served with `python -m http.server 8000 --directory dist` without installing simulation dependencies. The Git repository omits `dist/` because it is rebuilt from committed source and data.

## Executed verification

* Local engineering suite: **35 passed**; [execution record](test-results.xml).
* Browser QA: **14 checks passed**, including all 54 real configuration selections; [browser evidence](browser-qa.json). Viewports: 375, 390, 768 and 1440 CSS pixels. Mobile is Chromium viewport emulation, not physical-device testing.
* Public deployment QA: **7 checks passed**; [public evidence](public-qa.json).
* pvlib comparison: **5,050 points**; maximum absolute current error **9.803713 × 10⁻¹² A**, tolerance 10⁻⁸ A + 10⁻⁸ × |reference|.
* MPP maximum absolute errors: **1.575298 × 10⁻¹⁰ W**, **3.595584 × 10⁻⁷ V**; tolerances 10⁻⁵ W, 10⁻⁴ V.
* Timestep refinement: **15 scenario/controller cases**, 0.05 → 0.025 → 0.0125 s; maximum successive harvested-energy difference **0.004293%**, threshold 0.5%.
* Every published metric is recalculated from its actual trace by tests; full CSV/JSON consistency, checksums and oracle isolation pass.

## Findings and remaining limitations

Fixed voltage beats both adaptive trackers in the default cloud scenario (98.4064% versus 94.2548%). Both trackers outperform the fixed reference when cell temperature rises under the chosen profile. Neither tracking algorithm wins every matched comparison.

Aggressive 1.2 V / 0.10 s P&O under clouds reaches a zero-current operating reference and stays there under its low-current hold policy; efficiency is 31.2896%. This controller/actuator-abstraction failure is retained and diagnosed in the report. Adding anti-windup or a low-current reacquisition scan is future work, not a hidden change to the experiment.

The panel parameters are illustrative and unfitted. There are no physical measurements or physical validation. Numerical agreement with pvlib compares implementations of a shared mathematical model. The actuator is idealized; converter switching, losses, passive terminal-voltage clamping, thermal dynamics, partial shading and bypass diodes are absent. Noise sensitivity uses one Gaussian realization. Refinement checks finite energy sensitivity at representative default settings, not universal stability. Read [methodology.md](methodology.md) and [report.md](report.md) for the precise boundaries.
