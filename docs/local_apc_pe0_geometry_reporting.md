# Local APC PE0 source-geometry reporting

This bounded [service](../pyfoldable/application/apc_pe0_geometry_report.py) and
[CLI](../examples/report_local_pe0_geometry.py) report caller-supplied local PE0
bytes. External CAD/STEP is optional. They do not reconstruct a complete solid,
apply a joint, generate coordinates/polars, run BEM/FEA/trajectories or select a
hinge. The broader [hinge assessment](strength_aware_radial_hinge_assessment_proposal.md)
remains **PROPOSED / NOT IMPLEMENTED**; `physical_qualification=false`.

## Source integrity and bounded method

`local_pe0_source_geometry_report_v1` accepts at most 1 MiB, at most 1024 stations,
a bounded source reference, optional expected member SHA-256, a separately declared
nominal product diameter and exactly two distinct global SI hinge radii inside the
hub-to-nominal-tip span. It records actual member hash, title, version/date and
optional member/archive provenance. An archive hash supplied alongside member
bytes is **DECLARED_NOT_VERIFIED**: those bytes cannot verify their container.
No file is silently downloaded. Public repository contents remain first-party
implementation/tests and permissible attribution, not the vendor table or derivative.

The existing [PE0 parser](../pyfoldable/core/apc_pe0.py) remains unchanged and supplies
validated radius/chord/thickness/TWIST and dimensional provenance. The adapter also
validates the complete numeric table, all 14 finite fields, full footer tokens,
exact decimal-integer BLADES and represented footer/row correspondence with that parser.
Unsupported integer-to-binary64/core correspondence fails rather than rounding the count. Unsupported
footer exponent/suffix syntax is rejected rather than accepted by a numeric-prefix
match. Malformed rows, including a bad first cell or nonnumeric text in the active
station region, cannot silently disappear into metadata. The recognized
STATION/CHORD header establishes that boundary before the first numeric row,
even when no positional units row is supplied. Conflicting recognized column positions (including section thickness/area and
centroid fields) fail for every header length; partial-binding diagnostics cannot
excuse contradictions. Known scalar-footer labels are detected before values: an
empty first value or empty duplicate fails. Complete-number and exact-integer
checks remain unchanged. Error paths produce no report; CLI exits 2.

Every row keeps its original zero-based parent index, source line/line number,
number lexemes and all 14 numeric values. Fixed-layout field keys are:
`station`, `chord`, `pitch_1`, `pitch_2`, `pitch_3`, `sweep`, `rake`,
`thickness_ratio`, `twist`, `max_thickness`, `section_area`, `zhigh`, `cgy`, `cgz`.
The three pitch fields remain distinct. Their supplied measurement labels and
definitions are preserved without inventing dimensional meanings; none replaces TWIST.
Nonstation lines preserve all supplied labels, units, definitions and footer text.
Recognized vendor labels include `SWEEP(Y)`, `RAKE(Z)`, `MAX-THICK` and
`CROSS-SECTION`. A recognized 14-cell positional row accepts either bare `RATIO`
or `(RATIO)` in the thickness slot. The compatibility JSON field `supplied_unit`
preserves each source cell literally: `(QUOTED)`, `(LE-TE)` and `(PRATHER)` are
measurement labels, not inferred physical units. Absent or
partially labeled headers remain explicit unresolved-binding diagnostics; the
report does not invent missing unit/definition cells. SI radius/chord/TWIST use the
existing core PE0 inch/degree layout (`in * 0.0254`, `math.radians(TWIST)`) and record
that conversion basis. Unknown layouts are not clearance for another format.

The aerodynamic shortcut `geometry.blade(airfoil_id=...)` is **not called**. It
filters the last row beyond footer RADIUS and assigns a single profile to selected
stations, which would lose relevant source information for this task.

## Complete parent and complementary cuts

One canonical parent identity binds the complete table, source hash, nominal and
footer conventions, all source definitions and transition declarations. Both cuts
copy its **stored** rows: fixed `r <= r_h`, tip `r >= r_h`. They retain global shaft
radii, chord, supplied TWIST, sweep/rake and source-section fields, original indices
and the same parent hash. An existing hinge row belongs to both children. No
interpolation, padding, twist reset or rescaling occurs. Empty/single-row children
remain visible with insufficient-row diagnostics rather than becoming station bundles.

The report labels rows inside HUBRAD, in the HUBRAD-to-HUBTRA transition, in the
HUBTRA-to-RADIUS declared aerodynamic span, or beyond footer RADIUS. Nominal-radius
membership and nonzero chord are separate flags. These are descriptive source
relationships, not aerodynamic usability or joint/structural acceptance.
Observed cut spans, signed hinge endpoint gaps, missing hinge stations and the
independent radius discrepancies remain visible; no radius is silently normalized.

