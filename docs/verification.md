# Verification summary

All results below were computed by the included workflow.

* Numerical comparison: **PASS** — 5,050 signed-current points against pvlib 0.13.1.
* Maximum current absolute error: **9.803713e-12 A**; acceptance 1e-8 A + 1e-8 × |reference|.
* Maximum MPP power/voltage errors: **1.575298e-10 W / 3.595584e-07 V**; acceptance 1e-5 W / 1e-4 V.
* Timestep refinement: **PASS** — 15 scenario/controller combinations, three timesteps; maximum successive energy difference **0.004293%**, acceptance 0.5%.
* Published experiments: **54 complete configurations / 162 controller traces**, 1,201 timestamps per trace. All core metrics are recalculated from trace files in tests; full CSV archive is checked against JSON.
* Engineering test execution: see [test-results.xml](test-results.xml). Browser execution and viewport details: [browser-qa.json](browser-qa.json).

[Technical report](report.md) · [Exact method and grid](methodology.md) · [Verification JSON](../results/verification.json) · [Convergence JSON](../results/convergence.json)

Numerical comparison with pvlib tests a shared mathematical model. It is not physical validation. The aggressive cloud P&O controller failure remains a documented finding, not a numerical verification failure.
