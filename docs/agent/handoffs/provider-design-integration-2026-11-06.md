# Astra-A to Astra-B: bounded retained-provider application integration

Owner review is separate; internal automated review is not Astra-B approval.
Review the final PR exact head/tree published in its description and CI, not a
stale local status. Keep Draft/open/unmerged. No scientific gate is promoted.

## Bases and separable documentation correction

- Verified main: `022b466303c59b8c0adb02f935f9c2f065b0e2b5`.
- Unchanged dependency #103: `fc545b1584d679951fd28db0767cd71c790a7b06`,
  tree `dd399acd98c87d45845f6976eea7c24da81a4e7c`.
- Unchanged dependency #104: `8ba282e49ecf3c7ac96ada100c2721fa28a5803f`,
  tree `b354cc4318e5b864ff5886710cce81a3f5f06a10`.
- Published integration base: `81fdbaea0ae3f900900711c91e91578deb56f052`, tree
  `ee6b2d65e8b6ea36857f5bb071167d0dccf06633`, with those two ordered parents.
  Branch: `astra-a/provider-design-base-20261106`. The local merge candidate
  `a91cc954d57e99d74f4335659260a81685d5286b` has the same tree and ordered
  parents; GitHub created the published commit through its authenticated API
  because the shell remote has no write credentials. No original branch was reset.
  Only `docs/agent/current-state.md` and `docs/validation_and_development_roadmap.md`
  conflicted; both dated appendices were retained verbatim. No source conflict.
  Neither dependency is represented as merged into main.
- Separate #106 root-datum documentation closure:
  `f705d6b4c8dc528a0def94470798ae0ea2942db9`, tree
  `98a789415904e0302b52e4c6151a374eddcccbac`. Same Draft PR, two docs;
  [exact-head Tests 42192367856](https://github.com/Poyqraz/PyFoldable/actions/runs/42192367856)
  passed on Python 3.10/3.11, each 1948 passed, 9 skipped, 37 subtests passed.
  Root declaration/source/unit/meaning, missing-root block and all three inequalities
  are explicit. Historical results and the CAD-free requirement are preserved.

## What is implemented

See the [contract](../../provider_design_analysis.md). New
`application/provider_design_analysis.py` admits application-owned retained XFOIL
records against an independent declared plan. It reuses #104 request/provider/
capture binding and raw parser, validates source/template/catalog/solver identity,
full usable point and rectangular family coverage, raw bytes and provenance,
then materializes a private polar bundle and reuses `prepare_polar_run` /
`run_polar_run` and #103 snapshots. No provider constructor, scheduler or launch.

Dashboard opt-in supplies current five-profile draft, explicit root declaration,
registered family and annulus count; separate prepare/run actions; immutable
success/failure history and downloads. Missing root/data blocks; changed inputs
clear active outputs and never relabel saved records. Default operator registry
is empty. Trusted deployment registration/persistence remains to be connected.
No normal-user CAD/polar JSON file is required. The optional old upload route
remains; no dashboard redesign or new family/hinge optimization service is claimed.

One current hinge is checked against the declared root. The exposed condition
`h-r_root > R-h` is equivalent to `h > (R+r_root)/2`; `h > R/2` is separate.
Root declaration, hub and first station are not interchangeable. Shared parent
global geometry remains unchanged. No hinge is selected by this task.

## Evidence and tests

TDD RED: new application test collection failed because this module did not exist.
GREEN: 150 focused tests passed across new admission/UI and existing driver,
comparison, upload and active UI tests. The positive new tests use explicitly
INERT provider records and an INERT BEM seam. New malformed-record regressions
were observed failing, then fixed: null metadata/nested executable observations
now reject with source attribution and clear active state, and known inert failure
classification stays inert. Missing returned records have unknown launch status;
only explicit source-bound `UnlaunchedCell` declarations say not launched.
Real Streamlit startup and same-process
root/health HTTP checks returned 200; an earlier separate-call health attempt
returned connection refused and is not claimed as a pass. Compile/whitespace/link
checks and final internal review / exact-head CI are recorded in the PR.

The compressed [negative witness](../../../tests/fixtures/provider_design_analysis/README.md)
copies original actual cell00/capture/summary bytes: 35/37 usable rows; +32 and -38
degrees unavailable; seven later cells NOT_LAUNCHED / zero attempts. Admission
rejects it before BEM. Original execution archive SHA-256
`e779bb00158571541a10419ecccb011fc1c8a5ea32cad40a59e005c59f9082e9`; original
preflight SHA-256 `058a91997442d42df0859a373df1bbb00005fcd882c86616ef5707590f45331a`.
No replay, point repair, provider call or genuine BEM study was performed.

CI trigger inspection is material: standard Tests runs on `cursor/**` pushes,
but PR events target main only. The new Astra-A integration branch uses that
inherited namespace for standard software CI and targets the published integration
base branch above, so its diff contains only this bounded slice. No Cursor agent
is involved. No PR CI event is expected for this base.
Targeting main would include inherited XFOIL changes and trigger a real-provider
qualification, which is not authorized. Do not retarget/trigger that workflow.
The manual reproducibility workflow is not run. Push CI tests the actual head;
there is no separate automatic PR merge-result CI for this non-main base.

## Review focus / limits

Check foreign request/provider/coordinates, complete family and raw point equality,
root semantics, selected policy, stale active state, retained rejection/BEM failure
attribution and report/CSV/JSON provenance. Same-coordinate records must not count
as A+B. Hashes/receipts are content consistency, not build/process attestation.
No genuine-data class is promoted or comparison block removed.

Software acceptance is separate from genuine single-case BEM, a controlled genuine
two-profile comparison and physical qualification. The latter remain unestablished;
`physical_qualification=false`, qualified winner remains null. Mechanical/joint/
clearance/vibration/CFD/FEA/transient evidence is not supplied. Preserve #105 and
the completed probe. Preserve unrelated CSV CRLF/LF working-copy differences.
