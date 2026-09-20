# Task Handoff: GEOM-01 candidate-specific GEOM-04 evidence attachment

Goal:
Evidence integration only. Execute, bind, hash and inspect candidate-specific
GEOM-04 clearance without changing GEOM-01 selection constraints.

Code base commit:
`d7afc391d5f41b15259826b99a5ed7560153439e` (`main`)

Branch / current commit / tree:
`cursor/geom01-candidate-clearance-36c6`

Tested implementation SHA/tree:
`e12ebb90b3edc08c851dfa099f3567a1271c6ed0`
(this handoff commit may follow that SHA)

PR and remote head:
https://github.com/Poyqraz/PyFoldable/pull/67

Completed:
- Optional `clearance_inputs` / `hardware_json` on `prepare_geometry_search`
- Per-candidate draft hinge rewrite and GEOM-04 prepare/run
- Shared BVH/feature/hardware budgets; no report reuse
- Protected gates always `surface_path_clearance=None` and
  `interblade_clearance=None` for every GEOM-04 outcome
- Separate details classification: `scoped_geom04_violation`,
  `scoped_geom04_separated`, `unknown_scoped_geom04`
- Pair/interval/witness/bound/exclusion/hardware provenance attached
- `physical_qualification=False`, `full_propeller_clearance=None`
- Mapping helpers `_map_clearance_constraints`, `_reduce_statuses` and
  `_and_closed` removed
- Contract docs revised so this slice does not change GEOM-01 gates
- Local compileall and full pytest on `e12ebb9`: 1480 passed, 9 skipped,
  37 subtests passed
- Independent review of `e12ebb9`: approve (stale prior handoff was P2)

Remaining:
- Exact-head GitHub CI for the PR head after this handoff commit
- Independent human review; do not merge from this agent
- PR #66 is still open; `main` has not moved past `d7afc39`. Re-fetch and
  merge/rebase onto latest `main` if #66 lands before merge of #67
- Optional later UI opt-in; dashboard remains unbound
- A later reviewed slice would be required before mapping GEOM-04 into
  GEOM-01 constraint Booleans

Important decisions and evidence paths:
- Unbound default is unchanged; UI/examples do not pass clearance inputs
- GEOM-04 engine is not forked; late import only because
  `surface_clearance` already imports `geometry_search._inputs`
- GEOM-04 outcomes never assign True or False to the two protected
  GEOM-01 constraints. Violation and separated stay visible in details.
- Request context `selection_effect` is
  `evidence_only_does_not_alter_geom01_constraints`
- One clearance report is never reused for another hinge/angle

Files changed:
- `pyfoldable/application/geometry_search.py`
- `tests/application/test_geometry_search.py`
- `docs/geom01_feasibility_plan.md`
- `docs/geom04_surface_hardware.md`
- `docs/architecture/decisions.md`
- `docs/agent/current-state.md`
- `docs/agent/handoffs/geom01-candidate-clearance.md`

Unrelated work to preserve:
- Dirty `reports/foldable_v2_engineering_design/report_key_results.csv`
  (CRLF noise); not staged
- PR #3, UI work, legacy cleanup, Cursor rules/skills

Tests passed (command, result, tested SHA/tree):
- `./venv/bin/python -m pytest tests/application/test_geometry_search.py -q`
  → 36 passed on `e12ebb9`
- `./venv/bin/python -m compileall -q pyfoldable pythrust apps examples tests`
  → exit 0
- `./venv/bin/python -m pytest tests/ -q` → 1480 passed, 9 skipped,
  37 subtests passed on `e12ebb9`

Tests failing / skipped / not run (reason):
- 9 skipped: missing generated/reference foldable CSVs (legacy, unchanged)

Independent review (reviewed SHA, findings, disposition):
- Automated reviewer on `e12ebb9`: approve
- P2: this handoff was stale vs the evidence-only contract (fixed here)
- P3: hardware-empty label is not a gate; unbound details gained
  explicit `physical_qualification=false` / `full_propeller_clearance=null`
  without changing constraints. Left as-is.

GitHub CI / reviews (exact head, URLs, pending gates):
- Record exact-head Tests workflow after this handoff is pushed
- Human review and CLA check remain; do not merge

Known risks and evidence limits:
- Hinge radius rewrite is a `[hinge]` TOML line replacement; missing
  radius fails closed
- Attached query/interval payloads must fit the 256 KiB search-details
  snapshot; oversized details fail closed rather than pass
- Synthetic fixtures and CI do not qualify a project rotor
- This slice does not make a candidate feasible from GEOM-04 evidence

Unresolved questions:
- Whether a later reviewed slice should map attached GEOM-04 evidence
  into GEOM-01 gates
- Whether the dashboard should later opt in to bound clearance

Next recommended action:
Independent review of PR #67 after exact-head CI is green. Do not merge
from this handoff. If PR #66 merges first, sync this branch onto that
`main` before merge.

Rollback (affected commits/artifacts; preserve unrelated work):
- Revert `c6732d4`, `94725c4`, `978a723`, `c137eaa`, `e411c3d`,
  `e12ebb9` and the later handoff commit
- Leave the unstaged CSV and other branches untouched
