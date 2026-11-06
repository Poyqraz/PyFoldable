# Astra-A → Astra-B: local retained-provider store

Internal automated review is not Astra-B approval. Review the final exact PR
HEAD/tree and ordinary CI recorded in the Draft PR description.

Base: independently reviewed #107 `8f2d38a826b6118ab97273dbd26ef6bbf43d23ae`,
tree `08feaa83ac120f783f3f59cafecbbd9a20a06118`. Branch:
`cursor/astra-a-provider-store-20261106`, stacked onto
`cursor/astra-a-provider-design-integration-20261106`. There are no integration
conflicts or dependency edits. Main, #103–107, their original branches and the
older integration base remain unchanged/unmerged. This file cannot contain its
own future commit hash; the PR records the exact published identity.

## Implemented boundary

`ProviderRecordStore.register_family` is the single documented operator entry.
It retains the independently declared typed plan, exact canonical preimages,
provider/coordinate/source identities and original result/capture/provenance bytes.
Explicit source-bound unlaunched records and unavailable unknown-status slots
remain distinct. Registration is durable storage, not complete-family admission.
No normal deployment data is installed by this increment.

Schema1 manifests have stable content and family/version identities. No-overwrite
blob publication precedes complete reconstruction/integrity/budget checks and the
final atomic manifest link. Failed/interrupted registration exposes no new version;
identical registration is idempotent, conflicting version bytes reject. Pending
files/orphan blobs are ignored. Operator-provisioned parent, private POSIX local
store, no database/service/backup/garbage collector. The existing resource budgets
and small additional local-store I/O caps are documented in the existing contract.

`application_provider_repository()` loads the configured store through
`PYFOLDABLE_PROVIDER_STORE`. It reconstructs the existing typed repository and
reuses the reviewed admission; no approval boolean or second acceptance path.
Selected content/manifest/version/source identities are retained in admission and
immutable report snapshots. Preparation and explicit execution reopen and verify
selected bytes even with a cached caller repository. Missing/corrupt/changed data
blocks the run and clears active request/output. Added versions never replace a
selection. No file references escape the store; symlinks and path-like references
reject. Content hashes do not prove source authenticity or process-image identity.

The existing five-profile no-upload route lists current complete preparation
candidates versus incomplete/rejected records, requires explicit stored-version
choice, then keeps the existing separate prepare/run buttons. Profile changes and
removed selections clear active state without altering saved snapshots. It adds
no user CAD, polar JSON, manifest or filesystem-path input. No dashboard redesign,
template/hinge selection, provider acquisition or scientific-policy change.
Provider records persist locally; **comparison/user-result history stays
session-scoped** with the existing immutable export contract.

## Evidence / review focus

TDD RED: new store tests could not import the absent module. Initial new UI tests
failed before the version list/selection existed. The first working focused suite
passed53 tests; the broader inherited-boundary selection passed197 before final
review regressions. One attempted selection referenced a nonexistent UI test path
and ran no tests; the corrected command below was used.

Internal review reproduced a registration defect: a non-string provider field
accepted by the underlying constructor made post-publication reconstruction fail,
leaving a manifest that poisoned loading of a previously usable store. A second
witness removed the selected manifest between the adapter's first preparation and
execution's fresh admission, leaving ACTIVE_REQUEST behind. Both were observed RED,
then repaired: reconstruction now precedes publication; later run errors clear
both active keys. Tests also cover the retained-byte budget and preservation of
an already usable store after a rejected registration. A further exact-budget
witness showed proposed reconstruction omitted manifest bytes and the aggregate
cost of existing versions. This was observed RED, then fixed by checking the same
projected whole-repository read cost as runtime before publication, under a
nonblocking operator directory lock. A competing writer receives a specific busy
diagnostic, without retry. UI version changes clear both active keys. Final focused results,
including exact-cap identical-registration idempotency (also reproduced RED before
removing an unnecessary second manifest read),
final staged-tree review and exact-head CI are recorded in the PR.

Reproduce using ordinary inert software tests:

```bash
pytest tests/application/test_provider_record_store.py \
  tests/application/test_provider_design_analysis.py \
  tests/application/test_provider_design_admission_repairs.py \
  tests/application/test_profile_bem_comparison.py \
  tests/application/test_polar_upload.py \
  tests/application/test_polar_query_feasibility.py \
  tests/ui/test_managed_provider_design_ui.py \
  tests/ui/test_active_design_polar_ui.py -q
```

New tests actually serialize, close/reopen, use the configured application loader,
prepare and explicitly execute through an inert BEM seam for all five profiles.
They do not monkeypatch the loader to supply an in-memory family. Persistent UI
witnesses use the same actual loader, profile switching, explicit preparation/run,
corruption/removal invalidation and immutable saved history. New tests block
genuine provider/banner/BEM entry points; inert records live only in isolated test
stores. No actual engineering calculation is added or run.

The existing actual negative fixture round-trips unchanged after store close/reopen:
35/37 coefficients, +32° and −38° unavailable, seven source-bound NOT_LAUNCHED cells.
A separately labeled inert unknown-status witness stays distinct. Neither actual
profile has a complete applicable admitted family; BEM is never reached.
Original execution archive SHA-256:
`e779bb00158571541a10419ecccb011fc1c8a5ea32cad40a59e005c59f9082e9`.
Original preflight SHA-256:
`058a91997442d42df0859a373df1bbb00005fcd882c86616ef5707590f45331a`.
Negative fixture SHA-256:
`422b6004acad42dfcb92fac2b84b70d0b153929a969e96a66cbe49a5f29ba066`.
All remain unchanged. No replay, banner, qualification, retry or point repair.

## CI / remaining work

Workflow files are unchanged. Ordinary Tests runs on this inherited `cursor/**`
push namespace (Python3.10/3.11). PR events target main only, so this non-main
stack has no automatic PR-event merge-result CI. Do not retarget to main or trigger
real-provider qualification/reproducibility. Read final exact-head job logs/reviews;
leave CLA unchecked and PR Draft/open/unmerged. Preserve unrelated CSV EOL changes.

The remaining numerical milestone requires complete matching attributable genuine
provider records for a declared case and separately authorized genuine single-case
BEM. A genuine coordinate-distinct two-profile comparison is a further evidence
step. Inert software acceptance, genuine numerical evidence, experimental validation
and physical qualification remain separate. Genuine comparison UNESTABLISHED;
`physical_qualification=false`. No joint-loss, clearance, vibration, CFD, FEA,
transient result, qualified design or geometry/hinge selection is supplied.

### Ordinary CI follow-up

First published head `209897c2565490c1adcce12187da286159997bee`, tree
`abd85435b58f5b3a20df535a9202b28017e955b3`, ran ordinary
[Tests42283089081](https://github.com/Poyqraz/PyFoldable/actions/runs/42283089081).
The Python3.11 job failed the existing
`test_dashboard_avoids_arrow_dependent_convenience_renderers` guard: the new version
list used `st.dataframe`, contrary to the dashboard's existing Arrow-free rendering
boundary. Its summary was1 failed,2093 passed,9 skipped,37 subtests passed. The
same failure was reproduced locally before the correction.

The list now reuses the existing `_render_markdown_table`; persistent AppTest
assertions inspect the actual Markdown candidate/rejection table. Store/admission,
provider/numerical policy and workflow code are unchanged by this follow-up.
Final applicable tests, exact-head CI and independently rechecked tree are recorded
in the same Draft PR; the failed run remains historical and is not reused as a pass.
