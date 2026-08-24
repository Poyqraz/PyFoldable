# AGENTS.md

## Cursor Cloud specific instructions

PyFoldable is a pure-Python scientific library (numpy/scipy, optional matplotlib)
for tip-hinged foldable propeller analysis. It also includes a Streamlit engineering
workspace under `apps/`; numerical workflows remain available through `pytest` and
the standalone scripts in `examples/`.

### Environment
- Use the virtualenv at `venv/` created by the update script. Run tools via
  `./venv/bin/python` and `./venv/bin/pytest` (the package is installed editable, so
  source edits are picked up without reinstalling).
- Requires Python >=3.10 (CI tests 3.10 and 3.11; local VM may have 3.12). System
  package `python3.12-venv` is needed to create the venv; the update script installs it.

### Lint / test / build / run
- Tests: `./venv/bin/pytest tests/ -q` (**802 passed**, 9 skipped locally after the
  UI-05A evidence-import slice; CI remains the merge authority).
- No linter is configured in this repo (no ruff/flake8/black config or deps). For a
  baseline syntax check use `./venv/bin/python -m compileall pyfoldable pythrust examples tests`.
- Build/run = executing the `examples/*.py` scripts or
  `./venv/bin/streamlit run apps/pyfoldable_dashboard.py`; see README.

### Non-obvious gotchas
- Several example scripts are a **pipeline** and must be run in order because each one
  consumes the previous one's CSV/output under `outputs/` (they print a clear
  "Run examples/X first." message when a prerequisite is missing). Working order:
  `run_design_variant_sweep` → `run_design_variant_summary` →
  `run_design_variant_decision_matrix`; and
  `run_moment_kinematics_validation` → `run_foldable_visuals`;
  `run_deployment_diagnostics` → `generate_foldable_engineering_report`.
- `examples/run_foldable_sweep.py` uses `reference_scaled` thrust mode and loads the
  first-party synthetic software fixture to supply `fixed_thrust_n` per RPM (hover
  J=0). It is not physical qualification evidence. The legacy path
  `data/propellers/apc_202602/` remains temporarily stable.
- Standalone quick-start scripts (no pipeline): `run_foldable_sweep`, `run_foldable_operating_point`,
  `run_prescribed_rpm_physics`, `run_cfd_preparation`.
- Generated artifacts land in `outputs/` (gitignored) and `reports/`.
