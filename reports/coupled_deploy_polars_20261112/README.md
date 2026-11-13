# Widened attached-flow NACA2412 polars for deployment (2026-11-12)

Evidence for the second retained NACA2412 family in `data/research_reference/axial_800_store`:
`research_axial_800_deploy_xfoil_v3:NACA2412`, version `2026-11-12-deploy-v3`, content
`418d7d65d227df9f9bdcd9195f86531dd99fa29e6c23b8804f5223425748c222`. It widens the attached-flow
grid of the 2026-11-11 family in Reynolds and Mach so coupled deployment cases can run at lower
shaft speed and with larger opening swings. Unqualified numerical evidence (XFOIL), not measured
data; `physical_qualification` is false. More XFOIL coverage does not establish validity in
separated flow: the angle grid stays −6…8°, as in the 2026-11-11 family.

## Build

XFOIL 6.99 from MIT's `xfoil6.99.tgz` (sha256 `5c025064…ebe40`, verified), built with the
recipe of `.github/workflows/polar-real-qualification.yml` (`-O2 -fdefault-real-8
-fallow-argument-mismatch`, no FPE traps) and GNU Fortran 11.4.0 on WSL2 Ubuntu 22.04. Executable
`d1076680…136a7`; OSMAP `2f6b3c63…948c4` (byte-identical to the 2026-11-11 capture's). This is a
different executable from the 2026-11-11 capture (`2b952bd2…`, GNU Fortran 14.2.0 on Debian), so
the new grid is a separate family and no 2026-11-11 cell is mixed into its table.
`build/`: build record, the build script as run, and hashes of the preflight package (the
executable itself is not redistributed here).

## Declarations and outcomes (all retained)

| Protocol | Grid | Outcome |
|---|---|---|
| `configs/polars/RESEARCH_AXIAL_800_DEPLOY_V1.json` | Re 100k,130k,165k,245k,330k,400k × Mach 0.05,0.10,0.20,0.31,0.36; 160 iterations | Cells 0–3 complete; stopped at cell index 4 (zero-based; Mach 0.05, Re 330k): α 6° not converged (XFOIL `VISCAL: Convergence failed`), α 4° and 8° converged. `evidence_v1_failed/` |
| `…_DEPLOY_V2.json` | same, 300 iterations | Stopped at the same point: the iteration cap was not the cause. `evidence_v2_failed/` |
| `…_DEPLOY_V3.json` | Re 100k,165k,245k,330k,400k × Mach 0.07,0.10,0.31,0.36; 160 iterations | 20/20 cells complete, 160/160 points converged (expected by construction after the pre-screen below); lift signs as the conditional BEM scan requires. Installed. `evidence_v3/`, `store_registration_v3.json` |

Between V2 and V3 a **diagnostic, non-retained** convergence map of this executable
(`convergence_map.json`, script `scripts/xfoil_convergence_map.py`) was run over Re 100k–400k ×
Mach 0.05–0.36 for the 2° and a 1° angle sequence: 8 of 72 cell sweeps had one isolated
non-converged angle inside the attached range (2° sequence: Mach 0.05/Re 330k, 0.10/130k,
0.20/165k, 0.20/400k; the 1° sequence fails at other points). XFOIL is deterministic for a fixed
executable and input, so these are properties of this build at these states. V3's levels avoid
them while still covering the declared targets; the selection is by solver convergence, not by
coefficient values. Consequences: three non-converging states (Mach 0.10/Re 130k, 0.20/165k,
0.20/400k) lie inside the table's hull and are bridged by linear interpolation, so the table can
look smoother there than the solver's behaviour (a non-converging point can indicate transition or
bubble trouble); Mach interpolation 0.10–0.31 is as coarse as in the 2026-11-11 table, and Re is
interpolated linearly over 100k–165k. The application shows this caveat next to the version
choice. The map is diagnostic: its raw outputs are not retained (rerunning the script with the
same executable reproduces it).

## Cross-build reproducibility

`cross_build_comparison.json` (script `scripts/cross_build_compare.py`): at the six cells both
families share (Re 165k/245k/330k × Mach 0.10/0.31, 48 points), CL, CD and CM of the new build
are identical to the retained 2026-11-11 values to the precision XFOIL writes: for this recipe
and these cells, the two builds (GNU Fortran 11.4 / 14.2) reproduced the same polars. This does not
show build independence elsewhere.

## Coverage of the deployment targets

Declared in the protocol and checked by `tests/application/test_research_deploy_protocol.py`
with the application's own no-induction estimates (14 m/s, demonstration mechanics):
release from −22.5° at a constant 2400 RPM (opening-swing tip Mach ≤ 0.354, Re ≤ 3.59e5) and a
release from −20° at 1600 RPM during a 1600→2400 RPM ramp (α ≥ −3.98°, root Re ≥ 1.32e5, root
Mach ≥ 0.082). The coupled runs with this table (`…220252`, `…220255`, control `…220258`) completed;
their results are in `reports/coupled_deployment_20261112/` and `docs/coupled_dynamic_analysis.md` §13.

## Reproduce

```bash
./venv/bin/python examples/research_deploy_polar_data.py freeze --evidence <new-dir>
./venv/bin/python examples/research_deploy_polar_data.py capture --evidence <new-dir> --profile NACA2412 --preflight <preflight>
./venv/bin/python examples/research_deploy_polar_data.py install --evidence <new-dir> --profile NACA2412 --store <store>
```

The preflight must hold `bin/xfoil`, `runtime/osmapDP.dat` and `build/build-record.json` with the
hashes the protocol pins (`scripts/make_xfoil_preflight.sh` produced it). The three operator
folders `evidence_v1_failed/`, `evidence_v2_failed/` and `evidence_v3/` are kept complete (frozen
requests and scripts, every started cell's raw XFOIL capture, outcome, checksums); each re-verifies
against its own declaration (`tests/application/test_research_deploy_protocol.py`), as long as
`pyfoldable/providers/xfoil.py` is unchanged (its sha256 is part of the plan). The launcher installs
only V3; V1/V2 are verify-only. The retained runtime and capture records keep the operator's
absolute paths unchanged because they are hash-bound.
