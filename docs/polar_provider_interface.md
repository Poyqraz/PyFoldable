# Polar provider interface

PR-04 defines the dependency-free boundary shared by XFOIL and NeuralFoil adapters.
PR-04A adds the XFOIL subprocess implementation without bundling an executable.
PR-04B adds an optional NeuralFoil implementation without making it a core dependency.
PR-04C adds a provider-neutral filesystem cache with validated, atomic records.

## Contract

- `PolarGenerationRequest`: normalized airfoil coordinates, ordered angles, Reynolds,
  Mach, `Ncrit`, forced-transition locations, numerical limits, scenario, and options.
- `ProviderIdentity`: adapter/backend names and versions used for provenance and cache
  invalidation.
- `ProviderCapabilities`: declares supported inputs instead of silently ignoring them.
- `PolarPointResult`: point-level coefficients, convergence state, confidence,
  iterations, and message.
- `PolarGenerationResult`: preserves partial failures and can create a complete or
  explicitly partial `PolarTable`.
- `PolarProvider`: runtime-checkable protocol implemented by adapters.

The cache key is SHA-256 over canonical JSON containing schema version, normalized
coordinates, ordered angles, all physical and numerical request fields, provider and
backend versions, and provider options. Cache storage is implemented independently of
the XFOIL and NeuralFoil adapters, so neither adapter contains persistence behavior.

## Provider mapping

| Contract field | XFOIL adapter | NeuralFoil adapter |
|---|---|---|
| Angle input | degrees via `ALFA`/`ASEQ` | vectorized degrees |
| Reynolds | `VISC`/type-1 polar | `Re` |
| Mach | `MACH` | unsupported by standalone coordinate API; capability must be false |
| Transition | `VPAR N` and trips | `n_crit`, `xtr_upper`, `xtr_lower` |
| Failure signal | missing output row | coefficients plus `analysis_confidence` |
| Partial sweep | preserved point by point | normally complete; low confidence remains explicit |
| Iteration limit | optional `ITER` control | unsupported; capability must be false |
| Timeout | subprocess deadline | unsupported in-process; custom values rejected |

XFOIL continuation/hysteresis means alpha order is part of the request and cache key.
Ascending, descending, and custom unique sequences are valid; adapters must not reorder
the request invisibly. Conversion to `PolarTable` sorts usable points because that
interpolation model requires increasing angle. Retry strategies must be recorded in
provider options and provenance.

NeuralFoil's standalone coordinate API expects normalized Selig order, matching
`load_airfoil_coordinates()`. Its result includes `CL`, `CD`, `CM`, transition
locations, and `analysis_confidence`; confidence policy belongs to the adapter and
must not turn a low-confidence point into a silent success.

## XFOIL subprocess adapter

`XfoilProvider` discovers an executable from an explicit path or `PATH`, captures its
reported version (falling back to a SHA-256 executable fingerprint), and runs each
request in an isolated temporary directory. It sends commands on stdin without a
shell, disables plotting, writes a normalized labeled coordinate file, enables `PACC`,
and executes each requested angle in its original order.

Missing polar rows become `not_converged` point results instead of fabricated
coefficients. Non-zero process exits, missing/malformed polar files, startup failures,
and request timeouts use the typed provider errors. The only provider option is
`repanel: bool`, which defaults to true; unknown options are rejected.

## NeuralFoil adapter

Install the optional backend with `pip install pyfoldable[neuralfoil]`, then construct
`NeuralFoilProvider`. Importing `pyfoldable` does not import NeuralFoil; backend loading
and version capture happen only when the provider is constructed.

The provider evaluates all requested angles in one vectorized coordinate-API call. It
passes Reynolds number, `Ncrit`, and forced-transition positions directly, while Mach,
iteration limits, and custom timeouts are rejected by capability validation. Outputs
must contain correctly sized, finite `CL`, `CD`, `CM`, `analysis_confidence`, `Top_Xtr`,
and `Bot_Xtr` arrays; malformed backend responses fail as typed execution errors.

Provider options are `model_size` (default `xlarge`) and `confidence_threshold`
(default `0.5`). Confidence strictly below the threshold produces a usable
`low_confidence` point with an explicit warning; coefficients are never silently
discarded. Both options participate in the request cache key.

## Filesystem polar cache

`FilesystemPolarCache(root)` stores one JSON document per request/provider cache key.
Entries are sharded by the first two key characters. `generate_polar_cached()` first
validates provider capabilities, then returns a valid hit or calls the provider and
publishes the result. Returned result metadata records cache `status` as `hit`, `miss`,
or `recovered`, together with the schema version and relative entry path.

```python
from pyfoldable import FilesystemPolarCache, generate_polar_cached

cache = FilesystemPolarCache("outputs/polar-cache")
result = generate_polar_cached(provider, request, cache)
```

Each document records the storage schema version, cache key, complete provider
identity, canonical request payload, and the point-level result envelope. Reads reject
unknown fields, unsupported schemas, identity/request mismatches, malformed points,
and results that contradict provider capabilities. Invalid entries are moved under
`corrupt/` and regenerated; they are never treated as successful solver output.

Writes use a unique temporary file in the destination directory, flush and `fsync`
the complete JSON payload, then publish it with `os.replace`. Readers therefore see
either the previous complete entry or the new complete entry, while concurrent writers
for the same deterministic key remain safe. Cache misses and provider failures are not
stored as fabricated aerodynamic data.

## Next adapter increments

1. Cache lifecycle policy: size/age eviction and optional duplicate-work coalescing.
