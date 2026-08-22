# PR-06C fixed-propeller benchmark result

**Decision:** `pr06d_blocked` — benchmark pass: `false`.

## Qualification summary

| Gate | Result | Observed | Limit |
| --- | --- | ---: | ---: |
| Solution coverage | PASS | 100.0% | ≥ 95.0% |
| CT WMAPE | FAIL | 26.40% | ≤ 15.0% |
| CP WMAPE | FAIL | 28.28% | ≤ 20.0% |
| CT normalized bias | FAIL | -26.40% | ±10.0% |
| CP normalized bias | FAIL | -28.28% | ±15.0% |
| Radial 80→160 delta | PASS | 0.021% | ≤ 0.5% |
| Representative polar evidence | FAIL | proxy | required |
| Every-regime coverage | PASS | 100.0% | ≥ 95.0% |
| Every-regime CT WMAPE | FAIL | 40.31% | ≤ 15.0% |
| Every-regime CP WMAPE | FAIL | 38.35% | ≤ 20.0% |

## Correct interpretation

- passes the declared terminal annulus-sensitivity gate.
- not qualified: full-envelope coefficient accuracy and representative polar evidence fail, so PR-06D remains blocked.
- Principal failure: The signed local branch restores full solution coverage, exposing large forward-flight model-form/polar error that subset-only metrics hid.
- Data boundary: The existing APC 202602 repository table is manufacturer vortex-model output, not wind-tunnel validation; UIUC measurements are the physical reference used here.
- Timing is telemetry only and is not an acceptance gate.

## Coverage by regime

| Regime | Solved | Coverage | CT WMAPE | CP WMAPE |
| --- | ---: | ---: | ---: | ---: |
| static | 16/16 | 100.0% | 11.39% | 11.26% |
| forward | 34/34 | 100.0% | 40.31% | 38.35% |

## Evidence scope

The frozen fixture contains 60 measured points; 50 positive-thrust points are in the declared propulsive envelope and 10 windmilling points are retained but excluded.

The geometry is an approximate UIUC digitization. Run-specific tunnel atmosphere is not present in the coefficient files, so the solver uses a declared standard-atmosphere assumption. The APC airfoil proxy is intentionally non-qualifying.

## Required remediation before PR-06D

1. reconstruct or obtain the tested blade's spanwise section geometry
2. generate Reynolds-aware polars with recorded solver confidence and limits
3. address rotational/model-form error and rerun this unchanged frozen policy
4. obtain independent aerodynamic review before physical promotion

Machine-readable evidence: `reports/pr06c_fixed_propeller_benchmark.json`.
