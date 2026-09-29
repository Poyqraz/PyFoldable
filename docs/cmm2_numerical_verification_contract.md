# CMM-2 PR-C numerical verification contract

Status: PROPOSED / CONTRACT UNDER INDEPENDENT REVIEW.

Exact design base: `f739ded3d712e42b61a47bf5ef4170c7dfdb7ea8`.

PR-C implementation: NOT STARTED.

`physical_qualification`: false.

This document freezes the verification claims for the declared CMM-2 screening
model. It does not record evidence. No case below has a measured PASS. A
future ADR-009 may accept independent numerical verification of that screening
software model after implementation, exact-head CI, independent review, and
evidence closure. ADR-009 is not created and is not accepted here.

## 1. Scope

PR-C verifies the numerical implementation of the already accepted CMM-2
screening model: the paired-load mass matrix and right-hand side, the
integrator trajectory, first-contact termination, fail-closed domain behavior,
and one real source-bound join of PR-07, FoldableBEM, and the accepted planar
map.

The model under verification is `coupled_aero_hinge_screening_only`,
implementation id `cmm2_planar_projected_rate_independent_coupling_v1`.
Dynamics contract: [CMM-2 PR-A](cmm2_coupled_transient_contract.md).
Source binding: [CMM-2 PR-B](cmm2_source_bound_production_binding.md).

## 2. Mathematical model under verification

State order is `(theta, theta_dot, omega)`. Acceleration order is
`(omega_dot, theta_ddot)`.

```text
C = m R c
A = J + m R^2 + 2 C cos(theta)
B = J + C cos(theta)

M(theta) = [[I0 + N A, N B],
            [N B,      N J]]
```

Shaft row:

```text
Qm + Q_phi + N C sin(theta) (2 omega theta_dot + theta_dot^2)
```

Hinge row:

```text
N [
    Qh
    + q_theta
    - k (theta - theta_rest)
    - b theta_dot
    - tau_c tanh(theta_dot / v)
    - C omega^2 sin(theta)
]
```

`Q_phi` is the signed whole-rotor aerodynamic shaft generalized load. It is
not multiplied by `N` again. `q_theta` is the signed one-tip aerodynamic hinge
generalized load. The collective hinge row multiplies it by `N` exactly once.
Raw positive BEM resisting torque is not `Q_phi`.

Mechanical energy keeps the inherited definition. Kinetic energy uses the
represented mass matrix:

```text
T = 0.5 M00 omega^2 + M01 omega theta_dot + 0.5 M11 theta_dot^2
E = T + 0.5 N k (theta - theta_rest)^2
```

Instantaneous generalized-work identity:

```text
E_dot = Qm omega + Q_phi omega + N q_theta theta_dot
        + N Qh theta_dot - N b theta_dot^2
        - N tau_c theta_dot tanh(theta_dot / v)
```

Spring storage is inside `E`. Net gyroscopic and centrifugal power cancels
when the generalized equations are combined. Aerodynamic power
`Q_phi omega + N q_theta theta_dot` is counted once inside `E_dot`. There is
no battery-energy conservation claim.

## 3. Explicit non-goals

PR-C does not establish physical qualification, dynamic-stall or finite-rate
aerodynamic validity, PR-06C closure, GEOM qualification, calibration,
experimental correlation, design readiness, or dashboard completion.
`physical_qualification` stays false. The three clearance fields stay null.

It does not verify impact, bounce, or latch continuation. It does not
transfer CMM-1 Phase-4 status into CMM-2. It does not reopen ADR-006, ADR-007,
or ADR-008. It does not change equations or production behavior in order to
obtain a pass.

## 4. Accepted dependency boundary

PR-C may rely on these accepted layers without re-proving each of them:

- ADR-006 / PR #74 planar load map
- ADR-007 / PR-A dynamics contract
- ADR-008 / PR-B source-bound binding
- PR-07 motor algebra where the production path reuses it
- FoldableBEM under its accepted repository contracts
- CMM-1 numerical helpers that CMM-2 explicitly inherits, including the
  represented mass matrix, mechanical energy, dense-quartic audit, and
  first-contact reconstruction