E63/APC12 declarations are retained at their supplied anchors with source lines.
Inboard/outboard declaration indices only locate a station relative to those
anchors; they do not assign a profile or blend. The APC12/NACA4412 equivalence
statement, when supplied, is retained as a **vendor statement**, not a validated
coordinate identity. Thickness-scaling metadata is preserved rather than reapplied.
Unspecified transition geometry and coordinates stay null. Comparison through the
single-coordinate [station comparison service](parent_blade_station_comparison.md)
is explicitly `UNSUPPORTED_UNRESOLVED_SECTION_IDENTITY`. Numeric copy identity is
reported separately and cannot clear mixed-profile comparison or full 3D equivalence.

## Requested source and reproducible local command

The following identities/dimensions are **coordinator-provided provenance**, not
independently reproduced by this implementation task:

- Archive: `PE0-FILES_WEB-202602.zip`, SHA-256
  `85a97375dd9ffaeb38022cef1b5d79ac86c56f2960e9917369ad0e55ce37df38`.
- Member: `PE0-FILES_WEB/13x55MR-PERF.PE0`, SHA-256
  `2972e1b99215f2eb052e586e48cc59730cbfd4f08c6627ea7461a8afa150c30f`.
- Version `v2025-1001`, simulation date 2026-02-24, 51 numeric rows / 14 columns;
  E63/APC12 transition declarations at 3.70 / 6.00 inches.

| Convention | Separate supplied quantity |
| --- | --- |
| Nominal product diameter | 13 in / 330.2 mm |
| Footer RADIUS | 6.47 in / 164.338 mm |
| Last source station | 6.475 in / 164.465 mm |
| HUBRAD | 0.32 in |
| HUBTRA | 1.02 in |
| Comparison hinge positions | Global r = 101.6 mm / 127.0 mm |

Those positions are 8/13 and 10/13 of the nominal 6.5-inch radius (4 and 5 inches).
They are illustrative comparison positions, not recommendations. This 13-inch
manufacturer model is separate from the 250 mm project baseline. Actual binary64
unit conversions/row values are reported; displayed decimal equalities are not
numerical tolerance gates.

```bash
python examples/report_local_pe0_geometry.py /local/13x55MR-PERF.PE0 --source-reference "caller-local APC 13x5.5MR PE0 v2025-1001" --expected-sha256 2972e1b99215f2eb052e586e48cc59730cbfd4f08c6627ea7461a8afa150c30f --archive-sha256 85a97375dd9ffaeb38022cef1b5d79ac86c56f2960e9917369ad0e55ce37df38 --member-name PE0-FILES_WEB/13x55MR-PERF.PE0 --nominal-diameter "13 in" --hinges "101.6 mm" "127.0 mm"
```

Use `--format table` for the complete source table, preserved definitions and cut
index/coverage reports. JSON is deterministic, finite and includes code-content
identities; the returned service SHA hashes canonical UTF-8 JSON without the CLI's
stdout newline. Local output remains subject to source terms and should not be
committed as a public vendor derivative. Hashes identify content, not authenticity.

**Genuine local demonstration: UNAVAILABLE.** Neither the named archive nor member
was found in the available workspace; exact-name and shorter file searches did not
resolve accessible bytes. The coordinator's genuine row count, lexemes, header
layout, cut membership and metadata have not been rerun here. No synthetic result
is substituted for that missing APC demonstration.

[Tests](../tests/application/test_apc_pe0_geometry_report.py) use a first-party
six-inch toy with invented values/section labels and an independently generated
51-row capacity check. A local synthetic CLI check retained six rows, including
its last station beyond its toy footer, and copied cut indices `[0,1] / [2,3,4,5]`
and `[0,1,2,3] / [4,5]`. It is a software demonstration, not APC evidence.
Regression scope includes units/footer/header mismatch, malformed/omitted rows,
source hashes, supplied TWIST, distinct pitch fields, deterministic copying,
missing/insufficient rows, retained definitions and unsupported section comparison.

### 2026-10-03 supplied genuine member — repaired execution

This later execution supersedes the availability limitation above without changing
that historical record. The attached private `APC13x55MR_PR92_genuine_run.zip`
supplied `input/13x55MR-PERF.PE0`; its member SHA-256 was independently verified as
`2972e1b99215f2eb052e586e48cc59730cbfd4f08c6627ea7461a8afa150c30f`.
The original vendor archive was not supplied here; its pinned identity remains
coordinator-declared provenance, not a new archive verification claim. The supplied
pre-repair reports/witnesses are historical evidence, not repaired outputs.

