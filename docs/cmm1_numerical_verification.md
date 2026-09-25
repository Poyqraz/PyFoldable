# CMM-1 Phase 4 numerical verification

This evidence package is intended to establish numerical verification of the
CMM-1 screening model. Merge requires independent closure of PR #72.

Phase-4 evidence is implemented. Independent review is required before merge.

`physical_qualification` remains false. PR-06C remains unresolved. No
aerodynamic hinge load exists. No GEOM gate is promoted. There is no
calibration and no experimental validation. CMM-2 is not approved.

This document records frozen output of
`tests/verification/test_cmm1_numerical_verification.py`. It is not a
combined score. Production dynamics, BEM, motor algebra, and the
source-bound service are unchanged. `model_class` remains
`partial_coupled_screening_only`. `aerodynamic_hinge_torque_status` remains
`unavailable_omitted_by_cmm1`. `full_propeller_clearance` remains null.

Component order in every error triple is `theta`, `theta_dot`, `omega`.
For a reference component `r` and the run's solver controls,

```text
scale = atol + rtol * abs(r)
e = abs(test - r) / scale
```

The acceptance value `e <= 1` is a Phase 4 numerical-policy target for the
controls of that run. It is not a theorem about the RK45 local-error
controller. Radians, hinge rate, and shaft speed are never combined into one
raw norm.

## Layer 1 — exact algebra and the represented matrix

IDs 01 and 17. The mass solve is checked by an independent 2x2 solution of
the represented entries, in 80-digit test arithmetic when the forward gap is
reported. The motor cubic root is a standard-library `Decimal` bisection of
the represented coefficients. The PR-07 current is the value under test.
`_motor_state` is not the oracle.

## Layer 2 — exact analytic dynamics

IDs 02, 03, 04, 05, and 06. Cases A–D and the manufactured quadratic
trajectory use the pure-dynamics evaluator injection. `C = m R c` is zero
when the contract sets it to zero. Case D is the primary step-refinement
fixture. Its observed orders are measurements on that fixture. They are not
a claim of global fifth-order RK45.

## Layer 3 — independent integrator and quadrature

IDs 07 and 09. SciPy DOP853 is test-only and calls the declared CMM-1
right-hand side. A second, tighter DOP853 run is accepted only when every
component change is at most 0.1 of the CMM-1 error scale. The dense DOP853
solution is evaluated at the actual CMM-1 sample times. The CMM-1 samples
are not interpolated. `cumulative_work_j` is reported as a diagnostic and is
not the work oracle.

## Layer 4 — cross-model consistency

IDs 10, 11, and 12. PY-05 recovery is algebraic. The PR-07 operating point
is the runtime root of the real motor and foldable BEM laws. The deployed
fixed/foldable equality is the existing production test, reused rather than
copied. None of these results promote a free PY-05 trajectory, a physical
RPM, or a qualified rotor.

## Layer 5 — source-bound motor, BEM, and CMM-1

IDs 13 and 14. One folded source-bound fixture uses `Pr07MotorEvaluator`,
`FoldableBemShaftEvaluator`, `bounds="error"`, and committed synthetic
polars. ODE refinement and annulus refinement are separate. Annulus change
is not called rotor accuracy.

## Layer 6 — boundaries and determinism

IDs 08, 15, 16, 18, and 19. Tolerance sweeps report step counts before any
sensitivity sentence. Contact checks reconstruct the first stop time. They
do not validate impact physics. Same-process replay is bitwise. Python 3.10
and 3.11 are not required to share report hashes.

## Matrix

### 01 Mass / acceleration grid

- Reference: cross-model, represented entries plus an independent solve.
- Fixture: `N in {1, 2, 4}`, interior angles, ordinary `I0 = 1e-3`, larger
  `I0 = 1e-2`, resolved `I0 = 1e-8`, and the point-mass boundary
  `J = m c^2`. `I0 = 1e-20` at `theta = 0` stays unresolved.
