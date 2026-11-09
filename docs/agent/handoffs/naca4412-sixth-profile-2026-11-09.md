# Astra-B handoff: sixth catalog profile, NACA4412 — 2026-11-09

## Scope and base

Implements the owner's sixth-profile requirement on reviewed PR108 HEAD
`df9571542594c5f51206a4bce3cc5ff9bf107b63`, tree
`1773d9bb2146efda7b90a284654410779b09b9eb`. Live #108 was Draft/open/unmerged.
This separate Draft targets `cursor/astra-a-provider-store-20261106`, not main.
The final exact HEAD/tree and ordinary CI links are in its PR body. Main and
#103–111 are not modified, retargeted or merged. #111 remained at
`3ab98f23b9e4e3c1e1f060dd57b5f2806cc2c87c`.

NACA4412 is appended to the original five ordered IDs. Default NACA2412 remains.
[Coordinate/source contract](../../py02_profile_coordinate_identity.md#2026-11-09--sixth-selectable-profile-naca4412)
records exact PDAS first/common-x table transcription and attribution; this is
not the separate historical UIUC NACA4412 mixed-profile selected endpoint, APC12,
or NACA4415. Original five DAT bytes, coordinate hashes and manifest rows remain.

New asset byte SHA-256:
`fda8c1de8cc295c4cf7b5164d8e200d763db899701043c905657c8c87be8e30c`.
Canonical coordinate SHA-256:
`54c4b6e87914cd036e3a7674c043ebd670596b064b014623aaaf6fadfbfc1fee`.
All 26 source rows retain their printed precision through decimal percent/100
conversion; existing Lednicer parser yields 51 points. Open TE upper/lower at
x/c=1: +0.001295/−0.001248, gap 0.002543. No resampling or TE closing.

## Implemented application and UI connections

The existing package-resource catalog loader and selector feed the same actual
coordinate definition to draft construction and 2.5D preview. Changing profile
preserves parent dimensions, chord/twist, hinge and operating inputs; six distinct
coordinate/draft identities share one planform and condition identity in tests.
The existing configured local-store route admits exact selected-profile records,
creates its internal polar bundle, requires explicit prepare/run, and uses the
existing immutable snapshots and JSON/CSV references. No new solver, storage,
provider scheduling or UI layer is introduced.

The UI explains geometry selection separately from numerical-data readiness.
Selecting/rerendering does not solve. Missing applicable family shows its specific
diagnostic and no run/download result. The API retains explicit attempted-selection
rejection with null totals. Without any selected family/policy, the UI does not
invent them to create a rejection snapshot. Selected-family execution failures
retain existing immutable attribution and null totals. Normal users do not supply
CAD, polar JSON, manifests or paths. Deployment operators use the existing store
entry point; no production records are populated by this PR.

## Compatibility: observed change and bounded fix

Catalog digest changes from
`cab021803ad8832d82cac8954ff6a3548731b9c1aff4a9d6c4642f7bb4d4a0a0` to
`18951dba6dc59215c1b196f33637265d9ae01332244809a82d6592bcd077dcd0`.
New drafts retain the new digest. For unchanged canonical inputs NACA0012 draft
changes from `d993635db17360f767cff4f26226b3f238de9cd3fb7657c8180247366f2b4d4f`
to `cda8407afec959b1a8d74982b0d28b48dc6ba7b3a202a557876163a3ee3ad7f8`;
NACA2412 from `c3200882dbe6c1f0771bb89772ea8becb4ee143dc6929c4f9346fe55da4371ae`
to `4dc0b76ec1dd62d5cd87fdbb78cbc9ab24554dcd162a4ff195e8275fc8ed1535`.
NACA4412 draft for those declared inputs is
`ac3c31db1897cc1f79c7c799a538975e8872244ed70819e94cfcda2af55ad815`.

Canonical provider requests exclude catalog metadata, so old coordinate-bound
request preimages/digests remain valid. Existing saved snapshots and store blobs
are never rewritten. A pre-append [PR108 inert compatibility fixture](../../../tests/fixtures/provider_design_analysis/pr108_catalog_inert_compatibility.md)
retains an actual old draft, store version, snapshot and CSV created before the
catalog mutation. The real loader reopens it; its request/version identities and
saved snapshot/CSV remain unchanged. Fresh admission succeeds with old or new
matching draft. Application preparation also binds implementation bytes and
actual store path, so moved stores/current code generate fresh preparation IDs;
tests do not weaken this attribution to force a historical digest match.

A reproduced compatibility failure affected historical `polar_query_feasibility`
replay: current metadata no longer matched its old PR97 draft pins. The fix is
explicit historical catalog snapshot verification followed by current selected
asset source/table/raw/coordinate equality and historical metadata reconstruction
only for that replay. Existing design/draft/coordinate/policy guards remain.
Its archived report reproduces byte-for-byte, including dated five-profile schema.
The active application always uses the six-entry current catalog. Tampered snapshot
and changed-shape replay tests reject. No archived report was regenerated.

## Verification and UI evidence

TDD RED: sixth-ID assertions and NACA4412 preparation failed before implementation.
The first focused run also reproduced historical draft-pin incompatibility;
the bounded historical-input fix passes the unchanged report equality check.
Two test assumptions were corrected without production workarounds: prepared
application identities bind code/store location, and opening a store object alone
does not create an empty on-disk deployment layout.

**175 focused tests passed** on local Python3.12; the separate installed-wheel check also passed. One external anyio/pytest
future-deprecation warning; no focused skips. Command:

```bash
PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 python -m pytest -q \
  tests/application/test_project_airfoils.py \
  tests/application/test_profile_bem_comparison.py \
  tests/application/test_six_profile_compatibility.py \
  tests/application/test_provider_design_analysis.py \
  tests/application/test_provider_record_store.py \
  tests/application/test_polar_query_feasibility.py \
  tests/ui/test_managed_provider_design_ui.py \
  tests/ui/test_streamlit_dashboard.py tests/test_license_policy.py
```

- Six distinct catalog identities; original five byte/hash assertions; exact PDAS
  numeric-table reconstruction and open TE; exact-coordinate preview, no analytic
  substitution; one shared planform/condition across all six.
- Separate packaging command: `python tests/packaging/check_six_profile_wheel.py`
  with the existing `pyproject.toml` build requirements (`setuptools>=77.0.3`,
  `wheel`) preinstalled. It copies the source to a temporary area. Internal review
  reproduced missing build backends in a clean environment; this explicit check
  is therefore outside ordinary pytest and adds no CI/runtime dependency.
  Wheel built offline, installed with `pip --target` into an isolated directory,
  then imported under `python -I` outside the checkout: all six assets load.
- Actual configured store with all six inert families, closed/reopened through the
  normal loader; explicit inert preparation/run; no loader replacement in those
  persistence/UI witnesses. Inert records are test-only.
- AppTest: unchanged default, six options, actual coordinate captions, no upload,
  NACA4412 success/failure, rerender without solve, NACA4412→NACA0012→NACA4412
  invalidation, immutable saved history and JSON/CSV linkage. One coordinate
  identity is not a controlled distinct-profile comparison.
- Foreign profile, coherent same-name/wrong-shape family, foreign returned request,
  missing family, incomplete data and stale active state reject. New tests block
  genuine provider/banner/BEM entry points and use only an explicit inert seam.
- Real headless Streamlit startup: root HTTP200 and `/_stcore/health` HTTP200 `ok`;
  process stopped afterward. This smoke check is separate from interactive AppTest.

Genuine negative fixture SHA-256 remains
`422b6004acad42dfcb92fac2b84b70d0b153929a969e96a66cbe49a5f29ba066`.
It remains 35/37, +32°/−38° unavailable, seven NOT_LAUNCHED; admission rejects as
incomplete before BEM, including after store reopen. Original execution archive
identity `e779bb00158571541a10419ecccb011fc1c8a5ea32cad40a59e005c59f9082e9`
is preserved. #111 archive `592bc73eb29fe0077f3751e502e0a56590ff8cc6cdb6690b56bb2ada8b458112`
and section-CFD package `f098e36eb823e59bc7766475aa5afeaffb0bd034742f3c59e86fda8d9184d402`
were rehashed unchanged. Mixed-profile endpoint declaration and historical query
reports match the base byte-for-byte. An unrelated report CSV line-ending change
in the worktree is excluded from this PR.

Only ordinary Tests push CI is applicable to `cursor/**`; the stacked non-main
base does not trigger the main-target PR merge-result workflow. Final Python3.10/
3.11 results and exact HEAD are recorded in the PR body. Qualification and
reproducibility workflows are not dispatched. Independent internal review verified the source transcription and passed 24 inert
compatibility/UI checks; its packaging-harness finding was addressed as above.
This is not Astra-B approval of this new PR.

## Remaining numerical evidence

Software support for NACA4412 is not a genuine polar family, BEM result or profile
ranking. Complete matching applicable evidence, retained provenance, current
admission and explicit BEM still remain necessary. All source-bound root-datum,
longer-proximal/shared-parent, numerical-policy, immutable attribution and
coordinate-distinct comparison restrictions remain. No genuine provider/CFD/BEM
study, geometry/hinge selection, coefficient repair or qualification change.
Genuine single-case and two-profile acceptance UNESTABLISHED;
`physical_qualification=false`. No merge.
