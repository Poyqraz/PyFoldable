# PY-02 — project profile coordinate identity

## Scope and sources (2026-09-01)

One offline coordinate realization now follows each of the five project profiles
through the UI, downloadable draft, geometry preview and existing polar-provider
request. No new aerodynamic model, provider execution, manufactured geometry or
physical qualification is introduced. PR #3 remains separate.

| Exact ID | Bundled realization | Canonical points | Trailing edge |
| --- | --- | --- | --- |
| NACA0012 | Byte-identical copy of `configs/airfoils/NACA0012_81.dat` | 81 | Closed |
| NACA2412 | PDAS, first/common-x Section 2412 table | 51 | Open |
| NACA23012 | PDAS, first/common-x Section 23012 table | 51 | Open |
| NACA4415 | PDAS, first/common-x Section 4415 table | 51 | Open |
| NACA63-412 | PDAS, first/common-x Section 63-412 table | 51 | Closed |

Primary sources inspected:

- [PDAS four/five-digit tables](https://www.pdas.com/sections45.html).
- [PDAS six-series tables](https://www.pdas.com/sections6.html).
- [PDAS Appendix III description](https://www.pdas.com/avd.html): recomputed
  tables, not direct copies of Abbott/von Doenhoff book tables.
- [UIUC coordinate database](https://m-selig.ae.illinois.edu/ads/coord_database.html):
  notes the older NACA 63-412 lower-surface issue and points to corrected PDAS data.
- [PDAS NACA generator description](https://www.pdas.com/naca456.html): six-series
  geometry is not a four-digit polynomial substitution. No Fortran code is vendored.

For the four PDAS profiles, the **first** table with shared upper/lower x positions
was transcribed: all 26 rows, percentage chord divided by 100, six decimal places,
Lednicer upper/lower blocks. The existing parser combines the common leading edge,
producing 51 points. These are relatively coarse reference samples, not a claim of
solver-ready panel convergence. No resampling, smoothing, fitted substitute or
invented intermediate coordinates are applied. Changing sampling later requires a
new coordinate hash and new polars. Attribution boundaries are in
`THIRD_PARTY_NOTICES.md`.

## Contracts

- `load_project_airfoil(id)` uses package resources, not CWD, network or arbitrary
  paths. `catalog.json` fixes IDs, file names, source references, raw DAT SHA-256
  and canonical coordinate SHA-256. The raw hash identifies the **bundled
  transcription**, not the source web page. LF endings are pinned in Git.
- `airfoil_coordinate_sha256` retains the existing provider format exactly:
  SHA-256 of newline-separated `x:.17g,y:.17g` pairs, without a final newline.
  It does not authenticate a source or prove physical agreement.
- `validate_airfoil_definition` checks canonical ordering, normalized unit chord,
  finite values, repeated points, intersections and any claimed hash. It returns
  a fresh metadata snapshot without changing the sampled shape.
- `build_design_draft(..., airfoil_definition=foil)` requires the selected ID to
  match; replaces an existing same-ID definition; preserves coordinates, source
  and scalar provenance in inline TOML. Schema v1 coordinates are additive, but
  coordinate-bearing documents require a matching hash. Legacy coordinate-free
  configs remain readable. Canonical files remain read-only.
- `PropellerPreviewSpec(..., airfoil_definition=foil)` uses these same points.
  Only a duplicate closed-TE endpoint is removed for mesh indexing; the identity
  remains that of the complete canonical loop. Open-TE endpoints remain distinct.
  `section_vertex_count` records actual ring size; `section_point_count` remains
  the legacy analytic sampling control. New mesh fields have optional defaults
  for direct-constructor compatibility. Existing analytic NACA4 callers still work.
- Preparation records coordinate identity per station, and a common top-level
  hash only for a single profile. The active-design service requires **every**
  supplied polar table's coordinate hash to match a coordinate-bearing draft.
  Missing, malformed or mismatched metadata fails closed. Coordinate-free legacy
  callers retain their prior behavior. Service version is now 2.
- Provider cache identity still includes exact coordinates. A changed shape under
  the same ID cannot reuse the same request key. Provider-generated polar tables
  carry the shared coordinate hash. A matching hash is necessary, not sufficient,
  evidence; all active-design results remain `physical_qualification=false`.

## UI and acceptance

The geometry selector offers all five exact IDs, defaulting to NACA2412. The same
loaded definition goes to preview and draft; source and coordinate hash are shown.
A catalog failure removes draft/preparation downloads instead of showing stale
geometry. No BEM solve or backend process runs on selection. The existing 140 mm
mechanism incompatibility remains visible; profile support does not resolve it.

TDD red stages covered the new catalog/API and UI before implementation. Tests
cover all five round trips, exact mesh coordinates, no analytic substitution,
nondegenerate faces, rigid hinge transforms, PDAS anchor values, changed-shape cache
keys, source/coordinate tampering and per-table polar identity. Independent review
found malformed polar metadata could raise `AttributeError`; regression tests were
observed failing before adding controlled `DesignAnalysisError` rejection.

Local verification: **904 passed, 9 skipped**, including 46 new tests. Wheel
build and isolated import directly from the wheel ZIP (outside the repo) loaded
and validated all five profiles. The skipped tests remain explicit; no new
backend availability or physical qualification is claimed.
`compileall` and `git diff --check` passed; a real headless Streamlit process
returned HTTP 200 `ok` from its health endpoint, then was shut down. AppTest
covered all five selections and controlled catalog failure.

Next: **PY-03**, explicit validated polar-bundle upload and active-draft BEM UI.
Do not silently generate polars, reuse the 254 mm benchmark as the 250 mm draft,
or relax bounds to obtain an output.

## 2026-11-09 — sixth selectable profile: NACA4412

The owner requires **NACA4412 appended as the sixth entry**. The original order
NACA0012, NACA2412, NACA23012, NACA4415, NACA63-412 and default NACA2412 remain.
Earlier five-profile statements above describe their dated implementation.

The new asset uses Ralph Carmichael's PDAS [four/five-digit tables](https://www.pdas.com/sections45.html),
**“NACA Section 4412” first/common-x table**, not the adjacent “NACA 4412” table
whose upper/lower abscissae differ. Retrieved/transcribed 2026-11-08. The
[26-row transcription](declarations/pdas_naca4412_common_x_20261108.csv) preserves
all four printed percentage-chord columns at four decimal places. Divide by 100
using exact decimal arithmetic and emit six decimal places in two Lednicer
blocks, as for NACA2412/NACA4415. The existing parser combines the common LE
into 51 upper-TE→LE→lower-TE coordinates. No smoothing, fitting, resampling,
TE closing or generic NACA regeneration occurs. At x/c=1 the upper/lower
ordinates are +0.001295 and −0.001248: open gap 0.002543 chord is retained.

- Bundled DAT byte SHA-256: `fda8c1de8cc295c4cf7b5164d8e200d763db899701043c905657c8c87be8e30c`.
- Canonical coordinate SHA-256: `54c4b6e87914cd036e3a7674c043ebd670596b064b014623aaaf6fadfbfc1fee`.
- These identify the transcription and parsed shape respectively, not the HTML
  page, aerodynamic coefficients or a manufactured blade. Third-party factual
  numeric-subset attribution and license scope remain in
  [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
- This PDAS asset is separate from the historical UIUC NACA4412 selected endpoint
  in the mixed-profile study. No endpoint asset/declaration is replaced or
  relicensed. NACA4412 is not an APC12 or NACA4415 alias.

The catalog loader, internal draft, exact-coordinate preview, configured retained
provider store and existing explicit preparation/run/snapshot/export services
now accept all six IDs. The normal application route needs no CAD, polar JSON,
manifest or path supplied by the user. Selection/rerender only changes geometry
and preparation status. Matching coordinate-bound complete provider evidence,
source-bound template/root declarations and numerical policy remain mandatory.
No applicable genuine NACA4412 family is established or installed. An absent
family produces `missing_applicable_family`; it does not substitute coefficients
or run a provider/BEM. Software positive cases use labeled inert records and an
inert BEM seam; no genuine numerical acceptance follows.

### Catalog metadata compatibility

Original catalog SHA-256 `cab021803ad8832d82cac8954ff6a3548731b9c1aff4a9d6c4642f7bb4d4a0a0`
becomes `18951dba6dc59215c1b196f33637265d9ae01332244809a82d6592bcd077dcd0`.
The original five asset bytes, identities and manifest rows are unchanged.
Newly constructed drafts include the new manifest digest in airfoil metadata,
so even an old profile obtains a new **draft** identity. Provider canonical
preimages bind coordinates/ID/numerical request, not catalog metadata, so old
matching request identities and stored versions remain unchanged and admissible
under fresh checks. Old snapshots retain their original draft/report/provenance.
Application preparation identities also bind current implementation bytes and
store location; they are freshly computed, never migrated or forced to equal
old prepared identities. Changed selections/preparations invalidate active results.

The historical PR97 query diagnostic originally reconstructed drafts from the
live catalog, which no longer reproduced its pinned draft hashes after this
addition. Its replay now explicitly verifies the byte-exact
[original catalog snapshot](declarations/project_airfoil_catalog_20260901.json),
verifies the current selected asset's source/table/raw and coordinate identities
against it, and uses the historical manifest metadata only within that replay.
All original draft/coordinate/design/policy checks remain. Its report and
`five_profile_workflow_unchanged` historical declaration remain byte-identical;
the current UI and ordinary application admission continue using six entries.
Tampered historical manifests or changed assets block replay, not relax it.
