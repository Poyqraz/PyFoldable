# Architectural decision records

Compact recovered records, not retrospective claims about undocumented motives.
Recorded 2026-09-17 against `ca81d2d`. Accepted below means enforced/documented in
the cited repository, not newly approved by this onboarding. Append or supersede
material decisions; preserve their evidence and original scope.

## ADR-001 — Separate software evidence from physical qualification

**Status: accepted; recovered from code and contracts.**

Context: solver regression, literature context and prototype measurements answer
different questions. Decision: retain provenance, condition/revision identity,
explicit qualification gates and unknown results. A hash identifies content;
passing CI or importing data cannot authenticate measurements or promote a gate.

Consequences: PR-06C remains blocked despite numerical coverage; UI drafts,
GEOM-04 and PY-05 reports remain unqualified. The real-polar promoted baseline
has its own limited envelope; it does not qualify a project rotor. Neither the
254 mm benchmark nor a 0.70 fixture factor establishes the 250 mm target result.

Evidence: `pyfoldable/core/pr06c_physical_gate.py`,
`pyfoldable/application/surface_clearance.py`, `pyfoldable/application/evidence_import.py`,
`configs/ui/dashboard.toml`; [validation roadmap](../validation_and_development_roadmap.md),
[real-polar qualification](../polar_real_backend_qualification.md).

## ADR-002 — Python services and explicit session actions

**Status: accepted; recovered from implementation and Python-first plan.**

Decision: retain Python kernels and UI-independent application requests/artifacts.
Streamlit renders them and owns session state. Active calculations are explicit
actions; source/config changes invalidate results. Exact draft TOML and supplied
data snapshots bind runs; uploads do not overwrite canonical project evidence.
Legacy model/PyThrust paths coexist rather than being silently migrated.

Consequences: numerical workflows work without a UI, but the dashboard and some
services still depend on the checkout's configs/reports/fixtures. There is no
separate web API/database/auth layer. Python is the implementation priority for
feasible MATLAB-style numerical work; no MATLAB parity is claimed. Printing
orientation is outside this software workstream; compatible metadata is retained.

Evidence: `apps/pyfoldable_dashboard.py`, `pyfoldable/application/design_draft.py`,
`design_analysis.py`, `analysis_run.py` in that application directory,
`tests/ui/test_geometry_navigation_ui.py`;
[Python-first plan](../python_research_execution_plan.md),
[workspace contract](../ui_engineering_workspace.md).

## ADR-003 — Bounded geometry screening with explicit missing scope

**Status: accepted; recovered from GEOM-01–04 implementation.**

Decision: use the declared station/airfoil mesh, continuous interval bounds,
triangle refinement and optional source-bound finite/convex hardware. Keep motion,
precision and global work budgets explicit. Do not invent missing span or silently
rescale measured stations. Report excluded contact bands and unresolved intervals.

Consequences: 2.5D preview is not CAD. Exact triangle predicates do not establish
full-propeller collision freedom; `full_propeller_clearance` stays null. Synchronous
planar screening does not prove asynchronous or arbitrary 3D motion. GEOM-01 may
bind candidate-specific GEOM-04 evidence without changing
`surface_path_clearance` or `interblade_clearance`; those gates stay unknown.
Candidate-bound GEOM-04 evidence uses per-candidate budgets, identity-bound
artifacts and a namespaced complete report; it does not change those gates.
Reverse solid-query witnesses must preserve caller body order (PR #63 regression).

Evidence: `pyfoldable/application/blade_stations.py`, `geometry_search.py`,
`surface_clearance.py` in that application directory; `pyfoldable/geometry/`;
`tests/geometry/test_hardware_geometry.py::test_solid_distance_witnesses_follow_argument_order`;
[GEOM-02](../geom02_station_contract.md), [GEOM-04](../geom04_surface_hardware.md).

## ADR-004 — Prescribed-drive transient ends at first contact

**Status: accepted; recovered from PY-05 completion and PY-06D1 contracts.**

Decision: solve the explicit rigid tip-hinge equation with declared drive history,
mass/inertia binding and an explicitly uncalibrated smooth friction option. Stop at
the earliest within-step contact; no static holding, bounce, latch or BEM/motor
feedback is implied. Observation comparison is separate from parameter fitting.

Consequences: literature can support methods or scoped comparisons, not invent a
prototype's mass/material/drive history. PY-06D2 needs independently constrained,
identifiable parameters and frozen measured-run holdout; convergence is not validation.

Evidence: `pyfoldable/dynamics/mechanism_transient.py`,
`pyfoldable/application/mechanism_binding.py`, `pyfoldable/core/mechanism_observation.py`;
[PY-05 completion](../py05_completion.md), [PY-06 plan](../py06_calibration_uncertainty_plan.md).

## Future records

An unproven architectural interpretation must say **inferred — requires
confirmation**, with evidence and unresolved alternatives. Proposed changes are
not accepted decisions. No rationale is inferred here for why a database or
hosted service was not chosen; their absence is simply current repository reality.
