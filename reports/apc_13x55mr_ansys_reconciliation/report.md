# APC 13x5.5MR and ANSYS reconciliation

This is a source inventory and gap record. It is not a CFD, BEM, or qualification result.
physical_qualification: false
Genuine two-profile comparison: UNESTABLISHED

## What was read

Official APC downloads were retrieved on 2026-10-16 and kept under the gitignored local path
`outputs/apc_13x55mr_local/`. The full performance table is not committed.
Geometry identity uses the existing PE0 parser. The local reporting contract is
[local APC PE0 geometry reporting](../../docs/local_apc_pe0_geometry_reporting.md).
Its aerodynamic blade shortcut was not called.
The first-party files in `data/propellers/apc_202602/` are synthetic fixtures, not this model.

The ANSYS draft `Tahir_APC_4000RPM_Haftalik_Rapor_Taslagi1.docx` was not in the workspace.
Its expected SHA-256 `da6ea5414e49c10b40ff1202712193528b1bdb4b01fe7fde64b2d27ce5b856a3` was not verified.
Figures, tables, last-iteration values, and averaging-window statistics were not read.
The task states a CAD diameter of 329.3519 mm. That statement is not a file reading.

## Model separation

The selected file is fixed multi-rotor 13x5.5MR, SKU LP13055MR.
13x5.5E is a thin-electric propeller with catalog hub diameter 0.80 in and a different PE0 hub radius.
13x5.5MRP is the reverse-rotation pusher. 13x5.5MRF-L(B) and 13x5.5MRF-R(B) are folding blades whose hubs are not included.
Matching the text 13x5.5 does not make those geometries the same solid.

## Diameters

Nominal product diameter: 13 in = 330.2 mm.
PE0 footer RADIUS 6.47 in gives diameter 328.676 mm.
The last PE0 station, 6.475 in, gives 328.93 mm and sits beyond the footer radius.
The task-supplied CAD diameter is 329.3519 mm.
These four numbers are not the same. Nothing in this record rescales one onto another.
Catalog hub diameter is 0.65 in. Twice the PE0 HUBRAD of 0.32 in is 0.64 in. That difference stays unresolved.

PE0 `v2025-1001`, simulation date 2026-02-24, member SHA-256
`2972e1b99215f2eb052e586e48cc59730cbfd4f08c6627ea7461a8afa150c30f`,
matches the existing public pin. That member is in `PE0-FILES_WEB-202602.zipx`.
The performance file is a different archive, `PERFILES_WEB-202602.zipx`, and its internal
header is `v2022-0915`, simulation date 2022-09-22. The shared 202602 label does not prove
that the performance prediction used the 2026 stations.

Published masses also differ. The PE0 weight lines, after the RADIUS/HUBRAD/HUBTRA/BLADES footer,
say 0.054915 lb and 0.024905 kg.
The catalog says 0.85 oz, 0.0529 lb, and 23.994911 g. Both pairs are published values.

The PE0 file names E63 at 3.70 in and APC12 at 6.00 in. Those are vendor section labels,
not coordinate files for the five selectable project profiles.

## Performance table

Classification: manufacturer computational prediction, not an experiment.
File `https://www.apcprop.com/files/PER3_13x55MR.dat`, SHA-256
`bcf3914a4f7ac4c843823d6b9ebf26120824f2052ed145e03a1dad8246ec9751`.
That byte hash equals the 13x5.5MR member of `PERFILES_WEB-202602.zipx`.
The file has 17 RPM blocks from 1000 through 17000 and 15 columns.
502 lines contain a full coefficient row. Eight further lines, at 7000, 8000, 9000,
12000, 14000, 15000, 16000, and 17000 RPM, contain only V and J. Their other fields are blank.
That is 510 speed lines. Blank fields are not filled in.
Ct and Cp are defined with rho. The file does not state a numeric density.
Airfoil aero data are described as polar diagrams.

The 4000 RPM, zero-speed published tokens are thrust 6.002 N, torque 0.108 N-m, and power 45.403 W,
with Ct 0.0941 and Cp 0.0325.
Multiplying the published 0.108 N-m by 418.879020479 rad/s gives
45.2389 W, which is not the published 45.403 W.
The difference is displayed-torque rounding. It is not a replacement APC result.
The other speed lines stay in the local file.

No ANSYS thrust, torque, or power is available, so this record does not compare them
and does not copy the APC values into a CFD result.

## Source and gap matrix

### Exact 13x5.5MR identity versus E, pusher, and folding variants

Available from APC: Distinct SKUs, hub diameters, weights, and file hashes.
Reported by the ANSYS engineer: Not read. The named docx bytes were not in the workspace.
Reproducible from retained inputs: Catalog rows and the hashed PE0/PER3 headers.
Missing handoff: Confirm which SKU and rotation the CAD represents.

