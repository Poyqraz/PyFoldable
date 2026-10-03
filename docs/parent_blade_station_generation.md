# Internal parent realization and two complementary station cuts

This bounded service/example implements station-input generation for the
[comparison report](parent_blade_station_comparison.md). The broader
[radial-hinge proposal](strength_aware_radial_hinge_assessment_proposal.md) remains
**PROPOSED / NOT IMPLEMENTED**. Generated values are declared geometry, not
manufactured/as-built data or experimental evidence. External CAD/STEP is not
required. No complete blade/joint solid, offset transform, clearance, mass-property,
material, aerodynamic, FEA or trajectory computation is provided.

## Method and inputs

`parent_station_realization_v1` accepts an identified internal design TOML,
existing `DesignDraftInputs`, a validated coordinate-bearing `AirfoilDefinition`,
two distinct numeric SI hinge radii, a declared common deployed shaft frame and an
evidence label. Optional joint reference/modification records are kept separately.
The [service](../pyfoldable/application/parent_blade_generator.py) reuses the
[design draft](../pyfoldable/application/design_draft.py),
[profile catalog](../pyfoldable/core/profile_catalog.py),
[station parser](../pyfoldable/application/blade_stations.py) and comparison paths.

1. Reject mixed source-station profiles and unsupported source hinge geometry:
   axial/tangential offsets, axis azimuth, deployed and stop angles must be zero;
   axis elevation must be the represented +z value `pi/2`. The preview pose must
   be zero. No arbitrary frame/transform conversion is inferred. This narrow
   reporting restriction does not grant GEOM clearance for an offset topology.
2. Apply explicit parent-generation controls **once** through `build_design_draft`,
   with SI serialization (`m`, `rad`, `rad/s`). They may intentionally change the
   parent from the source, and are recorded. Validate the round-trip draft and its
   actual coordinate digest. Record source/draft hashes and keep source bytes intact.
3. Realize one immutable parent table using `r = r_over_R * (D/2)` once per row;
   retain its loaded SI chord/twist. The report binds draft bytes, controls, actual
   profile coordinates/metadata and relevant code-content hashes. Hashes identify
   content and do not authenticate geometry or certify an execution runtime.
4. For both cuts in declared input order, copy **stored** parent rows into fixed
   `r <= r_h` and tip `r >= r_h`. An existing hinge row is shared with explicit
   zero-based original-index correspondence. Children retain global shaft radii,
   diameter/hub conventions, profile-coordinate identity and the parent's canonical
   station hash as `derived_geometry` lineage. No child whole-blade draft/scaling
   pass occurs. Neither local tip coordinates nor reset root twist is generated.
5. Missing hinge/root/tip stations remain signed coverage gaps. No interpolation,
   extrapolation or padding is performed. A child with fewer than two rows has a
   null bundle, retained rows/indices/coverage and `INSUFFICIENT_CHILD_ROWS`; a valid
   other child is still emitted. An empty child has null supplied span/gap values.
   Comparison is unavailable for that cut, and the other cut remains independent.
6. Where both children are valid, emit the explicit comparison declaration and
   feed those exact canonical bundles to `compare_parent_blade_stations`.
   `REPORTED` means the comparison ran, not that complete coverage or geometry was
   established. Joint records do not fabricate a shape; no supplied modification
   is not evidence of an unchanged joint region.

Future evaluation of new rows from a continuous parent function requires an
explicit method and separately reviewed scope. This service only cuts the realized
sparse table. Unknown joint solid, complete 3D equivalence, movable mass/CG/inertia,
clearance, strength and safe winner remain null; `physical_qualification=false`.

## CLI and replay

The [small example/CLI](../examples/generate_parent_blade_cuts.py) defaults to the
250 mm canonical internal schema example and pinned NACA2412 coordinate catalog.
It labels outputs **synthetic software checks**. `--source` accepts an internal
TOML, not STEP. The CLI keeps source diameter/conditions and applies unit chord/twist
scales; the Python service accepts recorded intentional parent controls.

