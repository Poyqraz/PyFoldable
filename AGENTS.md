# AGENTS.md

## Cursor Cloud specific instructions

PyFoldable is a pure-Python scientific library (numpy/scipy, optional matplotlib)
for tip-hinged foldable propeller analysis. There is no server, database, or GUI —
work happens through `pytest` and the standalone scripts in `examples/`.

### Environment
- Use the virtualenv at `venv/` created by the update script. Run tools via
  `./venv/bin/python` and `./venv/bin/pytest` (the package is installed editable, so
  source edits are picked up without reinstalling).
- Requires Python >=3.10 (CI VM has 3.12). System package `python3.12-venv` is needed
  to create the venv; the update script installs it.

### Lint / test / build / run
- Tests: `./venv/bin/pytest tests/ -q` (≈197 pass, a few skips).
- No linter is configured in this repo (no ruff/flake8/black config or deps). For a
  baseline syntax check use `./venv/bin/python -m compileall pyfoldable pythrust examples tests`.
- Build/run = executing the `examples/*.py` scripts; see README "Quick start".

### Non-obvious gotchas
- Several example scripts are a **pipeline** and must be run in order because each one
  consumes the previous one's CSV/output under `outputs/` (they print a clear
  "Run examples/X first." message when a prerequisite is missing). Working order:
  `run_design_variant_sweep` → `run_design_variant_summary` →
  `run_design_variant_decision_matrix`; and
  `run_moment_kinematics_validation` → `run_foldable_visuals`;
  deployment diagnostics → `generate_foldable_engineering_report`.
- `examples/run_foldable_sweep.py` currently fails with
  `ImportError: cannot import name 'evaluate_sweep' from 'pyfoldable'`. This is a
  pre-existing source bug: `evaluate_sweep`/`evaluate_sweep_row` are listed in
  `pyfoldable/__init__.py` `__all__` but never imported there (they live in
  `pyfoldable.performance`). It is NOT an environment problem. Other examples work.
- Generated artifacts land in `outputs/` (gitignored) and `reports/`.
