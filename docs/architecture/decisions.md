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
Preparation `ArithmeticError` aborts the search rather than becoming a failed
grid row. Attached evidence must match the GEOM-04 query/interval producer
fields; malformed reports abort before oversize classification.
Reverse solid-query witnesses must preserve caller body order (PR #63 regression).

**Amendment 2026-09-22 — negative clearance policy v1.** The PR #67 evidence
attachment above is unchanged: accepted reports stay immutable and, with no
policy, both surface gates stay unknown. A separate opt-in declaration,
`geom01_negative_clearance_v1`, may set `surface_path_clearance` or
`interblade_clearance` to `False` from a qualifying witness on the accepted
report. v1 has no `True` result. Same-blade root/tip and a `hardware_surface`
body whose binding is `hub` and whose geometry kind is `finite_cylinder` can
reject the surface-path gate; retained interblade pairs can reject the
interblade gate. Infinite-cylinder fallback, contact-only observations,
general hardware and hardware pairs do not. Threshold and motion domain must
match exactly or both gates stay unknown. This is screening, not physical
qualification.

**Correction 2026-09-23.** A producer `violation` proves the threshold only
when the query-level witness and the single violation-interval witness are
exactly equal and strictly less than `required_clearance_m`. Hardware identity
follows producer position: `hardware_surface` is surface then hardware body,
`hardware_pair` is two hardware bodies, and hub is surface then
`hub_envelope`. Enabled policy request provenance is
`negative_policy_may_set_clearance_constraints_false_never_true`; a disabled
or absent policy keeps
`evidence_only_does_not_alter_geom01_constraints`. Final
`surface_path_clearance=False` records
`surface_path_clearance_status=negative_clearance_policy_relevant_violation`.
`None` leaves `unknown_no_swept_surface_collision_model`. Contradictory
violation evidence aborts; it does not become unknown.

**Clarification 2026-09-23 — positive readiness is not a decision.**
`geom01_positive_readiness_v1` is an optional diagnostic over the final
accepted GEOM-04 state. It does not replace this ADR and it does not authorize
`True`. `preconditions_satisfied` means only that the evidence meets the
prerequisites declared by that question. The current numerical open-surface
model duplicates the hinge station, so surface-path readiness remains blocked
by `shared_hinge_contact_domain_unresolved` even when retained triangles look
separated. Interblade readiness can report `preconditions_satisfied` without
setting `interblade_clearance`. No readiness result changes constraints,
selection, `physical_qualification`, or `full_propeller_clearance`. Separated
evidence is integrity-checked against the producer threshold independently of
the question threshold. Each gate exposes per-dimension states, and an
unexpected readiness `ArithmeticError` aborts the search instead of becoming
a failed grid row.

Evidence: `pyfoldable/application/blade_stations.py`, `geometry_search.py`,
`geometry_clearance_policy.py`, `geometry_clearance_readiness.py`,
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

## ADR-005 — CMM-1 is partial coupled screening, not hinge-load coupling

**Status: accepted for the CMM-1 software boundary.**

Decision: add a separate synchronous screening transient. Its states are hinge
angle, hinge rate, and shaft speed. Motor current stays algebraic and reuses
the PR-07 motor law without equation changes. Whole-rotor foldable BEM torque
enters the shaft equation once. Aerodynamic hinge torque is omitted
(`unavailable_omitted_by_cmm1`), not published as a physical zero. The mass
matrix uses caller-sourced base inertia `I0` that excludes the N movable tips.
Integration stops at the first mechanism-stop contact. Every accepted RK45
dense interval is audited on its continuous quartic; only the pre-contact
portion of a contacting step is relevant. Extrema are isolated on the real
axis. Unresolved root or range classification fails closed, as does a proven
exit below 100 rpm or outside the radial-cosine fold limit. v1 does not
publish a fabricated `model_domain_exit` point. Analytical mass positivity is
not enough: the represented scaled pivot and the backward residual must pass.
A standalone report contains the exact canonical sealed request, so its hash
can be recomputed from the report. Every artifact keeps
`physical_qualification=false` and `full_propeller_clearance=null`.

This ADR does not approve CMM-2. A later aerodynamic hinge-load model needs its
own reviewed local-load contract. CMM-1 does not replace PY-05, PR-07, or the
GEOM #67–#69 evidence, negative-policy, and readiness layers.

Evidence: `pyfoldable/dynamics/coupled_transient.py`,
`pyfoldable/application/coupled_transient_service.py`,
[CMM-1 contract](../cmm1_partial_coupled_transient.md).

## Future records

An unproven architectural interpretation must say **inferred — requires
confirmation**, with evidence and unresolved alternatives. Proposed changes are
not accepted decisions. No rationale is inferred here for why a database or
hosted service was not chosen; their absence is simply current repository reality.
