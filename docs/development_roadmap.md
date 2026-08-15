# Polar-to-analysis development roadmap

This map records the transition from the external polar-provider platform (PR-04) to
provider-generated polar families consumed by the analysis stack (PR-05). PR-05 had no
explicit definition in the repository before PR-04H; its scope below follows the current
boundary between `PolarGenerationResult.to_polar_table()` and manually assembled
`PolarFamily` objects.

## Current position

| Increment | Capability | Status |
| --- | --- | --- |
| PR-04 | Solver-neutral provider contract | Complete |
| PR-04A | XFOIL subprocess adapter | Complete |
| PR-04B | Optional NeuralFoil adapter | Complete |
| PR-04C | Validated atomic filesystem cache | Complete |
| PR-04D | Cache lifecycle and maintenance | Complete |
| PR-04E | Cross-process duplicate-work coalescing | Complete |
| PR-04F | Ordered fallback and bounded retry | Complete |
| PR-04G | Health telemetry and circuit breaker | Complete |
| PR-04H | Golden acceptance and cross-provider benchmark | Complete |
| PR-05A | Provider-backed family generation contract | Complete |
| PR-05B | Partial-grid policy and batch diagnostics | Complete |
| PR-05C | Strict configuration binding | Complete |
| PR-05D | Analysis integration | Complete in this change |
| PR-05E | Real-backend qualification | Next |

## PR-05 — provider-backed PolarFamily integration

PR-05 will close the remaining gap between generating one polar and safely supplying a
multi-Reynolds/Mach family to an aerodynamic analysis consumer.

1. **PR-05A — family generation contract.** Define an ordered operating-point grid,
   generate each table through `generate_polar_orchestrated()`, and assemble a
   deterministic `PolarFamily` without losing provider/cache/orchestration provenance.
   **Complete.**
2. **PR-05B — partial-grid policy and batch diagnostics.** Make fail-fast versus partial
   family behavior explicit; report every requested cell, retry/fallback outcome, and
   unusable alpha range. **Complete.** Provider results are qualified
   before family conversion, `collect_all` preserves every cell outcome, and only an
   explicitly requested complete-axis Cartesian sub-grid can become a partial family.
3. **PR-05C — configuration binding.** Map canonical airfoils, scenarios, Reynolds/Mach
   grids, provider order, retry, cache, health, and acceptance policies from a strict
   configuration boundary. **Complete in this change.** The standalone version-1
   polar config resolves paths relative to itself, rejects unknown/unused settings,
   validates provider coverage, and constructs the stateful runtime lazily.
4. **PR-05D — analysis integration.** Route generated families into the first section/BEM
   consumer with explicit interpolation bounds and end-to-end provenance in
   `SimulationResult`. **Complete in this change.** The initial fail-closed section
   consumer evaluates station kinematics and quasi-steady two-dimensional loads, then
   trapezoidally integrates only the declared station interval. It is explicitly not
   full BEM: induction, swirl, Prandtl losses, dynamic stall, and compressibility
   correction remain unapplied.
5. **PR-05E — real-backend qualification.** Capture reviewed XFOIL and NeuralFoil outputs
   for a declared operating envelope, freeze backend versions, and publish the benchmark
   report separately from deterministic adapter-contract fixtures.

## Confirmed PR-05 design decisions

- The family grid is a complete Cartesian product in deterministic Mach-major,
  Reynolds-minor order. Both axes must be strictly increasing and unique.
- The request template is anchored to the first grid cell, preventing its Reynolds or
  Mach values from becoming silently ignored inputs.
- Complete family generation remains sequential and fail-fast by default. Every
  accepted table requires a complete provider result; timing is telemetry and never an
  acceptance threshold.
- Every cell retains both `PolarGenerationResult` and its canonical `PolarTable`, so
  provider identity, cache state, retries, fallback, circuit state, warnings, and solver
  metadata remain auditable.
- A capability mismatch still follows the PR-04F provider chain. This lets a Mach-capable
  provider handle nonzero-Mach cells while NeuralFoil remains eligible at Mach zero.
- A partial provider result is evaluated by an explicit qualification policy before
  table conversion. Rejection is routing-neutral for provider health, is never retried,
  and continues to the next provider with an auditable `result_rejected` attempt.
- `collect_all` catches typed provider-chain exhaustion per cell but never masks cache
  infrastructure failures, unexpected exceptions without health isolation, or
  `BaseException` control flow.
- Sparse successes never become a `PolarFamily` implicitly. `subgrid_policy="none"`
  returns diagnostics only; `complete_axes` may materialize only a verified Cartesian
  product of complete Mach rows or complete Reynolds columns. The largest candidate is
  selected, with complete rows winning deterministic ties.
- Polar runtime configuration is separate from the canonical mechanical design schema.
  Every section is strict; durations and angles retain explicit units, while relative
  airfoil/cache paths are anchored to the config file.
- Optional provider backends are resolved only by `build_runtime()`. Config loading can
  therefore be audited without requiring XFOIL or NeuralFoil to be installed.
- Real XFOIL/NeuralFoil physical qualification remains PR-05E and is not represented by
  deterministic adapter doubles.

## Entry gates and distance

| PR-05 entry gate | State | Evidence |
| --- | --- | --- |
| Stable provider/result contract | Met | PR-04 |
| Both adapters and strict capability mapping | Met | PR-04A/B |
| Cache, lifecycle, and duplicate-work control | Met | PR-04C/D/E |
| Fallback, retry, health, and circuit isolation | Met | PR-04F/G |
| Deterministic acceptance and benchmark harness | Met | PR-04H |
| Real-solver physical qualification data | Open; not a code-start blocker | PR-05E |

The **PR-05 code-start gate is complete**, and PR-05A/B/C/D now supply generation,
partial-grid, strict runtime configuration, and fail-closed section-consumption contracts.
The implementation sequence is therefore **4 of 5 PR-05 increments complete**. PR-05E
real-backend qualification is next.
Production aerodynamic qualification remains **5 of 6 readiness gates complete** until
real XFOIL/NeuralFoil baselines are reviewed; that work is deliberately tracked as PR-05E
so contract fixtures cannot be mistaken for physical validation.
