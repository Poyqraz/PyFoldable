# GEOM-03 — bounded surface clearance along folding motion

GEOM-03 evaluates the existing preview triangles under the source-bound planar
hinge geometry. It separates three outcomes: `separated` (a continuous lower
bound exceeds the requested clearance), `violation` (an actual surface sample
witness violates that clearance), and `unknown` (bounds or work budgets cannot
resolve the question). It never promotes open meshes to CAD solids or physical
qualification. `full_propeller_clearance` is always null.

## Method and scope

The distinction between discrete collision, distance/tolerance queries and
continuous collision is also made in the primary
[FCL project documentation](https://github.com/flexible-collision-library/fcl).
GEOM-03 is a small Python implementation of conservative bounding-volume tests;
it does not install or claim the capabilities of FCL's narrow-phase algorithms.

For a path interval of width w ≤ pi, a moving surface point at planar distance r
from its hinge moves at most **2 r sin(w/4)** from its midpoint pose. A bounding
volume hierarchy stores each triangle group's original box and maximum vertex
radius. Its midpoint rotated box, expanded by this motion bound, encloses every
triangle throughout the interval: triangle interiors are convex combinations
of the vertices. Euclidean distance between disjoint expanded boxes is a lower
bound on the distance between the enclosed surfaces. Each relevant BVH pair must
pass; unresolved pairs trigger angular subdivision or remain unknown.

Overlapping boxes are never collision evidence. Vertices and triangle centroids
at an interval's midpoint can provide an upper-bound witness of a clearance
violation. The report stores the witness angle explicitly. A witness applies at
that angle, not throughout the containing interval. Unvisited intervals remain
unknown. Zero requested clearance does not turn overlapping boxes into a contact
detector: intersection without a suitable witness can remain unknown.

The absolute floating-point guard uses 4096 eps × 64 m for an input domain with
coordinates/pivots limited to ±10 m. This is a conservative engineering numerical
guard, not interval-arithmetic verification, mesh-resolution error, manufacturing
tolerance or physical validation. Source units are SI throughout the engine.

## Contact regions and hub obstacle

The existing mesh is split into fixed root and moving tip parts. Surface triangles
are clipped against explicit reference-radial planes; whole boundary faces are
not silently dropped and no new root/tip airfoil section is extrapolated.

- Root attachment exclusion: hub radius through hub radius + declared width.
- Hinge exclusion: hinge radius ± declared half-width; each side moves with its
  own rigid part.
- Defaults are zero. Positive exclusions require a source/revision reference.
- Each band is limited to a quarter of its corresponding segment; empty retained
  parts are rejected. The excluded hardware is explicitly not evaluated.

Queries cover retained root/tip surfaces of each blade, all interblade part pairs,
and each part against an infinite cylinder of the declared hub radius. The
infinite cylinder is a conservative obstacle because measured hub height is not
available. Intrusion into this envelope is not proof of collision with the real
finite hub. Exclusions, missing station span, open ends, solid containment,
asynchronous blade motion and undeclared hardware remain outside the result.

All tips rotate synchronously about zero-offset +z hinges, starting at zero and
ending inside the source's negative-angle travel. Non-planar or unsupported hinge
geometry is rejected. This is geometry screening, independent of RPM or inflow;
BEM's positive-RPM/nonnegative-inflow requirements remain unchanged.

## Application contract and budgets

`prepare_surface_clearance(draft, SurfaceClearanceInputs(...))` validates without
building a mesh. `run_surface_clearance(request)` reconstructs the source identity
before work. The request binds complete draft TOML, canonical source/draft hashes,
profile coordinates, contact declaration, controls, implementation hashes and
Python version. Reports retain all these inputs, scoped query results, triangle
counts, coverage gaps, excluded regions and used work budget.

At most eight blades, 64 input stations, 601 profile coordinates and 12000 clipped
triangles are supported, with a conservative triangle estimate before meshing.
Application diameter/chord caps are 2 m. A single application report shares at
most 200000 BVH node comparisons across all pairs (default 50000; UI default
20000), maximum subdivision depth 8 and maximum attempted intervals 255 per
pair. Pending pairs after global exhaustion remain unknown; no penalty value,
guessed separation or success is substituted. BVH construction is bounded by the
triangle limit but is not counted as a node comparison.

The existing GEOM-01 candidate search remains separate: this report checks the
active design, not every different hinge position in a grid. It does not turn
GEOM-01's uncomputed surface/interblade constraints into passed constraints.
A later GEOM-01 readiness diagnostic may read an accepted report; it does not
rerun this solver and `preconditions_satisfied` is not a GEOM-01 gate value.
The current open-surface model still duplicates the hinge station into the
root and tip, so surface-path readiness keeps that shared contact unresolved.

## Workspace and UI corrections

Open **Tasarım Geometrisi → Katlanma yolu · Yüzey açıklığı**. Declare endpoint,
clearance, optional contact bands and source; click the explicit run button.
The table distinguishes continuous lower bounds from witnessed sample values.
The interval plot uses green for bounded separation, gray for unresolved/sampled
intervals and red points for witnessed violations. At most 256 intervals are
plotted; the JSON retains the complete ledger. Untouched inputs/navigation do
not rerun analysis, while invalid inputs, draft changes and failed reruns clear
old results.

The existing UI audit found and fixed two regressions: navigating away no longer
silently discards the applied station source/form values/pending table edits;
geometry-only scans now work at RPM=0 without weakening aerodynamic checks.
Temporary invalid geometry clears stale reports while preserving the user's
chosen clearance, endpoint and other controls when those widgets reappear.
Uploads are retained as source bytes through navigation, with explicit removal
and a clear-source button. Restricted uploader/editor widget state is never
assigned by the application. Plotly width options are chosen from the installed
Streamlit API to remove new-version warnings while retaining 1.40 compatibility.

## Verification and remaining work

TDD covers analytical distances, midpoint approaches missed by endpoints,
triangle-interior inclusion, both rotating pivots, degeneracy, budget exhaustion,
strict finite inputs, request tampering, clipping, partial coverage, positive
full-span retained-surface separation, explicit UI runs and stale results.
The independent mathematical review additionally checked 358176 sampled
vertex/centroid poses across randomized motions. Such samples supplement the
enclosure argument; sampled success alone never proves continuous separation.

Next: GEOM-04 should add a reviewed triangle-level distance/contact refinement for
unresolved boxes and support explicitly supplied joint/hub solid geometry.
Asynchronous motion needs its own contract. Qualified hardware clearance,
strength, aerodynamics and deployment still require suitable engineering data.
