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
| PR-04H | Golden acceptance and cross-provider benchmark | Complete in this change |
| PR-05 | Provider-backed `PolarFamily` integration | Ready to start after PR-04H merges |

## PR-05 — provider-backed PolarFamily integration

PR-05 will close the remaining gap between generating one polar and safely supplying a
multi-Reynolds/Mach family to an aerodynamic analysis consumer.

1. **PR-05A — family generation contract.** Define an ordered operating-point grid,
   generate each table through `generate_polar_orchestrated()`, and assemble a
   deterministic `PolarFamily` without losing provider/cache/orchestration provenance.
2. **PR-05B — partial-grid policy and batch diagnostics.** Make fail-fast versus partial
   family behavior explicit; report every requested cell, retry/fallback outcome, and
   unusable alpha range.
3. **PR-05C — configuration binding.** Map canonical airfoils, scenarios, Reynolds/Mach
   grids, provider order, retry, cache, health, and acceptance policies from a strict
   configuration boundary.
4. **PR-05D — analysis integration.** Route generated families into the first section/BEM
   consumer with explicit interpolation bounds and end-to-end provenance in
   `SimulationResult`.
5. **PR-05E — real-backend qualification.** Capture reviewed XFOIL and NeuralFoil outputs
   for a declared operating envelope, freeze backend versions, and publish the benchmark
   report separately from deterministic adapter-contract fixtures.

## Entry gates and distance

| PR-05 entry gate | State | Evidence |
| --- | --- | --- |
| Stable provider/result contract | Met | PR-04 |
| Both adapters and strict capability mapping | Met | PR-04A/B |
| Cache, lifecycle, and duplicate-work control | Met | PR-04C/D/E |
| Fallback, retry, health, and circuit isolation | Met | PR-04F/G |
| Deterministic acceptance and benchmark harness | Met after this change | PR-04H |
| Real-solver physical qualification data | Open; not a code-start blocker | PR-05E |

After PR-04H merges, the **code-start gate for PR-05 is 100% complete**: the provider
platform can be integrated without adding another adapter-layer prerequisite. Production
aerodynamic qualification remains **5 of 6 gates complete** until real XFOIL/NeuralFoil
baselines are reviewed; that work is deliberately tracked as PR-05E so contract fixtures
cannot be mistaken for physical validation.
