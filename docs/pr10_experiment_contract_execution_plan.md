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
