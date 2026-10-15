# Hinge-location geometry screening

Geometric screening of two declared hinge radii on one immutable 250 mm parent. This is not clearance qualification and not a design selection.

physical_qualification: false
Qualified winner: none

Accepted parent SHA-256 `1a149afec4cb192703a597e86717e5040d15e3c7fcb1697b4898ea3d26b6eada`.
Profile NACA2412 coordinates `3f84aba0f9234ed6e9fe4eedebe88ae8701a19ae181d70e21a02b0704916999a`.
Declared stowed requirement: 140 mm.

A centerline result does not establish full clearance. Chord, thickness, hardware, root-tip contact, and interblade contact remain unresolved.

Radial projection is twice the larger of the hinge radius and the tip center's axial coordinate. The centerline envelope is twice the larger of the hinge radius and the tip center's distance from the shaft. A chord-inclusive or hardware-inclusive envelope is not computed.

## 100 mm

canonical schema-example reference

Necessary fixed-section bound: D_envelope >= 0.2 m.
Requirement minus that bound: -0.06 m.
Hinge station present in the parent: true.
Station comparison: DIFFERENCES_OR_GAPS.
Copied chord and twist match the parent wherever a row is marked equal. A gap status retains missing station coverage; it is not a twist reset.

| Component | Child index | Parent index | Radius m | Chord m | Twist rad |
| --- | --- | --- | --- | --- | --- |
| fixed | 0 | 0 | 0.025 | 0.028 | 0.54105207 |
| fixed | 1 | 1 | 0.05 | 0.026 | 0.41887902 |
| fixed | 2 | 2 | 0.075 | 0.023 | 0.29670597 |
| fixed | 3 | 3 | 0.1 | 0.017 | 0.17453293 |
| tip | 0 | 3 | 0.1 | 0.017 | 0.17453293 |
| tip | 1 | 4 | 0.1225 | 0.008 | 0.087266463 |

| Pose deg | Projected diameter m | Centerline envelope m | Hub centerline clearance m | Full-stow hub clearance m | Collision-free minimum envelope m | Requirement margin m | Requirement met | Reasons |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0.25 | 0.25 | 0.082 | 0.057 | 0.2 | -0.11 | false | stowed_requirement_unreachable, current_envelope_exceeds_requirement, surface_stations_do_not_cover_hub_to_tip |
| -90 | 0.2 | 0.20615528 | 0.082 | 0.057 | 0.2 | -0.066155281 | false | stowed_requirement_unreachable, current_envelope_exceeds_requirement, surface_stations_do_not_cover_hub_to_tip |
| -180 | 0.2 | 0.2 | 0.057 | 0.057 | 0.2 | -0.06 | false | stowed_requirement_unreachable, current_envelope_exceeds_requirement, surface_stations_do_not_cover_hub_to_tip |

Parent root coverage gap: 0.006999999999999999 m.
Parent tip coverage gap: 0.0025000000000000022 m.
No joint modification was declared. An empty modification list is not a flush joint.

## 50 mm

geometry-screening trial, not an optimum or manufactured design

Necessary fixed-section bound: D_envelope >= 0.1 m.
Requirement minus that bound: 0.04 m.
Hinge station present in the parent: true.
Station comparison: DIFFERENCES_OR_GAPS.
Copied chord and twist match the parent wherever a row is marked equal. A gap status retains missing station coverage; it is not a twist reset.

| Component | Child index | Parent index | Radius m | Chord m | Twist rad |
| --- | --- | --- | --- | --- | --- |
| fixed | 0 | 0 | 0.025 | 0.028 | 0.54105207 |
| fixed | 1 | 1 | 0.05 | 0.026 | 0.41887902 |
| tip | 0 | 1 | 0.05 | 0.026 | 0.41887902 |
| tip | 1 | 2 | 0.075 | 0.023 | 0.29670597 |
| tip | 2 | 3 | 0.1 | 0.017 | 0.17453293 |
| tip | 3 | 4 | 0.1225 | 0.008 | 0.087266463 |

| Pose deg | Projected diameter m | Centerline envelope m | Hub centerline clearance m | Full-stow hub clearance m | Collision-free minimum envelope m | Requirement margin m | Requirement met | Reasons |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0.25 | 0.25 | 0.032 | -0.018 | 0.1 | -0.11 | false | current_envelope_exceeds_requirement, full_stow_path_intersects_hub, surface_stations_do_not_cover_hub_to_tip |
| -90 | 0.1 | 0.18027756 | 0.032 | -0.018 | 0.1 | -0.040277564 | false | current_envelope_exceeds_requirement, full_stow_path_intersects_hub, surface_stations_do_not_cover_hub_to_tip |
| -180 | 0.1 | 0.1 | -0.018 | -0.018 | 0.1 | 0.04 | true | full_stow_path_intersects_hub, surface_stations_do_not_cover_hub_to_tip, tip_centerline_intersects_hub |

Parent root coverage gap: 0.006999999999999999 m.
Parent tip coverage gap: 0.0025000000000000022 m.
No joint modification was declared. An empty modification list is not a flush joint.

## Unresolved

- joint thickness
- exposed hardware
- root-to-tip surface contact
- interblade contact
- chord-inclusive envelope
- strength
- vibration
- mass, inertia, stiffness, damping, friction, backlash, and restraint
