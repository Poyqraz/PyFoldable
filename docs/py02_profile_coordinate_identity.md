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
