# Current state and repository reality report

**Audited 2026-09-17. Code baseline:**
`ca81d2d2b19622d65453e269d7bfcb48e70aec32` (merged GEOM-04 PR #63).
This is a dated snapshot, not a claim that the branch never advances. Recheck git
before starting. This increment adds repository memory only; it does not change
application behavior or introduce a feature migration.

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
| Partial | Candidate search cannot consume candidate-specific GEOM-04 clearance; surface/interblade constraints remain unknown, so no automatic promotion | `pyfoldable/application/geometry_search.py::run_geometry_search`, `active_design_search.py`; GEOM-04 contract final scope paragraph |
| Partial | CFD/FEA/experiment UI inspects specific existing canonical contracts in session; not arbitrary ANSYS or raw experimental import, not evidence promotion | `pyfoldable/application/evidence_import.py::_CANONICAL_IDENTITIES`, `inspect_evidence_upload`; `tests/application/test_evidence_import.py` |
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
| GEOM-01 result reason `unknown_no_swept_surface_collision_model` | GEOM-04 exists, but `geometry_search.py` still leaves surface/interblade constraints `None` | **Open diagnostic wording debt**: change only with the next reviewed behavioral slice; do not turn unknown into passed |

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

**Proposed next bounded development slice, not implemented or newly authorized by
this document:** connect candidate-specific scoped clearance to geometry search.
Rebuild each candidate's draft and clearance request; explicitly validate hardware
bindings against its hinge/frame; meter aggregate work; retain pair/interval/source
evidence and missing/excluded scope. Never reuse an active-design clearance result
for different geometry or imply full-propeller/physical qualification. Design the
contract and RED tests before implementation. PY-06D2 is not the automatic next
task without identifiable measured data.

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