```bash
python examples/generate_parent_blade_cuts.py --hinges "75 mm" "100 mm" --output-dir outputs/two-cuts
python examples/generate_parent_blade_cuts.py --hinges "75 mm" "100 mm" --format table
python examples/compare_parent_blade_stations.py outputs/two-cuts/parent.json outputs/two-cuts/cut-00-fixed.json outputs/two-cuts/cut-00-tip.json outputs/two-cuts/cut-00-declaration.json
```

JSON is deterministic and finite; table output includes the inherited values,
lineage, differences and coverage. The optional output directory must be new.
It contains parent TOML/JSON, valid child JSON bundles, usable declarations and
combined JSON/Markdown reports. Incomplete cuts remain in the combined report;
there is no fabricated declaration for an unusable pair. Invalid input exits 2.
The service supports supplied joint records; the minimal CLI supplies none.

## Actual software demonstrations

Observed locally with CPython 3.12.14, NumPy 2.3.5 and SciPy 1.17.0; no solver/source
or trajectory call was made. This local context is not the CI environment or a
CMM-2 runtime certificate. Source:
`configs/designs/TIP_HINGED_250_CANONICAL.toml`. Its schema-example note remains.
The 250 mm diameter means `R=0.125 m`; the hub is its parsed binary64
`0.018000000000000002 m`. A 13-inch rotor is a separate design scenario.

| Identity | SHA-256 |
| --- | --- |
| Source TOML bytes | `a3852e5d14f433528fa9ad63bae26dd076b5136eacf4a7860ef76971eec2afdc` |
| SI parent draft TOML | `15ffb723ef98e4a7608697cb8973fa0df0fcb6fff889e574051871330fce7fce` |
| Parent canonical station bundle | `1a149afec4cb192703a597e86717e5040d15e3c7fcb1697b4898ea3d26b6eada` |
| Validated profile coordinates | `3f84aba0f9234ed6e9fe4eedebe88ae8701a19ae181d70e21a02b0704916999a` |

Stored parent radii are `[0.025, 0.05, 0.075, 0.1, 0.1225] m`. Chords are
`[0.028, 0.026, 0.023, 0.017, 0.008] m`; twists retain parsed 31/24/17/10/5 degree
source values in radians. Copied child numeric differences were exactly zero and
all coordinate identities matched. Both cuts report `DIFFERENCES_OR_GAPS` because
the parent's hub/root gap is `0.006999999999999999 m` and tip gap is
`0.0025000000000000022 m`.

| Explicit hinge r (m) | Fixed parent indices | Tip parent indices | Hinge row |
| --- | --- | --- | --- |
| 0.075 | 0,1,2 | 2,3,4 | Present, copied into both |
| 0.1 | 0,1,2,3 | 3,4 | Present, copied into both |

A second run declared `"76.92307692307693 mm"` and `"96.15384615384616 mm"`,
illustrating sparse cuts near 8/13 and 10/13 of the **250 mm** radius. Unit parsing
produced the following actual binary64 values, with the same parent digest.
These are declared comparison positions, not measured optima or performance.

| Parsed hinge r (m) | Fixed / tip indices | Fixed hinge-end gap (m) | Tip hinge-start gap (m) |
| --- | --- | --- | --- |
| 0.07692307692307694 | 0,1,2 / 3,4 | 0.001923076923076944 | 0.023076923076923064 |
| 0.09615384615384616 | 0,1,2 / 3,4 | 0.021153846153846162 | 0.0038461538461538464 |

Both emit `HINGE_STATION_ABSENT`. They add no row in those gaps. Tests also exercise
single-row and empty children. The [regressions](../tests/application/test_parent_blade_generator.py)
cover exact copying/lineage, one parent build, deterministic outputs/replay, invalid
positions/profile identities, unsupported source topology, recorded controls,
separate joint records and missing endpoints/rows. CI checks software behavior,
not hardware safety, physical qualification or a selected hinge winner.
