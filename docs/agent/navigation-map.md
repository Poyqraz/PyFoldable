# Agent navigation map

Task type → first files. Read AGENTS.md, then
[current state](current-state.md) and the
[dated independent audit](onboarding-audit-2026-09-18.md) before scanning the
tree. Prefer tests next to the module.

## Orientation

| Task | Start here |
| --- | --- |
| What exists / what is next | `docs/agent/current-state.md` |
| How subsystems connect | `docs/architecture/overview.md` |
| Commands and which tests | `docs/development/commands.md` |
| Invariants / DoD | `AGENTS.md`, `docs/architecture/decisions.md` |
| Resume a long task | `docs/agent/handoff-protocol.md` |

## Canonical design and units

- Parser/SI: `pyfoldable/core/config.py`, `units.py`, `models.py`
- Schema docs: `docs/canonical_design_config.md`
- Canonical file: `configs/designs/TIP_HINGED_250_CANONICAL.toml`
- Tests: `tests/core/test_config.py`, `test_models.py`, `test_units.py`
- Do not merge with legacy `pyfoldable/models.py`

## Polars, providers, cache

- Contracts: `pyfoldable/core/providers.py`, `polar.py`, `polar_config.py`
- Orchestration/health: `polar_orchestration.py`, `polar_health.py`, `polar_family_generation.py`
- Cache/locks: `polar_cache.py`, `polar_cache_lock.py`
- Adapters: `pyfoldable/providers/xfoil.py`, `neuralfoil.py`
- Real-backend: `core/polar_real_qualification.py`, `.github/workflows/polar-real-*.yml`, `tests/fixtures/polar_real_qualification/`
- Docs: `docs/polar_configuration.md`, `docs/polar_real_backend_qualification.md`
- Tests: `tests/core/test_polar_*.py`, `tests/providers/`

## BEM / foldable rotor / motor coupling

- `pyfoldable/core/bem.py`, `bem_rotor.py`, `foldable_rotor.py`, `motor_bem_coupling.py`
- Physical gate: `core/pr06c_physical_gate.py`, `configs/ui/dashboard.toml`, `reports/pr06c_physical_gate.json`
- Tests: `tests/core/test_bem.py`, `test_bem_rotor.py`, `test_foldable_rotor.py`, `test_motor_bem_coupling.py`, `test_pr06c_physical_gate.py`

## Active draft, polar UI, chord/twist search

- Draft: `pyfoldable/application/design_draft.py`
- Analysis: `design_analysis.py`, `polar_upload.py`
- Search: `design_search.py`, `active_design_search.py`
- UI: `apps/pyfoldable_dashboard.py` (`_render_design_geometry`, `_render_active_polar_run`)
- Tests: `tests/application/test_design_draft.py`, `test_design_analysis.py`, `test_polar_upload.py`, `test_active_design_search.py`, `tests/ui/test_active_design_polar_ui.py`, `test_active_search_ui.py`
- Contract: `docs/py03_active_design_polar_ui.md`, `docs/py04_deterministic_design_search.md`

## Geometry stations, search, clearance, hardware

- Stations: `application/blade_stations.py` — `tests/application/test_blade_stations.py`, `tests/ui/test_blade_stations_ui.py`
- GEOM-01 search: `application/geometry_search.py` — **does not consume GEOM-04**
- GEOM-03/04 service: `application/surface_clearance.py`, `hardware_contract.py`, `hardware_clearance.py`
- Kernels: `geometry/surface_clearance.py`, `triangle_distance.py`, `hardware.py`
- Mesh: `visualization/propeller_25d.py`
- UI: geometry page clearance/search sections; tests `tests/geometry/`, `tests/ui/test_geometry_search_ui.py`, `test_surface_clearance_ui.py`, `test_geom04_hardware_ui.py`
- Contracts: `docs/geom02_station_contract.md`, `geom03_surface_clearance.md`, `geom04_surface_hardware.md`

## Mechanism (PY-05) vs legacy V2 dynamics

- PY-05: `dynamics/mechanism_transient.py`, `application/mechanism_transient.py`, `mechanism_binding.py`
- UI: pages `Mekanizma Geçişi` and bound checkbox on geometry
- Tests: `tests/dynamics/test_mechanism_transient*.py`, `tests/ui/test_mechanism_transient_ui.py`, `test_bound_mechanism_ui.py`
- Do not mix with legacy `dynamics/physics_*.py`, `hinge_dynamics.py`, `pyfoldable/models.py`
- Completion: `docs/py05_completion.md`

## Evidence, experiments, FEA, measurements

- Dashboard snapshot: `application/dashboard.py`, `configs/ui/dashboard.toml`
- Session import: `application/evidence_import.py` (allow-listed identities only)
- Contracts: `core/experiment_contract.py`, `fea_contract.py`, `cfd_reference.py`
- PY-06 Python APIs (no full UI): `core/measurement_comparison.py`, `motor_rotor_correlation.py`, `mechanism_observation.py`, `application/measurement_comparison.py`
- Tests: `tests/application/test_dashboard.py`, `test_evidence_import.py`, `tests/core/test_experiment_contract.py`, `test_fea_contract.py`, `test_measurement_comparison.py`, `test_motor_rotor_correlation.py`, `test_mechanism_observation.py`

## Analysis run / opening sensitivity (UI-04)

- `application/analysis_run.py`, `opening_sensitivity.py`
- Fixture: `tests/fixtures/rotor_benchmark/uiuc_apcsf_10x4.7_v1.json`
- Archive: `reports/pr06d_opening_sensitivity.json`
- Not the 250 mm draft solver

## UI / Streamlit

- Entrypoint: `apps/pyfoldable_dashboard.py`
- Theme: `.streamlit/config.toml`
- Placeholder pages: Motor–Pervane, Doğrulama ve Kanıtlar, Raporlar → `_render_planned_page`
- Tests: `tests/ui/`
- Workspace history: `docs/ui_engineering_workspace.md`

## Legacy V1/V2 reports and PyThrust slice

- Config JSON: `configs/foldable/TIP_HINGED_250_V02.json`
- Integration: `pyfoldable/integration.py`, `performance.py`, `pythrust/propellers/`, `pythrust/propulsion/`
- Reports: `reports/foldable_v2_engineering_design/`
- Examples: `examples/run_foldable_*.py`, `generate_foldable_engineering_report.py`
- Tests skip if `outputs/` CSVs missing

## Licensing / third-party

- `LICENSE`, `CLA.md`, `CONTRIBUTING.md`, `THIRD_PARTY_NOTICES.md`, `docs/licensing.md`
- Tests: `tests/test_license_policy.py`
- Synthetic propeller dir: `data/propellers/apc_202602/` (not APC data)

## CI / packaging

- `pyproject.toml`, `.github/workflows/tests.yml`
- Polar qualification workflows beside it
- PR template: `.github/pull_request_template.md`

## Auth / database / API / admin / payments

**Not present.** Do not search for them as missing features to invent.

## Unrelated open work

- Draft PR #3 `cursor/foldable-nonlinear-closing-c1e3` — leave alone unless the task is that PR.
