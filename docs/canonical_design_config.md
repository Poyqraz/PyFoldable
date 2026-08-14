# Canonical design configuration (schema version 1)

PyFoldable's new analysis boundary is `pyfoldable.core`.  It separates user-facing
engineering units from solver-facing SI scalars without changing the legacy
`FoldablePropellerConfig` JSON workflow.

## Rules

- SI is canonical inside model objects: metre, kilogram, second, radian, kelvin,
  newton, pascal, watt, ampere, volt, and ohm.
- Every dimensional value in TOML/JSON must include a unit.  Bare `250` is rejected;
  write `"250 mm"` or `{ value = 250, unit = "mm" }`.
- Dimensionless values such as `r_over_R` remain numeric.
- RPM, degrees, millimetres, and inches are converted only by the config loader.
  Physics functions therefore never contain hidden input-unit assumptions.
- Original unit labels are retained under `PropellerDesign.metadata["input_units"]`.
- `schema_version` is mandatory.  Unsupported versions fail explicitly.

The first implementation uses a small, strict conversion registry instead of Pint.
This layer only normalizes configuration boundaries; it does not perform symbolic
quantity arithmetic.  Avoiding a broad unit dependency keeps the scientific core
small while still rejecting dimensional mistakes.  Pint can be reconsidered if
future public APIs require compound-unit algebra rather than boundary conversion.

The reference file is
`configs/designs/TIP_HINGED_250_CANONICAL.toml`:

```python
from pyfoldable.core import load_design_config

design = load_design_config("configs/designs/TIP_HINGED_250_CANONICAL.toml")
print(design.blade.diameter_m)  # 0.25
print(design.operating_conditions[0].angular_speed_rad_s)  # 743.51...
```

## Model boundary

The canonical object graph covers:

- `OperatingCondition`
- `AirfoilDefinition` and `PolarTable`
- `BladeStation` and `BladeGeometry`
- `HingeGeometry`
- `MotorModel`
- `MaterialModel` and `ManufacturingModel`
- `PropellerDesign`
- `SimulationResult` and `ValidationRecord`

These objects are solver-neutral.  Future BEM, CAD, CFD, FEA, and experiment adapters
must consume or produce them instead of creating parallel unit conventions.
`SimulationResult` makes the design/condition identity, solver version, Git commit,
polar sources, model options, convergence state, and warnings part of the result
contract rather than relying on filenames.

Provider-backed polar runtime settings deliberately use the separate versioned boundary
documented in `docs/polar_configuration.md`. This prevents executable paths, retry/cache
policy, and backend selection from becoming mechanical design properties.

## Legacy compatibility

`pyfoldable.models.load_config()` continues to load
`configs/foldable/TIP_HINGED_250_V01.json` and `TIP_HINGED_250_V02.json` unchanged.
Migration into the canonical schema will be a separate, testable change after the
new BEM inputs are defined.

## Attached SolidWorks result

The team workbook `HedefDeğerlerTablo.xlsx` was treated as signed CFD output rather
than as a design input.  Its summary contains a mean Z force of approximately
`-6.6744 N`, mean Z torque of `-0.23677 N*m`, and mean maximum static pressure of
`107214.5 Pa` over a 65-iteration analysis window.  It should become one or more
`ValidationRecord` entries only after its geometry, RPM, fluid properties, boundary
conditions, and axis convention are documented.

Source workbook SHA-256:
`cfad5929aafc6515daa281f247df2da0b312643aedff3a39449c27562a48bc56`.
