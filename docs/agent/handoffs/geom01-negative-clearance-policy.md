# Task Handoff: GEOM-01 negative clearance policy v1

Goal:
Optional decision policy over already accepted GEOM-04 evidence. The policy
may set `surface_path_clearance` or `interblade_clearance` to `False` or
leave them `None`. It must never set `True`. Default searches stay
evidence-only.

Code base commit:
GitHub `origin/main` at implementation start:
`3b30183737020096855b6799b5dd19a6c58fc267`
(`Merge pull request #67`). It had not advanced past that SHA.

Branch:
`cursor/geom01-negative-clearance-policy-36c6`

Previous reviewed HEAD:
`afe0bc4dbee728f977a279b1a1baedf6f5ff07c1`
Its Python 3.10/3.11 CI had already succeeded
(push `35780566656`, pull_request `35780588558`). That record belongs to
`afe0bc4`, not to the witness/role correction below.

Tested commits:
- RED `68e4c8c` (module absent; integration import failed)
- GREEN policy `39601e7`
- Docs `e9f0ff1`
- Local verification record `afe0bc4`
- Witness, hardware-role, provenance and diagnostic correction:
  `23e740649e7b3929e800e6d1ffac8e6828b6f74a`

Local verification on the correction, Python 3.12 venv:
- RED against `afe0bc4` before the production edit: 19 failed, 8 passed
  among the new blocker tests. The 19 failures were the intended gaps
  (threshold proof, query/interval disagreement, extra violation intervals,
  blade-shaped hardware names, reversed producer roles, enabled
  `selection_effect`, contradictory-witness search abort, and the surface
  diagnostic). Already-closed cases stayed green: no violation interval,
  witness outside the interval or path, zero-clearance negative penetration,
  one unknown tail, a real `pair_clearance` violation, disabled provenance,
  and interblade-only `False`.
- Policy and geometry-search files: 151 passed
- Surface and hardware modules: 111 passed
- Full suite: 1595 passed, 9 skipped, 37 subtests passed
- `compileall` OK
- `git diff --check` OK except the unstaged CSV CRLF warning, which is not
  part of this branch
- Independent automated review: APPROVE
- `design_search.py` and GEOM-04 numerical kernels unchanged

Policy rules recorded by this correction:
- A `violation` is usable only when the query witness and the single
  violation-interval witness are exactly equal and strictly less than
  `required_clearance_m`. Contradictory violation evidence raises
  `ClearancePolicyError` and aborts through the existing `SearchError`
  boundary. It is not stored as `None`.
- `hardware_surface` is surface part then hardware body.
  `hardware_pair` is two declared hardware bodies. Hub is surface part
  then `hub_envelope`. Finite-hub `False` requires binding `hub` and
  geometry kind `finite_cylinder` on that hardware-role body.
- Enabled clearance binding uses
  `selection_effect=negative_policy_may_set_clearance_constraints_false_never_true`.
  No policy, or `enabled=False`, keeps
  `evidence_only_does_not_alter_geom01_constraints`.
- Final `surface_path_clearance=False` sets
  `surface_path_clearance_status=negative_clearance_policy_relevant_violation`.
  `None` keeps `unknown_no_swept_surface_collision_model`.

PR:
https://github.com/Poyqraz/PyFoldable/pull/68
Do not merge.

Exact-head CI for `23e740649e7b3929e800e6d1ffac8e6828b6f74a`:
- push: https://github.com/Poyqraz/PyFoldable/actions/runs/35831205015
- pull_request: https://github.com/Poyqraz/PyFoldable/actions/runs/35831208635
- Python 3.10 and 3.11: 1595 passed, 9 skipped, 37 subtests passed
- This handoff paragraph is documentation-only. It does not change runtime
  behavior. Do not treat the `afe0bc4` runs as CI for `23e7406`.

Remaining:
- Independent human review
- Do not merge from this agent
- No UI binding and no `True` promotion in this slice

Out of scope:
Dashboard, CAD, asynchronous motion, physical qualification,
full-propeller clearance, generic grid redesign, PR #3

Rollback:
Revert this branch. Leave unrelated dirty CSV edits unstaged.
