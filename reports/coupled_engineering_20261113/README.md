# Engineering reading of the deployment records (2026-11-13)

Which coupled deployment outputs are stable enough to compare, which can support preliminary
decisions once the mechanics are measured, and which remain illustrative. All files come from the
sealed records of `reports/coupled_deployment_20261112/` restored with `coupled_analysis.load_result`
(no coupled solver run) and from direct diagnostic XFOIL calls. Software and model evidence only;
mechanics are demonstration assumptions; `physical_qualification` is false. Discussion:
`docs/coupled_dynamic_analysis.md` §14; plan: `docs/prototype_measurement_plan.md`.

| File | Content | Kind |
|---|---|---|
| `engineering_assessment.txt`, `.json` | Per run: first-contact events (impact rate and energy vs the centrifugal bound, contact impulse balance, apparent restitution, peak stop torque vs the undamped estimate), shaft angular-momentum exchange, output classes; analytic sensitivities to each mechanical input; fold limits of the aerodynamic representation for other tolerances | from sealed records + scaling laws |
| `cell_polar_sensitivity.json` | Direct XFOIL (same pinned executable and settings as deploy-v3), with the family's 2° sequence at Re 130k–160k × Mach 0.085–0.10 and with the run's own angles −2…0°, against DUST's interpolation of the run's own C81 file (sha256-checked); first-order thrust estimate for the 1600 RPM run with its inputs (strip widths, cell windows, RPM range, load share) | diagnostic, never admitted |
| `scripts/` | The scripts as run | |

Key results: contact impulse balance 0.03–0.11 % (the 16–19 % pointwise residual is a differencing
artefact at the non-smooth stop law); impact energy 0.85–0.95 of m Ω² r_h c_g (1 − cos θ₀); across
the contact the shaft's net angular impulse equals the distal momentum change to ≤ 0.6 % (2.6 % with an
11 RPM speed change); the opening swing carries the opposite-sign impulse (+0.05…+0.24 N·m·s against
−0.07…−0.32 N·m·s across the contact, which scales with 1 + e); every contact spans 10 windows
(≈ 1.74 ms); peak drive torque ≈ 1.9 × impulse / duration (time-step dependence untested); in the
1600 RPM interpolation cell the table differs from direct XFOIL by ≤ 0.033 in cl in the run's α range,
a first-order thrust change of 0.13 N with induction frozen (the hinge moment changes only through
induction, not estimated).

Reproduce (WSL, from the repository root): `./venv/bin/python
reports/coupled_engineering_20261113/scripts/engineering_assessment.py <out.json>` (needs the run
folders under `outputs/coupled_runs/`), and `cell_polar_sensitivity.py <out.json>` (also needs the
local XFOIL preflight of `reports/coupled_deploy_polars_20261112/`).
