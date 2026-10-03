# Parent-blade station comparison reporting

This bounded service reports supplied station values and declared source lineage.
It implements only station-level reporting in a separate Draft PR, not the
broader [radial-hinge assessment proposal](strength_aware_radial_hinge_assessment_proposal.md),
which remains **PROPOSED / NOT IMPLEMENTED**. No design freeze or CAD comparison,
solver execution, qualification promotion or overall safe-winner claim follows.

**2026-10-03 superseding workflow clarification:** the primary product workflow
uses internally defined/generated parametric blade and joint geometry without
external CAD/STEP. External references/import, manufacturing export and external
validation are optional routes. Station bundles may originate from an identified
generated design; their provenance must distinguish declared geometry from
manufactured/as-built evidence. The current service only compares bundles and
does not yet generate complementary bundles or complete blade/joint solids.

## Inputs and supported scope

The [service](../pyfoldable/application/parent_blade_comparison.py) accepts four
bounded UTF-8 JSON byte inputs: parent, fixed and tip station bundles using the
unchanged [GEOM-02 parser/provenance](geom02_station_contract.md), and a comparison
declaration. Retain all four input files with the report. Raw and canonical
digests identify bytes, not authenticity. Profile coordinate digests are supplied
identities; the service does not recover or authenticate coordinate files/CAD.

Both children must explicitly be `derived_geometry` with `parent_sha256` equal
to the supplied parent's **canonical station bundle** digest. The declaration
binds each of the three canonical digests. Diameter/hub values must be identical.
One declared deployed shaft frame is supported: all three frame IDs must match,
radial origin is the shaft axis, radii are already global shaft-based, and the
transform is explicitly identity. Arbitrary transforms/offset topology, local tip
coordinates or other frames raise a controlled unsupported-input error. Declaring
a common frame does not prove actual 3D surface alignment.

Declare hinge radius in metres, strictly between hub and tip. Fixed supplied
radii must be at or below it; tip radii at or above it. No local-span conversion,
span scaling or twist reset occurs. Shared hinge stations may explicitly map to
the same parent station across the two children. Within each child, duplicate
child or parent index bindings are ambiguous and rejected. All indices are
zero-based and refer to the exact bound bundle order.

## Comparison declaration

Create the declaration only after parsing the supplied bundles. This code uses
existing files; it does not generate geometry or infer correspondence:

```python
import json
from pathlib import Path
from pyfoldable.application.blade_stations import parse_station_bundle

bundles = {role: parse_station_bundle(Path(role + ".json").read_bytes())
           for role in ("parent", "fixed", "tip")}
declaration = {
    "schema_version": 1,
    "evidence_label": "supplied study inputs; unqualified declarations",
    "hinge_radius_m": 0.1,  # illustrative only; replace with declared placement
    "bundle_sha256": {role: b.canonical_sha256 for role, b in bundles.items()},
    "frames": {role: {
        "id": "study-shaft", "radial_origin": "shaft_axis",
        "pose": "deployed", "transform": "identity",
        "radius_coordinate": "global_shaft_radius"
    } for role in bundles},
    "correspondence": [],  # supply explicit child_index/parent_index rows
    "joint_modifications": []  # supply known differences; absence is not proof
}
Path("comparison.json").write_text(json.dumps(declaration), encoding="utf-8")
```

Each correspondence row has exactly `component` (`fixed` or `tip`), `child_index`
and `parent_index`. For example, `{"component":"tip","child_index":0,"parent_index":2}`
is an illustrative declaration, not a default mapping. Unmapped child stations
are reported without a parent value or difference. Missing mapped parent stations
are listed for each complementary radial span; no nearest lookup/interpolation
or profile-name lineage inference fills them.

Each joint modification has exactly `component`, `child_index`, `description`,
`reference` and `revision`. `child_index` may be null for a separately described
joint-region change without a station sample. Otherwise it references a supplied
child station. Describe gaps, steps, protrusions or other changes with source
identity; no geometry is synthesized from that text. These records are separate
from inherited station comparisons and never excuse a numerical mismatch.
No modifications supplied does not establish an unchanged joint region.

## Output and commands

```bash
python examples/compare_parent_blade_stations.py parent.json fixed.json tip.json comparison.json > comparison-report.json
python examples/compare_parent_blade_stations.py parent.json fixed.json tip.json comparison.json --format table > comparison-table.md
```

