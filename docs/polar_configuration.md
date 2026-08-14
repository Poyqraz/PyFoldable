# Provider-backed polar configuration

PR-05C uses a standalone, versioned TOML/JSON boundary for polar generation. It does
not extend the mechanical `PropellerDesign` schema: mechanical design inputs and
solver/runtime policy therefore remain independently reviewable.

The reference file is `configs/polars/PYFOLDABLE_DEMO_FAMILY.toml` and its coordinate
source is resolved relative to that config file.

```python
from pyfoldable import load_polar_family_config

config = load_polar_family_config(
    "configs/polars/PYFOLDABLE_DEMO_FAMILY.toml"
)
runtime = config.build_runtime()
batch = runtime.generate()
```

Building the runtime is the point at which optional XFOIL/NeuralFoil dependencies are
resolved. Loading and auditing a config does not launch XFOIL or import NeuralFoil's
backend package.

## Version 1 sections

| Section | Bound contract |
| --- | --- |
| `request` | Coordinate file, alpha sweep, scenario, transition and solver limits |
| `grid` | Strictly increasing Reynolds and Mach axes |
| `providers` | Ordered `xfoil`/`neuralfoil` adapter declarations |
| `retry` | `PolarRetryPolicy` with unit-bearing backoff durations |
| `cache` | Optional filesystem root and `PolarCacheLockPolicy` |
| `health` | Optional registry and `PolarProviderHealthPolicy` |
| `qualification` | Full-coverage result policy and low-confidence handling |
| `batch` | `fail_fast`/`collect_all` and sparse-family policy |
| `acceptance` | CL/CD/CM benchmark tolerances and coverage rules |

Unknown fields are rejected at every level. Angles and durations require explicit units;
Reynolds and Mach remain dimensionless numeric arrays. Relative coordinate/cache paths
are anchored to the config location, not the process working directory.
`PolarFamilyConfig.source_sha256` identifies the exact parsed byte sequence for later
`SimulationResult` provenance.

## Safety constraints

- `qualification.minimum_usable_fraction` must remain `1.0`; incomplete alpha sweeps
  cannot enter `PolarFamily` interpolation.
- `minimum_usable_points` cannot exceed the configured alpha count.
- At least one configured provider must be capability-compatible with every grid cell.
- Provider kinds cannot repeat, preventing duplicate runtime identities.
- Disabled cache/health sections cannot carry silently ignored policy settings.
- Provider-specific request options are intentionally absent. The orchestration request
  is shared by the fallback chain, so adapter-only options would make later providers
  reject the same request. A future provider-scoped request transform requires a
  separate contract.

Custom factories may be supplied for tests or deployments, but every configured kind
must be present and the resulting provider identities must be unique:

```python
runtime = config.build_runtime(
    {
        "xfoil": build_managed_xfoil,
        "neuralfoil": build_managed_neuralfoil,
    }
)
```

The parsed `PolarAcceptanceCriteria` is retained for PR-05E benchmark qualification;
runtime family generation uses the qualification and batch policies directly.