An accepted dependency is not an independent PR-C oracle. Calling the same
production helper twice does not create independence.

## 5. Oracle-independence rules

An independent oracle assembles the quantities it claims to check with
test-owned arithmetic.

Forbidden as an independent equation oracle:

- `cmm2_coupled_accelerations`
- the production CMM-2 Schur solve
- the PR-B private request builder

A second integrator that still calls `cmm2_coupled_accelerations` is only a
secondary integration-only characterization. It is not the equation oracle.

Production `cumulative_work_j` is diagnostic. It is not the independent
integration oracle for energy.

## 6. Verification evidence classes

Primary classes, with no aggregate score:

- `MATHEMATICAL`
- `INDEPENDENT_NUMERICAL`
- `CROSS_MODEL`
- `PRODUCTION_PATH`
- `REGRESSION_CONTRACT`
- `EMPIRICAL_CHARACTERIZATION`

A failure in a merge-critical mathematical or numerical layer is not
compensated by another layer passing.

## 7. Normative critical matrix

These identities are merge-critical. None has been executed under this
contract.

### C2V-01 — matrix and paired-load algebra

Purpose: show that the represented `M` and both right-hand sides use `Q_phi`
and `q_theta` with the declared `N` accounting.

Features: `N` in `{1, 2, 4}`, nonzero off-diagonal coupling, both load signs,
and a state at which `q_theta` is not structurally zero.

Oracle class: `MATHEMATICAL`.

Independence: the reference matrix and right-hand side are assembled outside
the production acceleration function. Before the fixture is evidence, the
independently predicted gap between the correct output and each mutant must
exceed the documented numerical-uncertainty envelope.

Required metrics: represented matrix entries, both right-hand sides, and the
correct-versus-mutant gaps.

Acceptance basis: exact agreement with the section 2 equations, plus the
mutation-discrimination rule below. The forward-error envelope is Q2 and is
not closed by a small residual.

Failure modes: `Q_phi` multiplied by `N`; missing collective `N` on
`q_theta`; `N q_theta` supplied as the one-tip input; `q_theta` sign
reversal; raw positive resisting torque substituted for signed `Q_phi`.

Limitations: this case does not integrate a trajectory and does not qualify
FoldableBEM.

### C2V-02 — nonzero-load exact equilibrium

Purpose: a manufactured equilibrium with nonzero paired loads has zero
accelerations.

Features: nonzero `Q_phi` and `q_theta`, with spring, damping, friction, and
motor terms balanced by test-owned arithmetic.

Oracle class: `INDEPENDENT_NUMERICAL`.

Independence: the balancing loads are solved from the target equations, not
by calling the production acceleration function and negating its residual.

Required metrics: both accelerations.

Acceptance basis: accelerations match the independent zero prediction inside
the section 9 policy.

Failure modes: a dropped load, a doubled `N`, or a sign error that leaves a
nonzero acceleration.

Limitations: one equilibrium does not verify transient coupling.

### C2V-03 — genuinely coupled manufactured trajectory

Purpose: a prescribed `theta(t)` and `omega(t)` with resolvable coupling.

Features: resolvable nonzero `C`, `theta_dot`, `omega_dot`, `theta_ddot`,
`Q_phi`, `q_theta`, and spring or damping where the manufactured solution
uses them.

Oracle class: `INDEPENDENT_NUMERICAL`.

Independence: `Q_phi(t)` and `q_theta(t)` are solved from the target
equations with test-owned arithmetic. They are not taken from
`cmm2_coupled_accelerations`. `Cmm2AeroEvaluation` metadata may name the
queried state. The force law itself stays independently prescribed.

Required metrics: `theta`, `theta_dot`, and `omega` against the prescribed
trajectories.

Acceptance basis: section 9, after the reference uncertainty budget is met.

Failure modes: ignored hinge load, missing `N`, or a trajectory that only
exercises a zero-rate or zero-load reduction.

Limitations: a manufactured force is not the planar-map law. That law is
C2V-09.

### C2V-04 — independent work and energy balance

Purpose: separate instantaneous work identity and integrated energy balance.

Features: the independent reference includes `Q_phi omega`,
`N q_theta theta_dot`, `N Qh theta_dot`, the declared dissipation, and spring
storage through `E`.

