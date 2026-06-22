# PyFoldable

Standalone export of the foldable propeller analysis stack from
[PyThrust](https://github.com/Poyqraz/PyThrust) branch
`cursor/foldable-propeller-v1-2fe0`.

Ayrı GitHub reposu kurulumu: `REPO_SETUP.md`

## Scope

- V1 kinematics, effective diameter, design sweeps, decision matrix
- V2 hinge dynamics, split thrust, motor-coupled performance
- Engineering design report + Level-1 CFD preparation exports
- Minimal vendored `pythrust.propellers` + `pythrust.propulsion` for operating-point coupling

**Not included:** PyThrust core changes, OpenMDAO, full propeller database, CFD solver runs.

## Install

```bash
pip install -e ".[dev,plot]"
```

## Quick start

```bash
python3 examples/run_foldable_sweep.py
python3 examples/generate_foldable_engineering_report.py
python3 examples/run_cfd_preparation.py
```

## Tests

```bash
pytest tests/ -q
```

## Key results @ 7100 rpm (model)

| Metric | Value |
|--------|-------|
| root_only_20cm | ~3.73 N |
| foldable pretest | ~6.37 N |
| fixed 25cm reference | ~9.10 N |
| gain vs compact root | ~+70.9% |

See `reports/foldable_v2_engineering_design/` for the full engineering report.

## License

Apache-2.0 (see LICENSE).