The real, unmocked `report_pe0_geometry` call used
`source_reference="caller-supplied APC 13x5.5MR PE0 v2025-1001"`,
`member_name="PE0-FILES_WEB/13x55MR-PERF.PE0"`, the pinned original archive digest
as declared provenance, and the verified member digest as `expected_sha256`.
It used nominal diameter `0.3302 m` and
global hinge radii `0.1016 m` / `0.127 m`. Runtime: CPython 3.12.14, Clang 22.1.3,
Linux 6.18.44 x86_64 with glibc 2.39. All 51 rows / 14 fields, source lexemes and
values were checked against the actual local member; terminal station `6.4750 in`
was retained. Direct inherited rows and every numeric value were identical,
including binary64 SI fields. Header and unit bindings were recognized; no
measurement label was reinterpreted as a dimensional pitch unit.

| Global hinge radius | Fixed original indices | Tip original indices | Hinge station |
| --- | --- | --- | --- |
| 101.6 mm | 0–27 (28 rows) | 28–50 (23 rows) | Absent, explicit gap |
| 127.0 mm | 0–33 (34 rows) | 34–50 (17 rows) | Absent, explicit gap |

Fresh digests for this execution (canonical JSON excludes the stdout newline):

- Report SHA-256: `201de87a8fc8ccbeb37aba103e512b4f8de77730db0e69e814ab969e711f0026`.
- Parent SHA-256: `f4f4d8f7a7c3b7d1c23577fcb520ba5d73b2e5cbbe1c29569f5f85e59c518bb5`.
- Adapter implementation SHA-256: `e9b4da0eab63bb3ea28645bdc5930fbc79ba640b6a57f304592fad803f066e32`.
- Unchanged core parser SHA-256: `e256dae2fc525f4d5ab07a8ae46d394a5ca6351a7cbc9ddf3fdbd0ced1d7e6ca`.
- Unchanged core models SHA-256: `fec0b429c5201a7e7565205df756d00d344a5d5dd94703b7775d4b74ce17b853`.

Repaired negative witnesses on private in-memory copies reject malformed first
stations, contradictory 13/15-token headers and empty duplicate scalar footers.
Synthetic TDD observed 13 failing new checks / 31 passing prior checks, then
94 affected/parser/generator/comparison/licensing checks passed after repair.
The missing-single-footer cases already rejected at the old final completeness
check; they now reject immediately at their known labels with a missing-value reason.

Remaining diagnostics: unresolved section coordinates/transition geometry,
differing radius conventions and last station beyond footer RADIUS. E63/APC12
declarations, the vendor equivalence statement and thickness-scaling text remain
retained and unqualified. Full input, derived JSON/table and private witness inputs
stay outside public Git history. This receipt is geometry retention/copy evidence,
not experimental performance, BEM, FEA, trajectory, joint strength or hinge selection.
`physical_qualification=false`; broader proposal PROPOSED / NOT IMPLEMENTED.

## Primary references and evidence limits

- [APC geometry documentation](https://www.apcprop.com/propeller-technical-data/) and
  [download index](https://www.apcprop.com/technical-information/file-downloads/):
  spanwise manufacturer geometry and revision provenance.
- [APC performance documentation](https://www.apcprop.com/technical-information/performance-data/)
  and [engineering description](https://www.apcprop.com/technical-information/engineering/):
  proprietary, vortex-based manufacturer calculations, distinct from experiments.
- [UIUC Propeller Database](https://m-selig.ae.illinois.edu/props/propDB.html) and
  [Brandt–Selig, AIAA 2011-1255](https://m-selig.ae.illinois.edu/pubs/BrandtSelig-2011-AIAA-2011-1255-LRN-Propellers.pdf),
  DOI `10.2514/6.2011-1255`: wind-tunnel measurement methodology and low-Re context.
  A comparison must bind the exact tested model/revision, RPM, advance ratio/airspeed,
  coefficient conventions, atmosphere and measurement provenance; an APC SF 10x4.7
  benchmark is not an APC 13x5.5MR measurement or proof of the current specimen.
- Existing [third-party boundary](../THIRD_PARTY_NOTICES.md) and
  [licensing scope](licensing.md) remain controlling.

This slice performs no performance comparison (`performance_comparison=null`) and
imports no RPM/airspeed experiment. Simulation date is not an operating condition.
It does not establish BEM performance, fracture risk, joint strength, an optimum
hinge, accepted CMM-2 evidence, ADR-009 acceptance or physical qualification. C2V-09
fixtures and PR #81/#84/#91 remain unchanged. Complete CAD/section/coordinate and
experimental work retain their separate evidence requirements.
