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
`c7cb4144f0dc912c73d1f3d1b1d2d063c48db739`
(this handoff commit may follow that SHA)

PR and remote head:
https://github.com/Poyqraz/PyFoldable/pull/67

Completed:
- Optional `clearance_inputs` / `hardware_json` on `prepare_geometry_search`
- Per-candidate draft hinge rewrite and GEOM-04 prepare/run
- Protected gates always `surface_path_clearance=None` and
  `interblade_clearance=None` for every GEOM-04 outcome
- `physical_qualification=False`, `full_propeller_clearance=None`
- No dashboard opt-in; no GEOM-04 numerical redesign
- Astra blockers:
  1. Completed artifacts must match the exact candidate request SHA,
     report SHA, decoded object, report request SHA and request context
     (hinge/endpoint/hardware/controls). Mismatch aborts the search.
  2. Broad `except ValueError` around run/decode/identity/accounting
     removed. Only `prepare_surface_clearance` at the candidate hinge is
     a documented domain-validation catch (`SearchError` re-raised).
     `_draft_with_hinge_radius` is outside that catch. Identity, JSON,
     programming errors, GEOM-04 `ArithmeticError` and execution abort.
  3. Complete GEOM-04 report retained under `details.geom04_clearance`.
  4. Oversized evidence replaces only that namespace; GEOM-01 audit,
     objective and constraints remain. 256 KiB snapshot limit unchanged.
  5. Grid prepare no longer validates exclusions against the base hinge.
     Candidate prepare/hardware/exclusions use that candidate's geometry.
  6. Each candidate gets the configured `max_node_comparisons`,
     `max_feature_tests` and `max_hardware_queries`. Context records
     `N ×` aggregate ceilings. Impossible accounting aborts.

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
- Request context `selection_effect` is
  `evidence_only_does_not_alter_geom01_constraints`
- Request context `budget_policy` is
  `per_candidate_configured_limits_not_shared_grid_remainder`
- Nested search details still cannot declare `physical_qualification`
  other than false (existing `run_grid_search` snapshot rule). A forged
  True in a GEOM-04 report is stored as false in the attached copy so the
  audit is not wiped.
- Scope: no generic search-engine redesign; no GEOM-04 kernel change

Files changed versus current GitHub `main` (`d7afc39`):
- `pyfoldable/application/geometry_search.py`
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
- Record after the docs/handoff commit and full suite on that HEAD

Tests failing / skipped / not run (reason):
- 9 skipped: missing generated/reference foldable CSVs (legacy, unchanged)

Independent review (reviewed SHA, findings, disposition):
- Pending on the exact head after this documentation commit

GitHub CI / reviews (exact head, URLs, pending gates):
- Record exact-head Tests workflow after push
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