Oracle class: `INDEPENDENT_NUMERICAL`.

Independence: the reference integrates its own power. Production
`cumulative_work_j` is not the oracle.

Required metrics: instantaneous `E_dot` residual and integrated
`E(t) - E(t0) - integral(E_dot)`.

Acceptance basis: section 9 on those residuals. No battery-energy claim.

Failure modes: aerodynamic power omitted, counted twice, or taken from the
production diagnostic.

Limitations: cancellation of gyroscopic power is part of the identity, not a
separate physical conservation law.

### C2V-05 — nonlinear independent-integrator comparison

Purpose: compare the production trajectory with a separately assembled
right-hand side advanced by DOP853, or by another integrator whose
independence is justified in the evidence.

Oracle class: `INDEPENDENT_NUMERICAL`.

Independence: the reference right-hand side is not
`cmm2_coupled_accelerations`. A DOP853 run that calls that function is
secondary characterization only.

Required metrics: state error and a recorded reference-stabilization check.

Acceptance basis: the reference is shown stable before comparison. Production
comparison then uses section 9.

Failure modes: an unstabilized reference, or an oracle that reuses the
production acceleration.

Limitations: agreement of two integrators on a wrong shared right-hand side
is not this case.

### C2V-06 — zero-hinge CMM-1 cross-model limit

Purpose: at `q_theta = 0` and `Q_phi = -Qa`, the represented CMM-1 and CMM-2
mass matrix and right-hand side coincide for the same state, system, motor,
and actuation. `Qa` is CMM-1's positive resisting shaft aerodynamic torque.

Oracle class: `CROSS_MODEL`.

Independence: both represented equations are assembled for the comparison.
The case does not call one solver and treat its output as the other model's
proof.

Required metrics: matrix entries and both right-hand sides.

Acceptance basis: exact cross-model equality of those represented equations
inside the documented roundoff rule. This does not transfer CMM-1 Phase-4
status. The prior 21,062-state characterization is not repeated unless a new
verification need is independently justified.

Failure modes: a residual hinge load, or `Q_phi` left as positive resisting
torque.

Limitations: a cross-model invariant is not a CMM-2 trajectory certificate.

### C2V-07 — analytic first-contact timing

Purpose: one manufactured transverse first stop crossing with an analytic
first-hit time.

Features: first stop identity, contact time, pre-impact hinge rate, shaft
speed, terminal behavior, and no samples after contact.

Oracle class: `INDEPENDENT_NUMERICAL`.

Independence: the hit time is analytic. The allowance is the independently
bounded angle error divided by a strictly positive crossing-speed lower
bound, plus root-reconstruction roundoff.

Required metrics: stop identity, time error, pre-impact rates, and the sample
bound.

Acceptance basis: time error inside that allowance, and termination at first
contact.

Failure modes: the wrong stop, a late or early hit outside the allowance, or
a continued sample after contact.

Limitations: impact, bounce, and latch continuation are out of scope.

### C2V-08 — representative fail-closed numerical boundary

Purpose: show that CMM-2 fails closed on representative exits.

Features: fold-domain exit, the 100 rpm lower-bound exit, one work-budget or
right-hand-side budget exhaustion, and one hard failure.

Oracle class: `REGRESSION_CONTRACT`.

Independence: shared dense-quartic isolation remains a CMM-1 dependency.
PR-C shows that CMM-2 invokes fail-closed behavior. It does not reimplement
the CMM-1 proof and does not repeat every lower-layer exception test.

Required metrics: exception class, absence of a success artifact, and absence
of a shortened successful trajectory.

Acceptance basis: each listed exit fails closed.

Failure modes: a partial success, a zero-load substitution, or a continued
integration outside the domain.

Limitations: this is not a catalogue of BEM, polar, or motor exceptions.

### C2V-09 — real source-bound trajectory

Purpose: one trajectory of the sealed PR-B path with the real
`Pr07MotorEvaluator`, FoldableBEM, and the accepted PR #74 planar map.

Oracle class: `PRODUCTION_PATH` for the join, with an `INDEPENDENT_NUMERICAL`
right-hand side for the trajectory comparison.

