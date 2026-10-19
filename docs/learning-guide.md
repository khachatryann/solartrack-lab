# Learning guide: move the operating point

You do not need hardware or an account. Open the [public demonstration](https://khachatryann.github.io/solartrack-lab/) or follow the README's local setup.

## 1. Read the two curves

A solar panel's voltage and current cannot both be chosen freely. At a fixed sunlight level and cell temperature, the current–voltage (I–V) curve tells you the model's available current at each voltage. Multiplying voltage by current gives the power–voltage (P–V) curve. Its peak is the maximum power point (MPP). A controller tries to operate near this peak using measured voltage and current.

In this project, “tracking” means following that electrical peak. It does not mean mechanically pointing a panel at the sun.

## 2. Start with constant sunlight

Keep the 0.6 V step and 0.25 s sample interval. Reset the timeline and press Play. Each controller begins at 24 V. Fixed voltage slews toward 32 V. P&O and INC take small steps. Watch the P–V operating points move up the curve. The dashed oracle is an evaluation reference that controllers cannot see.

Pause near 50 s. Hide the fixed-voltage line to compare the adaptive traces. They can overlap: do not assume an overlapping line means data is missing. Read “Why did it move?” and expand the electrical-values table. True readings and sensor readings are identical in this clean scenario.

## 3. Follow a changing environment

Choose Drop & recovery. Move to 19.75, 20 and 20.25 s. Current/power change abruptly when light drops; the best voltage changes less dramatically for this parameter set. A recovery time of zero means the operating point already satisfies the 98%-for-2-s criterion. It does not mean perfect, instantaneous tracking.

Choose Passing clouds. The fixed baseline can beat a tracker because changing light confuses sampled power comparisons. At 1.2 V / 0.10 s, P&O has a severe recorded failure: its command outruns the actuator and eventually reaches a zero-current operating reference, where its simple low-current guard holds. Inspect the decisions after 20 s. This is useful evidence about an implementation limit, not a favorable example to hide.

## 4. Explore the tuning trade-off

Click cells in the parameter sweep. A small step can reduce power ripple, but reaching the peak may take longer. A large step with rapid sampling can request motion faster than the 8 V/s actuator can supply. The controller then reasons from readings taken before its last command was fully reached.

Compare 0.2 V / 0.50 s and 0.6 V / 0.10 s. Read the full-run efficiencies and the fixed steady-window ripple. One number cannot explain startup, oscillation and changing-light behavior together.

## 5. Separate noise from the plant

Choose Noisy sensors. Here σV = 0.12 V and σI = 0.04 A. The plant still has exact simulated voltage/current; only controller measurements receive noise. Expand the table to see the difference. Compare constant sunlight with the same settings. The true power ripple grows because noisy decisions move the operating point; the plotted power itself is not artificially sprinkled with sensor noise.

## 6. Check the energy calculation

Power is an instantaneous rate in watts. Energy accumulates over time. A 10 W source for 1 hour supplies 10 Wh. These 60 s experiments collect only a few Wh. Download the selected CSV, filter to one controller, and calculate trapezoidal energy:

```text
sum[(Pnext + Pnow)/2 × (tnext − tnow)] / 3600
```

Do the same for oracle power. Divide harvested by available energy and multiply by 100 to reproduce the displayed tracking efficiency. Converter efficiency is not modeled.

## 7. Change the source responsibly

1. Read `docs/methodology.md` and the small controller package.
2. Add a controlled-input test before introducing filtering, anti-windup or a low-current scan.
3. Rerun the whole scenario/tuning matrix, not just the setting that improved.
4. Rerun pvlib verification and timestep refinement after numerical changes.
5. Publish the failing cases and explain whether comparisons still have equal constraints.

Questions to investigate: How does filtering trade delay against noise? Can waiting for actuator arrival improve aggressive settings? Can a safe low-current scan recover without mistaking darkness for a high-voltage operating reference? How does a truly characterized commercial panel change the conclusions? Partial shading requires module/submodule and bypass-diode modeling; changing one irradiance number cannot represent it.
