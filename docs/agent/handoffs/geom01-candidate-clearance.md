# Task Handoff: GEOM-01 candidate-specific GEOM-04 binding

Goal:
Smallest fail-closed integration so GEOM-01 can consume candidate-specific
GEOM-04 clearance where that evidence exists. Unknown must not become passed.

Code base commit:
`d7afc391d5f41b15259826b99a5ed7560153439e` (`main`)

Branch / current commit / tree:
`cursor/geom01-candidate-clearance-36c6`

Tested implementation SHA/tree:
`978a723e49b3848754ce373eb2475cb3809c6d03`
(handoff commit may follow this SHA)

PR and remote head:
https://github.com/Poyqraz/PyFoldable/pull/67

Completed:
- Optional `clearance_inputs` / `hardware_json` on `prepare_geometry_search`
- Per-candidate draft hinge rewrite and GEOM-04 prepare/run
- Fail-closed pair mapping; shared BVH/feature/hardware budgets
- Qualification flags locked (`physical_qualification=False`,
  `full_propeller_clearance=None`)
- RED then GREEN tests in `tests/application/test_geometry_search.py`
- Independent review: approve; follow-up tests for empty hardware,
  hardware violation and candidate `ValueError`
- Local compileall and full pytest on `978a723`

Remaining:
- Exact-head GitHub CI for the PR head after this handoff commit
- Independent human review; do not merge from this agent
- Optional later UI opt-in; dashboard remains unbound

Important decisions and evidence paths:
- Unbound default is unchanged; UI/examples do not pass clearance inputs
- GEOM-04 engine is not forked; late import only because
  `surface_clearance` already imports `geometry_search._inputs`
- True only when required pair kinds exist and every extracted status is
  `separated`; missing/unknown/exhausted stay `None`; violation is `False`
- Hardware, when bound, is AND-closed onto both constraints
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
  → 33 passed on `978a723`
- `./venv/bin/python -m compileall -q pyfoldable pythrust apps examples tests`
  → exit 0
- `./venv/bin/python -m pytest tests/ -q` → 1477 passed, 9 skipped,
  37 subtests passed on `978a723`

Tests failing / skipped / not run (reason):
- 9 skipped: missing generated/reference foldable CSVs (legacy, unchanged)

Independent review (reviewed SHA, findings, disposition):
- Automated reviewer on `94725c4`: approve
- Minor: mixed-row status label; empty-hardware True-from-absent risk;
  current-state table wording
- Disposition: status uses both constraints; added empty-hardware,
  hardware-violation and candidate-error regressions; clarified
  current-state note. Re-reviewed locally via those tests on `978a723`

GitHub CI / reviews (exact head, URLs, pending gates):
- CI pending for the pushed head after this handoff
- Human review and CLA check remain; do not merge

Known risks and evidence limits:
- Hinge radius rewrite is a `[hinge]` TOML line replacement; missing
  radius fails closed
- Scoped GEOM-04 True is not physical qualification or full-propeller
  clearance
- Synthetic fixtures and CI do not qualify a project rotor

Unresolved questions:
- Whether the dashboard should later opt in to bound clearance

Next recommended action:
Independent review of PR #67 after exact-head CI is green. Do not merge
from this handoff.

Rollback (affected commits/artifacts; preserve unrelated work):
- Revert `c6732d4`, `94725c4`, `978a723` and the later handoff commit
- Leave the unstaged CSV and other branches untouched
