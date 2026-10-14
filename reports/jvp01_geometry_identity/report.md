# JVP-01 geometry identity

Schema-example intent for the canonical 250 mm blade and its declared 100 mm hinge. This is not a selected joint and not as-built evidence.

physical_qualification: false

## Identities

- Source `configs/designs/TIP_HINGED_250_CANONICAL.toml` SHA-256 `a3852e5d14f433528fa9ad63bae26dd076b5136eacf4a7860ef76971eec2afdc`.
- Draft SHA-256 `15ffb723ef98e4a7608697cb8973fa0df0fcb6fff889e574051871330fce7fce`. Chord scale and twist scale are 1.
- Profile NACA2412 coordinate SHA-256 `3f84aba0f9234ed6e9fe4eedebe88ae8701a19ae181d70e21a02b0704916999a`.
- Parent canonical SHA-256 `1a149afec4cb192703a597e86717e5040d15e3c7fcb1697b4898ea3d26b6eada`.
- Case A canonical SHA-256 `1a149afec4cb192703a597e86717e5040d15e3c7fcb1697b4898ea3d26b6eada`.
- Case A bytes are the parent bundle.

## Stations

Frame `schema_example_deployed_shaft`: global shaft radius, deployed pose, metres and radians.

| Radius m | r/R | Chord m | Twist rad |
| --- | --- | --- | --- |
| 0.025 | 0.2 | 0.028 | 0.54105207 |
| 0.05 | 0.4 | 0.026 | 0.41887902 |
| 0.075 | 0.6 | 0.023 | 0.29670597 |
| 0.1 | 0.8 | 0.017 | 0.17453293 |
| 0.1225 | 0.98 | 0.008 | 0.087266463 |

Root coverage gap: 0.006999999999999999 m.
Tip coverage gap: 0.0025000000000000022 m.
Station span complete: false.
These are the validated station-span gaps. The JSON file retains the same floats. They are missing parent stations, not a joint gap.

## Hinge

Declared radius 0.1 m from `configs/designs/TIP_HINGED_250_CANONICAL.toml [hinge].radius` = 100 mm.
Label: schema-example hinge, not a selected optimum.
No station was inserted. The radius matches an existing parent station.
The schema file sets axial and tangential offsets to 0 mm. Those zeros are not a flush-joint measurement.

## Geometric inventory

| Field | Status |
| --- | --- |
| exposed_hardware | absent |
| fold_misalignment | absent |
| joint_tolerances | absent |
| pitch_misalignment | absent |
| radial_gap | absent |
| surface_step | absent |
| sweep_misalignment | absent |

No geometric field is measured, so no measurement source, method, or uncertainty is recorded.

## Mechanical properties

- backlash: unestablished
- center_of_mass: unestablished
- damping: unestablished
- friction: unestablished
- inertia: unestablished
- mass: unestablished
- materials: unestablished
- restraint: unestablished
- stiffness: unestablished
- stop_latch: unestablished

Shared parent lineage does not establish that Case A equals a jointed Case B.

## Case C

Unsolved. Motion, clearance, contact, latch, release, and the closed envelope are absent.

## Missing inputs

- joint radial gap
- surface step
- fold misalignment
- pitch misalignment
- sweep misalignment
- exposed hardware identity and envelope
- joint tolerances
- measurement source, method, and uncertainty for every geometric field
- mass, center, and inertia
- materials
- stiffness, damping, friction, backlash, restraint, and stop or latch calibration
- Case C motion, clearance, contact, latch, release, and closed envelope
- as-built joint evidence
- acceptance limits

Reviewed contract head `0d1e78ee3c80ddc05ea8f2b2aa1c329088821369`, tree `206f4980c4cac7df5d5e5ff2df06565363f19dd0`. This packet does not modify that document.
