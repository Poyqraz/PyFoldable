# Task Handoff: GEOM-01 candidate-specific GEOM-04 evidence attachment

Goal:
Evidence integration only. Execute, bind, hash and inspect candidate-specific
GEOM-04 clearance without changing GEOM-01 selection constraints.

Code base commit:
GitHub `origin/main` at last fetch:
`d7afc391d5f41b15259826b99a5ed7560153439e`
Documentation reconciliation commit incorporated from PR #66 branch:
`24cac8f4ab7d026c338f3a48495b6ce28204d524`

Branch / current commit / tree:
`cursor/geom01-candidate-clearance-36c6`

Tested implementation SHA/tree:
`1bd4e41868be54a88873f82aef749ce816ee39a5`
(merge of `24cac8f` into the evidence-only branch; no Python/test edit)
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
- Synced PR #66 documentation reconciliation (`24cac8f`): auto-merge of
  `docs/agent/current-state.md` kept the 2026-09-19 drift ledger and the
  2026-09-20 evidence-only note. No application or test files changed.
- Local compileall and full pytest on `1bd4e41`: 1480 passed, 9 skipped,
  37 subtests passed; 36 geometry-search tests passed
- Independent review of `e12ebb9`: approve (evidence-only contract)

Remaining:
- Exact-head GitHub CI for the PR head after this handoff commit
- Independent human review; do not merge from this agent
- GitHub still listed PR #66 as OPEN at last fetch; `origin/main` had not
  moved past `d7afc39`. If #66 squash-merges later, re-sync this branch
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
- Synchronization required documentation merge only; no semantic/code change

Files changed versus current GitHub `main` (`d7afc39`):
- `pyfoldable/application/geometry_search.py`
- `tests/application/test_geometry_search.py`
- `docs/geom01_feasibility_plan.md`
- `docs/geom04_surface_hardware.md`
- `docs/architecture/decisions.md`
- `docs/agent/current-state.md`
- `docs/agent/handoffs/geom01-candidate-clearance.md`
- Plus PR #66 documentation files until GitHub `main` contains `24cac8f`:
  `docs/foldable_conventions.md`, `docs/py04_deterministic_design_search.md`,
  `docs/py05_completion.md`, `docs/python_research_execution_plan.md`,
  `docs/superpowers/specs/v2_thrust_split_audit.md`,
  `docs/ui_engineering_workspace.md`

Unrelated work to preserve:
- Dirty `reports/foldable_v2_engineering_design/report_key_results.csv`
  (CRLF noise); not staged
- PR #3, UI work, legacy cleanup, Cursor rules/skills

Tests passed (command, result, tested SHA/tree):
- `./venv/bin/python -m pytest tests/application/test_geometry_search.py -q`
  → 36 passed on `1bd4e41`
- `./venv/bin/python -m compileall -q pyfoldable pythrust apps examples tests`
  → exit 0
- `git diff --check` → exit 0 (unstaged CSV CRLF warning only)
- `./venv/bin/python -m pytest tests/ -q` → 1480 passed, 9 skipped,
  37 subtests passed on `1bd4e41`

Tests failing / skipped / not run (reason):
- 9 skipped: missing generated/reference foldable CSVs (legacy, unchanged)

Independent review (reviewed SHA, findings, disposition):
- Automated reviewer on `e12ebb9`: approve (evidence-only)
- Sync merge `1bd4e41` did not change production Python or tests

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
from this handoff. If GitHub `main` later contains a squash of #66 rather
than `24cac8f`, re-sync.

Rollback (affected commits/artifacts; preserve unrelated work):
- Revert `c6732d4`, `94725c4`, `978a723`, `c137eaa`, `e411c3d`,
  `e12ebb9`, `b516e49`, `1bd4e41` and the later handoff commit
- Leave the unstaged CSV and other branches untouched