The service returns canonical sorted finite JSON, its SHA-256 and a readable
Markdown table. Repeated identical inputs produce identical outputs. Reports
include raw/canonical source identities, provenance and complete canonical bundles,
the bound declaration and its raw/canonical digests, supplied SI values, signed
child-minus-parent radius/chord/twist differences, separate profile-label and
coordinate-digest comparisons, missing stations and signed endpoint coverage gaps.

`EQUAL_SUPPLIED_VALUES` is exact equality of normalized supplied binary64 values
and both profile identity fields. Even a one-ULP discrepancy is reported; this
introduces no tolerance or numerical acceptance gate. Different source unit
conversion paths may therefore produce visible arithmetic differences. The
existing parser's validation policy is unchanged. Endpoint coverage here is
literal descriptive equality to the required span, not continuous geometry or
an alternative GEOM acceptance policy.

`SUPPLIED_STATIONS_MATCH` means every supplied child station has an equal explicit
parent match, no parent station in its complementary span is missing, and all
required span endpoints are supplied. Otherwise the result is `DIFFERENCES_OR_GAPS`.
Neither result accepts a complete 3D surface, joint clearance, strength or safe
winner: those fields remain null and `physical_qualification=false`. No BEM,
FEA, CAD, Streamlit or trajectory path is invoked. Invalid source/declaration
inputs produce a controlled error; the CLI exits 2 instead of issuing a report.

The [tests](../tests/application/test_parent_blade_comparison.py) are explicitly
first-party **synthetic software checks**, not an actual blade/airfoil dataset.
They exercise inherited stations, twist/chord/radius mismatch, incompatible
coordinate identity, incorrect lineage, partial coverage, joint declarations,
unsupported frames and deterministic CLI output. Identified parent geometry/sections,
deployed transforms/joint-region comparison, directional PA-CF evidence and all
strength/clearance/experimental requirements of the broader proposal remain due.

## Next bounded CAD-independent slice (proposed only)

After separate implementation authorization, add one small service/example that
generates the reporting inputs directly from an internally defined design. Reuse
[design drafts](../pyfoldable/application/design_draft.py), the existing
[profile-coordinate catalog](../pyfoldable/core/profile_catalog.py) and
[station parser/export](../pyfoldable/application/blade_stations.py); do not add
a STEP importer, solid generator, UI expansion or solver path in that slice.

1. Validate one identified parent draft and its parameters, source/draft digests,
   units and deployed shaft frame. Bind the actual validated coordinate digest,
   not just a profile name. Record any intentional parent-generation chord/twist
   controls once, then hold that parent realization fixed for both placements.
2. Realize its parent station table with the recorded global-radius operation
   `r = r_over_R * (D/2)`, original chord and twist. Record method/code identity
   and serialize through the existing station parser. This is declared parametric
   geometry, not recovered or measured manufacturing geometry.
3. Accept two explicitly declared hinge radii in the same parent envelope. For
   each, partition existing parent rows into fixed `r <= r_h` and tip `r >= r_h`;
   copy stored SI radius/chord/twist/profile identity directly. Duplicate an
   existing hinge row into both children, with explicit original-index mappings.
   Do not rerun root distributions, change span, reset twist or pass children
   through legacy draft scaling as independent whole blades.
4. If a hinge/root/tip row is absent, retain the missing endpoint/partial coverage;
   no hidden interpolation or extrapolation adds it. Explicit evaluation of new
   stations from an identified parametric function is a separate declared scope,
   not inferred from a sparse table. Fewer than the parser's two required stations
   in either child produces a missing-input diagnostic; do not pad the bundle.
5. Give each child `derived_geometry` provenance with the immutable parent's
   canonical station digest and the placement/generation record. Keep parent
   diameter/hub conventions and emit explicit comparison bindings/correspondence,
   plus supplied joint modifications/identity. Unknown joint parameters, unsupported
   offsets/frames/profile changes or solid geometry remain explicit diagnostics;
   do not invent joint dimensions, material properties or clearance evidence.
6. Feed the emitted bundles/declarations directly to the current comparison
   service/CLI, yielding two deterministic JSON/table reports. Acceptance of this
   future software slice requires lineage/value preservation tests, distinct
   placement/coverage records, unsupported/missing-input regressions and independent
   review/CI. Demonstrations remain synthetic software checks. No performance
   prediction, full-surface equivalence, strength or safe winner is inferred.

This is a proposed next slice, **NOT IMPLEMENTED** by this documentation delta.
Complete parametric blade/joint solids, manufacturing exports and optional external
validation remain separately bounded work; broader design status is unchanged.
