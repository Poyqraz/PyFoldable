# Development contract

Run from the repository root. Authority: [pyproject.toml](../../pyproject.toml),
[Tests workflow](../../.github/workflows/tests.yml),
[README](../../README.md). No npm/Poetry/uv workspace or dependency lockfile is
tracked. Runtime dependency ranges are not a frozen scientific environment.

## Installation and commands

For a new environment (reuse a healthy existing environment instead):

```bash
python -m venv venv
./venv/bin/python -m pip install -e ".[dev,plot,ui]"
./venv/bin/python -m pip check
```

Python >=3.10; CI uses 3.10 and 3.11. Linux may need its Python venv package;
the repository does not include a machine provisioning/update script. On Windows
use the [README's PowerShell commands](../../README.md#kurulum) and the same
interpreter for pip, tests and Streamlit. Avoid mixing Conda base with another
environment's NumPy/PyArrow binaries.

| Operation | Canonical command / status |
| --- | --- |
| Full CI-equivalent test invocation | `./venv/bin/python -m pytest tests/ -q` |
| Focused tests | Same command with the affected test paths instead of `tests/` |
| Workspace | `./venv/bin/python -m streamlit run apps/pyfoldable_dashboard.py` |
| Syntax check | `./venv/bin/python -m compileall -q pyfoldable pythrust apps examples tests` |
| Whitespace check | `git diff --check` |
| Package build when packaging changes | `./venv/bin/python -m pip wheel --no-deps --wheel-dir outputs/wheels .` (PEP 517 setuptools backend from `pyproject.toml`; not a required ordinary CI step) |
| Lint / format / static typecheck | No configured command/tool/gate; do not report these as passed |
| Browser E2E | No configured browser-driver suite; real Streamlit AppTest lives in `tests/ui/` |
| DB migrations/reset, code generation | Not applicable; no database or generated schema pipeline |
| Production deployment/build | No repository deployment recipe; Streamlit launch is not a hardened hosted service |

The existing pytest command is the single canonical verification entry point;
no duplicate `ci.sh` wrapper is needed. Packaging is separate from source-checkout
workspace execution: configs/reports/test fixtures/apps are not all wheel data.

## Test selection and Definition of Done

| Changed boundary | First relevant tests |
| --- | --- |
| Units/config/polars/BEM/evidence | Corresponding `tests/core/test_*.py`; inspect application consumers |
| Backend execution/cache/health | `tests/providers/`, relevant `tests/core/test_polar_*.py` |
| Mechanism equations/first contact | `tests/dynamics/test_mechanism_transient*.py`, `tests/application/test_mechanism_binding.py`, transient service tests |
| Draft, station, source identity | `tests/application/test_design_draft.py`, `test_blade_stations.py`, service tests and related `tests/ui/` |
| Mesh/clearance/hardware | `tests/geometry/`, `tests/visualization/test_propeller_25d.py`, hardware/clearance service tests, corresponding UI tests |
| Streamlit lifecycle | Relevant `tests/ui/`; include navigation and source-change invalidation, not just initial render |
| Licensing/package metadata | `tests/test_license_policy.py`; build only when packaging changes |
| Documentation only | Verify every new path/link, command evidence, state/claim against code; inspect diff for accidental behavior or archived-report changes |

For behavioral work, record RED → GREEN and useful analytical/invariant tests.
UI changes require AppTest and actual Streamlit startup/root/health verification.
Unit-test doubles, passing imports and HTTP 200 do not replace each other.
`pytest` includes unit, integration and AppTest cases; no separate integration
marker command is configured. Some legacy tests skip without generated CSVs or
reference data; report actual skip reasons (`-rs`) instead of treating absence as
verification. Do not fabricate data to eliminate skips.

After affected checks, obtain independent automated review, fix findings, update
contracts, inspect final GitHub feedback and successful **exact-head** CI. Verify
the merged tree matches the tested tree. Documentation-only work need not rerun
the full suite locally when the required CI does so. Contribution/CLA requirements
remain in [CONTRIBUTING](../../CONTRIBUTING.md); scientific validation remains
separate from engineering software completion.

## Examples and generated outputs

Standalone quick starts from README:

```bash
./venv/bin/python examples/run_foldable_sweep.py
./venv/bin/python examples/run_foldable_operating_point.py
./venv/bin/python examples/run_prescribed_rpm_physics.py
./venv/bin/python examples/run_cfd_preparation.py
```

These use scoped example/reference inputs, not proof of prototype performance.
In particular the sweep's `reference_scaled` hover input comes from the first-party
synthetic fixture in the historically named `data/propellers/apc_202602/` directory.

Pipeline order (each item is an `examples/<name>.py` script):

- `run_design_variant_sweep` → `run_design_variant_summary` → `run_design_variant_decision_matrix`.
- `run_moment_kinematics_validation` → `run_foldable_visuals`.
- `run_deployment_diagnostics` → `generate_foldable_engineering_report`.

Read a script's input checks before invoking it: downstream tools can additionally
require earlier operating-point/physics outputs. `outputs/` is ignored; `reports/`
contains tracked artifacts too. Never stage regenerated reports indiscriminately.

## Optional solvers, CI and environment

Ordinary tests install `[dev,plot,ui]`, not real XFOIL/NeuralFoil. NeuralFoil is
optional (`[neuralfoil]`, supported range in the manifest). XFOIL is a separately
installed executable passed to `XfoilProvider` or resolved via `PATH`; config
parsing does not start it. See [polar configuration](../polar_configuration.md).

- `tests.yml`: full suite on PRs targeting main and pushes to main/`cursor/**`.
- `polar-real-qualification.yml`: path-filtered/manual real-backend capture and
  promoted-baseline regression; pinned XFOIL source SHA/build flags and NeuralFoil
  0.3.3. It downloads/builds third-party code and uploads evidence bundles.
- `polar-real-reproducibility.yml`: manual comparison of two distinct run artifacts,
  with manifest/digest checks. Promotion semantics are documented in
  [real-backend qualification](../polar_real_backend_qualification.md).

No project API key or `.env` variable is required for ordinary local development.
The following names belong to solver discovery or workflows, not a new app config:

| Variable | Purpose / requirement / local behavior |
| --- | --- |
| `PATH` | Optional XFOIL discovery when no explicit executable path is supplied |
| `XFOIL_SOURCE_URL`, `XFOIL_SOURCE_SHA256`, `XFOIL_FORTRAN_FLAGS` | Qualification workflow source/build pins; not required by the application |
| `XFOIL_BIN`, `XFOIL_BUILD_ID`, `OSMAP` | Workflow-built solver path/identity and XFOIL data location; workflow sets these; Python adapter receives executable explicitly |
| `GITHUB_SHA`, `RUNNER_TEMP`, `GITHUB_ENV`, `GITHUB_PATH` | GitHub runner metadata/paths used by qualification setup; absent locally unless caller supplies them |
| `FIRST_RUN_ID`, `SECOND_RUN_ID` | Reproducibility workflow inputs, required and validated distinct numeric IDs |
| `STEPS_JSON`, `SOURCE_REVISION`, `WORKFLOW_RUN_ID`, `WORKFLOW_RUN_ATTEMPT` | Failure-evidence metadata inside the qualification workflow |

`${{ github.token }}` is runner-supplied for artifact download; never persist or
print it. Source configs use explicit policy fields, not a feature-flag service.

## Security boundaries

No application login, tenant authorization, admin role or production deployment
policy is present. Do not assume network exposure is safe merely because local
Streamlit starts. Treat execution/configuration access as trusted operator access.

- Dashboard evidence paths must stay inside the resolved repo root
  (`application/dashboard.py::_inside_repo`). Other trusted Python/CLI file APIs
  are not a universal filesystem sandbox.
- Uploaders accept bounded declarative data, not executable code. Limits and
  strictness vary by contract: inspect `application/evidence_import.py`,
  `polar_upload.py`, `blade_stations.py`, `hardware_contract.py` before changing one.
  The existing CFD/FEA/experiment inspector accepts specific canonical contracts;
  it is not a universal ANSYS/raw-measurement importer.
- XFOIL uses an argument-list subprocess, an isolated temporary directory and
  timeout (`providers/xfoil.py`); executable selection remains trusted code/config.
- Cache JSON and OS locks have atomicity/ownership/symlink checks
  (`core/polar_cache.py`, `polar_cache_lock.py`). Do not replace them with ad-hoc
  file writes or swallow cache errors into a successful fallback.
- No secret values, private keys or production data belong in handoffs, reports,
  repository dumps or logs. Preserve source-license boundaries in
  [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES.md).
