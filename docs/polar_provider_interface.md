# Polar provider interface

PR-04 defines the dependency-free boundary shared by XFOIL and NeuralFoil adapters.
PR-04A adds the XFOIL subprocess implementation without bundling an executable.
PR-04B adds an optional NeuralFoil implementation without making it a core dependency.
PR-04C adds a provider-neutral filesystem cache with validated, atomic records.
PR-04D adds deterministic cache inventory, eviction, and artifact cleanup.
PR-04E adds cross-process duplicate-work coalescing and crash-safe lock ownership.
PR-04F adds ordered provider fallback, bounded retry, and attempt provenance.
PR-04G adds process-local health telemetry and a thread-safe circuit breaker.
PR-04H adds versioned golden fixtures, coefficient acceptance envelopes, and
cross-provider benchmark reports.

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

## Cache lifecycle management

`list_entries()` returns active records in deterministic relative-path order, including
their key, byte size, and modification time. `stats()` reports active, quarantined, and
temporary artifact counts and byte totals without creating a missing cache directory.

`maintain()` accepts four independent, opt-in policies:

- `max_age_s` evicts active entries older than the declared age.
- `max_bytes` evicts the oldest remaining active entries until their total size fits.
- `corrupt_max_age_s` removes old records from the `corrupt/` quarantine.
- `temporary_max_age_s` removes abandoned atomic-write temporary files.

Age eviction runs before size eviction. Equal modification times are ordered by
relative path, making the decision reproducible. Maintenance returns before/after
storage statistics, ordered removed-entry paths, and reclaimed bytes. Unrelated files,
symlinks, and non-cache directories are ignored; empty two-character shard directories
are removed after maintenance.

Operations on one `FilesystemPolarCache` instance use an in-process reentrant lock, so
its readers, atomic writers, and maintenance passes cannot delete each other's current
files.

## Cross-process duplicate-work coalescing

`generate_polar_cached()` also coordinates independent processes with one persistent
advisory-lock file per cache key under `locks/<prefix>/<key>.lock`. The default
`PolarCacheLockPolicy` bounds waiting to 60 seconds and uses exponential polling from
10 to 250 milliseconds; applications can supply a stricter policy when constructing
`FilesystemPolarCache`.

On a miss, a process acquires the key lock and checks the cache again before invoking
the provider. A follower therefore consumes the leader's newly published result rather
than repeating XFOIL or NeuralFoil work. Result cache metadata records whether work was
coalesced, lock wait time, the relative lock entry, and stale-metadata recovery.

While held, the lock document contains a version, cache key, random owner token, PID,
hostname, and acquisition time. Release clears the document only when the stored token
still matches the owner. The operating-system lock is released automatically if a
process exits, so a subsequent process can safely identify and replace abandoned owner
metadata without an arbitrary age threshold that could steal a long-running live lock.

Lock files remain as one-byte coordination sentinels after normal release. Maintenance
ignores the `locks/` tree and skips age/size eviction for an entry whose key is actively
locked by another process. If protected entries alone exceed `max_bytes`, the reported
post-maintenance size can remain above that requested target.

## Provider orchestration, fallback, and retry

`generate_polar_orchestrated()` evaluates an ordered provider chain and returns the
first valid result. A `PolarRetryPolicy` bounds retries independently for each provider;
the defaults allow two attempts, retry timeouts, do not retry execution failures, and
apply exponential backoff from 50 to 500 milliseconds.

```python
from pyfoldable import (
    FilesystemPolarCache,
    NeuralFoilProvider,
    PolarRetryPolicy,
    XfoilProvider,
    generate_polar_orchestrated,
)

result = generate_polar_orchestrated(
    (XfoilProvider(), NeuralFoilProvider()),
    request,
    retry_policy=PolarRetryPolicy(max_attempts=2),
    cache=FilesystemPolarCache(".cache/polars"),
)
```

Failures have explicit routing behavior:

| Failure | Retry same provider | Continue fallback chain |
| --- | --- | --- |
| Capability mismatch | Never | Yes |
| Backend unavailable | Never | Yes |
| Timeout | Controlled by `retry_timeouts` | After attempts are exhausted |
| Execution failure | Opt-in with `retry_execution_errors` | After attempts are exhausted |
| Unexpected non-provider exception | Never | With health isolation; otherwise propagated |

Execution retries are disabled by default because this error class also covers invalid
provider envelopes and other deterministic contract violations. Applications should
enable them only when their backend's execution failures are known to be transient.
Cache/lock infrastructure errors are not treated as provider failures and are likewise
propagated rather than hidden by fallback.

