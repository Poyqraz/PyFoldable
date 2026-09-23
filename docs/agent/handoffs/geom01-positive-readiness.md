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

PR:
https://github.com/Poyqraz/PyFoldable/pull/69

Previous request-changes head:
`4a93f0991dbfd80d4cfd241b487e72c0c01d9762`
Exact-head CI for that SHA already succeeded for Python 3.10 and 3.11:
pull_request run 35894611714 and push run 35894588896.
Do not describe that CI as still pending.

Tested behavior commit for this correction, before this handoff file:
`0fd2bb1b7114fba9897a2e29d646782f83d709c9`

This handoff commit only records that result. It does not change runtime
behavior. The branch tip after this file is committed is a different SHA.
Record that tip's exact-head CI in the PR description. Do not add another
commit solely to store the CI result.

Completed:
- Pure module `pyfoldable/application/geometry_clearance_readiness.py`
- Optional question on `prepare_geometry_search` / `run_geometry_search`
- Diagnostic namespace `details.geom04_positive_clearance_readiness`
- 256 KiB omit-in-full behavior
- Producer-threshold integrity is independent of question compatibility
- Per-dimension states on each gate
- Readiness `ArithmeticError` aborts as `SearchError`
- Tests and the GEOM-01 / ADR-003 / current-state notes through `0fd2bb1`

Remaining:
- Exact-head GitHub CI for the branch tip that contains this handoff
- Independent review of that tip
- Maintainer must check the contributor-agreement box; it is not satisfied here
- Do not merge

Important decisions:
- Applicability is structural. A one-blade rotor reports interblade
  `not_applicable` even when evidence is absent, failed, or oversize.
  Every dimension on that gate is `not_applicable`. Question and candidate
  fields stay on the parent result.
- `preconditions_satisfied` is not a constraint and is not `True`.
  Every applicable dimension is then `satisfied`; a dimension outside that
  gate may be `not_applicable`.
- Unavailable evidence blocks `candidate_binding` and leaves the other
  dimensions `not_assessed`.
- Completed surface-path assessments always include
  `shared_hinge_contact_domain_unresolved`. Exclusions and retained-surface
  separation do not remove it. Interblade does not inherit it. Interblade
  `hub_suitability` and `contact_domain` are `not_applicable`.
- Separated queries are always checked against
  `request.inputs.required_clearance_m`. Equality with that producer
  threshold is not enough. A question/report threshold difference is
  `threshold_mismatch` only after the producer claim is internally valid.
- Candidate endpoint, span, or exclusion contradictions inside a completed
  report abort. A separated query with a coverage gap, a non-finite or
  insufficient producer lower bound, a query minimum that is not the interval
  minimum, or a contradictory contact state aborts through
  `ClearanceReadinessError` and `SearchError`.
- `ZeroDivisionError` and `OverflowError` from readiness assessment are
  caught only as `ArithmeticError` and re-raised as `SearchError`.
  `TypeError` and unrelated `ValueError` are not caught there.
  `design_search.py` is unchanged.
- Infinite-envelope separation supports the hub component only when the
  question declares `infinite_envelope_under_nominal_containment`. A declared
  finite cylinder uses its own hardware rows. General hardware is ignored.
- The readiness namespace is appended only after negative policy and oversize
  rollback. If it does not fit in 256 KiB it is omitted in full. Omission is
  not success.
- Station endpoints reuse the mechanism audit's 8-ULP rule. The arithmetic
  is duplicated in the pure module so the diagnostic does not import mesh or
  clearance execution.

Follow-up, not changed here:
An extra mathematically dyadic zero-width singleton can coexist with an
already separated parent and still be accepted. It adds no angular extent and
no separation proof, and it did not create false `preconditions_satisfied`.
Do not treat that as a reason to rewrite the GEOM-04 interval producer in
this PR.

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

Local verification of behavior commit `0fd2bb1`, Python 3.12 venv:
- Readiness file: 60 passed
- Focused readiness, negative-policy, geometry-search, station, surface, and
  hardware tests: 353 passed
- Full suite: 1655 passed, 9 skipped, 37 subtests passed
- `compileall` on the readiness module and `geometry_search.py`: OK
- `git diff --check`: OK, aside from the unstaged CSV CRLF warning
- `design_search.py`, `geometry_clearance_policy.py`, and GEOM-04 numerical
  kernels are not in the diff

RED evidence against `4a93f099`, before `0fd2bb1`:
- Producer lower bound 0.0001 or 0.0005 with a different question threshold
  returned a search report instead of `SearchError` (`DID NOT RAISE`).
- Dimension consumers still received the eleven names, not `{name, state}`
  records.
- Injected `ZeroDivisionError` and `OverflowError` returned a finite search
  artifact instead of `SearchError`.
- Missing lower bound, query/interval minimum mismatch, and
  `ClearanceReadinessError` already aborted. Those retention tests passed
  on `4a93f099`.

Out of scope:
Dashboard, CAD, asynchronous motion, physical qualification,
full-propeller clearance, `True` promotion, PR #68 negative semantics, PR #3,
dyadic parent/child reconstruction.

Rollback:
Revert `0fd2bb1` and this handoff commit. Leave the unrelated CSV unstaged.

Do not merge.
