# Real polar-backend qualification

PR-05E separates physical solver evidence from the deterministic adapter-contract
fixture under `tests/fixtures/polar_acceptance`. That fixture remains a useful unit-test
input, but it is not physical XFOIL or NeuralFoil evidence.

## Frozen capture envelope

| Input | Value |
| --- | --- |
| Airfoil | Closed-trailing-edge NACA 0012, 81 cosine-spaced coordinates |
| Reynolds number | 200,000 |
| Mach number | 0.0 |
| Angles of attack | -6 to 10 degrees, inclusive, in 2-degree steps |
| Transition | Natural, `Ncrit = 9`, `xtr_upper = xtr_lower = 1` |
| Reference | XFOIL subprocess adapter v1, XFOIL 6.99 |
| Candidate | NeuralFoil adapter v1, NeuralFoil 0.3.3 |

XFOIL 6.99 is built from MIT's official `xfoil6.99.tgz` source archive, pinned by
SHA-256. The workflow uses the source-provided double-precision GNU Fortran build flags
without enabling floating-point traps. Ubuntu's `6.99.dfsg+1-3` package is not used:
its `invalid,zero` trap flags terminate the iterative viscous solver with `SIGFPE` for
this envelope. Adopting another XFOIL release creates a new qualification case instead
of silently changing this baseline. NeuralFoil is installed at exactly 0.3.3.

## Capture and review boundary

The `Polar real-backend qualification` workflow is manual-only and has
`contents: read` permission. It uploads a bundle containing:

- `manifest.json`, with source revision, request fingerprint, exact expected and actual
  provider identities, environment versions, and SHA-256 file hashes;
- one raw result per provider; and
- `benchmark.json`, with coverage and CL/CD/CM discrepancies.

If provider execution fails, the workflow retains its failing status but still uploads
a hash-manifested `failure.json`. Failure evidence is never eligible for promotion.

Every bundle starts with `review_state: "unreviewed"` and
`promotion_allowed: false`. Identity drift is rejected before solver execution, output
directories are never overwritten, and an unusable reference remains available as a
failed review artifact rather than being discarded.

Before promotion, a reviewer must verify every file hash, inspect XFOIL convergence and
NeuralFoil confidence, reproduce the capture on the same source revision, and compare
both raw result sets. Promotion is a separate code change that preserves the manifest
and adds regression coverage. Until reviewed data is promoted, PR-05E is in progress.

After promotion, `examples/run_real_backend_qualification.py` re-runs exact provider
identities against reviewed fixtures. It is deliberately separate from deterministic
adapter tests.
