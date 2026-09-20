# Task Handoff: GEOM-01 candidate-specific GEOM-04 evidence attachment

Goal:
Evidence integration only. Execute, bind, hash and inspect candidate-specific
GEOM-04 clearance without changing GEOM-01 selection constraints. Candidate
evidence must be identity-bound, per-candidate budgeted, and fail-closed.

Code base commit:
GitHub `origin/main` at last fetch:
`d7afc391d5f41b15259826b99a5ed7560153439e`
PR #66 was still OPEN/draft at that fetch. Documentation reconciliation
`24cac8f4ab7d026c338f3a48495b6ce28204d524` is already in this branch.

Branch / current commit / tree:
`cursor/geom01-candidate-clearance-36c6`

Tested implementation SHA/tree:
`5e7a3ca5046101d391ce75408fc1704df4ecd74d`

PR and remote head:
https://github.com/Poyqraz/PyFoldable/pull/67

Completed:
- Optional `clearance_inputs` / `hardware_json` on `prepare_geometry_search`
- Per-candidate draft hinge rewrite and GEOM-04 prepare/run
- Protected gates always `surface_path_clearance=None` and
  `interblade_clearance=None` for every GEOM-04 outcome
- `physical_qualification=False`, `full_propeller_clearance=None`
- No dashboard opt-in; no GEOM-04 numerical redesign
- Closed Astra blockers:
  1. Foreign/mismatched artifacts abort (request SHA, report digest,
     decoded request SHA/context, hinge/endpoint/hardware/controls).
  2. Only `SurfaceClearanceValidationError` from candidate
     `prepare_surface_clearance` becomes `candidate_validation_failed`.
     Programming `ValueError`, `SearchError`, `ArithmeticError`,
     `TypeError` and serializer failures abort. `_draft_with_hinge_radius`
     stays outside that catch.
  3. Valid completed GEOM-04 reports attach unchanged
     (`attached == json.loads(original.report_json)`).
     `physical_qualification is True` or `full_propeller_clearance is not
     None` aborts; no sanitization/`_search_safe_report`.
  4. Oversized *valid* evidence replaces only that namespace; GEOM-01
     audit, objective and constraints remain. 256 KiB snapshot limit
     unchanged. Serialization/schema failure aborts; it is not oversize.
  5. Grid prepare no longer validates exclusions against the base hinge.
     Candidate prepare/hardware/exclusions use that candidate's geometry.
  6. Per-candidate configured budgets; aggregate `N ×` ceilings.
  7. Strict finite JSON (`parse_constant` rejects NaN/Infinity) and
     report schema/content validation before attachment.
  8. Query-level node/feature/hardware accounting must be nonnegative
     integers, cannot exceed ceilings, and must reconcile with
     report-level totals.

Remaining:
- Exact-head GitHub CI for the PR head after this handoff commit
- Independent human review; do not merge from this agent
- If GitHub later squash-merges #66, re-sync this branch
- Optional later UI opt-in; dashboard remains unbound
- A later reviewed slice would be required before mapping GEOM-04 into
  GEOM-01 constraint Booleans

Important decisions and evidence paths:
- Unbound default is unchanged; UI/examples do not pass clearance inputs
- GEOM-04 engine is not forked; late import only because
  `surface_clearance` already imports `geometry_search._inputs`
- `surface_clearance.py` change is exception taxonomy only
  (`SurfaceClearanceValidationError` for input/candidate-domain raises).
  Numerical algorithms are unchanged.
- Request context `selection_effect` is
  `evidence_only_does_not_alter_geom01_constraints`
- Request context `budget_policy` is
  `per_candidate_configured_limits_not_shared_grid_remainder`
- Nested search details still cannot declare `physical_qualification`
  other than false (existing `run_grid_search` snapshot rule). Invalid
  qualification in a GEOM-04 report aborts before attachment.
- Scope: no generic search-engine redesign; no GEOM-04 kernel change

Files changed versus current GitHub `main` (`d7afc39`):
- `pyfoldable/application/geometry_search.py`
- `pyfoldable/application/surface_clearance.py` (exception taxonomy only)
- `tests/application/test_geometry_search.py`
- `docs/geom01_feasibility_plan.md`
- `docs/geom04_surface_hardware.md`
- `docs/architecture/decisions.md`
- `docs/agent/current-state.md`
- `docs/agent/handoffs/geom01-candidate-clearance.md`
- Plus PR #66 documentation files until GitHub `main` contains `24cac8f`

Unrelated work to preserve:
- Dirty `reports/foldable_v2_engineering_design/report_key_results.csv`
  (CRLF noise); not staged
- PR #3, UI work, legacy cleanup, Cursor rules/skills

Tests passed (command, result, tested SHA/tree):
- RED (production `6e00689`, tests then at `1066b24`): 17 expected
  adversarial failures (forged qualification, programming/serializer
  prepare ValueError, NaN/Infinity, missing/malformed schema,
  query-level overclaim/ledger, details serializer vs oversize).
  Already-correct paths stayed green (invalid candidate geometry,
  valid unmutated report, top-level negative/non-integer, oversize).
- GREEN implementation `5e7a3ca5046101d391ce75408fc1704df4ecd74d`:
  `./venv/bin/python -m pytest tests/application/test_geometry_search.py
  tests/application/test_surface_clearance_service.py
  tests/application/test_hardware_clearance_motion.py
  tests/geometry/test_surface_clearance.py -q` → 122 passed
  `./venv/bin/python -m compileall -q pyfoldable pythrust apps examples tests`
  `git diff --check`
  `./venv/bin/python -m pytest tests/ -q` → 1510 passed, 9 skipped,
  37 subtests passed
- This handoff commit may follow `5e7a3ca5046101d391ce75408fc1704df4ecd74d`; re-record HEAD after push

Tests failing / skipped / not run (reason):
- 9 skipped: missing generated/reference foldable CSVs (legacy, unchanged)

Independent review (reviewed SHA, findings, disposition):
- Pending on the exact head after this documentation commit

GitHub CI / reviews (exact head, URLs, pending gates):
- Record exact-head Tests workflow after push of this handoff
- Human review and CLA check remain; do not merge

Known risks and evidence limits:
- Hinge radius rewrite is a `[hinge]` TOML line replacement; missing
  radius fails closed
- Attached complete reports must fit 256 KiB or the evidence attachment
  is replaced with an explicit oversize failure
- Synthetic fixtures and CI do not qualify a project rotor
- This slice does not make a candidate feasible from GEOM-04 evidence

Unresolved questions:
- Whether a later reviewed slice should map attached GEOM-04 evidence
  into GEOM-01 gates
- Whether the dashboard should later opt in to bound clearance

Next recommended action:
Independent review of PR #67 after exact-head CI is green. Do not merge
from this handoff.

Rollback (affected commits/artifacts; preserve unrelated work):
- Revert this workstream on `cursor/geom01-candidate-clearance-36c6`
- Leave the unstaged CSV and other branches untouched
