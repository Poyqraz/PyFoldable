# Chord-bearing surface screening, 50 mm hinge

Retained preview-mesh and GEOM-03 screening of one existing trial hinge. This does not establish finite-hub clearance, controlled folding, strength, vibration, aerodynamic validity, or qualification.

physical_qualification: false
Qualified winner: none
full_propeller_clearance: null

Main head `022b466303c59b8c0adb02f935f9c2f065b0e2b5`.
Parent packet head `3db6b8909aa3e929a557699d98593fccb3fe8c4a` SHA-256 `5df16176a8774b02a0b2d3bd5dfc3b98c2e272761714f5f7b5c743d7f1388531`.
Parent canonical SHA-256 `1a149afec4cb192703a597e86717e5040d15e3c7fcb1697b4898ea3d26b6eada`.
PR #100 study head `56a3b52a439c408cbdd13ae3baf8c43fa577bf71` SHA-256 `f3c3e927c0ede938e5e770cce2eab405ca8413cec997eb17ab620b5fe22a7124`.
PR #101 study head `3ed68e9b8a2f1c9424204f1fb39404e000f539cf` SHA-256 `8d219acb44aa7cdd5fcf7d858ab1a59636d9aa413214d0756384102a8e4e2815`.
Study draft SHA-256 `89dfdd1907e9fe2221adea7ffa193f1849fbc1d6052dced1dafe5d20279c07d1`, hinge `50 mm` from `trial_50_mm`.
The study-draft identity is separate from the parent canonical identity.

## Declaration

Requested clearance is 0 m so the existing service can report modeled contact. It is not a manufacturing acceptance margin.
Attachment exclusions remain 0 m. No contact-band source is declared. Budgets are the existing defaults. There is no automatic retry and no budget increase.
Measured hub height is not available. The obstacle is an infinite cylinder of the retained hub radius. A bound against it is not collision evidence for a real finite hub, and a separated bound does not cover unmeshed span.
Nothing in this run adds joint relief, hardware, hub height, endcaps, or a surface across the uncovered root or tip span.

## Deployment preview

Deployment is a preview mesh at 0 deg. It is not a fourth GEOM report.

centerline_envelope_radius_m: 0.125
mesh_envelope_radius_m: 0.12264577843342518
axial_min_m: -0.0038213264999736912
axial_max_m: 0.010846400445746203

## Proposed stops

### -120 deg

modeled_surface_status: unknown
classification: blocked
station_span_complete: false
root_gap_m: 0.006999999999999999
tip_gap_m: 0.0025000000000000022
node_comparisons: 50000
feature_tests: 2048
full_propeller_clearance: null

Preview mesh, separate from the centerline quantity:

centerline_envelope_radius_m: 0.06614378277661477
mesh_envelope_radius_m: 0.06844487165894234
axial_min_m: -0.0038213264999736912
axial_max_m: 0.010846400445746203
pinned_centerline_diameter_m: 0.13228756555322954

Complete query ledger:

| Kind | A | B | Status | Contact | Reason | Intervals | Lower bound m | Witness m |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hub | blade_1_root | hub_envelope | separated | separated | continuous conservative mesh bounds against infinite hub cylinder | 1 | 0.0069999998835846775 |  |
| hub | blade_1_tip | hub_envelope | separated | separated | continuous conservative mesh bounds against infinite hub cylinder | 2 | 0.0002162650135510251 |  |
| hub | blade_2_root | hub_envelope | separated | separated | continuous conservative mesh bounds against infinite hub cylinder | 1 | 0.0069999998835846775 |  |
| hub | blade_2_tip | hub_envelope | separated | separated | continuous conservative mesh bounds against infinite hub cylinder | 2 | 0.00021626501355102162 |  |
| own_root_tip | blade_1_root | blade_1_tip | unknown | unknown | unresolved boxes or subdivision/comparison budget; no collision conclusion | 34 |  |  |
| interblade | blade_1_root | blade_2_root | unknown | unknown | global_budget_exhausted | 0 |  |  |
| interblade | blade_1_root | blade_2_tip | unknown | unknown | global_budget_exhausted | 0 |  |  |
| interblade | blade_1_tip | blade_2_root | unknown | unknown | global_budget_exhausted | 0 |  |  |
| interblade | blade_1_tip | blade_2_tip | unknown | unknown | global_budget_exhausted | 0 |  |  |
| own_root_tip | blade_2_root | blade_2_tip | unknown | unknown | global_budget_exhausted | 0 |  |  |

### -135 deg

modeled_surface_status: unknown
classification: blocked
station_span_complete: false
root_gap_m: 0.006999999999999999
tip_gap_m: 0.0025000000000000022
node_comparisons: 50000
feature_tests: 2048
full_propeller_clearance: null

