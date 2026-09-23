# GEOM-04 — refined surface clearance and declared hardware

GEOM-04A was merged in PR #62. The integration adds triangle-level refinement,
source-bound hardware and the existing workspace's explicit clearance action.
It remains geometry screening: `physical_qualification=false`,
`full_propeller_clearance=null`. GEOM-01 candidate selection is not promoted.

## Distance and continuous motion

`geometry/triangle_distance.py` computes exact rational predicates and squared
minimum distances for the supplied floating coordinates. Point/face, edge/edge
and explicit edge/face intersections cover nondegenerate, coplanar and degenerate
triangles. Outward-rounded square-root bounds enclose the exact distance.
Witness points are rounded display coordinates; feature IDs refer to their
exact rational originals. Unsupported precision or exhausted work gives unknown.

GEOM-03's expanded BVH boxes remain the first stage. Overlapping leaves use the
new distance interval. For midpoint lower bound d and interval width w, subtract
both parts' maximum motions `2*r*sin(w/4)`, plus a numerical guard. Every relevant
pair must pass before the whole interval is separated. A close-point witness
only establishes a violation at its reported angle. The infinite-cylinder
fallback is refined using the distance to the triangle's XY projection.

At zero requested clearance, surface contact remains an unresolved clearance
query with a separate contact observation. Identity poses preserve their input
coordinates exactly. Contact after a nontrivial floating rotation is labeled
`rounded_pose_contact`, not an exact geometric intersection certificate.
Positive-clearance witnesses and separation bounds include transform guards.

## Explicit hardware

The optional JSON contract supports one finite-cylinder hub and closed convex
triangular polyhedra. No hardware dimension is inferred from the blade preview.
Closed, consistently outward, convex, nondegenerate manifold topology and positive
volume are checked with rational predicates. General nonconvex CAD, STEP/STL
conversion and automatic topology repair remain unsupported.

A finite cylinder is bracketed by inner and outer convex prisms (8–32 sides).
Their enclosure and approximation error are checked against the supplied radius;
the inner geometry gives upper distance bounds, the outer geometry lower bounds.
Caps and solid containment are included. Coincident solids require a common
strict-interior witness, rather than relying on boundary intersections alone.

Transforms retain exact affine vertices for containment and account for conversion
to floating triangles in distance bounds. The application accepts penetration
only when an interior-margin lower bound exceeds tolerance and transform guard.
The tolerance weakens separation and violation conclusions in opposite directions;
near-boundary cases remain unknown. This is not a formal trigonometric proof or
physical safety certification.

Bindings are one-based: `hub`, `blade_1_root` through `blade_8_tip`, restricted to
the current blade count. All geometry starts in `body_local` coordinates:

| Binding | Origin before folding | Axes and motion |
|---|---|---|
| `hub` | Rotor origin | Rotor axes; stationary |
| `blade_N_root` | Rotor origin | Open blade axes; blade azimuth applied; stationary |
| `blade_N_tip` | Its hinge | Open blade axes; blade azimuth then hinge rotation |

The declared transform maps the supplied geometry into that body-local frame.
The finite hub must share the active rotor axis and hub radius; its explicit
height/axial offset determine the finite obstacle. It replaces only the infinite
hub queries. Other uploaded hardware adds surface/solid and solid/solid queries.
Attachment exclusion bands still affect blade surfaces only. Hardware pairs are
never silently ignored, including parts expected to contact after assembly.

## JSON example — synthetic, not measured project data

This example matches an 18 mm active hub radius. Its height and tolerance are
software-fixture values, not recommendations or engineering measurements.

```json
{
  "schema_version": "pyfoldable.hardware.v1",
  "units": "mm",
  "provenance": {
    "kind": "synthetic",
    "source": "Documentation-only example",
    "revision": "v1",
    "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "bodies": [{
    "name": "hub",
    "binding": "hub",
    "frame": "body_local",
    "transform": {
      "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
      "translation": [0, 0, 0]
    },
    "tolerance": 0.01,
    "geometry": {
      "kind": "finite_cylinder",
      "radius": 18,
      "height": 20,
      "segments": 16,
      "approximation_tolerance": 0.5
    }
  }]
}
```

