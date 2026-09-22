# GEOM-01 — bounded hinge/stow geometry screening

Implemented after PY-06D1, alongside the provisional
[literature measurement registry](literature_measurement_registry.md).
The active design page now exposes an explicit geometry scan without requiring
polars, CFD or prototype measurements. It retains the existing active-draft
parser's hash/schema checks. GEOM-03 separates the geometry-only loader from
BEM's positive-RPM/nonnegative-forward-speed restrictions; operating conditions
do not enter the geometry calculation.

## Reuse and scope

`prepare_geometry_search` binds the full draft TOML, SHA, canonical finite grid,
requirement, implementation hashes and Python version. It validates 1–25
candidates, at most nine values per axis, 64 stations, 601 explicit profile
coordinates, eight blades and 250000 aggregate preview vertices before evaluation.
`run_geometry_search` reconstructs that identity, then reuses the existing
`build_mechanism_geometry_audit`, `build_propeller_preview_mesh` and
`run_grid_search`. Geometry and aerodynamic equations are not replaced.

The supported topology is one rigid tip per blade, zero hinge offsets, a +z hinge
axis, radial open state and negative planar folding within the declared travel.
One explicit coordinate-bound airfoil is required. The proposed stowed angle is
an alternative endpoint for design exploration, not a measured equilibrium or
an automatic change to the canonical hard stops. Every row starts from the same
source geometry; only hinge radius and proposed endpoint vary. No extrapolated
root/tip stations, automatic candidate selection, CAD or physical claim is added.

## Two different path questions

For open radius R, hub radius b, hinge radius h and tip length L=R-h, a moving
centreline point s from the hinge has squared radius
`r² = h² + s² + 2*h*s*cos(theta)`. Over the path from zero toward an angle in
[-pi,0], every such radius is nonincreasing. Consequently the minimum
centreline-to-hub clearance over that proposed path equals the segment minimum
at its endpoint. GEOM-01 reuses the audit's endpoint segment clearance for this
continuous centreline bound; it does not infer surface collision clearance from
time samples. A zero centreline clearance is contact and does not pass the
strictly-positive clearance check.

Full 180-degree stow is a separate question, retained for every row. Nonpenetration
at 180 degrees requires `h-L >= b`, hence `h >= (R+b)/2`. The root segment extends
to h, so the centreline envelope diameter is at least `2h >= R+b`.
For R=125 mm and b=18 mm, the full-fold lower bound is **143 mm**. The 140 mm
target is therefore impossible for full 180-degree folding in this topology,
even if the canonical 100 mm hinge is moved. Equality is a touching bound, not
positive clearance or a surface guarantee.

A 60 mm hinge at -150 degrees illustrates why the proposed path and full 180
path must be separated: it meets the 140 mm centreline envelope with positive
centreline hub clearance on that partial path, while the full 180 path intersects
the hub. This still does not establish a usable propeller. The canonical surface
stations cover only 0.20R–0.98R, and swept-surface/interblade clearances remain
unknown. Chord-inclusive endpoint mesh diameter is reported separately from
centreline diameter. Missing mesh coverage is recorded without inventing a mesh.

All rows retain failed/unknown constraints. Swept-surface and interblade
constraints remain unknown (`None`) on every GEOM-01 row, including when a
search binds candidate-specific GEOM-04 inputs. A bound run rebuilds each
candidate draft and clearance request, gives every candidate its configured
node/feature/hardware limits, and records aggregate ceilings of
`N ×` those limits. It never reuses another geometry's report. A completed
artifact is attached only after request/report SHA, strict finite JSON,
report schema/content, request-context identity, qualification invariants
and query-level accounting checks. `physical_qualification` other than
literal false anywhere in the accepted report tree, or
`full_propeller_clearance` other than null, aborts before attachment so
generic snapshot handling cannot turn the forgery into a failed grid row;
the attached report is the decoded artifact, never rewritten. Malformed JSON, NaN or
Infinity, schema errors, accounting contradictions and programming errors
abort the search. Candidate-domain prepare failures raise
`SurfaceClearanceValidationError` and become bounded
`candidate_validation_failed`; other programming failures from preparation
or execution abort, including `ValueError`, `TypeError`, `SearchError` and
`ArithmeticError` (the last is wrapped as `SearchError` at the prepare
boundary so generic grid search cannot record a failed row). Query and
interval objects must match the GEOM-04 producer fields
(`ClearanceReport` / `ClearanceInterval` / hardware `_row`); missing
`intervals`/`reason`, non-object intervals or non-numeric bounds abort
before size classification. The complete GEOM-04 report is retained under
`details.geom04_clearance` (execution status, candidate/request identity,
artifact hashes, full report or an explicit failure reason). If a valid
payload cannot fit the existing 256 KiB search-details snapshot, only the
evidence attachment is replaced with a bounded oversize descriptor; the
GEOM-01 audit, objective and constraints remain. Serialization or schema
failure is not treated as oversize. GEOM-04 pair status,
witnesses, bounds, intervals, exclusions and hardware provenance stay in
that namespace under a separate classification (`scoped_geom04_violation`,
`scoped_geom04_separated`, `unknown_scoped_geom04`). That label does not
change
`surface_path_clearance` or `interblade_clearance`. `physical_qualification`
stays false and `full_propeller_clearance` stays null. `best_candidate` remains
absent unless every required constraint is True; with the two surface gates
unknown, selection stays blocked. The endpoint mesh is a 2.5D preview, not a
CAD solid.

## Run and verify

```sh
python examples/run_geometry_feasibility.py
python examples/run_literature_modal_audit.py
```

Both print JSON without modifying canonical files. In Streamlit, open
**Tasarım Geometrisi → Geometri fizibilitesi**; select hinge r/R and stowed angles,
then press **Geometri fizibilitesini tara**. Input changes, invalid previews and
failed reruns clear old results. A JSON download includes the original draft,
candidate ledger, source identity and constraints.

TDD observed the absent service and UI button before implementation, plus stale
results after invalid preview before the cleanup fix. Tests cover canonical order,
source identity, unsupported axes/offsets, budgets, missing station span,
partial/full paths, original geometry retention and real Streamlit AppTest runs.
Independent review checked the analytical path argument and 100 separately
sampled paths. Full regression, exact-head CI and final GitHub review precede merge.

## Next bounded work

GEOM-02–04 remain the station, retained-surface and hardware screening path.
This increment only attaches already-scoped GEOM-04 evidence to the GEOM-01
candidate that produced it. It does not change GEOM-01 feasibility gates.
A later reviewed slice would be required before any mapping into
`surface_path_clearance` / `interblade_clearance`. The dashboard search action
still runs unbound unless a later UI slice opts in. The raw literature-data
acquisition/observable adapter remains a parallel task; PY-06D2 fitting still
requires suitable independent measurements and identifiability.
