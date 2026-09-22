# Task Handoff: GEOM-01 candidate-specific GEOM-04 evidence attachment

Goal:
Evidence integration only. Execute, bind, hash and inspect candidate-specific
GEOM-04 clearance without changing GEOM-01 selection constraints. Candidate
evidence must be identity-bound, per-candidate budgeted, and fail-closed.

Code base commit:
GitHub `origin/main`:
`f1a45a404044d2d5b35e695b91761c7e28ab585b`
(`Merge pull request #66`). Unchanged for this increment.

Branch / current commit / tree:
`cursor/geom01-candidate-clearance-36c6`

Tested implementation SHA/tree:
GREEN production:
`7411440feb9be084aaa3272cd31a13845b7157a4`
RED tests:
`6d437c9`
(this handoff/docs commit follows that SHA)

PR and remote head:
https://github.com/Poyqraz/PyFoldable/pull/67
Do not merge.

Completed:
- Optional `clearance_inputs` / `hardware_json` on `prepare_geometry_search`
- Per-candidate draft hinge rewrite and GEOM-04 prepare/run
- Protected gates always `surface_path_clearance=None` and
  `interblade_clearance=None` for every GEOM-04 outcome
- `physical_qualification=False`, `full_propeller_clearance=None`
- No dashboard opt-in; no GEOM-04 numerical redesign
- Closed Astra blockers (including this increment):
  1. Foreign/mismatched artifacts abort (request SHA, report digest,
     decoded request SHA/context, hinge/endpoint/hardware/controls).
  2. Only `SurfaceClearanceValidationError` from candidate
     `prepare_surface_clearance` becomes `candidate_validation_failed`.
     Programming `ValueError`, `SearchError`, `TypeError` and serializer
     failures abort. Prepare `ArithmeticError` is wrapped as
     `SearchError("Candidate clearance preparation failed.")` with chaining
     so generic `run_grid_search` cannot record a failed row.
     `_draft_with_hinge_radius` stays outside that catch.
     `design_search.py` is unchanged.
  3. Valid completed GEOM-04 reports attach unchanged
     (`attached == json.loads(original.report_json)`).
     `physical_qualification is True` or `full_propeller_clearance is not
     None` aborts; no sanitization/`_search_safe_report`.
     Query/interval acceptance is derived from `ClearanceReport`,
     `ClearanceInterval` and hardware `_row` / `query_motion_pair`.
     Missing `intervals`/`reason`, non-object intervals, invalid interval
     status and non-numeric bounds abort. Schema runs before 256 KiB
     size classification, so malformed oversized evidence aborts as
     invalid rather than `evidence_attachment_exceeds_search_details_budget`.
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
- Independent human review; do not merge from this agent
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

Files changed versus current GitHub `main` (`f1a45a4`):
- `pyfoldable/application/geometry_search.py`
- `pyfoldable/application/surface_clearance.py` (exception taxonomy only)
- `tests/application/test_geometry_search.py`
- `docs/geom01_feasibility_plan.md`
- `docs/geom04_surface_hardware.md`
- `docs/architecture/decisions.md`
- `docs/agent/current-state.md`
- `docs/agent/handoffs/geom01-candidate-clearance.md`

This increment versus previous PR head `12ffac6`:
- `pyfoldable/application/geometry_search.py` (prepare ArithmeticError wrap;
  full query/interval producer schema)
- `tests/application/test_geometry_search.py`
- the four documentation files above plus this handoff

Unrelated work to preserve:
- Dirty `reports/foldable_v2_engineering_design/report_key_results.csv`
  (CRLF noise); not staged
- PR #3, UI work, legacy cleanup, Cursor rules/skills

Tests passed (command, result, tested SHA/tree):
- RED on production `12ffac6` / tests `6d437c9`: 8 expected failures
  (prepare ArithmeticError failed-row; six query/interval schema cases;
  oversized malformed classified as oversize). Retain paths green
  (ValidationError bounded; ValueError/TypeError/SearchError abort;
  valid oversize; empty intervals).
- GREEN `7411440feb9be084aaa3272cd31a13845b7157a4`:
  focused geometry-search 77 passed; surface/hardware 57 passed;
  full suite 1521 passed, 9 skipped, 37 subtests;
  compileall and `git diff --check` OK (CSV CRLF warning only, unstaged)

Tests failing / skipped / not run (reason):
- 9 skipped: missing generated/reference foldable CSVs (legacy, unchanged)

Independent review (reviewed SHA, findings, disposition):
- Automated independent review APPROVE at GREEN `7411440`
  (`design_search.py` unchanged; producer-derived schema; protected
  gates still None)
- Human review still required; do not merge

GitHub CI / reviews (exact head, URLs, pending gates):
- Record exact-head Tests workflow after push of this HEAD
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
Final Astra adversarial review of PR #67 at the exact HEAD after this
push and its CI. Do not merge from this handoff.

Rollback (affected commits/artifacts; preserve unrelated work):
- Revert this workstream on `cursor/geom01-candidate-clearance-36c6`
- Leave the unstaged CSV and other branches untouched