- Result: **PASS**. 42 resolved cases. Maximum row backward error
  `2.10e-16`. Minimum represented pivot `3.09e-5`.
- Point-mass `I0 = 1e-8`, `theta = 0`, `N = 2`: backward errors
  `9.06e-17` and `2.19e-17`, forward gap versus the high-precision solve
  `1.73e-5`.
- Threshold: the production row backward-error policy, including the
  zero-denominator rule. Basis: mathematical.
- Interpretation: the `I0 = 1e-8` point-mass row is accepted by the
  production pivot policy, and its backward error is near roundoff. The
  forward gap of `1.73e-5` shows that this small backward error is not a
  small forward error near the pivot. The `I0 = 1e-20` matrix still fails
  closed and returns no acceleration.

### 02 Constant equilibrium (Case A)

- Reference: analytic. Interior angle `-0.2 rad`, zero hinge rate, shaft
  speed `28 rad/s`, spring and centrifugal balance, regularized friction
  present and zero at zero rate.
- Controls: `rtol = 1e-6`, `max_step_s = 5e-4`, 82 samples.
- Endpoint and maximum normalized errors:
  `(0, 6.38e-10, 0)`.
- Initial accelerations are at the zero residual. Normalized mechanical-energy
  drift is `0`.
- Threshold: `e <= 1` and energy drift at most `rtol`. Basis: numerical-policy.
- Result: **PASS**.

### 03 Uniform hinge motion (Case B)

- Reference: analytic. `C = k = b = tau_c = Qh = Qm - Qa = 0`.
- Angle `0.12 + 0.35 t`, hinge rate `0.35 rad/s`, shaft speed `24 rad/s`,
  no contact.
- Maximum normalized errors: `(3.02e-9, 0, 0)`.
- Threshold: `e <= 1`. Basis: numerical-policy.
- Result: **PASS**.

### 04 Constant shaft acceleration (Case C)

- Reference: analytic. `C > 0`, `theta = theta_dot = theta_rest = 0`,
  `alpha = 4 rad/s^2`.
- `Qh = B(0) alpha` and `Qm - Qa = M00(0) alpha`.
- Maximum normalized errors: `(0, 0, 2.92e-9)`.
- Initial shaft acceleration matches `alpha` at `1e-12` relative tolerance.
- Threshold: `e <= 1`. Basis: numerical-policy.
- Result: **PASS**.

### 05 Coupled oscillator and conservative energy (Case D)

- Reference: analytic. `C = b = tau_c = Qh = Qm - Qa = 0`, `k = 0.8 N·m/rad`,
  `nu = 96.301 rad/s`.
- Step ceilings `0.002`, `0.001`, `0.0005` s with fixed loose controls
  `rtol = 1e-3` and atols `(1e-4, 1e-3, 1e-2)`, so the runs are step-limited.
- Samples / RHS evaluations: `26/178`, `51/353`, `101/703`.
- Maximum absolute errors:

| max_step_s | theta | theta_dot | omega |
| --- | --- | --- | --- |
| 0.002 | 1.122e-8 | 1.307e-6 | 1.796e-7 |
| 0.001 | 3.322e-10 | 4.238e-8 | 5.821e-9 |
| 0.0005 | 1.013e-11 | 1.338e-9 | 1.838e-10 |

- Observed `p = log2(error_h / error_h/2)`: theta `5.078`, `5.035`;
  theta_dot `4.947`, `4.985`; omega `4.947`, `4.985`.
- Both reductions are above the roundoff floor. The gate is `p >= 2` for every
  resolvable reduction, read from coarse to fine. The measured values are near
  5 on this smooth fixture only. They are not a global RK45 fifth-order claim.
- Roundoff fallback cannot override a failed resolvable refinement. A later
  sample at the floor does not excuse an earlier pair whose order is below 2,
  and a sequence that leaves the floor is rejected. The Case D theta floor is
  `5.684e-14`. On that floor, `[1e-6, 1e-6, 1e-14]` and
  `[1e-14, 1e-6, 1e-8]` fail. `[1e-6, 1e-8, 1e-14]` and a sequence that stays
  at or below the floor return `order_unresolvable_at_roundoff`. The measured
  Case D histories return `resolved_order`.
