# PY-06D1 — mechanism observation comparison

This increment makes transition histories usable before parameter fitting. It
extends the PY-05 numerical solver and supplies a typed Python comparison API;
it does not add a new equation, optimizer, JSON importer or UI flow. No usable
prototype transition dataset is currently included. Run the offline example:

```sh
python examples/run_mechanism_observation_comparison.py
```

The example prints deterministic JSON with `pending_no_measured_evidence`,
`physical_qualification=false` and `parameter_fitting_performed=false`.

## Supported input and source boundary

`MechanismObservationRun` binds an immutable PY-05 `TransientRequest` to ordered
time/relative-angle observations and per-sample standard angle uncertainty in
radians. Observation endpoints must equal the declared drive phase endpoints.
The phase starts strictly inside both stops and ends at observed first contact
when one is declared. Full opening/closing cycles, static holding, breakaway,
impact continuation, wrapping conversions and aerodynamic feedback are excluded.

`ObservationProvenance` requires physical acquisition/run identity, raw-data and
design SHA-256, blade identity, angle-calibration SHA-256, parameter/initial-state/
torque sources and sampling policy. Only synchronized elapsed seconds and the
PY-05 frame (+z counterclockwise, zero radial-outward, unwrapped relative hinge
angle in radians) are accepted. Initial state must be independently measured for
records declared measured; estimating initial velocity, timing or parameters from
the full holdout trajectory is not allowed by this contract.

RPM and torque use the existing unfiltered piecewise-linear drive. RPM
derivatives are those of each segment; the solver restarts at knots. Maximum
drive and observation gaps plus clock standard uncertainty are explicit. Filtered
or unsynchronized inputs require a future source-bound preprocessing contract.
Torque must be explicitly controlled zero or independently measured; unavailable
torque is not zero, and torque inferred from the evaluated angles is not an
independent input. This initial contract treats drive and angle values as parts
of one declared acquisition bundle. It does not parse or authenticate that bundle
or verify calibration certificates. `measured_declared_unverified` means exactly
that; hashes establish identity, not authenticity or physical qualification.

## Numerical and comparison behavior

`sample_mechanism_transient(request, times)` evaluates the existing RK45 quartic
interpolant only inside each accepted integration step through the first stop.
The returned `TransientSamples.result` is the same adaptive trajectory as the
original `solve_mechanism_transient(request)`, including quadrature and segment
indices. Observation timestamps do not change drive knots, solver steps or
equations. This uses SciPy's public
[RK45 dense output](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.RK45.html)
and [local interpolant API](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.RK45.dense_output.html).

`compare_mechanism_observations` reports model-minus-measured residuals in radians
at the original timestamps, per-run unweighted sample RMSE and maximum absolute
residual. These are descriptive values, not acceptance tests, time-integrated
scores or independent evidence from every dense sample. Multiple runs are not
pooled. Numerical tolerances are not measurement uncertainty. Observed angle
uncertainty is retained, but model, drive and clock uncertainty are not propagated;
the uncertainty decision therefore remains indeterminate, even at zero residual.

If predicted contact precedes the last measurement, all excluded timestamps and
the reason are retained, status is `blocked_incomplete_prediction`, and full-phase
RMSE/maximum are absent. No prediction is extrapolated through impact. Predicted
and observed stop identity and timing discrepancy are reported separately. No
contact-time acceptance tolerance is inferred. A contact boundary separated only
by at most eight floating-point ULPs is explicitly
`indeterminate_contact_boundary`, including an observed terminal stop missed by
that much angle roundoff. This diagnostic never snaps a timestamp, adds a
prediction or uses clock uncertainty to permit extrapolation. Excluded samples
and absent full-window aggregates remain visible.

The deterministic request JSON binds every input, provenance declaration,
implementation source hash and numerical runtime version. `request_sha256`
changes when any of these change; an old expected hash fails before solving.

## Frozen partitions and later calibration

`partition_mechanism_runs(training, holdout)` requires nonempty bounded tuples for
the same design and blade. Repeated physical-run IDs or raw-data hashes are
rejected across and within both partitions. The partition digest includes role,
order and complete request hashes, so later preprocessing/observation changes
invalidate it. A renamed file cannot create an independent holdout. A dishonest
new acquisition ID and changed raw hash cannot be discovered without raw-data
audit; callers must preserve the canonical physical identity before cropping or
resampling. Two phases extracted from the same run belong to the same partition;
this first API conservatively rejects repeated runs entirely.

`all_runs_declared_measured` only reports that every record declares measured evidence;
it does not grant calibration/qualification readiness. D2 additionally needs
independent evidence audit, identifiability, excitation and parameter-bound gates.
Uniformly scaling mass/inertia/spring stiffness/viscous damping/Coulomb torque
with zero applied torque, fixed geometry and fixed friction regularization speed
leaves the normalized equation invariant. A fit of every parameter to angle alone is not
defensible. No target fitting, calibration or physical promotion occurs in D1.

## TDD and review

The new contract test was observed red before implementation (missing module).
Analytic oscillator and signed-RPM ramp checks cover irregular timestamps, drive
knots, time translation and original-trajectory equality. Tests cover source/hash
changes, stale requests, invalid units/frame/clock/torque, gap/coverage/budget
limits, terminal/out-and-back contact, event mismatch and run/hash partition
leakage. Synthetic assertions establish software behavior only. Independent
automated review, the full regression suite and exact-head GitHub CI precede
merge. PR #3 and unrelated report edits remain separate.
