# Coupled deployment evidence (2026-11-12)

Evidence for the deployment extension of the DUST–MBDyn–preCICE route: fold geometry envelope,
aerodynamic coverage over shaft speed and fold, prescribed shaft-speed ramp, and three deployment
runs. Software and model evidence only; mechanical inputs are declared demonstration assumptions
and `physical_qualification` is false. Design and limits: `docs/coupled_dynamic_analysis.md` §13.

| File | Content | Kind |
|---|---|---|
| `hinge_geometry_study.json` | DUST's RBF point motion reproduced on the main mesh at folds 0…−90°: junction chord change, element span change, distal sweep | kinematic (no solver) |
| `section_state_map.json` | No-induction α / Re / Mach of all sections over 0…2400 RPM and 0…−45° fold at 14 m/s, against the admitted table | estimate |
| `deployment_runs_summary.txt`, `.json` | Events, fold rates, impact, rebound, coverage, checks and loads of the main (−5°) run and the three deployment runs | from sealed records |
| `deployment_wake_metrics.txt`, `.json` | Near-wake strength by band, particle counts and slipstream speed at event frames (flow companions) | DUST-computed wake |
| `frame_term_check.txt` | Independent hinge balance of the −20° ramp run with and without the rotating-frame acceleration moment | from sealed record |
| `flow_manifest_<run>.json` | Flow-companion manifests of the three deployment runs (source DUST files bound by sha256) | manifests |
| `scripts/` | The scripts that produced the files above, as run | |

Runs (raw outputs local under `outputs/coupled_runs/`): `20261112T191618_02b58b9c61` (−20°, constant
2400 RPM: stopped by DUST at the table's Mach 0.31 in the opening swing, 296 accepted windows kept),
`20261112T203049_d66ad5cd8d` (−20°, ramp 2200→2400 RPM over 0.05 s from release: completed),
`20261112T203052_6971a5d10d` (−15°, same ramp: completed). The two ramp cases were first run as
`…191622` and `…192518` during development; the review then changed the saved drive label to
`prescribed_speed_ramp`, so those records no longer restore and both cases were rerun with the final
code (identical events, rates, loads and checks to the printed precision). Only the reruns are cited.

Inputs: geometry (800 mm research template) and operating point are declared design inputs; polar
tables are retained XFOIL captures (model-derived, attached flow only); mechanics are demonstration
assumptions; the speed history is prescribed (assumed), so drive torque is an output and its impact
spikes reflect an infinitely stiff drive.
