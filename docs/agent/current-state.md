# Current state and repository reality report

**Audited 2026-09-17. Code baseline:**
`ca81d2d2b19622d65453e269d7bfcb48e70aec32` (merged GEOM-04 PR #63).
This is a dated snapshot, not a claim that the branch never advances. Recheck git
before starting.

**2026-09-19 documentation reconciliation** at main `d7afc391d5f41b15259826b99a5ed7560153439e`
(no application change): an independent re-audit of the 2026-09-17 snapshot
corrected stale `pythrust/foldable/` paths and undated “next PY-06 / PY-05”
sentences in historical plans. A large onboarding dump and task→file map were
reviewed against AGENTS.md, this file, architecture overview and the commands
guide, then **not** added; they duplicated those pages. This increment does not
change application behavior.

**2026-09-24 CMM-1.** A separate partial coupled screening transient is
implemented. States are hinge angle, hinge rate, and shaft speed. PR-07 motor
algebra and foldable BEM are reused; PY-05, PR-07, and GEOM #67–#69 behavior
stay in place. Aerodynamic hinge torque is omitted, not reported as a physical
zero. Each accepted RK45 dense interval is audited on its continuous
quartic by real-axis extremum isolation. Boundary equality requires the same
isolated stationary root; unresolved root identity fails closed, and v1 does
not publish a `model_domain_exit` point. Represented mass pivots, not analytical positivity
alone, authorize the solve. A standalone report contains the exact sealed
request. `physical_qualification` remains false and `full_propeller_clearance`
remains null. Contract: [CMM-1](../cmm1_partial_coupled_transient.md).

**2026-09-25 CMM-1 numerical verification.** Phase 4 evidence is
[numerical verification](../cmm1_numerical_verification.md). Phase-4 evidence
was merged in PR #72. Final PR head
`7494ffa7c2ba9f676152b02eebe54b794d7a8f52`. Merge commit
`b99c3f9f109e034380edfd6120c144bc9f66f030`. Numerical verification is complete
for the declared CMM-1 screening model. The production screening code was
unchanged by that evidence PR. `physical_qualification` remains false.
PR-06C remains unresolved. No aerodynamic hinge load exists. No GEOM gate is
promoted. There is no calibration and no experimental validation. CMM-2 is
not approved.

**2026-09-25 planar aerodynamic load prerequisite.** A screening adapter maps
the existing projected foldable-BEM field to a whole-rotor shaft generalized
aerodynamic load and one one-tip planar hinge generalized load. Model id
`planar_projected_material_load_v1`. Qualification
`screening_only_projected_rate_independent`. The prerequisite was independently
reviewed and merged in PR #74. ADR-006 is accepted. Final reviewed head
`d6624ba3e61f8dbb48001d784d8cd51d321c0e10`. Merge commit
`f6fe71912060a26f2dbd8d0665db5f2bda09b48f`. The production model remains
screening-only. This does not implement CMM-2 transient coupling, does not
change CMM-1 or its Phase-4 evidence, and does not establish folded-tip
aerodynamics or a validated hinge torque. `physical_qualification` remains
false. CMM-1 still omits aerodynamic hinge torque
(`unavailable_omitted_by_cmm1`). PR-06C remains unresolved. No GEOM gate is
promoted. There is no calibration and no experimental validation. CMM-2 is
not approved and not implemented. Contract:
[planar aero-load prerequisite](../cmm2_planar_aero_load_prerequisite.md).

**2026-09-26 CMM-2 PR-A isolated dynamics.** A separate screening transient
uses the accepted planar load identifiers with analytic paired loads. Model
class `coupled_aero_hinge_screening_only`. Implementation id
`cmm2_planar_projected_rate_independent_coupling_v1`. Whole-rotor shaft load
is not multiplied by `N`; one-tip hinge load is multiplied once. The isolated
slice was independently reviewed and merged in PR #76. ADR-007 is accepted for
that screening dynamics contract only. Final reviewed head
`da4dcb2589c1a58f1cb97ceb285968a66036e97f`. Merge commit
`63c75346c09280ed4572784aca1a6f1014463744`. The accepted slice includes the
reviewed centrifugal compatibility correction: CMM-2 uses the same `speed**2`
expression as CMM-1. The reviewed 21,062-state zero-hinge characterization
included square-equal and square-divergent shaft speeds and observed 0 ULP on
the compatibility quantities. That observation is not a universal IEEE-754
theorem. Production FoldableBEM source binding is absent. A source-bound
sealed CMM-2 production report is absent. Independent CMM-2 numerical
verification is not complete. The next CMM-2 implementation slice is that
production binding. There is no dashboard. The slice does not change CMM-1.
`physical_qualification` remains false. CMM-1 still reports
`aerodynamic_hinge_torque_status = unavailable_omitted_by_cmm1`. PR-06C
remains unresolved. No GEOM gate is promoted. There is no calibration and no
experimental validation. This does not state that CMM-2 is complete or
physically validated. Contract:
[CMM-2 PR-A](../cmm2_coupled_transient_contract.md).

**2026-09-28 CMM-2 PR-B source-bound screening service.** A separate application
module seals a CMM-2 request and binds PR-07, one FoldableBEM solve, and one
call to the accepted planar map on that same returned object. Service id
`pyfoldable.application.cmm2_coupled_transient_service`. Service implementation
id `cmm2_source_bound_screening_service_v1`. The dynamics implementation id is
unchanged. Whole-rotor shaft load is the mapped generalized field and is not
multiplied by `N`. One-tip hinge load is the mapped one-tip field. The
collective mapped hinge field is not fed into that slot. `bounds` stays
`"error"`. The request hash and report hash identify content. They do not
authenticate a source or establish qualification. The slice was independently
reviewed and merged in PR #78. ADR-008 is accepted for this software
integration only. Final reviewed head
`653526bca79160a2ec41e2e2ebea802dd8b39d1c`. Merge commit
`6f72b28273b38334851df570b1c4cccbbc6b5140`. Independent CMM-2 numerical
verification, PR-C, is not implemented. There is no dashboard. The service
does not change CMM-1 or the accepted load-map mathematics.
`physical_qualification` remains false. PR-06C remains unresolved. No GEOM
gate is promoted. There is no calibration and no experimental validation.
This does not state that CMM-2 is complete or physically validated. Binding:
[CMM-2 source-bound production binding](../cmm2_source_bound_production_binding.md).

**2026-09-29 CMM-2 PR-C verification contract.** The numerical-verification
contract was independently reviewed at head
`613072514f793f2a1bc65704f9158f536210707f`. The narrow C2V-02
initial-acceleration arithmetic amendment was independently reviewed at
technical head `b840ec55b4d1dd57197b97e91e1a48a7fbe7da0d`. That review is
APPROVE from a separate read-only automated reviewer and is not a submitted
GitHub review. Status is REVIEWED / FROZEN FOR IMPLEMENTATION WITH C2V-02
ARITHMETIC AMENDMENT. The amendment changes only initial-acceleration
accounting. Ordinary Q2 remains required. The analytic bridge is an
accounting bound. The trajectory acceptance policy was never reopened.
Implementation against this amended contract has not started. No merged or
accepted PR-C verification implementation exists. Draft PR #81 contains a
blocked evidence implementation attempt. That draft is unmerged and BLOCKED.
Its C2V-02 and C2V-03 trajectory results remain FAIL. Independent CMM-2
numerical verification remains not established. No accepted PR-C evidence
exists. ADR-009 is not created and is not accepted. `physical_qualification`
remains false. PR-06C remains unresolved. No GEOM gate is promoted. There is
no calibration and no experimental validation. Contract:
[CMM-2 PR-C numerical verification contract](../cmm2_numerical_verification_contract.md).

**2026-09-30 CMM-2 Radau remediation contract.** The design contract is
REVIEWED / FROZEN FOR IMPLEMENTATION — CMM-2 RADAU AMENDMENT at technical
reviewed head `2ec4da9acdccc7508fab7c33f289ec9771b2ea65`. That review is
APPROVE FOR CONTRACT FREEZE from a separate read-only automated reviewer and
is not a submitted GitHub review. The later status-closure commit is not that
technical head. Freezing approves the design contract. It does not authorize
production implementation, demonstrate feasibility, establish PR-C
verification, or accept ADR-009. This unmerged draft contains the authorized
CMM-2 v2 Radau integrator, cubic adapter, and certified-root repair. It remains
Draft/BLOCKED; local trajectory passes do not close the frozen contract.
Shipped main `4cf0d0ea017fa824ba8d4a063ceddd015dae09d6` remains RK45/v1.
CMM-1 remains RK45. Q1–Q4, DOP853 A/B, fixtures, controls and trajectory gates
remain unchanged. Q5 and minimum-SciPy support under `scipy>=1.7` remain open.
Refinement or work-budget exhaustion on one accepted interval is terminal for
both counters. A later candidate or helper call cannot return success after
that limit. Conversion infeasibility, direction rejection, unresolved identity
and exhaustion stay separate failures. The ordered C2V09-00…27 preflight
rejects every candidate before a trajectory metric: 00–25 fail in FoldableBEM
on the Mach-0 polar, and 26–27 fail in the motor domain. Expected source
rejection is by exception type. Before that evaluation, the sealed draft
artifact must match the draft built from the pinned declaration and source
file `a3852e5d14f433528fa9ad63bae26dd076b5136eacf4a7860ef76971eec2afdc`. An
extra mass sample or polar table is rejected first. A malformed BEM or mapper return is a contract
block. No candidate is selected. The corrected record is
`reports/c2v09_ordered_preflight/selection_record.json`. It binds the full
critical-fixture manifest `prc_critical_fixture_manifest_v1` at
`265d531f51f08d45139313cd81b0239de0c2e9dd8926e12ded66d2011d83c1f7`, snapshotted
from PR #81 head `1fdf213bb991b2f155bf812d837bb4dcb73a8cc8` without importing
that implementation. Historical digest
`1c465dae2d835fc85f468636131a2af6bce90220bcbde71c03ebea69c4ad3cf9` is the
earlier smaller record. Digest
`457186d5f52a40099acbebfe0e8ffc47eb2a8ee5fd43605ee159ae9c76cd1579` is the
superseded record that hashed only a shared-mechanism subset under the full
manifest id. Push checkout `8978ace` and PR merge checkout `c05fe99` share
tree `07ff58200f6db56e3db5299dde07cb6fb23e1eee`. CI for `be6b85d` failed only
`test_c2v07_presnap_observer_uses_the_cubic_contact` on both Python 3.10 and
3.11, with conversion infeasibility. CI for `c25f8a0` reached the suite and
failed that same acceptance test, plus a preflight assertion that demanded a
null pull-request SHA on a real pull-request event. The event SHA is recorded
when the event exists. The acceptance test is unchanged and
awaits a separately reviewed contract amendment. A local pass does not erase
that certificate. Coefficient replay inputs and the explicit rational image
are separate records. Draft PR #81 is a
separate blocked evidence attempt, not accepted PR-C verification. Independent
CMM-2 numerical verification is not established. ADR-009 is not created or
accepted; `physical_qualification=false`. PR-06C remains unresolved, with no GEOM
promotion, calibration or experimental validation. Earlier dated acceptance
records remain historical provenance. Contract:
[CMM-2 Radau remediation contract](../cmm2_radau_remediation_contract.md).

## Reality summary

The project is a Python scientific library plus one Streamlit engineering app,
with a bundled PyThrust compatibility slice in the same setuptools distribution.
There is no database, ORM/migration system, user authentication/authorization,
REST backend, worker queue, broker, cloud storage integration or deployment IaC.
Storage is versioned config/evidence files, ignored generated outputs, an optional
filesystem polar cache and ephemeral UI session state. API boundaries are Python
functions/dataclasses and strict TOML/JSON contracts. Dependencies and runtime
ranges: [pyproject.toml](../../pyproject.toml); UI routing:
[dashboard](../../apps/pyfoldable_dashboard.py); CI:
[workflows](../../.github/workflows).

## Capability inventory

| State | What exists / what remains | Evidence |
| --- | --- | --- |
| Current | Polar adapters, cache/locks, retries/health, family generation and reviewed real-backend regression envelope | `pyfoldable/core/polar_*.py`, `pyfoldable/providers/`, [qualification contract](../polar_real_backend_qualification.md) |
| Current | Canonical SI design; section analysis, BEM annulus/rotor, foldable projection and coupled motor equilibrium; distinct legacy V1/V2 path retained | `pyfoldable/core/config.py`, `bem*.py`, `foldable_rotor.py`, `motor_bem_coupling.py`; `pyfoldable/integration.py` |
| Current | Active draft/profile/polar binding and explicit BEM/chord–twist search UI (PY-01–04A); bounded grid/failure ledger | `pyfoldable/application/design_analysis.py`, `active_design_search.py`, [search contract](../py04_deterministic_design_search.md) |
| Current | PY-05 prescribed-drive transient, source-bound geometry/mass binding and explicit-run UI | [completion](../py05_completion.md), `pyfoldable/dynamics/mechanism_transient.py`, `tests/ui/test_bound_mechanism_ui.py` |
| Current | PY-06A/B1/C/D1: matched experiments, comparison service, motor correlation and mechanism observation/partition APIs | `pyfoldable/core/measurement_comparison.py`, `motor_rotor_correlation.py`, `mechanism_observation.py`; `pyfoldable/application/measurement_comparison.py` |
| Current | GEOM-01–04: feasibility scan, explicit station import/edit, continuous retained-surface bounds, triangle refinement, finite/convex hardware and UI | [GEOM-02](../geom02_station_contract.md), [GEOM-03](../geom03_surface_clearance.md), [GEOM-04](../geom04_surface_hardware.md), `pyfoldable/application/surface_clearance.py`, `tests/geometry/` |
| Partial | Default GEOM-01 surface gates stay unknown. Opt-in `geom01_negative_clearance_v1` may set either gate to False from accepted GEOM-04 witnesses; it cannot set True or select a candidate. Optional `geom01_positive_readiness_v1` only diagnoses proof prerequisites and does not assign either gate | `pyfoldable/application/geometry_clearance_policy.py`, `geometry_clearance_readiness.py`, `geometry_search.py`; [GEOM-01](../geom01_feasibility_plan.md) |
| Partial | CFD/FEA/experiment UI inspects specific existing canonical contracts in session; not arbitrary ANSYS or raw experimental import, not evidence promotion | `pyfoldable/application/evidence_import.py::_CANONICAL_IDENTITIES`, `inspect_evidence_upload`; `tests/application/test_evidence_import.py` |
| Current | Isolated CMM-2 paired-load screening dynamics are implemented, independently reviewed, and merged in PR #76. ADR-007 accepts that slice only | `pyfoldable/dynamics/cmm2_coupled_transient.py`, [CMM-2 PR-A](../cmm2_coupled_transient_contract.md) |
| Current | Source-bound CMM-2 screening service and sealed deterministic report were independently reviewed and merged in PR #78. ADR-008 accepts that software slice only | `pyfoldable/application/cmm2_coupled_transient_service.py`, [CMM-2 PR-B](../cmm2_source_bound_production_binding.md) |
| Partial | No merged or accepted PR-C verification implementation exists. Draft PR #81 contains a blocked evidence implementation attempt and is unmerged; its C2V-02 and C2V-03 trajectory results remain FAIL. Prior reviewed contract head `613072514f793f2a1bc65704f9158f536210707f`. Reviewed amended technical head `b840ec55b4d1dd57197b97e91e1a48a7fbe7da0d`. Status is REVIEWED / FROZEN FOR IMPLEMENTATION WITH C2V-02 ARITHMETIC AMENDMENT. The amendment changes only initial-acceleration accounting. Ordinary Q2 remains required. The trajectory acceptance policy was never reopened. Implementation against this amended contract has not started. Independent CMM-2 numerical verification is not established. ADR-009 is absent. `physical_qualification` is false | [CMM-2 PR-C contract](../cmm2_numerical_verification_contract.md) |
| Partial | Full workspace coverage: Motor–Pervane, Doğrulama ve Kanıtlar, Raporlar are placeholder pages despite lower-layer APIs | `apps/pyfoldable_dashboard.py::main`, `_render_planned_page` |
| Planned / evidence-dependent | PY-06D2 identifiable parameter fitting, E structural correlation, F consolidated comparison UI, physically supported Pareto recommendations | [PY-06 plan](../py06_calibration_uncertainty_plan.md), [Python roadmap](../python_research_execution_plan.md) |
| Not delivered | Qualified project rotor/structure/deployment; general CAD solids, asynchronous folding, impact/bounce/latch and full BEM–motor–hinge feedback | [validation roadmap](../validation_and_development_roadmap.md), [PY-05 limits](../py05_completion.md), [GEOM-04 limits](../geom04_surface_hardware.md) |

Short implementation filenames within a row share its preceding directory.
Stages named PR-07/PR-09/PR-10 are roadmap labels, not necessarily GitHub PR numbers.
PY-05 (mechanism) is distinct from the older PR-05 (polar family) series.

## Physical evidence and completed-work anchor

`configs/ui/dashboard.toml` binds PR-06C to **blocked**, PR-06D to
**screening_only**, and PR-07/08/09/10 to **pending** report decisions. The canonical
140 mm target, station coverage and representative polar/rotor accuracy are not
fixed merely by completing a UI or numerical solver. Literature remains scoped
context; imported hashes do not authenticate measurements. The first-party
synthetic reference and its 0.70 pretest factor are not calibrated project results.
See `data/propellers/apc_202602/README.md` and
`reports/foldable_v2_engineering_design/model_assumptions_and_limits.md`.

GEOM-04 is shipped in [PR #62](https://github.com/Poyqraz/PyFoldable/pull/62) and
[PR #63](https://github.com/Poyqraz/PyFoldable/pull/63). PR #63 final head
`95e049c70d2959baa2b5500b85e61bf2c44016bd` passed Python 3.10/3.11
[CI run 35186732969](https://github.com/Poyqraz/PyFoldable/actions/runs/35186732969).
Python 3.11 recorded **1464 passed, 9 skipped, 37 subtests passed**. This is
historical exact-head evidence, not a required permanent test count. Independent
review and Cursor Bugbot completed; Bugbot's reverse-query witness-label finding
was fixed with an observed RED/GREEN regression. Merged tree
`ea649f86a844e3f18d9d1d371f8c9f77d0d19c97` matched the tested tree.

Do not repeat GEOM-04 implementation on resumption. No product refactor/migration
is in progress in this documentation branch. Keep PR #3 and unrelated report
edits outside this workstream; inspect live git state rather than assuming a
particular user's uncommitted file still exists.

## DOCUMENTATION DRIFT

Claims below were found at the audited code baseline. Corrections preserve old
results/plans as history; they do not recompute experiments or change solver logic.

| Documentation claim | Repository reality / evidence | Correction / disposition in this increment |
| --- | --- | --- |
| AGENTS test command paired with `1063 passed` | PY-04A-era count; GEOM-04 regression and exact-head CI above are newer | Remove floating count from onboarding; retain dated CI evidence here |
| AGENTS assumes a preinstalled environment from an update script | No provisioning script or Cursor environment file is tracked | Document explicit venv/pip setup; external cloud bootstrap remains unknown |
| PY-06 plan: “GEOM-02 … is next” | GEOM-02–04 code and UI are merged | Replace stale next-task sentence with shipped progression and unresolved candidate integration |
| README workspace overview lacks later geometry/hardware and mechanism paths | Dashboard renders geometry search, clearance and bound mechanism | Add concise capability pointers to authoritative contracts/current state |
| README package-wide `reference_load_postprocess` wording | True of the old V2 report; `core/motor_bem_coupling.py` provides a separate coupled solver | Scope paragraph to historical V2 output and link modern solver; leave old numbers untouched |
| README 7100 RPM table has no adjacent fixture/target-factor warning | Synthetic reference and fixed pretest factor documented in data README and report assumptions | Add immediate classification; retain values as historical model output |
| GEOM-01 result reason `unknown_no_swept_surface_collision_model` | With no negative policy, or when `surface_path_clearance` stays `None`, this diagnostic remains. A v1 policy `False` on that gate records `negative_clearance_policy_relevant_violation` | **Corrected 2026-09-23**: unknown is not a pass; interblade-only `False` does not rewrite the surface-path diagnostic |
| `docs/foldable_conventions.md` and `docs/superpowers/specs/v2_thrust_split_audit.md` name `pythrust/foldable/` | Code lives under `pyfoldable/dynamics/` and related `pyfoldable` modules; `pythrust/` is only propellers/propulsion | **Corrected 2026-09-19**; keep V1/V2 vs core/PY-05 distinction |
| Undated “next PY-06” / “next PY-05” in PY-04/PY-05 delivery prose | PY-05 and PY-06A–D1 plus GEOM-01–04 have shipped | **Corrected 2026-09-19** as dated delivery history; remaining work stays evidence-dependent |
| PY-04A “1063 passed” read as the standing suite size | Dated milestone; current command is `./venv/bin/python -m pytest tests/ -q` | **Corrected 2026-09-19** in the PY-04A record; keep the count as history |
| Independent 2026-09-18 20-section dump / navigation map | Same facts already live in AGENTS.md, this file, architecture overview, commands | **Not imported**; avoid a second always-loaded dump |

`docs/development_roadmap.md` already identifies itself as PR-04/05 history; its
chronology remains intact. Historical test counts in dated delivery records remain
history. The current roadmap and feature contracts have authority over undated
“next” wording in older plans.

## Risks, technical debt and next candidate

- UI state coupling and private helper reuse make broad refactors risky; source
  hashes can also change report identity after code edits. Restart long-lived
  processes for reproducibility. See [architecture risks](../architecture/overview.md#high-risk-coupling).
- Source-checkout paths couple runtime workflows to reports/test fixtures. Wheel
  installation alone is not a tested workspace deployment.
- Dependency ranges are broad and no lockfile is tracked. CI must identify the
  environment actually tested; this is not a promise that all future combinations
  work (`pyproject.toml`, `.github/workflows/tests.yml`).
- Legacy tests can skip for absent generated/reference data. Preserve skipped
  checks explicitly; green CI is not proof of these missing integrations.
- Full numerical solver qualification, input-rights provenance and cache/geometry
  validation remain review-sensitive. No production hosting/security policy exists.

**Subsequent update 2026-09-20:** the application service can bind
candidate-specific GEOM-04 inputs as **evidence only**. The 2026-09-17 Partial
row still describes the GEOM-01 gates: `surface_path_clearance` and
`interblade_clearance` remain unknown. Bound runs rebuild each candidate
draft/request, validate exclusions/hardware against that candidate hinge,
give each candidate its configured GEOM-04 limits, and record `N ×` aggregate
ceilings. Completed artifacts are identity-bound or the search aborts.
Only intentional `SurfaceClearanceValidationError` from candidate prepare
becomes bounded `candidate_validation_failed`; other programming
`ValueError`, `TypeError`, `SearchError` and `ArithmeticError` values abort
(the prepare `ArithmeticError` is wrapped as `SearchError` so it is not a
failed grid row). Valid reports are attached unchanged. Query/interval
acceptance follows the GEOM-04 producer contract; malformed interval
evidence aborts before oversize classification.
`physical_qualification=true` anywhere in the accepted report tree, or
`full_propeller_clearance` other than null, aborts before generic snapshot
handling; nested `physical_qualification=False` remains valid. Non-finite JSON, schema errors and query-level accounting
contradictions abort. Evidence is the complete namespaced GEOM-04 report;
a valid payload that exceeds 256 KiB fails closed without wiping the
GEOM-01 audit. They do not assign True or False to
the protected GEOM-01 constraints or set `physical_qualification`. See
[GEOM-01](../geom01_feasibility_plan.md).

**Subsequent update 2026-09-22:** evidence acquisition and the decision policy
are separate. With no policy, the gates above stay `None`. Supplying
`geom01_negative_clearance_v1` binds its declaration into the GEOM-01 request
identity and may set `surface_path_clearance` or `interblade_clearance` to
`False` only. `True` is not a v1 result. The policy does not rerun GEOM-04,
does not mutate the attached report, and does not change generic grid
selection. A `False` gate makes the existing grid mark that candidate
infeasible; unresolved gates stay blocked. `physical_qualification` stays
false and `full_propeller_clearance` stays null.

**Subsequent update 2026-09-23:** a usable violation witness is strictly below
the policy threshold, and the query witness equals the single violation
interval witness exactly. Hardware roles follow producer position, so a
hardware body may use a blade-shaped name. Enabled clearance binding records
`selection_effect=negative_policy_may_set_clearance_constraints_false_never_true`.
Disabled or absent policy keeps
`evidence_only_does_not_alter_geom01_constraints`. Final surface `False`
sets `surface_path_clearance_status` to
`negative_clearance_policy_relevant_violation`; `None` keeps
`unknown_no_swept_surface_collision_model`.

**Subsequent update 2026-09-23 — positive readiness diagnostic.** Optional
`geom01_positive_readiness_v1` reads the final retained GEOM-04 state after
evidence attachment, negative policy, and oversize rollback. It does not
execute GEOM-04 and it does not assign `surface_path_clearance` or
`interblade_clearance`. `preconditions_satisfied` is not gate `True`.
Surface-path readiness stays blocked by
`shared_hinge_contact_domain_unresolved` for the current open-surface model.
Interblade readiness can be `preconditions_satisfied` on a full-span,
zero-exclusion separated candidate and still leaves the GEOM-01 gate at
`None` unless the negative policy has set `False`. The readiness namespace is
omitted in full when it would exceed the existing 256 KiB details budget.
This diagnostic does not authorize a future `True` promotion. A separated
claim is validated against the producer threshold even when the readiness
question uses another threshold; only a producer-valid report can then record
`threshold_mismatch`. Gate dimensions carry explicit states (`satisfied`,
`blocked`, `not_assessed`, `not_applicable`). Readiness `ArithmeticError`
aborts the search as `SearchError` rather than becoming a failed candidate row.

**Follow-up, not a merge blocker:** an extra dyadic zero-width singleton can
sit beside an already separated parent interval and still be accepted. It adds
no angular extent and no separation proof, and it did not create a false
`preconditions_satisfied`. A parent/child ledger check is deferred. The
GEOM-04 subdivision producer is unchanged.

**Proposed next bounded development slice, not implemented or newly authorized by
this document:** optional dashboard opt-in to bind already-scoped GEOM-04
inputs on the unbound UI path, and any `True` promotion of the clearance
gates. The opt-in v1 negative mapping and the readiness diagnostic above are
separate from that UI work and do not authorize `True`. PY-06D2 is not the
automatic next task without identifiable measured data.

Unresolved inputs: engineers' CAD/material/ANSYS/raw-measurement packages and their
rights/quality; representative polar validation; a separately agreed hosting model
if public deployment is desired. No dates, hidden credentials, external Cursor
setup or completed measurements are inferred from conversation.

## Onboarding report index (A–Q)

| Requested topic | Canonical home |
| --- | --- |
| A reality; I gaps; J risks; K debt; Q unresolved assumptions | This dated current-state report |
| B product; C architecture; D data; E critical flows | [Architecture overview](../architecture/overview.md) |
| F commands; G testing; H security | [Development contract](../development/commands.md) |
| L AGENTS structure / Done | [Root contract](../../AGENTS.md): orientation → map → commands → invariants → change protocol |
| M Cursor rules; N skills; P handoff | [Handoff and Cursor readiness](handoff-protocol.md) |
| O documentation changes | This drift ledger; architecture/decision/command/handoff docs; pointers from README and roadmaps |

No repository dump, application refactor, database or vendor-specific automation
was added to satisfy the documentation structure. Update only affected canonical
pages as capabilities evolve; keep detailed numeric contracts in their existing files.
