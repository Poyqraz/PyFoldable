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

The parsed `PolarAcceptanceCriteria` is consumed by the PR-05E real-backend runner;
runtime family generation uses the result-qualification and batch policies directly.

## Real-backend qualification

PR-05E deliberately runs outside the deterministic test suite because it launches the
installed XFOIL and NeuralFoil backends. Each reviewed golden fixture must match the
configured airfoil, scenario, alpha sweep, and Reynolds/Mach grid cell. Each discovered
backend must exactly match the pinned adapter and backend identity; merely reporting a
non-empty version is insufficient.

```bash
python examples/run_real_backend_qualification.py \
  configs/polars/PYFOLDABLE_DEMO_FAMILY.toml \
  path/to/reviewed-re100k.json path/to/reviewed-re200k.json \
  --output reports/polar_backend_qualification.json
```

The standalone JSON contains the full benchmark matrix and acceptance criteria plus the
polar configuration digest, every reviewed fixture digest, and discovered adapter/backend
identities. Timing remains telemetry rather than a pass gate. The output is written
atomically so an interrupted backend run cannot leave a plausible partial report.

Initial raw solver capture is performed by the manual GitHub Actions workflow documented
in `docs/polar_real_backend_qualification.md`. Capture artifacts are explicitly
unreviewed and cannot be treated as golden fixtures without a separate promotion review.