Use the real upstream source hash for actual supplied data. Provenance `kind` may
be `synthetic`, `literature`, `measurement` or `cad`; it is a declaration, not
independent qualification. Polyhedra use `geometry.kind=convex_polyhedron`,
`vertices` (xyz arrays) and `faces` (zero-based triangular vertex indices).
Length units are m/mm/cm; rotation matrices are dimensionless. Unknown fields,
duplicate keys and unsupported schemas are rejected.

## Budgets, identity and UI

Hardware uploads are limited to 256 KiB, 16 bodies, 64 vertices and 128 faces per
polyhedron. Source vertices are bounded to ±10 m; posed/query vertices to ±64 m.
Exact rational intermediates are capped at 4096 bits. Precision failure returns
unknown in queries; unsupported transforms fail validation.

The report shares BVH comparisons, triangle feature tests and hardware primitives
across all jobs. Defaults are 50000 / 2048 / 256 (UI BVH default 20000); maxima
are 200000 / 200000 / 10000. A hardware primitive is either a bounding-volume
check, one bounded convex clipping operation or one bounded triangle-distance
query. Budgets are not interchangeable wall-clock units. Unvisited pairs and
intervals remain unknown. Mesh/depth/interval limits from GEOM-03 remain intact.

Report schema 2 binds draft, profile, complete hardware source, raw/canonical
hashes, tolerances, budgets and implementation hashes. Result rows retain method,
contact status, witness points/angles and separate lower bounds. Changing input
or implementation invalidates the old request. Hardware uploads persist across
navigation, with explicit removal; invalid/oversized files block execution.

Open **Tasarım Geometrisi → Katlanma yolu · Yüzey açıklığı**. Upload hardware only
when its declared source is available, choose budgets and run explicitly. The
report can be downloaded as JSON. Unchanged rerenders do not rerun analysis.

## Verification boundary

TDD covers analytical distances, exact rational reference comparisons, motion
bounds, shared-solid interiors, caps/sidewalls, transform composition, precision
and work exhaustion, source identity and AppTest lifecycle regressions. Real
Streamlit startup is checked separately. Independent review, Cursor Bugbot,
exact-head CI and merged-tree comparison are integration gates.

GEOM-01 can attach these scoped reports to the candidate whose draft and
request were rebuilt, after cryptographic request/report identity checks,
strict finite JSON, report schema/content, qualification invariants and
query-level accounting. Query and interval fields are checked against the
GEOM-04 producer contract (`ClearanceReport`, `ClearanceInterval`, hardware
`_row`); malformed interval evidence aborts before oversize classification.
Invalid qualification, schema or accounting aborts;
a valid report is attached unchanged. Each search candidate receives the
configured GEOM-04 budgets unchanged; the search records aggregate ceilings
of `N ×` those limits. The complete report is retained under
`geom04_clearance` as evidence only: the evidence namespace itself does not
assign True or False to GEOM-01 `surface_path_clearance` or
`interblade_clearance`. An optional later policy,
`geom01_negative_clearance_v1`, may read that accepted report and set either
gate to `False` or leave it `None`; it never promotes `True` and it does not
mutate the report. It classifies `hardware_surface` and `hardware_pair` by
producer role, not by whether a hardware name looks like a blade part. A
`violation` is usable only when the query witness and the single violation
interval witness are exactly equal and strictly below the policy threshold;
a contradictory violation aborts the search. Missing geometry and evidence
remain explicit gates. A separate diagnostic,
`geom01_positive_readiness_v1`, may read the final accepted report and report
proof prerequisites only. It does not execute this solver, does not mutate the
report, and does not set `surface_path_clearance` or `interblade_clearance`.
`preconditions_satisfied` is not `True`. Surface-path readiness keeps
`shared_hinge_contact_domain_unresolved` under the current open-surface model.
A separated claim is judged against this solver's own requested clearance
before any readiness-question comparison. Readiness arithmetic failures abort
the search.
Asynchronous motion, general CAD solids and physical qualification require
separate work.