Independence: the reference may consume the same sealed mechanical
parameters. It assembles `M` and the right-hand side itself. It does not call
`cmm2_coupled_accelerations`, the production Schur solve, or the PR-B private
request builder as the equation oracle. Draft parsing and PR-B binding are
not reimplemented. This case does not reopen ADR-008.

Required metrics: state error against the independent reference, plus the
preflight load and same-state checks in sections 10 and the fixture rule
below.

Acceptance basis: section 9, only after the fixture rule and the same-state
preflight both hold.

Failure modes: invisible `q_theta` or hinge work, an ID-dependent numerical
load, or a fixture chosen after inspecting trajectory error.

Limitations: one fixture does not qualify the rotor, the map, or the motor.

### C2V-10 — piecewise actuation and knots

Purpose: actuation that changes across a knot is applied on the correct side
of the knot, without changing the paired-load equations.

Oracle class: `INDEPENDENT_NUMERICAL`.

Independence: expected hinge torque on each piece is the declared history,
not a value read back from a production diagnostic and then reused as the
reference.

Required metrics: applied `Qh` immediately on each side of the knot, and
state continuity at the knot.

Acceptance basis: the independent piece values, and section 9 on the state.

Failure modes: a knot skipped, interpolated across a declared discontinuity,
or used to alter `N` accounting.

Limitations: knot handling inherited from CMM-1 is not re-proved in full.

### C2V-01 mutation discrimination

The case must include all five mutants listed under C2V-01. For each mutant,
the independently predicted output difference is computed before the fixture
is accepted as evidence. That difference must exceed the documented
numerical-uncertainty envelope. A mutant that the envelope cannot see is not
evidence.

### C2V-09 fixture-selection rule

Select the fixture before any production trajectory acceptance metric is
computed. The rule uses only the sealed source identity and a single
pre-trajectory evaluation at the initial state:

- the fold angle is interior: a declared margin inside `(-pi/2, pi/2)` and
  away from the deployed angle
- shaft speed is a declared margin above 100 rpm
- that evaluation has nonzero `Q_phi`, resolvable nonzero `q_theta`, nonzero
  `theta_dot`, and a resolvable `N q_theta theta_dot` term
- the initial projected radius is a declared distance away from a hinge-cell
  boundary and from a radial midpoint partition boundary
- the sealed request digest and the selection record are written before the
  trajectory run

If that predeclared fixture does not provide observable `q_theta` or
aerodynamic hinge work, the contract is blocked and returns to independent
review. Another fixture is not substituted. A cheaper fixture is not
acceptable when `q_theta` or aerodynamic hinge work is numerically invisible.
The fixture is not chosen because its trajectory error is convenient.

### Same-state source invariance preflight

Before C2V-09 is evidence, identical physical and numerical BEM inputs with
changed evaluation-indexed metadata or state identifiers must leave numerical
thrust, `Q_phi`, and `q_theta` unchanged. Identifiers and ledger sequence may
differ. If a numerical load depends on an evaluation identifier, stop. That
is a production defect or a contract issue. PR-C is not adapted around it.

## 8. Characterization-only matrix

### C2V-11 — solver-setting sensitivity

Purpose: record how the trajectory moves when tolerance or maximum step
changes.

Oracle class: `EMPIRICAL_CHARACTERIZATION`.

Classification: `CHARACTERIZATION ONLY`.

This case does not certify global RK order or monotonic convergence. No
decreasing-difference gate is added.

### C2V-12 — BEM annulus and spatial sensitivity

Purpose: record how the source-bound loads move under a modest annulus or
spatial sweep.

Oracle class: `EMPIRICAL_CHARACTERIZATION`.

Classification: `CHARACTERIZATION ONLY`.

This case does not certify rotor accuracy or physical validity. No arbitrary
decreasing-difference gate is added.

## 9. Numerical acceptance policy

For a reference component `y*_j` and a production component `y_j`:

```text
S_j(t) = atol_j + rtol * abs(y*_j(t))
e_j = abs(y_j - y*_j) / S_j
```

