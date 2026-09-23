# Task Handoff: GEOM-01 positive-clearance readiness diagnostics v1

Goal:
Diagnose whether accepted GEOM-04 evidence meets the proof prerequisites a
future policy would need before it could consider numerical `True`.
The diagnostic must not authorize or assign `True`, and it must not change
clearance constraints, feasibility, selection, or `best_candidate`.

Code base commit:
`origin/main` at implementation start was
`84db6d1f7dff7a7d94c3ede23fc3fd3feead2af8`
(`Merge pull request #68`). It had not advanced past that SHA.

Branch:
`cursor/geom01-positive-readiness-36c6`

Completed:
- Pure module `pyfoldable/application/geometry_clearance_readiness.py`
- Optional question on `prepare_geometry_search` / `run_geometry_search`
- Diagnostic namespace `details.geom04_positive_clearance_readiness`
- 256 KiB omit-in-full behavior
- Tests and the GEOM-01 / ADR-003 / current-state notes in this branch

Remaining:
- Exact-head GitHub CI for the pushed head (record it in this file after the
  run exists; do not treat this paragraph as a CI result)
- Independent human review
- Do not merge

Important decisions:
- Applicability is structural. A one-blade rotor reports interblade
  `not_applicable` even when evidence is absent, failed, or oversize.
- `preconditions_satisfied` is not a constraint and is not `True`.
- Completed surface-path assessments always include
  `shared_hinge_contact_domain_unresolved`. Exclusions and retained-surface
  separation do not remove it. Interblade does not inherit it.
- Threshold and motion mismatches are blockers. Candidate endpoint, span, or
  exclusion contradictions inside a completed report abort.
- A separated query with a coverage gap, a non-finite or insufficient lower
  bound, a query minimum that is not the interval minimum, or a contradictory
  contact state aborts through `ClearanceReadinessError` and `SearchError`.
- Infinite-envelope separation supports the hub component only when the
  question declares `infinite_envelope_under_nominal_containment`. A declared
  finite cylinder uses its own hardware rows. General hardware is ignored.
- Zero-width dyadic singletons inside the producer depth do not create
  coverage and are not a blanket abort. Off-tree zero-width intervals abort.
- The readiness namespace is appended only after negative policy and oversize
  rollback. If it does not fit in 256 KiB it is omitted in full. Omission is
  not success.
- Station endpoints reuse the mechanism audit's 8-ULP rule. The arithmetic
  is duplicated in the pure module so the diagnostic does not import mesh or
  clearance execution.

Files:
- `pyfoldable/application/geometry_clearance_readiness.py`
- `pyfoldable/application/geometry_search.py`
- `tests/application/test_geometry_clearance_readiness.py`
- `docs/geom01_feasibility_plan.md`
- `docs/geom03_surface_clearance.md`
- `docs/geom04_surface_hardware.md`
- `docs/architecture/decisions.md`
- `docs/agent/current-state.md`
- this handoff

Unrelated work to preserve:
`reports/foldable_v2_engineering_design/report_key_results.csv` is a dirty
CRLF checkout and is not part of this slice.

Behavior commit:
`8cf3a83a23cfdefbd4e4af8a605b8b5ad66d2fb4`

RED evidence, before the module existed, on `84db6d1`:
`pytest tests/application/test_geometry_clearance_readiness.py` failed at
collection with `ModuleNotFoundError: pyfoldable.application.geometry_clearance_readiness`.

Local verification of behavior commit `8cf3a83`, Python 3.12 venv. The full
suite was run again with these documentation edits present; they do not
change runtime behavior:
- Readiness file: 43 passed
- Focused readiness, negative-policy, geometry-search, station, surface, and
  hardware tests: 351 passed
- Full suite: 1638 passed, 9 skipped, 37 subtests passed
- `compileall` on the readiness module and `geometry_search.py`: OK
- `git diff --check`: OK, aside from the unstaged CSV CRLF warning
- `design_search.py` and GEOM-04 numerical kernels are not in the diff

Exact-head GitHub CI is not claimed by this paragraph. Record the push and
pull_request runs for the final head after they finish.

Out of scope:
Dashboard, CAD, asynchronous motion, physical qualification,
full-propeller clearance, `True` promotion, PR #68 negative semantics, PR #3.

Rollback:
Revert this branch. Leave the unrelated CSV unstaged.

Do not merge.