- Final maximum normalized errors: `(7.39e-8, 2.74e-7, 3.71e-9)`.
- Conservative energy drift `/ E0`: `7.56e-10`, `2.44e-11`, `7.67e-13`.
  `E0` is the positive exact initial energy.
- Threshold: `e <= 1` and `p >= 2` while the error is above the floor.
  Basis: numerical-policy. Result: **PASS**.

### 06 Manufactured forcing

- Reference: manufactured. `theta* = 0.05 + 0.15 t - 0.2 t^2`,
  `omega* = 26 + 1.5 t - t^2`, viscous `b = 0.002`.
- Affine `Qh*` is stored at the two history endpoints. The shaft difference
  is supplied by a synthetic motor evaluator.
- Maximum absolute errors are `2.08e-17`, `5.55e-16`, and `3.55e-15`.
  The shaft-speed figure is one unit in the last place of a value near
  `26 rad/s`. Normalized errors are at most `3.97e-9`.
- Observed order is not required: the trajectory is already at the
  floating-point floor.
- `run_coupled_transient` still has no synthetic evaluator argument, and
  `assert_cmm1_production_evaluators` rejects the synthetic pair.
- Threshold: `e <= 1`. Basis: numerical-policy. Result: **PASS**.

### 07 Independent DOP853 comparison

- Reference: independent solver. Smooth nonlinear contact-free motion with
  `C > 0` and a nonzero spring. DOP853 tolerances `1e-8` then `1e-10`.
- Reference change, as a fraction of the CMM-1 scale:
  `(1.06e-2, 1.24e-3, 3.80e-5)`. Acceptance limit: `0.1`.
- CMM-1 `rtol = 1e-6`, `max_step_s = 0.001`, 41 samples.
- Maximum normalized errors versus the tight dense solution:
  `(2.66e-4, 3.90e-5, 1.29e-6)`.
- Threshold: stabilized reference and `e <= 1`. Basis: numerical-policy.
- Result: **PASS**. This checks RK45 against the same right-hand side. It
  does not prove the equations.

### 08 rtol / atol sensitivity

- Reference: characterization of Case D. `max_step_s = 0.002`, duration
  `0.04 s`.
- rtol sweep at atols `(1e-8, 1e-8, 1e-6)`: `rtol` of `1e-3`, `1e-4`, and
  `1e-5` all accept 21 samples and 143 right-hand-side evaluations.
- Proportional atol sweep at `rtol = 1e-4`: three scales, all 21 samples and
  143 evaluations.
- Maximum normalized hinge-rate error at `rtol = 1e-5` is `2.04`. The
  absolute trajectory is the step-limited one; the tighter scale makes `e`
  larger. That run is not the Case D acceptance run.
- Threshold basis: empirical-regression of step counts.
- Result: **CHARACTERIZATION ONLY**. rtol/atol sensitivity was not
  demonstrated in this fixture because max_step controlled the accepted steps.
  The `e ≈ 2.04` hinge-rate observation at `rtol = 1e-5` remains visible.

### 09 Forced / dissipative energy-work

- Reference: tight DOP853 trajectory and an independent `quad` of
  `(Qm-Qa) omega + N Qh theta_dot - N b theta_dot^2 - N tau_c theta_dot tanh(theta_dot/v)`.
- Reference change fractions: `(7.33e-6, 8.84e-5, 4.99e-8)`, limit `0.1`.
- Quadrature error estimate: `4.51e-18`. Positive energy scale: `0.746404 J`.
- `|Delta E - integral| / E`: `2.94e-16`.
- Trapezoidal `cumulative_work_j` diagnostic error `/ E`: `1.91e-10`.
  Fifth-order behavior is not required from that diagnostic.
- Threshold: balance error at most the CMM-1 `rtol` of `1e-6`.
  Basis: numerical-policy. Result: **PASS**.
