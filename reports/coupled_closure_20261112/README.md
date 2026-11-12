# Coupled-route release-closure review package (2026-11-12)

Compact evidence for the `continuous_rbf` DUST–MBDyn–preCICE route on
`feature/dust-mbdyn-precice-coupling`. Raw run directories (0.2–0.8 GB each) stay local under
`outputs/coupled_runs/<run id>` and `~/pyf-work/{runs,diag}`; this package holds extracted
values, manifests, digests, scripts and one sealed record. Integrity: `SHA256SUMS`.
Software evidence only: mechanical inputs are declared demonstration assumptions and
`physical_qualification` is false.

| Path | Content |
|---|---|
| `toolchain/manifest_pre_upgrade.json`, `manifest_post_upgrade.json` | Toolchain manifests before/after the 2026-11-12 Ubuntu unattended upgrade (only the coupling-interpreter hash differs; libgfortran5 is not hashed by the manifest) |
| `toolchain/replay_comparison.json` | Byte comparison of the repeated split_rigid locked-open run before/after the upgrade |
| `toolchain/run_environment_binding.json` | Every coupled run bound to the manifest it copied at start, with status and sealed `result_sha256`; standalone runs with binary hash, input hashes and whether they ran before or after the upgrade |
| `topology_control/per_revolution_means.json` | Static latched −0.5° fold vs open: two-line layout (+22–25 %) and continuous line (−0.2 %), per revolution |
| `rbf_discrepancy/element_states.json` | Per-element α, sectional speed, spanwise velocity, projected velocity, Γ, cl, dFz at result 0 and 300 for standalone stock, standalone diagnostic build, coupled rbf, and the two-line standalone/rigid-coupled pair; coupled written geometry |
| `rbf_discrepancy/rotor_loads_per_output.csv`, `matched_means.json` | Thrust/torque per output for standalone stock, diagnostic build and coupled rbf (one arithmetic; coupled values equal the sealed record), last 1 and 2 revolution means |
| `rbf_discrepancy/geometry_timing_velocity.json` | Coupled geometry vs reference (rigid-fit residual, azimuth vs window time) and MBDyn node speed vs Ωr at 5° and 2.5° |
| `rbf_discrepancy/dust-ubcen.diagnostic.patch` | The single-line DUST change used for the diagnostic standalone build (lifting-line `ub` at the leading-line midpoint). Diagnostic only; never used for production runs. DUST is MIT-licensed (copyright and permission notice in its `license.md`); this patch excerpt is redistributed under that licence |
| `spacing_sensitivity/summary.json` | Released runs with coupling-node spacing ×1, ×0.5, ×2 at fixed aerodynamic discretization |
| `release_case/<run id>.json.gz` | Sealed main release record (`continuous_rbf`, 2.5°, 720 windows); opens in the research workspace (*Karşılaştırma / kayıtlar → Önceki sonuç JSON’unu aç*) with full re-verification |
| `release_case/summary.json` | Averaging windows (latched, three revolutions after release), the locked-open 5° and the 5° release reference |
| `scripts/` | Diagnostics and the package builder, as run (paths refer to the local layout) |

## Reproduce (WSL, repository root, toolchain from `tools/coupled/build_toolchain.sh`)

```bash
P=~/pyf-work/opt/coupling-venv/bin/python   # has h5py
S=reports/coupled_closure_20261112/scripts
$P $S/rbf_geo.py ~/pyf-work/runs/sa_cont_s5_d150/dust outputs/coupled_runs/20261112T073117_fab3a9a152/dust
$P $S/rbf_ub_predict.py ~/pyf-work/runs/sa_cont_s5_d150/dust outputs/coupled_runs/20261112T073117_fab3a9a152/dust 300
$P $S/rbf_diag.py ~/pyf-work/diag/runs/sa_cont_s5_d150_ubcen outputs/coupled_runs/20261112T073117_fab3a9a152/dust 0 300
$P $S/dust_loads.py ~/pyf-work/runs/sa_cont_s5_d150/dust 72 1
$P $S/rbf_motion_closure.py outputs/coupled_runs/20261112T071200_20d4a1092d 6
python3 $S/summary_windows.py
```

Diagnostic build: copy the pinned DUST source, apply `dust-ubcen.diagnostic.patch` to
`src/geo/mod_geo.f90`, configure with `-DWITH_PRECICE=NO` into a separate prefix, and run it
on the inputs of `sa_cont_s5_d150` (byte-identical `geo_input.h5` and `dust.in`).

## Findings in one paragraph

Geometry, section frames, adapter transformations and timing are exact. The coupled
continuous line's −1.42 % thrust (locked open, 5°) against standalone DUST comes from DUST
3b1d2e61's rbf branch evaluating the lifting-line body velocity at the leading line instead of
the control point: the diagnostic standalone build with only that change gives −1.79 % and
matches the coupled per-element α to 0.003–0.013°; the +0.38 % remainder is not isolated
(MBDyn's +0.113 % node speed at 5° is a candidate for part of it). Not corrected; no multiplier. The bias during fold motion and at
2.5° has not been measured (see the design doc, §9 "Located" and §10).