Component order is `theta`, `theta_dot`, `omega`. The absolute tolerances are
the case's declared `angle_atol_rad`, `hinge_velocity_atol_rad_s`, and
`shaft_speed_atol_rad_s`. `rtol` is the case's declared solver relative
tolerance. Those controls are recorded before the run.

For merge-critical trajectory fixtures, `max e_j <= 1` for every state
component. Independent reference uncertainty and stabilization consume no more
than `0.1 S_j` at every production sample time.

These are PR-C numerical acceptance policies for the selected evidence
domain. They are not a theorem or a global-error guarantee of RK45. They are
not inherited automatically from CMM-1. These values are frozen by this
contract before PR-C result tuning. Measured compliance is not claimed.

Q1 remains open until independent review confirms this policy. Implementation
must not replace it with a threshold chosen after seeing results.

### C2V-01 conditioning policy

Do not use a fixed absolute forward-error tolerance near a difficult pivot.
The case must:

- assemble the represented `M` and right-hand side independently
- solve with high-precision `Decimal` or direct determinant arithmetic
- compute row backward errors
- report a matrix condition estimate
- derive the allowed forward-error envelope from represented arithmetic and
  that conditioning

The exact conditioning-aware bound is pre-implementation contract question Q2.
It is not closed in this document, because closing it here would require
fitting a production result. A small residual is not proof of a small forward
error.

## 10. Source-bound reference policy

Covered by C2V-09, the fixture-selection rule, and the same-state preflight.
The production path remains the PR-B service. The independent reference
checks the numerical trajectory of that sealed run. It does not become a
second binder.

## 11. Failure and domain policy

Covered by C2V-08. Accepted successful endings remain `completed` and
`first_contact_terminal`. Domain exit, unresolved audit, unresolved mass,
residual failure, nonfinite power, and budget exhaustion do not return a
shortened success.

## 12. Evidence artifact contract

A future implementation emits structured finite JSON. It does not write an
external database. Conceptual fields:

- repository head
- `case_id`
- primary evidence class
- purpose
- fixture identity and digest
- model identifiers
- dependency identifiers
- oracle method
- independence limit
- controls
- metrics with units
- component order
- reference stabilization
- acceptance rule
- threshold basis
- classification
- limitations

Classification is `PASS`, `FAIL`, or `CHARACTERIZATION ONLY`. There is no
aggregate score. This contract does not contain those artifacts.

## 13. CI and runtime policy

Normative intent, not a measured budget:

- C2V-01 through C2V-08 and C2V-10: fast or moderate CI
- C2V-09: one bounded real source-bound fixture in ordinary CI
- C2V-11: bounded characterization
- C2V-12: a modest sweep in ordinary CI only if measured cost is acceptable; a
  broader sweep may be separately reproducible characterization

Q5 measures that cost before the ordinary-CI boundary for the spatial sweep
is decided. Cost is not a reason to hide `q_theta`.

## 14. Open contract questions

These block implementation acceptance. They are not silent tasks, and they
are not replaced by a convenient post-result threshold.

Q1. Confirm the componentwise `max e_j <= 1` policy and the `0.1 S_j`
independent-reference budget.

Q2. Close the C2V-01 conditioning-aware forward-error envelope.

Q3. Freeze the deterministic C2V-09 fixture-selection rule before observing
acceptance trajectory metrics. The rule in section 7 is the proposal.

Q4. Confirm same-state numerical load invariance under evaluation-indexed
identifiers.

Q5. Measure expected C2V-09 and C2V-12 execution cost before deciding the
ordinary-CI boundary for the spatial sweep.

## 15. Implementation boundary

Implementation has not started. This pull request adds no test, fixture, or
production change. Expected production-code changes for the later
implementation are none. If rigorous verification needs a production change,
stop and report the missing observability or defect separately. Do not change
equations to obtain a pass.

## 16. Acceptance boundary

Review of this contract is not verification acceptance. Passing tests do not
yet exist. ADR-009 stays future language. `physical_qualification` stays
false. PR-06C stays unresolved. No GEOM gate is promoted. There is no
calibration and no experimental validation.

Dynamics contract link:
[CMM-2 PR-A](cmm2_coupled_transient_contract.md).