- No battery-to-mechanical conservation claim is made.

### 10 PY-05 seeded cross-model set

- Reference: cross-model. Twelve frozen interior states, `N in {1, 2, 4}`,
  both signs of hinge rate and shaft acceleration, and three regularized
  friction states.
- The shaft torque difference is built so the represented CMM-1 solve should
  recover the prescribed `omega_dot` and the PY-05 hinge acceleration.
- Maximum gaps: shaft acceleration `4.66e-15`, hinge acceleration
  `8.88e-16`. Minimum pivot `0.661`.
- Threshold: `1e-8` times the acceleration scale. Basis: mathematical.
- Result: **PASS**. This is not a claim that free PY-05 and free CMM-1
  trajectories match, and it is not a feedback controller.

### 11 PR-07 + real BEM equilibrium

- Reference: cross-model. Real `Pr07MotorEvaluator` and
  `FoldableBemShaftEvaluator` on broad synthetic polars. The pure-dynamics
  stops are `-0.5` and `0.5`, so zero is interior. Production stop checks
  are unchanged.
- Runtime root: `3596.5130378488584 rpm`. This is the solver output for this
  fixture, not a physical operating point and not a hard-coded pilot RPM.
- Torque residual `-9.06e-14 N·m`. Accepted PR-07 tolerance `1e-8 N·m`.
  The point is feasible.
- Independent accelerations from `M^-1 [Qm-Qa, 0]`:
  `omega_dot = -7.40e-11`, `theta_ddot = 7.40e-11` rad/s².
- Short-trajectory maximum normalized errors against that residual
  prediction: `(2.31e-9, 6.83e-7, 3.01e-10)`.
- Threshold: residual within the PR-07 tolerance, accelerations within the
  represented solve, and `e <= 1`. Basis: numerical-policy.
- Result: **PASS**.

### 12 Deployed BEM exact limit

- Reference: cross-model.
- Reused test:
  `tests/application/test_coupled_transient_service.py::test_deployed_evaluator_matches_fixed_and_foldable_bem`.
- That test uses production `FoldableBemShaftEvaluator`, `solve_bem_rotor`,
  and `solve_foldable_bem_rotor` at `theta = 0` with `bounds="error"`.
- Qualification remains `screening_only_until_pr06c_passes`.
- Result: **REUSED**. No physical promotion.

### 13 Production source-bound ODE convergence

- Reference: independent DOP853 using fresh PR-07 and foldable BEM instances,
  annulus count 8, the same laws as the production binding.
- Fixture: folded angle `-0.45 rad`, shaft speed `140 rad/s`, throttle
  `0.25`, duration `0.02 s`, `bounds="error"`, no contact.
- DOP853 change fractions: `(1.55e-4, 6.36e-4, 1.31e-5)`. Limit `0.1`.
- CMM-1 controls: `rtol = 1e-5`, atols `(1e-7, 1e-6, 1e-5)`.

| max_step_s | samples | RHS | endpoint e | max e |
| --- | --- | --- | --- | --- |
| 0.002 | 12 | 80 | (1.01e-4, 1.08e-4, 2.98e-6) | (1.01e-4, 1.08e-4, 2.98e-6) |
| 0.001 | 22 | 150 | (2.58e-6, 3.20e-6, 9.43e-8) | (5.19e-6, 1.76e-5, 4.26e-7) |
| 0.0005 | 42 | 290 | (3.24e-7, 3.53e-7, 1.18e-8) | (6.12e-6, 1.53e-5, 3.95e-7) |

- Endpoint absolute errors decrease on all three components across both
  halvings. The sample-maximum for `theta` rises from `5.19e-6` to
  `6.12e-6` on the last halving. That difference is far below `e = 1` and
  below the reference-change scale, so it is not a resolvable divergence.
- Invariants on the artifact: `physical_qualification = false`,
  `bem_qualification = screening_only_until_pr06c_passes`,
  aerodynamic hinge status `unavailable_omitted_by_cmm1`.