Preview mesh, separate from the centerline quantity:

centerline_envelope_radius_m: 0.05311966811926533
mesh_envelope_radius_m: 0.06386235284621412
axial_min_m: -0.0038213264999736912
axial_max_m: 0.010846400445746203
pinned_centerline_diameter_m: 0.10623933623853066

Complete query ledger:

| Kind | A | B | Status | Contact | Reason | Intervals | Lower bound m | Witness m |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hub | blade_1_root | hub_envelope | separated | separated | continuous conservative mesh bounds against infinite hub cylinder | 1 | 0.0069999998835846775 |  |
| hub | blade_1_tip | hub_envelope | separated | separated | continuous conservative mesh bounds against infinite hub cylinder | 3 | 6.659138525903427e-05 |  |
| hub | blade_2_root | hub_envelope | separated | separated | continuous conservative mesh bounds against infinite hub cylinder | 1 | 0.0069999998835846775 |  |
| hub | blade_2_tip | hub_envelope | separated | separated | continuous conservative mesh bounds against infinite hub cylinder | 3 | 0.00014867284226610655 |  |
| own_root_tip | blade_1_root | blade_1_tip | unknown | unknown | unresolved boxes or subdivision/comparison budget; no collision conclusion | 33 |  |  |
| interblade | blade_1_root | blade_2_root | unknown | unknown | global_budget_exhausted | 0 |  |  |
| interblade | blade_1_root | blade_2_tip | unknown | unknown | global_budget_exhausted | 0 |  |  |
| interblade | blade_1_tip | blade_2_root | unknown | unknown | global_budget_exhausted | 0 |  |  |
| interblade | blade_1_tip | blade_2_tip | unknown | unknown | global_budget_exhausted | 0 |  |  |
| own_root_tip | blade_2_root | blade_2_tip | unknown | unknown | global_budget_exhausted | 0 |  |  |

### -150 deg

modeled_surface_status: unknown
classification: blocked
station_span_complete: false
root_gap_m: 0.006999999999999999
tip_gap_m: 0.0025000000000000022
node_comparisons: 50000
feature_tests: 2048
full_propeller_clearance: null

Preview mesh, separate from the centerline quantity:

centerline_envelope_radius_m: 0.05
mesh_envelope_radius_m: 0.0609030645646491
axial_min_m: -0.0038213264999736912
axial_max_m: 0.010846400445746203
pinned_centerline_diameter_m: 0.1

Complete query ledger:

| Kind | A | B | Status | Contact | Reason | Intervals | Lower bound m | Witness m |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hub | blade_1_root | hub_envelope | separated | separated | continuous conservative mesh bounds against infinite hub cylinder | 1 | 0.0069999998835846775 |  |
| hub | blade_1_tip | hub_envelope | separated | separated | continuous conservative mesh bounds against infinite hub cylinder | 5 | 0.0002926829112883528 |  |
| hub | blade_2_root | hub_envelope | separated | separated | continuous conservative mesh bounds against infinite hub cylinder | 1 | 0.0069999998835846775 |  |
| hub | blade_2_tip | hub_envelope | separated | separated | continuous conservative mesh bounds against infinite hub cylinder | 5 | 0.00010410541659203881 |  |
| own_root_tip | blade_1_root | blade_1_tip | unknown | unknown | unresolved boxes or subdivision/comparison budget; no collision conclusion | 30 |  |  |
| interblade | blade_1_root | blade_2_root | unknown | unknown | global_budget_exhausted | 0 |  |  |
| interblade | blade_1_root | blade_2_tip | unknown | unknown | global_budget_exhausted | 0 |  |  |
| interblade | blade_1_tip | blade_2_root | unknown | unknown | global_budget_exhausted | 0 |  |  |
| interblade | blade_1_tip | blade_2_tip | unknown | unknown | global_budget_exhausted | 0 |  |  |
| own_root_tip | blade_2_root | blade_2_tip | unknown | unknown | global_budget_exhausted | 0 |  |  |

## Reading the blocked result

Every path is unknown and blocked. Hub rows that say separated are continuous lower bounds of the retained triangles against the infinite cylinder. They leave the uncovered root and tip span, the shared hinge, and the interblade pairs unresolved. The first own-root/tip query exhausts the default node and feature budgets without a separation or violation witness. Later own-root/tip and interblade rows stay unknown because the shared global budget is exhausted. Zero attachment exclusion keeps the shared hinge inside that unresolved query.

The mesh radial envelope is not the centerline radius. At deployment the meshed stations stop short of the blade radius, so the mesh envelope is inside the centerline radius. At the folded stops the chord and thickness put mesh vertices outside the centerline radius. Axial extent is the vertex z range of this planar preview; the same range appears at every recorded pose.