### Diameter

Available from APC: Nominal 330.2 mm, footer-based 328.676 mm, last station 328.93 mm.
Reported by the ANSYS engineer: Task states 329.3519 mm. That value was not read from the docx.
Reproducible from retained inputs: The three APC diameters and their inequalities.
Missing handoff: CAD diameter definition, units, and the solid that produced 329.3519 mm.

### Hub size

Available from APC: Catalog hub diameter 0.65 in. PE0 HUBRAD 0.32 in, which is 0.64 in diameter.
Reported by the ANSYS engineer: Not read. The named docx bytes were not in the workspace.
Reproducible from retained inputs: Both published APC values.
Missing handoff: Which hub surface the CAD measures.

### Mass

Available from APC: PE0 0.054915 lb / 0.024905 kg. Catalog 0.85 oz, 0.0529 lb, and 23.994911 g.
Reported by the ANSYS engineer: Not read. The named docx bytes were not in the workspace.
Reproducible from retained inputs: The published pairs are not the same number.
Missing handoff: CAD mass and the material density actually solved.

### 4000 RPM static thrust, torque, and power

Available from APC: Published prediction 6.002 N, 0.108 N-m, 45.403 W.
Reported by the ANSYS engineer: Not read. The named docx bytes were not in the workspace.
Reproducible from retained inputs: Rounded 0.108 N-m times 4000 RPM does not reproduce 45.403 W.
Missing handoff: Engineer's independent thrust, torque, and power, with their definitions.

### Advance condition actually solved

Available from APC: 4000 RPM has 30 speed rows from 0.00 mph through the file's last row.
Reported by the ANSYS engineer: Not read. The named docx bytes were not in the workspace.
Reproducible from retained inputs: No ANSYS airspeed or advance ratio is available to select a row.
Missing handoff: Freestream speed, RPM, and reference density used in Fluent.

### Coefficient and force definitions

Available from APC: Ct, Cp, J, and Pe formulas. Numeric rho is absent.
Reported by the ANSYS engineer: Not read. The named docx bytes were not in the workspace.
Reproducible from retained inputs: Formula text only.
Missing handoff: Force and moment definitions, component breakdown, and reference quantities.

### Last iteration versus averaging window

Available from APC: Not an APC performance-file quantity.
Reported by the ANSYS engineer: Not read. The named docx bytes were not in the workspace.
Reproducible from retained inputs: No history was supplied.
Missing handoff: Complete convergence and load histories, with the window stated separately from the last iteration.

### Mesh, wall resolution, and radial loads

Available from APC: Not in the performance file.
Reported by the ANSYS engineer: Not read. The named docx bytes were not in the workspace.
Reproducible from retained inputs: No mesh or radial export was supplied.
Missing handoff: Post-repair mesh statistics, wall-resolution evidence, and any existing radial-load export.

### Section polars for the five selectable profiles

Available from APC: PE0 names E63 and APC12 at stated stations. It does not supply those coordinates or a polar.
Reported by the ANSYS engineer: Not read. The named docx bytes were not in the workspace.
Reproducible from retained inputs: No.
Missing handoff: Not requested from this APC/CFD package. Coordinate-bound polars remain a separate blocked study.

## Engineer handoff

Existing files:

- Provide Tahir_APC_4000RPM_Haftalik_Rapor_Taslagi1.docx with SHA-256 da6ea5414e49c10b40ff1202712193528b1bdb4b01fe7fde64b2d27ce5b856a3.
- Exact CAD of the solid that was meshed, including units and the feature that measures diameter.
- Fluent case and data files, or the solver archive, with the settings actually run.
- Complete residual and thrust/torque histories.
- Written force and moment definitions and the component breakdown.
- Post-repair mesh statistics and wall-resolution evidence.
- Any radial-load export that already exists.

Proposed future calculations, not existing files:

- After those files are in hand, one same-mesh second-order 4000 RPM comparison.
- Mesh and domain changes only as a later, separate study.

## Next step

1. Assess the evidence now in hand: APC identities disagree with each other and with the task-supplied CAD diameter, and the ANSYS draft has not been read.
2. Do not tune a result to the APC prediction and do not copy the APC static load into the CFD record.
3. When the report and solver files arrive, compare the engineer's retained thrust, torque, and power with the published 4000 RPM row that matches the solved airspeed.
4. The first proposed calculation is a same-mesh second-order rerun at 4000 RPM. It is not authorized by this inventory.
5. Mesh and domain studies stay behind that same-mesh comparison.

The 13-inch APC benchmark stays separate from the 250 mm jointed design and from the blocked 7100 RPM polar study.
A full-rotor load does not supply coordinate-bound section polars.
The APC/CFD difference, once it can be computed, does not establish joint loss, structural adequacy,
vibration acceptance, or controlled folding.