- Threshold: stabilized reference, decreasing endpoint error, final
  `e <= 1`. Basis: numerical-policy. Result: **PASS**.

### 14 Embedded BEM annulus sensitivity

- Reference: characterization. The same source-bound fixture as ID 13.
- ODE controls fixed: `rtol = 1e-6`, `max_step_s = 0.001`. Every count
  accepts 23 samples.
- Endpoint changes:

| quantity | 4 to 8 | 8 to 16 |
| --- | --- | --- |
| theta | 2.19e-7 | 5.34e-8 |
| theta_dot | 1.97e-5 | 3.69e-6 |
| omega | 2.18e-5 | 4.32e-6 |
| rotor torque, N·m | 2.55e-6 | 2.53e-7 |

- Threshold: each `8 → 16` change is smaller than the `4 → 8` change, for
  `theta`, `theta_dot`, `omega`, and rotor torque. Basis: empirical-regression.
- Result: **CHARACTERIZATION ONLY**. The decreasing changes are for this
  synthetic fixture. This is not general BEM verification and not physical
  rotor accuracy. Physical and BEM qualification remain unresolved. The
  existing standalone midpoint-annulus test remains a separate prerequisite.

### 15 Knot restart / manual split

- Reference: analytic piecewise solution for continuous piecewise-linear
  `Qh` with one interior slope change at `0.02 s`.
- Knot time is present in `segment_boundary_times_s`. Forcing on each side
  matches its linear piece. A manual split initialized from the first
  terminal state matches the full-run endpoint within component scales
  (normalized split gap at most `3.96e-14`).
- Absolute errors are about `1e-18` to `1e-14`.
- Order disposition for every component:
  `order_unresolvable_at_roundoff`.
- Final normalized errors remain far below 1.
- Threshold: `e <= 1`, exact knot identity, and the roundoff rule.
  Basis: numerical-policy. Result: **PASS**.

### 16 Analytic first-contact convergence

- Reference: analytic Case B. Exact contact time `0.0098 s`, inside each
  tested step and not on a knot. Pre-impact hinge rate `1.5 rad/s`, shaft
  speed `30 rad/s`.
- Three ceilings. Time error is `3.47e-18`, `1.73e-18`, and `1.73e-18` s.
  Rate error and shaft-speed error are `0`.
- Every run ends `first_contact_terminal`. The last sample is the contact
  sample, and no sample is later.
- The error is at the floating-point floor, so a monotone-error requirement
  is not applied.
- Threshold: reconstruction tolerance from the solver angle atol, and
  terminal correctness. Basis: numerical-policy.
- Result: **PASS**. This is event reconstruction only.

### 17 Nonlinear motor algebra

- Reference: analytic. Independent `Decimal` bisection, precision 80, of
  `R2 I^3 + (R0 + Rline) I - Vhead = 0` with `R2 = 0.001 ohm/A^2`. The
  positive branch is strictly monotone. SciPy is not the oracle. The bisection
  half-width is about `3.14e-41` A.
- Production calls `root_scalar(..., method="brentq")` with no explicit `xtol`
  or `rtol`, so the public SciPy 1.18.1 `brentq` defaults apply:
  `xtol = 2e-12`, `rtol = 8.881784197001252e-16`.
- Documented root-location contract, from the `brentq` notes:
  `abs(exact - computed) <= xtol + rtol * abs(computed)`. The `rtol` factor
  multiplies the computed root. The reference half-width is added to that
  allowance and is negligible beside `xtol`.
- Interior shaft speeds `1000`, `5000`, `8500`, and `10500` rpm. `1000` rpm is
  the low-speed region near `19 A`.

