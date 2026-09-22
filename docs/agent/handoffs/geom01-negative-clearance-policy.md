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

Tested commits:
- RED `68e4c8c` (module absent; integration import failed)
- GREEN policy `39601e7`
- Docs `e9f0ff1` (this handoff update follows that commit)

Local verification on GREEN:
- policy + geometry-search: 124 passed
- surface/hardware: 56 passed
- full suite: 1568 passed, 9 skipped, 37 subtests
- `compileall` and `git diff --check` OK (unstaged CSV CRLF warning only)
- Independent automated review: APPROVE
- `design_search.py` and GEOM-04 numerical kernels unchanged

PR:
Do not merge.

Completed:
- `NegativeClearancePolicy` / `decide_negative_clearance` in
  `pyfoldable/application/geometry_clearance_policy.py`
- Policy id `geom01_negative_clearance_v1`
- Motion domain
  `synchronous_planar_rigid_tips_from_zero_to_declared_endpoint`
- Declaration bound into `prepare_geometry_search` context and request SHA
- Gates applied only after the existing PR #67 acceptance path
- Oversized final attachment forces both gates back to `None`
- `design_search.py` and GEOM-04 numerical kernels unchanged

Remaining:
- Exact-head Python 3.10/3.11 CI after push
- Independent human review
- Do not merge from this agent
- No UI binding and no `True` promotion in this slice

Out of scope:
Dashboard, CAD, asynchronous motion, physical qualification,
full-propeller clearance, generic grid redesign, PR #3

Rollback:
Revert this branch. Leave unrelated dirty CSV edits unstaged.
