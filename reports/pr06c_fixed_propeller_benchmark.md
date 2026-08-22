# PR-06C fixed-propeller benchmark result

**Decision:** `pr06d_blocked` — benchmark pass: `false`.

## Qualification summary

| Gate | Result | Observed | Limit |
| --- | --- | ---: | ---: |
| Solution coverage | FAIL | 46.0% | ≥ 95.0% |
| CT WMAPE | PASS | 14.73% | ≤ 15.0% |
| CP WMAPE | PASS | 14.13% | ≤ 20.0% |
| CT normalized bias | FAIL | -14.73% | ±10.0% |
| CP normalized bias | PASS | -14.13% | ±15.0% |
| Radial 80→160 delta | PASS | 0.021% | ≤ 0.5% |
| Representative polar evidence | FAIL | proxy | required |
| Every-regime coverage | FAIL | 20.6% | ≥ 95.0% |
| Every-regime CT WMAPE | FAIL | 22.99% | ≤ 15.0% |
| Every-regime CP WMAPE | FAIL | 20.35% | ≤ 20.0% |

## Correct interpretation

- passes the declared terminal annulus-sensitivity gate.
- not qualified: solution coverage and representative polar evidence must pass before coefficient error can authorize PR-06D.
- Principal failure: The positive-loading-only local branch rejects forward-flight cases when an inner annulus becomes locally unloaded or negative-loaded.
- Data boundary: The existing APC 202602 repository table is manufacturer vortex-model output, not wind-tunnel validation; UIUC measurements are the physical reference used here.
- Timing is telemetry only and is not an acceptance gate.

## Coverage by regime

| Regime | Solved | Coverage | CT WMAPE | CP WMAPE |
| --- | ---: | ---: | ---: | ---: |
| static | 16/16 | 100.0% | 11.39% | 11.26% |
| forward | 7/34 | 20.6% | 22.99% | 20.35% |

## Evidence scope

The frozen fixture contains 60 measured points; 50 positive-thrust points are in the declared propulsive envelope and 10 windmilling points are retained but excluded.

The geometry is an approximate UIUC digitization. Run-specific tunnel atmosphere is not present in the coefficient files, so the solver uses a declared standard-atmosphere assumption. The APC airfoil proxy is intentionally non-qualifying.

## Required remediation before PR-06D

1. add a reviewed mixed/local-negative-loading forward-flight branch
2. obtain or generate a span-representative, Reynolds-aware APC polar family
3. rerun this frozen fixture without weakening the predeclared policy

Machine-readable evidence: `reports/pr06c_fixed_propeller_benchmark.json`.