| rpm | production I, A | reference I, A | current error, A | root limit, A | cubic residual, V | residual bound, V |
| --- | --- | --- | --- | --- | --- | --- |
| 1000 | 19.006478676179 | 19.006478676179 | 2.72e-13 | 2.02e-12 | 3.23e-13 | 2.40e-12 |
| 5000 | 15.692182514425 | 15.692182514426 | 3.32e-13 | 2.01e-12 | -2.79e-13 | 1.70e-12 |
| 8500 | 11.182634656639 | 11.182634656639 | 8.41e-16 | 2.01e-12 | -4.44e-16 | 9.59e-13 |
| 10500 | 6.161192861578 | 6.161192861578 | 2.97e-16 | 2.01e-12 | 0 | 4.31e-13 |

- The residual bound is the mean-value bound
  `gain_max * delta_I + evaluation roundoff`, with
  `delta_I` the root-location allowance and
  `gain_max = R0 + Rline + 3 R2 I_max^2` over that allowance. The 8-ulp term
  covers float evaluation only.
- A current placed on the documented Brent boundary at `1000` rpm has a cubic
  residual above the previous `xtol`-only verification limit and inside this
  bound. An `xtol`-only residual statement does not follow from the solver
  contract.
- Torque from `kt (I - I0)` matches the PR-07 torque at a few ulps. The
  evaluator returns the same current and torque. That match is consistency,
  not the root oracle.
- Threshold basis: mathematical, the documented Brent contract plus the cubic
  derivative. Result: **PASS**. PR-07 is unchanged. This is not physical motor
  validation.

### 18 Numerical boundary classification

- Reference: characterization. Each family has one interior success and one
  exterior rejection. The rejection raises and does not return a shortened
  success artifact.
- Shaft speed: a short interior run completes; `0.5 * OMEGA_MIN` is rejected
  at the request boundary.
- Fold: `theta = pi/2` is rejected before integration.
- Motor current: an interior PR-07 sample returns; current above
  `current_max_a` raises `CoupledDomainExit`.
- Polars: the broad synthetic schedule evaluates; a Mach table that cannot
  cover the query raises `CoupledTransientFailure`.
- Mass: point-mass `I0 = 1e-8` resolves; `I0 = 1e-20` is unresolved.
- Threshold basis: mathematical fail-closed boundaries.
- Result: **PASS**. Smooth success across a hard boundary is not required.
  The PR #71 dense-root suite remains in the dynamics tests and is not
  duplicated here.

### 19 Same-environment reproducibility

- Reference: characterization. One sealed source-bound binding, two fresh
  `run_coupled_transient` calls.
- Status `completed`, 7 samples, no contact.
- Input SHA-256
  `eb428403a285e08708df1e8436db386eb3b48e83a730de3a96745139b3833b22`.
- Report SHA-256
  `1b4f983def8c6c56be94f5265a2033f7f18482c2682c91b6f09988e198564d72`.
- Sample tuples, canonical report JSON, and both hashes match exactly.
- Threshold: bitwise equality in one process. Basis: mathematical.
- Result: **PASS**. This does not require bitwise equality between Python
  3.10 and 3.11. Those jobs must each pass the analytic, normalized-error,
  invariant, and fail-closed gates on their own.

## Known numerical limitations

- Case D orders near 5 are fixture measurements under a binding `max_step`.
  They are not a general RK45 order certificate.
- When `max_step` binds, tightening `rtol` or `atol` does not move the
  accepted steps. Normalized `e` can then exceed 1 because the scale
  shrinks. ID 08 is characterization only. ID 05 is the acceptance run for
  Case D.
- Roundoff fallback cannot override a failed resolvable refinement.
- Near the point-mass pivot, ID 01 shows a forward gap of about `1.7e-5`
  while the backward error stays near roundoff.
- The source-bound sample-maximum for `theta` is not monotone on the last
  ODE halving. Endpoint errors are monotone, and the final normalized errors
  are far below 1.
- Contact-time error is already at a few ulps, so further step refinement
  does not produce a smaller monotone sequence.
- ID 14 is characterization only. The annulus result is a synthetic midpoint
  comparison. It is not a mesh certificate for a real propeller and not
  general BEM verification.
- DOP853 checks time integration of the declared right-hand side. It does
  not create aerodynamic hinge loads, calibration, or experimental validity.