Each provider retains its own identity and cache key. Consequently a cached primary
result wins without invoking its backend, while a cached fallback result is found after
earlier providers have been rejected for the current call. Successful result metadata
adds a versioned `orchestration` record containing the selected provider, retry/fallback
counts, and ordered `PolarProviderAttempt` entries. If every provider fails,
`PolarProviderChainExhaustedError.attempts` exposes the same ordered audit trail and the
last provider failure is preserved as the exception cause.

## Provider health telemetry and circuit breaker

A `PolarProviderHealthRegistry` persists process-local health across orchestration calls
and is safe to share between threads. Its default `PolarProviderHealthPolicy` opens a
provider circuit after three consecutive counted failures, waits 30 seconds, and then
admits exactly one half-open probe. A successful backend call closes the circuit; a
failed or neutral probe opens it for another cooldown period.

```python
from pyfoldable import (
    PolarProviderHealthPolicy,
    PolarProviderHealthRegistry,
    generate_polar_orchestrated,
)

health = PolarProviderHealthRegistry(
    PolarProviderHealthPolicy(
        failure_threshold=3,
        recovery_timeout_s=30.0,
    )
)

result = generate_polar_orchestrated(
    providers,
    request,
    cache=cache,
    health_registry=health,
)
```

Availability, timeout, execution, generic provider, and isolated unexpected errors are
counted by default. Capability mismatches and circuit rejections are request/routing
decisions and never affect health. Individual failure classes can be excluded through
the policy without changing retry behavior.

When a registry is supplied, cache lookup occurs before circuit admission. An open
provider can therefore serve a valid cached result without executing its backend or
being reported as a health success. Cache misses continue through the circuit state
machine. Cross-process cache coordination remains independent from this process-local
health registry.

Health isolation converts an unexpected provider `Exception` into a typed
`PolarProviderUnexpectedError`, records a bounded safe message, and continues the
fallback chain. It is enabled by default only when a health registry is explicitly
used, and can be disabled with `isolate_unexpected_errors=False`. `KeyboardInterrupt`,
`SystemExit`, and other `BaseException` types are never masked; an outstanding
half-open reservation is released before they are re-raised.

Version 2 orchestration provenance records circuit state before/after each attempt,
whether it was the half-open probe, health failure counts, circuit rejections, and a
snapshot for every provider in the configured chain. `snapshot()`, deterministic
`snapshots()`, and `reset()` provide direct operational telemetry and lifecycle control.
Generation tokens prevent completions from an older circuit epoch or pre-reset call
from mutating current state.

## Adapter acceptance and cross-provider benchmarks

`load_polar_golden_fixture()` loads strict schema-versioned JSON fixtures.
`compare_polar_results()` checks a request-identical candidate against its reference
using an absolute-plus-relative envelope for each of `CL`, `CD`, and `CM`. Acceptance
also records usable-point agreement and minimum reference coverage, so a solver cannot
pass by silently dropping difficult angles.

```python
from pyfoldable import (
    NeuralFoilProvider,
    PolarAcceptanceCriteria,
    PolarErrorTolerance,
    XfoilProvider,
    load_polar_golden_fixture,
    run_polar_provider_benchmark,
)

fixture = load_polar_golden_fixture("tests/fixtures/polar_acceptance/naca0012_re200k.json")
criteria = PolarAcceptanceCriteria(
    cl=PolarErrorTolerance(absolute=0.05, relative=0.02),
    cd=PolarErrorTolerance(absolute=0.002, relative=0.10),
    cm=PolarErrorTolerance(absolute=0.01, relative=0.05),
)
report = run_polar_provider_benchmark(
    (XfoilProvider(), NeuralFoilProvider()),
    (fixture,),
    criteria=criteria,
)
```

The report preserves the complete provider-by-fixture matrix, individual failures,
coefficient error statistics, wall-clock elapsed time, provider-reported elapsed time,
and per-provider timing summaries. Timing is telemetry only and never a CI pass/fail
gate, because shared-runner noise would make such a gate nondeterministic.

The committed NACA0012 fixture is an analytic **adapter-contract regression fixture**.
It proves angle/unit/status/coefficient mapping through deterministic XFOIL subprocess
and NeuralFoil API doubles. It is not wind-tunnel evidence and must not be presented as
physical agreement between real solver versions. A real-backend qualification run can
use the same API after its operating envelope, backend versions, and reviewed reference
data are frozen.

PR-04 is complete through PR-04H. The next integration milestone is tracked in
[`development_roadmap.md`](development_roadmap.md).
