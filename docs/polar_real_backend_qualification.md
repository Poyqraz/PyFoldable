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
| Reference | XFOIL subprocess adapter v2, XFOIL 6.99 |
| Candidate | NeuralFoil adapter v1, NeuralFoil 0.3.3 |

XFOIL 6.99 is built from MIT's official `xfoil6.99.tgz` source archive, pinned by
SHA-256. The workflow uses the source-provided double-precision GNU Fortran build flags
without enabling floating-point traps. Ubuntu's `6.99.dfsg+1-3` package is not used:
its `invalid,zero` trap flags terminate the iterative viscous solver with `SIGFPE` for
this envelope. Adopting another XFOIL release creates a new qualification case instead
of silently changing this baseline. NeuralFoil is installed at exactly 0.3.3.

## Capture and review boundary

The `Polar real-backend qualification` workflow runs on relevant pull requests and can
also be dispatched manually on `main`. It has `contents: read` permission and uploads a
bundle containing:

- `manifest.json`, with source revision, request fingerprint, exact expected and actual
  provider identities, environment versions, and SHA-256 file hashes;
- one raw result per provider; and
- `benchmark.json`, with coverage and CL/CD/CM discrepancies.

If provider execution fails, the workflow retains its failing status but still uploads
a hash-manifested `failure.json`. Failures before provider execution, including source
verification, compiler, dependency, and build failures, produce a separate
`workflow_failure.json` containing the exact run/attempt identity and step outcomes.
Artifact names include the run ID and attempt so repeated or concurrent captures cannot
be confused. Failure evidence is never eligible for promotion.

Every bundle starts with `review_state: "unreviewed"` and
`promotion_allowed: false`. Identity drift is rejected before solver execution, output
directories are never overwritten, and an unusable reference remains available as a
failed review artifact rather than being discarded.

Before promotion, a reviewer must verify every file hash, inspect XFOIL convergence and
NeuralFoil confidence, reproduce the capture on the same source revision, and compare
both raw result sets. Promotion is a separate code change that preserves the manifest
and adds regression coverage.

The `Polar real-backend reproducibility review` workflow accepts two distinct successful
qualification run IDs. It downloads both artifacts with `actions: read`, rejects digest
or manifest tampering, and compares source revision, solver inputs, provider/build
identity, environment, benchmark decisions, and raw point results exactly. Only capture
time and elapsed-time telemetry are excluded. Its report always remains review-only with
`promotion_allowed: false`; a successful comparison cannot promote a baseline by itself.

All first-party GitHub actions are pinned to verified release commits that use the
Node.js 24 runtime. This avoids deprecated Node.js 20 execution and prevents moving
major-version tags from silently changing the qualification environment.

After promotion, `examples/run_real_backend_qualification.py` re-runs exact provider
identities against reviewed fixtures. It is deliberately separate from deterministic
adapter tests.

## Promoted baseline

The `naca0012_re200k_real_v1` baseline under
`tests/fixtures/polar_real_qualification/` was promoted from qualification runs
`31942197266` and `31943335405`, both captured at source revision `464dde5`.
Reproducibility run `31945859274` verified both artifact and manifest digests and
reported no semantic differences. The committed directory preserves the first complete
capture, the second manifest, the comparison report, the XFOIL-derived golden fixture,
and an approved promotion record with all originating run, artifact, and digest IDs.

Physical review confirmed nine converged points from each provider, full coverage, a
minimum NeuralFoil confidence of 0.96435, and maximum NeuralFoil-to-XFOIL differences of
0.02501 in CL, 0.000864 in CD, and 0.00513 in CM. The symmetric NACA 0012 point pairs
have maximum XFOIL odd/even residuals of 0.0001 in CL, 0.00001 in CD, and zero in CM.
XFOIL exits successfully while retaining its non-fatal
`IEEE_DIVIDE_BY_ZERO` summary in the preserved metadata; the promotion tests require
that diagnostic, the zero return code, all converged statuses, and the reviewed physical
metrics to remain mutually consistent.

Every relevant qualification pull request now runs both an unreviewed fresh capture and
the promoted-baseline regression. The regression uses
`configs/polars/NACA0012_RE200K_REAL.toml`, disables cache and retry masking, and fails
if the exact provider identities, solver envelope, coverage, usability, or coefficient
tolerances drift.
