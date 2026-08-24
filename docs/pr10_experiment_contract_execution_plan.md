# PR-10 experimental validation contract execution plan

## Objective

Define the versioned boundary for thrust, torque, RPM, voltage, current, atmosphere,
calibration, zero drift, repeated runs, and uncertainty propagation.  The same test
stand contract must cover a fixed reference propeller and the foldable prototype.

## Test-driven gates

- Every required sensor has a certificate identity, SHA-256, SI unit, validity
  interval, and standard uncertainty.
- Raw steady samples retain run, role, design, repeat, and sample identities.
- Fixed-reference and foldable roles are both required; at least three independent
  repeats per run are required by the default policy.
- Duplicate samples, expired calibrations, non-finite values, excessive pre/post
  zero drift, or missing channels fail closed.
- Type-A repeatability, calibration uncertainty, and zero-drift uncertainty are
  combined by root-sum-square; expanded uncertainty uses an explicit coverage factor.
- Software fixtures can pass schema/math gates but can never become physical evidence.

## Completion boundary

PR-10 software/preparation is complete when a deterministic fixture reproduces the
quality decision and uncertainty budget. Physical validation remains pending until
the calibrated stand supplies raw fixed-reference and foldable-prototype measurements.

## Public experimental foundation

The existing APC Slow Flyer 10x4.7 UIUC fixture is linked into the PR-10 evidence
report as a published external baseline: 60 measured coefficient points, of which 50
are in the declared propulsive envelope. It remains in coefficient form (CT, CP, J,
RPM); the fixture's assumed standard atmosphere must not be used to reconstruct
dimensional thrust or torque.

An independent same-propeller wind-tunnel study by Morgado and Pascoa is retained as
method and cross-laboratory context. Its 4000/5000 RPM comparison, 400 samples at
8 Hz (50 seconds), sample-count convergence study, and in-situ thrust/torque check
loads are useful test-design precedents. Reported uncertainty values belonging to
other propellers are not transferred to this propeller or to the project hardware.

NIST TN 1297 supplies the Type-A/Type-B uncertainty reporting basis. ASTM E74 and
E2428 support static force/torque calibration traceability only; they do not establish
the dynamic adequacy of the rotating test stand. The research classification and
source links are recorded in the generated evidence and
[public-baseline note](pr10_public_experimental_baseline.md).
